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


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"expected JSONL objects: {path}")
            rows.append(cast(JsonObject, value))
    return rows


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
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


def cell_source(cell: JsonObject) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def notebook_cells(path: Path) -> list[JsonObject]:
    notebook = load_object(path)
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise TypeError("notebook cells must be a list")
    result: list[JsonObject] = []
    for raw_cell in cells:
        if not isinstance(raw_cell, dict):
            raise TypeError("notebook cell must be an object")
        result.append(cast(JsonObject, raw_cell))
    return result


def resolve_condition(node: ast.AST, assignments: dict[str, ast.AST]) -> bool:
    if not isinstance(node, ast.Compare):
        raise TypeError("only notebook comparisons are supported")
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise TypeError("only single notebook comparisons are supported")
    left = resolve_expression(node.left, assignments)
    right = resolve_expression(node.comparators[0], assignments)
    operator = node.ops[0]
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    raise TypeError(f"unsupported comparison: {type(operator).__name__}")


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
        raise TypeError(f"{name} selected branch is not a named prompt family")
    return selected.id


def call_keyword(name: str, keyword: str, assignments: dict[str, ast.AST]) -> object:
    node = assignments.get(name)
    if not isinstance(node, ast.Call):
        raise TypeError(f"{name} is not a call assignment")
    for item in node.keywords:
        if item.arg == keyword:
            return resolve_expression(item.value, assignments)
    raise KeyError(f"{name} call lacks keyword {keyword}")


def replay_until_text_input(
    notebook_path: Path,
    required_heading: str,
    target_input_file: str,
) -> tuple[dict[str, ast.AST], int, object]:
    assignments: dict[str, ast.AST] = {}
    heading_seen = False
    for index, cell in enumerate(notebook_cells(notebook_path)):
        cell_type = cell.get("cell_type")
        source = cell_source(cell)
        if cell_type == "markdown":
            if source.strip() == required_heading:
                heading_seen = True
            continue
        if cell_type != "code":
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        current = assignments_from_tree(tree)
        assignments.update(current)
        if heading_seen and "input_file" in current:
            input_file = resolve_name("input_file", assignments)
            if input_file == target_input_file:
                return assignments, index, cell.get("execution_count")
    raise RuntimeError("target text-validation input cell was not found")


def prompt_summary(value: object) -> JsonObject:
    prompt = as_object(value, where="prompt family")
    plain = prompt.get("prompt")
    contextual = prompt.get("prompt_contextual")
    if not isinstance(plain, str) or not isinstance(contextual, str):
        raise TypeError("prompt family lacks prompt or prompt_contextual")
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
    for name in ("source_freeze_v1_failure", "runtime_artifact_v2"):
        predecessor = as_object(predecessors[name], where=name)
        result = load_object(root / str(predecessor["result_path"]))
        if result.get("status") != predecessor["required_status"]:
            raise ValueError(f"{name} status mismatch")
        if result.get("operational_pass") is not predecessor["required_operational_pass"]:
            raise ValueError(f"{name} operational gate mismatch")
        required_next = predecessor.get("required_next_operation")
        if required_next is not None:
            if result.get("next_authorized_operation") != required_next:
                raise ValueError(f"{name} authorization mismatch")
        required_live = predecessor.get("required_live_predictions")
        if required_live is not None:
            if result.get("harmbench_live_predictions_generated") is not required_live:
                raise ValueError(f"{name} live-output boundary mismatch")


def source_identity(source_root: Path, source: JsonObject) -> tuple[list[JsonObject], bool]:
    expected = as_object(source["files"], where="harmbench_source.files")
    rows: list[JsonObject] = []
    passed = True
    for relative, expected_blob in sorted(expected.items()):
        path = source_root / relative
        exists = path.is_file()
        observed_blob = git_blob_sha(path) if exists else None
        matches = observed_blob == expected_blob
        passed = passed and matches
        rows.append(
            {
                "path": relative,
                "exists": exists,
                "expected_git_blob_sha": expected_blob,
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": matches,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": sha256_file(path) if exists else None,
            }
        )
    return rows, passed


