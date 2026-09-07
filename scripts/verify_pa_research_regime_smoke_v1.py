"""Independently verify one COMPLETE six-call smoke, without inference or writes.

Reads only the exact execution/proposal/V2 contracts, explicitly pinned code and
documents, safe receipts and the NEW smoke's twelve harmless request/reply files.
Does not import an experiment runner, rehash model weights, inspect old private
records or query live processes. A failed smoke can still be correctly verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = "scripts/verify_pa_research_regime_smoke_v1.py"
CONFIG = "configs/natural_language_localization/pa_research_regime_smoke_execution_v1.json"
PROPOSAL = "configs/natural_language_localization/pa_research_regime_smoke_proposal_v1.json"
V2 = "configs/natural_language_localization/pa_llama_target_admission_v2.json"
SAFE = "data/natural_language_localization/pa_research_regime_smoke_v1"
PRIVATE = "artifacts/pa_research_regime_smoke_v1/private"
SCHEMA = "jbspan-pa-research-regime-smoke-execution-v1"
PURPOSE = "LIMITED_SCIENTIFIC_REQUEST_REGIME_SMOKE_ONLY"
EVIDENCE = "RESULT_INFORMED_DEVELOPMENT_OPERATIONAL_SMOKE_NOT_CONFIRMATION"
GENERATION = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "min_p": 0,
    "repeat_penalty": 1,
    "max_tokens": 512,
}
TASKS = [
    {
        "task_id": "P2_ARITHMETIC",
        "fixture_id": "arithmetic",
        "scorer": "integer",
        "expected": 42,
        "text": "What is 17 + 25? Reply with only the number.",
    },
    {
        "task_id": "P2_COPY_TOKEN",
        "fixture_id": "copy_token",
        "scorer": "exact_text",
        "expected": "alpha-7",
        "text": "Copy this token exactly and output nothing else: alpha-7",
    },
]


class VerificationError(ValueError):
    """Only fixed content-free codes are returned to callers."""


def check(condition, code):
    if not condition:
        raise VerificationError(code)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(value):
    return sha(encoded(value))


def equal(left, right):
    return encoded(left) == encoded(right)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise VerificationError("NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def path_under(root, relative):
    check(
        isinstance(relative, str)
        and "\\" not in relative
        and not Path(relative).is_absolute()
        and ".." not in Path(relative).parts,
        "INVALID_RELATIVE_PATH",
    )
    path = (root / relative).resolve()
    check(
        path != root
        and path.is_relative_to(root)
        and path.relative_to(root).as_posix() == relative,
        "PATH_ALIAS_OR_ESCAPE",
    )
    return path


def read(path, maximum=2_000_000):
    check(path.is_file() and 0 <= path.stat().st_size <= maximum, "FILE_SIZE_OR_ABSENCE")
    raw = path.read_bytes()
    check(len(raw) <= maximum, "FILE_GREW_OVER_LIMIT")
    return raw


def pinned(root, item, allowed):
    check(
        isinstance(item, dict) and set(item) == {"path", "size_bytes", "sha256"},
        "INVALID_DESCRIPTOR",
    )
    relative = item["path"]
    check(isinstance(relative, str) and allowed(relative), "PINNED_READ_OUTSIDE_SCOPE")
    check(
        type(item["size_bytes"]) is int
        and 0 <= item["size_bytes"] <= 2_000_000
        and isinstance(item["sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None,
        "INVALID_DESCRIPTOR_VALUE",
    )
    raw = read(path_under(root, relative))
    check(len(raw) == item["size_bytes"] and sha(raw) == item["sha256"], "PINNED_FILE_DRIFT")
    return raw


def timestamp(value):
    check(isinstance(value, str), "TIME_NOT_STRING")
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise VerificationError("TIME_INVALID") from None
    check(
        value.tzinfo is not None and value.utcoffset() == timezone.utc.utcoffset(value),
        "TIME_NOT_UTC",
    )
    return value


def plan(config):
    rows = []
    for seed in (11, 23, 47):
        for task in TASKS:
            request = {
                "model": config["model"]["alias"],
                "stream": False,
                "messages": [{"role": "user", "content": task["text"]}],
                **GENERATION,
                "seed": seed,
            }
            rows.append({"ordinal": len(rows) + 1, "seed": seed, "task": task, "request": request})
    return rows


def score(content, task):
    """Independent whole-answer implementation; no legacy scorer import."""
    check(isinstance(content, str), "CONTENT_NOT_TEXT")
    stripped = content.strip()
    if task["scorer"] == "integer":
        parsed = re.fullmatch(r"-?(0|[1-9][0-9]*)", stripped) is not None
        normalized = int(stripped) if parsed else stripped
    else:
        check(task["scorer"] == "exact_text", "SCORER_UNKNOWN")
        parsed, normalized = True, stripped
    correct = (
        parsed and type(normalized) is type(task["expected"]) and normalized == task["expected"]
    )
    return {
        "content_check_passed": correct,
        "scorer": task["scorer"],
        "parsed_as_required_type": parsed,
        "raw_content_sha256": sha(content.encode("utf-8")),
        "normalized_content_sha256": identity({"scorer": task["scorer"], "value": normalized}),
        "response_characters": len(content),
    }


def reply(raw, item, alias):
    value = decode(raw)
    check(isinstance(value, dict) and value.get("model") == alias, "REPLY_MODEL_OR_SHAPE")
    choices = value.get("choices")
    check(isinstance(choices, list) and len(choices) == 1, "CHOICE_COUNT")
    choice = choices[0]
    check(isinstance(choice, dict) and equal(choice.get("index"), 0), "CHOICE_INDEX")
    message = choice.get("message")
    check(isinstance(message, dict) and message.get("role") == "assistant", "REPLY_ROLE")
    check(
        not any(
            message.get(key)
            for key in ("tool_calls", "function_call", "refusal", "reasoning_content")
        ),
        "NONANSWER_CHANNEL",
    )
    measured = score(message.get("content"), item["task"])
    finish = choice.get("finish_reason")
    check(finish in {"stop", "length"}, "FINISH_REASON")
    usage = value.get("usage")
    names = ("prompt_tokens", "completion_tokens", "total_tokens")
    check(
        isinstance(usage, dict)
        and all(type(usage.get(key)) is int and usage[key] >= 0 for key in names),
        "USAGE_TYPE",
    )
    check(0 < usage["prompt_tokens"] <= 4096 and usage["completion_tokens"] <= 512, "USAGE_BOUNDS")
    check(not message["content"] or usage["completion_tokens"] > 0, "CONTENT_WITH_ZERO_TOKENS")
    check(usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], "USAGE_SUM")
    return {
        **measured,
        "finish_reason": finish,
        "not_truncated": finish == "stop",
        "passed": measured["content_check_passed"] and finish == "stop",
        "usage": {key: usage[key] for key in names},
        "reply_bytes_sha256": sha(raw),
    }


def template(value, config, contract_sha, pid, *, ordinal=None):
    runtime = config["runtime"]
    expected = {
        "contract_sha256": contract_sha,
        "epoch": 1,
        "process_id": pid,
        "native_chat_template_sha256": runtime["native_chat_template_sha256"],
        "expected_served_chat_template_sha256": runtime["served_chat_template_sha256"],
        "observed_served_chat_template_sha256": runtime["served_chat_template_sha256"],
        "expected_served_chat_template_utf8_bytes": runtime["served_chat_template_utf8_bytes"],
        "observed_served_chat_template_utf8_bytes": runtime["served_chat_template_utf8_bytes"],
        "template_source_available": True,
        "served_template_matches_pin": True,
    }
    if ordinal is not None:
        expected["ordinal"] = ordinal
    check(
        all(equal(value.get(key), wanted) for key, wanted in expected.items()), "TEMPLATE_BINDING"
    )


def expected_summary(config, contract_sha, rows):
    public_plan = [
        {
            "ordinal": item["ordinal"],
            "seed": item["seed"],
            "task_id": item["task"]["task_id"],
            "fixture_id": item["task"]["fixture_id"],
            "request_sha256": identity(item["request"]),
        }
        for item in plan(config)
    ]
    passes = sum(row["passed"] for row in rows)
    return {
        "schema_version": SCHEMA,
        "contract_sha256": contract_sha,
        "proposal_sha256": config["proposal"]["sha256"],
        "purpose": PURPOSE,
        "evidence_class": EVIDENCE,
        "complete": True,
        "request_count": 6,
        "request_ceiling": 6,
        "task_count": 2,
        "seed_count": 3,
        "exact_task_passes": passes,
        "pass_denominator": 6,
        "bare_control_stochastic_regime_smoke_passed": passes == 6,
        "owned_server_stopped": True,
        "one_execution_batch": True,
        "prior_v2_basic_admission_gate_passed": False,
        "scientific_target_admitted": False,
        "judge_admitted": False,
        "jailbreak_confirmed": False,
        "paper_claim_supported": False,
        "fresh_capability_sample": False,
        "general_capability_demonstrated": False,
        "long_context_qualified": False,
        "automatic_next_experiment": False,
        "model_runtime_artifacts_rehashed": True,
        "historical_responses_rescored": False,
        "plan_sha256": identity(public_plan),
        "rows": rows,
    }


def verify(root, contract_sha):
    root = root.resolve()
    check(
        isinstance(contract_sha, str) and re.fullmatch(r"[0-9a-f]{64}", contract_sha), "CONFIG_SHA"
    )
    raw_config = read(path_under(root, CONFIG))
    check(sha(raw_config) == contract_sha, "CONFIG_SHA_MISMATCH")
    config = decode(raw_config)
    fixed = {
        "schema_version": SCHEMA,
        "frozen": True,
        "execution_authorized": True,
        "purpose": PURPOSE,
        "evidence_class": EVIDENCE,
        "paper_validity": False,
        "request_ceiling": 6,
        "one_batch_only": True,
        "no_retries": True,
        "tasks": TASKS,
        "seeds": [11, 23, 47],
        "generation": GENERATION,
        "context_tokens": 4096,
        "paths": {"safe_root": SAFE, "private_root": PRIVATE},
    }
    check(
        all(equal(config.get(key), value) for key, value in fixed.items()), "FIXED_CONTRACT_CHANGED"
    )
    proposal = decode(pinned(root, config["proposal"], lambda path: path == PROPOSAL))
    check(
        proposal.get("frozen") is True
        and proposal.get("execution_authorized") is False
        and equal(proposal.get("current_allowed_calls"), 0),
        "PROPOSAL_NOT_ZERO_CALL",
    )
    for key in ("tasks", "seeds", "generation", "context_tokens"):
        check(equal(config[key], proposal.get(key)), "PROPOSAL_DESIGN_MISMATCH")
    v2 = decode(pinned(root, config["v2_contract"], lambda path: path == V2))
    check(equal(config["v2_contract"], proposal["sources"]["v2_contract"]), "V2_PIN_BINDING")
    for key in ("model", "runtime", "server"):
        check(equal(config[key], v2.get(key)), "OLD_RUNTIME_IDENTITY_CHANGED")
    check(config["server"]["host"] == "127.0.0.1", "NONLOCAL_SERVER")
    for item in config["required_code"].values():
        pinned(root, item, lambda path: re.fullmatch(r"(?:scripts|tests)/[A-Za-z0-9_]+\.py", path))
    for item in config["sources"]:
        pinned(root, item, lambda path: re.fullmatch(r"docs/[A-Za-z0-9_-]+\.md", path))

    safe_dir = path_under(root, f"{SAFE}/{contract_sha}")
    private_dir = path_under(root, f"{PRIVATE}/{contract_sha}")
    reservation = decode(read(path_under(root, f"{SAFE}/one-batch.reserved.safe.json")))
    expected_reservation = {
        "contract_sha256": contract_sha,
        "proposal_sha256": config["proposal"]["sha256"],
        "request_ceiling": 6,
        "resume_allowed": False,
    }
    check(
        set(reservation) == {*expected_reservation, "reserved_at"}
        and all(equal(reservation[key], value) for key, value in expected_reservation.items()),
        "BATCH_RESERVATION",
    )
    lock = decode(read(safe_dir / "execution.lock.safe.json"))
    check(
        equal(
            lock, {"contract_sha256": contract_sha, "request_ceiling": 6, "resume_allowed": False}
        ),
        "EXECUTION_LOCK",
    )
    safe_names = {"execution.lock.safe.json", "result.safe.json"}
    safe_names |= {
        f"server-01.{suffix}.safe.json" for suffix in ("started", "identity", "stopped", "tpl")
    }
    safe_names |= {
        f"{ordinal:02d}.{suffix}.safe.json"
        for ordinal in range(1, 7)
        for suffix in ("dispatch", "tpl", "row")
    }
    observed_safe = {path.name for path in safe_dir.iterdir()}
    check(
        observed_safe in (safe_names, safe_names | {"independent-verification.safe.json"}),
        "UNEXPECTED_OR_INCOMPLETE_SAFE_SET",
    )
    private_names = {
        f"{ordinal:02d}.{suffix}.private.json"
        for ordinal in range(1, 7)
        for suffix in ("request", "reply")
    } | {"server-01.log.private.txt"}
    check(
        {path.name for path in private_dir.iterdir()} == private_names,
        "UNEXPECTED_OR_INCOMPLETE_PRIVATE_SET",
    )
    check(
        all(path.is_file() and not path.is_symlink() for path in private_dir.iterdir())
        and all(path.is_file() and not path.is_symlink() for path in safe_dir.iterdir()),
        "RECEIPT_ALIAS_OR_NOT_FILE",
    )

    started = decode(read(safe_dir / "server-01.started.safe.json"))
    bound = decode(read(safe_dir / "server-01.identity.safe.json"))
    stopped = decode(read(safe_dir / "server-01.stopped.safe.json"))
    pid = started.get("pid")
    check(type(pid) is int and pid > 0, "OWNED_PID")
    for value in (started, bound, stopped):
        check(
            value.get("contract_sha256") == contract_sha
            and equal(value.get("epoch"), 1)
            and equal(value.get("pid"), pid)
            and value.get("owned_process_only") is True,
            "EPOCH_BINDING",
        )
    command = [
        str(path_under(root, config["runtime"]["server"]["path"])),
        "--model",
        str(path_under(root, config["model"]["entry_path"])),
        "--alias",
        config["model"]["alias"],
        "--host",
        "127.0.0.1",
        "--port",
        str(config["server"]["port"]),
        *config["runtime"]["server_args"],
    ]
    check(
        started.get("command_sha256") == identity(command)
        and all(equal(bound.get(key), value) for key, value in started.items()),
        "COMMAND_IDENTITY",
    )
    check(
        bound.get("served_chat_template_sha256")
        == config["runtime"]["served_chat_template_sha256"],
        "EPOCH_TEMPLATE_IDENTITY",
    )
    check(type(stopped.get("returncode")) is int, "NO_STOP_RETURN_CODE")
    start_time, stop_time = (
        timestamp(started.get("started_at")),
        timestamp(stopped.get("stopped_at")),
    )
    check(timestamp(reservation["reserved_at"]) <= start_time <= stop_time, "EPOCH_TIME_ORDER")
    template(decode(read(safe_dir / "server-01.tpl.safe.json")), config, contract_sha, pid)
    rows = []
    previous_received = start_time
    for item in plan(config):
        number = item["ordinal"]
        prefix = f"{number:02d}"
        journal = decode(read(safe_dir / f"{prefix}.dispatch.safe.json"))
        journal_expected = {
            "contract_sha256": contract_sha,
            "proposal_sha256": config["proposal"]["sha256"],
            "ordinal": number,
            "seed": item["seed"],
            "epoch": 1,
            "task_id": item["task"]["task_id"],
            "fixture_id": item["task"]["fixture_id"],
            "process_id": pid,
            "request_sha256": identity(item["request"]),
            "served_chat_template_sha256": config["runtime"]["served_chat_template_sha256"],
        }
        check(
            set(journal) == {*journal_expected, "dispatch_at"}
            and all(equal(journal[key], value) for key, value in journal_expected.items()),
            "DISPATCH_BINDING",
        )
        template(
            decode(read(safe_dir / f"{prefix}.tpl.safe.json")),
            config,
            contract_sha,
            pid,
            ordinal=number,
        )
        request = decode(read(private_dir / f"{prefix}.request.private.json"))
        check(equal(request, item["request"]), "PRIVATE_REQUEST_BINDING")
        measured = reply(
            read(private_dir / f"{prefix}.reply.private.json"), item, config["model"]["alias"]
        )
        saved = decode(read(safe_dir / f"{prefix}.row.safe.json"))
        expected_fields = {**journal, **measured, "request_max_tokens": 512}
        check(
            set(saved) == {*expected_fields, "received_at", "latency_seconds"}
            and all(equal(saved[key], value) for key, value in expected_fields.items()),
            "SAFE_ROW_RECONSTRUCTION",
        )
        dispatch_time, received_time = (
            timestamp(journal["dispatch_at"]),
            timestamp(saved["received_at"]),
        )
        check(
            previous_received <= dispatch_time <= received_time <= stop_time, "REQUEST_TIME_ORDER"
        )
        previous_received = received_time
        check(
            type(saved["latency_seconds"]) in (int, float)
            and math.isfinite(saved["latency_seconds"])
            and saved["latency_seconds"] >= 0,
            "LATENCY_INVALID",
        )
        rows.append(saved)
    saved_raw = read(safe_dir / "result.safe.json")
    result = decode(saved_raw)
    check(equal(result, expected_summary(config, contract_sha, rows)), "RESULT_RECONSTRUCTION")
    output = {
        "schema_version": "jbspan-pa-research-regime-smoke-independent-verification-v1",
        "independent_verification_passed": True,
        "contract_sha256": contract_sha,
        "saved_result_sha256": sha(saved_raw),
        "verified_requests": 6,
        "verified_replies": 6,
        "verified_template_observations": 7,
        "verified_owned_server_epochs": 1,
        "exact_task_passes": sum(row["passed"] for row in rows),
        "pass_denominator": 6,
        "smoke_gate_passed": result["bare_control_stochastic_regime_smoke_passed"],
        "prior_v2_gate_passed": False,
        "scientific_target_admitted": False,
        "paper_or_judge_or_jailbreak_admission": False,
        "new_model_calls": 0,
        "new_own_harmless_private_files_read": 12,
        "historical_private_files_read": 0,
        "private_server_log_content_read": False,
        "model_artifacts_rehashed_by_verifier": False,
        "live_process_absence_checked": False,
        "recorded_stop_and_order_verified": True,
        "runner_or_scorer_imported": False,
    }
    output["verification_identity_sha256"] = identity(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify(args.root, args.config_sha256)
    except Exception as error:
        code = str(error) if isinstance(error, VerificationError) else type(error).__name__
        print(
            json.dumps(
                {
                    "independent_verification_passed": False,
                    "error_code": code,
                    "new_model_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
