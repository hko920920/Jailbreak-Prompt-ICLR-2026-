"""Invented matrices and temporary SAFE publications only; no actual products."""

from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/audit_pa_stage7_numeric_v2.py"
SPEC = importlib.util.spec_from_file_location("independent_stage7_numeric", SOURCE)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def seal(value, field="result_identity_sha256"):
    value.pop(field, None)
    value[field] = a.digest(value)
    return value


def measured_fixture(positions, *, crossing=False):
    rows, slices, qualified = [], [], []
    for index, position in enumerate(positions):
        matrix_row = [
            0,
            index % 2 if crossing else 0,
            1 - index % 2 if crossing else 0,
            None,
            None,
            None,
            0,
            1,
        ]
        for mask, label in enumerate(matrix_row):
            status = {None: "ABSTAINED", 0: "NOT_RECOVERED", 1: "RECOVERED"}[label]
            rows.append({"payload_position": position, "mask_id": mask, "status": status})
            for operator, seed in itertools.product(a.OPS, a.SEEDS):
                row = {
                    "payload_position": position,
                    "mask_id": mask,
                    "neutralizer_id": operator,
                    "seed": seed,
                    "status": status,
                    "label": label,
                }
                slices.append(row)
                qualified.append({**row, "matched_controls_passed": None if mask == 0 else True})
    return {
        "tables": {
            "primary_rows": rows,
            "slice_rows": slices,
            "control_qualified_slice_rows": qualified,
            "screen_result_identity_sha256": "a" * 64,
        }
    }


