"""Explicit Stage7 SAFE-only descriptive baseline supplement; no model calls.

The old D2 runner is never imported. Only hash-pinned pure AST definitions are
loaded. The six-order comparator is an existing tracked source snapshot, NOT a
newly asserted execution-contract pin. No frozen product is edited. The CLI is
read-only unless --write is supplied after source review.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import os
import re
import stat
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

# Keep the full execution identity explicit; no user-selectable data population.
EXECUTION = "1f720cab7e9678278e52542cf0ee33e791d9b2e331c4a2b7cb1b25f64e980ab2"
BASE = f"data/natural_language_localization/pa_reentry_v2/{EXECUTION}"
DIRECTION = "docs/PA_STAGE7_RUNTIME_2026-09-07_V2/direction.safe.json"
DIRECTION_ID = "0b8d4267de2b18e289c570903c0233559ba4ee5ad7bc855e2acf56bccbdf6d70"
STAGE7_ANALYSIS_ID = "c99308269def9766328d6020129ba87f03abdd640fc7359fe5dd0d575ba2c9bf"
STAGE7_VERIFICATION_ID = "32a6484a43f4378dc94046edd64b3cd6d953bd7f631a4f60cc0420665b3143d6"
SELF = "scripts/audit_pa_stage7_baselines_v2.py"
TEST = "tests/test_pa_stage7_baselines_v2.py"
CONFIG = "configs/natural_language_localization/pa_reentry_execution_v2.json"
UNITS = ("AIMDecorator", "RefusalSuppressionDecorator", "AffirmativePrefixInjectionDecorator")
PINNED = {
    CONFIG: (3126, "5f42e6a646f16c3e66596c6c5e31a9d84024456c3c03f356fcdcf687fbec5bae"),
    "scripts/run_topology_d2_micro_pilot.py": (
        94014,
        "c5646aa16928bd5f643a305f38d576f560a0b639650e61566f2c71f08394b513",
    ),
    "src/jbspan/topology.py": (
        29006,
        "a2b1cfaaead73d2efba61f7eb2e3141e327d69bb4f25889ab7813dcf27363672",
    ),
    "scripts/pa_llama_topology_analysis_v1.py": (
        26767,
        "9937a11708421c451893ef7aedfcd58f7ba712ceba7674b404b5a8606d67c5a7",
    ),
    "scripts/pa_llama_topology_search_comparison_v1.py": (
        12415,
        "aa6156961a2fc69912f89d467341a84ef3bd109ae86b798dc3944169f75949d3",
    ),
    "tests/test_pa_llama_topology_search_comparison_v1.py": (
        12685,
        "8fb0522af55ffa16311b018fe6c5c0a0c30c4261e947841f2e22e9acec4b1584",
    ),
    "docs/PA_LLAMA_TOPOLOGY_PROSPECTIVE_READINESS_2026-09-05_V1.md": (
        24218,
        "7d1f2a4dba63546ddce10df9ebd7c7eb8394632a2febbadbe0ff3a45e890e344",
    ),
    f"{BASE}/finalization/measurements-only/measurements.safe.json": (
        1997387,
        "b9ce483fbb633d5bd533190f1d7b2324c45caedd16ed3e83f69d324fbdb41ac1",
    ),
    f"{BASE}/finalization/measurements-only/result.safe.json": (
        3232,
        "b427c21a70700d7ad0995df48b7d79a378e374d629ff8f1b0716c204b747eda3",
    ),
    f"{BASE}/finalization/measurements-only/verification.safe.json": (
        5904,
        "c4f91f03091b5a9675de8594e275a92ee786c5fec41cb875a2d7ecf68086cf1f",
    ),
    f"{BASE}/finalization/with-analysis/verification.safe.json": (
        6059,
        "587bf2f425bff9131986e4a29e73ccc828c34c036b2152d68409159c5516822e",
    ),
}
PRODUCTS = ("measurements", "analysis", "result", "verification")
READ_PATHS = (
    set(PINNED)
    | {DIRECTION, SELF, TEST}
    | {f"{BASE}/finalization/with-analysis/{name}.safe.json" for name in PRODUCTS}
)
D2_FUNCTIONS = {
    "subset_status_map",
    "greedy_backward_baseline",
    "greedy_forward_baseline",
    "family_metrics",
}
COMPARISON_FUNCTIONS = {
    "require",
    "canonical",
    "digest",
    "normalize",
    "strict_subsets",
    "exhaustive_family",
    "single_path",
    "compare_search",
}
SOURCE_COMMIT = "abfedd6cc5c9bb568bc1f3a7896098db74b4d64a"
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(value, code):
    if not value:
        raise ValueError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(value, key="result_identity_sha256"):
    require(key not in value, "BASELINE_ALREADY_SEALED")
    return {**value, key: digest(value)}


def verify_seal(value, key="result_identity_sha256"):
    require(
        isinstance(value, dict) and isinstance(value.get(key), str) and SHA.fullmatch(value[key]),
        "BASELINE_SEAL_MISSING",
    )
    require(
        digest({k: v for k, v in value.items() if k != key}) == value[key], "BASELINE_SEAL_CHANGED"
    )
    return value


def parse_safe_json(raw, *, require_canonical=False):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "BASELINE_DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("BASELINE_NONFINITE_JSON_NUMBER")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("BASELINE_JSON_ENCODING_OR_SYNTAX") from None
    if require_canonical:
        require(raw == canonical(value) + b"\n", "BASELINE_SAFE_JSON_NOT_CANONICAL")
    return value


def reject_links(path):
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        require(
            not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 1024),
            "BASELINE_LINK_OR_REPARSE_POINT",
        )


def native(path):
    value = os.fspath(path)
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        value = "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return Path(value)


def owned(root, relative):
    require(
        isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative,
        "BASELINE_PATH_INVALID",
    )
    parsed = PurePosixPath(relative)
    require(
        not parsed.is_absolute()
        and parsed.as_posix() == relative
        and all(part not in {".", ".."} and part.rstrip(" .") == part for part in parsed.parts),
        "BASELINE_PATH_ESCAPE",
    )
    root = Path(os.path.abspath(root))
    path = root.joinpath(*parsed.parts)
    reject_links(path)
    require(path.is_relative_to(root), "BASELINE_PATH_ESCAPE")
    return native(path)


def read_file(root, relative):
    require(relative in READ_PATHS, "BASELINE_READ_OUTSIDE_EXACT_SAFE_SOURCE_CLOSURE")
    path = owned(root, relative)
    before = path.stat()
    require(
        stat.S_ISREG(before.st_mode) and before.st_size <= 3_000_000,
        "BASELINE_INPUT_NOT_SMALL_REGULAR_FILE",
    )
    raw = path.read_bytes()
    after = path.stat()
    reject_links(path)
    require(
        (before.st_size, before.st_mtime_ns, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_ino),
        "BASELINE_FILE_CHANGED_DURING_READ",
    )
    file_sha = hashlib.sha256(raw).hexdigest()
    if relative in PINNED:
        require((len(raw), file_sha) == PINNED[relative], "BASELINE_SOURCE_OR_INPUT_PIN_CHANGED")
    return raw, {"path": relative, "size_bytes": len(raw), "sha256": file_sha}


def ast_closure(raw, names, *, constants=(), classes=(), environment=None):
    tree = ast.parse(raw.decode("utf-8"))
    selected, found = [], set()
    for node in tree.body:
        name = None
        if isinstance(node, ast.FunctionDef) and node.name in names:
            name = node.name
        elif isinstance(node, ast.ClassDef) and node.name in classes:
            name = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in constants:
                name = target.id
        if name is not None:
            require(
                name not in found and not getattr(node, "decorator_list", []),
                "BASELINE_AST_DUPLICATE_OR_DECORATED",
            )
            require(
                not any(
                    isinstance(child, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal))
                    for child in ast.walk(node)
                ),
                "BASELINE_AST_NONPURE_DEPENDENCY",
            )
            selected.append(node)
            found.add(name)
    require(found == set(names) | set(constants) | set(classes), "BASELINE_AST_CLOSURE_MISSING")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *selected], type_ignores=[]))
    namespace = {"__name__": "pinned_baseline_pure_closure", **(environment or {})}
    exec(compile(module, "<hash-pinned-pure-baseline-closure>", "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in found})


def load_functions(root):
    paths = (
        "scripts/run_topology_d2_micro_pilot.py",
        "src/jbspan/topology.py",
        "scripts/pa_llama_topology_analysis_v1.py",
        "scripts/pa_llama_topology_search_comparison_v1.py",
        "tests/test_pa_llama_topology_search_comparison_v1.py",
    )
    loaded = {path: read_file(root, path) for path in paths}
    enum_source = ast.parse(loaded[paths[1]][0].decode("utf-8"))
    enum_nodes = [
        node
        for node in enum_source.body
        if isinstance(node, ast.ClassDef) and node.name == "RecoveryStatus"
    ]
    require(len(enum_nodes) == 1, "BASELINE_STATUS_ENUM_MISSING")
    members = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in enum_nodes[0].body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    status = Enum("RecoveryStatus", members, type=str)
    unit_closure = ast_closure(loaded[paths[2]][0], set(), constants={"UNIT_IDS"})
    require(unit_closure.UNIT_IDS == UNITS, "BASELINE_FROZEN_SOURCE_UNIT_ORDER_CHANGED")
    d2 = ast_closure(loaded[paths[0]][0], D2_FUNCTIONS, environment={"RecoveryStatus": status})
    comparison = ast_closure(
        loaded[paths[3]][0],
        COMPARISON_FUNCTIONS,
        constants={"SCHEMA", "UNIT_IDS", "ORDERS", "UNKNOWN", "STATUSES"},
        classes={"ComparisonError"},
        environment={
            "hashlib": hashlib,
            "itertools": itertools,
            "json": json,
            "re": re,
            "Counter": Counter,
        },
    )
    require(
        comparison.UNIT_IDS == UNITS
        and comparison.ORDERS == tuple(itertools.permutations(range(3))),
        "BASELINE_EXISTING_SIX_ORDERS_CHANGED",
    )
    return SimpleNamespace(
        d2=d2,
        comparison=comparison,
        status=status,
        source_pins=[value[1] for value in loaded.values()],
    )


def mask_units(mask):
    return tuple(unit for bit, unit in enumerate(UNITS) if mask & (1 << bit))


def unit_mask(units):
    require(
        len(units) == len(set(units)) and all(unit in UNITS for unit in units),
        "BASELINE_PREDICTED_UNIT_INVALID",
    )
    return sum(1 << UNITS.index(unit) for unit in units)


def summarize_method(name, observed, statuses, family, functions):
    if name == "all_singletons":
        predicted = [mask for mask in (1, 2, 4) if statuses[mask] == "RECOVERED"]
        queried = [1, 2, 4]
        reported_status = "OBSERVED_SINGLETON_SELECTION_NO_GLOBAL_CERTIFICATE"
    else:
        predicted = [unit_mask(value) for value in observed["predicted_sets"]]
        queried = [unit_mask(value) for value in observed["queried_subsets"]]
        require(len(set(queried)) == observed["query_count"], "BASELINE_QUERY_TRACE_CHANGED")
        reported_status = observed["status"]
    certified = family["certified_minimal_masks"]
    unresolved = family["unresolved_minimal_candidates"]
    exact = [mask_units(mask) for mask in certified]
    metrics = functions.d2.family_metrics(exact, [mask_units(mask) for mask in predicted])
    return {
        "method": name,
        "fixed_unit_order": list(UNITS),
        "historical_return_status_not_a_global_certificate": reported_status,
        "historical_one_minimal_flag_not_promoted": True,
        "predicted_masks": predicted,
        "predicted_unit_sets": [list(mask_units(mask)) for mask in predicted],
        "unique_query_trace_including_reference_neighbor_audit": [
            {"lookup_index": i, "mask_id": mask, "status": statuses[mask]}
            for i, mask in enumerate(queried)
        ],
        "oracle_distinct_query_count": len(set(queried)),
        "queried_unknown_masks": [
            mask for mask in queried if statuses[mask] in functions.comparison.UNKNOWN
        ],
        "certified_minima_returned": [mask for mask in certified if mask in predicted],
        "certified_minima_missed": [mask for mask in certified if mask not in predicted],
        "unresolved_candidates_returned": [mask for mask in unresolved if mask in predicted],
        "known_nonminimal_returned": [
            mask for mask in predicted if mask not in certified and mask not in unresolved
        ],
        "metrics_against_certified_family_only": metrics,
        "search_trace_alone_claims_strict_minimality": False,
        "unknown_means_not_recovered": False,
    }


def compare_tables(primary_rows, families, functions, *, source_identity_sha256):
    require(isinstance(families, list), "BASELINE_FAMILIES_REQUIRED")
    positions = [row["payload_position"] for row in families]
    six = functions.comparison.compare_search(
        primary_rows, all_payload_positions=positions, source_identity_sha256=source_identity_sha256
    )
    _, _, lookup = functions.comparison.normalize(primary_rows, positions)
    indexed = {row["payload_position"]: row for row in families}
    per_payload = []
    for reference in six["per_payload"]:
        position, exact = reference["payload_position"], reference["exhaustive_reference"]
        stored = indexed[position]
        require(
            stored["certified_minimal_masks"] == exact["certified_minimal_masks"]
            and stored["unresolved_minimal_candidates"] == exact["unresolved_minimal_candidates"]
            and stored["robust_recovery_masks"] == exact["recovered_masks"]
            and stored["unknown_masks"] == len(exact["unknown_masks"])
            and stored["known_masks"] == 8 - len(exact["unknown_masks"])
            and stored["truth_table_fully_identified"] is exact["all_eight_statuses_known"]
            and stored["minimum_certified_recovery_order"]
            == min((mask.bit_count() for mask in exact["certified_minimal_masks"]), default=None),
            "BASELINE_STAGE6_CERTIFIED_FAMILY_MISMATCH",
        )
        statuses = {mask: lookup[position, mask] for mask in range(8)}
        adapter = SimpleNamespace(
            unit_ids=UNITS,
            subset_decisions=[
                SimpleNamespace(
                    selected_unit_ids=mask_units(mask),
                    status=functions.status("INCOMPLETE" if value == "UNKNOWN" else value),
                )
                for mask, value in statuses.items()
            ],
        )
        methods = {
            "all_singletons": None,
            "greedy_backward": functions.d2.greedy_backward_baseline(adapter),
            "greedy_forward": functions.d2.greedy_forward_baseline(adapter),
        }
        per_payload.append(
            {
                "payload_position": position,
                "certified_minimal_masks": exact["certified_minimal_masks"],
                "unresolved_minimal_candidates": exact["unresolved_minimal_candidates"],
                "unknown_masks": exact["unknown_masks"],
                "methods": {
                    name: summarize_method(name, value, statuses, exact, functions)
                    for name, value in methods.items()
                },
            }
        )
    totals = {}
    for name in ("all_singletons", "greedy_backward", "greedy_forward"):
        values = [row["methods"][name] for row in per_payload]
        totals[name] = {
            "certified_minima_returned": sum(len(v["certified_minima_returned"]) for v in values),
            "certified_minima_missed": sum(len(v["certified_minima_missed"]) for v in values),
            "payloads_with_certified_minimum_missed": sum(
                bool(v["certified_minima_missed"]) for v in values
            ),
            "unresolved_candidates_returned": sum(
                len(v["unresolved_candidates_returned"]) for v in values
            ),
            "known_nonminimal_returned": sum(len(v["known_nonminimal_returned"]) for v in values),
            "oracle_distinct_query_count_summed_per_payload": sum(
                v["oracle_distinct_query_count"] for v in values
            ),
            "queried_unknown_count": sum(len(v["queried_unknown_masks"]) for v in values),
        }
    unions = [row["all_six_order_union"] for row in six["per_payload"]]
    return {
        "payload_denominator": len(positions),
        "primary_cell_denominator": len(primary_rows),
        "certified_family_denominator": sum(len(r["certified_minimal_masks"]) for r in per_payload),
        "payloads_with_certified_family": sum(
            bool(r["certified_minimal_masks"]) for r in per_payload
        ),
        "unknown_cell_count": sum(len(r["unknown_masks"]) for r in per_payload),
        "unresolved_candidate_count": sum(
            len(r["unresolved_minimal_candidates"]) for r in per_payload
        ),
        "per_payload": per_payload,
        "fixed_abc_method_totals": totals,
        "existing_all_six_order_comparison": six,
        "all_six_union_totals": {
            "certified_minima_reached_as_terminals": sum(
                len(v["certified_minima_reached_as_terminals"]) for v in unions
            ),
            "certified_minima_missed_as_terminals": sum(
                len(v["certified_minima_missed_as_terminals"]) for v in unions
            ),
            "unresolved_candidates_reached_as_terminals": sum(
                len(v["unresolved_candidates_reached_as_terminals"]) for v in unions
            ),
        },
    }


def validate_direction(direction, *, now=None, require_current_identity=True):
    verify_seal(direction, "direction_identity_sha256")
    require(
        direction.get("execution_identity") == EXECUTION
        and type(direction.get("stage")) is int
        and direction["stage"] == 7,
        "BASELINE_STAGE7_DIRECTION_REQUIRED",
    )
    if require_current_identity:
        require(
            direction["direction_identity_sha256"] == DIRECTION_ID,
            "BASELINE_CURRENT_STAGE7_DIRECTION_CHANGED",
        )
    issued = datetime.fromisoformat(direction["issued_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(direction["expires_at"].replace("Z", "+00:00"))
    require(
        issued.tzinfo is not None
        and expires.tzinfo is not None
        and 0 < (expires - issued).total_seconds() <= 7200
        and issued <= (now or datetime.now(timezone.utc)) <= expires,
        "BASELINE_STAGE7_DIRECTION_EXPIRED",
    )


def validate_bundle(stage6, stage7, direction):
    """Content identities and joins only; this supplement does not replay raw receipts."""
    for products in (stage6, stage7):
        proof = verify_seal(products["verification"], "verification_identity_sha256")
        verify_seal(proof["target_composite_proof"], "proof_identity_sha256")
        for key, value in products.items():
            if key != "verification" and value is not None:
                verify_seal(value)
                require(
                    proof["product_identity_sha256"][key] == value["result_identity_sha256"]
                    and proof["product_file_sha256"][key]
                    == hashlib.sha256(canonical(value) + b"\n").hexdigest(),
                    "BASELINE_PRODUCT_HASH_JOIN_CHANGED",
                )
        verify_seal(products["measurements"]["tables"])
        require(
            proof.get("actual_raw_verification_by_entrypoint") is True
            and proof.get("original_operational_gate_passed") is False
            and proof.get("first_continuation_operational_gate_passed") is False
            and proof.get("paper_validity") is False
            and proof.get("second_continuation_execution_identity") == EXECUTION,
            "BASELINE_UPSTREAM_SCOPE_CHANGED",
        )
    a, b = stage6["verification"], stage7["verification"]
    require(
        stage6["analysis"] is None
        and a["analysis_complete"] is False
        and b["analysis_complete"] is True
        and stage7["analysis"] is not None
        and stage6["measurements"] == stage7["measurements"]
        and a["target_composite_proof"] == b["target_composite_proof"]
        and a["axis_identity_sha256"] == b["axis_identity_sha256"]
        and b["current_stage_direction"] == direction,
        "BASELINE_STAGE6_STAGE7_INPUTS_OR_DIRECTION_CHANGED",
    )
    tables = stage6["measurements"]["tables"]
    result, analysis = stage7["result"], stage7["analysis"]
    require(
        analysis["upstream_declared_topology_aggregate_identity_sha256"]
        == tables["result_identity_sha256"]
        and result["analysis_identity_sha256"] == analysis["result_identity_sha256"]
        and result["measurements_identity_sha256"]
        == stage6["measurements"]["result_identity_sha256"]
        and result["table_identity_sha256"] == tables["result_identity_sha256"],
        "BASELINE_ANALYSIS_OR_TABLE_JOIN_CHANGED",
    )


def load_report(root):
    functions = load_functions(root)
    values, pins = {}, {}
    for relative in sorted(READ_PATHS):
        raw, pin = read_file(root, relative)
        pins[relative] = pin
        if relative.endswith(".json"):
            values[relative] = parse_safe_json(
                raw,
                require_canonical=(
                    relative == DIRECTION
                    or relative.startswith(f"{BASE}/finalization/with-analysis/")
                ),
            )
    direction = values[DIRECTION]
    validate_direction(direction)
    stage6 = {
        name: None
        if name == "analysis"
        else values[f"{BASE}/finalization/measurements-only/{name}.safe.json"]
        for name in PRODUCTS
    }
    stage7 = {
        name: values[f"{BASE}/finalization/with-analysis/{name}.safe.json"] for name in PRODUCTS
    }
    validate_bundle(stage6, stage7, direction)
    require(
        stage7["analysis"]["result_identity_sha256"] == STAGE7_ANALYSIS_ID
        and stage7["verification"]["verification_identity_sha256"] == STAGE7_VERIFICATION_ID,
        "BASELINE_CURRENT_STAGE7_PRODUCT_IDENTITY_CHANGED",
    )
    for name in ("measurements", "analysis", "result"):
        path = f"{BASE}/finalization/with-analysis/{name}.safe.json"
        require(
            pins[path]["sha256"] == stage7["verification"]["product_file_sha256"][name],
            "BASELINE_STAGE7_RAW_FILE_HASH_JOIN_CHANGED",
        )
    measured, analysis = stage6["measurements"], stage7["analysis"]
    table = measured["tables"]
    compared = compare_tables(
        table["primary_rows"],
        table["families"],
        functions,
        source_identity_sha256=table["result_identity_sha256"],
    )
    require(
        compared["payload_denominator"] == 21 and compared["primary_cell_denominator"] == 168,
        "BASELINE_CURRENT_STAGE6_POPULATION_CHANGED",
    )
    report = seal(
        {
            "schema_version": "pa-stage7-descriptive-baseline-supplement-v2",
            "execution_identity": EXECUTION,
            "stage": 7,
            "stage7_direction": direction,
            "stage7_analysis_identity_sha256": analysis["result_identity_sha256"],
            "stage7_verification_identity_sha256": stage7["verification"][
                "verification_identity_sha256"
            ],
            "stage6_measurements_identity_sha256": measured["result_identity_sha256"],
            "stage6_table_identity_sha256": table["result_identity_sha256"],
            "input_file_pins": [pins[path] for path in sorted(pins)],
            "source_pins": functions.source_pins,
            "existing_six_order_source_git_commit": SOURCE_COMMIT,
            "existing_six_order_source_execution_contract_pinned": False,
            "source_hash_snapshot_authenticated": True,
            "d2_imported_or_cli_called": False,
            "pure_ast_closure_only": True,
            "fixed_unit_order": list(UNITS),
            "unknown_adapter": "UNKNOWN_TO_INCOMPLETE_NOT_NEGATIVE",
            "comparison": compared,
            "query_accounting": {
                "unit": "LOOKUP_IN_ALREADY_MEASURED_AGGREGATED_PRIMARY_TABLE",
                "singletons_charge_masks": [1, 2, 4],
                "greedy_counts_include_initial_lookup_and_unique_neighbor_audit_lookups": True,
                "reference_table_cells": 168,
                "mask0_preexists_from_screen": True,
                "exact_oracle_certification_cost_is_separate_from_search_trace": True,
                "no_actual_matched_inference_budget_comparison": True,
                "query_cost_savings_claimed": False,
                "utility_superiority_claimed": False,
            },
            "all_six_existing_orders_reported_without_selection": True,
            "external_method_faithful_reproduction_claimed": False,
            "new_endpoint_or_practical_margin_introduced": False,
            "unknown_is_failure_or_absence": False,
            "scientific_primary_changed": False,
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
            "paper_validity": False,
            "raw_receipts_replayed_by_this_supplement": False,
            "upstream_safe_bytes_and_joins_verified": True,
            "new_model_calls": 0,
            "private_input_reads": 0,
            "automatic_next_stage": False,
        }
    )
    reverify(root, report)
    return report


def reverify(root, report):
    verify_seal(report)
    for expected in report["input_file_pins"]:
        _, actual = read_file(root, expected["path"])
        require(actual == expected, "BASELINE_INPUT_CHANGED_AFTER_COMPARISON")
    validate_direction(report["stage7_direction"])


def publish(root, report):
    reverify(root, report)
    identity = report["stage7_analysis_identity_sha256"]
    require(isinstance(identity, str) and SHA.fullmatch(identity), "BASELINE_ANALYSIS_ID_INVALID")
    relative = f"{BASE}/stage7-baselines/{identity}/baseline.safe.json"
    path = owned(root, relative)
    pending = owned(root, relative + ".pending")
    require(not path.exists() and not pending.exists(), "BASELINE_OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_links(path)
    with pending.open("xb") as handle:
        handle.write(canonical(report) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    reverify(root, report)
    reject_links(path)
    reject_links(pending)
    os.link(pending, path)
    pending.unlink()  # Only this invocation's new temporary publication link.
    return relative


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true", help="Requires prior source-review GO")
    args = parser.parse_args(argv)
    report = load_report(args.root)
    output = publish(args.root, report) if args.write else None
    print(
        canonical(
            {
                "result_identity_sha256": report["result_identity_sha256"],
                "output": output,
                "new_model_calls": 0,
                "summary": {
                    key: value
                    for key, value in report["comparison"].items()
                    if key not in {"per_payload", "existing_all_six_order_comparison"}
                },
            }
        ).decode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
