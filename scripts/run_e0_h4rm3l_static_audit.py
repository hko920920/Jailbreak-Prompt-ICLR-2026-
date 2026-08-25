from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
import types
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


def literal_only(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, int, float, bool, type(None)))
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(literal_only(item) for item in node.elts)
    return False


def components_from_node(node: ast.AST, *, allowed: set[str]) -> list[str]:
    if not isinstance(node, ast.Call):
        raise ValueError("decorator expression must be a call")

    if isinstance(node.func, ast.Name):
        name = node.func.id
        if name not in allowed:
            raise ValueError(f"component is not allowlisted: {name}")
        if not all(literal_only(item) for item in node.args):
            raise ValueError(f"non-literal positional argument in {name}")
        keywords_are_literal = all(
            keyword.arg is not None and literal_only(keyword.value)
            for keyword in node.keywords
        )
        if not keywords_are_literal:
            raise ValueError(f"non-literal keyword argument in {name}")
        return [name]

    if isinstance(node.func, ast.Attribute) and node.func.attr == "then":
        if node.keywords or len(node.args) != 1:
            raise ValueError("then() must have exactly one positional component")
        return components_from_node(node.func.value, allowed=allowed) + components_from_node(
            node.args[0], allowed=allowed
        )

    raise ValueError("only allowlisted decorator calls and .then() composition are permitted")


def components_from_expression(expression: str, *, allowed: set[str]) -> list[str]:
    parsed = ast.parse(expression, mode="eval")
    return components_from_node(parsed.body, allowed=allowed)


def class_names_from_source(path: Path) -> set[str]:
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in parsed.body if isinstance(node, ast.ClassDef)}


