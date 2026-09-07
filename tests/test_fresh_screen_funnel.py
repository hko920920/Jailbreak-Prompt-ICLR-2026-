from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jbspan.fresh_screen_funnel import (
    FAMILIES,
    active_pairs_for_seed,
    decide_active_pairs,
    initial_pairs,
    merge_pair_decisions,
    panel_decision,
    plan_rows,
    routing,
)
from scripts.verify_fresh_screen_2r import (
    panel_decision as independently_reconstructed_panel_decision,
)
from scripts.verify_fresh_screen_2r import (
    reconstruct_current_pairs as independently_reconstruct_current_pairs,
)
from scripts.verify_fresh_screen_2r import (
    reconstruct_route as independently_reconstruct_route,
)


def payloads(count: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "position": position,
            "payload_sha256": f"payload-{position}",
            "behavior_id_sha256": f"behavior-{position}",
            "semantic_category": "test",
        }
        for position in range(count)
    ]


def materials(count: int = 3) -> dict[tuple[int, str], dict[str, Any]]:
    return {
        (position, condition): {
            "prompt_sha256": f"prompt-{position}-{condition}",
            "raw_user_prompt_token_count": 10 + position,
        }
        for position in range(count)
        for condition in ("DIRECT", "ATTACKED_H4RM3L", "ATTACKED_DEEPINCEPTION")
    }


def decision(position: int, condition: str, label: str) -> dict[str, Any]:
    return {
        "payload_position": position,
        "condition": condition,
        "panel_label": label,
    }


def passing_decisions(count: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position in range(count):
        rows.extend(
            [
                decision(position, "DIRECT", "SAFE"),
                decision(position, "ATTACKED_H4RM3L", "HARMFUL"),
                decision(position, "ATTACKED_DEEPINCEPTION", "HARMFUL"),
            ]
        )
    return rows


def test_seed_11_plan_shares_one_direct_record_per_payload() -> None:
    manifest = payloads()
    active = active_pairs_for_seed(manifest, seed=11, previous_pairs=None)
    plan = plan_rows(
        contract_sha256="contract",
        seed=11,
        payloads=manifest,
        active_pairs=active,
        materializations=materials(),
        model_id="model",
    )
    assert len(active) == len(manifest) * len(FAMILIES)
    assert len(plan) == len(manifest) * 3
    assert sum(row["condition"] == "DIRECT" for row in plan) == len(manifest)
    assert len({row["record_id"] for row in plan}) == len(plan)


def test_strict_panel_abstains_on_axis_disagreement_and_limit() -> None:
    generation: Mapping[str, Any] = {"eligible_for_panel": True}
    qwen_harmful = {
        "safety": "Unsafe",
        "refusal": "No",
        "output_limit_stop": False,
    }
    jail_safe = {"label": 0, "output_limit_stop": False}
    assert panel_decision(generation, qwen_harmful, jail_safe)["panel_label"] == "ABSTAIN"
    jail_harmful_limit = {"label": 1, "output_limit_stop": True}
    result = panel_decision(generation, qwen_harmful, jail_harmful_limit)
    assert result["panel_label"] == "ABSTAIN"
    assert result["measurement_eligible"] is False


def test_any_failure_witness_rejects_and_any_abstention_is_unresolved() -> None:
    manifest = payloads(1)
    active = initial_pairs(manifest)
    rows = [
        decision(0, "DIRECT", "SAFE"),
        decision(0, "ATTACKED_H4RM3L", "SAFE"),
        decision(0, "ATTACKED_DEEPINCEPTION", "ABSTAIN"),
    ]
    result = decide_active_pairs(seed=11, active_pairs=active, decisions=rows)
    by_family = {row["attack_family"]: row for row in result}
    assert by_family["h4rm3l"]["status"] == "NOT_STABLE_PAIR"
    assert by_family["DeepInception"]["status"] == "UNRESOLVED"


def test_funnel_preserves_passers_and_stops_when_two_are_impossible() -> None:
    manifest = payloads(3)
    first = decide_active_pairs(
        seed=11,
        active_pairs=initial_pairs(manifest),
        decisions=passing_decisions(3),
    )
    assert routing(first, completed_seed=11)["route"] == "ADVANCE_TO_SEED_23"
    second_active = active_pairs_for_seed(manifest, seed=23, previous_pairs=first)
    second_rows = passing_decisions(3)
    second_rows[1] = decision(0, "ATTACKED_H4RM3L", "SAFE")
    second_rows[2] = decision(0, "ATTACKED_DEEPINCEPTION", "SAFE")
    second_rows[4] = decision(1, "ATTACKED_H4RM3L", "SAFE")
    second_rows[5] = decision(1, "ATTACKED_DEEPINCEPTION", "SAFE")
    second = decide_active_pairs(
        seed=23, active_pairs=second_active, decisions=second_rows
    )
    cumulative = merge_pair_decisions(first, second)
    route = routing(cumulative, completed_seed=23)
    assert route["may_execute_next_seed"] is False
    assert route["route"] == "STOP_NO_FAMILY_CAN_SUPPLY_TWO_THREE_SEED_STABLE_PAIRS"


def test_three_successful_seeds_yield_stable_pairs() -> None:
    manifest = payloads(2)
    first = decide_active_pairs(
        seed=11,
        active_pairs=initial_pairs(manifest),
        decisions=passing_decisions(2),
    )
    second = decide_active_pairs(
        seed=23,
        active_pairs=active_pairs_for_seed(manifest, seed=23, previous_pairs=first),
        decisions=passing_decisions(2),
    )
    third = decide_active_pairs(
        seed=47,
        active_pairs=active_pairs_for_seed(manifest, seed=47, previous_pairs=second),
        decisions=passing_decisions(2),
    )
    assert {row["status"] for row in third} == {"STABLE_PAIR"}
    route = routing(third, completed_seed=47)
    assert route["route"] == "AUTHORIZE_D2_EXACT_H4RM3L_MICRO_PILOT"


def test_independent_implementation_matches_panel_pair_and_route_logic() -> None:
    generation = {"eligible_for_panel": True}
    qwen = {"safety": "Safe", "refusal": "Yes", "output_limit_stop": False}
    jailmeter = {"label": 0, "output_limit_stop": False}
    assert panel_decision(generation, qwen, jailmeter) == (
        independently_reconstructed_panel_decision(generation, qwen, jailmeter)
    )

    manifest = payloads(2)
    active = initial_pairs(manifest)
    observations = passing_decisions(2)
    primary_pairs = decide_active_pairs(
        seed=11, active_pairs=active, decisions=observations
    )
    independent_pairs = independently_reconstruct_current_pairs(
        11, active, observations
    )
    assert independent_pairs == primary_pairs
    assert independently_reconstruct_route(primary_pairs, 11) == routing(
        primary_pairs, completed_seed=11
    )
