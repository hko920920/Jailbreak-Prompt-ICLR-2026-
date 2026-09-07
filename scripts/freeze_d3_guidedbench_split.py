from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
PROHIBITED_SAFE_KEYS = {
    "question",
    "target",
    "guidelines",
    "description",
    "examples",
    "payload",
    "prompt",
    "response",
    "content",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Freeze the outcome-blind GuidedBench D3/C1 split"
    )
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/d3_guidedbench_split_v1.json"
        ),
    )
    value.add_argument("--root", type=Path, default=Path("."))
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


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
            raise ValueError(f"expected object at {path}:{line_number}")
        rows.append(value)
    return rows


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite nonidentical split artifact: {path}")
        return
    atomic_write(path, payload)


def find_prohibited_keys(value: object, location: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if str(key) in PROHIBITED_SAFE_KEYS:
                found.append(child_location)
            found.extend(find_prohibited_keys(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_prohibited_keys(child, f"{location}[{index}]"))
    return tuple(found)


def required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"GuidedBench row has invalid {key}")
    return value


def safe_identity(
    row: Mapping[str, Any],
    *,
    topic_position: int,
    within_topic_ordinal: int,
    position: int,
) -> JsonObject:
    source_id = required_string(row, "id")
    topic = required_string(row, "topic")
    question = required_string(row, "question")
    target = required_string(row, "target")
    guidelines = row.get("guidelines")
    if not isinstance(guidelines, list) or not guidelines:
        raise ValueError("GuidedBench row has invalid guidelines")
    guideline_types = Counter(
        str(item.get("type")) for item in guidelines if isinstance(item, Mapping)
    )
    if sum(guideline_types.values()) != len(guidelines):
        raise ValueError("GuidedBench guideline is not an object")
    return {
        "position": position,
        "topic_position": topic_position,
        "topic_id": f"GUIDEDBENCH_CORE_TOPIC_{topic_position:02d}",
        "semantic_category": f"GUIDEDBENCH_CORE_TOPIC_{topic_position:02d}",
        "topic_sha256": sha256_text(topic),
        "within_topic_ordinal": within_topic_ordinal,
        "source_id": source_id,
        "source_id_sha256": sha256_text(source_id),
        "behavior_id_sha256": sha256_text(source_id),
        "payload_sha256": sha256_text(question),
        "payload_utf8_bytes": len(question.encode("utf-8")),
        "target_prefix_sha256": sha256_text(target),
        "target_prefix_utf8_bytes": len(target.encode("utf-8")),
        "guideline_count": len(guidelines),
        "guideline_type_counts": {
            "action": guideline_types["action"],
            "entity": guideline_types["entity"],
        },
        "guideline_manifest_sha256": canonical_sha256(guidelines),
        "source_row_sha256": canonical_sha256(row),
        "raw_content_recorded": False,
    }


def select_split(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_rows: int,
    required_topic_count: int,
) -> tuple[JsonRows, JsonRows, JsonObject]:
    if len(rows) != required_rows:
        raise ValueError("GuidedBench core row denominator differs")
    source_ids = [required_string(row, "id") for row in rows]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("GuidedBench source ids are not unique")
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("subset") != "core" or row.get("benchmark_version") != "1.0":
            raise ValueError("GuidedBench row differs from admitted core version")
        groups[required_string(row, "topic")].append(row)
    if len(groups) != required_topic_count:
        raise ValueError("GuidedBench core topic denominator differs")
    topics = sorted(groups, key=lambda topic: (sha256_text(topic), topic))
    topic_hashes = [sha256_text(topic) for topic in topics]
    if len(set(topic_hashes)) != len(topic_hashes):
        raise ValueError("GuidedBench topic hash collision")

    development: JsonRows = []
    confirmation: JsonRows = []
    remaining = 0
    within_topic_sizes: list[int] = []
    for topic_position, topic in enumerate(topics):
        ordered = sorted(
            groups[topic],
            key=lambda row: (
                sha256_text(required_string(row, "id")),
                required_string(row, "id"),
            ),
        )
        if len(ordered) < 4:
            raise ValueError(
                "GuidedBench topic cannot supply one development and three confirmation rows"
            )
        within_topic_sizes.append(len(ordered))
        development.append(
            safe_identity(
                ordered[0],
                topic_position=topic_position,
                within_topic_ordinal=0,
                position=len(development),
            )
        )
        for ordinal in (1, 2, 3):
            confirmation.append(
                safe_identity(
                    ordered[ordinal],
                    topic_position=topic_position,
                    within_topic_ordinal=ordinal,
                    position=len(confirmation),
                )
            )
        remaining += len(ordered) - 4

    if find_prohibited_keys(development) or find_prohibited_keys(confirmation):
        raise AssertionError("D3/C1 split manifest contains raw content")
    metadata: JsonObject = {
        "source_rows": len(rows),
        "topic_count": len(groups),
        "within_topic_sizes_sorted": sorted(within_topic_sizes),
        "development_rows": len(development),
        "confirmation_rows": len(confirmation),
        "remaining_rows": remaining,
        "development_confirmation_overlap": bool(
            {row["source_id"] for row in development}
            & {row["source_id"] for row in confirmation}
        ),
        "development_topics": len({row["topic_sha256"] for row in development}),
        "confirmation_topics": len({row["topic_sha256"] for row in confirmation}),
    }
    return development, confirmation, metadata


def resolve_core_path(config: Mapping[str, Any]) -> Path:
    source = config["source"]
    if not isinstance(source, Mapping):
        raise ValueError("source must be an object")
    cache_root = Path(str(source["cache_root"])).resolve()
    snapshot = cache_root / "snapshots" / str(source["revision"]) / "core.jsonl"
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    if file_sha256(snapshot) != source["core_sha256"]:
        raise ValueError("GuidedBench core cache hash mismatch")
    return snapshot


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_object(config_path)
    if (
        config.get("schema_version") != "jbspan-d3-guidedbench-split-contract-v1"
        or config.get("status") != "FROZEN_BEFORE_ANY_D3_OR_C1_TARGET_OUTPUT"
        or config.get("frozen") is not True
    ):
        raise ValueError("D3/C1 split contract is not frozen")
    for name, spec_value in config["dependencies"].items():
        if not isinstance(spec_value, Mapping):
            raise ValueError(f"invalid dependency: {name}")
        path = root / str(spec_value["path"])
        if file_sha256(path) != spec_value["sha256"]:
            raise ValueError(f"D3/C1 split dependency mismatch: {name}")
    dependencies = config["dependencies"]
    d2_result = load_object(root / str(dependencies["d2_result"]["path"]))
    if (
        d2_result.get("status") != "D2_EXACT_TOPOLOGY_MICRO_PILOT_COMPLETE"
        or d2_result.get("d2_gate_pass") is not True
        or d2_result.get("route")
        != "AUTHORIZE_D3_FRESH_DEVELOPMENT_TOPOLOGY_SCREEN"
    ):
        raise ValueError("D2 result does not authorize D3")
    d2_verification = load_object(
        root / str(dependencies["d2_verification"]["path"])
    )
    if (
        d2_verification.get("status") != "D2_INDEPENDENT_RECONSTRUCTION_PASS"
        or d2_verification.get("result_identity_sha256")
        != d2_result.get("result_identity_sha256")
    ):
        raise ValueError("D2 independent verification does not authorize D3")
    source_freeze = load_object(
        root / str(dependencies["guidedbench_source_freeze"]["path"])
    )
    source = config["source"]
    if not isinstance(source, Mapping):
        raise ValueError("source must be an object")
    if (
        source_freeze.get("status") != "pass"
        or source_freeze.get("dataset", {}).get("revision") != source["revision"]
        or source_freeze.get("admitted_files", {}).get("core.jsonl", {}).get("sha256")
        != source["core_sha256"]
    ):
        raise ValueError("GuidedBench source freeze differs from D3 split source")
    core_path = resolve_core_path(config)
    rows = load_jsonl(core_path)
    denominator = config["denominator"]
    if not isinstance(denominator, Mapping):
        raise ValueError("denominator must be an object")
    development, confirmation, metadata = select_split(
        rows,
        required_rows=int(denominator["core_rows"]),
        required_topic_count=int(denominator["topics"]),
    )
    recording = config["recording"]
    if not isinstance(recording, Mapping):
        raise ValueError("recording must be an object")
    development_path = root / str(recording["development_manifest"])
    confirmation_path = root / str(recording["confirmation_reservation_manifest"])
    audit_path = root / str(recording["audit"])
    write_once(development_path, encode_jsonl(development))
    write_once(confirmation_path, encode_jsonl(confirmation))
    result: JsonObject = {
        "schema_version": "jbspan-d3-guidedbench-split-result-v1",
        "status": "D3_GUIDEDBENCH_SPLIT_FREEZE_PASS",
        "contract_sha256": file_sha256(config_path),
        "source_core_sha256": file_sha256(core_path),
        **metadata,
        "selection_rule": (
            "WITHIN_EACH_EXACT_TOPIC_ASCENDING_SHA256_OF_EXACT_UTF8_SOURCE_ID_"
            "THEN_SOURCE_ID"
        ),
        "development_ordinal": 0,
        "confirmation_ordinals": [1, 2, 3],
        "development_manifest_sha256": file_sha256(development_path),
        "development_manifest_identity_sha256": canonical_sha256(development),
        "confirmation_reservation_manifest_sha256": file_sha256(confirmation_path),
        "confirmation_reservation_identity_sha256": canonical_sha256(confirmation),
        "target_model_called": False,
        "evaluator_called": False,
        "raw_content_written_to_repository": False,
        "next_operation": "FREEZE_AND_PREFLIGHT_D3_FRESH_DEVELOPMENT_SCREEN",
    }
    if metadata["development_confirmation_overlap"] is not False:
        raise AssertionError("D3 development and C1 confirmation overlap")
    result["result_identity_sha256"] = canonical_sha256(result)
    if find_prohibited_keys(result):
        raise AssertionError("D3/C1 split audit contains raw content")
    write_once(
        audit_path,
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    result = run(args.root, args.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "development_rows": result["development_rows"],
                "confirmation_rows": result["confirmation_rows"],
                "remaining_rows": result["remaining_rows"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
