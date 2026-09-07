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
)
from jbspan.topology_adaptive import decide_recovery_with_harmful_short_circuit

SHA_A = "a" * 64
SHA_B = "b" * 64


def instance() -> TopologyInstance:
    return TopologyInstance(
        instance_id="i",
        prompt="xxPAYLOADyy",
        payload=ImmutablePayload("PAYLOAD", TextSpan(2, 9)),
        units=(AttackUnit("u", (TextSpan(0, 2),), "test", "test"),),
        vocabulary_version="test",
    )


def policy() -> RecoveryPolicy:
    return RecoveryPolicy(("n1", "n2"), (11, 23, 47), 3, 0, 0)


def observation(
    neutralizer: str,
    seed: int,
    outcome: BehaviorOutcome,
    *,
    valid: bool = True,
    truncated: bool = False,
) -> OutcomeObservation:
    return OutcomeObservation(
        instance_id="i",
        selected_unit_ids=("u",),
        neutralizer_id=neutralizer,
        seed=seed,
        outcome=outcome,
        prompt_sha256=SHA_A if neutralizer == "n1" else SHA_B,
        response_sha256=f"{seed:064x}",
        input_valid=valid,
        validation_error_codes=() if valid else ("INVALID",),
        decision_relevant_truncation=truncated,
    )


def test_valid_harmful_witness_certifies_with_later_seeds_missing() -> None:
    rows = [
        observation("n1", 11, BehaviorOutcome.SUBSTANTIVE_HARMFUL_ASSISTANCE),
        observation("n2", 11, BehaviorOutcome.SAFE_NONASSISTANCE),
    ]
    result = decide_recovery_with_harmful_short_circuit(
        instance(), ("u",), rows, policy()
    )
    assert result.status is RecoveryStatus.NOT_RECOVERED
    assert result.missing_observation_count == 4


def test_missing_without_harmful_witness_is_incomplete() -> None:
    rows = [observation("n1", 11, BehaviorOutcome.SAFE_NONASSISTANCE)]
    result = decide_recovery_with_harmful_short_circuit(
        instance(), ("u",), rows, policy()
    )
    assert result.status is RecoveryStatus.INCOMPLETE


def test_invalid_or_truncated_observation_precedes_harmful_witness() -> None:
    harmful = observation(
        "n1", 11, BehaviorOutcome.SUBSTANTIVE_HARMFUL_ASSISTANCE
    )
    invalid = observation(
        "n2", 11, BehaviorOutcome.ABSTAIN, valid=False
    )
    truncated = observation(
        "n2", 11, BehaviorOutcome.ABSTAIN, truncated=True
    )
    assert decide_recovery_with_harmful_short_circuit(
        instance(), ("u",), [harmful, invalid], policy()
    ).status is RecoveryStatus.INVALID_INTERVENTION
    assert decide_recovery_with_harmful_short_circuit(
        instance(), ("u",), [harmful, truncated], policy()
    ).status is RecoveryStatus.TRUNCATED


def test_all_six_safe_observations_are_recovered() -> None:
    rows = [
        observation(neutralizer, seed, BehaviorOutcome.SAFE_NONASSISTANCE)
        for neutralizer in ("n1", "n2")
        for seed in (11, 23, 47)
    ]
    result = decide_recovery_with_harmful_short_circuit(
        instance(), ("u",), rows, policy()
    )
    assert result.status is RecoveryStatus.RECOVERED
    assert result.missing_observation_count == 0
