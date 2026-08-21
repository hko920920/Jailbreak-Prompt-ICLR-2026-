from __future__ import annotations

import string
from collections.abc import Mapping
from itertools import product

from jbspan.gate1.common import (
    JsonObject,
    as_array,
    as_boolean,
    as_object,
    as_string,
    unique_strings,
)
from jbspan.gate1.models import (
    CompositionFamily,
    ContractValidationError,
    NeutralizerSpec,
    PrimitiveSpec,
    ProgramNode,
)

_FORMATTER = string.Formatter()


def _template_fields(template: str) -> tuple[str, ...]:
    fields: list[str] = []
    try:
        parsed = tuple(_FORMATTER.parse(template))
    except ValueError as exc:
        raise ContractValidationError("template has malformed braces") from exc
    for _, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if (
            not field_name
            or "." in field_name
            or "[" in field_name
            or "]" in field_name
            or format_spec
            or conversion is not None
        ):
            raise ContractValidationError("templates may use only simple named fields")
        fields.append(field_name)
    return tuple(fields)


def _parameter_assignments(
    parameters: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, str], ...]:
    names = tuple(sorted(parameters))
    if not names:
        return ({},)
    domains = tuple(parameters[name] for name in names)
    return tuple(dict(zip(names, values, strict=True)) for values in product(*domains))


def _validate_template(template: str, parameters: set[str], *, where: str) -> None:
    fields = _template_fields(template)
    unknown = sorted(set(fields) - parameters)
    if unknown:
        raise ContractValidationError(f"{where} has unknown template fields: {unknown}")
    if "payload" in fields:
        raise ContractValidationError(f"{where} must not interpolate the payload")


def parse_primitives(
    payload: JsonObject,
) -> tuple[dict[str, PrimitiveSpec], tuple[str, ...]]:
    forbidden = unique_strings(
        as_array(
            payload.get("forbidden_neutral_cues"),
            where="primitive_registry.forbidden_neutral_cues",
        ),
        where="primitive_registry.forbidden_neutral_cues",
    )
    primitives: dict[str, PrimitiveSpec] = {}
    for index, raw in enumerate(
        as_array(payload.get("primitives"), where="primitive_registry.primitives")
    ):
        item = as_object(raw, where=f"primitive[{index}]")
        primitive_id = as_string(
            item.get("primitive_id"), where=f"primitive[{index}].primitive_id"
        )
        if primitive_id in primitives:
            raise ContractValidationError(f"duplicate primitive_id: {primitive_id}")
        parameters = _parse_parameter_domains(item, index=index, primitive_id=primitive_id)
        templates = _parse_templates(item, index=index)
        for name, template in templates.items():
            _validate_template(template, set(parameters), where=f"{primitive_id}.{name}")
        _validate_neutral_templates(
            primitive_id=primitive_id,
            templates=templates,
            parameters=parameters,
            forbidden=forbidden,
        )
        primitives[primitive_id] = PrimitiveSpec(
            primitive_id=primitive_id,
            version=as_string(item.get("version"), where=f"{primitive_id}.version"),
            family=as_string(item.get("family"), where=f"{primitive_id}.family"),
            prefix_template=templates["prefix_template"],
            suffix_template=templates["suffix_template"],
            neutral_prefix_template=templates["neutral_prefix_template"],
            neutral_suffix_template=templates["neutral_suffix_template"],
            parameters=parameters,
            neutralizable=as_boolean(
                item.get("neutralizable"), where=f"{primitive_id}.neutralizable"
            ),
            primary_gate1=as_boolean(
                item.get("primary_gate1"), where=f"{primitive_id}.primary_gate1"
            ),
        )
    return primitives, forbidden


def _parse_parameter_domains(
    item: JsonObject,
    *,
    index: int,
    primitive_id: str,
) -> dict[str, tuple[str, ...]]:
    raw_parameters = as_object(item.get("parameters"), where=f"primitive[{index}].parameters")
    parameters: dict[str, tuple[str, ...]] = {}
    for raw_name, raw_values in raw_parameters.items():
        name = as_string(raw_name, where=f"primitive[{index}].parameter_name")
        parameters[name] = unique_strings(
            as_array(raw_values, where=f"primitive[{index}].parameters.{name}"),
            where=f"primitive[{index}].parameters.{name}",
        )
        if not parameters[name]:
            raise ContractValidationError(f"{primitive_id}.{name} has an empty domain")
    return parameters


def _parse_templates(item: JsonObject, *, index: int) -> dict[str, str]:
    suffix = item.get("suffix_template", "")
    neutral_suffix = item.get("neutral_suffix_template", "")
    if not isinstance(suffix, str) or not isinstance(neutral_suffix, str):
        raise ContractValidationError("suffix templates must be strings")
    return {
        "prefix_template": as_string(
            item.get("prefix_template"), where=f"primitive[{index}].prefix_template"
        ),
        "suffix_template": suffix,
        "neutral_prefix_template": as_string(
            item.get("neutral_prefix_template"),
            where=f"primitive[{index}].neutral_prefix_template",
        ),
        "neutral_suffix_template": neutral_suffix,
    }


