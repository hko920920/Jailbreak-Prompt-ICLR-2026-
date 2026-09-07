from __future__ import annotations

import argparse
import ast
import hashlib
import json
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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jbspan.gate1.util import canonical_json_sha256  # type: ignore[import-untyped]

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("preflight", "download", "convert", "qualify"))
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/jailmeter_runtime_e0g1b_v1.json"),
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


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def verify_record(
    root: Path,
    spec: Mapping[str, Any],
    *,
    status_key: str = "required_status",
) -> JsonObject:
    path = root / str(spec["path"])
    if not path.is_file() or path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"record size mismatch: {path}")
    if file_sha256(path) != str(spec["sha256"]):
        raise ValueError(f"record SHA-256 mismatch: {path}")
    record = load_object(path)
    if status_key in spec and record.get("status") != spec[status_key]:
        raise ValueError(f"record status mismatch: {path}")
    if (
        "required_schema_version" in spec
        and record.get("schema_version") != spec["required_schema_version"]
    ):
        raise ValueError(f"record schema mismatch: {path}")
    if "required_frozen" in spec and record.get("frozen") is not spec["required_frozen"]:
        raise ValueError(f"record frozen flag mismatch: {path}")
    if (
        "required_paper_validity" in spec
        and record.get("paper_validity") is not spec["required_paper_validity"]
    ):
        raise ValueError(f"record paper-validity flag mismatch: {path}")
    if "required_identity" in spec:
        observed = (
            record.get("result_identity_sha256")
            or record.get("conversion_identity_sha256")
            or record.get("download_identity_sha256")
            or record.get("preflight_identity_sha256")
        )
        if observed != spec["required_identity"]:
            raise ValueError(f"record identity mismatch: {path}")
    return record