def analysis_fixture(measured, positions):
    """Coherent envelope fixture; arithmetic is independently tested against literal enumeration."""
    matrices, input_sha = a.matrix_inputs(measured, positions)
    cache, calculated = {}, {}
    for name, matrix in matrices.items():
        summary = a.summarize_matrix(matrix, cache)
        calculated[name] = {
            **summary,
            "p_independent_lookup": {
                "minimum_known_label_error_count": summary["p_independent_lookup_error"]
            },
            "common_order_incompatible_with_known_labels": summary["known_fit"][
                "minimum_label_error_count"
            ]
            > 0,
            "statistical_rejection_claimed": False,
            "out_of_sample_prediction_claimed": False,
            "independent_witness_count_claimed": False,
        }

    def group(name):
        six = [
            {"neutralizer_id": op, "seed": seed, "analysis": calculated[f"{name}:{op}:{seed}"]}
            for op, seed in itertools.product(a.OPS, a.SEEDS)
        ]
        return {
            "neutralizer_seed_tables": six,
            "all_six_uniformly_certified_cells": calculated[name + ":uniform"],
            "all_six_same_oriented_crossovers": a.shared_crossovers(
                [row["analysis"]["strict_crossovers"] for row in six], positions
            ),
        }

    return {
        "all_stable_payload_positions": list(positions),
        "selected_payload_denominator": len(positions),
        "normalized_analysis_input_identity_sha256": input_sha,
        "control_qualified_frame_supplied": True,
        "reference_code_sha256": a.REFERENCE,
        "primary": calculated["primary"],
        **group("ordinary"),
        "control_qualified_c3": group("qualified"),
        "exact_fit_unique_matrix_count": len(cache),
        "evidence_class": "RESULT_INFORMED_EXPOSED_DEVELOPMENT_NOT_CONFIRMATION",
        **dict.fromkeys(
            (
                "execution_authorized",
                "topology_authorized",
                "paper_validity",
                "scientific_measurement_reverified",
                "statistical_rejection_claimed",
                "payload_semantic_causality_claimed",
            ),
            False,
        ),
        "new_model_calls": 0,
        "historical_private_reads": 0,
        "sealed_reads": 0,
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = a.canonical(value) + b"\n"
    path.write_bytes(raw)
    return a.sha(raw)


@pytest.fixture
def publication(tmp_path, monkeypatch):
    """Entirely invented SAFE proof chain; no production/raw loader is invoked."""
    if os.name == "nt":
        tmp_path = Path("\\\\?\\" + str(tmp_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    direction = seal(
        {
            "schema_version": "pa-reentry-postprocessing-direction-v2",
            "execution_identity": a.EXECUTION,
            "stage": 7,
            "issued_at": (now - timedelta(minutes=5)).isoformat(),
            "expires_at": (now + timedelta(minutes=55)).isoformat(),
            "direction_ref": "SYNTHETIC_ONLY",
        },
        "direction_identity_sha256",
    )
    monkeypatch.setattr(a, "DIRECTION", direction["direction_identity_sha256"])
    shared = {
        "second_continuation_execution_identity": a.EXECUTION,
        "prior_operation_failures": a.FAILURES.copy(),
        **dict.fromkeys(
            (
                "original_operational_gate_passed",
                "first_continuation_operational_gate_passed",
                "archive_relocation_contemporaneous_receipt_available",
                "original_unqualified_pass_claimed",
                "epoch_invariance_claimed",
                "paper_validity",
            ),
            False,
        ),
    }
    measured = measured_fixture(a.POSITIONS)
    analyzed = analysis_fixture(measured, a.POSITIONS)
    measured["tables"].update(schema_version="pa-reentry-measurement-v2", **shared)
    seal(measured["tables"])
    measured.update(schema_version="pa-reentry-joined-measurements-v2", **shared)
    seal(measured)
    analyzed.update(schema_version="pa-reentry-analysis-v2", **shared)
    analyzed["upstream_declared_topology_aggregate_identity_sha256"] = measured["tables"][
        "result_identity_sha256"
    ]
    seal(analyzed)
    base_result = {
        "schema_version": "pa-reentry-finalization-v2",
        **shared,
        "measurements_identity_sha256": measured["result_identity_sha256"],
        "table_identity_sha256": measured["tables"]["result_identity_sha256"],
        "axis_identity_sha256": {"qwen": "b" * 64, "jailmeter": "c" * 64},
    }
    old_result = seal({**base_result, "analysis_complete": False, "analysis_identity_sha256": None})
    new_result = seal(
        {
            **base_result,
            "analysis_complete": True,
            "analysis_identity_sha256": analyzed["result_identity_sha256"],
        }
    )
    old = {"measurements": measured, "result": old_result}
    current = {"measurements": measured, "analysis": analyzed, "result": new_result}
    for products, is_new in ((old, False), (current, True)):
        products["verification"] = seal(
            {
                "schema_version": "pa-reentry-final-verification-v2",
                **shared,
                "actual_raw_verification_by_entrypoint": True,  # invented assertion, never executed
                "product_identity_sha256": {
                    k: v["result_identity_sha256"] for k, v in products.items()
                },
                "product_file_sha256": {
                    k: a.sha(a.canonical(v) + b"\n") for k, v in products.items()
                },
                "result_identity_sha256": products["result"]["result_identity_sha256"],
                "axis_identity_sha256": base_result["axis_identity_sha256"],
                "target_composite_proof": {"synthetic_not_a_real_target_proof": True},
                "analysis_complete": is_new,
                **({"current_stage_direction": direction} if is_new else {}),
            },
            "verification_identity_sha256",
        )
    pins = {}
    for suffix, products in (("measurements-only", old), ("with-analysis", current)):
        directory = tmp_path / a.BASE / suffix
        for name, value in products.items():
            pin = write_json(directory / (name + ".safe.json"), value)
            if suffix == "measurements-only":
                pins[name + ".safe.json"] = pin
        (directory / "publication.lock").write_bytes(b"synthetic lock")
    monkeypatch.setattr(a, "STAGE6_PINS", pins)
    runtime = tmp_path / a.RUNTIME
    write_json(runtime / "direction.safe.json", direction)
    (runtime / "run.lock").write_bytes(b"synthetic lock")
    names = [
        "STAGE7_STARTED",
        "STAGE6_INPUTS_VERIFIED",
        "FROZEN_CONTEXT_LOAD_STARTED",
        "FROZEN_CONTEXT_VERIFIED",
        "ANALYSIS_FINALIZATION_STARTED",
        "STAGE7_FROZEN_ANALYSIS_COMPLETE",
    ]
    for index, name in enumerate(names):
        event = {
            "schema_version": "pa-stage7-wrapper-event-v2",
            "execution_identity": a.EXECUTION,
            "stage": 7,
            "attempt_id": "d" * 32,
            "event": name,
            "at": (now - timedelta(minutes=4) + timedelta(seconds=index)).isoformat(),
            "elapsed_seconds": index,
            "pid": 100,
            "wrapper_sha256": a.WRAPPER,
            "run_analysis": True,
            "new_model_calls": 0,
        }
        if index == 0:
            event["direction"] = direction
        if index == 1:
            event["stage6_file_sha256"] = pins
        if index == 5:
            event.update(
                verification_identity_sha256=current["verification"][
                    "verification_identity_sha256"
                ],
                analysis_identity_sha256=analyzed["result_identity_sha256"],
                result_identity_sha256=new_result["result_identity_sha256"],
                stage6_preserved=True,
                automatic_next_stage=False,
            )
        write_json(runtime / "events" / f"{index:02d}.safe.json", seal(event, "identity_sha256"))
    for relative in (a.SCRIPT, a.TEST):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# synthetic provenance, no code execution\n")
    return {
        "root": tmp_path,
        "current": current,
        "old": old,
        "direction": direction,
        "pin": a.sha(a.canonical(current["verification"]) + b"\n"),
        "now": now.isoformat(),
    }


def test_exhaustive_145_literal_cases():
    assert a.synthetic_self_check() == 145


@pytest.mark.parametrize(
    "matrix,expected",
    [
        ([[0, 1], [1, 0]], 1),
        ([[0, 1, 0], [0, 1, 0]], 0),
        ([[0, 1, None], [None, 0, 1], [1, None, 0]], 1),
        ([[None, None], [None, None]], 0),
        ([[0, 0], [1, 1]], 0),
    ],
)
def test_known_finite_counterexamples(matrix, expected):
    assert a.fit(matrix)["minimum_label_error_count"] == expected


def test_eight_factorial_and_first_cut_unknown_predictions():
    result = a.fit([[None] * 8])
    assert result["orders_evaluated"] == result["optimal_order_count"] == 40320
    assert result["lexicographically_first_optimal_low_to_high_mask_order"] == list(range(8))
    assert result["first_optimal_split_index_by_row"] == [0]
    assert [
        row["prediction"] for row in result["one_optimal_fit_unknown_predictions_not_observations"]
    ] == [1] * 8


@pytest.mark.parametrize("matrix", [[], [[]], [[True]], [[0.0]], [[2]], [[0], [1, 0]], [[0] * 9]])
def test_matrix_domain_fail_closed(matrix):
    with pytest.raises(ValueError):
        a.fit(matrix)


def test_partial_cycle_need_not_have_observed_checkerboard():
    matrix = [[0, 1, None], [None, 0, 1], [1, None, 0]]
    assert a.fit(matrix)["minimum_label_error_count"] == 1
    assert a.crossovers(matrix)["strict_crossover_count"] == 0


def test_shared_witness_orientation_and_dependence():
    cross = a.crossovers([[0, 1], [1, 0], [1, 0]])
    result = a.shared_crossovers([cross] * 6, [3, 10, 44])
    assert result["strict_shared_crossover_count"] == 2
    assert result["maximum_witnesses_sharing_one_cell"] == 2
    reversed_cross = a.crossovers([[1, 0], [0, 1], [0, 1]])
    assert (
        a.shared_crossovers([cross] * 5 + [reversed_cross], [3, 10, 44])[
            "strict_shared_crossover_count"
        ]
        == 0
    )
    assert (
        a.shared_crossovers([cross] * 5 + [a.crossovers([[0, None], [1, 0], [1, 0]])], [3, 10, 44])[
            "strict_shared_crossover_count"
        ]
        == 0
    )


def test_exact_and_loose_unknown_bounds():
    result = a.summarize_matrix([[0, 1, 0, 0, 0, 0, 0, None], [1, 0, 0, 0, 0, 0, 0, 0]], {})
    sensitivity = result["unknown_sensitivity"]
    assert sensitivity["method"] == "EXACT_ALL_COMPLETIONS"
    assert sensitivity["completion_count"] == 2
    assert sensitivity["unknown_imputed_as_observed"] is False
    loose = a.summarize_matrix([[None] * 8], {})["unknown_sensitivity"]
    assert loose["full_table_reoptimized_error_bounds"] == [0, 8]
    assert loose["upper_bound_is_sharp"] is False


def test_all_fifteen_complete_fit_dictionaries():
    measured = measured_fixture([3, 10], crossing=True)
    analyzed = analysis_fixture(measured, [3, 10])
    result = a.verify_analysis(measured, analyzed, positions=[3, 10])
    assert result["matrix_count"] == 15
    assert result["matrices"]["primary"]["known_fit"]["minimum_label_error_count"] == 1
    assert result["shared_orientation"]["qualified"]["strict_shared_crossover_count"] == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("minimum_label_error_count", 0),
        ("orders_evaluated", 1),
        ("optimal_order_count", 40320),
        ("lexicographically_first_optimal_low_to_high_mask_order", list(reversed(range(8)))),
        ("first_optimal_split_index_by_row", [0, 0]),
        ("one_optimal_fit_known_label_errors", []),
        ("one_optimal_fit_unknown_predictions_not_observations", []),
    ],
)
def test_coherent_outer_fit_tampering_rejected(key, value):
    measured = measured_fixture([3, 10], crossing=True)
    analyzed = analysis_fixture(measured, [3, 10])
    analyzed["primary"]["known_fit"][key] = value
    with pytest.raises(ValueError, match="MATRIX_COMPARISON"):
        a.verify_analysis(measured, analyzed, positions=[3, 10])


@pytest.mark.parametrize("branch", ["crossover", "shared", "cache", "lookup", "unknown", "claims"])
def test_nonfit_metric_tampering_rejected(branch):
    measured = measured_fixture([3, 10], crossing=True)
    analyzed = analysis_fixture(measured, [3, 10])
    if branch == "crossover":
        analyzed["primary"]["strict_crossovers"]["witnesses"][0]["labels_row_major"].reverse()
        # Reversal leaves a checkerboard unchanged; instead coherently reverse its orientation.
        analyzed["primary"]["strict_crossovers"]["witnesses"][0]["labels_row_major"] = [1, 0, 0, 1]
    elif branch == "shared":
        analyzed["control_qualified_c3"]["all_six_same_oriented_crossovers"][
            "strict_shared_crossover_count"
        ] = 0
    elif branch == "cache":
        analyzed["exact_fit_unique_matrix_count"] += 1
    elif branch == "lookup":
        analyzed["primary"]["p_independent_lookup"]["minimum_known_label_error_count"] += 1
    elif branch == "unknown":
        analyzed["primary"]["unknown_sensitivity"]["unknown_imputed_as_observed"] = True
    else:
        analyzed["scientific_measurement_reverified"] = True
    with pytest.raises(ValueError):
        a.verify_analysis(measured, analyzed, positions=[3, 10])


@pytest.mark.parametrize("branch", ["missing", "duplicate", "qualified", "primary", "bad_slice"])
def test_exact_frame_and_label_joins(branch):
    measured = measured_fixture([3, 10], crossing=True)
    if branch == "missing":
        measured["tables"]["slice_rows"].pop()
    elif branch == "duplicate":
        measured["tables"]["primary_rows"][-1] = measured["tables"]["primary_rows"][0]
    elif branch == "qualified":
        row = next(
            x for x in measured["tables"]["control_qualified_slice_rows"] if x["mask_id"] == 1
        )
        row["matched_controls_passed"] = False
    elif branch == "primary":
        measured["tables"]["primary_rows"][7]["status"] = "NOT_RECOVERED"
    else:
        measured["tables"]["slice_rows"][0]["label"] = False
    with pytest.raises(ValueError):
        a.matrix_inputs(measured, [3, 10])


def test_complete_synthetic_publication_audit_and_writeonce(publication):
    fixture = publication
    report = a.audit(fixture["root"], fixture["pin"])
    assert report["comparison"]["matrix_count"] == 15
    assert report["synthetic_literal_oracle_cases"] == 145
    assert report["raw_receipts_independently_reverified"] is False
    assert not (fixture["root"] / a.REPORT_BASE).exists()
    path, written = a.publish_report(fixture["root"], report, now=fixture["now"])
    assert written
    raw = (fixture["root"] / path).read_bytes()
    assert a.strict_json(raw) == report
    assert a.publish_report(fixture["root"], report, now=fixture["now"]) == (path, False)


@pytest.mark.parametrize(
    "case",
    [
        "proof_pin",
        "stage6_whitespace",
        "analysis_link",
        "old_failure",
        "event_schema",
        "event_pid",
        "event_elapsed",
        "event_stage",
        "no_complete_event",
        "unexpected_product",
        "pending",
    ],
)
def test_publication_corruption_preserved(publication, case):
    root, pin = publication["root"], publication["pin"]
    if case == "proof_pin":
        pin = "0" * 64
    elif case == "stage6_whitespace":
        path = root / a.BASE / "measurements-only/measurements.safe.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif case in ("analysis_link", "old_failure"):
        # Rehash all new envelope links, leaving the externally supplied pin updated:
        # the semantic cross-stage assertion must still reject this coherent alteration.
        current = copy.deepcopy(publication["current"])
        if case == "analysis_link":
            current["analysis"]["upstream_declared_topology_aggregate_identity_sha256"] = "f" * 64
            seal(current["analysis"])
            current["result"]["analysis_identity_sha256"] = current["analysis"][
                "result_identity_sha256"
            ]
            seal(current["result"])
        else:
            current["analysis"]["original_operational_gate_passed"] = True
            seal(current["analysis"])
        proof = current["verification"]
        for name in ("measurements", "result", "analysis"):
            proof["product_identity_sha256"][name] = current[name]["result_identity_sha256"]
            proof["product_file_sha256"][name] = write_json(
                root / a.BASE / "with-analysis" / (name + ".safe.json"), current[name]
            )
        proof["result_identity_sha256"] = current["result"]["result_identity_sha256"]
        pin = write_json(
            root / a.BASE / "with-analysis/verification.safe.json",
            seal(proof, "verification_identity_sha256"),
        )
    elif case.startswith("event_"):
        path = root / a.RUNTIME / "events/03.safe.json"
        value = json.loads(path.read_bytes())
        field = case.removeprefix("event_")
        value[{"schema": "schema_version", "elapsed": "elapsed_seconds"}.get(field, field)] = {
            "schema": "wrong",
            "pid": 101,
            "elapsed": -1,
            "stage": 6,
        }[field]
        write_json(path, seal(value, "identity_sha256"))
    elif case == "no_complete_event":
        (root / a.RUNTIME / "events/05.safe.json").unlink()
    elif case == "unexpected_product":
        (root / a.BASE / "with-analysis/unexpected.safe.json").write_bytes(b"{}\n")
    else:
        (root / a.BASE / "with-analysis/result.safe.json.pending").write_bytes(b"evidence")
    with pytest.raises(ValueError):
        a.load_products(root, pin)
    assert not (root / a.REPORT_BASE).exists()


@pytest.mark.parametrize("raw", [b'{"a":1,"a":1}\n', b'{ "a":1}\n', b'{"a":1}\r\n'])
def test_noncanonical_and_duplicate_json_rejected(raw):
    with pytest.raises(ValueError):
        a.strict_json(raw)


@pytest.mark.parametrize(
    "relative", ["../outside", "/absolute", "a\\b", "a:b", "a/./b", "a/../b", "a./b"]
)
def test_path_scope(relative, tmp_path):
    with pytest.raises(ValueError, match="PATH_SCOPE"):
        a.safe_path(tmp_path, relative, missing=True)


def test_input_double_snapshot_and_single_read_mutation(tmp_path):
    write_json(tmp_path / "data/value.safe.json", {"n": 1})
    snap = a.Snapshot(tmp_path)
    snap.directory("data", ["value.safe.json"])
    snap.read("data/value.safe.json")
    snap.unchanged()
    write_json(tmp_path / "data/value.safe.json", {"n": 2})
    with pytest.raises(ValueError, match="INPUT_CHANGED"):
        snap.read("data/value.safe.json")
    with pytest.raises(ValueError, match="INPUT_CHANGED"):
        snap.unchanged()


def test_directory_census_change(tmp_path):
    (tmp_path / "data").mkdir()
    snap = a.Snapshot(tmp_path)
    snap.directory("data")
    (tmp_path / "data/new").write_bytes(b"new")
    with pytest.raises(ValueError, match="DIRECTORY_CHANGED"):
        snap.unchanged()


def test_symlink_rejected(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    try:
        (tmp_path / "link").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation privilege unavailable; no OS changes requested")
    with pytest.raises(ValueError, match="REPARSE"):
        a.safe_path(tmp_path, "link", missing=True)


@pytest.mark.parametrize("case", ["conflict", "pending", "expired", "claim"])
def test_optional_report_preserves_conflicts_and_authority(publication, case):
    root = publication["root"]
    report = a.audit(root, publication["pin"])
    relative = a.REPORT_BASE + "/" + publication["pin"] + "/audit.safe.json"
    path = root / relative
    now = publication["now"]
    if case in ("conflict", "pending"):
        path.parent.mkdir(parents=True, exist_ok=True)
        if case == "pending":
            path = Path(str(path) + ".pending")
        path.write_bytes(b"preserved evidence")
    elif case == "expired":
        now = (a.stamp(report["direction"]["expires_at"]) + timedelta(seconds=1)).isoformat()
    else:
        report["raw_receipts_independently_reverified"] = True
        seal(report)
    with pytest.raises(ValueError):
        a.publish_report(root, report, now=now)
    if case in ("conflict", "pending"):
        assert path.read_bytes() == b"preserved evidence"
    else:
        assert not path.exists()


def test_main_readonly_and_safe_failure(publication, monkeypatch, capsys):
    args = ["--root", str(publication["root"]), "--verification-sha256", publication["pin"]]
    assert a.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["report_written"] is False and result["report_path"] is None
    assert not (publication["root"] / a.REPORT_BASE).exists()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic secret raw text must never print")

    monkeypatch.setattr(a, "audit", fail)
    assert a.main(args) == 1
    output = capsys.readouterr().out
    assert "synthetic secret" not in output
    assert json.loads(output)["error_code"] == "NUMERIC_SAFE_FAILURE"


@pytest.mark.parametrize("relative", [a.SCRIPT, a.TEST])
def test_publication_rechecks_source_manifest(publication, relative):
    root = publication["root"]
    report = a.audit(root, publication["pin"])
    (root / relative).write_bytes(b"# changed after calculation\n")
    with pytest.raises(ValueError, match="PUBLISH_INPUT_CHANGED"):
        a.publish_report(root, report, now=publication["now"])
    assert not (root / a.REPORT_BASE).exists()
