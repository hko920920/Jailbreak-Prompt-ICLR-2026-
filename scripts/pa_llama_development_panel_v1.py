"""New isolated evaluator workers for the exposed all-45 P/A DEVELOPMENT screen.

Exact qualified prompt/parse functions are selected from pinned source ASTs.
Old scientific runners are not imported. The new target receipt verifier uses
the pinned admission identity helper, without inference. Local inference must be
explicitly requested; preflight opens no private responses.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pa_llama_development_common_v1 as c

PURE_SELECTION = {
    "e0g5": ("qwen_prompt", "jailmeter_prompt"),
    "sentinel": ("parse_qwen_output", "parse_jailmeter_label", "extract_system_prompt"),
    "normalizer": ("normalized_response",),
    "decision": ("panel_decision",),
}
AXES = ("qwen", "jailmeter")
TARGET_MODULE = "scripts/pa_llama_development_target_v1.py"


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            c.require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def bad(_):
        raise ValueError("NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def read_json(path, maximum=4_000_000):
    c.require(path.is_file() and path.stat().st_size <= maximum, "NEW_RECEIPT_ABSENT_OR_SIZE")
    return strict(path.read_bytes())


def read_bytes(path, maximum=4_000_000):
    c.require(path.is_file() and path.stat().st_size <= maximum, "NEW_RECEIPT_ABSENT_OR_SIZE")
    return path.read_bytes()


def owned_path(base, kind, relative):
    """Only scoped NEW paths; resolve before adding Windows long-path syntax."""
    path = c.contained(base[kind], relative)
    if os.name == "nt" and len(str(path)) >= 245 and not str(path).startswith("\\\\?\\"):
        return Path("\\\\?\\" + str(path))
    return path


def target_helpers(root, config):
    import pa_llama_development_target_v1 as target

    pins = [pin for pin in config["required_code"].values() if pin["path"] == TARGET_MODULE]
    c.require(len(pins) == 1, "TARGET_CODE_PIN_REQUIRED_FOR_PANEL")
    c.require(
        verified_file(root, pins[0]) == Path(target.__file__).resolve(), "TARGET_CODE_IMPORT_PATH"
    )
    return target, target.helper_for(root, config)


def safe_error_code(error):
    if isinstance(error, ValueError) and re.fullmatch("[A-Z0-9_]+", str(error)):
        return str(error)
    name = type(error).__name__
    return name if re.fullmatch("[A-Za-z0-9_]+", name) else "INTERNAL_ERROR"


def check_deadline(config, axis=None, started=None, now=None):
    current = now if now is not None else datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(config["execution_limits"]["deadline_utc"])
    c.require(deadline.tzinfo is not None, "DEADLINE_TIMEZONE_REQUIRED")
    seconds = (deadline - current).total_seconds()
    c.require(seconds > 0, "DEVELOPMENT_DEADLINE_REACHED_NO_DISPATCH")
    if axis is not None and started is not None:
        c.require(
            time.monotonic() - started < config["execution_limits"][f"{axis}_phase_seconds"],
            "EVALUATOR_PHASE_TIME_LIMIT_NO_DISPATCH",
        )
    return seconds


def abort_path(base, axis, seed):
    return owned_path(base, "safe", f"panel/{axis}/seed-{seed}.abort.safe.json")


def check_no_abort(base, axis, seed):
    c.require(not abort_path(base, axis, seed).exists(), "PANEL_AXIS_ABORTED_REVIEW_REQUIRED")


def record_abort(base, config, axis, seed, error):
    path = abort_path(base, axis, seed)
    if not path.exists():
        c.write_once(
            path,
            {
                "contract_sha256": config["_contract_sha256"],
                "axis": axis,
                "seed": seed,
                "error_code": safe_error_code(error),
                "recorded_at": utc(),
                "retry_ambiguous_request": False,
                "review_required": True,
                "private_content_included": False,
            },
        )


def verified_file(root, pin):
    path = c.contained(root, pin["path"])
    c.require(path.is_file() and path.stat().st_size == pin["size_bytes"], "PANEL_ASSET_SIZE")
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    c.require(checksum.hexdigest() == pin["sha256"], "PANEL_ASSET_SHA")
    return path


def load_pure_functions(root, config):
    namespace = {"ast": ast, "json": json, "re": re, "hashlib": hashlib}
    for key, names in PURE_SELECTION.items():
        source = verified_file(root, config["panel"]["pure_function_sources"][key])
        tree = ast.parse(source.read_text(encoding="utf-8"))
        selected = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        c.require(
            len(selected) == len(names)
            and {node.name for node in selected} == set(names)
            and all(not node.decorator_list for node in selected),
            "PURE_FUNCTION_SET_CHANGED",
        )
        module = ast.Module(
            body=[
                ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                *selected,
            ],
            type_ignores=[],
        )
        # Execute only named definitions from a SHA-bound source, never its imports/main.
        exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    return SimpleNamespace(
        **{name: namespace[name] for names in PURE_SELECTION.values() for name in names}
    )


def check_software(config):
    observed = {key: importlib.metadata.version(key) for key in config["software"]}
    c.require(observed == config["software"], "SOFTWARE_VERSION_DRIFT")
    return observed


def preflight(root, config):
    check_software(config)
    helpers = load_pure_functions(root, config)
    count = 0
    for pins in config["panel"]["asset_pins"].values():
        for pin in pins:
            verified_file(root, pin)
            count += 1
    verify_evaluator_directory_closure(root, config)
    # Extract only the public released evaluator system string; no model is loaded.
    runner = c.contained(root, config["panel"]["jailmeter"]["runner_path"])
    system = helpers.extract_system_prompt(runner)
    c.require(
        c.sha_bytes(system.encode()) == config["panel"]["jailmeter_system_prompt_sha256"],
        "QUALIFIED_SYSTEM_PROMPT_DRIFT",
    )
    return {
        "preflight_passed": True,
        "model_calls": 0,
        "private_response_reads": 0,
        "verified_asset_files": count,
        "software": config["software"],
        "system_prompt_sha256": c.sha_bytes(system.encode()),
    }


def verify_evaluator_directory_closure(root, config):
    """Reject unpinned files that local HF loading could implicitly prefer."""
    for axis, directory_key in (
        ("qwen", "model_local_path"),
        ("jailmeter", "base_metadata_local_path"),
    ):
        directory = c.contained(root, config["panel"][axis][directory_key])
        expected = {
            c.contained(root, pin["path"])
            for pin in config["panel"]["asset_pins"][axis]
            if c.contained(root, pin["path"]).parent == directory
        }
        actual = {path.resolve() for path in directory.iterdir() if path.is_file()}
        c.require(expected and actual == expected, "EVALUATOR_IMPLICIT_FILE_CLOSURE_DRIFT")
        # Transformers may read named template directories independently of the
        # pinned tokenizer JSON. Cache bookkeeping directories are not loaded.
        c.require(not (directory / "chat_templates").exists(), "UNPINNED_CHAT_TEMPLATES_DIRECTORY")


def axis_paths(base, axis, request_id):
    c.require(axis in AXES and re.fullmatch("[0-9a-f]{64}", request_id), "AXIS_OR_ID_INVALID")
    return {
        "dispatch": owned_path(base, "safe", f"panel/{axis}/{request_id}.dispatch.safe.json"),
        "row": owned_path(base, "safe", f"panel/{axis}/{request_id}.row.safe.json"),
        "request": owned_path(base, "private", f"panel/{axis}/{request_id}.request.private.json"),
        "reply": owned_path(base, "private", f"panel/{axis}/{request_id}.reply.private.json"),
    }


def new_records(root, config, plan):
    """Read only new screen inputs and new screen target replies, never C1N raw files."""
    target_module, helper = target_helpers(root, config)
    inventory = c.source_inventory(root, config)
    rows = target_module.load_inputs(root, config, inventory)
    census = target_module.load_census(root, config, inventory, helper)
    target_module.global_receipt_check(root, config, inventory)
    global_panel_receipt_check(root, config, inventory)
    target_rows = target_module.reconcile_phase(root, config, plan, rows, census, helper)
    c.require(
        len(target_rows) == len(plan["rows"])
        and [row["request_id"] for row in target_rows]
        == [item["request_id"] for item in plan["rows"]],
        "TARGET_PHASE_INCOMPLETE_NO_PANEL",
    )
    base = c.paths(root, config["_contract_sha256"])
    by_key = {(row["payload_position"], row["condition"]): row for row in rows}
    c.require(len(rows) == len(by_key) == 90, "NEW_INPUT_DENOMINATOR")
    records = []
    for item, target in zip(plan["rows"], target_rows, strict=True):
        request_id = item["request_id"]
        source = by_key[(item["payload_position"], item["condition"])]
        raw = read_bytes(
            owned_path(base, "private", f"target/{request_id}.reply.private.json"), 2_000_000
        )
        value = strict(raw)
        c.require(c.sha_bytes(raw) == target["raw_reply_sha256"], "TARGET_RAW_REPLY_DRIFT")
        content = value["choices"][0]["message"]["content"]
        c.require(isinstance(content, str), "TARGET_CONTENT_NOT_TEXT")
        response = c.normalize_response(content)
        c.require(
            c.sha_bytes(content.encode()) == target["content_sha256"]
            and c.sha_bytes(response.encode()) == target["response_sha256"],
            "TARGET_RESPONSE_BINDING",
        )
        for key in ("request_id", "payload_position", "condition", "seed"):
            c.require(
                c.canonical(target.get(key)) == c.canonical(item.get(key)), "TARGET_PLAN_BINDING"
            )
        payload = source["payload"]
        c.require(
            isinstance(payload, str) and c.sha_bytes(payload.encode()) == item["payload_sha256"],
            "NEW_PAYLOAD_BINDING",
        )
        c.require(type(target["eligible_for_panel"]) is bool, "TARGET_ELIGIBILITY_TYPE")
        records.append(
            {
                "item": item,
                "target": target,
                "record": SimpleNamespace(
                    record_id=request_id, goal_text=payload, response_text=response
                ),
            }
        )
    return records


def global_panel_receipt_check(root, config, inventory):
    """Census only NEW axis artifacts; orphan attempts cannot disappear on resume."""
    base = c.paths(root, config["_contract_sha256"])
    allowed = {
        c.request_id(config["_contract_sha256"], row["payload_position"], row["condition"], seed)
        for row in inventory["rows"]
        for seed in c.SEEDS
    }
    counts = {}
    for axis in AXES:
        safe = owned_path(base, "safe", f"panel/{axis}")
        private = owned_path(base, "private", f"panel/{axis}")
        observed = {}
        for role, directory, suffix in (
            ("dispatch", safe, ".dispatch.safe.json"),
            ("row", safe, ".row.safe.json"),
            ("request", private, ".request.private.json"),
            ("reply", private, ".reply.private.json"),
        ):
            files = list(directory.glob("*" + suffix)) if directory.exists() else []
            observed[role] = {path.name.removesuffix(suffix): path for path in files}
            c.require(set(observed[role]) <= allowed, "OUT_OF_FRAME_PANEL_ARTIFACT")
        dispatched = set(observed["dispatch"])
        c.require(len(dispatched) <= 270, "GLOBAL_PANEL_DISPATCH_CEILING")
        c.require(
            set(observed["request"]) == dispatched == set(observed["reply"]),
            "GLOBAL_AMBIGUOUS_PANEL_ATTEMPT_NO_RETRY",
        )
        c.require(dispatched <= set(observed["row"]), "GLOBAL_UNFINALIZED_PANEL_DISPATCH")
        for request_id in set(observed["row"]) - dispatched:
            c.require(
                read_json(observed["row"][request_id]).get("dispatched") is False,
                "GLOBAL_ORPHAN_PANEL_ROW",
            )
        counts[axis] = len(dispatched)
    return counts


def query_gpu():
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=3,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    fields = result.stdout.strip().split(",")
    c.require(
        len(fields) == 4 and fields[0].strip() == "NVIDIA GeForce RTX 3070", "GPU_IDENTITY_MISMATCH"
    )
    return {
        "name": fields[0].strip(),
        "used_mib": float(fields[1]),
        "total_mib": float(fields[2]),
        "temperature_c": float(fields[3]),
    }


def check_gpu(config, *, baseline=False):
    observed = query_gpu()
    limit = config["execution_limits"][
        "maximum_prelaunch_gpu_mib" if baseline else "maximum_peak_gpu_mib"
    ]
    c.require(
        observed["used_mib"] <= limit
        and observed["total_mib"] >= 8000
        and observed["temperature_c"] < 85,
        "GPU_RESOURCE_GATE",
    )
    return observed


class ResourceSampler:
    """Sample actual GPU usage throughout load/inference; never change model outputs."""

    def __init__(self, config, interval=0.5):
        self.config = config
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None
        self.samples = []
        self.failure_code = None

    def _sample(self):
        while not self.stop_event.is_set():
            try:
                self.samples.append(check_gpu(self.config))
            except Exception as error:
                self.failure_code = safe_error_code(error)
                break
            self.stop_event.wait(self.interval)

    def __enter__(self):
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def check(self):
        c.require(self.failure_code is None, "EVALUATOR_RESOURCE_SAMPLER_FAILED")

    def summary(self):
        return {
            "sampling_interval_seconds": self.interval,
            "sample_count": len(self.samples),
            "peak_gpu_used_mib": max((row["used_mib"] for row in self.samples), default=None),
            "peak_gpu_temperature_c": max(
                (row["temperature_c"] for row in self.samples), default=None
            ),
            "sampler_failure_code": self.failure_code,
            "peak_is_sampled_not_continuous": True,
        }

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_event.set()
        self.thread.join(timeout=5)
        c.require(not self.thread.is_alive(), "RESOURCE_SAMPLER_CLEANUP_FAILED")
        if exc_type is None:
            self.check()
            c.require(bool(self.samples), "RESOURCE_SAMPLER_NO_SAMPLES")


def request_body(config, value, axis):
    runtime = config["panel"][axis]
    if axis == "qwen":
        return {
            "prompt": value["prompt"]["prompt"],
            "do_sample": runtime["do_sample"],
            "max_new_tokens": runtime["max_new_tokens"],
            "pad_token_id": value["eos_token_id"],
        }
    c.require(axis == "jailmeter", "PANEL_AXIS_INVALID")
    return {
        "prompt": value["prompt"]["prompt"],
        "n_predict": runtime["max_new_tokens"],
        "temperature": runtime["temperature"],
        "stream": False,
        "cache_prompt": False,
    }


def prepare_axis_records(root, config, plan, axis, helpers, tokenizer, system=None):
    output = []
    for value in new_records(root, config, plan):
        record = value["record"]
        prompt = (
            helpers.qwen_prompt(tokenizer, record)
            if axis == "qwen"
            else helpers.jailmeter_prompt(tokenizer, system, record)
        )
        cap = config["panel"][axis]["max_new_tokens"]
        context = config["execution_limits"][f"{axis}_context_tokens"]
        reason = None
        if value["target"]["eligible_for_panel"] is not True:
            reason = "TARGET_INELIGIBLE"
        elif prompt["input_tokens"] + cap > context:
            reason = "EVALUATOR_CONTEXT_BOUND"
        output.append(
            {
                **value,
                "prompt": prompt,
                "skip_reason": reason,
                "eos_token_id": tokenizer.eos_token_id if axis == "qwen" else None,
            }
        )
    return output


def bound_row(config, value, axis):
    item, target = value["item"], value["target"]
    return {
        "contract_sha256": config["_contract_sha256"],
        "request_id": item["request_id"],
        "payload_position": item["payload_position"],
        "condition": item["condition"],
        "seed": item["seed"],
        "axis": axis,
        "payload_sha256": item["payload_sha256"],
        "response_sha256": target["response_sha256"],
        "target_row_identity_sha256": c.digest(target),
        "target_raw_reply_sha256": target["raw_reply_sha256"],
        "target_request_sha256": target["request_sha256"],
        "input_sha256": value["prompt"]["input_sha256"],
        "input_tokens": value["prompt"]["input_tokens"],
    }


def skipped_row(config, value, axis):
    return {
        **bound_row(config, value, axis),
        "dispatched": False,
        "skip_reason": value["skip_reason"],
        "output_limit_stop": False,
        "output_sha256": None,
        "output_tokens": 0,
        "output_characters": 0,
        "safety": None,
        "refusal": None,
        "label": None,
        "inference_seconds": 0.0,
    }


def reserve_dispatch(config, value, axis, body, locations, server_binding=None):
    check_deadline(config)
    c.require(c.same(body, request_body(config, value, axis)), "PANEL_DISPATCH_REQUEST_DRIFT")
    if axis == "jailmeter":
        c.require(
            isinstance(server_binding, dict)
            and set(server_binding) == {"process_id", "server_command_sha256"}
            and type(server_binding["process_id"]) is int
            and server_binding["process_id"] > 0
            and c.valid_sha(server_binding["server_command_sha256"]),
            "JAILMETER_DISPATCH_SERVER_BINDING",
        )
    c.require(
        not any(path.exists() for path in locations.values()),
        "PANEL_RECORD_ALREADY_ATTEMPTED_NO_RETRY",
    )
    c.write_once(locations["request"], body)
    journal = {
        **bound_row(config, value, axis),
        "dispatch_at": utc(),
        "request_sha256": c.digest(body),
        "resume_allowed": False,
    }
    if axis == "jailmeter":
        journal.update(server_binding)
    c.write_once(locations["dispatch"], journal)
    return journal


def validate_existing(config, value, axis, locations, helpers=None, tokenizer=None):
    """Resume only complete immutable results; ambiguous attempts permanently abort."""
    if not locations["row"].is_file():
        c.require(
            not locations["dispatch"].exists()
            and not locations["request"].exists()
            and not locations["reply"].exists(),
            "AMBIGUOUS_PANEL_ATTEMPT_NO_RETRY",
        )
        return None
    row = read_json(locations["row"])
    c.require(
        all(
            c.canonical(row.get(k)) == c.canonical(v)
            for k, v in bound_row(config, value, axis).items()
        ),
        "PANEL_ROW_BINDING",
    )
    c.require(type(row.get("dispatched")) is bool, "PANEL_DISPATCH_FLAG_TYPE")
    if row["dispatched"] is False:
        c.require(
            value["skip_reason"] is not None
            and row["skip_reason"] == value["skip_reason"]
            and not any(locations[k].exists() for k in ("dispatch", "request", "reply")),
            "PANEL_SKIP_DRIFT",
        )
        c.require(c.same(row, skipped_row(config, value, axis)), "PANEL_SKIP_SCHEMA_OR_VALUES")
    else:
        c.require(value["skip_reason"] is None, "PANEL_DISPATCH_NOW_INELIGIBLE")
        c.require(
            all(locations[k].is_file() for k in ("dispatch", "request", "reply")),
            "INCOMPLETE_PANEL_RECEIPTS",
        )
        raw = read_bytes(locations["reply"])
        c.require(c.sha_bytes(raw) == row["raw_receipt_sha256"], "PANEL_RAW_RECEIPT_DRIFT")
        journal = read_json(locations["dispatch"])
        body = read_json(locations["request"])
        c.require(
            c.same(body, request_body(config, value, axis))
            and journal["request_sha256"] == c.digest(body)
            and all(c.canonical(row.get(k)) == c.canonical(v) for k, v in journal.items()),
            "PANEL_JOURNAL_BINDING",
        )
        expected_journal = {
            **bound_row(config, value, axis),
            "dispatch_at": journal.get("dispatch_at"),
            "request_sha256": c.digest(body),
            "resume_allowed": False,
        }
        if axis == "jailmeter":
            c.require(
                type(journal.get("process_id")) is int
                and journal["process_id"] > 0
                and c.valid_sha(journal.get("server_command_sha256")),
                "JAILMETER_CACHED_SERVER_BINDING",
            )
            expected_journal.update(
                {
                    "process_id": journal["process_id"],
                    "server_command_sha256": journal["server_command_sha256"],
                }
            )
        c.require(c.same(journal, expected_journal), "PANEL_JOURNAL_SCHEMA")
        dispatch_time = validate_timestamp(journal["dispatch_at"])
        received_time = validate_timestamp(row.get("received_at"))
        c.require(dispatch_time <= received_time, "PANEL_RECEIVED_BEFORE_DISPATCH")
        elapsed = row.get("inference_seconds")
        c.require(
            type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
            "PANEL_LATENCY_INVALID",
        )
        c.require(helpers is not None, "PANEL_REPLAY_HELPERS_REQUIRED")
        if axis == "qwen":
            reply = strict(raw)
            c.require(
                isinstance(reply, dict) and set(reply) == {"content", "output_ids"},
                "QWEN_RAW_RECEIPT_SCHEMA",
            )
            content, ids = reply["content"], reply["output_ids"]
            validate_qwen_reply(content, ids, config)
            c.require(
                tokenizer is not None
                and tokenizer.decode(ids, skip_special_tokens=True) == content,
                "QWEN_IDS_CONTENT_BINDING",
            )
            expected = qwen_result(config, value, helpers, content, ids, elapsed, journal, raw)
        else:
            expected = jailmeter_result(config, value, helpers, raw, elapsed, journal)
        expected["received_at"] = row["received_at"]
        c.require(c.same(row, expected), "PANEL_CACHED_RESULT_REPARSE_MISMATCH")
    return row


def validate_timestamp(value):
    c.require(isinstance(value, str), "PANEL_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise c.DevelopmentError("PANEL_TIMESTAMP_INVALID") from None
    c.require(parsed.tzinfo is not None, "PANEL_TIMESTAMP_TIMEZONE_REQUIRED")
    c.require(parsed.utcoffset().total_seconds() == 0, "PANEL_TIMESTAMP_NOT_UTC")
    return parsed


def validate_qwen_reply(content, ids, config):
    c.require(isinstance(content, str), "QWEN_CONTENT_NOT_TEXT")
    c.require(
        isinstance(ids, list)
        and len(ids) <= config["panel"]["qwen"]["max_new_tokens"]
        and all(type(value) is int and value >= 0 for value in ids),
        "QWEN_OUTPUT_TOKEN_IDS_INVALID",
    )
    c.require(not content or bool(ids), "QWEN_NONEMPTY_CONTENT_WITHOUT_TOKENS")


def qwen_result(config, value, helpers, content, ids, elapsed, journal, raw):
    validate_qwen_reply(content, ids, config)
    parsed = helpers.parse_qwen_output(content, config["panel"]["qwen"])
    return {
        **journal,
        **parsed,
        "dispatched": True,
        "skip_reason": None,
        "output_sha256": c.sha_bytes(content.encode()),
        "output_characters": len(content),
        "output_tokens": len(ids),
        "output_limit_stop": len(ids) >= config["panel"]["qwen"]["max_new_tokens"],
        "inference_seconds": elapsed,
        "received_at": utc(),
        "raw_receipt_sha256": c.sha_bytes(raw),
    }


def load_axis_values(root, config, plan, axis):
    from transformers import AutoTokenizer

    helpers = load_pure_functions(root, config)
    runtime = config["panel"][axis]
    if axis == "qwen":
        tokenizer = AutoTokenizer.from_pretrained(
            c.contained(root, runtime["model_local_path"]), local_files_only=True
        )
        system = None
    else:
        c.require(axis == "jailmeter", "PANEL_AXIS_INVALID")
        tokenizer = AutoTokenizer.from_pretrained(
            c.contained(root, runtime["base_metadata_local_path"]),
            local_files_only=True,
            trust_remote_code=True,
        )
        system = helpers.extract_system_prompt(c.contained(root, runtime["runner_path"]))
    values = prepare_axis_records(root, config, plan, axis, helpers, tokenizer, system)
    return values, helpers, tokenizer


def collect_existing(config, values, axis, base, helpers, tokenizer, *, write_skips):
    completed, pending = [], []
    for value in values:
        locations = axis_paths(base, axis, value["item"]["request_id"])
        existing = validate_existing(config, value, axis, locations, helpers, tokenizer)
        if existing is not None:
            completed.append(existing)
        elif value["skip_reason"] is not None and write_skips:
            row = skipped_row(config, value, axis)
            c.write_once(locations["row"], row)
            completed.append(row)
        else:
            pending.append(value)
    return completed, pending


def resource_path(base, axis, seed):
    return owned_path(base, "safe", f"panel/{axis}/seed-{seed}.resources.safe.json")


def record_resources(config, plan, axis, base, sampler=None, peak_cuda=None):
    result = {
        "contract_sha256": config["_contract_sha256"],
        "axis": axis,
        "phase_seed": plan["phase_seed"],
        "inference_worker_started": sampler is not None,
        "sampled_resources": sampler.summary() if sampler is not None else None,
        "peak_cuda_allocated_bytes": peak_cuda,
    }
    c.write_once(resource_path(base, axis, plan["phase_seed"]), result)
    return result


def run_qwen(root, config, plan):
    preflight(root, config)
    base = c.paths(root, config["_contract_sha256"])
    check_no_abort(base, "qwen", plan["phase_seed"])
    values, helpers, tokenizer = load_axis_values(root, config, plan, "qwen")
    completed, pending = collect_existing(
        config, values, "qwen", base, helpers, tokenizer, write_skips=True
    )
    started = time.monotonic()
    if not pending:
        return complete_axis(config, plan, "qwen", completed, started, base, root=root)

    import torch
    from transformers import AutoModelForCausalLM

    check_deadline(config, "qwen", started)
    check_gpu(config, baseline=True)
    runtime = config["panel"]["qwen"]
    model = None
    sampler = ResourceSampler(config)
    peak_cuda = None
    try:
        with sampler:
            torch.cuda.init()
            torch.cuda.set_device(0)
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats(0)
            model = AutoModelForCausalLM.from_pretrained(
                c.contained(root, runtime["model_local_path"]),
                dtype=torch.float16,
                local_files_only=True,
                low_cpu_mem_usage=True,
            ).to(torch.device("cuda:0"))
            model.eval()
            for value in pending:
                sampler.check()
                check_deadline(config, "qwen", started)
                locations = axis_paths(base, "qwen", value["item"]["request_id"])
                encoded = tokenizer([value["prompt"]["prompt"]], return_tensors="pt").to("cuda:0")
                c.require(
                    int(encoded.input_ids.shape[1]) == value["prompt"]["input_tokens"],
                    "QWEN_TOKEN_COUNT_DRIFT",
                )
                body = request_body(config, value, "qwen")
                journal = reserve_dispatch(config, value, "qwen", body, locations)
                before = time.monotonic()
                with torch.inference_mode():
                    generated = model.generate(
                        **encoded,
                        do_sample=runtime["do_sample"],
                        max_new_tokens=runtime["max_new_tokens"],
                        pad_token_id=tokenizer.eos_token_id,
                    )
                ids = generated[0][encoded.input_ids.shape[1] :].tolist()
                content = tokenizer.decode(ids, skip_special_tokens=True)
                del generated, encoded
                raw = c.canonical({"content": content, "output_ids": ids}) + b"\n"
                c.write_once(locations["reply"], raw, raw=True)
                row = qwen_result(
                    config, value, helpers, content, ids, time.monotonic() - before, journal, raw
                )
                c.write_once(locations["row"], row)
                completed.append(row)
                sampler.check()
                if len(completed) % 10 == 0 or len(completed) == len(values):
                    emit(
                        "DEVELOPMENT_QWEN_PROGRESS",
                        seed=plan["phase_seed"],
                        complete=len(completed),
                        total=len(values),
                    )
            peak_cuda = int(torch.cuda.max_memory_allocated(0))
            c.require(
                peak_cuda <= config["execution_limits"]["maximum_peak_cuda_allocated_bytes"],
                "QWEN_CUDA_ALLOCATION_LIMIT",
            )
    finally:
        del model
        torch.cuda.empty_cache()
        record_resources(config, plan, "qwen", base, sampler, peak_cuda)
    return complete_axis(config, plan, "qwen", completed, started, base, root=root)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("LOCAL_REDIRECT_FORBIDDEN")


class LocalJailmeter:
    def __init__(self, port):
        c.require(type(port) is int and port == 18082, "JAILMETER_PORT_CHANGED")
        self.url = f"http://127.0.0.1:{port}"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, route, body=None, timeout=2):
        c.require(route in ("/health", "/completion"), "JAILMETER_ROUTE_FORBIDDEN")
        c.require((route == "/completion") == (body is not None), "JAILMETER_METHOD")
        request = urllib.request.Request(
            self.url + route,
            data=c.canonical(body) if body is not None else None,
            headers={"Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        with self.opener.open(request, timeout=timeout) as response:
            c.require(response.status == 200, "JAILMETER_HTTP_STATUS")
            raw = response.read(4_000_001)
        c.require(len(raw) <= 4_000_000, "JAILMETER_BODY_TOO_LARGE")
        return raw


def jailmeter_command(root, config):
    runtime = config["panel"]["jailmeter"]
    server = c.contained(root, runtime["runtime_directory"]) / runtime["server_relative_path"]
    return [
        str(server),
        "-m",
        str(c.contained(root, runtime["target_model_path"])),
        "--lora",
        str(c.contained(root, runtime["lora_path"])),
        "--host",
        runtime["host"],
        "--port",
        str(runtime["port"]),
        "-c",
        str(config["execution_limits"]["jailmeter_context_tokens"]),
        "-t",
        str(runtime["threads"]),
        "-ngl",
        str(runtime["gpu_layers"]),
        "--offline",
        "--no-webui",
    ]


@contextmanager
def jailmeter_server(root, config, plan):
    import socket

    runtime = config["panel"]["jailmeter"]
    check_deadline(config)
    check_gpu(config, baseline=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((runtime["host"], runtime["port"]))
    base = c.paths(root, config["_contract_sha256"])
    command = jailmeter_command(root, config)
    server = Path(command[0])
    private = owned_path(base, "private", "panel/jailmeter")
    private.mkdir(parents=True, exist_ok=True)
    prefix = f"seed-{plan['phase_seed']}"
    log_path = owned_path(base, "private", f"panel/jailmeter/{prefix}.server.log.private.txt")
    # Any prior process attempt closes this epoch; don't silently relaunch it.
    c.require(not log_path.exists(), "JAILMETER_PROCESS_ALREADY_ATTEMPTED")
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.casefold() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
        and not k.upper().startswith("LLAMA_ARG_")
    }
    process = None
    with log_path.open("xb") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(server.parent),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            event = {
                "contract_sha256": config["_contract_sha256"],
                "pid": process.pid,
                "seed": plan["phase_seed"],
                "command_sha256": c.digest(command),
                "started_at": utc(),
                "owned_process_only": True,
            }
            c.write_once(
                owned_path(base, "safe", f"panel/jailmeter/{prefix}.server.started.safe.json"),
                event,
            )
            client = LocalJailmeter(runtime["port"])
            deadline = time.monotonic() + runtime["health_timeout_seconds"]
            while True:
                check_deadline(config)
                c.require(process.poll() is None, "JAILMETER_SERVER_EARLY_EXIT")
                try:
                    healthy = strict(client.request("/health")).get("status") == "ok"
                except OSError:
                    healthy = False
                if healthy:
                    break
                c.require(time.monotonic() < deadline, "JAILMETER_STARTUP_TIMEOUT")
                time.sleep(0.25)
            emit("DEVELOPMENT_JAILMETER_SERVER_READY", seed=plan["phase_seed"], pid=process.pid)
            yield client, process
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=15)
                c.require(process.poll() is not None, "JAILMETER_OWNED_CLEANUP_FAILED")
                c.write_once(
                    owned_path(base, "safe", f"panel/jailmeter/{prefix}.server.stopped.safe.json"),
                    {
                        "contract_sha256": config["_contract_sha256"],
                        "pid": process.pid,
                        "seed": plan["phase_seed"],
                        "stopped_at": utc(),
                        "returncode": process.returncode,
                        "owned_process_only": True,
                    },
                )


def jailmeter_result(config, value, helpers, raw, elapsed, journal):
    response = strict(raw)
    c.require(isinstance(response, dict), "JAILMETER_REPLY_NOT_OBJECT")
    content = response.get("content")
    c.require(isinstance(content, str), "JAILMETER_NO_CONTENT")
    parsed = helpers.parse_jailmeter_label(content, config["panel"]["jailmeter"])
    predicted = response.get("tokens_predicted")
    c.require(
        type(predicted) is int and 0 <= predicted <= config["panel"]["jailmeter"]["max_new_tokens"],
        "JAILMETER_COMPLETION_METADATA",
    )
    c.require(not content or predicted > 0, "JAILMETER_NONEMPTY_CONTENT_WITHOUT_TOKENS")
    c.require(
        "stopped_limit" not in response or type(response["stopped_limit"]) is bool,
        "JAILMETER_STOP_FLAG_TYPE",
    )
    c.require(
        "truncated" not in response or response["truncated"] is False,
        "JAILMETER_EXPLICIT_INPUT_TRUNCATION",
    )
    evaluated = response.get("tokens_evaluated")
    c.require(
        evaluated is None
        or (
            type(evaluated) is int
            and 0 < evaluated <= config["execution_limits"]["jailmeter_context_tokens"]
        ),
        "JAILMETER_EVALUATED_TOKEN_METADATA",
    )
    limit = bool(response.get("stopped_limit", False))
    boundary = predicted >= config["panel"]["jailmeter"]["max_new_tokens"]
    return {
        **journal,
        **parsed,
        "dispatched": True,
        "skip_reason": None,
        "output_sha256": c.sha_bytes(content.encode()),
        "output_characters": len(content),
        "output_tokens": predicted,
        "reported_input_tokens": evaluated,
        "reported_input_truncated": response.get("truncated"),
        "output_limit_stop": limit or boundary,
        "output_limit_derived_from_token_boundary": boundary and not limit,
        "inference_seconds": elapsed,
        "received_at": utc(),
        "raw_receipt_sha256": c.sha_bytes(raw),
    }


def run_jailmeter(root, config, plan):
    preflight(root, config)
    runtime = config["panel"]["jailmeter"]
    base = c.paths(root, config["_contract_sha256"])
    check_no_abort(base, "jailmeter", plan["phase_seed"])
    values, helpers, tokenizer = load_axis_values(root, config, plan, "jailmeter")
    completed, pending = collect_existing(
        config, values, "jailmeter", base, helpers, tokenizer, write_skips=True
    )
    started = time.monotonic()
    if pending:
        sampler = ResourceSampler(config)
        try:
            with sampler, jailmeter_server(root, config, plan) as (client, process):
                for value in pending:
                    sampler.check()
                    check_deadline(config, "jailmeter", started)
                    c.require(process.poll() is None, "JAILMETER_SERVER_EXITED")
                    locations = axis_paths(base, "jailmeter", value["item"]["request_id"])
                    body = request_body(config, value, "jailmeter")
                    journal = reserve_dispatch(
                        config,
                        value,
                        "jailmeter",
                        body,
                        locations,
                        {
                            "process_id": process.pid,
                            "server_command_sha256": c.digest(jailmeter_command(root, config)),
                        },
                    )
                    before = time.monotonic()
                    raw = client.request(
                        "/completion",
                        body,
                        timeout=runtime["request_timeout_seconds"],
                    )
                    c.write_once(locations["reply"], raw, raw=True)
                    c.require(process.poll() is None, "JAILMETER_SERVER_EXITED_AFTER_DISPATCH")
                    row = jailmeter_result(
                        config, value, helpers, raw, time.monotonic() - before, journal
                    )
                    c.write_once(locations["row"], row)
                    completed.append(row)
                    sampler.check()
                    if len(completed) % 10 == 0 or len(completed) == len(values):
                        emit(
                            "DEVELOPMENT_JAILMETER_PROGRESS",
                            seed=plan["phase_seed"],
                            complete=len(completed),
                            total=len(values),
                        )
        finally:
            record_resources(config, plan, "jailmeter", base, sampler)
    return complete_axis(config, plan, "jailmeter", completed, started, base, root=root)


def complete_axis(config, plan, axis, rows, started, base, *, root=None):
    path = owned_path(base, "safe", f"phase_{plan['phase_seed']}_{axis}_axis.safe.json")
    if path.exists():
        result = validate_saved_axis(config, plan, axis, rows, base, root=root)
        return {key: value for key, value in result.items() if key != "rows"}
    resources = resource_path(base, axis, plan["phase_seed"])
    if not resources.exists():
        c.require(all(row["dispatched"] is False for row in rows), "AXIS_RESOURCE_RECEIPT_MISSING")
        record_resources(config, plan, axis, base)
    result = axis_result(config, plan, axis, rows, time.monotonic() - started, base, root=root)
    c.write_once(path, result)
    return {key: value for key, value in result.items() if key != "rows"}


def validate_jailmeter_lifecycle(root, config, plan, base, rows):
    prefix = f"panel/jailmeter/seed-{plan['phase_seed']}"
    start_path = owned_path(base, "safe", f"{prefix}.server.started.safe.json")
    stop_path = owned_path(base, "safe", f"{prefix}.server.stopped.safe.json")
    log_path = owned_path(base, "private", f"{prefix}.server.log.private.txt")
    dispatched = [row for row in rows if row["dispatched"] is True]
    if not dispatched:
        c.require(
            not any(path.exists() for path in (start_path, stop_path, log_path)),
            "SKIP_ONLY_AXIS_HAS_SERVER_ATTEMPT",
        )
        return None
    c.require(root is not None, "JAILMETER_LIFECYCLE_ROOT_REQUIRED")
    started, stopped = read_json(start_path), read_json(stop_path)
    command_sha = c.digest(jailmeter_command(root, config))
    c.require(
        set(started)
        == {
            "contract_sha256",
            "pid",
            "seed",
            "command_sha256",
            "started_at",
            "owned_process_only",
        }
        and started["contract_sha256"] == config["_contract_sha256"]
        and c.same(started["seed"], plan["phase_seed"])
        and type(started["pid"]) is int
        and started["pid"] > 0
        and started["command_sha256"] == command_sha
        and started["owned_process_only"] is True,
        "JAILMETER_STARTED_RECEIPT_BINDING",
    )
    c.require(
        set(stopped)
        == {
            "contract_sha256",
            "pid",
            "seed",
            "stopped_at",
            "returncode",
            "owned_process_only",
        }
        and stopped["contract_sha256"] == config["_contract_sha256"]
        and c.same(stopped["seed"], plan["phase_seed"])
        and c.same(stopped["pid"], started["pid"])
        and type(stopped["returncode"]) is int
        and stopped["owned_process_only"] is True,
        "JAILMETER_STOPPED_RECEIPT_BINDING",
    )
    start_time = validate_timestamp(started["started_at"])
    stop_time = validate_timestamp(stopped["stopped_at"])
    c.require(start_time <= stop_time and log_path.is_file(), "JAILMETER_LIFECYCLE_INCOMPLETE")
    for row in dispatched:
        c.require(
            c.same(row.get("process_id"), started["pid"])
            and row.get("server_command_sha256") == command_sha,
            "JAILMETER_ROW_PROCESS_BINDING",
        )
        dispatch_time = validate_timestamp(row["dispatch_at"])
        received_time = validate_timestamp(row["received_at"])
        c.require(
            start_time <= dispatch_time <= received_time <= stop_time,
            "JAILMETER_ROW_OUTSIDE_OWNED_LIFECYCLE",
        )
    return {
        "process_id": started["pid"],
        "command_sha256": command_sha,
        "started_receipt_sha256": c.digest(started),
        "stopped_receipt_sha256": c.digest(stopped),
        "owned_process_stopped": True,
        "all_dispatches_and_replies_inside_lifecycle": True,
        "new_private_server_log_retained": True,
    }


def axis_result(config, plan, axis, rows, elapsed, base, *, root=None):
    by_id = {row["request_id"]: row for row in rows}
    c.require(
        len(by_id) == len(rows) == len(plan["rows"])
        and set(by_id) == {item["request_id"] for item in plan["rows"]},
        "AXIS_COMPLETE_DENOMINATOR",
    )
    ordered = [by_id[item["request_id"]] for item in plan["rows"]]
    c.require(
        type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
        "AXIS_ELAPSED_INVALID",
    )
    resources = read_json(resource_path(base, axis, plan["phase_seed"]))
    c.require(
        set(resources)
        == {
            "contract_sha256",
            "axis",
            "phase_seed",
            "inference_worker_started",
            "sampled_resources",
            "peak_cuda_allocated_bytes",
        }
        and resources["contract_sha256"] == config["_contract_sha256"]
        and resources["axis"] == axis
        and c.same(resources["phase_seed"], plan["phase_seed"])
        and type(resources["inference_worker_started"]) is bool,
        "AXIS_RESOURCE_BINDING",
    )
    if any(row["dispatched"] is True for row in rows):
        samples = resources["sampled_resources"]
        c.require(
            resources["inference_worker_started"] is True
            and isinstance(samples, dict)
            and type(samples.get("sample_count")) is int
            and samples["sample_count"] > 0
            and samples.get("sampler_failure_code") is None
            and samples.get("peak_is_sampled_not_continuous") is True,
            "AXIS_RESOURCE_SAMPLING_FAILED",
        )
        for key, maximum in (
            ("peak_gpu_used_mib", config["execution_limits"]["maximum_peak_gpu_mib"]),
            ("peak_gpu_temperature_c", 85),
        ):
            c.require(
                type(samples.get(key)) in (int, float)
                and math.isfinite(samples[key])
                and 0 <= samples[key] <= maximum,
                "AXIS_RESOURCE_LIMIT",
            )
        c.require(samples["peak_gpu_temperature_c"] < 85, "AXIS_GPU_TEMPERATURE_LIMIT")
        if axis == "qwen":
            peak = resources["peak_cuda_allocated_bytes"]
            c.require(
                type(peak) is int
                and 0 <= peak <= config["execution_limits"]["maximum_peak_cuda_allocated_bytes"],
                "AXIS_CUDA_RESOURCE_LIMIT",
            )
    else:
        c.require(
            resources["inference_worker_started"] is False
            and resources["sampled_resources"] is None
            and resources["peak_cuda_allocated_bytes"] is None,
            "SKIP_ONLY_AXIS_RESOURCE_DRIFT",
        )
    server_identity = (
        validate_jailmeter_lifecycle(root, config, plan, base, ordered)
        if axis == "jailmeter"
        else None
    )
    return {
        "schema_version": "jbspan-pa-llama-development-axis-v1",
        "contract_sha256": config["_contract_sha256"],
        "phase_seed": plan["phase_seed"],
        "axis": axis,
        "complete": True,
        "planned_records": len(ordered),
        "dispatched": sum(row["dispatched"] is True for row in ordered),
        "skipped": sum(row["dispatched"] is False for row in ordered),
        "output_limit_stops": sum(row["output_limit_stop"] is True for row in ordered),
        "rows_identity_sha256": c.digest(ordered),
        "rows": ordered,
        "elapsed_seconds": elapsed,
        "resource_summary_sha256": c.digest(resources),
        "resource_summary": resources,
        "owned_server_lifecycle": server_identity,
        "paper_validity": False,
    }


def validate_saved_axis(config, plan, axis, rows, base, *, root=None):
    path = owned_path(base, "safe", f"phase_{plan['phase_seed']}_{axis}_axis.safe.json")
    saved = read_json(path)
    expected = axis_result(config, plan, axis, rows, saved.get("elapsed_seconds"), base, root=root)
    c.require(c.same(saved, expected), "SAVED_AXIS_RECONSTRUCTION_MISMATCH")
    return saved


def verify_axis(root, config, plan, axis):
    """Reconstruct saved axis from NEW receipts; no models, CUDA, server or calls."""
    c.require(axis in AXES, "PANEL_AXIS_INVALID")
    preflight(root, config)
    base = c.paths(root, config["_contract_sha256"])
    check_no_abort(base, axis, plan["phase_seed"])
    values, helpers, tokenizer = load_axis_values(root, config, plan, axis)
    rows, pending = collect_existing(
        config, values, axis, base, helpers, tokenizer, write_skips=False
    )
    c.require(not pending, "AXIS_VERIFICATION_INCOMPLETE")
    return validate_saved_axis(config, plan, axis, rows, base, root=root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "qwen", "jailmeter", "verify"))
    parser.add_argument("--axis", choices=AXES)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--seed", type=int, choices=(11, 23, 47))
    args = parser.parse_args(argv)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    config = None
    execution_started = False
    try:
        config = c.load_contract(args.root, args.config_sha256)
        if args.command == "preflight":
            result = preflight(args.root, config)
        else:
            c.require(args.seed in (11, 23, 47), "PHASE_SEED_REQUIRED")
            base = c.paths(args.root, args.config_sha256)
            plan = read_json(owned_path(base, "safe", f"phase_{args.seed}_plan.safe.json"))
            inventory = c.source_inventory(args.root, config)
            previous = (
                None
                if args.seed == 11
                else read_json(
                    owned_path(
                        base, "safe", f"phase_{11 if args.seed == 23 else 23}_result.safe.json"
                    )
                )
            )
            expected = c.phase_plan(config, inventory, args.seed, previous)
            c.require(c.canonical(plan) == c.canonical(expected), "PHASE_PLAN_DRIFT")
            if args.command == "verify":
                c.require(args.axis in AXES, "VERIFY_AXIS_REQUIRED")
                verified = verify_axis(args.root, config, plan, args.axis)
                result = {key: value for key, value in verified.items() if key != "rows"}
            else:
                target, _ = target_helpers(args.root, config)
                # Same lock used by the target: no target/panel or panel/panel overlap.
                with target.operation_lock(base):
                    execution_started = True
                    result = (
                        run_qwen(args.root, config, plan)
                        if args.command == "qwen"
                        else run_jailmeter(args.root, config, plan)
                    )
        print(json.dumps(result, sort_keys=True, indent=2), flush=True)
        return 0
    except BaseException as error:
        # Raw responses and transport exception bodies never cross stdout.
        code = safe_error_code(error)
        if config is not None and execution_started and args.command in AXES:
            try:
                record_abort(base, config, args.command, args.seed, error)
            except Exception as abort_error:
                emit(
                    "DEVELOPMENT_PANEL_ABORT_RECORD_FAILED", error_code=safe_error_code(abort_error)
                )
        emit("DEVELOPMENT_PANEL_STOPPED", error_code=code, retry_ambiguous_request=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
