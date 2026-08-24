from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode("utf-8") + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def git_tree_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def assignments_from_tree(tree: ast.Module) -> dict[str, ast.AST]:
    assignments: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments[node.target.id] = node.value
    return assignments


def notebook_assignments(notebook_path: Path) -> dict[str, ast.AST]:
    notebook = load_object(notebook_path)
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise TypeError("notebook cells must be a list")
    assignments: dict[str, ast.AST] = {}
    for raw_cell in cells:
        if not isinstance(raw_cell, dict) or raw_cell.get("cell_type") != "code":
            continue
        source = raw_cell.get("source", "")
        if isinstance(source, list):
            code = "".join(str(part) for part in source)
        else:
            code = str(source)
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        assignments.update(assignments_from_tree(tree))
    return assignments


def resolve_expression(
    node: ast.AST,
    assignments: dict[str, ast.AST],
    resolving: frozenset[str] = frozenset(),
) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        return ast.literal_eval(node)
    if isinstance(node, ast.Name):
        if node.id in resolving:
            raise ValueError(f"cyclic assignment involving {node.id}")
        if node.id not in assignments:
            raise KeyError(f"unresolved notebook name: {node.id}")
        return resolve_expression(
            assignments[node.id],
            assignments,
            resolving | frozenset({node.id}),
        )
    if isinstance(node, ast.IfExp):
        branch = node.body if resolve_condition(node.test, assignments) else node.orelse
        return resolve_expression(branch, assignments, resolving)
    raise TypeError(f"unsupported expression: {type(node).__name__}")


def resolve_condition(node: ast.AST, assignments: dict[str, ast.AST]) -> bool:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        raise TypeError("only single notebook comparisons are supported")
    left = resolve_expression(node.left, assignments)
    right = resolve_expression(node.comparators[0], assignments)
    operator = node.ops[0]
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    raise TypeError(f"unsupported comparison: {type(operator).__name__}")


def resolve_name(name: str, assignments: dict[str, ast.AST]) -> object:
    if name not in assignments:
        raise KeyError(f"missing assignment: {name}")
    return resolve_expression(assignments[name], assignments, frozenset({name}))


def selected_ifexp_family(name: str, assignments: dict[str, ast.AST]) -> str:
    node = assignments.get(name)
    if not isinstance(node, ast.IfExp):
        raise TypeError(f"{name} is not an if-expression")
    selected = node.body if resolve_condition(node.test, assignments) else node.orelse
    if not isinstance(selected, ast.Name):
        raise TypeError(f"{name} branch is not a named prompt family")
    return selected.id


def call_keyword(name: str, keyword: str, assignments: dict[str, ast.AST]) -> object:
    node = assignments.get(name)
    if not isinstance(node, ast.Call):
        raise TypeError(f"{name} is not a call assignment")
    for item in node.keywords:
        if item.arg == keyword:
            return resolve_expression(item.value, assignments)
    raise KeyError(f"{name} call lacks keyword {keyword}")


def prompt_summary(value: object) -> JsonObject:
    prompt = as_object(value, where="prompt family")
    plain = prompt.get("prompt")
    contextual = prompt.get("prompt_contextual")
    if not isinstance(plain, str) or not isinstance(contextual, str):
        raise TypeError("prompt family must contain prompt and prompt_contextual strings")
    return {
        "field_names": sorted(str(key) for key in prompt),
        "prompt_length": len(plain),
        "prompt_sha256": sha256_text(plain),
        "prompt_contextual_length": len(contextual),
        "prompt_contextual_sha256": sha256_text(contextual),
        "canonical_family_sha256": canonical_sha256(prompt),
        "raw_prompt_recorded": False,
    }


def verify_predecessors(root: Path, contract: JsonObject) -> None:
    predecessors = as_object(contract["predecessors"], where="predecessors")
    for name in ("e1c_preflight", "runtime_artifact_v2"):
        predecessor = as_object(predecessors[name], where=name)
        result = load_object(root / str(predecessor["result_path"]))
        if result.get("status") != predecessor["required_status"]:
            raise ValueError(f"{name} status mismatch")
        if result.get("operational_pass") is not predecessor["required_operational_pass"]:
            raise ValueError(f"{name} operational gate mismatch")
        required_next = predecessor.get("required_next_operation")
        if required_next is not None and result.get("next_authorized_operation") != required_next:
            raise ValueError(f"{name} authorization mismatch")


def source_identity(source_root: Path, source: JsonObject) -> tuple[list[JsonObject], bool]:
    expected_files = as_object(source["files"], where="harmbench_source.files")
    rows: list[JsonObject] = []
    passed = True
    for relative_path, expected_blob in sorted(expected_files.items()):
        path = source_root / relative_path
        exists = path.is_file()
        observed_blob = git_blob_sha(path) if exists else None
        matches = observed_blob == expected_blob
        passed = passed and matches
        rows.append(
            {
                "path": relative_path,
                "exists": exists,
                "expected_git_blob_sha": expected_blob,
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": matches,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": sha256_file(path) if exists else None,
            }
        )
    return rows, passed


