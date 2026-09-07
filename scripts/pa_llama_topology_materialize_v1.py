"""Restricted, no-inference materialization of the frozen three-unit P/A design.

Only nine explicitly pinned public code/configuration files are read by load().
Payloads are supplied in memory; there is no dataset/private-input reader,
experiment launcher, scorer, response access, or artifact writer. Raw rendered
strings remain in the returned private in-memory object, never in safe_report().
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import itertools
import json
import re
import sys
import types
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COMPONENTS = (
    "AIMDecorator",
    "RefusalSuppressionDecorator",
    "AffirmativePrefixInjectionDecorator",
)
OPERATORS = ("SOURCE_AWARE_OMIT", "LAYOUT_PRESERVING_BLANK")
EXPRESSION_SHA = "d35b015a875284f7e3cb1d218b78c4eecd5e18e6d7449a6aa25af3293515f099"
PINS = {
    "decorators": (
        "artifacts/p3_signal_screen_v1/sources/h4rm3l-lf/h4rm3l/src/h4rm3l/decorators.py",
        50443,
        "875cdbd3d41b0d06af6f3e7fee6c91f8e227b45402325264cd36ccbc8471ac91",
    ),
    "static": (
        "scripts/run_e0_h4rm3l_static_audit.py",
        12964,
        "98099ab218897221a9679152a0d3e55733f110ffe333eb6ee954aae672d290ca",
    ),
    "typed": (
        "scripts/run_e0_h4rm3l_typed_units.py",
        15908,
        "edae4d4eac67228bfac47883889cf25202043d4817c919c07a30ea00cc722816",
    ),
    "d2": (
        "scripts/run_topology_d2_micro_pilot.py",
        94014,
        "c5646aa16928bd5f643a305f38d576f560a0b639650e61566f2c71f08394b513",
    ),
    "topology": (
        "src/jbspan/topology.py",
        29006,
        "a2b1cfaaead73d2efba61f7eb2e3141e327d69bb4f25889ab7813dcf27363672",
    ),
    "schemas": (
        "src/jbspan/schemas.py",
        4217,
        "2146818d719b4c7d7385d0dc14487322479bdd502e30d2be78cba03791641cc0",
    ),
    "p3": (
        "configs/natural_language_localization/local_signal_screen_p3_v1.json",
        15158,
        "cab5e7899c57c267e2b2f2ad5b202c05026103dac48de6cace835085120c5a1b",
    ),
    "p2": (
        "configs/natural_language_localization/local_q4_runtime_qualification_p2_v1.json",
        7789,
        "bc9e05aa6e1447917ca07c0fc8198dcdfb32e891d3879be28c9f1968a87cbe34",
    ),
    "d3": (
        "configs/natural_language_localization/d3_exact_topology_v1.json",
        9696,
        "d2824dee65ca65683154795ce52e4bd462a13bb052d19937514dd40a8bbf1ed7",
    ),
}
SELECTION = {
    "schemas": ("TextSpan",),
    "topology": (
        "sha256_text",
        "_occurrence_count",
        "AttackUnit",
        "ImmutablePayload",
        "TopologyInstance",
        "all_unit_subsets",
        "ValidationCheck",
        "InterventionMaterialization",
    ),
    "static": (
        "literal_only",
        "components_from_node",
        "components_from_expression",
        "compile_and_render",
    ),
    "typed": (
        "component_call_nodes",
        "component_call_sources",
        "layout_preserving_blank",
        "fragment_record",
        "shift_fragments",
        "build_manifest",
        "neutralize",
    ),
    "decorators": (
        "PromptDecorator",
        *COMPONENTS,
        "compile_decorator_v2",
        "make_prompt_decorator",
    ),
    "d2": ("validation_checks", "build_one_h4_materialization_family"),
}
MAX_PAYLOAD_BYTES = 100_000


def require(condition, code):
    if not condition:
        raise ValueError(code)


def text_sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha(value):
    # Exact P3 canonical_sha256 semantics, including ensure_ascii=True default.
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_CONFIGURATION_KEY")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def read_pinned(root, role):
    require(role in PINS, "UNDECLARED_SOURCE_ROLE")
    relative, size, expected = PINS[role]
    base = Path(root).resolve()
    path = (base / relative).resolve()
    require(
        path.is_relative_to(base) and path.relative_to(base).as_posix() == relative,
        "PINNED_SOURCE_PATH_ESCAPE_OR_ALIAS",
    )
    require(path.is_file() and path.stat().st_size == size, "PINNED_SOURCE_SIZE_CHANGED")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "PINNED_SOURCE_HASH_CHANGED")
    return raw


def selected_ast(raw, role):
    tree = ast.parse(raw.decode("utf-8"))
    names = SELECTION[role]
    by_name = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            require(node.name not in by_name, "DUPLICATE_SELECTED_DEFINITION")
            by_name[node.name] = node
    require(set(by_name) == set(names), "SELECTED_DEFINITION_MISSING")
    nodes = [by_name[name] for name in names]
    require(
        not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            for selected in nodes
            for node in ast.walk(selected)
        ),
        "SELECTED_DEFINITION_IMPORT_FORBIDDEN",
    )
    return nodes


class RestrictedRenderer:
    def __init__(self, sources):
        require(set(sources) == set(PINS), "SOURCE_CLOSURE_NOT_EXACT")
        # Also verify bytes when a synthetic test supplies an in-memory source map.
        for role, raw in sources.items():
            require(
                isinstance(raw, bytes)
                and len(raw) == PINS[role][1]
                and hashlib.sha256(raw).hexdigest() == PINS[role][2],
                "IN_MEMORY_SOURCE_PIN_CHANGED",
            )
        self.read_roles = tuple(PINS)
        self.traps = {"model_calls": 0, "random_draws": 0, "compiler_errors": 0}
        p3, p2, d3 = (strict_json(sources[role]) for role in ("p3", "p2", "d3"))
        families = [row for row in p3["attack_families"] if row["family"] == "h4rm3l"]
        require(len(families) == 1, "FROZEN_H4_FAMILY_NOT_UNIQUE")
        family = families[0]
        self.expression = family["representative_expression"]
        require(
            text_sha(self.expression) == EXPRESSION_SHA
            and family["representative_expression_sha256"] == EXPRESSION_SHA
            and tuple(family["expected_components"]) == COMPONENTS
            and type(family["syntax_version"]) is int
            and family["syntax_version"] == 2,
            "FROZEN_H4_PROGRAM_CHANGED",
        )
        harmless = {row["prompt_id"]: row for row in p2["harmless_prompts"]}
        tasks = d3["capability_controls"]["tasks"]
        require(
            [(row["id"], row["source_prompt_id"]) for row in tasks]
            == [("P2_ARITHMETIC", "arithmetic"), ("P2_COPY_TOKEN", "copy_token")],
            "FROZEN_CONTROL_TASKS_CHANGED",
        )
        self.tasks = tuple(
            {**task, "text": harmless[task["source_prompt_id"]]["text"]} for task in tasks
        )
        self.control_generation = dict(d3["capability_controls"]["generation"])
        self.namespace = self._build_namespace(sources)

    def _build_namespace(self, sources):
        def model_trap(*args, **kwargs):
            self.traps["model_calls"] += 1
            raise ValueError("MODEL_CALL_FORBIDDEN_IN_RENDERER")

        def compiler_error(*args, **kwargs):
            self.traps["compiler_errors"] += 1
            raise ValueError("RESTRICTED_COMPILER_FAILURE")

        class UnusedRandomState:
            # Selected classes only construct this attribute; none reads it.
            # The source AST is checked below. No numpy import or RNG state exists.
            def __init__(inner_self, seed=42):
                require(type(seed) is int and seed == 42, "UNEXPECTED_RENDERER_RNG_SEED")

            def __getattr__(inner_self, name):
                self.traps["random_draws"] += 1
                raise ValueError("RANDOM_DRAW_FORBIDDEN_IN_RENDERER")

        safe_names = (
            "__build_class__",
            "object",
            "super",
            "property",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "tuple",
            "dict",
            "set",
            "len",
            "range",
            "enumerate",
            "zip",
            "sorted",
            "min",
            "max",
            "sum",
            "all",
            "any",
            "isinstance",
            "callable",
            "getattr",
            "type",
            "ValueError",
            "TypeError",
            "RuntimeError",
            "NotImplementedError",
            "Exception",
        )
        namespace = {
            "__builtins__": {name: getattr(builtins, name) for name in safe_names},
            "ast": ast,
            "hashlib": hashlib,
            "itertools": itertools,
            "argparse": argparse,
            "types": types,
            "Any": Any,
            "JsonObject": dict,
            "UnitSubset": tuple,
            "dataclass": dataclass,
            "field": field,
            "RandomState": UnusedRandomState,
            "logging": types.SimpleNamespace(error=compiler_error),
            "get_model_prompting_interface": model_trap,
            "initialize_model_prompting_interface": model_trap,
            "compile_decorator_v1": compiler_error,
            "NEUTRALIZERS": OPERATORS,
            "text_sha256": text_sha,
        }

        def restricted_eval(expression):
            require(isinstance(expression, str), "EXPRESSION_NOT_TEXT")
            nodes = namespace["component_call_nodes"](ast.parse(expression, mode="eval").body)
            require(
                all(
                    isinstance(node.func, ast.Name)
                    and node.func.id in COMPONENTS
                    and not node.args
                    and not node.keywords
                    for node in nodes
                ),
                "EXPRESSION_OUTSIDE_FROZEN_ZERO_ARGUMENT_COMPONENTS",
            )
            require(
                len(nodes) <= 3 and len({node.func.id for node in nodes}) == len(nodes),
                "EXPRESSION_REPEATED_OR_EXCESS_COMPONENT",
            )
            return eval(
                compile(expression, "<restricted-h4-expression>", "eval"),
                {"__builtins__": {}},
                {name: namespace[name] for name in COMPONENTS},
            )

        namespace["eval"] = restricted_eval
        nodes_by_role = {role: selected_ast(sources[role], role) for role in SELECTION}
        require(
            not any(
                isinstance(node, ast.Attribute)
                and node.attr == "_random_state"
                and isinstance(node.ctx, ast.Load)
                for selected in nodes_by_role["decorators"]
                for node in ast.walk(selected)
            ),
            "SELECTED_RENDERER_READS_RANDOM_STATE",
        )
        module_name = f"_pa_topology_restricted_{id(namespace):x}"
        module = types.ModuleType(module_name)
        module.__dict__.update(namespace)
        namespace = module.__dict__
        require(module_name not in sys.modules, "RESTRICTED_MODULE_NAME_COLLISION")
        sys.modules[module_name] = module
        try:
            for role, nodes in nodes_by_role.items():
                selected_module = ast.Module(body=nodes, type_ignores=[])
                exec(
                    compile(
                        ast.fix_missing_locations(selected_module),
                        f"<pinned-{role}-definitions>",
                        "exec",
                    ),
                    namespace,
                )
            namespace["h4_typed"] = types.SimpleNamespace(
                **{name: namespace[name] for name in SELECTION["typed"]}
            )
        finally:
            del sys.modules[module_name]
        self.selected_definition_hashes = {
            role: text_sha(
                ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)
            )
            for role, nodes in nodes_by_role.items()
        }
        return namespace

    def _parts(self):
        static = types.SimpleNamespace(
            **{name: self.namespace[name] for name in SELECTION["static"]}
        )
        h4 = types.SimpleNamespace(make_prompt_decorator=self.namespace["make_prompt_decorator"])
        return static, h4

    def render_family(self, payload):
        """Pure in-memory rendering; callers must bind real inputs before use."""
        require(
            isinstance(payload, str) and payload and len(payload.encode()) <= MAX_PAYLOAD_BYTES,
            "PAYLOAD_EMPTY_NONSTRING_OR_OVERSIZED",
        )
        require("\x00" not in payload, "PAYLOAD_NULL_CHARACTER")
        require(re.search(r"<\|[^<>|\r\n]+\|>", payload) is None, "PAYLOAD_RESERVED_CONTROL_MARKER")
        static, h4 = self._parts()
        full, units, fragments, partition = self.namespace["build_manifest"](
            static,
            h4,
            expression=self.expression,
            expected_components=list(COMPONENTS),
            allowed=set(COMPONENTS),
            payload=payload,
            syntax_version=2,
        )
        require(partition, "SOURCE_FRAGMENT_PARTITION_FAILED")
        instance, materials = self.namespace["build_one_h4_materialization_family"](
            payload=payload,
            instance_id=text_sha(payload),
            expression=self.expression,
            components=COMPONENTS,
            syntax_version=2,
            static=static,
            h4_module=h4,
        )
        require(
            instance.prompt == full and instance.unit_ids == COMPONENTS,
            "D2_TYPED_MANIFEST_RECONSTRUCTION_MISMATCH",
        )
        rows = []
        raw_prompts = {}
        for mask in range(8):
            selected = tuple(name for bit, name in enumerate(COMPONENTS) if mask & (1 << bit))
            for operator in OPERATORS:
                material = materials[(selected, operator)]
                prompt = material.edited_prompt
                require(material.input_valid, "SOURCE_MATERIAL_VALIDATION_FAILED")
                require(
                    self.namespace["_occurrence_count"](prompt, payload) == 1
                    and prompt.encode().count(payload.encode()) == 1,
                    "IMMUTABLE_PAYLOAD_NOT_BYTE_UNIQUE",
                )
                require(
                    re.search(r"<\|[^<>|\r\n]+\|>", prompt) is None,
                    "RENDERED_CONTROL_MARKER_INJECTION",
                )
                raw_prompts[(mask, operator)] = prompt
                rows.append(
                    {
                        **material.to_safe_dict(),
                        "mask_id": mask,
                        "prompt_character_length": len(prompt),
                        "prompt_utf8_bytes": len(prompt.encode()),
                        "payload_start_character": prompt.index(payload),
                        "payload_utf8_bytes": len(payload.encode()),
                        "payload_occurrences": 1,
                        "reserved_control_marker_count": 0,
                    }
                )
        require(
            len(rows) == 16 and all(raw_prompts[(0, op)] == full for op in OPERATORS),
            "EMPTY_MASK_OR_DENOMINATOR_CHANGED",
        )
        require(raw_prompts[(7, "SOURCE_AWARE_OMIT")] == payload, "FULL_OMISSION_NOT_PAYLOAD")
        require(not any(self.traps.values()), "RENDERER_TRAP_TRIGGERED")
        return {
            "payload": payload,
            "full_prompt": full,
            "raw_prompts": raw_prompts,
            "units": units,
            "fragments": fragments,
            "rows": rows,
            "identity": {
                "payload_sha256": text_sha(payload),
                "prompt_sha256": text_sha(full),
                "unit_manifest_sha256": canonical_sha(units),
                "fragment_manifest_sha256": canonical_sha(fragments),
            },
        }

    def prepare_bound_payload(self, payload, full_prompt, expected_identity):
        """Future production entry point: bind all four source hashes before returning."""
        require(
            isinstance(expected_identity, dict)
            and set(expected_identity)
            == {
                "payload_sha256",
                "prompt_sha256",
                "unit_manifest_sha256",
                "fragment_manifest_sha256",
            }
            and all(
                isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value)
                for value in expected_identity.values()
            ),
            "EXPECTED_SOURCE_IDENTITIES_REQUIRED",
        )
        family = self.render_family(payload)
        require(
            family["identity"] == expected_identity and family["full_prompt"] == full_prompt,
            "SAVED_FULL_PROMPT_OR_MANIFEST_IDENTITY_MISMATCH",
        )
        return family

    def prepare_controls(self, family):
        """Replace only the P slot, then independently compare historical task re-render."""
        payload = family["payload"]
        # Reject a mutated caller-owned object rather than deriving controls from it.
        fresh = self.prepare_bound_payload(payload, family["full_prompt"], family["identity"])
        require(fresh["raw_prompts"] == family["raw_prompts"], "SCIENTIFIC_MATERIAL_CHANGED")
        output = []
        for task in self.tasks:
            historical = self.render_family(task["text"])
            for mask in range(8):
                for operator in OPERATORS:
                    scientific = fresh["raw_prompts"][(mask, operator)]
                    start = scientific.index(payload)
                    substituted = (
                        scientific[:start] + task["text"] + scientific[start + len(payload) :]
                    )
                    rerendered = historical["raw_prompts"][(mask, operator)]
                    require(substituted == rerendered, "CONTROL_STRUCTURE_MATCH_FAILED")
                    output.append(
                        {
                            "task_id": task["id"],
                            "source_prompt_id": task["source_prompt_id"],
                            "mask_id": mask,
                            "neutralizer_id": operator,
                            "scientific_payload_sha256": fresh["identity"]["payload_sha256"],
                            "task_sha256": text_sha(task["text"]),
                            "prompt_sha256": text_sha(substituted),
                            "source_rerender_prompt_sha256": text_sha(rerendered),
                            "control_unit_manifest_sha256": historical["identity"][
                                "unit_manifest_sha256"
                            ],
                            "control_fragment_manifest_sha256": historical["identity"][
                                "fragment_manifest_sha256"
                            ],
                            "source_rerender_matches_slot_replacement": True,
                            "generation": dict(self.control_generation),
                            "prompt_character_length": len(substituted),
                            "prompt_utf8_bytes": len(substituted.encode()),
                            "raw_prompt": substituted,
                        }
                    )
        require(len(output) == 32, "CONTROL_MATERIAL_DENOMINATOR")
        return output

    def safe_report(self, family, controls=()):
        fresh = self.prepare_bound_payload(
            family["payload"], family["full_prompt"], family["identity"]
        )
        if controls:
            expected_controls = self.prepare_controls(fresh)
            require(list(controls) == expected_controls, "SAFE_CONTROL_PROJECTION_INPUT_CHANGED")
        else:
            expected_controls = []
        safe_controls = [
            {key: value for key, value in row.items() if key != "raw_prompt"}
            for row in expected_controls
        ]
        return {
            "schema_version": "jbspan-pa-llama-topology-materialization-v1",
            "execution_authorized": False,
            "model_calls": 0,
            "private_files_read": 0,
            "cohort_or_response_reads": 0,
            "frozen_unit_ids": list(COMPONENTS),
            "identity": dict(fresh["identity"]),
            "units": fresh["units"],
            "fragments": fresh["fragments"],
            "materials": fresh["rows"],
            "control_materials": safe_controls,
            "source_read_roles": list(self.read_roles),
            "selected_definition_sha256": dict(self.selected_definition_hashes),
            "traps": dict(self.traps),
            "control_equivalence": control_equivalence(safe_controls),
            "equivalence_does_not_authorize_deduplication": True,
            "no_response_scoring_or_recovery_status": True,
        }

    def prepare_bound_bundle(self, payload, full_prompt, expected_identity, payload_position):
        """Uniform all-mask rows for a future separate plan; no IDs or authority issued."""
        require(
            type(payload_position) is int and 0 <= payload_position < 45,
            "EXPOSED_FRAME_PAYLOAD_POSITION_INVALID",
        )
        family = self.prepare_bound_payload(payload, full_prompt, expected_identity)
        controls = self.prepare_controls(family)
        safe_rows, private_rows = [], []
        source = family["identity"]
        for row in family["rows"]:
            key = {
                "payload_position": payload_position,
                "mask": row["mask_id"],
                "operator": row["neutralizer_id"],
                "kind": "science",
                "task_id": None,
            }
            safe_rows.append(
                {
                    **key,
                    "payload_sha256": source["payload_sha256"],
                    "prompt_sha256": row["prompt_sha256"],
                    "prompt_utf8_bytes": row["prompt_utf8_bytes"],
                    "prompt_character_length": row["prompt_character_length"],
                    "payload_start_character": row["payload_start_character"],
                    "unit_manifest_sha256": source["unit_manifest_sha256"],
                    "fragment_manifest_sha256": source["fragment_manifest_sha256"],
                    "input_valid": row["input_valid"],
                    "source_anchor_verified": True,
                    "validation_checks": row["validation_checks"],
                    "control_task_sha256": None,
                }
            )
            private_rows.append(
                {**key, "prompt": family["raw_prompts"][(key["mask"], key["operator"])]}
            )
        for row in controls:
            key = {
                "payload_position": payload_position,
                "mask": row["mask_id"],
                "operator": row["neutralizer_id"],
                "kind": "control",
                "task_id": row["task_id"],
            }
            safe_rows.append(
                {
                    **key,
                    "payload_sha256": source["payload_sha256"],
                    "prompt_sha256": row["prompt_sha256"],
                    "prompt_utf8_bytes": row["prompt_utf8_bytes"],
                    "prompt_character_length": row["prompt_character_length"],
                    "unit_manifest_sha256": source["unit_manifest_sha256"],
                    "fragment_manifest_sha256": source["fragment_manifest_sha256"],
                    "control_unit_manifest_sha256": row["control_unit_manifest_sha256"],
                    "control_fragment_manifest_sha256": row["control_fragment_manifest_sha256"],
                    "control_task_sha256": row["task_sha256"],
                    "input_valid": True,
                    "source_anchor_verified": True,
                    "source_rerender_matches_slot_replacement": True,
                }
            )
            private_rows.append({**key, "prompt": row["raw_prompt"]})
        require(len(safe_rows) == len(private_rows) == 48, "BOUND_BUNDLE_DENOMINATOR")
        return {
            "source_identity": dict(source),
            "safe_rows": safe_rows,
            "private_rows": private_rows,
            "execution_authorized": False,
            "model_calls": 0,
            "control_equivalence": control_equivalence(controls),
        }


def control_equivalence(rows):
    """Prompt AND exact generation-regime classes; identities do not reuse outcomes."""
    groups = defaultdict(list)
    for row in rows:
        key = canonical_sha(
            {"prompt_sha256": row["prompt_sha256"], "generation": row["generation"]}
        )
        groups[key].append(
            {
                key: row[key]
                for key in (
                    "scientific_payload_sha256",
                    "task_id",
                    "mask_id",
                    "neutralizer_id",
                )
            }
        )
    return [
        {"prompt_and_regime_identity_sha256": key, "member_count": len(members), "members": members}
        for key, members in sorted(groups.items())
    ]


def load(root):
    return RestrictedRenderer({role: read_pinned(root, role) for role in PINS})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        renderer = load(args.root)
        family = renderer.render_family("Synthetic harmless payload: describe a blue ceramic cup.")
        controls = renderer.prepare_controls(family)
        print(json.dumps(renderer.safe_report(family, controls), sort_keys=True, indent=2))
        return 0
    except Exception as error:
        code = (
            str(error)
            if isinstance(error, ValueError) and re.fullmatch("[A-Z0-9_]+", str(error))
            else type(error).__name__
        )
        print(
            json.dumps({"status": "MATERIALIZATION_STOPPED", "error_code": code, "model_calls": 0})
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