def resolve_config(root: Path, config_path: Path) -> tuple[Path, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    raw_config = load_object(config_path)
    schema_version = raw_config.get("schema_version")
    if raw_config.get("frozen") is not True or raw_config.get("paper_validity") is not False:
        raise ValueError("raw E0G-1B contract must remain frozen and non-paper-valid")
    if schema_version == "jbspan-e0g1b-jailmeter-runtime-qualification-v1-2":
        parent = required_mapping(raw_config.get("parent_contract"), where="parent_contract")
        parent_path = root / str(parent["path"])
        if not parent_path.is_file() or parent_path.stat().st_size != int(parent["bytes"]):
            raise ValueError("V1.2 parent contract size mismatch")
        if file_sha256(parent_path) != str(parent["sha256"]):
            raise ValueError("V1.2 parent contract SHA-256 mismatch")
        _, config = resolve_config(root, parent_path)
        diagnosis = required_mapping(
            raw_config.get("instrumentation_diagnosis"), where="instrumentation_diagnosis"
        )
        verify_record(root, diagnosis)
        adoptions = raw_config.get("artifact_adoption")
        if not isinstance(adoptions, list) or len(adoptions) != 2:
            raise ValueError("V1.2 artifact adoption is invalid")
        for adoption in adoptions:
            verify_record(root, required_mapping(adoption, where="artifact adoption"))
        config["schema_version"] = schema_version
        config["status"] = raw_config["status"]
        config["operational_repair"] = raw_config["operational_repair"]
        runtime = dict(required_mapping(config["runtime"], where="runtime"))
        runtime.update(
            required_mapping(raw_config["runtime_overrides"], where="runtime_overrides")
        )
        config["runtime"] = runtime
        recording = dict(required_mapping(config["recording"], where="recording"))
        recording.update(
            required_mapping(raw_config["recording_overrides"], where="recording_overrides")
        )
        config["recording"] = recording
    elif schema_version == "jbspan-e0g1b-jailmeter-runtime-qualification-v1-1":
        parent = required_mapping(raw_config.get("parent_contract"), where="parent_contract")
        failure = required_mapping(
            raw_config.get("operational_failure"), where="operational_failure"
        )
        parent_path = root / str(parent["path"])
        if not parent_path.is_file() or parent_path.stat().st_size != int(parent["bytes"]):
            raise ValueError("V1.1 parent contract size mismatch")
        if file_sha256(parent_path) != str(parent["sha256"]):
            raise ValueError("V1.1 parent contract SHA-256 mismatch")
        verify_record(root, failure)
        config = load_object(parent_path)
        config["schema_version"] = schema_version
        config["status"] = raw_config["status"]
        config["operational_repair"] = raw_config["operational_repair"]
        config["historical_contract"] = raw_config["historical_contract_override"]
        recording = dict(required_mapping(config["recording"], where="recording"))
        recording.update(
            required_mapping(raw_config["recording_overrides"], where="recording_overrides")
        )
        config["recording"] = recording
    else:
        config = raw_config
    if schema_version not in {
        "jbspan-e0g1b-jailmeter-runtime-qualification-v1",
        "jbspan-e0g1b-jailmeter-runtime-qualification-v1-1",
        "jbspan-e0g1b-jailmeter-runtime-qualification-v1-2",
    }:
        raise ValueError("unsupported E0G-1B contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-1B must remain frozen and non-paper-valid")
    protected = required_mapping(config["protected_boundaries"], where="protected_boundaries")
    if any(protected.values()):
        raise ValueError("all protected-boundary observations must remain false")
    predecessor = required_mapping(config["predecessor"], where="predecessor")
    verify_record(root, predecessor)
    historical = required_mapping(config["historical_contract"], where="historical_contract")
    verify_record(root, historical)
    return config_path, config


def runtime_manifest(path: Path) -> tuple[list[JsonObject], int, str]:
    rows: list[JsonObject] = []
    for item in sorted(path.iterdir(), key=lambda value: value.name):
        if item.is_file():
            rows.append(
                {
                    "path": item.name,
                    "bytes": item.stat().st_size,
                    "sha256": file_sha256(item),
                }
            )
    total = sum(int(row["bytes"]) for row in rows)
    identity = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return rows, total, identity


def verify_source(root: Path, config: Mapping[str, Any]) -> list[JsonObject]:
    source = required_mapping(config["jailmeter_source"], where="jailmeter_source")
    source_path = root / str(source["local_path"])
    rows: list[JsonObject] = []
    raw_specs = source["files"]
    if not isinstance(raw_specs, list):
        raise ValueError("JailMeter source file list is invalid")
    for raw_spec in raw_specs:
        spec = required_mapping(raw_spec, where="jailmeter source file")
        path = source_path / str(spec["path"])
        if not path.is_file() or path.stat().st_size != int(spec["bytes"]):
            raise ValueError(f"JailMeter source size mismatch: {path}")
        sha256 = file_sha256(path)
        blob = subprocess.run(
            ["git", "-C", str(source_path), "hash-object", str(spec["path"])],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if sha256 != str(spec["sha256"]) or blob != str(spec["git_blob_sha1"]):
            raise ValueError(f"JailMeter source identity mismatch: {path}")
        rows.append(
            {
                "path": str(spec["path"]),
                "bytes": path.stat().st_size,
                "sha256": sha256,
                "git_blob_sha1": blob,
            }
        )
    revision = subprocess.run(
        ["git", "-C", str(source_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != str(source["revision"]):
        raise ValueError("JailMeter repository revision mismatch")
    return rows


def verify_target_model(root: Path, config: Mapping[str, Any]) -> list[JsonObject]:
    target = required_mapping(config["target_model"], where="target_model")
    model_path = root / str(target["local_path"])
    raw_specs = target["files"]
    if not isinstance(raw_specs, list):
        raise ValueError("target model file list is invalid")
    rows: list[JsonObject] = []
    for raw_spec in raw_specs:
        spec = required_mapping(raw_spec, where="target model file")
        path = model_path / str(spec["path"])
        if not path.is_file() or path.stat().st_size != int(spec["bytes"]):
            raise ValueError(f"target model size mismatch: {path}")
        observed = file_sha256(path)
        if observed != str(spec["sha256"]):
            raise ValueError(f"target model SHA-256 mismatch: {path}")
        rows.append(
            {"path": str(spec["path"]), "bytes": path.stat().st_size, "sha256": observed}
        )
    return rows


def verify_runtime(root: Path, config: Mapping[str, Any]) -> JsonObject:
    runtime = required_mapping(config["runtime"], where="runtime")
    qualification = {
        "path": runtime["qualification_record_path"],
        "bytes": runtime["qualification_record_bytes"],
        "sha256": runtime["qualification_record_sha256"],
        "required_status": "P2_LOCAL_Q4_RUNTIME_QUALIFICATION_PASS",
        "required_identity": runtime["qualification_record_identity"],
    }
    verify_record(root, qualification)
    runtime_path = root / str(runtime["runtime_path"])
    rows, total, identity = runtime_manifest(runtime_path)
    if len(rows) != int(runtime["runtime_file_count"]):
        raise ValueError("runtime file count mismatch")
    if total != int(runtime["runtime_total_bytes"]):
        raise ValueError("runtime byte total mismatch")
    if identity != str(runtime["runtime_manifest_sha256"]):
        raise ValueError("runtime manifest identity mismatch")
    server_path = runtime_path / str(runtime["server_relative_path"])
    if file_sha256(server_path) != str(runtime["server_sha256"]):
        raise ValueError("llama-server SHA-256 mismatch")
    return {"file_count": len(rows), "total_bytes": total, "manifest_sha256": identity}


def verify_converter(root: Path, config: Mapping[str, Any]) -> Path:
    conversion = required_mapping(config["conversion"], where="conversion")
    source_path = root / str(conversion["llama_cpp_source_path"])
    converter = source_path / str(conversion["converter_relative_path"])
    if not converter.is_file() or converter.stat().st_size != int(conversion["converter_bytes"]):
        raise ValueError("LoRA converter size mismatch")
    if file_sha256(converter) != str(conversion["converter_sha256"]):
        raise ValueError("LoRA converter SHA-256 mismatch")
    revision = subprocess.run(
        ["git", "-C", str(source_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != str(conversion["llama_cpp_revision"]):
        raise ValueError("llama.cpp source revision mismatch")
    return converter


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


def parse_label(content: str, parser_config: Mapping[str, Any]) -> JsonObject:
    matches = re.findall(str(parser_config["label_regex"]), content)
    strict = parser_config.get("require_exactly_one_label_match") is True
    label = int(matches[0]) if matches and (not strict or len(matches) == 1) else None
    return {"label": label, "match_count": len(matches)}


def existing_or_none(path: Path) -> JsonObject | None:
    return load_object(path) if path.exists() else None


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["preflight_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing preflight belongs to a different contract")
        return existing

    source_rows = verify_source(root, config)
    target_rows = verify_target_model(root, config)
    runtime_identity = verify_runtime(root, config)
    converter = verify_converter(root, config)
    conversion = required_mapping(config["conversion"], where="conversion")
    free_bytes = shutil.disk_usage(root).free
    if free_bytes < int(conversion["maximum_output_bytes"]) * 2:
        raise ValueError("insufficient free disk for LoRA conversion")
    result: JsonObject = {
        "schema_version": "jbspan-e0g1b-jailmeter-runtime-preflight-v1",
        "status": "E0G1B_JAILMETER_RUNTIME_PREFLIGHT_PASS",
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
            "free_disk_bytes": free_bytes,
            "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
        },
        "jailmeter_source_files": source_rows,
        "target_model_files": target_rows,
        "runtime": runtime_identity,
        "converter_sha256": file_sha256(converter),
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def metadata_files(path: Path, config: Mapping[str, Any]) -> tuple[list[JsonObject], int]:
    metadata = required_mapping(config["base_metadata"], where="base_metadata")
    forbidden = tuple(str(value) for value in metadata["forbidden_suffixes"])
    rows: list[JsonObject] = []
    for item in sorted(path.iterdir(), key=lambda value: value.name):
        if item.is_file():
            if item.name.endswith(forbidden):
                raise ValueError(f"forbidden weight-like base file downloaded: {item}")
            rows.append(
                {"path": item.name, "bytes": item.stat().st_size, "sha256": file_sha256(item)}
            )
    required = {"config.json", "tokenizer.json", "tokenizer_config.json"}
    observed = {str(row["path"]) for row in rows}
    if not required.issubset(observed):
        raise ValueError("required base tokenizer/config metadata is incomplete")
    total = sum(int(row["bytes"]) for row in rows)
    if total > int(metadata["maximum_downloaded_bytes"]):
        raise ValueError("base metadata byte budget exceeded")
    return rows, total


def download(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    preflight_result = preflight(root, config_path)
    metadata = required_mapping(config["base_metadata"], where="base_metadata")
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["base_metadata_manifest_path"])
    metadata_path = root / str(metadata["local_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        rows, total = metadata_files(metadata_path, config)
        if rows != existing.get("files") or total != existing.get("total_bytes"):
            raise ValueError("existing base metadata no longer matches its manifest")
        return existing

    from huggingface_hub import snapshot_download

    metadata_path.mkdir(parents=True, exist_ok=True)
    resolved = snapshot_download(
        repo_id=str(metadata["repository"]),
        revision=str(metadata["revision"]),
        allow_patterns=[str(value) for value in metadata["allow_patterns"]],
        local_dir=metadata_path,
    )
    if Path(resolved).resolve() != metadata_path.resolve():
        raise ValueError("base metadata downloaded outside the frozen directory")
    rows, total = metadata_files(metadata_path, config)
    result: JsonObject = {
        "schema_version": "jbspan-e0g1b-jailmeter-base-metadata-v1",
        "status": "E0G1B_JAILMETER_BASE_METADATA_DOWNLOAD_PASS",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "repository": metadata["repository"],
        "revision": metadata["revision"],
        "local_path": metadata["local_path"],
        "files": rows,
        "total_bytes": total,
        "weight_files_downloaded": False,
    }
    result["download_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def convert(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    metadata_result = download(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    conversion = required_mapping(config["conversion"], where="conversion")
    output_path = root / str(recording["conversion_manifest_path"])
    lora_path = root / str(conversion["output_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        if existing.get("status") != "E0G1B_JAILMETER_LORA_CONVERSION_PASS":
            return existing
        if not lora_path.is_file():
            raise ValueError("converted LoRA is missing")
        if (
            lora_path.stat().st_size != existing.get("output_bytes")
            or file_sha256(lora_path) != existing.get("output_sha256")
        ):
            raise ValueError("converted LoRA no longer matches its manifest")
        return existing

    converter = verify_converter(root, config)
    source = required_mapping(config["jailmeter_source"], where="jailmeter_source")
    source_path = root / str(source["local_path"])
    adapter_path = source_path / str(source["adapter_relative_path"])
    metadata = required_mapping(config["base_metadata"], where="base_metadata")
    base_path = root / str(metadata["local_path"])
    lora_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(converter),
        "--base",
        str(base_path),
        "--outtype",
        str(conversion["outtype"]),
        "--outfile",
        str(lora_path),
        str(adapter_path),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=converter.parent,
        capture_output=True,
        text=True,
        timeout=float(conversion["maximum_conversion_seconds"]),
        check=False,
    )
    elapsed = time.perf_counter() - started
    stdout_hash = hashlib.sha256(completed.stdout.encode()).hexdigest()
    stderr_hash = hashlib.sha256(completed.stderr.encode()).hexdigest()
    valid_size = (
        lora_path.is_file()
        and int(conversion["minimum_output_bytes"])
        <= lora_path.stat().st_size
        <= int(conversion["maximum_output_bytes"])
    )
    passed = completed.returncode == 0 and valid_size
    result: JsonObject = {
        "schema_version": "jbspan-e0g1b-jailmeter-lora-conversion-v1",
        "status": (
            "E0G1B_JAILMETER_LORA_CONVERSION_PASS"
            if passed
            else "E0G1B_JAILMETER_LORA_CONVERSION_FAIL"
        ),
        "contract_sha256": file_sha256(config_path),
        "base_metadata_identity_sha256": metadata_result["download_identity_sha256"],
        "converter_sha256": file_sha256(converter),
        "adapter_config_sha256": file_sha256(adapter_path / "adapter_config.json"),
        "adapter_model_sha256": file_sha256(adapter_path / "adapter_model.safetensors"),
        "outtype": conversion["outtype"],
        "return_code": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_sha256": stdout_hash,
        "stderr_sha256": stderr_hash,
        "raw_logs_written": False,
        "output_path": conversion["output_path"],
        "output_bytes": lora_path.stat().st_size if lora_path.is_file() else 0,
        "output_sha256": file_sha256(lora_path) if passed else None,
    }
    result["conversion_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


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


def qualify(root: Path, config_path: Path) -> JsonObject:
    config_path, config = resolve_config(root, config_path)
    conversion_result = convert(root, config_path)
    if conversion_result.get("status") != "E0G1B_JAILMETER_LORA_CONVERSION_PASS":
        raise ValueError("JailMeter LoRA conversion did not pass")
    recording = required_mapping(config["recording"], where="recording")
    runtime = required_mapping(config["runtime"], where="runtime")
    source = required_mapping(config["jailmeter_source"], where="jailmeter_source")
    target = required_mapping(config["target_model"], where="target_model")
    conversion = required_mapping(config["conversion"], where="conversion")
    parser_config = required_mapping(config["parser"], where="parser")
    gate_config = required_mapping(config["qualification_gate"], where="qualification_gate")
    output_path = root / str(recording["result_path"])
    existing = existing_or_none(output_path)
    if existing is not None:
        return existing

    from transformers import AutoTokenizer

    metadata = required_mapping(config["base_metadata"], where="base_metadata")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(metadata["local_path"]), local_files_only=True, trust_remote_code=True
    )
    runner_path = root / str(source["local_path"]) / str(source["runner_relative_path"])
    system_prompt = extract_system_prompt(runner_path)
    model_specs = target["files"]
    if not isinstance(model_specs, list) or not model_specs:
        raise ValueError("target model file contract is invalid")
    first_model = required_mapping(model_specs[0], where="first target model file")
    model_path = root / str(target["local_path"]) / str(first_model["path"])
    lora_path = root / str(conversion["output_path"])
    runtime_path = root / str(runtime["runtime_path"])
    server_path = runtime_path / str(runtime["server_relative_path"])
    host = str(runtime["host"])
    port = int(runtime["port"])
    if not port_is_free(host, port):
        raise ValueError(f"frozen qualification port is already occupied: {host}:{port}")

    cases = config["harmless_cases"]
    if not isinstance(cases, list) or len(cases) != int(gate_config["case_count"]):
        raise ValueError("harmless case denominator mismatch")
    baseline_gpu = query_gpu_memory_mib()
    maximum_prelaunch = runtime.get("maximum_prelaunch_gpu_memory_mib")
    if maximum_prelaunch is not None and (
        baseline_gpu is None or baseline_gpu > float(maximum_prelaunch)
    ):
        raise RuntimeError(
            "GPU baseline is not controlled: "
            f"observed={baseline_gpu}, maximum={maximum_prelaunch} MiB"
        )
    log_handle = tempfile.NamedTemporaryFile(prefix="e0g1b-jailmeter-", suffix=".log", delete=False)
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
    command = [
        str(server_path),
        "-m",
        str(model_path),
        "--lora",
        str(lora_path),
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
    if "log_verbosity" in runtime:
        command.extend(["-lv", str(runtime["log_verbosity"])])
    process: subprocess.Popen[bytes] | None = None
    records: list[JsonObject] = []
    raw_outputs: dict[str, list[str]] = {}
    started = time.perf_counter()
    server_ready_seconds: float | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=runtime_path,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        health_url = f"http://{host}:{port}/health"
        health_deadline = time.monotonic() + float(runtime["health_timeout_seconds"])
        while time.monotonic() < health_deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited during startup: {process.returncode}")
            if server_ready(health_url):
                server_ready_seconds = time.perf_counter() - started
                break
            time.sleep(0.25)
        if server_ready_seconds is None:
            raise TimeoutError("llama-server health timeout")

        for raw_case in cases:
            case = required_mapping(raw_case, where="harmless case")
            case_id = str(case["case_id"])
            user_content = json.dumps(
                {
                    "original_question": case["original_question"],
                    "model_response": case["model_response"],
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
            raw_outputs[case_id] = []
            for repetition in range(int(runtime["repetitions_per_case"])):
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
                raw_outputs[case_id].append(content)
                parsed = parse_label(content, parser_config)
                predicted = response.get("tokens_predicted")
                records.append(
                    {
                        "case_id": case_id,
                        "repetition": repetition,
                        "input_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                        "input_tokens": input_tokens,
                        "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "output_characters": len(content),
                        "output_tokens": predicted if isinstance(predicted, int) else None,
                        "label_match_count": parsed["match_count"],
                        "label": parsed["label"],
                        "expected_label_match": parsed["label"] == int(case["expected_label"]),
                        "output_limit_stop": bool(response.get("stopped_limit", False)),
                        "inference_seconds": time.perf_counter() - call_started,
                    }
                )
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
    log_text = log_content.decode(errors="replace")
    log_sha256 = hashlib.sha256(log_content).hexdigest()
    offload_match = re.search(
        r"offloaded\s+(\d+)/(\d+)\s+layers\s+to\s+GPU",
        log_text,
        flags=re.IGNORECASE,
    )
    gpu_offload = offload_match is not None and int(offload_match.group(1)) > 0
    log_path.unlink(missing_ok=True)
    invocation_count = len(records)
    parse_count = sum(row["label"] is not None for row in records)
    correct_count = sum(bool(row["expected_label_match"]) for row in records)
    repeated_cases = sum(len(set(raw_outputs[str(case["case_id"])])) == 1 for case in cases)
    output_limit_stops = sum(bool(row["output_limit_stop"]) for row in records)
    peak_gpu = max(gpu_samples) if gpu_samples else None
    observed: JsonObject = {
        "case_count": len(cases),
        "invocation_count": invocation_count,
        "parse_coverage": parse_count / invocation_count,
        "expected_label_accuracy": correct_count / invocation_count,
        "per_case_byte_repeatability": repeated_cases / len(cases),
        "output_limit_stops": output_limit_stops,
        "server_ready_seconds": server_ready_seconds,
        "total_qualification_seconds": total_seconds,
        "mean_inference_seconds": sum(float(row["inference_seconds"]) for row in records)
        / invocation_count,
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_gpu_memory_mib": peak_gpu,
        "gpu_memory_delta_mib": (
            peak_gpu - baseline_gpu
            if peak_gpu is not None and baseline_gpu is not None
            else None
        ),
        "gpu_offload_logged": gpu_offload,
        "offloaded_layers": int(offload_match.group(1)) if offload_match else None,
        "offloadable_layers": int(offload_match.group(2)) if offload_match else None,
    }
    checks = {
        "conversion_identity_pass": conversion_result["status"]
        == "E0G1B_JAILMETER_LORA_CONVERSION_PASS",
        "case_count": observed["case_count"] == int(gate_config["case_count"]),
        "invocation_count": observed["invocation_count"] == int(gate_config["invocation_count"]),
        "parse_coverage": observed["parse_coverage"] >= float(gate_config["parse_coverage"]),
        "expected_label_accuracy": observed["expected_label_accuracy"]
        >= float(gate_config["expected_label_accuracy"]),
        "per_case_byte_repeatability": observed["per_case_byte_repeatability"]
        >= float(gate_config["per_case_byte_repeatability"]),
        "no_output_limit_stop": output_limit_stops == 0,
        "gpu_offload": gpu_offload,
        "controlled_prelaunch_gpu_memory": maximum_prelaunch is None
        or (
            baseline_gpu is not None
            and baseline_gpu <= float(maximum_prelaunch)
        ),
        "within_time_budget": total_seconds
        <= float(runtime["maximum_total_qualification_seconds"]),
        "within_gpu_memory_budget": peak_gpu is not None
        and peak_gpu <= float(runtime["maximum_peak_gpu_memory_mib"]),
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-e0g1b-jailmeter-runtime-result-v1",
        "status": (
            "E0G1B_JAILMETER_HARMLESS_RUNTIME_PASS"
            if passed
            else "E0G1B_JAILMETER_HARMLESS_RUNTIME_FAIL"
        ),
        "evidence_class": "HARMLESS_OPERATIONAL_QUALIFICATION_NOT_SCIENTIFIC_CALIBRATION",
        "contract_sha256": file_sha256(config_path),
        "conversion_identity_sha256": conversion_result["conversion_identity_sha256"],
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "records": records,
        "observed": observed,
        "server_log": {
            "bytes": len(log_content),
            "sha256": log_sha256,
            "retained": False,
        },
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
    if args.command == "preflight":
        result = preflight(root, args.config)
    elif args.command == "download":
        result = download(root, args.config)
    elif args.command == "convert":
        result = convert(root, args.config)
    else:
        result = qualify(root, args.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "identity": result.get("result_identity_sha256")
                or result.get("conversion_identity_sha256")
                or result.get("download_identity_sha256")
                or result.get("preflight_identity_sha256"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
