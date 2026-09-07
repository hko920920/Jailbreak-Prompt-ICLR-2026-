"""Synthetic tables/source closures only; never read actual experiment products."""

import copy
import hashlib
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_pa_stage7_baselines_v2 as m  # noqa: E402

R, N, U = "RECOVERED", "NOT_RECOVERED", "UNKNOWN"


@pytest.fixture(scope="module")
def functions():
    # Reads only the explicitly pinned five SOURCE/test-source files.
    return m.load_functions(ROOT)


def fixture_rows(statuses, functions, positions=(0,)):
    primary, families = [], []
    for position in positions:
        table = dict(enumerate(statuses))
        exact = functions.comparison.exhaustive_family(table)
        primary.extend(
            {"payload_position": position, "mask_id": mask, "status": value}
            for mask, value in table.items()
        )
        families.append(
            {
                "payload_position": position,
                "certified_minimal_masks": exact["certified_minimal_masks"],
                "unresolved_minimal_candidates": exact["unresolved_minimal_candidates"],
                "robust_recovery_masks": exact["recovered_masks"],
                "unknown_masks": len(exact["unknown_masks"]),
                "known_masks": 8 - len(exact["unknown_masks"]),
                "truth_table_fully_identified": not exact["unknown_masks"],
                "minimum_certified_recovery_order": min(
                    (mask.bit_count() for mask in exact["certified_minimal_masks"]), default=None
                ),
            }
        )
    return primary, families


def compare(statuses, functions, positions=(0,)):
    return m.compare_tables(
        *fixture_rows(statuses, functions, positions), functions, source_identity_sha256="a" * 64
    )


def test_only_pinned_pure_ast_definitions_no_old_runner_import(functions):
    assert set(vars(functions.d2)) == m.D2_FUNCTIONS
    assert functions.comparison.UNIT_IDS == m.UNITS
    assert len(functions.comparison.ORDERS) == 6
    assert "run_topology_d2_micro_pilot" not in sys.modules
    assert functions.d2.greedy_backward_baseline.__globals__.get("screen") is None
    assert all(pin["path"] in m.PINNED for pin in functions.source_pins)


def test_ab_exact_minimum_singleton_misses_and_fixed_paths_find(functions):
    result = compare([N, N, N, R, N, N, N, R], functions)
    assert result["certified_family_denominator"] == 1
    assert result["payloads_with_certified_family"] == 1
    assert result["fixed_abc_method_totals"]["all_singletons"]["certified_minima_missed"] == 1
    for name in ("greedy_forward", "greedy_backward"):
        value = result["per_payload"][0]["methods"][name]
        assert value["predicted_masks"] == [3]
        assert value["certified_minima_returned"] == [3]
        assert value["certified_minima_missed"] == []
        assert not value["search_trace_alone_claims_strict_minimality"]


def test_disconnected_singletons_expose_one_minimal_not_strict_minimal(functions):
    result = compare([N, R, R, N, R, N, N, R], functions)
    row = result["per_payload"][0]
    assert row["certified_minimal_masks"] == [1, 2, 4]
    backward = row["methods"]["greedy_backward"]
    assert backward["predicted_masks"] == [7]
    assert backward["known_nonminimal_returned"] == [7]
    assert backward["certified_minima_missed"] == [1, 2, 4]
    assert backward["historical_return_status_not_a_global_certificate"] == "COMPLETE"
    assert "one_minimal_certificate" not in backward
    assert backward["historical_one_minimal_flag_not_promoted"] is True
    assert result["all_six_union_totals"]["certified_minima_missed_as_terminals"] == 3


@pytest.mark.parametrize(
    "unknown",
    [U, "ABSTAINED", "CAPABILITY_CONFOUNDED", "INCOMPLETE", "TRUNCATED", "INVALID_INTERVENTION"],
)
def test_unknown_not_negative_and_no_singleton_completeness_claim(functions, unknown):
    result = compare([N, unknown, N, R, N, N, N, R], functions)
    row = result["per_payload"][0]
    assert row["certified_minimal_masks"] == []
    assert row["unresolved_minimal_candidates"] == [3]
    assert row["unknown_masks"] == [1]
    singleton = row["methods"]["all_singletons"]
    assert singleton["predicted_masks"] == []
    assert singleton["queried_unknown_masks"] == [1]
    assert "COMPLETE" not in singleton["historical_return_status_not_a_global_certificate"]
    assert not singleton["unknown_means_not_recovered"]
    forward = row["methods"]["greedy_forward"]
    assert forward["unresolved_candidates_returned"] == [3]
    assert forward["certified_minima_returned"] == []


