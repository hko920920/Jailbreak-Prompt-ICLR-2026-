from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jbspan.evaluator_panel_external_data import (
    ExclusionReason,
    ExternalHumanRecord,
    ExternalPartition,
    HumanBinaryLabel,
    behavior_partition,
    deduplicate_external_records,
    normalize_external_text,
    normalized_text_sha256,
    safe_manifest_record,
    sealed_heldout_identity_record,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _record(
    source: str,
    locator: str,
    behavior: str,
    response: str,
    label: HumanBinaryLabel = HumanBinaryLabel.SAFE,
    annotations: int = 3,
) -> ExternalHumanRecord:
    return ExternalHumanRecord(
        source_id=source,
        source_locator=locator,
        behavior_group_sha256=_digest(behavior),
        response_sha256=_digest(response),
        human_label=label,
        human_annotation_count=annotations,
        human_label_support_count=annotations,
        strata=(f"source:{source}",),
    )


def test_normalization_is_nfkc_whitespace_collapsed_and_casefolded() -> None:
    assert normalize_external_text("  Ａ\tB\nStraße  ") == "a b strasse"
    assert normalized_text_sha256("Ａ  B") == normalized_text_sha256("a\nb")


def test_behavior_partition_is_deterministic_and_behavior_level() -> None:
    behavior = _digest("same-behavior")
    first = behavior_partition(behavior, seed="frozen-seed")
    second = behavior_partition(behavior, seed="frozen-seed")
    assert first is second
    assert first in {ExternalPartition.CALIBRATION, ExternalPartition.HELDOUT}


def test_deduplication_prefers_more_annotations_for_same_pair() -> None:
    low = _record("a", "row-1", "goal", "answer", annotations=3)
    high = _record("a", "row-2", "goal", "answer", annotations=5)
    result = deduplicate_external_records((low, high))
    assert result.admitted_records == (high,)
    assert result.exclusions[0].reason is ExclusionReason.SOURCE_PAIR_DUPLICATE
    assert result.exclusions[0].excluded_record_count == 1


def test_deduplication_excludes_label_conflict() -> None:
    safe = _record("a", "row-1", "goal", "answer")
    harmful = _record(
        "a",
        "row-2",
        "goal",
        "answer",
        HumanBinaryLabel.HARMFUL,
    )
    result = deduplicate_external_records((safe, harmful))
    assert result.admitted_records == ()
    assert result.exclusions[0].reason is ExclusionReason.SOURCE_PAIR_LABEL_CONFLICT
    assert result.exclusions[0].excluded_record_count == 2


def test_deduplication_excludes_cross_source_response_overlap() -> None:
    left = _record("a", "row-1", "goal-a", "same-answer")
    right = _record("b", "row-2", "goal-b", "same-answer")
    result = deduplicate_external_records((left, right))
    assert result.admitted_records == ()
    assert {audit.source_id for audit in result.exclusions} == {"a", "b"}
    assert all(
        audit.reason is ExclusionReason.CROSS_SOURCE_RESPONSE_OVERLAP
        for audit in result.exclusions
    )


def test_safe_manifest_contains_hashes_but_no_raw_locator() -> None:
    record = _record("source", "private-row", "goal", "answer")
    safe = safe_manifest_record(record, split_seed="frozen")
    encoded = json.dumps(safe, sort_keys=True)
    assert "private-row" not in encoded
    assert "goal" not in encoded
    assert "answer" not in encoded
    assert safe["human_label"] == "SAFE"


def test_heldout_identity_omits_every_human_label_field() -> None:
    seed = "heldout-seed"
    chosen: ExternalHumanRecord | None = None
    for index in range(1000):
        candidate = _record("source", f"row-{index}", f"goal-{index}", "answer")
        if behavior_partition(
            candidate.behavior_group_sha256,
            seed=seed,
        ) is ExternalPartition.HELDOUT:
            chosen = candidate
            break
    assert chosen is not None
    identity = sealed_heldout_identity_record(chosen, split_seed=seed)
    assert identity["human_label_sealed"] is True
    assert all(not key.startswith("human_") or key == "human_label_sealed" for key in identity)


def test_frozen_e0b_safe_manifest_contract_when_present() -> None:
    root = Path(__file__).resolve().parents[1]
    calibration = root / "data/evaluator_panel_v2/e0b_external_calibration.safe.jsonl"
    heldout = root / "data/evaluator_panel_v2/e0b_external_heldout_identity.safe.jsonl"
    preflight = root / "data/evaluator_panel_v2/e0b_external_source_preflight.safe.json"
    if not calibration.exists() or not heldout.exists() or not preflight.exists():
        return

    calibration_rows = [
        json.loads(line) for line in calibration.read_text(encoding="utf-8").splitlines()
    ]
    heldout_rows = [
        json.loads(line) for line in heldout.read_text(encoding="utf-8").splitlines()
    ]
    rows = calibration_rows + heldout_rows
    result = json.loads(preflight.read_text(encoding="utf-8"))
    assert len(rows) == 1836
    assert len(calibration_rows) == 889
    assert len(heldout_rows) == 947
    assert all(row["partition"] == "calibration" for row in calibration_rows)
    assert all(row["human_label"] in {"SAFE", "HARMFUL"} for row in calibration_rows)
    assert all(row["partition"] == "heldout" for row in heldout_rows)
    assert all(row["human_label_sealed"] is True for row in heldout_rows)
    assert all("human_label" not in row for row in heldout_rows)
    assert len({row["record_id"] for row in rows}) == len(rows)
    assert len({row["response_sha256"] for row in rows}) == len(rows)
    behavior_partitions: dict[str, set[str]] = {}
    for row in rows:
        behavior_partitions.setdefault(row["behavior_group_sha256"], set()).add(
            row["partition"]
        )
    assert all(len(partitions) == 1 for partitions in behavior_partitions.values())
    assert result["status"] == "E0B_EXTERNAL_SOURCE_PREFLIGHT_AND_SPLIT_PASS"
    assert result["heldout_opened"] is False
    assert result["raw_prompt_committed"] is False
    assert result["raw_response_committed"] is False
    assert hashlib.sha256(calibration.read_bytes()).hexdigest() == (
        result["safe_manifests"]["calibration_labeled"]["sha256"]
    )
    assert hashlib.sha256(heldout.read_bytes()).hexdigest() == (
        result["safe_manifests"]["heldout_identity_only"]["sha256"]
    )
