"""Verify NEW topology receipts and publish SAFE measurements/analysis, proof last.

No inference, historical extractor or parent writer. The separate execution loader
authenticates the complete source/code/config closure and raw parent screen chain.
Pure build_artifacts() does not itself claim that its supplied receipts were read.
"""

from __future__ import annotations

from collections import Counter

import pa_llama_development_aggregate_v1 as independent
import pa_llama_development_common_v1 as c
import pa_llama_development_panel_v1 as low
import pa_llama_topology_analysis_v1 as analysis
import pa_llama_topology_materialize_v1 as materialize
import pa_llama_topology_measurement_v1 as measurement
import pa_llama_topology_panel_v1 as panel
import pa_llama_topology_plan_v1 as p

SCRIPT = "scripts/pa_llama_topology_finalize_v1.py"
SCHEMA = "jbspan-pa-llama-topology-finalization-v1"
OUTPUTS = {
    "measurements": "measurements.safe.json",
    "analysis": "analysis.safe.json",
    "result": "result.safe.json",
    "verification": "verification.safe.json",
}


def baseline_references(plan, source_context):
    """Bind each shared mask0 slot to the exact three-seed screen decision."""
    states = source_context["final_result"]["pair_states"]
    rows = []
    for reference in plan["mask_zero_screen_reuse"]:
        position, seed = reference["payload_position"], reference["seed"]
        state = states[position]
        observations = {row["seed"]: row for row in state["seed_observations"]}
        c.require(
            state["payload_position"] == position
            and state["status"] == "STABLE_PAIR"
            and set(observations) == set(p.SEEDS),
            "TOPOLOGY_BASELINE_THREE_SEED_SOURCE_REQUIRED",
        )
        decision = observations[seed]["attacked"]
        c.require(
            decision["request_id"] == reference["source_request_id"]
            and decision["panel_label"] == "HARMFUL"
            and decision["eligible"] is True,
            "TOPOLOGY_BASELINE_EXACT_HARMFUL_DECISION_REQUIRED",
        )
        rows.append(
            {
                **reference,
                "screen_decision_identity_sha256": c.digest(decision),
                "screen_state_identity_sha256": c.digest(state),
            }
        )
    c.require(len(rows) == 6 * plan["n"], "TOPOLOGY_BASELINE_COMPLETE_REFERENCE_FRAME")
    return rows


def join_frames(config, plan, targets, axes, helpers):
    """Exact all-target and both science-axis joins; independently check the rule."""
    requests = plan["requests"]
    c.require(
        isinstance(targets, list)
        and len(targets) == 70 * plan["n"]
        and [row["request_id"] for row in targets] == [r["request_id"] for r in requests],
        "TOPOLOGY_FINALIZE_ALL_ORDERED_TARGETS_REQUIRED",
    )
    by_target = {}
    for item, row in zip(requests, targets, strict=True):
        c.require(
            all(c.same(row.get(key), value) for key, value in item.items())
            and row.get("contract_sha256") == config["_contract_sha256"]
            and type(row.get("eligible_for_panel")) is bool
            and type(row.get("eligible_for_control")) is bool
            and type(row.get("completion_cap_reached")) is bool
            and row.get("finish_reason") in {"stop", "length"}
            and c.valid_sha(row.get("response_sha256"))
            and c.valid_sha(row.get("content_sha256"))
            and c.valid_sha(row.get("raw_reply_sha256")),
            "TOPOLOGY_FINALIZE_TARGET_BINDING",
        )
        c.require(
            row["eligible_for_control"] is False
            if item["kind"] == "science"
            else row["eligible_for_panel"] is False,
            "TOPOLOGY_FINALIZE_KIND_ELIGIBILITY",
        )
        by_target[item["request_id"]] = row
    science = panel.science_frame(plan)
    expected_ids = [row["request_id"] for row in science]
    c.require(set(axes) == {"qwen", "jailmeter"}, "TOPOLOGY_FINALIZE_BOTH_AXES_REQUIRED")
    maps = {}
    for axis in ("qwen", "jailmeter"):
        result = axes[axis]
        rows = result["rows"]
        c.require(
            result.get("schema_version") == "jbspan-pa-llama-topology-panel-axis-v1"
            and result.get("contract_sha256") == config["_contract_sha256"]
            and result.get("bound_plan_identity_sha256") == plan["plan_identity_sha256"]
            and result.get("axis") == axis
            and result.get("complete") is True
            and c.same(result.get("planned_records"), len(science))
            and result.get("rows_identity_sha256") == c.digest(rows)
            and result.get("all_scientific_rows_included") is True
            and result.get("raw_receipts_reverified") is True
            and c.same(result.get("controls_judged"), 0)
            and c.same(
                result.get("parent_operational_amendment_disclosure"),
                plan["parent_operational_amendment_disclosure"],
            )
            and isinstance(rows, list)
            and [r["request_id"] for r in rows] == expected_ids,
            "TOPOLOGY_FINALIZE_AXIS_BINDING",
        )
        c.require(
            all(type(row.get("dispatched")) is bool for row in rows)
            and c.same(result.get("dispatched"), sum(r["dispatched"] for r in rows))
            and c.same(result.get("skipped"), sum(not r["dispatched"] for r in rows)),
            "TOPOLOGY_FINALIZE_AXIS_COUNTS",
        )
        maps[axis] = {row["request_id"]: row for row in rows}
    decisions = []
    for item in science:
        rid = item["request_id"]
        values = (by_target[rid], maps["qwen"][rid], maps["jailmeter"][rid])
        observed = helpers.panel_decision(*values)
        c.require(
            c.same(observed, independent.independent_panel(*values)),
            "TOPOLOGY_FINALIZE_INDEPENDENT_PANEL_MISMATCH",
        )
        decisions.append(
            {
                "request_id": rid,
                **observed,
                "target_row_identity_sha256": c.digest(values[0]),
                "qwen_row_identity_sha256": c.digest(values[1]),
                "jailmeter_row_identity_sha256": c.digest(values[2]),
            }
        )
    return by_target, decisions


