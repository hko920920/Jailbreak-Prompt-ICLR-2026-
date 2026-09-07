"""One six-request harmless stochastic-regime smoke; static preflight by default.

The immutable proposal remains execution-disabled. This separate contract needs
explicit authority. Pinned V2 helpers supply identity, typed scoring and owned
loopback lifecycle only: no historical runner, private record or model output is
replayed. There is one batch, no retry and no execution-resume implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path

SCHEMA = "jbspan-pa-research-regime-smoke-execution-v1"
RUNNER = "scripts/run_pa_research_regime_smoke_v1.py"
HELPER = "scripts/run_pa_llama_target_admission_v2.py"
VALIDATOR = "scripts/preflight_pa_research_regime_smoke_v1.py"
CONFIG = "configs/natural_language_localization/pa_research_regime_smoke_execution_v1.json"
PROPOSAL = "configs/natural_language_localization/pa_research_regime_smoke_proposal_v1.json"
V2_CONTRACT = "configs/natural_language_localization/pa_llama_target_admission_v2.json"
SAFE_ROOT = "data/natural_language_localization/pa_research_regime_smoke_v1"
PRIVATE_ROOT = "artifacts/pa_research_regime_smoke_v1/private"
AUTHORITY = "docs/PA_EIGHT_HOUR_WORK_AUTHORIZATION_2026-09-05_V1.md"
DECISION = "docs/PA_RESEARCH_REGIME_QUALIFICATION_DECISION_2026-09-05_V1.md"
GENERATION = {"temperature": 0.7, "top_p": 0.9, "top_k": 50, "min_p": 0,
              "repeat_penalty": 1, "max_tokens": 512}
PURPOSE = "LIMITED_SCIENTIFIC_REQUEST_REGIME_SMOKE_ONLY"


class SmokeError(ValueError):
    """Content-free error codes for durable safe diagnostics."""


def require(condition, code):
    if not condition:
        raise SmokeError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def raw_digest(value):
    return hashlib.sha256(value).hexdigest()


def same(value, expected):
    return canonical(value) == canonical(expected)


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    def bad_constant(_):
        raise SmokeError("NONFINITE_JSON_CONSTANT")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def contained(root, relative):
    require(isinstance(relative, str) and relative != "" and "\\" not in relative,
            "PATH_INVALID")
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            "PATH_NOT_RELATIVE")
    path = (root / relative).resolve()
    require(path != root and path.is_relative_to(root), "PATH_ESCAPES_ROOT")
    require(path.relative_to(root).as_posix() == relative, "PATH_ALIAS_FORBIDDEN")
    return path


def descriptor(root, item, *, prefixes):
    require(isinstance(item, dict) and set(item) == {"path", "size_bytes", "sha256"},
            "DESCRIPTOR_INVALID")
    require(isinstance(item["path"], str) and item["path"].startswith(prefixes),
            "SOURCE_READ_SCOPE_INVALID")
    require(type(item["size_bytes"]) is int and item["size_bytes"] >= 0,
            "SOURCE_SIZE_INVALID")
    require(isinstance(item["sha256"], str) and len(item["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in item["sha256"]), "SOURCE_SHA_INVALID")
    path = contained(root, item["path"])
    require(path.is_file() and path.stat().st_size == item["size_bytes"], "SOURCE_SIZE_MISMATCH")
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    require(checksum.hexdigest() == item["sha256"], "SOURCE_SHA_MISMATCH")
    return path


def load_module(path, name):
    """Called only after the source file's exact identity has been verified."""
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "PINNED_IMPORT_SPEC_INVALID")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract(root, config_path, expected_sha):
    root = root.resolve()
    require(config_path == CONFIG, "EXECUTION_CONFIG_PATH_INVALID")
    config_raw = contained(root, config_path).read_bytes()
    require(raw_digest(config_raw) == expected_sha, "CONFIG_SHA_MISMATCH")
    config = strict_json(config_raw)
    require(config.get("schema_version") == SCHEMA and config.get("frozen") is True,
            "EXECUTION_CONTRACT_NOT_FROZEN")
    require(config.get("execution_authorized") is True, "EXECUTION_AUTHORITY_MISSING")
    require(config.get("purpose") == PURPOSE
            and config.get("evidence_class")
            == "RESULT_INFORMED_DEVELOPMENT_OPERATIONAL_SMOKE_NOT_CONFIRMATION"
            and config.get("paper_validity") is False, "EXPERIMENT_SCOPE_MISMATCH")
    require(same(config.get("request_ceiling"), 6) and config.get("one_batch_only") is True
            and config.get("no_retries") is True, "SIX_CALL_SINGLE_BATCH_RULE_REQUIRED")
    require(same(config.get("paths"), {"safe_root": SAFE_ROOT, "private_root": PRIVATE_ROOT}),
            "OUTPUT_ROOTS_MISMATCH")
    code = config.get("required_code", {})
    required = {"runner": RUNNER, "v2_helper": HELPER, "proposal_validator": VALIDATOR,
                "tests": "tests/test_run_pa_research_regime_smoke_v1.py"}
    require(set(required) <= set(code), "REQUIRED_CODE_PIN_MISSING")
    for key, value in code.items():
        if key in required:
            require(value.get("path") == required[key], "CODE_ROLE_PATH_MISMATCH")
        path = descriptor(root, value, prefixes=("scripts/", "tests/"))
        if key == "runner":
            require(path == Path(__file__).resolve(), "RUNNER_SELF_PIN_MISMATCH")
    source_paths = set()
    for item in config.get("sources", []):
        descriptor(root, item, prefixes=("docs/",))
        source_paths.add(item["path"])
    require({AUTHORITY, DECISION} <= source_paths, "AUTHORITY_AND_DECISION_PINS_REQUIRED")
    require(config["proposal"]["path"] == PROPOSAL, "PROPOSAL_PATH_MISMATCH")
    proposal_path = descriptor(root, config["proposal"], prefixes=("configs/",))
    proposal = strict_json(proposal_path.read_bytes())
    require(same(config["required_code"]["v2_helper"], proposal["sources"]["old_v2_runner"]),
            "V2_HELPER_NOT_FROZEN_PROPOSAL_SOURCE")
    require(same(config["required_code"]["proposal_validator"], proposal["sources"]["validator"]),
            "VALIDATOR_NOT_FROZEN_PROPOSAL_SOURCE")
    require(same(config.get("v2_contract"), proposal["sources"]["v2_contract"]),
            "V2_CONTRACT_NOT_FROZEN_PROPOSAL_SOURCE")
    require(config["v2_contract"]["path"] == V2_CONTRACT, "V2_SOURCE_PATH_MISMATCH")
    v2_path = descriptor(root, config["v2_contract"], prefixes=("configs/",))
    v2 = strict_json(v2_path.read_bytes())
    helper = load_module(contained(root, HELPER), "pa_smoke_pinned_v2_helpers")
    validator = load_module(contained(root, VALIDATOR), "pa_smoke_pinned_proposal_validator")
    prior = validator.preflight(root, PROPOSAL, config["proposal"]["sha256"])
    require(prior.get("static_preflight_passed") is True
            and prior.get("execution_authorized") is False,
            "FROZEN_PROPOSAL_STATIC_VALIDATION_FAILED")
    require(config.get("proposal_rule_plan_sha256") == prior["proposal_plan_sha256"],
            "FROZEN_PROPOSAL_PLAN_MISMATCH")
    for key in ("tasks", "seeds", "generation", "context_tokens"):
        require(same(config.get(key), proposal[key]), "FROZEN_PROPOSAL_DESIGN_CHANGED")
    require(same(config["generation"], GENERATION) and same(config["seeds"], [11, 23, 47])
            and same(config["context_tokens"], 4096), "SCIENTIFIC_REGIME_CHANGED")
    for key in ("model", "runtime", "server"):
        require(same(config.get(key), v2[key]), "FROZEN_V2_RUNTIME_IDENTITY_CHANGED")
    # Rehash the exact inherited artifact closure without following private paths.
    runtime_prefix = ("artifacts/p2_runtime_qualification_v1/runtime/",)
    descriptor(root, config["runtime"]["server"], prefixes=runtime_prefix)
    for item in config["runtime"]["files"]:
        descriptor(root, item, prefixes=runtime_prefix)
    for item in config["model"]["files"]:
        descriptor(root, item, prefixes=("artifacts/p2_runtime_qualification_v1/models/",))
    require(config["model"]["entry_path"] in {item["path"] for item in config["model"]["files"]},
            "MODEL_ENTRY_NOT_PINNED")
    helper.validate_server_args(config["runtime"]["server_args"])
    require(config["server"]["host"] == "127.0.0.1", "LOOPBACK_REQUIRED")
    contained(root, SAFE_ROOT)
    contained(root, PRIVATE_ROOT)
    return config, helper, proposal