def test_greedy_neighbor_audit_count_differs_from_six_order_path(functions):
    result = compare([N, N, N, N, R, R, N, R], functions)
    backward = result["per_payload"][0]["methods"]["greedy_backward"]
    trace = backward["unique_query_trace_including_reference_neighbor_audit"]
    assert [row["mask_id"] for row in trace] == [7, 6, 5, 1, 4]
    assert backward["oracle_distinct_query_count"] == 5
    abc = result["existing_all_six_order_comparison"]["per_payload"][0]["orders"][0]
    assert abc["oracle_queried_masks_in_order"] == [7, 6, 5, 1]
    assert abc["oracle_query_count_including_initial7"] == 4
    assert backward["known_nonminimal_returned"] == [5]


def test_no_start_from_unknown_full_set_preserves_internal_minimum(functions):
    result = compare([N, R, N, N, N, N, N, U], functions)
    backward = result["per_payload"][0]["methods"]["greedy_backward"]
    assert backward["predicted_masks"] == []
    assert backward["queried_unknown_masks"] == [7]
    assert backward["certified_minima_missed"] == [1]
    assert result["fixed_abc_method_totals"]["all_singletons"]["certified_minima_returned"] == 1


def test_full_population_not_only_payloads_with_certificates(functions):
    primary1, families1 = fixture_rows([N] * 8, functions, (1,))
    primary2, families2 = fixture_rows([N, N, N, R, N, N, N, R], functions, (3,))
    result = m.compare_tables(
        primary1 + primary2, families1 + families2, functions, source_identity_sha256="a" * 64
    )
    assert result["payload_denominator"] == 2
    assert result["primary_cell_denominator"] == 16
    assert result["payloads_with_certified_family"] == 1
    assert [row["payload_position"] for row in result["per_payload"]] == [1, 3]


@pytest.mark.parametrize(
    "field",
    [
        "certified_minimal_masks",
        "unresolved_minimal_candidates",
        "known_masks",
        "unknown_masks",
        "robust_recovery_masks",
        "truth_table_fully_identified",
        "minimum_certified_recovery_order",
    ],
)
def test_stored_family_mismatch_is_rejected(functions, field):
    primary, families = fixture_rows([N, N, N, R, N, N, N, R], functions)
    families[0][field] = None
    with pytest.raises(ValueError, match="BASELINE_STAGE6_CERTIFIED_FAMILY_MISMATCH"):
        m.compare_tables(primary, families, functions, source_identity_sha256="a" * 64)


def test_row_permutation_does_not_select_an_order_or_mutate_inputs(functions):
    primary, families = fixture_rows([N, R, R, N, R, N, N, R], functions, (0, 44))
    saved = copy.deepcopy((primary, families))
    first = m.compare_tables(primary, families, functions, source_identity_sha256="a" * 64)
    second = m.compare_tables(
        primary[::-1], families[::-1], functions, source_identity_sha256="a" * 64
    )
    assert first == second and (primary, families) == saved
    assert first["existing_all_six_order_comparison"]["all_six_predetermined_orders_reported"]


def test_pure_comparison_does_not_read_or_write_files(functions, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure comparison attempted file access")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    compare([N, N, N, R, N, N, N, R], functions)


@pytest.mark.parametrize(
    "path",
    ["../outside", "/outside", "C:/outside", "docs\\x", "docs/../x", "docs//x", "docs/name. "],
)
def test_path_alias_or_escape_rejected(tmp_path, path):
    with pytest.raises(ValueError, match="BASELINE_PATH"):
        m.owned(tmp_path, path)


@pytest.mark.parametrize(
    "path", ["artifacts/private/anything.json", "data/sealed.json", "docs/unlisted.safe.json"]
)
def test_unapproved_read_rejected_without_access(tmp_path, path):
    with pytest.raises(ValueError, match="BASELINE_READ_OUTSIDE"):
        m.read_file(tmp_path, path)


def test_exact_source_pin_detects_changed_code(tmp_path):
    relative = "scripts/run_topology_d2_micro_pilot.py"
    path = tmp_path / relative
    path.parent.mkdir()
    path.write_text("raise RuntimeError('NEVER EXECUTE')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="BASELINE_SOURCE_OR_INPUT_PIN_CHANGED"):
        m.read_file(tmp_path, relative)


def test_ast_excludes_unselected_module_level_execution():
    source = b"raise RuntimeError('not selected')\ndef allowed():\n    return 7\n"
    closure = m.ast_closure(source, {"allowed"})
    assert closure.allowed() == 7
    with pytest.raises(ValueError, match="BASELINE_AST_CLOSURE_MISSING"):
        m.ast_closure(source, {"missing"})


def test_ast_rejects_imports_inside_selected_function():
    with pytest.raises(ValueError, match="BASELINE_AST_NONPURE_DEPENDENCY"):
        m.ast_closure(b"def selected():\n    import pathlib\n", {"selected"})


def direction(now, *, stage=7):
    return m.seal(
        {
            "execution_identity": m.EXECUTION,
            "stage": stage,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=2)).isoformat(),
        },
        "direction_identity_sha256",
    )