def build_artifacts(
    config,
    plan,
    source_context,
    targets,
    axes,
    helpers,
    control_raw,
    tasks,
    *,
    reference=None,
    run_analysis=True,
):
    """Pure all-frame assembly from explicitly supplied NEW verified observations."""
    p.validate_plan(plan, **source_context)
    c.require(type(run_analysis) is bool, "TOPOLOGY_ANALYSIS_FLAG_BOOLEAN_REQUIRED")
    c.require(
        config.get("frozen") is True
        and config.get("execution_authorized") is True
        and config.get("paper_validity") is False
        and c.valid_sha(config.get("_contract_sha256"))
        and config.get("bound_plan_identity_sha256") == plan["plan_identity_sha256"]
        and c.same(config.get("budgets"), plan["budgets"]),
        "TOPOLOGY_FINALIZE_FROZEN_AUTHORITY_REQUIRED",
    )
    baseline = baseline_references(plan, source_context)
    by_target, decisions = join_frames(config, plan, targets, axes, helpers)
    by_decision = {row["request_id"]: row for row in decisions}
    materials = {
        row["materialization_id"]: row["renderer_row"] for row in plan["bound_materializations"]
    }
    control_items = [row for row in plan["requests"] if row["kind"] == "control"]
    c.require(
        set(control_raw) == {row["request_id"] for row in control_items},
        "TOPOLOGY_FINALIZE_EXACT_CONTROL_RAW_FRAME",
    )
    c.require(set(tasks) == set(p.TASKS), "TOPOLOGY_FINALIZE_EXACT_BENIGN_TASKS")
    scientific, controls, control_scores = [], [], []
    for item in plan["requests"]:
        rid = item["request_id"]
        target, material = by_target[rid], materials[item["materialization_id"]]
        row = {
            key: item[key] for key in ("request_id", "payload_position", "mask", "operator", "seed")
        }
        row.update(
            prompt_sha256=material["prompt_sha256"], response_sha256=target["response_sha256"]
        )
        if item["kind"] == "science":
            decision = by_decision[rid]
            scientific.append(
                {
                    **row,
                    "panel_label": decision["panel_label"],
                    "measurement_eligible": decision["measurement_eligible"],
                    "input_valid": material["input_valid"],
                    "target_truncated": target["finish_reason"] == "length",
                }
            )
            continue
        raw = control_raw[rid]
        c.require(
            isinstance(raw, bytes) and c.sha_bytes(raw) == target["raw_reply_sha256"],
            "TOPOLOGY_FINALIZE_CONTROL_RAW_HASH",
        )
        content = c.strict_json(raw)["choices"][0]["message"]["content"]
        response = c.normalize_response(content)
        c.require(
            c.sha_bytes(content.encode()) == target["content_sha256"]
            and c.sha_bytes(response.encode()) == target["response_sha256"],
            "TOPOLOGY_FINALIZE_CONTROL_CONTENT_HASH",
        )
        score = measurement.score_control(
            response,
            tasks[item["task_id"]],
            item["task_id"],
            operational_pass=target["eligible_for_control"],
            truncated=target["finish_reason"] == "length" or target["completion_cap_reached"],
        )
        controls.append(
            {
                **row,
                "task_id": item["task_id"],
                "content_capability_pass": score["content_capability_pass"],
                "whole_answer_diagnostic_pass": score["whole_answer_diagnostic_pass"],
            }
        )
        control_scores.append(
            {"request_id": rid, **score, "target_row_identity_sha256": c.digest(target)}
        )
    measured = measurement.assemble_tables(
        plan, scientific, controls, source_context=source_context
    )
    c.require(measured["complete_execution_frame"] is True, "TOPOLOGY_FINALIZE_INCOMPLETE_FRAME")
    analyzed = (
        analysis.analyze_topology(
            source_context["final_result"],
            measured["primary_rows"],
            measured["slice_rows"],
            source_identity_sha256=measured["result_identity_sha256"],
            screen_verification=source_context["final_verification"],
            reference=reference,
            control_qualified_slice_rows=measured["control_qualified_slice_rows"],
        )
        if run_analysis
        else None
    )
    measurements = {
        "schema_version": "jbspan-pa-llama-topology-joined-measurements-v1",
        "contract_sha256": config["_contract_sha256"],
        "bound_plan_identity_sha256": plan["plan_identity_sha256"],
        "scientific_rows": scientific,
        "control_rows": controls,
        "panel_decisions": decisions,
        "control_scores": control_scores,
        "mask0_screen_references": baseline,
        "tables": measured,
        "raw_receipts_verified_by_this_pure_function": False,
        "new_model_calls": 0,
        "paper_validity": False,
    }
    measurements["result_identity_sha256"] = c.digest(measurements)
    result = {
        "schema_version": SCHEMA,
        "contract_sha256": config["_contract_sha256"],
        "bound_plan_identity_sha256": plan["plan_identity_sha256"],
        "source_bundle_identity_sha256": config["source_bundle_identity_sha256"],
        "screen_result_identity_sha256": plan["screen_result_identity_sha256"],
        "screen_verification_identity_sha256": plan["screen_verification_identity_sha256"],
        "parent_operational_amendment_disclosure": plan["parent_operational_amendment_disclosure"],
        "evidence_class": plan["evidence_class"],
        "original_screen_denominator": 45,
        "selected_payload_denominator": plan["n"],
        "all_stable_payload_positions": [row["payload_position"] for row in plan["population"]],
        "target_records_verified": len(targets),
        "scientific_records": len(scientific),
        "control_records": len(controls),
        "actual_axis_calls": {axis: axes[axis]["dispatched"] for axis in axes},
        "target_rows_identity_sha256": c.digest(targets),
        "axis_identity_sha256": {axis: c.digest(axes[axis]) for axis in axes},
        "measurements_identity_sha256": measurements["result_identity_sha256"],
        "table_identity_sha256": measured["result_identity_sha256"],
        "analysis_identity_sha256": analyzed["result_identity_sha256"] if analyzed else None,
        "baseline_references_identity_sha256": c.digest(baseline),
        "primary_status_counts": measured["primary_status_counts"],
        "panel_label_counts": dict(
            sorted(Counter(row["panel_label"] for row in decisions).items())
        ),
        "control_content_passes": sum(row["content_capability_pass"] for row in controls),
        "control_whole_answer_diagnostic_passes": sum(
            row["whole_answer_diagnostic_pass"] for row in controls
        ),
        "complete_execution_frame": True,
        "analysis_complete": run_analysis,
        "truth_table_fully_identified_payloads": sum(
            row["truth_table_fully_identified"] for row in measured["families"]
        ),
        "mask0_is_shared_screen_reference_not_new_replication": True,
        "scientific_panel_rules_unchanged": True,
        "control_cap_reached_is_noncertifying": True,
        "whole_answer_format_is_primary_gate": False,
        "raw_receipts_verified_by_this_pure_function": False,
        "paper_validity": False,
        "execution_authorized": False,
        "new_model_calls": 0,
        "historical_private_reads": 0,
        "sealed_reads": 0,
    }
    result["result_identity_sha256"] = c.digest(result)
    return {"measurements": measurements, "analysis": analyzed, "result": result}


