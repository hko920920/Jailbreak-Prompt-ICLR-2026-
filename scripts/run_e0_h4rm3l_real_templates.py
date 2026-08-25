from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import types
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(JsonObject, value)


def load_typed_support() -> types.ModuleType:
    path = Path(__file__).with_name("run_e0_h4rm3l_typed_units.py")
    spec = importlib.util.spec_from_file_location("e0_h4rm3l_typed_support", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load h4rm3l typed-unit support")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def object_array(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{where} must be an object array")
    return cast(list[JsonObject], value)


def string_array(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_object(config_path)
    if config["status"] != "FROZEN_BEFORE_H4RM3L_REAL_TEMPLATE_EXECUTION":
        raise ValueError("unexpected real-template contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid real-template contract boundary")

    predecessor = cast(JsonObject, config["predecessor"])
    prior_path = Path(str(predecessor["result_path"]))
    prior = load_object(prior_path)
    if prior["status"] != predecessor["required_status"]:
        raise ValueError("typed-unit predecessor status mismatch")
    if prior["operational_pass"] is not predecessor["required_operational_pass"]:
        raise ValueError("typed-unit predecessor pass mismatch")

    typed = load_typed_support()
    static = typed.load_static_audit_module()
    h4rm3l_module, decorators_path, prompt_counter = static.load_h4rm3l(source_root)
    allowed = set(string_array(config["allowed_components"], where="allowed_components"))
    payload = str(config["synthetic_payload"])
    syntax_version = int(config["syntax_version"])
    neutralizers = string_array(config["neutralizers"], where="neutralizers")

    programs = [
        typed.audit_program(
            static,
            h4rm3l_module,
            row,
            allowed=allowed,
            payload=payload,
            syntax_version=syntax_version,
            neutralizers=neutralizers,
        )
        for row in object_array(config["programs"], where="programs")
    ]

    budget = cast(JsonObject, config["subset_budget"])
    program_count = len(programs)
    component_count = sum(int(row["component_count"]) for row in programs)
    subset_count = sum(int(row["subset_count"]) for row in programs)
    variant_count = sum(int(row["neutralized_variant_count"]) for row in programs)
    variant_pass_count = sum(
        int(row["neutralized_variant_pass_count"]) for row in programs
    )
    budget_match = all(
        (
            program_count == int(budget["expected_program_count"]),
            component_count == int(budget["expected_component_count"]),
            subset_count == int(budget["expected_subset_count"]),
            variant_count == int(budget["expected_neutralized_variant_count"]),
        )
    )
    prompting_attempted = prompt_counter["calls"] > 0
    operational_pass = all(row["operational_pass"] is True for row in programs) and all(
        (
            budget_match,
            variant_pass_count == variant_count,
            not prompting_attempted,
        )
    )

    gate = cast(JsonObject, config["decision_gate"])
    status = (
        "E0_H4RM3L_REAL_TEMPLATES_PASS_FREEZE_REGIME_S_H4RM3L_ADAPTER"
        if operational_pass
        else "E0_H4RM3L_REAL_TEMPLATES_FAIL"
    )
    result: JsonObject = {
        "schema_version": "e0-h4rm3l-real-templates-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "source_revision": cast(JsonObject, config["source"])["revision"],
        "decorators_sha256": sha256_file(decorators_path),
        "config_sha256": sha256_file(config_path),
        "predecessor_result_sha256": sha256_file(prior_path),
        "synthetic_payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "program_count": program_count,
        "program_pass_count": sum(row["operational_pass"] is True for row in programs),
        "total_component_count": component_count,
        "total_subset_count": subset_count,
        "total_neutralized_variant_count": variant_count,
        "total_neutralized_variant_pass_count": variant_pass_count,
        "budget_match": budget_match,
        "model_prompting_attempted": prompting_attempted,
        "target_model_called": False,
        "attack_success_scored": False,
        "real_harmful_payload_used": False,
        "raw_template_or_rendered_text_committed": False,
        "programs": programs,
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
    parser = argparse.ArgumentParser(description="Run h4rm3l real-template E0 audit")
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
        "components": result["total_component_count"],
        "subsets": result["total_subset_count"],
        "variants": result["total_neutralized_variant_count"],
        "variant_passes": result["total_neutralized_variant_pass_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
