from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR.parent / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from jbspan.evaluator_panel import (  # noqa: E402
    SanitizedText,
    parse_wildguard_output,
    sanitize_untrusted_text,
)
from jbspan.evaluator_panel_external_calibration import (  # noqa: E402
    CalibrationTextRecord,
    reconstruct_calibration_texts,
)
from jbspan.evaluator_panel_redesign import (  # noqa: E402
    ExistingSignalRecord,
    build_existing_signal_records,
    canonical_json_bytes,
    canonical_jsonl_bytes,
)
from jbspan.evaluator_panel_wildguard_sentinel import (  # noqa: E402
    build_sentinel_records,
    evaluate_sentinel,
    validate_candidate_specs,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f1-wildguard-sentinel-contract-v1"
EXPECTED_STATUS = "FROZEN_BEFORE_ANY_E0F1_WILDGUARD_OUTPUT"
SERVER_STARTUP_TIMEOUT_SECONDS = 240
HTTP_TIMEOUT_SECONDS = 600
HTTP_ATTEMPTS = 3
FORBIDDEN_SAFE_KEYS = {
    "human_label",
    "question_text",
    "response_text",
    "human_request",
    "assistant_response",
    "classifier_input",
    "raw_output",
    "input_token_ids",
}


@dataclass(frozen=True, slots=True)
class ScientificPlanRecord:
    safe: JsonObject
    question: str
    response: str
    classifier_input: str


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    subcommands = value.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        command = subcommands.add_parser(name)
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument(
            "--contract",
            type=Path,
            default=Path("configs/evaluator_panel/calibration_redesign_e0f1_sentinel_v1.json"),
        )
    return value


def rooted(root: Path, path: object) -> Path:
    value = Path(str(path))
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value: object = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"JSONL object required: {path}:{line_number}")
        rows.append(cast(JsonObject, value))
    return rows


