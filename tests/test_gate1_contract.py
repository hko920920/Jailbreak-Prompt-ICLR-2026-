from __future__ import annotations

from pathlib import Path

import pytest

from jbspan.gate1 import (
    ContractValidationError,
    contract_manifest,
    load_gate1_registry,
    render_program,
    sha256_text,
)

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_registry_meets_gate1_contract() -> None:
    registry = load_gate1_registry(ROOT)

    assert registry.payload_source.expected_rows == 100
    assert registry.payload_source.expected_category_count == 10
    assert registry.payload_source.target_count == 60
    assert registry.payload_source.development_count == 50
    assert registry.payload_source.heldout_count == 10
    assert sum(item.primary_gate1 for item in registry.primitives.values()) >= 6
    assert sum(item.primary_gate1 for item in registry.families.values()) >= 4
    assert sum(item.primary_gate1 for item in registry.neutralizers.values()) == 2


def test_rendering_preserves_payload_and_complete_provenance() -> None:
    registry = load_gate1_registry(ROOT)
    payload = "Explain how pollinators support flowering plants. 🌼"
    rendered = render_program(
        registry,
        program_id="toy-program",
        family_id="layered_fictional_persona",
        payload_id="TOY-001",
        payload_text=payload,
    )

    assert rendered.payload_sha256 == sha256_text(payload)
    char_span = rendered.payload_character_span
    byte_span = rendered.payload_utf8_byte_span
    assert rendered.text[char_span.start : char_span.end] == payload
    assert rendered.text.encode("utf-8")[byte_span.start : byte_span.end] == payload.encode(
        "utf-8"
    )
    assert sum(item.source_kind == "payload" for item in rendered.provenance) == 1
    assert rendered.provenance[0].character_span.start == 0
    assert rendered.provenance[-1].character_span.end == len(rendered.text)
    assert rendered.provenance[-1].utf8_byte_span.end == len(rendered.text.encode("utf-8"))


def test_parameter_binding_is_deterministic_and_uses_frozen_domains() -> None:
    registry = load_gate1_registry(ROOT)
    rendered = [
        render_program(
            registry,
            program_id=f"toy-{index}",
            family_id="persona_justification",
            payload_id=f"TOY-{index:03d}",
            payload_text="Summarize photosynthesis.",
        )
        for index in range(20)
    ]
    repeated = render_program(
        registry,
        program_id="repeat",
        family_id="persona_justification",
        payload_id="TOY-000",
        payload_text="Summarize photosynthesis.",
    )

    assert rendered[0].resolved_nodes == repeated.resolved_nodes
    observed_personas = {
        item.resolved_nodes[0].parameters["persona"] for item in rendered
    }
    assert len(observed_personas) > 1
    assert observed_personas <= set(registry.primitives["persona_frame"].parameters["persona"])


def test_both_primary_neutralizers_keep_payload_byte_identical() -> None:
    registry = load_gate1_registry(ROOT)
    payload = "Describe a safe household recycling routine. ♻️"
    family = registry.families["authority_directness"]
    node_id = family.nodes[0].node_id

    baseline = render_program(
        registry,
        program_id="toy-program",
        family_id=family.family_id,
        payload_id="TOY-002",
        payload_text=payload,
    )
    variants = []
    for neutralizer in registry.neutralizers.values():
        if not neutralizer.primary_gate1:
            continue
        variants.append(
            render_program(
                registry,
                program_id="toy-program",
                family_id=family.family_id,
                payload_id="TOY-002",
                payload_text=payload,
                neutralized_node_ids=(node_id,),
                neutralizer_id=neutralizer.neutralizer_id,
            )
        )

    assert len(variants) == 2
    assert all(item.payload_sha256 == baseline.payload_sha256 for item in variants)
    assert all(
        item.text.encode("utf-8")[
            item.payload_utf8_byte_span.start : item.payload_utf8_byte_span.end
        ]
        == payload.encode("utf-8")
        for item in variants
    )
    assert all(item.text != baseline.text for item in variants)


def test_unknown_duplicate_or_unbound_interventions_are_rejected() -> None:
    registry = load_gate1_registry(ROOT)
    kwargs = {
        "program_id": "toy-program",
        "family_id": "persona_justification",
        "payload_id": "TOY-003",
        "payload_text": "Summarize photosynthesis.",
    }
    with pytest.raises(ContractValidationError, match="unknown neutralized nodes"):
        render_program(
            registry,
            neutralized_node_ids=("missing",),
            neutralizer_id="typed_disable_v1",
            **kwargs,
        )
    with pytest.raises(ContractValidationError, match="must be unique"):
        render_program(
            registry,
            neutralized_node_ids=("persona", "persona"),
            neutralizer_id="typed_disable_v1",
            **kwargs,
        )
    with pytest.raises(ContractValidationError, match="without selected nodes"):
        render_program(registry, neutralizer_id="typed_disable_v1", **kwargs)


def test_contract_manifest_is_safe_and_deterministic() -> None:
    registry = load_gate1_registry(ROOT)
    first = contract_manifest(ROOT, registry)
    second = contract_manifest(ROOT, registry)

    assert first == second
    assert first["status"] == "GATE1_CONTRACT_VALIDATED"
    assert first["raw_payloads_committed"] is False
    assert first["gate1_development_payload_count"] == 50
    assert first["gate2_heldout_payload_count"] == 10
    assert first["projected_gate1_attack_count"] >= 200
    assert len(first["contract_sha256"]) == 64
