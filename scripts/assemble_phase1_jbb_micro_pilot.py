from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SELECTED_INDICES = (0, 1, 2, 3, 5, 7, 8, 10, 11, 12)


@dataclass(frozen=True)
class ArtifactSource:
    family: str
    source_model: str
    attack_type: str
    artifact_path: str
    raw_url: str
    blob_sha: str
    license: str = "MIT"


_SOURCES = (
    ArtifactSource(
        family="PAIR",
        source_model="gpt-3.5-turbo-1106",
        attack_type="black_box",
        artifact_path="attack-artifacts/PAIR/black_box/gpt-3.5-turbo-1106.json",
        raw_url=(
            "https://raw.githubusercontent.com/JailbreakBench/artifacts/main/"
            "attack-artifacts/PAIR/black_box/gpt-3.5-turbo-1106.json"
        ),
        blob_sha="9612434c11c29492ae83fe160d466285b32114a8",
    ),
    ArtifactSource(
        family="GCG",
        source_model="vicuna-13b-v1.5",
        attack_type="white_box",
        artifact_path="attack-artifacts/GCG/white_box/vicuna-13b-v1.5.json",
        raw_url=(
            "https://raw.githubusercontent.com/JailbreakBench/artifacts/main/"
            "attack-artifacts/GCG/white_box/vicuna-13b-v1.5.json"
        ),
        blob_sha="1430aafc1795106ac89555b8ede5eee925d90e00",
    ),
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(payload: str) -> str:
    return _sha256_bytes(payload.encode("utf-8"))


def _read_json(source: ArtifactSource, local_path: Path | None) -> dict[str, Any]:
    if local_path is None:
        with urllib.request.urlopen(source.raw_url, timeout=60) as response:  # noqa: S310
            raw = response.read()
    else:
        raw = local_path.read_bytes()

    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("jailbreaks"), list):
        raise ValueError(f"invalid artifact schema for {source.family}")
    return payload


def _index_entries(payload: dict[str, Any], source: ArtifactSource) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for raw_entry in payload["jailbreaks"]:
        if not isinstance(raw_entry, dict) or not isinstance(raw_entry.get("index"), int):
            raise ValueError(f"invalid jailbreak entry in {source.family}")
        index = int(raw_entry["index"])
        if index in indexed:
            raise ValueError(f"duplicate source index {index} in {source.family}")
        indexed[index] = raw_entry
    return indexed


def _build_record(source: ArtifactSource, entry: dict[str, Any]) -> dict[str, Any]:
    index = int(entry["index"])
    required = ("goal", "behavior", "category", "prompt")
    for field_name in required:
        if not isinstance(entry.get(field_name), str) or not str(entry[field_name]).strip():
            raise ValueError(f"missing {field_name} for {source.family} index {index}")
    if entry.get("jailbroken") is not True:
        raise ValueError(f"source entry is not marked jailbroken: {source.family} index {index}")

    family_slug = source.family.lower()
    model_slug = source.source_model.replace("/", "-")
    return {
        "id": f"jbb-{family_slug}-{model_slug}-{index:03d}",
        "behavior": str(entry["behavior"]),
        "original_prompt": str(entry["goal"]),
        "jailbreak_prompt": str(entry["prompt"]),
        "attack_family": source.family,
        "metadata": {
            "category": str(entry["category"]),
            "source_repository": "JailbreakBench/artifacts",
            "source_artifact": source.artifact_path,
            "source_blob_sha": source.blob_sha,
            "source_index": index,
            "source_model": source.source_model,
            "source_attack_type": source.attack_type,
            "source_jailbroken": True,
            "source_jailbroken_llama_guard1": bool(
                entry.get("jailbroken_llama_guard1", False)
            ),
            "source_queries_to_jailbreak": entry.get("queries_to_jailbreak"),
            "license": source.license,
            "split": "development",
            "pairing_key": f"JBB-{index:03d}",
        },
    }


