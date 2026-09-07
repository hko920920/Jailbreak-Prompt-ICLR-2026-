from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jbspan.evaluator_abstaining_panel import (
    metrics_by_group,
    panel_label,
    qwen_axis_label,
    select_stratified_sentinel,
)
from jbspan.evaluator_cpu_router import classification_metrics
from jbspan.gate1.util import canonical_json_sha256

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument(
        "command", choices=("freeze", "preflight", "qwen", "jailmeter", "finalize")
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/heterogeneous_panel_sentinel_e0g2_v1.json"),
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


def safe_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite different frozen output: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
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


def verify_qualification(root: Path, spec: Mapping[str, Any]) -> JsonObject:
    path = root / str(spec["result_path"])
    verify_file(path, bytes_=spec["result_bytes"], sha256=spec["result_sha256"])
    value = load_object(path)
    if value.get("status") != spec["required_status"]:
        raise ValueError(f"qualification status mismatch: {path}")
    if value.get("result_identity_sha256") != spec["required_identity"]:
        raise ValueError(f"qualification identity mismatch: {path}")
    return value


def load_config(root: Path, config_path: Path) -> tuple[Path, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    raw_config = load_object(config_path)
    schema_version = raw_config.get("schema_version")
    if raw_config.get("frozen") is not True or raw_config.get("paper_validity") is not False:
        raise ValueError("raw E0G-2 contract must remain frozen and non-paper-valid")
    if schema_version == "jbspan-e0g2-heterogeneous-panel-development-sentinel-v1-1":
        parent = required_mapping(raw_config["parent_contract"], where="parent_contract")
        parent_path = root / str(parent["path"])
        verify_file(parent_path, bytes_=parent["bytes"], sha256=parent["sha256"])
        failure = required_mapping(raw_config["selection_failure"], where="selection_failure")
        failure_path = root / str(failure["path"])
        verify_file(failure_path, bytes_=failure["bytes"], sha256=failure["sha256"])
        if load_object(failure_path).get("status") != failure["required_status"]:
            raise ValueError("selection-failure status mismatch")
        config = load_object(parent_path)
        config["schema_version"] = schema_version
        config["status"] = raw_config["status"]
        selection = dict(required_mapping(config["selection"], where="selection"))
        selection.update(
            required_mapping(raw_config["selection_overrides"], where="selection_overrides")
        )
        config["selection"] = selection
        recording = dict(required_mapping(config["recording"], where="recording"))
        recording.update(
            required_mapping(raw_config["recording_overrides"], where="recording_overrides")
        )
        config["recording"] = recording
        config["operational_repair"] = raw_config["operational_repair"]
    else:
        config = raw_config
    if schema_version not in {
        "jbspan-e0g2-heterogeneous-panel-development-sentinel-v1",
        "jbspan-e0g2-heterogeneous-panel-development-sentinel-v1-1",
    }:
        raise ValueError("unsupported E0G-2 contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-2 must remain frozen and non-paper-valid")
    protected = required_mapping(config["protected_boundaries"], where="protected_boundaries")
    if any(protected.values()):
        raise ValueError("E0G-2 protected boundaries must remain false")
    axes = required_mapping(config["qualified_axes"], where="qualified_axes")
    verify_qualification(root, required_mapping(axes["qwen3guard"], where="qwen3guard"))
    jailmeter = required_mapping(axes["jailmeter"], where="jailmeter")
    verify_qualification(root, jailmeter)
    jailmeter_contract = root / str(jailmeter["contract_path"])
    verify_file(
        jailmeter_contract,
        bytes_=jailmeter["contract_bytes"],
        sha256=jailmeter["contract_sha256"],
    )
    pool = required_mapping(config["development_pool"], where="development_pool")
    router_contract = root / str(pool["router_contract_path"])
    verify_file(
        router_contract,
        bytes_=pool["router_contract_bytes"],
        sha256=pool["router_contract_sha256"],
    )
    return config_path, config


def development_metadata(root: Path, config: Mapping[str, Any]) -> list[JsonObject]:
    pool = required_mapping(config["development_pool"], where="development_pool")
    router = load_object(root / str(pool["router_contract_path"]))
    inputs = required_mapping(router["inputs"], where="router inputs")
    labels_spec = required_mapping(inputs["calibration_labels"], where="calibration labels")
    folds_spec = required_mapping(inputs["outer_folds"], where="outer folds")
    labels_path = root / str(labels_spec["path"])
    folds_path = root / str(folds_spec["path"])
    verify_file(labels_path, bytes_=labels_spec["bytes"], sha256=labels_spec["sha256"])
    verify_file(folds_path, bytes_=folds_spec["bytes"], sha256=folds_spec["sha256"])
    labels = load_jsonl(labels_path)
    folds = {str(row["record_id"]): row for row in load_jsonl(folds_path)}
    if len(labels) != int(pool["records"]) or len(folds) != int(pool["records"]):
        raise ValueError("development-pool denominator mismatch")
    rows: list[JsonObject] = []
    for row in labels:
        record_id = str(row["record_id"])
        fold = folds.get(record_id)
        if fold is None:
            raise ValueError("development record has no frozen fold")
        if (
            fold["source_id"] != row["source_id"]
            or fold["behavior_group_sha256"] != row["behavior_group_sha256"]
        ):
            raise ValueError("development label/fold identity mismatch")
        rows.append(
            {
                "record_id": record_id,
                "source_id": row["source_id"],
                "human_label": row["human_label"],
                "human_unanimous": bool(row["human_unanimous"]),
                "behavior_group_sha256": row["behavior_group_sha256"],
                "response_sha256": row["response_sha256"],
                "outer_fold": int(fold["outer_fold"]),
            }
        )
    return rows


def freeze_selection(root: Path, config_path: Path) -> JsonObject:
    config_path, config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    selection_path = root / str(recording["selection_path"])
    manifest_path = root / str(recording["selection_manifest_path"])
    if selection_path.exists() or manifest_path.exists():
        if not selection_path.exists() or not manifest_path.exists():
            raise ValueError("partial frozen selection exists")
        existing_manifest = load_object(manifest_path)
        if existing_manifest.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing selection belongs to a different contract")
        if existing_manifest.get("selection_file_sha256") != file_sha256(selection_path):
            raise ValueError("existing selection file identity mismatch")
        return existing_manifest

    selection = required_mapping(config["selection"], where="selection")
    quota = required_mapping(selection["per_source_label_quota"], where="selection quota")
    rows = development_metadata(root, config)
    selected = select_stratified_sentinel(
        rows,
        seed=str(selection["seed"]),
        sources=[str(value) for value in config["development_pool"]["sources"]],
        unanimous_quota=int(quota["unanimous"]),
        split_vote_quota=int(quota["split_vote"]),
        maximum_records_per_behavior_group=int(
            selection.get("maximum_records_per_behavior_group", 1)
        ),
    )
    output_fields = (
        "record_id",
        "source_id",
        "human_label",
        "human_unanimous",
        "agreement_stratum",
        "behavior_group_sha256",
        "response_sha256",
        "outer_fold",
        "selection_score",
    )
    safe_rows = [{field: row[field] for field in output_fields} for row in selected]
    expected_records = int(selection["records"])
    if len(safe_rows) != expected_records:
        raise ValueError("sentinel selection denominator mismatch")
    group_counts = Counter(str(row["behavior_group_sha256"]) for row in safe_rows)
    maximum_per_group = int(selection.get("maximum_records_per_behavior_group", 1))
    if not group_counts or max(group_counts.values()) > maximum_per_group:
        raise ValueError("sentinel behavior-group cap was exceeded")
    safe_write_jsonl(selection_path, safe_rows)
    counts = Counter(
        (
            str(row["source_id"]),
            str(row["human_label"]),
            str(row["agreement_stratum"]),
        )
        for row in safe_rows
    )
    truth_commitment = canonical_json_sha256(
        [{"record_id": row["record_id"], "human_label": row["human_label"]} for row in safe_rows]
    )
    manifest: JsonObject = {
        "schema_version": "jbspan-e0g2-panel-sentinel-selection-manifest-v1",
        "status": "E0G2_PANEL_SENTINEL_SELECTION_FROZEN",
        "contract_sha256": file_sha256(config_path),
        "selection_file": selection_path.relative_to(root).as_posix(),
        "selection_file_bytes": selection_path.stat().st_size,
        "selection_file_sha256": file_sha256(selection_path),
        "truth_commitment_sha256": truth_commitment,
        "record_count": len(safe_rows),
        "behavior_group_count": len(
            {str(row["behavior_group_sha256"]) for row in safe_rows}
        ),
        "maximum_records_in_one_behavior_group": max(group_counts.values()),
        "maximum_records_per_behavior_group_contract": maximum_per_group,
        "dependence_warning": selection.get("dependence_warning"),
        "human_harmful": sum(row["human_label"] == "HARMFUL" for row in safe_rows),
        "human_safe": sum(row["human_label"] == "SAFE" for row in safe_rows),
        "unanimous": sum(bool(row["human_unanimous"]) for row in safe_rows),
        "split_vote": sum(not bool(row["human_unanimous"]) for row in safe_rows),
        "stratum_counts": {
            "|".join(key): value for key, value in sorted(counts.items())
        },
        "raw_text_read": False,
        "model_output_observed": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    manifest["selection_identity_sha256"] = canonical_json_sha256(manifest)
    safe_write(manifest_path, manifest)
    return manifest


def reconstruct_selected(root: Path, config: Mapping[str, Any]) -> list[Any]:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    reconstruction_module = importlib.import_module(
        "scripts.audit_evaluator_cpu_learned_router_e0g0"
    )
    pool = required_mapping(config["development_pool"], where="development_pool")
    router = load_object(root / str(pool["router_contract_path"]))
    records, _summary = reconstruction_module.reconstruct_records(root, router)
    recording = required_mapping(config["recording"], where="recording")
    selected = load_jsonl(root / str(recording["selection_path"]))
    index = {record.record_id: record for record in records}
    output: list[Any] = []
    for row in selected:
        record = index.get(str(row["record_id"]))
        if record is None:
            raise ValueError("frozen sentinel record could not be reconstructed")
        if (
            record.behavior_group_sha256 != row["behavior_group_sha256"]
            or hashlib.sha256(record.response_text.encode()).hexdigest()
            != row["response_sha256"]
        ):
            raise ValueError("reconstructed sentinel text identity mismatch")
        output.append(record)
    return output


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config = load_config(root, config_path)
    selection = freeze_selection(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["preflight_path"])
    if output_path.exists():
        existing = load_object(output_path)
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing preflight belongs to a different contract")
        return existing

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    jailmeter_module = importlib.import_module("scripts.qualify_jailmeter_runtime_e0g1b")
    qwen_module = importlib.import_module("scripts.qualify_qwen3guard_runtime_e0g1a")
    axes = required_mapping(config["qualified_axes"], where="qualified_axes")
    qwen_spec = required_mapping(axes["qwen3guard"], where="qwen3guard")
    _, qwen_config = qwen_module.resolve_config(root, root / str(qwen_spec["contract_path"]))
    qwen_files, qwen_bytes = qwen_module.verify_model_files(root, qwen_config)
    jailmeter_spec = required_mapping(axes["jailmeter"], where="jailmeter")
    conversion = jailmeter_module.convert(
        root, root / str(jailmeter_spec["contract_path"])
    )
    records = reconstruct_selected(root, config)
    if len(records) != int(config["selection"]["records"]):
        raise ValueError("reconstructed sentinel denominator mismatch")
    result: JsonObject = {
        "schema_version": "jbspan-e0g2-panel-sentinel-preflight-v1",
        "status": "E0G2_PANEL_SENTINEL_PREFLIGHT_PASS",
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
            "cuda_available": _cuda_available(),
            "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
            "free_disk_bytes": shutil.disk_usage(root).free,
        },
        "selection_identity_sha256": selection["selection_identity_sha256"],
        "selection_records_reconstructed": len(records),
        "qwen_model_files": qwen_files,
        "qwen_model_bytes": qwen_bytes,
        "jailmeter_conversion_identity_sha256": conversion["conversion_identity_sha256"],
        "raw_text_written": False,
        "model_output_observed": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def _cuda_available() -> bool:
    import torch

    return bool(torch.cuda.is_available())


def parse_qwen_output(content: str, runtime: Mapping[str, Any]) -> JsonObject:
    safety_matches = re.findall(str(runtime["safety_regex"]), content)
    refusal_matches = re.findall(str(runtime["refusal_regex"]), content)
    safety = (
        safety_matches[0]
        if safety_matches
        and (
            runtime.get("require_exactly_one_safety_match") is not True
            or len(safety_matches) == 1
        )
        else None
    )
    refusal = (
        refusal_matches[0]
        if refusal_matches
        and (
            runtime.get("require_exactly_one_refusal_match") is not True
            or len(refusal_matches) == 1
        )
        else None
    )
    return {
        "safety": safety,
        "refusal": refusal,
        "categories": re.findall(str(runtime["category_regex"]), content),
        "safety_match_count": len(safety_matches),
        "refusal_match_count": len(refusal_matches),
    }


def verify_axis_pair(path: Path, summary_path: Path, expected_records: int) -> JsonObject:
    if not path.is_file() or not summary_path.is_file():
        raise ValueError("axis output pair is incomplete")
    summary = load_object(summary_path)
    if summary.get("axis_file_sha256") != file_sha256(path):
        raise ValueError("axis output identity mismatch")
    if summary.get("record_count") != expected_records:
        raise ValueError("axis output denominator mismatch")
    return summary


def run_qwen(root: Path, config_path: Path) -> JsonObject:
    config_path, config = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    axis_path = root / str(recording["qwen_axis_path"])
    summary_path = root / str(recording["qwen_summary_path"])
    expected_records = int(config["selection"]["records"])
    if axis_path.exists() or summary_path.exists():
        return verify_axis_pair(axis_path, summary_path, expected_records)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    runtime = required_mapping(config["qwen3guard_runtime"], where="qwen3guard_runtime")
    if not torch.cuda.is_available():
        raise RuntimeError("frozen Qwen3Guard sentinel requires CUDA")
    torch.cuda.init()  # type: ignore[no-untyped-call]
    torch.cuda.set_device(0)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    model_path = root / str(runtime["model_local_path"])
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        model_path, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        dtype=torch.float16,
        local_files_only=True,
        low_cpu_mem_usage=True,
    ).to(torch.device("cuda:0"))  # type: ignore[arg-type]
    model.eval()
    load_seconds = time.perf_counter() - started
    records = reconstruct_selected(root, config)
    rows: list[JsonObject] = []
    inference_started = time.perf_counter()
    for record in records:
        rendered = tokenizer.apply_chat_template(
            [
                {"role": "user", "content": record.goal_text},
                {"role": "assistant", "content": record.response_text},
            ],
            tokenize=False,
        )
        if not isinstance(rendered, str) or not rendered:
            raise ValueError("Qwen3Guard tokenizer returned an invalid prompt")
        encoded = tokenizer([rendered], return_tensors="pt").to(torch.device("cuda:0"))
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
        parsed = parse_qwen_output(content, runtime)
        rows.append(
            {
                "record_id": record.record_id,
                "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
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
    inference_seconds = time.perf_counter() - inference_started
    total_seconds = time.perf_counter() - started
    safe_write_jsonl(axis_path, rows)
    parsed_count = sum(row["safety"] is not None and row["refusal"] is not None for row in rows)
    summary: JsonObject = {
        "schema_version": "jbspan-e0g2-panel-sentinel-qwen-axis-summary-v1",
        "status": "E0G2_QWEN3GUARD_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
        "load_seconds": load_seconds,
        "inference_seconds": inference_seconds,
        "total_seconds": total_seconds,
        "mean_inference_seconds": sum(float(row["inference_seconds"]) for row in rows)
        / len(rows),
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(0),
        "safety_counts": dict(Counter(str(row["safety"]) for row in rows)),
        "refusal_counts": dict(Counter(str(row["refusal"]) for row in rows)),
        "axis_file": axis_path.relative_to(root).as_posix(),
        "axis_file_bytes": axis_path.stat().st_size,
        "axis_file_sha256": file_sha256(axis_path),
        "raw_text_written": False,
        "raw_model_output_written": False,
    }
    summary["axis_identity_sha256"] = canonical_json_sha256(summary)
    safe_write(summary_path, summary)
    return summary


def extract_system_prompt(path: Path) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "system_prompt_with_cot"
            for target in targets
        ):
            continue
        if node.value is None:
            continue
        result = ast.literal_eval(node.value)
        if isinstance(result, str) and result.strip():
            return result
    raise ValueError("JailMeter system prompt was not found")


def parse_jailmeter_label(content: str, runtime: Mapping[str, Any]) -> JsonObject:
    matches = re.findall(str(runtime["label_regex"]), content)
    strict = runtime.get("require_exactly_one_label_match") is True
    label = int(matches[0]) if matches and (not strict or len(matches) == 1) else None
    return {"label": label, "match_count": len(matches)}


def post_json(url: str, payload: JsonObject, timeout: float) -> JsonObject:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        value: object = json.loads(response.read().decode())
    if not isinstance(value, dict):
        raise ValueError("llama-server returned a non-object JSON value")
    return value


def server_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
            status = getattr(response, "status", None)
            return isinstance(status, int) and status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        return handle.connect_ex((host, port)) != 0


def query_gpu_memory_mib() -> float | None:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    completed = subprocess.run(
        [
            executable,
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
            "-i",
            "0",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip().splitlines()[0])
    except (IndexError, ValueError):
        return None


def run_jailmeter(root: Path, config_path: Path) -> JsonObject:
    config_path, config = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    axis_path = root / str(recording["jailmeter_axis_path"])
    summary_path = root / str(recording["jailmeter_summary_path"])
    expected_records = int(config["selection"]["records"])
    if axis_path.exists() or summary_path.exists():
        return verify_axis_pair(axis_path, summary_path, expected_records)

    from transformers import AutoTokenizer

    runtime = required_mapping(config["jailmeter_runtime"], where="jailmeter_runtime")
    baseline_gpu = query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(runtime["maximum_prelaunch_gpu_memory_mib"]):
        raise RuntimeError(
            "GPU baseline is not controlled before JailMeter sentinel: "
            f"observed={baseline_gpu} MiB"
        )
    host = str(runtime["host"])
    port = int(runtime["port"])
    if not port_is_free(host, port):
        raise ValueError(f"frozen JailMeter sentinel port is occupied: {host}:{port}")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    system_prompt = extract_system_prompt(root / str(runtime["runner_path"]))
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
        str(runtime["context_tokens"]),
        "-t",
        str(runtime["threads"]),
        "-ngl",
        str(runtime["gpu_layers"]),
        "--offline",
        "--no-webui",
    ]
    records = reconstruct_selected(root, config)
    log_handle = tempfile.NamedTemporaryFile(prefix="e0g2-jailmeter-", suffix=".log", delete=False)
    log_path = Path(log_handle.name)
    gpu_samples: list[float] = []
    stop_sampling = threading.Event()

    def sample_gpu() -> None:
        while not stop_sampling.is_set():
            value = query_gpu_memory_mib()
            if value is not None:
                gpu_samples.append(value)
            stop_sampling.wait(0.25)

    sampler = threading.Thread(target=sample_gpu, daemon=True)
    sampler.start()
    process: subprocess.Popen[bytes] | None = None
    rows: list[JsonObject] = []
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
            if server_ready(health_url):
                ready_seconds = time.perf_counter() - started
                break
            time.sleep(0.25)
        if ready_seconds is None:
            raise TimeoutError("JailMeter sentinel server health timeout")

        for record in records:
            user_content = json.dumps(
                {
                    "original_question": record.goal_text,
                    "model_response": record.response_text,
                },
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
                raise ValueError("tokenizer returned an invalid JailMeter prompt")
            input_tokens = len(tokenizer.encode(rendered, add_special_tokens=False))
            call_started = time.perf_counter()
            response = post_json(
                f"http://{host}:{port}/completion",
                {
                    "prompt": rendered,
                    "n_predict": int(runtime["max_new_tokens"]),
                    "temperature": float(runtime["temperature"]),
                    "stream": False,
                    "cache_prompt": False,
                },
                timeout=float(runtime["request_timeout_seconds"]),
            )
            content = response.get("content")
            if not isinstance(content, str):
                raise ValueError("JailMeter endpoint returned no text")
            parsed = parse_jailmeter_label(content, runtime)
            predicted = response.get("tokens_predicted")
            rows.append(
                {
                    "record_id": record.record_id,
                    "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                    "input_tokens": input_tokens,
                    "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "output_characters": len(content),
                    "output_tokens": predicted if isinstance(predicted, int) else None,
                    "output_limit_stop": bool(response.get("stopped_limit", False)),
                    "label": parsed["label"],
                    "label_match_count": parsed["match_count"],
                    "inference_seconds": time.perf_counter() - call_started,
                }
            )
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

    safe_write_jsonl(axis_path, rows)
    parsed_count = sum(row["label"] is not None for row in rows)
    peak_gpu = max(gpu_samples) if gpu_samples else None
    summary: JsonObject = {
        "schema_version": "jbspan-e0g2-panel-sentinel-jailmeter-axis-summary-v1",
        "status": "E0G2_JAILMETER_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "record_count": len(rows),
        "parse_count": parsed_count,
        "parse_coverage": parsed_count / len(rows),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
        "server_ready_seconds": ready_seconds,
        "total_seconds": total_seconds,
        "mean_inference_seconds": sum(float(row["inference_seconds"]) for row in rows)
        / len(rows),
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_gpu_memory_mib": peak_gpu,
        "gpu_memory_delta_mib": (
            peak_gpu - baseline_gpu if peak_gpu is not None else None
        ),
        "label_counts": dict(Counter(str(row["label"]) for row in rows)),
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "server_log_bytes": len(log_content),
        "server_log_sha256": log_sha256,
        "server_log_retained": False,
        "axis_file": axis_path.relative_to(root).as_posix(),
        "axis_file_bytes": axis_path.stat().st_size,
        "axis_file_sha256": file_sha256(axis_path),
        "raw_text_written": False,
        "raw_model_output_written": False,
    }
    summary["axis_identity_sha256"] = canonical_json_sha256(summary)
    safe_write(summary_path, summary)
    return summary


def axis_index(path: Path, expected_ids: set[str]) -> dict[str, JsonObject]:
    rows = load_jsonl(path)
    index = {str(row["record_id"]): row for row in rows}
    if len(rows) != len(index) or set(index) != expected_ids:
        raise ValueError(f"axis keys do not match frozen selection: {path}")
    return index


def combination_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(
        f"qwen={row['qwen_axis_label']}|jailmeter={row['jailmeter_axis_label']}"
        for row in rows
    )
    return dict(sorted(counts.items()))


def finalize(root: Path, config_path: Path) -> JsonObject:
    config_path, config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    result_path = root / str(recording["result_path"])
    if result_path.exists():
        return load_object(result_path)
    expected_records = int(config["selection"]["records"])
    qwen_summary = verify_axis_pair(
        root / str(recording["qwen_axis_path"]),
        root / str(recording["qwen_summary_path"]),
        expected_records,
    )
    jailmeter_summary = verify_axis_pair(
        root / str(recording["jailmeter_axis_path"]),
        root / str(recording["jailmeter_summary_path"]),
        expected_records,
    )
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
        jailmeter_axis = (
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
                "human_label": truth_row["human_label"],
                "human_unanimous": truth_row["human_unanimous"],
                "qwen_safety": qwen_row.get("safety"),
                "qwen_refusal": qwen_row.get("refusal"),
                "qwen_axis_label": qwen_label,
                "jailmeter_axis_label": jailmeter_axis,
                "panel_label": prediction,
                "panel_correct_if_decided": (
                    prediction == truth_row["human_label"]
                    if prediction != "ABSTAIN"
                    else None
                ),
            }
        )
    truth = [str(row["human_label"]) for row in records]
    panel_predictions = [str(row["panel_label"]) for row in records]
    qwen_predictions = [str(row["qwen_axis_label"]) for row in records]
    jailmeter_predictions = [str(row["jailmeter_axis_label"]) for row in records]
    pooled = classification_metrics(truth, panel_predictions)
    per_source = metrics_by_group(
        truth, panel_predictions, [str(row["source_id"]) for row in records]
    )
    per_agreement = metrics_by_group(
        truth,
        panel_predictions,
        ["unanimous" if bool(row["human_unanimous"]) else "split_vote" for row in records],
    )
    gate = required_mapping(config["sentinel_gate"], where="sentinel_gate")
    checks = {
        "qwen_parse_coverage": float(qwen_summary["parse_coverage"])
        >= float(gate["qwen_parse_coverage_min"]),
        "jailmeter_parse_coverage": float(jailmeter_summary["parse_coverage"])
        >= float(gate["jailmeter_parse_coverage_min"]),
        "panel_decided_coverage": float(pooled["decided_coverage"])
        >= float(gate["panel_decided_coverage_min"]),
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
        "minimum_per_source_coverage": all(
            float(value["decided_coverage"])
            >= float(gate["minimum_per_source_decided_coverage"])
            for value in per_source.values()
        ),
        "maximum_per_source_error": all(
            float(value["decided_error_rate"])
            <= float(gate["maximum_per_source_decided_error_rate"])
            for value in per_source.values()
        ),
        "maximum_unanimous_error": float(per_agreement["unanimous"]["decided_error_rate"])
        <= float(gate["maximum_unanimous_decided_error_rate"]),
        "no_output_limit_stops": int(qwen_summary["output_limit_stops"])
        + int(jailmeter_summary["output_limit_stops"])
        <= int(gate["output_limit_stops_allowed"]),
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-e0g2-heterogeneous-panel-sentinel-result-v1",
        "status": (
            "E0G2_HETEROGENEOUS_PANEL_SENTINEL_PASS"
            if passed
            else "E0G2_HETEROGENEOUS_PANEL_SENTINEL_FAIL"
        ),
        "evidence_class": "LABEL_BALANCED_PUBLIC_DEVELOPMENT_SENTINEL_NOT_PANEL_QUALIFICATION",
        "contract_sha256": file_sha256(config_path),
        "selection_manifest_identity_sha256": load_object(
            root / str(recording["selection_manifest_path"])
        )["selection_identity_sha256"],
        "axis_identities": {
            "qwen3guard": qwen_summary["axis_identity_sha256"],
            "jailmeter": jailmeter_summary["axis_identity_sha256"],
        },
        "panel_rule": dict(config["panel_rule"]),
        "pooled_metrics": pooled,
        "per_source_metrics": per_source,
        "per_agreement_metrics": per_agreement,
        "standalone_axis_metrics": {
            "qwen3guard": classification_metrics(truth, qwen_predictions),
            "jailmeter": classification_metrics(truth, jailmeter_predictions),
        },
        "axis_combination_counts": combination_counts(records),
        "records": records,
        "gate": {"checks": checks, "passes_all": passed},
        "balanced_selection_warning": config["selection"]["interpretation"],
        "new_human_annotation": False,
        "raw_text_written": False,
        "raw_model_output_written": False,
        "paper_valid_result": False,
        "panel_qualified": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
        "next_operation": (
            config["next_operation_on_pass"] if passed else config["next_operation_on_fail"]
        ),
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(result_path, result)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    if args.command == "freeze":
        result = freeze_selection(root, args.config)
    elif args.command == "preflight":
        result = preflight(root, args.config)
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