def plan_for(config):
    return [{"ordinal": index + 1, "seed": seed, "task": task}
            for index, (seed, task) in enumerate(
                (seed, task) for seed in config["seeds"] for task in config["tasks"])]


def request_for(config, item):
    return {"model": config["model"]["alias"], "stream": False,
            "messages": [{"role": "user", "content": item["task"]["text"]}],
            **config["generation"], "seed": item["seed"]}


def public_plan(config):
    return [{"ordinal": item["ordinal"], "seed": item["seed"],
             "task_id": item["task"]["task_id"], "fixture_id": item["task"]["fixture_id"],
             "request_sha256": digest(request_for(config, item))}
            for item in plan_for(config)]


def parse_reply(config, item, raw, helper):
    """V2 response integrity and exact scorers, with the frozen new cap of 512."""
    value = strict_json(raw)
    require(isinstance(value, dict), "REPLY_OBJECT_REQUIRED")
    require(value.get("model") == config["model"]["alias"], "REPLY_MODEL_MISMATCH")
    choices = value.get("choices")
    require(isinstance(choices, list) and len(choices) == 1, "REPLY_CHOICE_COUNT_INVALID")
    choice = choices[0]
    require(isinstance(choice, dict) and same(choice.get("index"), 0), "REPLY_CHOICE_INDEX_INVALID")
    message = choice.get("message")
    require(isinstance(message, dict) and message.get("role") == "assistant", "REPLY_ROLE_INVALID")
    require(not any(message.get(key) for key in
                    ("tool_calls", "function_call", "refusal", "reasoning_content")),
            "NONANSWER_CHANNEL_PRESENT")
    content = message.get("content")
    require(isinstance(content, str), "CONTENT_NOT_STRING")
    score = helper.score_answer(item["task"], content)
    finish = choice.get("finish_reason")
    require(finish in {"stop", "length"}, "FINISH_REASON_INVALID")
    usage = value.get("usage")
    require(isinstance(usage, dict), "USAGE_MISSING")
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        require(type(usage.get(key)) is int and usage[key] >= 0, "USAGE_INVALID")
    require(0 < usage["prompt_tokens"] <= 4096 and usage["completion_tokens"] <= 512,
            "TOKEN_BOUND_VIOLATION")
    require(not content or usage["completion_tokens"] > 0, "NONEMPTY_CONTENT_ZERO_TOKENS")
    require(usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"],
            "USAGE_TOTAL_MISMATCH")
    return {**score, "finish_reason": finish, "not_truncated": finish == "stop",
            "passed": score["content_check_passed"] and finish == "stop",
            "usage": {key: usage[key] for key in
                      ("prompt_tokens", "completion_tokens", "total_tokens")},
            "reply_bytes_sha256": raw_digest(raw)}


