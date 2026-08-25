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


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSONL object: {path}")
        rows.append(cast(JsonObject, value))
    return rows


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_string_list(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


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
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


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


def human_label(row: JsonObject) -> tuple[int, bool]:
    votes: list[int] = []
    for key in ("human_0", "human_1", "human_2"):
        value = row.get(key)
        if isinstance(value, bool):
            votes.append(int(value))
        elif isinstance(value, int) and value in (0, 1):
            votes.append(value)
        else:
            raise ValueError(f"invalid human vote in {key}")
    return (1 if sum(votes) >= 2 else 0, len(set(votes)) == 1)


def private_record_id(behavior_id: str, row: JsonObject) -> str:
    private_identity = {
        "behavior_id": behavior_id,
        "test_case": row.get("test_case"),
        "generation": row.get("generation"),
        "model": row.get("model"),
        "method": row.get("method"),
        "experiment": row.get("experiment"),
        "human_0": row.get("human_0"),
        "human_1": row.get("human_1"),
        "human_2": row.get("human_2"),
    }
    if not isinstance(private_identity["test_case"], str):
        raise ValueError("validation row is missing test_case")
    if not isinstance(private_identity["generation"], str):
        raise ValueError("validation row is missing generation")
    return canonical_sha256(private_identity)


def validation_index(validation: JsonObject) -> dict[str, JsonObject]:
    index: dict[str, JsonObject] = {}
    for behavior_id, raw_rows in sorted(validation.items()):
        if not isinstance(behavior_id, str) or not isinstance(raw_rows, list):
            raise TypeError("validation must map behavior IDs to row arrays")
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise TypeError("validation rows must be objects")
            row = cast(JsonObject, raw_row)
            record_id = private_record_id(behavior_id, row)
            if record_id in index:
                raise ValueError("duplicate private validation record ID")
            label, unanimous = human_label(row)
            generation = row.get("generation")
            if not isinstance(generation, str):
                raise ValueError("validation row is missing generation")
            index[record_id] = {
                "record_id": record_id,
                "behavior_id_private": behavior_id,
                "behavior_hash": sha256_text(behavior_id),
                "label": label,
                "human_unanimous": unanimous,
                "generation_private": generation,
            }
    return index


def registry_rows(path: Path, id_field: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        behavior_id = row.get(id_field)
        if not behavior_id:
            raise ValueError(f"registry row lacks {id_field}: {path}")
        if behavior_id in result:
            raise ValueError(f"duplicate registry ID: {behavior_id}")
        result[behavior_id] = dict(row)
    return result


def combined_registry(
    text_registry: dict[str, dict[str, str]],
    multimodal_registry: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    result = dict(text_registry)
    result.update(multimodal_registry)
    return result


def reconstruct_selection(
    selection_rows: list[JsonObject],
    validation: dict[str, JsonObject],
    registry: dict[str, dict[str, str]],
    *,
    behavior_field: str,
    context_field: str,
) -> list[JsonObject]:
    positions = [row.get("position") for row in selection_rows]
    if positions != list(range(len(selection_rows))):
        raise ValueError("selection positions are not contiguous and ordered")
    seen: set[str] = set()
    reconstructed: list[JsonObject] = []
    for safe_row in selection_rows:
        record_id = safe_row.get("record_id")
        behavior_hash = safe_row.get("behavior_hash")
        label = safe_row.get("label")
        if not isinstance(record_id, str) or record_id in seen:
            raise ValueError("selection record IDs must be unique strings")
        seen.add(record_id)
        private = validation.get(record_id)
        if private is None:
            raise ValueError("selection record does not resolve in validation data")
        if private["behavior_hash"] != behavior_hash:
            raise ValueError("selection behavior hash mismatch")
        if private["label"] != label:
            raise ValueError("selection label mismatch")
        behavior_id = str(private["behavior_id_private"])
        registry_row = registry.get(behavior_id)
        if registry_row is None:
            raise ValueError("selection behavior does not resolve in registry")
        behavior = registry_row.get(behavior_field)
        context = registry_row.get(context_field)
        if not isinstance(behavior, str) or not isinstance(context, str):
            raise ValueError("selection registry row lacks required prompt fields")
        reconstructed.append(
            {
                "position": safe_row["position"],
                "record_id": record_id,
                "behavior_hash": behavior_hash,
                "label": label,
                "behavior_private": behavior,
                "context_private": context,
                "generation_private": private["generation_private"],
            }
        )
    return reconstructed


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
            raise KeyError(f"unresolved source name: {node.id}")
        return resolve_expression(
            assignments[node.id],
            assignments,
            resolving | frozenset({node.id}),
        )
    if isinstance(node, ast.IfExp):
        branch = node.body if resolve_condition(node.test, assignments) else node.orelse
        return resolve_expression(branch, assignments, resolving)
    raise TypeError(f"unsupported source expression: {type(node).__name__}")


def resolve_condition(node: ast.AST, assignments: dict[str, ast.AST]) -> bool:
    if not isinstance(node, ast.Compare):
        raise TypeError("only source comparisons are supported")
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise TypeError("only single source comparisons are supported")
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
        raise KeyError(f"missing source assignment: {name}")
    return resolve_expression(assignments[name], assignments, frozenset({name}))


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


def safe_prompt_manifest(
    reconstructed: list[JsonObject],
    prompt_family: JsonObject,
    *,
    plain_key: str,
    contextual_key: str,
) -> list[JsonObject]:
    plain_template = prompt_family.get(plain_key)
    contextual_template = prompt_family.get(contextual_key)
    if not isinstance(plain_template, str) or not isinstance(contextual_template, str):
        raise TypeError("prompt family lacks contracted template keys")
    manifest: list[JsonObject] = []
    for row in reconstructed:
        behavior = row["behavior_private"]
        context = row["context_private"]
        generation = row["generation_private"]
        if not all(isinstance(value, str) for value in (behavior, context, generation)):
            raise TypeError("private reconstruction fields must be strings")
        behavior_text = cast(str, behavior)
        context_text = cast(str, context)
        generation_text = cast(str, generation)
        context_present = bool(context_text)
        template_key = contextual_key if context_present else plain_key
        template = contextual_template if context_present else plain_template
        rendered = template.format(
            behavior=behavior_text,
            generation=generation_text,
            context=context_text,
        )
        manifest.append(
            {
                "position": row["position"],
                "record_id": row["record_id"],
                "behavior_hash": row["behavior_hash"],
                "label": row["label"],
                "template_key": template_key,
                "context_present": context_present,
                "behavior_sha256": sha256_text(behavior_text),
                "behavior_length": len(behavior_text),
                "context_sha256": sha256_text(context_text),
                "context_length": len(context_text),
                "generation_sha256": sha256_text(generation_text),
                "generation_length": len(generation_text),
                "rendered_prompt_sha256": sha256_text(rendered),
                "rendered_prompt_length": len(rendered),
            }
        )
    return manifest


def label_counts(rows: list[JsonObject]) -> dict[str, int]:
    counts: Counter[int] = Counter()
    for row in rows:
        label = row.get("label")
        if not isinstance(label, int) or isinstance(label, bool) or label not in (0, 1):
            raise ValueError("invalid binary label")
        counts[label] += 1
    return {"0": counts[0], "1": counts[1]}


def source_identity(source_root: Path, files: JsonObject) -> tuple[list[JsonObject], bool]:
    rows: list[JsonObject] = []
    passed = True
    for relative, expected in sorted(files.items()):
        path = source_root / relative
        observed = git_blob_sha(path) if path.is_file() else None
        match = observed == expected
        passed = passed and match
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "expected_git_blob_sha": expected,
                "observed_git_blob_sha": observed,
                "git_blob_match": match,
                "sha256": sha256_file(path) if path.is_file() else None,
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    return rows, passed


def verify_predecessors(root: Path, contract: JsonObject) -> dict[str, JsonObject]:
    predecessors = as_object(contract["predecessors"], where="predecessors")
    repair_contract = as_object(predecessors["selection_repair"], where="selection_repair")
    repair = load_object(root / str(repair_contract["result_path"]))
    repair_selection = as_object(repair["new_selection"], where="repair.new_selection")
    repair_expectations = {
        "status": repair_contract["required_status"],
        "operational_pass": repair_contract["required_operational_pass"],
        "next_authorized_operation": repair_contract["required_next_operation"],
        "harmbench_live_predictions_generated": repair_contract["required_live_predictions"],
    }
    for key, expected in repair_expectations.items():
        if repair.get(key) != expected:
            raise ValueError(f"selection repair predecessor mismatch: {key}")
    for key, contract_key in (
        ("record_count", "required_selection_record_count"),
        ("label_counts", "required_selection_label_counts"),
        ("behavior_count", "required_selection_behavior_count"),
        ("record_ids_sha256", "required_selection_record_ids_sha256"),
        ("safe_rows_sha256", "required_selection_safe_rows_sha256"),
    ):
        if repair_selection.get(key) != repair_contract[contract_key]:
            raise ValueError(f"selection repair identity mismatch: {key}")

    runtime_contract = as_object(predecessors["runtime_artifact_v2"], where="runtime")
    runtime = load_object(root / str(runtime_contract["result_path"]))
    selected_file = as_object(runtime["selected_file"], where="runtime.selected_file")
    runtime_expectations = {
        "status": runtime_contract["required_status"],
        "operational_pass": runtime_contract["required_operational_pass"],
        "official_source_repository": runtime_contract[
            "required_official_source_repository"
        ],
        "official_source_revision": runtime_contract["required_official_source_revision"],
        "candidate_repository": runtime_contract["required_candidate_repository"],
        "candidate_revision": runtime_contract["required_candidate_revision"],
    }
    for key, expected in runtime_expectations.items():
        if runtime.get(key) != expected:
            raise ValueError(f"runtime predecessor mismatch: {key}")
    for key, contract_key in (
        ("filename", "required_filename"),
        ("sha256", "required_sha256"),
        ("size", "required_size"),
    ):
        if selected_file.get(key) != runtime_contract[contract_key]:
            raise ValueError(f"runtime artifact identity mismatch: {key}")

    v2_contract = as_object(predecessors["prompt_source_v2"], where="prompt_source_v2")
    v2 = load_object(root / str(v2_contract["result_path"]))
    text_execution = as_object(v2["text_section_execution"], where="v2.text_execution")
    effective_prompt = as_object(
        text_execution["effective_prompt"], where="v2.effective_prompt"
    )
    v2_expectations = {
        "status": v2_contract["required_status"],
        "operational_pass": v2_contract["required_operational_pass"],
        "next_authorized_operation": v2_contract["required_next_operation"],
        "harmbench_live_predictions_generated": v2_contract["required_live_predictions"],
    }
    for key, expected in v2_expectations.items():
        if v2.get(key) != expected:
            raise ValueError(f"prompt-source v2 predecessor mismatch: {key}")
    if text_execution.get("effective_prompt_family") != v2_contract[
        "required_notebook_effective_prompt_family"
    ]:
        raise ValueError("notebook effective prompt family mismatch")
    if text_execution.get("loaded_model_argument") != v2_contract[
        "required_notebook_loaded_model"
    ]:
        raise ValueError("notebook loaded model mismatch")
    if text_execution.get("classifier_path") != v2_contract[
        "required_notebook_classifier_path"
    ]:
        raise ValueError("notebook classifier path mismatch")
    if text_execution.get("model_prompt_family_mismatch") is not v2_contract[
        "required_notebook_model_prompt_family_mismatch"
    ]:
        raise ValueError("notebook mismatch flag changed")
    if effective_prompt.get("canonical_family_sha256") != v2_contract[
        "required_notebook_prompt_canonical_sha256"
    ]:
        raise ValueError("notebook prompt identity mismatch")
    behavior_registry = as_object(v2["behavior_registry"], where="v2.behavior_registry")
    if behavior_registry.get("selected_missing_registry_row_count") != v2_contract[
        "required_selected_missing_registry_row_count"
    ]:
        raise ValueError("prompt-source v2 missing-row count changed")
    if behavior_registry.get("selected_notebook_unusable_row_count") != v2_contract[
        "required_selected_notebook_unusable_row_count"
    ]:
        raise ValueError("prompt-source v2 unusable-row count changed")
    v2_checks = as_object(v2["checks"], where="v2.checks")
    observed_false_checks = sorted(
        key for key, value in v2_checks.items() if value is False
    )
    expected_false_checks = sorted(
        as_string_list(
            v2_contract["required_false_checks"],
            where="prompt_source_v2.required_false_checks",
        )
    )
    if observed_false_checks != expected_false_checks:
        raise ValueError("prompt-source v2 failure-check set changed")

    return {
        "selection_repair": repair,
        "runtime_artifact_v2": runtime,
        "prompt_source_v2": v2,
    }


def run(
    root: Path,
    source_root: Path,
    config_path: Path,
    safe_output: Path,
    manifest_output: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_E1C_PROMPT_SOURCE_V3":
        raise ValueError("unexpected E1C prompt-source v3 status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("prompt-source v3 must be frozen and non-paper-valid")
    predecessors = verify_predecessors(root, contract)

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    observed_tree = git_tree_sha(source_root)
    source_rows, source_pass = source_identity(
        source_root, as_object(source["files"], where="harmbench_source.files")
    )

    selection_contract = as_object(contract["selection"], where="selection")
    selection_path = root / str(selection_contract["path"])
    selection_rows = load_jsonl(selection_path)
    selection_record_ids = [str(row.get("record_id")) for row in selection_rows]
    selection_summary = {
        "file_sha256": sha256_file(selection_path),
        "record_count": len(selection_rows),
        "label_counts": label_counts(selection_rows),
        "behavior_count": len({str(row.get("behavior_hash")) for row in selection_rows}),
        "record_ids_sha256": canonical_sha256(selection_record_ids),
        "safe_rows_sha256": canonical_sha256(selection_rows),
        "raw_records_recorded": False,
    }

    validation_contract = as_object(contract["validation"], where="validation")
    validation = validation_index(
        load_object(source_root / str(validation_contract["path"]))
    )
    registry_contract = as_object(contract["registry"], where="registry")
    if registry_contract.get("update_order") != ["text_csv", "multimodal_csv"]:
        raise ValueError("unexpected registry update order")
    id_field = str(registry_contract["required_id_field"])
    text_registry = registry_rows(
        source_root / str(registry_contract["text_csv"]), id_field
    )
    multimodal_registry = registry_rows(
        source_root / str(registry_contract["multimodal_csv"]), id_field
    )
    registry = combined_registry(text_registry, multimodal_registry)
    reconstructed = reconstruct_selection(
        selection_rows,
        validation,
        registry,
        behavior_field=str(registry_contract["required_behavior_field"]),
        context_field=str(registry_contract["required_context_field"]),
    )

    primary = as_object(contract["primary_execution"], where="primary_execution")
    prompt_assignments = assignments_from_tree(
        ast.parse((source_root / str(primary["prompt_source_file"])).read_text(
            encoding="utf-8"
        ))
    )
    primary_prompt = as_object(
        resolve_name(str(primary["prompt_family"]), prompt_assignments),
        where="primary prompt family",
    )
    primary_summary = prompt_summary(primary_prompt)
    expected_summary = as_object(
        primary["expected_prompt_summary"], where="expected_prompt_summary"
    )
    expected_summary_with_boundary = dict(expected_summary)
    expected_summary_with_boundary["raw_prompt_recorded"] = False

    manifest = safe_prompt_manifest(
        reconstructed,
        primary_prompt,
        plain_key=str(primary["plain_template_key"]),
        contextual_key=str(primary["contextual_template_key"]),
    )
    manifest_repeat = safe_prompt_manifest(
        reconstructed,
        primary_prompt,
        plain_key=str(primary["plain_template_key"]),
        contextual_key=str(primary["contextual_template_key"]),
    )
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    with manifest_output.open("w", encoding="utf-8") as handle:
        for row in manifest:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    template_counts = Counter(str(row["template_key"]) for row in manifest)
    context_count = sum(int(row["context_present"] is True) for row in manifest)
    manifest_summary = {
        "record_count": len(manifest),
        "label_counts": label_counts(manifest),
        "template_counts": dict(sorted(template_counts.items())),
        "contextual_record_count": context_count,
        "plain_record_count": len(manifest) - context_count,
        "record_ids_sha256": canonical_sha256(
            [str(row["record_id"]) for row in manifest]
        ),
        "canonical_rows_sha256": canonical_sha256(manifest),
        "file_sha256": sha256_file(manifest_output),
        "deterministic": manifest == manifest_repeat,
        "raw_text_recorded": False,
    }

    notebook_contract = as_object(
        contract["notebook_diagnostic"], where="notebook_diagnostic"
    )
    v2 = predecessors["prompt_source_v2"]
    text_execution = as_object(v2["text_section_execution"], where="v2.text_execution")
    notebook_effective_prompt = as_object(
        text_execution["effective_prompt"], where="v2.effective_prompt"
    )
    runtime = predecessors["runtime_artifact_v2"]
    selected_runtime_file = as_object(runtime["selected_file"], where="runtime.file")

    expected_labels = as_object(
        selection_contract["required_label_counts"], where="required_label_counts"
    )
    manifest_contract = as_object(contract["safe_manifest"], where="safe_manifest")
    required_manifest_fields = set(
        as_string_list(
            manifest_contract["required_fields"],
            where="safe_manifest.required_fields",
        )
    )
    manifest_fields_match = all(set(row) == required_manifest_fields for row in manifest)
    checks = {
        "source_tree_matches": observed_tree == source["tree_sha"],
        "source_files_match": source_pass,
        "selection_file_sha256_matches": (
            selection_summary["file_sha256"] == selection_contract["required_file_sha256"]
        ),
        "selection_record_count_matches": (
            selection_summary["record_count"] == selection_contract["required_record_count"]
        ),
        "selection_label_counts_match": (
            selection_summary["label_counts"] == expected_labels
        ),
        "selection_behavior_count_matches": (
            selection_summary["behavior_count"] == selection_contract["required_behavior_count"]
        ),
        "selection_record_identity_matches": (
            selection_summary["record_ids_sha256"]
            == selection_contract["required_record_ids_sha256"]
        ),
        "selection_safe_rows_identity_matches": (
            selection_summary["safe_rows_sha256"]
            == selection_contract["required_safe_rows_sha256"]
        ),
        "all_selection_rows_reconstructed": len(reconstructed) == len(selection_rows),
        "all_reconstructed_record_ids_unique": (
            len({str(row["record_id"]) for row in reconstructed}) == len(reconstructed)
        ),
        "primary_prompt_summary_matches": primary_summary == expected_summary_with_boundary,
        "primary_model_matches_runtime_source": (
            primary["model_repository"] == runtime["official_source_repository"]
            and primary["model_revision"] == runtime["official_source_revision"]
        ),
        "runtime_artifact_identity_present": (
            selected_runtime_file.get("filename") is not None
            and selected_runtime_file.get("sha256") is not None
        ),
        "notebook_diagnostic_matches_predecessor": (
            text_execution["effective_prompt_family"]
            == notebook_contract["effective_prompt_family"]
            and text_execution["loaded_model_argument"]
            == notebook_contract["loaded_model_argument"]
            and text_execution["classifier_path"] == notebook_contract["classifier_path"]
            and text_execution["model_prompt_family_mismatch"]
            is notebook_contract["model_prompt_family_mismatch"]
            and notebook_effective_prompt["canonical_family_sha256"]
            == notebook_contract["effective_prompt_canonical_sha256"]
        ),
        "primary_and_notebook_prompt_families_are_distinct": (
            primary_summary["canonical_family_sha256"]
            != notebook_effective_prompt["canonical_family_sha256"]
        ),
        "manifest_record_count_matches": len(manifest) == len(selection_rows),
        "manifest_label_counts_match": label_counts(manifest) == expected_labels,
        "manifest_record_identity_matches_selection": (
            manifest_summary["record_ids_sha256"]
            == selection_summary["record_ids_sha256"]
        ),
        "manifest_fields_match_contract": manifest_fields_match,
        "manifest_output_filename_matches": (
            manifest_output.name == manifest_contract["output_filename"]
        ),
        "manifest_deterministic": manifest_summary["deterministic"] is True,
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_live_predictions": True,
    }
    passed = all(checks.values())
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-prompt-source-freeze-v3-result-v1",
        "status": (
            "E1C_PROMPT_SOURCE_FREEZE_V3_PASS"
            if passed
            else "E1C_PROMPT_SOURCE_FREEZE_V3_FAIL"
        ),
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": sha256_file(config_path),
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": source["tree_sha"],
            "observed_tree_sha": observed_tree,
            "files": source_rows,
        },
        "selection": selection_summary,
        "reconstruction": {
            "record_count": len(reconstructed),
            "validation_index_count": len(validation),
            "text_registry_count": len(text_registry),
            "multimodal_registry_count": len(multimodal_registry),
            "combined_registry_count": len(registry),
            "raw_behavior_generation_or_context_recorded": False,
        },
        "primary_execution": {
            "model_repository": primary["model_repository"],
            "model_revision": primary["model_revision"],
            "runtime_artifact": {
                "repository": runtime["candidate_repository"],
                "revision": runtime["candidate_revision"],
                "filename": selected_runtime_file["filename"],
                "sha256": selected_runtime_file["sha256"],
                "size": selected_runtime_file["size"],
            },
            "prompt_source_file": primary["prompt_source_file"],
            "prompt_family": primary["prompt_family"],
            "decoder_temperature": primary["decoder_temperature"],
            "decoder_max_tokens": primary["decoder_max_tokens"],
            "prompt_summary": primary_summary,
        },
        "notebook_diagnostic": {
            "role": notebook_contract["role"],
            "effective_prompt_family": text_execution["effective_prompt_family"],
            "loaded_model_argument": text_execution["loaded_model_argument"],
            "classifier_path": text_execution["classifier_path"],
            "model_prompt_family_mismatch": text_execution[
                "model_prompt_family_mismatch"
            ],
            "effective_prompt_canonical_sha256": notebook_effective_prompt[
                "canonical_family_sha256"
            ],
            "cached_cls_is_primary_reference": False,
            "human_majority_is_primary_reference": True,
        },
        "safe_manifest": manifest_summary,
        "checks": checks,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["on_pass"] if passed else gate["on_fail"],
    }
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze E1C prompt-source v3 identities")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        args.root.resolve(),
        args.source_root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
        args.manifest_output.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "selection": result["selection"],
                "safe_manifest": result["safe_manifest"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
