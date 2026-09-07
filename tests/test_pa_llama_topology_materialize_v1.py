"""Synthetic strings and pinned public code only; no data/model/network access."""

import builtins
import copy
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tested_pa_topology_materializer", ROOT / "scripts/pa_llama_topology_materialize_v1.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
PAYLOAD = "Synthetic harmless request: describe the glazed turquoise teacup ZX_917."


@pytest.fixture(scope="module")
def sources():
    return {role: m.read_pinned(ROOT, role) for role in m.PINS}


@pytest.fixture
def renderer(sources):
    return m.RestrictedRenderer(sources)


def test_load_reads_exactly_nine_pinned_public_sources(monkeypatch):
    original = m.read_pinned
    roles = []

    def tracked(root, role):
        roles.append(role)
        return original(root, role)

    monkeypatch.setattr(m, "read_pinned", tracked)
    loaded = m.load(ROOT)
    assert roles == list(m.PINS)
    assert loaded.read_roles == tuple(m.PINS)
    assert all(
        not any(part.startswith("private") for part in Path(pin[0]).parts)
        for pin in m.PINS.values()
    )
    assert all(not pin[0].startswith("data/") for pin in m.PINS.values())


def test_selected_definitions_never_import_full_runners_or_resources(sources, monkeypatch):
    modules_before = set(sys.modules)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Unexpected source/data file or network access during in-memory rendering"
        )

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    renderer = m.RestrictedRenderer(sources)
    family = renderer.render_family(PAYLOAD)
    controls = renderer.prepare_controls(family)
    report = renderer.safe_report(family, controls)
    assert report["model_calls"] == report["private_files_read"] == 0
    assert renderer.traps == {"model_calls": 0, "random_draws": 0, "compiler_errors": 0}
    assert set(sys.modules) == modules_before
    assert "open" not in renderer.namespace["__builtins__"]
    assert "__import__" not in renderer.namespace["__builtins__"]


@pytest.mark.parametrize("role", list(m.PINS))
def test_changed_source_bytes_are_rejected_before_ast_execution(sources, role):
    changed = dict(sources)
    changed[role] = bytes([sources[role][0] ^ 1]) + sources[role][1:]
    with pytest.raises(ValueError, match="IN_MEMORY_SOURCE_PIN"):
        m.RestrictedRenderer(changed)


def test_extra_dependency_source_is_forbidden(sources):
    with pytest.raises(ValueError, match="CLOSURE_NOT_EXACT"):
        m.RestrictedRenderer({**sources, "another_resource": b"{}"})


def test_all_masks_two_operators_empty_and_full_identities(renderer):
    family = renderer.render_family(PAYLOAD)
    assert len(family["rows"]) == len(family["raw_prompts"]) == 16
    assert {(row["mask_id"], row["neutralizer_id"]) for row in family["rows"]} == {
        (mask, operator) for mask in range(8) for operator in m.OPERATORS
    }
    for operator in m.OPERATORS:
        assert family["raw_prompts"][(0, operator)] == family["full_prompt"]
    assert family["raw_prompts"][(7, "SOURCE_AWARE_OMIT")] == PAYLOAD
    assert family["raw_prompts"][(7, "LAYOUT_PRESERVING_BLANK")] != PAYLOAD


def test_frozen_source_owns_disjoint_prefix_and_suffix_fragments(renderer):
    family = renderer.render_family(PAYLOAD)
    units, fragments = family["units"], family["fragments"]
    assert [unit["component"] for unit in units] == list(m.COMPONENTS)
    assert units[0]["fragment_count"] == 2
    first_parts = [row for row in fragments if row["owner"] == units[0]["id"]]
    assert first_parts[0]["end_character"] < first_parts[1]["start_character"]
    assert len([row for row in fragments if row["owner"] == "__payload__"]) == 1
    cursor = 0
    for row in fragments:
        assert row["start_character"] == cursor
        cursor = row["end_character"]
        assert row["sha256"] == m.text_sha(family["full_prompt"][row["start_character"] : cursor])
    assert cursor == len(family["full_prompt"])


