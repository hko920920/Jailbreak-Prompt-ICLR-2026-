from __future__ import annotations

import json
from pathlib import Path

from scripts.freeze_fresh_screen_2r_payloads import freeze
from scripts.run_fresh_screen_2r import find_prohibited_keys, load_config, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/natural_language_localization/fresh_screen_2r_v1.json"
DATA = ROOT / "data/natural_language_localization/fresh_screen_2r_v1"


def test_payload_freeze_reconstructs_committed_source_exhaustive_artifacts() -> None:
    payload, audit = freeze(
        ROOT,
        Path("configs/natural_language_localization/local_signal_screen_p3_v1.json"),
        Path("artifacts/p3_signal_screen_v1/sources/HarmBench-lf"),
    )
    assert payload == (DATA / "payload_manifest.safe.jsonl").read_bytes()
    observed_audit = json.loads(
        (DATA / "payload_manifest_audit.safe.json").read_text(encoding="utf-8")
    )
    assert audit == observed_audit
    assert audit["fresh_payloads"] == 37
    assert audit["screen_pair_denominator_total"] == 74


def test_contract_dependencies_and_disclosed_d1_trigger_are_immutable() -> None:
    _path, contract, dependencies = load_config(ROOT, CONFIG)
    assert contract["outcome_boundary_at_freeze"]["d1_stable_pairs"] == 0
    assert contract["outcome_boundary_at_freeze"]["d1_unresolved_pairs"] == 6
    assert contract["outcome_boundary_at_freeze"]["fresh_2r_target_output_observed"] is False
    assert len(dependencies) == len(contract["dependencies"])


def test_preflight_and_seed_11_plan_have_exact_safe_denominators() -> None:
    preflight = json.loads((DATA / "preflight.safe.json").read_text(encoding="utf-8"))
    plan = load_jsonl(DATA / "phase_11_plan.safe.jsonl")
    assert preflight["status"] == "FRESH_SCREEN_2R_PREFLIGHT_PASS"
    assert preflight["payload_count"] == 37
    assert preflight["initial_pair_count"] == 74
    assert len(plan) == 111
    assert sum(row["condition"] == "DIRECT" for row in plan) == 37
    assert sum(row["condition"] == "ATTACKED_H4RM3L" for row in plan) == 37
    assert sum(row["condition"] == "ATTACKED_DEEPINCEPTION" for row in plan) == 37
    assert not find_prohibited_keys(preflight)
    assert not find_prohibited_keys(plan)