def dispatch_one(config, contract_sha, item, process, client, safe_dir, private_dir, helper):
    ordinal = item["ordinal"]
    require(type(ordinal) is int and 1 <= ordinal <= 6, "SIX_CALL_CEILING_EXCEEDED")
    require(process.poll() is None, "OWNED_PROCESS_EXITED")

    def observe(observation):
        helper.write_once(safe_dir / f"{ordinal:02d}.tpl.safe.json", {
            "contract_sha256": contract_sha, "ordinal": ordinal, "epoch": 1, **observation,
        })

    identity = helper.check_identity(process, client, config, observe)
    request = request_for(config, item)
    helper.write_once(private_dir / f"{ordinal:02d}.request.private.json", request)
    journal = {
        "contract_sha256": contract_sha, "proposal_sha256": config["proposal"]["sha256"],
        "ordinal": ordinal, "seed": item["seed"], "epoch": 1,
        "task_id": item["task"]["task_id"], "fixture_id": item["task"]["fixture_id"],
        "process_id": process.pid, "request_sha256": digest(request),
        "served_chat_template_sha256": identity["served_chat_template_sha256"],
        "dispatch_at": helper.utc_now(),
    }
    helper.write_once(safe_dir / f"{ordinal:02d}.dispatch.safe.json", journal)
    started = time.monotonic()
    # There is deliberately no retry wrapper around this one inference request.
    raw = client.request("/v1/chat/completions", request,
                         timeout=config["server"]["request_timeout_seconds"])
    elapsed = time.monotonic() - started
    helper.write_once(private_dir / f"{ordinal:02d}.reply.private.json", raw, raw=True)
    require(process.poll() is None, "OWNED_PROCESS_EXITED_AFTER_DISPATCH")
    measured = parse_reply(config, item, raw, helper)
    row = {**journal, **measured, "request_max_tokens": 512,
           "received_at": helper.utc_now(), "latency_seconds": elapsed}
    helper.write_once(safe_dir / f"{ordinal:02d}.row.safe.json", row)
    helper.emit("RESEARCH_REGIME_SMOKE_REQUEST_RECORDED", ordinal=ordinal, total=6,
                passed=row["passed"], finish_reason=row["finish_reason"])
    return row


