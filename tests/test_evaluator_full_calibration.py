from __future__ import annotations

from jbspan.evaluator_full_calibration import (
    behavior_cluster_bootstrap,
    behavior_group_decision_metrics,
    deterministic_execution_order,
)


def test_full_execution_order_is_deterministic() -> None:
    rows = [{"record_id": value} for value in ("c", "a", "b")]
    first = deterministic_execution_order(rows, seed="seed")
    second = deterministic_execution_order(list(reversed(rows)), seed="seed")
    assert first == second
    assert [row["execution_order"] for row in first] == [0, 1, 2]


def test_behavior_group_metrics_do_not_treat_repeated_responses_as_new_groups() -> None:
    metrics = behavior_group_decision_metrics(
        ["HARMFUL", "HARMFUL", "SAFE", "SAFE"],
        ["HARMFUL", "ABSTAIN", "HARMFUL", "ABSTAIN"],
        ["a", "a", "b", "c"],
    )
    assert metrics["behavior_groups"] == 3
    assert metrics["groups_with_at_least_one_decision"] == 2
    assert metrics["behavior_group_decision_coverage"] == 2 / 3
    assert metrics["groups_with_at_least_one_decided_error"] == 1


def test_behavior_cluster_bootstrap_is_deterministic() -> None:
    truth = ["HARMFUL", "HARMFUL", "SAFE", "SAFE", "SAFE", "HARMFUL"]
    predicted = ["HARMFUL", "ABSTAIN", "SAFE", "SAFE", "ABSTAIN", "HARMFUL"]
    groups = ["a", "a", "b", "c", "c", "d"]
    first = behavior_cluster_bootstrap(
        truth,
        predicted,
        groups,
        seed="bootstrap",
        replicates=200,
        metric_names=("decided_coverage", "harmful_precision", "safe_precision"),
    )
    second = behavior_cluster_bootstrap(
        truth,
        predicted,
        groups,
        seed="bootstrap",
        replicates=200,
        metric_names=("decided_coverage", "harmful_precision", "safe_precision"),
    )
    assert first == second
    for interval in first["intervals"].values():
        assert 0 <= interval["lower_2_5"] <= interval["median"]
        assert interval["median"] <= interval["upper_97_5"] <= 1