def load_config(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("contract must be a JSON object")
    return cast(JsonObject, value)


def string_list(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def object_list(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{where} must be an object array")
    return cast(list[JsonObject], value)


def load_h4rm3l(source_root: Path) -> tuple[types.ModuleType, Path, dict[str, int]]:
    package_dir = source_root / "h4rm3l" / "src" / "h4rm3l"
    decorators_path = package_dir / "decorators.py"
    if not decorators_path.is_file():
        raise FileNotFoundError(f"pinned source is missing: {decorators_path}")

    prompt_counter = {"calls": 0}
    package = types.ModuleType("h4rm3l")
    package.__path__ = [str(package_dir)]
    sys.modules["h4rm3l"] = package

    prompter = types.ModuleType("h4rm3l.prompter")

    def forbidden_prompt_model(*args: object, **kwargs: object) -> str:
        del args, kwargs
        prompt_counter["calls"] += 1
        raise RuntimeError("model prompting is forbidden in the E0 static audit")

    prompter.prompt_model = forbidden_prompt_model
    sys.modules["h4rm3l.prompter"] = prompter

    resources = types.ModuleType("h4rm3l.decorator_resources")
    resources.__path__ = [str(package_dir / "decorator_resources")]
    sys.modules["h4rm3l.decorator_resources"] = resources

    spec = importlib.util.spec_from_file_location("h4rm3l.decorators", decorators_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load h4rm3l.decorators")
    module = importlib.util.module_from_spec(spec)
    sys.modules["h4rm3l.decorators"] = module
    spec.loader.exec_module(module)
    return module, decorators_path, prompt_counter


def compile_and_render(
    module: types.ModuleType,
    *,
    expression: str,
    payload: str,
    syntax_version: int,
) -> str:
    compiler = getattr(module, "make_prompt_decorator", None)
    if not callable(compiler):
        raise RuntimeError("make_prompt_decorator is unavailable")
    args = argparse.Namespace(
        decorator_syntax_version=syntax_version,
        synthesis_model_name="DISABLED_IN_STATIC_AUDIT",
    )
    decorator = compiler(expression, credentials=None, args=args)
    if not callable(decorator):
        raise RuntimeError("expression did not compile")
    rendered = decorator(payload)
    if not isinstance(rendered, str):
        raise TypeError("decorator returned a non-string")
    return rendered


def audit_expression(
    module: types.ModuleType,
    row: JsonObject,
    *,
    payload: str,
    allowed: set[str],
    blocked: set[str],
    repetitions: int,
    syntax_version: int,
    expected_occurrences: int,
    null_allowed: bool,
) -> JsonObject:
    expression_id = str(row["id"])
    expression = str(row["expression"])
    expected_components = string_list(
        row["expected_components"], where=f"{expression_id}.expected_components"
    )
    components = components_from_expression(expression, allowed=allowed)
    outputs = [
        compile_and_render(
            module,
            expression=expression,
            payload=payload,
            syntax_version=syntax_version,
        )
        for _ in range(repetitions)
    ]
    hashes = [sha256_bytes(output.encode("utf-8")) for output in outputs]
    text_counts = [output.count(payload) for output in outputs]
    byte_counts = [output.encode().count(payload.encode()) for output in outputs]
    null_counts = [output.count("\x00") for output in outputs]

    deterministic = len(set(hashes)) == 1
    payload_preserved = all(count == expected_occurrences for count in text_counts)
    byte_preserved = all(count == expected_occurrences for count in byte_counts)
    blocked_overlap = sorted(blocked.intersection(components))
    manifest_match = components == expected_components
    null_rule_pass = null_allowed or all(count == 0 for count in null_counts)
    passed = all(
        (
            deterministic,
            payload_preserved,
            byte_preserved,
            manifest_match,
            not blocked_overlap,
            null_rule_pass,
        )
    )

    return {
        "id": expression_id,
        "expression_sha256": sha256_bytes(expression.encode()),
        "components": components,
        "component_count": len(components),
        "manifest_match": manifest_match,
        "blocked_component_overlap": blocked_overlap,
        "fresh_compilation_repetitions": repetitions,
        "deterministic": deterministic,
        "output_sha256": hashes[0] if deterministic else None,
        "output_character_length": len(outputs[0]) if deterministic else None,
        "payload_occurrence_counts": text_counts,
        "payload_byte_occurrence_counts": byte_counts,
        "payload_preserved": payload_preserved and byte_preserved,
        "null_character_counts": null_counts,
        "rendered_text_recorded": False,
        "operational_pass": passed,
    }


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_config(config_path)
    if config["status"] != "FROZEN_BEFORE_H4RM3L_STATIC_EXECUTION":
        raise ValueError("unexpected contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid contract boundary")

    source = cast(JsonObject, config["source"])
    rules = cast(JsonObject, config["rules"])
    gate = cast(JsonObject, config["decision_gate"])
    module, decorators_path, prompt_counter = load_h4rm3l(source_root)
    source_classes = class_names_from_source(decorators_path)
    allowed = set(string_list(config["allowed_components"], where="allowed_components"))
    blocked = set(
        string_list(
            config["payload_mutating_or_model_rewriting_components"],
            where="blocked_components",
        )
    )
    missing_allowed = sorted(allowed.difference(source_classes))
    missing_blocked = sorted(blocked.difference(source_classes))

    payload = str(config["synthetic_payload"])
    repetitions = int(config["fresh_compilation_repetitions"])
    syntax_version = int(config["syntax_version"])
    expected_occurrences = int(rules["payload_occurrence_count"])
    null_allowed = bool(rules["null_characters_allowed"])
    rows = [
        audit_expression(
            module,
            row,
            payload=payload,
            allowed=allowed,
            blocked=blocked,
            repetitions=repetitions,
            syntax_version=syntax_version,
            expected_occurrences=expected_occurrences,
            null_allowed=null_allowed,
        )
        for row in object_list(config["expressions"], where="expressions")
    ]

    prompt_attempted = prompt_counter["calls"] > 0
    operational_pass = all(row["operational_pass"] is True for row in rows) and not any(
        (missing_allowed, missing_blocked, prompt_attempted)
    )
    status = (
        "E0_H4RM3L_STATIC_ADAPTER_PASS_ADVANCE_TO_TYPED_UNIT_MANIFEST"
        if operational_pass
        else "E0_H4RM3L_STATIC_ADAPTER_FAIL"
    )
    next_operation = gate["on_pass"] if operational_pass else gate["on_fail"]

    result: JsonObject = {
        "schema_version": "e0-h4rm3l-static-adapter-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "decorators_git_blob_sha": source["decorators_git_blob_sha"],
            "decorators_sha256": sha256_file(decorators_path),
            "license": source["license"],
        },
        "config_sha256": sha256_file(config_path),
        "synthetic_payload_sha256": sha256_bytes(payload.encode()),
        "synthetic_payload_character_length": len(payload),
        "real_harmful_payload_used": False,
        "target_model_called": False,
        "model_prompting_attempted": prompt_attempted,
        "source_class_count": len(source_classes),
        "allowed_component_count": len(allowed),
        "blocked_component_count": len(blocked),
        "missing_allowed_components": missing_allowed,
        "missing_blocked_components": missing_blocked,
        "expression_count": len(rows),
        "expression_pass_count": sum(row["operational_pass"] is True for row in rows),
        "expressions": rows,
        "rendered_text_committed": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": next_operation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the pinned h4rm3l E0 static audit")
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
        "expression_count": result["expression_count"],
        "expression_pass_count": result["expression_pass_count"],
        "model_prompting_attempted": result["model_prompting_attempted"],
        "next_authorized_operation": result["next_authorized_operation"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
