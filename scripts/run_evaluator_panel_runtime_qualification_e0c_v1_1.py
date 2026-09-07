from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import cast

from jbspan.evaluator_panel_runtime_qualification import JsonObject


def load_base_runner(root: Path) -> ModuleType:
    path = root / "scripts/run_evaluator_panel_runtime_qualification_e0c.py"
    spec = importlib.util.spec_from_file_location("e0c_v1_base_for_v1_1", path)
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


def extract_last_terminal_json(stdout: str) -> str:
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


def make_fixed_extractor(base: ModuleType):  # type: ignore[no-untyped-def]
    def extract(stdout: str, prompt: str) -> str:
        try:
            return str(base.extract_simple_io_response_original(stdout, prompt))
        except ValueError:
            return extract_last_terminal_json(stdout)

    return extract


def make_native_template_builder(base: ModuleType):  # type: ignore[no-untyped-def]
    def build(*args: object, **kwargs: object) -> list[str]:
        command = list(base.build_cli_command_original(*args, **kwargs))
        command[command.index("--jinja")] = "--no-jinja"
        return cast(list[str], command)

    return build


def make_checked_executor(base: ModuleType):  # type: ignore[no-untyped-def]
    def execute(*args: object, **kwargs: object) -> JsonObject:
        record = cast(JsonObject, base.execute_cli_original(*args, **kwargs))
        log_text = str(record.get("stdout", "")) + "\n" + str(record.get("stderr", ""))
        if "Failed to initialize samplers" in log_text:
            record["error_type"] = "SamplerInitializationError"
            record["response"] = ""
            record["response_extraction_error"] = "SamplerInitializationError"
        return record

    return execute


def validate_repair_provenance(root: Path, contract: JsonObject, base: ModuleType) -> None:
    if contract.get("status") != "FROZEN_AFTER_E0C_REPAIR_PROBE_BEFORE_V1_1_INFERENCE":
        raise ValueError("unexpected E0C V1.1 status")
    if contract.get("schema_version") != "jbspan-evaluator-panel-runtime-qualification-e0c-v1-1":
        raise ValueError("unexpected E0C V1.1 schema")
    repair = as_object(contract["repair_provenance"], where="repair_provenance")
    for key in ("e0c_v1_failure", "repair_probe_result"):
        dependency = as_object(repair[key], where=f"repair_provenance.{key}")
        path = root / str(dependency["path"])
        if path.stat().st_size != int(dependency["bytes"]):
            raise ValueError(f"repair provenance size mismatch: {path}")
        if base.sha256_file(path) != dependency["sha256"]:
            raise ValueError(f"repair provenance hash mismatch: {path}")
        value = load_object(path)
        if value.get("result_identity_sha256") != dependency["result_identity"]:
            raise ValueError(f"repair provenance identity mismatch: {path}")
    probe_path = root / str(
        as_object(repair["repair_probe_result"], where="repair_probe_result")["path"]
    )
    probe = load_object(probe_path)
    if probe.get("selected_candidate_id") != repair["required_selected_candidate_id"]:
        raise ValueError("E0C V1.1 does not use the frozen repair-probe selection")
    generation = as_object(contract["generation"], where="generation")
    if generation.get("jinja_engine") is not False:
        raise ValueError("E0C V1.1 must use the selected native template path")
    if generation.get("json_schema_constraint") is not True:
        raise ValueError("E0C V1.1 must retain JSON-schema constrained decoding")


def run(
    root: Path,
    config_path: Path,
    artifact_root: Path,
    safe_output: Path,
    *,
    prepare_only: bool,
) -> JsonObject:
    base = load_base_runner(root)
    contract = load_object(config_path)
    validate_repair_provenance(root, contract, base)

    original_validate = base.validate_contract

    def validate_v1_1(
        validation_root: Path,
        validation_config_path: Path,
        validation_contract: JsonObject,
    ) -> None:
        adapted = dict(validation_contract)
        adapted["status"] = "FROZEN_BEFORE_ANY_E0C_MODEL_DOWNLOAD_OR_INFERENCE"
        original_validate(validation_root, validation_config_path, adapted)

    base.extract_simple_io_response_original = base.extract_simple_io_response
    base.build_cli_command_original = base.build_cli_command
    base.execute_cli_original = base.execute_cli
    base.extract_simple_io_response = make_fixed_extractor(base)
    base.build_cli_command = make_native_template_builder(base)
    base.execute_cli = make_checked_executor(base)
    base.validate_contract = validate_v1_1
    base.__file__ = str(Path(__file__).resolve())

    result = cast(
        JsonObject,
        base.run(
            root,
            config_path,
            artifact_root,
            safe_output,
            prepare_only=prepare_only,
        ),
    )
    if prepare_only:
        result["status"] = "E0C_V1_1_EXACT_MODEL_ARTIFACT_PREPARATION_PASS"
        return result

    result["schema_version"] = (
        "jbspan-evaluator-panel-runtime-qualification-e0c-result-v1-1"
    )
    result["status"] = (
        "E0C_V1_1_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_PASS"
        if result["operational_pass"] is True
        else "E0C_V1_1_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_FAIL"
    )
    result["repair_audit"] = {
        "e0c_v1_failure_result_identity": as_object(
            contract["repair_provenance"], where="repair_provenance"
        )["e0c_v1_failure"]["result_identity"],
        "repair_probe_result_identity": as_object(
            contract["repair_provenance"], where="repair_provenance"
        )["repair_probe_result"]["result_identity"],
        "selected_candidate_id": as_object(
            contract["repair_provenance"], where="repair_provenance"
        )["required_selected_candidate_id"],
        "terminal_json_extractor_used": True,
        "native_template_without_jinja_used": True,
        "json_schema_constraint_retained": True,
        "semantic_scores_used_to_select_repair": False,
    }
    result.pop("result_identity_sha256", None)
    result["result_identity_sha256"] = base.canonical_sha256(result)
    base.assert_safe_result(result)
    base.atomic_write_json(safe_output, result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run repaired E0C V1.1 qualification")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/runtime_qualification_e0c_v1_1.json"),
    )
    value.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/evaluator_panel_v2/runtime_qualification_e0c"),
    )
    value.add_argument("--safe-output", type=Path)
    value.add_argument("--prepare-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (root / args.config).resolve()
    artifact_root = (root / args.artifact_root).resolve()
    contract = load_object(config_path)
    safe_output = (
        args.safe_output.resolve()
        if args.safe_output
        else root
        / str(as_object(contract["recording"], where="recording")["safe_result_path"])
    )
    result = run(
        root,
        config_path,
        artifact_root,
        safe_output,
        prepare_only=args.prepare_only,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result.get("operational_pass"),
                "result_identity_sha256": result.get("result_identity_sha256"),
                "next_authorized_operation": result.get("next_authorized_operation"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if args.prepare_only:
        return 0
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
