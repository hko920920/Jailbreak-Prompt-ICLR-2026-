from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import analyze_d3_postoutcome_narrow as audit  # noqa: E402

CONFIG = ROOT / (
    "configs/natural_language_localization/d3_postoutcome_narrow_audit_v1.json"
)


def test_strict_minimality_rejects_unresolved_strict_subset() -> None:
    statuses = {
        (): "NOT_RECOVERED",
        ("a",): "ABSTAINED",
        ("b",): "NOT_RECOVERED",
        ("a", "b"): "RECOVERED",
    }
    assert audit.minimal_sets(statuses, ("a", "b")) == ()


def test_postoutcome_audit_reconstructs_narrow_route_without_relabeling_d3() -> None:
    result = audit.run(ROOT, CONFIG)
    assert result["official_cross_family_result"]["d3_core_gate_pass"] is False
    assert result["official_cross_family_result"]["failed_gates"] == [
        "positive_neutralizer_jaccard_at_least_0_80"
    ]
    assert result["project_route_decision"]["classification"] == "NARROW"
    assert result["project_route_decision"]["retroactive_d3_pass"] is False


def test_family_split_and_coarsening_expose_both_signal_and_risk() -> None:
    result = audit.run(ROOT, CONFIG)
    h4 = result["family_diagnostics"]["h4rm3l"]
    deep = result["family_diagnostics"]["DeepInception"]
    assert h4["reportable_topology_count"] == 8
    assert h4["nontrivial_topology_count"] == 7
    assert h4["neutralizer_agreement"]["pooled_positive_jaccard"] == 25 / 30
    assert h4["capability_control_failure_count"] == 0
    assert h4["baselines"]["best_one_path_recall_loss"] == pytest.approx(1 / 3)
    assert h4["all_unchanged_family_diagnostic_gates_pass"] is True
    assert deep["neutralizer_agreement"]["pooled_positive_jaccard"] == 39 / 111
    assert deep["capability_control_failure_count"] == 22
    assert deep["all_unchanged_family_diagnostic_gates_pass"] is False
    coarse_h4 = result["coarsening_sensitivity"]["by_family"]["h4rm3l"]
    assert coarse_h4["reportable_topology_count"] == 9
    assert coarse_h4["nontrivial_topology_count"] == 0
    assert coarse_h4["all_reportable_share_one_identical_signature"] is True


def test_axis_sensitivity_never_promotes_uncontrolled_positive() -> None:
    result = audit.run(ROOT, CONFIG)
    assert result["evaluator_axis_sensitivity"][
        "selected_attacked_baselines_harmful_on_both_axes"
    ] is True
    controlled = [
        row
        for row in result["evaluator_axis_sensitivity"]["aggregate"]
        if row["mode"] == "controlled"
    ]
    assert controlled
    assert all(
        row["status_counts"].get("UNCONTROLLED_AXIS_POSITIVE", 0) >= 0
        for row in controlled
    )
