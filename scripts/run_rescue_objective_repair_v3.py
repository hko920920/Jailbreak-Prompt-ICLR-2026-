"""Frozen harmless objective-repair pilot; owned local servers and durable replies.

This is a new SYSTEM/USER target protocol, not inherited judge qualification.
Default invocation is static preflight. Screen and exact each require --execute.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402

SCHEMA = "jbspan-rescue-objective-repair-v3"
CONDITIONS = ("CLEAN", "UNEDITED", "ALL_BLANK", "ALIGNED")
OPERATORS = ("SOURCE_OMIT", "LAYOUT_BLANK")
WRAPPER = "scripts/run_rescue_local_development_v2.py"


def emit(status: str, **fields: Any) -> None:
    value = {"schema_version": SCHEMA, "status": status, **fields}
    support.content_free(value)
    print(json.dumps(value, sort_keys=True), flush=True)


def core_module():
    from jbspan import objective_repair

    return objective_repair


def verify_file(root: Path, spec: dict) -> None:
    path = support.contained(root, spec["path"])
    if support.file_digest(path) != spec["sha256"]:
        raise ValueError("frozen file identity differs")
    if "size_bytes" in spec and path.stat().st_size != spec["size_bytes"]:
        raise ValueError("frozen file size differs")


def verify_config(root: Path, relative: str, expected_sha: str) -> tuple[dict, list[dict]]:
    """Hash code/safe inputs only; no model, runtime archive or private output reads."""
    path = support.contained(root, relative)
    if support.file_digest(path) != expected_sha:
        raise ValueError("exact objective contract hash differs")
    config = support.read_object(path)
    if config.get("schema_version") != SCHEMA or config.get("frozen") is not True:
        raise ValueError("objective contract must be frozen")
    for spec in config["dependencies"].values():
        dependency = support.contained(root, spec["path"])
        if not dependency.is_relative_to(root / "artifacts"):
            verify_file(root, spec)
    required = {
        "scripts/run_rescue_objective_repair_v3.py",
        "src/jbspan/objective_repair.py",
        "src/jbspan/rescue_guidedeval_development.py",
        WRAPPER,
    }
    if not required.issubset({x["path"] for x in config["dependencies"].values()}):
        raise ValueError("all executed implementation dependencies must be frozen")
    cases = core_module().build_cases()
    if support.digest(cases) != config["case_manifest_sha256"]:
        raise ValueError("harmless case manifest differs")
    if len(cases) != 8 or len({x["case_id"] for x in cases}) != 8:
        raise ValueError("exactly eight distinct harmless cases required")
    if any(len(c["conflict_units"]) != 5 or len(c["aligned_units"]) != 5 for c in cases):
        raise ValueError("exactly five intervention units required")
    design = config["design"]
    if any(
        design.get(key) != value
        for key, value in {
            "cases": 8,
            "units": 5,
            "max_exact_cases_per_model": 2,
            "screen_conditions": list(CONDITIONS),
            "operators": list(OPERATORS),
            "minimum_eligible_per_model": 1,
            "selection": "FIRST_ELIGIBLE_PER_TASK_FAMILY_LEX_CASE_ID",
        }.items()
    ):
        raise ValueError("fixed pilot design differs")
    decoding = config["decoding"]
    if any(
        decoding.get(key) != value
        for key, value in {
            "seed": 11,
            "temperature": 0,
            "max_tokens": 128,
            "top_k": 1,
            "top_p": 1,
            "min_p": 0,
            "repeat_penalty": 1,
        }.items()
    ):
        raise ValueError("fixed pilot decoding differs")
    models = config["models"]
    if len(models) != 2 or len({m["model_id"] for m in models}) != 2:
        raise ValueError("exactly two target snapshots required")
    if len({m["alias"] for m in models}) != 2:
        raise ValueError("distinct exact target aliases required")
    port = config["runtime"]["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("explicit valid loopback port required")
    for model in models:
        support.contained(root, model["model"]["path"])
        for spec in model.get("additional_files", []):
            support.contained(root, spec["path"])
        args = model["server_args"]
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            raise ValueError("server arguments must be a string vector")
        for flag, value in (
            ("--host", "127.0.0.1"),
            ("--port", str(port)),
            ("--alias", model["alias"]),
            ("--parallel", "1"),
        ):
            if args.count(flag) != 1 or args[args.index(flag) + 1] != value:
                raise ValueError("server command differs from fixed local identity")
        if any(flag not in args for flag in ("--offline", "--jinja", "--no-webui")):
            raise ValueError("offline native chat template must be explicit")
        if any(flag in args for flag in ("--no-jinja", "--model", "-m")):
            raise ValueError("model override or chat flattening is not permitted")
    limits = config["limits"]
    if limits["maximum_unique_requests"] != 304:
        raise ValueError("maximum pilot dispatch bound differs")
    for key in (
        "per_request_seconds",
        "screen_seconds",
        "exact_seconds",
        "max_request_utf8_bytes",
        "max_reply_utf8_bytes",
    ):
        if type(limits[key]) is not int or limits[key] <= 0:
            raise ValueError("positive explicit time and byte limits required")
    for key, directory in (
        ("safe_base", "data/natural_language_localization"),
        ("private_base", "artifacts"),
    ):
        output = support.contained(root, config["recording"][key])
        if not output.is_relative_to(root / directory):
            raise ValueError("safe/private output separation differs")
    return config, sorted(cases, key=lambda c: c["case_id"])


def verify_execution_files(root: Path, config: dict) -> None:
    """Only called under --execute, before starting any owned model process."""
    for spec in config["dependencies"].values():
        verify_file(root, spec)
    verify_file(root, config["runtime"]["server"])
    if "runtime_archive" not in config["dependencies"]:
        raise ValueError("runtime archive must be explicitly frozen")
    runtime_directory = support.contained(root, config["runtime"]["server"]["path"]).parent
    covered = {support.contained(root, x["path"]) for x in config["dependencies"].values()}
    if not set(runtime_directory.glob("*.dll")).issubset(covered):
        raise ValueError("all runtime DLLs must have frozen dependency identities")
    for model in config["models"]:
        verify_file(root, model["model"])
        for spec in model.get("additional_files", []):
            verify_file(root, spec)


def lifecycle_module(root: Path):
    spec = importlib.util.spec_from_file_location("_objective_owned_server_v3", root / WRAPPER)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen owned-server helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_request(config: dict, model: dict, messages: list[dict]) -> dict:
    return {"model": model["alias"], "messages": messages, **config["decoding"]}


def plan_row(
    config: dict,
    model: dict,
    case: dict,
    *,
    condition: str,
    mask: int,
    operator: str,
    aligned: bool = False,
) -> dict:
    messages = core_module().build_messages(case, mask, operator, aligned=aligned)
    request = make_request(config, model, messages)
    request_sha = support.digest(request)
    execution_key = support.digest({"model_id": model["model_id"], "request_sha256": request_sha})
    row = {
        "model_id": model["model_id"],
        "case_id": case["case_id"],
        "condition": condition,
        "removed_mask": mask,
        "operator": operator,
        "aligned": aligned,
        "request_sha256": request_sha,
        "execution_key": execution_key,
        "expected_answer_sha256": support.digest(case["expected_answer"]),
    }
    row["row_id"] = support.digest(row)
    return {**row, "request": request, "expected_answer": case["expected_answer"]}


def public_plan(plan: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in row.items() if k not in {"request", "expected_answer"}} for row in plan
    ]


def screen_plan(config: dict, cases: list[dict]) -> list[dict]:
    result = []
    controls = (
        ("CLEAN", 31, "SOURCE_OMIT", False),
        ("UNEDITED", 0, "SOURCE_OMIT", False),
        ("ALL_BLANK", 31, "LAYOUT_BLANK", False),
        ("ALIGNED", 0, "SOURCE_OMIT", True),
    )
    for model in config["models"]:
        for case in sorted(cases, key=lambda c: c["case_id"]):
            for condition, mask, operator, aligned in controls:
                result.append(
                    plan_row(
                        config,
                        model,
                        case,
                        condition=condition,
                        mask=mask,
                        operator=operator,
                        aligned=aligned,
                    )
                )
    return result


def select_eligible(config: dict, cases: list[dict], screen: dict) -> dict[str, list[str]]:
    expected = screen_plan(config, cases)
    rows = screen.get("rows", [])
    if len(rows) != 64 or len({r["row_id"] for r in rows}) != 64:
        raise ValueError("all 64 logical screen rows required before exact phase")
    indexed = {r["row_id"]: r for r in rows}
    cells = {}
    for planned in public_plan(expected):
        row = indexed.get(planned["row_id"])
        if row is None or any(row.get(k) != v for k, v in planned.items()):
            raise ValueError("screen row does not bind its frozen request")
        if row.get("status") not in {"CORRECT", "INCORRECT", "UNKNOWN"}:
            raise ValueError("screen status is invalid")
        cells[(row["model_id"], row["case_id"], row["condition"])] = row["status"]
    selected = {}
    for model in config["models"]:
        selected[model["model_id"]] = []
        for family in sorted({c["task_family"] for c in cases}):
            for case in sorted(cases, key=lambda c: c["case_id"]):
                if case["task_family"] != family:
                    continue
                key = (model["model_id"], case["case_id"])
                conditions = {condition: cells[(*key, condition)] for condition in CONDITIONS}
                if core_module().screen_eligible(conditions):
                    selected[model["model_id"]].append(case["case_id"])
                    break
        if len(selected[model["model_id"]]) > 2:
            raise ValueError("selection exceeds fixed two-family design")
    return selected


def exact_plan(config: dict, cases: list[dict], screen: dict) -> tuple[list[dict], dict]:
    selected = select_eligible(config, cases, screen)
    by_case = {case["case_id"]: case for case in cases}
    result = []
    for model in config["models"]:
        for case_id in selected[model["model_id"]]:
            for operator in OPERATORS:
                for mask in range(32):
                    result.append(
                        plan_row(
                            config,
                            model,
                            by_case[case_id],
                            condition="EXACT",
                            mask=mask,
                            operator=operator,
                        )
                    )
    combined = screen_plan(config, cases) + result
    if len({r["execution_key"] for r in combined}) > 304:
        raise ValueError("frozen unique request ceiling exceeded")
    return result, selected


def parse_reply(reply: dict, model: dict, expected: str) -> dict:
    error = None
    text = None
    finish = None
    completed_refusal = False
    if reply.get("model") != model["alias"]:
        error = "RETURNED_MODEL_MISMATCH"
    choices = reply.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        error = error or "MALFORMED_REPLY"
    else:
        finish = choices[0].get("finish_reason")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            error = error or "MALFORMED_REPLY"
        else:
            text = message.get("content")
            if isinstance(message.get("refusal"), str) and message["refusal"].strip():
                completed_refusal = not text
            if not isinstance(text, str) and not completed_refusal:
                error = error or "MALFORMED_REPLY"
            if message.get("tool_calls") or message.get("function_call"):
                error = error or "UNEXPECTED_TOOL_OUTPUT"
            if message.get("reasoning_content") or message.get("reasoning"):
                error = error or "UNEXPECTED_SEPARATE_REASONING"
            if message.get("role", "assistant") != "assistant":
                error = error or "UNEXPECTED_MESSAGE_ROLE"
        if finish != "stop":
            error = error or "NONSTOP_OR_TRUNCATED_OUTPUT"
    if error is not None:
        score = None
    elif completed_refusal:
        score = {"status": "INCORRECT", "reason": "COMPLETED_REFUSAL"}
    else:
        score = core_module().score_response(text, expected)
    usage = reply.get("usage")
    tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    return {
        "status": "UNKNOWN" if score is None else score["status"],
        "error_code": error,
        "score_reason": None if score is None else score["reason"],
        "reply_sha256": support.digest(reply),
        "output_sha256": support.digest(text),
        "finish_reason_sha256": support.digest(finish),
        "returned_model_sha256": support.digest(reply.get("model")),
        "completion_tokens": tokens if type(tokens) is int and tokens >= 0 else None,
    }


def request_identity(contract_sha: str, row: dict) -> dict:
    return {
        "contract_sha256": contract_sha,
        **{
            k: row[k]
            for k in ("model_id", "execution_key", "request_sha256", "expected_answer_sha256")
        },
    }


def endpoint(config: dict) -> dict:
    return {
        "endpoint": f"http://127.0.0.1:{config['runtime']['port']}/v1/chat/completions",
        "auth_required": False,
        "timeout_seconds": config["limits"]["per_request_seconds"],
        "max_request_utf8_bytes": config["limits"]["max_request_utf8_bytes"],
        "max_reply_utf8_bytes": config["limits"]["max_reply_utf8_bytes"],
    }


def load_checkpoint(directory: Path, identity: dict) -> dict | None:
    key = identity["execution_key"]
    pending = directory / f"{key}.pending.safe.json"
    completed = directory / f"{key}.reply.private.json"
    if completed.exists():
        stored = support.read_object(completed)
        body = {k: v for k, v in stored.items() if k != "receipt_sha256"}
        if (
            stored.get("identity") != identity
            or stored.get("receipt_sha256") != support.digest(body)
            or not pending.exists()
            or support.read_object(pending) != identity
        ):
            raise ValueError("durable reply identity or journal differs")
        return {**stored["safe_result"], "private_receipt_sha256": stored["receipt_sha256"]}
    if pending.exists():
        raise support.TransportFailure("UNFINISHED_DISPATCH_NO_AUTOMATIC_RETRY")
    return None


def evaluate_once(
    directory: Path, contract_sha: str, config: dict, model: dict, row: dict, *, send=None
) -> dict:
    identity = request_identity(contract_sha, row)
    previous = load_checkpoint(directory, identity)
    if previous is not None:
        return previous
    request = row["request"]
    if support.digest(request) != row["request_sha256"]:
        raise ValueError("request differs from frozen plan")
    if len(support.encode(request)) > config["limits"]["max_request_utf8_bytes"]:
        raise ValueError("request exceeds frozen byte bound")
    directory.mkdir(parents=True, exist_ok=True)
    if (
        len(list(directory.glob("*.pending.safe.json")))
        >= config["limits"]["maximum_unique_requests"]
    ):
        raise RuntimeError("frozen dispatch ceiling reached before new request")
    key = row["execution_key"]
    # Exclusive ownership and fsync before dispatch; even a torn marker blocks retries.
    with (directory / f"{key}.pending.safe.json").open("xb") as handle:
        handle.write(support.encode(identity))
        handle.flush()
        os.fsync(handle.fileno())
    started = time.monotonic()
    reply = None
    try:
        reply = (send or support.transport)(endpoint(config), request)
        safe = parse_reply(reply, model, row["expected_answer"])
    except support.TransportFailure:
        safe = {
            "status": "UNKNOWN",
            "error_code": "TRANSPORT_UNCERTAIN_NO_RETRY",
            "score_reason": None,
            "reply_sha256": None,
            "output_sha256": None,
            "finish_reason_sha256": None,
            "returned_model_sha256": None,
            "completion_tokens": None,
        }
    safe["elapsed_seconds"] = round(time.monotonic() - started, 6)
    support.content_free(safe)
    stored = {"identity": identity, "safe_result": safe, "raw_reply": reply}
    stored["receipt_sha256"] = support.digest(stored)
    support.write_once(directory / f"{key}.reply.private.json", stored, safe=False)
    return {**safe, "private_receipt_sha256": stored["receipt_sha256"]}


@contextmanager
def progress(directory: Path, phase: str, logical_rows: int):
    stopped = threading.Event()

    def report() -> None:
        while not stopped.is_set():
            completed = len(list(directory.glob("*.reply.private.json")))
            pending = len(list(directory.glob("*.pending.safe.json")))
            emit(
                "OBJECTIVE_CHECKPOINT_PROGRESS",
                phase=phase,
                logical_rows=logical_rows,
                completed_unique_replies=completed,
                journaled_unique_requests=pending,
                unfinished_dispatches=max(0, pending - completed),
            )
            stopped.wait(30)

    thread = threading.Thread(target=report, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


def verify_result(value: dict, contract_sha: str, phase: str) -> None:
    body = {k: v for k, v in value.items() if k != "result_identity_sha256"}
    if (
        value.get("schema_version") != SCHEMA
        or value.get("contract_sha256") != contract_sha
        or value.get("phase") != phase
        or value.get("complete") is not True
        or value.get("result_identity_sha256") != support.digest(body)
    ):
        raise ValueError("immutable phase result binding differs")
    support.content_free(value)


def directories(root: Path, config: dict, contract_sha: str) -> tuple[Path, Path]:
    safe = support.contained(root, config["recording"]["safe_base"]) / contract_sha
    private = support.contained(root, config["recording"]["private_base"]) / contract_sha
    return safe, private


def prepare_plan(
    root: Path, config: dict, cases: list[dict], contract_sha: str, phase: str
) -> tuple[list[dict], dict, str | None]:
    if phase == "screen":
        return screen_plan(config, cases), {}, None
    safe, _ = directories(root, config, contract_sha)
    screen_path = safe / "screen.safe.json"
    screen = support.read_object(screen_path)
    verify_result(screen, contract_sha, "screen")
    plan, selected = exact_plan(config, cases, screen)
    return plan, selected, support.file_digest(screen_path)


def run(root: Path, relative: str, contract_sha: str, phase: str, *, execute: bool) -> dict:
    config, cases = verify_config(root, relative, contract_sha)
    plan, selected, screen_sha = prepare_plan(root, config, cases, contract_sha, phase)
    safe_directory, private_directory = directories(root, config, contract_sha)
    result_path = safe_directory / f"{phase}.safe.json"
    plan_safe = public_plan(plan)
    unique_count = len({r["execution_key"] for r in plan})
    if not execute:
        value = {
            "phase": phase,
            "contract_sha256": contract_sha,
            "logical_rows": len(plan),
            "unique_phase_requests": unique_count,
            "selected_case_ids": selected,
            "private_inputs_read": False,
            "model_files_read": False,
            "network_calls": 0,
        }
        emit("OBJECTIVE_STATIC_PREFLIGHT_PASS", **value)
        return value
    if result_path.exists():
        result = support.read_object(result_path)
        verify_result(result, contract_sha, phase)
        if result.get("plan_sha256") != support.digest(plan_safe):
            raise ValueError("completed phase does not bind regenerated plan")
        emit("OBJECTIVE_COMPLETED_PHASE_REUSED", phase=phase, network_calls=0)
        return result
    checkpoints = private_directory / "checkpoints"
    # Scan all planned journal identities before model reads or server launch.
    for row in plan:
        cached = load_checkpoint(checkpoints, request_identity(contract_sha, row))
        if cached and cached.get("error_code") == "RETURNED_MODEL_MISMATCH":
            raise RuntimeError("previous returned model mismatch requires review")
    receipt = {
        "schema_version": SCHEMA,
        "phase": phase,
        "contract_sha256": contract_sha,
        "plan_sha256": support.digest(plan_safe),
        "rows": plan_safe,
        "selected_case_ids": selected,
        "screen_file_sha256": screen_sha,
        "frozen_before_first_phase_dispatch": True,
        "maximum_unique_requests": 304,
    }
    support.write_once(safe_directory / f"{phase}.plan.safe.json", receipt)
    needs_calls = any(
        load_checkpoint(checkpoints, request_identity(contract_sha, row)) is None for row in plan
    )
    if needs_calls:
        verify_execution_files(root, config)
    lifecycle = lifecycle_module(root)
    lifecycle.disable_process_proxies()
    deadline = time.monotonic() + config["limits"][f"{phase}_seconds"]
    rows = []
    with progress(checkpoints, phase, len(plan)):
        for model in config["models"]:
            target_plan = [r for r in plan if r["model_id"] == model["model_id"]]
            missing = [
                r
                for r in target_plan
                if load_checkpoint(checkpoints, request_identity(contract_sha, r)) is None
            ]

            def collect(target_plan=target_plan, model=model) -> None:
                for row in target_plan:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("frozen phase walltime reached; no further dispatch")
                    result = evaluate_once(checkpoints, contract_sha, config, model, row)
                    rows.append({**public_plan([row])[0], **result})
                    if result.get("error_code") == "RETURNED_MODEL_MISMATCH":
                        raise RuntimeError("returned target model mismatch requires review")

            if missing:
                command = [
                    str(support.contained(root, config["runtime"]["server"]["path"])),
                    "--model",
                    str(support.contained(root, model["model"]["path"])),
                    *model["server_args"],
                ]
                with lifecycle.owned_server(
                    command,
                    config["runtime"]["port"],
                    model["alias"],
                    config["runtime"]["startup_seconds"],
                ) as process:
                    template_sha = None
                    try:
                        properties = lifecycle.local_json(config["runtime"]["port"], "/props")
                        if "chat_template" in properties:
                            template_sha = support.digest(properties["chat_template"])
                    except (OSError, ValueError):
                        pass  # Optional provenance does not create a qualification gate.
                    support.write_once(
                        safe_directory / f"owned_server_{process.pid}_{time.time_ns()}.safe.json",
                        {
                            "contract_sha256": contract_sha,
                            "phase": phase,
                            "model_id": model["model_id"],
                            "process_id": process.pid,
                            "command_sha256": support.digest(command),
                            "owned_process_only": True,
                            "native_chat_template_sha256": template_sha,
                        },
                    )
                    collect()
            else:
                collect()
    result = {
        "schema_version": SCHEMA,
        "phase": phase,
        "contract_sha256": contract_sha,
        "complete": True,
        "plan_sha256": support.digest(plan_safe),
        "screen_file_sha256": screen_sha,
        "logical_rows": len(rows),
        "unique_phase_requests": unique_count,
        "total_journaled_unique_requests": len(list(checkpoints.glob("*.pending.safe.json"))),
        "selected_case_ids": selected,
        "rows": rows,
        "counts": {
            status: sum(r["status"] == status for r in rows)
            for status in ("CORRECT", "INCORRECT", "UNKNOWN")
        },
        "owned_servers_stopped": True,
        "maximum_paid_cost_usd": 0,
        "scope": "HARMLESS_OBJECTIVE_DEVELOPMENT_PILOT_NOT_SAFETY_VALIDATION",
    }
    if result["total_journaled_unique_requests"] > 304:
        raise RuntimeError("dispatch ceiling exceeded")
    if phase == "screen":
        result["selected_case_ids"] = select_eligible(config, cases, result)
    result["result_identity_sha256"] = support.digest(result)
    support.write_once(result_path, result)
    emit(
        "OBJECTIVE_PHASE_COMPLETED",
        phase=phase,
        counts=result["counts"],
        selected_case_ids=result["selected_case_ids"],
        safe_result=str(result_path.relative_to(root)).replace("\\", "/"),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--phase", choices=("screen", "exact"), required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        run(args.root.resolve(), args.config, args.config_sha256, args.phase, execute=args.execute)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        emit(
            "OBJECTIVE_PHASE_STOPPED",
            phase=args.phase,
            error_type=type(exc).__name__,
            uncertain_dispatch=isinstance(exc, support.TransportFailure),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