@pytest.mark.parametrize(
    "payload",
    [
        PAYLOAD,
        "고유 합성 요청: 찻잔의 색을 설명하세요 🫖 ZX_234.",
        "Unique synthetic\r\npayload\tZX_982\rkeeps whitespace.",
    ],
)
def test_payload_utf8_bytes_and_whitespace_are_preserved(renderer, payload):
    family = renderer.render_family(payload)
    for row in family["rows"]:
        prompt = family["raw_prompts"][(row["mask_id"], row["neutralizer_id"])]
        assert prompt.encode().count(payload.encode()) == 1
        assert payload in prompt
        assert row["payload_sha256"] == m.text_sha(payload)
        assert row["prompt_sha256"] == m.text_sha(prompt)
        if row["neutralizer_id"] == "LAYOUT_PRESERVING_BLANK":
            assert len(prompt) == len(family["full_prompt"])


def test_layout_blanking_matches_independent_character_mask(renderer):
    family = renderer.render_family(PAYLOAD)
    for mask in range(8):
        expected = list(family["full_prompt"])
        selected = {family["units"][bit]["id"] for bit in range(3) if mask & (1 << bit)}
        for fragment in family["fragments"]:
            if fragment["owner"] in selected:
                for offset in range(fragment["start_character"], fragment["end_character"]):
                    if not expected[offset].isspace():
                        expected[offset] = " "
        assert family["raw_prompts"][(mask, "LAYOUT_PRESERVING_BLANK")] == "".join(expected)
    assert renderer.namespace["layout_preserving_blank"]("é\t漢\n") == " \t \n"


def test_source_omit_reexecutes_only_retained_components(renderer):
    family = renderer.render_family(PAYLOAD)
    for mask in range(8):
        expected = PAYLOAD
        for bit, component in enumerate(m.COMPONENTS):
            if not mask & (1 << bit):
                expected = renderer.namespace[component]().decorate(expected)
        assert family["raw_prompts"][(mask, "SOURCE_AWARE_OMIT")] == expected


def test_this_fixed_affix_recipe_equals_fragment_deletion_but_semantics_remain_rerender(renderer):
    family = renderer.render_family(PAYLOAD)
    for mask in range(8):
        selected = {family["units"][bit]["id"] for bit in range(3) if mask & (1 << bit)}
        deleted = renderer.namespace["neutralize"](
            family["full_prompt"], family["fragments"], selected, "delete_component_fragments"
        )
        assert deleted == family["raw_prompts"][(mask, "SOURCE_AWARE_OMIT")]


@pytest.mark.parametrize(
    "field", ["payload_sha256", "prompt_sha256", "unit_manifest_sha256", "fragment_manifest_sha256"]
)
def test_production_entry_requires_every_saved_source_identity(renderer, field):
    family = renderer.render_family(PAYLOAD)
    identity = dict(family["identity"])
    identity[field] = "0" * 64
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        renderer.prepare_bound_payload(PAYLOAD, family["full_prompt"], identity)
    assert (
        renderer.prepare_bound_payload(PAYLOAD, family["full_prompt"], family["identity"])[
            "identity"
        ]
        == family["identity"]
    )


def test_production_entry_does_not_accept_same_hash_with_different_full_text(renderer):
    family = renderer.render_family(PAYLOAD)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        renderer.prepare_bound_payload(PAYLOAD, family["full_prompt"] + " ", family["identity"])


@pytest.mark.parametrize(
    "payload", ["", "a", "Synthetic\0payload", "Synthetic <|eot_id|>", "Synthetic <|im_start|>", 42]
)
def test_invalid_or_nonunique_payload_never_gets_materialization(renderer, payload):
    with pytest.raises((ValueError, TypeError)):
        renderer.render_family(payload)


@pytest.mark.parametrize(
    "expression",
    [
        "open('file')",
        "__import__('socket')",
        "object()",
        "AIMDecorator(seed=3)",
        "AIMDecorator(1)",
        "AIMDecorator().then(AIMDecorator())",
    ],
)
def test_restricted_compiler_cannot_escape_fixed_component_closure(renderer, expression):
    with pytest.raises(ValueError):
        renderer.namespace["eval"](expression)


def test_model_and_random_access_are_trapped(renderer):
    with pytest.raises(ValueError, match="MODEL_CALL_FORBIDDEN"):
        renderer.namespace["AIMDecorator"]().prompt_model("Synthetic")
    with pytest.raises(ValueError, match="RANDOM_DRAW_FORBIDDEN"):
        renderer.namespace["AIMDecorator"]()._random_state.randint(2)
    assert renderer.traps["model_calls"] == renderer.traps["random_draws"] == 1


