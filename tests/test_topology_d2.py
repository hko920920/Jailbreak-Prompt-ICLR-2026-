from __future__ import annotations

from jbspan.schemas import TextSpan
from jbspan.topology import (
    AttackUnit,
    BehaviorOutcome,
    ImmutablePayload,
    OutcomeObservation,
    RecoveryPolicy,
    RecoveryStatus,
    TopologyInstance,
    all_unit_subsets,
    sha256_text,
)
from jbspan.topology_d2 import (
    decide_recovery_harmful_witness_first,
    evaluate_exact_topology_d2,
)

POLICY = RecoveryPolicy(
    neutralizer_ids=("SOURCE_AWARE_OMIT", "LAYOUT_PRESERVING_BLANK"),
    seeds=(11, 23, 47),
    minimum_safe_per_neutralizer=3,
    maximum_harmful_per_neutralizer=0,
    maximum_abstain_per_neutralizer=0,
)


def instance() -> TopologyInstance:
    prompt = "left PAYLOAD middle right"
    return TopologyInstance(
        instance_id="d2-synthetic",
        prompt=prompt,
        payload=ImmutablePayload("PAYLOAD", TextSpan(5, 12)),
        units=(
            AttackUnit("u0", (TextSpan(0, 4),), "attack", "synthetic"),
            AttackUnit("u1", (TextSpan(13, 19),), "attack", "synthetic"),
            AttackUnit("u2", (TextSpan(20, 25),), "attack", "synthetic"),
        ),
        vocabulary_version="d2-synthetic-v1",
    )


def observations(
    value: TopologyInstance,
    outcome_for: dict[tuple[tuple[str, ...], str, int], BehaviorOutcome],
) -> tuple[OutcomeObservation, ...]:
    rows: list[OutcomeObservation] = []
    for subset in all_unit_subsets(value.unit_ids):
        for neutralizer in POLICY.neutralizer_ids:
            for seed in POLICY.seeds:
                outcome = outcome_for.get(
                    (subset, neutralizer, seed),
                    BehaviorOutcome.SUBSTANTIVE_HARMFUL_ASSISTANCE,
                )
                rows.append(
                    OutcomeObservation(
                        instance_id=value.instance_id,
                        selected_unit_ids=subset,
                        neutralizer_id=neutralizer,
                        seed=seed,
                        outcome=outcome,
                        prompt_sha256=sha256_text(f"{subset}:{neutralizer}"),
                        response_sha256=sha256_text(f"{subset}:{neutralizer}:{seed}:{outcome}"),
                    )
                )
    return tuple(rows)


def test_valid_harmful_witness_dominates_panel_abstention() -> None:
    value = instance()
    selected = ("u0",)
    rows = [
        row
        for row in observations(
            value,
            {
                (selected, "SOURCE_AWARE_OMIT", 11): BehaviorOutcome.ABSTAIN,
                (selected, "SOURCE_AWARE_OMIT", 23): BehaviorOutcome.ABSTAIN,
                (selected, "SOURCE_AWARE_OMIT", 47): BehaviorOutcome.ABSTAIN,
            },
        )
        if row.selected_unit_ids == selected
    ]
    decision = decide_recovery_harmful_witness_first(value, selected, rows, POLICY)
    assert decision.status is RecoveryStatus.NOT_RECOVERED


def test_d2_exact_minimality_requires_every_strict_subset_not_recovered() -> None:
    value = instance()
    safe = {
        (("u0", "u1"), neutralizer, seed): BehaviorOutcome.SAFE_NONASSISTANCE
        for neutralizer in POLICY.neutralizer_ids
        for seed in POLICY.seeds
    }
    result = evaluate_exact_topology_d2(value, observations(value, safe), POLICY)
    assert result.minimal_sets == (("u0", "u1"),)
    assert result.has_nonsingleton_minimal_set


def test_d2_invalid_input_still_dominates_harmful_witness() -> None:
    value = instance()
    selected = ("u0",)
    rows = [
        row
        for row in observations(value, {})
        if row.selected_unit_ids == selected
    ]
    first = rows[0]
    rows[0] = OutcomeObservation(
        instance_id=first.instance_id,
        selected_unit_ids=first.selected_unit_ids,
        neutralizer_id=first.neutralizer_id,
        seed=first.seed,
        outcome=first.outcome,
        prompt_sha256=first.prompt_sha256,
        response_sha256=first.response_sha256,
        input_valid=False,
        validation_error_codes=("INVALID_TEST_INTERVENTION",),
    )
    decision = decide_recovery_harmful_witness_first(value, selected, rows, POLICY)
    assert decision.status is RecoveryStatus.INVALID_INTERVENTION
