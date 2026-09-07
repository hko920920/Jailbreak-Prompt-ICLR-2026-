from __future__ import annotations

import argparse
import csv
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jbspan.evaluator_heldout_inputs import HeldoutInputRecord
from jbspan.fresh_screen_funnel import (
    FAMILIES,
    SEEDS,
    active_pairs_for_seed,
    canonical_sha256,
    decide_active_pairs,
    merge_pair_decisions,
    plan_rows,
    record_decisions,
    routing,
    selected_h4rm3l_pairs,
)

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
SHA256_LENGTH = 64


@dataclass(frozen=True, slots=True)
class EvaluatorInput:
    record: HeldoutInputRecord
    metadata: JsonObject


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run the prospective fresh 2R screen")
    value.add_argument(
        "command",
        choices=(
            "preflight",
            "generate",
            "qwen",
            "jailmeter",
            "finalize-phase",
            "finalize",
            "status",
        ),
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/natural_language_localization/fresh_screen_2r_v1.json"),
    )
    value.add_argument("--seed", type=int, choices=SEEDS)
    return value


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    rows: JsonRows = []
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


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode()


def safe_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def safe_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encode_jsonl(rows))
    temporary.replace(path)


def write_once_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    payload = encode_jsonl(rows)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite a nonidentical frozen plan: {path}")
        return "REUSED_BYTE_IDENTICAL"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return "CREATED"


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def rooted(root: Path, value: object, *, where: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a nonempty relative path")
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{where} escapes the repository root")
    return path


def repo_module(root: Path, name: str) -> Any:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return importlib.import_module(name)


def verify_file(root: Path, spec: Mapping[str, Any], *, where: str) -> Path:
    path = rooted(root, spec.get("path"), where=f"{where}.path")
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = spec.get("sha256")
    if not isinstance(expected, str) or len(expected) != SHA256_LENGTH:
        raise ValueError(f"{where}.sha256 is invalid")
    if file_sha256(path) != expected:
        raise ValueError(f"{where} hash mismatch: {path}")
    return path


def find_prohibited_keys(value: object, path: str = "$") -> tuple[str, ...]:
    prohibited = {
        "payload",
        "prompt",
        "response",
        "response_text",
        "goal_text",
        "assistant_response",
        "human_request",
        "content",
        "raw_output",
        "stdout",
        "stderr",
        "input_token_ids",
    }
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in prohibited:
                found.append(child_path)
            found.extend(find_prohibited_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_prohibited_keys(child, f"{path}[{index}]"))
    return tuple(found)


def load_config(root: Path, config_path: Path) -> tuple[Path, JsonObject, dict[str, Path]]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config_path = config_path.resolve()
    if not config_path.is_relative_to(root):
        raise ValueError("2R config escapes the repository root")
    config = load_object(config_path)
    if (
        config.get("schema_version") != "jbspan-fresh-screen-2r-contract-v1"
        or config.get("status") != "FROZEN_PROSPECTIVE_AFTER_D1_BEFORE_2R_OUTPUT"
        or config.get("frozen") is not True
    ):
        raise ValueError("2R config is not the supported frozen prospective contract")
    dependencies = required_mapping(config.get("dependencies"), where="dependencies")
    verified = {
        str(name): verify_file(
            root, required_mapping(spec, where=f"dependencies.{name}"), where=str(name)
        )
        for name, spec in dependencies.items()
    }
    payloads = load_jsonl(verified["payload_manifest"])
    if len(payloads) != 37 or [int(row["position"]) for row in payloads] != list(range(37)):
        raise ValueError("2R frozen payload denominator or positions differ")
    audit = load_object(verified["payload_audit"])
    if (
        audit.get("status") != "FRESH_2R_SOURCE_EXHAUSTIVE_PAYLOAD_FREEZE_PASS"
        or audit.get("fresh_payloads") != 37
        or audit.get("manifest_sha256") != file_sha256(verified["payload_manifest"])
    ):
        raise ValueError("2R payload audit mismatch")
    d1 = load_object(verified["d1_result"])
    if (
        d1.get("status") != "D1_P3_E0G5_RESCORE_COMPLETE"
        or d1.get("routing", {}).get("stable_pairs") != 0
        or d1.get("routing", {}).get("unresolved_pairs") != 6
    ):
        raise ValueError("2R parent D1 outcome differs from the disclosed redesign trigger")
    d1_verification = load_object(verified["d1_verification"])
    if d1_verification.get("status") != "D1_INDEPENDENT_RECONSTRUCTION_PASS":
        raise ValueError("2R parent D1 independent verification did not pass")
    panel_result = load_object(verified["e0g5_result"])
    if (
        panel_result.get("status") != "E0G5_PRIMARY_HELDOUT_QUALIFICATION_PASS"
        or panel_result.get("primary_panel_qualified_for_topology_candidate") is not True
    ):
        raise ValueError("2R evaluator panel is not qualified")
    funnel = required_mapping(config.get("funnel"), where="funnel")
    if (
        funnel.get("seeds") != list(SEEDS)
        or funnel.get("attack_families") != list(FAMILIES)
        or funnel.get("initial_payloads") != 37
        or funnel.get("initial_pairs") != 74
        or funnel.get("minimum_pairs_in_one_family_to_continue") != 2
    ):
        raise ValueError("2R funnel contract differs from the implemented exact gate")
    return config_path, config, verified


def output_directory(root: Path, config: Mapping[str, Any]) -> Path:
    recording = required_mapping(config["recording"], where="recording")
    return rooted(root, recording["output_directory"], where="output directory")


def phase_paths(root: Path, config: Mapping[str, Any], seed: int) -> dict[str, Path]:
    base = output_directory(root, config)
    prefix = f"phase_{seed}"
    return {
        "plan": base / f"{prefix}_plan.safe.jsonl",
        "generation_progress": base / f"{prefix}_generation_progress.safe.jsonl",
        "generation": base / f"{prefix}_generation.safe.jsonl",
        "generation_summary": base / f"{prefix}_generation_summary.safe.json",
        "qwen_progress": base / f"{prefix}_qwen_progress.safe.jsonl",
        "qwen_axis": base / f"{prefix}_qwen_axis.safe.jsonl",
        "qwen_summary": base / f"{prefix}_qwen_summary.safe.json",
        "jailmeter_progress": base / f"{prefix}_jailmeter_progress.safe.jsonl",
        "jailmeter_axis": base / f"{prefix}_jailmeter_axis.safe.jsonl",
        "jailmeter_summary": base / f"{prefix}_jailmeter_summary.safe.json",
        "decisions": base / f"{prefix}_record_decisions.safe.jsonl",
        "result": base / f"{prefix}_result.safe.json",
    }


def preflight_path(root: Path, config: Mapping[str, Any]) -> Path:
    return output_directory(root, config) / "preflight.safe.json"


def final_result_path(root: Path, config: Mapping[str, Any]) -> Path:
    return output_directory(root, config) / "result.safe.json"


def verification_path(root: Path, config: Mapping[str, Any]) -> Path:
    return output_directory(root, config) / "independent_verification.safe.json"


def source_roots(root: Path, config: Mapping[str, Any]) -> dict[str, Path]:
    values = required_mapping(config["source_roots"], where="source_roots")
    return {
        str(name): rooted(root, path, where=f"source_roots.{name}")
        for name, path in values.items()
    }


def reconstruct_payloads(
    root: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
    parent: Mapping[str, Any],
) -> JsonRows:
    manifest = load_jsonl(verified["payload_manifest"])
    roots = source_roots(root, config)
    source = required_mapping(parent["payload_source"], where="parent payload_source")
    csv_path = roots["harmbench"] / str(source["path"])
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    p3 = repo_module(root, "scripts.run_local_signal_screen_p3")
    if p3.git_head(roots["harmbench"]) != source["revision"]:
        raise ValueError("2R HarmBench revision mismatch")
    p3.require_git_blob(csv_path, source["git_blob_sha"], label="2R HarmBench CSV")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    by_hash: dict[str, list[Mapping[str, str]]] = {}
    for row in source_rows:
        behavior = str(row.get("Behavior", ""))
        by_hash.setdefault(text_sha256(behavior), []).append(row)
    output: JsonRows = []
    for safe in manifest:
        matches = by_hash.get(str(safe["payload_sha256"]), [])
        if len(matches) != 1:
            raise ValueError("2R payload hash does not resolve to one HarmBench source row")
        source_row = matches[0]
        behavior = str(source_row["Behavior"])
        behavior_id = str(source_row["BehaviorID"])
        if (
            text_sha256(behavior_id) != safe["behavior_id_sha256"]
            or str(source_row["SemanticCategory"]) != safe["semantic_category"]
            or len(behavior.encode("utf-8")) != safe["payload_utf8_bytes"]
        ):
            raise ValueError("2R payload safe identity differs from source row")
        output.append({**safe, "_payload": behavior})
    return output


def rematerialize(
    root: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
) -> tuple[JsonRows, dict[tuple[int, str], JsonObject], Any, JsonObject]:
    parent = load_object(verified["p3_contract"])
    p3 = repo_module(root, "scripts.run_local_signal_screen_p3")
    roots = source_roots(root, config)
    payloads = reconstruct_payloads(root, config, verified, parent)
    _, h4_materialize, prompt_counter = p3.prepare_h4rm3l(
        root, roots["h4rm3l"], parent
    )
    _, deep_materialize = p3.prepare_deepinception(
        root, roots["deepinception"], parent
    )
    materials = p3.build_materializations(payloads, h4_materialize, deep_materialize)
    if prompt_counter["calls"] != 0:
        raise ValueError("2R h4rm3l adapter unexpectedly invoked a model")
    return payloads, materials, p3, parent


def token_census(values: Sequence[int]) -> JsonObject:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("token census requires at least one value")
    return {
        "minimum": ordered[0],
        "median": ordered[len(ordered) // 2],
        "p95_nearest_rank": ordered[min(len(ordered) - 1, (95 * len(ordered) - 1) // 100)],
        "maximum": ordered[-1],
    }


def materialization_metadata(
    payloads: Sequence[Mapping[str, Any]],
    materials: Mapping[tuple[int, str], Mapping[str, Any]],
    *,
    tokenizer: Path,
    model: Path,
    p3: Any,
    parent: Mapping[str, Any],
) -> JsonRows:
    generation = required_mapping(parent["generation"], where="parent generation")
    rows: JsonRows = []
    for payload in payloads:
        position = int(payload["position"])
        for condition in ("DIRECT", "ATTACKED_H4RM3L", "ATTACKED_DEEPINCEPTION"):
            material = materials[(position, condition)]
            count = p3.count_tokens(tokenizer, model, str(material["_text"]))
            if count > int(generation["maximum_input_tokens_before_chat_margin"]):
                raise ValueError("2R materialization exceeds the frozen target context budget")
            rows.append(
                {
                    "payload_position": position,
                    "payload_sha256": payload["payload_sha256"],
                    "semantic_category": payload["semantic_category"],
                    "condition": condition,
                    "raw_user_prompt_token_count": count,
                    **p3.safe_materialization(material),
                }
            )
    return rows


def material_map(
    rows: Sequence[Mapping[str, Any]],
    raw: Mapping[tuple[int, str], Mapping[str, Any]],
) -> dict[tuple[int, str], JsonObject]:
    values: dict[tuple[int, str], JsonObject] = {}
    for row in rows:
        key = (int(row["payload_position"]), str(row["condition"]))
        if raw[key]["prompt_sha256"] != row["prompt_sha256"]:
            raise ValueError("2R prompt materialization drifted after preflight")
        values[key] = {**raw[key], **row}
    return values


def panel_runtime(root: Path, config: Mapping[str, Any], verified: Mapping[str, Path]):
    e0g5 = repo_module(root, "scripts.run_heterogeneous_panel_heldout_e0g5")
    _path, panel_config, parent_runtime = e0g5.load_config(
        root, verified["e0g5_contract"]
    )
    if panel_config.get("fixed_panel_rule") != config.get("e0g5_source_rule"):
        raise ValueError("2R panel rule differs from E0G5")
    return e0g5, panel_config, parent_runtime


def validate_panel_assets(
    root: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
) -> JsonObject:
    e0g5, panel_config, parent_runtime = panel_runtime(root, config, verified)
    observed_gpu = e0g5.verify_gpu_identity(panel_config)
    axes = required_mapping(parent_runtime["qualified_axes"], where="qualified_axes")
    qwen = repo_module(root, "scripts.qualify_qwen3guard_runtime_e0g1a")
    qwen_axis = required_mapping(axes["qwen3guard"], where="qwen axis")
    _, qwen_config = qwen.resolve_config(root, root / str(qwen_axis["contract_path"]))
    qwen_files, qwen_bytes = qwen.verify_model_files(root, qwen_config)
    jailmeter = repo_module(root, "scripts.qualify_jailmeter_runtime_e0g1b")
    jailmeter_axis = required_mapping(axes["jailmeter"], where="jailmeter axis")
    _, jailmeter_config = jailmeter.resolve_config(
        root, root / str(jailmeter_axis["contract_path"])
    )
    source_files = jailmeter.verify_source(root, jailmeter_config)
    target_files = jailmeter.verify_target_model(root, jailmeter_config)
    runtime_identity = jailmeter.verify_runtime(root, jailmeter_config)
    conversion = jailmeter.convert(root, root / str(jailmeter_axis["contract_path"]))
    return {
        "gpu": observed_gpu,
        "qwen_model_file_count": len(qwen_files),
        "qwen_model_bytes": qwen_bytes,
        "jailmeter_source_files": len(source_files),
        "jailmeter_target_files": len(target_files),
        "jailmeter_runtime_identity": runtime_identity,
        "jailmeter_conversion_identity_sha256": conversion["conversion_identity_sha256"],
    }


def preflight(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path, config, verified = load_config(root, config_path)
    destination = preflight_path(root, config)
    if destination.exists():
        existing = load_object(destination)
        if (
            existing.get("status") != "FRESH_SCREEN_2R_PREFLIGHT_PASS"
            or existing.get("contract_sha256") != file_sha256(config_path)
        ):
            raise ValueError("existing 2R preflight belongs to another contract")
        return existing
    payloads, materials, p3, parent = rematerialize(root, config, verified)
    runtime = p3.validate_runtime(
        parent, rooted(root, config["target_runtime_root"], where="target runtime root")
    )
    metadata = materialization_metadata(
        payloads,
        materials,
        tokenizer=Path(runtime["_tokenizer"]),
        model=Path(runtime["_model"]),
        p3=p3,
        parent=parent,
    )
    mapped = material_map(metadata, materials)
    initial = active_pairs_for_seed(payloads, seed=SEEDS[0], previous_pairs=None)
    plans = plan_rows(
        contract_sha256=file_sha256(config_path),
        seed=SEEDS[0],
        payloads=payloads,
        active_pairs=initial,
        materializations=mapped,
        model_id=str(parent["target_model"]["model_id"]),
    )
    plan_path = phase_paths(root, config, SEEDS[0])["plan"]
    write_once_jsonl(plan_path, plans)
    smoke_parent = dict(parent)
    smoke_parent["privacy"] = config["privacy"]
    smoke = p3.run_harmless_smoke(
        root,
        file_sha256(config_path),
        file_sha256(Path(__file__).resolve()),
        smoke_parent,
        runtime,
    )
    panel_assets = validate_panel_assets(root, config, verified)
    free_disk = shutil.disk_usage(root).free
    runtime_limits = required_mapping(config["runtime"], where="runtime")
    passes = bool(
        smoke["operational_pass"]
        and len(plans) == 111
        and len(initial) == 74
        and all(row["payload_occurrence_count"] == 1 for row in metadata)
        and all(row["payload_byte_occurrence_count"] == 1 for row in metadata)
        and all(row["reserved_chat_marker_count"] == 0 for row in metadata)
        and free_disk >= int(runtime_limits["minimum_free_disk_bytes"])
    )
    if not passes:
        raise RuntimeError("2R operational preflight failed without scientific generation")
    result: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-preflight-v1",
        "status": "FRESH_SCREEN_2R_PREFLIGHT_PASS",
        "evidence_class": "PRE_SCIENTIFIC_OUTPUT_IDENTITY_AND_RUNTIME_VALIDATION",
        "contract_path": config_path.relative_to(root).as_posix(),
        "contract_sha256": file_sha256(config_path),
        "implementation_sha256": file_sha256(Path(__file__).resolve()),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "free_disk_bytes": free_disk,
        },
        "payload_count": len(payloads),
        "initial_pair_count": len(initial),
        "source_exhaustive_after_p3_exclusion": True,
        "materializations": metadata,
        "materialization_identity_sha256": canonical_sha256(metadata),
        "target_input_token_census": token_census(
            [int(row["raw_user_prompt_token_count"]) for row in metadata]
        ),
        "seed_11_plan_path": plan_path.relative_to(root).as_posix(),
        "seed_11_plan_sha256": file_sha256(plan_path),
        "seed_11_plan_identity_sha256": canonical_sha256(plans),
        "seed_11_planned_generations": len(plans),
        "harmless_runner_smoke": smoke,
        "panel_assets": panel_assets,
        "target_runtime": {
            key: value for key, value in runtime.items() if not key.startswith("_")
        },
        "d1_outcome_disclosed_before_2r": True,
        "scientific_target_generation_performed": False,
        "panel_output_observed": False,
        "stable_pair_outcome_observed": False,
        "raw_text_written": False,
        "next_operation": "GENERATE_SEED_11_TARGET_RESPONSES",
    }
    if find_prohibited_keys(result):
        raise AssertionError("2R preflight contains prohibited raw content")
    result["preflight_identity_sha256"] = canonical_sha256(result)
    safe_write(destination, result)
    return result


def previous_phase_result(
    root: Path, config: Mapping[str, Any], seed: int
) -> JsonObject | None:
    if seed == SEEDS[0]:
        return None
    previous_seed = SEEDS[SEEDS.index(seed) - 1]
    path = phase_paths(root, config, previous_seed)["result"]
    if not path.is_file():
        raise ValueError(f"seed {previous_seed} phase must be finalized first")
    result = load_object(path)
    if result.get("routing", {}).get("may_execute_next_seed") is not True:
        raise ValueError("frozen routing does not authorize another seed")
    return result


def ensure_phase_plan(
    root: Path,
    config_path: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
    seed: int,
) -> tuple[JsonRows, JsonRows, dict[tuple[int, str], JsonObject], Any, JsonObject]:
    preflight_result = preflight(root, config_path)
    payloads, raw_materials, p3, parent = rematerialize(root, config, verified)
    mapped = material_map(preflight_result["materializations"], raw_materials)
    previous = previous_phase_result(root, config, seed)
    previous_pairs = None if previous is None else previous["cumulative_pair_decisions"]
    active = active_pairs_for_seed(payloads, seed=seed, previous_pairs=previous_pairs)
    plans = plan_rows(
        contract_sha256=file_sha256(config_path),
        seed=seed,
        payloads=payloads,
        active_pairs=active,
        materializations=mapped,
        model_id=str(parent["target_model"]["model_id"]),
    )
    path = phase_paths(root, config, seed)["plan"]
    write_once_jsonl(path, plans)
    if seed == SEEDS[0] and (
        file_sha256(path) != preflight_result["seed_11_plan_sha256"]
        or canonical_sha256(plans) != preflight_result["seed_11_plan_identity_sha256"]
    ):
        raise ValueError("seed 11 plan differs from preflight")
    return plans, payloads, mapped, p3, parent


def validate_progress_rows(
    path: Path,
    plan: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    prompt_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> JsonRows:
    if not path.exists():
        return []
    rows = load_jsonl(path)
    plan_by_id = {str(row["record_id"]): row for row in plan}
    ids = [str(row.get("record_id")) for row in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(plan_by_id):
        raise ValueError(f"2R {kind} progress identities are invalid")
    for row in rows:
        record_id = str(row["record_id"])
        expected = plan_by_id[record_id]
        if row.get("execution_order") != expected["execution_order"]:
            raise ValueError(f"2R {kind} execution order drifted")
        if prompt_index is not None:
            prompt = prompt_index[record_id]
            if (
                row.get("input_sha256") != prompt["input_sha256"]
                or row.get("input_tokens") != prompt["input_tokens"]
            ):
                raise ValueError(f"2R {kind} evaluator prompt identity drifted")
        if find_prohibited_keys(row):
            raise ValueError(f"2R {kind} progress contains prohibited raw content")
    return sorted(rows, key=lambda row: int(row["execution_order"]))


def complete_artifact_pair(
    data_path: Path,
    summary_path: Path,
    *,
    expected: int,
    contract_sha: str,
) -> JsonObject | None:
    if not data_path.exists() and not summary_path.exists():
        return None
    if not data_path.exists() or not summary_path.exists():
        raise ValueError("partial finalized 2R artifact pair exists")
    summary = load_object(summary_path)
    if (
        summary.get("record_count") != expected
        or summary.get("contract_sha256") != contract_sha
        or summary.get("data_file_sha256") != file_sha256(data_path)
    ):
        raise ValueError("finalized 2R artifact identity mismatch")
    return summary


def finalize_rows(
    *,
    root: Path,
    progress_path: Path,
    data_path: Path,
    summary_path: Path,
    rows: Sequence[Mapping[str, Any]],
    summary: JsonObject,
) -> JsonObject:
    if find_prohibited_keys(list(rows)) or find_prohibited_keys(summary):
        raise AssertionError("2R safe artifact contains prohibited raw content")
    safe_write_jsonl(data_path, rows)
    summary["data_file"] = data_path.relative_to(root).as_posix()
    summary["data_file_bytes"] = data_path.stat().st_size
    summary["data_file_sha256"] = file_sha256(data_path)
    summary["summary_identity_sha256"] = canonical_sha256(summary)
    safe_write(summary_path, summary)
    progress_path.unlink(missing_ok=True)
    return summary


def generate(root: Path, config_path: Path, seed: int) -> JsonObject:
    root = root.resolve()
    config_path, config, verified = load_config(root, config_path)
    paths = phase_paths(root, config, seed)
    plans, payloads, materials, p3, parent = ensure_phase_plan(
        root, config_path, config, verified, seed
    )
    completed = complete_artifact_pair(
        paths["generation"],
        paths["generation_summary"],
        expected=len(plans),
        contract_sha=file_sha256(config_path),
    )
    if completed is not None:
        return completed
    rows = validate_progress_rows(paths["generation_progress"], plans, kind="generation")
    completed_ids = {str(row["record_id"]) for row in rows}
    payload_by_position = {int(row["position"]): row for row in payloads}
    runtime = p3.validate_runtime(
        parent, rooted(root, config["target_runtime_root"], where="target runtime root")
    )
    parameters = p3.generation_parameters(parent, smoke=False)
    privacy = required_mapping(config["privacy"], where="privacy")
    private_root = rooted(root, privacy["private_root"], where="private root")
    staging_root = rooted(
        root, privacy["private_prompt_staging_root"], where="private staging root"
    )
    p3.ensure_scoped_private_path(root, private_root)
    p3.ensure_scoped_private_path(root, staging_root)
    runtime_contract = required_mapping(parent["runtime"], where="parent runtime")
    target = required_mapping(parent["target_model"], where="parent target_model")
    cache_hits = 0
    started = time.perf_counter()
    for plan in plans:
        record_id = str(plan["record_id"])
        if record_id in completed_ids:
            continue
        position = int(plan["payload_position"])
        condition = str(plan["condition"])
        material = materials[(position, condition)]
        identity: JsonObject = {
            **plan,
            "runner_sha256": file_sha256(Path(__file__).resolve()),
            "generation_parameters": parameters,
            "model_runtime_revision": target["runtime_revision"],
            "model_file_sha256s": runtime["model_file_sha256s"],
            "llama_cpp_revision": runtime_contract["revision"],
        }
        execution_identity_sha = canonical_sha256(identity)
        private_path = (
            private_root / "scientific_generations" / f"{execution_identity_sha}.json"
        )
        private, cache_hit = p3.run_private_invocation(
            identity=identity,
            prompt=str(material["_text"]),
            payload=str(payload_by_position[position]["_payload"]),
            private_record_path=private_path,
            staging_root=staging_root,
            cli=Path(runtime["_cli"]),
            model=Path(runtime["_model"]),
            parameters=parameters,
            seed=seed,
            device=str(runtime_contract["selected_device"]),
            required_gpu_name=str(runtime_contract["selected_device_name"]),
        )
        cache_hits += int(cache_hit)
        safe = p3.safe_invocation(private, int(parameters["maximum_new_tokens"]))
        row = {
            "record_id": record_id,
            "execution_order": plan["execution_order"],
            **safe,
            "private_record_sha256": file_sha256(private_path),
            "eligible_for_panel": safe["eligible_for_screening"],
        }
        if find_prohibited_keys(row):
            raise AssertionError("2R generation safe row contains prohibited raw content")
        rows.append(row)
        rows.sort(key=lambda item: int(item["execution_order"]))
        safe_write_jsonl(paths["generation_progress"], rows)
    elapsed = time.perf_counter() - started
    if len(rows) != len(plans):
        raise RuntimeError("2R target generation phase is incomplete")
    operational = all(row["operational_pass"] is True for row in rows)
    summary: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-generation-summary-v1",
        "status": (
            "FRESH_SCREEN_2R_TARGET_GENERATION_COMPLETE"
            if operational
            else "FRESH_SCREEN_2R_TARGET_GENERATION_OPERATIONAL_FAIL"
        ),
        "contract_sha256": file_sha256(config_path),
        "phase_seed": seed,
        "plan_sha256": file_sha256(paths["plan"]),
        "record_count": len(rows),
        "operational_count": sum(row["operational_pass"] is True for row in rows),
        "eligible_for_panel_count": sum(row["eligible_for_panel"] is True for row in rows),
        "possible_max_token_truncation_count": sum(
            row["possible_max_token_truncation"] is True for row in rows
        ),
        "cache_hits_this_invocation": cache_hits,
        "total_seconds_this_invocation": elapsed,
        "raw_text_written": False,
        "private_records_retained": True,
    }
    result = finalize_rows(
        root=root,
        progress_path=paths["generation_progress"],
        data_path=paths["generation"],
        summary_path=paths["generation_summary"],
        rows=rows,
        summary=summary,
    )
    if not operational:
        raise RuntimeError("2R target generation contains an operational failure")
    return result


def load_evaluator_inputs(
    root: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
    seed: int,
) -> tuple[list[EvaluatorInput], JsonRows, JsonRows]:
    paths = phase_paths(root, config, seed)
    plans = load_jsonl(paths["plan"])
    generations = load_jsonl(paths["generation"])
    generation_by_id = {str(row["record_id"]): row for row in generations}
    if len(generation_by_id) != len(plans) or set(generation_by_id) != {
        str(row["record_id"]) for row in plans
    }:
        raise ValueError("2R evaluator generation denominator differs from plan")
    p3 = repo_module(root, "scripts.run_local_signal_screen_p3")
    private_root = rooted(
        root,
        required_mapping(config["privacy"], where="privacy")["private_root"],
        where="private root",
    )
    values: list[EvaluatorInput] = []
    inventory: JsonRows = []
    for plan in plans:
        record_id = str(plan["record_id"])
        safe = generation_by_id[record_id]
        execution_identity_sha = str(safe["execution_identity_sha256"])
        private_path = (
            private_root / "scientific_generations" / f"{execution_identity_sha}.json"
        )
        if file_sha256(private_path) != safe["private_record_sha256"]:
            raise ValueError("2R private generation file hash mismatch")
        private = p3.load_object(private_path)
        if private.get("execution_identity_sha256") != execution_identity_sha:
            raise ValueError("2R private execution identity mismatch")
        payload = str(private.get("payload", ""))
        raw_response = str(private.get("response", ""))
        response = p3.normalized_response(raw_response)
        if (
            text_sha256(payload) != plan["payload_sha256"]
            or text_sha256(response) != safe["response_sha256"]
            or text_sha256(str(private.get("prompt", ""))) != plan["prompt_sha256"]
        ):
            raise ValueError("2R private evaluator content hash mismatch")
        record = HeldoutInputRecord(
            record_id=record_id,
            source_id="FRESH_SCREEN_2R_PROSPECTIVE_DEVELOPMENT",
            source_locator_sha256=execution_identity_sha,
            behavior_group_sha256=str(plan["payload_sha256"]),
            response_sha256=str(safe["response_sha256"]),
            strata=(str(plan["condition"]), f"SEED_{seed}"),
            evaluation_role="FRESH_SCREEN_2R_CANDIDATE_DISCOVERY",
            goal_text=payload,
            response_text=response,
        )
        values.append(EvaluatorInput(record=record, metadata={**plan, **safe}))
        inventory.append(
            {
                "record_id": record_id,
                "execution_identity_sha256": execution_identity_sha,
                "private_record_sha256": safe["private_record_sha256"],
                "payload_sha256": plan["payload_sha256"],
                "response_sha256": safe["response_sha256"],
            }
        )
    return values, plans, inventory


def evaluator_prompts(
    root: Path,
    config: Mapping[str, Any],
    verified: Mapping[str, Path],
    seed: int,
    axis: str,
) -> tuple[list[EvaluatorInput], JsonRows, Any, Mapping[str, Any], Any]:
    e0g5, panel_config, parent_runtime = panel_runtime(root, config, verified)
    e0g5.verify_gpu_identity(panel_config)
    inputs, _plans, _inventory = load_evaluator_inputs(root, config, verified, seed)
    records = [item.record for item in inputs]
    from transformers import AutoTokenizer

    if axis == "qwen":
        runtime = required_mapping(parent_runtime["qwen3guard_runtime"], where="qwen runtime")
        tokenizer = AutoTokenizer.from_pretrained(
            root / str(runtime["model_local_path"]), local_files_only=True
        )
        prompts = [e0g5.qwen_prompt(tokenizer, record) for record in records]
        auxiliary: Any = tokenizer
    else:
        runtime = required_mapping(parent_runtime["jailmeter_runtime"], where="jailmeter runtime")
        tokenizer = AutoTokenizer.from_pretrained(
            root / str(runtime["base_metadata_local_path"]),
            local_files_only=True,
            trust_remote_code=True,
        )
        sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
        system_prompt = sentinel.extract_system_prompt(root / str(runtime["runner_path"]))
        prompts = [e0g5.jailmeter_prompt(tokenizer, system_prompt, record) for record in records]
        auxiliary = system_prompt
    return inputs, prompts, runtime, auxiliary, parent_runtime


def run_qwen(root: Path, config_path: Path, seed: int) -> JsonObject:
    root = root.resolve()
    config_path, config, verified = load_config(root, config_path)
    generate(root, config_path, seed)
    paths = phase_paths(root, config, seed)
    plans = load_jsonl(paths["plan"])
    completed = complete_artifact_pair(
        paths["qwen_axis"],
        paths["qwen_summary"],
        expected=len(plans),
        contract_sha=file_sha256(config_path),
    )
    if completed is not None:
        return completed
    import torch
    from transformers import AutoModelForCausalLM

    if not torch.cuda.is_available():
        raise RuntimeError("2R Qwen3Guard requires the qualified CUDA device")
    inputs, prompts, runtime, tokenizer, _parent_runtime = evaluator_prompts(
        root, config, verified, seed, "qwen"
    )
    prompt_index = {str(row["record_id"]): row for row in prompts}
    rows = validate_progress_rows(
        paths["qwen_progress"], plans, kind="qwen", prompt_index=prompt_index
    )
    completed_ids = {str(row["record_id"]) for row in rows}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch.cuda.init()
    torch.cuda.set_device(0)
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    limits = required_mapping(config["runtime"], where="runtime")
    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(limits["maximum_prelaunch_gpu_mib"]):
        raise RuntimeError(f"2R Qwen GPU baseline is uncontrolled: {baseline_gpu} MiB")
    if bool(runtime["do_sample"]):
        raise ValueError("2R Qwen evaluator must remain deterministic")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    started = time.perf_counter()
    load_started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        root / str(runtime["model_local_path"]),
        dtype=torch.float16,
        local_files_only=True,
        low_cpu_mem_usage=True,
    ).to(torch.device("cuda:0"))
    model.eval()
    model_load_seconds = time.perf_counter() - load_started
    for item in inputs:
        record_id = item.record.record_id
        if record_id in completed_ids:
            continue
        prompt = prompt_index[record_id]
        encoded = tokenizer([prompt["prompt"]], return_tensors="pt").to(
            torch.device("cuda:0")
        )
        if int(encoded.input_ids.shape[1]) != int(prompt["input_tokens"]):
            raise ValueError("2R Qwen runtime token count differs from prompt construction")
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
                "record_id": record_id,
                "execution_order": item.metadata["execution_order"],
                "cache_origin": "FRESH_SCREEN_2R_NEW_PANEL_INFERENCE",
                "input_sha256": prompt["input_sha256"],
                "input_tokens": int(encoded.input_ids.shape[1]),
                "output_sha256": text_sha256(content),
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
        safe_write_jsonl(paths["qwen_progress"], rows)
        if time.perf_counter() - started > float(limits["qwen_maximum_seconds_per_phase"]):
            raise TimeoutError("2R Qwen phase exceeded its frozen time budget")
    elapsed = time.perf_counter() - started
    if len(rows) != len(plans):
        raise RuntimeError("2R Qwen phase denominator is incomplete")
    peak_cuda = int(torch.cuda.max_memory_allocated(0))
    if peak_cuda > int(limits["maximum_peak_cuda_allocated_bytes"]):
        raise RuntimeError("2R Qwen exceeded its frozen CUDA allocation budget")
    summary: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-qwen-axis-v1",
        "status": "FRESH_SCREEN_2R_QWEN_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "phase_seed": seed,
        "record_count": len(rows),
        "parse_count": sum(
            row["safety"] is not None and row["refusal"] is not None for row in rows
        ),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
        "model_load_seconds_this_invocation": model_load_seconds,
        "total_seconds_this_invocation": elapsed,
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_cuda_allocated_bytes_this_invocation": peak_cuda,
        "raw_text_written": False,
        "panel_label_opened": False,
    }
    del model
    torch.cuda.empty_cache()
    return finalize_rows(
        root=root,
        progress_path=paths["qwen_progress"],
        data_path=paths["qwen_axis"],
        summary_path=paths["qwen_summary"],
        rows=rows,
        summary=summary,
    )


def run_jailmeter(root: Path, config_path: Path, seed: int) -> JsonObject:
    root = root.resolve()
    config_path, config, verified = load_config(root, config_path)
    generate(root, config_path, seed)
    paths = phase_paths(root, config, seed)
    plans = load_jsonl(paths["plan"])
    completed = complete_artifact_pair(
        paths["jailmeter_axis"],
        paths["jailmeter_summary"],
        expected=len(plans),
        contract_sha=file_sha256(config_path),
    )
    if completed is not None:
        return completed
    inputs, prompts, runtime, system_prompt, _parent_runtime = evaluator_prompts(
        root, config, verified, seed, "jailmeter"
    )
    prompt_index = {str(row["record_id"]): row for row in prompts}
    rows = validate_progress_rows(
        paths["jailmeter_progress"],
        plans,
        kind="jailmeter",
        prompt_index=prompt_index,
    )
    completed_ids = {str(row["record_id"]) for row in rows}
    sentinel = repo_module(root, "scripts.run_heterogeneous_panel_sentinel_e0g2")
    limits = required_mapping(config["runtime"], where="runtime")
    if float(runtime["temperature"]) != 0.0:
        raise ValueError("2R JailMeter evaluator must remain deterministic")
    context_required = max(int(row["input_tokens"]) for row in prompts) + int(
        runtime["max_new_tokens"]
    )
    if context_required > int(limits["jailmeter_context_tokens"]):
        raise ValueError("2R JailMeter prompt exceeds the frozen context budget")
    baseline_gpu = sentinel.query_gpu_memory_mib()
    if baseline_gpu is None or baseline_gpu > float(limits["maximum_prelaunch_gpu_mib"]):
        raise RuntimeError(f"2R JailMeter GPU baseline is uncontrolled: {baseline_gpu} MiB")
    host = str(runtime["host"])
    port = int(runtime["port"])
    if not sentinel.port_is_free(host, port):
        raise ValueError(f"2R JailMeter port is occupied: {host}:{port}")
    runtime_directory = root / str(runtime["runtime_directory"])
    command = [
        str(runtime_directory / str(runtime["server_relative_path"])),
        "-m",
        str(root / str(runtime["target_model_path"])),
        "--lora",
        str(root / str(runtime["lora_path"])),
        "--host",
        host,
        "--port",
        str(port),
        "-c",
        str(limits["jailmeter_context_tokens"]),
        "-t",
        str(runtime["threads"]),
        "-ngl",
        str(runtime["gpu_layers"]),
        "--offline",
        "--no-webui",
    ]
    log_handle = tempfile.NamedTemporaryFile(
        prefix=f"2r-{seed}-jailmeter-", suffix=".log", delete=False
    )
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
                raise RuntimeError(
                    f"2R JailMeter server exited during startup: {process.returncode}"
                )
            if sentinel.server_ready(health_url):
                ready_seconds = time.perf_counter() - started
                break
            time.sleep(0.25)
        if ready_seconds is None:
            raise TimeoutError("2R JailMeter server health timeout")
        for item in inputs:
            record_id = item.record.record_id
            if record_id in completed_ids:
                continue
            prompt = prompt_index[record_id]
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
                raise ValueError("2R JailMeter endpoint returned no text")
            parsed = sentinel.parse_jailmeter_label(content, runtime)
            predicted_raw = response.get("tokens_predicted")
            predicted = (
                predicted_raw
                if isinstance(predicted_raw, int) and not isinstance(predicted_raw, bool)
                else None
            )
            raw_limit = bool(response.get("stopped_limit", False))
            boundary_limit = predicted is not None and predicted >= int(runtime["max_new_tokens"])
            rows.append(
                {
                    "record_id": record_id,
                    "execution_order": item.metadata["execution_order"],
                    "cache_origin": "FRESH_SCREEN_2R_NEW_PANEL_INFERENCE",
                    "input_sha256": prompt["input_sha256"],
                    "input_tokens": prompt["input_tokens"],
                    "output_sha256": text_sha256(content),
                    "output_characters": len(content),
                    "output_tokens": predicted,
                    "output_limit_stop": raw_limit or boundary_limit,
                    "output_limit_derived_from_token_boundary": boundary_limit and not raw_limit,
                    "label": parsed["label"],
                    "label_match_count": parsed["match_count"],
                    "inference_seconds": time.perf_counter() - call_started,
                }
            )
            rows.sort(key=lambda row: int(row["execution_order"]))
            safe_write_jsonl(paths["jailmeter_progress"], rows)
            if time.perf_counter() - started > float(
                limits["jailmeter_maximum_seconds_per_phase"]
            ):
                raise TimeoutError("2R JailMeter phase exceeded its frozen time budget")
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
    elapsed = time.perf_counter() - started
    log_content = log_path.read_bytes()
    log_path.unlink(missing_ok=True)
    if failure is not None:
        raise failure
    if len(rows) != len(plans):
        raise RuntimeError("2R JailMeter phase denominator is incomplete")
    peak_gpu = max(gpu_samples) if gpu_samples else None
    if peak_gpu is None or peak_gpu > float(limits["maximum_peak_gpu_mib"]):
        raise RuntimeError(f"2R JailMeter peak GPU budget failed: {peak_gpu} MiB")
    summary: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-jailmeter-axis-v1",
        "status": "FRESH_SCREEN_2R_JAILMETER_AXIS_COMPLETE",
        "contract_sha256": file_sha256(config_path),
        "phase_seed": seed,
        "record_count": len(rows),
        "parse_count": sum(row["label"] is not None for row in rows),
        "output_limit_stops": sum(bool(row["output_limit_stop"]) for row in rows),
        "server_ready_seconds_this_invocation": ready_seconds,
        "total_seconds_this_invocation": elapsed,
        "baseline_gpu_memory_mib": baseline_gpu,
        "peak_gpu_memory_mib": peak_gpu,
        "system_prompt_sha256": text_sha256(str(system_prompt)),
        "server_log_bytes": len(log_content),
        "server_log_sha256": hashlib.sha256(log_content).hexdigest(),
        "server_log_retained": False,
        "raw_text_written": False,
        "panel_label_opened": False,
    }
    return finalize_rows(
        root=root,
        progress_path=paths["jailmeter_progress"],
        data_path=paths["jailmeter_axis"],
        summary_path=paths["jailmeter_summary"],
        rows=rows,
        summary=summary,
    )


def indexed(rows: Sequence[Mapping[str, Any]], expected: set[str], *, kind: str):
    value = {str(row["record_id"]): row for row in rows}
    if len(value) != len(rows) or set(value) != expected:
        raise ValueError(f"2R {kind} identities differ from the phase plan")
    return value


def finalize_phase(root: Path, config_path: Path, seed: int) -> JsonObject:
    root = root.resolve()
    config_path, config, _verified = load_config(root, config_path)
    paths = phase_paths(root, config, seed)
    if paths["result"].exists():
        existing = load_object(paths["result"])
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing 2R phase result belongs to another contract")
        return existing
    plans = load_jsonl(paths["plan"])
    expected = {str(row["record_id"]) for row in plans}
    generations = indexed(load_jsonl(paths["generation"]), expected, kind="generation")
    qwen = indexed(load_jsonl(paths["qwen_axis"]), expected, kind="qwen")
    jailmeter = indexed(load_jsonl(paths["jailmeter_axis"]), expected, kind="jailmeter")
    decisions = record_decisions(plans, generations, qwen, jailmeter)
    if find_prohibited_keys(decisions):
        raise AssertionError("2R record decisions contain prohibited raw content")
    previous = previous_phase_result(root, config, seed)
    previous_pairs = None if previous is None else previous["cumulative_pair_decisions"]
    manifest = load_jsonl(
        rooted(
            root,
            required_mapping(config["dependencies"], where="dependencies")[
                "payload_manifest"
            ]["path"],
            where="payload manifest",
        )
    )
    active = active_pairs_for_seed(manifest, seed=seed, previous_pairs=previous_pairs)
    current_pairs = decide_active_pairs(seed=seed, active_pairs=active, decisions=decisions)
    cumulative = merge_pair_decisions(previous_pairs, current_pairs)
    route = routing(cumulative, completed_seed=seed)
    safe_write_jsonl(paths["decisions"], decisions)
    panel_counts = Counter(str(row["panel_label"]) for row in decisions)
    result: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-phase-result-v1",
        "status": "FRESH_SCREEN_2R_PHASE_COMPLETE",
        "evidence_class": "PROSPECTIVE_DEVELOPMENT_CANDIDATE_SCREEN_NOT_TOPOLOGY_EVIDENCE",
        "contract_sha256": file_sha256(config_path),
        "phase_seed": seed,
        "plan_sha256": file_sha256(paths["plan"]),
        "generation_sha256": file_sha256(paths["generation"]),
        "qwen_axis_sha256": file_sha256(paths["qwen_axis"]),
        "jailmeter_axis_sha256": file_sha256(paths["jailmeter_axis"]),
        "record_decisions_path": paths["decisions"].relative_to(root).as_posix(),
        "record_decisions_sha256": file_sha256(paths["decisions"]),
        "record_count": len(decisions),
        "active_pair_count": len(active),
        "panel_counts": {
            name: panel_counts[name] for name in ("HARMFUL", "SAFE", "ABSTAIN")
        },
        "measurement": {
            "eligible": sum(bool(row["measurement_eligible"]) for row in decisions),
            "ineligible": sum(not bool(row["measurement_eligible"]) for row in decisions),
            "axis_agreement": sum(bool(row["axis_agreement"]) for row in decisions),
            "axis_disagreement_or_abstain": sum(
                not bool(row["axis_agreement"]) for row in decisions
            ),
        },
        "phase_pair_decisions": current_pairs,
        "cumulative_pair_decisions": cumulative,
        "routing": route,
        "early_rejection_exact_for_three_seed_predicate": True,
        "threshold_or_panel_tuning_after_output": False,
        "new_human_annotation": False,
        "topology_outcomes_opened": False,
        "paper_valid_topology_result": False,
        "raw_text_written": False,
        "next_operation": route["route"],
    }
    if find_prohibited_keys(result):
        raise AssertionError("2R phase result contains prohibited raw content")
    result["result_identity_sha256"] = canonical_sha256(result)
    safe_write(paths["result"], result)
    return result


