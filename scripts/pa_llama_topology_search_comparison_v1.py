"""Pure descriptive single-path deletion comparisons on supplied SAFE topology tables.

No readers, writers, inference, execution authority, ddmin reproduction or new gate.
Every oracle query below is a lookup in an already supplied table, not a model call.
The caller supplies and authenticates the complete population and source artifact.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections import Counter

SCHEMA = "jbspan-pa-llama-topology-search-comparison-v1"
UNIT_IDS = (
    "AIMDecorator", "RefusalSuppressionDecorator", "AffirmativePrefixInjectionDecorator"
)
ORDERS = tuple(itertools.permutations(range(3)))
UNKNOWN = frozenset({
    "ABSTAINED", "CAPABILITY_CONFOUNDED", "INVALID_INTERVENTION", "TRUNCATED",
    "INCOMPLETE", "UNKNOWN",
})
STATUSES = UNKNOWN | {"RECOVERED", "NOT_RECOVERED"}


class ComparisonError(ValueError):
    """Content-free SAFE input contract error."""


def require(condition, code):
    if not condition:
        raise ComparisonError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def normalize(primary_rows, all_payload_positions):
    require(isinstance(all_payload_positions, (list, tuple))
            and 1 <= len(all_payload_positions) <= 45, "COMPLETE_POPULATION_REQUIRED")
    require(all(type(position) is int and 0 <= position < 45
                for position in all_payload_positions), "PAYLOAD_POSITION_INVALID")
    require(len(set(all_payload_positions)) == len(all_payload_positions),
            "DUPLICATE_POPULATION_POSITION")
    positions = sorted(all_payload_positions)
    require(isinstance(primary_rows, list) and len(primary_rows) == len(positions) * 8,
            "COMPLETE_N_BY_8_FRAME_REQUIRED")
    lookup = {}
    for row in primary_rows:
        require(isinstance(row, dict)
                and set(row) == {"payload_position", "mask_id", "status"},
                "EXACT_SAFE_ROW_FIELDS_REQUIRED")
        position, mask, status = row["payload_position"], row["mask_id"], row["status"]
        require(type(position) is int and position in positions
                and type(mask) is int and 0 <= mask <= 7, "ROW_POSITION_OR_MASK_INVALID")
        require(isinstance(status, str) and status in STATUSES, "ROW_STATUS_INVALID")
        require((position, mask) not in lookup, "DUPLICATE_PRIMARY_CELL")
        lookup[position, mask] = status
    require(set(lookup) == set(itertools.product(positions, range(8))),
            "COMPLETE_N_BY_8_FRAME_REQUIRED")
    require(all(lookup[position, 0] == "NOT_RECOVERED" for position in positions),
            "SCREEN_MASK0_REFERENCE_MUST_REMAIN_NOT_RECOVERED")
    rows = [{"payload_position": position, "mask_id": mask,
             "status": lookup[position, mask]}
            for position, mask in itertools.product(positions, range(8))]
    return positions, rows, lookup


def strict_subsets(mask):
    return [other for other in range(8) if other != mask and other & mask == other]


def exhaustive_family(statuses):
    recovered = [mask for mask in range(8) if statuses[mask] == "RECOVERED"]
    candidates = [mask for mask in recovered
                  if not any(statuses[sub] == "RECOVERED" for sub in strict_subsets(mask))]
    certified = [mask for mask in candidates
                 if all(statuses[sub] == "NOT_RECOVERED" for sub in strict_subsets(mask))]
    return {
        "recovered_masks": recovered,
        "certified_minimal_masks": certified,
        "unresolved_minimal_candidates": [mask for mask in candidates if mask not in certified],
        "unknown_masks": [mask for mask in range(8) if statuses[mask] in UNKNOWN],
        "status_counts": dict(sorted(Counter(statuses.values()).items())),
        "all_eight_statuses_known": all(value not in UNKNOWN for value in statuses.values()),
        "subset_monotonicity_assumed": False,
        "certificates_apply_only_to_supplied_finite_observation_table": True,
    }


def single_path(statuses, order, family):
    """Try each unit once in fixed order; no retries after a later successful move."""
    initial = statuses[7]
    current = 7 if initial == "RECOVERED" else None
    trace = [{"step_index": 0, "kind": "INITIAL_MASK7", "mask_id": 7, "status": initial,
              "removed_unit_id": None, "current_before": None, "current_after": current,
              "move_accepted": initial == "RECOVERED"}]
    if current is not None:
        for step, unit in enumerate(order, start=1):
            candidate = current & ~(1 << unit)
            observed = statuses[candidate]
            accepted = observed == "RECOVERED"
            after = candidate if accepted else current
            trace.append({"step_index": step, "kind": "REMOVE_ONE_NEUTRALIZED_UNIT",
                          "mask_id": candidate, "status": observed,
                          "removed_unit_id": UNIT_IDS[unit], "current_before": current,
                          "current_after": after, "move_accepted": accepted})
            current = after
    if current is None:
        minimality = "NOT_STARTED"
    elif current in family["certified_minimal_masks"]:
        minimality = "CERTIFIED_BY_EXHAUSTIVE_TABLE"
    elif current in family["unresolved_minimal_candidates"]:
        minimality = "UNRESOLVED_UNKNOWN_STRICT_SUBSETS"
    else:
        minimality = "KNOWN_NONMINIMAL_BY_EXHAUSTIVE_TABLE"
    queried = [row["mask_id"] for row in trace]
    return {
        "unit_deletion_order": [UNIT_IDS[index] for index in order],
        "unit_bit_order": list(order),
        "start_status": ("STARTED" if initial == "RECOVERED" else
                         "CANNOT_START_NOT_RECOVERED" if initial == "NOT_RECOVERED" else
                         "CANNOT_START_UNKNOWN"),
        "trace": trace,
        "oracle_queried_masks_in_order": queried,
        "oracle_query_count_including_initial7": len(queried),
        "oracle_distinct_queried_mask_count": len(set(queried)),
        "oracle_queries_with_unknown_status": [row["mask_id"] for row in trace
                                                if row["status"] in UNKNOWN],
        "observed_recovered_masks": sorted({row["mask_id"] for row in trace
                                             if row["status"] == "RECOVERED"}),
        "terminal_recovery_mask": current,
        "terminal_minimality_using_exhaustive_reference": minimality,
        "search_trace_alone_claims_minimality": False,
    }


def compare_search(primary_rows, *, all_payload_positions, source_identity_sha256):
    """Retain every caller-declared P; run all six orders, never choose a favorable one.

    Complete means all eight status entries exist, not that every status is binary.
    The explicit population guards row omission relative to that declaration; this
    pure function does not authenticate that it equals the upstream ALL-stable pool.
    """
    require(isinstance(source_identity_sha256, str)
            and re.fullmatch("[0-9a-f]{64}", source_identity_sha256) is not None,
            "CALLER_DECLARED_SOURCE_IDENTITY_REQUIRED")
    positions, rows, lookup = normalize(primary_rows, all_payload_positions)
    per_payload = []
    for position in positions:
        statuses = {mask: lookup[position, mask] for mask in range(8)}
        family = exhaustive_family(statuses)
        orders = [single_path(statuses, order, family) for order in ORDERS]
        terminals = sorted({row["terminal_recovery_mask"] for row in orders
                            if row["terminal_recovery_mask"] is not None})
        discovered = sorted({mask for row in orders for mask in row["observed_recovered_masks"]})
        queried = [mask for row in orders for mask in row["oracle_queried_masks_in_order"]]
        certified = family["certified_minimal_masks"]
        unresolved = family["unresolved_minimal_candidates"]
        per_payload.append({
            "payload_position": position, "exhaustive_reference": family, "orders": orders,
            "all_six_order_union": {
                "terminal_recovery_masks": terminals,
                "observed_recovered_masks": discovered,
                "oracle_queried_masks_distinct": sorted(set(queried)),
                "oracle_query_count_without_cross_order_cache": len(queried),
                "oracle_distinct_queried_mask_count_within_payload": len(set(queried)),
                "certified_minima_reached_as_terminals": [
                    mask for mask in certified if mask in terminals],
                "certified_minima_missed_as_terminals": [
                    mask for mask in certified if mask not in terminals],
                "unresolved_candidates_reached_as_terminals": [
                    mask for mask in unresolved if mask in terminals],
                "unresolved_candidates_missed_as_terminals": [
                    mask for mask in unresolved if mask not in terminals],
                "exhaustive_recoveries_not_observed_in_any_trace": [
                    mask for mask in family["recovered_masks"] if mask not in discovered],
            },
            "constant_ab": {"mask_id": 3, "status": statuses[3],
                            "oracle_table_lookup_count": 1, "utility_superiority_claimed": False},
        })
    ab_statuses = [row["constant_ab"]["status"] for row in per_payload]
    count = len(positions)
    result = {
        "schema_version": SCHEMA,
        "evidence_class": "DESCRIPTIVE_EXISTING_EXPOSED_DEVELOPMENT_TABLE_ORACLE_COMPARISON",
        "upstream_caller_declared_source_identity_sha256": source_identity_sha256,
        "upstream_source_artifact_authenticated": False,
        "caller_population_authenticated_against_screen": False,
        "normalized_input_identity_sha256": digest({"all_payload_positions": positions,
                                                    "primary_rows": rows}),
        "all_payload_positions": positions, "payload_count": count,
        "primary_status_rows": rows, "unit_ids": list(UNIT_IDS),
        "baseline_name": "DETERMINISTIC_SINGLE_PATH_UNIT_DELETION_FROM_MASK7",
        "mask_semantics": "SET_BITS_IDENTIFY_NEUTRALIZED_ATTACK_UNITS",
        "search_transition": "CLEAR_ONE_BIT_RESTORING_ONE_ATTACK_UNIT",
        "order_count_per_payload": 6,
        "all_six_predetermined_orders_reported": True,
        "move_rule": "ONLY_RECOVERED_MOVES_UNKNOWN_NEVER_TREATED_AS_NOT_RECOVERED",
        "retest_previously_rejected_units": False,
        "per_payload": per_payload,
        "descriptive_oracle_accounting": {
            "reference_status_cells_already_supplied": count * 8,
            "six_order_query_count_without_cross_order_cache": sum(
                row["all_six_order_union"]["oracle_query_count_without_cross_order_cache"]
                for row in per_payload),
            "distinct_payload_mask_queries_across_all_six_orders": sum(
                row["all_six_order_union"]["oracle_distinct_queried_mask_count_within_payload"]
                for row in per_payload),
            "all_counts_are_existing_table_lookups_not_new_model_calls": True,
            "mask0_is_preexisting_screen_reference": True,
            "initial_mask7_lookup_charged_once_per_independent_order": True,
            "target_judge_control_inference_costs_not_estimated": True,
            "actual_query_cost_savings_claimed": False,
        },
        "constant_ab": {
            "mask_id": 3, "payload_denominator": count,
            "status_counts": dict(sorted(Counter(ab_statuses).items())),
            "recovery_fraction_lower": ab_statuses.count("RECOVERED") / count,
            "recovery_fraction_possible_upper": (ab_statuses.count("RECOVERED")
                + sum(value in UNKNOWN for value in ab_statuses)) / count,
            "utility_or_deployment_superiority_claimed": False,
        },
        "ddmin_reproduction_claimed": False, "novel_algorithm_claimed": False,
        "semantic_causality_claimed": False, "statistical_rejection_claimed": False,
        "scientific_measurement_reverified": False, "scientific_gate": False,
        "execution_authorized": False, "paper_validity": False,
        "new_model_calls": 0, "private_input_reads": 0,
    }
    result["result_identity_sha256"] = digest(result)
    return result
