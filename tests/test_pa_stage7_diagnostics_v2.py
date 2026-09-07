"""Invented SAFE metadata only; never load production artifacts or fit outcomes."""

import copy
import sys
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_pa_stage7_diagnostics_v2 as m

j = m.j


def seal(doc, field="result_identity_sha256"):
    doc.pop(field, None)
    doc[field] = j.digest(doc)
    return doc


def fixture():
    requests, bound, targets, qrows, mrows, decisions, scores, refs = [], [], [], [], [], [], [], []
    slices, primary, groups = [], [], []
    for p, mask, op in product((0, 1), range(1, 8), m.OPS):
        groups.append(
            dict(
                payload_position=p,
                mask_id=mask,
                neutralizer_id=op,
                content_passes=2,
                observed_control_count=2,
                required_control_count=2,
                whole_answer_diagnostic_passes=0,
                matched_controls_passed=True,
            )
        )
        for seed in (*m.SEEDS, 17, 19):
            n = len(requests) + 1
            science = seed in m.SEEDS
            item = dict(
                request_id=j.digest(n),
                ordinal=n,
                payload_position=p,
                mask=mask,
                operator=op,
                seed=seed,
                kind="science" if science else "control",
                task_id=None if science else str(seed),
                payload_sha256=j.digest(p),
                materialization_id=j.digest([p, mask, op, seed]),
            )
            row = dict(
                item,
                epoch_index=4,
                dispatch_at="2026-09-07T01:00:00+00:00",
                received_at="2026-09-07T01:00:01+00:00",
                usage=dict(prompt_tokens=n, completion_tokens=1),
                response_sha256=j.digest([n, "answer"]),
                request_sha256=j.digest([n, "request"]),
                raw_reply_sha256=j.digest([n, "envelope"]),
                eligible_for_panel=science,
                completion_cap_reached=False,
                ineligible_reason=None,
            )
            requests.append(item)
            bound.append(
                dict(
                    materialization_id=item["materialization_id"],
                    renderer_row=dict(
                        prompt_sha256=j.digest([n, "render"]),
                        prompt_utf8_bytes=n + 5,
                        prompt_character_length=n + 5,
                        **({"payload_start_character": 3} if science else {}),
                        input_valid=True,
                    ),
                )
            )
            targets.append(dict(row=row, source_namespace="original" if p == 0 else "reentry"))
            if science:
                recovered = (p == 0 and mask == 1) or (p == 1 and mask == 2)
                common = {
                    k: row[k]
                    for k in (
                        "request_id",
                        "payload_position",
                        "payload_sha256",
                        "seed",
                        "response_sha256",
                    )
                }
                common.update(
                    target_row_identity_sha256=j.digest(row),
                    target_raw_reply_sha256=row["raw_reply_sha256"],
                    target_request_sha256=row["request_sha256"],
                    dispatched=True,
                    skip_reason=None,
                    output_limit_stop=False,
                )
                q = dict(
                    common,
                    axis="qwen",
                    safety="Safe" if recovered else "Unsafe",
                    refusal="Yes" if recovered else "No",
                    categories=["None"],
                )
                jm = dict(common, axis="jailmeter", label=0 if recovered else 1)
                qrows.append(q)
                mrows.append(jm)
                decisions.append(
                    dict(
                        m.panel_rule(row, q, jm),
                        request_id=item["request_id"],
                        qwen_row_identity_sha256=j.digest(q),
                        jailmeter_row_identity_sha256=j.digest(jm),
                        target_row_identity_sha256=j.digest(row),
                    )
                )
            else:
                scores.append(
                    dict(
                        request_id=item["request_id"],
                        target_row_identity_sha256=j.digest(row),
                        response_sha256=row["response_sha256"],
                        content_capability_pass=True,
                        whole_answer_diagnostic_pass=False,
                        whole_answer_is_primary_gate=False,
                    )
                )
    for p, mask in product((0, 1), range(8)):
        value = int((p == 0 and mask == 1) or (p == 1 and mask == 2))
        primary.append(
            dict(payload_position=p, mask_id=mask, status="RECOVERED" if value else "NOT_RECOVERED")
        )
        for op, seed in product(m.OPS, m.SEEDS):
            slices.append(
                dict(payload_position=p, mask_id=mask, neutralizer_id=op, seed=seed, label=value)
            )
            if mask == 0:
                refs.append(
                    dict(
                        payload_position=p,
                        mask=0,
                        operator=op,
                        seed=seed,
                        independent_replication=False,
                        new_inference_calls=0,
                    )
                )
    plan = seal(
        dict(
            population=[dict(payload_position=p) for p in (0, 1)],
            requests=requests,
            bound_materializations=bound,
        ),
        "plan_identity_sha256",
    )
    tables = seal(
        dict(
            primary_rows=primary,
            slice_rows=slices,
            control_qualified_slice_rows=copy.deepcopy(slices),
            control_groups=groups,
        )
    )
    measured = seal(
        dict(
            tables=tables,
            bound_plan_identity_sha256=plan["plan_identity_sha256"],
            panel_decisions=decisions,
            control_scores=scores,
            mask0_screen_references=refs,
        )
    )
    matrix = dict(
        observed_matrix=[[0, 1, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0, 0]],
        known_fit=dict(
            minimum_label_error_count=1,
            one_optimal_fit_known_label_errors=[
                dict(row_index=0, mask_id=1, observed_label=1, prediction=0)
            ],
        ),
    )
    branch = dict(
        neutralizer_seed_tables=[
            dict(neutralizer_id=op, seed=s, analysis=copy.deepcopy(matrix))
            for op, s in product(m.OPS, m.SEEDS)
        ],
        all_six_uniformly_certified_cells=copy.deepcopy(matrix),
        all_six_same_oriented_crossovers=dict(
            strict_shared_crossover_count=1,
            witnesses=[
                dict(
                    payload_positions=[0, 1],
                    mask_ids=[1, 2],
                    labels_row_major=[1, 0, 0, 1],
                    matching_slice_count=6,
                )
            ],
        ),
    )
    analysis = seal(
        dict(
            all_stable_payload_positions=[0, 1],
            second_continuation_execution_identity=m.E,
            upstream_declared_topology_aggregate_identity_sha256=tables["result_identity_sha256"],
            primary=copy.deepcopy(matrix),
            control_qualified_c3=copy.deepcopy(branch),
            **branch,
        )
    )
    target_proof = seal(
        dict(target_rows_sha256=j.digest([t["row"] for t in targets])), "proof_identity_sha256"
    )
    proofs = {
        axis: seal(
            dict(
                rows=rows,
                rows_identity_sha256=j.digest(rows),
                target_composite_proof=target_proof,
                execution_identity=m.E,
                bound_plan_identity_sha256=plan["plan_identity_sha256"],
            ),
            "proof_identity_sha256",
        )
        for axis, rows in (("qwen", qrows), ("jailmeter", mrows))
    }
    flags = dict(
        positions_with_an_original_failed_epoch_judge_response=[0, 4],
        primary_stable_positions=[0, 1],
        stable_positions_not_depending_on_original_failed_epoch=[1],
        original_failed_epoch_request_count=30,
        diagnostic_only_not_primary_population_selection=True,
        original_failed_epoch_reliability_established=False,
    )
    return dict(
        plan=plan,
        measured=measured,
        analysis=analysis,
        targets=targets,
        proofs=proofs,
        dependency_flags=flags,
    )


