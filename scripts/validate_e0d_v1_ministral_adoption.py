from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
MIB = 1024 * 1024

EXPECTED = {
    "v1_contract": "bc80bbdb59e50275afae78a41c76c2e51b94de84c030a6cea7c2f093979c592f",
    "v1_runner": "d1eeddbbf6af42e79fa2514657114047ff65c61b550855d5fa19b1c8ba97c589",
    "repair_runner": "8ed681d8b3fe401589d021849f6048e9e774f43fb77a31bbcd40ad168f8530f7",
    "v1_summary": "eaf5bf15cff8ad9c6aeb4e0e8f6cc32a27788785af30903a808dfe301517c33e",
    "v1_axes": "af02b790e732390f54021f6aba1ff9fb025e013b4ad0ce3775968bb4a6714d38",
}

CRITICAL_FUNCTIONS = (
    "render_external",
    "chat_completion",
    "execution_identity",
    "run_judge",
    "axes_from_judge_rows",
    "run_ga_screen",
    "run_wildguard",
    "run_finalize",
)

UNCHANGED_CONTRACT_FIELDS = (
    "external_calibration",
    "heldout_policy",
    "static_external_projection",
    "prompt_contract",
    "source_limits",
    "runtime",
    "judge_generation",
    "wildguard_generation",
    "wildguard_canary_parity",
    "A_profiles",
    "calibration_selection_gates",
    "selection_rule",
    "sound_fail_fast",
)

