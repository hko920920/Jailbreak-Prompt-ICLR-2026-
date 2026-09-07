from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import analyze_d3_resolution_rescue as audit  # noqa: E402

CONFIG = ROOT / (
    "configs/natural_language_localization/d3_resolution_rescue_audit_v1.json"
)
RESULT = ROOT / (
    "data/natural_language_localization/d3_exact_topology_v1/"
    "postoutcome_resolution_rescue_audit.safe.json"
)


def test_resolution_rescue_reconstructs_fine_d3_without_new_inference() -> None:
    result = audit.run(ROOT, CONFIG)
    assert result["overall"]["instance_count"] == 12
    assert result["overall"]["reference_reportable_count"] == 11
    assert result["overall"]["reference_nontrivial_count"] == 10
    assert result["scope"] == {
        "official_d3_reclassified": False,
        "official_c1n_reclassified": False,
        "new_target_inference": False,
        "new_evaluator_inference": False,
        "new_human_annotation": False,
        "raw_text_read": False,
        "raw_text_written": False,
        "paper_valid_confirmatory_claim": False,
    }


def test_partition_denominators_are_complete() -> None:
    result = audit.run(ROOT, CONFIG)
    for row in result["per_instance"]:
        unit_count = int(row["unit_count"])
        assert row["atomic_truth_table_count"] == 2**unit_count
        assert row["contiguous_partition_spectrum"]["partition_count"] == 2 ** (
            unit_count - 1
        )
        expected_bell = 5 if unit_count == 3 else 877
        assert row["all_partition_spectrum"]["partition_count"] == expected_bell
        assert len(row["arbitrary_one_merge"]) == unit_count * (unit_count - 1) // 2
        assert len(row["contiguous_one_merge"]) == unit_count - 1


def test_stored_result_matches_reconstruction_byte_for_byte() -> None:
    stored = json.loads(RESULT.read_text(encoding="utf-8"))
    reconstructed = audit.run(ROOT, CONFIG)
    assert stored == reconstructed