def _validate_records(records: list[dict[str, Any]]) -> None:
    expected_count = len(_SOURCES) * len(_SELECTED_INDICES)
    if len(records) != expected_count:
        raise ValueError(f"expected {expected_count} records, found {len(records)}")

    ids = [str(record["id"]) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate stable IDs")

    prompt_hashes = [_sha256_text(str(record["jailbreak_prompt"])) for record in records]
    if len(prompt_hashes) != len(set(prompt_hashes)):
        raise ValueError("duplicate jailbreak prompts")

    pairing: dict[str, set[str]] = {}
    goals: dict[str, set[str]] = {}
    for record in records:
        metadata = record["metadata"]
        key = str(metadata["pairing_key"])
        pairing.setdefault(key, set()).add(str(record["attack_family"]))
        goals.setdefault(key, set()).add(str(record["original_prompt"]))

    expected_families = {source.family for source in _SOURCES}
    incomplete = sorted(key for key, families in pairing.items() if families != expected_families)
    inconsistent_goals = sorted(key for key, values in goals.items() if len(values) != 1)
    if incomplete:
        raise ValueError(f"incomplete cross-family pairs: {incomplete}")
    if inconsistent_goals:
        raise ValueError(f"inconsistent paired goals: {inconsistent_goals}")


def _write_outputs(
    output_path: Path,
    manifest_path: Path,
    records: list[dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records
    ) + "\n"
    output_path.write_text(serialized, encoding="utf-8")

    selection_rows = []
    for record in records:
        metadata = record["metadata"]
        selection_rows.append(
            {
                "id": record["id"],
                "pairing_key": metadata["pairing_key"],
                "behavior": record["behavior"],
                "category": metadata["category"],
                "attack_family": record["attack_family"],
                "source_artifact": metadata["source_artifact"],
                "source_blob_sha": metadata["source_blob_sha"],
                "source_index": metadata["source_index"],
                "source_model": metadata["source_model"],
                "license": metadata["license"],
                "original_sha256": _sha256_text(str(record["original_prompt"])),
                "jailbreak_sha256": _sha256_text(str(record["jailbreak_prompt"])),
                "original_chars": len(str(record["original_prompt"])),
                "jailbreak_chars": len(str(record["jailbreak_prompt"])),
            }
        )

    family_counts = dict(sorted(Counter(str(r["attack_family"]) for r in records).items()))
    manifest = {
        "schema_version": "phase1-micro-pilot-selection-v1",
        "raw_prompts_committed": False,
        "output_sha256": _sha256_text(serialized),
        "example_count": len(records),
        "unique_behavior_count": len({str(r["behavior"]) for r in records}),
        "ids_sha256": _sha256_text("\n".join(sorted(str(r["id"]) for r in records))),
        "attack_family_counts": family_counts,
        "selected_source_indices": list(_SELECTED_INDICES),
        "sources": [
            {
                "family": source.family,
                "source_model": source.source_model,
                "attack_type": source.attack_type,
                "artifact_path": source.artifact_path,
                "blob_sha": source.blob_sha,
                "license": source.license,
            }
            for source in _SOURCES
        ],
        "selection": selection_rows,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair-artifact",
        type=Path,
        help="optional local copy of the PAIR artifact; otherwise download the pinned raw file",
    )
    parser.add_argument(
        "--gcg-artifact",
        type=Path,
        help="optional local copy of the GCG artifact; otherwise download the pinned raw file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/phase1_micro_pilot_20.local.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/phase1_micro_pilot_20.selection.json"),
    )
    args = parser.parse_args()

    local_paths = {
        "PAIR": args.pair_artifact,
        "GCG": args.gcg_artifact,
    }
    records: list[dict[str, Any]] = []
    for source in _SOURCES:
        payload = _read_json(source, local_paths[source.family])
        indexed = _index_entries(payload, source)
        for index in _SELECTED_INDICES:
            if index not in indexed:
                raise ValueError(f"missing source index {index} in {source.family}")
            records.append(_build_record(source, indexed[index]))

    records.sort(key=lambda row: str(row["id"]))
    _validate_records(records)
    _write_outputs(args.output, args.manifest, records)
    print(
        json.dumps(
            {
                "status": "ASSEMBLED",
                "examples": len(records),
                "families": dict(
                    sorted(Counter(str(r["attack_family"]) for r in records).items())
                ),
                "output": str(args.output),
                "manifest": str(args.manifest),
                "raw_prompts_committed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
