"""Synthetic-only tests of disclosed execution amendment and unchanged states."""

import copy
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_llama_development_continued_aggregate_v1 as m  # noqa: E402
from test_pa_llama_development_aggregate_v1 import frame as frame  # noqa: E402

c = m.c


def synthetic_inputs(config, plan, amendment, *, failed_positions=()):
    generations, qwen, jailmeter = [], [], []
    for item in plan["rows"]:
        harmful = (
            item["condition"] == "ATTACKED_H4RM3L"
            and item["payload_position"] not in failed_positions
        )
        generations.append(
            {
                "request_id": item["request_id"],
                "eligible_for_panel": True,
                "ineligible_reason": None,
                "response_sha256": "e" * 64,
            }
        )
        qwen.append(
            {
                "request_id": item["request_id"],
                "safety": "Unsafe" if harmful else "Safe",
                "refusal": "No" if harmful else "Yes",
                "output_limit_stop": False,
                "dispatched": True,
            }
        )
        jailmeter.append(
            {
                "request_id": item["request_id"],
                "label": int(harmful),
                "output_limit_stop": False,
                "dispatched": True,
            }
        )
    axes = {}
    for axis, rows in (("qwen", qwen), ("jailmeter", jailmeter)):
        axes[axis] = {
            "contract_sha256": config["_contract_sha256"],
            "phase_seed": plan["phase_seed"],
            "axis": axis,
            "complete": True,
            "rows": rows,
            "rows_identity_sha256": c.digest(rows),
        }
    axes["jailmeter"].update(
        {
            "schema_version": m.CONTINUED_SCHEMA,
            "execution_amendment_sha256": amendment["_amendment_sha256"],
            "raw_receipts_reverified": True,
            "composite_lifecycle_verified": True,
            "resource_stop_preserved": True,
            "all_original_completed_reused": True,
        }
    )
    return generations, axes, SimpleNamespace(panel_decision=m.original.independent_panel)


@pytest.fixture
def setup(request):
    config, inventory = request.getfixturevalue("frame")
    plan = c.phase_plan(config, inventory, 11)
    amendment = {
        "_amendment_sha256": "c" * 64,
        "original_seed11_prefix": {
            "dispatched_request_ids": [row["request_id"] for row in plan["rows"][:30]]
        },
    }
    return config, inventory, plan, amendment


def assemble(setup, *, failed_positions=()):
    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(
        config, plan, amendment, failed_positions=failed_positions
    )
    return m.build_artifacts(config, amendment, inventory, plan, generations, axes, helpers)


def test_primary_states_unchanged_and_operational_failure_disclosed(setup):
    measurement, result, proof = assemble(setup)
    assert result["advance_positions"] == list(range(45))
    assert result["status_counts"]["ADVANCE"] == 45
    for artifact in (measurement, result, proof):
        assert artifact["original_seed11_jailmeter_operational_gate_passed"] is False
        assert artifact["verification_scope"] == m.SCOPE
        assert artifact["operational_amendment_sha256s"] == ["c" * 64]
        assert artifact["scientific_rules_unchanged"] is True
    assert proof["verification_passed"] is True and result["paper_validity"] is False
    m.validate_previous(setup[0], setup[3], result, proof)


def test_conservative_diagnostic_does_not_replace_primary(setup):
    measurement, result, _ = assemble(setup)
    sensitivity = measurement["failed_epoch_sensitivity"]
    assert sensitivity["hypothetical_all_original30_unknown"]["advance_positions"] == list(
        range(15, 45)
    )
    assert sensitivity["hypothetical_all_original30_unknown"]["status_counts"]["UNRESOLVED"] == 15
    assert result["advance_positions"] == list(range(45))
    assert sensitivity["hypothetical_labels_are_not_observations"] is True
    assert sensitivity["diagnostic_only_not_primary_population_selection"] is True


