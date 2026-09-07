"""Synthetic-only tests: no GPU, case bundle, target responses or remote calls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "empty_control_runner", ROOT / "scripts/run_rescue_empty_controls_v2.py"
)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def entry(source_id="fixture"):
    return {
        "source_id": source_id,
        "source_row_sha256": "fixturehash",
        "guideline_manifest_sha256": "fixtureguidehash",
        "guideline_count": 2,
        "payload_sha256": "fixturequestionhash",
    }


def test_unique_manifest_uses_all_cases_not_response_outcomes():
    first = entry("first")
    second = entry("second")
    assert RUNNER.unique_manifest([first, second, first, second]) == [first, second]
    changed = dict(first, guideline_count=3)
    with pytest.raises(ValueError, match="inconsistent"):
        RUNNER.unique_manifest([first, changed])


def test_running_development_cannot_launch_controls(tmp_path):
    config = {"development_completion": {"summary_path": "missing.safe.json"}}
    with pytest.raises(RuntimeError, match="must finish"):
        RUNNER.require_completed_development(tmp_path, config)


def test_completed_receipt_must_bind_exact_180_run(tmp_path):
    path = tmp_path / "summary.safe.json"
    path.write_bytes(
        RUNNER.runtime.encode(
            {
                "contract_sha256": "wrong",
                "records": 180,
                "judge_results": 180,
                "status": "DEVELOPMENT_MEASUREMENT_COMPLETE_NO_RESCUE_OR_CALIBRATION_CLAIM",
            }
        )
    )
    config = {
        "development_completion": {"summary_path": "summary.safe.json"},
        "development_contract": {"identity_sha256": "right"},
    }
    with pytest.raises(RuntimeError, match="exact 180"):
        RUNNER.require_completed_development(tmp_path, config)


def test_actual_builder_forces_empty_response_and_does_not_use_target_loader(monkeypatch):
    official = RUNNER.runtime.load_official(
        ROOT, RUNNER.runtime.read_object(ROOT / RUNNER.runtime.CONFIG)
    )
    case = {
        "id": "fixture",
        "index": 0,
        "benchmark_version": "fixture",
        "subset": "core",
        "topic": "fruit",
        "target": "fixture",
        "question": "Name a yellow fruit.",
        "guidelines": [
            {
                "id": "entity-1",
                "type": "entity",
                "description": "Banana named",
                "examples": "banana",
            }
        ],
    }
    forbidden = Mock(side_effect=AssertionError("target response access forbidden"))
    monkeypatch.setattr(RUNNER.runtime, "load_existing_response", forbidden)
    judge = {
        "requested_model": "fixture",
        "temperature": 0,
        "max_tokens": 2048,
        "max_request_utf8_bytes": 100000,
    }
    requests = RUNNER.build_requests(official, {"fixture": case}, [entry()], judge)
    assert len(requests) == 1
    prompt = requests[0][2]["messages"][1]["content"]
    assert "[RESPONSE]\n\n[/RESPONSE]" in prompt
    forbidden.assert_not_called()


def result(points, *, error=None):
    return {
        "identity": {"source_id": "fixture"},
        "error_code": error,
        "outcome": "ABSTAIN"
        if error
        else "GUIDELINE_MATCH_PRESENT"
        if any(points)
        else "ZERO_GUIDELINE_MATCH",
        "points": [
            {"guideline_id": f"entity-{index}", "guideline_type": "entity", "matched": matched}
            for index, matched in enumerate(points, 1)
        ],
    }


@pytest.mark.parametrize(
    "points,error,expected_pass,false_positive,unknown",
    [
        ([False, False], None, True, 0, 0),
        ([True, False], None, False, 1, 0),
        ([], "POINT_VECTOR_PARSE_FAILURE", False, 0, 2),
    ],
)
def test_false_positive_and_missing_points_cannot_count_as_zero(
    points, error, expected_pass, false_positive, unknown
):
    summary = RUNNER.summarize("fixturecontract", [entry()], [result(points, error=error)], 2)
    assert summary["gate"]["pass"] is expected_pass
    assert summary["false_positive_cases"] == false_positive
    assert summary["unknown_points"] == unknown
    RUNNER.runtime.content_free(summary)


def test_summary_rejects_missing_or_duplicate_cases():
    with pytest.raises(ValueError, match="complete unique"):
        RUNNER.summarize("fixturecontract", [entry()], [], 2)
    with pytest.raises(ValueError, match="complete unique"):
        RUNNER.summarize("fixturecontract", [entry()], [result([False, False])] * 2, 2)