def test_full_frame_and_all_critical_bindings():
    inputs = fixture()
    before = j.digest(inputs)
    report = m.build(**inputs)
    assert j.digest(inputs) == before
    j.verify_seal(report, "result_identity_sha256")
    assert len(report["target_records"]) == 140
    assert sum(g["count"] for g in report["epoch_mask_operator_seed_groups"]) == 140
    assert {g["physical_epoch_key"] for g in report["epoch_mask_operator_seed_groups"]} == {
        "original:4",
        "reentry:4",
    }
    for rows in report["shared_witness_bindings"].values():
        assert len(rows) == 1 and len(rows[0]["cell_metadata_ids"]) == 24
    assert len(report["one_lexoptimal_fit_error_bindings"]) == 15
    assert len(report["target_records"][0]["matched_control_request_ids"]) == 2
    assert report["fixed_panel_counts"] == {"SAFE": 12, "HARMFUL": 72}
    assert report["failed_screen_epoch_sensitivity"]["surviving_witness_indices"] == {
        "qualified": [],
        "unqualified": [],
    }
    assert report["primary_population_or_labels_changed"] is False


def test_baseline_error_links_only_to_existing_screen_reference():
    inputs = fixture()
    inputs["analysis"]["primary"]["known_fit"]["one_optimal_fit_known_label_errors"] = [
        dict(row_index=0, mask_id=0, observed_label=0, prediction=1)
    ]
    seal(inputs["analysis"])
    errors = m.build(**inputs)["one_lexoptimal_fit_error_bindings"]
    assert all(r.startswith("screen-reference:") for r in errors[0]["cell_metadata_ids"])


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_target",
        "target_plan",
        "axis_hash",
        "matrix",
        "witness",
        "controls",
        "screen_subset",
    ],
)
def test_fail_closed(case):
    inputs = fixture()
    if case == "duplicate_target":
        inputs["targets"][0] = inputs["targets"][1]
    if case == "target_plan":
        inputs["plan"]["requests"][0]["seed"] = 99
        seal(inputs["plan"], "plan_identity_sha256")
    if case == "axis_hash":
        inputs["proofs"]["qwen"]["rows"][0]["refusal"] = "No"
    if case == "matrix":
        inputs["analysis"]["primary"]["observed_matrix"][0][1] = 0
        seal(inputs["analysis"])
    if case == "witness":
        inputs["analysis"]["all_six_same_oriented_crossovers"]["witnesses"][0]["mask_ids"] = [1, 3]
        seal(inputs["analysis"])
    if case == "controls":
        inputs["measured"]["control_scores"][0]["content_capability_pass"] = False
        seal(inputs["measured"])
    if case == "screen_subset":
        inputs["dependency_flags"]["stable_positions_not_depending_on_original_failed_epoch"] = [
            0,
            1,
        ]
    with pytest.raises(ValueError):
        m.build(**inputs)


