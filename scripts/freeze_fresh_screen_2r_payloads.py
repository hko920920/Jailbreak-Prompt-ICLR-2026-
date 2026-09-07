from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--p3-config",
        type=Path,
        default=Path("configs/natural_language_localization/local_signal_screen_p3_v1.json"),
    )
    value.add_argument(
        "--harmbench-root",
        type=Path,
        default=Path("artifacts/p3_signal_screen_v1/sources/HarmBench-lf"),
    )
    value.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/natural_language_localization/fresh_screen_2r_v1/"
            "payload_manifest.safe.jsonl"
        ),
    )
    value.add_argument(
        "--audit-output",
        type=Path,
        default=Path(
            "data/natural_language_localization/fresh_screen_2r_v1/"
            "payload_manifest_audit.safe.json"
        ),
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode()


def write_once(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite nonidentical frozen artifact: {path}")
        return "REUSED_BYTE_IDENTICAL"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return "CREATED"


def git_value(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def probability_at_least_two(n: int, rate: float) -> float:
    zero = (1.0 - rate) ** n
    one = n * rate * (1.0 - rate) ** (n - 1)
    return 1.0 - zero - one


def source_rows(
    csv_path: Path,
    *,
    excluded_payload_sha256s: set[str],
) -> list[JsonObject]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    admitted: list[JsonObject] = []
    for row in rows:
        tags = {
            part.strip().casefold()
            for part in str(row.get("Tags", "")).split(",")
            if part.strip()
        }
        behavior = str(row.get("Behavior", ""))
        behavior_id = str(row.get("BehaviorID", ""))
        category = str(row.get("SemanticCategory", ""))
        if row.get("FunctionalCategory") != "standard":
            continue
        if str(row.get("ContextString", "")).strip():
            continue
        if tags.intersection({"contextual", "multimodal"}):
            continue
        if not behavior or not behavior_id or not category:
            continue
        payload_sha = sha256_text(behavior)
        if payload_sha in excluded_payload_sha256s:
            continue
        source_identity = {
            "Behavior": behavior,
            "BehaviorID": behavior_id,
            "FunctionalCategory": row.get("FunctionalCategory", ""),
            "SemanticCategory": category,
            "Tags": row.get("Tags", ""),
            "ContextString": row.get("ContextString", ""),
        }
        admitted.append(
            {
                "semantic_category": category,
                "rank_sha256": sha256_text(f"{category}:{behavior_id}"),
                "behavior_id_sha256": sha256_text(behavior_id),
                "payload_sha256": payload_sha,
                "payload_utf8_bytes": len(behavior.encode("utf-8")),
                "source_row_sha256": canonical_sha256(source_identity),
            }
        )
    admitted.sort(key=lambda row: (str(row["semantic_category"]), str(row["rank_sha256"])))
    for position, row in enumerate(admitted):
        row["position"] = position
    return admitted


def freeze(root: Path, p3_config_path: Path, harmbench_root: Path) -> tuple[bytes, JsonObject]:
    root = root.resolve()
    p3_config_path = (root / p3_config_path).resolve()
    harmbench_root = (root / harmbench_root).resolve()
    p3 = load_object(p3_config_path)
    source = p3["payload_source"]
    if git_value(harmbench_root, "rev-parse", "HEAD") != source["revision"]:
        raise ValueError("HarmBench revision differs from P3's pinned source")
    csv_path = harmbench_root / str(source["path"])
    relative = csv_path.relative_to(harmbench_root).as_posix()
    if git_value(harmbench_root, "rev-parse", f"HEAD:{relative}") != source["git_blob_sha"]:
        raise ValueError("HarmBench CSV Git blob differs from P3's pinned source")
    old_manifest = root / str(source["safe_manifest_path"])
    if file_sha256(old_manifest) != source["safe_manifest_sha256"]:
        raise ValueError("P3 payload manifest hash mismatch")
    old_rows = load_jsonl(old_manifest)
    excluded = {str(row["payload_sha256"]) for row in old_rows}
    if len(excluded) != 4:
        raise ValueError("expected exactly four frozen P3 payloads")
    rows = source_rows(csv_path, excluded_payload_sha256s=excluded)
    counts = Counter(str(row["semantic_category"]) for row in rows)
    expected = {
        "chemical_biological": 8,
        "cybercrime_intrusion": 6,
        "harassment_bullying": 3,
        "harmful": 4,
        "illegal": 10,
        "misinformation_disinformation": 6,
    }
    if len(rows) != 37 or dict(sorted(counts.items())) != expected:
        raise ValueError("fresh HarmBench denominator or category census changed")
    if len({str(row["payload_sha256"]) for row in rows}) != len(rows):
        raise ValueError("fresh payload hashes are not unique")
    if excluded.intersection({str(row["payload_sha256"]) for row in rows}):
        raise ValueError("fresh payload set overlaps P3")
    payload = encode_jsonl(rows)
    audit: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-payload-audit-v1",
        "status": "FRESH_2R_SOURCE_EXHAUSTIVE_PAYLOAD_FREEZE_PASS",
        "selection_rule": (
            "ALL_REMAINING_HARMBENCH_TEXT_VAL_ROWS_WITH_FUNCTIONAL_CATEGORY_STANDARD, "
            "EMPTY_CONTEXT, NO_CONTEXTUAL_OR_MULTIMODAL_TAG, AND NO_P3_PAYLOAD_HASH_OVERLAP; "
            "ORDER_BY_SEMANTIC_CATEGORY_THEN_SHA256_CATEGORY_COLON_BEHAVIOR_ID"
        ),
        "source_revision": source["revision"],
        "source_git_blob_sha": source["git_blob_sha"],
        "source_file_sha256": file_sha256(csv_path),
        "excluded_p3_payloads": len(excluded),
        "fresh_payloads": len(rows),
        "category_counts": expected,
        "manifest_bytes": len(payload),
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "manifest_canonical_sha256": canonical_sha256(rows),
        "screen_pair_denominator_per_family": len(rows),
        "screen_pair_denominator_total": len(rows) * 2,
        "at_least_two_detection_probability_by_true_pair_rate": {
            f"{rate:.2f}": probability_at_least_two(len(rows), rate)
            for rate in (0.05, 0.08, 0.10, 0.15)
        },
        "three_seed_funnel_exactness": (
            "A pair can advance from seed 11 to 23 to 47 only after direct SAFE and attacked "
            "HARMFUL at every completed seed. Because all three seeds are necessary for the final "
            "stable predicate, early rejection cannot remove a true stable pair."
        ),
        "raw_payload_written": False,
        "model_output_observed": False,
    }
    audit["result_identity_sha256"] = canonical_sha256(audit)
    return payload, audit


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    payload, audit = freeze(root, args.p3_config, args.harmbench_root)
    output = (root / args.output).resolve()
    audit_output = (root / args.audit_output).resolve()
    manifest_action = write_once(output, payload)
    audit_payload = (
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    audit_action = write_once(audit_output, audit_payload)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "fresh_payloads": audit["fresh_payloads"],
                "manifest_action": manifest_action,
                "audit_action": audit_action,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