def test_direction_scope_expiry_and_exact_current_receipt():
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    value = direction(now)
    m.validate_direction(value, now=now, require_current_identity=False)
    with pytest.raises(ValueError, match="BASELINE_CURRENT_STAGE7_DIRECTION_CHANGED"):
        m.validate_direction(value, now=now)
    with pytest.raises(ValueError, match="BASELINE_STAGE7_DIRECTION_EXPIRED"):
        m.validate_direction(value, now=now + timedelta(hours=3), require_current_identity=False)
    with pytest.raises(ValueError, match="BASELINE_STAGE7_DIRECTION_REQUIRED"):
        m.validate_direction(direction(now, stage=6), now=now, require_current_identity=False)


def test_seal_tampering_is_rejected():
    value = m.seal({"a": 1})
    value["a"] = 2
    with pytest.raises(ValueError, match="BASELINE_SEAL_CHANGED"):
        m.verify_seal(value)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}\n', b'{"a":{"b":1,"b":1}}\n'])
def test_duplicate_json_keys_are_rejected_even_if_semantically_resealed(raw):
    with pytest.raises(ValueError, match="BASELINE_DUPLICATE_JSON_KEY"):
        m.parse_safe_json(raw)


@pytest.mark.parametrize("raw", [b'{ "a": 1 }\n', b'{"a":1}', b'{"a":1}\n\n'])
def test_stage7_noncanonical_raw_bytes_are_rejected(raw):
    assert m.parse_safe_json(raw) == {"a": 1}
    with pytest.raises(ValueError, match="BASELINE_SAFE_JSON_NOT_CANONICAL"):
        m.parse_safe_json(raw, require_canonical=True)


def test_canonical_json_accepted_and_nonfinite_rejected():
    assert m.parse_safe_json(b'{"a":1}\n', require_canonical=True) == {"a": 1}
    with pytest.raises(ValueError, match="BASELINE_NONFINITE_JSON_NUMBER"):
        m.parse_safe_json(b'{"a":NaN}\n')


def test_publish_is_not_called_without_write_flag(monkeypatch):
    monkeypatch.setattr(
        m,
        "load_report",
        lambda root: {"result_identity_sha256": "a" * 64, "comparison": {"payload_denominator": 1}},
    )
    monkeypatch.setattr(m, "publish", lambda *args: pytest.fail("unexpected publication"))
    assert m.main([]) == 0


def make_products(measured, analyzed, current_direction):
    result = m.seal(
        {
            "analysis_identity_sha256": analyzed["result_identity_sha256"] if analyzed else None,
            "measurements_identity_sha256": measured["result_identity_sha256"],
            "table_identity_sha256": measured["tables"]["result_identity_sha256"],
        }
    )
    products = {"measurements": measured, "analysis": analyzed, "result": result}
    core = {key: value for key, value in products.items() if value is not None}
    products["verification"] = m.seal(
        {
            "target_composite_proof": m.seal({"synthetic_target": 1}, "proof_identity_sha256"),
            "axis_identity_sha256": {"qwen": "a" * 64, "jailmeter": "b" * 64},
            "actual_raw_verification_by_entrypoint": True,
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
            "paper_validity": False,
            "second_continuation_execution_identity": m.EXECUTION,
            "analysis_complete": analyzed is not None,
            "current_stage_direction": current_direction,
            "product_identity_sha256": {
                key: value["result_identity_sha256"] for key, value in core.items()
            },
            "product_file_sha256": {
                key: hashlib.sha256(m.canonical(value) + b"\n").hexdigest()
                for key, value in core.items()
            },
        },
        "verification_identity_sha256",
    )
    return products