def test_missing_flags_reports_not_performed():
    inputs = fixture()
    inputs["dependency_flags"] = None
    assert m.build(**inputs)["failed_screen_epoch_sensitivity"]["status"].startswith(
        "NOT_PERFORMED"
    )


def test_control_location_is_not_applicable_and_never_invented():
    report = m.build(**fixture())
    controls = [r["renderer_metadata"] for r in report["target_records"] if r["kind"] == "control"]
    assert len(controls) == 56
    for metadata in controls:
        assert "payload_start_character" not in metadata
        assert metadata["payload_location_status"] == "NOT_APPLICABLE_CONTROL_TASK"
        assert metadata["control_task_location_status"] == "NOT_RECORDED_IN_SAFE_RENDERER"
        assert metadata["control_task_location_metadata"] == {}
    renderer = dict(prompt_utf8_bytes=10, prompt_character_length=10, task_start_character=2)
    metadata = m.render_metadata("control", renderer)
    assert metadata["control_task_location_metadata"] == {"task_start_character": 2}
    assert metadata["control_task_location_status"] == "RECORDED"
    with pytest.raises(ValueError, match="DIAGNOSTIC_RENDER_LOCATION_MISSING"):
        m.render_metadata("science", renderer)


@pytest.mark.parametrize(
    "case", ["negative_index", "missing_length", "missing_location", "unsafe_field"]
)
def test_critical_schema_is_not_silently_invented(case):
    inputs = fixture()
    if case == "negative_index":
        inputs["analysis"]["primary"]["known_fit"]["one_optimal_fit_known_label_errors"][0][
            "row_index"
        ] = -1
        seal(inputs["analysis"])
    if case == "missing_length":
        inputs["plan"]["bound_materializations"][0]["renderer_row"]["prompt_character_length"] = (
            None
        )
        seal(inputs["plan"], "plan_identity_sha256")
    if case == "missing_location":
        inputs["plan"]["bound_materializations"][0]["renderer_row"]["payload_start_character"] = (
            None
        )
        seal(inputs["plan"], "plan_identity_sha256")
    if case == "unsafe_field":
        inputs["dependency_flags"]["prompt"] = "INVENTED_HARMLESS_TEXT"
    if case in {"missing_length", "missing_location"}:
        identity = inputs["plan"]["plan_identity_sha256"]
        inputs["measured"]["bound_plan_identity_sha256"] = identity
        seal(inputs["measured"])
        for proof in inputs["proofs"].values():
            proof["bound_plan_identity_sha256"] = identity
            seal(proof, "proof_identity_sha256")
    expected = {
        "negative_index": "DIAGNOSTIC_FIT_ERROR_INDEX",
        "missing_length": "DIAGNOSTIC_RENDER_LENGTH_MISSING",
        "missing_location": "DIAGNOSTIC_RENDER_LOCATION_MISSING",
        "unsafe_field": "JOURNAL_PRIVATE_FIELD_IN_SAFE",
    }
    with pytest.raises(ValueError, match=expected[case]):
        m.build(**inputs)


