from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSON object at {path}:{number}")
        rows.append(cast(JsonObject, value))
    return rows


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def require_blob(root: Path, path: str, expected: str) -> Path:
    target = root / path
    observed = git_blob_sha(target)
    if observed != expected:
        raise ValueError(f"Git blob mismatch for {path}: {observed}")
    return target


def require_status(value: JsonObject, expected: str, label: str) -> None:
    if value.get("status") != expected:
        raise ValueError(f"{label} status mismatch: {value.get('status')!r}")


def validate_predecessors(root: Path, contract: JsonObject) -> JsonObject:
    predecessors = cast(JsonObject, contract["predecessors"])

    manifest_spec = cast(JsonObject, predecessors["signal_screen_input_manifest"])
    manifest_path = require_blob(
        root, str(manifest_spec["path"]), str(manifest_spec["git_blob_sha"])
    )
    manifest = load_object(manifest_path)
    require_status(manifest, str(manifest_spec["required_status"]), "signal-screen manifest")
    if manifest.get("next_authorized_operation") != manifest_spec["required_next_operation"]:
        raise ValueError("signal-screen manifest authorization mismatch")
    cardinality = cast(JsonObject, manifest["manifest_cardinality"])
    if cardinality.get("planned_baseline_generation_count") != manifest_spec[
        "required_total_target_generations"
    ]:
        raise ValueError("target-generation cardinality mismatch")

    execution_spec = cast(JsonObject, predecessors["execution_freeze"])
    execution_path = require_blob(
        root, str(execution_spec["path"]), str(execution_spec["git_blob_sha"])
    )
    execution = load_object(execution_path)
    require_status(execution, str(execution_spec["required_status"]), "execution freeze")
    payloads = cast(list[JsonObject], execution["payload_manifest"])
    if len(payloads) != int(execution_spec["required_payload_count"]):
        raise ValueError("payload count mismatch")
    if execution.get("payload_manifest_sha256") != execution_spec[
        "required_payload_manifest_sha256"
    ]:
        raise ValueError("payload manifest identity mismatch")

    preflight_spec = cast(JsonObject, predecessors["gcg_qwen_preflight"])
    preflight_path = require_blob(
        root, str(preflight_spec["path"]), str(preflight_spec["git_blob_sha"])
    )
    preflight = load_object(preflight_path)
    require_status(preflight, str(preflight_spec["required_status"]), "GCG-Qwen preflight")
    if preflight.get("operational_pass") is not preflight_spec["required_operational_pass"]:
        raise ValueError("GCG-Qwen operational pass mismatch")
    audit = cast(JsonObject, preflight["audit"])
    if audit.get("compatibility_pass") is not preflight_spec["required_compatibility_pass"]:
        raise ValueError("GCG-Qwen compatibility mismatch")
    if audit.get("control_token_count") != preflight_spec["required_control_token_count"]:
        raise ValueError("GCG control-token count mismatch")
    if len(cast(list[object], audit["block_ranges"])) != preflight_spec["required_block_count"]:
        raise ValueError("GCG block count mismatch")
    candidates = cast(list[JsonObject], audit["candidate_results"])
    if not candidates or any(
        item.get("subset_count") != preflight_spec["required_subset_count"] for item in candidates
    ):
        raise ValueError("GCG subset compatibility mismatch")

    h4rm3l_spec = cast(JsonObject, predecessors["h4rm3l_real_templates"])
    h4rm3l_path = require_blob(
        root, str(h4rm3l_spec["path"]), str(h4rm3l_spec["git_blob_sha"])
    )
    h4rm3l = load_object(h4rm3l_path)
    require_status(h4rm3l, str(h4rm3l_spec["required_status"]), "h4rm3l templates")
    if h4rm3l.get("operational_pass") is not h4rm3l_spec["required_operational_pass"]:
        raise ValueError("h4rm3l operational pass mismatch")
    if h4rm3l.get("program_count") != h4rm3l_spec["required_program_count"]:
        raise ValueError("h4rm3l program count mismatch")

    gcg_spec = cast(JsonObject, predecessors["gcg_static_audit"])
    gcg_path = require_blob(root, str(gcg_spec["path"]), str(gcg_spec["git_blob_sha"]))
    gcg = load_object(gcg_path)
    require_status(gcg, str(gcg_spec["required_status"]), "GCG static audit")
    if gcg.get("operational_pass") is not gcg_spec["required_operational_pass"]:
        raise ValueError("GCG static-audit operational pass mismatch")

    return {
        "signal_screen_input_manifest": manifest["status"],
        "execution_freeze": execution["status"],
        "gcg_qwen_preflight": preflight["status"],
        "h4rm3l_real_templates": h4rm3l["status"],
        "gcg_static_audit": gcg["status"],
        "payloads": payloads,
    }


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def validate_harmbench_source(
    source_root: Path, source: JsonObject, payloads: list[JsonObject]
) -> list[JsonObject]:
    if git_head(source_root) != source["revision"]:
        raise ValueError("HarmBench revision mismatch")
    behavior_path = source_root / str(source["behavior_path"])
    target_path = source_root / str(source["optimizer_target_path"])
    if git_blob_sha(behavior_path) != source["behavior_git_blob_sha"]:
        raise ValueError("HarmBench behavior source blob mismatch")
    if git_blob_sha(target_path) != source["optimizer_target_git_blob_sha"]:
        raise ValueError("HarmBench optimizer-target source blob mismatch")

    with behavior_path.open("r", encoding="utf-8", newline="") as handle:
        behavior_rows = list(csv.DictReader(handle))
    targets = json.loads(target_path.read_text(encoding="utf-8"))
    if not isinstance(targets, dict):
        raise TypeError("optimizer targets must be a JSON object")

    safe_rows: list[JsonObject] = []
    for frozen in sorted(payloads, key=lambda row: int(row["position"])):
        matching: list[dict[str, str]] = []
        for row in behavior_rows:
            behavior = row.get("Behavior", "")
            behavior_id = row.get("BehaviorID", "")
            if sha256_bytes(behavior.encode()) != frozen["payload_sha256"]:
                continue
            if sha256_bytes(behavior_id.encode()) != frozen["behavior_id_sha256"]:
                continue
            matching.append(row)
        if len(matching) != 1:
            raise ValueError(f"expected one source row for payload position {frozen['position']}")
        behavior_id = matching[0]["BehaviorID"]
        target = targets.get(behavior_id)
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"missing optimizer target for payload position {frozen['position']}")
        safe_rows.append(
            {
                "position": frozen["position"],
                "semantic_category": frozen["semantic_category"],
                "behavior_id_sha256": frozen["behavior_id_sha256"],
                "payload_sha256": frozen["payload_sha256"],
                "optimizer_target_sha256": sha256_bytes(target.encode()),
                "optimizer_target_utf8_bytes": len(target.encode()),
                "raw_payload_or_target_recorded": False,
            }
        )
    if len(safe_rows) != int(source["expected_payload_count"]):
        raise ValueError("optimizer-target mapping count mismatch")
    return safe_rows