def publish(worker, products):
    """Compare every existing file before any first write; proof is always last."""
    c.require(
        set(products) == set(OUTPUTS) and list(products)[-1] == "verification",
        "TOPOLOGY_FINALIZE_PROOF_MUST_BE_LAST",
    )
    if worker.path("safe", OUTPUTS["verification"]).exists():
        c.require(
            all(
                worker.path("safe", OUTPUTS[key]).is_file()
                for key, value in products.items()
                if value is not None
            ),
            "TOPOLOGY_FINALIZE_ORPHAN_PROOF_NO_REPAIR",
        )
    for key, value in products.items():
        if value is None:
            c.require(
                not worker.path("safe", OUTPUTS[key]).exists(),
                "TOPOLOGY_FINALIZE_DEFERRED_ANALYSIS_ALREADY_EXISTS",
            )
        elif worker.path("safe", OUTPUTS[key]).exists():
            saved = low.read_bytes(worker.path("safe", OUTPUTS[key]), maximum=32_000_000)
            c.require(
                saved == c.canonical(value) + b"\n",
                "TOPOLOGY_FINALIZE_EXISTING_OUTPUT_MISMATCH",
            )
    for key, value in products.items():
        if value is not None and not worker.path("safe", OUTPUTS[key]).exists():
            worker.write("safe", OUTPUTS[key], value)


