"""Independent producer/consumer integration on invented full-1470 SAFE rows.

Actual CompositeTarget proof production and continued-evaluation acceptance run.
Raw replay, process ownership and source-pin I/O are explicit fakes: this suite
tests interface/identity composition, NOT raw certification or scientific fits.
No real experiment artifacts, models, GPU, sockets or subprocesses are accessed.
"""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pa_llama_topology_continued_evaluation_v1 as e  # noqa: E402
import pa_llama_topology_plan_v1 as p  # noqa: E402
import pa_llama_topology_target_continuation_v1 as t  # noqa: E402

c = t.c
POSITIONS = (0, 3, 4, 10, 11, 14, 15, 16, 18, 21, 22, 23, 24, 25, 33, 34, 36, 37, 42, 43, 44)


@pytest.fixture
def joined(tmp_path, monkeypatch):
    population = [
        {
            "payload_position": pos,
            **{
                key: c.digest(["invented", key, pos])
                for key in (
                    "payload_sha256",
                    "prompt_sha256",
                    "unit_manifest_sha256",
                    "fragment_manifest_sha256",
                )
            },
        }
        for pos in POSITIONS
    ]
    requests, materials = p._schedule(c.digest("invented schedule"), population)
    plan = {
        "n": 21,
        "plan_identity_sha256": t.PLAN_SHA,
        "requests": requests,
        "bound_materializations": materials,
        "budgets": p.budgets(21),
        "parent_operational_amendment_disclosure": {
            "operational_amendment_sha256s": ["b" * 64],
            "original_seed11_jailmeter_operational_gate_passed": False,
        },
    }
    config = {
        "_contract_sha256": t.PARENT_SHA,
        "bound_plan_identity_sha256": t.PLAN_SHA,
        "source_bundle_identity_sha256": e.SOURCE_BUNDLE,
        "execution_limits": {"deadline_utc": e.DEADLINE},
    }
    parent = SimpleNamespace(
        root=tmp_path,
        plan=plan,
        config=config,
        helper=SimpleNamespace(),
        assert_unchanged=lambda: None,
    )
    parent.path = lambda kind, relative: c.contained(
        tmp_path / ("invented-parent-" + kind), relative
    )
    failed_id = requests[872]["request_id"]
    manifest = {
        "files": [
            {
                "kind": "safe",
                "relative": relative,
                "size_bytes": 17,
                "sha256": c.digest(["invented pin", relative]),
            }
            for relative in (
                "generate-aborted.safe.json",
                f"target/{failed_id}.cooldown.safe.json",
            )
        ]
    }
    amendment = {
        "_amendment_sha256": "a" * 64,
        "frozen": True,
        "execution_authorized": True,
        "frozen_at_utc": "2026-09-05T21:00:00+00:00",
        "prefix_manifest": {
            "path": t.PREFIX_PATH,
            "size_bytes": len(c.canonical(manifest)) + 1,
            "sha256": c.sha_bytes(c.canonical(manifest) + b"\n"),
        },
        "epoch_schedule": copy.deepcopy(t.EPOCHS),
        "prelaunch_minimum_disk_free_bytes": t.PRELAUNCH_BYTES,
    }
    target = t.CompositeTarget(parent, amendment, manifest)
    rows = []
    for item in requests:
        epoch = (
            2
            if item["ordinal"] <= 872
            else next(
                block["epoch_index"]
                for block in t.EPOCHS
                if block["first_ordinal"] <= item["ordinal"] <= block["last_ordinal"]
            )
        )
        rows.append(
            {
                **item,
                "contract_sha256": t.PARENT_SHA,
                "epoch_index": epoch,
                "process_id": 1000 + epoch,
                "eligible_for_panel": item["kind"] == "science",
                "eligible_for_control": item["kind"] == "control",
            }
        )

    # Explicit fake raw/process boundary. Production proof assembly is NOT mocked.
    monkeypatch.setattr(target, "load_materials", lambda: {})
    monkeypatch.setattr(target, "load_census", lambda _prompts=None: {})
    monkeypatch.setattr(target, "reconcile", lambda *_: copy.deepcopy(rows))
    monkeypatch.setattr(target, "verify_attempt_authority", lambda _rows: True)
    monkeypatch.setattr(
        target,
        "verified_epoch",
        lambda index: {
            "contract_sha256": t.PARENT_SHA,
            "epoch": 1,
            "pid": 1000 + index,
            "owned_process_only": True,
            "started_at": f"2026-09-05T21:0{index}:00+00:00",
            "stopped_at": f"2026-09-05T21:0{index}:01+00:00",
        },
    )
    monkeypatch.setattr(e, "source_pin", lambda _target: None)
    return target, rows


