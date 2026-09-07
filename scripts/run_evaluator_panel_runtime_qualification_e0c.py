from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from jbspan.evaluator_panel_runtime_qualification import (
    JsonObject,
    RenderedJudgeCase,
    actionability_expectations_passed,
    canonical_json,
    render_case,
)
from jbspan.evaluator_panel_v2 import (
    capability_control_response_passed,
    parse_actionability_output_v2,
    parse_guided_output_v2,
)

MIB = 1024 * 1024
GIB = 1024 * 1024 * 1024
PRIVATE_TEXT_KEYS = {
    "prompt",
    "prompt_text",
    "system_prompt",
    "user_prompt",
    "response",
    "response_text",
    "stdout",
    "stderr",
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
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def normalized_response(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


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


def _validate_hash_dependency(root: Path, dependency: JsonObject, *, where: str) -> None:
    path = root / str(dependency["path"])
    if not path.is_file():
        raise FileNotFoundError(f"missing {where}: {path}")
    if path.stat().st_size != int(dependency["bytes"]):
        raise ValueError(f"byte-size mismatch for {where}: {path}")
    observed = sha256_file(path)
    if observed != dependency["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {where}: {path}")


def validate_contract(root: Path, config_path: Path, contract: JsonObject) -> None:
    if contract.get("status") != "FROZEN_BEFORE_ANY_E0C_MODEL_DOWNLOAD_OR_INFERENCE":
        raise ValueError("unexpected E0C contract status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("E0C contract must be frozen and non-paper-valid")
    scope = as_object(contract["scope_boundary"], where="scope_boundary")
    if any(value is not False for value in scope.values()):
        raise ValueError("E0C scope opens a prohibited outcome boundary")

    predecessor = as_object(contract["predecessor"], where="predecessor")
    _validate_hash_dependency(root, predecessor, where="E0B predecessor")
    predecessor_value = load_object(root / str(predecessor["path"]))
    if predecessor_value.get("status") != predecessor["required_status"]:
        raise ValueError("E0B predecessor status mismatch")
    if predecessor_value.get("result_identity_sha256") != predecessor["result_identity"]:
        raise ValueError("E0B predecessor identity mismatch")

    for name, dependency_value in as_object(
        contract["frozen_dependencies"], where="frozen_dependencies"
    ).items():
        _validate_hash_dependency(
            root,
            as_object(dependency_value, where=f"frozen_dependencies.{name}"),
            where=name,
        )

    models = as_object_list(contract["models"], where="models")
    cases = as_object_list(contract["harmless_cases"], where="harmless_cases")
    gate = as_object(contract["gate"], where="gate")
    if len(models) != int(gate["required_models"]):
        raise ValueError("E0C model count does not match the gate")
    if len(cases) != int(gate["required_harmless_cases_per_model"]):
        raise ValueError("E0C harmless case count does not match the gate")
    if len({str(case["case_id"]) for case in cases}) != len(cases):
        raise ValueError("E0C case ids must be unique")
    required_axes = set(cast(list[str], gate["required_axes"]))
    if {str(case["axis"]) for case in cases} != required_axes:
        raise ValueError("E0C case axes do not match the frozen gate")
    if not all(case.get("harmless") is True for case in cases):
        raise ValueError("every E0C case must be explicitly harmless")
    if not all(int(case["repetitions"]) == 2 for case in cases):
        raise ValueError("every E0C case requires two independent-process repetitions")
    for model in models:
        if re.fullmatch(r"[0-9a-f]{40}", str(model["runtime_revision"])) is None:
            raise ValueError(f"mutable model revision: {model['judge_id']}")
        if re.fullmatch(r"[0-9a-f]{64}", str(model["runtime_lfs_sha256"])) is None:
            raise ValueError(f"invalid model digest: {model['judge_id']}")
    generation = as_object(contract["generation"], where="generation")
    required_cpu = {
        "device": "none",
        "gpu_layers": 0,
        "op_offload": False,
        "fit": "off",
    }
    if any(generation.get(key) != value for key, value in required_cpu.items()):
        raise ValueError("E0C generation is not frozen to CPU-only execution")
    if not config_path.is_file():
        raise FileNotFoundError("E0C config is missing")


def run_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
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


def validate_runtime(root: Path, contract: JsonObject) -> JsonObject:
    runtime = as_object(contract["runtime"], where="runtime")
    archive = root / str(runtime["archive_path"])
    cli = root / str(runtime["cli_path"])
    server = root / str(runtime["server_path"])
    for path, bytes_key, digest_key in (
        (archive, "archive_bytes", "archive_sha256"),
        (cli, "cli_bytes", "cli_sha256"),
        (server, "server_bytes", "server_sha256"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"pinned runtime artifact is missing: {path}")
        if path.stat().st_size != int(runtime[bytes_key]):
            raise ValueError(f"runtime artifact size mismatch: {path}")
        if sha256_file(path) != runtime[digest_key]:
            raise ValueError(f"runtime artifact digest mismatch: {path}")
    bundle_rows: list[JsonObject] = []
    with zipfile.ZipFile(archive) as bundle:
        for entry in sorted(
            (item for item in bundle.infolist() if not item.is_dir()),
            key=lambda item: item.filename,
        ):
            relative = Path(entry.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe runtime archive member: {entry.filename}")
            local = cli.parent / relative
            if not local.is_file() or local.stat().st_size != entry.file_size:
                raise ValueError(f"runtime extraction mismatch: {entry.filename}")
            archived_digest = hashlib.sha256()
            with bundle.open(entry) as handle:
                for block in iter(lambda: handle.read(4 * MIB), b""):
                    archived_digest.update(block)
            local_digest = sha256_file(local)
            if archived_digest.hexdigest() != local_digest:
                raise ValueError(f"runtime bundle byte mismatch: {entry.filename}")
            bundle_rows.append(
                {
                    "path": entry.filename,
                    "bytes": entry.file_size,
                    "sha256": local_digest,
                }
            )
    version = run_command([str(cli), "--version"], timeout=30)
    version_text = version.stdout + version.stderr
    if version.returncode != 0:
        raise RuntimeError("llama.cpp version probe failed")
    for expected in cast(list[str], runtime["required_version_substrings"]):
        if expected not in version_text:
            raise ValueError(f"llama.cpp version output missing: {expected}")
    help_run = run_command([str(cli), "--help"], timeout=30)
    help_text = help_run.stdout + help_run.stderr
    for flag in cast(list[str], runtime["required_cli_flags"]):
        if flag not in help_text:
            raise ValueError(f"llama.cpp CLI does not expose required flag: {flag}")
    return {
        "archive_sha256": runtime["archive_sha256"],
        "cli_path": str(cli.resolve()),
        "cli_sha256": runtime["cli_sha256"],
        "server_sha256": runtime["server_sha256"],
        "extracted_bundle_file_count": len(bundle_rows),
        "extracted_bundle_bytes": sum(int(row["bytes"]) for row in bundle_rows),
        "extracted_bundle_manifest_sha256": canonical_sha256(bundle_rows),
        "version_output_sha256": sha256_bytes(version_text.encode("utf-8")),
        "help_output_sha256": sha256_bytes(help_text.encode("utf-8")),
    }


def sibling_metadata(sibling: object) -> JsonObject:
    entry = cast(Any, sibling)
    size = getattr(entry, "size", None)
    digest: str | None = None
    lfs = getattr(entry, "lfs", None)
    if isinstance(lfs, dict):
        size = lfs.get("size", size)
        raw_digest = lfs.get("sha256")
        digest = str(raw_digest) if raw_digest is not None else None
    elif lfs is not None:
        size = getattr(lfs, "size", size)
        raw_digest = getattr(lfs, "sha256", None)
        digest = str(raw_digest) if raw_digest is not None else None
    return {
        "filename": str(entry.rfilename),
        "size_bytes": size,
        "sha256": digest,
    }


def _safe_remove_tree(path: Path, *, artifact_root: Path) -> bool:
    if not path.exists():
        return False
    resolved = path.resolve()
    resolved.relative_to(artifact_root.resolve())
    if resolved == artifact_root.resolve():
        raise ValueError("refusing to remove the E0C artifact root")
    shutil.rmtree(resolved)
    return True


def prepare_models(
    contract: JsonObject, artifact_root: Path
) -> tuple[list[JsonObject], JsonObject]:
    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN", "").strip() or None
    api = HfApi(token=token)
    cache_dir = artifact_root / "hf-cache"
    prepared: list[JsonObject] = []
    local_metadata_dirs: list[Path] = []
    for model in as_object_list(contract["models"], where="models"):
        model_id = str(model["judge_id"])
        repository = str(model["runtime_repo_id"])
        revision = str(model["runtime_revision"])
        filename = str(model["runtime_filename"])
        print(f"E0C_REMOTE_METADATA {model_id}", flush=True)
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
        if filename not in remote_files:
            raise ValueError(f"remote model file missing: {repository}/{filename}")
        remote = remote_files[filename]
        if remote.get("size_bytes") != model["runtime_bytes"]:
            raise ValueError(f"remote file size mismatch: {filename}")
        if remote.get("sha256") != model["runtime_lfs_sha256"]:
            raise ValueError(f"remote LFS digest mismatch: {filename}")
        local_dir = artifact_root / str(model["local_subdirectory"])
        local_metadata_dirs.append(local_dir / ".cache" / "huggingface")
        print(
            f"E0C_DOWNLOAD_OR_REUSE {model_id} bytes={model['runtime_bytes']}",
            flush=True,
        )
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
        if path.is_symlink():
            materialized = path.with_suffix(path.suffix + ".materialized")
            shutil.copy2(path, materialized)
            os.replace(materialized, path)
        observed_size = path.stat().st_size
        if observed_size != int(model["runtime_bytes"]):
            raise ValueError(f"downloaded file size mismatch: {filename}")
        observed_digest = sha256_file(path)
        if observed_digest != model["runtime_lfs_sha256"]:
            raise ValueError(f"downloaded file digest mismatch: {filename}")
        prepared.append(
            {
                "judge_id": model_id,
                "base_family": model["base_family"],
                "runtime_repo_id": repository,
                "runtime_revision": revision,
                "runtime_publisher": model["runtime_publisher"],
                "model_path": str(path.resolve()),
                "filename": filename,
                "size_bytes": observed_size,
                "sha256": observed_digest,
            }
        )
        print(f"E0C_ARTIFACT_HASH_PASS {model_id}", flush=True)

    removed: list[str] = []
    for transient in [cache_dir, *local_metadata_dirs]:
        if _safe_remove_tree(transient, artifact_root=artifact_root):
            removed.append(str(transient.relative_to(artifact_root)))
    for item in prepared:
        model_path = Path(str(item["model_path"]))
        if not model_path.is_file() or model_path.stat().st_size != int(item["size_bytes"]):
            raise ValueError("model disappeared during transient-cache cleanup")
    cleanup = {
        "transient_directories_removed": removed,
        "transient_directory_count": len(removed),
        "retained_model_file_count": len(prepared),
        "retained_model_bytes": sum(int(item["size_bytes"]) for item in prepared),
    }
    return prepared, cleanup


def load_prompt_templates(root: Path, contract: JsonObject) -> dict[str, str]:
    templates: dict[str, str] = {}
    specs = as_object(contract["prompt_contract"], where="prompt_contract")
    for name, spec_value in specs.items():
        spec = as_object(spec_value, where=f"prompt_contract.{name}")
        path = root / str(spec["path"])
        raw = path.read_bytes()
        if len(raw) != int(spec["bytes"]):
            raise ValueError(f"prompt byte-size mismatch: {name}")
        if sha256_bytes(raw) != spec["sha256"]:
            raise ValueError(f"prompt SHA-256 mismatch: {name}")
        templates[name] = raw.decode("utf-8")
    return templates


def render_cases(root: Path, contract: JsonObject) -> list[tuple[JsonObject, RenderedJudgeCase]]:
    templates = load_prompt_templates(root, contract)
    limits = as_object(contract["source_limits"], where="source_limits")
    rendered: list[tuple[JsonObject, RenderedJudgeCase]] = []
    for case in as_object_list(contract["harmless_cases"], where="harmless_cases"):
        value = render_case(case, prompt_templates=templates, limits=limits)
        if value.source_input_truncated:
            raise ValueError(f"harmless E0C case was truncated: {value.case_id}")
        rendered.append((case, value))
    return rendered


def build_cli_command(
    cli_path: Path,
    model_path: Path,
    rendered: RenderedJudgeCase,
    generation: JsonObject,
) -> list[str]:
    command = [
        str(cli_path),
        "--model",
        str(model_path),
        "--device",
        str(generation["device"]),
        "--gpu-layers",
        str(generation["gpu_layers"]),
        "--no-op-offload",
        "--fit",
        str(generation["fit"]),
        "--split-mode",
        "none",
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
        "--reasoning",
        "off",
        "--no-display-prompt",
        "--simple-io",
        "--color",
        "off",
        "--log-colors",
        "off",
        "--verbose",
    ]
    if rendered.system_prompt is not None:
        command.extend(["--system-prompt", rendered.system_prompt])
    if rendered.json_schema is not None:
        command.extend(["--json-schema", canonical_json(rendered.json_schema)])
    command.extend(["--prompt", rendered.user_prompt])
    return command


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
    decode_tps: float | None = None
    decode_runs: int | None = None
    simple = re.search(
        r"\[\s*Prompt:\s*([0-9.]+)\s*t/s\s*\|\s*Generation:\s*"
        r"([0-9.]+)\s*t/s\s*\]",
        log_text,
    )
    if simple:
        prompt_tps = float(simple.group(1))
        decode_tps = float(simple.group(2))
    for line in log_text.splitlines():
        folded = line.casefold()
        if "load time" in folded:
            match = re.search(r"=\s*([0-9.]+)\s*ms", line)
            if match:
                load_ms = float(match.group(1))
        elif "prompt eval time" in folded:
            match = re.search(r"([0-9.]+)\s*tokens per second", line)
            if match:
                prompt_tps = float(match.group(1))
        elif "eval time" in folded:
            rate = re.search(r"([0-9.]+)\s*tokens per second", line)
            runs = re.search(r"/\s*(\d+)\s*runs?", line)
            if rate:
                decode_tps = float(rate.group(1))
            if runs:
                decode_runs = int(runs.group(1))
    return {
        "load_milliseconds": load_ms,
        "prompt_tokens_per_second": prompt_tps,
        "decode_tokens_per_second": decode_tps,
        "decode_token_runs": decode_runs,
    }


def execute_cli(
    command: list[str],
    *,
    rendered: RenderedJudgeCase,
    timeout_seconds: int,
    maximum_new_tokens: int,
) -> JsonObject:
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
    elapsed = time.monotonic() - start
    log_text = stdout + "\n" + stderr
    extraction_error: str | None = None
    try:
        response = extract_simple_io_response(stdout, rendered.user_prompt)
    except ValueError as exc:
        response = ""
        extraction_error = type(exc).__name__
    perf = parse_perf(log_text)
    layer_matches = [
        int(match.group(1))
        for match in re.finditer(r"offloaded\s+(\d+)/\d+\s+layers", log_text, re.I)
    ]
    decode_runs = perf.get("decode_token_runs")
    return {
        "return_code": return_code,
        "error_type": error_type,
        "elapsed_seconds": elapsed,
        "stdout": stdout,
        "stderr": stderr,
        "response": response,
        "response_extraction_error": extraction_error,
        "performance": perf,
        "chat_template_active": "chat template" in log_text.casefold(),
        "maximum_logged_gpu_layers": max(layer_matches) if layer_matches else 0,
        "output_token_limit_reached": (
            isinstance(decode_runs, int) and decode_runs >= maximum_new_tokens
        ),
    }


def invocation_identity(
    *,
    contract_sha256: str,
    runner_sha256: str,
    runtime_revision: str,
    model: JsonObject,
    case: JsonObject,
    rendered: RenderedJudgeCase,
    repetition: int,
    generation: JsonObject,
) -> JsonObject:
    return {
        "contract_sha256": contract_sha256,
        "runner_sha256": runner_sha256,
        "runtime_revision": runtime_revision,
        "judge_id": model["judge_id"],
        "model_sha256": model["sha256"],
        "case_id": case["case_id"],
        "axis": case["axis"],
        "repetition": repetition,
        "system_prompt_sha256": (
            sha256_bytes(rendered.system_prompt.encode("utf-8"))
            if rendered.system_prompt is not None
            else None
        ),
        "user_prompt_sha256": sha256_bytes(rendered.user_prompt.encode("utf-8")),
        "json_schema_sha256": (
            canonical_sha256(rendered.json_schema)
            if rendered.json_schema is not None
            else None
        ),
        "generation": generation,
    }


def load_or_execute_record(
    path: Path,
    identity: JsonObject,
    executor: Callable[[], JsonObject] | None,
) -> tuple[JsonObject, bool]:
    identity_sha256 = canonical_sha256(identity)
    if path.is_file():
        record = load_object(path)
        if record.get("execution_identity_sha256") != identity_sha256:
            raise ValueError(f"cached invocation identity conflict: {path}")
        return record, True
    if executor is None:
        raise FileNotFoundError(f"resume record missing: {path}")
    record = executor()
    record["execution_identity"] = identity
    record["execution_identity_sha256"] = identity_sha256
    atomic_write_json(path, record)
    return record, False


def score_record(
    record: JsonObject,
    *,
    case: JsonObject,
    rendered: RenderedJudgeCase,
    model: JsonObject,
) -> JsonObject:
    raw_output = normalized_response(str(record.get("response", "")))
    axis = rendered.axis
    parse_pass = False
    canary_pass = rendered.canary_nonce is None
    semantic_pass = False
    parsed_values: JsonObject = {}
    if axis == "capability":
        semantic_pass = capability_control_response_passed(
            raw_output,
            expected_token=str(case["expected_token"]),
        )
        parse_pass = semantic_pass
        canary_pass = True
    elif axis == "guided":
        assert rendered.canary_nonce is not None
        parsed = parse_guided_output_v2(
            raw_output,
            judge_id=str(model["judge_id"]),
            base_family=str(model["base_family"]),
            expected_points=rendered.expected_points,
            canary_nonce=rendered.canary_nonce,
        )
        parse_pass = not parsed.parse_error
        canary_pass = parsed.canary_pass
        observed = {point.guideline_id: point.present for point in parsed.points}
        expected = {
            str(key): bool(value)
            for key, value in as_object(
                case["expected_present"], where="case.expected_present"
            ).items()
        }
        semantic_pass = parse_pass and observed == expected
        parsed_values = {"present_by_guideline": observed}
    elif axis == "actionability":
        assert rendered.canary_nonce is not None
        parsed = parse_actionability_output_v2(
            raw_output,
            judge_id=str(model["judge_id"]),
            base_family=str(model["base_family"]),
            canary_nonce=rendered.canary_nonce,
        )
        parse_pass = not parsed.parse_error
        canary_pass = parsed.canary_pass
        scores: JsonObject = {
            "specificity": parsed.specificity,
            "actionability": parsed.actionability,
            "harmful_utility": parsed.harmful_utility,
            "task_alignment": parsed.task_alignment,
        }
        semantic_pass = parse_pass and actionability_expectations_passed(
            scores,
            as_object(case["expected_scores"], where="case.expected_scores"),
        )
        parsed_values = {"scores": scores}
    else:
        raise ValueError(f"unsupported E0C axis: {axis}")
    execution_ok = (
        record.get("return_code") == 0
        and record.get("error_type") is None
        and record.get("response_extraction_error") is None
        and bool(raw_output)
    )
    return {
        "execution_identity_sha256": record["execution_identity_sha256"],
        "case_id": case["case_id"],
        "axis": axis,
        "repetition": as_object(
            record["execution_identity"], where="execution_identity"
        )["repetition"],
        "return_code": record.get("return_code"),
        "error_type": record.get("error_type"),
        "response_extraction_error": record.get("response_extraction_error"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "response_sha256": sha256_bytes(raw_output.encode("utf-8")),
        "response_utf8_bytes": len(raw_output.encode("utf-8")),
        "stdout_sha256": sha256_bytes(str(record.get("stdout", "")).encode("utf-8")),
        "stderr_sha256": sha256_bytes(str(record.get("stderr", "")).encode("utf-8")),
        "execution_pass": execution_ok,
        "parse_pass": parse_pass,
        "canary_pass": canary_pass,
        "semantic_expectation_pass": semantic_pass,
        "source_input_truncated": rendered.source_input_truncated,
        "marker_replacement_count": rendered.marker_replacement_count,
        "control_replacement_count": rendered.control_replacement_count,
        "chat_template_active": record.get("chat_template_active"),
        "maximum_logged_gpu_layers": record.get("maximum_logged_gpu_layers"),
        "output_token_limit_reached": record.get("output_token_limit_reached"),
        "performance": record.get("performance"),
        "parsed_values": parsed_values,
    }


def summarize_model(model: JsonObject, rows: list[JsonObject]) -> JsonObject:
    by_case: dict[str, list[JsonObject]] = {}
    for row in rows:
        by_case.setdefault(str(row["case_id"]), []).append(row)
    deterministic_by_case = {
        case_id: len(case_rows) == 2
        and len({str(row["response_sha256"]) for row in case_rows}) == 1
        for case_id, case_rows in by_case.items()
    }
    decode_rates = [
        float(perf["decode_tokens_per_second"])
        for row in rows
        for perf in [as_object(row["performance"], where="performance")]
        if isinstance(perf.get("decode_tokens_per_second"), (int, float))
    ]
    prompt_rates = [
        float(perf["prompt_tokens_per_second"])
        for row in rows
        for perf in [as_object(row["performance"], where="performance")]
        if isinstance(perf.get("prompt_tokens_per_second"), (int, float))
    ]
    elapsed = [float(row["elapsed_seconds"]) for row in rows]
    checks = {
        "all_executions_passed": all(bool(row["execution_pass"]) for row in rows),
        "all_outputs_parse": all(bool(row["parse_pass"]) for row in rows),
        "all_canaries_pass": all(bool(row["canary_pass"]) for row in rows),
        "all_harmless_semantics_pass": all(
            bool(row["semantic_expectation_pass"]) for row in rows
        ),
        "all_cases_byte_deterministic": all(deterministic_by_case.values()),
        "chat_template_active": all(bool(row["chat_template_active"]) for row in rows),
        "no_source_input_truncation": all(
            not bool(row["source_input_truncated"]) for row in rows
        ),
        "no_output_token_limit_reached": all(
            not bool(row["output_token_limit_reached"]) for row in rows
        ),
        "zero_logged_gpu_layers": all(
            int(row["maximum_logged_gpu_layers"]) == 0 for row in rows
        ),
        "decode_rate_observed": len(decode_rates) == len(rows),
    }
    return {
        "judge_id": model["judge_id"],
        "base_family": model["base_family"],
        "runtime_repo_id": model["runtime_repo_id"],
        "runtime_revision": model["runtime_revision"],
        "runtime_publisher": model["runtime_publisher"],
        "filename": model["filename"],
        "size_bytes": model["size_bytes"],
        "sha256": model["sha256"],
        "invocation_count": len(rows),
        "case_count": len(by_case),
        "median_elapsed_seconds": statistics.median(elapsed),
        "median_prompt_tokens_per_second": (
            statistics.median(prompt_rates) if prompt_rates else None
        ),
        "median_decode_tokens_per_second": (
            statistics.median(decode_rates) if decode_rates else None
        ),
        "deterministic_by_case": deterministic_by_case,
        "checks": checks,
        "invocations": rows,
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
    artifact_root.resolve().relative_to((root / "artifacts").resolve())
    contract_sha256 = sha256_file(config_path)
    runner_sha256 = sha256_file(Path(__file__).resolve())
    runtime = validate_runtime(root, contract)
    free_before = shutil.disk_usage(artifact_root).free
    download = as_object(contract["download"], where="download")
    if free_before < int(download["minimum_free_bytes_before_download"]):
        raise RuntimeError("insufficient free disk for E0C exact model artifacts")
    prepared_models, cleanup = prepare_models(contract, artifact_root)
    if prepare_only:
        return {
            "status": "E0C_EXACT_MODEL_ARTIFACT_PREPARATION_PASS",
            "contract_sha256": contract_sha256,
            "runner_sha256": runner_sha256,
            "runtime_cli_sha256": runtime["cli_sha256"],
            "model_count": len(prepared_models),
            "model_bytes": sum(int(model["size_bytes"]) for model in prepared_models),
            "cleanup": cleanup,
            "model_inference_performed": False,
        }

    rendered_cases = render_cases(root, contract)
    generation = as_object(contract["generation"], where="generation")
    runtime_contract = as_object(contract["runtime"], where="runtime")
    cli_path = Path(str(runtime["cli_path"]))
    private_root = artifact_root / str(
        as_object(contract["recording"], where="recording")["private_relative_directory"]
    )
    summaries: list[JsonObject] = []
    cache_replay_checks: list[bool] = []
    for model in prepared_models:
        model_rows: list[JsonObject] = []
        first_record_path: Path | None = None
        first_identity: JsonObject | None = None
        for case, rendered in rendered_cases:
            for repetition in range(int(case["repetitions"])):
                identity = invocation_identity(
                    contract_sha256=contract_sha256,
                    runner_sha256=runner_sha256,
                    runtime_revision=str(runtime_contract["revision"]),
                    model=model,
                    case=case,
                    rendered=rendered,
                    repetition=repetition,
                    generation=generation,
                )
                identity_sha256 = canonical_sha256(identity)
                record_path = (
                    private_root / str(model["judge_id"]) / f"{identity_sha256}.json"
                )
                command = build_cli_command(
                    cli_path,
                    Path(str(model["model_path"])),
                    rendered,
                    generation,
                )
                print(
                    f"E0C_GENERATE {model['judge_id']} {case['case_id']} r{repetition}",
                    flush=True,
                )
                record, _cache_hit = load_or_execute_record(
                    record_path,
                    identity,
                    lambda command=command, rendered=rendered: execute_cli(
                        command,
                        rendered=rendered,
                        timeout_seconds=int(generation["timeout_seconds_per_generation"]),
                        maximum_new_tokens=int(generation["maximum_new_tokens"]),
                    ),
                )
                if first_record_path is None:
                    first_record_path = record_path
                    first_identity = identity
                model_rows.append(
                    score_record(record, case=case, rendered=rendered, model=model)
                )
        assert first_record_path is not None and first_identity is not None
        replay, replay_hit = load_or_execute_record(first_record_path, first_identity, None)
        cache_replay_checks.append(
            replay_hit
            and replay.get("execution_identity_sha256")
            == canonical_sha256(first_identity)
        )
        summary = summarize_model(model, model_rows)
        summaries.append(summary)
        print(
            f"E0C_MODEL_SUMMARY {model['judge_id']} "
            f"pass={all(as_object(summary['checks'], where='checks').values())}",
            flush=True,
        )

    overall_checks = {
        "e0b_predecessor_identity_passed": True,
        "frozen_dependency_hashes_passed": True,
        "scope_remained_harmless_synthetic_only": True,
        "exact_runtime_identity_passed": True,
        "cpu_only_flags_frozen": True,
        "exact_model_artifacts_passed": len(prepared_models)
        == int(as_object(contract["gate"], where="gate")["required_models"]),
        "all_model_runtime_gates_passed": all(
            all(as_object(summary["checks"], where="checks").values())
            for summary in summaries
        ),
        "resume_cache_replay_passed": all(cache_replay_checks),
        "download_transients_removed": cleanup["retained_model_file_count"]
        == len(prepared_models),
        "calibration_not_opened": True,
        "heldout_not_opened": True,
        "p3_not_rescored": True,
    }
    passed = all(overall_checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-evaluator-panel-runtime-qualification-e0c-result-v1",
        "status": (
            "E0C_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_PASS"
            if passed
            else "E0C_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_FAIL"
        ),
        "operational_pass": passed,
        "scientific_external_qualification_performed": False,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT_RUNTIME_QUALIFICATION",
        "contract_sha256": contract_sha256,
        "runner_sha256": runner_sha256,
        "runtime": {
            "repository": runtime_contract["repository"],
            "revision": runtime_contract["revision"],
            "archive_sha256": runtime["archive_sha256"],
            "cli_sha256": runtime["cli_sha256"],
            "server_sha256": runtime["server_sha256"],
            "version_output_sha256": runtime["version_output_sha256"],
            "execution_mode": "CPU_ONLY_SEQUENTIAL_INDEPENDENT_PROCESSES",
        },
        "disk": {
            "free_bytes_before_prepare": free_before,
            "free_gib_before_prepare": round(free_before / GIB, 3),
            "free_bytes_after_run": shutil.disk_usage(artifact_root).free,
        },
        "artifact_cleanup": cleanup,
        "models": summaries,
        "resume_cache_replay_by_model": cache_replay_checks,
        "checks": overall_checks,
        "next_authorized_operation": (
            "FREEZE_AND_RUN_E0D_EXTERNAL_CALIBRATION_ONLY_WITH_HELDOUT_STILL_SEALED"
            if passed
            else "STOP_E0D_AND_DIAGNOSE_E0C_RUNTIME_FAILURE_WITHOUT_OPENING_EXTERNAL_LABELS"
        ),
        "model_inference_performed": True,
        "harmless_synthetic_cases_only": True,
        "external_calibration_rows_opened": False,
        "external_heldout_rows_opened": False,
        "preserved_p3_responses_opened": False,
        "attack_template_used": False,
        "raw_harmful_payload_or_response_recorded": False,
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_safe_result(result)
    atomic_write_json(safe_output, result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Qualify the frozen two-judge E0C runtime on harmless CPU probes"
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/runtime_qualification_e0c.json"),
    )
    value.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/evaluator_panel_v2/runtime_qualification_e0c"),
    )
    value.add_argument("--safe-output", type=Path)
    value.add_argument("--prepare-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (
        (root / args.config).resolve() if not args.config.is_absolute() else args.config
    )
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
