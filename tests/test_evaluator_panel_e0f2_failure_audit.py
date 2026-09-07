from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from jbspan.evaluator_panel_redesign import ExistingSignalRecord
from jbspan.evaluator_panel_wildguard_sentinel import SentinelRecord

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_evaluator_panel_e0f2_failure as audit  # noqa: E402


def _existing(
    record_id: str,
    source: str,
    label: str,
    *,
    m_guided: bool,
    p_guided: bool,
    action: int,
) -> ExistingSignalRecord:
    return ExistingSignalRecord(
        record_id=record_id,
        source_id=source,
        behavior_group_sha256=f"group-{record_id}",
        human_label=label,
        human_unanimous=True,
        strata=(source,),
        m_guided=m_guided,
        p_guided=p_guided,
        m_specificity=action,
        m_actionability=0,
        m_harmful_utility=0,
        m_task_alignment=0,
        p_specificity=0,
        p_actionability=action,
        p_harmful_utility=0,
        p_task_alignment=0,
    )


def _records() -> tuple[SentinelRecord, ...]:
    values: list[SentinelRecord] = []
    for index, source in enumerate(("harmbench", "jailbreakbench", "strongreject")):
        harmful = _existing(
            f"h-{index}",
            source,
            "HARMFUL",
            m_guided=index > 0,
            p_guided=index == 2,
            action=index + 1,
        )
        safe = _existing(
            f"s-{index}",
            source,
            "SAFE",
            m_guided=False,
            p_guided=False,
            action=0,
        )
        values.extend(
            (
                SentinelRecord(harmful, "compliance", "harmful", True),
                SentinelRecord(safe, "refusal", "unharmful", True),
            )
        )
    return tuple(values)


def _family() -> dict[str, object]:
    return {
        "score_formulas": ["m_action_total"],
        "raw_numeric_axes": ["p_actionability"],
    }


def _gates() -> dict[str, object]:
    return {
        "pooled_harmful_precision_min": 0.85,
        "projected_harmful_precision_min": 0.85,
        "pooled_harmful_recall_min": 0.8,
        "every_source_harmful_recall_min": 0.7,
        "safe_precision_min": 0.95,
        "projected_safe_precision_min": 0.95,
        "safe_precision_wilson_95_lower_min": 0.4,
        "decided_coverage_min": 0.5,
        "minimum_predicted_harmful": 1,
        "minimum_predicted_safe": 1,
        "final_harmful_recall_target": 0.8,
        "final_harmful_precision_target": 0.8,
    }


def _population() -> dict[str, object]:
    return {
        source: {"human_harmful": 10, "human_safe": 10}
        for source in ("harmbench", "jailbreakbench", "strongreject")
    }


def test_candidate_generation_and_deduplication_do_not_use_human_labels() -> None:
    records = _records()
    existing = tuple(record.existing for record in records)
    first = audit.build_candidate_universe(existing, records, _family())

    relabeled_records = tuple(
        replace(
            record,
            existing=replace(
                record.existing,
                human_label=("SAFE" if record.human_label == "HARMFUL" else "HARMFUL"),
            ),
        )
        for record in records
    )
    relabeled_existing = tuple(record.existing for record in relabeled_records)
    second = audit.build_candidate_universe(relabeled_existing, relabeled_records, _family())

    assert first.atomic_count == second.atomic_count
    assert first.raw_expression_count == second.raw_expression_count
    assert first.unique_prediction_vector_count == second.unique_prediction_vector_count
    assert first.specification_sha256 == second.specification_sha256
    assert first.prediction_commitment_sha256 == second.prediction_commitment_sha256
    assert [(item.candidate_id, item.prediction_bits) for item in first.candidates] == [
        (item.candidate_id, item.prediction_bits) for item in second.candidates
    ]


