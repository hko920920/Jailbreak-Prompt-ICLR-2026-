from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import threading
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
MIB = 1024 * 1024
GIB = 1024 * 1024 * 1024
PRIVATE_TEXT_KEYS = {
    "prompt",
    "prompt_text",
    "response",
    "response_text",
    "stderr",
    "stdout",
}


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_object_list(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{where} must be a list of objects")
    return cast(list[JsonObject], value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def assert_safe_result(value: object, *, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PRIVATE_TEXT_KEYS:
                raise ValueError(f"private text field in safe result at {location}.{key}")
            assert_safe_result(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_safe_result(child, location=f"{location}[{index}]")


def normalized_response(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", normalized_response(value)).casefold()
    return "".join(normalized.split())


def capability_pass(response: str, required_substrings: list[str]) -> bool:
    haystack = comparison_text(response)
    return all(comparison_text(value) in haystack for value in required_substrings)


def extract_simple_io_response(stdout: str, prompt: str) -> str:
    normalized = stdout.replace("\r\n", "\n").replace("\r", "\n")
    marker_pattern = re.compile(r"(?:^|\n)>\s*" + re.escape(prompt) + r"\n")
    matches = list(marker_pattern.finditer(normalized))
    if len(matches) != 1:
        raise ValueError(f"expected one simple-io prompt marker, got {len(matches)}")
    tail = normalized[matches[0].end() :]
    timing_marker = re.search(r"\n+\[\s*Prompt:\s*[0-9.]+\s*t/s\s*\|", tail)
    if timing_marker is None:
        raise ValueError("simple-io timing boundary is missing")
    return normalized_response(tail[: timing_marker.start()])


def parse_perf(log_text: str) -> JsonObject:
    load_ms: float | None = None
    prompt_tps: float | None = None
    eval_tps: float | None = None
    eval_tokens: int | None = None
    time_pattern = re.compile(r"=\s*([0-9.]+)\s*ms")
    rate_pattern = re.compile(r"([0-9.]+)\s*tokens per second")
    run_pattern = re.compile(r"/\s*(\d+)\s*runs?")
    simple_summary = re.search(
        r"\[\s*Prompt:\s*([0-9.]+)\s*t/s\s*\|\s*Generation:\s*"
        r"([0-9.]+)\s*t/s\s*\]",
        log_text,
    )
    if simple_summary:
        prompt_tps = float(simple_summary.group(1))
        eval_tps = float(simple_summary.group(2))
    for line in log_text.splitlines():
        folded = line.casefold()
        if "load time" in folded:
            match = time_pattern.search(line)
            if match:
                load_ms = float(match.group(1))
        elif "prompt eval time" in folded:
            match = rate_pattern.search(line)
            if match:
                prompt_tps = float(match.group(1))
        elif "eval time" in folded:
            rate_match = rate_pattern.search(line)
            run_match = run_pattern.search(line)
            if rate_match:
                eval_tps = float(rate_match.group(1))
            if run_match:
                eval_tokens = int(run_match.group(1))
    return {
        "load_ms": load_ms,
        "prompt_tokens_per_second": prompt_tps,
        "decode_tokens_per_second": eval_tps,
        "decode_token_runs": eval_tokens,
    }


def validate_contract(root: Path, config_path: Path, contract: JsonObject) -> None:
    if contract.get("status") != "FROZEN_BEFORE_ANY_P2_MODEL_GENERATION":
        raise ValueError("unexpected P2 contract status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("P2 contract must be frozen and non-paper-valid")
    scope = as_object(contract["scope_boundary"], where="scope_boundary")
    if any(value is not False for value in scope.values()):
        raise ValueError("P2 scope opens a prohibited outcome boundary")
    predecessor = as_object(contract["predecessor"], where="predecessor")
    predecessor_value = load_object(root / str(predecessor["path"]))
    if predecessor_value.get("status") != predecessor["required_status"]:
        raise ValueError("P1 predecessor status mismatch")
    if (
        predecessor_value.get("result_identity_sha256")
        != predecessor["required_result_identity_sha256"]
    ):
        raise ValueError("P1 predecessor identity mismatch")
    models = as_object_list(contract["models"], where="models")
    prompts = as_object_list(contract["harmless_prompts"], where="harmless_prompts")
    gate = as_object(contract["gate"], where="gate")
    if len(models) != int(gate["required_models"]):
        raise ValueError("P2 model count does not match the gate")
    if len(prompts) != int(gate["required_unique_harmless_prompts_per_model"]):
        raise ValueError("P2 harmless prompt count does not match the gate")
    prompt_ids = [str(prompt["prompt_id"]) for prompt in prompts]
    if len(set(prompt_ids)) != len(prompt_ids):
        raise ValueError("P2 prompt ids must be unique")
    determinism = as_object(contract["determinism_check"], where="determinism_check")
    if determinism["prompt_id"] not in prompt_ids:
        raise ValueError("determinism prompt is not in the harmless prompt set")
    for model in models:
        revision = str(model["runtime_revision"])
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"mutable model revision: {model['model_id']}")
        files = as_object_list(model["files"], where=f"{model['model_id']}.files")
        for file_spec in files:
            if not re.fullmatch(r"[0-9a-f]{64}", str(file_spec["sha256"])):
                raise ValueError(f"invalid model digest: {file_spec['filename']}")
    if not config_path.is_file():
        raise ValueError("P2 config is missing")


def sibling_metadata(sibling: object) -> JsonObject:
    entry = cast(Any, sibling)
    name = str(entry.rfilename)
    size = getattr(entry, "size", None)
    digest: str | None = None
    lfs = getattr(sibling, "lfs", None)
    if isinstance(lfs, dict):
        size = lfs.get("size", size)
        raw_digest = lfs.get("sha256")
        digest = str(raw_digest) if raw_digest is not None else None
    elif lfs is not None:
        size = getattr(lfs, "size", size)
        raw_digest = getattr(lfs, "sha256", None)
        digest = str(raw_digest) if raw_digest is not None else None
    return {"filename": name, "size_bytes": size, "sha256": digest}


def prepare_models(contract: JsonObject, artifact_root: Path) -> list[JsonObject]:
    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN", "").strip() or None
    api = HfApi(token=token)
    prepared: list[JsonObject] = []
    cache_dir = artifact_root / "hf-cache"
    for model in as_object_list(contract["models"], where="models"):
        model_id = str(model["model_id"])
        repository = str(model["runtime_repository"])
        revision = str(model["runtime_revision"])
        print(f"P2_PREPARE_REMOTE {model_id}", flush=True)
        info = api.model_info(
            repository,
            revision=revision,
            files_metadata=True,
            token=token,
        )
        if str(info.sha) != revision:
            raise ValueError(f"remote revision mismatch: {model_id}")
        remote_files = {
            str(cast(Any, sibling).rfilename): sibling_metadata(sibling)
            for sibling in info.siblings or ()
        }
        local_dir = artifact_root / str(model["local_subdirectory"])
        local_files: list[JsonObject] = []
        for file_spec in as_object_list(model["files"], where=f"{model_id}.files"):
            filename = str(file_spec["filename"])
            if filename not in remote_files:
                raise ValueError(f"remote file missing: {repository}/{filename}")
            remote = remote_files[filename]
            if remote.get("size_bytes") != file_spec["size_bytes"]:
                raise ValueError(f"remote file size mismatch: {filename}")
            if remote.get("sha256") != file_spec["sha256"]:
                raise ValueError(f"remote LFS digest mismatch: {filename}")
            print(f"P2_DOWNLOAD {model_id} {filename}", flush=True)
            path = Path(
                hf_hub_download(
                    repo_id=repository,
                    revision=revision,
                    filename=filename,
                    cache_dir=cache_dir,
                    local_dir=local_dir,
                    token=token,
                )
            )
            observed_size = path.stat().st_size
            if observed_size != int(file_spec["size_bytes"]):
                raise ValueError(f"downloaded file size mismatch: {filename}")
            observed_digest = sha256_file(path)
            if observed_digest != file_spec["sha256"]:
                raise ValueError(f"downloaded file digest mismatch: {filename}")
            local_files.append(
                {
                    "filename": filename,
                    "path": str(path.resolve()),
                    "size_bytes": observed_size,
                    "sha256": observed_digest,
                }
            )
            print(f"P2_HASH_PASS {model_id} {filename}", flush=True)
        entry_path = local_dir / str(model["entry_file"])
        if not entry_path.is_file():
            raise ValueError(f"model entry file missing: {entry_path}")
        prepared.append(
            {
                "model_id": model_id,
                "runtime_repository": repository,
                "runtime_revision": revision,
                "entry_path": str(entry_path.resolve()),
                "files": local_files,
            }
        )
    return prepared


def run_command(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=creationflags,
    )


def validate_runtime(contract: JsonObject, artifact_root: Path) -> JsonObject:
    runtime = as_object(contract["runtime"], where="runtime")
    archive = artifact_root / str(runtime["archive_relative_path"])
    cli = artifact_root / str(runtime["cli_relative_path"])
    if not archive.is_file() or not cli.is_file():
        raise FileNotFoundError("pinned llama.cpp runtime archive or CLI is missing")
    if archive.stat().st_size != int(runtime["asset_size_bytes"]):
        raise ValueError("llama.cpp archive size mismatch")
    if sha256_file(archive) != runtime["asset_sha256"]:
        raise ValueError("llama.cpp archive SHA-256 mismatch")
    version_run = run_command([str(cli), "--version"])
    version_text = version_run.stdout + version_run.stderr
    for required in cast(list[str], runtime["required_version_substrings"]):
        if required not in version_text:
            raise ValueError(f"llama.cpp version output missing: {required}")
    devices_run = run_command([str(cli), "--list-devices"])
    device_text = devices_run.stdout + devices_run.stderr
    machine_floor = as_object(contract["machine_floor"], where="machine_floor")
    required_name = str(machine_floor["required_gpu_name"])
    matches: list[str] = []
    for line in device_text.splitlines():
        match = re.match(r"\s*(Vulkan\d+):\s*(.+?)\s*\(", line)
        if match and match.group(2).strip() == required_name:
            matches.append(match.group(1))
    if len(matches) != 1:
        raise ValueError(f"expected one exact Vulkan device match, got {matches}")
    return {
        "archive_path": str(archive.resolve()),
        "archive_sha256": runtime["asset_sha256"],
        "cli_path": str(cli.resolve()),
        "cli_sha256": sha256_file(cli),
        "version_sha256": sha256_bytes(version_text.encode("utf-8")),
        "device_listing_sha256": sha256_bytes(device_text.encode("utf-8")),
        "selected_device": matches[0],
        "selected_device_name": required_name,
    }


def nvidia_rows() -> list[JsonObject]:
    query = (
        "index,name,driver_version,memory.total,memory.used,memory.free,"
        "temperature.gpu,utilization.gpu,power.draw"
    )
    completed = run_command(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("nvidia-smi query failed")
    rows: list[JsonObject] = []
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 9:
            continue
        rows.append(
            {
                "index": int(fields[0]),
                "name": fields[1],
                "driver_version": fields[2],
                "memory_total_mib": float(fields[3]),
                "memory_used_mib": float(fields[4]),
                "memory_free_mib": float(fields[5]),
                "temperature_c": float(fields[6]),
                "utilization_percent": float(fields[7]),
                "power_w": float(fields[8]),
            }
        )
    return rows


def machine_inventory(contract: JsonObject, artifact_root: Path) -> JsonObject:
    import psutil

    floor = as_object(contract["machine_floor"], where="machine_floor")
    required_name = str(floor["required_gpu_name"])
    matches = [row for row in nvidia_rows() if row["name"] == required_name]
    if len(matches) != 1:
        raise ValueError("required NVIDIA GPU not found exactly once")
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(artifact_root)
    gpu = matches[0]
    checks = {
        "gpu_name_matches": gpu["name"] == required_name,
        "vram_floor_met": gpu["memory_total_mib"] >= float(floor["minimum_total_vram_mib"]),
        "system_ram_floor_met": memory.total / GIB >= float(floor["minimum_system_ram_gib"]),
        "disk_floor_met": disk.free / GIB >= float(floor["minimum_free_disk_before_download_gib"]),
        "temperature_below_ceiling": gpu["temperature_c"]
        < float(floor["maximum_gpu_temperature_c"]),
    }
    return {
        "gpu": gpu,
        "system_ram_gib": round(memory.total / GIB, 3),
        "system_ram_available_gib": round(memory.available / GIB, 3),
        "disk_free_gib": round(disk.free / GIB, 3),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "checks": checks,
    }


def build_cli_command(
    cli_path: Path,
    model_path: Path,
    prompt: str,
    generation: JsonObject,
    device: str,
) -> list[str]:
    return [
        str(cli_path),
        "--model",
        str(model_path),
        "--device",
        device,
        "--split-mode",
        str(generation["split_mode"]),
        "--main-gpu",
        "0",
        "--gpu-layers",
        str(generation["gpu_layers"]),
        "--fit",
        str(generation["fit"]),
        "--ctx-size",
        str(generation["context_tokens"]),
        "--threads",
        str(generation["threads"]),
        "--threads-batch",
        str(generation["threads_batch"]),
        "--batch-size",
        str(generation["batch_size"]),
        "--ubatch-size",
        str(generation["ubatch_size"]),
        "--seed",
        str(generation["seed"]),
        "--temperature",
        str(generation["temperature"]),
        "--top-k",
        str(generation["top_k"]),
        "--top-p",
        str(generation["top_p"]),
        "--min-p",
        str(generation["min_p"]),
        "--predict",
        str(generation["maximum_new_tokens"]),
        "--conversation",
        "--single-turn",
        "--jinja",
        "--no-display-prompt",
        "--simple-io",
        "--color",
        "off",
        "--log-colors",
        "off",
        "--verbose",
        "--prompt",
        prompt,
    ]


def sample_machine(
    stop: threading.Event,
    required_gpu_name: str,
    samples: list[JsonObject],
) -> None:
    import psutil

    while not stop.is_set():
        try:
            matches = [row for row in nvidia_rows() if row["name"] == required_gpu_name]
            if len(matches) == 1:
                row = dict(matches[0])
                memory = psutil.virtual_memory()
                row["system_ram_used_gib"] = memory.used / GIB
                row["system_ram_available_gib"] = memory.available / GIB
                row["sample_monotonic_s"] = time.monotonic()
                samples.append(row)
        except Exception:  # noqa: BLE001 - a failed sample does not hide process status.
            pass
        stop.wait(0.25)


def execute_cli(
    command: list[str],
    *,
    prompt: str,
    timeout_seconds: int,
    required_gpu_name: str,
) -> JsonObject:
    samples: list[JsonObject] = []
    stop = threading.Event()
    sampler = threading.Thread(
        target=sample_machine,
        args=(stop, required_gpu_name, samples),
        daemon=True,
    )
    sampler.start()
    start = time.monotonic()
    error_type: str | None = None
    try:
        completed = run_command(command, timeout=timeout_seconds)
        return_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        return_code = None
        error_type = type(exc).__name__
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
    finally:
        elapsed = time.monotonic() - start
        stop.set()
        sampler.join(timeout=5)
    log_text = stdout + "\n" + stderr
    perf = parse_perf(log_text)
    response_extraction_error: str | None = None
    try:
        response = extract_simple_io_response(stdout, prompt)
    except ValueError as exc:
        response = ""
        response_extraction_error = type(exc).__name__
    used_values = [float(row["memory_used_mib"]) for row in samples]
    temperature_values = [float(row["temperature_c"]) for row in samples]
    ram_values = [float(row["system_ram_used_gib"]) for row in samples]
    baseline_gpu = used_values[0] if used_values else None
    peak_gpu = max(used_values) if used_values else None
    return {
        "return_code": return_code,
        "error_type": error_type,
        "elapsed_seconds": elapsed,
        "stdout": stdout,
        "stderr": stderr,
        "response": response,
        "response_extraction_error": response_extraction_error,
        "performance": perf,
        "sampling": {
            "sample_count": len(samples),
            "baseline_gpu_memory_used_mib": baseline_gpu,
            "peak_gpu_memory_used_mib": peak_gpu,
            "gpu_memory_delta_mib": (
                peak_gpu - baseline_gpu
                if peak_gpu is not None and baseline_gpu is not None
                else None
            ),
            "peak_gpu_temperature_c": max(temperature_values)
            if temperature_values
            else None,
            "peak_system_ram_used_gib": max(ram_values) if ram_values else None,
        },
        "chat_template_active": "chat template" in log_text.casefold(),
        "gpu_offload_logged": "offload" in log_text.casefold(),
    }


def invocation_identity(
    *,
    contract_sha256: str,
    runtime_revision: str,
    runner_sha256: str,
    model: JsonObject,
    prompt_id: str,
    seed: int,
    replicate_index: int,
    generation: JsonObject,
) -> JsonObject:
    files = as_object_list(model["files"], where=f"{model['model_id']}.files")
    return {
        "contract_sha256": contract_sha256,
        "runtime_revision": runtime_revision,
        "runner_sha256": runner_sha256,
        "model_id": model["model_id"],
        "model_file_sha256s": [str(item["sha256"]) for item in files],
        "prompt_id": prompt_id,
        "seed": seed,
        "replicate_index": replicate_index,
        "generation_parameters": generation,
    }


def load_or_execute_record(
    record_path: Path,
    identity: JsonObject,
    executor: Callable[[], JsonObject] | None,
) -> tuple[JsonObject, bool]:
    identity_sha256 = canonical_sha256(identity)
    if record_path.is_file():
        record = load_object(record_path)
        if record.get("execution_identity_sha256") != identity_sha256:
            raise ValueError(f"cached invocation identity conflict: {record_path}")
        return record, True
    if executor is None:
        raise FileNotFoundError(f"resume record missing: {record_path}")
    record = executor()
    record["execution_identity"] = identity
    record["execution_identity_sha256"] = identity_sha256
    atomic_write_json(record_path, record)
    return record, False


def safe_invocation(record: JsonObject, capability_ok: bool) -> JsonObject:
    response = str(record.get("response", ""))
    stdout = str(record.get("stdout", ""))
    stderr = str(record.get("stderr", ""))
    identity = as_object(record["execution_identity"], where="execution_identity")
    return {
        "execution_identity_sha256": record["execution_identity_sha256"],
        "prompt_id": identity["prompt_id"],
        "replicate_index": identity["replicate_index"],
        "return_code": record.get("return_code"),
        "error_type": record.get("error_type"),
        "response_extraction_error": record.get("response_extraction_error"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "response_sha256": sha256_bytes(normalized_response(response).encode("utf-8")),
        "response_utf8_bytes": len(response.encode("utf-8")),
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
        "capability_pass": capability_ok,
        "performance": record.get("performance"),
        "sampling": record.get("sampling"),
        "chat_template_active": record.get("chat_template_active"),
        "gpu_offload_logged": record.get("gpu_offload_logged"),
    }


def summarize_model(
    model: JsonObject,
    records: list[tuple[JsonObject, JsonObject, bool]],
    gate: JsonObject,
    determinism_prompt: str,
) -> JsonObject:
    safe_rows: list[JsonObject] = []
    capability_by_prompt: dict[str, bool] = {}
    deterministic_hashes: list[str] = []
    decode_rates: list[float] = []
    load_times: list[float] = []
    peak_vram: list[float] = []
    peak_temperatures: list[float] = []
    gpu_deltas: list[float] = []
    for prompt, record, _cache_hit in records:
        required = cast(list[str], prompt["required_normalized_substrings"])
        response = str(record.get("response", ""))
        prompt_echo = comparison_text(str(prompt["text"])) in comparison_text(response)
        capability_ok = capability_pass(response, required) and not prompt_echo
        row = safe_invocation(record, capability_ok)
        row["prompt_echo_detected"] = prompt_echo
        safe_rows.append(row)
        identity = as_object(record["execution_identity"], where="execution_identity")
        prompt_id = str(identity["prompt_id"])
        if int(identity["replicate_index"]) == 0:
            capability_by_prompt[prompt_id] = capability_ok
        if prompt_id == determinism_prompt:
            deterministic_hashes.append(str(row["response_sha256"]))
        perf = as_object(record["performance"], where="performance")
        if isinstance(perf.get("decode_tokens_per_second"), (int, float)):
            decode_rates.append(float(perf["decode_tokens_per_second"]))
        if isinstance(perf.get("load_ms"), (int, float)):
            load_times.append(float(perf["load_ms"]))
        sampling = as_object(record["sampling"], where="sampling")
        for key, target in (
            ("peak_gpu_memory_used_mib", peak_vram),
            ("peak_gpu_temperature_c", peak_temperatures),
            ("gpu_memory_delta_mib", gpu_deltas),
        ):
            if isinstance(sampling.get(key), (int, float)):
                target.append(float(sampling[key]))
    successful = sum(
        row["return_code"] == 0
        and row["error_type"] is None
        and row["response_extraction_error"] is None
        for row in safe_rows
    )
    capability_count = sum(capability_by_prompt.values())
    median_tps = statistics.median(decode_rates) if decode_rates else None
    median_load_ms = statistics.median(load_times) if load_times else None
    elapsed_times = [
        float(row["elapsed_seconds"])
        for row in safe_rows
        if isinstance(row.get("elapsed_seconds"), (int, float))
    ]
    median_cold_elapsed = statistics.median(elapsed_times) if elapsed_times else None
    maximum_vram = max(peak_vram) if peak_vram else None
    maximum_temperature = max(peak_temperatures) if peak_temperatures else None
    maximum_gpu_delta = max(gpu_deltas) if gpu_deltas else None
    deterministic = (
        len(deterministic_hashes) == 2 and len(set(deterministic_hashes)) == 1
    )
    checks = {
        "all_generations_succeeded": successful
        >= int(gate["minimum_successful_generations_per_model"]),
        "capability_floor_met": capability_count
        >= int(gate["minimum_capability_passes_per_model"]),
        "decode_rate_floor_met": median_tps is not None
        and median_tps >= float(gate["minimum_median_decode_tokens_per_second"]),
        "vram_ceiling_met": maximum_vram is not None
        and maximum_vram <= float(gate["maximum_peak_vram_mib"]),
        "temperature_ceiling_met": maximum_temperature is not None
        and maximum_temperature <= float(gate["maximum_gpu_temperature_c"]),
        "chat_template_active": all(bool(row["chat_template_active"]) for row in safe_rows),
        "gpu_offload_active": maximum_gpu_delta is not None
        and maximum_gpu_delta >= 1024.0,
        "deterministic_replay": deterministic,
        "no_prompt_echo": all(not bool(row["prompt_echo_detected"]) for row in safe_rows),
    }
    return {
        "model_id": model["model_id"],
        "runtime_repository": model["runtime_repository"],
        "runtime_revision": model["runtime_revision"],
        "license": model["license"],
        "quantization": model["quantization"],
        "runtime_authority": model["runtime_authority"],
        "model_files": [
            {
                "filename": item["filename"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in as_object_list(model["files"], where="model.files")
        ],
        "successful_generation_count": successful,
        "capability_pass_count": capability_count,
        "capability_prompt_count": len(capability_by_prompt),
        "deterministic_replay": deterministic,
        "median_load_milliseconds": median_load_ms,
        "median_cold_process_seconds": median_cold_elapsed,
        "median_decode_tokens_per_second": median_tps,
        "projected_512_token_seconds": (
            median_load_ms / 1000.0 + 512.0 / median_tps
            if median_load_ms is not None and median_tps is not None and median_tps > 0
            else None
        ),
        "maximum_peak_vram_mib": maximum_vram,
        "maximum_gpu_memory_delta_mib": maximum_gpu_delta,
        "maximum_gpu_temperature_c": maximum_temperature,
        "checks": checks,
        "invocations": safe_rows,
    }


def run(
    root: Path,
    config_path: Path,
    artifact_root: Path,
    safe_output: Path,
    *,
    prepare_only: bool,
) -> JsonObject:
    contract = load_object(config_path)
    validate_contract(root, config_path, contract)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact_resolved = artifact_root.resolve()
    artifact_resolved.relative_to((root / "artifacts").resolve())
    contract_sha256 = sha256_file(config_path)
    runner_sha256 = sha256_file(Path(__file__).resolve())
    machine = machine_inventory(contract, artifact_root)
    if not all(as_object(machine["checks"], where="machine.checks").values()):
        raise RuntimeError("P2 machine floor failed")
    runtime = validate_runtime(contract, artifact_root)
    prepared_models = prepare_models(contract, artifact_root)
    if prepare_only:
        return {
            "status": "P2_LOCAL_Q4_ARTIFACT_PREPARATION_PASS",
            "contract_sha256": contract_sha256,
            "runner_sha256": runner_sha256,
            "runtime_cli_sha256": runtime["cli_sha256"],
            "model_count": len(prepared_models),
            "model_files_verified": sum(len(item["files"]) for item in prepared_models),
            "model_inference_performed": False,
        }
    generation = as_object(contract["generation"], where="generation")
    gate = as_object(contract["gate"], where="gate")
    runtime_contract = as_object(contract["runtime"], where="runtime")
    cli_path = Path(str(runtime["cli_path"]))
    required_gpu_name = str(runtime["selected_device_name"])
    device = str(runtime["selected_device"])
    prompts = as_object_list(contract["harmless_prompts"], where="harmless_prompts")
    prompt_by_id = {str(prompt["prompt_id"]): prompt for prompt in prompts}
    determinism = as_object(contract["determinism_check"], where="determinism_check")
    determinism_prompt = str(determinism["prompt_id"])
    repetitions = int(determinism["independent_process_repetitions"])
    private_dir = artifact_root / str(
        as_object(contract["recording"], where="recording")["private_relative_directory"]
    )
    prepared_by_id = {str(item["model_id"]): item for item in prepared_models}
    model_summaries: list[JsonObject] = []
    resume_checks: list[bool] = []
    for model in as_object_list(contract["models"], where="models"):
        model_id = str(model["model_id"])
        model_path = Path(str(prepared_by_id[model_id]["entry_path"]))
        collected: list[tuple[JsonObject, JsonObject, bool]] = []
        run_plan: list[tuple[JsonObject, int]] = [(prompt, 0) for prompt in prompts]
        for replicate_index in range(1, repetitions):
            run_plan.append((prompt_by_id[determinism_prompt], replicate_index))
        for prompt, replicate_index in run_plan:
            prompt_id = str(prompt["prompt_id"])
            prompt_text = str(prompt["text"])
            identity = invocation_identity(
                contract_sha256=contract_sha256,
                runtime_revision=str(runtime_contract["revision"]),
                runner_sha256=runner_sha256,
                model=model,
                prompt_id=prompt_id,
                seed=int(generation["seed"]),
                replicate_index=replicate_index,
                generation=generation,
            )
            identity_sha256 = canonical_sha256(identity)
            record_path = private_dir / model_id / f"{identity_sha256}.json"
            command = build_cli_command(
                cli_path,
                model_path,
                prompt_text,
                generation,
                device,
            )
            print(f"P2_GENERATE {model_id} {prompt_id} r{replicate_index}", flush=True)
            record, cache_hit = load_or_execute_record(
                record_path,
                identity,
                lambda command=command, prompt_text=prompt_text: execute_cli(
                    command,
                    prompt=prompt_text,
                    timeout_seconds=int(generation["timeout_seconds_per_generation"]),
                    required_gpu_name=required_gpu_name,
                ),
            )
            collected.append((prompt, record, cache_hit))
        first_prompt, first_record, _ = collected[0]
        first_identity = as_object(first_record["execution_identity"], where="execution_identity")
        first_path = private_dir / model_id / (
            f"{first_record['execution_identity_sha256']}.json"
        )
        replay_record, replay_hit = load_or_execute_record(first_path, first_identity, None)
        resume_checks.append(
            replay_hit
            and replay_record["execution_identity_sha256"]
            == first_record["execution_identity_sha256"]
            and first_prompt["prompt_id"] == first_identity["prompt_id"]
        )
        summary = summarize_model(model, collected, gate, determinism_prompt)
        model_summaries.append(summary)
        print(
            "P2_MODEL_SUMMARY "
            f"{model_id} checks={all(as_object(summary['checks'], where='checks').values())}",
            flush=True,
        )
    overall_checks = {
        "predecessor_matches": True,
        "scope_remained_harmless": True,
        "machine_floor_passed": all(
            as_object(machine["checks"], where="machine.checks").values()
        ),
        "runtime_identity_passed": True,
        "exact_model_artifacts_passed": len(prepared_models) == int(gate["required_models"]),
        "all_model_gates_passed": all(
            all(as_object(model["checks"], where="model.checks").values())
            for model in model_summaries
        ),
        "resume_cache_replay_passed": all(resume_checks),
        "no_attack_or_topology_outcome_opened": True,
    }
    passed = all(overall_checks.values())
    result: JsonObject = {
        "schema_version": "local-q4-runtime-qualification-p2-result-v1",
        "status": (
            "P2_LOCAL_Q4_RUNTIME_QUALIFICATION_PASS"
            if passed
            else "P2_LOCAL_Q4_RUNTIME_QUALIFICATION_FAIL"
        ),
        "operational_pass": passed,
        "scientific_hypothesis_tested": False,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": contract_sha256,
        "runner_sha256": runner_sha256,
        "runtime": {
            "repository": runtime_contract["repository"],
            "release_tag": runtime_contract["release_tag"],
            "revision": runtime_contract["revision"],
            "asset": runtime_contract["asset"],
            "asset_sha256": runtime["archive_sha256"],
            "cli_sha256": runtime["cli_sha256"],
            "backend": runtime_contract["backend"],
            "selected_device": runtime["selected_device"],
            "selected_device_name": runtime["selected_device_name"],
        },
        "machine": machine,
        "models": model_summaries,
        "resume_cache_replay_by_model": resume_checks,
        "checks": overall_checks,
        "next_authorized_operation": gate["on_pass"] if passed else gate["on_fail"],
        "model_inference_performed": True,
        "harmless_prompts_only": True,
        "attack_template_used": False,
        "attack_success_observed": False,
        "topology_outcome_observed": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "raw_harmful_payload_or_response_recorded": False,
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_safe_result(result)
    atomic_write_json(safe_output, result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run harmless two-model local Q4 P2 qualification")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "local_q4_runtime_qualification_p2_v1.json"
        ),
    )
    value.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/p2_runtime_qualification_v1"),
    )
    value.add_argument("--safe-output", type=Path)
    value.add_argument("--prepare-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (root / args.config).resolve() if not args.config.is_absolute() else args.config
    artifact_root = (
        (root / args.artifact_root).resolve()
        if not args.artifact_root.is_absolute()
        else args.artifact_root.resolve()
    )
    contract = load_object(config_path)
    recording = as_object(contract["recording"], where="recording")
    safe_output = (
        args.safe_output.resolve()
        if args.safe_output
        else (root / str(recording["safe_result_path"])).resolve()
    )
    result = run(
        root,
        config_path,
        artifact_root,
        safe_output,
        prepare_only=args.prepare_only,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result.get("operational_pass"),
                "result_identity_sha256": result.get("result_identity_sha256"),
                "next_authorized_operation": result.get("next_authorized_operation"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if args.prepare_only:
        return 0
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