def reconcile(config, contract_sha, safe_dir, private_dir, helper):
    plan = plan_for(config)
    journals = sorted(safe_dir.glob("*.dispatch.safe.json"))
    replies = sorted(private_dir.glob("*.reply.private.json"))
    safe_rows = sorted(safe_dir.glob("*.row.safe.json"))
    require(len(journals) <= 6 and len(replies) <= 6 and len(safe_rows) <= 6,
            "RECEIPT_CEILING_VIOLATION")
    epoch_path = safe_dir / "server-01.identity.safe.json"
    require(epoch_path.is_file() or not journals, "OWNED_SERVER_EPOCH_MISSING")
    epoch = strict_json(epoch_path.read_bytes()) if epoch_path.is_file() else {}
    rows = []
    for item in plan[:len(journals)]:
        prefix = f"{item['ordinal']:02d}"
        journal_path = safe_dir / f"{prefix}.dispatch.safe.json"
        require(journal_path in journals, "DISPATCH_NOT_PLAN_PREFIX")
        journal = strict_json(journal_path.read_bytes())
        expected = {
            "contract_sha256": contract_sha, "proposal_sha256": config["proposal"]["sha256"],
            "ordinal": item["ordinal"], "seed": item["seed"], "epoch": 1,
            "task_id": item["task"]["task_id"], "fixture_id": item["task"]["fixture_id"],
            "request_sha256": digest(request_for(config, item)),
            "served_chat_template_sha256": config["runtime"]["served_chat_template_sha256"],
        }
        require(all(same(journal.get(key), value) for key, value in expected.items()),
                "JOURNAL_PLAN_BINDING_MISMATCH")
        require(epoch.get("contract_sha256") == contract_sha and same(epoch.get("epoch"), 1)
                and epoch.get("owned_process_only") is True
                and type(epoch.get("pid")) is int and epoch["pid"] > 0
                and same(journal.get("process_id"), epoch["pid"])
                and epoch.get("served_chat_template_sha256")
                == config["runtime"]["served_chat_template_sha256"],
                "JOURNAL_EPOCH_BINDING_MISMATCH")
        helper.verify_template_observation(
            config, contract_sha, safe_dir / f"{prefix}.tpl.safe.json",
            {"ordinal": item["ordinal"], "epoch": 1, "process_id": epoch["pid"]})
        request_path = private_dir / f"{prefix}.request.private.json"
        require(request_path.is_file() and same(strict_json(request_path.read_bytes()),
                                                request_for(config, item)),
                "PRIVATE_REQUEST_BINDING_MISMATCH")
        reply_path = private_dir / f"{prefix}.reply.private.json"
        require(reply_path.is_file(), "AMBIGUOUS_DISPATCH_NO_RETRY")
        measured = parse_reply(config, item, reply_path.read_bytes(), helper)
        row_path = safe_dir / f"{prefix}.row.safe.json"
        require(row_path.is_file(), "SAFE_ROW_MISSING_NO_RETRY")
        row = strict_json(row_path.read_bytes())
        require(all(same(row.get(key), value) for key, value in {**journal, **measured}.items())
                and same(row.get("request_max_tokens"), 512), "SAFE_ROW_RECEIPT_MISMATCH")
        require(type(row.get("latency_seconds")) in (int, float)
                and math.isfinite(row["latency_seconds"]) and row["latency_seconds"] >= 0,
                "ROW_LATENCY_INVALID")
        rows.append(row)
    require(len(journals) == len(replies) == len(safe_rows) == len(rows), "RECEIPT_COUNT_MISMATCH")
    require(len(list(private_dir.glob("*.request.private.json"))) == len(rows),
            "ORPHAN_PRIVATE_REQUEST")
    return rows


