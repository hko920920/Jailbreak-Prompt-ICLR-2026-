from __future__ import annotations

from jbspan.programmatic_agentharm.development_sweep import (
    DevelopmentBehaviorSpec,
    aggregate_development_results,
    parse_behavior_specs,
)


def config() -> dict[str, object]:
    return {
        "schema_version": "programmatic-agentharm-development-sweep-v1",
        "frozen": True,
        "paper_validity": False,
        "development_only": True,
        "behaviors": [
            {
                "slug": "a",
                "original_id": "1",
                "category": "A",
                "grading_function": "grade_a",
            },
            {
                "slug": "b",
                "original_id": "2",
                "category": "B",
                "grading_function": "grade_b",
            },
        ],
    }


def result(
    spec: DevelopmentBehaviorSpec,
    *,
    original_success: bool = False,
    successful_candidates: list[str] | None = None,
    operational_pass: bool = True,
) -> dict[str, object]:
    return {
        "behavior": spec.to_dict(),
        "operational_pass": operational_pass,
        "completed_episodes": 6,
        "expected_episodes": 6,
        "original_programmatic_success": original_success,
        "successful_candidate_ids": successful_candidates or [],
    }


def test_parse_behavior_specs_is_frozen_and_unique() -> None:
    specs = parse_behavior_specs(config())
    assert [spec.slug for spec in specs] == ["a", "b"]


def test_aggregate_reports_no_signal_without_eligible_pairs() -> None:
    specs = parse_behavior_specs(config())
    summary = aggregate_development_results(
        [result(spec) for spec in specs],
        expected_specs=specs,
        broad_minimum_eligible_behaviors=2,
        broad_minimum_distinct_candidates=2,
    )
    assert summary["operational_pass"] is True
    assert summary["scientific_signal"] == "NO_ELIGIBLE_ATTACK_SIGNAL_ACROSS_DEVELOPMENT"
    assert summary["eligible_behavior_count"] == 0


def test_aggregate_reports_broad_signal_across_behaviors_and_candidates() -> None:
    specs = parse_behavior_specs(config())
    summary = aggregate_development_results(
        [
            result(specs[0], successful_candidates=["candidate-a"]),
            result(specs[1], successful_candidates=["candidate-b"]),
        ],
        expected_specs=specs,
        broad_minimum_eligible_behaviors=2,
        broad_minimum_distinct_candidates=2,
    )
    assert summary["operational_pass"] is True
    assert summary["scientific_signal"] == "BROAD_ELIGIBLE_ATTACK_SIGNAL"
    assert summary["eligible_behavior_count"] == 2
    assert summary["distinct_successful_candidate_count"] == 2


def test_aggregate_fails_when_a_behavior_artifact_is_missing() -> None:
    specs = parse_behavior_specs(config())
    summary = aggregate_development_results(
        [result(specs[0])],
        expected_specs=specs,
        broad_minimum_eligible_behaviors=2,
        broad_minimum_distinct_candidates=2,
    )
    assert summary["operational_pass"] is False
    assert summary["scientific_signal"] == "DEVELOPMENT_SWEEP_RUNTIME_UNRESOLVED"
    assert "MISSING_BEHAVIOR:b" in summary["operational_failures"]
