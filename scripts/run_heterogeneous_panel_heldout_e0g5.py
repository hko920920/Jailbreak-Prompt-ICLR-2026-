from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jbspan.evaluator_abstaining_panel import metrics_by_group, panel_label, qwen_axis_label
from jbspan.evaluator_cpu_router import classification_metrics
from jbspan.evaluator_full_calibration import (
    behavior_cluster_bootstrap,
    behavior_group_decision_metrics,
    deterministic_execution_order,
)
from jbspan.evaluator_heldout_inputs import (
    HeldoutInputRecord,
    load_and_validate_identity_manifests,
    reconstruct_label_blind_inputs,
)
from jbspan.evaluator_output_integrity import output_limit_integrity_summary
from jbspan.gate1.util import canonical_json_sha256

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument(
        "command", choices=("freeze", "preflight", "status", "qwen", "jailmeter", "finalize")
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/heterogeneous_panel_heldout_e0g5_v1.json"),
    )
    return value


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value: object = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    encoded = text.encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite different frozen output: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()


def safe_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = encode_jsonl(rows)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite different frozen output: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def checkpoint_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encode_jsonl(rows))
    temporary.replace(path)


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def verify_file(path: Path, spec: Mapping[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"file size mismatch: {path}")
    if file_sha256(path) != str(spec["sha256"]):
        raise ValueError(f"file SHA-256 mismatch: {path}")


def repo_module(root: Path, name: str) -> Any:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return importlib.import_module(name)


def load_config(root: Path, config_path: Path) -> tuple[Path, JsonObject, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_object(config_path)
    if config.get("schema_version") != "jbspan-e0g5-heterogeneous-panel-heldout-v1":
        raise ValueError("unsupported E0G-5 contract")
    if config.get("status") != "FROZEN_BEFORE_HELDOUT_MODEL_OUTPUT_OR_LABEL_OPENING":
        raise ValueError("E0G-5 contract is not in its frozen pre-outcome state")
    if config.get("frozen") is not True:
        raise ValueError("E0G-5 contract must be frozen")

    protected = required_mapping(config["protected_boundaries"], where="protected_boundaries")
    if any(protected.values()):
        raise ValueError("E0G-5 contract must begin with every protected boundary false")

    implementation = required_mapping(config["implementation"], where="implementation")
    for name in (
        "runner",
        "heldout_input_module",
        "output_integrity_module",
        "panel_module",
        "metric_module",
        "source_freeze_runner",
        "source_data_module",
    ):
        implementation_spec = required_mapping(implementation[name], where=name)
        verify_file(root / str(implementation_spec["path"]), implementation_spec)

    protocol = required_mapping(config["prospective_protocol"], where="prospective_protocol")
    verify_file(root / str(protocol["path"]), protocol)

    source = required_mapping(config["source_freeze"], where="source_freeze")
    verify_file(root / str(source["contract_path"]), {"sha256": source["contract_sha256"]})
    verify_file(
        root / str(source["preflight_path"]),
        {"bytes": source["preflight_bytes"], "sha256": source["preflight_sha256"]},
    )
    source_preflight = load_object(root / str(source["preflight_path"]))
    if (
        source_preflight.get("status") != source["required_preflight_status"]
        or source_preflight.get("result_identity_sha256")
        != source["required_preflight_identity"]
        or source_preflight.get("heldout_opened") is not False
    ):
        raise ValueError("E0B source-freeze identity or sealed state mismatch")

    manifests = required_mapping(config["sealed_identity_manifests"], where="manifests")
    for name in ("full", "primary", "exposed_stress"):
        spec = required_mapping(manifests[name], where=f"manifests.{name}")
        verify_file(root / str(spec["path"]), spec)

    development = required_mapping(
        config["development_qualification"], where="development_qualification"
    )
    parent_contract = required_mapping(development["parent_contract"], where="parent_contract")
    verify_file(root / str(parent_contract["path"]), parent_contract)
    amendment = required_mapping(development["integrity_amendment"], where="amendment")
    verify_file(root / str(amendment["path"]), amendment)
    result_spec = required_mapping(development["authoritative_result"], where="result")
    verify_file(root / str(result_spec["path"]), result_spec)
    result = load_object(root / str(result_spec["path"]))
    if (
        result.get("status") != result_spec["required_status"]
        or result.get("result_identity_sha256") != result_spec["required_identity"]
        or result.get("authoritative_result") is not True
        or result.get("panel_qualified_for_heldout_candidate") is not True
    ):
        raise ValueError("E0G-4 did not authorize the held-out gate")
    if dict(required_mapping(config["fixed_panel_rule"], where="fixed_panel_rule")) != dict(
        required_mapping(result["panel_rule"], where="qualified panel_rule")
    ):
        raise ValueError("E0G-5 panel rule differs from qualified E0G-4")

    e0g4 = repo_module(root, "scripts.run_heterogeneous_panel_full_development_e0g4")
    _, _, parent_runtime = e0g4.load_config(root, root / str(parent_contract["path"]))
    return config_path, config, parent_runtime


def identity_paths(config: Mapping[str, Any]) -> tuple[Path, Path, Path]:
    manifests = required_mapping(config["sealed_identity_manifests"], where="manifests")
    return tuple(  # type: ignore[return-value]
        Path(str(required_mapping(manifests[name], where=name)["path"]))
        for name in ("full", "primary", "exposed_stress")
    )


def load_identities(root: Path, config: Mapping[str, Any]) -> list[JsonObject]:
    full_path, primary_path, stress_path = identity_paths(config)
    return load_and_validate_identity_manifests(
        root=root,
        full_path=full_path,
        primary_path=primary_path,
        stress_path=stress_path,
    )


def frozen_fold(group_sha256: str, *, seed: str, folds: int) -> int:
    if folds <= 1:
        raise ValueError("held-out reporting requires at least two folds")
    digest = hashlib.sha256(f"{seed}|{group_sha256}".encode()).hexdigest()
    return int(digest[:16], 16) % folds


def freeze_selection(root: Path, config_path: Path) -> JsonObject:
    config_path, config, _parent = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    selection_path = root / str(recording["selection_path"])
    manifest_path = root / str(recording["selection_manifest_path"])
    if selection_path.exists() or manifest_path.exists():
        if not selection_path.exists() or not manifest_path.exists():
            raise ValueError("partial E0G-5 selection exists")
        existing = load_object(manifest_path)
        if (
            existing.get("contract_sha256") != file_sha256(config_path)
            or existing.get("selection_file_sha256") != file_sha256(selection_path)
        ):
            raise ValueError("existing E0G-5 selection identity mismatch")
        return existing

    identities = load_identities(root, config)
    analysis = required_mapping(config["analysis"], where="analysis")
    fold_seed = str(analysis["reporting_fold_seed"])
    folds = int(analysis["reporting_folds"])
    for row in identities:
        row["reporting_fold"] = frozen_fold(
            str(row["behavior_group_sha256"]), seed=fold_seed, folds=folds
        )
    execution = required_mapping(config["execution_order"], where="execution_order")
    ordered = deterministic_execution_order(identities, seed=str(execution["seed"]))
    fields = (
        "record_id",
        "source_id",
        "source_locator_sha256",
        "behavior_group_sha256",
        "response_sha256",
        "partition",
        "strata",
        "human_label_sealed",
        "evaluation_role",
        "reporting_fold",
        "execution_score",
        "execution_order",
    )
    rows = [{field: row[field] for field in fields} for row in ordered]
    forbidden_label_fields = (
        "human_label",
        "human_unanimous",
        "human_annotation_count",
        "human_label_support_count",
    )
    if len(rows) != 947 or any(
        label_field in row for row in rows for label_field in forbidden_label_fields
    ):
        raise ValueError("E0G-5 selection count or label seal failed")
    safe_write_jsonl(selection_path, rows)
    role_counts = Counter(str(row["evaluation_role"]) for row in rows)
    source_counts = Counter(str(row["source_id"]) for row in rows)
    manifest: JsonObject = {
        "schema_version": "jbspan-e0g5-heldout-selection-manifest-v1",
        "status": "E0G5_LABEL_SEALED_SELECTION_FROZEN",
        "contract_sha256": file_sha256(config_path),
        "selection_file": selection_path.relative_to(root).as_posix(),
        "selection_file_bytes": selection_path.stat().st_size,
        "selection_file_sha256": file_sha256(selection_path),
        "record_count": len(rows),
        "role_counts": dict(sorted(role_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "behavior_groups": len({str(row["behavior_group_sha256"]) for row in rows}),
        "primary_behavior_groups": len(
            {
                str(row["behavior_group_sha256"])
                for row in rows
                if row["evaluation_role"] == "PRIMARY"
            }
        ),
        "stress_behavior_groups": len(
            {
                str(row["behavior_group_sha256"])
                for row in rows
                if row["evaluation_role"] == "EXPOSED_STRESS"
            }
        ),
        "reporting_fold_counts": dict(
            sorted(Counter(str(row["reporting_fold"]) for row in rows).items())
        ),
        "human_labels_present": False,
        "model_outputs_observed": False,
        "raw_text_read": False,
        "raw_text_written": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    manifest["selection_identity_sha256"] = canonical_json_sha256(manifest)
    safe_write(manifest_path, manifest)
    return manifest


def reconstruct_ordered_records(
    root: Path, config: Mapping[str, Any]
) -> tuple[list[HeldoutInputRecord], JsonObject]:
    recording = required_mapping(config["recording"], where="recording")
    selection = load_jsonl(root / str(recording["selection_path"]))
    source_spec = required_mapping(config["source_freeze"], where="source_freeze")
    source_contract = load_object(root / str(source_spec["contract_path"]))
    records, audit = reconstruct_label_blind_inputs(
        root=root,
        source_contract=source_contract,
        identities=selection,
    )
    for record, identity in zip(records, selection, strict=True):
        if (
            record.record_id != identity["record_id"]
            or record.evaluation_role != identity["evaluation_role"]
            or record.behavior_group_sha256 != identity["behavior_group_sha256"]
            or record.response_sha256 != identity["response_sha256"]
        ):
            raise ValueError("ordered label-blind input differs from frozen selection")
    return records, audit


def gpu_identity() -> JsonObject:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        raise RuntimeError("nvidia-smi is unavailable")
    completed = subprocess.run(
        [
            executable,
            "--query-gpu=name,driver_version,pci.device_id,compute_cap",
            "--format=csv,noheader",
            "-i",
            "0",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not query E0G-5 GPU identity")
    parts = [value.strip() for value in completed.stdout.strip().split(",")]
    if len(parts) != 4:
        raise ValueError("unexpected nvidia-smi GPU identity shape")
    return {
        "gpu_name": parts[0],
        "driver_version": parts[1],
        "pci_device_id": parts[2],
        "compute_capability": parts[3],
    }


def verify_gpu_identity(config: Mapping[str, Any]) -> JsonObject:
    runtime = required_mapping(config["runtime"], where="runtime")
    expected = dict(required_mapping(runtime["device_continuity"], where="device"))
    expected.pop("rule", None)
    observed = gpu_identity()
    if observed != expected:
        raise RuntimeError(f"E0G-5 GPU identity changed: observed={observed}")
    return observed


def qwen_prompt(tokenizer: Any, record: HeldoutInputRecord) -> JsonObject:
    rendered = tokenizer.apply_chat_template(
        [
            {"role": "user", "content": record.goal_text},
            {"role": "assistant", "content": record.response_text},
        ],
        tokenize=False,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("Qwen3Guard tokenizer returned an invalid E0G-5 prompt")
    return {
        "record_id": record.record_id,
        "prompt": rendered,
        "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_tokens": len(tokenizer.encode(rendered, add_special_tokens=False)),
    }


def jailmeter_prompt(
    tokenizer: Any, system_prompt: str, record: HeldoutInputRecord
) -> JsonObject:
    user_content = json.dumps(
        {"original_question": record.goal_text, "model_response": record.response_text},
        ensure_ascii=False,
    )
    rendered = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("JailMeter tokenizer returned an invalid E0G-5 prompt")
    return {
        "record_id": record.record_id,
        "prompt": rendered,
        "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_tokens": len(tokenizer.encode(rendered, add_special_tokens=False)),
    }


def token_census(values: Sequence[int]) -> JsonObject:
    if not values:
        raise ValueError("token census requires records")
    ordered = sorted(values)
    return {
        "minimum": ordered[0],
        "median": ordered[len(ordered) // 2],
        "p95_nearest_rank": ordered[min(len(ordered) - 1, (95 * len(ordered) - 1) // 100)],
        "maximum": ordered[-1],
    }


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_runtime = load_config(root, config_path)
    selection_manifest = freeze_selection(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["preflight_path"])
    if output_path.exists():
        existing = load_object(output_path)
        if (
            existing.get("contract_sha256") != file_sha256(config_path)
            or existing.get("preflight_identity_sha256") is None
        ):
            raise ValueError("existing E0G-5 preflight identity mismatch")
        return existing

    for field in (
        "qwen_progress_path",
        "qwen_axis_path",
        "qwen_summary_path",
        "jailmeter_progress_path",
        "jailmeter_axis_path",
        "jailmeter_summary_path",
        "label_opening_receipt_path",
        "result_path",
    ):
        if (root / str(recording[field])).exists():
            raise ValueError("E0G-5 output exists before first preflight")

    observed_gpu = verify_gpu_identity(config)
    records, reconstruction = reconstruct_ordered_records(root, config)
    axes = required_mapping(parent_runtime["qualified_axes"], where="qualified_axes")

    qwen = repo_module(root, "scripts.qualify_qwen3guard_runtime_e0g1a")
    qwen_axis = required_mapping(axes["qwen3guard"], where="qwen3guard axis")
    _, qwen_config = qwen.resolve_config(root, root / str(qwen_axis["contract_path"]))
    qwen_files, qwen_bytes = qwen.verify_model_files(root, qwen_config)
    from transformers import AutoTokenizer

    qwen_runtime = required_mapping(parent_runtime["qwen3guard_runtime"], where="qwen runtime")
    qwen_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(qwen_runtime["model_local_path"]), local_files_only=True
    )
    qwen_prompts = [qwen_prompt(qwen_tokenizer, record) for record in records]

    jailmeter = repo_module(root, "scripts.qualify_jailmeter_runtime_e0g1b")
    jailmeter_axis = required_mapping(axes["jailmeter"], where="jailmeter axis")
    _, jailmeter_config = jailmeter.resolve_config(
        root, root / str(jailmeter_axis["contract_path"])
    )
    source_rows = jailmeter.verify_source(root, jailmeter_config)
    target_rows = jailmeter.verify_target_model(root, jailmeter_config)
    runtime_identity = jailmeter.verify_runtime(root, jailmeter_config)
    conversion = jailmeter.convert(root, root / str(jailmeter_axis["contract_path"]))
    jailmeter_runtime = required_mapping(
        parent_runtime["jailmeter_runtime"], where="jailmeter runtime"
    )
    jailmeter_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(jailmeter_runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    system_prompt = sentinel.extract_system_prompt(root / str(jailmeter_runtime["runner_path"]))
    jailmeter_prompts = [
        jailmeter_prompt(jailmeter_tokenizer, system_prompt, record) for record in records
    ]
    full_runtime = required_mapping(config["runtime"], where="runtime")
    jailmeter_full = required_mapping(full_runtime["jailmeter"], where="jailmeter full")
    jailmeter_tokens = [int(row["input_tokens"]) for row in jailmeter_prompts]
    context_required = max(jailmeter_tokens) + int(jailmeter_runtime["max_new_tokens"])
    if context_required > int(jailmeter_full["context_tokens"]):
        raise ValueError("E0G-5 JailMeter prompt exceeds frozen context budget")
    if shutil.disk_usage(root).free < int(full_runtime["minimum_free_disk_bytes"]):
        raise RuntimeError("insufficient free disk for E0G-5")

    result: JsonObject = {
        "schema_version": "jbspan-e0g5-heldout-preflight-v1",
        "status": "E0G5_LABEL_SEALED_PREFLIGHT_PASS",
        "contract_path": config_path.relative_to(root).as_posix(),
        "contract_sha256": file_sha256(config_path),
        "implementation": {
            "path": Path(__file__).resolve().relative_to(root).as_posix(),
            "bytes": Path(__file__).stat().st_size,
            "sha256": file_sha256(Path(__file__)),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "free_disk_bytes": shutil.disk_usage(root).free,
            "gpu": observed_gpu,
        },
        "selection_identity_sha256": selection_manifest["selection_identity_sha256"],
        "records_reconstructed": len(records),
        "reconstruction": reconstruction,
        "qwen_model_file_count": len(qwen_files),
        "qwen_model_bytes": qwen_bytes,
        "qwen_token_census": token_census(
            [int(row["input_tokens"]) for row in qwen_prompts]
        ),
        "qwen_input_identity_sha256": canonical_json_sha256(
            [
                {"record_id": row["record_id"], "input_sha256": row["input_sha256"]}
                for row in qwen_prompts
            ]
        ),
        "jailmeter_source_files_verified": len(source_rows),
        "jailmeter_target_files_verified": len(target_rows),
        "jailmeter_runtime_identity": runtime_identity,
        "jailmeter_conversion_identity_sha256": conversion["conversion_identity_sha256"],
        "jailmeter_token_census": token_census(jailmeter_tokens),
        "jailmeter_context_required_maximum": context_required,
        "jailmeter_context_tokens": int(jailmeter_full["context_tokens"]),
        "jailmeter_input_identity_sha256": canonical_json_sha256(
            [
                {"record_id": row["record_id"], "input_sha256": row["input_sha256"]}
                for row in jailmeter_prompts
            ]
        ),
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "parallel_slots": 1,
        "human_label_fields_accessed": False,
        "human_vote_fields_accessed": False,
        "raw_text_read_in_memory": True,
        "raw_text_written": False,
        "heldout_model_output_observed": False,
        "heldout_label_opened": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def execution_order_index(root: Path, config: Mapping[str, Any]) -> dict[str, int]:
    recording = required_mapping(config["recording"], where="recording")
    return {
        str(row["record_id"]): int(row["execution_order"])
        for row in load_jsonl(root / str(recording["selection_path"]))
    }


def prepare_progress(
    *,
    progress_path: Path,
    prompt_index: Mapping[str, Mapping[str, Any]],
    order_index: Mapping[str, int],
) -> list[JsonObject]:
    rows = load_jsonl(progress_path) if progress_path.exists() else []
    ids = [str(row["record_id"]) for row in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(order_index):
        raise ValueError("E0G-5 progress IDs are duplicated or outside the frozen pool")
    for row in rows:
        record_id = str(row["record_id"])
        prompt = prompt_index[record_id]
        if (
            row.get("execution_order") != order_index[record_id]
            or row.get("input_sha256") != prompt["input_sha256"]
            or row.get("input_tokens") != prompt["input_tokens"]
            or row.get("cache_origin") != "E0G5_NEW_ONE_SHOT"
            or "prompt" in row
            or "content" in row
        ):
            raise ValueError("E0G-5 progress row failed identity/safety validation")
    return sorted(rows, key=lambda row: int(row["execution_order"]))


def complete_axis_pair(
    root: Path, axis_path: Path, summary_path: Path, expected_records: int
) -> JsonObject | None:
    if not axis_path.exists() and not summary_path.exists():
        return None
    if not axis_path.exists() or not summary_path.exists():
        raise ValueError("partial E0G-5 final axis pair exists")
    summary = load_object(summary_path)
    if (
        summary.get("record_count") != expected_records
        or summary.get("axis_file_sha256") != file_sha256(axis_path)
    ):
        raise ValueError("E0G-5 final axis identity mismatch")
    return summary


def finalize_axis_files(
    *,
    root: Path,
    progress_path: Path,
    axis_path: Path,
    summary_path: Path,
    rows: Sequence[Mapping[str, Any]],
    summary: JsonObject,
) -> JsonObject:
    safe_write_jsonl(axis_path, rows)
    summary["axis_file"] = axis_path.relative_to(root).as_posix()
    summary["axis_file_bytes"] = axis_path.stat().st_size
    summary["axis_file_sha256"] = file_sha256(axis_path)
    summary["axis_identity_sha256"] = canonical_json_sha256(summary)
    safe_write(summary_path, summary)
    if progress_path.exists():
        progress_path.unlink()
    return summary


def integrity_rows(rows: Sequence[Mapping[str, Any]]) -> list[JsonObject]:
    output: list[JsonObject] = []
    for row in rows:
        value = dict(row)
        raw_flag = value.get("raw_output_limit_stop")
        if not isinstance(raw_flag, bool):
            raise ValueError("axis row lacks a raw output-limit flag")
        value["output_limit_stop"] = raw_flag
        output.append(value)
    return output


def run_qwen(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_runtime = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    verify_gpu_identity(config)
    recording = required_mapping(config["recording"], where="recording")
    expected_records = int(config["heldout_pool"]["records"])
    progress_path = root / str(recording["qwen_progress_path"])
    axis_path = root / str(recording["qwen_axis_path"])
    summary_path = root / str(recording["qwen_summary_path"])
    completed = complete_axis_pair(root, axis_path, summary_path, expected_records)
    if completed is not None:
        return completed

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("E0G-5 Qwen3Guard requires CUDA")
    runtime = required_mapping(parent_runtime["qwen3guard_runtime"], where="qwen runtime")
    full_runtime = required_mapping(config["runtime"]["qwen3guard"], where="qwen full")
    records, _audit = reconstruct_ordered_records(root, config)
    model_path = root / str(runtime["model_local_path"])
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        model_path, local_files_only=True
    )
    prompt_rows = [qwen_prompt(tokenizer, record) for record in records]
    prompt_index = {str(row["record_id"]): row for row in prompt_rows}
    order_index = execution_order_index(root, config)
    rows = prepare_progress(
        progress_path=progress_path,
        prompt_index=prompt_index,
        order_index=order_index,
    )
    initially_completed = len(rows)
    completed_ids = {str(row["record_id"]) for row in rows}
    new_records = [record for record in records if record.record_id not in completed_ids]
    if not new_records:
        raise RuntimeError("unexpected complete Qwen progress without final axis")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch.cuda.init()  # type: ignore[no-untyped-call]
    torch.cuda.set_device(0)
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(
        full_runtime["maximum_prelaunch_gpu_memory_mib"]
    ):
        raise RuntimeError(f"E0G-5 Qwen GPU baseline is uncontrolled: {baseline_gpu} MiB")
    if bool(runtime["do_sample"]):
        raise ValueError("E0G-5 Qwen generation must remain deterministic")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    started = time.perf_counter()
    load_started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        dtype=torch.float16,
        local_files_only=True,
        low_cpu_mem_usage=True,
    ).to(torch.device("cuda:0"))  # type: ignore[arg-type]
    model.eval()
    model_load_seconds = time.perf_counter() - load_started
    for record in new_records:
        prompt = prompt_index[record.record_id]
        encoded = tokenizer([prompt["prompt"]], return_tensors="pt").to(torch.device("cuda:0"))
        if int(encoded.input_ids.shape[1]) != int(prompt["input_tokens"]):
            raise ValueError("Qwen runtime token count differs from preflight reconstruction")
        call_started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                do_sample=bool(runtime["do_sample"]),
                max_new_tokens=int(runtime["max_new_tokens"]),
                pad_token_id=tokenizer.eos_token_id,
            )
        output_ids = generated[0][encoded.input_ids.shape[1] :].tolist()
        content = tokenizer.decode(output_ids, skip_special_tokens=True)
        parsed = sentinel.parse_qwen_output(content, runtime)
        limit_stop = len(output_ids) >= int(runtime["max_new_tokens"])
        rows.append(
            {
                "record_id": record.record_id,
                "execution_order": order_index[record.record_id],
                "cache_origin": "E0G5_NEW_ONE_SHOT",
                "input_sha256": prompt["input_sha256"],
                "input_tokens": int(encoded.input_ids.shape[1]),
                "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "output_characters": len(content),
                "output_tokens": len(output_ids),
                "raw_output_limit_stop": limit_stop,
                "output_limit_stop": limit_stop,
                "output_limit_derived_from_token_boundary": False,
                "safety": parsed["safety"],
                "refusal": parsed["refusal"],
                "categories": parsed["categories"],
                "safety_match_count": parsed["safety_match_count"],
                "refusal_match_count": parsed["refusal_match_count"],
                "inference_seconds": time.perf_counter() - call_started,
            }
        )
        rows.sort(key=lambda row: int(row["execution_order"]))
        checkpoint_jsonl(progress_path, rows)
        if time.perf_counter() - started > float(full_runtime["maximum_total_seconds"]):
            raise TimeoutError("E0G-5 Qwen3Guard exceeded its per-invocation budget")
    total_seconds = time.perf_counter() - started
    if len(rows) != expected_records:
        raise RuntimeError("E0G-5 Qwen3Guard denominator is incomplete")
    parsed_count = sum(row["safety"] is not None and row["refusal"] is not None for row in rows)
    integrity = output_limit_integrity_summary(
        integrity_rows(rows), maximum_output_tokens=int(runtime["max_new_tokens"])
    )
    if int(integrity["missing_output_token_count"]) != 0:
        raise ValueError("Qwen axis has missing output-token metadata")
    peak_cuda = int(torch.cuda.max_memory_allocated(0))
    summary: JsonObject = {
        "schema_version": "jbspan-e0g5-qwen-axis-summary-v1",
        "status": "E0G5_QWEN3GUARD_HELDOUT_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "cached_progress_records": initially_completed,
        "new_records_this_invocation": len(new_records),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "raw_output_limit_stops": int(integrity["raw_flag_count"]),
        "effective_output_limit_stops": int(integrity["effective_count"]),
        "model_load_seconds_this_invocation": model_load_seconds,
        "total_seconds_this_invocation": total_seconds,
        "sum_per_record_inference_seconds": sum(float(row["inference_seconds"]) for row in rows),
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_cuda_allocated_bytes_this_invocation": peak_cuda,
        "safety_counts": dict(Counter(str(row["safety"]) for row in rows)),
        "refusal_counts": dict(Counter(str(row["refusal"]) for row in rows)),
        "resume_checkpoint_used": initially_completed > 0,
        "progress_checkpoint_retained": False,
        "human_labels_opened": False,
        "raw_text_written": False,
        "raw_model_output_written": False,
    }
    del model
    torch.cuda.empty_cache()
    return finalize_axis_files(
        root=root,
        progress_path=progress_path,
        axis_path=axis_path,
        summary_path=summary_path,
        rows=rows,
        summary=summary,
    )


def run_jailmeter(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_runtime = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    verify_gpu_identity(config)
    recording = required_mapping(config["recording"], where="recording")
    expected_records = int(config["heldout_pool"]["records"])
    progress_path = root / str(recording["jailmeter_progress_path"])
    axis_path = root / str(recording["jailmeter_axis_path"])
    summary_path = root / str(recording["jailmeter_summary_path"])
    completed = complete_axis_pair(root, axis_path, summary_path, expected_records)
    if completed is not None:
        return completed

    from transformers import AutoTokenizer

    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    runtime = required_mapping(parent_runtime["jailmeter_runtime"], where="jailmeter runtime")
    full_runtime = required_mapping(config["runtime"]["jailmeter"], where="jailmeter full")
    if float(runtime["temperature"]) != 0.0:
        raise ValueError("E0G-5 JailMeter generation must remain deterministic")
    records, _audit = reconstruct_ordered_records(root, config)
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    system_prompt = sentinel.extract_system_prompt(root / str(runtime["runner_path"]))
    prompt_rows = [jailmeter_prompt(tokenizer, system_prompt, record) for record in records]
    prompt_index = {str(row["record_id"]): row for row in prompt_rows}
    order_index = execution_order_index(root, config)
    rows = prepare_progress(
        progress_path=progress_path,
        prompt_index=prompt_index,
        order_index=order_index,
    )
    initially_completed = len(rows)
    completed_ids = {str(row["record_id"]) for row in rows}
    new_records = [record for record in records if record.record_id not in completed_ids]
    if not new_records:
        raise RuntimeError("unexpected complete JailMeter progress without final axis")

    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(
        full_runtime["maximum_prelaunch_gpu_memory_mib"]
    ):
        raise RuntimeError(f"E0G-5 JailMeter GPU baseline is uncontrolled: {baseline_gpu} MiB")
    host = str(runtime["host"])
    port = int(runtime["port"])
    if not sentinel.port_is_free(host, port):
        raise ValueError(f"E0G-5 JailMeter port is occupied: {host}:{port}")
    runtime_directory = root / str(runtime["runtime_directory"])
    server_path = runtime_directory / str(runtime["server_relative_path"])
    command = [
        str(server_path),
        "-m",
        str(root / str(runtime["target_model_path"])),
        "--lora",
        str(root / str(runtime["lora_path"])),
        "--host",
        host,
        "--port",
        str(port),
        "-c",
        str(full_runtime["context_tokens"]),
        "-t",
        str(runtime["threads"]),
        "-ngl",
        str(runtime["gpu_layers"]),
        "--offline",
        "--no-webui",
    ]
    log_handle = tempfile.NamedTemporaryFile(prefix="e0g5-jailmeter-", suffix=".log", delete=False)
    log_path = Path(log_handle.name)
    gpu_samples: list[float] = []
    stop_sampling = threading.Event()

    def sample_gpu() -> None:
        while not stop_sampling.is_set():
            value = sentinel.query_gpu_memory_mib()
            if value is not None:
                gpu_samples.append(float(value))
            stop_sampling.wait(0.25)

    sampler = threading.Thread(target=sample_gpu, daemon=True)
    sampler.start()
    process: subprocess.Popen[bytes] | None = None
    started = time.perf_counter()
    ready_seconds: float | None = None
    failure: BaseException | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=runtime_directory,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        health_url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + float(runtime["health_timeout_seconds"])
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited during startup: {process.returncode}")
            if sentinel.server_ready(health_url):
                ready_seconds = time.perf_counter() - started
                break
            time.sleep(0.25)
        if ready_seconds is None:
            raise TimeoutError("E0G-5 JailMeter server health timeout")
        for record in new_records:
            prompt = prompt_index[record.record_id]
            call_started = time.perf_counter()
            response = sentinel.post_json(
                f"http://{host}:{port}/completion",
                {
                    "prompt": prompt["prompt"],
                    "n_predict": int(runtime["max_new_tokens"]),
                    "temperature": float(runtime["temperature"]),
                    "stream": False,
                    "cache_prompt": False,
                },
                timeout=float(runtime["request_timeout_seconds"]),
            )
            content = response.get("content")
            if not isinstance(content, str):
                raise ValueError("E0G-5 JailMeter endpoint returned no text")
            parsed = sentinel.parse_jailmeter_label(content, runtime)
            predicted_value = response.get("tokens_predicted")
            predicted = (
                predicted_value
                if isinstance(predicted_value, int) and not isinstance(predicted_value, bool)
                else None
            )
            raw_limit = bool(response.get("stopped_limit", False))
            boundary_limit = predicted is not None and predicted >= int(runtime["max_new_tokens"])
            effective_limit = raw_limit or boundary_limit
            rows.append(
                {
                    "record_id": record.record_id,
                    "execution_order": order_index[record.record_id],
                    "cache_origin": "E0G5_NEW_ONE_SHOT",
                    "input_sha256": prompt["input_sha256"],
                    "input_tokens": prompt["input_tokens"],
                    "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "output_characters": len(content),
                    "output_tokens": predicted,
                    "raw_output_limit_stop": raw_limit,
                    "output_limit_stop": effective_limit,
                    "output_limit_derived_from_token_boundary": boundary_limit and not raw_limit,
                    "label": parsed["label"],
                    "label_match_count": parsed["match_count"],
                    "inference_seconds": time.perf_counter() - call_started,
                }
            )
            rows.sort(key=lambda row: int(row["execution_order"]))
            checkpoint_jsonl(progress_path, rows)
            if time.perf_counter() - started > float(full_runtime["maximum_total_seconds"]):
                raise TimeoutError("E0G-5 JailMeter exceeded its per-invocation budget")
    except BaseException as exc:
        failure = exc
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
        stop_sampling.set()
        sampler.join(timeout=10)
        log_handle.close()
    total_seconds = time.perf_counter() - started
    log_content = log_path.read_bytes()
    log_sha256 = hashlib.sha256(log_content).hexdigest()
    log_path.unlink(missing_ok=True)
    if failure is not None:
        raise failure
    if len(rows) != expected_records:
        raise RuntimeError("E0G-5 JailMeter denominator is incomplete")
    peak_gpu = max(gpu_samples) if gpu_samples else None
    if peak_gpu is None or peak_gpu > float(full_runtime["maximum_peak_gpu_memory_mib"]):
        raise RuntimeError(f"E0G-5 JailMeter peak GPU budget failed: {peak_gpu} MiB")
    integrity = output_limit_integrity_summary(
        integrity_rows(rows), maximum_output_tokens=int(runtime["max_new_tokens"])
    )
    if int(integrity["missing_output_token_count"]) != 0:
        raise ValueError("JailMeter axis has missing output-token metadata")
    parsed_count = sum(row["label"] is not None for row in rows)
    summary = {
        "schema_version": "jbspan-e0g5-jailmeter-axis-summary-v1",
        "status": "E0G5_JAILMETER_HELDOUT_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "cached_progress_records": initially_completed,
        "new_records_this_invocation": len(new_records),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "raw_output_limit_stops": int(integrity["raw_flag_count"]),
        "effective_output_limit_stops": int(integrity["effective_count"]),
        "derived_only_output_limit_stops": int(integrity["derived_only_count"]),
        "server_ready_seconds_this_invocation": ready_seconds,
        "total_seconds_this_invocation": total_seconds,
        "sum_per_record_inference_seconds": sum(float(row["inference_seconds"]) for row in rows),
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_gpu_memory_mib": peak_gpu,
        "gpu_memory_delta_mib": peak_gpu - baseline_gpu,
        "label_counts": dict(Counter(str(row["label"]) for row in rows)),
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "server_log_bytes": len(log_content),
        "server_log_sha256": log_sha256,
        "server_log_retained": False,
        "resume_checkpoint_used": initially_completed > 0,
        "progress_checkpoint_retained": False,
        "human_labels_opened": False,
        "raw_text_written": False,
        "raw_model_output_written": False,
    }
    return finalize_axis_files(
        root=root,
        progress_path=progress_path,
        axis_path=axis_path,
        summary_path=summary_path,
        rows=rows,
        summary=summary,
    )


def axis_index(path: Path, expected_ids: set[str]) -> dict[str, JsonObject]:
    rows = load_jsonl(path)
    index = {str(row["record_id"]): row for row in rows}
    if len(rows) != len(index) or set(index) != expected_ids:
        raise ValueError(f"E0G-5 axis keys differ from the frozen selection: {path}")
    return index


def open_committed_labels(
    root: Path,
    config: Mapping[str, Any],
    selection: Sequence[Mapping[str, Any]],
    axis_sha256s: Mapping[str, str],
) -> tuple[list[JsonObject], JsonObject]:
    """Open the precommitted public labels only after both axes are immutable."""

    source_spec = required_mapping(config["source_freeze"], where="source_freeze")
    source_contract = load_object(root / str(source_spec["contract_path"]))
    source_runner = repo_module(root, "scripts.freeze_evaluator_panel_external_sources_e0b")
    specs = source_runner._source_specs(source_contract)
    sources = (
        source_runner._load_strongreject(root, specs["strongreject"]),
        source_runner._load_jailbreakbench(root, specs["jailbreakbench"]),
        source_runner._load_harmbench(root, specs["harmbench"]),
    )
    all_records = tuple(record for source in sources for record in source.records)
    deduplicated = source_runner.deduplicate_external_records(all_records)
    split = required_mapping(source_contract["split"], where="source split")
    split_seed = str(split["seed"])
    labeled_rows = [
        source_runner.safe_manifest_record(record, split_seed=split_seed)
        for record in deduplicated.admitted_records
    ]
    labeled_rows.sort(key=lambda row: (row["partition"], row["source_id"], row["record_id"]))
    source_runner._assert_no_leakage(labeled_rows)
    source_runner._assert_expected(source_contract, labeled_rows)
    heldout = [row for row in labeled_rows if row["partition"] == "heldout"]
    payload = encode_jsonl(heldout)
    commitment = required_mapping(config["label_commitment"], where="label_commitment")
    if (
        len(heldout) != int(commitment["records"])
        or len(payload) != int(commitment["bytes"])
        or hashlib.sha256(payload).hexdigest() != commitment["sha256"]
    ):
        raise ValueError("opened held-out labels do not match the precommitted payload")

    full_path, _primary_path, _stress_path = identity_paths(config)
    sealed_rows = load_jsonl(root / full_path)
    sealed_index = {str(row["record_id"]): row for row in sealed_rows}
    opened_index = {str(row["record_id"]): row for row in heldout}
    if len(sealed_index) != 947 or set(sealed_index) != set(opened_index):
        raise ValueError("opened labels differ from the sealed held-out ID set")
    for record_id, row in opened_index.items():
        reconstructed = dict(row)
        for field in (
            "human_label",
            "human_annotation_count",
            "human_label_support_count",
            "human_unanimous",
        ):
            reconstructed.pop(field)
        reconstructed["schema_version"] = "jbspan-e0b-external-heldout-identity-v1"
        reconstructed["human_label_sealed"] = True
        if reconstructed != sealed_index[record_id]:
            raise ValueError("opened label row does not reconstruct its sealed identity")

    selection_roles = {
        str(row["record_id"]): str(row["evaluation_role"]) for row in selection
    }
    if set(selection_roles) != set(opened_index):
        raise ValueError("label opening and E0G-5 selection IDs differ")
    role_counts: dict[str, JsonObject] = {}
    for role in ("PRIMARY", "EXPOSED_STRESS"):
        selected = [row for row in heldout if selection_roles[str(row["record_id"])] == role]
        role_counts[role] = {
            "records": len(selected),
            "human_harmful": sum(row["human_label"] == "HARMFUL" for row in selected),
            "human_safe": sum(row["human_label"] == "SAFE" for row in selected),
            "human_unanimous": sum(bool(row["human_unanimous"]) for row in selected),
            "human_split_vote": sum(not bool(row["human_unanimous"]) for row in selected),
            "behavior_groups": len(
                {str(row["behavior_group_sha256"]) for row in selected}
            ),
        }
    expected_roles = required_mapping(commitment["expected_roles"], where="expected_roles")
    for role, expected in expected_roles.items():
        observed = role_counts[str(role)]
        for field, value in required_mapping(expected, where=f"expected_roles.{role}").items():
            if observed[field] != value:
                raise ValueError(f"opened label denominator mismatch: {role}.{field}")

    receipt: JsonObject = {
        "schema_version": "jbspan-e0g5-label-opening-receipt-v1",
        "status": "E0G5_PRECOMMITTED_LABELS_OPENED_AFTER_BOTH_AXES",
        "commitment_records": len(heldout),
        "commitment_bytes": len(payload),
        "commitment_sha256": hashlib.sha256(payload).hexdigest(),
        "axis_file_sha256s": dict(axis_sha256s),
        "role_denominators": role_counts,
        "source_denominators": {
            source: {
                "records": sum(row["source_id"] == source for row in heldout),
                "human_harmful": sum(
                    row["source_id"] == source and row["human_label"] == "HARMFUL"
                    for row in heldout
                ),
                "human_safe": sum(
                    row["source_id"] == source and row["human_label"] == "SAFE"
                    for row in heldout
                ),
            }
            for source in sorted({str(row["source_id"]) for row in heldout})
        },
        "per_record_human_labels_persisted": False,
        "raw_text_persisted": False,
        "heldout_labels_opened": True,
        "p3_opened": False,
        "topology_opened": False,
    }
    receipt["opening_identity_sha256"] = canonical_json_sha256(receipt)
    return heldout, receipt


def grouped_behavior_metrics(
    records: Sequence[Mapping[str, Any]], group_key: str
) -> dict[str, JsonObject]:
    output: dict[str, JsonObject] = {}
    for value in sorted({str(row[group_key]) for row in records}):
        selected = [row for row in records if str(row[group_key]) == value]
        output[value] = behavior_group_decision_metrics(
            [str(row["human_label"]) for row in selected],
            [str(row["panel_label"]) for row in selected],
            [str(row["behavior_group_sha256"]) for row in selected],
        )
    return output


def strata_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, JsonObject]:
    output: dict[str, JsonObject] = {}
    strata = sorted(
        {
            str(stratum)
            for row in records
            for stratum in row["strata"]
        }
    )
    for stratum in strata:
        selected = [row for row in records if stratum in row["strata"]]
        output[stratum] = classification_metrics(
            [str(row["human_label"]) for row in selected],
            [str(row["panel_label"]) for row in selected],
        )
    return output


def subset_metrics(
    records: Sequence[Mapping[str, Any]], *, bootstrap_spec: Mapping[str, Any], seed_suffix: str
) -> JsonObject:
    truth = [str(row["human_label"]) for row in records]
    panel_predictions = [str(row["panel_label"]) for row in records]
    qwen_predictions = [str(row["qwen_axis_label"]) for row in records]
    jailmeter_predictions = [str(row["jailmeter_axis_label"]) for row in records]
    sources = [str(row["source_id"]) for row in records]
    folds = [str(row["reporting_fold"]) for row in records]
    agreement = ["unanimous" if bool(row["human_unanimous"]) else "split_vote" for row in records]
    groups = [str(row["behavior_group_sha256"]) for row in records]
    metric_names = tuple(str(value) for value in bootstrap_spec["metrics"])
    bootstrap = behavior_cluster_bootstrap(
        truth,
        panel_predictions,
        groups,
        seed=f"{bootstrap_spec['seed']}|{seed_suffix}",
        replicates=int(bootstrap_spec["replicates"]),
        metric_names=metric_names,
    )
    return {
        "pooled_metrics": classification_metrics(truth, panel_predictions),
        "per_source_metrics": metrics_by_group(truth, panel_predictions, sources),
        "per_reporting_fold_metrics": metrics_by_group(truth, panel_predictions, folds),
        "per_agreement_metrics": metrics_by_group(truth, panel_predictions, agreement),
        "behavior_group_metrics": behavior_group_decision_metrics(
            truth, panel_predictions, groups
        ),
        "per_source_behavior_group_metrics": grouped_behavior_metrics(records, "source_id"),
        "behavior_cluster_bootstrap": bootstrap,
        "per_stratum_metrics": strata_metrics(records),
        "standalone_axis_metrics": {
            "qwen3guard": classification_metrics(truth, qwen_predictions),
            "jailmeter": classification_metrics(truth, jailmeter_predictions),
        },
        "axis_combination_counts": dict(
            sorted(
                Counter(
                    f"qwen={row['qwen_axis_label']}|jailmeter={row['jailmeter_axis_label']}"
                    for row in records
                ).items()
            )
        ),
    }


def parse_coverage(
    selection: Sequence[Mapping[str, Any]],
    axis: Mapping[str, Mapping[str, Any]],
    *,
    qwen: bool,
) -> JsonObject:
    def parsed(record_id: str) -> bool:
        row = axis[record_id]
        if qwen:
            return row.get("safety") is not None and row.get("refusal") is not None
        return row.get("label") is not None

    overall = sum(parsed(str(row["record_id"])) for row in selection) / len(selection)
    by_source = {
        source: (
            sum(
                parsed(str(row["record_id"]))
                for row in selection
                if row["source_id"] == source
            )
            / sum(row["source_id"] == source for row in selection)
        )
        for source in sorted({str(row["source_id"]) for row in selection})
    }
    return {"overall": overall, "by_source": by_source}


def build_primary_gate(
    *,
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    qwen_parse: Mapping[str, Any],
    jailmeter_parse: Mapping[str, Any],
    qwen_integrity: Mapping[str, Any],
    jailmeter_integrity: Mapping[str, Any],
) -> JsonObject:
    gate = required_mapping(config["primary_qualification_gate"], where="primary gate")
    pooled = required_mapping(metrics["pooled_metrics"], where="pooled metrics")
    per_source = required_mapping(metrics["per_source_metrics"], where="source metrics")
    per_fold = required_mapping(metrics["per_reporting_fold_metrics"], where="fold metrics")
    agreement = required_mapping(metrics["per_agreement_metrics"], where="agreement")
    behavior = required_mapping(metrics["behavior_group_metrics"], where="behavior metrics")
    per_source_behavior = required_mapping(
        metrics["per_source_behavior_group_metrics"], where="source behavior metrics"
    )
    bootstrap = required_mapping(metrics["behavior_cluster_bootstrap"], where="bootstrap")
    intervals = required_mapping(bootstrap["intervals"], where="bootstrap intervals")
    qwen_by_source = required_mapping(qwen_parse["by_source"], where="qwen parse sources")
    jailmeter_by_source = required_mapping(
        jailmeter_parse["by_source"], where="jailmeter parse sources"
    )
    checks = {
        "qwen_parse_coverage": float(qwen_parse["overall"])
        >= float(gate["axis_parse_coverage_min"]),
        "jailmeter_parse_coverage": float(jailmeter_parse["overall"])
        >= float(gate["axis_parse_coverage_min"]),
        "per_source_parse_coverage": all(
            float(value) >= float(gate["per_source_parse_coverage_min"])
            for value in list(qwen_by_source.values()) + list(jailmeter_by_source.values())
        ),
        "qwen_output_limit_stops": float(qwen_integrity["effective_fraction"])
        <= float(gate["output_limit_stop_fraction_max"]),
        "jailmeter_output_limit_stops": float(jailmeter_integrity["effective_fraction"])
        <= float(gate["output_limit_stop_fraction_max"]),
        "predicted_harmful_denominator": int(pooled["predicted_harmful"])
        >= int(gate["predicted_harmful_min"]),
        "predicted_safe_denominator": int(pooled["predicted_safe"])
        >= int(gate["predicted_safe_min"]),
        "harmful_precision": float(pooled["harmful_precision"])
        >= float(gate["harmful_precision_min"]),
        "harmful_precision_wilson": float(pooled["harmful_precision_wilson_95_lower"])
        >= float(gate["harmful_precision_wilson_95_lower_min"]),
        "safe_precision": float(pooled["safe_precision"])
        >= float(gate["safe_precision_min"]),
        "safe_precision_wilson": float(pooled["safe_precision_wilson_95_lower"])
        >= float(gate["safe_precision_wilson_95_lower_min"]),
        "harmful_recall": float(pooled["harmful_recall"])
        >= float(gate["harmful_recall_min"]),
        "safe_recall": float(pooled["safe_recall"]) >= float(gate["safe_recall_min"]),
        "decided_coverage": float(pooled["decided_coverage"])
        >= float(gate["decided_coverage_min"]),
        "decided_error_rate": float(pooled["decided_error_rate"])
        <= float(gate["decided_error_rate_max"]),
        "bootstrap_harmful_precision_lower": float(
            intervals["harmful_precision"]["lower_2_5"]
        )
        >= float(gate["behavior_cluster_bootstrap_harmful_precision_lower_min"]),
        "bootstrap_safe_precision_lower": float(intervals["safe_precision"]["lower_2_5"])
        >= float(gate["behavior_cluster_bootstrap_safe_precision_lower_min"]),
        "bootstrap_coverage_lower": float(intervals["decided_coverage"]["lower_2_5"])
        >= float(gate["behavior_cluster_bootstrap_decided_coverage_lower_min"]),
        "minimum_per_source_coverage": all(
            float(value["decided_coverage"]) >= float(gate["minimum_per_source_coverage"])
            for value in per_source.values()
        ),
        "minimum_per_source_harmful_recall": all(
            float(value["harmful_recall"])
            >= float(gate["minimum_per_source_harmful_recall"])
            for value in per_source.values()
        ),
        "minimum_per_source_safe_recall": all(
            float(value["safe_recall"]) >= float(gate["minimum_per_source_safe_recall"])
            for value in per_source.values()
        ),
        "maximum_per_source_error": all(
            float(value["decided_error_rate"])
            <= float(gate["maximum_per_source_decided_error_rate"])
            for value in per_source.values()
        ),
        "minimum_per_fold_coverage": all(
            float(value["decided_coverage"]) >= float(gate["minimum_per_fold_coverage"])
            for value in per_fold.values()
        ),
        "maximum_per_fold_error": all(
            float(value["decided_error_rate"])
            <= float(gate["maximum_per_fold_decided_error_rate"])
            for value in per_fold.values()
        ),
        "behavior_group_decision_coverage": float(
            behavior["behavior_group_decision_coverage"]
        )
        >= float(gate["behavior_group_decision_coverage_min"]),
        "per_source_behavior_group_decision_coverage": all(
            float(value["behavior_group_decision_coverage"])
            >= float(gate["minimum_per_source_behavior_group_decision_coverage"])
            for value in per_source_behavior.values()
        ),
        "maximum_unanimous_error": float(agreement["unanimous"]["decided_error_rate"])
        <= float(gate["maximum_unanimous_decided_error_rate"]),
    }
    return {"checks": checks, "passes_all": all(checks.values())}


def finalize(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_runtime = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    result_path = root / str(recording["result_path"])
    if result_path.exists():
        existing = load_object(result_path)
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing E0G-5 result belongs to another contract")
        return existing

    expected_records = int(config["heldout_pool"]["records"])
    qwen_path = root / str(recording["qwen_axis_path"])
    jailmeter_path = root / str(recording["jailmeter_axis_path"])
    qwen_summary = complete_axis_pair(
        root, qwen_path, root / str(recording["qwen_summary_path"]), expected_records
    )
    jailmeter_summary = complete_axis_pair(
        root,
        jailmeter_path,
        root / str(recording["jailmeter_summary_path"]),
        expected_records,
    )
    if qwen_summary is None or jailmeter_summary is None:
        raise ValueError("both immutable E0G-5 axes must exist before label opening")
    if qwen_summary.get("human_labels_opened") is not False or jailmeter_summary.get(
        "human_labels_opened"
    ) is not False:
        raise ValueError("an E0G-5 axis claims premature label opening")

    selection = load_jsonl(root / str(recording["selection_path"]))
    expected_ids = {str(row["record_id"]) for row in selection}
    qwen = axis_index(qwen_path, expected_ids)
    jailmeter = axis_index(jailmeter_path, expected_ids)
    axis_sha256s = {
        "qwen3guard": file_sha256(qwen_path),
        "jailmeter": file_sha256(jailmeter_path),
    }
    labels, receipt = open_committed_labels(root, config, selection, axis_sha256s)
    receipt_path = root / str(recording["label_opening_receipt_path"])
    safe_write(receipt_path, receipt)
    label_index = {str(row["record_id"]): row for row in labels}
    if set(label_index) != expected_ids:
        raise ValueError("opened label IDs differ from frozen E0G-5 selection")

    evaluated: list[JsonObject] = []
    for identity in selection:
        record_id = str(identity["record_id"])
        truth = label_index[record_id]
        qwen_row = qwen[record_id]
        jailmeter_row = jailmeter[record_id]
        qwen_label = qwen_axis_label(qwen_row.get("safety"), qwen_row.get("refusal"))
        jailmeter_value = jailmeter_row.get("label")
        jailmeter_label = (
            "HARMFUL"
            if jailmeter_value == 1
            else "SAFE"
            if jailmeter_value == 0
            else "ABSTAIN"
        )
        prediction = panel_label(
            safety=qwen_row.get("safety"),
            refusal=qwen_row.get("refusal"),
            jailmeter_label=jailmeter_value,
        )
        evaluated.append(
            {
                "record_id": record_id,
                "source_id": identity["source_id"],
                "evaluation_role": identity["evaluation_role"],
                "behavior_group_sha256": identity["behavior_group_sha256"],
                "reporting_fold": identity["reporting_fold"],
                "strata": identity["strata"],
                "human_label": truth["human_label"],
                "human_unanimous": truth["human_unanimous"],
                "qwen_axis_label": qwen_label,
                "jailmeter_axis_label": jailmeter_label,
                "panel_label": prediction,
            }
        )
    primary_records = [row for row in evaluated if row["evaluation_role"] == "PRIMARY"]
    stress_records = [
        row for row in evaluated if row["evaluation_role"] == "EXPOSED_STRESS"
    ]
    if len(primary_records) != 803 or len(stress_records) != 144:
        raise ValueError("E0G-5 primary/stress result denominators differ")
    analysis = required_mapping(config["analysis"], where="analysis")
    bootstrap_spec = required_mapping(analysis["bootstrap"], where="bootstrap")
    primary_metrics = subset_metrics(
        primary_records, bootstrap_spec=bootstrap_spec, seed_suffix="PRIMARY"
    )
    stress_metrics = subset_metrics(
        stress_records, bootstrap_spec=bootstrap_spec, seed_suffix="EXPOSED_STRESS"
    )

    primary_selection = [row for row in selection if row["evaluation_role"] == "PRIMARY"]
    stress_selection = [
        row for row in selection if row["evaluation_role"] == "EXPOSED_STRESS"
    ]
    primary_qwen_parse = parse_coverage(primary_selection, qwen, qwen=True)
    primary_jailmeter_parse = parse_coverage(primary_selection, jailmeter, qwen=False)
    stress_qwen_parse = parse_coverage(stress_selection, qwen, qwen=True)
    stress_jailmeter_parse = parse_coverage(stress_selection, jailmeter, qwen=False)
    qwen_runtime = required_mapping(parent_runtime["qwen3guard_runtime"], where="qwen runtime")
    jailmeter_runtime = required_mapping(
        parent_runtime["jailmeter_runtime"], where="jailmeter runtime"
    )
    primary_ids = {str(row["record_id"]) for row in primary_selection}
    stress_ids = {str(row["record_id"]) for row in stress_selection}
    primary_qwen_integrity = output_limit_integrity_summary(
        integrity_rows([qwen[record_id] for record_id in sorted(primary_ids)]),
        maximum_output_tokens=int(qwen_runtime["max_new_tokens"]),
    )
    primary_jailmeter_integrity = output_limit_integrity_summary(
        integrity_rows([jailmeter[record_id] for record_id in sorted(primary_ids)]),
        maximum_output_tokens=int(jailmeter_runtime["max_new_tokens"]),
    )
    stress_qwen_integrity = output_limit_integrity_summary(
        integrity_rows([qwen[record_id] for record_id in sorted(stress_ids)]),
        maximum_output_tokens=int(qwen_runtime["max_new_tokens"]),
    )
    stress_jailmeter_integrity = output_limit_integrity_summary(
        integrity_rows([jailmeter[record_id] for record_id in sorted(stress_ids)]),
        maximum_output_tokens=int(jailmeter_runtime["max_new_tokens"]),
    )
    if any(
        int(value["missing_output_token_count"]) != 0
        for value in (
            primary_qwen_integrity,
            primary_jailmeter_integrity,
            stress_qwen_integrity,
            stress_jailmeter_integrity,
        )
    ):
        raise ValueError("completed E0G-5 axis has missing output-token metadata")
    gate = build_primary_gate(
        config=config,
        metrics=primary_metrics,
        qwen_parse=primary_qwen_parse,
        jailmeter_parse=primary_jailmeter_parse,
        qwen_integrity=primary_qwen_integrity,
        jailmeter_integrity=primary_jailmeter_integrity,
    )
    passed = bool(gate["passes_all"])
    thresholds = required_mapping(
        config["primary_qualification_gate"], where="primary gate"
    )
    result: JsonObject = {
        "schema_version": "jbspan-e0g5-heterogeneous-panel-heldout-result-v1",
        "status": (
            "E0G5_PRIMARY_HELDOUT_QUALIFICATION_PASS"
            if passed
            else "E0G5_PRIMARY_HELDOUT_QUALIFICATION_FAIL"
        ),
        "evidence_class": "ONE_SHOT_BEHAVIOR_DISJOINT_PUBLIC_HELDOUT_EVALUATOR_QUALIFICATION",
        "contract_sha256": file_sha256(config_path),
        "selection_identity_sha256": load_object(
            root / str(recording["selection_manifest_path"])
        )["selection_identity_sha256"],
        "axis_identities": {
            "qwen3guard": qwen_summary["axis_identity_sha256"],
            "jailmeter": jailmeter_summary["axis_identity_sha256"],
        },
        "axis_file_sha256s": axis_sha256s,
        "label_opening_receipt_path": receipt_path.relative_to(root).as_posix(),
        "label_opening_receipt_sha256": file_sha256(receipt_path),
        "label_opening_identity_sha256": receipt["opening_identity_sha256"],
        "fixed_panel_rule": dict(config["fixed_panel_rule"]),
        "primary": {
            **primary_metrics,
            "axis_parse_coverage": {
                "qwen3guard": primary_qwen_parse,
                "jailmeter": primary_jailmeter_parse,
            },
            "axis_output_integrity": {
                "qwen3guard": primary_qwen_integrity,
                "jailmeter": primary_jailmeter_integrity,
            },
        },
        "exposed_jailbreakbench_stress": {
            **stress_metrics,
            "axis_parse_coverage": {
                "qwen3guard": stress_qwen_parse,
                "jailmeter": stress_jailmeter_parse,
            },
            "axis_output_integrity": {
                "qwen3guard": stress_qwen_integrity,
                "jailmeter": stress_jailmeter_integrity,
            },
            "influences_primary_pass_fail": False,
        },
        "primary_gate": gate,
        "interpretation": (
            thresholds["interpretation_on_pass"]
            if passed
            else thresholds["interpretation_on_fail"]
        ),
        "primary_panel_qualified_for_topology_candidate": passed,
        "heldout_labels_opened_after_both_axes": True,
        "per_record_human_labels_persisted": False,
        "new_human_annotation": False,
        "p3_opened": False,
        "topology_outcomes_opened": False,
        "paper_valid_topology_result": False,
        "raw_text_written": False,
        "raw_model_output_written": False,
        "next_operation": (
            config["next_operation_on_pass"]
            if passed
            else config["next_operation_on_fail"]
        ),
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(result_path, result)
    return result


def status(root: Path, config_path: Path) -> JsonObject:
    _config_path, config, _parent = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    total = int(config["heldout_pool"]["records"])

    def count(axis: str) -> tuple[int, str]:
        final_path = root / str(recording[f"{axis}_axis_path"])
        progress_path = root / str(recording[f"{axis}_progress_path"])
        if final_path.exists():
            return len(load_jsonl(final_path)), "COMPLETE"
        if progress_path.exists():
            return len(load_jsonl(progress_path)), "IN_PROGRESS"
        return 0, "NOT_STARTED"

    qwen_count, qwen_status = count("qwen")
    jailmeter_count, jailmeter_status = count("jailmeter")
    return {
        "status": "E0G5_PROGRESS_STATUS",
        "records_total": total,
        "qwen": {
            "status": qwen_status,
            "records": qwen_count,
            "remaining": total - qwen_count,
            "estimated_remaining_seconds_at_e0g4_mean": (total - qwen_count)
            * 0.6311625780456838,
        },
        "jailmeter": {
            "status": jailmeter_status,
            "records": jailmeter_count,
            "remaining": total - jailmeter_count,
            "estimated_remaining_seconds_at_e0g4_mean": (total - jailmeter_count)
            * 8.347824583473797,
        },
        "label_opened": (root / str(recording["label_opening_receipt_path"])).exists(),
        "result_exists": (root / str(recording["result_path"])).exists(),
        "raw_text_read": False,
        "model_invoked": False,
    }


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    if args.command == "freeze":
        result = freeze_selection(root, args.config)
    elif args.command == "preflight":
        result = preflight(root, args.config)
    elif args.command == "status":
        result = status(root, args.config)
    elif args.command == "qwen":
        result = run_qwen(root, args.config)
    elif args.command == "jailmeter":
        result = run_jailmeter(root, args.config)
    else:
        result = finalize(root, args.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "identity": result.get("result_identity_sha256")
                or result.get("axis_identity_sha256")
                or result.get("preflight_identity_sha256")
                or result.get("selection_identity_sha256"),
                "qwen": result.get("qwen"),
                "jailmeter": result.get("jailmeter"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
