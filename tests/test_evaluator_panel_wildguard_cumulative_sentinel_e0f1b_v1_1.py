from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jbspan.evaluator_panel_redesign import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_evaluator_panel_wildguard_cumulative_sentinel_e0f1b_v1_1 as repaired  # noqa: E402

CONTRACT_PATH = (
    ROOT / "configs/evaluator_panel/calibration_redesign_e0f1b_cumulative_sentinel_v1_1.json"
)


def _assert_identity(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    identity = value.pop("result_identity_sha256")
    assert hashlib.sha256(canonical_json_bytes(value)).hexdigest() == identity
    value["result_identity_sha256"] = identity
    return value


def _prepared_postrun_design() -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[repaired.base.ScientificPlanRecord],
    dict[str, object],
    Path,
]:
    contract, predecessor_contract, base_contract, interruption = repaired.validate_contract(
        ROOT, CONTRACT_PATH
    )
    dependencies = repaired.base.object_value(contract["dependencies"], where="dependencies")
    predecessor_contract_path = repaired._dependency_path(
        ROOT, dependencies, "predecessor_contract"
    )
    (
        _,
        prepared_base_contract,
        adopted_rows,
        plan,
        _,
        _,
        _,
        _,
    ) = repaired.predecessor.prepare_design(ROOT, predecessor_contract_path)
    assert repaired.base.canonical_sha256(base_contract) == repaired.base.canonical_sha256(
        prepared_base_contract
    )
    return (
        contract,
        predecessor_contract,
        adopted_rows,
        plan,
        interruption,
        predecessor_contract_path,
    )


def test_e0f1b_v1_1_preflight_and_interruption_identities() -> None:
    preflight = _assert_identity(
        ROOT / "data/evaluator_panel_v2/e0f1b_v1_1_minimal_cache_preflight.safe.json"
    )
    interruption = _assert_identity(
        ROOT / "data/evaluator_panel_v2/e0f1b_v1_raw_private_cache_defender_interruption.safe.json"
    )
    assert preflight["new_model_inference_performed"] is False
    assert preflight["automatic_execution_started"] is False
    assert preflight["migrated_predecessor_record_candidates"] == 5
    assert preflight["new_completion_call_ceiling"] == 67
    assert interruption["completed_model_responses_before_abort"] == 6
    assert interruption["completed_private_records_preserved"] == 5
    assert interruption["quarantined_private_record_restored"] is False
    assert interruption["windows_defender_exclusion_added"] is False


def test_e0f1b_v1_1_design_and_salvage_mapping_are_exact() -> None:
    (
        contract,
        predecessor_contract,
        adopted_rows,
        plan,
        interruption,
        predecessor_contract_path,
    ) = _prepared_postrun_design()
    assert len(adopted_rows) == 72
    assert len(plan) == 72

    predecessor_contract_sha = repaired.base.file_sha256(predecessor_contract_path)
    plan_by_predecessor_identity = {
        repaired._predecessor_execution_identity(
            plan_record, predecessor_contract, predecessor_contract_sha
        ): plan_record
        for plan_record in plan
    }
    salvage_specs = repaired.base.object_rows(
        interruption["remaining_private_records"], where="remaining private records"
    )
    assert len(salvage_specs) == 5
    assert all(
        str(spec["execution_identity_sha256"]) in plan_by_predecessor_identity
        for spec in salvage_specs
    )

    outputs = repaired.base.object_value(contract["outputs"], where="outputs")
    minimal_dir = (
        repaired.base.rooted(ROOT, outputs["private_artifact_root"]) / "private_records"
    )
    minimal_files = sorted(minimal_dir.glob("*.json"))
    assert len(minimal_files) == 72
    assert sum(path.stat().st_size for path in minimal_files) == 202_671

    implementation = repaired.base.object_value(contract["implementation"], where="implementation")
    inference = repaired.base.object_value(contract["inference"], where="inference")
    runtime = repaired.base.object_value(contract["runtime"], where="runtime")
    model_sha = str(repaired.base.object_value(runtime["model"], where="model")["sha256"])
    contract_sha = repaired.base.file_sha256(CONTRACT_PATH)
    migrated_record_ids: set[str] = set()
    for spec in salvage_specs:
        predecessor_identity = str(spec["execution_identity_sha256"])
        plan_record = plan_by_predecessor_identity[predecessor_identity]
        _, minimal_identity = repaired._minimal_execution_identity(
            plan=plan_record,
            contract_sha256=contract_sha,
            implementation=implementation,
            model_sha256=model_sha,
            inference=inference,
        )
        payload = repaired.base.load_object(minimal_dir / f"{minimal_identity}.json")
        provenance = repaired.base.object_value(payload["provenance"], where="provenance")
        assert provenance["kind"] == "MIGRATED_COMPLETE_PREDECESSOR_RESPONSE"
        assert provenance["predecessor_execution_identity_sha256"] == predecessor_identity
        assert provenance["predecessor_private_record_sha256"] == spec["sha256"]
        assert provenance["model_completion_performed_in_v1_1"] is False
        migrated_record_ids.add(str(plan_record.safe["record_id"]))
    assert len(migrated_record_ids) == 5

    predecessor_outputs = repaired.base.object_value(
        predecessor_contract["outputs"], where="predecessor outputs"
    )
    old_private_dir = (
        repaired.base.rooted(ROOT, predecessor_outputs["private_artifact_root"])
        / "private_records"
    )
    assert list(old_private_dir.glob("*.json")) == []
    assert contract["scientific_design_adoption"]["selection_changed"] is False
    assert contract["scientific_design_adoption"]["candidate_family_changed"] is False
    assert contract["scientific_design_adoption"]["futility_gates_changed"] is False


