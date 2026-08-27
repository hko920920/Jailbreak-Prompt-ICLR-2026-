#!/usr/bin/env python3
"""Attest a private self-hosted GPU runner without downloading model weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


class ContractError(RuntimeError):
    """An expected, safe-to-report contract failure."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _version_tuple(value: str) -> tuple[int, ...]:
    pieces = value.strip().split(".")
    if not pieces or any(not piece.isdigit() for piece in pieces):
        raise ContractError("INVALID_DRIVER_VERSION")
    return tuple(int(piece) for piece in pieces)


def _parse_nvidia_smi(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pieces = [piece.strip() for piece in line.split(",")]
        if len(pieces) != 5:
            raise ContractError("INVALID_NVIDIA_SMI_ROW")
        name, total_mib, free_mib, driver, uuid = pieces
        try:
            total = int(total_mib)
            free = int(free_mib)
        except ValueError as exc:
            raise ContractError("INVALID_NVIDIA_SMI_MEMORY") from exc
        rows.append(
            {
                "name": name,
                "memory_total_mib": total,
                "memory_free_mib": free,
                "driver_version": driver,
                "uuid_sha256": _sha256_text(uuid),
            }
        )
    if not rows:
        raise ContractError("NO_GPU_ROWS")
    return rows


def _resolve_private_root(
    env_name: str,
    default_value: str,
    workspace: Path,
) -> Path:
    raw = os.environ.get(env_name, "").strip() or os.path.expanduser(default_value)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ContractError(f"{env_name}_NOT_ABSOLUTE")
    resolved = path.resolve()
    workspace_resolved = workspace.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        pass
    else:
        raise ContractError(f"{env_name}_INSIDE_WORKSPACE")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved.chmod(0o700)
    mode = stat.S_IMODE(resolved.stat().st_mode)
    if mode != 0o700:
        raise ContractError(f"{env_name}_MODE_NOT_0700")
    return resolved


def _safe_base(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "gcg-qwen-self-hosted-runner-attestation-result-v1",
        "evidence_class": "PROTOCOL",
        "paper_validity": False,
        "scientific_pass": False,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "attack_optimization_performed": False,
        "attack_success_observed": False,
        "raw_payload_prompt_target_control_response_or_evaluator_output_recorded": False,
        "contract_schema_version": config.get("schema_version"),
        "source_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "workflow_run": {
            "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"),
        },
    }


def attest(config: dict[str, Any], workspace: Path) -> dict[str, Any]:
    runner = config["runner_contract"]
    hardware = runner["hardware"]
    storage = runner["private_storage"]

    if platform.system() != runner["required_os"]:
        raise ContractError("RUNNER_OS_MISMATCH")
    if platform.machine().lower() not in {item.lower() for item in runner["allowed_architectures"]}:
        raise ContractError("RUNNER_ARCH_MISMATCH")

    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version,uuid",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ContractError("NVIDIA_SMI_FAILED") from exc
    gpu_rows = _parse_nvidia_smi(completed.stdout)

    matching = [row for row in gpu_rows if row["name"] in hardware["allowed_gpu_names"]]
    if len(matching) < hardware["minimum_gpu_count"]:
        raise ContractError("INSUFFICIENT_MATCHING_GPU_COUNT")
    matching = matching[: hardware["minimum_gpu_count"]]

    minimum_total = hardware["minimum_total_memory_mib_per_gpu"]
    minimum_free = hardware["minimum_free_memory_mib_per_gpu"]
    if any(row["memory_total_mib"] < minimum_total for row in matching):
        raise ContractError("INSUFFICIENT_TOTAL_GPU_MEMORY")
    if any(row["memory_free_mib"] < minimum_free for row in matching):
        raise ContractError("INSUFFICIENT_FREE_GPU_MEMORY")

    minimum_driver = _version_tuple(hardware["minimum_driver_version"])
    maximum_driver = _version_tuple(hardware["maximum_driver_version_exclusive"])
    for row in matching:
        observed = _version_tuple(row["driver_version"])
        if observed < minimum_driver or observed >= maximum_driver:
            raise ContractError("DRIVER_OUTSIDE_FROZEN_RANGE")

    cache_root = _resolve_private_root(
        storage["cache_root_env"], storage["cache_root_default"], workspace
    )
    venv_root = _resolve_private_root(
        storage["venv_root_env"], storage["venv_root_default"], workspace
    )
    work_root = _resolve_private_root(
        storage["work_root_env"], storage["work_root_default"], workspace
    )

    free_disk = shutil.disk_usage(cache_root).free
    if free_disk < storage["minimum_free_disk_bytes"]:
        raise ContractError("INSUFFICIENT_PRIVATE_CACHE_DISK")

    safe = _safe_base(config)
    safe.update(
        {
            "status": "GCG_QWEN_SELF_HOSTED_RUNNER_ATTESTATION_PASS",
            "operational_pass": True,
            "runner_attestation_observed": True,
            "execution_ready": False,
            "next_authorized_operation": (
                "MATERIALIZE_GCG_QWEN_DIFFERENTIABLE_ENVIRONMENT_AND_VERIFY_GRADIENT_SMOKE"
            ),
            "runner": {
                "required_labels": runner["required_labels"],
                "runner_name_sha256": _sha256_text(os.environ.get("RUNNER_NAME", "LOCAL")),
                "os": platform.system(),
                "architecture": platform.machine(),
                "host_python": platform.python_version(),
            },
            "gpu_attestation": {
                "observed_gpu_count": len(gpu_rows),
                "qualified_gpu_count": len(matching),
                "qualified_gpus": matching,
                "minimum_total_memory_mib_per_gpu": minimum_total,
                "minimum_free_memory_mib_per_gpu": minimum_free,
                "minimum_driver_version": hardware["minimum_driver_version"],
                "maximum_driver_version_exclusive": hardware["maximum_driver_version_exclusive"],
            },
            "private_storage_attestation": {
                "cache_root_sha256": _sha256_text(str(cache_root)),
                "venv_root_sha256": _sha256_text(str(venv_root)),
                "work_root_sha256": _sha256_text(str(work_root)),
                "directory_mode": "0700",
                "cache_free_disk_bytes": free_disk,
                "raw_paths_recorded": False,
            },
            "attestation_checks": {
                "required_labels_enforced_by_scheduler": True,
                "gpu_identity_pass": True,
                "gpu_count_pass": True,
                "total_gpu_memory_pass": True,
                "free_gpu_memory_pass": True,
                "driver_range_pass": True,
                "private_roots_outside_workspace": True,
                "private_directory_modes_pass": True,
                "private_cache_disk_pass": True,
                "no_model_weight_download": True,
                "no_target_inference": True,
                "no_attack_optimization": True,
            },
        }
    )
    return safe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = attest(config, args.workspace)
    except ContractError as exc:
        result = _safe_base(config)
        result.update(
            {
                "status": "GCG_QWEN_SELF_HOSTED_RUNNER_ATTESTATION_FAIL",
                "operational_pass": False,
                "runner_attestation_observed": True,
                "execution_ready": False,
                "failure_code": str(exc),
                "next_authorized_operation": ("REPAIR_SELF_HOSTED_RUNNER_OR_PRIVATE_STORAGE_ONLY"),
            }
        )
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 1

    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
