from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from jbspan.gate1.models import (
    ContractValidationError,
    Gate1Registry,
    NeutralizerSpec,
    OffsetSpan,
    PrimitiveSpec,
    ProgramNode,
    ProvenanceSegment,
    RenderedProgram,
)
from jbspan.gate1.util import sha256_text


def _render_template(template: str, parameters: Mapping[str, str]) -> str:
    try:
        return template.format_map(dict(parameters))
    except KeyError as exc:
        raise ContractValidationError(f"missing primitive parameter: {exc.args[0]}") from exc


def _select_parameter(
    registry: Gate1Registry,
    *,
    payload_id: str,
    family_id: str,
    node_id: str,
    parameter_name: str,
    domain: tuple[str, ...],
) -> str:
    identity = "\0".join(
        (
            registry.parameter_binding_seed,
            payload_id,
            family_id,
            node_id,
            parameter_name,
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], byteorder="big") % len(domain)
    return domain[index]


def _resolve_node(
    registry: Gate1Registry,
    *,
    payload_id: str,
    family_id: str,
    node: ProgramNode,
) -> ProgramNode:
    primitive = registry.primitives[node.primitive_id]
    resolved: dict[str, str] = {}
    for name, configured in node.parameters.items():
        if configured == registry.parameter_binding_sentinel:
            resolved[name] = _select_parameter(
                registry,
                payload_id=payload_id,
                family_id=family_id,
                node_id=node.node_id,
                parameter_name=name,
                domain=primitive.parameters[name],
            )
        else:
            resolved[name] = configured
    return ProgramNode(node.node_id, node.primitive_id, resolved)


def _node_parts(
    primitive: PrimitiveSpec,
    parameters: Mapping[str, str],
    *,
    neutralizer: NeutralizerSpec | None,
    selected: bool,
) -> tuple[str, str]:
    if not selected or neutralizer is None:
        return (
            _render_template(primitive.prefix_template, parameters),
            _render_template(primitive.suffix_template, parameters),
        )
    if not primitive.neutralizable:
        raise ContractValidationError(f"{primitive.primitive_id} is not neutralizable")
    if neutralizer.mode in {"disable", "diagnostic_delete"}:
        return "", ""
    if neutralizer.mode == "neutral_replace":
        return (
            _render_template(primitive.neutral_prefix_template, parameters),
            _render_template(primitive.neutral_suffix_template, parameters),
        )
    raise ContractValidationError(f"unsupported neutralizer mode: {neutralizer.mode}")


def render_program(
    registry: Gate1Registry,
    *,
    program_id: str,
    family_id: str,
    payload_id: str,
    payload_text: str,
    neutralized_node_ids: Sequence[str] = (),
    neutralizer_id: str | None = None,
) -> RenderedProgram:
    if not program_id.strip() or not payload_id.strip() or not payload_text:
        raise ContractValidationError("program_id, payload_id, and payload_text are required")
    family = registry.families.get(family_id)
    if family is None:
        raise ContractValidationError(f"unknown family_id: {family_id}")
    selected = tuple(neutralized_node_ids)
    if len(set(selected)) != len(selected):
        raise ContractValidationError("neutralized_node_ids must be unique")
    valid_ids = {node.node_id for node in family.nodes}
    unknown = sorted(set(selected) - valid_ids)
    if unknown:
        raise ContractValidationError(f"unknown neutralized nodes: {unknown}")
    neutralizer = _resolve_neutralizer(registry, selected, neutralizer_id)

    resolved_nodes = tuple(
        _resolve_node(
            registry,
            payload_id=payload_id,
            family_id=family_id,
            node=node,
        )
        for node in family.nodes
    )
    selected_set = set(selected)
    prefixes: list[tuple[ProgramNode, str]] = []
    suffixes: list[tuple[ProgramNode, str]] = []
    for node in resolved_nodes:
        primitive = registry.primitives[node.primitive_id]
        prefix, suffix = _node_parts(
            primitive,
            node.parameters,
            neutralizer=neutralizer,
            selected=node.node_id in selected_set,
        )
        prefixes.append((node, prefix))
        suffixes.append((node, suffix))

    parts: list[tuple[str, str, str, str]] = []
    parts.extend(
        ("node", node.node_id, "prefix", text)
        for node, text in prefixes
        if text
    )
    parts.append(("payload", payload_id, "payload", payload_text))
    parts.extend(
        ("node", node.node_id, "suffix", text)
        for node, text in reversed(suffixes)
        if text
    )
    rendered = _assemble(
        program_id=program_id,
        family_id=family_id,
        payload_id=payload_id,
        payload_text=payload_text,
        parts=parts,
        resolved_nodes=resolved_nodes,
        neutralizer_id=neutralizer_id,
        selected=selected,
    )
    validate_rendered_program(rendered, payload_text=payload_text)
    return rendered


