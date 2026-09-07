from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jbspan.gate1.util import canonical_json_sha256  # type: ignore[import-untyped]

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("preflight", "download", "qualify"))
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/qwen3guard_runtime_e0g1a_v1.json"),
    )
    return value


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()  # noqa: S324


def file_git_blob_sha1(path: Path) -> str:
    digest = hashlib.sha1()  # noqa: S324
    digest.update(f"blob {path.stat().st_size}\0".encode())
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


def resolve_config(root: Path, config_path: Path) -> tuple[Path, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    raw_config = load_object(config_path)
    schema_version = raw_config.get("schema_version")
    repair_versions = {
        "jbspan-e0g1a-qwen3guard-runtime-qualification-v1-1",
        "jbspan-e0g1a-qwen3guard-runtime-qualification-v1-2",
    }
    if schema_version in repair_versions:
        parent = raw_config.get("parent_contract")
        adoption = raw_config.get("download_adoption")
        raw_failures = raw_config.get("operational_failures")
        if raw_failures is None:
            raw_failures = [raw_config.get("operational_failure")]
        if (
            not isinstance(parent, Mapping)
            or not isinstance(adoption, Mapping)
            or not isinstance(raw_failures, list)
            or not raw_failures
            or not all(isinstance(value, Mapping) for value in raw_failures)
        ):
            raise ValueError("repair parent, failures, and adoption are invalid")
        assert isinstance(parent, Mapping)
        assert isinstance(adoption, Mapping)
        parent_path = root / str(parent["path"])
        adoption_path = root / str(adoption["path"])
        if file_sha256(parent_path) != str(parent["sha256"]):
            raise ValueError("repair parent contract SHA-256 mismatch")
        for raw_failure in raw_failures:
            assert isinstance(raw_failure, Mapping)
            failure_path = root / str(raw_failure["path"])
            if file_sha256(failure_path) != str(raw_failure["sha256"]):
                raise ValueError("repair failure-record SHA-256 mismatch")
            failure_record = load_object(failure_path)
            if failure_record.get("status") != raw_failure["required_status"]:
                raise ValueError("repair failure-record status mismatch")
        if file_sha256(adoption_path) != str(adoption["sha256"]):
            raise ValueError("V1.1 adopted-download SHA-256 mismatch")
        adoption_record = load_object(adoption_path)
        if adoption_record.get("status") != adoption["status"]:
            raise ValueError("V1.1 adopted-download status mismatch")
        if adoption_record.get("download_identity_sha256") != adoption["download_identity_sha256"]:
            raise ValueError("V1.1 adopted-download identity mismatch")
        config = load_object(parent_path)
        config["schema_version"] = schema_version
        config["status"] = raw_config["status"]
        config["operational_repair"] = raw_config["operational_repair"]
        recording = dict(config["recording"])
        overrides = raw_config.get("recording_overrides")
        if not isinstance(overrides, Mapping):
            raise ValueError("V1.1 recording overrides must be an object")
        recording.update(overrides)
        config["recording"] = recording
    else:
        config = raw_config
    if schema_version not in {
        "jbspan-e0g1a-qwen3guard-runtime-qualification-v1",
        "jbspan-e0g1a-qwen3guard-runtime-qualification-v1-1",
        "jbspan-e0g1a-qwen3guard-runtime-qualification-v1-2",
    }:
        raise ValueError("unsupported E0G-1A contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-1A must remain frozen and non-paper-valid")
    protected = config["protected_boundaries"]
    if not isinstance(protected, Mapping) or any(protected.values()):
        raise ValueError("all protected-boundary observations must remain false")
    predecessor = config["predecessor"]
    if not isinstance(predecessor, Mapping):
        raise ValueError("predecessor must be an object")
    predecessor_path = root / str(predecessor["path"])
    if file_sha256(predecessor_path) != str(predecessor["sha256"]):
        raise ValueError("E0G-0 predecessor SHA-256 mismatch")
    if load_object(predecessor_path).get("status") != predecessor["required_status"]:
        raise ValueError("E0G-0 predecessor status mismatch")
    return config_path, config


def model_specs(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    model = config["model"]
    if not isinstance(model, Mapping) or not isinstance(model["files"], list):
        raise ValueError("model file contract is invalid")
    files = [item for item in model["files"] if isinstance(item, Mapping)]
    if len(files) != len(model["files"]):
        raise ValueError("model file entry must be an object")
    if sum(int(item["bytes"]) for item in files) != int(model["expected_total_bytes"]):
        raise ValueError("expected model byte total mismatch")
    return files


def parse_output(content: str, parser_config: Mapping[str, Any]) -> JsonObject:
    safety = re.findall(str(parser_config["safety_regex"]), content)
    refusal = re.findall(str(parser_config["refusal_regex"]), content)
    if parser_config.get("require_exactly_one_safety_match") is True and len(safety) != 1:
        raise ValueError("safety parser did not find exactly one decision")
    if parser_config.get("require_exactly_one_refusal_match") is True and len(refusal) != 1:
        raise ValueError("refusal parser did not find exactly one decision")
    categories = re.findall(str(parser_config["category_regex"]), content)
    return {
        "safety": safety[0] if safety else None,
        "categories": categories,
        "refusal": refusal[0] if refusal else None,
    }


def existing_or_none(path: Path) -> JsonObject | None:
    return load_object(path) if path.exists() else None


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    recording = config["recording"]
    if not isinstance(recording, Mapping):
        raise ValueError("recording must be an object")
    output_path = root / str(recording["preflight_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing preflight belongs to a different contract")
        return existing

    import torch
    import transformers
    from huggingface_hub import __version__ as hub_version

    model = config["model"]
    if not isinstance(model, Mapping):
        raise ValueError("model must be an object")
    usage = shutil.disk_usage(root)
    required_bytes = int(model["expected_total_bytes"])
    if usage.free < required_bytes * 2:
        raise ValueError("insufficient free disk for exact model and download overhead")
    _ = model_specs(config)
    cuda_available = torch.cuda.is_available()
    result: JsonObject = {
        "schema_version": "jbspan-e0g1a-qwen3guard-runtime-preflight-v1",
        "status": "E0G1A_QWEN3GUARD_RUNTIME_PREFLIGHT_PASS",
        "contract_path": config_path.relative_to(root).as_posix(),
        "contract_sha256": file_sha256(config_path),
        "implementation": {
            "path": Path(__file__).resolve().relative_to(root).as_posix(),
            "bytes": Path(__file__).stat().st_size,
            "sha256": file_sha256(Path(__file__)),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "huggingface_hub": hub_version,
            "cuda_available": cuda_available,
            "cuda_device_count": torch.cuda.device_count(),
            "selected_device": "cuda:0" if cuda_available else "cpu",
            "selected_dtype": "float16" if cuda_available else "float32",
            "cuda_device_name": torch.cuda.get_device_name(0) if cuda_available else None,
            "free_disk_bytes_before_download": usage.free,
        },
        "model_repository": model["repository"],
        "model_revision": model["revision"],
        "expected_model_bytes": required_bytes,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def verify_model_files(root: Path, config: Mapping[str, Any]) -> tuple[list[JsonObject], int]:
    model = config["model"]
    if not isinstance(model, Mapping):
        raise ValueError("model must be an object")
    model_path = root / str(model["local_path"])
    rows: list[JsonObject] = []
    total = 0
    for spec in model_specs(config):
        path = model_path / str(spec["path"])
        if not path.is_file() or path.stat().st_size != int(spec["bytes"]):
            raise ValueError(f"model file identity mismatch: {path}")
        sha256 = file_sha256(path)
        if "sha256" in spec and sha256 != str(spec["sha256"]):
            raise ValueError(f"model SHA-256 mismatch: {path}")
        blob_sha1 = file_git_blob_sha1(path)
        if "git_blob_sha1" in spec and blob_sha1 != str(spec["git_blob_sha1"]):
            raise ValueError(f"model Git-blob mismatch: {path}")
        rows.append(
            {
                "path": str(spec["path"]),
                "bytes": path.stat().st_size,
                "sha256": sha256,
                "git_blob_sha1": blob_sha1,
            }
        )
        total += path.stat().st_size
    if total != int(model["expected_total_bytes"]):
        raise ValueError("downloaded model byte total mismatch")
    return rows, total


def download(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    preflight_result = preflight(root, config_path)
    model = config["model"]
    recording = config["recording"]
    if not isinstance(model, Mapping) or not isinstance(recording, Mapping):
        raise ValueError("model and recording must be objects")
    output_path = root / str(recording["download_manifest_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        verify_model_files(root, config)
        return existing

    from huggingface_hub import snapshot_download

    model_path = root / str(model["local_path"])
    model_path.mkdir(parents=True, exist_ok=True)
    resolved = snapshot_download(
        repo_id=str(model["repository"]),
        revision=str(model["revision"]),
        local_dir=model_path,
        allow_patterns=[str(item["path"]) for item in model_specs(config)],
    )
    if Path(resolved).resolve() != model_path.resolve():
        raise ValueError("snapshot downloaded outside the frozen local directory")
    files, total = verify_model_files(root, config)
    result: JsonObject = {
        "schema_version": "jbspan-e0g1a-qwen3guard-download-v1",
        "status": "E0G1A_QWEN3GUARD_EXACT_DOWNLOAD_PASS",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "repository": model["repository"],
        "revision": model["revision"],
        "local_path": model["local_path"],
        "files": files,
        "total_bytes": total,
    }
    result["download_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def qualify(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    download_result = download(root, config_path)
    recording = config["recording"]
    runtime = config["runtime"]
    model_config = config["model"]
    parser_config = config["parser"]
    gate_config = config["qualification_gate"]
    if not all(
        isinstance(value, Mapping)
        for value in (recording, runtime, model_config, parser_config, gate_config)
    ):
        raise ValueError("qualification config sections must be objects")
    output_path = root / str(recording["result_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        return existing

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(int(runtime["torch_threads_on_cpu"]))
    cuda_available = torch.cuda.is_available()
    device = torch.device("cuda:0" if cuda_available else "cpu")
    dtype = torch.float16 if cuda_available else torch.float32
    if cuda_available:
        torch.cuda.init()  # type: ignore[no-untyped-call]
        torch.cuda.set_device(0)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(0)
    model_path = root / str(model_config["local_path"])
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        model_path, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=dtype,
        local_files_only=True,
        low_cpu_mem_usage=True,
    ).to(device)  # type: ignore[arg-type]
    model.eval()
    load_seconds = time.perf_counter() - started

    cases = config["harmless_cases"]
    if not isinstance(cases, list) or len(cases) != int(gate_config["case_count"]):
        raise ValueError("harmless case denominator mismatch")
    records: list[JsonObject] = []
    raw_outputs: dict[str, list[str]] = {}
    inference_started = time.perf_counter()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("harmless case must be an object")
        case_id = str(case["case_id"])
        messages = [
            {"role": "user", "content": str(case["user"])},
            {"role": "assistant", "content": str(case["assistant"])},
        ]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False)
        if not isinstance(rendered, str) or not rendered:
            raise ValueError("tokenizer returned an invalid chat template")
        encoded = tokenizer([rendered], return_tensors="pt").to(device)
        raw_outputs[case_id] = []
        for repetition in range(int(runtime["repetitions_per_case"])):
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
            raw_outputs[case_id].append(content)
            parsed = parse_output(content, parser_config)
            records.append(
                {
                    "case_id": case_id,
                    "repetition": repetition,
                    "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                    "input_tokens": int(encoded.input_ids.shape[1]),
                    "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "output_characters": len(content),
                    "output_tokens": len(output_ids),
                    "output_limit_stop": len(output_ids) >= int(runtime["max_new_tokens"]),
                    "safety": parsed["safety"],
                    "categories": parsed["categories"],
                    "refusal": parsed["refusal"],
                    "expected_safety_match": parsed["safety"] == case["expected_safety"],
                    "expected_refusal_match": parsed["refusal"] == case["expected_refusal"],
                    "inference_seconds": time.perf_counter() - call_started,
                }
            )
    inference_seconds = time.perf_counter() - inference_started
    total_seconds = time.perf_counter() - started
    invocation_count = len(records)
    parse_count = sum(row["safety"] is not None and row["refusal"] is not None for row in records)
    safety_correct = sum(bool(row["expected_safety_match"]) for row in records)
    refusal_correct = sum(bool(row["expected_refusal_match"]) for row in records)
    repeated_cases = sum(len(set(raw_outputs[str(case["case_id"])])) == 1 for case in cases)
    output_limit_stops = sum(bool(row["output_limit_stop"]) for row in records)
    observed = {
        "case_count": len(cases),
        "invocation_count": invocation_count,
        "parse_coverage": parse_count / invocation_count,
        "expected_safety_accuracy": safety_correct / invocation_count,
        "expected_refusal_accuracy": refusal_correct / invocation_count,
        "per_case_byte_repeatability": repeated_cases / len(cases),
        "output_limit_stops": output_limit_stops,
        "load_seconds": load_seconds,
        "inference_seconds": inference_seconds,
        "total_qualification_seconds": total_seconds,
        "mean_inference_seconds": sum(float(row["inference_seconds"]) for row in records)
        / invocation_count,
        "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated(0) if cuda_available else 0),
    }
    checks = {
        "download_identity_pass": download_result["status"]
        == "E0G1A_QWEN3GUARD_EXACT_DOWNLOAD_PASS",
        "case_count": observed["case_count"] == int(gate_config["case_count"]),
        "invocation_count": observed["invocation_count"] == int(gate_config["invocation_count"]),
        "parse_coverage": observed["parse_coverage"] >= float(gate_config["parse_coverage"]),
        "expected_safety_accuracy": observed["expected_safety_accuracy"]
        >= float(gate_config["expected_safety_accuracy"]),
        "expected_refusal_accuracy": observed["expected_refusal_accuracy"]
        >= float(gate_config["expected_refusal_accuracy"]),
        "per_case_byte_repeatability": observed["per_case_byte_repeatability"]
        >= float(gate_config["per_case_byte_repeatability"]),
        "no_output_limit_stop": output_limit_stops == 0,
        "within_time_budget": total_seconds
        <= float(runtime["maximum_total_qualification_seconds"]),
        "within_cuda_memory_budget": (
            not cuda_available
            or observed["peak_cuda_allocated_bytes"]
            <= int(runtime["maximum_peak_cuda_allocated_bytes"])
        ),
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-e0g1a-qwen3guard-runtime-result-v1",
        "status": (
            "E0G1A_QWEN3GUARD_HARMLESS_RUNTIME_PASS"
            if passed
            else "E0G1A_QWEN3GUARD_HARMLESS_RUNTIME_FAIL"
        ),
        "evidence_class": "HARMLESS_OPERATIONAL_QUALIFICATION_NOT_SCIENTIFIC_CALIBRATION",
        "contract_sha256": file_sha256(config_path),
        "download_identity_sha256": download_result["download_identity_sha256"],
        "device": {
            "device": str(device),
            "dtype": str(dtype),
            "cuda_device_name": torch.cuda.get_device_name(0) if cuda_available else None,
        },
        "records": records,
        "observed": observed,
        "gate": {"checks": checks, "passes_all": passed},
        "raw_model_output_written": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
        "panel_qualified": False,
        "paper_valid_result": False,
        "next_operation": (
            config["next_operation_on_pass"] if passed else config["next_operation_on_fail"]
        ),
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = args.config
    if args.command == "preflight":
        result = preflight(root, config_path)
    elif args.command == "download":
        result = download(root, config_path)
    else:
        result = qualify(root, config_path)
    print(
        json.dumps(
            {
                "status": result["status"],
                "identity": result.get("result_identity_sha256")
                or result.get("download_identity_sha256")
                or result.get("preflight_identity_sha256"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