def test_actual_composite_producer_to_amended_acceptor_full1470(joined):
    target, rows = joined
    produced = target.verify_composite_targets()
    accepted_rows, accepted_proof = e.verify_target_frame(target)
    assert accepted_rows == rows == produced["rows"]
    assert accepted_proof == produced["proof"]
    assert sum(r["kind"] == "science" for r in rows) == 882
    assert sum(r["kind"] == "control" for r in rows) == 588
    assert sum(r["kind"] == "science" for r in rows[:872]) == 536
    assert sum(r["kind"] == "control" for r in rows[:872]) == 336
    assert [x["target_count"] for x in accepted_proof["continuation_epoch_proofs"]] == [
        210,
        210,
        178,
    ]
    assert target.summary(rows)["operational_gate_passed"] is False
    assert accepted_proof["original_operational_gate_passed"] is False
    assert accepted_proof["amended_execution_gate_passed"] is True


@pytest.mark.parametrize(
    "mutation", ["old_pass", "old_pin_shape", "epoch_order", "epoch_digest", "row_order"]
)
def test_coherently_resealed_interface_corruption_is_rejected(joined, monkeypatch, mutation):
    target, _ = joined
    value = target.verify_composite_targets()
    proof = value["proof"]
    if mutation == "old_pass":
        proof["original_operational_gate_passed"] = True
    elif mutation == "old_pin_shape":
        pin = proof["original_abort_pin"]
        proof["original_abort_pin"] = {
            "path": pin["relative"],
            "size_bytes": pin["size_bytes"],
            "sha256": pin["sha256"],
        }
    elif mutation == "epoch_order":
        proof["continuation_epoch_proofs"].reverse()
    elif mutation == "epoch_digest":
        proof["continuation_epoch_proofs"][0]["target_rows_identity_sha256"] = "f" * 64
    else:
        value["rows"][872], value["rows"][873] = value["rows"][873], value["rows"][872]
        proof["rows_identity_sha256"] = c.digest(value["rows"])
        proof["continuation_rows_identity_sha256"] = c.digest(value["rows"][872:])
    e.seal(proof)
    monkeypatch.setattr(target, "verify_composite_targets", lambda: value)
    with pytest.raises(c.DevelopmentError):
        e.verify_target_frame(target)


@pytest.mark.parametrize("run_analysis", [True, False])
def test_actual_disclosure_decoration_rebinds_all_product_identities(joined, run_analysis):
    target, rows = joined
    _, proof = e.verify_target_frame(target)
    shared = e.disclosure(proof)
    science = [dict(row) for row in rows if row["kind"] == "science"]
    axes = {
        axis: {
            "schema_version": e.AXIS_SCHEMA,
            "axis": axis,
            "rows": science,
            "rows_identity_sha256": c.digest(science),
            "planned_records": 882,
            "parent_operational_amendment_disclosure": copy.deepcopy(
                target.plan["parent_operational_amendment_disclosure"]
            ),
            **copy.deepcopy(shared),
        }
        for axis in ("qwen", "jailmeter")
    }
    for axis, value in axes.items():
        projected = e.scientific_axis_projection(value, axis, proof)
        assert not e.DISCLOSURE_KEYS.intersection(projected)
        assert projected["schema_version"] == "jbspan-pa-llama-topology-panel-axis-v1"
        assert projected["rows"] == science
        assert value["schema_version"] == e.AXIS_SCHEMA
    tables = e.seal({"schema_version": "synthetic-table", "observed_scientific_records": 882})
    analyzed = (
        e.seal(
            {
                "schema_version": "synthetic-analysis",
                "upstream_declared_topology_aggregate_identity_sha256": tables[
                    "result_identity_sha256"
                ],
            }
        )
        if run_analysis
        else None
    )
    measured = e.seal(
        {
            "schema_version": "synthetic-measurements",
            "tables": tables,
            "scientific_rows": science,
            "control_rows": rows[0:0],
        }
    )
    measured["control_rows"] = [dict(row) for row in rows if row["kind"] == "control"]
    e.seal(measured)
    result = e.seal(
        {
            "schema_version": "synthetic-result",
            "analysis_complete": run_analysis,
            "parent_operational_amendment_disclosure": copy.deepcopy(
                target.plan["parent_operational_amendment_disclosure"]
            ),
        }
    )
    original = {"measurements": measured, "analysis": analyzed, "result": result}
    before = copy.deepcopy(original)
    decorated = e.decorate_products(original, axes, proof)
    assert original == before, "Projection/decorating must not rewrite original products"
    new_table = decorated["measurements"]["tables"]
    for value in [new_table, *[v for v in decorated.values() if v is not None]]:
        assert value["result_identity_sha256"] == c.digest(
            {k: v for k, v in value.items() if k != "result_identity_sha256"}
        )
        assert all(c.same(value[k], expected) for k, expected in shared.items())
        assert "continued" in value["schema_version"]
    final = decorated["result"]
    assert final["table_identity_sha256"] == new_table["result_identity_sha256"]
    assert (
        final["measurements_identity_sha256"] == decorated["measurements"]["result_identity_sha256"]
    )
    assert final["axis_identity_sha256"] == {axis: c.digest(value) for axis, value in axes.items()}
    assert final["original_v1_finalization_pass_claimed"] is False
    assert final["epoch_invariance_or_independent_epoch_replication_claimed"] is False
    assert (
        final["parent_operational_amendment_disclosure"]
        == target.plan["parent_operational_amendment_disclosure"]
    )
    if run_analysis:
        assert final["analysis_identity_sha256"] == decorated["analysis"]["result_identity_sha256"]
        assert (
            decorated["analysis"]["upstream_declared_topology_aggregate_identity_sha256"]
            == new_table["result_identity_sha256"]
        )
    else:
        assert decorated["analysis"] is None and final["analysis_identity_sha256"] is None
        assert final["analysis_complete"] is False