def _resolve_neutralizer(
    registry: Gate1Registry,
    selected: tuple[str, ...],
    neutralizer_id: str | None,
) -> NeutralizerSpec | None:
    if not selected:
        if neutralizer_id is not None:
            raise ContractValidationError("neutralizer_id without selected nodes is invalid")
        return None
    if neutralizer_id is None:
        raise ContractValidationError("neutralizer_id is required for an intervention")
    neutralizer = registry.neutralizers.get(neutralizer_id)
    if neutralizer is None:
        raise ContractValidationError(f"unknown neutralizer_id: {neutralizer_id}")
    return neutralizer


def _assemble(
    *,
    program_id: str,
    family_id: str,
    payload_id: str,
    payload_text: str,
    parts: Sequence[tuple[str, str, str, str]],
    resolved_nodes: tuple[ProgramNode, ...],
    neutralizer_id: str | None,
    selected: tuple[str, ...],
) -> RenderedProgram:
    character_cursor = 0
    byte_cursor = 0
    text_parts: list[str] = []
    provenance: list[ProvenanceSegment] = []
    payload_character_span: OffsetSpan | None = None
    payload_byte_span: OffsetSpan | None = None
    for source_kind, source_id, part, text in parts:
        encoded = text.encode("utf-8")
        character_span = OffsetSpan(character_cursor, character_cursor + len(text))
        byte_span = OffsetSpan(byte_cursor, byte_cursor + len(encoded))
        text_parts.append(text)
        provenance.append(
            ProvenanceSegment(
                source_kind=source_kind,
                source_id=source_id,
                part=part,
                character_span=character_span,
                utf8_byte_span=byte_span,
                sha256=hashlib.sha256(encoded).hexdigest(),
            )
        )
        if source_kind == "payload":
            if payload_character_span is not None:
                raise ContractValidationError("payload rendered more than once")
            payload_character_span = character_span
            payload_byte_span = byte_span
        character_cursor = character_span.end
        byte_cursor = byte_span.end
    if payload_character_span is None or payload_byte_span is None:
        raise ContractValidationError("payload was not rendered")
    return RenderedProgram(
        program_id=program_id,
        family_id=family_id,
        payload_id=payload_id,
        text="".join(text_parts),
        payload_sha256=sha256_text(payload_text),
        payload_character_span=payload_character_span,
        payload_utf8_byte_span=payload_byte_span,
        provenance=tuple(provenance),
        resolved_nodes=resolved_nodes,
        neutralizer_id=neutralizer_id,
        neutralized_node_ids=selected,
    )


def validate_rendered_program(rendered: RenderedProgram, *, payload_text: str) -> None:
    if rendered.payload_sha256 != sha256_text(payload_text):
        raise ContractValidationError("payload hash changed")
    if rendered.text.count(payload_text) != 1:
        raise ContractValidationError("payload text must occur exactly once")
    observed = rendered.text[
        rendered.payload_character_span.start : rendered.payload_character_span.end
    ]
    if observed != payload_text:
        raise ContractValidationError("payload is not character-for-character invariant")
    encoded = rendered.text.encode("utf-8")
    payload_bytes = payload_text.encode("utf-8")
    observed_bytes = encoded[
        rendered.payload_utf8_byte_span.start : rendered.payload_utf8_byte_span.end
    ]
    if observed_bytes != payload_bytes:
        raise ContractValidationError("payload is not byte-for-byte invariant")
    payload_segments = [
        item for item in rendered.provenance if item.source_kind == "payload"
    ]
    if len(payload_segments) != 1:
        raise ContractValidationError("exactly one payload segment is required")
    character_cursor = 0
    byte_cursor = 0
    for item in rendered.provenance:
        if item.character_span.start != character_cursor:
            raise ContractValidationError("character provenance has a gap")
        if item.utf8_byte_span.start != byte_cursor:
            raise ContractValidationError("UTF-8 byte provenance has a gap")
        segment = rendered.text[item.character_span.start : item.character_span.end]
        segment_bytes = encoded[item.utf8_byte_span.start : item.utf8_byte_span.end]
        if segment.encode("utf-8") != segment_bytes:
            raise ContractValidationError("character and byte provenance disagree")
        if hashlib.sha256(segment_bytes).hexdigest() != item.sha256:
            raise ContractValidationError("provenance segment hash mismatch")
        if item.source_kind == "node" and (
            item.character_span.start < rendered.payload_character_span.end
            and rendered.payload_character_span.start < item.character_span.end
        ):
            raise ContractValidationError("node provenance overlaps payload provenance")
        character_cursor = item.character_span.end
        byte_cursor = item.utf8_byte_span.end
    if character_cursor != len(rendered.text):
        raise ContractValidationError("character provenance does not cover the prompt")
    if byte_cursor != len(encoded):
        raise ContractValidationError("byte provenance does not cover the prompt")
