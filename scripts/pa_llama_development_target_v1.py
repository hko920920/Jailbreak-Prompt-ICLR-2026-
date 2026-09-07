"""Bounded target-side I/O for the frozen, exposed 45-payload development frame.

No evaluator or scientific success decisions. Historical input access occurs only
in ``prepare`` and reads the 90 inventory-pinned whole records (including incidental
old replies); only the original payload and prompt are copied. Census endpoints
do not generate. Every target dispatch is write-ahead journaled and never retried.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import shutil
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pa_llama_development_common_v1 as c

RUNNER = "scripts/pa_llama_development_target_v1.py"
HELPER = "scripts/run_pa_llama_target_admission_v2.py"
INPUT_KEYS = {"payload_position", "condition", "payload", "prompt", "payload_sha256",
              "prompt_sha256", "source_private_record_sha256"}
MAX_REPLY_BYTES = 2_000_000
GPU_NAME = "NVIDIA GeForce RTX 3070"
MIN_DISK_BYTES = 15 * 1024 ** 3


def read_json(path):
    c.require(path.is_file() and path.stat().st_size <= 4_000_000, "JSON_MISSING_OR_TOO_LARGE")
    return c.strict_json(path.read_bytes())


def own_path(paths, kind, relative):
    """Common owns scoped Windows long-path bases; every child remains contained."""
    return c.contained(paths[kind], relative)


def helper_for(root, config):
    runners = [pin for pin in config["required_code"].values() if pin["path"] == RUNNER]
    c.require(len(runners) == 1, "TARGET_RUNNER_PIN_REQUIRED")
    c.require(c.verify_pin(root, runners[0], ("scripts/",)) == Path(__file__).resolve(),
              "TARGET_RUNNER_SELF_PIN_MISMATCH")
    pins = [pin for pin in config["required_code"].values() if pin["path"] == HELPER]
    c.require(len(pins) == 1, "V2_HELPER_PIN_REQUIRED")
    path = c.verify_pin(root, pins[0], ("scripts/",))
    spec = importlib.util.spec_from_file_location("pa_development_pinned_v2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reserve_experiment(root, config):
    path = c.contained(root, c.SAFE_ROOT + "/experiment-reservation.safe.json")
    expected = {"contract_sha256": config["_contract_sha256"], "target_call_ceiling": 270,
                "outcome_driven_retries_allowed": False, "historical_source_reads_ceiling": 90}
    if path.exists():
        c.require(c.same(read_json(path), expected), "ANOTHER_EXPERIMENT_ALREADY_RESERVED")
    else:
        c.write_once(path, expected)
    return expected


@contextmanager
def operation_lock(paths):
    path = own_path(paths, "safe", "target-operation.lock.safe.json")
    c.write_once(path, {"pid": os.getpid(), "concurrent_operation_forbidden": True})
    try:
        yield
    finally:
        # Only our newly-created, exact fixed lock is removed, never user data.
        path.unlink()


def extract_input(raw, source):
    """Pure extraction; synthetic tests supply bytes, not historical file paths."""
    c.require(len(raw) == source["private_source"]["size_bytes"], "OLD_RECORD_SIZE_MISMATCH")
    c.require(c.sha_bytes(raw) == source["private_source"]["sha256"], "OLD_RECORD_SHA_MISMATCH")
    old = c.strict_json(raw)
    c.require(isinstance(old, dict)
              and old.get("schema_version") == "local-signal-screen-p3-private-invocation-v1",
              "OLD_RECORD_SCHEMA_MISMATCH")
    identity = old.get("execution_identity")
    c.require(isinstance(identity, dict)
              and c.digest(identity) == source["source_execution_identity_sha256"]
              and old.get("execution_identity_sha256") == c.digest(identity),
              "OLD_EXECUTION_IDENTITY_MISMATCH")
    for key, expected in (("record_id", source["source_record_id"]),
                          ("target_id", source["source_target_id"]),
                          ("seed", 11), ("payload_position", source["payload_position"]),
                          ("condition", source["condition"]),
                          ("payload_sha256", source["payload_sha256"]),
                          ("prompt_sha256", source["prompt_sha256"])):
        c.require(c.same(identity.get(key), expected), "OLD_PLAN_IDENTITY_MISMATCH")
    payload, prompt = old.get("payload"), old.get("prompt")
    c.require(isinstance(payload, str) and payload and isinstance(prompt, str) and prompt,
              "OLD_INPUT_NOT_NONEMPTY_TEXT")
    c.require(c.sha_bytes(payload.encode("utf-8")) == source["payload_sha256"]
              and c.sha_bytes(prompt.encode("utf-8")) == source["prompt_sha256"]
              and len(prompt.encode("utf-8")) == source["prompt_utf8_bytes"],
              "OLD_INPUT_HASH_OR_SIZE_MISMATCH")
    first = prompt.find(payload)
    c.require(first >= 0 and prompt.find(payload, first + 1) < 0,
              "PAYLOAD_OCCURRENCE_NOT_ONE")
    c.require(source["condition"] != "DIRECT" or prompt == payload, "DIRECT_NOT_EXACT_PAYLOAD")
    return {"payload_position": source["payload_position"], "condition": source["condition"],
            "payload": payload, "prompt": prompt, "payload_sha256": source["payload_sha256"],
            "prompt_sha256": source["prompt_sha256"],
            "source_private_record_sha256": source["private_source"]["sha256"]}


def input_receipt(config, inventory, raw):
    return {"contract_sha256": config["_contract_sha256"],
            "source_inventory_sha256": config["source_inventory"]["sha256"],
            "inventory_rows_sha256": inventory["rows_sha256"],
            "private_input_sha256": c.sha_bytes(raw), "input_records": 90,
            "historical_private_files_read": 90,
            "historical_responses_incidentally_read": True,
            "historical_response_copies": 0, "sealed_reads": 0, "dataset_core_reads": 0,
            "target_generations": 0}


def load_inputs(root, config, inventory):
    paths = c.paths(root, config["_contract_sha256"])
    private = own_path(paths, "private", "inputs.private.json")
    c.require(private.is_file() and private.stat().st_size <= 2_000_000,
              "NEW_INPUT_ARTIFACT_MISSING_OR_OVERSIZED")
    raw = private.read_bytes()
    receipt = read_json(own_path(paths, "safe", "inputs.safe.json"))
    c.require(c.same(receipt, input_receipt(config, inventory, raw)), "INPUT_RECEIPT_MISMATCH")
    value = c.strict_json(raw)
    c.require(isinstance(value, dict) and set(value) == {"rows"}, "INPUT_WRAPPER_INVALID")
    rows = value["rows"]
    c.require(isinstance(rows, list) and len(rows) == 90, "INPUT_FRAME_NOT_90")
    for row, source in zip(rows, inventory["rows"], strict=True):
        c.require(isinstance(row, dict) and set(row) == INPUT_KEYS, "INPUT_EXTRA_OR_MISSING_FIELD")
        for key in ("payload_position", "condition", "payload_sha256", "prompt_sha256"):
            c.require(c.same(row[key], source[key]), "INPUT_SOURCE_BINDING_MISMATCH")
        c.require(row["source_private_record_sha256"] == source["private_source"]["sha256"],
                  "INPUT_SOURCE_RECORD_MISMATCH")
        c.require(isinstance(row["payload"], str) and row["payload"]
                  and isinstance(row["prompt"], str) and row["prompt"], "INPUT_TEXT_INVALID")
        c.require(c.sha_bytes(row["payload"].encode()) == row["payload_sha256"]
                  and c.sha_bytes(row["prompt"].encode()) == row["prompt_sha256"]
                  and len(row["prompt"].encode()) == source["prompt_utf8_bytes"],
                  "INPUT_CONTENT_HASH_MISMATCH")
        c.require(row["prompt"].count(row["payload"]) == 1
                  and (row["condition"] != "DIRECT" or row["prompt"] == row["payload"]),
                  "INPUT_PAYLOAD_PARTITION_MISMATCH")
    return rows


def prepare_inputs(root, config, inventory):
    paths = c.paths(root, config["_contract_sha256"])
    reserve_experiment(root, config)
    with operation_lock(paths):
        if own_path(paths, "safe", "inputs.safe.json").exists():
            load_inputs(root, config, inventory)
            return read_json(own_path(paths, "safe", "inputs.safe.json"))
        # One read-once batch. Partial extraction cannot silently reread old records.
        c.write_once(own_path(paths, "safe", "extraction-started.safe.json"), {
            "contract_sha256": config["_contract_sha256"], "planned_old_private_reads": 90,
            "includes_incidental_old_responses": True})
        rows = []
        for ordinal, source in enumerate(inventory["rows"], 1):
            descriptor = source["private_source"]
            expected = f"{c.OLD_PRIVATE}/{source['source_execution_identity_sha256']}.json"
            c.require(descriptor["path"] == expected, "OLD_READ_NOT_INVENTORY_PATH")
            path = c.contained(root, expected)
            c.require(path.is_file() and path.stat().st_size == descriptor["size_bytes"]
                      and 0 < descriptor["size_bytes"] <= 2_000_000, "OLD_READ_SIZE_MISMATCH")
            c.write_once(own_path(paths, "safe", f"extraction/{ordinal:02d}.read.safe.json"), {
                "contract_sha256": config["_contract_sha256"], "ordinal": ordinal,
                "source_private_record_sha256": descriptor["sha256"],
                "read_may_have_occurred": True})
            rows.append(extract_input(path.read_bytes(), source))
        raw = c.canonical({"rows": rows}) + b"\n"
        c.write_once(own_path(paths, "private", "inputs.private.json"), raw, raw=True)
        receipt = input_receipt(config, inventory, raw)
        c.write_once(own_path(paths, "safe", "inputs.safe.json"), receipt)
        return receipt


def request_for(config, item, input_row):
    c.require(item["seed"] in c.SEEDS, "REQUEST_SEED_INVALID")
    return {"model": config["model"]["alias"], "stream": False,
            "messages": [{"role": "user", "content": input_row["prompt"]}],
            **config["generation"], "seed": item["seed"]}


def check_deadline(config):
    text = config.get("execution_limits", {}).get("deadline_utc")
    c.require(isinstance(text, str), "EXECUTION_DEADLINE_REQUIRED")
    try:
        deadline = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise c.DevelopmentError("EXECUTION_DEADLINE_INVALID") from None
    c.require(deadline.tzinfo is not None and deadline.utcoffset().total_seconds() == 0,
              "EXECUTION_DEADLINE_NOT_UTC")
    c.require(datetime.now(timezone.utc) < deadline, "AUTHORIZED_EXECUTION_DEADLINE_REACHED")


def parse_gpu_csv(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    c.require(len(lines) == 1, "EXACTLY_ONE_NVIDIA_GPU_REQUIRED")
    parts = [part.strip() for part in lines[0].split(",")]
    c.require(len(parts) == 4 and parts[0] == GPU_NAME
              and all(part.isascii() and part.isdecimal() for part in parts[1:]),
              "GPU_QUERY_SCHEMA_OR_DEVICE_CHANGED")
    total, used, temperature = map(int, parts[1:])
    c.require(total == 8192 and 0 <= used <= total and 0 <= temperature <= 120,
              "GPU_MEMORY_OR_TEMPERATURE_SCHEMA_CHANGED")
    return {"gpu_name": parts[0], "gpu_total_mib": total, "gpu_used_mib": used,
            "gpu_temperature_c": temperature}


def gpu_sample():
    command = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu",
               "--format=csv,noheader,nounits"]
    measured = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", timeout=10, check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    c.require(measured.returncode == 0, "GPU_QUERY_FAILED")
    return {**parse_gpu_csv(measured.stdout),
            "sampled_at": datetime.now(timezone.utc).isoformat()}


def validate_resource_sample(sample, *, baseline):
    expected_limit = 1000 if baseline else 7600
    c.require(sample.get("gpu_name") == GPU_NAME and c.same(sample.get("gpu_total_mib"), 8192),
              "RESOURCE_GPU_IDENTITY_CHANGED")
    c.require(type(sample.get("gpu_used_mib")) is int
              and 0 <= sample["gpu_used_mib"] <= expected_limit, "GPU_MEMORY_LIMIT_EXCEEDED")
    c.require(type(sample.get("gpu_temperature_c")) is int
              and 0 <= sample["gpu_temperature_c"] < 85, "GPU_TEMPERATURE_LIMIT_EXCEEDED")
    c.require(type(sample.get("disk_free_bytes")) is int
              and sample["disk_free_bytes"] >= MIN_DISK_BYTES, "DISK_FREE_SPACE_BELOW_15_GIB")
    parse_utc(sample.get("sampled_at"))


def prelaunch_resource_check(root, config, observer=None):
    sample = {**gpu_sample(), "disk_free_bytes": shutil.disk_usage(root).free}
    if observer is not None:
        observer(sample)
    validate_resource_sample(sample, baseline=True)
    return sample


def record_prelaunch(root, config, paths, epoch):
    def observe(sample):
        c.write_once(own_path(paths, "safe", f"epochs/{epoch:03d}/resource.safe.json"), {
            "contract_sha256": config["_contract_sha256"], "epoch_index": epoch,
            "baseline": True, **sample})

    return prelaunch_resource_check(root, config, observe)


def metadata_request(client, config, route, payload):
    c.require(route in {"/apply-template", "/tokenize"}, "METADATA_ROUTE_FORBIDDEN")
    c.require(config["server"]["host"] == "127.0.0.1", "METADATA_LOOPBACK_REQUIRED")
    # Reuse the frozen helper's explicit no-proxy, no-redirect opener.
    request = urllib.request.Request(
        f"http://127.0.0.1:{config['server']['port']}{route}",
        data=c.canonical(payload), headers={"Content-Type": "application/json"}, method="POST")
    timeout = config["server"]["request_timeout_seconds"]
    with client.opener.open(request, timeout=timeout) as response:
        c.require(response.status == 200, "METADATA_HTTP_STATUS")
        raw = response.read(MAX_REPLY_BYTES + 1)
    c.require(len(raw) <= MAX_REPLY_BYTES, "METADATA_REPLY_TOO_LARGE")
    return raw


def census_one(config, row, client, post=metadata_request):
    request = request_for(config, {"seed": 11}, row)
    rendered_raw = post(client, config, "/apply-template", request)
    rendered = c.strict_json(rendered_raw)
    c.require(isinstance(rendered, dict) and isinstance(rendered.get("prompt"), str)
              and rendered["prompt"], "TEMPLATE_RENDER_INVALID")
    token_lists = []
    replies = [rendered_raw]
    for text in (row["prompt"], rendered["prompt"]):
        raw = post(client, config, "/tokenize", {"content": text, "add_special": True,
                                                "parse_special": True, "with_pieces": False})
        value = c.strict_json(raw)
        tokens = value.get("tokens") if isinstance(value, dict) else None
        c.require(isinstance(tokens, list) and tokens
                  and all(type(token) is int and token >= 0 for token in tokens),
                  "TOKENIZATION_REPLY_INVALID")
        token_lists.append(tokens)
        replies.append(raw)
    plain, templated = map(len, token_lists)
    within = plain <= 3456 and templated <= 3584 and templated - plain <= 128
    return {"payload_position": row["payload_position"], "condition": row["condition"],
            "payload_sha256": row["payload_sha256"], "prompt_sha256": row["prompt_sha256"],
            "input_tokens": plain, "native_prompt_tokens": templated,
            "template_overhead_tokens": templated - plain,
            "rendered_prompt_sha256": c.sha_bytes(rendered["prompt"].encode()),
            "native_token_ids_sha256": c.digest(token_lists[1]),
            "context_budget_passed": within, "metadata_post_requests": 3,
            "metadata_reply_sha256": [c.sha_bytes(raw) for raw in replies]}, replies


def next_epoch(paths):
    directory = own_path(paths, "safe", "epochs")
    indices = [int(path.name) for path in directory.iterdir()] if directory.exists() else []
    return max(indices, default=0) + 1


def epoch_paths(paths, epoch):
    return (own_path(paths, "safe", f"epochs/{epoch:03d}"),
            own_path(paths, "private", f"epochs/{epoch:03d}"))


def parse_utc(value):
    c.require(isinstance(value, str), "RECEIPT_TIMESTAMP_NOT_STRING")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise c.DevelopmentError("RECEIPT_TIMESTAMP_INVALID") from None
    c.require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
              "RECEIPT_TIMESTAMP_NOT_UTC")
    return parsed


def command_for(root, config):
    return [str(c.contained(root, config["runtime"]["server"]["path"])),
            "--model", str(c.contained(root, config["model"]["entry_path"])),
            "--alias", config["model"]["alias"], "--host", "127.0.0.1",
            "--port", str(config["server"]["port"]), *config["runtime"]["server_args"]]


def verify_epoch(config, paths, epoch, helper, root):
    safe, _ = epoch_paths(paths, epoch)
    started = read_json(safe / "server-01.started.safe.json")
    identity = read_json(safe / "server-01.identity.safe.json")
    stopped = read_json(safe / "server-01.stopped.safe.json")
    resource = read_json(safe / "resource.safe.json")
    c.require(resource.get("contract_sha256") == config["_contract_sha256"]
              and c.same(resource.get("epoch_index"), epoch) and resource.get("baseline") is True,
              "PRELAUNCH_RESOURCE_BINDING_INVALID")
    validate_resource_sample(resource, baseline=True)
    c.require(set(started) == {"contract_sha256", "epoch", "pid", "owned_process_only",
                               "started_at", "command_sha256"}
              and started.get("command_sha256") == c.digest(command_for(root, config))
              and all(c.same(identity.get(key), value) for key, value in started.items()),
              "EPOCH_STARTED_COMMAND_BINDING_INVALID")
    c.require(identity.get("contract_sha256") == config["_contract_sha256"]
              and identity.get("epoch") == 1 and identity.get("owned_process_only") is True
              and type(identity.get("pid")) is int and identity["pid"] > 0,
              "EPOCH_IDENTITY_INVALID")
    c.require(stopped.get("contract_sha256") == config["_contract_sha256"]
              and stopped.get("pid") == identity["pid"] and stopped.get("epoch") == 1
              and stopped.get("owned_process_only") is True
              and type(stopped.get("returncode")) is int, "EPOCH_CLEANUP_NOT_VERIFIED")
    c.require(parse_utc(started["started_at"]) <= parse_utc(stopped.get("stopped_at")),
              "EPOCH_TIMESTAMP_ORDER_INVALID")
    c.require(parse_utc(resource["sampled_at"]) <= parse_utc(started["started_at"]),
              "PRELAUNCH_RESOURCE_TIMESTAMP_INVALID")
    helper.verify_template_observation(config, config["_contract_sha256"],
                                       safe / "server-01.tpl.safe.json",
                                       {"epoch": 1, "process_id": identity["pid"]})
    return {**identity, "stopped_at": stopped["stopped_at"]}


def census_inputs(root, config, inventory, helper):
    paths = c.paths(root, config["_contract_sha256"])
    reserve_experiment(root, config)
    inputs = load_inputs(root, config, inventory)
    with operation_lock(paths):
        existing = own_path(paths, "safe", "census.safe.json")
        if existing.exists():
            return load_census(root, config, inventory, helper)
        c.require(not own_path(paths, "safe", "census-started.safe.json").exists(),
                  "PARTIAL_CENSUS_REQUIRES_AUDIT")
        epoch = next_epoch(paths)
        safe_epoch, private_epoch = epoch_paths(paths, epoch)
        record_prelaunch(root, config, paths, epoch)
        c.write_once(own_path(paths, "safe", "census-started.safe.json"), {
            "contract_sha256": config["_contract_sha256"], "input_records": 90,
            "planned_metadata_post_requests": 270, "planned_generations": 0})
        private_epoch.mkdir(parents=True, exist_ok=False)
        rows = []
        with helper.owned_server(root, config, private_epoch, safe_epoch, 1,
                                 config["_contract_sha256"]) as (process, client, properties):
            properties_now = client.get("/props")
            served_context = properties_now.get("default_generation_settings", {}).get("n_ctx")
            c.require(c.same(served_context, 4096), "SERVED_CONTEXT_NOT_4096")
            for ordinal, row in enumerate(inputs, 1):
                c.require(process.poll() is None, "CENSUS_PROCESS_EXITED")
                measured, replies = census_one(config, row, client)
                for number, raw in enumerate(replies):
                    c.write_once(own_path(paths, "private",
                                         f"census/{ordinal:02d}-{number}.reply.private.json"),
                                 raw, raw=True)
                rows.append({**measured, "epoch_index": epoch, "process_id": process.pid,
                             "served_chat_template_sha256":
                             properties["served_chat_template_sha256"]})
                c.write_once(own_path(paths, "safe", f"census/{ordinal:02d}.row.safe.json"),
                             rows[-1])
        verify_epoch(config, paths, epoch, helper, root)
        result = {"contract_sha256": config["_contract_sha256"],
                  "inventory_rows_sha256": inventory["rows_sha256"], "epoch_index": epoch,
                  "input_records": 90, "metadata_post_requests": 270, "target_generations": 0,
                  "served_context_tokens": served_context,
                  "all_inputs_within_context": all(row["context_budget_passed"] for row in rows),
                  "rows": rows, "rows_sha256": c.digest(rows)}
        c.write_once(existing, result)
        return result


def load_census(root, config, inventory, helper):
    paths = c.paths(root, config["_contract_sha256"])
    result = read_json(own_path(paths, "safe", "census.safe.json"))
    rows = result.get("rows")
    c.require(result.get("contract_sha256") == config["_contract_sha256"]
              and result.get("inventory_rows_sha256") == inventory["rows_sha256"]
              and isinstance(rows, list) and len(rows) == 90
              and c.same(result.get("served_context_tokens"), 4096)
              and c.same(result.get("metadata_post_requests"), 270)
              and c.same(result.get("target_generations"), 0)
              and c.digest(rows) == result.get("rows_sha256")
              and result.get("all_inputs_within_context") is True,
              "CENSUS_INCOMPLETE_OR_CONTEXT_FAILED")
    identity = verify_epoch(config, paths, result["epoch_index"], helper, root)
    for ordinal, (row, source) in enumerate(zip(rows, inventory["rows"], strict=True), 1):
        for key in ("payload_position", "condition", "payload_sha256", "prompt_sha256"):
            c.require(c.same(row.get(key), source[key]), "CENSUS_SOURCE_BINDING_INVALID")
        c.require(c.same(read_json(own_path(paths, "safe", f"census/{ordinal:02d}.row.safe.json")),
                         row), "CENSUS_ROW_FILE_CHANGED")
        raw_replies = [own_path(paths, "private",
                               f"census/{ordinal:02d}-{number}.reply.private.json").read_bytes()
                       for number in range(3)]
        c.require([c.sha_bytes(raw) for raw in raw_replies] == row["metadata_reply_sha256"],
                  "CENSUS_METADATA_RECEIPT_CHANGED")
        tokens = [c.strict_json(raw)["tokens"] for raw in raw_replies[1:]]
        rendered = c.strict_json(raw_replies[0])["prompt"]
        c.require(type(row.get("input_tokens")) is int and 0 < row["input_tokens"] <= 3456
                  and type(row.get("native_prompt_tokens")) is int
                  and 0 < row["native_prompt_tokens"] <= 3584
                  and row["native_prompt_tokens"] - row["input_tokens"] <= 128
                  and [len(value) for value in tokens]
                  == [row["input_tokens"], row["native_prompt_tokens"]]
                  and c.digest(tokens[1]) == row["native_token_ids_sha256"]
                  and c.sha_bytes(rendered.encode()) == row["rendered_prompt_sha256"]
                  and row.get("context_budget_passed") is True
                  and row.get("process_id") == identity["pid"]
                  and row.get("epoch_index") == result["epoch_index"]
                  and row.get("served_chat_template_sha256")
                  == config["runtime"]["served_chat_template_sha256"],
                  "CENSUS_TOKEN_BINDING_INVALID")
    return result


def parse_reply(config, raw, expected_prompt_tokens):
    value = c.strict_json(raw)
    c.require(isinstance(value, dict) and value.get("model") == config["model"]["alias"],
              "REPLY_MODEL_MISMATCH")
    choices = value.get("choices")
    c.require(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict),
              "REPLY_CHOICES_INVALID")
    choice = choices[0]
    c.require(c.same(choice.get("index"), 0), "REPLY_CHOICE_INDEX_INVALID")
    message = choice.get("message")
    c.require(isinstance(message, dict) and message.get("role") == "assistant",
              "REPLY_ROLE_INVALID")
    c.require(not any(message.get(key) for key in
                      ("tool_calls", "function_call", "refusal", "reasoning_content")),
              "NONANSWER_CHANNEL_PRESENT")
    content = message.get("content")
    c.require(isinstance(content, str), "REPLY_CONTENT_NOT_STRING")
    finish = choice.get("finish_reason")
    c.require(finish in {"stop", "length"}, "REPLY_FINISH_INVALID")
    usage = value.get("usage")
    c.require(isinstance(usage, dict) and all(type(usage.get(key)) is int and usage[key] >= 0
              for key in ("prompt_tokens", "completion_tokens", "total_tokens")),
              "REPLY_USAGE_INVALID")
    c.require(usage["prompt_tokens"] == expected_prompt_tokens,
              "NATIVE_CENSUS_USAGE_MISMATCH_NO_SILENT_TRUNCATION")
    c.require(0 < usage["prompt_tokens"] <= 3584 and usage["completion_tokens"] <= 512
              and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
              and usage["total_tokens"] <= 4096, "REPLY_TOKEN_BUDGET_VIOLATION")
    c.require(not content or usage["completion_tokens"] > 0, "NONEMPTY_REPLY_ZERO_TOKENS")
    normalized = c.normalize_response(content)
    reason = "TRUNCATED_UNKNOWN" if finish == "length" else (
        "EMPTY_UNKNOWN" if not normalized else None)
    return {"content_sha256": c.sha_bytes(content.encode()),
            "response_sha256": c.sha_bytes(normalized.encode()),
            "raw_reply_sha256": c.sha_bytes(raw), "finish_reason": finish,
            "usage": {key: usage[key] for key in
                      ("prompt_tokens", "completion_tokens", "total_tokens")},
            "eligible_for_panel": reason is None, "ineligible_reason": reason,
            "completion_cap_reached": usage["completion_tokens"] == 512,
            "request_max_tokens": 512}


def phase_for(root, config, inventory, seed):
    paths = c.paths(root, config["_contract_sha256"])
    previous = None
    if seed != 11:
        c.require(seed in (23, 47), "PHASE_SEED_INVALID")
        prior_seed = 11 if seed == 23 else 23
        previous = read_json(own_path(paths, "safe",
                                      f"phase_{prior_seed}_result.safe.json"))
        proof = read_json(own_path(paths, "safe",
                                   f"phase_{prior_seed}_verification.safe.json"))
        expected = {"contract_sha256": config["_contract_sha256"], "phase_seed": prior_seed,
                    "phase_result_identity_sha256": previous.get("result_identity_sha256"),
                    "raw_axis_receipts_verified": True, "independent_pair_states_verified": True,
                    "verification_passed": True, "new_model_calls": 0}
        c.require(all(c.same(proof.get(key), value) for key, value in expected.items()),
                  "PREVIOUS_PHASE_INDEPENDENT_VERIFICATION_REQUIRED")
    return c.phase_plan(config, inventory, seed, previous)


def dispatch_one(config, paths, item, input_row, census_row, process, client, epoch, helper):
    check_deadline(config)
    request_id = item["request_id"]
    request = request_for(config, item, input_row)
    resource = {**gpu_sample(), "disk_free_bytes": shutil.disk_usage(paths["safe"]).free,
                "contract_sha256": config["_contract_sha256"], "request_id": request_id,
                "epoch_index": epoch, "baseline": False}
    c.write_once(own_path(paths, "safe", f"epochs/{epoch:03d}/gpu-{request_id}.safe.json"),
                 resource)
    validate_resource_sample(resource, baseline=False)

    def observe(observation):
        c.write_once(own_path(paths, "safe", f"target/{request_id}.tpl.safe.json"), {
            "contract_sha256": config["_contract_sha256"], "request_id": request_id,
            "epoch_index": epoch, **observation})

    properties = helper.check_identity(process, client, config, observe)
    check_deadline(config)
    c.write_once(own_path(paths, "private", f"target/{request_id}.request.private.json"), request)
    journal = {**item, "contract_sha256": config["_contract_sha256"],
               "request_sha256": c.digest(request), "epoch_index": epoch,
               "process_id": process.pid, "dispatch_at": helper.utc_now(),
               "resource_sample_sha256": c.digest(resource),
               "gpu_memory_used_mib": resource["gpu_used_mib"],
               "gpu_temperature_c": resource["gpu_temperature_c"],
               "served_chat_template_sha256": properties["served_chat_template_sha256"]}
    c.write_once(own_path(paths, "safe", f"target/{request_id}.dispatch.safe.json"), journal)
    started = time.monotonic()
    raw = client.request("/v1/chat/completions", request,
                         timeout=config["server"]["request_timeout_seconds"])
    c.write_once(own_path(paths, "private", f"target/{request_id}.reply.private.json"),
                 raw, raw=True)
    c.require(process.poll() is None, "OWNED_SERVER_EXITED_AFTER_DISPATCH")
    parsed = parse_reply(config, raw, census_row["native_prompt_tokens"])
    row = {**journal, **parsed, "latency_seconds": time.monotonic() - started,
           "received_at": helper.utc_now()}
    c.write_once(own_path(paths, "safe", f"target/{request_id}.row.safe.json"), row)
    helper.emit("DEVELOPMENT_TARGET_RECORDED", seed=item["seed"],
                payload_position=item["payload_position"], condition=item["condition"],
                eligible_for_panel=row["eligible_for_panel"], finish_reason=row["finish_reason"])
    return row


def reconcile_phase(root, config, plan, inputs, census, helper):
    paths = c.paths(root, config["_contract_sha256"])
    input_map = {(row["payload_position"], row["condition"]): row for row in inputs}
    census_map = {(row["payload_position"], row["condition"]): row for row in census["rows"]}
    completed = []
    missing = False
    for item in plan["rows"]:
        rid = item["request_id"]
        journal_path = own_path(paths, "safe", f"target/{rid}.dispatch.safe.json")
        row_path = own_path(paths, "safe", f"target/{rid}.row.safe.json")
        reply_path = own_path(paths, "private", f"target/{rid}.reply.private.json")
        request_path = own_path(paths, "private", f"target/{rid}.request.private.json")
        observation_path = own_path(paths, "safe", f"target/{rid}.tpl.safe.json")
        if not journal_path.exists():
            c.require(not any(path.exists() for path in
                              (row_path, reply_path, request_path, observation_path)),
                      "ORPHAN_PRE_DISPATCH_STATE_REQUIRES_AUDIT")
            missing = True
            continue
        c.require(not missing, "DISPATCHES_NOT_COMPLETE_PLAN_PREFIX")
        c.require(row_path.is_file() and reply_path.is_file(),
                  "AMBIGUOUS_OR_UNFINALIZED_DISPATCH_NO_RETRY")
        journal, row = read_json(journal_path), read_json(row_path)
        journal_fields = {"contract_sha256", "request_sha256", "epoch_index", "process_id",
                          "dispatch_at", "served_chat_template_sha256", "resource_sample_sha256",
                          "gpu_memory_used_mib", "gpu_temperature_c"}
        c.require(set(journal) == set(item) | journal_fields, "JOURNAL_EXTRA_OR_MISSING_FIELD")
        for key, value in {**item, "contract_sha256": config["_contract_sha256"]}.items():
            c.require(c.same(journal.get(key), value), "JOURNAL_PLAN_BINDING_MISMATCH")
        key = (item["payload_position"], item["condition"])
        request = request_for(config, item, input_map[key])
        c.require(c.same(read_json(request_path), request)
                  and journal.get("request_sha256") == c.digest(request), "REQUEST_BYTES_CHANGED")
        epoch = verify_epoch(config, paths, journal["epoch_index"], helper, root)
        resource = read_json(own_path(paths, "safe",
            f"epochs/{journal['epoch_index']:03d}/gpu-{rid}.safe.json"))
        validate_resource_sample(resource, baseline=False)
        resource_binding = {"contract_sha256": config["_contract_sha256"], "request_id": rid,
                            "epoch_index": journal["epoch_index"], "baseline": False}
        c.require(all(c.same(resource.get(key), value) for key, value in resource_binding.items())
                  and c.digest(resource) == journal.get("resource_sample_sha256")
                  and c.same(resource["gpu_used_mib"], journal.get("gpu_memory_used_mib"))
                  and c.same(resource["gpu_temperature_c"], journal.get("gpu_temperature_c")),
                  "DISPATCH_RESOURCE_BINDING_INVALID")
        c.require(journal.get("process_id") == epoch["pid"]
                  and journal.get("served_chat_template_sha256")
                  == config["runtime"]["served_chat_template_sha256"], "DISPATCH_EPOCH_MISMATCH")
        helper.verify_template_observation(
            config, config["_contract_sha256"], observation_path,
            {"request_id": rid, "epoch_index": journal["epoch_index"], "process_id": epoch["pid"]})
        parsed = parse_reply(config, reply_path.read_bytes(),
                             census_map[key]["native_prompt_tokens"])
        expected = {**journal, **parsed}
        c.require(set(row) == set(expected) | {"latency_seconds", "received_at"},
                  "TARGET_ROW_EXTRA_OR_MISSING_FIELD")
        c.require(all(c.same(row.get(key), value) for key, value in expected.items()),
                  "TARGET_ROW_RECEIPT_MISMATCH")
        c.require(type(row.get("latency_seconds")) in (int, float)
                  and math.isfinite(row["latency_seconds"]) and row["latency_seconds"] >= 0,
                  "TARGET_LATENCY_INVALID")
        c.require(parse_utc(epoch["started_at"]) <= parse_utc(journal.get("dispatch_at"))
                  <= parse_utc(row.get("received_at")) <= parse_utc(epoch["stopped_at"]),
                  "TARGET_TIMESTAMP_ORDER_INVALID")
        c.require(parse_utc(epoch["started_at"]) <= parse_utc(resource["sampled_at"])
                  <= parse_utc(journal["dispatch_at"]), "DISPATCH_RESOURCE_TIMESTAMP_INVALID")
        completed.append(row)
    return completed


def global_receipt_check(root, config, inventory):
    paths = c.paths(root, config["_contract_sha256"])
    directory = own_path(paths, "safe", "target")
    journals = list(directory.glob("*.dispatch.safe.json")) if directory.exists() else []
    c.require(len(journals) <= 270, "GLOBAL_TARGET_CEILING_EXCEEDED")
    valid = {c.request_id(config["_contract_sha256"],
                         row["payload_position"], row["condition"], seed)
             for seed in c.SEEDS for row in inventory["rows"]}
    c.require(all(path.name.removesuffix(".dispatch.safe.json") in valid for path in journals),
              "OUT_OF_FRAME_TARGET_DISPATCH")
    journal_ids = {path.name.removesuffix(".dispatch.safe.json") for path in journals}
    # Check all observed new reply/row/request artifacts, not just the chosen phase.
    for kind, suffix in (("safe", ".row.safe.json"), ("safe", ".tpl.safe.json"),
                         ("private", ".reply.private.json"), ("private", ".request.private.json")):
        artifact_dir = own_path(paths, kind, "target")
        observed = list(artifact_dir.glob("*" + suffix)) if artifact_dir.exists() else []
        observed_ids = {path.name.removesuffix(suffix) for path in observed}
        c.require(observed_ids <= journal_ids, "ORPHAN_TARGET_ARTIFACT_REQUIRES_AUDIT")
    return len(journals)


def run_phase(root, config, inventory, seed, helper):
    paths = c.paths(root, config["_contract_sha256"])
    reserve_experiment(root, config)
    inputs = load_inputs(root, config, inventory)
    census = load_census(root, config, inventory, helper)
    plan = phase_for(root, config, inventory, seed)
    with operation_lock(paths):
        path = own_path(paths, "safe", f"phase_{seed}_plan.safe.json")
        if path.exists():
            c.require(c.same(read_json(path), plan), "FROZEN_PHASE_PLAN_CHANGED")
        else:
            c.write_once(path, plan)
        count = global_receipt_check(root, config, inventory)
        # A new phase cannot hide an ambiguous dispatch in an earlier phase.
        audited_ids = set()
        for prior_seed in c.SEEDS:
            prior_path = own_path(paths, "safe", f"phase_{prior_seed}_plan.safe.json")
            if prior_path.exists():
                prior_plan = phase_for(root, config, inventory, prior_seed)
                c.require(c.same(read_json(prior_path), prior_plan), "PRIOR_PHASE_PLAN_CHANGED")
                prior_rows = reconcile_phase(root, config, prior_plan, inputs, census, helper)
                c.require(prior_seed >= seed or len(prior_rows) == prior_plan["request_count"],
                          "PREVIOUS_PHASE_TARGETS_INCOMPLETE")
                audited_ids.update(row["request_id"] for row in prior_rows)
        c.require(len(audited_ids) == count, "UNRECONCILED_GLOBAL_DISPATCH")
        complete = reconcile_phase(root, config, plan, inputs, census, helper)
        pending = plan["rows"][len(complete):]
        c.require(count + len(pending) <= 270, "GLOBAL_TARGET_CEILING_EXCEEDED")
        if not pending:
            return {**finalize_phase(config, paths, seed, complete), "new_target_generations": 0}
        input_map = {(row["payload_position"], row["condition"]): row for row in inputs}
        census_map = {(row["payload_position"], row["condition"]): row for row in census["rows"]}
        epoch = next_epoch(paths)
        safe_epoch, private_epoch = epoch_paths(paths, epoch)
        record_prelaunch(root, config, paths, epoch)
        private_epoch.mkdir(parents=True, exist_ok=False)
        with helper.owned_server(root, config, private_epoch, safe_epoch, 1,
                                 config["_contract_sha256"]) as (process, client, _):
            for item in pending:
                key = (item["payload_position"], item["condition"])
                complete.append(dispatch_one(config, paths, item, input_map[key], census_map[key],
                                             process, client, epoch, helper))
        reconcile_phase(root, config, plan, inputs, census, helper)
        return finalize_phase(config, paths, seed, complete)


def finalize_phase(config, paths, seed, complete):
    result = {"contract_sha256": config["_contract_sha256"], "phase_seed": seed,
              "target_records": len(complete), "phase_complete": True,
              "eligible_for_panel": sum(row["eligible_for_panel"] for row in complete),
              "gpu_memory_sampled_max_mib": max(row["gpu_memory_used_mib"] for row in complete),
              "gpu_temperature_sampled_max_c": max(row["gpu_temperature_c"] for row in complete),
              "gpu_measurement": "PREDISPATCH_SNAPSHOTS_NOT_CONTINUOUS_PEAK",
              "target_rows_sha256": c.digest(complete), "scientific_gate_evaluated": False}
    path = own_path(paths, "safe", f"phase_{seed}_target.safe.json")
    if path.exists():
        c.require(c.same(read_json(path), result), "FINAL_TARGET_RECEIPT_CHANGED")
    else:
        c.write_once(path, result)
    return result


def safe_error_code(error):
    candidate = str(error)
    if candidate and len(candidate) <= 120 and all(
            char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in candidate):
        return candidate
    return type(error).__name__


def record_abort(root, config, command, seed, error):
    paths = c.paths(root, config["_contract_sha256"])
    target_dir = own_path(paths, "safe", "target")
    reply_dir = own_path(paths, "private", "target")
    receipt = {"contract_sha256": config["_contract_sha256"], "command": command,
               "phase_seed": seed, "error_code": safe_error_code(error),
               "aborted_at": datetime.now(timezone.utc).isoformat(),
               "journaled_target_dispatches": len(list(target_dir.glob("*.dispatch.safe.json")))
               if target_dir.exists() else 0,
               "target_reply_receipts": len(list(reply_dir.glob("*.reply.private.json")))
               if reply_dir.exists() else 0, "automatic_retry_allowed": False,
               "raw_content_included": False}
    c.write_once(own_path(paths, "safe", f"failures/{time.time_ns()}.safe.json"), receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("command", choices=("preflight", "prepare", "census", "generate", "status"))
    parser.add_argument("--seed", type=int, choices=c.SEEDS)
    args = parser.parse_args(argv)
    config = None
    try:
        root = args.root.resolve()
        config = c.load_contract(root, args.config_sha256)
        inventory = c.source_inventory(root, config)
        helper = helper_for(root, config)
        if args.command == "prepare":
            result = prepare_inputs(root, config, inventory)
        elif args.command == "census":
            result = census_inputs(root, config, inventory, helper)
            result = {key: value for key, value in result.items() if key != "rows"}
        elif args.command == "generate":
            c.require(args.seed is not None, "GENERATE_PHASE_SEED_REQUIRED")
            result = run_phase(root, config, inventory, args.seed, helper)
        else:
            result = {"static_preflight_passed": True, "model_calls_this_command": 0,
                      "historical_private_reads_this_command": 0,
                      "journaled_target_dispatches": global_receipt_check(root, config, inventory),
                      "scientific_gate_evaluated": False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        abort_saved = False
        if config is not None and args.command in {"prepare", "census", "generate"}:
            try:
                record_abort(root, config, args.command, args.seed, error)
                abort_saved = True
            except Exception:
                pass  # Never obscure the original safe failure or emit private exception text.
        print(json.dumps({"completed": False, "error_code": safe_error_code(error),
                          "abort_receipt_saved": abort_saved, "no_automatic_retry": True}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