PROHIBITED_SAFE_KEYS = {
    "prompt",
    "prompt_text",
    "raw_output",
    "response_text",
    "system_prompt",
    "user_prompt",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def function_hashes(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(CRITICAL_FUNCTIONS) - functions.keys())
    if missing:
        raise ValueError(f"missing critical functions in {path}: {missing}")
    return {
        name: hashlib.sha256(
            ast.dump(functions[name], include_attributes=False).encode("utf-8")
        ).hexdigest()
        for name in CRITICAL_FUNCTIONS
    }


def judge_without_paths(contract: JsonObject, judge_id: str) -> JsonObject:
    judges = contract.get("judges")
    if not isinstance(judges, list):
        raise TypeError("contract judges must be a list")
    judge = next(
        cast(JsonObject, value)
        for value in judges
        if isinstance(value, dict) and value.get("judge_id") == judge_id
    )
    result = dict(judge)
    result.pop("safe_output_path", None)
    result.pop("safe_summary_path", None)
    return result


def assert_no_private_text_keys(value: object, *, location: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PROHIBITED_SAFE_KEYS:
                raise ValueError(f"private text key at {location}.{key}")
            assert_no_private_text_keys(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_private_text_keys(child, location=f"{location}[{index}]")


def validate_axes(path: Path) -> JsonObject:
    axis_counts: Counter[str] = Counter()
    record_ids: dict[str, set[str]] = {"guided": set(), "actionability": set()}
    identities: set[str] = set()
    rows = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw: object = json.loads(line)
        if not isinstance(raw, dict):
            raise TypeError(f"non-object at {path}:{line_number}")
        row = cast(JsonObject, raw)
        assert_no_private_text_keys(row, location=f"row[{line_number}]")
        axis = str(row.get("axis"))
        if axis not in record_ids:
            raise ValueError(f"unexpected axis at line {line_number}: {axis}")
        if row.get("judge_id") != "ministral_3_3b_instruct_2512_q4_k_m":
            raise ValueError(f"unexpected judge at line {line_number}")
        if row.get("base_family") != "mistral":
            raise ValueError(f"unexpected family at line {line_number}")
        if row.get("eligible_measurement") is not True:
            raise ValueError(f"ineligible predecessor row at line {line_number}")
        if row.get("context_budget_pass") is not True:
            raise ValueError(f"context failure at line {line_number}")
        parsed = row.get("parsed")
        if not isinstance(parsed, dict):
            raise TypeError(f"missing parsed object at line {line_number}")
        if parsed.get("parse_error") is not False or parsed.get("canary_pass") is not True:
            raise ValueError(f"parse or canary failure at line {line_number}")
        record_id = str(row.get("record_id"))
        identity = str(row.get("execution_identity_sha256"))
        if record_id in record_ids[axis]:
            raise ValueError(f"duplicate record/axis at line {line_number}")
        if identity in identities:
            raise ValueError(f"duplicate execution identity at line {line_number}")
        record_ids[axis].add(record_id)
        identities.add(identity)
        axis_counts[axis] += 1
        rows += 1
    if axis_counts != {"guided": 889, "actionability": 889}:
        raise ValueError(f"unexpected predecessor axis counts: {axis_counts}")
    if record_ids["guided"] != record_ids["actionability"]:
        raise ValueError("guided and actionability record sets differ")
    return {
        "rows": rows,
        "axis_counts": dict(sorted(axis_counts.items())),
        "unique_records": len(record_ids["guided"]),
        "unique_execution_identities": len(identities),
        "all_rows_eligible_parse_valid_and_canary_valid": True,
        "private_text_keys_present": False,
    }


def run(root: Path, output: Path) -> JsonObject:
    paths = {
        "v1_contract": root / "configs/evaluator_panel/external_calibration_e0d.json",
        "v1_runner": root / "scripts/run_evaluator_panel_external_calibration_e0d.py",
        "repair_contract": root
        / "configs/evaluator_panel/external_calibration_e0d_v1_1.json",
        "repair_runner": root
        / "scripts/run_evaluator_panel_external_calibration_e0d_v1_1.py",
        "v1_summary": root
        / "data/evaluator_panel_v2/e0d_ministral_judge_execution.safe.json",
        "v1_axes": root
        / "data/evaluator_panel_v2/e0d_ministral_judge_axes.safe.jsonl",
        "v1_failure": root
        / "data/evaluator_panel_v2/e0d_v1_implementation_failure.safe.json",
    }
    observed = {name: file_sha256(path) for name, path in paths.items()}
    for name, expected in EXPECTED.items():
        if observed[name] != expected:
            raise ValueError(f"frozen {name} SHA-256 mismatch")

    old_contract = load_object(paths["v1_contract"])
    repair_contract = load_object(paths["repair_contract"])
    failure = load_object(paths["v1_failure"])
    summary = load_object(paths["v1_summary"])

    unequal_fields = [
        name
        for name in UNCHANGED_CONTRACT_FIELDS
        if old_contract.get(name) != repair_contract.get(name)
    ]
    if unequal_fields:
        raise ValueError(f"scientific contract fields changed: {unequal_fields}")
    old_judge = judge_without_paths(old_contract, "ministral_3_3b_instruct_2512_q4_k_m")
    repair_judge = judge_without_paths(
        repair_contract, "ministral_3_3b_instruct_2512_q4_k_m"
    )
    if old_judge != repair_judge:
        raise ValueError("Ministral judge specification changed")

    old_functions = function_hashes(paths["v1_runner"])
    repair_functions = function_hashes(paths["repair_runner"])
    if old_functions != repair_functions:
        changed = [
            name
            for name in CRITICAL_FUNCTIONS
            if old_functions[name] != repair_functions[name]
        ]
        raise ValueError(f"scientific execution functions changed: {changed}")

    parity = summary.get("server_mode_e0c_parity")
    if not isinstance(parity, dict):
        raise TypeError("missing V1 Ministral parity summary")
    if not (
        parity.get("pass") is True
        and parity.get("all_byte_identical_to_e0c") is True
        and parity.get("case_count") == 5
    ):
        raise ValueError("V1 Ministral did not pass the stronger raw-byte parity gate")
    if not all(
        isinstance(row, dict)
        and row.get("request_completed") is True
        and row.get("finish_reason") == "stop"
        and row.get("matches_e0c_response_sha256") is True
        and row.get("parse_pass") is True
        and row.get("semantic_pass") is True
        for row in cast(list[object], parity.get("cases", []))
    ):
        raise ValueError("V1 Ministral parity case failure")
    if not (
        summary.get("status") == "E0D_CALIBRATION_JUDGE_EXECUTION_COMPLETE"
        and summary.get("contract_sha256") == EXPECTED["v1_contract"]
        and summary.get("runner_sha256") == EXPECTED["v1_runner"]
        and summary.get("axis_rows") == 1778
        and summary.get("eligible_measurements") == 1778
        and summary.get("parse_or_canary_failures") == 0
        and summary.get("context_budget_failures") == 0
        and summary.get("heldout_opened") is False
    ):
        raise ValueError("V1 Ministral execution summary is not adoptable")
    if failure.get("governed_repair", {}).get("prompts_changed") is not False:
        raise ValueError("failure record does not freeze unchanged prompts")
    axes = validate_axes(paths["v1_axes"])

    result: JsonObject = {
        "schema_version": "jbspan-e0d-v1-ministral-adoption-safe-v1",
        "status": "E0D_V1_MINISTRAL_EVIDENCE_ADOPTION_VALIDATED",
        "adoption_valid": True,
        "paper_validity": False,
        "panel_qualified": False,
        "evidence_class": "NO_INFERENCE_PREDECESSOR_EVIDENCE_ADOPTION",
        "validator_sha256": file_sha256(Path(__file__).resolve()),
        "v1_contract_sha256": observed["v1_contract"],
        "v1_runner_sha256": observed["v1_runner"],
        "repair_contract_sha256": observed["repair_contract"],
        "repair_runner_sha256": observed["repair_runner"],
        "v1_failure_sha256": observed["v1_failure"],
        "adopted_summary_sha256": observed["v1_summary"],
        "adopted_axes_sha256": observed["v1_axes"],
        "critical_execution_function_ast_sha256": old_functions,
        "unchanged_scientific_contract_fields": list(UNCHANGED_CONTRACT_FIELDS),
        "ministral_specification_equal_ignoring_safe_output_paths": True,
        "v1_raw_byte_parity_pass_is_stronger_than_repaired_normalized_parity": True,
        "adopted_axes": axes,
        "adoption_policy": {
            "adopt_by_frozen_reference_without_rewriting_execution_identities": True,
            "model_inference_performed_during_adoption": False,
            "model_outputs_or_parsed_values_changed": False,
            "v1_1_partial_rerun_records_used": False,
            "phi_evidence_adopted": False,
            "heldout_or_p3_opened": False,
        },
        "result_identity_scheme": (
            "SHA256_of_UTF8_canonical_sorted_compact_JSON_ensure_ascii_false_"
            "with_result_identity_sha256_omitted"
        ),
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    atomic_write_json(output, result)
    reloaded = load_object(output)
    declared = str(reloaded.pop("result_identity_sha256"))
    if declared != canonical_sha256(reloaded):
        raise RuntimeError("adoption result identity failed after serialization")
    return load_object(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/evaluator_panel_v2/e0d_v1_ministral_adoption.safe.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    result = run(root, output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "adoption_valid": result["adoption_valid"],
                "rows": result["adopted_axes"]["rows"],
                "result_identity_sha256": result["result_identity_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