def validate_attack_sources(
    harmbench_root: Path,
    h4rm3l_root: Path,
    llm_attacks_root: Path,
    contract: JsonObject,
) -> JsonObject:
    runtimes = cast(JsonObject, contract["attack_runtimes"])
    h4rm3l = cast(JsonObject, runtimes["h4rm3l"])
    if git_head(h4rm3l_root) != h4rm3l["revision"]:
        raise ValueError("h4rm3l source revision mismatch")
    decorators = h4rm3l_root / str(h4rm3l["decorators_path"])
    if git_blob_sha(decorators) != h4rm3l["decorators_git_blob_sha"]:
        raise ValueError("h4rm3l decorators blob mismatch")

    gcg = cast(JsonObject, runtimes["GCG"])
    if git_head(llm_attacks_root) != gcg["algorithm_revision"]:
        raise ValueError("llm-attacks revision mismatch")
    tree = subprocess.run(
        ["git", "-C", str(llm_attacks_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tree != gcg["algorithm_tree_sha"]:
        raise ValueError("llm-attacks tree mismatch")
    if git_blob_sha(harmbench_root / str(gcg["harmbench_executable_path"])) != gcg[
        "harmbench_executable_git_blob_sha"
    ]:
        raise ValueError("HarmBench GCG executable blob mismatch")
    if git_blob_sha(harmbench_root / str(gcg["harmbench_config_path"])) != gcg[
        "harmbench_config_git_blob_sha"
    ]:
        raise ValueError("HarmBench GCG config blob mismatch")
    return {
        "h4rm3l_revision": h4rm3l["revision"],
        "h4rm3l_decorators_path": h4rm3l["decorators_path"],
        "h4rm3l_program_count": h4rm3l["program_count"],
        "gcg_algorithm_revision": gcg["algorithm_revision"],
        "gcg_gradient_required": gcg["gradient_required"],
        "gcg_num_steps": gcg["num_steps"],
        "gcg_search_width": gcg["search_width"],
        "gcg_topk": gcg["topk"],
    }


def validate_evaluators(root: Path, contract: JsonObject) -> JsonObject:
    evaluators = cast(JsonObject, contract["evaluators"])
    summary: JsonObject = {}
    for name in ("WildGuard", "HarmBench"):
        spec = cast(JsonObject, evaluators[name])
        contract_path = require_blob(
            root, str(spec["contract_path"]), str(spec["contract_git_blob_sha"])
        )
        result_path = require_blob(root, str(spec["result_path"]), str(spec["result_git_blob_sha"]))
        result = load_object(result_path)
        expected_status = spec.get("required_result_status", spec.get("observed_result_status"))
        require_status(result, str(expected_status), name)
        if "required_operational_pass" in spec:
            if result.get("operational_pass") is not spec["required_operational_pass"]:
                raise ValueError(f"{name} operational-pass mismatch")
        summary[name] = {
            "role": spec["role"],
            "contract_sha256": sha256_file(contract_path),
            "result_status": result["status"],
            "operational_pass": result.get("operational_pass"),
            "voting_enabled": bool(spec.get("voting_enabled", False)),
            "single_primary_judge": spec["single_primary_judge"],
        }
    summary["human_audit"] = evaluators["human_audit"]
    return summary


def resolve_differentiable_model_metadata(contract: JsonObject) -> JsonObject:
    from huggingface_hub import HfApi

    target = cast(JsonObject, contract["target_model"])
    api = HfApi()
    info = api.model_info(
        str(target["repository"]),
        revision=str(target["revision"]),
        files_metadata=True,
    )
    if str(info.sha) != target["revision"]:
        raise ValueError("Qwen differentiable model revision did not resolve exactly")
    weights: list[JsonObject] = []
    for sibling in info.siblings or ():
        name = str(sibling.rfilename)
        if not name.endswith(".safetensors"):
            continue
        lfs = getattr(sibling, "lfs", None)
        if isinstance(lfs, dict):
            digest = lfs.get("sha256")
            size = lfs.get("size")
        else:
            digest = getattr(lfs, "sha256", None)
            size = getattr(lfs, "size", None)
        if size is None:
            size = getattr(sibling, "size", None)
        if not isinstance(digest, str) or not isinstance(size, int):
            raise ValueError(f"missing LFS metadata for {name}")
        weights.append({"filename": name, "sha256": digest, "size_bytes": size})
    if not weights:
        raise ValueError("no differentiable safetensors weights resolved")
    return {
        "repository": target["repository"],
        "revision": str(info.sha),
        "tokenizer_revision": target["tokenizer_revision"],
        "weight_files": sorted(weights, key=lambda row: str(row["filename"])),
        "total_weight_bytes": sum(int(row["size_bytes"]) for row in weights),
        "weights_downloaded": False,
    }


def evaluate_readiness(contract: JsonObject) -> JsonObject:
    target = cast(JsonObject, contract["target_model"])
    runtime = cast(JsonObject, target["differentiable_optimizer_runtime"])
    checks = {
        "gradient_enabled": runtime.get("gradient_enabled") is True,
        "unquantized_optimizer_weights": runtime.get("quantization") == "none",
        "cuda_device_required": runtime.get("device_type") == "cuda",
        "runner_contract_frozen": runtime.get("runner_contract_frozen") is True,
        "runner_labels_frozen": bool(runtime.get("runner_labels")),
        "minimum_free_device_memory_frozen": isinstance(
            runtime.get("minimum_free_device_memory_bytes"), int
        ),
        "wall_clock_budget_frozen": isinstance(runtime.get("maximum_wall_clock_minutes"), int),
        "private_cache_contract_frozen": runtime.get("private_cache_contract_frozen") is True,
    }
    return {"checks": checks, "execution_ready": all(checks.values())}


def assert_safe_result(value: JsonObject) -> None:
    serialized = json.dumps(value, sort_keys=True)
    forbidden = (
        '"Behavior"',
        '"BehaviorID"',
        '"payload_text"',
        '"raw_payload"',
        '"optimizer_target_text"',
        '"raw_prompt"',
        '"raw_response"',
        '"optimized_control"',
        '"evaluator_output"',
    )
    for token in forbidden:
        if token in serialized:
            raise ValueError(f"unsafe field entered safe result: {token}")


def run(
    root: Path,
    harmbench_root: Path,
    h4rm3l_root: Path,
    llm_attacks_root: Path,
    config_path: Path,
    safe_output: Path,
    target_manifest_output: Path,
    model_metadata_path: Path | None,
) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_PRIVATE_SIGNAL_SCREEN_RUNTIME_MATERIALIZATION":
        raise ValueError("unexpected runtime-bundle contract status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("runtime-bundle freeze boundary mismatch")
    sealed = cast(JsonObject, contract["sealed_boundaries"])
    if any(value is not False for value in sealed.values()):
        raise ValueError("an outcome boundary opened before runtime-bundle freeze")

    predecessor = validate_predecessors(root, contract)
    payloads = cast(list[JsonObject], predecessor.pop("payloads"))
    source = cast(JsonObject, contract["payload_and_optimizer_target_source"])
    target_manifest = validate_harmbench_source(harmbench_root, source, payloads)
    attacks = validate_attack_sources(harmbench_root, h4rm3l_root, llm_attacks_root, contract)
    evaluators = validate_evaluators(root, contract)
    model = (
        load_object(model_metadata_path)
        if model_metadata_path is not None
        else resolve_differentiable_model_metadata(contract)
    )
    target = cast(JsonObject, contract["target_model"])
    if model.get("revision") != target["revision"]:
        raise ValueError("differentiable model metadata revision mismatch")
    if model.get("weights_downloaded") is not False:
        raise ValueError("runtime-bundle freeze unexpectedly downloaded weights")

    readiness = evaluate_readiness(contract)
    privacy = cast(JsonObject, contract["privacy"])
    freeze_checks = {
        "predecessors_match": True,
        "optimizer_target_source_matches": True,
        "optimizer_target_mapping_complete": (
            len(target_manifest) == source["expected_payload_count"]
        ),
        "optimizer_targets_are_hash_only": all(
            set(row).isdisjoint({"target", "target_text", "optimizer_target_text"})
            for row in target_manifest
        ),
        "attack_sources_match": True,
        "differentiable_model_revision_resolved": True,
        "differentiable_weight_metadata_resolved": bool(model.get("weight_files")),
        "generation_runtime_frozen": True,
        "evaluator_revisions_frozen": True,
        "wildguard_is_not_primary_judge": evaluators["WildGuard"]["single_primary_judge"]
        is False,
        "harmbench_is_nonvoting_after_operational_fail": evaluators["HarmBench"][
            "voting_enabled"
        ]
        is False,
        "human_audit_remains_primary": cast(JsonObject, evaluators["human_audit"])[
            "primary_reference"
        ]
        is True,
        "safe_output_boundary_frozen": privacy[
            "safe_records_contain_hashes_lengths_parse_statuses_and_aggregates_only"
        ]
        is True,
        "no_model_weight_download": True,
        "no_attack_optimization": True,
        "no_target_inference": True,
        "sealed_boundaries_preserved": True,
    }
    freeze_pass = all(freeze_checks.values())
    execution_ready = bool(readiness["execution_ready"])
    decision = cast(JsonObject, contract["decision_gate"])
    if freeze_pass and execution_ready:
        status = "H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_FREEZE_PASS_READY"
        next_operation = decision["on_bundle_freeze_pass_and_execution_ready"]
    elif freeze_pass:
        status = "H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_FREEZE_PASS_EXECUTION_BLOCKED"
        next_operation = decision["on_bundle_freeze_pass_but_gcg_runtime_missing"]
    else:
        status = "H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_FREEZE_FAIL"
        next_operation = decision["on_bundle_freeze_fail"]

    result: JsonObject = {
        "schema_version": "h4rm3l-gcg-signal-screen-runtime-bundle-result-v1",
        "status": status,
        "operational_pass": freeze_pass,
        "execution_ready": execution_ready,
        "scientific_pass": False,
        "paper_validity": False,
        "evidence_class": "PROTOCOL",
        "contract_sha256": sha256_file(config_path),
        "contract_git_blob_sha": git_blob_sha(config_path),
        "source_commit": git_head(root),
        "workflow_run": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "workflow_sha": os.environ.get("GITHUB_SHA"),
        },
        "predecessors": predecessor,
        "payload_and_optimizer_target_source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "behavior_path": source["behavior_path"],
            "behavior_git_blob_sha": source["behavior_git_blob_sha"],
            "optimizer_target_path": source["optimizer_target_path"],
            "optimizer_target_git_blob_sha": source["optimizer_target_git_blob_sha"],
            "raw_payload_or_target_recorded": False,
        },
        "optimizer_target_manifest": target_manifest,
        "optimizer_target_manifest_sha256": canonical_sha256(target_manifest),
        "attack_runtimes": attacks,
        "differentiable_model": model,
        "generation_runtime": target["generation_runtime"],
        "evaluators": evaluators,
        "readiness": readiness,
        "freeze_checks": freeze_checks,
        "blocking_reasons": []
        if execution_ready
        else [
            key for key, passed in cast(JsonObject, readiness["checks"]).items() if not passed
        ],
        "next_authorized_operation": next_operation,
        "model_weight_downloaded": False,
        "attack_optimization_performed": False,
        "model_inference_performed": False,
        "attack_success_observed": False,
        "automated_label_observed": False,
        "human_label_observed": False,
        "new_harmful_attack_outputs_generated": False,
        "raw_payload_prompt_target_control_response_or_evaluator_output_recorded": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
    }
    assert_safe_result(result)
    write_json(safe_output, result)
    write_jsonl(target_manifest_output, target_manifest)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Freeze h4rm3l/GCG signal-screen runtime identities"
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument("--harmbench-root", type=Path, required=True)
    value.add_argument("--h4rm3l-root", type=Path, required=True)
    value.add_argument("--llm-attacks-root", type=Path, required=True)
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--target-manifest-output", type=Path, required=True)
    value.add_argument("--model-metadata", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    result = run(
        root=args.root.resolve(),
        harmbench_root=args.harmbench_root.resolve(),
        h4rm3l_root=args.h4rm3l_root.resolve(),
        llm_attacks_root=args.llm_attacks_root.resolve(),
        config_path=args.config.resolve(),
        safe_output=args.safe_output.resolve(),
        target_manifest_output=args.target_manifest_output.resolve(),
        model_metadata_path=args.model_metadata.resolve() if args.model_metadata else None,
    )
    print(result["status"])
    print(result["next_authorized_operation"])
    return 0 if result["operational_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
