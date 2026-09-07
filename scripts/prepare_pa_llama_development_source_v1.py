"""SAFE-only inventory of all exposed C1N inputs; no private-content reader.

The only file contents opened are three exact pinned SAFE metadata artifacts.
Private records are stat'ed for prospective descriptors, never opened/hashed.
No dataset-core path, inference, network, subprocess or output-write API exists.
The inventory grants no data-access or inference authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SAFE_BASE = "data/natural_language_localization/c1n_h4rm3l_fresh_screen_v1/"
SOURCE_PINS = [
    {
        "path": SAFE_BASE + "phase_11_plan.safe.jsonl",
        "size_bytes": 207293,
        "sha256": "6b0c728986491af427a66f1e254b936ddbb608e8f6cfe3e9c0978b2a393c9baa",
    },
    {
        "path": SAFE_BASE + "phase_11_generation.safe.jsonl",
        "size_bytes": 351998,
        "sha256": "fb161099f018ab890994976776a9e3d542f7a8f0996d97793487b7c3229b6745",
    },
    {
        "path": SAFE_BASE + "materializations.safe.jsonl",
        "size_bytes": 165895,
        "sha256": "ca9c574f2812dd3a3d5d8bc970092108ca36100f3d1e4e667ce94a5121a734f2",
    },
]
OLD_CONTRACT = "14d965711a112f35eb7bf27dfc4646b5dbe4a4f867836ee52c036129cdd90be8"
TARGET = "qwen2.5-7b-instruct-q4-k-m"
OTHER_TARGET = "google-gemma-4-e4b-it-qat-q4-0"
CONDITIONS = ("DIRECT", "ATTACKED_H4RM3L")
PRIVATE_ROOT = "artifacts/c1n_h4rm3l_fresh_screen_v1/private_records/scientific_generations"
RAW_KEYS = {"prompt", "payload", "response", "text", "question", "guidelines", "stdout", "stderr"}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "DUPLICATE_KEY")
            value[key] = item
        return value

    def invalid(_):
        raise ValueError("NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def assert_safe(value):
    if isinstance(value, dict):
        require(not RAW_KEYS.intersection(value), "RAW_CONTENT_FIELD")
        for item in value.values():
            assert_safe(item)
    elif isinstance(value, list):
        for item in value:
            assert_safe(item)


def sha(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value), "SHA_INVALID")
    return value


def resolve_path(root, relative):
    require(isinstance(relative, str) and "\\" not in relative, "PATH_INVALID")
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "PATH_INVALID")
    lexical = root / relative
    resolved = lexical.resolve()
    require(resolved.is_relative_to(root) and resolved != root, "PATH_ESCAPES_ROOT")
    # Reject aliases/reparse redirects, even when their destination remains under root.
    require(resolved == lexical.absolute(), "PATH_ALIAS_FORBIDDEN")
    require(not any(part.is_symlink() for part in [lexical, *lexical.parents]), "SYMLINK_FORBIDDEN")
    return resolved


def read_pinned_safe(root, pin):
    path = resolve_path(root, pin["path"])
    raw = path.read_bytes()
    require(len(raw) == pin["size_bytes"] and digest(raw) == pin["sha256"], "SAFE_SOURCE_DRIFT")
    rows = [strict_json(line) for line in raw.splitlines() if line.strip()]
    assert_safe(rows)
    return rows


def build_rows(plans, generations, materials):
    """Pure complete-cohort selection. Never consult response labels or eligibility."""
    require(len(plans) == len(generations) == len(materials) == 180, "FULL_DENOMINATOR_REQUIRED")
    for rows in (plans, generations, materials):
        require(all(isinstance(row, dict) for row in rows), "ROW_OBJECT_REQUIRED")
        assert_safe(rows)
    by_generation = {row["record_id"]: row for row in generations}
    by_material = {
        (row["target_id"], row["payload_position"], row["condition"]): row for row in materials
    }
    require(len(by_generation) == len(by_material) == 180, "DUPLICATE_RECORD")
    require(len({row["record_id"] for row in plans}) == 180, "DUPLICATE_PLAN")
    expected_keys = {
        (target, position, condition)
        for target in (TARGET, OTHER_TARGET)
        for position in range(45)
        for condition in CONDITIONS
    }
    actual_keys = {(row["target_id"], row["payload_position"], row["condition"]) for row in plans}
    require(actual_keys == expected_keys and set(by_material) == expected_keys, "COHORT_CHANGED")
    require(set(by_generation) == {row["record_id"] for row in plans}, "RECORD_JOIN_MISMATCH")
    output = []
    payload_identity = {}
    topics = {}
    for plan in plans:
        require(type(plan["phase_seed"]) is int and plan["phase_seed"] == 11, "SEED_CHANGED")
        require(plan["contract_sha256"] == OLD_CONTRACT, "OLD_CONTRACT_CHANGED")
        position = plan["payload_position"]
        require(type(position) is int and 0 <= position < 45, "POSITION_INVALID")
        target, condition = plan["target_id"], plan["condition"]
        material = by_material[(target, position, condition)]
        generation = by_generation[plan["record_id"]]
        for key in (
            "target_id",
            "payload_position",
            "condition",
            "pair_id",
            "payload_sha256",
            "prompt_sha256",
        ):
            require(
                canonical(generation.get(key)) == canonical(plan.get(key))
                and canonical(material.get(key)) == canonical(plan.get(key)),
                "IDENTITY_JOIN_MISMATCH",
            )
        require(
            type(generation["seed"]) is int and generation["seed"] == 11, "GENERATION_SEED_CHANGED"
        )
        for key in ("record_id", "pair_id", "payload_sha256", "prompt_sha256", "topic_sha256"):
            sha(plan[key])
        require(material.get("topic_sha256") == plan["topic_sha256"], "TOPIC_MISMATCH")
        require(
            material.get("partition_pass") is True
            and type(material.get("payload_byte_occurrence_count")) is int
            and material["payload_byte_occurrence_count"] == 1,
            "INVALID_MATERIALIZATION",
        )
        require(
            type(material["prompt_utf8_bytes"]) is int and material["prompt_utf8_bytes"] > 0,
            "PROMPT_SIZE_INVALID",
        )
        require(
            type(material.get("reserved_chat_marker_count")) is int
            and material["reserved_chat_marker_count"] == 0,
            "RESERVED_MARKER_PRESENT",
        )
        require(
            type(material["unit_count"]) is int
            and material["unit_count"] == (0 if condition == "DIRECT" else 3),
            "UNIT_COUNT_CHANGED",
        )
        if condition == "DIRECT":
            require(plan["prompt_sha256"] == plan["payload_sha256"], "DIRECT_NOT_EXACT_PAYLOAD")
        pair_identity = (plan["payload_sha256"], plan["topic_sha256"])
        require(
            payload_identity.setdefault(position, pair_identity) == pair_identity, "PAYLOAD_DRIFT"
        )
        topics.setdefault(plan["topic_sha256"], set()).add(position)
        if target != TARGET:
            continue
        execution_sha = sha(generation["execution_identity_sha256"])
        output.append(
            {
                "payload_position": position,
                "condition": condition,
                "source_target_id": target,
                "source_seed": 11,
                "source_record_id": plan["record_id"],
                "source_execution_identity_sha256": execution_sha,
                "payload_sha256": plan["payload_sha256"],
                "topic_sha256": plan["topic_sha256"],
                "prompt_sha256": plan["prompt_sha256"],
                "prompt_utf8_bytes": material["prompt_utf8_bytes"],
                "unit_count": material["unit_count"],
                "unit_manifest_sha256": sha(material["unit_manifest_sha256"]),
                "fragment_manifest_sha256": sha(material["fragment_manifest_sha256"]),
                "private_source": {
                    "path": f"{PRIVATE_ROOT}/{TARGET}/{execution_sha}.json",
                    "sha256": sha(generation["private_record_sha256"]),
                },
            }
        )
    require(
        len(payload_identity) == 45 and len({x[0] for x in payload_identity.values()}) == 45,
        "PAYLOAD_COUNT_CHANGED",
    )
    require(
        len(topics) == 15 and all(len(group) == 3 for group in topics.values()),
        "TOPIC_COUNT_CHANGED",
    )
    require(len(output) == 90, "SELECTED_DENOMINATOR_CHANGED")
    require(
        len({row["private_source"]["path"] for row in output}) == 90,
        "DUPLICATE_PRIVATE_SOURCE_PATH",
    )
    return sorted(
        output, key=lambda row: (row["payload_position"], CONDITIONS.index(row["condition"]))
    )


def prepare(root):
    root = root.resolve()
    rows = build_rows(*(read_pinned_safe(root, pin) for pin in SOURCE_PINS))
    for row in rows:
        path = resolve_path(root, row["private_source"]["path"])
        require(path.is_file(), "PRIVATE_SOURCE_ABSENT")
        size = path.stat().st_size  # Metadata only: NO open, read or hash of this file.
        require(0 < size <= 2_000_000, "PRIVATE_SOURCE_SIZE_INVALID")
        row["private_source"]["size_bytes"] = size
    result = {
        "schema_version": "jbspan-pa-llama-development-source-inventory-v1",
        "execution_authorized": False,
        "private_content_access_authorized": False,
        "evidence_class": "EXPOSED_DEVELOPMENT_INPUT_INVENTORY_NOT_RESULTS",
        "source_pins": SOURCE_PINS,
        "old_c1n_contract_sha256": OLD_CONTRACT,
        "selected_source_target": TARGET,
        "selection": "ALL_45_PAYLOADS_BOTH_CONDITIONS_NO_OUTCOME_FILTER",
        "payloads": 45,
        "topics": 15,
        "input_records": 90,
        "old_private_content_reads": 0,
        "private_record_metadata_stats": 90,
        "private_hashes_reused_from_pinned_safe_receipts_not_rehashed": True,
        "prospective_private_file_reads_if_later_authorized": 90,
        "prospective_files_also_contain_historical_responses": True,
        "historical_responses_not_selected_or_rejudged": True,
        "dataset_core_opened": False,
        "sealed_A60_B60_opened": False,
        "model_calls": 0,
        "rows": rows,
        "rows_sha256": digest(canonical(rows)),
    }
    assert_safe(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.root)
    except (ValueError, KeyError, OSError, TypeError) as error:
        code = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"inventory_passed": False, "error_code": code}))
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
