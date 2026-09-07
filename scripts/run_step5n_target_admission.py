"""Run the frozen Step 5N harmless admission for the final target-model pair.

The runner may download only the pinned Gemma text GGUF.  It never materializes an
attack, reads a confirmation payload, invokes an evaluator, or opens a C1N outcome.
Each harmless invocation is atomically checkpointed and safely projected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_local_q4_runtime_qualification_p2 as p2  # noqa: E402
import run_local_signal_screen_p3 as p3  # noqa: E402
import run_topology_d2_micro_pilot_v1_1 as extraction  # noqa: E402

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
DEFAULT_CONFIG = Path("configs/natural_language_localization/step5n_h4rm3l_confirmation_v1.json")
SCHEMA = "jbspan-step5n-h4rm3l-confirmation-v1"
STATUS = "FROZEN_AFTER_AUTHOR_NARROW_APPROVAL_BEFORE_GEMMA_DOWNLOAD_OR_C1N_OUTPUT"
PASS_STATUS = "STEP5N_PREFERRED_TARGET_ADMISSION_PASS"
FAIL_STATUS = "STEP5N_PREFERRED_TARGET_ADMISSION_FAIL"
PRIVATE_KEYS = {"prompt", "response", "stdout", "stderr", "payload"}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run Step 5N harmless target admission")
    value.add_argument(
        "command",
        choices=("preflight", "prepare", "run", "finalize", "status"),
    )
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return cast(JsonRows, rows)


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def safe_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def safe_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encode_jsonl(rows))
    os.replace(temporary, path)


def write_once_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    encoded = encode_jsonl(rows)
    if path.exists():
        if path.read_bytes() != encoded:
            raise RuntimeError(f"refusing to overwrite a nonidentical frozen plan: {path}")
        return "REUSED_BYTE_IDENTICAL"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)
    return "CREATED"


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def required_objects(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{where} must be a list of objects")
    return cast(list[JsonObject], value)


def resolve(root: Path, value: str | Path, *, where: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{where} escapes repository root")
    return resolved


def display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def output_paths(root: Path, contract: Mapping[str, Any]) -> dict[str, Path]:
    recording = required_mapping(contract["recording"], where="recording")
    base = resolve(root, str(recording["safe_output_root"]), where="safe output root")
    private = resolve(root, str(recording["private_root"]), where="private root")
    staging = resolve(root, str(recording["staging_root"]), where="staging root")
    return {
        "base": base,
        "preflight": base / "preflight.safe.json",
        "plan": base / "admission_plan.safe.jsonl",
        "preparation": base / "preparation.safe.json",
        "progress": base / "qualification_progress.safe.jsonl",
        "result": base / "result.safe.json",
        "verification": base / "independent_verification.safe.json",
        "private": private,
        "staging": staging,
    }


def assert_safe(value: object, *, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PRIVATE_KEYS:
                raise ValueError(f"private text field in safe value at {location}.{key}")
            assert_safe(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_safe(child, location=f"{location}[{index}]")


def verify_file(root: Path, specification: Mapping[str, Any]) -> JsonObject:
    path = resolve(root, str(specification["path"]), where="hashed file")
    exists = path.is_file()
    size = path.stat().st_size if exists else None
    digest = file_sha256(path) if exists else None
    expected_size = specification.get("size_bytes")
    return {
        "path": display(root, path),
        "exists": exists,
        "expected_size_bytes": expected_size,
        "observed_size_bytes": size,
        "size_matches": expected_size is None or size == expected_size,
        "expected_sha256": specification["sha256"],
        "observed_sha256": digest,
        "sha256_matches": digest == specification["sha256"],
    }


def file_audit_passed(value: Mapping[str, Any]) -> bool:
    return bool(value["exists"] and value["size_matches"] and value["sha256_matches"])


def validate_contract(root: Path, config_path: Path) -> tuple[JsonObject, dict[str, Path]]:
    contract = load_object(config_path)
    if (
        contract.get("schema_version") != SCHEMA
        or contract.get("status") != STATUS
        or contract.get("frozen") is not True
        or contract.get("paper_validity") is not False
    ):
        raise ValueError("Step 5N confirmation contract is not frozen at the supported boundary")
    scope = required_mapping(contract["scope_boundary"], where="scope boundary")
    if scope.get("harmless_prompt_only") is not True or any(
        scope.get(name) is not False
        for name in (
            "attack_template_allowed",
            "confirmation_payload_access_allowed",
            "attack_success_observation_allowed",
            "evaluator_call_allowed",
            "topology_outcome_allowed",
            "c1n_scientific_output_allowed",
            "paper_claim_allowed",
        )
    ):
        raise ValueError("Step 5N scope opens a prohibited scientific boundary")

    dependencies = required_mapping(contract["dependencies"], where="dependencies")
    verified: dict[str, Path] = {}
    for name, raw_specification in dependencies.items():
        specification = required_mapping(raw_specification, where=f"dependencies.{name}")
        audit = verify_file(root, specification)
        if not file_audit_passed(audit):
            raise ValueError(f"Step 5N dependency mismatch: {name}")
        path = resolve(root, str(specification["path"]), where=f"dependencies.{name}")
        verified[str(name)] = path

    code = required_mapping(contract["required_code"], where="required code")
    for name, raw_specification in code.items():
        specification = required_mapping(raw_specification, where=f"required_code.{name}")
        audit = verify_file(root, specification)
        if not file_audit_passed(audit):
            raise ValueError(f"Step 5N code mismatch: {name}")
        path = resolve(root, str(specification["path"]), where=f"required_code.{name}")
        verified[f"code_{name}"] = path
    if verified.get("code_runner") != Path(__file__).resolve():
        raise ValueError("Step 5N runner does not identify this implementation")

    authorization = load_object(verified["author_authorization"])
    if (
        authorization.get("status") != "AUTHOR_APPROVED_H4RM3L_NARROW_AND_PREFERRED_TARGET_PAIR"
        or authorization.get("official_d3_boundary", {}).get("project_route") != "NARROW"
        or authorization.get("official_d3_boundary", {}).get("cross_family_d3_gate_pass")
        is not False
        or authorization.get("authority", {}).get("may_run_harmless_qwen_and_gemma_admission")
        is not True
        or authorization.get("authority", {}).get("may_generate_c1n_scientific_target_output")
        is not False
    ):
        raise ValueError("author authorization differs from the Step 5N boundary")

    d3 = load_object(verified["d3_official_result"])
    if d3.get("status") != "D3_EXACT_TOPOLOGY_COMPLETE" or d3.get("d3_core_gate_pass") is not False:
        raise ValueError("official cross-family D3 FAIL was not preserved")
    narrow = load_object(verified["d3_narrow_audit"])
    if narrow.get("project_route_decision", {}).get("classification") != "NARROW":
        raise ValueError("D3 NARROW route differs")

    models = required_objects(contract["models"], where="models")
    model_ids = [str(item["model_id"]) for item in models]
    if model_ids != [
        "qwen2.5-7b-instruct-q4-k-m",
        "google-gemma-4-e4b-it-qat-q4-0",
    ]:
        raise ValueError("Step 5N preferred target pair differs")
    prompts = required_objects(contract["harmless_prompts"], where="harmless prompts")
    prompt_ids = [str(item["prompt_id"]) for item in prompts]
    if len(prompts) != 10 or len(set(prompt_ids)) != 10:
        raise ValueError("Step 5N harmless prompt denominator differs")
    determinism = required_mapping(contract["determinism_check"], where="determinism")
    if (
        determinism.get("prompt_id") not in prompt_ids
        or determinism.get("independent_process_repetitions") != 2
    ):
        raise ValueError("Step 5N determinism contract differs")
    gate = required_mapping(contract["gate"], where="gate")
    if (
        gate.get("required_models") != 2
        or gate.get("required_unique_harmless_prompts_per_model") != 10
        or gate.get("required_invocations_per_model") != 11
        or gate.get("minimum_capability_passes_per_model") != 10
    ):
        raise ValueError("Step 5N admission gate differs")
    return contract, verified


def install_extractor() -> None:
    p3.extract_simple_io_response = extraction.extract_simple_io_response_v3
    p3.RESPONSE_EXTRACTOR_VERSION = extraction.EXTRACTOR_VERSION


def inspect_machine(root: Path, contract: Mapping[str, Any]) -> JsonObject:
    import psutil

    floor = required_mapping(contract["machine_floor"], where="machine floor")
    matches = [row for row in p2.nvidia_rows() if row["name"] == floor["required_gpu_name"]]
    if len(matches) != 1:
        raise ValueError("Step 5N requires one exact target GPU")
    gpu = matches[0]
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(root)
    gib = 1024**3
    checks = {
        "gpu_name_matches": gpu["name"] == floor["required_gpu_name"],
        "vram_floor_met": gpu["memory_total_mib"] >= float(floor["minimum_total_vram_mib"]),
        "system_ram_floor_met": memory.total / gib >= float(floor["minimum_system_ram_gib"]),
        "disk_floor_met": disk.free / gib >= float(floor["minimum_free_disk_before_download_gib"]),
        "temperature_below_ceiling": gpu["temperature_c"]
        < float(floor["maximum_gpu_temperature_c"]),
    }
    return {
        "gpu": gpu,
        "system_ram_gib": round(memory.total / gib, 3),
        "system_ram_available_gib": round(memory.available / gib, 3),
        "disk_free_gib": round(disk.free / gib, 3),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "checks": checks,
    }


def validate_runtime(root: Path, contract: Mapping[str, Any]) -> JsonObject:
    runtime = required_mapping(contract["runtime"], where="runtime")
    files = {}
    for name in ("archive", "cli", "tokenizer"):
        audit = verify_file(
            root,
            required_mapping(runtime[name], where=f"runtime.{name}"),
        )
        files[name] = audit
        if not file_audit_passed(audit):
            raise ValueError(f"Step 5N runtime {name} mismatch")
    cli = resolve(root, runtime["cli"]["path"], where="runtime CLI")
    version = p2.run_command([str(cli), "--version"], timeout=30)
    version_text = version.stdout + version.stderr
    if version.returncode != 0 or any(
        marker not in version_text for marker in runtime["required_version_substrings"]
    ):
        raise ValueError("Step 5N llama.cpp version mismatch")
    devices = p2.run_command([str(cli), "--list-devices"], timeout=30)
    device_text = devices.stdout + devices.stderr
    required_name = str(contract["machine_floor"]["required_gpu_name"])
    matches = []
    for line in device_text.splitlines():
        match = re.match(r"\s*(Vulkan\d+):\s*(.+?)\s*\(", line)
        if match and match.group(2).strip() == required_name:
            matches.append(match.group(1))
    if devices.returncode != 0 or len(matches) != 1:
        raise ValueError("Step 5N Vulkan device identity mismatch")
    return {
        "files": files,
        "release_tag": runtime["release_tag"],
        "revision": runtime["revision"],
        "backend": runtime["backend"],
        "selected_device": matches[0],
        "selected_device_name": required_name,
        "version_output_sha256": text_sha256(version_text),
        "device_output_sha256": text_sha256(device_text),
        "_cli": str(cli),
        "_tokenizer": str(resolve(root, runtime["tokenizer"]["path"], where="runtime tokenizer")),
    }


def model_file_audits(root: Path, model: Mapping[str, Any]) -> list[JsonObject]:
    return [
        verify_file(root, required_mapping(item, where="model file"))
        for item in required_objects(model["files"], where="model files")
    ]


def model_entry(root: Path, model: Mapping[str, Any]) -> Path:
    return resolve(root, str(model["entry_path"]), where="model entry")


def build_plan(contract: Mapping[str, Any], contract_sha256: str) -> JsonRows:
    runner_sha = str(contract["required_code"]["runner"]["sha256"])
    generation = dict(required_mapping(contract["generation"], where="generation"))
    prompts = required_objects(contract["harmless_prompts"], where="harmless prompts")
    prompt_by_id = {str(item["prompt_id"]): item for item in prompts}
    determinism = required_mapping(contract["determinism_check"], where="determinism")
    determinism_id = str(determinism["prompt_id"])
    repetitions = int(determinism["independent_process_repetitions"])
    rows: JsonRows = []
    for model in required_objects(contract["models"], where="models"):
        run_plan: list[tuple[JsonObject, int]] = [(prompt, 0) for prompt in prompts]
        for replicate_index in range(1, repetitions):
            run_plan.append((prompt_by_id[determinism_id], replicate_index))
        file_hashes = [str(item["sha256"]) for item in model["files"]]
        for prompt, replicate_index in run_plan:
            core = {
                "contract_sha256": contract_sha256,
                "runner_sha256": runner_sha,
                "model_id": model["model_id"],
                "model_runtime_repository": model["runtime_repository"],
                "model_runtime_revision": model["runtime_revision"],
                "model_file_sha256s": file_hashes,
                "prompt_id": prompt["prompt_id"],
                "prompt_sha256": text_sha256(str(prompt["text"])),
                "seed": generation["seed"],
                "replicate_index": replicate_index,
                "generation_parameters": generation,
            }
            rows.append(
                {
                    "record_id": canonical_sha256(core),
                    "execution_order": len(rows),
                    **core,
                }
            )
    if len(rows) != 22 or len({str(row["record_id"]) for row in rows}) != 22:
        raise ValueError("Step 5N admission plan denominator differs")
    return rows


def validated_existing_result(path: Path, *, schema: str, config_sha256: str) -> JsonObject | None:
    if not path.exists():
        return None
    existing = load_object(path)
    identity = existing.get("result_identity_sha256")
    body = dict(existing)
    body.pop("result_identity_sha256", None)
    if (
        existing.get("schema_version") != schema
        or existing.get("contract_sha256") != config_sha256
        or not isinstance(identity, str)
        or canonical_sha256(body) != identity
    ):
        raise ValueError(f"existing Step 5N result identity is invalid: {path}")
    return existing


def preflight(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract, verified = validate_contract(root, config_path)
    contract_sha = file_sha256(config_path)
    paths = output_paths(root, contract)
    existing = validated_existing_result(
        paths["preflight"],
        schema="jbspan-step5n-target-admission-preflight-v1",
        config_sha256=contract_sha,
    )
    if existing is not None:
        plan = build_plan(contract, contract_sha)
        if not paths["plan"].is_file() or file_sha256(paths["plan"]) != existing["plan_sha256"]:
            raise ValueError("existing Step 5N preflight plan differs")
        if load_jsonl(paths["plan"]) != plan:
            raise ValueError("existing Step 5N plan content differs")
        return existing

    machine = inspect_machine(root, contract)
    runtime = validate_runtime(root, contract)
    models = required_objects(contract["models"], where="models")
    qwen_audits = model_file_audits(root, models[0])
    if not all(file_audit_passed(item) for item in qwen_audits):
        raise ValueError("existing Qwen target artifacts differ")
    gemma_audits = model_file_audits(root, models[1])
    gemma_state_ok = all(file_audit_passed(item) for item in gemma_audits) or all(
        not item["exists"] for item in gemma_audits
    )
    if not gemma_state_ok:
        raise ValueError("partial or mismatching Gemma artifact exists before preparation")
    plan = build_plan(contract, contract_sha)
    write_once_jsonl(paths["plan"], plan)
    scientific_paths = [
        resolve(root, item, where="scientific output root")
        for item in contract["scientific_output_absence_roots"]
    ]
    scientific_files = sum(
        len([item for item in path.rglob("*") if item.is_file()]) if path.exists() else 0
        for path in scientific_paths
    )
    checks = {
        "all_dependencies_and_code_match": bool(verified),
        "author_authorized_step5n_only": True,
        "official_cross_family_d3_remains_failed": True,
        "machine_floor_passed": all(machine["checks"].values()),
        "runtime_identity_passed": True,
        "existing_qwen_artifacts_passed": all(file_audit_passed(item) for item in qwen_audits),
        "gemma_absent_or_exact_before_download": gemma_state_ok,
        "plan_has_exactly_22_harmless_invocations": len(plan) == 22,
        "scientific_output_absent": scientific_files == 0,
        "confirmation_payload_not_read": True,
        "target_or_evaluator_inference_not_performed": True,
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-step5n-target-admission-preflight-v1",
        "status": (
            "STEP5N_TARGET_ADMISSION_PREFLIGHT_PASS"
            if passed
            else "STEP5N_TARGET_ADMISSION_PREFLIGHT_FAIL"
        ),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "contract_path": display(root, config_path),
        "contract_sha256": contract_sha,
        "runner_sha256": file_sha256(Path(__file__).resolve()),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "machine": machine,
        "runtime": {key: value for key, value in runtime.items() if not key.startswith("_")},
        "qwen_file_audits": qwen_audits,
        "gemma_file_state_before_preparation": gemma_audits,
        "plan_path": display(root, paths["plan"]),
        "plan_sha256": file_sha256(paths["plan"]),
        "plan_identity_sha256": canonical_sha256(plan),
        "planned_invocations": len(plan),
        "checks": checks,
        "preflight_pass": passed,
        "model_download_performed": False,
        "model_inference_performed": False,
        "evaluator_inference_performed": False,
        "confirmation_payload_read": False,
        "c1n_output_opened": False,
        "raw_prompt_payload_or_response_recorded": False,
        "paper_validity": False,
        "next_operation": "PREPARE_EXACT_GEMMA_TEXT_GGUF",
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_safe(result)
    if not passed:
        raise RuntimeError("Step 5N preflight failed before model download")
    safe_write_json(paths["preflight"], result)
    return result


def remote_file_metadata(sibling: object) -> JsonObject:
    item = cast(Any, sibling)
    size = getattr(item, "size", None)
    digest = None
    lfs = getattr(item, "lfs", None)
    if isinstance(lfs, dict):
        size = lfs.get("size", size)
        digest = lfs.get("sha256")
    elif lfs is not None:
        size = getattr(lfs, "size", size)
        digest = getattr(lfs, "sha256", None)
    return {
        "filename": str(item.rfilename),
        "size_bytes": size,
        "sha256": str(digest) if digest is not None else None,
    }


def prepare(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract, _verified = validate_contract(root, config_path)
    contract_sha = file_sha256(config_path)
    paths = output_paths(root, contract)
    preflight_result = preflight(root, config_path)
    existing = validated_existing_result(
        paths["preparation"],
        schema="jbspan-step5n-target-admission-preparation-v1",
        config_sha256=contract_sha,
    )
    models = required_objects(contract["models"], where="models")
    if existing is not None:
        current = {str(model["model_id"]): model_file_audits(root, model) for model in models}
        if not all(file_audit_passed(item) for audits in current.values() for item in audits):
            raise ValueError("prepared Step 5N model bytes changed")
        return existing

    gemma = models[1]
    if gemma.get("download_in_step5n") is not True:
        raise ValueError("Gemma download is not authorized by the frozen contract")
    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN", "").strip() or None
    repository = str(gemma["runtime_repository"])
    revision = str(gemma["runtime_revision"])
    filename = str(gemma["files"][0]["filename"])
    api = HfApi(token=token)
    print(f"STEP5N_REMOTE_METADATA {repository}@{revision}", flush=True)
    info = api.model_info(repository, revision=revision, files_metadata=True, token=token)
    if str(info.sha) != revision:
        raise ValueError("Gemma remote revision differs")
    remote = {
        str(cast(Any, sibling).rfilename): remote_file_metadata(sibling)
        for sibling in info.siblings or ()
    }
    if filename not in remote:
        raise ValueError("pinned Gemma text GGUF is absent remotely")
    expected = gemma["files"][0]
    if (
        remote[filename]["size_bytes"] != expected["size_bytes"]
        or remote[filename]["sha256"] != expected["sha256"]
    ):
        raise ValueError("Gemma remote size or LFS digest differs")
    if any(value in filename.casefold() for value in ("mmproj", "vision", "projector")):
        raise ValueError("multimodal projector download is forbidden")
    destination = model_entry(root, gemma)
    destination.parent.mkdir(parents=True, exist_ok=True)
    download_performed = not destination.is_file()
    if download_performed:
        print(f"STEP5N_DOWNLOAD {filename} bytes={expected['size_bytes']}", flush=True)
        downloaded = Path(
            hf_hub_download(
                repo_id=repository,
                revision=revision,
                filename=filename,
                local_dir=destination.parent,
                token=token,
            )
        ).resolve()
        if downloaded != destination:
            raise ValueError("Gemma download resolved to an unexpected path")
    audits = {str(model["model_id"]): model_file_audits(root, model) for model in models}
    if not all(file_audit_passed(item) for values in audits.values() for item in values):
        raise ValueError("Step 5N model artifact verification failed")
    gemma_cache = destination.parent / ".cache" / "huggingface"
    incomplete = (
        [item for item in gemma_cache.rglob("*") if item.is_file() and ".incomplete" in item.name]
        if gemma_cache.exists()
        else []
    )
    checks = {
        "preflight_passed": preflight_result["preflight_pass"] is True,
        "remote_revision_matches": str(info.sha) == revision,
        "remote_size_and_lfs_sha256_match": True,
        "only_text_gguf_requested": True,
        "all_local_model_hashes_match": True,
        "no_incomplete_download_residue": not incomplete,
        "no_model_inference_performed": True,
    }
    result: JsonObject = {
        "schema_version": "jbspan-step5n-target-admission-preparation-v1",
        "status": "STEP5N_TARGET_ARTIFACT_PREPARATION_PASS",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "contract_sha256": contract_sha,
        "preflight_identity_sha256": preflight_result["result_identity_sha256"],
        "remote_repository": repository,
        "remote_revision": revision,
        "requested_filename": filename,
        "remote_file_metadata": remote[filename],
        "model_file_audits": audits,
        "download_performed": download_performed,
        "downloaded_multimodal_projector": False,
        "incomplete_download_file_count": len(incomplete),
        "checks": checks,
        "preparation_pass": all(checks.values()),
        "model_inference_performed": False,
        "evaluator_inference_performed": False,
        "confirmation_payload_read": False,
        "c1n_output_opened": False,
        "raw_prompt_payload_or_response_recorded": False,
        "paper_validity": False,
        "next_operation": "RUN_22_HARMLESS_TARGET_ADMISSION_INVOCATIONS",
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_safe(result)
    safe_write_json(paths["preparation"], result)
    return result


def validate_progress(plan: Sequence[Mapping[str, Any]], path: Path) -> JsonRows:
    if not path.exists():
        return []
    rows = load_jsonl(path)
    if len(rows) > len(plan):
        raise ValueError("Step 5N progress exceeds the frozen plan")
    for index, row in enumerate(rows):
        expected = plan[index]
        if (
            row.get("record_id") != expected["record_id"]
            or row.get("execution_order") != index
            or row.get("model_id") != expected["model_id"]
            or row.get("prompt_id") != expected["prompt_id"]
            or row.get("replicate_index") != expected["replicate_index"]
        ):
            raise ValueError("Step 5N progress is not an exact plan prefix")
        assert_safe(row)
    return rows


def safe_invocation_row(
    plan: Mapping[str, Any],
    prompt: Mapping[str, Any],
    private: Mapping[str, Any],
    private_path: Path,
    maximum_new_tokens: int,
    *,
    cache_hit: bool,
) -> JsonObject:
    base = p3.safe_invocation(dict(private), maximum_new_tokens)
    response = p3.normalized_response(str(private.get("response", "")))
    prompt_echo = p2.comparison_text(str(prompt["text"])) in p2.comparison_text(response)
    required = [str(value) for value in prompt["required_normalized_substrings"]]
    capability = p2.capability_pass(response, required) and not prompt_echo
    row: JsonObject = {
        "record_id": plan["record_id"],
        "execution_order": plan["execution_order"],
        "model_id": plan["model_id"],
        "model_runtime_revision": plan["model_runtime_revision"],
        "prompt_id": plan["prompt_id"],
        "prompt_sha256": plan["prompt_sha256"],
        "replicate_index": plan["replicate_index"],
        "seed": plan["seed"],
        "private_record_sha256": file_sha256(private_path),
        "cache_hit_this_invocation": cache_hit,
        "capability_pass": capability,
        "prompt_echo_detected": prompt_echo,
        **base,
    }
    assert_safe(row)
    return row


def summarize_model(
    model: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], gate: Mapping[str, Any]
) -> JsonObject:
    primary = [row for row in rows if int(row["replicate_index"]) == 0]
    sentinel = [row for row in rows if row["prompt_id"] == gate["determinism_prompt_id"]]
    decode_rates = [
        float(row["performance"]["decode_tokens_per_second"])
        for row in rows
        if isinstance(row.get("performance", {}).get("decode_tokens_per_second"), (int, float))
    ]
    load_times = [
        float(row["performance"]["load_ms"])
        for row in rows
        if isinstance(row.get("performance", {}).get("load_ms"), (int, float))
    ]
    elapsed = [
        float(row["elapsed_seconds"])
        for row in rows
        if isinstance(row.get("elapsed_seconds"), (int, float))
    ]
    peak_vram = [
        float(row["sampling"]["peak_gpu_memory_used_mib"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("peak_gpu_memory_used_mib"), (int, float))
    ]
    gpu_delta = [
        float(row["sampling"]["gpu_memory_delta_mib"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("gpu_memory_delta_mib"), (int, float))
    ]
    temperatures = [
        float(row["sampling"]["peak_gpu_temperature_c"])
        for row in rows
        if isinstance(row.get("sampling", {}).get("peak_gpu_temperature_c"), (int, float))
    ]
    median_tps = statistics.median(decode_rates) if decode_rates else None
    median_load = statistics.median(load_times) if load_times else None
    maximum_vram = max(peak_vram) if peak_vram else None
    maximum_delta = max(gpu_delta) if gpu_delta else None
    maximum_temperature = max(temperatures) if temperatures else None
    deterministic = (
        len(sentinel) == 2 and len({str(row["response_sha256"]) for row in sentinel}) == 1
    )
    successful = sum(
        row["operational_pass"] is True and row["possible_max_token_truncation"] is False
        for row in rows
    )
    capability_count = sum(row["capability_pass"] is True for row in primary)
    checks = {
        "all_generations_succeeded": successful == int(gate["required_invocations_per_model"]),
        "all_ten_capabilities_passed": capability_count
        >= int(gate["minimum_capability_passes_per_model"]),
        "decode_rate_floor_met": median_tps is not None
        and median_tps >= float(gate["minimum_median_decode_tokens_per_second"]),
        "vram_ceiling_met": maximum_vram is not None
        and maximum_vram <= float(gate["maximum_peak_vram_mib"]),
        "temperature_ceiling_met": maximum_temperature is not None
        and maximum_temperature <= float(gate["maximum_gpu_temperature_c"]),
        "chat_template_active": all(row["chat_template_active"] is True for row in rows),
        "gpu_offload_active": maximum_delta is not None
        and maximum_delta >= float(gate["minimum_gpu_memory_delta_mib"])
        and all(row["gpu_offload_logged"] is True for row in rows),
        "deterministic_replay": deterministic,
        "no_prompt_echo": all(row["prompt_echo_detected"] is False for row in rows),
        "no_max_token_truncation": all(
            row["possible_max_token_truncation"] is False for row in rows
        ),
        "private_file_extractor_v3": all(
            row["response_extractor_version"] == extraction.EXTRACTOR_VERSION for row in rows
        ),
    }
    return {
        "model_id": model["model_id"],
        "runtime_repository": model["runtime_repository"],
        "runtime_revision": model["runtime_revision"],
        "runtime_authority": model["runtime_authority"],
        "license": model["license"],
        "quantization": model["quantization"],
        "invocation_count": len(rows),
        "successful_generation_count": successful,
        "capability_pass_count": capability_count,
        "capability_prompt_count": len(primary),
        "deterministic_replay": deterministic,
        "median_load_milliseconds": median_load,
        "median_cold_process_seconds": statistics.median(elapsed) if elapsed else None,
        "median_decode_tokens_per_second": median_tps,
        "projected_512_token_seconds": (
            median_load / 1000 + 512 / median_tps
            if median_load is not None and median_tps is not None and median_tps > 0
            else None
        ),
        "maximum_peak_vram_mib": maximum_vram,
        "maximum_gpu_memory_delta_mib": maximum_delta,
        "maximum_gpu_temperature_c": maximum_temperature,
        "checks": checks,
    }


def run_qualification(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract, _verified = validate_contract(root, config_path)
    contract_sha = file_sha256(config_path)
    paths = output_paths(root, contract)
    existing = validated_existing_result(
        paths["result"],
        schema="jbspan-step5n-target-admission-result-v1",
        config_sha256=contract_sha,
    )
    if existing is not None:
        return existing
    preparation = prepare(root, config_path)
    runtime = validate_runtime(root, contract)
    machine = inspect_machine(root, contract)
    if not all(machine["checks"].values()):
        raise RuntimeError("Step 5N live machine floor failed")
    install_extractor()
    plan = load_jsonl(paths["plan"])
    if plan != build_plan(contract, contract_sha):
        raise ValueError("Step 5N frozen plan differs before qualification")
    rows = validate_progress(plan, paths["progress"])
    prompts = {
        str(item["prompt_id"]): item
        for item in required_objects(contract["harmless_prompts"], where="harmless prompts")
    }
    models = {
        str(item["model_id"]): item for item in required_objects(contract["models"], where="models")
    }
    paths["private"].mkdir(parents=True, exist_ok=True)
    paths["staging"].mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cache_hits = 0
    for item in plan[len(rows) :]:
        model = models[str(item["model_id"])]
        prompt = prompts[str(item["prompt_id"])]
        identity = {
            "kind": "STEP5N_HARMLESS_TARGET_ADMISSION",
            **{key: value for key, value in item.items() if key != "execution_order"},
            "private_file_transport": True,
            "response_extractor_version": extraction.EXTRACTOR_VERSION,
        }
        record_id = str(item["record_id"])
        private_path = paths["private"] / str(item["model_id"]) / f"{record_id}.json"
        print(
            f"STEP5N_HARMLESS {item['execution_order'] + 1}/22 "
            f"{item['model_id']} {item['prompt_id']} r{item['replicate_index']}",
            flush=True,
        )
        private, cache_hit = p3.run_private_invocation(
            identity=identity,
            prompt=str(prompt["text"]),
            payload=None,
            private_record_path=private_path,
            staging_root=paths["staging"],
            cli=Path(runtime["_cli"]),
            model=model_entry(root, model),
            parameters=dict(contract["generation"]),
            seed=int(item["seed"]),
            device=str(runtime["selected_device"]),
            required_gpu_name=str(runtime["selected_device_name"]),
        )
        cache_hits += int(cache_hit)
        row = safe_invocation_row(
            item,
            prompt,
            private,
            private_path,
            int(contract["generation"]["maximum_new_tokens"]),
            cache_hit=cache_hit,
        )
        rows.append(row)
        safe_write_jsonl(paths["progress"], rows)
    elapsed_this_invocation = time.perf_counter() - started
    if len(rows) != len(plan):
        raise RuntimeError("Step 5N qualification progress is incomplete")
    return finalize(
        root,
        config_path,
        elapsed_this_invocation=elapsed_this_invocation,
        cache_hits_this_invocation=cache_hits,
        preparation=preparation,
        machine=machine,
        runtime=runtime,
    )


def finalize(
    root: Path,
    config_path: Path,
    *,
    elapsed_this_invocation: float = 0.0,
    cache_hits_this_invocation: int = 0,
    preparation: JsonObject | None = None,
    machine: JsonObject | None = None,
    runtime: JsonObject | None = None,
) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract, _verified = validate_contract(root, config_path)
    contract_sha = file_sha256(config_path)
    paths = output_paths(root, contract)
    existing = validated_existing_result(
        paths["result"],
        schema="jbspan-step5n-target-admission-result-v1",
        config_sha256=contract_sha,
    )
    if existing is not None:
        return existing
    if preparation is None:
        preparation = prepare(root, config_path)
    if machine is None:
        machine = inspect_machine(root, contract)
    if runtime is None:
        runtime = validate_runtime(root, contract)
    plan = load_jsonl(paths["plan"])
    rows = validate_progress(plan, paths["progress"])
    if len(rows) != 22:
        raise RuntimeError("cannot finalize Step 5N before all 22 harmless calls")
    gate = dict(required_mapping(contract["gate"], where="gate"))
    gate["determinism_prompt_id"] = contract["determinism_check"]["prompt_id"]
    models = required_objects(contract["models"], where="models")
    summaries = [
        summarize_model(
            model,
            [row for row in rows if row["model_id"] == model["model_id"]],
            gate,
        )
        for model in models
    ]
    checks = {
        "author_scope_and_pair_authorized": True,
        "official_cross_family_d3_remains_failed": True,
        "preparation_passed": preparation["preparation_pass"] is True,
        "machine_floor_passed": all(machine["checks"].values()),
        "runtime_identity_passed": True,
        "exactly_22_planned_and_completed": len(plan) == len(rows) == 22,
        "both_model_gates_passed": all(all(summary["checks"].values()) for summary in summaries),
        "checkpoint_prefix_and_resume_contract_passed": True,
        "no_attack_evaluator_or_topology_output_opened": True,
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-step5n-target-admission-result-v1",
        "status": PASS_STATUS if passed else FAIL_STATUS,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "evidence_class": "HARMLESS_OPERATIONAL_TARGET_ADMISSION_NOT_PAPER_EVIDENCE",
        "contract_sha256": contract_sha,
        "runner_sha256": file_sha256(Path(__file__).resolve()),
        "preparation_identity_sha256": preparation["result_identity_sha256"],
        "plan_sha256": file_sha256(paths["plan"]),
        "progress_sha256": file_sha256(paths["progress"]),
        "invocation_count": len(rows),
        "elapsed_seconds_this_invocation": elapsed_this_invocation,
        "cache_hits_this_invocation": cache_hits_this_invocation,
        "runtime": {key: value for key, value in runtime.items() if not key.startswith("_")},
        "machine": machine,
        "models": summaries,
        "checks": checks,
        "operational_pass": passed,
        "preferred_target_pair_admitted": passed,
        "fallback_activated": False,
        "fallback_activation_allowed_only_before_c1n_output": True,
        "model_inference_performed": True,
        "harmless_prompts_only": True,
        "attack_template_used": False,
        "confirmation_payload_read": False,
        "attack_success_observed": False,
        "evaluator_inference_performed": False,
        "topology_outcome_observed": False,
        "c1n_output_opened": False,
        "raw_harmful_prompt_payload_or_response_recorded": False,
        "paper_validity": False,
        "next_operation": (
            "AUTHORIZE_SEPARATE_FROZEN_C1N_EXECUTION_CONTRACT"
            if passed
            else "MATERIALIZE_PREDECLARED_LLAMA_FALLBACK_ADMISSION_IF_FAILURE_IS_OPERATIONAL"
        ),
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_safe(result)
    safe_write_json(paths["result"], result)
    return result


def status(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path, where="config")
    contract, _verified = validate_contract(root, config_path)
    paths = output_paths(root, contract)
    plan = load_jsonl(paths["plan"]) if paths["plan"].is_file() else []
    progress = validate_progress(plan, paths["progress"]) if plan else []
    return {
        "status": "STEP5N_TARGET_ADMISSION_STATUS",
        "planned_invocations": len(plan),
        "completed_invocations": len(progress),
        "remaining_invocations": len(plan) - len(progress),
        "preflight_exists": paths["preflight"].is_file(),
        "preparation_exists": paths["preparation"].is_file(),
        "result_exists": paths["result"].is_file(),
        "verification_exists": paths["verification"].is_file(),
        "model_invoked_by_status": False,
        "evaluator_invoked_by_status": False,
        "c1n_output_opened": False,
    }


def main() -> int:
    arguments = parser().parse_args()
    root = arguments.root.resolve()
    config = arguments.config
    if arguments.command == "preflight":
        result = preflight(root, config)
    elif arguments.command == "prepare":
        result = prepare(root, config)
    elif arguments.command == "run":
        result = run_qualification(root, config)
    elif arguments.command == "finalize":
        result = finalize(root, config)
    else:
        result = status(root, config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    if arguments.command in {"preflight", "prepare"}:
        return 0 if result.get("preflight_pass", result.get("preparation_pass")) else 1
    if arguments.command in {"run", "finalize"}:
        return 0 if result.get("operational_pass") is True else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
