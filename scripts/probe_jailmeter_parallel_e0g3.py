from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from jbspan.evaluator_parallel_probe import exact_output_matches, select_parallel_probe
from jbspan.gate1.util import canonical_json_sha256

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("freeze", "preflight", "run"))
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/jailmeter_parallel_probe_e0g3_v1.json"),
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
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
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


def repo_module(root: Path, name: str) -> Any:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return importlib.import_module(name)


def load_config(root: Path, config_path: Path) -> tuple[Path, JsonObject, JsonObject]:
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_object(config_path)
    if config.get("schema_version") != "jbspan-e0g3-jailmeter-parallel-equivalence-probe-v1":
        raise ValueError("unsupported E0G-3 contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-3 must remain frozen and non-paper-valid")
    protected = required_mapping(config["protected_boundaries"], where="protected_boundaries")
    if any(protected.values()):
        raise ValueError("E0G-3 protected boundaries must remain false")

    parent = required_mapping(config["parent_sentinel"], where="parent_sentinel")
    for prefix in ("contract", "selection_manifest", "result"):
        verify_file(
            root / str(parent[f"{prefix}_path"]),
            bytes_=parent[f"{prefix}_bytes"],
            sha256=parent[f"{prefix}_sha256"],
        )
    parent_result = load_object(root / str(parent["result_path"]))
    if (
        parent_result.get("status") != parent["required_status"]
        or parent_result.get("result_identity_sha256") != parent["result_identity_sha256"]
    ):
        raise ValueError("E0G-2 sentinel result identity/status mismatch")
    parent_selection = load_object(root / str(parent["selection_manifest_path"]))
    if parent_selection.get("selection_identity_sha256") != parent["selection_identity_sha256"]:
        raise ValueError("E0G-2 sentinel selection identity mismatch")

    reference = required_mapping(config["sequential_reference"], where="sequential_reference")
    for prefix in ("axis", "summary"):
        verify_file(
            root / str(reference[f"{prefix}_path"]),
            bytes_=reference[f"{prefix}_bytes"],
            sha256=reference[f"{prefix}_sha256"],
        )
    summary = load_object(root / str(reference["summary_path"]))
    if (
        summary.get("axis_identity_sha256") != reference["axis_identity_sha256"]
        or summary.get("record_count") != reference["records"]
    ):
        raise ValueError("sequential JailMeter reference identity mismatch")

    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    _, parent_config = sentinel.load_config(root, root / str(parent["contract_path"]))
    return config_path, config, parent_config


