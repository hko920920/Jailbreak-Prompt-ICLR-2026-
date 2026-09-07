"""Synthetic status tables only; no actual corpus, results, GPU or model access."""

import ast
import copy
import importlib.util
import itertools
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/pa_llama_topology_search_comparison_v1.py"
SPEC = importlib.util.spec_from_file_location("synthetic_search_comparison", SOURCE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
SHA = "a" * 64
R, N, U = "RECOVERED", "NOT_RECOVERED", "UNKNOWN"


def rows_for(statuses, positions=(1,)):
    return [{"payload_position": position, "mask_id": mask, "status": statuses[mask]}
            for position, mask in itertools.product(positions, range(8))]


def compare(statuses, positions=(1,)):
    return m.compare_search(rows_for(statuses, positions), all_payload_positions=positions,
                            source_identity_sha256=SHA)


def order(result, bits):
    return next(row for row in result["per_payload"][0]["orders"]
                if row["unit_bit_order"] == list(bits))


def test_exact_six_orders_and_units_no_ddmin_or_execution_claim():
    result = compare([N, R, R, R, N, R, R, R])
    assert result["unit_ids"] == ["AIMDecorator", "RefusalSuppressionDecorator",
                                  "AffirmativePrefixInjectionDecorator"]
    assert [row["unit_bit_order"] for row in result["per_payload"][0]["orders"]] == [
        list(value) for value in itertools.permutations(range(3))]
    assert result["per_payload"][0]["all_six_order_union"]["terminal_recovery_masks"] == [1, 2]
    for field in ("ddmin_reproduction_claimed", "novel_algorithm_claimed", "scientific_gate",
                  "execution_authorized", "paper_validity", "scientific_measurement_reverified"):
        assert result[field] is False
    assert result["new_model_calls"] == result["private_input_reads"] == 0
    assert result["descriptive_oracle_accounting"][
        "six_order_query_count_without_cross_order_cache"] == 24


def test_one_pass_can_finish_at_a_known_nonminimal_recovery_without_retesting():
    result = compare([N, N, N, N, R, R, N, R])
    first = order(result, (0, 1, 2))
    assert first["oracle_queried_masks_in_order"] == [7, 6, 5, 1]
    assert first["terminal_recovery_mask"] == 5
    assert first["terminal_minimality_using_exhaustive_reference"] == (
        "KNOWN_NONMINIMAL_BY_EXHAUSTIVE_TABLE")
    alternate = order(result, (1, 0, 2))
    assert alternate["oracle_queried_masks_in_order"] == [7, 5, 4, 0]
    assert alternate["terminal_recovery_mask"] == 4
    assert alternate["terminal_minimality_using_exhaustive_reference"] == (
        "CERTIFIED_BY_EXHAUSTIVE_TABLE")


def test_all_six_paths_can_miss_all_three_disconnected_minima():
    result = compare([N, R, R, N, R, N, N, R])
    payload = result["per_payload"][0]
    assert payload["exhaustive_reference"]["certified_minimal_masks"] == [1, 2, 4]
    assert payload["all_six_order_union"]["terminal_recovery_masks"] == [7]
    assert payload["all_six_order_union"]["certified_minima_missed_as_terminals"] == [1, 2, 4]
    assert payload["all_six_order_union"][
        "exhaustive_recoveries_not_observed_in_any_trace"] == [1, 2, 4]


@pytest.mark.parametrize("initial", [N, *sorted(m.UNKNOWN)])
def test_no_start_from_nonrecovered_or_unknown7_despite_interior_recovery(initial):
    result = compare([N, R, N, R, N, N, N, initial])
    payload = result["per_payload"][0]
    for row in payload["orders"]:
        assert row["oracle_queried_masks_in_order"] == [7]
        assert row["oracle_query_count_including_initial7"] == 1
        assert row["terminal_recovery_mask"] is None
        assert row["start_status"] == (
            "CANNOT_START_NOT_RECOVERED" if initial == N else "CANNOT_START_UNKNOWN")
    assert payload["all_six_order_union"]["certified_minima_missed_as_terminals"] == [1]
    assert payload["all_six_order_union"]["oracle_query_count_without_cross_order_cache"] == 6
    assert payload["all_six_order_union"]["oracle_distinct_queried_mask_count_within_payload"] == 1
    assert payload["constant_ab"]["status"] == R


@pytest.mark.parametrize("unknown", sorted(m.UNKNOWN))
def test_unknown_blocks_move_but_never_certifies_failure_or_minimality(unknown):
    result = compare([N, N, N, N, N, N, unknown, R])
    first = order(result, (0, 1, 2))
    assert first["oracle_queried_masks_in_order"] == [7, 6, 5, 3]
    assert first["trace"][1]["status"] == unknown
    assert first["trace"][1]["move_accepted"] is False
    assert first["trace"][1]["current_before"] == first["trace"][1]["current_after"] == 7
    assert first["oracle_queries_with_unknown_status"] == [6]
    assert first["terminal_minimality_using_exhaustive_reference"] == (
        "UNRESOLVED_UNKNOWN_STRICT_SUBSETS")
    family = result["per_payload"][0]["exhaustive_reference"]
    assert family["certified_minimal_masks"] == []
    assert family["unresolved_minimal_candidates"] == [7]


def test_unknown_strict_subset_not_queried_still_blocks_exhaustive_certificate():
    result = compare([N, U, N, N, N, N, N, R])
    assert all(1 not in row["oracle_queried_masks_in_order"]
               for row in result["per_payload"][0]["orders"])
    assert all(row["terminal_minimality_using_exhaustive_reference"] ==
               "UNRESOLVED_UNKNOWN_STRICT_SUBSETS"
               for row in result["per_payload"][0]["orders"])


def test_all_128_binary_tables_match_independent_set_based_oracle():
    universe = frozenset(range(3))
    sets = {mask: frozenset(unit for unit in universe if mask & (1 << unit))
            for mask in range(8)}
    for bits in itertools.product((N, R), repeat=7):
        statuses = [N, *bits]
        result = compare(statuses)
        payload = result["per_payload"][0]
        recovering = {sets[mask] for mask in range(8) if statuses[mask] == R}
        minima = sorted(mask for mask in range(8) if sets[mask] in recovering
                        and not any(other < sets[mask] for other in recovering))
        assert payload["exhaustive_reference"]["certified_minimal_masks"] == minima
        assert payload["exhaustive_reference"]["unresolved_minimal_candidates"] == []
        for tested in payload["orders"]:
            current = universe if universe in recovering else None
            queried = [7]
            if current is not None:
                for unit in tested["unit_bit_order"]:
                    candidate = current - {unit}
                    queried.append(sum(2 ** index for index in candidate))
                    if candidate in recovering:
                        current = candidate
            terminal = None if current is None else sum(2 ** index for index in current)
            assert tested["oracle_queried_masks_in_order"] == queried
            assert tested["terminal_recovery_mask"] == terminal


def test_all2187_partial_tables_keep_unknown_out_of_minimum_certificates():
    sets = {mask: frozenset(unit for unit in range(3) if mask & (1 << unit))
            for mask in range(8)}
    for values in itertools.product((N, R, U), repeat=7):
        statuses = dict(enumerate([N, *values]))
        # Independent set-inclusion definition, not the implementation's bit predicate.
        candidates, certified = [], []
        for mask, subset in sets.items():
            smaller = [other for other in sets if sets[other] < subset]
            if statuses[mask] != R or any(statuses[other] == R for other in smaller):
                continue
            candidates.append(mask)
            if all(statuses[other] == N for other in smaller):
                certified.append(mask)
        observed = m.exhaustive_family(statuses)
        assert observed["certified_minimal_masks"] == certified
        assert observed["unresolved_minimal_candidates"] == [
            mask for mask in candidates if mask not in certified]


def test_complete45_population_no_rowdrop_and_permutation_invariance():
    positions = list(range(45))
    rows = rows_for([N, U, N, R, N, N, N, R], positions)
    original = copy.deepcopy(rows)
    first = m.compare_search(rows, all_payload_positions=positions, source_identity_sha256=SHA)
    second = m.compare_search(list(reversed(rows)), all_payload_positions=positions[::-1],
                              source_identity_sha256=SHA)
    assert first == second and rows == original
    assert first["payload_count"] == 45 and len(first["primary_status_rows"]) == 360
    assert [row["payload_position"] for row in first["per_payload"]] == positions
    assert first["constant_ab"]["payload_denominator"] == 45
    assert first["constant_ab"]["recovery_fraction_lower"] == 1.0
    assert first["result_identity_sha256"] == m.digest({
        key: value for key, value in first.items() if key != "result_identity_sha256"})


def test_constant_ab_unknown_bounds_preserve_all_three_payloads():
    rows = rows_for([N, N, N, N, N, N, N, N], (2, 9, 44))
    for row in rows:
        if row["mask_id"] == 3:
            row["status"] = {2: R, 9: N, 44: "INCOMPLETE"}[row["payload_position"]]
    result = m.compare_search(rows, all_payload_positions=[2, 9, 44], source_identity_sha256=SHA)
    assert result["constant_ab"]["recovery_fraction_lower"] == 1 / 3
    assert result["constant_ab"]["recovery_fraction_possible_upper"] == 2 / 3
    assert result["constant_ab"]["status_counts"] == {"INCOMPLETE": 1, N: 1, R: 1}


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra_field", "bool_mask",
                                      "bool_position", "unknown_position", "status_type",
                                      "status_value", "baseline_promote"])