def object_value(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def object_rows(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{where} must be a list of objects")
    return cast(list[JsonObject], value)


def verify_file(root: Path, raw_spec: object, *, label: str) -> Path:
    spec = object_value(raw_spec, where=label)
    path = rooted(root, spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"{label} byte-size mismatch")
    if file_sha256(path) != spec["sha256"]:
        raise ValueError(f"{label} SHA-256 mismatch")
    return path


def result_identity(value: Mapping[str, object]) -> str:
    payload = dict(value)
    payload.pop("result_identity_sha256", None)
    return canonical_sha256(payload)


def verify_result_identity(value: Mapping[str, object], *, label: str) -> None:
    expected = value.get("result_identity_sha256")
    if not isinstance(expected, str) or result_identity(value) != expected:
        raise ValueError(f"{label} result identity mismatch")


def _scan_safe(value: object, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_SAFE_KEYS:
                raise ValueError(f"forbidden raw field in safe output: {path}.{key}")
            _scan_safe(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_safe(item, path=f"{path}[{index}]")


def _atomic_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def frozen_write(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite nonidentical frozen artifact: {path}")
        return
    _atomic_replace(path, payload)


def atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    payload = (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    _atomic_replace(path, payload)


def frozen_write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    frozen_write(path, canonical_jsonl_bytes(rows))


def write_frozen_result(path: Path, value: Mapping[str, object]) -> JsonObject:
    result = dict(value)
    result["result_identity_scheme"] = (
        "SHA256_of_UTF8_canonical_sorted_compact_JSON_ensure_ascii_false_"
        "with_result_identity_sha256_omitted"
    )
    _scan_safe(result)
    result["result_identity_sha256"] = result_identity(result)
    payload = (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    frozen_write(path, payload)
    return result


def validate_contract(root: Path, contract_path: Path) -> JsonObject:
    contract = load_object(contract_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-1 contract schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-1 contract is not frozen before output")
    if rooted(root, contract["contract_path"]) != contract_path.resolve():
        raise ValueError("E0F-1 contract self-path mismatch")
    if contract.get("scientific_completion_call_ceiling") != 144:
        raise ValueError("E0F-1 scientific completion ceiling must be 144")
    if contract.get("automatic_expansion_beyond_sentinel") is not False:
        raise ValueError("E0F-1 must prohibit automatic expansion")
    implementation = object_value(contract["implementation"], where="implementation")
    module_path = verify_file(root, implementation["module"], label="E0F-1 module")
    runner_path = verify_file(root, implementation["runner"], label="E0F-1 runner")
    if module_path != (root / "src/jbspan/evaluator_panel_wildguard_sentinel.py").resolve():
        raise ValueError("unexpected E0F-1 module path")
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected E0F-1 runner path")
    dependencies = object_value(contract["dependencies"], where="dependencies")
    for name, spec in dependencies.items():
        verify_file(root, spec, label=f"dependency {name}")
    predecessor_spec = object_value(contract["predecessor"], where="predecessor")
    predecessor_path = verify_file(root, predecessor_spec, label="E0F-0 predecessor")
    predecessor = load_object(predecessor_path)
    verify_result_identity(predecessor, label="E0F-0 predecessor")
    if predecessor.get("status") != predecessor_spec["required_status"]:
        raise ValueError("E0F-0 predecessor status mismatch")
    decision = object_value(predecessor["scientific_decision"], where="E0F-0 decision")
    if decision.get("wildguard_sentinel_144_run_authorized") is not True:
        raise ValueError("E0F-0 does not authorize the WildGuard sentinel")
    if decision.get("wildguard_intermediate_300_run_authorized") is not False:
        raise ValueError("E0F-0 unexpectedly authorizes 300 calls")
    prior = object_value(contract["prior_runtime_qualification"], where="qualification")
    e1b_path = rooted(
        root,
        object_value(dependencies["e1b_wildguard_qualification"], where="E1B")["path"],
    )
    e1b = load_object(e1b_path)
    if e1b.get("status") != prior["required_e1b_status"]:
        raise ValueError("prior E1B WildGuard qualification status mismatch")
    hardened = object_value(
        object_value(e1b["live_canaries"], where="E1B canaries")["hardened_template"],
        where="E1B hardened canaries",
    )
    if hardened != object_value(
        prior["required_hardened_canary_summary"], where="required canaries"
    ):
        raise ValueError("prior E1B hardened canary aggregate mismatch")
    p3_path = rooted(
        root,
        object_value(dependencies["p3_exact_wildguard_screen"], where="P3 screen")["path"],
    )
    p3_result = load_object(p3_path)
    verify_result_identity(p3_result, label="P3 exact WildGuard screen")
    if p3_result.get("status") != prior["required_p3_status"]:
        raise ValueError("prior P3 exact WildGuard status mismatch")
    p3_runtime = object_value(p3_result["runtime"], where="P3 runtime")
    runtime = object_value(contract["runtime"], where="runtime")
    model = object_value(runtime["model"], where="runtime model")
    server = object_value(runtime["server"], where="runtime server")
    if (
        p3_runtime.get("model_sha256") != model["sha256"]
        or p3_runtime.get("server_sha256") != server["sha256"]
        or p3_runtime.get("cpu_only_gpu_layer_count") != 0
    ):
        raise ValueError("E0F-1 runtime differs from the qualified P3 WildGuard runtime")
    candidates = object_rows(contract["candidate_specs"], where="candidate_specs")
    validate_candidate_specs(candidates)
    if len(candidates) != int(contract["expected_candidate_count"]):
        raise ValueError("E0F-1 candidate count mismatch")
    return contract


def load_existing_records(root: Path, contract: JsonObject) -> tuple[ExistingSignalRecord, ...]:
    inputs = object_value(contract["inputs"], where="inputs")
    calibration_path = verify_file(root, inputs["calibration"], label="calibration manifest")
    calibration_rows = load_jsonl(calibration_path)
    axis_rows: list[JsonObject] = []
    for index, spec in enumerate(object_rows(inputs["axis_files"], where="axis_files")):
        axis_path = verify_file(root, spec, label=f"axis file {index}")
        axis_rows.extend(load_jsonl(axis_path))
    return build_existing_signal_records(calibration_rows, axis_rows)


def selected_record_ids(root: Path, contract: JsonObject) -> tuple[str, ...]:
    inputs = object_value(contract["inputs"], where="inputs")
    stage_path = verify_file(root, inputs["stage_manifest"], label="stage manifest")
    rows = load_jsonl(stage_path)
    selected = tuple(
        str(row["record_id"])
        for row in rows
        if row.get("first_included_stage") == "E0F_1_SENTINEL"
    )
    if len(selected) != 144 or len(set(selected)) != 144:
        raise ValueError("E0F-1 stage selection must contain 144 unique records")
    return selected


def sanitization_metadata(value: SanitizedText) -> JsonObject:
    result = asdict(value)
    result.pop("text")
    return result


def reconstruct_text_records(
    root: Path,
    contract: JsonObject,
) -> tuple[CalibrationTextRecord, ...]:
    inputs = object_value(contract["inputs"], where="inputs")
    calibration = object_value(inputs["calibration"], where="calibration")
    source_contract = object_value(inputs["source_contract"], where="source_contract")
    source_contract_path = verify_file(
        root,
        source_contract,
        label="external source contract",
    )
    return reconstruct_calibration_texts(
        root,
        source_contract_path=source_contract_path,
        calibration_manifest_path=rooted(root, calibration["path"]),
        calibration_manifest_sha256=str(calibration["sha256"]),
        expected_records=int(calibration["records"]),
    )


def build_plan(
    root: Path,
    contract: JsonObject,
) -> tuple[list[ScientificPlanRecord], tuple[ExistingSignalRecord, ...], JsonObject]:
    existing = load_existing_records(root, contract)
    existing_by_id = {record.record_id: record for record in existing}
    selected = selected_record_ids(root, contract)
    if not set(selected).issubset(existing_by_id):
        raise ValueError("E0F-1 selection is outside existing calibration records")
    texts = reconstruct_text_records(root, contract)
    text_by_id = {record.record_id: record for record in texts}
    if set(text_by_id) != set(existing_by_id):
        raise ValueError("reconstructed calibration text identities differ from existing signals")
    prompt_spec = object_value(
        object_value(contract["inputs"], where="inputs")["prompt_template"],
        where="prompt_template",
    )
    prompt_path = verify_file(root, prompt_spec, label="WildGuard prompt template")
    template = prompt_path.read_text(encoding="utf-8")
    inference = object_value(contract["inference"], where="inference")
    nonce = str(inference["nonce"])
    max_characters = int(inference["max_untrusted_characters"])
    plan: list[ScientificPlanRecord] = []
    source_label_counts: Counter[str] = Counter()
    truncations = 0
    for record_id in selected:
        text_record = text_by_id[record_id]
        signal_record = existing_by_id[record_id]
        request = sanitize_untrusted_text(text_record.question, max_characters=max_characters)
        response = sanitize_untrusted_text(text_record.response, max_characters=max_characters)
        classifier_input = template.format(
            nonce=nonce,
            prompt=request.text,
            response=response.text,
        )
        source_input_truncated = request.truncated or response.truncated
        truncations += source_input_truncated
        safe: JsonObject = {
            "schema_version": "jbspan-e0f1-wildguard-plan-record-v1",
            "record_id": record_id,
            "source_id": signal_record.source_id,
            "behavior_group_sha256": signal_record.behavior_group_sha256,
            "response_sha256": text_record.response_sha256,
            "question_sanitization": sanitization_metadata(request),
            "response_sanitization": sanitization_metadata(response),
            "source_input_truncated": source_input_truncated,
            "classifier_input_sha256": hashlib.sha256(classifier_input.encode("utf-8")).hexdigest(),
            "classifier_input_utf8_bytes": len(classifier_input.encode("utf-8")),
            "human_label_written": False,
        }
        safe["judge_input_identity_sha256"] = canonical_sha256(safe)
        plan.append(
            ScientificPlanRecord(
                safe=safe,
                question=text_record.question,
                response=text_record.response,
                classifier_input=classifier_input,
            )
        )
        source_label_counts[f"{signal_record.source_id}:{signal_record.human_label}"] += 1
    expected_counts = object_value(
        object_value(contract["stage"], where="stage")["expected_source_label_counts"],
        where="expected_source_label_counts",
    )
    if dict(sorted(source_label_counts.items())) != {
        str(key): int(value) for key, value in sorted(expected_counts.items())
    }:
        raise ValueError("E0F-1 source/label balance mismatch")
    if truncations != 0:
        raise ValueError("E0F-1 plan has source-input truncation")
    safe_rows = [value.safe for value in plan]
    summary: JsonObject = {
        "records": len(plan),
        "source_label_counts": dict(sorted(source_label_counts.items())),
        "source_input_truncation_count": truncations,
        "plan_identity_sha256": canonical_sha256(safe_rows),
        "maximum_classifier_input_utf8_bytes": max(
            int(row["classifier_input_utf8_bytes"]) for row in safe_rows
        ),
        "raw_text_written_to_safe_plan": False,
    }
    return plan, existing, summary


def runtime_identity(root: Path, contract: JsonObject) -> JsonObject:
    runtime = object_value(contract["runtime"], where="runtime")
    server_spec = object_value(runtime["server"], where="llama-server")
    model_spec = object_value(runtime["model"], where="WildGuard model")
    server_path = verify_file(root, server_spec, label="llama-server")
    model_path = verify_file(root, model_spec, label="WildGuard model")
    completed = subprocess.run(
        [str(server_path), "--version"],
        cwd=server_path.parent,
        check=False,
        capture_output=True,
        timeout=30,
    )
    version_text = (completed.stdout + b"\n" + completed.stderr).decode(
        "utf-8", errors="replace"
    ).strip()
    if completed.returncode != 0:
        raise RuntimeError("unable to obtain llama-server version")
    if f"build {runtime['required_build']}" not in version_text:
        raise ValueError("llama-server build mismatch")
    if f"commit {runtime['required_revision_prefix']}" not in version_text:
        raise ValueError("llama-server revision mismatch")
    return {
        "server_sha256": server_spec["sha256"],
        "server_bytes": server_path.stat().st_size,
        "server_version_output_sha256": hashlib.sha256(version_text.encode()).hexdigest(),
        "server_build": runtime["required_build"],
        "server_revision_prefix": runtime["required_revision_prefix"],
        "model_sha256": model_spec["sha256"],
        "model_bytes": model_path.stat().st_size,
        "conversion": runtime["conversion"],
        "cpu_only_gpu_layer_count": 0,
    }


def preflight(root: Path, contract_path: Path) -> JsonObject:
    contract = validate_contract(root, contract_path)
    plan, _, plan_summary = build_plan(root, contract)
    runtime = runtime_identity(root, contract)
    outputs = object_value(contract["outputs"], where="outputs")
    plan_path = rooted(root, outputs["plan_path"])
    safe_rows = [value.safe for value in plan]
    frozen_write_jsonl(plan_path, safe_rows)
    result: JsonObject = {
        "schema_version": "jbspan-e0f1-wildguard-sentinel-preflight-safe-v1",
        "status": "E0F1_PREFLIGHT_PASS_AUTHORIZE_EXACTLY_144_SCIENTIFIC_COMPLETIONS",
        "evidence_class": "ZERO_SCIENTIFIC_INFERENCE_PREFLIGHT",
        "contract_sha256": file_sha256(contract_path),
        "implementation": contract["implementation"],
        "runtime": runtime,
        "scientific_plan": {
            **plan_summary,
            "path": str(plan_path.relative_to(root)),
            "bytes": plan_path.stat().st_size,
            "sha256": file_sha256(plan_path),
        },
        "candidate_count": len(object_rows(contract["candidate_specs"], where="candidates")),
        "candidate_specs_sha256": canonical_sha256(contract["candidate_specs"]),
        "scientific_completion_call_ceiling": 144,
        "separate_canary_completion_calls_authorized": 0,
        "new_model_inference_performed": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "next_operation": "RUN_E0F1_EXACT_144_WILDGUARD_SCIENTIFIC_SENTINEL",
    }
    return write_frozen_result(rooted(root, outputs["preflight_path"]), result)


def post_json(url: str, payload: Mapping[str, object]) -> JsonObject:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(HTTP_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                value: object = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise TypeError("llama-server response is not an object")
            return cast(JsonObject, value)
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(1.0)
    raise RuntimeError("llama-server request failed after retries") from last_error


def server_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=2) as response:
            return int(response.status) == 200
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"local server port is already in use: {port}")


@contextmanager
def local_server(
    *,
    server_path: Path,
    model_path: Path,
    port: int,
    inference: Mapping[str, object],
    log_path: Path,
) -> Iterator[tuple[str, float]]:
    require_free_port(port)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    command = [
        str(server_path),
        "--model",
        str(model_path),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--device",
        "none",
        "--gpu-layers",
        "0",
        "--no-op-offload",
        "--fit",
        "off",
        "--split-mode",
        "none",
        "--ctx-size",
        str(inference["context_tokens"]),
        "--threads",
        str(inference["threads"]),
        "--threads-batch",
        str(inference["threads_batch"]),
        "--batch-size",
        str(inference["batch_size"]),
        "--ubatch-size",
        str(inference["ubatch_size"]),
        "--parallel",
        "1",
        "--offline",
        "--no-jinja",
        "--reasoning",
        "off",
        "--no-warmup",
        "--log-colors",
        "off",
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=server_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        while time.monotonic() - started < SERVER_STARTUP_TIMEOUT_SECONDS:
            if process.poll() is not None:
                raise RuntimeError("llama-server exited before readiness")
            if server_ready(url):
                yield url, time.monotonic() - started
                return
            time.sleep(1.0)
        raise TimeoutError("llama-server readiness timeout")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=20)
        log_handle.close()


def numeric_timings(value: object) -> JsonObject:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "prompt_n",
        "prompt_ms",
        "prompt_per_token_ms",
        "prompt_per_second",
        "predicted_n",
        "predicted_ms",
        "predicted_per_token_ms",
        "predicted_per_second",
    }
    return {
        str(key): item
        for key, item in value.items()
        if key in allowed and isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def execute_record(
    *,
    plan: ScientificPlanRecord,
    server_url: str,
    private_dir: Path,
    contract_sha256: str,
    implementation: Mapping[str, object],
    model_sha256: str,
    inference: Mapping[str, object],
) -> tuple[JsonObject, bool, bool]:
    identity: JsonObject = {
        "contract_sha256": contract_sha256,
        "module_sha256": object_value(implementation["module"], where="module")["sha256"],
        "runner_sha256": object_value(implementation["runner"], where="runner")["sha256"],
        "model_sha256": model_sha256,
        "record_id": plan.safe["record_id"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "inference": dict(inference),
    }
    identity_sha = canonical_sha256(identity)
    private_path = private_dir / f"{identity_sha}.json"
    cache_hit = False
    new_completion = False
    if private_path.is_file():
        execution = load_object(private_path)
        if execution.get("execution_identity_sha256") != identity_sha:
            raise ValueError("private E0F-1 cache identity conflict")
        cache_hit = execution.get("record_complete") is True
        if not cache_hit:
            execution = {}
    else:
        execution = {}
    if not cache_hit:
        started = time.monotonic()
        tokenized = post_json(
            server_url + "/tokenize",
            {
                "content": plan.classifier_input,
                "add_special": False,
                "parse_special": True,
                "with_pieces": False,
            },
        )
        tokens = tokenized.get("tokens")
        if not isinstance(tokens, list) or not all(isinstance(token, int) for token in tokens):
            raise RuntimeError("WildGuard tokenizer response is invalid")
        prompt_tokens = len(tokens)
        context_budget_pass = prompt_tokens + int(
            str(inference["maximum_new_tokens"])
        ) <= int(
            str(inference["context_tokens"])
        )
        raw_output = ""
        completion: JsonObject | None = None
        source_input_truncated = plan.safe["source_input_truncated"] is True
        if context_budget_pass and not source_input_truncated:
            completion = post_json(
                server_url + "/completion",
                {
                    "prompt": plan.classifier_input,
                    "n_predict": int(str(inference["maximum_new_tokens"])),
                    "temperature": float(str(inference["temperature"])),
                    "top_p": float(str(inference["top_p"])),
                    "stream": False,
                    "cache_prompt": False,
                    "seed": int(str(inference["seed"])),
                },
            )
            content = completion.get("content")
            if not isinstance(content, str):
                raise RuntimeError("WildGuard completion returned no text")
            raw_output = content
            new_completion = True
        execution = {
            "schema_version": "jbspan-e0f1-private-wildguard-record-v1",
            "execution_identity": identity,
            "execution_identity_sha256": identity_sha,
            "record_id": plan.safe["record_id"],
            "human_request": plan.question,
            "assistant_response": plan.response,
            "classifier_input": plan.classifier_input,
            "input_token_ids": tokens,
            "prompt_tokens": prompt_tokens,
            "context_budget_pass": context_budget_pass,
            "completion_requested": completion is not None,
            "request_completed": completion is not None,
            "raw_output": raw_output,
            "stop_type": completion.get("stop_type") if completion else None,
            "tokens_predicted": completion.get("tokens_predicted") if completion else None,
            "truncated": completion.get("truncated") if completion else None,
            "timings": numeric_timings(completion.get("timings")) if completion else {},
            "elapsed_seconds": time.monotonic() - started,
            "record_complete": True,
        }
        atomic_write_json(private_path, execution)
    if hashlib.sha256(str(execution.get("human_request", "")).encode()).hexdigest() != plan.safe[
        "question_sanitization"
    ]["original_sha256"]:
        raise ValueError("private cached question mismatch")
    cached_response_sha = hashlib.sha256(
        str(execution.get("assistant_response", "")).encode()
    ).hexdigest()
    if cached_response_sha != plan.safe["response_sanitization"]["original_sha256"]:
        raise ValueError("private cached response mismatch")
    if hashlib.sha256(str(execution.get("classifier_input", "")).encode()).hexdigest() != plan.safe[
        "classifier_input_sha256"
    ]:
        raise ValueError("private cached classifier input mismatch")
    raw_output = str(execution.get("raw_output", ""))
    axis = parse_wildguard_output(raw_output, canary_nonce=str(inference["nonce"]))
    output_limit_hit = execution.get("stop_type") == "limit" or (
        isinstance(execution.get("tokens_predicted"), int)
        and int(execution["tokens_predicted"])
        >= int(str(inference["maximum_new_tokens"]))
    )
    server_context_truncated = execution.get("truncated") is True
    eligible = all(
        (
            execution.get("record_complete") is True,
            execution.get("request_completed") is True,
            execution.get("context_budget_pass") is True,
            plan.safe["source_input_truncated"] is False,
            not server_context_truncated,
            not output_limit_hit,
            not axis.parse_error,
            axis.canary_pass,
        )
    )
    safe: JsonObject = {
        "schema_version": "jbspan-e0f1-safe-wildguard-record-v1",
        "record_id": plan.safe["record_id"],
        "source_id": plan.safe["source_id"],
        "behavior_group_sha256": plan.safe["behavior_group_sha256"],
        "response_sha256": plan.safe["response_sha256"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "execution_identity_sha256": identity_sha,
        "private_record_sha256": file_sha256(private_path),
        "question_sanitization": plan.safe["question_sanitization"],
        "response_sanitization": plan.safe["response_sanitization"],
        "classifier_input_sha256": plan.safe["classifier_input_sha256"],
        "classifier_input_utf8_bytes": plan.safe["classifier_input_utf8_bytes"],
        "source_input_truncated": plan.safe["source_input_truncated"],
        "prompt_tokens": execution.get("prompt_tokens"),
        "context_budget_pass": execution.get("context_budget_pass") is True,
        "request_completed": execution.get("request_completed") is True,
        "server_context_truncated": server_context_truncated,
        "output_limit_hit": output_limit_hit,
        "stop_type": execution.get("stop_type"),
        "tokens_predicted": execution.get("tokens_predicted"),
        "output_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
        "output_utf8_bytes": len(raw_output.encode("utf-8")),
        "response_refusal": axis.response_refusal,
        "response_harmfulness": axis.response_harmfulness,
        "safe_redirection": axis.safe_redirection,
        "parse_error": axis.parse_error,
        "canary_pass": axis.canary_pass,
        "eligible_measurement": eligible,
        "timings": execution.get("timings", {}),
        "first_execution_elapsed_seconds": execution.get("elapsed_seconds"),
        "human_label_written": False,
        "raw_prompt_or_response_written": False,
    }
    _scan_safe(safe)
    return safe, cache_hit, new_completion


def integrity_summary(rows: Sequence[Mapping[str, object]], expected_records: int) -> JsonObject:
    result: JsonObject = {
        "records": len(rows),
        "expected_records": expected_records,
        "eligible_measurements": sum(row.get("eligible_measurement") is True for row in rows),
        "request_failures": sum(row.get("request_completed") is not True for row in rows),
        "context_budget_failures": sum(
            row.get("context_budget_pass") is not True for row in rows
        ),
        "source_input_truncations": sum(
            row.get("source_input_truncated") is True for row in rows
        ),
        "server_context_truncations": sum(
            row.get("server_context_truncated") is True for row in rows
        ),
        "output_limit_hits": sum(row.get("output_limit_hit") is True for row in rows),
        "parse_failures": sum(row.get("parse_error") is True for row in rows),
        "canary_failures": sum(row.get("canary_pass") is not True for row in rows),
        "duplicate_record_ids": len(rows) - len({str(row.get("record_id")) for row in rows}),
    }
    result["pass"] = (
        result["records"] == expected_records
        and result["eligible_measurements"] == expected_records
        and all(
            result[field] == 0
            for field in (
                "request_failures",
                "context_budget_failures",
                "source_input_truncations",
                "server_context_truncations",
                "output_limit_hits",
                "parse_failures",
                "canary_failures",
                "duplicate_record_ids",
            )
        )
    )
    return result


def finalize(
    root: Path,
    contract_path: Path,
    contract: JsonObject,
    rows: list[JsonObject],
    execution_summary: JsonObject,
) -> JsonObject:
    selected = set(selected_record_ids(root, contract))
    existing = load_existing_records(root, contract)
    sentinel_records = build_sentinel_records(existing, rows, selected_record_ids=selected)
    integrity = integrity_summary(rows, len(selected))
    candidates = evaluate_sentinel(
        sentinel_records,
        object_rows(contract["candidate_specs"], where="candidate_specs"),
        population=object_value(contract["calibration_population"], where="population"),
        gates=object_value(contract["futility_gates"], where="futility_gates"),
        integrity_pass=integrity["pass"] is True,
    )
    passed = candidates["sentinel_pass"] is True
    outputs = object_value(contract["outputs"], where="outputs")
    axis_path = rooted(root, outputs["axis_path"])
    result: JsonObject = {
        "schema_version": "jbspan-e0f1-wildguard-sentinel-result-safe-v1",
        "status": (
            "E0F1_SENTINEL_PASS_AUTHORIZE_E0F2_DESIGN_REVIEW"
            if passed
            else "E0F1_SENTINEL_FAIL_STOP_WILDGUARD_EXPANSION"
        ),
        "evidence_class": "CALIBRATION_ONLY_SCIENTIFIC_FUTILITY_SENTINEL",
        "contract_sha256": file_sha256(contract_path),
        "runtime": execution_summary["runtime"],
        "execution": execution_summary,
        "integrity": integrity,
        "candidate_evaluation": candidates,
        "axis_artifact": {
            "path": str(axis_path.relative_to(root)),
            "records": len(rows),
            "bytes": axis_path.stat().st_size,
            "sha256": file_sha256(axis_path),
        },
        "scientific_decision": {
            "e0f1_sentinel_pass": passed,
            "e0f2_design_and_execution_may_be_frozen_after_review": passed,
            "automatic_e0f2_execution_started": False,
            "e0f3_full_889_authorized": False,
            "heldout_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": (
                "REVIEW_E0F1_THEN_FREEZE_E0F2_CUMULATIVE_300_EXECUTION"
                if passed
                else "STOP_WILDGUARD_PATH_AND_REVIEW_PREDECLARED_FALLBACK_WITHOUT_HELDOUT"
            ),
        },
        "scientific_completion_call_ceiling": 144,
        "separate_canary_completion_calls_performed": 0,
        "per_record_human_labels_written": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
    }
    return write_frozen_result(rooted(root, outputs["result_path"]), result)


def run(root: Path, contract_path: Path) -> JsonObject:
    contract = validate_contract(root, contract_path)
    outputs = object_value(contract["outputs"], where="outputs")
    result_path = rooted(root, outputs["result_path"])
    if result_path.is_file():
        result = load_object(result_path)
        verify_result_identity(result, label="existing E0F-1 result")
        axis_spec = object_value(result["axis_artifact"], where="axis artifact")
        verify_file(root, axis_spec, label="existing E0F-1 axis")
        print(
            "E0F1_ALREADY_COMPLETE "
            f"status={result['status']} identity={result['result_identity_sha256']}",
            flush=True,
        )
        return result
    plan, _, plan_summary = build_plan(root, contract)
    preflight_path = rooted(root, outputs["preflight_path"])
    if not preflight_path.is_file():
        raise FileNotFoundError("E0F-1 preflight must pass before scientific inference")
    preflight_result = load_object(preflight_path)
    verify_result_identity(preflight_result, label="E0F-1 preflight")
    if preflight_result.get("status") != (
        "E0F1_PREFLIGHT_PASS_AUTHORIZE_EXACTLY_144_SCIENTIFIC_COMPLETIONS"
    ):
        raise ValueError("E0F-1 preflight status does not authorize execution")
    preflight_plan = object_value(preflight_result["scientific_plan"], where="preflight plan")
    if preflight_plan.get("plan_identity_sha256") != plan_summary["plan_identity_sha256"]:
        raise ValueError("E0F-1 plan identity changed after preflight")
    verify_file(root, preflight_plan, label="E0F-1 safe plan")
    axis_path = rooted(root, outputs["axis_path"])
    execution_path = rooted(root, outputs["execution_path"])
    if axis_path.is_file() or execution_path.is_file():
        if not axis_path.is_file() or not execution_path.is_file():
            raise ValueError("partial safe E0F-1 terminal artifacts require audit")
        rows = load_jsonl(axis_path)
        execution_summary = load_object(execution_path)
        verify_result_identity(execution_summary, label="E0F-1 execution")
        return finalize(root, contract_path, contract, rows, execution_summary)

    runtime = runtime_identity(root, contract)
    runtime_spec = object_value(contract["runtime"], where="runtime")
    server_path = rooted(root, object_value(runtime_spec["server"], where="server")["path"])
    model_path = rooted(root, object_value(runtime_spec["model"], where="model")["path"])
    inference = object_value(contract["inference"], where="inference")
    artifact_root = rooted(root, outputs["private_artifact_root"])
    private_dir = artifact_root / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    safe_rows: list[JsonObject] = []
    cache_hits = 0
    new_completion_calls = 0
    integrity_failures = 0
    contract_sha = file_sha256(contract_path)
    with local_server(
        server_path=server_path,
        model_path=model_path,
        port=int(runtime_spec["port"]),
        inference=inference,
        log_path=artifact_root / "server_logs/wildguard.log",
    ) as (server_url, startup_seconds):
        for index, plan_record in enumerate(plan, 1):
            safe, cache_hit, new_completion = execute_record(
                plan=plan_record,
                server_url=server_url,
                private_dir=private_dir,
                contract_sha256=contract_sha,
                implementation=object_value(contract["implementation"], where="implementation"),
                model_sha256=str(runtime["model_sha256"]),
                inference=inference,
            )
            safe_rows.append(safe)
            cache_hits += cache_hit
            new_completion_calls += new_completion
            integrity_failures += safe["eligible_measurement"] is not True
            if index % 6 == 0 or index == len(plan):
                print(
                    "E0F1_WILDGUARD_PROGRESS "
                    f"completed={index}/{len(plan)} new_completion_calls={new_completion_calls} "
                    f"cache_hits={cache_hits} integrity_failures={integrity_failures} "
                    f"elapsed_seconds={time.monotonic() - started:.1f}",
                    flush=True,
                )
    if new_completion_calls + cache_hits > int(contract["scientific_completion_call_ceiling"]):
        raise RuntimeError("E0F-1 scientific completion ceiling exceeded")
    frozen_write_jsonl(axis_path, safe_rows)
    integrity = integrity_summary(safe_rows, len(plan))
    execution: JsonObject = {
        "schema_version": "jbspan-e0f1-wildguard-execution-safe-v1",
        "status": "E0F1_EXACT_144_WILDGUARD_EXECUTION_COMPLETE",
        "contract_sha256": contract_sha,
        "runtime": runtime,
        "server_startup_seconds": startup_seconds,
        "planned_scientific_records": len(plan),
        "completed_scientific_records": len(safe_rows),
        "new_completion_calls_this_invocation": new_completion_calls,
        "resumed_private_cache_records": cache_hits,
        "scientific_completion_records_total": sum(
            row["request_completed"] is True for row in safe_rows
        ),
        "separate_canary_completion_calls": 0,
        "integrity": integrity,
        "axis_path": str(axis_path.relative_to(root)),
        "axis_bytes": axis_path.stat().st_size,
        "axis_sha256": file_sha256(axis_path),
        "elapsed_seconds": time.monotonic() - started,
        "cpu_only": True,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
    }
    execution_summary = write_frozen_result(execution_path, execution)
    return finalize(root, contract_path, contract, safe_rows, execution_summary)


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract_path = rooted(root, args.contract)
    if args.command == "preflight":
        result = preflight(root, contract_path)
    else:
        result = run(root, contract_path)
    print(
        "E0F1_COMMAND_RESULT "
        f"status={result['status']} identity={result['result_identity_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