def freeze_selection(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    selection_path = root / str(recording["selection_path"])
    manifest_path = root / str(recording["selection_manifest_path"])
    if selection_path.exists() or manifest_path.exists():
        if not selection_path.exists() or not manifest_path.exists():
            raise ValueError("partial E0G-3 frozen selection exists")
        existing_manifest = load_object(manifest_path)
        if (
            existing_manifest.get("contract_sha256") != file_sha256(config_path)
            or existing_manifest.get("selection_file_sha256") != file_sha256(selection_path)
        ):
            raise ValueError("existing E0G-3 selection identity mismatch")
        return existing_manifest

    reference = required_mapping(config["sequential_reference"], where="sequential_reference")
    candidates = load_jsonl(root / str(reference["axis_path"]))
    selection = required_mapping(config["selection"], where="selection")
    selected = select_parallel_probe(
        candidates,
        seed=str(selection["seed"]),
        stress_records=int(selection["longest_observed_records"]),
        hash_ranked_records=int(selection["deterministic_remainder_records"]),
    )
    output_fields = (
        "record_id",
        "selection_order",
        "selection_stratum",
        "selection_score",
        "combined_observed_tokens",
        "input_sha256",
        "input_tokens",
        "output_sha256",
        "output_characters",
        "output_tokens",
        "output_limit_stop",
        "label",
        "label_match_count",
        "inference_seconds",
    )
    safe_rows = [{field: row[field] for field in output_fields} for row in selected]
    if len(safe_rows) != int(selection["records"]):
        raise ValueError("E0G-3 selection denominator mismatch")
    safe_write_jsonl(selection_path, safe_rows)

    parent_runtime = required_mapping(
        parent_config["jailmeter_runtime"], where="parent jailmeter_runtime"
    )
    runtime = required_mapping(config["runtime_overrides"], where="runtime_overrides")
    required_per_slot = max(
        int(row["input_tokens"]) + int(parent_runtime["max_new_tokens"])
        for row in safe_rows
    )
    if required_per_slot > int(runtime["context_tokens_per_slot"]):
        raise ValueError("frozen E0G-3 selection exceeds per-slot context capacity")
    counts = Counter(str(row["selection_stratum"]) for row in safe_rows)
    manifest: JsonObject = {
        "schema_version": "jbspan-e0g3-parallel-probe-selection-manifest-v1",
        "status": "E0G3_PARALLEL_PROBE_SELECTION_FROZEN",
        "contract_sha256": file_sha256(config_path),
        "sequential_axis_identity_sha256": reference["axis_identity_sha256"],
        "selection_file": selection_path.relative_to(root).as_posix(),
        "selection_file_bytes": selection_path.stat().st_size,
        "selection_file_sha256": file_sha256(selection_path),
        "record_count": len(safe_rows),
        "stratum_counts": dict(sorted(counts.items())),
        "maximum_observed_input_tokens": max(int(row["input_tokens"]) for row in safe_rows),
        "maximum_observed_output_tokens": max(int(row["output_tokens"]) for row in safe_rows),
        "maximum_required_tokens_per_slot": required_per_slot,
        "context_tokens_per_slot": runtime["context_tokens_per_slot"],
        "parallel_model_output_observed": False,
        "raw_text_read": False,
        "raw_text_written": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    manifest["selection_identity_sha256"] = canonical_json_sha256(manifest)
    safe_write(manifest_path, manifest)
    return manifest


def reconstructed_records(
    root: Path, config: Mapping[str, Any], parent_config: Mapping[str, Any]
) -> list[Any]:
    recording = required_mapping(config["recording"], where="recording")
    selected = load_jsonl(root / str(recording["selection_path"]))
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    candidates = sentinel.reconstruct_selected(root, parent_config)
    index = {str(record.record_id): record for record in candidates}
    records: list[Any] = []
    for row in selected:
        record = index.get(str(row["record_id"]))
        if record is None:
            raise ValueError("E0G-3 record missing from frozen E0G-2 selection")
        records.append(record)
    return records


def rendered_prompts(
    root: Path,
    config: Mapping[str, Any],
    parent_config: Mapping[str, Any],
) -> tuple[list[JsonObject], str]:
    from transformers import AutoTokenizer

    recording = required_mapping(config["recording"], where="recording")
    selected = load_jsonl(root / str(recording["selection_path"]))
    expected = {str(row["record_id"]): row for row in selected}
    runtime = required_mapping(
        parent_config["jailmeter_runtime"], where="parent jailmeter_runtime"
    )
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        root / str(runtime["base_metadata_local_path"]),
        local_files_only=True,
        trust_remote_code=True,
    )
    system_prompt = sentinel.extract_system_prompt(root / str(runtime["runner_path"]))
    rows: list[JsonObject] = []
    for record in reconstructed_records(root, config, parent_config):
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
            raise ValueError("tokenizer returned an invalid E0G-3 prompt")
        input_sha256 = hashlib.sha256(rendered.encode()).hexdigest()
        input_tokens = len(tokenizer.encode(rendered, add_special_tokens=False))
        reference = expected[str(record.record_id)]
        if input_sha256 != reference["input_sha256"] or input_tokens != reference["input_tokens"]:
            raise ValueError("E0G-3 reconstructed prompt differs from sequential reference")
        rows.append(
            {
                "record_id": record.record_id,
                "prompt": rendered,
                "input_sha256": input_sha256,
                "input_tokens": input_tokens,
            }
        )
    return rows, system_prompt


def preflight(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    selection = freeze_selection(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    output_path = root / str(recording["preflight_path"])
    if output_path.exists():
        existing_preflight = load_object(output_path)
        if existing_preflight.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing E0G-3 preflight belongs to a different contract")
        return existing_preflight

    axes = required_mapping(parent_config["qualified_axes"], where="qualified_axes")
    jailmeter_axis = required_mapping(axes["jailmeter"], where="jailmeter axis")
    jailmeter = repo_module(root, "scripts.qualify_jailmeter_runtime_e0g1b")
    _, qualification = jailmeter.resolve_config(
        root, root / str(jailmeter_axis["contract_path"])
    )
    source_rows = jailmeter.verify_source(root, qualification)
    target_rows = jailmeter.verify_target_model(root, qualification)
    runtime_identity = jailmeter.verify_runtime(root, qualification)
    conversion = jailmeter.convert(root, root / str(jailmeter_axis["contract_path"]))
    prompt_rows, system_prompt = rendered_prompts(root, config, parent_config)

    runtime = required_mapping(config["runtime_overrides"], where="runtime_overrides")
    if int(runtime["context_tokens_total"]) // int(runtime["parallel_slots"]) != int(
        runtime["context_tokens_per_slot"]
    ):
        raise ValueError("E0G-3 total/per-slot context declaration is inconsistent")
    parent_runtime = required_mapping(
        parent_config["jailmeter_runtime"], where="parent jailmeter_runtime"
    )
    maximum_required = max(
        int(row["input_tokens"]) + int(parent_runtime["max_new_tokens"])
        for row in prompt_rows
    )
    if maximum_required > int(runtime["context_tokens_per_slot"]):
        raise ValueError("E0G-3 prompt can overflow one server slot")
    baseline_gpu = repo_module(
        root, "scripts.run_heterogeneous_panel_sentinel_e0g2"
    ).query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(runtime["maximum_prelaunch_gpu_memory_mib"]):
        raise RuntimeError(f"E0G-3 GPU baseline is uncontrolled: {baseline_gpu} MiB")

    result: JsonObject = {
        "schema_version": "jbspan-e0g3-parallel-probe-preflight-v1",
        "status": "E0G3_PARALLEL_PROBE_PREFLIGHT_PASS",
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
            "baseline_gpu_memory_mib": baseline_gpu,
        },
        "selection_identity_sha256": selection["selection_identity_sha256"],
        "records_reconstructed": len(prompt_rows),
        "maximum_required_tokens_per_slot": maximum_required,
        "context_tokens_per_slot": runtime["context_tokens_per_slot"],
        "source_files_verified": len(source_rows),
        "target_model_files_verified": len(target_rows),
        "runtime_identity": runtime_identity,
        "lora_conversion_identity_sha256": conversion["conversion_identity_sha256"],
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "raw_text_read_in_memory": True,
        "raw_text_written": False,
        "parallel_model_output_observed": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(output_path, result)
    return result


def run(root: Path, config_path: Path) -> JsonObject:
    config_path, config, parent_config = load_config(root, config_path)
    preflight_result = preflight(root, config_path)
    recording = required_mapping(config["recording"], where="recording")
    axis_path = root / str(recording["axis_path"])
    result_path = root / str(recording["result_path"])
    if axis_path.exists() or result_path.exists():
        if not axis_path.exists() or not result_path.exists():
            raise ValueError("partial E0G-3 output pair exists")
        existing_result = load_object(result_path)
        if (
            existing_result.get("contract_sha256") != file_sha256(config_path)
            or existing_result.get("axis_file_sha256") != file_sha256(axis_path)
        ):
            raise ValueError("existing E0G-3 output identity mismatch")
        return existing_result

    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    parent_runtime = required_mapping(
        parent_config["jailmeter_runtime"], where="parent jailmeter_runtime"
    )
    runtime = required_mapping(config["runtime_overrides"], where="runtime_overrides")
    selected = load_jsonl(root / str(recording["selection_path"]))
    prompts, system_prompt = rendered_prompts(root, config, parent_config)

    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(runtime["maximum_prelaunch_gpu_memory_mib"]):
        raise RuntimeError(f"E0G-3 GPU baseline is uncontrolled: {baseline_gpu} MiB")
    host = str(parent_runtime["host"])
    port = int(parent_runtime["port"])
    if not sentinel.port_is_free(host, port):
        raise ValueError(f"E0G-3 server port is occupied: {host}:{port}")
    runtime_directory = root / str(parent_runtime["runtime_directory"])
    server_path = runtime_directory / str(parent_runtime["server_relative_path"])
    command = [
        str(server_path),
        "-m",
        str(root / str(parent_runtime["target_model_path"])),
        "--lora",
        str(root / str(parent_runtime["lora_path"])),
        "--host",
        host,
        "--port",
        str(port),
        "-c",
        str(runtime["context_tokens_total"]),
        "-np",
        str(runtime["parallel_slots"]),
        "-t",
        str(parent_runtime["threads"]),
        "-ngl",
        str(parent_runtime["gpu_layers"]),
        "--offline",
        "--no-webui",
    ]
    if runtime["continuous_batching"] is True:
        command.append("-cb")

    log_handle = tempfile.NamedTemporaryFile(prefix="e0g3-jailmeter-", suffix=".log", delete=False)
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
    actual_by_id: dict[str, JsonObject] = {}
    started = time.perf_counter()
    ready_seconds: float | None = None
    request_wall_seconds: float | None = None
    failure: BaseException | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=runtime_directory,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        health_url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + float(parent_runtime["health_timeout_seconds"])
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited during startup: {process.returncode}")
            if sentinel.server_ready(health_url):
                ready_seconds = time.perf_counter() - started
                break
            time.sleep(0.25)
        if ready_seconds is None:
            raise TimeoutError("E0G-3 JailMeter server health timeout")

        def invoke(row: Mapping[str, Any]) -> JsonObject:
            call_started = time.perf_counter()
            response = sentinel.post_json(
                f"http://{host}:{port}/completion",
                {
                    "prompt": row["prompt"],
                    "n_predict": int(parent_runtime["max_new_tokens"]),
                    "temperature": float(parent_runtime["temperature"]),
                    "stream": False,
                    "cache_prompt": False,
                },
                timeout=float(parent_runtime["request_timeout_seconds"]),
            )
            content = response.get("content")
            if not isinstance(content, str):
                raise ValueError("E0G-3 JailMeter endpoint returned no text")
            parsed = sentinel.parse_jailmeter_label(content, parent_runtime)
            predicted = response.get("tokens_predicted")
            return {
                "record_id": row["record_id"],
                "input_sha256": row["input_sha256"],
                "input_tokens": row["input_tokens"],
                "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "output_characters": len(content),
                "output_tokens": predicted if isinstance(predicted, int) else None,
                "output_limit_stop": bool(response.get("stopped_limit", False)),
                "label": parsed["label"],
                "label_match_count": parsed["match_count"],
                "request_seconds": time.perf_counter() - call_started,
            }

        request_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=int(runtime["request_workers"])) as executor:
            future_to_id = {
                executor.submit(invoke, row): str(row["record_id"]) for row in prompts
            }
            for future in as_completed(future_to_id):
                row = future.result()
                actual_by_id[str(row["record_id"])] = row
        request_wall_seconds = time.perf_counter() - request_started
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
    if request_wall_seconds is None or len(actual_by_id) != len(selected):
        raise RuntimeError("E0G-3 concurrent request denominator mismatch")

    axis_rows: list[JsonObject] = []
    for reference in selected:
        record_id = str(reference["record_id"])
        actual = actual_by_id[record_id]
        matches = exact_output_matches(reference, actual)
        axis_rows.append(
            {
                **actual,
                "selection_order": reference["selection_order"],
                "selection_stratum": reference["selection_stratum"],
                "exact_reference_matches": matches,
            }
        )
    safe_write_jsonl(axis_path, axis_rows)

    match_keys = tuple(axis_rows[0]["exact_reference_matches"])
    match_fractions = {
        key: sum(bool(row["exact_reference_matches"][key]) for row in axis_rows)
        / len(axis_rows)
        for key in match_keys
    }
    parse_coverage = sum(row["label"] is not None for row in axis_rows) / len(axis_rows)
    output_limit_stops = sum(bool(row["output_limit_stop"]) for row in axis_rows)
    peak_gpu = max(gpu_samples) if gpu_samples else None
    sequential_seconds = sum(float(row["inference_seconds"]) for row in selected)
    speedup = sequential_seconds / request_wall_seconds
    gates = required_mapping(config["gates"], where="gates")
    checks = {
        "exact_input_sha256": match_fractions["input_sha256"]
        >= float(gates["exact_input_sha256_fraction"]),
        "exact_input_tokens": match_fractions["input_tokens"]
        >= float(gates["exact_input_token_fraction"]),
        "exact_output_sha256": match_fractions["output_sha256"]
        >= float(gates["exact_output_sha256_fraction"]),
        "exact_output_characters": match_fractions["output_characters"]
        >= float(gates["exact_output_character_fraction"]),
        "exact_output_tokens": match_fractions["output_tokens"]
        >= float(gates["exact_output_token_fraction"]),
        "exact_label": match_fractions["label"] >= float(gates["exact_label_fraction"]),
        "exact_label_match_count": match_fractions["label_match_count"]
        >= float(gates["exact_label_match_count_fraction"]),
        "parse_coverage": parse_coverage >= float(gates["parse_coverage_min"]),
        "no_output_limit_stops": output_limit_stops
        <= int(gates["output_limit_stops_allowed"]),
        "within_prelaunch_gpu_budget": baseline_gpu
        <= float(runtime["maximum_prelaunch_gpu_memory_mib"]),
        "within_peak_gpu_budget": peak_gpu is not None
        and peak_gpu <= float(runtime["maximum_peak_gpu_memory_mib"]),
        "within_time_budget": total_seconds <= float(runtime["maximum_total_seconds"]),
        "minimum_speedup": speedup >= float(gates["minimum_speedup_for_adoption"]),
    }
    equivalence_keys = (
        "exact_input_sha256",
        "exact_input_tokens",
        "exact_output_sha256",
        "exact_output_characters",
        "exact_output_tokens",
        "exact_label",
        "exact_label_match_count",
        "parse_coverage",
        "no_output_limit_stops",
    )
    resource_keys = (
        "within_prelaunch_gpu_budget",
        "within_peak_gpu_budget",
        "within_time_budget",
    )
    equivalence_pass = all(checks[key] for key in equivalence_keys)
    resource_pass = all(checks[key] for key in resource_keys)
    adopted = equivalence_pass and resource_pass and checks["minimum_speedup"]
    if not equivalence_pass:
        status = "E0G3_PARALLEL_IDENTITY_FAIL_DO_NOT_ADOPT"
    elif not resource_pass:
        status = "E0G3_PARALLEL_RESOURCE_FAIL_DO_NOT_ADOPT"
    elif adopted:
        status = "E0G3_PARALLEL_EQUIVALENCE_PASS_ADOPT"
    else:
        status = "E0G3_PARALLEL_EQUIVALENCE_PASS_NO_SPEEDUP_DO_NOT_ADOPT"
    result: JsonObject = {
        "schema_version": "jbspan-e0g3-jailmeter-parallel-probe-result-v1",
        "status": status,
        "evidence_class": "OPERATIONAL_EQUIVALENCE_AND_THROUGHPUT_ONLY",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "selection_identity_sha256": load_object(
            root / str(recording["selection_manifest_path"])
        )["selection_identity_sha256"],
        "record_count": len(axis_rows),
        "match_fractions": match_fractions,
        "parse_coverage": parse_coverage,
        "output_limit_stops": output_limit_stops,
        "sequential_reference_inference_seconds": sequential_seconds,
        "parallel_request_wall_seconds": request_wall_seconds,
        "request_wall_speedup": speedup,
        "server_ready_seconds": ready_seconds,
        "total_seconds": total_seconds,
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_gpu_memory_mib": peak_gpu,
        "gpu_memory_delta_mib": peak_gpu - baseline_gpu if peak_gpu is not None else None,
        "parallel_slots": runtime["parallel_slots"],
        "request_workers": runtime["request_workers"],
        "context_tokens_total": runtime["context_tokens_total"],
        "context_tokens_per_slot": runtime["context_tokens_per_slot"],
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "server_log_bytes": len(log_content),
        "server_log_sha256": log_sha256,
        "server_log_retained": False,
        "checks": checks,
        "equivalence_pass": equivalence_pass,
        "resource_pass": resource_pass,
        "parallel_execution_adopted": adopted,
        "axis_file": axis_path.relative_to(root).as_posix(),
        "axis_file_bytes": axis_path.stat().st_size,
        "axis_file_sha256": file_sha256(axis_path),
        "raw_text_written": False,
        "raw_model_output_written": False,
        "paper_valid_result": False,
        "protected_boundaries": dict(config["protected_boundaries"]),
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
    else:
        result = run(root, args.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "identity": result.get("result_identity_sha256")
                or result.get("preflight_identity_sha256")
                or result.get("selection_identity_sha256"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