def finalize(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path, config, _verified = load_config(root, config_path)
    destination = final_result_path(root, config)
    if destination.exists():
        existing = load_object(destination)
        if existing.get("contract_sha256") != file_sha256(config_path):
            raise ValueError("existing 2R final result belongs to another contract")
        return existing
    latest: JsonObject | None = None
    for seed in SEEDS:
        path = phase_paths(root, config, seed)["result"]
        if not path.exists():
            break
        latest = load_object(path)
    if latest is None:
        raise ValueError("no 2R phase has been finalized")
    route = required_mapping(latest["routing"], where="latest routing")
    if route["may_execute_next_seed"] is True:
        raise ValueError("2R cannot finalize while another seed is authorized")
    pairs = latest["cumulative_pair_decisions"]
    selected = selected_h4rm3l_pairs(pairs, limit=3)
    result: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-result-v1",
        "status": "FRESH_SCREEN_2R_COMPLETE",
        "evidence_class": "PROSPECTIVE_DEVELOPMENT_CANDIDATE_SCREEN_NOT_TOPOLOGY_EVIDENCE",
        "contract_sha256": file_sha256(config_path),
        "last_completed_seed": latest["phase_seed"],
        "last_phase_result_sha256": file_sha256(
            phase_paths(root, config, int(latest["phase_seed"]))["result"]
        ),
        "initial_payloads": 37,
        "initial_pairs": 74,
        "cumulative_pair_decisions": pairs,
        "routing": route,
        "selected_h4rm3l_pairs_for_d2": selected,
        "d2_selection_rule": "LEXICOGRAPHIC_MIN_PAIR_ID_UP_TO_THREE",
        "d2_selection_count": len(selected),
        "exact_three_seed_success_rule_unchanged": True,
        "source_exhaustive_after_p3_exclusion": True,
        "target_responses_fresh": True,
        "qualified_panel_reused_without_tuning": True,
        "new_human_annotation": False,
        "paper_valid_topology_result": False,
        "raw_text_written": False,
        "interpretation": (
            "This prospective screen can authorize exact topology work on independently "
            "screened candidates; it is not itself evidence about minimal recovery sets."
        ),
        "next_operation": route["route"],
    }
    if find_prohibited_keys(result):
        raise AssertionError("2R final result contains prohibited raw content")
    result["result_identity_sha256"] = canonical_sha256(result)
    safe_write(destination, result)
    return result