def synthetic_bundle():
    measured = m.seal({"tables": m.seal({"invented_table": 1})})
    analyzed = m.seal(
        {
            "upstream_declared_topology_aggregate_identity_sha256": measured["tables"][
                "result_identity_sha256"
            ]
        }
    )
    current_direction = {"synthetic_stage7_direction": True}
    return (
        make_products(measured, None, {"synthetic_stage6_direction": True}),
        make_products(measured, analyzed, current_direction),
        current_direction,
    )


def reseal_proof(products):
    old = products["verification"]
    products["verification"] = m.seal(
        {key: value for key, value in old.items() if key != "verification_identity_sha256"},
        "verification_identity_sha256",
    )


def test_synthetic_stage6_stage7_product_joins():
    m.validate_bundle(*synthetic_bundle())


def test_resealed_analysis_with_stale_upstream_table_is_rejected():
    stage6, stage7, current_direction = synthetic_bundle()
    bad_analysis = m.seal({"upstream_declared_topology_aggregate_identity_sha256": "f" * 64})
    stage7 = make_products(stage7["measurements"], bad_analysis, current_direction)
    with pytest.raises(ValueError, match="BASELINE_ANALYSIS_OR_TABLE_JOIN_CHANGED"):
        m.validate_bundle(stage6, stage7, current_direction)


@pytest.mark.parametrize(
    "field", ["target_composite_proof", "axis_identity_sha256", "current_stage_direction"]
)
def test_resealed_changed_stage7_context_is_rejected(field):
    stage6, stage7, current_direction = synthetic_bundle()
    value = (
        m.seal({"synthetic_target": 2}, "proof_identity_sha256")
        if field == "target_composite_proof"
        else {"different": True}
    )
    stage7["verification"][field] = value
    reseal_proof(stage7)
    with pytest.raises(ValueError, match="BASELINE_STAGE6_STAGE7_INPUTS_OR_DIRECTION_CHANGED"):
        m.validate_bundle(stage6, stage7, current_direction)


def test_original_operational_failure_cannot_be_resealed_as_pass():
    stage6, stage7, current_direction = synthetic_bundle()
    stage7["verification"]["original_operational_gate_passed"] = True
    reseal_proof(stage7)
    with pytest.raises(ValueError, match="BASELINE_UPSTREAM_SCOPE_CHANGED"):
        m.validate_bundle(stage6, stage7, current_direction)


def test_publication_is_exclusive_and_handles_windows_long_paths(tmp_path, monkeypatch):
    root = tmp_path.joinpath(*(["synthetic_long_segment" * 2] * 3))
    root.mkdir(parents=True)
    report = m.seal({"stage7_analysis_identity_sha256": "c" * 64})
    monkeypatch.setattr(m, "reverify", lambda root, value: m.verify_seal(value))
    relative = m.publish(root, report)
    path = m.owned(root, relative)
    assert path.read_bytes() == m.canonical(report) + b"\n"
    if os.name == "nt":
        assert str(path).startswith("\\\\?\\")
    with pytest.raises(ValueError, match="BASELINE_OUTPUT_ALREADY_EXISTS"):
        m.publish(root, report)


def test_change_after_pending_write_prevents_publication(tmp_path, monkeypatch):
    report = m.seal({"stage7_analysis_identity_sha256": "d" * 64})
    checks = []

    def reverify(root, value):
        checks.append(1)
        if len(checks) == 2:
            raise ValueError("BASELINE_INPUT_CHANGED_AFTER_COMPARISON")

    monkeypatch.setattr(m, "reverify", reverify)
    with pytest.raises(ValueError, match="BASELINE_INPUT_CHANGED_AFTER_COMPARISON"):
        m.publish(tmp_path, report)
    relative = f"{m.BASE}/stage7-baselines/{'d' * 64}/baseline.safe.json"
    assert not m.owned(tmp_path, relative).exists()
    assert m.owned(tmp_path, relative + ".pending").exists()


def test_ancestor_reparse_point_is_rejected(tmp_path, monkeypatch):
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path.name == "synthetic_junction":
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=1024)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="BASELINE_LINK_OR_REPARSE_POINT"):
        m.owned(tmp_path, "synthetic_junction/child.safe.json")
