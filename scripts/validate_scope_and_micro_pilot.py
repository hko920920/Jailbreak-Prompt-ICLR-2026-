from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def validate(scope_path: Path, pilot_path: Path) -> dict[str, Any]:
    scope = load_object(scope_path)
    pilot = load_object(pilot_path)

    checks = {
        "scope_frozen": scope.get("frozen") is True,
        "scope_preoutcome": scope.get("status")
        == "FROZEN_BEFORE_NEW_TARGET_MODEL_OUTCOMES",
        "primary_object_is_minimal_sets": scope.get("primary_object")
        == "ALL_ROBUST_MINIMAL_RECOVERY_SETS_WITHIN_A_FROZEN_COARSE_INTERVENTION_VOCABULARY",
        "development_families_are_h4rm3l_and_gcg": [
            row.get("name") for row in scope["development_core"]["families"]
        ]
        == ["h4rm3l", "GCG"],
        "harmbench_not_production_vote": scope["measurement"]
        ["harmbench_is_production_vote"]
        is False,
        "human_audit_required": scope["measurement"]
        ["human_audit_required_for_paper_reported_baselines_and_cut_sets"]
        is True,
        "wavelet_closed": scope["wavelet"]["opened"] is False,
        "pilot_frozen": pilot.get("frozen") is True,
        "pilot_development_only": pilot.get("paper_validity") is False
        and pilot.get("evidence_class") == "DEVELOPMENT",
        "pilot_two_families": [row.get("name") for row in pilot["families"]]
        == ["h4rm3l", "GCG"],
        "all_subsets_required": pilot["causal_interventions"]
        ["enumerate_all_subsets"]
        is True,
        "coarse_unit_cap_six": pilot["causal_interventions"]
        ["maximum_coarse_units_per_instance"]
        == 6,
        "two_neutralizers": pilot["causal_interventions"]["neutralizer_count"]
        == 2,
        "three_seeds": pilot["generation"]["seed_count"] == 3,
        "human_minimality_audit": pilot["human_audit"]
        ["required_for_every_strict_subset_needed_for_minimality"]
        is True,
        "go_requires_nontrivial_topology": pilot["decision_gate"]["go"]
        ["instances_with_nonsingleton_or_multiple_minimal_sets_min"]
        >= 2,
        "wavelet_excluded": "WAVELET" in pilot["excluded_now"],
        "heldout_sealed": pilot["sealed_boundaries"]["heldout_opened"] is False,
    }
    passed = all(checks.values())
    return {
        "schema_version": "scope-and-micro-pilot-validation-v1",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "next_authorized_operation": pilot["next_authorized_operation"]
        if passed
        else "REPAIR_SCOPE_OR_MICRO_PILOT_CONTRACT",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.scope, args.pilot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
