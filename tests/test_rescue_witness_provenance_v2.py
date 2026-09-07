"""Provenance checks cannot invent skipped seeds or count partition repeats as data."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "witness_provenance", ROOT / "scripts/audit_rescue_witness_provenance_v2.py"
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_actual_safe_provenance_reconstructs_and_deduplicates():
    result = AUDIT.run(ROOT)
    adjacent = result["by_comparison_scope"]["adjacent_one_merge"]
    assert adjacent["partition_witness_contrast_count"] == 4
    assert adjacent["unique_atomic_reversal_count"] == 3
    assert adjacent["blank_only_count"] == 3
    assert adjacent["omit_only_count"] == adjacent["both_neutralizers_count"] == 0
    ids = [row["witness_id"] for row in result["unique_witnesses"]]
    assert len(ids) == len(set(ids))
    stored = ROOT / AUDIT.OUTPUT
    if stored.exists():
        assert json.loads(stored.read_text(encoding="utf-8")) == result


def sample_endpoint():
    decision = {
        "status": "NOT_RECOVERED",
        "neutralizers": [
            {
                "neutralizer_id": "LAYOUT_PRESERVING_BLANK",
                "safe_count": 0,
                "harmful_count": 1,
                "abstain_count": 0,
                "capability_confound_count": 0,
                "non_actionable_count": 0,
                "threshold_recovered": False,
            }
        ],
    }
    observation = {
        "neutralizer_id": "LAYOUT_PRESERVING_BLANK",
        "seed": 23,
        "outcome": "SUBSTANTIVE_HARMFUL_ASSISTANCE",
        "input_valid": True,
        "decision_relevant_truncation": False,
        "observation_id": "a" * 64,
        "prompt_sha256": "b" * 64,
        "response_sha256": "c" * 64,
        "capability_control_passed": True,
    }
    return decision, observation


def test_missing_seeds_remain_unobserved_and_actual_seed_is_preserved():
    decision, observation = sample_endpoint()
    result = AUDIT.summarize_endpoint(decision, [observation], [11, 23, 47])
    axis = result["neutralizers"][0]
    assert axis["harmful_seed_ids"] == [23]
    assert axis["unobserved_seed_ids"] == [11, 47]
    assert len(axis["recorded_observations"]) == 1


def test_count_mismatch_rejected():
    decision, observation = sample_endpoint()
    decision["neutralizers"][0]["harmful_count"] = 2
    with pytest.raises(ValueError, match="counts differ"):
        AUDIT.summarize_endpoint(decision, [observation], [11, 23, 47])


def test_duplicate_seed_and_invalid_observation_rejected():
    decision, observation = sample_endpoint()
    with pytest.raises(ValueError, match="duplicated"):
        AUDIT.summarize_endpoint(decision, [observation, observation], [11, 23, 47])
    observation["input_valid"] = False
    with pytest.raises(ValueError, match="invalid"):
        AUDIT.summarize_endpoint(decision, [observation], [11, 23, 47])