def validation_summary(validation_path: Path, behavior_csv_path: Path) -> JsonObject:
    validation = load_object(validation_path)
    record_count = 0
    cached_counts: Counter[int] = Counter()
    invalid_cached_count = 0
    behavior_ids = set(validation)
    for raw_rows in validation.values():
        if not isinstance(raw_rows, list):
            raise TypeError("validation behavior entries must be lists")
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise TypeError("validation rows must be objects")
            record_count += 1
            cached = raw_row.get("cls")
            if isinstance(cached, int) and not isinstance(cached, bool) and cached in (0, 1):
                cached_counts[cached] += 1
            else:
                invalid_cached_count += 1

    with behavior_csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    csv_behavior_ids = {
        str(row["BehaviorID"])
        for row in csv_rows
        if isinstance(row.get("BehaviorID"), str) and row["BehaviorID"]
    }
    missing = sorted(behavior_ids - csv_behavior_ids)
    return {
        "validation_record_count": record_count,
        "validation_behavior_count": len(behavior_ids),
        "cached_cls_present_count": sum(cached_counts.values()),
        "cached_cls_label_counts": {
            "0": cached_counts[0],
            "1": cached_counts[1],
        },
        "cached_cls_invalid_count": invalid_cached_count,
        "behavior_csv_row_count": len(csv_rows),
        "validation_behaviors_missing_from_csv_count": len(missing),
        "validation_behaviors_missing_from_csv_hash": canonical_sha256(missing),
        "raw_test_case_or_generation_recorded": False,
    }


def run(root: Path, source_root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_E1C_PROMPT_SOURCE_EXTRACTION":
        raise ValueError("unexpected E1C prompt source freeze status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("prompt source freeze must be frozen and non-paper-valid")
    verify_predecessors(root, contract)

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    observed_tree = git_tree_sha(source_root)
    expected_tree = str(source["tree_sha"])
    source_files, source_files_pass = source_identity(source_root, source)

    notebook_path = source_root / "notebooks/run_classifier_val_set.ipynb"
    eval_utils_path = source_root / "eval_utils.py"
    validation_path = source_root / "data/classifier_val_sets/text_behaviors_val_set.json"
    behavior_csv_path = source_root / "data/behavior_datasets/harmbench_behaviors_text_all.csv"

    notebook = notebook_assignments(notebook_path)
    production = assignments_from_tree(ast.parse(eval_utils_path.read_text(encoding="utf-8")))

    test_classifier_path = resolve_name("test_classifier_path", notebook)
    val_classifier_path = resolve_name("val_classifier_path", notebook)
    classifier_path = resolve_name("classifier_path", notebook)
    loaded_model_argument = call_keyword("cls", "model", notebook)
    effective_prompt_family = selected_ifexp_family("PROMPT", notebook)
    effective_prompt = resolve_name("PROMPT", notebook)
    temperature = call_keyword("cls_params", "temperature", notebook)
    max_tokens = call_keyword("cls_params", "max_tokens", notebook)
    model_prompt_family_mismatch = (
        loaded_model_argument == test_classifier_path
        and effective_prompt_family != "LLAMA2_CLS_PROMPT"
    )

    notebook_expectation = as_object(
        contract["notebook_effective_execution"], where="notebook_effective_execution"
    )
    production_expectation = as_object(
        contract["production_execution"], where="production_execution"
    )
    production_prompt_family = str(production_expectation["prompt_family"])
    production_prompt = resolve_name(production_prompt_family, production)

    dataset = validation_summary(validation_path, behavior_csv_path)
    checks = {
        "source_tree_matches": observed_tree == expected_tree,
        "source_file_blobs_match": source_files_pass,
        "test_classifier_path_matches": (
            test_classifier_path == notebook_expectation["expected_test_classifier_path"]
        ),
        "val_classifier_path_matches": (
            val_classifier_path == notebook_expectation["expected_val_classifier_path"]
        ),
        "classifier_path_matches": (
            classifier_path == notebook_expectation["expected_classifier_path"]
        ),
        "loaded_model_argument_matches": (
            loaded_model_argument == notebook_expectation["expected_loaded_model_argument"]
        ),
        "effective_prompt_family_matches": (
            effective_prompt_family == notebook_expectation["expected_effective_prompt_family"]
        ),
        "model_prompt_family_mismatch_matches": (
            model_prompt_family_mismatch
            is notebook_expectation["expected_model_prompt_family_mismatch"]
        ),
        "temperature_matches": temperature == notebook_expectation["expected_temperature"],
        "max_tokens_matches": max_tokens == notebook_expectation["expected_max_tokens"],
        "all_cached_cls_binary": dataset["cached_cls_invalid_count"] == 0,
        "all_validation_behavior_ids_in_csv": (
            dataset["validation_behaviors_missing_from_csv_count"] == 0
        ),
        "notebook_and_production_prompt_families_are_distinct": (
            effective_prompt_family != production_prompt_family
        ),
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_live_predictions": True,
    }
    passed = all(checks.values())
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-prompt-source-freeze-result-v1",
        "status": (
            "E1C_PROMPT_SOURCE_FREEZE_PASS" if passed else "E1C_PROMPT_SOURCE_FREEZE_FAIL"
        ),
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": sha256_file(config_path),
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": expected_tree,
            "observed_tree_sha": observed_tree,
            "files": source_files,
        },
        "notebook_effective_execution": {
            "test_classifier_path": test_classifier_path,
            "val_classifier_path": val_classifier_path,
            "classifier_path": classifier_path,
            "loaded_model_argument": loaded_model_argument,
            "effective_prompt_family": effective_prompt_family,
            "model_prompt_family_mismatch": model_prompt_family_mismatch,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "effective_prompt": prompt_summary(effective_prompt),
        },
        "production_execution": {
            "prompt_family": production_prompt_family,
            "temperature": production_expectation["decoder_temperature"],
            "max_tokens": production_expectation["decoder_max_tokens"],
            "prompt": prompt_summary(production_prompt),
        },
        "dataset": dataset,
        "checks": checks,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["on_pass"] if passed else gate["on_fail"],
    }
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze E1C official prompt source identities")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        args.root.resolve(),
        args.source_root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "notebook_effective_execution": result["notebook_effective_execution"],
                "production_execution": result["production_execution"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