def test_minimal_private_payload_contains_no_raw_fields() -> None:
    contract, _, _, plan, _, _ = _prepared_postrun_design()
    implementation = repaired.base.object_value(contract["implementation"], where="implementation")
    inference = repaired.base.object_value(contract["inference"], where="inference")
    record = plan[0]
    identity, identity_sha = repaired._minimal_execution_identity(
        plan=record,
        contract_sha256="a" * 64,
        implementation=implementation,
        model_sha256="b" * 64,
        inference=inference,
    )
    payload = repaired._minimal_payload(
        identity=identity,
        identity_sha256=identity_sha,
        plan=record,
        prompt_tokens=100,
        context_budget_pass=True,
        request_completed=True,
        classifier_output=("Prompt harmful: yes\nResponse refusal: no\nResponse harmful: yes"),
        stop_type="eos",
        tokens_predicted=20,
        truncated=False,
        timings={},
        elapsed_seconds=1.0,
        provenance={"kind": "TEST"},
        inference=inference,
    )
    assert payload["schema_version"] == repaired.PRIVATE_SCHEMA
    encoded = json.dumps(payload, sort_keys=True)
    for key in repaired.FORBIDDEN_PRIVATE_KEYS:
        assert f'"{key}"' not in encoded
    assert "Prompt harmful" not in encoded


def test_e0f1b_v1_1_terminal_artifacts_are_complete_after_authorized_run() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    outputs = contract["outputs"]
    terminal = [
        ROOT / outputs[name]
        for name in (
            "addition_axis_path",
            "cumulative_axis_path",
            "execution_path",
            "result_path",
        )
    ]
    assert all(path.is_file() for path in terminal)
    assert contract["automatic_execution_after_preflight"] is False
    preflight = _assert_identity(ROOT / outputs["preflight_path"])
    assert preflight["explicit_post_preflight_authorization_required"] is True
    execution = _assert_identity(ROOT / outputs["execution_path"])
    assert execution["status"] == "E0F1B_V1_1_72_ADDITION_AND_144_CUMULATIVE_EXECUTION_COMPLETE"
    assert execution["new_completion_calls_this_invocation"] == 67
    assert execution["migrated_complete_predecessor_records"] == 5
    assert execution["cumulative_integrity"]["pass"] is True


def test_completed_e0f1b_v1_1_result_identity_and_seals_when_present() -> None:
    path = ROOT / "data/evaluator_panel_v2/e0f1b_v1_1_cumulative_result.safe.json"
    assert path.is_file()
    result = _assert_identity(path)
    assert result["result_identity_sha256"] == (
        "f6895b20f344897c0dc4739dc7cc94b733d8a2ae135adc337e2d83425031e643"
    )
    assert result["status"] == "E0F1B_CUMULATIVE_PASS_AUTHORIZE_E0F2_300_DESIGN_REVIEW"
    assert result["candidate_evaluation"]["passing_candidate_ids"] == [
        "B5_wildguard_or_full_ga_precision_anchor"
    ]
    assert result["storage_repair"]["raw_fields_stored_in_v1_1_private_cache"] is False
    assert result["storage_repair"]["defender_exclusion_added"] is False
    assert result["cumulative_scientific_records"] == 144
    assert result["integrity"]["eligible_measurements"] == 144
    assert result["integrity"]["pass"] is True
    assert result["scientific_decision"]["automatic_e0f2_300_execution_started"] is False
    assert result["heldout_opened"] is False
    assert result["p3_opened"] is False
    assert result["topology_opened"] is False
    assert result["panel_qualified"] is False