def finalize(target_worker, payloads_by_position, source_context, *, run_analysis=True):
    """Root loader only: reverify all NEW raw receipts, then publish deterministic SAFE proof."""
    worker = target_worker
    with worker.operation("finalize"):
        worker.assert_unchanged()
        prompts = worker.load_materials()
        census = worker.load_census(prompts)
        targets = worker.reconcile(prompts, census)
        status = worker.summary(targets)
        c.require(
            status.get("complete") is True and status.get("operational_gate_passed") is True,
            "TOPOLOGY_FINALIZE_TARGET_OPERATIONAL_FAILURE",
        )
        evaluator = panel.TopologyPanel(worker, payloads_by_position)
        axes = {axis: evaluator.verify(axis) for axis in ("qwen", "jailmeter")}
        helpers = low.load_pure_functions(worker.root, worker.config)
        renderer = materialize.load(worker.root)
        tasks = {task["id"]: task["text"] for task in renderer.tasks}
        control_raw = {
            row["request_id"]: low.read_bytes(
                worker.path("private", f"target/{row['request_id']}.reply.private.json"), 2_000_000
            )
            for row in worker.plan["requests"]
            if row["kind"] == "control"
        }
        products = build_artifacts(
            worker.config,
            worker.plan,
            source_context,
            targets,
            axes,
            helpers,
            control_raw,
            tasks,
            reference=analysis.load_reference_functions(worker.root) if run_analysis else None,
            run_analysis=run_analysis,
        )
        proof = {
            "schema_version": "jbspan-pa-llama-topology-verification-v1",
            "contract_sha256": worker.config["_contract_sha256"],
            "finalizer_source_path": SCRIPT,
            "result_identity_sha256": products["result"]["result_identity_sha256"],
            "product_identity_sha256": {
                key: value["result_identity_sha256"]
                for key, value in products.items()
                if value is not None
            },
            "product_file_sha256": {
                key: c.sha_bytes(c.canonical(value) + b"\n")
                for key, value in products.items()
                if value is not None
            },
            "target_status_identity_sha256": c.digest(status),
            "native_census_identity_sha256": c.digest(census),
            "axis_identity_sha256": products["result"]["axis_identity_sha256"],
            "parent_operational_amendment_disclosure": worker.plan[
                "parent_operational_amendment_disclosure"
            ],
            "source_bundle_identity_sha256": worker.config["source_bundle_identity_sha256"],
            "parent_raw_screen_chain_verified_by_execution_loader": True,
            "new_raw_target_receipts_reverified": True,
            "new_raw_evaluator_receipts_reverified": True,
            "control_raw_hash_and_content_rechecked": True,
            "independent_frozen_panel_rule_verified": True,
            "all_stable_payloads_and_full_planned_frame_retained": True,
            "operational_lifecycle_and_resource_receipts_verified": True,
            "analysis_complete": run_analysis,
            "paper_validity": False,
            "new_model_calls": 0,
            "historical_private_reads": 0,
            "sealed_reads": 0,
        }
        proof["verification_identity_sha256"] = c.digest(proof)
        products["verification"] = proof
        worker.assert_unchanged()
        publish(worker, products)
        return {
            **products["result"],
            "verification_identity_sha256": proof["verification_identity_sha256"],
        }
