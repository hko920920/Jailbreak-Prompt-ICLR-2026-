"""Synthetic-only exact finite null analysis; no real outcome/private input reads."""

import ast
import copy
import importlib.util
import itertools
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "scripts/pa_llama_topology_analysis_v1.py"
SPEC = importlib.util.spec_from_file_location("pa_topology_analysis_test", MODULE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


@pytest.fixture(scope="module")
def reference():
    return m.load_reference_functions()


def screen(n=6):
    states = [{"payload_position": position, "payload_sha256": m.digest([position, "P"]),
               "topic_sha256": m.digest([position // 3, "topic"]),
               "status": "STABLE_PAIR" if position < n else "NOT_STABLE"}
              for position in range(45)]
    result = {"schema_version": "jbspan-pa-llama-development-phase-result-v1",
              "contract_sha256": "c" * 64, "source_inventory_sha256": "a" * 64,
              "phase_seed": 47, "complete": True, "initial_payload_denominator": 45,
              "stable_pair_floor": 6, "route": "DEVELOPMENT_STABLE_POOL_AVAILABLE",
              "next_seed": None, "advance_positions": [], "paper_validity": False,
              "is_original_c1n_pass": False, "topology_authorized": False,
              "fresh_confirmation": False, "sealed_cohort_opened": False,
              "stable_positions": list(range(n)), "pair_states": states,
              "status_counts": {"ADVANCE": 0, "STABLE_PAIR": n, "NOT_STABLE": 45 - n,
                                "UNRESOLVED": 0}}
    result["result_identity_sha256"] = m.digest(result)
    return result


def proof(result):
    value = {"schema_version": "jbspan-pa-llama-development-phase-verification-v1",
             "contract_sha256": result["contract_sha256"], "phase_seed": 47,
             "phase_result_identity_sha256": result["result_identity_sha256"],
             "raw_axis_receipts_verified": True, "independent_pair_states_verified": True,
             "verification_passed": True, "new_model_calls": 0}
    value["verification_identity_sha256"] = m.digest(value)
    return value


def frame(matrix, *, altered_slice=None):
    result = screen(len(matrix))
    matrices = [copy.deepcopy(matrix) for _ in range(6)]
    if altered_slice is not None:
        altered_slice(matrices)
    primary, slices = [], []
    for position, mask in itertools.product(range(len(matrix)), range(8)):
        values = [table[position][mask] for table in matrices]
        status = ("RECOVERED" if values == [1] * 6 else "NOT_RECOVERED"
                  if 0 in values else "UNKNOWN")
        primary.append({"payload_position": position, "mask_id": mask, "status": status})
        for index, (neutralizer, seed) in enumerate(itertools.product(m.NEUTRALIZERS, m.SEEDS)):
            slices.append({"payload_position": position, "mask_id": mask,
                           "neutralizer_id": neutralizer, "seed": seed,
                           "label": matrices[index][position][mask]})
    return result, primary, slices


def analyze(rows, reference, **kwargs):
    result, primary, slices = rows
    return m.analyze_topology(result, primary, slices, source_identity_sha256="b" * 64,
                             reference=reference, **kwargs)


def crossover_matrix(n=6):
    return [[0, 1, 0, 1, 0, 1, 0, 1],
            *[[0, 0, 0, 1, 0, 1, 1, 1] for _ in range(n - 1)]]


def test_reference_four_function_closure_no_historical_readers(reference):
    assert set(vars(reference)) == m.REFERENCE_FUNCTIONS | {"source_sha256"}
    assert reference.source_sha256 == m.REFERENCE_SHA256
    assert not hasattr(reference, "read_source") and not hasattr(reference, "analyze")


def test_reference_wrong_code_rejected_before_ast_execution(tmp_path):
    path = tmp_path / m.REFERENCE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * m.REFERENCE_BYTES)
    with pytest.raises(m.AnalysisError, match="REFERENCE_SHA_DRIFT"):
        m.load_reference_functions(tmp_path)


def test_exact_all40320_orders_against_independent_small_null(reference):
    matrix = [[0, 1, 0, 1, 0, 1, 0, 1], [0, 0, 0, 1, 0, 1, 1, 1]]
    result = m.analyze_matrix(matrix, reference=reference)
    assert result["known_fit"]["orders_evaluated"] == 40320
    assert result["minimum_known_cell_change_distance_to_common_order"] == 1
    assert result["strict_crossovers"]["strict_crossover_count"] == 1
    assert result["p_independent_lookup"]["minimum_known_label_error_count"] == 2
    assert result["constant_ab_repair"]["certified_recovered"] == 2
    assert result["observed_matrix"] == matrix
    assert not result["statistical_rejection_claimed"]


def test_known_partial_cycle_detected_without_observed_two_by_two(reference):
    matrix = [[0, 1, 0, None, None, None, None, None],
              [0, None, 1, 0, None, None, None, None],
              [0, 0, None, 1, None, None, None, None]]
    result = m.analyze_matrix(matrix, reference=reference)
    assert result["minimum_known_cell_change_distance_to_common_order"] == 1
    assert result["strict_crossovers"]["strict_crossover_count"] == 0
    assert result["unknown_sensitivity"]["completion_count"] == 0


def test_unknown_two_exact_assignments_are_never_observations(reference):
    matrix = [[0, 1, 0, 1, 0, 1, 0, None], [0, 0, 0, 1, 0, 1, 1, None]]
    result = m.analyze_matrix(matrix, reference=reference)
    sensitivity = result["unknown_sensitivity"]
    assert sensitivity["completion_count"] == 4 and sensitivity["upper_bound_is_sharp"]
    assert sensitivity["optimistic_full_table_error_exact"] == 1
    assert not sensitivity["unknown_imputed_as_observed"]
    assert all(row["assignment_is_observed"] is False
               for row in sensitivity["hypothetical_completions"])
    assert result["observed_matrix"] == matrix


def test_all45_many_unknown_no_exponential_enumeration(reference):
    matrix = [[0, None, None, None, None, None, None, None] for _ in range(45)]
    result = analyze(frame(matrix), reference)
    primary = result["primary"]
    assert result["selected_payload_denominator"] == 45
    assert primary["unknown_cell_count"] == 315
    assert primary["known_fit"]["orders_evaluated"] == 40320
    assert primary["unknown_sensitivity"]["completion_count"] == 0
    assert primary["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == [0, 315]
    assert primary["unknown_sensitivity"]["upper_bound_is_sharp"] is False
    assert len(result["neutralizer_seed_tables"]) == 6
    assert result["exact_fit_unique_matrix_count"] == 1
    assert result["primary_status_counts"] == {"NOT_RECOVERED": 45, "UNKNOWN": 315}


def test_repeated_shared_cell_is_not_independent_evidence(reference):
    result = analyze(frame(crossover_matrix()), reference)
    shared = result["all_six_same_oriented_crossovers"]
    assert shared["strict_shared_crossover_count"] == 5
    assert shared["maximum_witnesses_sharing_one_cell"] == 5
    assert result["primary"]["minimum_known_cell_change_distance_to_common_order"] == 1
    assert not shared["independent_replicate_or_statistical_significance_claimed"]
    assert all(row["matching_slice_count"] == 6 for row in shared["witnesses"])


@pytest.mark.parametrize("change", ["unknown", "same_order", "orientation_flip"])
def test_shared_witness_requires_same_orientation_in_all_six(reference, change):
    def altered(matrices):
        if change == "unknown":
            matrices[5][0][1] = None
        elif change == "same_order":
            matrices[5][0][1] = 0
        else:
            for row in matrices[5]:
                row[1], row[6] = row[6], row[1]

    result = analyze(frame(crossover_matrix(), altered_slice=altered), reference)
    shared = result["all_six_same_oriented_crossovers"]
    assert shared["strict_shared_crossover_count"] == 0
    assert result["neutralizer_seed_tables"][0]["analysis"]["strict_crossovers"][
        "strict_crossover_count"] == 5
    if change == "orientation_flip":
        assert result["neutralizer_seed_tables"][5]["analysis"]["strict_crossovers"][
            "strict_crossover_count"] == 5


def test_input_row_permutation_preserves_all_identities_and_results(reference):
    rows = frame(crossover_matrix())
    first = analyze(rows, reference, screen_verification=proof(rows[0]))
    rows[1].reverse()
    rows[2].reverse()
    second = analyze(rows, reference, screen_verification=proof(rows[0]))
    assert first == second
    assert first["screen_verification_receipt_binding_checked"]
    assert first["all_stable_payload_positions"] == list(range(6))
    assert first["new_model_calls"] == 0 and first["historical_private_reads"] == 0
    assert first["execution_authorized"] is first["paper_validity"] is False


def test_matrix_row_and_mask_relabeling_preserves_distance_and_crossover_count(reference):
    matrix = crossover_matrix()
    order = [7, 3, 6, 2, 4, 0, 1, 5]
    changed = [[row[mask] for mask in order] for row in reversed(matrix)]
    first = m.analyze_matrix(matrix, reference=reference)
    second = m.analyze_matrix(changed, reference=reference)
    assert first["minimum_known_cell_change_distance_to_common_order"] == second[
        "minimum_known_cell_change_distance_to_common_order"]
    assert first["strict_crossovers"]["strict_crossover_count"] == second[
        "strict_crossovers"]["strict_crossover_count"]
    # Constant ab is not invariant to changing the physical unit/mask labels.


@pytest.mark.parametrize("mutation", [
    lambda s, p, r: p.pop(),
    lambda s, p, r: r.pop(),
    lambda s, p, r: p.__setitem__(1, dict(p[0])),
    lambda s, p, r: r.__setitem__(1, dict(r[0])),
    lambda s, p, r: p[0].update(payload_position=44),
    lambda s, p, r: p[0].update(mask_id=True),
    lambda s, p, r: p[0].update(raw_response="forbidden"),
    lambda s, p, r: p[0].update(status="SAFE"),
    lambda s, p, r: r[0].update(label=False),
    lambda s, p, r: r[0].update(seed=17),
    lambda s, p, r: r[0].update(neutralizer_id="other"),
    lambda s, p, r: r[0].update(status="RECOVERED"),
    lambda s, p, r: p[1].update(status="RECOVERED"),
])
def test_incomplete_favorable_subset_raw_extra_or_relaxed_labels_fail(reference, mutation):
    rows = frame([[0] * 8 for _ in range(6)])
    mutation(*rows)
    with pytest.raises(m.AnalysisError):
        analyze(rows, reference)


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(phase_seed=23),
    lambda s: s.update(stable_pair_floor=5),
    lambda s: s.update(topology_authorized=True),
    lambda s: s.update(paper_validity=True),
    lambda s: s["pair_states"].pop(),
    lambda s: s["stable_positions"].pop(),
    lambda s: s["pair_states"][0].update(payload_position=True),
    lambda s: s["pair_states"][0].update(payload_sha256=s["pair_states"][1]["payload_sha256"]),
])
def test_self_consistent_screen_scope_mutation_rejected(reference, mutation):
    rows = frame([[0] * 8 for _ in range(6)])
    mutation(rows[0])
    rows[0]["result_identity_sha256"] = m.digest({
        key: value for key, value in rows[0].items() if key != "result_identity_sha256"})
    with pytest.raises(m.AnalysisError):
        analyze(rows, reference)


def test_screen_tamper_and_wrong_verification_rejected(reference):
    rows = frame([[0] * 8 for _ in range(6)])
    forged = proof(rows[0])
    forged["phase_result_identity_sha256"] = "e" * 64
    forged["verification_identity_sha256"] = m.digest({
        key: value for key, value in forged.items() if key != "verification_identity_sha256"})
    with pytest.raises(m.AnalysisError, match="SCREEN_PROOF_BINDING"):
        analyze(rows, reference, screen_verification=forged)
    rows[0]["result_identity_sha256"] = "f" * 64
    with pytest.raises(m.AnalysisError, match="SCREEN_RESULT_IDENTITY"):
        analyze(rows, reference)


def test_unknown_categories_are_preserved_not_converted_to_failure(reference):
    rows = frame([[0, None, None, None, None, None, None, None] for _ in range(6)])
    rows[1][1]["status"] = "CAPABILITY_CONFOUNDED"
    rows[2][6]["status"] = "TRUNCATED"
    result = analyze(rows, reference)
    assert result["primary_status_counts"]["CAPABILITY_CONFOUNDED"] == 1
    assert result["slice_status_counts"]["TRUNCATED"] == 1
    assert result["primary"]["observed_matrix"][0][1] is None
    assert result["primary"]["constant_ab_repair"]["unknown"] == 6


def test_all_six_certified_positive_cannot_be_hidden_as_unknown(reference):
    rows = frame([[0, 1, 0, 1, 0, 1, 0, 1] for _ in range(6)])
    rows[1][1]["status"] = "UNKNOWN"
    with pytest.raises(m.AnalysisError, match="SIX_CERTIFIED_SLICES_NOT_ROBUST_POSITIVE"):
        analyze(rows, reference)


def test_direct_shared_helper_cannot_certify_only_five_tables():
    tables = [{"neutralizer_id": neutralizer, "seed": seed}
              for neutralizer, seed in itertools.product(m.NEUTRALIZERS, m.SEEDS)][:-1]
    with pytest.raises(m.AnalysisError, match="EXACT_SIX_SLICES"):
        m.shared_witnesses(tables, [])


def test_only_stdlib_imports_no_process_or_network_or_runtime_module():
    imports = set()
    for node in ast.walk(ast.parse(MODULE.read_bytes())):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
    assert imports <= {"__future__", "ast", "hashlib", "itertools", "json", "math", "re",
                       "collections", "pathlib", "types"}


def qualified_frame(slices, failed=()):
    rows = []
    for source in slices:
        row = dict(source)
        key = row["payload_position"], row["mask_id"], row["neutralizer_id"]
        controls = None if row["mask_id"] == 0 else key not in failed
        row["matched_controls_passed"] = controls
        if controls is False:
            row["label"] = None
            row["status"] = "CAPABILITY_CONFOUNDED"
        rows.append(row)
    return rows


def test_absent_secondary_frame_never_implies_capability_qualified_c3(reference):
    result = analyze(frame(crossover_matrix()), reference)
    assert result["control_qualified_frame_supplied"] is False
    assert result["control_qualified_c3"] is None
    assert result["control_qualified_frame_required_for_capability_qualified_c3"] is True
    assert result["all_six_same_oriented_crossovers"]["strict_shared_crossover_count"] == 5


def test_primary_negative_valid_when_all_negative_controls_fail(reference):
    rows = frame([[0] * 8 for _ in range(6)])
    failed = set(itertools.product(range(6), range(1, 8), m.NEUTRALIZERS))
    qualified = qualified_frame(rows[2], failed)
    result = analyze(rows, reference, control_qualified_slice_rows=qualified)
    secondary = result["control_qualified_c3"]
    assert result["primary_status_counts"] == {"NOT_RECOVERED": 48}
    assert result["primary"]["unknown_cell_count"] == 0
    assert secondary["nonempty_slice_denominator"] == 252
    assert secondary["nonempty_matched_controls_not_passed"] == 252
    assert secondary["not_passed_includes_missing_controls"] is True
    assert secondary["nonempty_matched_controls_passed"] == 0
    assert secondary["all_six_uniformly_certified_cells"]["unknown_cell_count"] == 42
    assert secondary["primary_population_or_status_changed"] is False
    assert secondary["mask0_is_uncontrolled_screen_reference_only"] is True
    assert secondary["mask0_counts_as_new_replication"] is False


def test_qualified_witness_loss_does_not_erase_unqualified_d3_witness(reference):
    rows = frame(crossover_matrix())
    qualified = qualified_frame(rows[2], {(0, 6, m.NEUTRALIZERS[1])})
    result = analyze(rows, reference, control_qualified_slice_rows=qualified)
    assert result["all_six_same_oriented_crossovers"]["strict_shared_crossover_count"] == 5
    secondary = result["control_qualified_c3"]
    assert secondary["all_six_same_oriented_crossovers"]["strict_shared_crossover_count"] == 0
    assert secondary["nonempty_matched_controls_not_passed"] == 3
    assert secondary["neutralizer_seed_tables"][0]["analysis"]["strict_crossovers"][
        "strict_crossover_count"] == 5
    assert secondary["neutralizer_seed_tables"][5]["analysis"]["strict_crossovers"][
        "strict_crossover_count"] == 0


def test_all_qualified_witnesses_keep_shared_cell_fragility(reference):
    rows = frame(crossover_matrix())
    result = analyze(rows, reference, control_qualified_slice_rows=qualified_frame(rows[2]))
    secondary = result["control_qualified_c3"]
    shared = secondary["all_six_same_oriented_crossovers"]
    assert shared["strict_shared_crossover_count"] == 5
    assert shared["maximum_witnesses_sharing_one_cell"] == 5
    assert all(0 not in row["mask_ids"] for row in shared["witnesses"])
    assert not shared["independent_replicate_or_statistical_significance_claimed"]


@pytest.mark.parametrize("mutation", [
    "missing", "duplicate", "wrong_seed", "wrong_operator", "raw_field", "boolean_label",
    "label_flip", "selected_unknown", "negative_without_controls", "unproven_control",
    "mask0_controls", "mask0_unknown", "control_seed_drift", "positive_failed_controls",
])
def test_qualified_frame_is_complete_fixed_filter_not_favorable_subset(reference, mutation):
    rows = frame(crossover_matrix())
    qualified = qualified_frame(rows[2])
    negative = next(row for row in qualified if row["mask_id"] == 6
                    and row["payload_position"] == 0)
    if mutation == "missing":
        qualified.pop()
    elif mutation == "duplicate":
        qualified[-1] = copy.deepcopy(qualified[0])
    elif mutation == "wrong_seed":
        negative["seed"] = 17
    elif mutation == "wrong_operator":
        negative["neutralizer_id"] = "OTHER"
    elif mutation == "raw_field":
        negative["raw_response"] = "forbidden synthetic field"
    elif mutation == "boolean_label":
        negative["label"] = False
    elif mutation == "label_flip":
        negative["label"] = 1
    elif mutation == "selected_unknown":
        negative["label"] = None
    elif mutation == "negative_without_controls":
        negative["matched_controls_passed"] = False
    elif mutation == "unproven_control":
        negative["matched_controls_passed"] = None
    elif mutation == "mask0_controls":
        qualified[0]["matched_controls_passed"] = True
    elif mutation == "mask0_unknown":
        qualified[0]["label"] = None
    elif mutation == "control_seed_drift":
        negative.update(matched_controls_passed=False, label=None)
    else:
        positive = next(row for row in qualified if row["label"] == 1)
        positive.update(matched_controls_passed=False, label=None)
    with pytest.raises(m.AnalysisError):
        analyze(rows, reference, control_qualified_slice_rows=qualified)


def test_qualified_cannot_promote_existing_unknown_to_observed(reference):
    rows = frame([[0, None, None, None, None, None, None, None] for _ in range(6)])
    qualified = qualified_frame(rows[2])
    qualified[6]["label"] = 0
    with pytest.raises(m.AnalysisError, match="QUALIFIED_NOT_EXACT_CONTROL_FILTER"):
        analyze(rows, reference, control_qualified_slice_rows=qualified)


def test_qualified_all45_frame_and_input_order_identity(reference):
    rows = frame([[0, None, None, None, None, None, None, None] for _ in range(45)])
    qualified = qualified_frame(rows[2])
    first = analyze(rows, reference, control_qualified_slice_rows=qualified)
    second = analyze(rows, reference, control_qualified_slice_rows=list(reversed(qualified)))
    assert first == second
    assert first["control_qualified_c3"]["full_slice_denominator_including_reference"] == 2160
    assert first["control_qualified_c3"]["nonempty_slice_denominator"] == 1890
    assert first["control_qualified_c3"]["all_six_uniformly_certified_cells"][
        "unknown_sensitivity"]["completion_count"] == 0


def test_qualified_orientation_flip_in_one_operator_cannot_be_robust(reference):
    def altered(matrices):
        for table in matrices[3:]:
            for row in table:
                row[1], row[6] = row[6], row[1]

    rows = frame(crossover_matrix(), altered_slice=altered)
    result = analyze(rows, reference, control_qualified_slice_rows=qualified_frame(rows[2]))
    secondary = result["control_qualified_c3"]
    assert all(table["analysis"]["strict_crossovers"]["strict_crossover_count"] == 5
               for table in secondary["neutralizer_seed_tables"])
    assert secondary["all_six_same_oriented_crossovers"]["strict_shared_crossover_count"] == 0


def amended_frame():
    rows = frame([[0] * 8 for _ in range(6)])
    rows[0].update(operational_amendment_sha256s=["e" * 64],
                   original_seed11_jailmeter_operational_gate_passed=False,
                   verification_scope=m.AMENDED_SCOPE, scientific_rules_unchanged=True)
    rows[0].pop("result_identity_sha256")
    rows[0]["result_identity_sha256"] = m.digest(rows[0])
    return rows


def test_original_failed_epoch_disclosure_propagates_into_analysis_identity(reference):
    rows = amended_frame()
    verified = proof(rows[0])
    verified.update({key: rows[0][key] for key in m.AMENDMENT_FIELDS})
    verified.pop("verification_identity_sha256")
    verified["verification_identity_sha256"] = m.digest(verified)
    result = analyze(rows, reference, screen_verification=verified)
    disclosure = result["screen_execution_amendment_disclosure"]
    assert disclosure["operational_amendment_sha256s"] == ["e" * 64]
    assert disclosure["original_seed11_jailmeter_operational_gate_passed"] is False
    assert disclosure["amendment_artifact_reverified_by_this_analyzer"] is False


@pytest.mark.parametrize("field,value", [
    ("operational_amendment_sha256s", []),
    ("original_seed11_jailmeter_operational_gate_passed", True),
    ("verification_scope", "ORIGINAL_OPERATIONAL_PASS"),
    ("scientific_rules_unchanged", False),
])
def test_analyzer_never_promotes_amended_failure(reference, field, value):
    rows = amended_frame()
    rows[0][field] = value
    rows[0].pop("result_identity_sha256")
    rows[0]["result_identity_sha256"] = m.digest(rows[0])
    with pytest.raises(m.AnalysisError):
        analyze(rows, reference)


def test_amended_analysis_proof_cannot_silently_omit_disclosure(reference):
    rows = amended_frame()
    with pytest.raises(m.AnalysisError, match="SCREEN_AMENDMENT_PROOF_MISMATCH"):
        analyze(rows, reference, screen_verification=proof(rows[0]))
