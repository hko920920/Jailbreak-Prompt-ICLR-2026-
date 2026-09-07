"""Prospective harmless witness validation with frozen V3 transport and parser.

No V3 observations are reused as V4 evidence. The fixed frame is measured without
screening, outcome-dependent exclusion, request retries, or template repair.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402

SCHEMA = "jbspan-rescue-objective-transfer-v4"
PHASE = "validation"
REFERENCE_CONFIG = "configs/natural_language_localization/rescue_objective_repair_v3.json"
REFERENCE_SHA256 = "e6f7a170395f75d99b1b39f7b462dff07ed7dfb1fa5fc0519d5ab0b352d9e65d"
FROZEN_RUNNER = "scripts/run_rescue_objective_repair_v3.py"
FROZEN_RUNNER_SHA256 = "28b340f132d8f562f844c4c25215725b11917b0508d9bbb2f514a5835acf977d"


def emit(status: str, **fields: Any) -> None:
    value = {"schema_version": SCHEMA, "phase": PHASE, "status": status, **fields}
    support.content_free(value)
    print(json.dumps(value, sort_keys=True), flush=True)


def frozen_runner(root: Path):
    path = support.contained(root, FROZEN_RUNNER)
    if support.file_digest(path) != FROZEN_RUNNER_SHA256:
        raise ValueError("V3 transport/parser implementation changed")
    spec = importlib.util.spec_from_file_location("_frozen_objective_runner_for_v4", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen V3 helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def core_module():
    from jbspan import objective_transfer

    return objective_transfer


def verify_reference(root: Path, config: dict) -> dict:
    if config.get("reference_v3") != {"path": REFERENCE_CONFIG, "sha256": REFERENCE_SHA256}:
        raise ValueError("explicit pinned V3 reference is required")
    path = support.contained(root, REFERENCE_CONFIG)
    if support.file_digest(path) != REFERENCE_SHA256:
        raise ValueError("frozen V3 reference contract differs")
    reference = support.read_object(path)
    for key in ("runtime", "models", "decoding"):
        if config[key] != reference[key]:
            raise ValueError("V4 model/runtime/decoding must equal the frozen V3 protocol")
    for name, spec in reference["dependencies"].items():
        if spec not in config["dependencies"].values():
            raise ValueError("frozen V3 implementation dependency is not preserved: " + name)
    return reference


def verify_config(root: Path, relative: str, expected_sha: str) -> tuple[dict, list, list, Any]:
    """Read frozen code and safe contracts only, never model/runtime artifact bytes."""
    path = support.contained(root, relative)
    if support.file_digest(path) != expected_sha:
        raise ValueError("exact V4 contract file hash differs")
    config = support.read_object(path)
    if config.get("schema_version") != SCHEMA or config.get("frozen") is not True:
        raise ValueError("V4 validation contract must be frozen")
    verify_reference(root, config)
    helper = frozen_runner(root)
    for spec in config["dependencies"].values():
        if not support.contained(root, spec["path"]).is_relative_to(root / "artifacts"):
            helper.verify_file(root, spec)
    required = {
        "scripts/run_rescue_objective_transfer_v4.py",
        "tests/test_objective_transfer_runner_v4.py",
        "src/jbspan/objective_transfer.py",
    }
    if not required.issubset({s["path"] for s in config["dependencies"].values()}):
        raise ValueError("new V4 code and runner tests must be hash-bound")
    core = core_module()
    cases, strata = core.build_cases(), core.build_strata()
    if (
        support.digest(cases) != config["case_manifest_sha256"]
        or support.digest(strata) != config["strata_manifest_sha256"]
    ):
        raise ValueError("fixed case or stratum manifest differs")
    if len(cases) != 128 or len({case["case_id"] for case in cases}) != 128:
        raise ValueError("all 128 style-specific cases are required")
    if len(strata) != 5 or len({s["stratum_id"] for s in strata}) != 5:
        raise ValueError("all five unique strata are required")
    expected_design = {
        "task_data_per_family": 32,
        "task_families": ["lookup", "sort"],
        "cases": 128,
        "strata": 5,
        "selection": "NO_OUTCOME_SELECTION_ALL_FROZEN_CASES",
        "expected_logical_rows": 1280,
        "expected_unique_requests": 1120,
    }
    if any(config["design"].get(k) != v for k, v in expected_design.items()):
        raise ValueError("fixed V4 frame or no-selection design differs")
    limits = config["limits"]
    if limits["maximum_unique_requests"] != 1120:
        raise ValueError("fixed 1,120-request dispatch ceiling differs")
    if type(limits["validation_seconds"]) is not int or limits["validation_seconds"] <= 0:
        raise ValueError("positive validation walltime ceiling required")
    reference = support.read_object(root / REFERENCE_CONFIG)
    for key in ("per_request_seconds", "max_request_utf8_bytes", "max_reply_utf8_bytes"):
        if limits[key] != reference["limits"][key]:
            raise ValueError("per-request timing/byte contract differs from V3")
    for key, prefix in (
        ("safe_base", "data/natural_language_localization"),
        ("private_base", "artifacts"),
    ):
        output = support.contained(root, config["recording"][key])
        if not output.is_relative_to(root / prefix):
            raise ValueError("safe/private output separation differs")
        if output == support.contained(root, reference["recording"][key]):
            raise ValueError("V4 cannot share its output base with V3")
    return config, cases, strata, helper


def build_plan(config: dict, cases: list[dict], strata: list[dict], helper: Any) -> list[dict]:
    result = []
    core = core_module()
    for model in config["models"]:
        for stratum in strata:
            if stratum["model_id"] != model["model_id"]:
                continue
            witness = stratum["witness_mask"]
            if type(witness) is not int or not 0 < witness < 32:
                raise ValueError("nonempty five-unit witness mask required")
            selected_cases = sorted(
                (
                    case
                    for case in cases
                    if case["task_family"] == stratum["task_family"]
                    and case["conflict_style"] == stratum["conflict_style"]
                ),
                key=lambda case: case["case_id"],
            )
            for case in selected_cases:
                queries = [
                    (
                        "SOURCE_WITNESS" if mask == witness else "SOURCE_PROPER",
                        mask,
                        "LAYOUT_BLANK",
                        False,
                    )
                    for mask in range(32)
                    if mask & witness == mask
                ]
                queries.extend(
                    [
                        ("TARGET_WITNESS", witness, "SOURCE_OMIT", False),
                        ("CLEAN", 31, "SOURCE_OMIT", False),
                        ("ALL_BLANK", 31, "LAYOUT_BLANK", False),
                        ("ALIGNED", 0, "SOURCE_OMIT", True),
                    ]
                )
                for role, mask, operator, aligned in queries:
                    messages = core.build_messages(case, mask, operator, aligned=aligned)
                    request = helper.make_request(config, model, messages)
                    request_sha = support.digest(request)
                    row = {
                        "stratum_id": stratum["stratum_id"],
                        "stratum_role": stratum["role"],
                        "witness_mask": witness,
                        "task_data_id": case["task_data_id"],
                        "presentation_sha256": case["presentation_sha256"],
                        "task_family": case["task_family"],
                        "conflict_style": case["conflict_style"],
                        "model_id": model["model_id"],
                        "case_id": case["case_id"],
                        "query_role": role,
                        "condition": role,
                        "removed_mask": mask,
                        "operator": operator,
                        "aligned": aligned,
                        "request_sha256": request_sha,
                        "execution_key": support.digest(
                            {"model_id": model["model_id"], "request_sha256": request_sha}
                        ),
                        "expected_answer_sha256": support.digest(case["expected_answer"]),
                    }
                    row["row_id"] = support.digest(row)
                    result.append(
                        {**row, "request": request, "expected_answer": case["expected_answer"]}
                    )
    return result


def public_plan(plan: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in row.items() if k not in {"request", "expected_answer"}} for row in plan
    ]


def verify_plan(plan: list[dict], config: dict) -> None:
    if len(plan) != 1280 or len({row["row_id"] for row in plan}) != 1280:
        raise ValueError("all 1,280 distinct logical stratum views are required")
    if len({row["execution_key"] for row in plan}) != 1120:
        raise ValueError("the frozen frame must resolve to exactly 1,120 unique requests")
    if len({row["task_data_id"] for row in plan}) != 64:
        raise ValueError("exactly 64 shared task-data units required")
    if len({row["stratum_id"] for row in plan}) != 5:
        raise ValueError("all five predeclared strata required")
    for stratum in {row["stratum_id"] for row in plan}:
        if len({row["task_data_id"] for row in plan if row["stratum_id"] == stratum}) != 32:
            raise ValueError("every stratum must retain all 32 task-data units")
    identities = {}
    for row in plan:
        request = row["request"]
        request_sha = support.digest(request)
        expected_sha = support.digest(row["expected_answer"])
        execution_key = support.digest({"model_id": row["model_id"], "request_sha256": request_sha})
        if (
            row["request_sha256"] != request_sha
            or row["execution_key"] != execution_key
            or row["expected_answer_sha256"] != expected_sha
        ):
            raise ValueError("request/expected-value identity differs")
        if len(support.encode(request)) > config["limits"]["max_request_utf8_bytes"]:
            raise ValueError("planned request exceeds the frozen byte bound")
        identity = (row["model_id"], request_sha, expected_sha)
        if execution_key in identities and identities[execution_key] != identity:
            raise ValueError("identical cached requests have incompatible expectations")
        identities[execution_key] = identity
    support.content_free(public_plan(plan))


def verify_result(result: dict, contract_sha: str, plan: list[dict]) -> None:
    body = {k: v for k, v in result.items() if k != "result_identity_sha256"}
    if (
        result.get("schema_version") != SCHEMA
        or result.get("phase") != PHASE
        or result.get("contract_sha256") != contract_sha
        or result.get("complete") is not True
        or result.get("result_identity_sha256") != support.digest(body)
        or result.get("plan_sha256") != support.digest(public_plan(plan))
    ):
        raise ValueError("completed validation result binding differs")
    rows = result.get("rows", [])
    if len(rows) != len(plan) or len({r["row_id"] for r in rows}) != len(plan):
        raise ValueError("completed validation omitted logical stratum views")
    for row, planned in zip(rows, public_plan(plan), strict=True):
        if any(row.get(k) != v for k, v in planned.items()):
            raise ValueError("completed logical row differs from the frozen plan")
        if row.get("status") not in {"CORRECT", "INCORRECT", "UNKNOWN"}:
            raise ValueError("unrecognized objective status")
    support.content_free(result)


@contextmanager
def progress(directory: Path):
    stopped = threading.Event()

    def report() -> None:
        while not stopped.is_set():
            completed = len(list(directory.glob("*.reply.private.json")))
            pending = len(list(directory.glob("*.pending.safe.json")))
            emit(
                "OBJECTIVE_TRANSFER_CHECKPOINT_PROGRESS",
                logical_rows=1280,
                expected_unique_requests=1120,
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


def frame_counts(plan: list[dict]) -> dict:
    return {
        "task_data_units": len({r["task_data_id"] for r in plan}),
        "model_task_data_units": len({(r["model_id"], r["task_data_id"]) for r in plan}),
        "stratum_task_data_units": len({(r["stratum_id"], r["task_data_id"]) for r in plan}),
    }


def stratum_views(rows: list[dict]) -> list[dict]:
    result = []
    for stratum in sorted({row["stratum_id"] for row in rows}):
        group = [row for row in rows if row["stratum_id"] == stratum]
        result.append(
            {
                "stratum_id": stratum,
                "stratum_role": group[0]["stratum_role"],
                "model_id": group[0]["model_id"],
                "task_family": group[0]["task_family"],
                "witness_mask": group[0]["witness_mask"],
                "task_data_units": len({row["task_data_id"] for row in group}),
                "logical_rows": len(group),
                "unique_requests": len({row["execution_key"] for row in group}),
                "counts": dict(Counter(row["status"] for row in group)),
                "row_ids": [row["row_id"] for row in group],
            }
        )
    return result


def run(root: Path, relative: str, contract_sha: str, *, execute: bool) -> dict:
    config, cases, strata, helper = verify_config(root, relative, contract_sha)
    plan = build_plan(config, cases, strata, helper)
    verify_plan(plan, config)
    plan_safe = public_plan(plan)
    plan_sha = support.digest(plan_safe)
    counts = frame_counts(plan)
    safe_directory, private_directory = helper.directories(root, config, contract_sha)
    result_path = safe_directory / "validation.safe.json"
    if not execute:
        value = {
            "contract_sha256": contract_sha,
            "plan_sha256": plan_sha,
            "logical_rows": len(plan),
            "unique_phase_requests": 1120,
            "fixed_frame_counts": counts,
            "private_inputs_read": False,
            "model_files_read": False,
            "network_calls": 0,
        }
        emit("OBJECTIVE_TRANSFER_STATIC_PREFLIGHT_PASS", **value)
        return value
    if result_path.exists():
        result = support.read_object(result_path)
        verify_result(result, contract_sha, plan)
        emit("OBJECTIVE_TRANSFER_COMPLETED_PHASE_REUSED", network_calls=0)
        return result
    checkpoints = private_directory / "checkpoints"
    cache = {}
    for row in plan:
        key = row["execution_key"]
        if key not in cache:
            cache[key] = helper.load_checkpoint(
                checkpoints, helper.request_identity(contract_sha, row)
            )
        if cache[key] and cache[key].get("error_code") == "RETURNED_MODEL_MISMATCH":
            raise RuntimeError("previous target model mismatch requires review")
    support.write_once(
        safe_directory / "validation.plan.safe.json",
        {
            "schema_version": SCHEMA,
            "phase": PHASE,
            "contract_sha256": contract_sha,
            "plan_sha256": plan_sha,
            "rows": plan_safe,
            "fixed_frame_counts": counts,
            "frozen_before_first_phase_dispatch": True,
            "maximum_unique_requests": 1120,
            "no_outcome_selection": True,
            "no_v3_response_reuse": True,
        },
    )
    if any(value is None for value in cache.values()):
        helper.verify_execution_files(root, config)
    lifecycle = helper.lifecycle_module(root)
    lifecycle.disable_process_proxies()
    deadline = time.monotonic() + config["limits"]["validation_seconds"]
    rows = []
    with progress(checkpoints):
        for model in config["models"]:
            target_plan = [row for row in plan if row["model_id"] == model["model_id"]]
            missing = any(cache[row["execution_key"]] is None for row in target_plan)

            def collect(target_plan=target_plan, model=model) -> None:
                for row in target_plan:
                    key = row["execution_key"]
                    if cache[key] is None:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("frozen validation walltime reached")
                        cache[key] = helper.evaluate_once(
                            checkpoints, contract_sha, config, model, row
                        )
                    measured = cache[key]
                    rows.append({**public_plan([row])[0], **measured})
                    if measured.get("error_code") == "RETURNED_MODEL_MISMATCH":
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
                        pass
                    support.write_once(
                        safe_directory / f"owned_server_{process.pid}_{time.time_ns()}.safe.json",
                        {
                            "contract_sha256": contract_sha,
                            "phase": PHASE,
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
    journaled = len(list(checkpoints.glob("*.pending.safe.json")))
    completed = len(list(checkpoints.glob("*.reply.private.json")))
    if journaled != 1120 or completed != 1120:
        raise RuntimeError("completed frame must have exactly 1,120 durable request receipts")
    result = {
        "schema_version": SCHEMA,
        "phase": PHASE,
        "contract_sha256": contract_sha,
        "complete": True,
        "plan_sha256": plan_sha,
        "logical_rows": len(rows),
        "unique_phase_requests": len(cache),
        "total_journaled_unique_requests": journaled,
        "completed_unique_replies": completed,
        "fixed_frame_counts": counts,
        "stratum_views": stratum_views(rows),
        "rows": rows,
        "counts": {
            status: sum(row["status"] == status for row in rows)
            for status in ("CORRECT", "INCORRECT", "UNKNOWN")
        },
        "unique_request_counts": dict(Counter(value["status"] for value in cache.values())),
        "owned_servers_stopped": True,
        "maximum_paid_cost_usd": 0,
        "no_outcome_selection": True,
        "no_v3_response_reuse": True,
        "scope": "HARMLESS_OBJECTIVE_FIXED_FRAME_VALIDATION_NOT_SAFETY_VALIDATION",
    }
    result["result_identity_sha256"] = support.digest(result)
    verify_result(result, contract_sha, plan)
    support.write_once(result_path, result)
    emit(
        "OBJECTIVE_TRANSFER_VALIDATION_COMPLETED",
        counts=result["counts"],
        unique_request_counts=result["unique_request_counts"],
        fixed_frame_counts=counts,
        safe_result=str(result_path.relative_to(root)).replace("\\", "/"),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--phase", choices=(PHASE,), default=PHASE)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        run(args.root.resolve(), args.config, args.config_sha256, execute=args.execute)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        emit(
            "OBJECTIVE_TRANSFER_VALIDATION_STOPPED",
            error_type=type(exc).__name__,
            uncertain_dispatch=isinstance(exc, support.TransportFailure),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
