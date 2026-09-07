"""Harmless guard/lifecycle tests; no local server or private C1N input is opened."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "local_development_wrapper", ROOT / "scripts/run_rescue_local_development_v2.py"
)
assert SPEC is not None and SPEC.loader is not None
WRAPPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WRAPPER)


@pytest.mark.parametrize(
    "config_path, config_hash",
    [
        (WRAPPER.REFERENCE_SMOKE_CONFIG, WRAPPER.REFERENCE_SMOKE_SHA256),
        (
            "configs/natural_language_localization/rescue_local_guidedeval_smoke_phi_v3.json",
            "383ea86dd66e30059bb24c818a8da21df47488e98f0ce1946247e281439946ce",
        ),
    ],
)
def test_real_failed_smoke_stops_before_runtime_bundle_or_process_access(
    monkeypatch, config_path, config_hash
):
    verifier = Mock()
    plan = Mock()
    server = Mock()
    monkeypatch.setattr(WRAPPER, "verify_runtime_after_pass", verifier)
    monkeypatch.setattr(WRAPPER.runtime, "verify_project", plan)
    monkeypatch.setattr(WRAPPER, "owned_server", server)
    with pytest.raises(WRAPPER.QualificationFailure):
        WRAPPER.execute(ROOT, config_path, config_hash)
    verifier.assert_not_called()
    plan.assert_not_called()
    server.assert_not_called()


def synthetic_pass(tmp_path):
    reference = ROOT / WRAPPER.REFERENCE_SMOKE_CONFIG
    copied = tmp_path / WRAPPER.REFERENCE_SMOKE_CONFIG
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_bytes(reference.read_bytes())
    config = copy.deepcopy(json.loads(reference.read_text(encoding="utf-8")))
    config["recording"]["safe_result"] = (
        "data/natural_language_localization/fixture/result.safe.json"
    )
    selected = tmp_path / "configs/synthetic-smoke.json"
    selected.write_bytes(WRAPPER.runtime.encode(config))
    selected_hash = WRAPPER.runtime.file_digest(selected)
    result = {
        "schema_version": WRAPPER.SMOKE_SCHEMA,
        "status": "LOCAL_GUIDEDEVAL_HARMLESS_SMOKE_PASS",
        "contract_sha256": selected_hash,
        "gate": {
            "pass": True,
            "expected_cases": 12,
            "completed_cases": 12,
            "parsed_cases": 12,
            "exact_vector_cases": 12,
        },
        "operation_error_type": None,
        "owned_server_stopped": True,
        "rows": [
            {
                "fixture_id": fixture["id"],
                "expected_matches": fixture["expected_matches"],
                "observed_matches": list(fixture["expected_matches"]),
                "parsed": True,
                "exact_vector": True,
                "error_code": None,
            }
            for fixture in config["fixtures"]
        ],
    }
    path = tmp_path / config["recording"]["safe_result"]
    path.parent.mkdir(parents=True, exist_ok=True)
    return selected.relative_to(tmp_path).as_posix(), selected_hash, result, path


def write_result(path, result):
    result.pop("result_identity_sha256", None)
    result["result_identity_sha256"] = WRAPPER.runtime.digest(result)
    path.write_bytes(WRAPPER.runtime.encode(result))


def test_exact_synthetic_pass_accepts_without_model_or_private_reads(tmp_path):
    selected, selected_hash, result, path = synthetic_pass(tmp_path)
    write_result(path, result)
    _, accepted = WRAPPER.verify_smoke_evidence(tmp_path, selected, selected_hash)
    assert accepted["gate"]["pass"]


def test_vector_mismatch_cannot_be_hidden_by_pass_flags(tmp_path):
    selected, selected_hash, result, path = synthetic_pass(tmp_path)
    result["rows"][0]["observed_matches"][0] = not result["rows"][0]["observed_matches"][0]
    write_result(path, result)
    with pytest.raises(WRAPPER.QualificationFailure, match="contradicts"):
        WRAPPER.verify_smoke_evidence(tmp_path, selected, selected_hash)


def test_owned_server_stopped_when_readiness_raises(monkeypatch):
    process = Mock(pid=1234)
    process.poll.side_effect = [None, 0]
    monkeypatch.setattr(WRAPPER, "require_free_port", Mock())
    popen = Mock(return_value=process)
    monkeypatch.setattr(WRAPPER.subprocess, "Popen", popen)
    monkeypatch.setattr(WRAPPER, "await_ready", Mock(side_effect=RuntimeError("fixture startup")))
    with pytest.raises(RuntimeError, match="fixture startup"):
        with WRAPPER.owned_server(["fixture-server.exe"], 18879, "fixture", 1):
            pytest.fail("unready process must not be yielded")
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)
    process.kill.assert_not_called()
    assert popen.call_args.kwargs["stdout"] is subprocess.DEVNULL


def test_kill_escalation_targets_only_owned_process():
    process = Mock(pid=4321)
    process.poll.side_effect = [None, -9]
    process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 10), 0]
    WRAPPER.stop_owned(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
