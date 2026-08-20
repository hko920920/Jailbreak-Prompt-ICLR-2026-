from __future__ import annotations

import importlib.util
from pathlib import Path


def module():
    path = Path("scripts/run_gate1_step3b_primary_judge_experiment.py")
    spec = importlib.util.spec_from_file_location("primary_experiment", path)
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_frozen_confirmatory_identity_and_balance() -> None:
    value = module()
    ids = [payload_id for payload_id, _ in value.CONFIRMATORY_ASSIGNMENT]
    candidates = [candidate_id for _, candidate_id in value.CONFIRMATORY_ASSIGNMENT]
    assert value.canonical_json_sha256(ids) == value.CONFIRMATORY_IDS_SHA256
    counts = {candidate: candidates.count(candidate) for candidate in set(candidates)}
    assert set(counts.values()) == {2}


def test_primary_parser_and_stability() -> None:
    value = module()
    parsed = value.parse_wildguard_output(
        "Prompt harmful: yes\nResponse refusal: no\nResponse harmful: yes"
    )
    assert parsed == ("harmful", "compliance", "harmful")
    assert value.stable_label([True, True, False]) == "HARMFUL"
    assert value.stable_label([False, False, None]) == "SAFE"
    assert value.stable_label([True, False, None]) == "EVALUATOR_ABSTAIN"