def test_three_seed_full_frame_and_dependent_stable_diagnostic(setup):
    config, inventory, _, amendment = setup
    measurement, result, proof = assemble(setup)
    for seed in (23, 47):
        plan = c.phase_plan(config, inventory, seed, result)
        generations, axes, helpers = synthetic_inputs(config, plan, amendment)
        measurement, result, proof = m.build_artifacts(
            config, amendment, inventory, plan, generations, axes, helpers, result, proof
        )
    assert result["stable_positions"] == list(range(45))
    assert all(len(row["seed_observations"]) == 3 for row in result["pair_states"])
    assert measurement["failed_epoch_sensitivity"][
        "stable_positions_not_depending_on_original_failed_epoch"
    ] == list(range(15, 45))
    assert "hypothetical_all_original30_unknown" not in measurement["failed_epoch_sensitivity"]


@pytest.mark.parametrize("survivors", [0, 5, 6, 7, 44, 45])
def test_same_exact_futility_boundary(setup, survivors):
    _, result, _ = assemble(setup, failed_positions=range(survivors, 45))
    assert len(result["advance_positions"]) == survivors
    assert result["next_seed"] == (23 if survivors >= 6 else None)


@pytest.mark.parametrize(
    "key",
    [
        "raw_receipts_reverified",
        "composite_lifecycle_verified",
        "resource_stop_preserved",
        "all_original_completed_reused",
        "complete",
    ],
)
def test_composite_requires_each_provenance_check(setup, key):
    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(config, plan, amendment)
    axes["jailmeter"][key] = False
    with pytest.raises(c.DevelopmentError, match="COMPOSITE_AXIS_AUTHORITY"):
        m.build_artifacts(config, amendment, inventory, plan, generations, axes, helpers)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "jbspan-pa-llama-development-axis-v1"),
        ("execution_amendment_sha256", "d" * 64),
        ("contract_sha256", "f" * 64),
        ("phase_seed", 23),
        ("axis", "qwen"),
    ],
)
def test_parent_axis_or_wrong_authority_not_accepted(setup, key, value):
    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(config, plan, amendment)
    axes["jailmeter"][key] = value
    with pytest.raises(c.DevelopmentError, match="COMPOSITE_AXIS_AUTHORITY"):
        m.build_artifacts(config, amendment, inventory, plan, generations, axes, helpers)


@pytest.mark.parametrize(
    "key,value",
    [
        ("operational_amendment_sha256s", []),
        ("original_seed11_jailmeter_operational_gate_passed", True),
        ("verification_scope", "ORIGINAL_CLEAN_PASS"),
        ("scientific_rules_unchanged", False),
    ],
)
def test_rehashed_prior_cannot_hide_amendment(setup, key, value):
    _, result, proof = assemble(setup)
    result[key] = value
    result["result_identity_sha256"] = c.digest(
        {k: v for k, v in result.items() if k != "result_identity_sha256"}
    )
    proof[key] = value
    proof["phase_result_identity_sha256"] = result["result_identity_sha256"]
    proof["verification_identity_sha256"] = c.digest(
        {k: v for k, v in proof.items() if k != "verification_identity_sha256"}
    )
    with pytest.raises(c.DevelopmentError, match="AMENDED_PRIOR_DISCLOSURE_REQUIRED"):
        m.validate_previous(setup[0], setup[3], result, proof)


def test_forged_proof_hash_rejected(setup):
    _, result, proof = assemble(setup)
    proof["verification_identity_sha256"] = "0" * 64
    with pytest.raises(c.DevelopmentError, match="AMENDED_PRIOR_PROOF_HASH"):
        m.validate_previous(setup[0], setup[3], result, proof)


def test_out_of_frame_join_rejected(setup):
    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(config, plan, amendment)
    axes["jailmeter"]["rows"][-1]["request_id"] = "f" * 64
    axes["jailmeter"]["rows_identity_sha256"] = c.digest(axes["jailmeter"]["rows"])
    with pytest.raises(c.DevelopmentError, match="EXACT_THREE_WAY_JOIN"):
        m.build_artifacts(config, amendment, inventory, plan, generations, axes, helpers)


def test_inputs_are_not_mutated_and_replay_is_deterministic(setup):
    saved = copy.deepcopy(setup)
    assert assemble(setup) == assemble(setup)
    assert setup == saved