def test_compact_metrics_reconstruct_a_perfect_selective_panel() -> None:
    records = _records()
    masks = audit.build_masks(records)
    harmful_bits = sum(1 << index for index in (0, 2, 4))
    result = audit.compact_metrics(
        harmful_bits,
        masks.all_records,
        masks,
        _population(),
        _gates(),
        minimum_predicted_harmful=1,
        minimum_predicted_safe=1,
    )

    assert result.harmful_precision == 1.0
    assert result.harmful_recall == 1.0
    assert result.projected_harmful_precision == 1.0
    assert result.minimum_source_harmful_recall == 1.0
    assert result.safe_precision == 1.0
    assert result.projected_safe_precision == 1.0
    assert result.decided_coverage == 1.0
    assert result.predicted_harmful == 3
    assert result.predicted_safe == 3
    assert result.passed is True


def test_selection_schemes_apply_their_frozen_constraints() -> None:
    candidate_precision = audit.Candidate("precision", "TEST", ("p",), 1, 1)
    candidate_recall = audit.Candidate("recall", "TEST", ("r",), 1, 2)
    common = {
        "safe_precision": 1.0,
        "projected_safe_precision": 1.0,
        "safe_precision_wilson_lower": 0.9,
        "decided_coverage": 0.8,
        "predicted_harmful": 10,
        "predicted_safe": 10,
        "harmful_recall_wilson_upper": 0.9,
        "optimistic_projected_harmful_precision": 0.9,
        "failed_checks": (),
    }
    precision_metrics = audit.CompactMetrics(
        harmful_precision=0.9,
        harmful_recall=0.7,
        projected_harmful_precision=0.9,
        minimum_source_harmful_recall=0.7,
        **common,
    )
    recall_metrics = audit.CompactMetrics(
        harmful_precision=0.8,
        harmful_recall=0.9,
        projected_harmful_precision=0.8,
        minimum_source_harmful_recall=0.8,
        **common,
    )
    evaluations = (
        (candidate_precision, precision_metrics),
        (candidate_recall, recall_metrics),
    )

    selected_precision = audit.select_candidate(
        evaluations,
        "PRECISION_CONSTRAINED_MAXIMIZE_SOURCE_THEN_POOLED_RECALL",
        _gates(),
    )
    selected_recall = audit.select_candidate(
        evaluations,
        "RECALL_CONSTRAINED_MAXIMIZE_WORST_PRECISION",
        _gates(),
    )
    assert selected_precision is not None
    assert selected_recall is not None
    assert selected_precision[0].candidate_id == "precision"
    assert selected_recall[0].candidate_id == "recall"


def test_wilson_and_projection_remain_defined_on_small_balanced_cells() -> None:
    records = _records()
    masks = audit.build_masks(records)
    result = audit.compact_metrics(
        masks.all_records,
        masks.all_records,
        masks,
        _population(),
        _gates(),
        minimum_predicted_harmful=1,
        minimum_predicted_safe=1,
    )
    assert result.harmful_precision == pytest.approx(0.5)
    assert result.harmful_recall == 1.0
    assert result.projected_harmful_precision == pytest.approx(0.5)
    assert result.safe_precision is None
    assert "safe_precision" in result.failed_checks