def status(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path, config, _verified = load_config(root, config_path)
    phases: JsonObject = {}
    for seed in SEEDS:
        paths = phase_paths(root, config, seed)
        plan_count = len(load_jsonl(paths["plan"])) if paths["plan"].exists() else 0
        phases[str(seed)] = {
            "plan_records": plan_count,
            "generation_records": (
                len(load_jsonl(paths["generation"]))
                if paths["generation"].exists()
                else len(load_jsonl(paths["generation_progress"]))
                if paths["generation_progress"].exists()
                else 0
            ),
            "qwen_records": (
                len(load_jsonl(paths["qwen_axis"]))
                if paths["qwen_axis"].exists()
                else len(load_jsonl(paths["qwen_progress"]))
                if paths["qwen_progress"].exists()
                else 0
            ),
            "jailmeter_records": (
                len(load_jsonl(paths["jailmeter_axis"]))
                if paths["jailmeter_axis"].exists()
                else len(load_jsonl(paths["jailmeter_progress"]))
                if paths["jailmeter_progress"].exists()
                else 0
            ),
            "phase_finalized": paths["result"].exists(),
        }
    return {
        "status": "FRESH_SCREEN_2R_PROGRESS_STATUS",
        "contract_sha256": file_sha256(config_path),
        "preflight": preflight_path(root, config).exists(),
        "phases": phases,
        "final_result": final_result_path(root, config).exists(),
        "independent_verification": verification_path(root, config).exists(),
        "model_invoked_by_status": False,
    }


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    if args.command in {"generate", "qwen", "jailmeter", "finalize-phase"} and args.seed is None:
        raise SystemExit("--seed is required for this command")
    if args.command == "preflight":
        result = preflight(root, config)
    elif args.command == "generate":
        result = generate(root, config, int(args.seed))
    elif args.command == "qwen":
        result = run_qwen(root, config, int(args.seed))
    elif args.command == "jailmeter":
        result = run_jailmeter(root, config, int(args.seed))
    elif args.command == "finalize-phase":
        result = finalize_phase(root, config, int(args.seed))
    elif args.command == "finalize":
        result = finalize(root, config)
    else:
        result = status(root, config)
    visible = {
        key: result[key]
        for key in (
            "status",
            "phase_seed",
            "record_count",
            "seed_11_planned_generations",
            "routing",
            "next_operation",
            "preflight",
            "phases",
            "final_result",
            "independent_verification",
        )
        if key in result
    }
    print(json.dumps(visible, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