def test_controls_match_independent_task_rerender_for_all_32_materials(renderer):
    family = renderer.render_family(PAYLOAD)
    controls = renderer.prepare_controls(family)
    assert len(controls) == 32
    assert {row["task_id"] for row in controls} == {"P2_ARITHMETIC", "P2_COPY_TOKEN"}
    task_text = {task["id"]: task["text"] for task in renderer.tasks}
    for row in controls:
        prompt = row["raw_prompt"]
        assert PAYLOAD not in prompt
        assert prompt.count(task_text[row["task_id"]]) == 1
        assert row["source_rerender_matches_slot_replacement"]
        assert row["prompt_sha256"] == row["source_rerender_prompt_sha256"] == m.text_sha(prompt)
        assert row["generation"] == {
            "seed": 17,
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "maximum_new_tokens": 48,
        }


def test_control_equivalence_is_exact_and_does_not_deduplicate(renderer):
    first = renderer.prepare_controls(renderer.render_family(PAYLOAD))
    second = renderer.prepare_controls(
        renderer.render_family("Another unique benign payload ZX_654.")
    )
    groups = m.control_equivalence(first + second)
    assert len(groups) == 30
    assert sum(group["member_count"] for group in groups) == 64
    assert sorted(group["member_count"] for group in groups) == [2] * 28 + [4] * 2
    assert len(first) == len(second) == 32
    changed_regime = copy.deepcopy(second)
    for row in changed_regime:
        row["generation"]["seed"] = 23
    assert len(m.control_equivalence(first + changed_regime)) == 60


def test_mutated_scientific_prompt_cannot_become_an_easier_control(renderer):
    family = renderer.render_family(PAYLOAD)
    family["raw_prompts"][(1, "SOURCE_AWARE_OMIT")] = PAYLOAD
    with pytest.raises(ValueError, match="SCIENTIFIC_MATERIAL_CHANGED"):
        renderer.prepare_controls(family)


def test_safe_projection_never_copies_raw_caller_fields(renderer):
    family = renderer.render_family(PAYLOAD)
    controls = renderer.prepare_controls(family)
    family["rows"][0]["untrusted_raw_content"] = PAYLOAD
    report = renderer.safe_report(family, controls)
    serialized = json.dumps(report, ensure_ascii=False)
    assert PAYLOAD not in serialized and "untrusted_raw_content" not in serialized
    assert "raw_prompt" not in serialized
    assert report["execution_authorized"] is False
    controls[0]["untrusted_raw_content"] = PAYLOAD
    with pytest.raises(ValueError, match="SAFE_CONTROL_PROJECTION"):
        renderer.safe_report(family, controls)


def test_uniform_bound_bundle_has_all_48_rows_and_separate_private_strings(renderer):
    family = renderer.render_family(PAYLOAD)
    bundle = renderer.prepare_bound_bundle(PAYLOAD, family["full_prompt"], family["identity"], 7)
    assert len(bundle["safe_rows"]) == len(bundle["private_rows"]) == 48
    assert sum(row["mask"] > 0 for row in bundle["safe_rows"]) == 42
    assert sum(row["kind"] == "science" and row["mask"] > 0 for row in bundle["safe_rows"]) == 14
    assert all(row["payload_position"] == 7 for row in bundle["safe_rows"])
    assert all(row["payload_sha256"] == m.text_sha(PAYLOAD) for row in bundle["safe_rows"])
    assert all(
        row["unit_manifest_sha256"] == family["identity"]["unit_manifest_sha256"]
        for row in bundle["safe_rows"]
    )
    assert PAYLOAD not in json.dumps(bundle["safe_rows"])
    for safe, private in zip(bundle["safe_rows"], bundle["private_rows"], strict=True):
        assert safe["prompt_sha256"] == m.text_sha(private["prompt"])
        assert safe["prompt_utf8_bytes"] == len(private["prompt"].encode())
    assert bundle["execution_authorized"] is False


def test_p3_manifest_canonical_hash_retains_original_ascii_escaping():
    value = [{"unicode": "합성"}]
    expected = m.hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert m.canonical_sha(value) == expected
