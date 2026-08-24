from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import itertools
import json
import types
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(JsonObject, value)


def load_static_audit_module() -> types.ModuleType:
    path = Path(__file__).with_name("run_e0_h4rm3l_static_audit.py")
    spec = importlib.util.spec_from_file_location("e0_h4rm3l_static_support", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load static-audit support module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def component_call_nodes(node: ast.AST) -> list[ast.Call]:
    if not isinstance(node, ast.Call):
        raise ValueError("decorator expression must be a call")
    if isinstance(node.func, ast.Name):
        return [node]
    if isinstance(node.func, ast.Attribute) and node.func.attr == "then":
        if node.keywords or len(node.args) != 1:
            raise ValueError("then() must have exactly one positional component")
        return component_call_nodes(node.func.value) + component_call_nodes(node.args[0])
    raise ValueError("only decorator calls and .then() composition are supported")


def component_call_sources(expression: str) -> list[str]:
    parsed = ast.parse(expression, mode="eval")
    return [ast.unparse(node) for node in component_call_nodes(parsed.body)]


def layout_preserving_blank(value: str) -> str:
    return "".join(character if character.isspace() else " " for character in value)


def all_nonempty_subsets(values: list[str]) -> list[tuple[str, ...]]:
    return [
        subset
        for size in range(1, len(values) + 1)
        for subset in itertools.combinations(values, size)
    ]


def fragment_record(
    *,
    fragment_id: str,
    owner: str,
    component: str,
    kind: str,
    start: int,
    end: int,
    text: str,
) -> JsonObject:
    return {
        "id": fragment_id,
        "owner": owner,
        "component": component,
        "kind": kind,
        "start_character": start,
        "end_character": end,
        "character_length": end - start,
        "utf8_byte_length": len(text.encode("utf-8")),
        "sha256": sha256_text(text),
        "raw_text_recorded": False,
    }


def shift_fragments(fragments: list[JsonObject], amount: int) -> None:
    for fragment in fragments:
        fragment["start_character"] = int(fragment["start_character"]) + amount
        fragment["end_character"] = int(fragment["end_character"]) + amount


def build_manifest(
    static: types.ModuleType,
    h4rm3l_module: types.ModuleType,
    *,
    expression: str,
    expected_components: list[str],
    allowed: set[str],
    payload: str,
    syntax_version: int,
) -> tuple[str, list[JsonObject], list[JsonObject], bool]:
    observed_components = static.components_from_expression(expression, allowed=allowed)
    if observed_components != expected_components:
        raise ValueError("AST component manifest differs from frozen manifest")
    calls = component_call_sources(expression)
    if len(calls) != len(expected_components):
        raise ValueError("component-call count differs from frozen manifest")

    payload_fragment: JsonObject = fragment_record(
        fragment_id="payload",
        owner="__payload__",
        component="IMMUTABLE_PAYLOAD",
        kind="payload",
        start=0,
        end=len(payload),
        text=payload,
    )
    fragments = [payload_fragment]
    units: list[JsonObject] = []
    current = payload

    for index, (component, call_source) in enumerate(zip(expected_components, calls, strict=True)):
        unit_id = f"u{index + 1:02d}_{component}"
        output = static.compile_and_render(
            h4rm3l_module,
            expression=call_source,
            payload=current,
            syntax_version=syntax_version,
        )
        occurrence_count = output.count(current)
        if occurrence_count != 1:
            raise ValueError(
                f"{unit_id} embeds its complete input {occurrence_count} times instead of once"
            )
        insertion_start = output.index(current)
        prefix = output[:insertion_start]
        suffix = output[insertion_start + len(current) :]
        shift_fragments(fragments, len(prefix))
        unit_fragment_ids: list[str] = []

        if prefix:
            fragment_id = f"{unit_id}:prefix"
            fragments.append(
                fragment_record(
                    fragment_id=fragment_id,
                    owner=unit_id,
                    component=component,
                    kind="prefix",
                    start=0,
                    end=len(prefix),
                    text=prefix,
                )
            )
            unit_fragment_ids.append(fragment_id)
        if suffix:
            fragment_id = f"{unit_id}:suffix"
            suffix_start = len(prefix) + len(current)
            fragments.append(
                fragment_record(
                    fragment_id=fragment_id,
                    owner=unit_id,
                    component=component,
                    kind="suffix",
                    start=suffix_start,
                    end=len(output),
                    text=suffix,
                )
            )
            unit_fragment_ids.append(fragment_id)
        if not unit_fragment_ids:
            raise ValueError(f"{unit_id} added no attributable text fragment")

        units.append(
            {
                "id": unit_id,
                "component": component,
                "component_expression_sha256": sha256_text(call_source),
                "fragment_ids": unit_fragment_ids,
                "fragment_count": len(unit_fragment_ids),
                "input_sha256": sha256_text(current),
                "output_sha256": sha256_text(output),
                "input_occurrence_count_in_output": occurrence_count,
            }
        )
        current = output

    full_output = static.compile_and_render(
        h4rm3l_module,
        expression=expression,
        payload=payload,
        syntax_version=syntax_version,
    )
    full_chain_matches = full_output == current
    ordered = sorted(fragments, key=lambda row: int(row["start_character"]))
    cursor = 0
    reconstructed_parts: list[str] = []
    for fragment in ordered:
        start = int(fragment["start_character"])
        end = int(fragment["end_character"])
        if start != cursor or end < start:
            raise ValueError("fragments do not form a contiguous non-overlapping partition")
        reconstructed_parts.append(current[start:end])
        cursor = end
    partition_pass = cursor == len(current) and "".join(reconstructed_parts) == current
    return current, units, ordered, full_chain_matches and partition_pass


def neutralize(
    full_text: str,
    fragments: list[JsonObject],
    selected_units: set[str],
    neutralizer: str,
) -> str:
    pieces: list[str] = []
    for fragment in fragments:
        start = int(fragment["start_character"])
        end = int(fragment["end_character"])
        text = full_text[start:end]
        owner = str(fragment["owner"])
        if owner not in selected_units:
            pieces.append(text)
        elif neutralizer == "delete_component_fragments":
            pieces.append("")
        elif neutralizer == "layout_preserving_blank":
            pieces.append(layout_preserving_blank(text))
        else:
            raise ValueError(f"unknown neutralizer: {neutralizer}")
    return "".join(pieces)


def audit_program(
    static: types.ModuleType,
    h4rm3l_module: types.ModuleType,
    row: JsonObject,
    *,
    allowed: set[str],
    payload: str,
    syntax_version: int,
    neutralizers: list[str],
) -> JsonObject:
    program_id = str(row["id"])
    expression = str(row["expression"])
    expected_components = cast(list[str], row["expected_components"])
    full_text, units, fragments, manifest_pass = build_manifest(
        static,
        h4rm3l_module,
        expression=expression,
        expected_components=expected_components,
        allowed=allowed,
        payload=payload,
        syntax_version=syntax_version,
    )
    unit_ids = [str(unit["id"]) for unit in units]
    subsets = all_nonempty_subsets(unit_ids)
    variants: list[JsonObject] = []

    for subset in subsets:
        for neutralizer in neutralizers:
            output = neutralize(full_text, fragments, set(subset), neutralizer)
            payload_count = output.count(payload)
            payload_byte_count = output.encode().count(payload.encode())
            length_rule = (
                len(output) <= len(full_text)
                if neutralizer == "delete_component_fragments"
                else len(output) == len(full_text)
            )
            passed = all(
                (
                    payload_count == 1,
                    payload_byte_count == 1,
                    "\x00" not in output,
                    length_rule,
                )
            )
            variants.append(
                {
                    "subset": list(subset),
                    "subset_size": len(subset),
                    "neutralizer": neutralizer,
                    "output_sha256": sha256_text(output),
                    "output_character_length": len(output),
                    "payload_occurrence_count": payload_count,
                    "payload_byte_occurrence_count": payload_byte_count,
                    "length_rule_pass": length_rule,
                    "raw_text_recorded": False,
                    "operational_pass": passed,
                }
            )

    program_pass = manifest_pass and all(
        variant["operational_pass"] is True for variant in variants
    )
    return {
        "id": program_id,
        "expression_sha256": sha256_text(expression),
        "full_output_sha256": sha256_text(full_text),
        "full_output_character_length": len(full_text),
        "components": expected_components,
        "component_count": len(units),
        "units": units,
        "fragments": fragments,
        "fragment_count": len(fragments),
        "manifest_partition_pass": manifest_pass,
        "subset_count": len(subsets),
        "neutralized_variant_count": len(variants),
        "neutralized_variant_pass_count": sum(
            variant["operational_pass"] is True for variant in variants
        ),
        "variants": variants,
        "raw_text_recorded": False,
        "operational_pass": program_pass,
    }


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_json_object(config_path)
    predecessor = cast(JsonObject, config["predecessor"])
    prior = load_json_object(Path(str(predecessor["result_path"])))
    if prior["status"] != predecessor["required_status"]:
        raise ValueError("h4rm3l static-audit predecessor status mismatch")
    if prior["operational_pass"] is not predecessor["required_operational_pass"]:
        raise ValueError("h4rm3l static-audit predecessor pass mismatch")
    if config["status"] != "FROZEN_BEFORE_H4RM3L_TYPED_UNIT_EXECUTION":
        raise ValueError("unexpected typed-unit contract status")

    static = load_static_audit_module()
    h4rm3l_module, decorators_path, prompt_counter = static.load_h4rm3l(source_root)
    allowed = set(cast(list[str], config["allowed_components"]))
    payload = str(config["synthetic_payload"])
    syntax_version = int(config["syntax_version"])
    neutralizers = [
        str(cast(JsonObject, row)["id"])
        for row in cast(list[object], config["neutralizers"])
    ]
    results = [
        audit_program(
            static,
            h4rm3l_module,
            cast(JsonObject, row),
            allowed=allowed,
            payload=payload,
            syntax_version=syntax_version,
            neutralizers=neutralizers,
        )
        for row in cast(list[object], config["programs"])
    ]

    prompting_attempted = prompt_counter["calls"] > 0
    operational_pass = all(row["operational_pass"] is True for row in results) and not (
        prompting_attempted
    )
    gate = cast(JsonObject, config["decision_gate"])
    status = (
        "E0_H4RM3L_TYPED_UNITS_PASS_ADVANCE_TO_REAL_TEMPLATE_PAYLOAD_INVARIANCE_AUDIT"
        if operational_pass
        else "E0_H4RM3L_TYPED_UNITS_FAIL"
    )
    result: JsonObject = {
        "schema_version": "e0-h4rm3l-typed-units-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "source_revision": cast(JsonObject, config["source"])["revision"],
        "decorators_sha256": static.sha256_file(decorators_path),
        "config_sha256": static.sha256_file(config_path),
        "predecessor_result_sha256": static.sha256_file(Path(str(predecessor["result_path"]))),
        "synthetic_payload_sha256": sha256_text(payload),
        "program_count": len(results),
        "program_pass_count": sum(row["operational_pass"] is True for row in results),
        "total_component_count": sum(int(row["component_count"]) for row in results),
        "total_subset_count": sum(int(row["subset_count"]) for row in results),
        "total_neutralized_variant_count": sum(
            int(row["neutralized_variant_count"]) for row in results
        ),
        "total_neutralized_variant_pass_count": sum(
            int(row["neutralized_variant_pass_count"]) for row in results
        ),
        "model_prompting_attempted": prompting_attempted,
        "target_model_called": False,
        "real_harmful_payload_used": False,
        "raw_fragment_or_prompt_text_committed": False,
        "programs": results,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["on_pass"] if operational_pass else gate["on_fail"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run h4rm3l typed-unit E0 audit")
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
        "programs": result["program_count"],
        "subsets": result["total_subset_count"],
        "variants": result["total_neutralized_variant_count"],
        "variant_passes": result["total_neutralized_variant_pass_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
