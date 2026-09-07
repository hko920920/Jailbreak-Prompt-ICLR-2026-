"""Invented scientific fixtures only; no real topology results opened or generated."""

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_pa_llama_topology_finalize_v1 import state as frozen_state  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_reentry_finalize_v2 as m  # noqa: E402


@pytest.fixture
def data(request, monkeypatch):
    state = request.getfixturevalue("frozen_state")
    total = len(state.targets)
    science = len(state.axes["qwen"]["rows"])
    monkeypatch.setattr(m, "TOTAL", total)
    monkeypatch.setattr(m, "REUSED", 2)
    monkeypatch.setattr(m, "SCIENCE", science)
    proof = m.j.seal(
        {
            "schema_version": "pa-reentry-target-composite-v2",
            "execution_identity": "a" * 64,
            "original_contract_sha256": state.config["_contract_sha256"],
            "bound_plan_identity_sha256": state.plan["plan_identity_sha256"],
            "target_records": total,
            "reused_target_records": 2,
            "new_target_records": total - 2,
            "target_rows_sha256": m.j.digest(state.targets),
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
            "prior_operation_failures": m.FAILURES,
            "composite_target_complete": True,
            "scientific_gate_evaluated": False,
            "paper_validity": False,
            "archive_relocation_contemporaneous_receipt_available": False,
            "missing_stop_epochs": [],
            "all_attempts": [],
            "all_attempts_sha256": m.j.digest([]),
            "latest_target_release_at": "2026-09-07T04:00:00+00:00",
        },
        "proof_identity_sha256",
    )
    axes = {}
    for axis, previous in state.axes.items():
        value = copy.deepcopy(previous)
        value.update(
            schema_version="pa-reentry-panel-axis-v2",
            execution_identity=proof["execution_identity"],
            original_contract_sha256=state.config["_contract_sha256"],
            stage=axis,
            target_composite_proof=proof,
            original_operational_gate_passed=False,
            first_continuation_operational_gate_passed=False,
            prior_operation_failures=m.FAILURES,
            scientific_rules_changed=False,
            paper_validity=False,
            epochs=[{"dispatches": science, "resource_evidence_complete": True}],
        )
        axes[axis] = m.j.seal(value, "proof_identity_sha256")
    state.proof, state.v2_axes = proof, axes
    return state


def build(state, *, run_analysis=False):
    return m.build_products(
        state.config,
        state.plan,
        state.context,
        state.targets,
        state.v2_axes,
        state.proof,
        state.helpers,
        state.control_raw,
        state.tasks,
        run_analysis=run_analysis,
    )


def test_pure_scientific_results_unchanged_and_failures_disclosed(data):
    old = m.frozen.build_artifacts(
        data.config,
        data.plan,
        data.context,
        data.targets,
        data.axes,
        data.helpers,
        data.control_raw,
        data.tasks,
        run_analysis=False,
    )
    new = build(data)
    m.validate_products(new)
    assert new["result"]["primary_status_counts"] == old["result"]["primary_status_counts"]
    assert new["result"]["control_content_passes"] == old["result"]["control_content_passes"]
    assert (
        new["result"]["truth_table_fully_identified_payloads"]
        == old["result"]["truth_table_fully_identified_payloads"]
    )
    assert new["result"]["original_unqualified_pass_claimed"] is False
    assert new["result"]["paper_validity"] is False
    assert new["verification"]["actual_raw_verification_by_entrypoint"] is False
    assert new["analysis"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_axis",
        "missing_target",
        "target_false",
        "failure_removed",
        "changed_axis_target",
        "resource_incomplete",
        "axis_skip_count",
        "missing_axis_row",
    ],
)
def test_incomplete_or_changed_proofs_block_pure_join(data, mutation):
    if mutation == "missing_axis":
        data.v2_axes.pop("jailmeter")
    elif mutation == "missing_target":
        data.targets.pop()
    elif mutation == "target_false":
        data.proof["composite_target_complete"] = False
        m.reseal(data.proof, "proof_identity_sha256")
    elif mutation == "failure_removed":
        data.proof["prior_operation_failures"] = m.FAILURES[:1]
        m.reseal(data.proof, "proof_identity_sha256")
    else:
        axis = data.v2_axes["qwen"]
        if mutation == "changed_axis_target":
            axis["target_composite_proof"] = {}
        elif mutation == "resource_incomplete":
            axis["epochs"][0]["resource_evidence_complete"] = False
        elif mutation == "axis_skip_count":
            axis["skipped"] += 1
        elif mutation == "missing_axis_row":
            axis["rows"].pop()
        m.reseal(axis, "proof_identity_sha256")
    with pytest.raises(ValueError):
        build(data)