def test_real_amended_publication_names_survive_child_namespace_check(joined, monkeypatch):
    """Publication namespace is real; original-file inventory is an explicit fake."""
    target, rows = joined
    _, proof = e.verify_target_frame(target)
    shared = e.disclosure(proof)
    science = [dict(row) for row in rows if row["kind"] == "science"]
    axes = {
        axis: {
            "schema_version": e.AXIS_SCHEMA,
            "axis": axis,
            "rows": science,
            "rows_identity_sha256": c.digest(science),
            "planned_records": 882,
            **copy.deepcopy(shared),
        }
        for axis in ("qwen", "jailmeter")
    }
    # Invented measurements exercise the real decoration/publication joins, not
    # scientific classification or raw verification, which remain explicit fakes.
    tables = e.seal({"schema_version": "synthetic-table", "observed_scientific_records": 882})
    original = {
        "measurements": e.seal(
            {
                "schema_version": "synthetic-measurements",
                "tables": tables,
                "scientific_rows": science,
                "control_rows": [dict(row) for row in rows if row["kind"] == "control"],
            }
        ),
        "analysis": e.seal(
            {
                "schema_version": "synthetic-analysis",
                "upstream_declared_topology_aggregate_identity_sha256": tables[
                    "result_identity_sha256"
                ],
            }
        ),
        "result": e.seal(
            {
                "schema_version": "synthetic-result",
                "analysis_complete": True,
                "parent_operational_amendment_disclosure": copy.deepcopy(
                    target.plan["parent_operational_amendment_disclosure"]
                ),
            }
        ),
    }
    products = e.decorate_products(original, axes, proof)
    products["verification"] = e.seal(
        {
            "schema_version": "jbspan-pa-llama-topology-continued-final-verification-v1",
            "original_contract_sha256": e.PARENT,
            "finalizer_source_path": e.SCRIPT,
            **shared,
            "result_identity_sha256": products["result"]["result_identity_sha256"],
            "product_identity_sha256": {
                key: value["result_identity_sha256"] for key, value in products.items()
            },
            "product_file_sha256": {
                key: c.sha_bytes(c.canonical(value) + b"\n") for key, value in products.items()
            },
            "axis_identity_sha256": products["result"]["axis_identity_sha256"],
            "parent_operational_amendment_disclosure": copy.deepcopy(
                target.plan["parent_operational_amendment_disclosure"]
            ),
            "source_bundle_identity_sha256": e.SOURCE_BUNDLE,
            "target_composite_raw_receipts_reverified": True,
            "new_evaluator_raw_receipts_reverified": True,
            "new_panel_lifecycle_and_resource_receipts_verified": True,
            "independent_frozen_panel_rule_verified": True,
            "control_raw_hash_and_content_rechecked": True,
            "all1470_targets_and_both882_science_axes_retained": True,
            "original_target_operational_pass_claimed": False,
            "original_v1_finalization_pass_claimed": False,
            "epoch_invariance_or_independent_epoch_replication_claimed": False,
            "analysis_complete": True,
            "paper_validity": False,
            "execution_authorized": False,
            "new_model_calls": 0,
            "historical_private_reads": 0,
            "sealed_reads": 0,
        },
        "verification_identity_sha256",
    )
    writes = []
    actual_write = target.write

    def write(kind, relative, value, *, raw=False):
        writes.append(relative)
        return actual_write(kind, relative, value, raw=raw)

    monkeypatch.setattr(target, "write", write)
    monkeypatch.setattr(t, "verify_parent_names", lambda _parent: [])
    e.publish(target, products)
    assert writes == list(e.OUTPUTS.values())
    assert writes[-1] == "continued-verification.safe.json"
    assert target.global_check("target") == {
        row["request_id"] for row in target.plan["requests"][:872]
    }
    e.publish(target, products)
    assert len(writes) == 4, "Idempotent publication must not rewrite proof or products"
    actual_write("safe", "result.safe.json", {"invented_original_shape_facade": True})
    with pytest.raises(c.DevelopmentError, match="UNEXPECTED_CHILD_ROOT_NAMESPACE"):
        target.global_check("target")
