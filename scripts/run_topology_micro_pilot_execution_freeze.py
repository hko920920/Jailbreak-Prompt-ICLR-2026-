from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git identity.


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def require_blob(root: Path, path: str, expected: str) -> None:
    observed = git_blob_sha(root / path)
    if observed != expected:
        raise ValueError(f"Git blob mismatch for {path}: {observed}")


def validate_predecessors(root: Path, contract: JsonObject) -> JsonObject:
    parent = cast(JsonObject, contract["parent_micro_pilot"])
    require_blob(root, str(parent["path"]), str(parent["required_git_blob_sha"]))
    parent_value = load_object(root / str(parent["path"]))
    if parent_value.get("status") != parent["required_status"]:
        raise ValueError("parent micro-pilot status mismatch")
    if parent_value.get("next_authorized_operation") != parent["required_next_operation"]:
        raise ValueError("parent authorization mismatch")

    target = cast(JsonObject, contract["target_model"])
    identity = cast(JsonObject, target["identity_predecessor"])
    require_blob(root, str(identity["path"]), str(identity["required_git_blob_sha"]))
    identity_value = load_object(root / str(identity["path"]))
    tokenizer = cast(JsonObject, identity_value["target_tokenizer"])
    if tokenizer.get("repository") != identity["required_repository"]:
        raise ValueError("target repository identity mismatch")
    if tokenizer.get("revision") != identity["required_revision"]:
        raise ValueError("target revision identity mismatch")

    family_checks: list[JsonObject] = []
    for raw in cast(list[JsonObject], contract["attack_families"]):
        require_blob(root, str(raw["predecessor_path"]), str(raw["predecessor_git_blob_sha"]))
        value = load_object(root / str(raw["predecessor_path"]))
        if value.get("status") != raw["required_status"]:
            raise ValueError(f"family predecessor mismatch: {raw['family']}")
        if value.get("target_model_called") is not False:
            raise ValueError("pre-outcome family audit unexpectedly called a target")
        family_checks.append({
            "family": raw["family"],
            "status": value["status"],
            "predecessor_sha256": sha256_file(root / str(raw["predecessor_path"])),
        })
    return {"parent": parent_value["status"], "families": family_checks}


def select_payloads(csv_path: Path, contract: JsonObject) -> list[JsonObject]:
    source = cast(JsonObject, contract["development_payload_source"])
    categories = cast(list[str], source["semantic_categories"])
    excluded = {str(value).casefold() for value in cast(list[str], source["excluded_tags"])}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected: list[JsonObject] = []
    for position, category in enumerate(categories):
        candidates: list[dict[str, str]] = []
        for row in rows:
            tags = {part.strip().casefold() for part in row.get("Tags", "").split(",") if part.strip()}
            if row.get("FunctionalCategory") != source["functional_category_required"]:
                continue
            if row.get("SemanticCategory") != category:
                continue
            if str(row.get("ContextString", "")).strip():
                continue
            if tags & excluded:
                continue
            if not row.get("Behavior") or not row.get("BehaviorID"):
                continue
            candidates.append(row)
        if not candidates:
            raise ValueError(f"no eligible payload for category {category}")
        candidates.sort(
            key=lambda row: sha256_bytes(f"{category}:{row['BehaviorID']}".encode("utf-8"))
        )
        row = candidates[0]
        payload = row["Behavior"]
        behavior_id = row["BehaviorID"]
        source_identity = {
            "Behavior": payload,
            "BehaviorID": behavior_id,
            "FunctionalCategory": row.get("FunctionalCategory", ""),
            "SemanticCategory": row.get("SemanticCategory", ""),
            "Tags": row.get("Tags", ""),
            "ContextString": row.get("ContextString", ""),
        }
        selected.append({
            "position": position,
            "semantic_category": category,
            "behavior_id_sha256": sha256_bytes(behavior_id.encode("utf-8")),
            "payload_sha256": sha256_bytes(payload.encode("utf-8")),
            "payload_utf8_bytes": len(payload.encode("utf-8")),
            "source_row_sha256": canonical_sha256(source_identity),
        })
    return selected


def resolve_hf_metadata(contract: JsonObject) -> JsonObject:
    from huggingface_hub import HfApi

    target = cast(JsonObject, contract["target_model"])
    api = HfApi()
    canonical = api.model_info(
        str(target["canonical_repository"]),
        revision=str(target["canonical_revision"]),
        files_metadata=True,
    )
    canonical_sha = str(canonical.sha)
    if canonical_sha != target["canonical_revision"]:
        raise ValueError("canonical model revision did not resolve exactly")
    runtime = cast(JsonObject, target["development_runtime"])
    runtime_info = api.model_info(str(runtime["repository"]), files_metadata=True)
    runtime_sha = str(runtime_info.sha)
    required = [str(value).casefold() for value in cast(list[str], runtime["file_name_casefold_contains"])]
    files: list[JsonObject] = []
    for sibling in runtime_info.siblings or ():
        name = str(sibling.rfilename)
        folded = name.casefold()
        if not all(token in folded for token in required):
            continue
        size = getattr(sibling, "size", None)
        lfs = getattr(sibling, "lfs", None)
        digest = None
        if isinstance(lfs, dict):
            digest = lfs.get("sha256")
            size = lfs.get("size", size)
        elif lfs is not None:
            digest = getattr(lfs, "sha256", None)
            size = getattr(lfs, "size", size)
        if not isinstance(digest, str) or not isinstance(size, int):
            raise ValueError(f"runtime LFS metadata missing for {name}")
        files.append({"filename": name, "sha256": digest, "size_bytes": size})
    if not files:
        raise ValueError("no Q4_K_M GGUF runtime artifact resolved")
    return {
        "canonical_repository": target["canonical_repository"],
        "canonical_revision": canonical_sha,
        "tokenizer_revision": target["tokenizer_revision"],
        "development_runtime_repository": runtime["repository"],
        "development_runtime_revision": runtime_sha,
        "development_runtime_files": sorted(files, key=lambda row: str(row["filename"])),
        "llama_cpp_repository": runtime["llama_cpp_repository"],
        "llama_cpp_release_tag": runtime["llama_cpp_release_tag"],
        "llama_cpp_revision": runtime["llama_cpp_revision"],
        "model_weights_downloaded": False,
    }


