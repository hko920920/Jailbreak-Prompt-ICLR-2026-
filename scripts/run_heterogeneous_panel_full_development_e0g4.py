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

from jbspan.evaluator_abstaining_panel import (
    metrics_by_group,
    panel_label,
    qwen_axis_label,
)
from jbspan.evaluator_cpu_router import classification_metrics
from jbspan.evaluator_full_calibration import (
    behavior_cluster_bootstrap,
    behavior_group_decision_metrics,
    deterministic_execution_order,
)
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
        default=Path(
            "configs/evaluator_panel/heterogeneous_panel_full_development_e0g4_v1.json"
        ),
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


def safe_write(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite different frozen output: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
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
    """Atomically replace the mutable, metadata-only progress checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encode_jsonl(rows))
    temporary.replace(path)


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def verify_file(path: Path, *, bytes_: object, sha256: object) -> None:
    if not path.is_file() or path.stat().st_size != int(str(bytes_)):
        raise ValueError(f"file size mismatch: {path}")
    if file_sha256(path) != str(sha256):
        raise ValueError(f"file SHA-256 mismatch: {path}")


def repo_module(root: Path, name: str) -> Any:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return importlib.import_module(name)


def verify_status_identity(
    path: Path,
    spec: Mapping[str, Any],
    *,
    status_key: str,
    identity_key: str,
) -> JsonObject:
    value = load_object(path)
    if (
        value.get("status") != spec[status_key]
        or value.get(identity_key) != spec["required_identity"]
    ):
        raise ValueError(f"status/identity mismatch: {path}")
    return value


def load_config(root: Path, config_path: Path) -> tuple[Path, JsonObject, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_object(config_path)
    if config.get("schema_version") != "jbspan-e0g4-heterogeneous-panel-full-development-v1":
        raise ValueError("unsupported E0G-4 contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-4 must remain frozen and non-paper-valid")
    protected = required_mapping(config["protected_boundaries"], where="protected_boundaries")
    if any(protected.values()):
        raise ValueError("E0G-4 protected boundaries must remain false")

    parent = required_mapping(config["fixed_parent_sentinel"], where="fixed_parent_sentinel")
    for prefix in ("contract", "result"):
        verify_file(
            root / str(parent[f"{prefix}_path"]),
            bytes_=parent[f"{prefix}_bytes"],
            sha256=parent[f"{prefix}_sha256"],
        )
    verify_status_identity(
        root / str(parent["result_path"]),
        parent,
        status_key="required_status",
        identity_key="result_identity_sha256",
    )
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    _, parent_config = sentinel.load_config(root, root / str(parent["contract_path"]))
    fixed_rule = dict(required_mapping(config["fixed_panel_rule"], where="fixed_panel_rule"))
    fixed_rule.pop("changed_after_e0g2", None)
    if fixed_rule != dict(parent_config["panel_rule"]):
        raise ValueError("E0G-4 panel rule differs from the frozen E0G-2 rule")

    parallel = required_mapping(config["parallel_probe"], where="parallel_probe")
    verify_file(
        root / str(parallel["result_path"]),
        bytes_=parallel["result_bytes"],
        sha256=parallel["result_sha256"],
    )
    parallel_result = verify_status_identity(
        root / str(parallel["result_path"]),
        parallel,
        status_key="required_status",
        identity_key="result_identity_sha256",
    )
    if parallel_result.get("parallel_execution_adopted") is not False:
        raise ValueError("E0G-4 cannot adopt the failed parallel execution route")

    pool = required_mapping(config["development_pool"], where="development_pool")
    for prefix in ("router_contract", "labels", "folds"):
        verify_file(
            root / str(pool[f"{prefix}_path"]),
            bytes_=pool[f"{prefix}_bytes"],
            sha256=pool[f"{prefix}_sha256"],
        )
    cache = required_mapping(config["cache_adoption"], where="cache_adoption")
    for axis in ("qwen", "jailmeter"):
        for suffix in ("axis", "summary"):
            prefix = f"{axis}_{suffix}"
            verify_file(
                root / str(cache[f"{prefix}_path"]),
                bytes_=cache[f"{prefix}_bytes"],
                sha256=cache[f"{prefix}_sha256"],
            )
        summary = load_object(root / str(cache[f"{axis}_summary_path"]))
        if summary.get("axis_identity_sha256") != cache[f"{axis}_axis_identity"]:
            raise ValueError(f"E0G-4 {axis} cache identity mismatch")
    return config_path, config, parent_config


def freeze_selection(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    selection_path = root / str(recording["selection_path"])
    manifest_path = root / str(recording["selection_manifest_path"])
    if selection_path.exists() or manifest_path.exists():
        if not selection_path.exists() or not manifest_path.exists():
            raise ValueError("partial E0G-4 frozen selection exists")
        existing_manifest = load_object(manifest_path)
        if (
            existing_manifest.get("contract_sha256") != file_sha256(config_path)
            or existing_manifest.get("selection_file_sha256") != file_sha256(selection_path)
        ):
            raise ValueError("existing E0G-4 selection identity mismatch")
        return existing_manifest

    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    metadata = sentinel.development_metadata(root, parent_config)
    order = required_mapping(config["execution_order"], where="execution_order")
    ordered = deterministic_execution_order(metadata, seed=str(order["seed"]))
    output_fields = (
        "record_id",
        "source_id",
        "human_label",
        "human_unanimous",
        "behavior_group_sha256",
        "response_sha256",
        "outer_fold",
        "execution_score",
        "execution_order",
    )
    safe_rows = [{field: row[field] for field in output_fields} for row in ordered]
    pool = required_mapping(config["development_pool"], where="development_pool")
    if len(safe_rows) != int(pool["records"]):
        raise ValueError("E0G-4 selection denominator mismatch")
    safe_write_jsonl(selection_path, safe_rows)
    source_counts = Counter(str(row["source_id"]) for row in safe_rows)
    group_counts = Counter(str(row["source_id"]) for row in safe_rows)
    source_group_counts = {
        source: len(
            {
                str(row["behavior_group_sha256"])
                for row in safe_rows
                if row["source_id"] == source
            }
        )
        for source in sorted(source_counts)
    }
    if set(group_counts) != set(source_counts):
        raise AssertionError("unreachable source-count inconsistency")
    manifest: JsonObject = {
        "schema_version": "jbspan-e0g4-full-development-selection-manifest-v1",
        "status": "E0G4_FULL_DEVELOPMENT_SELECTION_FROZEN",
        "contract_sha256": file_sha256(config_path),
        "selection_file": selection_path.relative_to(root).as_posix(),
        "selection_file_bytes": selection_path.stat().st_size,
        "selection_file_sha256": file_sha256(selection_path),
        "truth_commitment_sha256": canonical_json_sha256(
            [
                {"record_id": row["record_id"], "human_label": row["human_label"]}
                for row in safe_rows
            ]
        ),
        "record_count": len(safe_rows),
        "human_harmful": sum(row["human_label"] == "HARMFUL" for row in safe_rows),
        "human_safe": sum(row["human_label"] == "SAFE" for row in safe_rows),
        "human_unanimous": sum(bool(row["human_unanimous"]) for row in safe_rows),
        "human_split_vote": sum(not bool(row["human_unanimous"]) for row in safe_rows),
        "behavior_groups": len({str(row["behavior_group_sha256"]) for row in safe_rows}),
        "source_record_counts": dict(sorted(source_counts.items())),
        "source_behavior_group_counts": source_group_counts,
        "model_output_observed": False,
        "raw_text_read": False,
        "raw_text_written": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    manifest["selection_identity_sha256"] = canonical_json_sha256(manifest)
    safe_write(manifest_path, manifest)
    return manifest


def reconstruct_ordered_records(
    root: Path, config: Mapping[str, Any]
) -> tuple[list[Any], JsonObject]:
    pool = required_mapping(config["development_pool"], where="development_pool")
    router = load_object(root / str(pool["router_contract_path"]))
    audit = repo_module(root, "scripts.audit_evaluator_cpu_learned_router_e0g0")
    records, reconstruction = audit.reconstruct_records(root, router)
    recording = required_mapping(config["recording"], where="recording")
    selection = load_jsonl(root / str(recording["selection_path"]))
    index = {str(record.record_id): record for record in records}
    ordered: list[Any] = []
    for row in selection:
        record = index.get(str(row["record_id"]))
        if record is None:
            raise ValueError("E0G-4 frozen record could not be reconstructed")
        if (
            record.behavior_group_sha256 != row["behavior_group_sha256"]
            or hashlib.sha256(record.response_text.encode()).hexdigest() != row["response_sha256"]
            or record.human_label != row["human_label"]
            or record.outer_fold != row["outer_fold"]
        ):
            raise ValueError("E0G-4 reconstructed record identity mismatch")
        ordered.append(record)
    return ordered, reconstruction


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
        raise RuntimeError("could not query frozen E0G-4 GPU identity")
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
    expected = dict(required_mapping(runtime["device_continuity"], where="device_continuity"))
    expected.pop("rule", None)
    observed = gpu_identity()
    if observed != expected:
        raise RuntimeError(f"E0G-4 GPU identity changed: observed={observed}")
    return observed


def qwen_prompt(tokenizer: Any, record: Any) -> JsonObject:
    rendered = tokenizer.apply_chat_template(
        [
            {"role": "user", "content": record.goal_text},
            {"role": "assistant", "content": record.response_text},
        ],
        tokenize=False,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("Qwen3Guard tokenizer returned an invalid E0G-4 prompt")
    return {
        "record_id": record.record_id,
        "prompt": rendered,
        "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_tokens": len(tokenizer.encode(rendered, add_special_tokens=False)),
    }


def jailmeter_prompt(tokenizer: Any, system_prompt: str, record: Any) -> JsonObject:
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
        raise ValueError("JailMeter tokenizer returned an invalid E0G-4 prompt")
    return {
        "record_id": record.record_id,
        "prompt": rendered,
        "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_tokens": len(tokenizer.encode(rendered, add_special_tokens=False)),
    }


def validate_cache_inputs(
    cache_rows: Sequence[Mapping[str, Any]], prompt_index: Mapping[str, Mapping[str, Any]]
) -> None:
    if len(cache_rows) != 60 or len({str(row["record_id"]) for row in cache_rows}) != 60:
        raise ValueError("E0G-4 cache denominator/uniqueness mismatch")
    for row in cache_rows:
        prompt = prompt_index.get(str(row["record_id"]))
        if prompt is None:
            raise ValueError("E0G-4 cache row is not in the full development pool")
        if (
            prompt["input_sha256"] != row["input_sha256"]
            or prompt["input_tokens"] != row["input_tokens"]
        ):
            raise ValueError("E0G-4 cached input differs from exact reconstruction")


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    selection_manifest = freeze_selection(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["preflight_path"])
    if output_path.exists():
        existing_preflight = load_object(output_path)
        if existing_preflight.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing E0G-4 preflight belongs to another contract")
        return existing_preflight

    observed_gpu = verify_gpu_identity(config)
    records, reconstruction = reconstruct_ordered_records(root, config)
    cache = required_mapping(config["cache_adoption"], where="cache_adoption")
    axes = required_mapping(parent_config["qualified_axes"], where="qualified_axes")

    qwen = repo_module(root, "scripts.qualify_qwen3guard_runtime_e0g1a")
    qwen_axis = required_mapping(axes["qwen3guard"], where="qwen3guard axis")
    _, qwen_config = qwen.resolve_config(root, root / str(qwen_axis["contract_path"]))
    qwen_files, qwen_bytes = qwen.verify_model_files(root, qwen_config)
    from transformers import AutoTokenizer

    qwen_runtime = required_mapping(
        parent_config["qwen3guard_runtime"], where="qwen3guard_runtime"
    )
    qwen_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(qwen_runtime["model_local_path"]), local_files_only=True
    )
    qwen_cached = load_jsonl(root / str(cache["qwen_axis_path"]))
    qwen_cached_ids = {str(row["record_id"]) for row in qwen_cached}
    qwen_prompts = {
        str(record.record_id): qwen_prompt(qwen_tokenizer, record)
        for record in records
        if str(record.record_id) in qwen_cached_ids
    }
    validate_cache_inputs(qwen_cached, qwen_prompts)

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
        parent_config["jailmeter_runtime"], where="jailmeter_runtime"
    )
    jailmeter_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(jailmeter_runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    system_prompt = sentinel.extract_system_prompt(root / str(jailmeter_runtime["runner_path"]))
    jailmeter_cached = load_jsonl(root / str(cache["jailmeter_axis_path"]))
    jailmeter_cached_ids = {str(row["record_id"]) for row in jailmeter_cached}
    jailmeter_prompts = {
        str(record.record_id): jailmeter_prompt(jailmeter_tokenizer, system_prompt, record)
        for record in records
        if str(record.record_id) in jailmeter_cached_ids
    }
    validate_cache_inputs(jailmeter_cached, jailmeter_prompts)

    result: JsonObject = {
        "schema_version": "jbspan-e0g4-full-development-preflight-v1",
        "status": "E0G4_FULL_DEVELOPMENT_PREFLIGHT_PASS",
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
        "qwen_cache_records_verified": len(qwen_cached),
        "jailmeter_source_files_verified": len(source_rows),
        "jailmeter_target_files_verified": len(target_rows),
        "jailmeter_runtime_identity": runtime_identity,
        "jailmeter_conversion_identity_sha256": conversion["conversion_identity_sha256"],
        "jailmeter_cache_records_verified": len(jailmeter_cached),
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "parallel_slots": 1,
        "raw_text_read_in_memory": True,
        "raw_text_written": False,
        "new_full_model_output_observed": False,
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
    cache_rows: Sequence[Mapping[str, Any]],
    cache_origin: str,
    prompt_index: Mapping[str, Mapping[str, Any]],
    order_index: Mapping[str, int],
) -> list[JsonObject]:
    if progress_path.exists():
        rows = load_jsonl(progress_path)
    else:
        validate_cache_inputs(cache_rows, prompt_index)
        rows = [
            {
                **dict(row),
                "execution_order": order_index[str(row["record_id"])],
                "cache_origin": cache_origin,
            }
            for row in cache_rows
        ]
        rows.sort(key=lambda row: int(row["execution_order"]))
        checkpoint_jsonl(progress_path, rows)
    ids = [str(row["record_id"]) for row in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(order_index):
        raise ValueError("E0G-4 progress IDs are duplicated or outside the frozen pool")
    for row in rows:
        record_id = str(row["record_id"])
        prompt = prompt_index[record_id]
        if (
            row.get("execution_order") != order_index[record_id]
            or row.get("input_sha256") != prompt["input_sha256"]
            or row.get("input_tokens") != prompt["input_tokens"]
            or "prompt" in row
            or "content" in row
        ):
            raise ValueError("E0G-4 progress row failed identity/safety validation")
    return sorted(rows, key=lambda row: int(row["execution_order"]))


def complete_axis_pair(
    root: Path,
    axis_path: Path,
    summary_path: Path,
    expected_records: int,
) -> JsonObject | None:
    if not axis_path.exists() and not summary_path.exists():
        return None
    if not axis_path.exists() or not summary_path.exists():
        raise ValueError("partial E0G-4 final axis pair exists")
    summary = load_object(summary_path)
    if (
        summary.get("record_count") != expected_records
        or summary.get("axis_file_sha256") != file_sha256(axis_path)
    ):
        raise ValueError("E0G-4 final axis identity mismatch")
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


def run_qwen(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    verify_gpu_identity(config)
    recording = required_mapping(config["recording"], where="recording")
    pool = required_mapping(config["development_pool"], where="development_pool")
    expected_records = int(pool["records"])
    progress_path = root / str(recording["qwen_progress_path"])
    axis_path = root / str(recording["qwen_axis_path"])
    summary_path = root / str(recording["qwen_summary_path"])
    completed = complete_axis_pair(root, axis_path, summary_path, expected_records)
    if completed is not None:
        return completed

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("E0G-4 Qwen3Guard requires CUDA")
    runtime = required_mapping(parent_config["qwen3guard_runtime"], where="qwen3guard_runtime")
    full_runtime = required_mapping(config["runtime"]["qwen3guard"], where="full qwen runtime")
    records, _ = reconstruct_ordered_records(root, config)
    model_path = root / str(runtime["model_local_path"])
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        model_path, local_files_only=True
    )
    prompt_rows = [qwen_prompt(tokenizer, record) for record in records]
    prompt_index = {str(row["record_id"]): row for row in prompt_rows}
    order_index = execution_order_index(root, config)
    cache = required_mapping(config["cache_adoption"], where="cache_adoption")
    cached_rows = load_jsonl(root / str(cache["qwen_axis_path"]))
    rows = prepare_progress(
        progress_path=progress_path,
        cache_rows=cached_rows,
        cache_origin="E0G2_EXACT_SENTINEL_AXIS",
        prompt_index=prompt_index,
        order_index=order_index,
    )
    completed_ids = {str(row["record_id"]) for row in rows}
    new_records = [record for record in records if str(record.record_id) not in completed_ids]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch.cuda.init()  # type: ignore[no-untyped-call]
    torch.cuda.set_device(0)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    started = time.perf_counter()
    model_load_seconds = 0.0
    if new_records:
        load_started = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.float16,
            local_files_only=True,
            low_cpu_mem_usage=True,
        ).to(torch.device("cuda:0"))  # type: ignore[arg-type]
        model.eval()
        model_load_seconds = time.perf_counter() - load_started
        sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
        for record in new_records:
            prompt = prompt_index[str(record.record_id)]
            encoded = tokenizer([prompt["prompt"]], return_tensors="pt").to(
                torch.device("cuda:0")
            )
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
            rows.append(
                {
                    "record_id": record.record_id,
                    "execution_order": order_index[str(record.record_id)],
                    "cache_origin": "E0G4_NEW_SEQUENTIAL",
                    "input_sha256": prompt["input_sha256"],
                    "input_tokens": int(encoded.input_ids.shape[1]),
                    "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "output_characters": len(content),
                    "output_tokens": len(output_ids),
                    "output_limit_stop": len(output_ids) >= int(runtime["max_new_tokens"]),
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
                raise TimeoutError("E0G-4 Qwen3Guard run exceeded its per-invocation budget")
    total_seconds = time.perf_counter() - started
    if len(rows) != expected_records:
        raise RuntimeError("E0G-4 Qwen3Guard progress denominator is incomplete")
    parsed_count = sum(row["safety"] is not None and row["refusal"] is not None for row in rows)
    summary: JsonObject = {
        "schema_version": "jbspan-e0g4-qwen-axis-summary-v1",
        "status": "E0G4_QWEN3GUARD_FULL_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "cache_records": sum(row["cache_origin"] == "E0G2_EXACT_SENTINEL_AXIS" for row in rows),
        "new_records": sum(row["cache_origin"] == "E0G4_NEW_SEQUENTIAL" for row in rows),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
        "model_load_seconds_this_invocation": model_load_seconds,
        "total_seconds_this_invocation": total_seconds,
        "sum_per_record_inference_seconds": sum(float(row["inference_seconds"]) for row in rows),
        "peak_cuda_allocated_bytes_this_invocation": torch.cuda.max_memory_allocated(0),
        "safety_counts": dict(Counter(str(row["safety"]) for row in rows)),
        "refusal_counts": dict(Counter(str(row["refusal"]) for row in rows)),
        "resume_checkpoint_used": len(completed_ids) > len(cached_rows),
        "progress_checkpoint_retained": False,
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


def run_jailmeter(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    verify_gpu_identity(config)
    recording = required_mapping(config["recording"], where="recording")
    pool = required_mapping(config["development_pool"], where="development_pool")
    expected_records = int(pool["records"])
    progress_path = root / str(recording["jailmeter_progress_path"])
    axis_path = root / str(recording["jailmeter_axis_path"])
    summary_path = root / str(recording["jailmeter_summary_path"])
    completed = complete_axis_pair(root, axis_path, summary_path, expected_records)
    if completed is not None:
        return completed

    from transformers import AutoTokenizer

    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    runtime = required_mapping(parent_config["jailmeter_runtime"], where="jailmeter_runtime")
    full_runtime = required_mapping(config["runtime"]["jailmeter"], where="full jailmeter runtime")
    records, _ = reconstruct_ordered_records(root, config)
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    system_prompt = sentinel.extract_system_prompt(root / str(runtime["runner_path"]))
    prompt_rows = [jailmeter_prompt(tokenizer, system_prompt, record) for record in records]
    prompt_index = {str(row["record_id"]): row for row in prompt_rows}
    order_index = execution_order_index(root, config)
    cache = required_mapping(config["cache_adoption"], where="cache_adoption")
    cached_rows = load_jsonl(root / str(cache["jailmeter_axis_path"]))
    rows = prepare_progress(
        progress_path=progress_path,
        cache_rows=cached_rows,
        cache_origin="E0G2_EXACT_SENTINEL_AXIS",
        prompt_index=prompt_index,
        order_index=order_index,
    )
    completed_ids = {str(row["record_id"]) for row in rows}
    new_records = [record for record in records if str(record.record_id) not in completed_ids]
    if not new_records:
        raise RuntimeError("unexpected complete JailMeter progress without final axis")

    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(
        full_runtime["maximum_prelaunch_gpu_memory_mib"]
    ):
        raise RuntimeError(f"E0G-4 JailMeter GPU baseline is uncontrolled: {baseline_gpu} MiB")
    host = str(runtime["host"])
    port = int(runtime["port"])
    if not sentinel.port_is_free(host, port):
        raise ValueError(f"E0G-4 JailMeter port is occupied: {host}:{port}")
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
    log_handle = tempfile.NamedTemporaryFile(prefix="e0g4-jailmeter-", suffix=".log", delete=False)
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
            raise TimeoutError("E0G-4 JailMeter server health timeout")
        for record in new_records:
            prompt = prompt_index[str(record.record_id)]
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
                raise ValueError("E0G-4 JailMeter endpoint returned no text")
            parsed = sentinel.parse_jailmeter_label(content, runtime)
            predicted = response.get("tokens_predicted")
            rows.append(
                {
                    "record_id": record.record_id,
                    "execution_order": order_index[str(record.record_id)],
                    "cache_origin": "E0G4_NEW_SEQUENTIAL",
                    "input_sha256": prompt["input_sha256"],
                    "input_tokens": prompt["input_tokens"],
                    "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "output_characters": len(content),
                    "output_tokens": predicted if isinstance(predicted, int) else None,
                    "output_limit_stop": bool(response.get("stopped_limit", False)),
                    "label": parsed["label"],
                    "label_match_count": parsed["match_count"],
                    "inference_seconds": time.perf_counter() - call_started,
                }
            )
            rows.sort(key=lambda row: int(row["execution_order"]))
            checkpoint_jsonl(progress_path, rows)
            if time.perf_counter() - started > float(full_runtime["maximum_total_seconds"]):
                raise TimeoutError("E0G-4 JailMeter run exceeded its per-invocation budget")
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
        raise RuntimeError("E0G-4 JailMeter progress denominator is incomplete")
    peak_gpu = max(gpu_samples) if gpu_samples else None
    if peak_gpu is None or peak_gpu > float(full_runtime["maximum_peak_gpu_memory_mib"]):
        raise RuntimeError(f"E0G-4 JailMeter peak GPU budget failed: {peak_gpu} MiB")
    parsed_count = sum(row["label"] is not None for row in rows)
    summary: JsonObject = {
        "schema_version": "jbspan-e0g4-jailmeter-axis-summary-v1",
        "status": "E0G4_JAILMETER_FULL_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "cache_records": sum(row["cache_origin"] == "E0G2_EXACT_SENTINEL_AXIS" for row in rows),
        "new_records": sum(row["cache_origin"] == "E0G4_NEW_SEQUENTIAL" for row in rows),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
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
        "resume_checkpoint_used": len(completed_ids) > len(cached_rows),
        "progress_checkpoint_retained": False,
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
        raise ValueError(f"E0G-4 axis keys differ from frozen selection: {path}")
    return index


def grouped_behavior_metrics(
    records: Sequence[Mapping[str, Any]], group_key: str
) -> dict[str, JsonObject]:
    values = sorted({str(row[group_key]) for row in records})
    output: dict[str, JsonObject] = {}
    for value in values:
        selected = [row for row in records if str(row[group_key]) == value]
        output[value] = behavior_group_decision_metrics(
            [str(row["human_label"]) for row in selected],
            [str(row["panel_label"]) for row in selected],
            [str(row["behavior_group_sha256"]) for row in selected],
        )
    return output


def per_source_parse(
    selection: Sequence[Mapping[str, Any]], axis: Mapping[str, Mapping[str, Any]], axis_name: str
) -> dict[str, float]:
    output: dict[str, float] = {}
    for source in sorted({str(row["source_id"]) for row in selection}):
        ids = [str(row["record_id"]) for row in selection if row["source_id"] == source]
        if axis_name == "qwen":
            parsed = sum(
                axis[record_id].get("safety") is not None
                and axis[record_id].get("refusal") is not None
                for record_id in ids
            )
        else:
            parsed = sum(axis[record_id].get("label") is not None for record_id in ids)
        output[source] = parsed / len(ids)
    return output


def finalize(root: Path, config_path: Path) -> JsonObject:
    config_path, config, _parent_config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    result_path = root / str(recording["result_path"])
    if result_path.exists():
        existing_result = load_object(result_path)
        if existing_result.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing E0G-4 result belongs to another contract")
        return existing_result
    pool = required_mapping(config["development_pool"], where="development_pool")
    expected_records = int(pool["records"])
    qwen_summary = complete_axis_pair(
        root,
        root / str(recording["qwen_axis_path"]),
        root / str(recording["qwen_summary_path"]),
        expected_records,
    )
    jailmeter_summary = complete_axis_pair(
        root,
        root / str(recording["jailmeter_axis_path"]),
        root / str(recording["jailmeter_summary_path"]),
        expected_records,
    )
    if qwen_summary is None or jailmeter_summary is None:
        raise ValueError("both E0G-4 axes must be complete before finalization")
    selection = load_jsonl(root / str(recording["selection_path"]))
    expected_ids = {str(row["record_id"]) for row in selection}
    qwen = axis_index(root / str(recording["qwen_axis_path"]), expected_ids)
    jailmeter = axis_index(root / str(recording["jailmeter_axis_path"]), expected_ids)
    records: list[JsonObject] = []
    for truth_row in selection:
        record_id = str(truth_row["record_id"])
        qwen_row = qwen[record_id]
        jailmeter_row = jailmeter[record_id]
        qwen_label = qwen_axis_label(qwen_row.get("safety"), qwen_row.get("refusal"))
        jailmeter_value = jailmeter_row.get("label")
        jailmeter_label = (
            "HARMFUL" if jailmeter_value == 1 else "SAFE" if jailmeter_value == 0 else "ABSTAIN"
        )
        prediction = panel_label(
            safety=qwen_row.get("safety"),
            refusal=qwen_row.get("refusal"),
            jailmeter_label=jailmeter_value,
        )
        records.append(
            {
                "record_id": record_id,
                "source_id": truth_row["source_id"],
                "behavior_group_sha256": truth_row["behavior_group_sha256"],
                "outer_fold": truth_row["outer_fold"],
                "human_label": truth_row["human_label"],
                "human_unanimous": truth_row["human_unanimous"],
                "qwen_safety": qwen_row.get("safety"),
                "qwen_refusal": qwen_row.get("refusal"),
                "qwen_axis_label": qwen_label,
                "jailmeter_axis_label": jailmeter_label,
                "panel_label": prediction,
                "panel_correct_if_decided": (
                    prediction == truth_row["human_label"] if prediction != "ABSTAIN" else None
                ),
            }
        )
    truth = [str(row["human_label"]) for row in records]
    panel_predictions = [str(row["panel_label"]) for row in records]
    qwen_predictions = [str(row["qwen_axis_label"]) for row in records]
    jailmeter_predictions = [str(row["jailmeter_axis_label"]) for row in records]
    sources = [str(row["source_id"]) for row in records]
    folds = [str(row["outer_fold"]) for row in records]
    agreement = ["unanimous" if bool(row["human_unanimous"]) else "split_vote" for row in records]
    groups = [str(row["behavior_group_sha256"]) for row in records]
    pooled = classification_metrics(truth, panel_predictions)
    per_source = metrics_by_group(truth, panel_predictions, sources)
    per_fold = metrics_by_group(truth, panel_predictions, folds)
    per_agreement = metrics_by_group(truth, panel_predictions, agreement)
    behavior_metrics = behavior_group_decision_metrics(truth, panel_predictions, groups)
    per_source_behavior = grouped_behavior_metrics(records, "source_id")
    uncertainty = required_mapping(config["uncertainty"], where="uncertainty")
    metric_names = tuple(str(value) for value in uncertainty["metrics"])
    bootstrap = behavior_cluster_bootstrap(
        truth,
        panel_predictions,
        groups,
        seed=str(uncertainty["seed"]),
        replicates=int(uncertainty["replicates"]),
        metric_names=metric_names,
    )
    per_source_bootstrap = {
        source: behavior_cluster_bootstrap(
            [truth[index] for index, value in enumerate(sources) if value == source],
            [panel_predictions[index] for index, value in enumerate(sources) if value == source],
            [groups[index] for index, value in enumerate(sources) if value == source],
            seed=f"{uncertainty['seed']}|{source}",
            replicates=int(uncertainty["replicates"]),
            metric_names=metric_names,
        )
        for source in sorted(set(sources))
    }
    qwen_parse_source = per_source_parse(selection, qwen, "qwen")
    jailmeter_parse_source = per_source_parse(selection, jailmeter, "jailmeter")
    gate = required_mapping(config["qualification_gate"], where="qualification_gate")
    intervals = required_mapping(bootstrap["intervals"], where="bootstrap intervals")
    checks = {
        "qwen_parse_coverage": float(qwen_summary["parse_coverage"])
        >= float(gate["qwen_parse_coverage_min"]),
        "jailmeter_parse_coverage": float(jailmeter_summary["parse_coverage"])
        >= float(gate["jailmeter_parse_coverage_min"]),
        "per_source_parse_coverage": all(
            value >= float(gate["per_source_parse_coverage_min"])
            for value in list(qwen_parse_source.values()) + list(jailmeter_parse_source.values())
        ),
        "qwen_output_limit_stops": int(qwen_summary["output_limit_stops"]) / expected_records
        <= float(gate["output_limit_stop_fraction_max"]),
        "jailmeter_output_limit_stops": int(jailmeter_summary["output_limit_stops"])
        / expected_records
        <= float(gate["output_limit_stop_fraction_max"]),
        "panel_decided_coverage": float(pooled["decided_coverage"])
        >= float(gate["panel_decided_coverage_min"]),
        "predicted_harmful_denominator": int(pooled["predicted_harmful"])
        >= int(gate["predicted_harmful_min"]),
        "predicted_safe_denominator": int(pooled["predicted_safe"])
        >= int(gate["predicted_safe_min"]),
        "harmful_precision": float(pooled["harmful_precision"])
        >= float(gate["harmful_precision_min"]),
        "harmful_precision_wilson": float(pooled["harmful_precision_wilson_95_lower"])
        >= float(gate["harmful_precision_wilson_95_lower_min"]),
        "safe_precision": float(pooled["safe_precision"]) >= float(gate["safe_precision_min"]),
        "safe_precision_wilson": float(pooled["safe_precision_wilson_95_lower"])
        >= float(gate["safe_precision_wilson_95_lower_min"]),
        "harmful_recall": float(pooled["harmful_recall"]) >= float(gate["harmful_recall_min"]),
        "safe_recall": float(pooled["safe_recall"]) >= float(gate["safe_recall_min"]),
        "decided_error_rate": float(pooled["decided_error_rate"])
        <= float(gate["decided_error_rate_max"]),
        "cluster_bootstrap_harmful_precision_lower": float(
            intervals["harmful_precision"]["lower_2_5"]
        )
        >= float(gate["behavior_cluster_bootstrap_harmful_precision_lower_min"]),
        "cluster_bootstrap_safe_precision_lower": float(
            intervals["safe_precision"]["lower_2_5"]
        )
        >= float(gate["behavior_cluster_bootstrap_safe_precision_lower_min"]),
        "cluster_bootstrap_coverage_lower": float(
            intervals["decided_coverage"]["lower_2_5"]
        )
        >= float(gate["behavior_cluster_bootstrap_decided_coverage_lower_min"]),
        "minimum_per_source_coverage": all(
            float(value["decided_coverage"])
            >= float(gate["minimum_per_source_decided_coverage"])
            for value in per_source.values()
        ),
        "minimum_per_source_harmful_recall": all(
            float(value["harmful_recall"]) >= float(gate["minimum_per_source_harmful_recall"])
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
        "maximum_unanimous_error": float(per_agreement["unanimous"]["decided_error_rate"])
        <= float(gate["maximum_unanimous_decided_error_rate"]),
        "behavior_group_decision_coverage": float(
            behavior_metrics["behavior_group_decision_coverage"]
        )
        >= float(gate["behavior_group_decision_coverage_min"]),
        "per_source_behavior_group_decision_coverage": all(
            float(value["behavior_group_decision_coverage"])
            >= float(gate["minimum_per_source_behavior_group_decision_coverage"])
            for value in per_source_behavior.values()
        ),
        "minimum_per_fold_coverage": all(
            float(value["decided_coverage"]) >= float(gate["minimum_per_fold_decided_coverage"])
            for value in per_fold.values()
        ),
        "maximum_per_fold_error": all(
            float(value["decided_error_rate"])
            <= float(gate["maximum_per_fold_decided_error_rate"])
            for value in per_fold.values()
        ),
    }
    passed = all(checks.values())
    combination_counts = Counter(
        f"qwen={row['qwen_axis_label']}|jailmeter={row['jailmeter_axis_label']}"
        for row in records
    )
    result: JsonObject = {
        "schema_version": "jbspan-e0g4-heterogeneous-panel-full-development-result-v1",
        "status": (
            "E0G4_FULL_DEVELOPMENT_QUALIFICATION_PASS"
            if passed
            else "E0G4_FULL_DEVELOPMENT_QUALIFICATION_FAIL"
        ),
        "evidence_class": "FULL_PUBLIC_DEVELOPMENT_QUALIFICATION_NOT_HELDOUT_NOT_PAPER_RESULT",
        "contract_sha256": file_sha256(config_path),
        "selection_identity_sha256": load_object(
            root / str(recording["selection_manifest_path"])
        )["selection_identity_sha256"],
        "axis_identities": {
            "qwen3guard": qwen_summary["axis_identity_sha256"],
            "jailmeter": jailmeter_summary["axis_identity_sha256"],
        },
        "panel_rule": dict(config["fixed_panel_rule"]),
        "pooled_metrics": pooled,
        "per_source_metrics": per_source,
        "per_fold_metrics": per_fold,
        "per_agreement_metrics": per_agreement,
        "behavior_group_metrics": behavior_metrics,
        "per_source_behavior_group_metrics": per_source_behavior,
        "behavior_cluster_bootstrap": bootstrap,
        "per_source_behavior_cluster_bootstrap": per_source_bootstrap,
        "axis_parse_coverage_by_source": {
            "qwen3guard": qwen_parse_source,
            "jailmeter": jailmeter_parse_source,
        },
        "standalone_axis_metrics": {
            "qwen3guard": classification_metrics(truth, qwen_predictions),
            "jailmeter": classification_metrics(truth, jailmeter_predictions),
        },
        "axis_combination_counts": dict(sorted(combination_counts.items())),
        "records": records,
        "gate": {"checks": checks, "passes_all": passed},
        "interpretation": (
            gate["interpretation_on_pass"] if passed else gate["interpretation_on_fail"]
        ),
        "new_human_annotation": False,
        "heldout_opened": False,
        "topology_outcomes_opened": False,
        "raw_text_written": False,
        "raw_model_output_written": False,
        "paper_valid_result": False,
        "panel_qualified_for_heldout_candidate": passed,
        "protected_boundaries": dict(config["protected_boundaries"]),
        "next_operation": (
            config["next_operation_on_pass"] if passed else config["next_operation_on_fail"]
        ),
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(result_path, result)
    return result


def status(root: Path, config_path: Path) -> JsonObject:
    _config_path, config, _parent_config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    pool = required_mapping(config["development_pool"], where="development_pool")
    total = int(pool["records"])

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
        "status": "E0G4_PROGRESS_STATUS",
        "records_total": total,
        "qwen": {
            "status": qwen_status,
            "records": qwen_count,
            "remaining": total - qwen_count,
            "estimated_remaining_seconds_at_e0g2_mean": (total - qwen_count) * 0.7471661433422317,
        },
        "jailmeter": {
            "status": jailmeter_status,
            "records": jailmeter_count,
            "remaining": total - jailmeter_count,
            "estimated_remaining_seconds_at_e0g2_mean": (total - jailmeter_count)
            * 9.226787133289811,
        },
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
