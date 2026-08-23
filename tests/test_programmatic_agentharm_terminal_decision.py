from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION = (
    ROOT
    / "data/programmatic_agentharm/development/agentharm_terminal_decision.json"
)


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_agentharm_terminal_decision_is_self_identifying() -> None:
    value = json.loads(DECISION.read_text(encoding="utf-8"))
    identity = value.pop("decision_identity_sha256")
    assert identity == canonical_sha256(value)


def test_agentharm_terminal_decision_stops_runtime_tuning() -> None:
    value = json.loads(DECISION.read_text(encoding="utf-8"))
    assert value["status"] == (
        "STOP_AGENTHARM_PIVOT_RETURN_TO_NATURAL_LANGUAGE_LOCALIZATION"
    )
    assert value["qwen25_7b"]["eligible_behavior_count"] == 0
    assert value["qwen25_7b"]["resolved_episode_count"] == 36
    assert value["llama31_8b"]["additional_runtime_modifications_allowed"] is False
    assert value["llama31_8b"]["matched_six_behavior_sweep_opened"] is False
    assert value["terminal_rule_application"]["agentharm_main_paper_status"] == (
        "STOPPED"
    )
    assert value["terminal_rule_application"]["next_operation"] == (
        "FREEZE_NATURAL_LANGUAGE_LOCALIZATION_CONTRACT"
    )


def test_agentharm_terminal_decision_preserves_claim_boundary() -> None:
    value = json.loads(DECISION.read_text(encoding="utf-8"))
    boundary = value["claim_boundary"]
    assert boundary["final_outputs_observed"] is False
    assert boundary["heldout_outputs_observed"] is False
    assert boundary["causal_oracle_opened"] is False
    assert boundary["wavelet_used"] is False
    interpretation = value["interpretation_boundary"]
    assert interpretation["agentharm_benchmark_generalization_claimed"] is False
    assert interpretation["causal_localization_hypothesis_rejected"] is False
