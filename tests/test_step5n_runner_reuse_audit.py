from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import audit_step5n_runner_reuse as audit  # noqa: E402

CONFIG_PATH = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "step5n_runner_reuse_audit_v1.json"
)


def load_config() -> dict[str, object]:
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_static_source_audits_bind_hashes_functions_and_fragments() -> None:
    config = load_config()
    sources = config["sources"]
    assert isinstance(sources, dict)
    results = {
        name: audit.audit_source(ROOT, specification)
        for name, specification in sources.items()
    }
    assert results
    assert all(result["passed"] for result in results.values())


def test_boundary_requires_new_target_scoped_layers_and_no_authority() -> None:
    checks = audit.validate_contract_boundary(load_config())
    assert checks
    assert all(checks.values())


def test_cross_target_response_sharing_tamper_is_detected() -> None:
    config = copy.deepcopy(load_config())
    invariants = config["required_invariants"]
    assert isinstance(invariants, dict)
    invariants["direct_response_shared_across_target_models"] = True
    checks = audit.validate_contract_boundary(config)
    assert checks["cross_target_response_sharing_forbidden"] is False


def test_full_static_audit_requires_new_runners_and_opens_no_output() -> None:
    output_path = (
        ROOT
        / "data"
        / "natural_language_localization"
        / "step5n_runner_reuse_audit_v1"
        / "runner_reuse_audit.safe.json"
    )
    before = output_path.read_bytes()
    result = audit.run(ROOT, CONFIG_PATH)
    assert output_path.read_bytes() == before
    assert result["status"] == "STEP5N_RUNNER_REUSE_STATIC_AUDIT_PASS"
    assert result["conclusion"] == "CORE_REUSE_PASS_NEW_TARGET_SCOPED_RUNNERS_REQUIRED"
    assert result["audit_pass"] is True
    assert result["model_download_performed"] is False
    assert result["target_or_evaluator_inference_performed"] is False
    assert result["confirmatory_output_opened"] is False
    assert result["frozen_d3_file_modified"] is False
    assert result["raw_prompt_payload_or_response_recorded"] is False
    assert result["paper_validity"] is False
