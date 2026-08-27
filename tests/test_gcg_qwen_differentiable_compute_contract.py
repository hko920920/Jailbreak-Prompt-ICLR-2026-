from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/freeze_gcg_qwen_differentiable_compute_contract.py"
SPEC = importlib.util.spec_from_file_location("freeze_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _git(path: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")

    predecessor_path = root / (
        "data/natural_language_localization/topology_micro_pilot_v1/"
        "h4rm3l_gcg_signal_screen_runtime_bundle_v1.safe.json"
    )
    predecessor_path.parent.mkdir(parents=True)
    predecessor = {
        "status": "H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_FREEZE_PASS_EXECUTION_BLOCKED",
        "operational_pass": True,
        "execution_ready": False,
        "next_authorized_operation": "FREEZE_GCG_QWEN_DIFFERENTIABLE_RUNTIME_AND_COMPUTE_CONTRACT",
        "differentiable_model": {
            "repository": "Qwen/Qwen2.5-7B-Instruct",
            "revision": "a09a35458c702b33eeacc393d103063234e8bc28",
            "total_weight_bytes": 15231271888,
            "weights_downloaded": False,
        },
        "model_inference_performed": False,
        "attack_optimization_performed": False,
        "optimizer_target_manifest": [{}, {}, {}, {}],
    }
    predecessor_path.write_text(json.dumps(predecessor), encoding="utf-8")

    workflow_path = root / ".github/workflows/gcg_qwen_self_hosted_attestation.yml"
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text("name: test\non: workflow_dispatch\n", encoding="utf-8")

    config = json.loads(
        (
            ROOT / "configs/natural_language_localization/"
            "gcg_qwen_differentiable_compute_contract_v1.json"
        ).read_text(encoding="utf-8")
    )
    config["predecessor"]["git_blob_sha"] = _git(root, "hash-object", str(predecessor_path))
    config["attestation_workflow"]["git_blob_sha"] = _git(root, "hash-object", str(workflow_path))
    config_path = root / (
        "configs/natural_language_localization/gcg_qwen_differentiable_compute_contract_v1.json"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return root, config_path


def test_freeze_passes_with_exact_contract(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)
    result = MODULE.freeze(root, config_path)
    assert result["operational_pass"] is True
    assert result["execution_ready"] is False
    assert result["runner_attestation_observed"] is False
    assert result["next_authorized_operation"] == (
        "REGISTER_AND_ATTEST_GCG_QWEN_SELF_HOSTED_RUNNER"
    )
    assert result["model_weight_downloaded"] is False
    assert result["attack_optimization_performed"] is False


def test_predecessor_drift_fails(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)
    predecessor = root / (
        "data/natural_language_localization/topology_micro_pilot_v1/"
        "h4rm3l_gcg_signal_screen_runtime_bundle_v1.safe.json"
    )
    predecessor.write_text("{}", encoding="utf-8")
    with pytest.raises(MODULE.ContractError, match="PREDECESSOR_BLOB_MISMATCH"):
        MODULE.freeze(root, config_path)


def test_attestation_workflow_drift_fails(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)
    workflow = root / ".github/workflows/gcg_qwen_self_hosted_attestation.yml"
    workflow.write_text("name: changed\n", encoding="utf-8")
    with pytest.raises(MODULE.ContractError, match="ATTESTATION_WORKFLOW_BLOB_MISMATCH"):
        MODULE.freeze(root, config_path)


def test_search_width_cannot_be_reduced(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["optimizer_compute_contract"]["search_width"] = 256
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(MODULE.ContractError, match="GCG_SEARCH_WIDTH_MISMATCH"):
        MODULE.freeze(root, config_path)
