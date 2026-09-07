"""Explicit v2 acceptance bridge into unchanged PURE scientific joins.

No inference. A pure builder validates supplied identities, not their historical
truth. The actual finalizer must reverify target and both axes first. Old v1
operational PASS is never produced or published by this module.
"""

from __future__ import annotations

import copy

import pa_llama_development_panel_v1 as low
import pa_llama_topology_analysis_v1 as analysis
import pa_llama_topology_finalize_v1 as frozen
import pa_llama_topology_materialize_v1 as materialize
import pa_reentry_journal_v2 as j

TOTAL, REUSED, SCIENCE = 1470, 1082, 882
FAILURES = ["DISK_FREE_SPACE_BELOW_15_GIB", "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB"]
OUTPUTS = {
    "measurements": "measurements.safe.json",
    "analysis": "analysis.safe.json",
    "result": "result.safe.json",
    "verification": "verification.safe.json",
}


def reseal(value, key="result_identity_sha256"):
    value.pop(key, None)
    value[key] = j.digest(value)
    return value


def validate_target(proof, targets, config, plan):
    j.verify_seal(proof, "proof_identity_sha256")
    expected = {
        "schema_version": "pa-reentry-target-composite-v2",
        "original_contract_sha256": config["_contract_sha256"],
        "bound_plan_identity_sha256": plan["plan_identity_sha256"],
        "target_records": TOTAL,
        "reused_target_records": REUSED,
        "new_target_records": TOTAL - REUSED,
        "target_rows_sha256": j.digest(targets),
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "prior_operation_failures": FAILURES,
        "composite_target_complete": True,
        "scientific_gate_evaluated": False,
        "paper_validity": False,
        "archive_relocation_contemporaneous_receipt_available": False,
    }
    j.require(
        all(proof.get(k) == value for k, value in expected.items()),
        "FINAL_V2_TARGET_COMPLETENESS_OR_DISCLOSURE_CHANGED",
    )
    j.require(
        len(targets) == TOTAL
        and len(plan["requests"]) == TOTAL
        and [row["request_id"] for row in targets]
        == [row["request_id"] for row in plan["requests"]],
        "FINAL_V2_TARGET_FRAME_CHANGED",
    )
    j.require(
        isinstance(proof.get("missing_stop_epochs"), list)
        and isinstance(proof.get("all_attempts"), list)
        and proof.get("all_attempts_sha256") == j.digest(proof["all_attempts"]),
        "FINAL_V2_ATTEMPT_DISCLOSURE_REQUIRED",
    )
    j.stamp(proof["latest_target_release_at"])


def project_axis(value, axis, target_proof, config, plan):
    """In-memory scientific schema only; never publish this unqualified adapter."""
    j.verify_seal(value, "proof_identity_sha256")
    expected = {
        "schema_version": "pa-reentry-panel-axis-v2",
        "execution_identity": target_proof["execution_identity"],
        "original_contract_sha256": config["_contract_sha256"],
        "bound_plan_identity_sha256": plan["plan_identity_sha256"],
        "stage": axis,
        "complete": True,
        "planned_records": SCIENCE,
        "controls_judged": 0,
        "target_composite_proof": target_proof,
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "prior_operation_failures": FAILURES,
        "raw_receipts_reverified": True,
        "scientific_rules_changed": False,
        "paper_validity": False,
    }
    j.require(
        all(value.get(k) == item for k, item in expected.items()),
        "FINAL_V2_AXIS_PROOF_OR_DISCLOSURE_CHANGED",
    )
    rows = value["rows"]
    frame = [row for row in plan["requests"] if row["kind"] == "science"]
    j.require(
        len(rows) == len(frame) == SCIENCE
        and [row["request_id"] for row in rows] == [row["request_id"] for row in frame]
        and value["rows_identity_sha256"] == j.digest(rows),
        "FINAL_V2_AXIS_FRAME_CHANGED",
    )
    j.require(
        all(type(row.get("dispatched")) is bool for row in rows)
        and value["dispatched"] == sum(row["dispatched"] for row in rows)
        and value["skipped"] == sum(not row["dispatched"] for row in rows),
        "FINAL_V2_AXIS_COUNTS_CHANGED",
    )
    j.require(
        isinstance(value.get("epochs"), list)
        and all(
            epoch.get("resource_evidence_complete") is True
            for epoch in value["epochs"]
            if epoch.get("dispatches", 0)
        ),
        "FINAL_V2_INCOMPLETE_RESOURCE_EVIDENCE",
    )
    return {
        "schema_version": "jbspan-pa-llama-topology-panel-axis-v1",
        "contract_sha256": config["_contract_sha256"],
        "bound_plan_identity_sha256": plan["plan_identity_sha256"],
        "axis": axis,
        "complete": True,
        "planned_records": SCIENCE,
        "rows": copy.deepcopy(rows),
        "rows_identity_sha256": j.digest(rows),
        "dispatched": value["dispatched"],
        "skipped": value["skipped"],
        "all_scientific_rows_included": True,
        "raw_receipts_reverified": True,
        "controls_judged": 0,
        "parent_operational_amendment_disclosure": copy.deepcopy(
            plan["parent_operational_amendment_disclosure"]
        ),
    }