def read_registry(path: Path, id_field: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    registry: dict[str, dict[str, str]] = {}
    for row in rows:
        behavior_id = row.get(id_field)
        if not behavior_id:
            raise ValueError(f"registry row lacks {id_field}: {path}")
        if behavior_id in registry:
            raise ValueError(f"duplicate behavior ID in registry: {path}")
        registry[behavior_id] = dict(row)
    return registry


def validation_summary(path: Path, cached_field: str) -> tuple[set[str], JsonObject]:
    validation = load_object(path)
    cached_counts: Counter[int] = Counter()
    invalid_cached = 0
    record_count = 0
    for raw_rows in validation.values():
        if not isinstance(raw_rows, list):
            raise TypeError("validation entries must be row lists")
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise TypeError("validation rows must be objects")
            record_count += 1
            cached = raw_row.get(cached_field)
            if isinstance(cached, int) and not isinstance(cached, bool) and cached in (0, 1):
                cached_counts[cached] += 1
            else:
                invalid_cached += 1
    return set(validation), {
        "record_count": record_count,
        "behavior_count": len(validation),
        "cached_prediction_count": sum(cached_counts.values()),
        "cached_label_counts": {"0": cached_counts[0], "1": cached_counts[1]},
        "invalid_cached_prediction_count": invalid_cached,
        "raw_validation_text_recorded": False,
    }


def registry_coverage(
    validation_ids: set[str],
    selection_rows: list[JsonObject],
    text_registry: dict[str, dict[str, str]],
    multimodal_registry: dict[str, dict[str, str]],
    behavior_field: str,
    context_field: str,
) -> JsonObject:
    registry = dict(text_registry)
    overlap_ids = set(text_registry) & set(multimodal_registry)
    registry.update(multimodal_registry)

    hash_to_id: dict[str, str] = {}
    collision_hashes: set[str] = set()
    for behavior_id in registry:
        digest = sha256_text(behavior_id)
        if digest in hash_to_id and hash_to_id[digest] != behavior_id:
            collision_hashes.add(digest)
        hash_to_id[digest] = behavior_id

    text_missing = sorted(sha256_text(item) for item in validation_ids - set(text_registry))
    union_missing_ids = validation_ids - set(registry)
    union_missing = sorted(sha256_text(item) for item in union_missing_ids)
    union_unusable_ids = {
        behavior_id
        for behavior_id in validation_ids & set(registry)
        if behavior_field not in registry[behavior_id]
        or context_field not in registry[behavior_id]
    }
    union_unusable = sorted(sha256_text(item) for item in union_unusable_ids)

    selected_missing_rows = 0
    selected_unusable_rows = 0
    selected_missing_hashes: set[str] = set()
    selected_unusable_hashes: set[str] = set()
    for row in selection_rows:
        behavior_hash = row.get("behavior_hash")
        if not isinstance(behavior_hash, str):
            raise TypeError("selection row lacks behavior_hash")
        behavior_id = hash_to_id.get(behavior_hash)
        if behavior_id is None:
            selected_missing_rows += 1
            selected_missing_hashes.add(behavior_hash)
            continue
        source_row = registry[behavior_id]
        if behavior_field not in source_row or context_field not in source_row:
            selected_unusable_rows += 1
            selected_unusable_hashes.add(behavior_hash)

    return {
        "text_registry_count": len(text_registry),
        "multimodal_registry_count": len(multimodal_registry),
        "registry_overlap_count": len(overlap_ids),
        "union_registry_count": len(registry),
        "behavior_hash_collision_count": len(collision_hashes),
        "behavior_hash_collisions": sorted(collision_hashes),
        "full_validation_missing_from_text_count": len(text_missing),
        "full_validation_missing_from_text_hashes": text_missing,
        "full_validation_missing_from_union_count": len(union_missing),
        "full_validation_missing_from_union_hashes": union_missing,
        "full_validation_notebook_unusable_count": len(union_unusable),
        "full_validation_notebook_unusable_hashes": union_unusable,
        "selected_record_count": len(selection_rows),
        "selected_missing_registry_row_count": selected_missing_rows,
        "selected_missing_behavior_hashes": sorted(selected_missing_hashes),
        "selected_notebook_unusable_row_count": selected_unusable_rows,
        "selected_notebook_unusable_behavior_hashes": sorted(selected_unusable_hashes),
        "raw_behavior_ids_or_text_recorded": False,
    }


def selection_summary(rows: list[JsonObject]) -> JsonObject:
    labels: Counter[int] = Counter()
    for row in rows:
        label = row.get("label")
        if isinstance(label, int) and not isinstance(label, bool) and label in (0, 1):
            labels[label] += 1
        else:
            raise ValueError("selection row has invalid label")
    return {
        "record_count": len(rows),
        "label_counts": {"0": labels[0], "1": labels[1]},
        "record_ids_sha256": canonical_sha256([row.get("record_id") for row in rows]),
        "raw_records_recorded": False,
    }


def run(root: Path, source_root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_E1C_TEXT_SECTION_SOURCE_REPLAY":
        raise ValueError("unexpected E1C source-freeze v2 status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("source-freeze v2 must be frozen and non-paper-valid")
    verify_predecessors(root, contract)

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    expected_tree = str(source["tree_sha"])
    observed_tree = git_tree_sha(source_root)
    source_files, source_files_pass = source_identity(source_root, source)

    replay = as_object(contract["text_section_replay"], where="text_section_replay")
    notebook_path = source_root / "notebooks/run_classifier_val_set.ipynb"
    assignments, target_cell_index, execution_count = replay_until_text_input(
        notebook_path,
        str(replay["required_markdown_heading"]),
        str(replay["target_input_file"]),
    )
    test_classifier_path = resolve_name("test_classifier_path", assignments)
    val_classifier_path = resolve_name("val_classifier_path", assignments)
    classifier_path = resolve_name("classifier_path", assignments)
    loaded_model_argument = call_keyword("cls", "model", assignments)
    effective_prompt_family = selected_ifexp_family("PROMPT", assignments)
    effective_prompt = resolve_name("PROMPT", assignments)
    temperature = call_keyword("cls_params", "temperature", assignments)
    max_tokens = call_keyword("cls_params", "max_tokens", assignments)
    model_prompt_family_mismatch = (
        loaded_model_argument == test_classifier_path
        and effective_prompt_family != "LLAMA2_CLS_PROMPT"
    )

    production = as_object(contract["production_execution"], where="production_execution")
    production_assignments = assignments_from_tree(
        ast.parse((source_root / "eval_utils.py").read_text(encoding="utf-8"))
    )
    production_family = str(production["prompt_family"])
    production_prompt = resolve_name(production_family, production_assignments)

    registry_contract = as_object(
        contract["behavior_registry_replay"], where="behavior_registry_replay"
    )
    id_field = str(registry_contract["required_id_field"])
    behavior_field = str(registry_contract["required_behavior_field"])
    context_field = str(registry_contract["required_notebook_context_field"])
    text_registry = read_registry(source_root / str(registry_contract["text_csv"]), id_field)
    multimodal_registry = read_registry(
        source_root / str(registry_contract["multimodal_csv"]), id_field
    )

    validation_path = source_root / "data/classifier_val_sets/text_behaviors_val_set.json"
    validation_ids, validation = validation_summary(
        validation_path, str(replay["cached_prediction_field"])
    )
    selection_contract = as_object(contract["frozen_selection"], where="frozen_selection")
    selection_rows = load_jsonl(root / str(selection_contract["path"]))
    selection = selection_summary(selection_rows)
    coverage = registry_coverage(
        validation_ids,
        selection_rows,
        text_registry,
        multimodal_registry,
        behavior_field,
        context_field,
    )

    expected_labels = as_object(
        selection_contract["required_label_counts"], where="required_label_counts"
    )
    checks = {
        "source_tree_matches": observed_tree == expected_tree,
        "source_file_blobs_match": source_files_pass,
        "text_target_cell_found": target_cell_index >= 0,
        "test_classifier_path_matches": (
            test_classifier_path == replay["expected_test_classifier_path"]
        ),
        "val_classifier_path_matches": (
            val_classifier_path == replay["expected_val_classifier_path"]
        ),
        "classifier_path_matches": classifier_path == replay["expected_classifier_path"],
        "loaded_model_argument_matches": (
            loaded_model_argument == replay["expected_loaded_model_argument"]
        ),
        "effective_prompt_family_matches": (
            effective_prompt_family == replay["expected_effective_prompt_family"]
        ),
        "model_prompt_family_mismatch_matches": (
            model_prompt_family_mismatch
            is replay["expected_model_prompt_family_mismatch"]
        ),
        "temperature_matches": temperature == replay["expected_temperature"],
        "max_tokens_matches": max_tokens == replay["expected_max_tokens"],
        "notebook_and_production_prompt_families_are_distinct": (
            effective_prompt_family != production_family
        ),
        "all_cached_predictions_binary": (
            validation["invalid_cached_prediction_count"] == 0
        ),
        "selection_record_count_matches": (
            selection["record_count"] == selection_contract["required_record_count"]
        ),
        "selection_label_counts_match": selection["label_counts"] == expected_labels,
        "behavior_hashes_collision_free": coverage["behavior_hash_collision_count"] == 0,
        "all_selected_rows_resolve_in_notebook_registry": (
            coverage["selected_missing_registry_row_count"] == 0
        ),
        "all_selected_rows_have_notebook_required_fields": (
            coverage["selected_notebook_unusable_row_count"] == 0
        ),
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_live_predictions": True,
    }
    passed = all(checks.values())
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-prompt-source-freeze-v2-result-v1",
        "status": (
            "E1C_PROMPT_SOURCE_FREEZE_V2_PASS"
            if passed
            else "E1C_PROMPT_SOURCE_FREEZE_V2_FAIL"
        ),
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": sha256_file(config_path),
        "v1_resolution": {
            "failure_class": "CROSS_SECTION_LAST_ASSIGNMENT_OVERWRITE",
            "v1_result_preserved": True,
            "scientific_contract_changed": False,
            "live_predictions_observed_before_resolution": False,
        },
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": expected_tree,
            "observed_tree_sha": observed_tree,
            "files": source_files,
        },
        "text_section_execution": {
            "target_cell_index": target_cell_index,
            "target_cell_execution_count": execution_count,
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
            "prompt_family": production_family,
            "temperature": production["decoder_temperature"],
            "max_tokens": production["decoder_max_tokens"],
            "prompt": prompt_summary(production_prompt),
        },
        "validation": validation,
        "selection": selection,
        "behavior_registry": coverage,
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
    parser = argparse.ArgumentParser(description="Replay E1C text-section source state")
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
                "text_section_execution": result["text_section_execution"],
                "behavior_registry": result["behavior_registry"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