def _validate_neutral_templates(
    *,
    primitive_id: str,
    templates: Mapping[str, str],
    parameters: Mapping[str, tuple[str, ...]],
    forbidden: tuple[str, ...],
) -> None:
    rendered_neutral_texts = (
        (
            templates["neutral_prefix_template"].format_map(assignment)
            + templates["neutral_suffix_template"].format_map(assignment)
        ).casefold()
        for assignment in _parameter_assignments(parameters)
    )
    leaked = sorted(
        {
            cue
            for text in rendered_neutral_texts
            for cue in forbidden
            if cue.casefold() in text
        }
    )
    if leaked:
        raise ContractValidationError(
            f"{primitive_id} neutral templates contain forbidden cues: {leaked}"
        )
    if (
        templates["prefix_template"] == templates["neutral_prefix_template"]
        and templates["suffix_template"] == templates["neutral_suffix_template"]
    ):
        raise ContractValidationError(f"{primitive_id} neutralization is a no-op")


def parse_families(
    payload: JsonObject,
    primitives: Mapping[str, PrimitiveSpec],
    *,
    binding_sentinel: str,
) -> dict[str, CompositionFamily]:
    families: dict[str, CompositionFamily] = {}
    raw_families = as_array(payload.get("families"), where="composition_grammar.families")
    for family_index, raw in enumerate(raw_families):
        item = as_object(raw, where=f"family[{family_index}]")
        family_id = as_string(item.get("family_id"), where="family.family_id")
        if family_id in families:
            raise ContractValidationError(f"duplicate family_id: {family_id}")
        nodes = _parse_nodes(
            item,
            family_id=family_id,
            primitives=primitives,
            binding_sentinel=binding_sentinel,
        )
        families[family_id] = CompositionFamily(
            family_id=family_id,
            description=as_string(item.get("description"), where=f"{family_id}.description"),
            nodes=nodes,
            split_group=as_string(item.get("split_group"), where=f"{family_id}.split_group"),
            primary_gate1=as_boolean(
                item.get("primary_gate1"), where=f"{family_id}.primary_gate1"
            ),
        )
    return families


def _parse_nodes(
    item: JsonObject,
    *,
    family_id: str,
    primitives: Mapping[str, PrimitiveSpec],
    binding_sentinel: str,
) -> tuple[ProgramNode, ...]:
    nodes: list[ProgramNode] = []
    node_ids: set[str] = set()
    primitive_ids: set[str] = set()
    for node_index, raw_node in enumerate(as_array(item.get("nodes"), where=f"{family_id}.nodes")):
        node = as_object(raw_node, where=f"{family_id}.nodes[{node_index}]")
        node_id = as_string(node.get("node_id"), where=f"{family_id}.node_id")
        primitive_id = as_string(
            node.get("primitive_id"), where=f"{family_id}.primitive_id"
        )
        if node_id in node_ids:
            raise ContractValidationError(f"duplicate node_id in {family_id}: {node_id}")
        if primitive_id in primitive_ids:
            raise ContractValidationError(
                f"duplicate primitive in one composition family: {primitive_id}"
            )
        primitive = primitives.get(primitive_id)
        if primitive is None:
            raise ContractValidationError(f"unknown primitive: {primitive_id}")
        parameters = _parse_node_parameters(
            node,
            family_id=family_id,
            node_id=node_id,
            primitive=primitive,
            binding_sentinel=binding_sentinel,
        )
        nodes.append(ProgramNode(node_id, primitive_id, parameters))
        node_ids.add(node_id)
        primitive_ids.add(primitive_id)
    if not nodes:
        raise ContractValidationError(f"{family_id} has no nodes")
    return tuple(nodes)


def _parse_node_parameters(
    node: JsonObject,
    *,
    family_id: str,
    node_id: str,
    primitive: PrimitiveSpec,
    binding_sentinel: str,
) -> dict[str, str]:
    raw_parameters = as_object(node.get("parameters"), where=f"{family_id}.{node_id}.parameters")
    if set(raw_parameters) != set(primitive.parameters):
        raise ContractValidationError(
            f"{family_id}.{node_id} parameters do not match the primitive"
        )
    parameters: dict[str, str] = {}
    for raw_name, raw_value in raw_parameters.items():
        name = as_string(raw_name, where=f"{family_id}.{node_id}.parameter_name")
        selected = as_string(raw_value, where=f"{family_id}.{node_id}.{name}")
        if selected != binding_sentinel and selected not in primitive.parameters[name]:
            raise ContractValidationError(
                f"{family_id}.{node_id}.{name} is outside the frozen domain"
            )
        parameters[name] = selected
    return parameters


def parse_neutralizers(payload: JsonObject) -> dict[str, NeutralizerSpec]:
    neutralizers: dict[str, NeutralizerSpec] = {}
    raw_items = as_array(payload.get("neutralizers"), where="neutralizer_registry")
    for index, raw in enumerate(raw_items):
        item = as_object(raw, where=f"neutralizer[{index}]")
        identifier = as_string(item.get("neutralizer_id"), where="neutralizer_id")
        if identifier in neutralizers:
            raise ContractValidationError(f"duplicate neutralizer_id: {identifier}")
        mode = as_string(item.get("mode"), where=f"{identifier}.mode")
        if mode not in {"disable", "neutral_replace", "diagnostic_delete"}:
            raise ContractValidationError(f"unsupported neutralizer mode: {mode}")
        neutralizers[identifier] = NeutralizerSpec(
            neutralizer_id=identifier,
            mode=mode,
            primary_gate1=as_boolean(
                item.get("primary_gate1"), where=f"{identifier}.primary_gate1"
            ),
            payload_preserving=as_boolean(
                item.get("payload_preserving"), where=f"{identifier}.payload_preserving"
            ),
            typed_rerender_required=as_boolean(
                item.get("typed_rerender_required"),
                where=f"{identifier}.typed_rerender_required",
            ),
            description=as_string(item.get("description"), where=f"{identifier}.description"),
        )
    return neutralizers