def disclosure(target_proof):
    return {
        "second_continuation_execution_identity": target_proof["execution_identity"],
        "target_composite_proof_identity_sha256": target_proof["proof_identity_sha256"],
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "prior_operation_failures": FAILURES,
        "archive_relocation_contemporaneous_receipt_available": False,
        "original_unqualified_pass_claimed": False,
        "epoch_invariance_claimed": False,
        "paper_validity": False,
    }


def build_products(
    config,
    plan,
    source_context,
    targets,
    axes,
    target_proof,
    helpers,
    control_raw,
    tasks,
    *,
    reference=None,
    run_analysis=False,
):
    """Synthetic-testable identity bridge; no file access or inference here."""
    validate_target(target_proof, targets, config, plan)
    j.require(set(axes) == {"qwen", "jailmeter"}, "FINAL_V2_BOTH_AXES_REQUIRED")
    projected = {
        axis: project_axis(value, axis, target_proof, config, plan) for axis, value in axes.items()
    }
    products = frozen.build_artifacts(
        config,
        plan,
        source_context,
        targets,
        projected,
        helpers,
        control_raw,
        tasks,
        reference=reference,
        run_analysis=run_analysis,
    )
    shared = disclosure(target_proof)
    measured, analyzed, result = (products[key] for key in ("measurements", "analysis", "result"))
    tables = measured["tables"]
    tables.update(schema_version="pa-reentry-measurement-v2", **shared)
    reseal(tables)
    measured.update(schema_version="pa-reentry-joined-measurements-v2", **shared)
    reseal(measured)
    if analyzed is not None:
        analyzed.update(schema_version="pa-reentry-analysis-v2", **shared)
        analyzed["upstream_declared_topology_aggregate_identity_sha256"] = tables[
            "result_identity_sha256"
        ]
        reseal(analyzed)
    result.update(schema_version="pa-reentry-finalization-v2", **shared)
    result.update(
        measurements_identity_sha256=measured["result_identity_sha256"],
        table_identity_sha256=tables["result_identity_sha256"],
        analysis_identity_sha256=analyzed["result_identity_sha256"]
        if analyzed is not None
        else None,
        axis_identity_sha256={axis: j.digest(value) for axis, value in axes.items()},
    )
    reseal(result)
    core = {key: value for key, value in products.items() if value is not None}
    products["verification"] = j.seal(
        {
            "schema_version": "pa-reentry-final-verification-v2",
            **shared,
            "target_composite_proof": target_proof,
            "axis_identity_sha256": result["axis_identity_sha256"],
            "result_identity_sha256": result["result_identity_sha256"],
            "product_identity_sha256": {
                key: value["result_identity_sha256"] for key, value in core.items()
            },
            "product_file_sha256": {
                key: j.sha_bytes(j.canonical(value) + b"\n") for key, value in core.items()
            },
            "raw_receipts_read_by_this_pure_builder": False,
            "actual_raw_verification_by_entrypoint": False,
            "analysis_complete": run_analysis,
        },
        "verification_identity_sha256",
    )
    return products


