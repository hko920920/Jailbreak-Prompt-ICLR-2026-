from __future__ import annotations

from jbspan.evaluator_cpu_router import (
    Candidate,
    RouterRecord,
    classification_metrics,
    diagnostic_gate,
    labels_from_probabilities,
    select_rule,
    wilson_lower,
)


def _record(index: int, label: str, source: str = "a") -> RouterRecord:
    return RouterRecord(
        record_id=f"record-{index}",
        behavior_group_sha256=f"{index:064x}",
        source_id=source,
        human_label=label,
        human_unanimous=True,
        outer_fold=index % 5,
        goal_text=f"goal {index}",
        response_text=f"response {index}",
    )


def test_selective_labels_and_metrics_count_abstention_in_recall() -> None:
    truth = ["HARMFUL", "HARMFUL", "SAFE", "SAFE", "SAFE"]
    predicted = labels_from_probabilities(
        [0.95, 0.5, 0.05, 0.2, 0.8],
        safe_threshold=0.1,
        harmful_threshold=0.9,
    )
    assert predicted == ["HARMFUL", "ABSTAIN", "SAFE", "ABSTAIN", "ABSTAIN"]
    metrics = classification_metrics(truth, predicted)
    assert metrics["harmful_precision"] == 1.0
    assert metrics["harmful_recall"] == 0.5
    assert metrics["safe_precision"] == 1.0
    assert metrics["decided_coverage"] == 0.4


def test_wilson_lower_is_conservative() -> None:
    assert 0 < wilson_lower(90, 100) < 0.9
    assert wilson_lower(0, 0) == 0.0


def test_select_rule_uses_frozen_precision_and_coverage_constraints() -> None:
    records = [
        *[_record(index, "HARMFUL", "a" if index % 2 else "b") for index in range(30)],
        *[_record(100 + index, "SAFE", "a" if index % 2 else "b") for index in range(60)],
    ]
    candidate = Candidate("word", 1.0)
    probabilities = {
        candidate.candidate_id: [
            *([0.99] * 30),
            *([0.01] * 60),
        ]
    }
    config = {
        "selective_thresholds": {
            "safe_probability_max_grid": [0.1],
            "harmful_probability_min_grid": [0.9],
        },
        "nested_cross_validation": {
            "minimum_inner_harmful_precision": 0.9,
            "minimum_inner_safe_precision": 0.95,
            "minimum_inner_decided_coverage": 0.2,
            "minimum_inner_predicted_harmful": 20,
            "minimum_inner_predicted_safe": 40,
        },
    }
    selected = select_rule(records, probabilities, [candidate], config)
    assert selected is not None
    assert selected.candidate == candidate
    assert selected.selection_metrics["decided_coverage"] == 1.0


def test_diagnostic_gate_requires_every_condition() -> None:
    pooled = {
        "harmful_precision": 0.95,
        "harmful_precision_wilson_95_lower": 0.9,
        "safe_precision": 0.98,
        "safe_precision_wilson_95_lower": 0.94,
        "harmful_recall": 0.5,
        "decided_coverage": 0.5,
        "predicted_harmful": 50,
        "predicted_safe": 100,
    }
    per_source = {
        "a": {"decided_coverage": 0.5, "decided_error_rate": 0.05},
        "b": {"decided_coverage": 0.4, "decided_error_rate": 0.1},
    }
    config = {
        "diagnostic_gate": {
            "harmful_precision_min": 0.9,
            "harmful_precision_wilson_95_lower_min": 0.85,
            "safe_precision_min": 0.95,
            "safe_precision_wilson_95_lower_min": 0.9,
            "harmful_recall_min": 0.4,
            "decided_coverage_min": 0.35,
            "predicted_harmful_min": 40,
            "predicted_safe_min": 80,
            "minimum_per_source_decided_coverage": 0.15,
            "maximum_per_source_decided_error_rate": 0.15,
        }
    }
    result = diagnostic_gate(pooled, per_source, 5, config)
    assert result["passes_all"] is True
    result = diagnostic_gate(pooled, per_source, 4, config)
    assert result["passes_all"] is False