def test_malformed_or_reframed_rows_are_rejected(mutation):
    rows = rows_for([N] * 8)
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[7] = copy.deepcopy(rows[6])
    elif mutation == "extra_field":
        rows[0]["prompt"] = "Synthetic forbidden field"
    elif mutation == "bool_mask":
        rows[1]["mask_id"] = True
    elif mutation == "bool_position":
        rows[0]["payload_position"] = True
    elif mutation == "unknown_position":
        rows[0]["payload_position"] = 2
    elif mutation == "status_type":
        rows[0]["status"] = []
    elif mutation == "status_value":
        rows[0]["status"] = "SAFE"
    else:
        rows[0]["status"] = R
    with pytest.raises(m.ComparisonError):
        m.compare_search(rows, all_payload_positions=[1], source_identity_sha256=SHA)


@pytest.mark.parametrize("population", [[], [1, 1], [True], [-1], [45], "1", None])
def test_exact_explicit_population_required(population):
    with pytest.raises(m.ComparisonError):
        m.compare_search(rows_for([N] * 8), all_payload_positions=population,
                          source_identity_sha256=SHA)


def test_actual_screen_zero_based_boundary_accepts0_rejects45():
    result = compare([N] * 8, (0, 44))
    assert result["all_payload_positions"] == [0, 44]
    with pytest.raises(m.ComparisonError, match="PAYLOAD_POSITION_INVALID"):
        compare([N] * 8, (45,))


@pytest.mark.parametrize("identity", [None, "a" * 63, "A" * 64, 1, "private/path"])
def test_source_identity_is_required_but_not_claimed_authenticated(identity):
    with pytest.raises(m.ComparisonError):
        m.compare_search(rows_for([N] * 8), all_payload_positions=[1],
                          source_identity_sha256=identity)
    result = compare([N] * 8)
    assert result["upstream_source_artifact_authenticated"] is False
    assert result["caller_population_authenticated_against_screen"] is False


def test_no_file_or_inference_access_even_for45_tables(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure comparator must not open files")
    monkeypatch.setattr("builtins.open", forbidden)
    result = compare([N] * 8, list(range(45)))
    assert result["new_model_calls"] == 0


def test_source_has_only_pure_stdlib_imports_and_no_execution_entrypoint():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    modules = {name.name.split(".")[0] for node in ast.walk(tree)
               if isinstance(node, ast.Import) for name in node.names}
    modules |= {node.module.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)}
    assert modules <= {"__future__", "hashlib", "itertools", "json", "re", "collections"}
    names = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not names & {"open", "eval", "exec", "print", "compile"}
    assert not any(isinstance(node, ast.FunctionDef) and node.name == "main"
                   for node in tree.body)