def validate_products(products):
    j.require(
        set(products) == set(OUTPUTS) and list(products)[-1] == "verification",
        "FINAL_V2_PROOF_LAST_REQUIRED",
    )
    proof = j.verify_seal(products["verification"], "verification_identity_sha256")
    target_proof = j.verify_seal(proof["target_composite_proof"], "proof_identity_sha256")
    shared = disclosure(target_proof)
    measured, analyzed, result = (products[key] for key in ("measurements", "analysis", "result"))
    tables = measured["tables"]
    values = [
        (tables, "pa-reentry-measurement-v2"),
        (measured, "pa-reentry-joined-measurements-v2"),
        (result, "pa-reentry-finalization-v2"),
    ]
    if analyzed is not None:
        values.append((analyzed, "pa-reentry-analysis-v2"))
    for value, schema in values:
        j.verify_seal(value, "result_identity_sha256")
        j.require(
            value["schema_version"] == schema and all(value.get(k) == v for k, v in shared.items()),
            "FINAL_V2_PRODUCT_DISCLOSURE_CHANGED",
        )
    j.require(
        proof["schema_version"] == "pa-reentry-final-verification-v2"
        and all(proof.get(k) == v for k, v in shared.items()),
        "FINAL_V2_VERIFICATION_DISCLOSURE_CHANGED",
    )
    core = {
        key: value for key, value in products.items() if key != "verification" and value is not None
    }
    j.require(
        proof["product_identity_sha256"]
        == {key: value["result_identity_sha256"] for key, value in core.items()}
        and proof["product_file_sha256"]
        == {key: j.sha_bytes(j.canonical(value) + b"\n") for key, value in core.items()},
        "FINAL_V2_PRODUCT_HASH_JOINS_CHANGED",
    )
    j.require(
        result["measurements_identity_sha256"] == measured["result_identity_sha256"]
        and result["table_identity_sha256"] == tables["result_identity_sha256"]
        and result["analysis_identity_sha256"]
        == (analyzed["result_identity_sha256"] if analyzed else None)
        and result["analysis_complete"] is (analyzed is not None)
        and proof["analysis_complete"] is (analyzed is not None)
        and proof["result_identity_sha256"] == result["result_identity_sha256"]
        and proof["axis_identity_sha256"] == result["axis_identity_sha256"]
        and result["target_rows_identity_sha256"] == target_proof["target_rows_sha256"]
        and (
            analyzed is None
            or analyzed["upstream_declared_topology_aggregate_identity_sha256"]
            == tables["result_identity_sha256"]
        ),
        "FINAL_V2_INNER_JOINS_CHANGED",
    )


def publish(directory, products):
    validate_products(products)
    j.reject_links(directory)
    for name in ("publication.lock", *OUTPUTS.values()):
        j.reject_links(directory / name)
        j.reject_links(j.pending_path(directory / name))
    j.require(
        products["verification"]["actual_raw_verification_by_entrypoint"] is True,
        "FINAL_V2_PURE_BUILDER_NOT_RAW_VERIFICATION",
    )
    marker = directory / OUTPUTS["verification"]
    if marker.exists():
        j.require(
            all(
                (directory / OUTPUTS[key]).is_file()
                for key, value in products.items()
                if value is not None
            ),
            "FINAL_V2_ORPHAN_PROOF_NO_REPAIR",
        )
    for key, value in products.items():
        path = directory / OUTPUTS[key]
        if value is None:
            j.require(not path.exists(), "FINAL_V2_DEFERRED_PRODUCT_CONFLICT")
        elif path.exists():
            j.require(
                path.read_bytes() == j.canonical(value) + b"\n", "FINAL_V2_EXISTING_PRODUCT_CHANGED"
            )
    for key, value in products.items():
        if value is not None and not (directory / OUTPUTS[key]).exists():
            j.atomic_json(directory / OUTPUTS[key], value)


def make_direction(execution_identity, stage, *, issued_at, expires_at, direction_ref):
    value = j.seal(
        {
            "schema_version": "pa-reentry-postprocessing-direction-v2",
            "execution_identity": execution_identity,
            "stage": stage,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "direction_ref": direction_ref,
        },
        "direction_identity_sha256",
    )
    validate_direction(value, execution_identity, run_analysis=stage == 7, now=issued_at)
    return value


