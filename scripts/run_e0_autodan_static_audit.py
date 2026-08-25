from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity is SHA-1.


def load_config(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("contract must be a JSON object")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_string_list(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def literal_value(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def assignment_literal(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return literal_value(node.value)
    return None


def argparse_defaults(module: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if not node.args:
            continue
        flag = literal_value(node.args[0])
        if not isinstance(flag, str) or not flag.startswith("--"):
            continue
        default: object = None
        for keyword in node.keywords:
            if keyword.arg == "default":
                default = literal_value(keyword.value)
                break
        values[flag[2:].replace("-", "_")] = default
    return values


def dict_assignment_keys(module: ast.Module, name: str) -> list[str]:
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            return []
        keys: list[str] = []
        for key in node.value.keys:
            value = literal_value(key) if key is not None else None
            if isinstance(value, str):
                keys.append(value)
        return keys
    return []


def is_self_instruction_lower(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or node.args or node.keywords:
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "lower":
        return False
    value = node.func.value
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "instruction"
        and isinstance(value.value, ast.Name)
        and value.value.id == "self"
    )


def detect_official_payload_replacement(module: ast.Module, placeholder: str) -> bool:
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "replace":
            continue
        if len(node.args) < 2:
            continue
        first = literal_value(node.args[0])
        if first == placeholder and is_self_instruction_lower(node.args[1]):
            return True
    return False


def call_keyword_name(call: ast.Call, keyword_name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        if isinstance(keyword.value, ast.Name):
            return keyword.value.id
        if isinstance(keyword.value, ast.Attribute):
            return keyword.value.attr
    return None


def detect_suffix_manager_wiring(module: ast.Module) -> bool:
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        else:
            continue
        if function_name != "autodan_SuffixManager":
            continue
        return (
            call_keyword_name(node, "instruction") == "user_prompt"
            and call_keyword_name(node, "target") == "target"
            and call_keyword_name(node, "adv_string") == "adv_suffix"
        )
    return False


def protected_terms_in_function(module: ast.Module, function_name: str) -> set[str]:
    for node in ast.walk(module):
        if not isinstance(node, ast.FunctionDef) or node.name != function_name:
            continue
        values: set[str] = set()
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Set):
                continue
            for element in inner.elts:
                value = literal_value(element)
                if isinstance(value, str):
                    values.add(value.lower())
        return values
    return set()


def file_identity_rows(source_root: Path, files: JsonObject) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for role, raw in sorted(files.items()):
        spec = as_object(raw, where=f"source.files.{role}")
        relative = Path(str(spec["path"]))
        path = source_root / relative
        expected_blob = str(spec["git_blob_sha"])
        exists = path.is_file()
        observed_blob = git_blob_sha(path) if exists else None
        rows.append(
            {
                "role": role,
                "path": relative.as_posix(),
                "exists": exists,
                "expected_git_blob_sha": expected_blob,
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": observed_blob == expected_blob,
                "sha256": sha256_file(path) if exists else None,
                "size_bytes": path.stat().st_size if exists else None,
            }
        )
    return rows


def materialization_summary(
    template: str,
    placeholder: str,
    payload: str,
    repetitions: int,
) -> JsonObject:
    official_outputs = [template.replace(placeholder, payload.lower()) for _ in range(repetitions)]
    adapter_outputs = [template.replace(placeholder, payload) for _ in range(repetitions)]
    official_hashes = [sha256_bytes(item.encode()) for item in official_outputs]
    adapter_hashes = [sha256_bytes(item.encode()) for item in adapter_outputs]
    lower_payload = payload.lower()
    return {
        "repetitions": repetitions,
        "template_placeholder_occurrences": template.count(placeholder),
        "official_route": {
            "deterministic": len(set(official_hashes)) == 1,
            "output_sha256": official_hashes[0],
            "exact_payload_occurrences": official_outputs[0].count(payload),
            "lowercased_payload_occurrences": official_outputs[0].count(lower_payload),
            "placeholder_occurrences_after_materialization": official_outputs[0].count(
                placeholder
            ),
            "byte_invariant": official_outputs[0].encode().count(payload.encode()) == 1,
        },
        "exact_placeholder_adapter": {
            "deterministic": len(set(adapter_hashes)) == 1,
            "output_sha256": adapter_hashes[0],
            "exact_payload_occurrences": adapter_outputs[0].count(payload),
            "exact_payload_byte_occurrences": adapter_outputs[0].encode().count(
                payload.encode()
            ),
            "placeholder_occurrences_after_materialization": adapter_outputs[0].count(
                placeholder
            ),
            "payload_preserved": (
                adapter_outputs[0].count(payload) == 1
                and adapter_outputs[0].encode().count(payload.encode()) == 1
            ),
        },
        "rendered_text_recorded": False,
    }


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_config(config_path)
    if config["status"] != "FROZEN_BEFORE_AUTODAN_STATIC_EXECUTION":
        raise ValueError("unexpected contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid contract boundary")

    source = as_object(config["source"], where="source")
    files = as_object(source["files"], where="source.files")
    rules = as_object(config["rules"], where="rules")
    expected_defaults = as_object(
        config["expected_entrypoint_defaults"], where="expected_entrypoint_defaults"
    )
    target = as_object(config["target_compatibility"], where="target_compatibility")
    admission = as_object(config["admission"], where="admission")
    gate = as_object(config["decision_gate"], where="decision_gate")

    identity_rows = file_identity_rows(source_root, files)
    identities_pass = all(row["git_blob_match"] is True for row in identity_rows)

    def source_path(role: str) -> Path:
        return source_root / str(as_object(files[role], where=role)["path"])

    license_text = source_path("license").read_text(encoding="utf-8")
    license_pass = license_text.startswith("MIT License")

    initial_prompt = source_path("initial_prompt").read_text(encoding="utf-8")
    string_module = ast.parse(source_path("string_utils").read_text(encoding="utf-8"))
    ga_module = ast.parse(source_path("ga_entrypoint").read_text(encoding="utf-8"))
    hga_module = ast.parse(source_path("hga_entrypoint").read_text(encoding="utf-8"))
    opt_path = source_path("opt_utils")
    opt_text = opt_path.read_text(encoding="utf-8")
    opt_module = ast.parse(opt_text)

    payload = str(config["synthetic_payload"])
    placeholder = str(config["placeholder"])
    repetitions = int(config["fresh_materialization_repetitions"])
    materialization = materialization_summary(
        initial_prompt, placeholder, payload, repetitions
    )

    lowercasing_detected = detect_official_payload_replacement(
        string_module, placeholder
    )
    ga_wiring_pass = detect_suffix_manager_wiring(ga_module)
    hga_wiring_pass = detect_suffix_manager_wiring(hga_module)

    ga_defaults = argparse_defaults(ga_module)
    observed_defaults = {
        "seed": assignment_literal(ga_module, "seed"),
        "num_steps": ga_defaults.get("num_steps"),
        "batch_size": ga_defaults.get("batch_size"),
        "model": ga_defaults.get("model"),
    }
    defaults_pass = observed_defaults == expected_defaults

    model_keys = dict_assignment_keys(ga_module, "model_path_dicts")
    expected_model_keys = as_string_list(
        config["expected_official_model_keys"], where="expected_official_model_keys"
    )
    model_keys_match = model_keys == expected_model_keys
    current_target_name = str(target["current_project_target"])
    current_target_supported = any(
        current_target_name.lower() in item.lower() for item in model_keys
    )

    gpt_mutation_placeholder_protected = (
        "Do not change the words" in opt_text and placeholder in opt_text
    )
    synonym_terms = protected_terms_in_function(opt_module, "replace_with_synonyms")
    hga_terms = protected_terms_in_function(
        opt_module, "replace_with_best_synonym"
    )
    local_synonym_placeholder_protected = "replace" in synonym_terms
    hga_placeholder_protected = "replace" in hga_terms

    prompt_group = source_path("prompt_group")
    prompt_group_prefix = prompt_group.read_bytes()[:16]
    prompt_group_summary = {
        "path": prompt_group.relative_to(source_root).as_posix(),
        "sha256": sha256_file(prompt_group),
        "size_bytes": prompt_group.stat().st_size,
        "first_16_bytes_sha256": sha256_bytes(prompt_group_prefix),
        "deserialized": False,
        "deserialization_forbidden_by_contract": (
            rules["binary_prompt_group_deserialization_allowed"] is False
        ),
    }

    initial_placeholder_count = int(materialization["template_placeholder_occurrences"])
    official = as_object(materialization["official_route"], where="official_route")
    adapter = as_object(
        materialization["exact_placeholder_adapter"],
        where="exact_placeholder_adapter",
    )

    mandatory_checks = {
        "source_identities": identities_pass,
        "license": license_pass,
        "initial_placeholder_count": (
            initial_placeholder_count
            == int(rules["initial_prompt_placeholder_occurrence_count"])
        ),
        "official_lowercasing_detected": (
            lowercasing_detected
            is bool(rules["official_route_must_be_detected_as_lowercasing_instruction"])
        ),
        "official_route_non_invariant_detected": (
            official["byte_invariant"] is bool(rules["official_route_is_byte_invariant"])
        ),
        "exact_adapter_payload_preservation": adapter["payload_preserved"] is True,
        "exact_adapter_placeholder_removed": (
            int(adapter["placeholder_occurrences_after_materialization"]) == 0
        ),
        "ga_suffix_manager_wiring": ga_wiring_pass,
        "hga_suffix_manager_wiring": hga_wiring_pass,
        "entrypoint_defaults": defaults_pass,
        "official_model_keys": model_keys_match,
        "prompt_group_not_deserialized": prompt_group_summary["deserialized"] is False,
    }
    audit_pass = all(mandatory_checks.values())

    blockers: list[str] = []
    if official["byte_invariant"] is not True:
        blockers.append("OFFICIAL_SUFFIX_MANAGER_LOWERCASES_PAYLOAD")
    if current_target_supported is not bool(
        target["current_project_target_officially_supported"]
    ):
        blockers.append("TARGET_COMPATIBILITY_CONTRACT_MISMATCH")
    if not current_target_supported:
        blockers.append("CURRENT_QWEN_TARGET_NOT_IN_OFFICIAL_MODEL_MAP")
    if not local_synonym_placeholder_protected:
        blockers.append("LOCAL_SYNONYM_MUTATION_DOES_NOT_PROTECT_REPLACE_TOKEN")
    if not hga_placeholder_protected:
        blockers.append("HGA_SYNONYM_REPLACEMENT_DOES_NOT_PROTECT_REPLACE_TOKEN")
    blockers.append("OFFICIAL_FINAL_OPTIMIZED_PROMPT_ARTIFACT_ROUTE_NOT_ESTABLISHED")
    blockers.append("REGENERATION_COMPUTE_AND_SELECTION_BUDGET_NOT_FROZEN")

    status = (
        "E0_AUTODAN_STATIC_AUDIT_CONDITIONAL_ADVANCE"
        if audit_pass
        else "E0_AUTODAN_STATIC_AUDIT_FAIL"
    )
    next_operation = (
        gate["on_audit_pass"] if audit_pass else gate["on_audit_fail"]
    )

    result: JsonObject = {
        "schema_version": "e0-autodan-static-adapter-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": audit_pass,
        "family": admission["family"],
        "regime": admission["regime"],
        "family_admitted_to_balanced_signal_screen": False,
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "tree_sha": source["tree_sha"],
            "license": source["license"],
            "file_identities": identity_rows,
        },
        "config_sha256": sha256_file(config_path),
        "synthetic_payload_sha256": sha256_bytes(payload.encode()),
        "synthetic_payload_character_length": len(payload),
        "materialization": materialization,
        "source_analysis": {
            "official_lowercase_replacement_detected": lowercasing_detected,
            "ga_suffix_manager_wiring_pass": ga_wiring_pass,
            "hga_suffix_manager_wiring_pass": hga_wiring_pass,
            "observed_entrypoint_defaults": observed_defaults,
            "expected_entrypoint_defaults": expected_defaults,
            "entrypoint_defaults_match": defaults_pass,
            "official_model_keys": model_keys,
            "official_model_keys_match": model_keys_match,
            "current_project_target": current_target_name,
            "current_project_target_officially_supported": current_target_supported,
            "gpt_mutation_prompt_protects_placeholder": (
                gpt_mutation_placeholder_protected
            ),
            "local_synonym_protected_terms_sha256": sha256_bytes(
                "\n".join(sorted(synonym_terms)).encode()
            ),
            "local_synonym_placeholder_protected": (
                local_synonym_placeholder_protected
            ),
            "hga_protected_terms_sha256": sha256_bytes(
                "\n".join(sorted(hga_terms)).encode()
            ),
            "hga_placeholder_protected": hga_placeholder_protected,
        },
        "prompt_group_artifact": prompt_group_summary,
        "mandatory_checks": mandatory_checks,
        "blockers_before_admission": sorted(set(blockers)),
        "required_follow_up": admission["required_follow_up"],
        "real_harmful_payload_used": False,
        "target_model_called": False,
        "raw_rendered_prompt_committed": False,
        "binary_artifact_deserialized": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": next_operation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pinned AutoDAN E0 static audit")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_audit(args.config, args.source_root, args.output)
    summary = {
        "status": result["status"],
        "operational_pass": result["operational_pass"],
        "family_admitted_to_balanced_signal_screen": result[
            "family_admitted_to_balanced_signal_screen"
        ],
        "blocker_count": len(cast(list[object], result["blockers_before_admission"])),
        "next_authorized_operation": result["next_authorized_operation"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
