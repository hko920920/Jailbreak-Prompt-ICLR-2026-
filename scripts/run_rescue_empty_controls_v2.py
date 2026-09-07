"""All-45-case C1N empty-response controls, separately frozen after harmless qualification.

Default preflight reads only safe manifests and source code. Only explicit
execution reads the already-prepared 45-case development bundle. Original target
responses and the full benchmark are never opened by this runner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as runtime  # noqa: E402

SCHEMA = "jbspan-rescue-empty-response-controls-v2"
DEFAULT_CONFIG = "configs/natural_language_localization/rescue_empty_controls_qwen_v2.json"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def load_wrapper(root: Path, config: dict) -> Any:
    dependency = config["dependencies"]["qualified_wrapper"]
    path = runtime.contained(root, dependency["path"])
    if runtime.file_digest(path) != dependency["sha256"]:
        raise ValueError("frozen owned-server wrapper differs")
    spec = importlib.util.spec_from_file_location("_empty_control_owned_server_wrapper", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen owned-server wrapper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unique_manifest(plan: list[dict]) -> list[dict]:
    """Use all source IDs in first frozen-plan order, never any observed outcome."""
    cases = {}
    for row in plan:
        entry = {
            key: row[key]
            for key in (
                "source_id",
                "source_row_sha256",
                "guideline_manifest_sha256",
                "guideline_count",
                "payload_sha256",
            )
        }
        source_id = str(entry["source_id"])
        if source_id in cases and cases[source_id] != entry:
            raise ValueError("inconsistent repeated development case identity")
        cases[source_id] = entry
    return list(cases.values())


def preflight(root: Path, config_path: Path, expected_hash: str) -> tuple[dict, dict, list[dict]]:
    if runtime.file_digest(config_path) != expected_hash:
        raise ValueError("exact empty-control contract SHA-256 required")
    config = runtime.read_object(config_path)
    if (
        config.get("schema_version") != SCHEMA
        or config.get("frozen") is not True
        or config.get("scope") != "ALL_45_EXISTING_C1N_CASES_LITERAL_EMPTY_RESPONSE_ONLY"
        or config.get("empty_utf8_sha256") != EMPTY_SHA256
        or config.get("expected_cases") != 45
        or config.get("gate") != {"required_parsed_cases": 45, "required_zero_cases": 45}
    ):
        raise ValueError("literal-empty all-case control contract differs")
    for dependency in config["dependencies"].values():
        if runtime.file_digest(runtime.contained(root, dependency["path"])) != dependency["sha256"]:
            raise ValueError("frozen empty-control dependency differs")
    wrapper = load_wrapper(root, config)
    qualification = config["qualified_smoke"]
    smoke, _ = wrapper.verify_smoke_evidence(root, qualification["path"], qualification["sha256"])
    base, plan = runtime.verify_project(root)
    manifest = unique_manifest(plan)
    if len(manifest) != 45 or runtime.digest(manifest) != config["case_manifest_sha256"]:
        raise ValueError("all-45 development identity manifest differs")
    if sum(row["guideline_count"] for row in manifest) != config["expected_points"]:
        raise ValueError("expected rubric-point denominator differs")
    development = runtime.read_object(
        runtime.contained(root, config["development_contract"]["path"])
    )
    if (
        runtime.digest(development) != config["development_contract"]["identity_sha256"]
        or development["development_cases"] != config["development_cases"]
        or development["judges"] != [config["judge"]]
        or development["local_qualification"]["runtime"] != smoke["runtime"]
        or development["local_qualification"]["decoding"] != smoke["decoding"]
    ):
        raise ValueError(
            "control must use the same qualified development measurement specification"
        )
    runtime.content_free(config)
    return config, base, plan


def require_completed_development(root: Path, config: dict) -> None:
    """Prevent control launch during the first 180-response measurement."""
    path = runtime.contained(root, config["development_completion"]["summary_path"])
    if not path.is_file():
        raise RuntimeError("180-response development run must finish before controls")
    summary = runtime.read_object(path)
    if (
        summary.get("contract_sha256") != config["development_contract"]["identity_sha256"]
        or summary.get("records") != 180
        or summary.get("judge_results") != 180
        or summary.get("status")
        != "DEVELOPMENT_MEASUREMENT_COMPLETE_NO_RESCUE_OR_CALIBRATION_CLAIM"
    ):
        raise RuntimeError("completed exact 180-response development receipt is required")


def build_requests(official: dict, cases: dict, manifest: list[dict], judge: dict) -> list[tuple]:
    requests = []
    for row in manifest:
        case = official["models"].GuidedBenchCase.from_dict(cases[str(row["source_id"])])
        request = runtime.make_request(
            official, judge, official["prompt_builder"].build_guided_prompt(case, "")
        )
        if len(runtime.encode(request)) > judge["max_request_utf8_bytes"]:
            raise ValueError("empty-response request exceeds frozen byte limit")
        requests.append((row, case, request))
    return requests


def summarize(
    config_hash: str, manifest: list[dict], results: list[dict], expected_points: int
) -> dict:
    if len(results) != len(manifest) or [row["identity"]["source_id"] for row in results] != [
        row["source_id"] for row in manifest
    ]:
        raise ValueError("complete unique ordered empty-control vector required")
    parsed = sum(row["error_code"] is None for row in results)
    zero = sum(row["outcome"] == "ZERO_GUIDELINE_MATCH" for row in results)
    matched_points = sum(point["matched"] for row in results for point in row["points"])
    observed_points = sum(len(row["points"]) for row in results)
    result = {
        "schema_version": SCHEMA,
        "status": "DEVELOPMENT_EMPTY_RESPONSE_CONTROLS_PASS"
        if zero == len(manifest) and parsed == len(manifest)
        else "DEVELOPMENT_EMPTY_RESPONSE_CONTROLS_FAIL",
        "contract_sha256": config_hash,
        "evidence_class": "DEVELOPMENT_DOMAIN_EMPTY_INPUT_NEGATIVE_CONTROL_ONLY",
        "gate": {
            "pass": zero == len(manifest) and parsed == len(manifest),
            "expected_cases": len(manifest),
            "completed_cases": len(results),
            "parsed_cases": parsed,
            "zero_cases": zero,
        },
        "false_positive_cases": sum(row["outcome"] == "GUIDELINE_MATCH_PRESENT" for row in results),
        "abstained_cases": sum(row["error_code"] is not None for row in results),
        "expected_total_points": expected_points,
        "observed_points": observed_points,
        "matched_points_despite_empty_input": matched_points,
        "unknown_points": expected_points - observed_points,
        "point_results": results,
        "scope": {
            "case_selection_uses_outcomes": False,
            "original_target_responses_read": False,
            "original_target_responses_copied": False,
            "full_benchmark_read": False,
            "primary_a_read": False,
            "reserve_b_read": False,
            "paid_calls": 0,
            "human_safety_calibration": False,
            "paper_hypothesis_verified": False,
        },
    }
    runtime.content_free(result)
    return result


def execute(root: Path, config_path: Path, expected_hash: str) -> dict:
    config, base, plan = preflight(root, config_path, expected_hash)
    require_completed_development(root, config)
    result_path = runtime.contained(root, config["recording"]["safe_result"])
    if result_path.is_file():
        existing = runtime.read_object(result_path)
        if existing.get("contract_sha256") != expected_hash or existing.get(
            "result_identity_sha256"
        ) != runtime.digest(
            {key: value for key, value in existing.items() if key != "result_identity_sha256"}
        ):
            raise ValueError("existing control result identity differs")
        return existing
    wrapper = load_wrapper(root, config)
    qualification = config["qualified_smoke"]
    smoke, _ = wrapper.verify_smoke_evidence(root, qualification["path"], qualification["sha256"])
    # Both GGUF shards and the complete runtime bundle are checked before private-case access.
    wrapper.verify_runtime_after_pass(root, qualification["path"], smoke, qualification["sha256"])
    cases = runtime.load_development_cases(root, config, plan)
    official = runtime.load_official(root, base)
    manifest = unique_manifest(plan)
    requests = build_requests(official, cases, manifest, config["judge"])
    checkpoints = runtime.contained(root, config["recording"]["private_checkpoints"])
    runtime.write_once(
        checkpoints.parent / "pre_dispatch_receipt.safe.json",
        {
            "contract_sha256": expected_hash,
            "case_manifest_sha256": runtime.digest(manifest),
            "expected_cases": 45,
            "empty_utf8_sha256": EMPTY_SHA256,
            "frozen_before_control_inference": True,
        },
    )
    spec = smoke["runtime"]
    command = [
        str(runtime.contained(root, spec["server"]["path"])),
        "--model",
        str(runtime.contained(root, spec["model"]["path"])),
        *spec["server_args"],
    ]
    wrapper.disable_process_proxies()
    results = []
    started = time.monotonic()
    with wrapper.owned_server(
        command, spec["port"], spec["alias"], smoke["limits"]["startup_seconds"]
    ) as process:
        owned_pid = process.pid
        with wrapper.report_progress(checkpoints, 45):
            for row, case, request in requests:
                if time.monotonic() - started > config["maximum_suite_seconds"]:
                    raise TimeoutError(
                        "empty-control suite time limit; completed receipts retained"
                    )
                identity = {
                    "contract_sha256": expected_hash,
                    "control_kind": "LITERAL_EMPTY",
                    "source_id": row["source_id"],
                    "source_row_sha256": row["source_row_sha256"],
                    "judge_id": config["judge"]["judge_id"],
                    "empty_utf8_sha256": EMPTY_SHA256,
                    "request_sha256": runtime.digest(request),
                }
                item = runtime.evaluate_once(
                    checkpoints,
                    runtime.digest(identity),
                    identity,
                    config["judge"],
                    request,
                    official,
                    case,
                )
                results.append(item)
                if item["error_code"] == "RETURNED_MODEL_MISMATCH":
                    raise RuntimeError("model identity changed; completed control receipt retained")
    result = summarize(expected_hash, manifest, results, config["expected_points"])
    result["elapsed_seconds"] = time.monotonic() - started
    result["owned_server_pid"] = owned_pid
    result["owned_server_stopped"] = process.poll() is not None
    result["result_identity_sha256"] = runtime.digest(result)
    runtime.write_once(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        path = runtime.contained(root, args.config)
        if args.execute:
            result = execute(root, path, args.config_sha256)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["gate"]["pass"] else 1
        config, _, plan = preflight(root, path, args.config_sha256)
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA,
                    "status": "EMPTY_CONTROL_PREFLIGHT_PASS",
                    "expected_cases": len(unique_manifest(plan)),
                    "expected_points": config["expected_points"],
                    "private_inputs_read": False,
                    "network_calls": 0,
                    "server_started": False,
                }
            )
        )
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA,
                    "status": "EMPTY_CONTROL_STOPPED",
                    "error_type": type(exc).__name__,
                    "raw_content_printed": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