def test_builder_cannot_publish_unverified_raw_claim(data, tmp_path):
    with pytest.raises(ValueError, match="PURE_BUILDER_NOT_RAW"):
        m.publish(tmp_path, build(data))
    assert list(tmp_path.iterdir()) == []


def test_publication_proof_last_exact_replay(data, tmp_path, monkeypatch):
    products = build(data)
    products["verification"]["actual_raw_verification_by_entrypoint"] = True
    m.reseal(products["verification"], "verification_identity_sha256")
    written = []
    actual = m.j.atomic_json

    def publish(path, value):
        written.append(path.name)
        actual(path, value)

    monkeypatch.setattr(m.j, "atomic_json", publish)
    m.publish(tmp_path, products)
    assert written[-1] == "verification.safe.json"
    m.publish(tmp_path, products)
    assert len(written) == 3
    (tmp_path / "result.safe.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="EXISTING_PRODUCT_CHANGED"):
        m.publish(tmp_path, products)


def test_orphan_verification_never_repaired(data, tmp_path):
    products = build(data)
    products["verification"]["actual_raw_verification_by_entrypoint"] = True
    m.reseal(products["verification"], "verification_identity_sha256")
    m.j.atomic_json(tmp_path / "verification.safe.json", products["verification"])
    with pytest.raises(ValueError, match="ORPHAN_PROOF"):
        m.publish(tmp_path, products)


@pytest.mark.parametrize("component", ["measurements", "result", "verification"])
def test_changed_disclosure_rejected_even_if_resealed(data, component):
    products = build(data)
    value = products[component]
    value["original_operational_gate_passed"] = True
    m.reseal(
        value,
        "verification_identity_sha256" if component == "verification" else "result_identity_sha256",
    )
    with pytest.raises(ValueError, match="DISCLOSURE"):
        m.validate_products(products)


def rebind_products(products):
    """Rebind outer hashes to test semantic joins, not just accidental hash drift."""
    result = products["result"]
    if products["analysis"] is not None:
        m.reseal(products["analysis"])
        result["analysis_identity_sha256"] = products["analysis"]["result_identity_sha256"]
    m.reseal(result)
    proof = products["verification"]
    core = {
        key: value for key, value in products.items() if key != "verification" and value is not None
    }
    proof.update(
        result_identity_sha256=result["result_identity_sha256"],
        product_identity_sha256={
            key: value["result_identity_sha256"] for key, value in core.items()
        },
        product_file_sha256={
            key: m.j.sha_bytes(m.j.canonical(value) + b"\n") for key, value in core.items()
        },
    )
    m.reseal(proof, "verification_identity_sha256")


def test_analysis_branch_and_resealed_stale_upstream_rejected(data):
    products = build(data, run_analysis=True)
    m.validate_products(products)
    assert products["analysis"] is not None
    assert products["result"]["analysis_complete"] is True
    products["analysis"]["upstream_declared_topology_aggregate_identity_sha256"] = "f" * 64
    rebind_products(products)
    with pytest.raises(ValueError, match="INNER_JOINS"):
        m.validate_products(products)


def test_resealed_stale_target_identity_rejected(data):
    products = build(data)
    products["result"]["target_rows_identity_sha256"] = "f" * 64
    rebind_products(products)
    with pytest.raises(ValueError, match="INNER_JOINS"):
        m.validate_products(products)


def test_stage6_direction_cannot_run_stage7_or_read_raw():
    now = datetime.now(timezone.utc)
    direction = m.make_direction(
        "a" * 64,
        6,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=30)).isoformat(),
        direction_ref="synthetic-stage-six-direction",
    )
    target = SimpleNamespace(
        execution_identity="a" * 64,
        assert_launch_ready=lambda: pytest.fail("must reject before raw/context checks"),
    )
    with pytest.raises(ValueError, match="WRONG_STAGE_DIRECTION"):
        m.finalize(target, {}, direction=direction, run_analysis=True)
    with pytest.raises(ValueError, match="WRONG_STAGE_DIRECTION"):
        m.validate_direction(direction, "b" * 64, run_analysis=False)


def test_finalizer_publication_reparse_descendant_rejected(data, tmp_path, monkeypatch):
    products = build(data)
    products["verification"]["actual_raw_verification_by_entrypoint"] = True
    m.reseal(products["verification"], "verification_identity_sha256")
    directory = tmp_path / "finalization" / "measurements-only"
    directory.mkdir(parents=True)
    old = Path.lstat

    def observe(path, *args, **kwargs):
        result = old(path, *args, **kwargs)
        if path.name == "measurements-only":
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=1024)
        return result

    monkeypatch.setattr(Path, "lstat", observe)
    with pytest.raises(ValueError, match="REPARSE"):
        m.publish(directory, products)
