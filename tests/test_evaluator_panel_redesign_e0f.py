from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from jbspan.evaluator_panel_redesign import (
    SCORE_FORMULAS,
    ExistingSignalRecord,
    ScoreCandidate,
    assign_behavior_group_folds,
    build_existing_signal_records,
    candidate_gate,
    candidate_predictions,
    canonical_json_bytes,
    enumerate_score_candidates,
    harmful_metrics,
    score_record,
    stage_summary,
    staged_wildguard_assignment,
)


def _record(
    index: int,
    *,
    source: str = "alpha",
    label: str = "SAFE",
    group: str | None = None,
    m_guided: bool = False,
    p_guided: bool = False,
    m_scores: tuple[int, int, int, int] = (0, 0, 0, 0),
    p_scores: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> ExistingSignalRecord:
    return ExistingSignalRecord(
        record_id=f"{index:064x}",
        source_id=source,
        behavior_group_sha256=group or f"{index:064x}",
        human_label=label,
        human_unanimous=True,
        strata=(f"source:{source}",),
        m_guided=m_guided,
        p_guided=p_guided,
        m_specificity=m_scores[0],
        m_actionability=m_scores[1],
        m_harmful_utility=m_scores[2],
        m_task_alignment=m_scores[3],
        p_specificity=p_scores[0],
        p_actionability=p_scores[1],
        p_harmful_utility=p_scores[2],
        p_task_alignment=p_scores[3],
    )


def test_score_family_is_finite_source_blind_and_monotone() -> None:
    low = _record(1)
    high = _record(
        2,
        source="different-source",
        m_guided=True,
        p_guided=True,
        m_scores=(2, 2, 2, 2),
        p_scores=(2, 2, 2, 2),
    )
    assert len(SCORE_FORMULAS) == 17
    for formula in SCORE_FORMULAS:
        assert score_record(high, formula) >= score_record(low, formula)
    same_features_other_source = _record(3, source="third-source")
    for formula in SCORE_FORMULAS:
        assert score_record(low, formula) == score_record(same_features_other_source, formula)


def test_harmful_metrics_and_gate_keep_worst_group_constraint() -> None:
    records = (
        _record(1, label="HARMFUL", m_guided=True),
        _record(2, label="HARMFUL", m_guided=False),
        _record(3, label="SAFE", m_guided=True),
        _record(4, label="SAFE", m_guided=False),
    )
    candidate = ScoreCandidate("m_guided", 1)
    metrics = harmful_metrics(records, candidate_predictions(records, candidate))
    assert metrics["true_positive"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    gate = candidate_gate(
        records,
        candidate,
        {
            "harmful_precision_min": 0.4,
            "harmful_precision_wilson_95_lower_min": 0.0,
            "harmful_recall_min": 0.4,
            "minimum_predicted_harmful": 1,
            "worst_group_min_human_harmful": 2,
            "worst_group_harmful_fnr_max": 0.4,
        },
    )
    assert gate["checks"]["worst_group_harmful_false_negative_rate"] is False
    assert gate["pass"] is False


def test_behavior_group_folds_are_deterministic_and_never_split_groups() -> None:
    records = tuple(
        _record(
            index,
            source="alpha" if index % 2 else "beta",
            label="HARMFUL" if index % 3 == 0 else "SAFE",
            group=f"{index // 2:064x}",
        )
        for index in range(60)
    )
    first = assign_behavior_group_folds(records, fold_count=5, seed="fixed")
    second = assign_behavior_group_folds(records, fold_count=5, seed="fixed")
    assert first == second
    assert set(first.values()) == set(range(5))
    by_group: dict[str, set[int]] = {}
    for record in records:
        by_group.setdefault(record.behavior_group_sha256, set()).add(first[record.record_id])
    assert all(len(folds) == 1 for folds in by_group.values())


def test_staged_assignment_is_nested_144_300_889_shape() -> None:
    records: list[ExistingSignalRecord] = []
    index = 0
    for source in ("a", "b", "c"):
        for label in ("SAFE", "HARMFUL"):
            for _ in range(55):
                records.append(_record(index, source=source, label=label))
                index += 1
    assignment = staged_wildguard_assignment(
        records,
        seed="fixed",
        stage1_per_source_label=24,
        stage2_per_source_label=50,
    )
    summary = stage_summary(records, assignment)
    assert summary["cumulative"]["E0F_1_SENTINEL"]["records"] == 144
    assert summary["cumulative"]["E0F_2_INTERMEDIATE"]["records"] == 300
    assert summary["cumulative"]["E0F_3_FULL"]["records"] == 330
    first_counts = Counter(
        (record.source_id, record.human_label)
        for record in records
        if assignment[record.record_id] == "E0F_1_SENTINEL"
    )
    assert set(first_counts.values()) == {24}


def test_existing_signal_builder_rejects_missing_axis_cell() -> None:
    calibration = [
        {
            "schema_version": "jbspan-e0b-external-human-label-record-v1",
            "partition": "calibration",
            "record_id": "a" * 64,
            "source_id": "alpha",
            "behavior_group_sha256": "b" * 64,
            "human_label": "SAFE",
            "human_unanimous": True,
            "strata": ["source:alpha"],
        }
    ]
    with pytest.raises(ValueError, match="record set"):
        build_existing_signal_records(calibration, [])


def test_candidates_enumerate_only_observed_thresholds() -> None:
    records = (
        _record(1, p_guided=False),
        _record(2, p_guided=True),
    )
    candidates = enumerate_score_candidates(records, ("p_guided",))
    assert [candidate.candidate_id for candidate in candidates] == [
        "p_guided@ge_00",
        "p_guided@ge_01",
    ]


def test_completed_e0f_result_identity_and_seals_when_present() -> None:
    root = Path(__file__).resolve().parents[1]
    result_path = root / "data/evaluator_panel_v2/e0f_existing_signal_audit.safe.json"
    if not result_path.is_file():
        return
    result = json.loads(result_path.read_text(encoding="utf-8"))
    identity = result.pop("result_identity_sha256")
    assert hashlib.sha256(canonical_json_bytes(result)).hexdigest() == identity
    assert result["new_model_inference_performed"] is False
    assert result["protected_boundary"] == {
        "heldout_candidate_outputs_generated": False,
        "heldout_candidate_metrics_computed": False,
        "p3_responses_opened": False,
        "topology_outcomes_opened": False,
    }
    assert result["heldout_boundary"]["primary_records"] == 803
    assert (
        result["heldout_boundary"]["labeled_commitments"]["primary_803"]["labeled_rows_written"]
        is False
    )
    primary_path = root / result["heldout_boundary"]["primary_identity_manifest"]["path"]
    primary_rows = [
        json.loads(line) for line in primary_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(primary_rows) == 803
    assert all(row["human_label_sealed"] is True for row in primary_rows)
    assert all("human_label" not in row for row in primary_rows)
