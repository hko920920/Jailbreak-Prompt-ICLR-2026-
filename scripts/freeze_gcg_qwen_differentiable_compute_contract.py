#!/usr/bin/env python3
"""Freeze the GCG-Qwen differentiable compute contract without GPU execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class ContractError(RuntimeError):
    """An expected contract violation."""


def _git_blob_sha(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise ContractError(f"MISSING_FILE:{relative}")
    try:
        completed = subprocess.run(
            ["git", "hash-object", str(path)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"GIT_HASH_FAILED:{relative}") from exc
    return completed.stdout.strip()


def _canonical_sha256(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _expect(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def freeze(root: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _expect(
        config["schema_version"] == "gcg-qwen-differentiable-compute-contract-v1",
        "SCHEMA_VERSION_MISMATCH",
    )
    _expect(config["frozen"] is True, "CONTRACT_NOT_FROZEN")
    _expect(config["paper_validity"] is False, "PAPER_VALIDITY_MUST_BE_FALSE")

    predecessor_contract = config["predecessor"]
    predecessor_path = root / predecessor_contract["path"]
    _expect(predecessor_path.is_file(), "PREDECESSOR_MISSING")
    _expect(
        _git_blob_sha(root, predecessor_contract["path"]) == predecessor_contract["git_blob_sha"],
        "PREDECESSOR_BLOB_MISMATCH",
    )
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    _expect(
        predecessor["status"] == predecessor_contract["required_status"],
        "PREDECESSOR_STATUS_MISMATCH",
    )
    _expect(
        predecessor["operational_pass"] is predecessor_contract["required_operational_pass"],
        "PREDECESSOR_OPERATIONAL_PASS_MISMATCH",
    )
    _expect(
        predecessor["execution_ready"] is predecessor_contract["required_execution_ready"],
        "PREDECESSOR_EXECUTION_READY_MISMATCH",
    )
    _expect(
        predecessor["next_authorized_operation"] == predecessor_contract["required_next_operation"],
        "PREDECESSOR_NEXT_OPERATION_MISMATCH",
    )
    model = predecessor["differentiable_model"]
    _expect(
        model["repository"] == predecessor_contract["required_model_repository"],
        "MODEL_REPOSITORY_MISMATCH",
    )
    _expect(
        model["revision"] == predecessor_contract["required_model_revision"],
        "MODEL_REVISION_MISMATCH",
    )
    _expect(
        model["total_weight_bytes"] == predecessor_contract["required_weight_bytes"],
        "MODEL_WEIGHT_BYTES_MISMATCH",
    )
    _expect(model["weights_downloaded"] is False, "PREDECESSOR_DOWNLOADED_WEIGHTS")
    _expect(
        predecessor["model_inference_performed"] is False,
        "PREDECESSOR_PERFORMED_INFERENCE",
    )
    _expect(
        predecessor["attack_optimization_performed"] is False,
        "PREDECESSOR_PERFORMED_OPTIMIZATION",
    )
    _expect(
        len(predecessor["optimizer_target_manifest"])
        == predecessor_contract["required_optimizer_jobs"],
        "OPTIMIZER_JOB_COUNT_MISMATCH",
    )

    workflow = config["attestation_workflow"]
    _expect(
        _git_blob_sha(root, workflow["path"]) == workflow["git_blob_sha"],
        "ATTESTATION_WORKFLOW_BLOB_MISMATCH",
    )
    _expect(workflow["dispatch_only"] is True, "ATTESTATION_NOT_DISPATCH_ONLY")
    _expect(
        workflow["must_not_download_model_weights"] is True,
        "ATTESTATION_MAY_DOWNLOAD_WEIGHTS",
    )
    _expect(
        workflow["must_not_execute_attack_optimization"] is True,
        "ATTESTATION_MAY_EXECUTE_OPTIMIZATION",
    )

    runner = config["runner_contract"]
    hardware = runner["hardware"]
    _expect(
        runner["required_labels"]
        == [
            "self-hosted",
            "Linux",
            "X64",
            "gpu",
            "a100-80gb",
            "private-research",
        ],
        "RUNNER_LABELS_MISMATCH",
    )
    _expect(hardware["minimum_gpu_count"] == 2, "GPU_COUNT_NOT_TWO")
    _expect(
        hardware["allowed_gpu_names"] == ["NVIDIA A100 80GB PCIe"],
        "GPU_IDENTITY_MISMATCH",
    )
    _expect(
        hardware["minimum_total_memory_mib_per_gpu"] == 81920,
        "GPU_TOTAL_MEMORY_MISMATCH",
    )
    _expect(
        hardware["minimum_free_memory_mib_per_gpu"] == 65536,
        "GPU_FREE_MEMORY_MISMATCH",
    )
    _expect(
        hardware["minimum_driver_version"] == "525.60.13",
        "MINIMUM_DRIVER_MISMATCH",
    )
    _expect(
        hardware["maximum_driver_version_exclusive"] == "580.0.0",
        "MAXIMUM_DRIVER_MISMATCH",
    )
    _expect(hardware["bf16_required"] is True, "BF16_NOT_REQUIRED")
    _expect(hardware["mig_must_be_disabled"] is True, "MIG_NOT_DISABLED")

    software = config["software_contract"]
    torch = software["pytorch"]
    _expect(software["python_version"] == "3.11", "PYTHON_VERSION_MISMATCH")
    _expect(torch["version"] == "2.6.0", "TORCH_VERSION_MISMATCH")
    _expect(torch["cuda_build"] == "12.4", "CUDA_BUILD_MISMATCH")
    _expect(torch["dtype"] == "bfloat16", "DTYPE_MISMATCH")
    _expect(torch["quantization"] == "none", "QUANTIZATION_NOT_NONE")
    _expect(torch["gradient_enabled"] is True, "GRADIENT_NOT_ENABLED")
    _expect(
        software["packages"]["transformers"] == "4.48.3",
        "TRANSFORMERS_VERSION_MISMATCH",
    )
    _expect(
        software["packages"]["jinja2"] == "3.1.6",
        "JINJA2_VERSION_MISMATCH",
    )

    optimizer = config["optimizer_compute_contract"]
    _expect(optimizer["optimizer_job_count"] == 4, "OPTIMIZER_JOB_COUNT_NOT_FOUR")
    _expect(optimizer["num_steps_per_job"] == 500, "GCG_STEP_COUNT_MISMATCH")
    _expect(optimizer["search_width"] == 512, "GCG_SEARCH_WIDTH_MISMATCH")
    _expect(optimizer["topk"] == 256, "GCG_TOPK_MISMATCH")
    _expect(
        optimizer["starting_search_batch_size"] == 64,
        "GCG_STARTING_BATCH_MISMATCH",
    )
    _expect(optimizer["maximum_concurrent_jobs"] == 2, "CONCURRENCY_MISMATCH")
    _expect(
        optimizer["gpu_assignment"]
        == {
            "gpu_0_payload_positions": [0, 2],
            "gpu_1_payload_positions": [1, 3],
        },
        "GPU_ASSIGNMENT_MISMATCH",
    )
    _expect(
        optimizer["search_width_must_not_change_after_oom"] is True,
        "OOM_MAY_CHANGE_SEARCH_WIDTH",
    )
    _expect(
        optimizer["only_candidate_evaluation_microbatch_may_halve_after_oom"] is True,
        "OOM_POLICY_MISMATCH",
    )

    gate = config["attestation_gate"]
    _expect(gate["runner_attestation_required"] is True, "ATTESTATION_NOT_REQUIRED")
    _expect(
        gate["gradient_smoke_uses_synthetic_nonharmful_fixture"] is True,
        "GRADIENT_SMOKE_NOT_SYNTHETIC",
    )
    _expect(
        gate["full_model_download_before_attestation"] is False,
        "WEIGHT_DOWNLOAD_ALLOWED_BEFORE_ATTESTATION",
    )
    _expect(
        gate["full_attack_optimization_before_gradient_smoke"] is False,
        "OPTIMIZATION_ALLOWED_BEFORE_SMOKE",
    )

    safe_contract = config["safe_output_contract"]
    for field in (
        "raw_payload",
        "raw_optimizer_target",
        "raw_prompt",
        "raw_control",
        "raw_response",
        "raw_evaluator_output",
        "raw_hostname",
        "raw_private_path",
    ):
        _expect(safe_contract[field] is False, f"SAFE_OUTPUT_FIELD_ENABLED:{field}")

    sealed = config["sealed_boundaries"]
    _expect(not any(sealed.values()), "SEALED_BOUNDARY_OPENED")

    contract_sha = _canonical_sha256(config)
    predecessor_sha = _canonical_sha256(predecessor)
    return {
        "schema_version": "gcg-qwen-differentiable-compute-contract-result-v1",
        "status": (
            "GCG_QWEN_DIFFERENTIABLE_COMPUTE_CONTRACT_FREEZE_PASS_AWAITING_RUNNER_ATTESTATION"
        ),
        "operational_pass": True,
        "execution_ready": False,
        "runner_attestation_observed": False,
        "scientific_pass": False,
        "paper_validity": False,
        "evidence_class": "PROTOCOL",
        "source_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "contract_git_blob_sha": _git_blob_sha(
            root,
            str(config_path.relative_to(root)),
        ),
        "contract_sha256": contract_sha,
        "predecessor_git_blob_sha": predecessor_contract["git_blob_sha"],
        "predecessor_sha256": predecessor_sha,
        "attestation_workflow_git_blob_sha": workflow["git_blob_sha"],
        "runner_contract": {
            "required_labels": runner["required_labels"],
            "required_os": runner["required_os"],
            "allowed_architectures": runner["allowed_architectures"],
            "allowed_gpu_names": hardware["allowed_gpu_names"],
            "minimum_gpu_count": hardware["minimum_gpu_count"],
            "minimum_total_memory_mib_per_gpu": hardware["minimum_total_memory_mib_per_gpu"],
            "minimum_free_memory_mib_per_gpu": hardware["minimum_free_memory_mib_per_gpu"],
            "minimum_driver_version": hardware["minimum_driver_version"],
            "maximum_driver_version_exclusive": hardware["maximum_driver_version_exclusive"],
        },
        "software_contract": {
            "python_version": software["python_version"],
            "torch_version": torch["version"],
            "torch_cuda_build": torch["cuda_build"],
            "transformers_version": software["packages"]["transformers"],
            "dtype": torch["dtype"],
            "gradient_enabled": torch["gradient_enabled"],
            "quantization": torch["quantization"],
            "package_lock_sha256": _canonical_sha256(software["packages"]),
        },
        "optimizer_compute_contract": {
            "optimizer_job_count": optimizer["optimizer_job_count"],
            "num_steps_per_job": optimizer["num_steps_per_job"],
            "search_width": optimizer["search_width"],
            "topk": optimizer["topk"],
            "starting_search_batch_size": optimizer["starting_search_batch_size"],
            "maximum_concurrent_jobs": optimizer["maximum_concurrent_jobs"],
            "maximum_wall_clock_minutes_per_job": optimizer["maximum_wall_clock_minutes_per_job"],
            "maximum_total_elapsed_minutes": optimizer["maximum_total_elapsed_minutes"],
        },
        "private_storage_contract": {
            "minimum_free_disk_bytes": runner["private_storage"]["minimum_free_disk_bytes"],
            "required_directory_mode": runner["private_storage"]["required_directory_mode"],
            "required_file_mode": runner["private_storage"]["required_file_mode"],
            "raw_paths_recorded": False,
        },
        "freeze_checks": {
            "predecessor_identity_match": True,
            "predecessor_status_match": True,
            "attestation_workflow_identity_match": True,
            "two_a100_80gb_contract_frozen": True,
            "cuda_12_4_torch_2_6_contract_frozen": True,
            "four_job_two_gpu_sharding_frozen": True,
            "oom_microbatch_only_policy_frozen": True,
            "private_storage_contract_frozen": True,
            "safe_output_contract_frozen": True,
            "no_model_weight_download": True,
            "no_target_inference": True,
            "no_attack_optimization": True,
            "sealed_boundaries_preserved": True,
        },
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "attack_optimization_performed": False,
        "attack_success_observed": False,
        "raw_payload_prompt_target_control_response_or_evaluator_output_recorded": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["next_on_static_freeze_pass"],
        "workflow_run": {
            "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"),
            "workflow_sha": os.environ.get("GITHUB_SHA", "LOCAL"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = freeze(args.root.resolve(), args.config.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
