from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path
from types import ModuleType
from typing import cast

from jbspan.evaluator_panel_runtime_qualification import JsonObject
from jbspan.evaluator_panel_v2 import parse_actionability_output_v2


def load_base_runner(root: Path) -> ModuleType:
    path = root / "scripts/run_evaluator_panel_runtime_qualification_e0c.py"
    spec = importlib.util.spec_from_file_location("e0c_v1_base", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load E0C V1 runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_object_list(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{where} must be a list of objects")
    return cast(list[JsonObject], value)


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def extract_last_json_response(stdout: str) -> str:
    normalized = stdout.replace("\r\n", "\n").replace("\r", "\n")
    timing = re.search(r"\n+\[\s*Prompt:\s*[0-9.]+\s*t/s\s*\|", normalized)
    if timing is None:
        raise ValueError("simple-io timing boundary is missing")
    prefix = normalized[: timing.start()].rstrip()
    for position in reversed([match.start() for match in re.finditer(r"\{", prefix)]):
        candidate = prefix[position:].strip()
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return candidate
    raise ValueError("no terminal JSON object was found before the timing boundary")


def transform_command(command: list[str], candidate: JsonObject) -> list[str]:
    transformed = list(command)
    if candidate.get("skip_chat_parsing") is True:
        transformed.insert(transformed.index("--verbose"), "--skip-chat-parsing")
    if candidate.get("jinja") is False:
        transformed[transformed.index("--jinja")] = "--no-jinja"
    if candidate.get("json_schema") is False:
        index = transformed.index("--json-schema")
        del transformed[index : index + 2]
    return transformed


def execute_probe(
    base: ModuleType,
    command: list[str],
    *,
    timeout_seconds: int,
) -> JsonObject:
    start = time.monotonic()
    error_type: str | None = None
    try:
        completed = base.run_command(command, timeout=timeout_seconds)
        return_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        return_code = None
        error_type = type(exc).__name__
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
    log_text = stdout + "\n" + stderr
    if "Failed to initialize samplers" in log_text:
        error_type = "SamplerInitializationError"
    extraction_error: str | None = None
    try:
        response = extract_last_json_response(stdout)
    except ValueError as exc:
        response = ""
        extraction_error = type(exc).__name__
    layer_matches = [
        int(match.group(1))
        for match in re.finditer(r"offloaded\s+(\d+)/\d+\s+layers", log_text, re.I)
    ]
    return {
        "return_code": return_code,
        "error_type": error_type,
        "elapsed_seconds": time.monotonic() - start,
        "stdout": stdout,
        "stderr": stderr,
        "response": response,
        "response_extraction_error": extraction_error,
        "performance": base.parse_perf(log_text),
        "chat_template_active": "chat template" in log_text.casefold(),
        "maximum_logged_gpu_layers": max(layer_matches) if layer_matches else 0,
    }


def validate_probe_contract(root: Path, contract: JsonObject, base: ModuleType) -> None:
    if contract.get("status") != "FROZEN_AFTER_E0C_V1_FAILURE_BEFORE_ANY_REPAIR_PROBE":
        raise ValueError("unexpected E0C repair-probe status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("repair probe must be frozen and non-paper-valid")
    if any(
        value is not False
        for value in as_object(contract["scope_boundary"], where="scope_boundary").values()
    ):
        raise ValueError("repair probe opens a prohibited boundary")
    for dependency_value in as_object(
        contract["dependencies"], where="dependencies"
    ).values():
        dependency = as_object(dependency_value, where="dependency")
        path = root / str(dependency["path"])
        if path.stat().st_size != int(dependency["bytes"]):
            raise ValueError(f"dependency size mismatch: {path}")
        if base.sha256_file(path) != dependency["sha256"]:
            raise ValueError(f"dependency hash mismatch: {path}")
    failure = as_object(contract["e0c_v1_failure"], where="e0c_v1_failure")
    failure_result = load_object(root / str(failure["path"]))
    if failure_result.get("status") != "E0C_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_FAIL":
        raise ValueError("E0C V1 failure status mismatch")
    if failure_result.get("result_identity_sha256") != failure["result_identity"]:
        raise ValueError("E0C V1 failure identity mismatch")
    candidates = as_object_list(contract["ordered_candidates"], where="ordered_candidates")
    if [int(candidate["priority"]) for candidate in candidates] != list(
        range(1, len(candidates) + 1)
    ):
        raise ValueError("repair candidates are not in a complete priority order")


def run(root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    base = load_base_runner(root)
    contract = load_object(config_path)
    validate_probe_contract(root, contract, base)
    v1_contract_path = root / str(
        as_object(contract["dependencies"], where="dependencies")["e0c_v1_contract"][
            "path"
        ]
    )
    v1_contract = base.load_object(v1_contract_path)
    base.validate_contract(root, v1_contract_path, v1_contract)
    runtime = base.validate_runtime(root, v1_contract)
    rendered_cases = base.render_cases(root, v1_contract)
    probe_case_id = str(contract["probe_case_id"])
    matches = [item for item in rendered_cases if str(item[0]["case_id"]) == probe_case_id]
    if len(matches) != 1:
        raise ValueError("repair probe case is not unique")
    case, rendered = matches[0]
    if rendered.axis != "actionability" or rendered.canary_nonce is None:
        raise ValueError("repair probe requires the frozen harmless actionability case")

    model_contract = as_object(contract["model"], where="model")
    model_path = root / str(model_contract["local_path"])
    if model_path.stat().st_size != int(model_contract["bytes"]):
        raise ValueError("repair-probe model size mismatch")
    if base.sha256_file(model_path) != model_contract["sha256"]:
        raise ValueError("repair-probe model hash mismatch")
    generation = as_object(v1_contract["generation"], where="generation")
    base_command = base.build_cli_command(
        Path(str(runtime["cli_path"])), model_path, rendered, generation
    )
    private_root = root / str(
        as_object(contract["recording"], where="recording")["private_directory"]
    )
    candidate_summaries: list[JsonObject] = []
    selected: str | None = None
    for candidate in as_object_list(
        contract["ordered_candidates"], where="ordered_candidates"
    ):
        candidate_id = str(candidate["candidate_id"])
        rows: list[JsonObject] = []
        print(f"E0C_REPAIR_PROBE {candidate_id}", flush=True)
        for repetition in range(int(contract["independent_process_repetitions"])):
            command = transform_command(base_command, candidate)
            record = execute_probe(
                base,
                command,
                timeout_seconds=int(generation["timeout_seconds_per_generation"]),
            )
            identity: JsonObject = {
                "repair_probe_contract_sha256": base.sha256_file(config_path),
                "candidate_id": candidate_id,
                "model_sha256": model_contract["sha256"],
                "case_id": case["case_id"],
                "repetition": repetition,
                "generation": generation,
            }
            identity_sha256 = base.canonical_sha256(identity)
            record["execution_identity"] = identity
            record["execution_identity_sha256"] = identity_sha256
            atomic_write_json(
                private_root / candidate_id / f"{identity_sha256}.json", record
            )
            raw_output = base.normalized_response(str(record["response"]))
            parsed = parse_actionability_output_v2(
                raw_output,
                judge_id=str(model_contract["judge_id"]),
                base_family=str(model_contract["base_family"]),
                canary_nonce=rendered.canary_nonce,
            )
            rows.append(
                {
                    "execution_identity_sha256": identity_sha256,
                    "repetition": repetition,
                    "return_code": record["return_code"],
                    "error_type": record["error_type"],
                    "response_extraction_error": record["response_extraction_error"],
                    "response_sha256": base.sha256_bytes(raw_output.encode("utf-8")),
                    "response_utf8_bytes": len(raw_output.encode("utf-8")),
                    "parse_pass": not parsed.parse_error,
                    "canary_pass": parsed.canary_pass,
                    "chat_template_active": record["chat_template_active"],
                    "maximum_logged_gpu_layers": record["maximum_logged_gpu_layers"],
                    "performance": record["performance"],
                }
            )
        candidate_pass = (
            all(row["return_code"] == 0 for row in rows)
            and all(row["error_type"] is None for row in rows)
            and all(row["response_extraction_error"] is None for row in rows)
            and all(bool(row["parse_pass"]) for row in rows)
            and all(bool(row["canary_pass"]) for row in rows)
            and all(bool(row["chat_template_active"]) for row in rows)
            and all(int(row["maximum_logged_gpu_layers"]) == 0 for row in rows)
            and len({str(row["response_sha256"]) for row in rows}) == 1
        )
        candidate_summaries.append(
            {
                "candidate_id": candidate_id,
                "priority": candidate["priority"],
                "operational_pass": candidate_pass,
                "semantic_scores_used_for_selection": False,
                "invocations": rows,
            }
        )
        if candidate_pass:
            selected = candidate_id
            break

    passed = selected is not None
    result: JsonObject = {
        "schema_version": "jbspan-evaluator-panel-e0c-runtime-repair-probe-result-v1",
        "status": "E0C_REPAIR_PROBE_PASS" if passed else "E0C_REPAIR_PROBE_FAIL",
        "operational_pass": passed,
        "paper_validity": False,
        "scientific_judge_qualification_performed": False,
        "probe_contract_sha256": base.sha256_file(config_path),
        "probe_runner_sha256": base.sha256_file(Path(__file__).resolve()),
        "selected_candidate_id": selected,
        "selection_rule": contract["selection_rule"],
        "semantic_scores_used_for_selection": False,
        "candidate_summaries": candidate_summaries,
        "external_calibration_rows_opened": False,
        "external_heldout_rows_opened": False,
        "preserved_p3_responses_opened": False,
        "next_authorized_operation": (
            "FREEZE_E0C_V1_1_WITH_SELECTED_OPERATIONAL_REPAIR"
            if passed
            else "STOP_AND_REASSESS_THE_PHI_RUNTIME_CANDIDATE_BEFORE_EXTERNAL_DATA"
        ),
    }
    result["result_identity_sha256"] = base.canonical_sha256(result)
    base.assert_safe_result(result)
    atomic_write_json(safe_output, result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Probe frozen E0C runtime repair candidates")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/runtime_qualification_e0c_repair_probe.json"),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (root / args.config).resolve()
    contract = load_object(config_path)
    safe_output = root / str(
        as_object(contract["recording"], where="recording")["safe_result_path"]
    )
    result = run(root, config_path, safe_output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "selected_candidate_id": result["selected_candidate_id"],
                "result_identity_sha256": result["result_identity_sha256"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