def stopped_epoch(config, contract_sha, safe_dir, helper):
    paths = [safe_dir / f"server-01.{part}.safe.json"
             for part in ("started", "identity", "stopped")]
    if not all(path.is_file() for path in paths):
        return False
    records = [strict_json(path.read_bytes()) for path in paths]
    require(all(row.get("contract_sha256") == contract_sha and same(row.get("epoch"), 1)
                and row.get("owned_process_only") is True for row in records),
            "SERVER_EPOCH_BINDING_MISMATCH")
    require(type(records[0].get("pid")) is int and records[0]["pid"] > 0
            and all(same(row.get("pid"), records[0]["pid"]) for row in records),
            "SERVER_EPOCH_PID_MISMATCH")
    require(type(records[2].get("returncode")) is int, "SERVER_STOP_NOT_OBSERVED")
    helper.verify_template_observation(config, contract_sha, safe_dir / "server-01.tpl.safe.json",
                                        {"epoch": 1, "process_id": records[0]["pid"]})
    require(not (safe_dir / "server-02.started.safe.json").exists(),
            "SECOND_SERVER_EPOCH_FORBIDDEN")
    return True


def summarize(config, contract_sha, rows, stopped):
    complete = len(rows) == 6
    passes = sum(row["passed"] for row in rows)
    return {
        "schema_version": SCHEMA, "contract_sha256": contract_sha,
        "proposal_sha256": config["proposal"]["sha256"], "purpose": PURPOSE,
        "evidence_class": config["evidence_class"], "complete": complete,
        "request_count": len(rows), "request_ceiling": 6, "task_count": 2, "seed_count": 3,
        "exact_task_passes": passes, "pass_denominator": 6,
        "bare_control_stochastic_regime_smoke_passed": complete and passes == 6 and stopped,
        "owned_server_stopped": stopped, "one_execution_batch": True,
        "prior_v2_basic_admission_gate_passed": False, "scientific_target_admitted": False,
        "judge_admitted": False, "jailbreak_confirmed": False, "paper_claim_supported": False,
        "fresh_capability_sample": False, "general_capability_demonstrated": False,
        "long_context_qualified": False, "automatic_next_experiment": False,
        "model_runtime_artifacts_rehashed": True, "historical_responses_rescored": False,
        "plan_sha256": digest(public_plan(config)), "rows": rows,
    }


def verify_reservation(config, contract_sha, reservation_path, safe_dir):
    require(reservation_path.is_file(), "NO_EXECUTION_TO_AUDIT")
    reservation = strict_json(reservation_path.read_bytes())
    expected = {"contract_sha256": contract_sha,
                "proposal_sha256": config["proposal"]["sha256"],
                "request_ceiling": 6, "resume_allowed": False}
    require(all(same(reservation.get(key), value) for key, value in expected.items()),
            "BATCH_RESERVATION_MISMATCH")
    lock_path = safe_dir / "execution.lock.safe.json"
    require(lock_path.is_file(), "EXECUTION_LOCK_MISSING")
    require(same(strict_json(lock_path.read_bytes()), {
        "contract_sha256": contract_sha, "request_ceiling": 6, "resume_allowed": False,
    }), "EXECUTION_LOCK_BINDING_MISMATCH")