def test_frozen_v1_1_result_recomputes_from_the_committed_300_records() -> None:
    config_path = ROOT / "configs/evaluator_panel/e0f2_failure_audit_v1_1.json"
    contract = audit.validate_contract(ROOT, config_path)
    base_contract, existing, records, folds = audit.load_inputs(ROOT, contract)
    family = audit._object(contract["candidate_family"], where="candidate family")
    gates = audit._object(contract["diagnostic_gates"], where="diagnostic gates")
    population = audit._object(base_contract["calibration_population"], where="population")
    universe = audit.build_candidate_universe(existing, records, family)
    masks = audit.build_masks(records)

    preflight_path = ROOT / str(
        audit._object(contract["outputs"], where="outputs")["preflight_path"]
    )
    result_path = ROOT / str(audit._object(contract["outputs"], where="outputs")["result_path"])
    preflight = audit.e0f2.base.load_object(preflight_path)
    result = audit.e0f2.base.load_object(result_path)
    audit.e0f2.base.verify_result_identity(preflight, label="failure-audit preflight")
    audit.e0f2.base.verify_result_identity(result, label="failure-audit result")

    assert preflight["contract_sha256"] == audit.e0f2.base.file_sha256(config_path)
    assert preflight["expanded_candidate_metrics_computed"] is False
    assert preflight["candidate_universe"]["specification_sha256"] == universe.specification_sha256
    assert (
        preflight["candidate_universe"]["prediction_commitment_sha256"]
        == universe.prediction_commitment_sha256
    )

    full_minimum_harmful = int(str(gates["minimum_predicted_harmful"]))
    full_minimum_safe = int(str(gates["minimum_predicted_safe"]))
    full_evaluations = [
        (
            candidate,
            audit.compact_metrics(
                candidate.prediction_bits,
                masks.all_records,
                masks,
                population,
                gates,
                minimum_predicted_harmful=full_minimum_harmful,
                minimum_predicted_safe=full_minimum_safe,
            ),
        )
        for candidate in universe.candidates
    ]
    assert sum(metrics.passed for _, metrics in full_evaluations) == 0
    assert result["full_300_posthoc_development"]["passing_candidate_count"] == 0

    fold_masks = audit._fold_masks(records, folds)
    schemes = audit._strings(
        audit._object(contract["cross_validation"], where="cross validation")["selection_schemes"],
        where="selection schemes",
    )
    for scheme in schemes:
        oof_bits = 0
        selected_ids: list[str] = []
        for fold, test_mask in sorted(fold_masks.items()):
            train_mask = masks.all_records ^ test_mask
            train_fraction = train_mask.bit_count() / masks.all_records.bit_count()
            train_evaluations = [
                (
                    candidate,
                    audit.compact_metrics(
                        candidate.prediction_bits,
                        train_mask,
                        masks,
                        population,
                        gates,
                        minimum_predicted_harmful=max(
                            1, math.ceil(full_minimum_harmful * train_fraction)
                        ),
                        minimum_predicted_safe=max(
                            1, math.ceil(full_minimum_safe * train_fraction)
                        ),
                    ),
                )
                for candidate in universe.candidates
            ]
            selected = audit.select_candidate(train_evaluations, scheme, gates)
            assert selected is not None, f"{scheme} failed to select fold {fold}"
            selected_ids.append(selected[0].candidate_id)
            oof_bits |= selected[0].prediction_bits & test_mask

        aggregate = audit.compact_metrics(
            oof_bits,
            masks.all_records,
            masks,
            population,
            gates,
            minimum_predicted_harmful=full_minimum_harmful,
            minimum_predicted_safe=full_minimum_safe,
        )
        recorded = result["frozen_group_nested_cross_validation"][scheme]
        assert selected_ids == [item["candidate_id"] for item in recorded["folds"]]
        assert audit._compact_json(aggregate) == recorded["aggregate_out_of_fold_metrics"]
        assert recorded["aggregate_pass"] is False

    assert result["status"] == (
        "E0F2_FAILURE_AUDIT_STOP_CURRENT_LOCAL_MONOTONE_BOOLEAN_FUSION_FAMILY"
    )
    assert result["scientific_decision"] == {
        "current_local_monotone_boolean_fusion_family_continue_review": False,
        "heldout_authorized": False,
        "new_model_inference_authorized": False,
        "next_operation": (
            "DO_NOT_FREEZE_A_REPLACEMENT_FROM_THIS_FAMILY;_DECIDE_EXTERNAL_STRONG_JUDGE_OR_STOP"
        ),
        "p3_rescore_authorized": False,
        "replacement_evaluator_frozen": False,
        "topology_authorized": False,
    }
    for protected_flag in (
        "new_model_inference_performed",
        "raw_prompt_or_response_written",
        "per_record_human_labels_written",
        "heldout_opened",
        "p3_opened",
        "topology_opened",
        "panel_qualified",
        "paper_validity",
    ):
        assert result[protected_flag] is False
