"""Safe-only retrospective analysis of the frozen harmless objective-repair pilot.

No execution helpers, private receipts, model files, or response text are read.
Certificates concern the fixed finite, single-run output-contract oracle only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402
from jbspan.topology_identification import minimal_family_bounds  # noqa: E402

SCHEMA = "jbspan-objective-repair-analysis-v3"
STATUSES = ("CORRECT", "INCORRECT", "UNKNOWN")
UNITS = tuple(f"u{i}" for i in range(5))
SAFE_FIELDS = {
    "status",
    "error_code",
    "score_reason",
    "reply_sha256",
    "output_sha256",
    "finish_reason_sha256",
    "returned_model_sha256",
    "completion_tokens",
    "elapsed_seconds",
    "private_receipt_sha256",
}


def runner_module():
    path = Path(__file__).with_name("run_rescue_objective_repair_v3.py")
    spec = importlib.util.spec_from_file_location("_objective_analysis_runner_v3", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import frozen read-only plan helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def counts(values):
    tally = Counter(values)
    return {status: tally[status] for status in STATUSES}


def verify_phase(value, plan, contract_sha, phase, selected, screen_sha, total_unique):
    """Bind every safe row, duplicate execution, count, and phase to its plan."""
    runner = runner_module()
    runner.verify_result(value, contract_sha, phase)
    public = runner.public_plan(plan)
    rows = value.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("safe phase rows must be objects")
    indexed = {row.get("row_id"): row for row in rows}
    if len(indexed) != len(rows) or set(indexed) != {row["row_id"] for row in public}:
        raise ValueError("safe row denominator or identity differs")
    if (
        value.get("plan_sha256") != support.digest(public)
        or value.get("logical_rows") != len(public)
        or value.get("unique_phase_requests") != len({row["execution_key"] for row in public})
        or value.get("total_journaled_unique_requests") != total_unique
        or total_unique > 304
        or value.get("selected_case_ids") != selected
        or value.get("screen_file_sha256") != screen_sha
    ):
        raise ValueError("phase plan, selection, or request denominator differs")
    by_execution = {}
    for planned in public:
        row = indexed[planned["row_id"]]
        if set(row) != set(planned) | SAFE_FIELDS or any(
            row[key] != expected for key, expected in planned.items()
        ):
            raise ValueError("safe row does not bind exactly its frozen request")
        status = row["status"]
        if status not in STATUSES:
            raise ValueError("unknown result label")
        if status == "UNKNOWN":
            if not isinstance(row["error_code"], str) or not row["error_code"]:
                raise ValueError("unknown result requires an operational error")
            if row["score_reason"] is not None:
                raise ValueError("unknown result cannot contain a completed score")
        elif row["error_code"] is not None or row["score_reason"] not in (
            {"EXACT_JSON_OBJECT"}
            if status == "CORRECT"
            else {"MALFORMED_JSON", "WRONG_SCHEMA", "WRONG_VALUE", "COMPLETED_REFUSAL"}
        ):
            raise ValueError("score status/reason binding differs")
        for key in SAFE_FIELDS:
            if key.endswith("sha256"):
                digest = row[key]
                nullable = status == "UNKNOWN" and key != "private_receipt_sha256"
                if digest is None and nullable:
                    continue
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                ):
                    raise ValueError("malformed safe provenance digest")
        elapsed = row["elapsed_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("invalid elapsed time")
        tokens = row["completion_tokens"]
        if tokens is not None and (type(tokens) is not int or tokens < 0):
            raise ValueError("invalid completion token count")
        safe = {key: row[key] for key in SAFE_FIELDS}
        previous = by_execution.setdefault(row["execution_key"], safe)
        if previous != safe:
            raise ValueError("one cached execution has contradictory safe outcomes")
    if value.get("counts") != counts(row["status"] for row in rows):
        raise ValueError("phase status denominator differs")
    return rows


def validate_table(table):
    if set(table) != set(range(32)) or any(type(mask) is not int for mask in table):
        raise ValueError("exactly 32 distinct integer masks are required")
    if set(table.values()) - set(STATUSES):
        raise ValueError("unrecognized table status")


def proper_masks(mask):
    return [other for other in range(32) if other != mask and other & mask == other]


def candidate_certificate(table, mask):
    proper = proper_masks(mask)
    positive = [other for other in proper if table[other] == "CORRECT"]
    unresolved = [other for other in proper if table[other] == "UNKNOWN"]
    immediate = [mask ^ (1 << unit) for unit in range(5) if mask & (1 << unit)]
    positive_candidate = table[mask] == "CORRECT"
    one_minimal = positive_candidate and all(table[other] == "INCORRECT" for other in immediate)
    if not positive_candidate:
        status = "CANDIDATE_NOT_KNOWN_CORRECT"
    elif positive:
        status = "REFUTED_BY_KNOWN_STRICT_SUBSET"
    elif unresolved:
        status = "UNRESOLVED_STRICT_MINIMALITY"
    else:
        status = "CERTIFIED_STRICT_MINIMAL"
    return {
        "mask": mask,
        "known_one_minimal": one_minimal,
        "strict_status": status,
        "known_correct_proper_masks": positive,
        "unresolved_proper_masks": unresolved,
    }


def greedy_replay(table, reverse=False):
    """One fixed deletion pass, then neighbor audit; never silently iterate.

    Endpoint observations 0/31 are already available from screening. The policy
    sees only cached callback results. A full-table audit is separate from what
    its own transcript certifies. Query counts are logical cells, not model calls.
    """
    validate_table(table)
    observed = {mask: table[mask] for mask in (0, 31)}
    queries = []

    def query(mask):
        if mask not in observed:
            observed[mask] = table[mask]
            queries.append({"mask": mask, "status": observed[mask]})
        return observed[mask]

    current = 31
    moves = []
    if query(current) == "CORRECT":
        for unit in range(4, -1, -1) if reverse else range(5):
            candidate = current ^ (1 << unit)
            if query(candidate) == "CORRECT":
                moves.append({"from_mask": current, "to_mask": candidate})
                current = candidate
        for unit in range(5):
            if current & (1 << unit):
                query(current ^ (1 << unit))
    visible = {mask: observed.get(mask, "UNKNOWN") for mask in range(32)}
    return {
        "policy": "REVERSE_SINGLE_PASS" if reverse else "FORWARD_SINGLE_PASS",
        "preobserved_masks": [0, 31],
        "final_mask": current,
        "moves": moves,
        "new_logical_query_count": len(queries),
        "known_cell_count": len(observed),
        "new_queries": queries,
        "transcript_certificate": candidate_certificate(visible, current),
        "full_table_posthoc_audit": candidate_certificate(table, current),
        "model_calls_made": 0,
    }


def analyze_table(table):
    validate_table(table)
    names = {
        mask: tuple(unit for i, unit in enumerate(UNITS) if mask & (1 << i)) for mask in range(32)
    }
    labels = {"CORRECT": "RECOVERED", "INCORRECT": "NOT_RECOVERED", "UNKNOWN": "UNKNOWN"}
    bounds = minimal_family_bounds(
        UNITS, {names[mask]: labels[value] for mask, value in table.items()}
    )
    masks = {units: mask for mask, units in names.items()}
    necessary = sorted(masks[units] for units in bounds.necessary)
    possible = sorted(masks[units] for units in bounds.possible)
    reversals = [
        {"correct_mask": small, "incorrect_superset_mask": large}
        for small in range(32)
        if table[small] == "CORRECT"
        for large in range(32)
        if small != large and small & large == small and table[large] == "INCORRECT"
    ]
    closures = []
    for boundary in range(4):
        block = 3 << boundary
        for mask in necessary:
            closed = mask | block if mask & block else mask
            if table[closed] in {"INCORRECT", "UNKNOWN"}:
                closures.append(
                    {
                        "merge_boundary": boundary,
                        "certified_minimum_mask": mask,
                        "closure_mask": closed,
                        "closure_status": table[closed],
                    }
                )
    one_minimal = [
        candidate_certificate(table, mask)
        for mask in range(32)
        if candidate_certificate(table, mask)["known_one_minimal"]
    ]
    return {
        "cell_count": 32,
        "status_counts": counts(table.values()),
        "necessary_minimum_masks": necessary,
        "possible_minimum_masks": possible,
        "family_identified": bounds.identified,
        "necessary_minimum_count": len(necessary),
        "possible_minimum_count": len(possible),
        "known_nonmonotone_witnesses": reversals,
        "known_nonmonotone_witness_count": len(reversals),
        "known_one_minimal_candidates": one_minimal,
        "one_minimal_strict_status_counts": dict(
            Counter(row["strict_status"] for row in one_minimal)
        ),
        "adjacent_merge_count": 4,
        "adjacent_closure_checks": closures,
        "adjacent_known_closure_witness_count": sum(
            row["closure_status"] == "INCORRECT" for row in closures
        ),
        "adjacent_unique_known_reversal_count": len(
            {
                (row["certified_minimum_mask"], row["closure_mask"])
                for row in closures
                if row["closure_status"] == "INCORRECT"
            }
        ),
        "adjacent_unresolved_closure_count": sum(
            row["closure_status"] == "UNKNOWN" for row in closures
        ),
        "baselines": [greedy_replay(table), greedy_replay(table, reverse=True)],
    }


def screen_summary(config, cases, rows, selected):
    runner = runner_module()
    by_case = {case["case_id"]: case for case in cases}
    cells = {(row["model_id"], row["case_id"], row["condition"]): row for row in rows}
    summaries = []
    for model in config["models"]:
        for case_id, case in sorted(by_case.items()):
            conditions = {
                condition: cells[(model["model_id"], case_id, condition)]["status"]
                for condition in runner.CONDITIONS
            }
            summaries.append(
                {
                    "model_id": model["model_id"],
                    "case_id": case_id,
                    "task_family": case["task_family"],
                    "conflict_style": case["conflict_style"],
                    "task_data_sha256": support.digest(case["task_data"]),
                    "condition_statuses": conditions,
                    "unedited_score_reason": cells[(model["model_id"], case_id, "UNEDITED")][
                        "score_reason"
                    ],
                    "eligible": runner.core_module().screen_eligible(conditions),
                    "selected": case_id in selected[model["model_id"]],
                }
            )
    return {
        "logical_rows": len(rows),
        "model_case_count": len(summaries),
        "unique_case_count": len(by_case),
        "unique_task_data_count": len({support.digest(case["task_data"]) for case in cases}),
        "eligible_model_case_count": sum(row["eligible"] for row in summaries),
        "selected_model_case_count": sum(row["selected"] for row in summaries),
        "selected_case_ids": selected,
        "condition_counts": {
            condition: counts(row["status"] for row in rows if row["condition"] == condition)
            for condition in runner.CONDITIONS
        },
        "model_cases": summaries,
    }


def analyze_exact_rows(cases, rows):
    """Pure table analysis; callers must first verify phase identities."""
    runner = runner_module()
    by_case = {case["case_id"]: case for case in cases}
    tables = {}
    for row in rows:
        key = (row["model_id"], row["case_id"], row["operator"])
        table = tables.setdefault(key, {})
        mask = row["removed_mask"]
        if mask in table:
            raise ValueError("duplicate exact table cell")
        table[mask] = row["status"]
    output = []
    for (model_id, case_id, operator), table in sorted(tables.items()):
        if case_id not in by_case or operator not in runner.OPERATORS:
            raise ValueError("unrecognized case or operator")
        other = next(value for value in runner.OPERATORS if value != operator)
        opposite = tables.get((model_id, case_id, other))
        if opposite is None:
            raise ValueError("both operator tables are required")
        validate_table(opposite)
        result = analyze_table(table)
        case = by_case[case_id]
        transfers = [
            {"minimum_mask": mask, "opposite_status": opposite[mask]}
            for mask in result["necessary_minimum_masks"]
        ]
        output.append(
            {
                "model_id": model_id,
                "case_id": case_id,
                "operator": operator,
                "task_family": case["task_family"],
                "conflict_style": case["conflict_style"],
                "task_data_sha256": support.digest(case["task_data"]),
                **result,
                "opposite_operator": other,
                "minimum_operator_transfers": transfers,
                "minimum_operator_transfer_counts": counts(
                    row["opposite_status"] for row in transfers
                ),
            }
        )
    witness_tables = [row for row in output if row["known_nonmonotone_witness_count"]]
    return {
        "logical_cell_count": len(rows),
        "operator_table_count": len(output),
        "model_case_count": len({(row["model_id"], row["case_id"]) for row in output}),
        "unique_case_count": len({row["case_id"] for row in output}),
        "unique_task_data_count": len({row["task_data_sha256"] for row in output}),
        "known_nonmonotone_operator_table_count": len(witness_tables),
        "known_nonmonotone_model_case_count": len(
            {(row["model_id"], row["case_id"]) for row in witness_tables}
        ),
        "known_nonmonotone_unique_task_data_count": len(
            {row["task_data_sha256"] for row in witness_tables}
        ),
        "necessary_minimum_occurrence_count": sum(row["necessary_minimum_count"] for row in output),
        "possible_minimum_occurrence_count": sum(row["possible_minimum_count"] for row in output),
        "identified_operator_table_count": sum(row["family_identified"] for row in output),
        "tables": output,
    }


def analyze(root, relative, contract_sha, *, screen_only=False):
    runner = runner_module()
    config, cases = runner.verify_config(root, relative, contract_sha)
    directory = support.contained(root, config["recording"]["safe_base"]) / contract_sha
    screen_path = directory / "screen.safe.json"
    screen = support.read_object(screen_path)
    runner.verify_result(screen, contract_sha, "screen")
    selected = runner.select_eligible(config, cases, screen)
    screen_plan = runner.screen_plan(config, cases)
    screen_keys = {row["execution_key"] for row in screen_plan}
    screen_rows = verify_phase(
        screen, screen_plan, contract_sha, "screen", selected, None, len(screen_keys)
    )
    screen_sha = support.file_digest(screen_path)
    result = {
        "schema_version": SCHEMA,
        "contract_sha256": contract_sha,
        "screen_file_sha256": screen_sha,
        "analysis_source_sha256": support.file_digest(Path(__file__)),
        "identification_source_sha256": support.file_digest(
            root / "src/jbspan/topology_identification.py"
        ),
        "screen": screen_summary(config, cases, screen_rows, selected),
        "scope": "SELECTED_HARMLESS_SINGLE_RUN_OUTPUT_CONTRACT_REPAIR_PILOT",
        "interpretation": {
            "unknown_is_not_incorrect": True,
            "no_statistical_independence_of_repeated_cells": True,
            "selection_conditions_both_endpoints": True,
            "one_minimal_is_not_subset_minimal": True,
            "cross_model_selected_style_may_differ": True,
            "paper_quality_gate": None,
            "not_harmful_jailbreak_or_safety_validation": True,
        },
        "network_calls": 0,
        "private_inputs_read": False,
        "model_files_read": False,
    }
    if screen_only or not any(selected.values()):
        result["status"] = (
            "SCREEN_VERIFIED_ONLY" if any(selected.values()) else "SCREEN_VERIFIED_NO_ELIGIBLE_CASE"
        )
        result["exact_analyzed"] = False
    else:
        exact_path = directory / "exact.safe.json"
        exact = support.read_object(exact_path)
        plan, expected_selected = runner.exact_plan(config, cases, screen)
        keys = screen_keys | {row["execution_key"] for row in plan}
        exact_rows = verify_phase(
            exact, plan, contract_sha, "exact", expected_selected, screen_sha, len(keys)
        )
        # Every cache reuse must agree across phases, not only within each phase.
        executions = {}
        for row in screen_rows + exact_rows:
            safe = {key: row[key] for key in SAFE_FIELDS}
            if executions.setdefault(row["execution_key"], safe) != safe:
                raise ValueError("screen/exact cached outcome binding differs")
        result.update(
            {
                "status": "EXACT_SAFE_ANALYSIS_COMPLETE",
                "exact_analyzed": True,
                "exact_file_sha256": support.file_digest(exact_path),
                "exact": analyze_exact_rows(cases, exact_rows),
            }
        )
    support.content_free(result)
    result["result_identity_sha256"] = support.digest(result)
    return result, directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--screen-only", action="store_true")
    parser.add_argument("--write", action="store_true", help="Publish a write-once safe analysis")
    args = parser.parse_args()
    result, directory = analyze(
        args.root.resolve(), args.config, args.config_sha256, screen_only=args.screen_only
    )
    if args.write:
        name = "analysis.safe.json" if result["exact_analyzed"] else "screen.analysis.safe.json"
        support.write_once(directory / name, result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
