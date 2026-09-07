"""Independently reconstruct the frozen Step 5N harmless target admission.

This verifier deliberately does not import the Step 5N runner.  It rebuilds the
22-call plan, safe projections, per-model gates, and final decision from the
frozen contract plus the private *harmless-only* invocation records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
DEFAULT_CONFIG = Path("configs/natural_language_localization/step5n_h4rm3l_confirmation_v1.json")
CONTRACT_SCHEMA = "jbspan-step5n-h4rm3l-confirmation-v1"
CONTRACT_STATUS = "FROZEN_AFTER_AUTHOR_NARROW_APPROVAL_BEFORE_GEMMA_DOWNLOAD_OR_C1N_OUTPUT"
EXTRACTOR_VERSION = "LLAMA_CPP_SIMPLE_IO_DISPLAY_ECHO_V3_TRAILING_NEWLINE_BOUNDARY_AMENDMENT"
PRIVATE_KEYS = {"prompt", "response", "stdout", "stderr", "payload"}


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return cast(JsonRows, rows)


def resolve(root: Path, value: str | Path, *, where: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{where} escapes repository root")
    return resolved


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def required_objects(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{where} must be a list of objects")
    return cast(list[JsonObject], value)


def forbidden_locations(value: object, location: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if str(key).casefold() in PRIVATE_KEYS:
                found.append(child_location)
            found.extend(forbidden_locations(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_locations(child, f"{location}[{index}]"))
    return found


def normalized_response(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", normalized_response(value)).casefold()
    return "".join(normalized.split())


def capability_pass(response: str, required: Sequence[str]) -> bool:
    haystack = comparison_text(response)
    return all(comparison_text(value) in haystack for value in required)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def validate_contract(root: Path, path: Path) -> JsonObject:
    contract = load_object(path)
    if (
        contract.get("schema_version") != CONTRACT_SCHEMA
        or contract.get("status") != CONTRACT_STATUS
        or contract.get("frozen") is not True
        or contract.get("paper_validity") is not False
    ):
        raise ValueError("unsupported Step 5N contract boundary")
    scope = required_mapping(contract.get("scope_boundary"), where="scope boundary")
    if scope.get("harmless_prompt_only") is not True or any(
        scope.get(key) is not False
        for key in (
            "attack_template_allowed",
            "confirmation_payload_access_allowed",
            "attack_success_observation_allowed",
            "evaluator_call_allowed",
            "topology_outcome_allowed",
            "c1n_scientific_output_allowed",
            "paper_claim_allowed",
        )
    ):
        raise ValueError("contract opens a prohibited Step 5N boundary")
    for group_name in ("dependencies", "required_code"):
        group = required_mapping(contract.get(group_name), where=group_name)
        for name, raw in group.items():
            specification = required_mapping(raw, where=f"{group_name}.{name}")
            target = resolve(root, str(specification["path"]), where=f"{group_name}.{name}")
            if not target.is_file() or file_sha256(target) != specification["sha256"]:
                raise ValueError(f"frozen file mismatch: {group_name}.{name}")
            size = specification.get("size_bytes")
            if size is not None and target.stat().st_size != int(size):
                raise ValueError(f"frozen file size mismatch: {group_name}.{name}")
    return contract


def build_plan(contract: Mapping[str, Any], contract_sha256: str) -> JsonRows:
    prompts = required_objects(contract.get("harmless_prompts"), where="prompts")
    prompt_by_id = {str(item["prompt_id"]): item for item in prompts}
    generation = dict(required_mapping(contract.get("generation"), where="generation"))
    determinism = required_mapping(contract.get("determinism_check"), where="determinism")
    determinism_id = str(determinism["prompt_id"])
    repetitions = int(determinism["independent_process_repetitions"])
    runner_sha = str(contract["required_code"]["runner"]["sha256"])
    rows: JsonRows = []
    for model in required_objects(contract.get("models"), where="models"):
        calls: list[tuple[JsonObject, int]] = [(prompt, 0) for prompt in prompts]
        calls.extend((prompt_by_id[determinism_id], index) for index in range(1, repetitions))
        hashes = [str(item["sha256"]) for item in model["files"]]
        for prompt, replicate_index in calls:
            core = {
                "contract_sha256": contract_sha256,
                "runner_sha256": runner_sha,
                "model_id": model["model_id"],
                "model_runtime_repository": model["runtime_repository"],
                "model_runtime_revision": model["runtime_revision"],
                "model_file_sha256s": hashes,
                "prompt_id": prompt["prompt_id"],
                "prompt_sha256": text_sha256(str(prompt["text"])),
                "seed": generation["seed"],
                "replicate_index": replicate_index,
                "generation_parameters": generation,
            }
            rows.append({"record_id": canonical_sha256(core), "execution_order": len(rows), **core})
    if len(rows) != 22 or len({row["record_id"] for row in rows}) != 22:
        raise ValueError("independently reconstructed plan is not exactly 22 unique calls")
    return rows


def reconstruct_safe_row(
    plan: Mapping[str, Any], prompt: Mapping[str, Any], private: Mapping[str, Any], path: Path
) -> JsonObject:
    expected_identity = {
        "kind": "STEP5N_HARMLESS_TARGET_ADMISSION",
        **{key: value for key, value in plan.items() if key != "execution_order"},
        "private_file_transport": True,
        "response_extractor_version": EXTRACTOR_VERSION,
    }
    if private.get("schema_version") != "local-signal-screen-p3-private-invocation-v1":
        raise ValueError(f"private record schema mismatch: {path}")
    if private.get("execution_identity") != expected_identity:
        raise ValueError(f"private execution identity mismatch: {path}")
    if private.get("execution_identity_sha256") != canonical_sha256(expected_identity):
        raise ValueError(f"private execution identity hash mismatch: {path}")
    if private.get("prompt") != prompt["text"] or private.get("payload") is not None:
        raise ValueError(f"private record is not the planned harmless prompt: {path}")
    response = normalized_response(str(private.get("response", "")))
    prompt_echo = comparison_text(str(prompt["text"])) in comparison_text(response)
    capability = (
        capability_pass(
            response, [str(value) for value in prompt["required_normalized_substrings"]]
        )
        and not prompt_echo
    )
    performance = required_mapping(private.get("performance", {}), where="performance")
    decode_runs = performance.get("decode_token_runs")
    maximum = int(plan["generation_parameters"]["maximum_new_tokens"])
    possible_truncation = isinstance(decode_runs, int) and decode_runs >= maximum
    operational = all(
        (
            private.get("return_code") == 0,
            private.get("error_type") is None,
            private.get("response_extraction_error") is None,
            bool(response),
            private.get("chat_template_active") is True,
            private.get("gpu_offload_logged") is True,
        )
    )
    identity = expected_identity
    return {
        "record_id": plan["record_id"],
        "execution_order": plan["execution_order"],
        "model_id": plan["model_id"],
        "model_runtime_revision": plan["model_runtime_revision"],
        "prompt_id": plan["prompt_id"],
        "prompt_sha256": plan["prompt_sha256"],
        "replicate_index": plan["replicate_index"],
        "seed": plan["seed"],
        "private_record_sha256": file_sha256(path),
        "cache_hit_this_invocation": False,
        "capability_pass": capability,
        "prompt_echo_detected": prompt_echo,
        "execution_identity_sha256": private["execution_identity_sha256"],
        "invocation_id": identity.get("invocation_id"),
        "payload_position": identity.get("payload_position"),
        "payload_sha256": identity.get("payload_sha256"),
        "semantic_category": identity.get("semantic_category"),
        "condition": identity.get("condition"),
        "attack_family": identity.get("attack_family"),
        "return_code": private.get("return_code"),
        "error_type": private.get("error_type"),
        "response_extraction_error": private.get("response_extraction_error"),
        "response_extractor_version": private.get("response_extractor_version"),
        "response_repaired_from_preserved_stdout": private.get(
            "response_repaired_from_preserved_stdout", False
        ),
        "elapsed_seconds": private.get("elapsed_seconds"),
        "response_sha256": text_sha256(response),
        "response_character_length": len(str(private.get("response", ""))),
        "response_utf8_bytes": len(str(private.get("response", "")).encode("utf-8")),
        "stdout_sha256": text_sha256(str(private.get("stdout", ""))),
        "stderr_sha256": text_sha256(str(private.get("stderr", ""))),
        "performance": dict(performance),
        "sampling": private.get("sampling"),
        "chat_template_active": private.get("chat_template_active"),
        "gpu_offload_logged": private.get("gpu_offload_logged"),
        "possible_max_token_truncation": possible_truncation,
        "operational_pass": operational,
        "eligible_for_screening": operational and not possible_truncation,
    }


def summarize_model(
    model: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]
) -> JsonObject:
    primary = [row for row in rows if int(row["replicate_index"]) == 0]
    sentinel = [row for row in rows if row["prompt_id"] == gate["determinism_prompt_id"]]
    rates = [
        float(row["performance"]["decode_tokens_per_second"])
        for row in rows
        if isinstance(row.get("performance", {}).get("decode_tokens_per_second"), (int, float))
    ]
    loads = [
        float(row["performance"]["load_ms"])
        for row in rows
        if isinstance(row.get("performance", {}).get("load_ms"), (int, float))
    ]
    elapsed = [
        float(row["elapsed_seconds"])
        for row in rows
        if isinstance(row.get("elapsed_seconds"), (int, float))
    ]
    vram = [
        float(row["sampling"]["peak_gpu_memory_used_mib"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("peak_gpu_memory_used_mib"), (int, float))
    ]
    deltas = [
        float(row["sampling"]["gpu_memory_delta_mib"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("gpu_memory_delta_mib"), (int, float))
    ]
    temperatures = [
        float(row["sampling"]["peak_gpu_temperature_c"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("peak_gpu_temperature_c"), (int, float))
    ]
    median_rate = statistics.median(rates) if rates else None
    median_load = statistics.median(loads) if loads else None
    maximum_vram = max(vram) if vram else None
    maximum_delta = max(deltas) if deltas else None
    maximum_temperature = max(temperatures) if temperatures else None
    deterministic = (
        len(sentinel) == 2 and len({str(row["response_sha256"]) for row in sentinel}) == 1
    )
    successful = sum(
        row["operational_pass"] is True and row["possible_max_token_truncation"] is False
        for row in rows
    )
    capability_count = sum(row["capability_pass"] is True for row in primary)
    checks = {
        "all_generations_succeeded": successful == int(gate["required_invocations_per_model"]),
        "all_ten_capabilities_passed": capability_count
        >= int(gate["minimum_capability_passes_per_model"]),
        "decode_rate_floor_met": median_rate is not None
        and median_rate >= float(gate["minimum_median_decode_tokens_per_second"]),
        "vram_ceiling_met": maximum_vram is not None
        and maximum_vram <= float(gate["maximum_peak_vram_mib"]),
        "temperature_ceiling_met": maximum_temperature is not None
        and maximum_temperature <= float(gate["maximum_gpu_temperature_c"]),
        "chat_template_active": all(row["chat_template_active"] is True for row in rows),
        "gpu_offload_active": maximum_delta is not None
        and maximum_delta >= float(gate["minimum_gpu_memory_delta_mib"])
        and all(row["gpu_offload_logged"] is True for row in rows),
        "deterministic_replay": deterministic,
        "no_prompt_echo": all(row["prompt_echo_detected"] is False for row in rows),
        "no_max_token_truncation": all(
            row["possible_max_token_truncation"] is False for row in rows
        ),
        "private_file_extractor_v3": all(
            row["response_extractor_version"] == EXTRACTOR_VERSION for row in rows
        ),
    }
    return {
        "model_id": model["model_id"],
        "runtime_repository": model["runtime_repository"],
        "runtime_revision": model["runtime_revision"],
        "runtime_authority": model["runtime_authority"],
        "license": model["license"],
        "quantization": model["quantization"],
        "invocation_count": len(rows),
        "successful_generation_count": successful,
        "capability_pass_count": capability_count,
        "capability_prompt_count": len(primary),
        "deterministic_replay": deterministic,
        "median_load_milliseconds": median_load,
        "median_cold_process_seconds": statistics.median(elapsed) if elapsed else None,
        "median_decode_tokens_per_second": median_rate,
        "projected_512_token_seconds": median_load / 1000 + 512 / median_rate
        if median_load is not None and median_rate is not None and median_rate > 0
        else None,
        "maximum_peak_vram_mib": maximum_vram,
        "maximum_gpu_memory_delta_mib": maximum_delta,
        "maximum_gpu_temperature_c": maximum_temperature,
        "checks": checks,
    }


def verify(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract = validate_contract(root, config_path)
    contract_sha = file_sha256(config_path)
    recording = required_mapping(contract["recording"], where="recording")
    safe_root = resolve(root, str(recording["safe_output_root"]), where="safe root")
    private_root = resolve(root, str(recording["private_root"]), where="private root")
    staging_root = resolve(root, str(recording["staging_root"]), where="staging root")
    plan_path = safe_root / "admission_plan.safe.jsonl"
    progress_path = safe_root / "qualification_progress.safe.jsonl"
    preparation_path = safe_root / "preparation.safe.json"
    result_path = safe_root / "result.safe.json"
    observed_plan = load_jsonl(plan_path)
    expected_plan = build_plan(contract, contract_sha)
    prompts = {str(item["prompt_id"]): item for item in contract["harmless_prompts"]}
    reconstructed: JsonRows = []
    expected_private_paths: set[Path] = set()
    for item in expected_plan:
        path = private_root / str(item["model_id"]) / f"{item['record_id']}.json"
        expected_private_paths.add(path.resolve())
        reconstructed.append(
            reconstruct_safe_row(item, prompts[str(item["prompt_id"])], load_object(path), path)
        )
    observed_progress = load_jsonl(progress_path)
    # Cache-hit is an execution-local resume diagnostic, not scientific evidence.
    comparable_reconstructed = (
        [
            {
                **row,
                "cache_hit_this_invocation": observed_progress[index].get(
                    "cache_hit_this_invocation"
                ),
            }
            for index, row in enumerate(reconstructed)
        ]
        if len(observed_progress) == len(reconstructed)
        else reconstructed
    )
    actual_private_paths = {
        path.resolve() for path in private_root.rglob("*.json") if path.is_file()
    }
    preparation = load_object(preparation_path)
    result = load_object(result_path)
    result_body = dict(result)
    claimed_result_identity = result_body.pop("result_identity_sha256", None)
    preparation_body = dict(preparation)
    claimed_preparation_identity = preparation_body.pop("result_identity_sha256", None)
    gate = dict(required_mapping(contract["gate"], where="gate"))
    gate["determinism_prompt_id"] = contract["determinism_check"]["prompt_id"]
    summaries = [
        summarize_model(
            model, [row for row in reconstructed if row["model_id"] == model["model_id"]], gate
        )
        for model in contract["models"]
    ]
    expected_pass = all(all(summary["checks"].values()) for summary in summaries)
    expected_result_checks = {
        "author_scope_and_pair_authorized": True,
        "official_cross_family_d3_remains_failed": True,
        "preparation_passed": preparation.get("preparation_pass") is True,
        "machine_floor_passed": all(
            required_mapping(
                result.get("machine", {}).get("checks", {}), where="machine checks"
            ).values()
        ),
        "runtime_identity_passed": True,
        "exactly_22_planned_and_completed": len(observed_plan) == len(observed_progress) == 22,
        "both_model_gates_passed": expected_pass,
        "checkpoint_prefix_and_resume_contract_passed": True,
        "no_attack_evaluator_or_topology_output_opened": True,
    }
    safe_values = [observed_plan, observed_progress, preparation, result]
    extra_scientific_files = sum(
        len(
            [
                item
                for item in resolve(root, path, where="scientific root").rglob("*")
                if item.is_file()
            ]
        )
        if resolve(root, path, where="scientific root").exists()
        else 0
        for path in contract["scientific_output_absence_roots"]
    )
    checks = {
        "contract_and_frozen_files_match": True,
        "plan_reconstruction_exact": observed_plan == expected_plan,
        "plan_file_sha256_matches_result": file_sha256(plan_path) == result.get("plan_sha256"),
        "progress_reconstruction_exact": observed_progress == comparable_reconstructed,
        "progress_file_sha256_matches_result": file_sha256(progress_path)
        == result.get("progress_sha256"),
        "exact_private_record_set": actual_private_paths == expected_private_paths,
        "private_records_are_harmless_only": all(
            row.get("payload_sha256") is None and row.get("attack_family") is None
            for row in reconstructed
        ),
        "preparation_identity_valid": claimed_preparation_identity
        == canonical_sha256(preparation_body),
        "preparation_contract_matches": preparation.get("contract_sha256") == contract_sha,
        "result_identity_valid": claimed_result_identity == canonical_sha256(result_body),
        "result_contract_and_runner_match": result.get("contract_sha256") == contract_sha
        and result.get("runner_sha256") == contract["required_code"]["runner"]["sha256"],
        "model_summaries_reconstructed_exact": result.get("models") == summaries,
        "overall_checks_reconstructed_exact": result.get("checks") == expected_result_checks,
        "overall_decision_reconstructed_exact": result.get("operational_pass") is expected_pass
        and result.get("preferred_target_pair_admitted") is expected_pass
        and result.get("status")
        == (
            "STEP5N_PREFERRED_TARGET_ADMISSION_PASS"
            if expected_pass
            else "STEP5N_PREFERRED_TARGET_ADMISSION_FAIL"
        ),
        "safe_outputs_exclude_private_text_fields": not any(
            forbidden_locations(value) for value in safe_values
        ),
        "staging_directory_empty": not staging_root.exists()
        or not any(item.is_file() for item in staging_root.rglob("*")),
        "scientific_output_roots_still_empty": extra_scientific_files == 0,
        "reported_boundary_is_nonpaper_harmless_admission": result.get("paper_validity") is False
        and result.get("harmless_prompts_only") is True
        and result.get("c1n_output_opened") is False
        and result.get("evaluator_inference_performed") is False,
    }
    passed = all(checks.values())
    reconstruction_identity = canonical_sha256(
        {
            "contract_sha256": contract_sha,
            "plan_sha256": file_sha256(plan_path),
            "progress_sha256": file_sha256(progress_path),
            "private_record_sha256s": [row["private_record_sha256"] for row in reconstructed],
            "model_summaries": summaries,
            "operational_pass": expected_pass,
        }
    )
    verification: JsonObject = {
        "schema_version": "jbspan-step5n-target-admission-independent-verification-v1",
        "status": "STEP5N_TARGET_ADMISSION_INDEPENDENT_RECONSTRUCTION_PASS"
        if passed
        else "STEP5N_TARGET_ADMISSION_INDEPENDENT_RECONSTRUCTION_FAIL",
        "contract_sha256": contract_sha,
        "target_result_identity_sha256": claimed_result_identity,
        "reconstruction_identity_sha256": reconstruction_identity,
        "checks": checks,
        "passed_check_count": sum(checks.values()),
        "check_count": len(checks),
        "verification_pass": passed,
        "private_harmless_records_read": len(reconstructed),
        "harmful_payload_read": False,
        "attack_template_read": False,
        "evaluator_invoked": False,
        "c1n_output_opened": False,
        "paper_validity": False,
    }
    if forbidden_locations(verification):
        raise ValueError("independent verification output contains a private text field")
    verification["verification_identity_sha256"] = canonical_sha256(verification)
    atomic_write_json(safe_root / "independent_verification.safe.json", verification)
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify Step 5N admission")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    arguments = parser.parse_args()
    result = verify(arguments.root, arguments.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