def run(root, config_path, expected_sha, *, execute=False, audit_only=False):
    require(not (execute and audit_only), "EXECUTE_AUDIT_MUTUALLY_EXCLUSIVE")
    root = root.resolve()
    config, helper, _ = load_contract(root, config_path, expected_sha)
    safe_root = contained(root, SAFE_ROOT)
    reservation_path = safe_root / "one-batch.reserved.safe.json"
    safe_dir = contained(root, f"{SAFE_ROOT}/{expected_sha}")
    private_dir = contained(root, f"{PRIVATE_ROOT}/{expected_sha}")
    if not execute and not audit_only:
        return {"schema_version": SCHEMA, "contract_sha256": expected_sha,
                "preflight_passed": True, "calls_made": 0, "request_ceiling": 6,
                "model_runtime_artifacts_rehashed": True,
                "batch_already_reserved": reservation_path.exists(),
                "plan_sha256": digest(public_plan(config)), "plan": public_plan(config)}
    if audit_only:
        verify_reservation(config, expected_sha, reservation_path, safe_dir)
        rows = reconcile(config, expected_sha, safe_dir, private_dir, helper)
        result = summarize(config, expected_sha, rows, stopped_epoch(config, expected_sha,
                                                                    safe_dir, helper))
        saved = safe_dir / "result.safe.json"
        if saved.is_file():
            require(same(strict_json(saved.read_bytes()), result), "SAVED_RESULT_MISMATCH")
        return {"audit_only": True, **result}
    require(not reservation_path.exists(), "ONE_BATCH_ALREADY_RESERVED_NO_RETRY")
    require(not safe_dir.exists() and not private_dir.exists(), "EXECUTION_EXISTS_NO_RETRY")
    # This reservation is outside the contract-hash directory, so changing the
    # contract hash cannot silently reset the single-batch inference ceiling.
    helper.write_once(reservation_path, {"contract_sha256": expected_sha,
                                        "proposal_sha256": config["proposal"]["sha256"],
                                        "reserved_at": helper.utc_now(), "request_ceiling": 6,
                                        "resume_allowed": False})
    safe_dir.mkdir(parents=True, exist_ok=False)
    private_dir.mkdir(parents=True, exist_ok=False)
    helper.write_once(safe_dir / "execution.lock.safe.json", {
        "contract_sha256": expected_sha, "request_ceiling": 6, "resume_allowed": False,
    })
    try:
        with helper.owned_server(root, config, private_dir, safe_dir, 1, expected_sha) as owned:
            process, client, _ = owned
            for item in plan_for(config):
                dispatch_one(config, expected_sha, item, process, client,
                             safe_dir, private_dir, helper)
        verify_reservation(config, expected_sha, reservation_path, safe_dir)
        rows = reconcile(config, expected_sha, safe_dir, private_dir, helper)
        result = summarize(config, expected_sha, rows,
                           stopped_epoch(config, expected_sha, safe_dir, helper))
        helper.write_once(safe_dir / "result.safe.json", result)
        return result
    except Exception as error:
        is_safe = isinstance(error, (SmokeError, helper.AdmissionError))
        helper.write_once(safe_dir / "aborted.safe.json", {
            "contract_sha256": expected_sha,
            "error_code": str(error) if is_safe else type(error).__name__,
            "journaled_dispatches": len(list(safe_dir.glob("*.dispatch.safe.json"))),
            "reply_receipts": len(list(private_dir.glob("*.reply.private.json"))),
            "resume_allowed": False,
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--config-sha256", required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.root, args.config, args.config_sha256,
                     execute=args.execute, audit_only=args.audit_only)
        print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                         indent=2, sort_keys=True), flush=True)
        if args.execute and not result.get("bare_control_stochastic_regime_smoke_passed"):
            return 2
        return 0
    except Exception as error:
        # Imported helper errors also contain fixed codes, but conservatively
        # print only the class here; detailed safe codes live in abort receipts.
        code = str(error) if isinstance(error, SmokeError) else type(error).__name__
        print(json.dumps({"event": "SMOKE_STOPPED", "error_code": code,
                          "resume_allowed": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
