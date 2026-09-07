from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "step5n_pre_authorization_readiness_v1.json"
        ),
    )
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[JsonObject]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return rows


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def verify_hashed_file(root: Path, specification: Mapping[str, Any]) -> JsonObject:
    path = resolve(root, str(specification["path"]))
    exists = path.is_file()
    observed_size = path.stat().st_size if exists else None
    observed_sha256 = file_sha256(path) if exists else None
    expected_size = specification.get("size_bytes")
    return {
        "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
        "exists": exists,
        "expected_size_bytes": expected_size,
        "observed_size_bytes": observed_size,
        "size_matches": expected_size is None or observed_size == expected_size,
        "expected_sha256": specification["sha256"],
        "observed_sha256": observed_sha256,
        "sha256_matches": observed_sha256 == specification["sha256"],
    }


def parse_nvidia_row(row: str) -> JsonObject:
    values = [value.strip() for value in row.split(",")]
    if len(values) != 6:
        raise ValueError(f"unexpected nvidia-smi field count: {len(values)}")
    return {
        "name": values[0],
        "driver_version": values[1],
        "memory_total_mib": int(values[2]),
        "memory_used_mib": int(values[3]),
        "memory_free_mib": int(values[4]),
        "temperature_c": int(values[5]),
    }


def inspect_gpu() -> JsonObject:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    rows = [row for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one NVIDIA GPU, observed {len(rows)}")
    return parse_nvidia_row(rows[0])


def system_memory_gib() -> tuple[float, float]:
    if os.name != "nt":
        raise RuntimeError("this readiness snapshot currently supports Windows only")

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.length = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    gib = 1024**3
    return status.total_physical / gib, status.available_physical / gib


def inspect_machine(root: Path) -> JsonObject:
    total_memory, available_memory = system_memory_gib()
    disk = shutil.disk_usage(root)
    return {
        "gpu": inspect_gpu(),
        "system_ram_gib": round(total_memory, 3),
        "system_ram_available_gib": round(available_memory, 3),
        "logical_cpu_count": os.cpu_count(),
        "disk_free_gib": round(disk.free / (1024**3), 3),
    }


def audit_reservation(
    confirmation_rows: Sequence[Mapping[str, Any]],
    development_rows: Sequence[Mapping[str, Any]],
    expectations: Mapping[str, Any],
) -> JsonObject:
    topics = Counter(str(row["topic_id"]) for row in confirmation_rows)
    payloads = [str(row["payload_sha256"]) for row in confirmation_rows]
    development_payloads = {str(row["payload_sha256"]) for row in development_rows}
    ordinals = sorted({int(row["within_topic_ordinal"]) for row in confirmation_rows})
    raw_absent = all(row.get("raw_content_recorded") is False for row in confirmation_rows)
    checks = {
        "row_count_matches": len(confirmation_rows) == int(expectations["rows"]),
        "topic_count_matches": len(topics) == int(expectations["topics"]),
        "rows_per_topic_match": set(topics.values()) == {
            int(expectations["rows_per_topic"])
        },
        "within_topic_ordinals_match": ordinals
        == [int(value) for value in expectations["within_topic_ordinals"]],
        "payloads_unique": len(payloads) == len(set(payloads)),
        "development_overlap_absent": not (set(payloads) & development_payloads),
        "raw_content_absent": raw_absent,
    }
    return {
        "rows": len(confirmation_rows),
        "topics": len(topics),
        "rows_per_topic_counts": dict(sorted(topics.items())),
        "within_topic_ordinals": ordinals,
        "unique_payloads": len(set(payloads)),
        "development_overlap_count": len(set(payloads) & development_payloads),
        "checks": checks,
        "passed": all(checks.values()),
    }


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path)
    config = load_object(config_path)

    dependency_audits = {
        name: verify_hashed_file(root, specification)
        for name, specification in config["dependencies"].items()
    }
    runtime_audit = verify_hashed_file(root, config["runtime"])
    model_audits = []
    for model in config["models"]:
        files = [verify_hashed_file(root, item) for item in model["files"]]
        model_audits.append(
            {
                "model_id": model["model_id"],
                "role_if_authorized": model["role_if_authorized"],
                "runtime_authority": model["runtime_authority"],
                "files": files,
                "passed": all(
                    item["exists"] and item["size_matches"] and item["sha256_matches"]
                    for item in files
                ),
            }
        )

    p2_result = load_object(
        resolve(root, config["dependencies"]["p2_runtime_result"]["path"])
    )
    narrow_audit = load_object(
        resolve(root, config["dependencies"]["d3_narrow_audit"]["path"])
    )
    split_audit = load_object(
        resolve(root, config["dependencies"]["guidedbench_split_audit"]["path"])
    )
    confirmation_rows = load_jsonl(
        resolve(root, config["dependencies"]["confirmation_reservation"]["path"])
    )
    development_rows = load_jsonl(
        resolve(root, config["dependencies"]["development_payload_manifest"]["path"])
    )
    reservation = audit_reservation(
        confirmation_rows,
        development_rows,
        config["reservation_expectations"],
    )
    machine = inspect_machine(root)
    floor = config["machine_floor"]
    machine_checks = {
        "gpu_name_matches": machine["gpu"]["name"] == floor["required_gpu_name"],
        "vram_floor_met": machine["gpu"]["memory_total_mib"]
        >= int(floor["minimum_total_vram_mib"]),
        "system_ram_floor_met": machine["system_ram_gib"]
        >= float(floor["minimum_system_ram_gib"]),
        "disk_floor_met": machine["disk_free_gib"]
        >= float(floor["minimum_free_disk_gib"]),
    }
    machine["checks"] = machine_checks

    dependency_pass = all(
        item["exists"] and item["sha256_matches"] for item in dependency_audits.values()
    )
    checks = {
        "all_dependency_hashes_match": dependency_pass,
        "prior_p2_qualification_passed": p2_result.get("status")
        == "P2_LOCAL_Q4_RUNTIME_QUALIFICATION_PASS",
        "d3_project_route_is_narrow": narrow_audit.get("project_route_decision", {}).get(
            "classification"
        )
        == "NARROW",
        "old_cross_family_d3_not_relabelled_pass": narrow_audit.get(
            "official_cross_family_result", {}
        ).get("d3_core_gate_pass")
        is False,
        "runtime_identity_matches": runtime_audit["exists"]
        and runtime_audit["sha256_matches"],
        "both_model_artifact_sets_match": len(model_audits) == 2
        and all(model["passed"] for model in model_audits),
        "machine_floor_met": all(machine_checks.values()),
        "confirmation_reservation_passed": reservation["passed"],
        "split_audit_confirms_no_overlap": split_audit.get(
            "development_confirmation_overlap"
        )
        is False,
        "no_model_or_evaluator_inference_performed": True,
        "author_narrow_decision_still_required": config["authorization_boundary"][
            "author_narrow_decision_recorded"
        ]
        is False,
    }
    readiness_pass = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-step5n-pre-authorization-readiness-result-v1",
        "status": (
            "STEP5N_PREAUTHORIZATION_STATIC_READINESS_PASS"
            if readiness_pass
            else "STEP5N_PREAUTHORIZATION_STATIC_READINESS_FAIL"
        ),
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "config_sha256": file_sha256(config_path),
        "checks": checks,
        "dependencies": dependency_audits,
        "runtime": runtime_audit,
        "models": model_audits,
        "machine": machine,
        "reservation": reservation,
        "prior_p2_result_identity_sha256": p2_result.get("result_identity_sha256"),
        "split_result_identity_sha256": split_audit.get("result_identity_sha256"),
        "static_readiness_pass": readiness_pass,
        "author_narrow_decision_recorded": False,
        "confirmatory_contract_frozen": False,
        "confirmatory_output_opened": False,
        "scientific_confirmation_authorized": False,
        "paper_validity": False,
        "next_operation": (
            "RECORD_EXPLICIT_AUTHOR_NARROW_DECISION_THEN_FREEZE_AND_PREFLIGHT_"
            "THE_H4RM3L_ONLY_TWO_MODEL_CONFIRMATORY_CONTRACT"
        ),
        "raw_prompt_payload_or_response_recorded": False,
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    output_path = resolve(root, config["recording"]["output_path"])
    write_json_atomic(output_path, result)
    return result


def main() -> int:
    arguments = parser().parse_args()
    result = run(arguments.root, arguments.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_identity_sha256": result["result_identity_sha256"],
                "output_opened": result["confirmatory_output_opened"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["static_readiness_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
