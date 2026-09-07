"""Freeze a content-free 60/60 split of the unused GuidedBench core frame.

The audit reconstructs the original outcome-blind D3/C1 split, isolates only
within-topic ordinals four and above, and proves that their payload hashes do
not occur in any completed scientific target-output root.  It writes no raw
question, target, guideline, prompt, or response text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import freeze_d3_guidedbench_split as original_split

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
PAYLOAD_FIELD_PATTERN = re.compile(rb'"payload_sha256"\s*:\s*"([0-9a-f]{64})"')
PROHIBITED_SAFE_KEYS = {
    "question",
    "target",
    "guidelines",
    "description",
    "examples",
    "payload",
    "prompt",
    "response",
    "response_text",
    "content",
    "raw_output",
    "stdout",
    "stderr",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "guidedbench_rescue_frame_r0_v1.json"
        ),
    )
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return rows


def resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def verify_dependencies(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, dependency in config["dependencies"].items():
        path = resolve(root, str(dependency["path"]))
        digest = file_sha256(path)
        if digest != dependency["sha256"]:
            raise ValueError(f"dependency hash mismatch: {name}")
        observed[str(name)] = digest
    return observed


def verify_receipts(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, receipt in config["required_verification_receipts"].items():
        value = load_object(resolve(root, str(receipt["path"])))
        expected_status = str(receipt["status"])
        if value.get("status") != expected_status:
            raise ValueError(f"verification receipt status mismatch: {name}")
        observed[str(name)] = expected_status
    return observed


def required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"GuidedBench row has invalid {key}")
    return value


def ordered_core_groups(rows: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("subset") != "core" or row.get("benchmark_version") != "1.0":
            raise ValueError("GuidedBench row differs from admitted core version")
        groups[required_string(row, "topic")].append(row)
    topics = sorted(
        groups,
        key=lambda topic: (original_split.sha256_text(topic), topic),
    )
    return [
        sorted(
            groups[topic],
            key=lambda row: (
                original_split.sha256_text(required_string(row, "id")),
                required_string(row, "id"),
            ),
        )
        for topic in topics
    ]


def reconstruct_remaining(rows: Sequence[Mapping[str, Any]]) -> JsonRows:
    output: JsonRows = []
    for topic_position, ordered in enumerate(ordered_core_groups(rows)):
        for ordinal, row in enumerate(ordered[4:], start=4):
            output.append(
                original_split.safe_identity(
                    row,
                    topic_position=topic_position,
                    within_topic_ordinal=ordinal,
                    position=len(output),
                )
            )
    return output


def split_balanced_alternating(remaining: Sequence[Mapping[str, Any]]) -> tuple[JsonRows, JsonRows]:
    by_topic: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in remaining:
        by_topic[int(row["topic_position"])].append(row)
    odd_topics = sorted(
        (
            rows[0]["topic_sha256"],
            topic_position,
        )
        for topic_position, rows in by_topic.items()
        if len(rows) % 2
    )
    primary_extra_count = len(odd_topics) // 2
    primary_first_topics = {
        int(topic_position)
        for _, topic_position in odd_topics[:primary_extra_count]
    }
    primary: JsonRows = []
    replication: JsonRows = []
    for topic_position in sorted(by_topic):
        topic_rows = sorted(
            by_topic[topic_position], key=lambda row: int(row["within_topic_ordinal"])
        )
        primary_first = len(topic_rows) % 2 == 0 or topic_position in primary_first_topics
        for local_position, row in enumerate(topic_rows):
            goes_primary = local_position % 2 == (0 if primary_first else 1)
            selected = primary if goes_primary else replication
            safe = dict(row)
            safe["remaining_frame_position"] = int(row["position"])
            safe["cohort"] = "PRIMARY_A" if goes_primary else "REPLICATION_RESERVE_B"
            safe["cohort_position"] = len(selected)
            safe["position"] = len(selected)
            selected.append(safe)
    return primary, replication


def _payload_hashes_in_paths(paths: Iterable[Path]) -> tuple[set[str], int, int, int]:
    hashes: set[str] = set()
    file_count = 0
    field_file_count = 0
    byte_count = 0
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        file_count += 1
        payload = path.read_bytes()
        byte_count += len(payload)
        matches = PAYLOAD_FIELD_PATTERN.findall(payload)
        if matches:
            field_file_count += 1
            hashes.update(match.decode("ascii") for match in matches)
    return hashes, file_count, field_file_count, byte_count


def scan_completed_outputs(
    root: Path, config: Mapping[str, Any]
) -> tuple[set[str], JsonObject]:
    paths: list[Path] = []
    for raw_root in config["completed_scientific_output_roots"]:
        scan_root = resolve(root, str(raw_root))
        if not scan_root.is_dir():
            raise FileNotFoundError(scan_root)
        paths.extend(scan_root.rglob("*"))
    hashes, files, field_files, bytes_scanned = _payload_hashes_in_paths(paths)
    return hashes, {
        "root_count": len(config["completed_scientific_output_roots"]),
        "json_or_jsonl_file_count": files,
        "files_with_payload_sha256": field_files,
        "bytes_scanned": bytes_scanned,
        "unique_payload_sha256_count": len(hashes),
    }


def scan_private_hash_fields(
    root: Path, config: Mapping[str, Any]
) -> tuple[set[str], JsonObject]:
    paths: list[Path] = []
    for raw_root in config["completed_private_record_roots"]:
        scan_root = resolve(root, str(raw_root))
        if not scan_root.is_dir():
            raise FileNotFoundError(scan_root)
        paths.extend(scan_root.rglob("*"))
    hashes, files, field_files, bytes_scanned = _payload_hashes_in_paths(paths)
    return hashes, {
        "root_count": len(config["completed_private_record_roots"]),
        "json_or_jsonl_file_count": files,
        "files_with_payload_sha256": field_files,
        "bytes_scanned": bytes_scanned,
        "unique_payload_sha256_count": len(hashes),
        "raw_text_interpreted_or_recorded": False,
        "scan_method": "BYTE_REGEX_EXTRACTION_OF_PAYLOAD_SHA256_FIELD_ONLY",
    }


def find_prohibited_keys(value: object, location: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if str(key).lower() in PROHIBITED_SAFE_KEYS:
                found.append(child_location)
            found.extend(find_prohibited_keys(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_prohibited_keys(child, f"{location}[{index}]"))
    return tuple(found)


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows)


def write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite nonidentical artifact: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _topic_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(row["topic_id"]) for row in rows).items())
    )


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_file = resolve(root, config_path)
    config = load_object(config_file)
    if config.get("status") != "FROZEN_BEFORE_UNUSED_FRAME_RECONSTRUCTION":
        raise ValueError("GuidedBench rescue-frame contract is not frozen")
    if config.get("target_or_evaluator_inference_authorized") is not False:
        raise ValueError("rescue-frame audit cannot authorize inference")
    observed_dependencies = verify_dependencies(root, config)
    observed_receipts = verify_receipts(root, config)

    source = config["source"]
    core_path = resolve(root, str(source["core_path"]))
    if file_sha256(core_path) != source["core_sha256"]:
        raise ValueError("GuidedBench core hash mismatch")
    core_rows = load_jsonl(core_path)
    if len(core_rows) != int(config["denominator"]["core_rows"]):
        raise ValueError("GuidedBench core denominator changed")

    development, confirmation, prior_metadata = original_split.select_split(
        core_rows,
        required_rows=int(config["denominator"]["core_rows"]),
        required_topic_count=int(config["denominator"]["topics"]),
    )
    stored_development = load_jsonl(resolve(root, config["prior_split"]["development_manifest"]))
    stored_confirmation = load_jsonl(
        resolve(root, config["prior_split"]["confirmation_manifest"])
    )
    if development != stored_development or confirmation != stored_confirmation:
        raise ValueError("prior D3/C1 split does not reconstruct exactly")

    remaining = reconstruct_remaining(core_rows)
    if len(remaining) != int(config["denominator"]["unused_rows"]):
        raise ValueError("unexpected unused-row denominator")
    used_hashes = {
        str(row["payload_sha256"]) for row in (*development, *confirmation)
    }
    remaining_hashes = {str(row["payload_sha256"]) for row in remaining}
    if len(remaining_hashes) != len(remaining) or used_hashes & remaining_hashes:
        raise ValueError("remaining frame overlaps or duplicates the prior split")

    safe_hashes, safe_scan = scan_completed_outputs(root, config)
    private_hashes, private_scan = scan_private_hash_fields(root, config)
    safe_collisions = sorted(remaining_hashes & safe_hashes)
    private_collisions = sorted(remaining_hashes & private_hashes)
    if safe_collisions or private_collisions:
        raise RuntimeError("unused GuidedBench frame has prior target-output hash collisions")

    primary, replication = split_balanced_alternating(remaining)
    expected_cohort = int(config["denominator"]["cohort_rows"])
    if len(primary) != expected_cohort or len(replication) != expected_cohort:
        raise ValueError("balanced rescue cohorts do not match the frozen denominator")
    primary_hashes = {str(row["payload_sha256"]) for row in primary}
    replication_hashes = {str(row["payload_sha256"]) for row in replication}
    overlap = primary_hashes & replication_hashes
    union = primary_hashes | replication_hashes
    if overlap or union != remaining_hashes:
        raise ValueError("rescue cohorts do not form an exact partition")
    if find_prohibited_keys(primary) or find_prohibited_keys(replication):
        raise ValueError("rescue cohort manifest contains prohibited raw content")

    recording = config["recording"]
    primary_path = resolve(root, recording["primary_manifest"])
    replication_path = resolve(root, recording["replication_manifest"])
    audit_path = resolve(root, recording["audit"])
    write_once(primary_path, encode_jsonl(primary))
    write_once(replication_path, encode_jsonl(replication))

    result: JsonObject = {
        "schema_version": "jbspan-guidedbench-rescue-frame-r0-result-v1",
        "status": "GUIDEDBENCH_UNUSED_FRAME_60_60_FREEZE_PASS",
        "evidence_class": "PRE_RESCUE_TARGET_SOURCE_IDENTITY_AND_SAMPLING_FREEZE",
        "contract_sha256": file_sha256(config_file),
        "verified_dependency_sha256": observed_dependencies,
        "verified_receipt_status": observed_receipts,
        "source_core_sha256": file_sha256(core_path),
        "prior_split_reconstructed_exactly": True,
        "prior_split": {
            "development_rows": len(development),
            "confirmation_rows": len(confirmation),
            "used_unique_payloads": len(used_hashes),
            "reported_remaining_rows": prior_metadata["remaining_rows"],
        },
        "unused_frame": {
            "rows": len(remaining),
            "unique_payloads": len(remaining_hashes),
            "topics": len({str(row["topic_sha256"]) for row in remaining}),
            "topic_counts": _topic_counts(remaining),
            "prior_safe_output_collision_count": len(safe_collisions),
            "prior_private_record_collision_count": len(private_collisions),
        },
        "prior_output_hash_scan": {
            "safe_outputs": safe_scan,
            "private_records": private_scan,
        },
        "cohorts": {
            "primary_a": {
                "rows": len(primary),
                "unique_payloads": len(primary_hashes),
                "topics": len({str(row["topic_sha256"]) for row in primary}),
                "topic_counts": _topic_counts(primary),
                "manifest_sha256": file_sha256(primary_path),
                "manifest_identity_sha256": canonical_sha256(primary),
            },
            "replication_reserve_b": {
                "rows": len(replication),
                "unique_payloads": len(replication_hashes),
                "topics": len({str(row["topic_sha256"]) for row in replication}),
                "topic_counts": _topic_counts(replication),
                "manifest_sha256": file_sha256(replication_path),
                "manifest_identity_sha256": canonical_sha256(replication),
            },
            "overlap_count": len(primary_hashes & replication_hashes),
            "union_equals_unused_frame": primary_hashes | replication_hashes == remaining_hashes,
        },
        "selection_rule": (
            "WITHIN_EACH_TOPIC_USE_PRIOR_HASH_ORDER; ALTERNATE ORDINALS FROM FOUR; "
            "ASSIGN HALF_OF_ODD_REMAINDER_TOPICS TO EACH STARTING COHORT BY TOPIC_HASH_ORDER"
        ),
        "scope": {
            "target_model_called": False,
            "evaluator_called": False,
            "private_response_text_interpreted": False,
            "raw_content_written_to_repository": False,
            "primary_a_target_output_authorized": False,
            "replication_reserve_b_target_output_authorized": False,
            "official_d3_or_c1n_reclassified": False,
        },
        "next_operation": "FREEZE_RESCUE_CLAIM_MEASUREMENT_AND_KILL_GATES_BEFORE_PRIMARY_A_ACCESS",
    }
    if find_prohibited_keys(result):
        raise ValueError("rescue-frame result contains prohibited raw content")
    result["result_identity_sha256"] = canonical_sha256(result)
    write_once(
        audit_path,
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n",
    )
    return result


def main() -> None:
    arguments = parser().parse_args()
    result = run(arguments.root, arguments.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "unused_rows": result["unused_frame"]["rows"],
                "primary_rows": result["cohorts"]["primary_a"]["rows"],
                "replication_rows": result["cohorts"]["replication_reserve_b"]["rows"],
                "prior_safe_collisions": result["unused_frame"][
                    "prior_safe_output_collision_count"
                ],
                "prior_private_collisions": result["unused_frame"][
                    "prior_private_record_collision_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