def test_existing_fixed_abstention_is_not_relabelled():
    inputs = fixture()
    for axis in inputs["proofs"].values():
        axis["rows"][0].update(
            dispatched=False, skip_reason="TARGET_TRUNCATED", output_limit_stop=False
        )
    q, jm = inputs["proofs"]["qwen"]["rows"][0], inputs["proofs"]["jailmeter"]["rows"][0]
    q.update(safety=None, refusal=None)
    jm["label"] = None
    for axis in inputs["proofs"].values():
        axis["rows_identity_sha256"] = j.digest(axis["rows"])
        seal(axis, "proof_identity_sha256")
    decision = inputs["measured"]["panel_decisions"][0]
    decision.update(
        m.panel_rule(inputs["targets"][0]["row"], q, jm),
        qwen_row_identity_sha256=j.digest(q),
        jailmeter_row_identity_sha256=j.digest(jm),
    )
    seal(inputs["measured"])
    report = m.build(**inputs)
    assert report["fixed_panel_counts"]["ABSTAIN"] == 1
    assert (
        report["target_records"][0]["evaluator_rows"]["qwen"]["skip_reason"] == "TARGET_TRUNCATED"
    )


def test_publish_is_separate_exclusive_and_synthetic(tmp_path, monkeypatch):
    report = m.build(**fixture())
    now = datetime.now(timezone.utc)
    report["stage7_direction"] = seal(
        dict(
            schema_version="pa-reentry-postprocessing-direction-v2",
            execution_identity=m.E,
            stage=7,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=10)).isoformat(),
            direction_ref="SYNTHETIC_ONLY",
        ),
        "direction_identity_sha256",
    )
    seal(report)
    monkeypatch.setattr(m, "load", lambda root, **kwargs: report)
    with pytest.raises(ValueError, match="DIAGNOSTIC_DIRECTION_REFERENCE"):
        m.publish(tmp_path, direction_ref="NOT_THE_CURRENT_DIRECTION")
    path = m.publish(tmp_path, direction_ref="SYNTHETIC_ONLY")
    assert path.parent.name == "stage7-diagnostics"
    assert j.read_json(path) == report
    with pytest.raises((FileExistsError, ValueError)):
        m.publish(tmp_path, direction_ref="SYNTHETIC_ONLY")