def run(
    root: Path,
    source_root: Path,
    config_path: Path,
    safe_output: Path,
    payload_manifest_output: Path,
    model_metadata_path: Path | None,
) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_SIGNAL_SCREEN_INPUTS_OR_TARGET_OUTCOMES":
        raise ValueError("unexpected execution-freeze status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("execution-freeze boundary invalid")
    sealed = cast(JsonObject, contract["sealed_boundaries"])
    if any(value is not False for value in sealed.values()):
        raise ValueError("a sealed boundary was opened before the freeze")
    predecessor = validate_predecessors(root, contract)
    source = cast(JsonObject, contract["development_payload_source"])
    csv_path = source_root / str(source["path"])
    if git_blob_sha(csv_path) != source["git_blob_sha"]:
        raise ValueError("payload source blob mismatch")
    payloads = select_payloads(csv_path, contract)
    if len(payloads) != int(source["selected_payload_count"]):
        raise ValueError("payload count mismatch")
    metadata = load_object(model_metadata_path) if model_metadata_path else resolve_hf_metadata(contract)
    if metadata.get("canonical_revision") != cast(JsonObject, contract["target_model"])["canonical_revision"]:
        raise ValueError("resolved canonical revision mismatch")
    generation = cast(JsonObject, contract["generation"])
    budget = cast(JsonObject, contract["causal_budget"])
    if len(cast(list[int], generation["seeds"])) != int(budget["seed_count"]):
        raise ValueError("seed count mismatch")
    if (2 ** int(budget["maximum_coarse_units_per_instance"])) != int(budget["maximum_subsets_per_instance"]):
        raise ValueError("subset budget mismatch")
    expected = (
        int(budget["maximum_subsets_per_instance"])
        * len(cast(list[str], budget["neutralizers"]))
        * int(budget["seed_count"])
    )
    if expected != int(budget["maximum_intervened_generations_per_stable_pair"]):
        raise ValueError("intervention request budget mismatch")
    checks = {
        "predecessors_match": True,
        "payload_source_matches": True,
        "payload_count_matches": True,
        "payloads_are_hash_only": all(
            not any(key in row for key in ("payload", "payload_text", "raw_payload"))
            for row in payloads
        ),
        "canonical_model_revision_resolved": True,
        "development_runtime_metadata_resolved": bool(metadata.get("development_runtime_files")),
        "decoding_is_frozen": True,
        "audit_packet_is_frozen": True,
        "intervention_budget_matches": True,
        "no_model_weight_download": metadata.get("model_weights_downloaded") is False,
        "no_model_inference": True,
        "no_attack_success_observed": True,
        "sealed_boundaries_preserved": True,
    }
    passed = all(checks.values())
    result: JsonObject = {
        "schema_version":"topology-micro-pilot-execution-freeze-result-v1",
        "status":"TOPOLOGY_MICRO_PILOT_EXECUTION_FREEZE_PASS" if passed else "TOPOLOGY_MICRO_PILOT_EXECUTION_FREEZE_FAIL",
        "operational_pass":passed,
        "scientific_pass":False,
        "paper_validity":False,
        "evidence_class":"PROTOCOL",
        "contract_sha256":sha256_file(config_path),
        "contract_git_blob_sha":git_blob_sha(config_path),
        "predecessor":predecessor,
        "payload_source":{
            "repository":source["repository"],
            "revision":source["revision"],
            "path":source["path"],
            "git_blob_sha":source["git_blob_sha"],
            "selection_rule":source["selection_rule"],
            "raw_payload_recorded":False,
        },
        "payload_manifest":payloads,
        "payload_manifest_sha256":canonical_sha256(payloads),
        "target_model":metadata,
        "generation":generation,
        "causal_budget":budget,
        "screening_and_audit":contract["screening_and_audit"],
        "checks":checks,
        "next_authorized_operation":cast(JsonObject, contract["decision_gate"])["on_freeze_pass"] if passed else cast(JsonObject, contract["decision_gate"])["on_operational_fail"],
        "model_weight_downloaded":False,
        "model_inference_performed":False,
        "attack_success_observed":False,
        "new_harmful_attack_outputs_generated":False,
        "stage_a_opened":False,
        "heldout_opened":False,
        "causal_oracle_opened":False,
        "keep_only_oracle_opened":False,
        "wavelet_used":False,
        "raw_payload_or_response_recorded":False,
    }
    write_json(safe_output, result)
    write_jsonl(payload_manifest_output, payloads)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Freeze topology micro-pilot execution identities")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--payload-manifest-output", type=Path, required=True)
    value.add_argument("--model-metadata", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    result = run(
        args.root.resolve(),
        args.source_root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
        args.payload_manifest_output.resolve(),
        args.model_metadata.resolve() if args.model_metadata else None,
    )
    print(result["status"])
    return 0 if result["operational_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