def test_first_phase_cannot_smuggle_previous(setup):
    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(config, plan, amendment)
    with pytest.raises(c.DevelopmentError, match="FIRST_PHASE_HAS_PRIOR"):
        m.build_artifacts(config, amendment, inventory, plan, generations, axes, helpers, {})


def test_prefix_size_change_rejected(setup):
    setup[3]["original_seed11_prefix"]["dispatched_request_ids"].pop()
    with pytest.raises(c.DevelopmentError, match="PREFIX_EXACT30_REQUIRED"):
        assemble(setup)


@pytest.mark.parametrize("mutation", ["duplicate_extra", "foreign"])
def test_prefix_cannot_duplicate_or_leave_seed11_frame(setup, mutation):
    values = setup[3]["original_seed11_prefix"]["dispatched_request_ids"]
    if mutation == "duplicate_extra":
        values.append(values[0])
    else:
        values[0] = "0" * 64
    with pytest.raises(c.DevelopmentError, match="PREFIX_"):
        assemble(setup)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "wrong"),
        ("finalizer_source_path", "scripts/wrong.py"),
        ("pair_states_checked", 44),
        ("phase_decisions_checked", 88),
        ("historical_private_reads", 1),
        ("sealed_reads", 1),
        ("verified_axis_identities", {"qwen": "a" * 64}),
        ("target_rows_sha256", "invalid"),
        ("measurement_rows_sha256", None),
        ("extra_unrecognized_field", "synthetic text"),
    ],
)
def test_coherently_rehashed_wrong_prior_proof_rejected(setup, key, value):
    _, result, proof = assemble(setup)
    proof[key] = value
    proof["verification_identity_sha256"] = c.digest(
        {k: v for k, v in proof.items() if k != "verification_identity_sha256"}
    )
    with pytest.raises(c.DevelopmentError, match="AMENDED_PRIOR_"):
        m.validate_previous(setup[0], setup[3], result, proof)


def test_aggregate_proof_written_last_and_completed_replay_does_not_rewrite(
    setup, tmp_path, monkeypatch
):
    import pa_llama_development_jailmeter_continuation_v1 as continued

    config, inventory, plan, amendment = setup
    generations, axes, helpers = synthetic_inputs(config, plan, amendment)
    base = c.paths(tmp_path, config["_contract_sha256"])
    c.write_once(base["safe"] / "phase_11_plan.safe.json", plan)
    monkeypatch.setattr(c, "source_inventory", lambda *args: inventory)
    monkeypatch.setattr(m.target, "helper_for", lambda *args: object())
    monkeypatch.setattr(m.target, "operation_lock", lambda *args: nullcontext())
    monkeypatch.setattr(m.panel, "verify_axis", lambda *args: axes["qwen"])
    monkeypatch.setattr(continued, "verify", lambda *args: axes["jailmeter"])
    monkeypatch.setattr(m.target, "load_inputs", lambda *args: [])
    monkeypatch.setattr(m.target, "load_census", lambda *args: [])
    monkeypatch.setattr(m.target, "reconcile_phase", lambda *args: generations)
    monkeypatch.setattr(m.panel, "load_pure_functions", lambda *args: helpers)
    original_write = m.original.write_or_verify
    writes = []

    def observed_write(path, value):
        writes.append(path.name)
        return original_write(path, value)

    monkeypatch.setattr(m.original, "write_or_verify", observed_write)
    first = m.aggregate(tmp_path, config, amendment, 11)
    assert writes == [
        "phase_11_measurements.safe.json",
        "phase_11_result.safe.json",
        "phase_11_verification.safe.json",
    ]
    paths = [base["safe"] / name for name in writes]
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
    assert m.aggregate(tmp_path, config, amendment, 11) == first
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths] == before
    axes["qwen"]["rows"][0]["safety"] = "Unsafe"
    axes["qwen"]["rows"][0]["refusal"] = "No"
    axes["qwen"]["rows_identity_sha256"] = c.digest(axes["qwen"]["rows"])
    with pytest.raises(c.DevelopmentError, match="EXISTING_AGGREGATE_CHANGED"):
        m.aggregate(tmp_path, config, amendment, 11)
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths] == before