def validate_direction(direction, execution_identity, *, run_analysis, now=None):
    j.require(type(run_analysis) is bool, "FINAL_V2_ANALYSIS_FLAG_TYPE")
    j.require(
        isinstance(execution_identity, str) and j.SHA.fullmatch(execution_identity),
        "FINAL_V2_EXECUTION_IDENTITY_REQUIRED",
    )
    j.verify_seal(direction, "direction_identity_sha256")
    j.require(
        set(direction)
        == {
            "schema_version",
            "execution_identity",
            "stage",
            "issued_at",
            "expires_at",
            "direction_ref",
            "direction_identity_sha256",
        },
        "FINAL_V2_DIRECTION_FIELDS",
    )
    j.require(
        direction["schema_version"] == "pa-reentry-postprocessing-direction-v2"
        and direction["execution_identity"] == execution_identity
        and type(direction["stage"]) is int
        and direction["stage"] == (7 if run_analysis else 6),
        "FINAL_V2_WRONG_STAGE_DIRECTION",
    )
    j.require(
        isinstance(direction["direction_ref"], str)
        and bool(direction["direction_ref"].strip())
        and len(direction["direction_ref"]) <= 512,
        "FINAL_V2_CURRENT_STAGE_DIRECTION_REQUIRED",
    )
    issued, expires = j.stamp(direction["issued_at"]), j.stamp(direction["expires_at"])
    j.require(
        0 < (expires - issued).total_seconds() <= 2 * 3600
        and issued <= j.stamp(now or j.utc()) <= expires,
        "FINAL_V2_DIRECTION_WINDOW",
    )


def finalize(target, payloads, *, direction, run_analysis=False):
    """Only a later, explicit stage-6/7 caller may invoke this write operation."""
    validate_direction(direction, target.execution_identity, run_analysis=run_analysis)
    target.assert_launch_ready()
    from pa_reentry_panel_v2 import ReentryPanel

    rows, proof = target.verify_complete()
    panel = ReentryPanel(
        target, payloads, target.safe.parent, target.private.parent, target.execution_identity
    )
    axes = {axis: panel.verify(axis) for axis in ("qwen", "jailmeter")}
    if run_analysis:
        prior_directory = target.safe.parent / "finalization" / "measurements-only"
        j.reject_links(prior_directory)
        previous = {
            key: j.read_json(prior_directory / name) if key != "analysis" else None
            for key, name in OUTPUTS.items()
        }
        validate_products(previous)
        j.require(
            previous["verification"]["actual_raw_verification_by_entrypoint"] is True
            and previous["verification"]["target_composite_proof"] == proof
            and previous["verification"]["axis_identity_sha256"]
            == {axis: j.digest(value) for axis, value in axes.items()},
            "FINAL_V2_STAGE6_VERIFIED_INPUTS_REQUIRED",
        )
    helpers = low.load_pure_functions(target.root, target.config)
    renderer = materialize.load(target.root)
    tasks = {task["id"]: task["text"] for task in renderer.tasks}
    controls = {
        item["request_id"]: target.raw_reply(item["request_id"])
        for item in target.plan["requests"]
        if item["kind"] == "control"
    }
    products = build_products(
        target.config,
        target.plan,
        target.history.source_context,
        rows,
        axes,
        proof,
        helpers,
        controls,
        tasks,
        reference=analysis.load_reference_functions(target.root) if run_analysis else None,
        run_analysis=run_analysis,
    )
    verification = products["verification"]
    verification.update(
        actual_raw_verification_by_entrypoint=True, current_stage_direction=direction
    )
    reseal(verification, "verification_identity_sha256")
    directory = (
        target.safe.parent
        / "finalization"
        / ("with-analysis" if run_analysis else "measurements-only")
    )
    with j.run_lock(directory / "publication.lock"):
        validate_direction(direction, target.execution_identity, run_analysis=run_analysis)
        publish(directory, products)
    return verification
