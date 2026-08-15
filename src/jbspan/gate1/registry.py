from __future__ import annotations

from pathlib import Path

from jbspan.gate1.common import JsonObject, as_integer, as_object, as_string
from jbspan.gate1.models import ContractValidationError, Gate1Registry
from jbspan.gate1.parse_program import parse_families, parse_neutralizers, parse_primitives
from jbspan.gate1.parse_source import parse_payload_source
from jbspan.gate1.util import load_json

_SUPPORTED_PARAMETER_BINDING = "sha256_domain_index_v1"


def load_gate1_registry(root: Path) -> Gate1Registry:
    config = load_json(root / "configs/gate1/gate1_frozen_config.json")
    if config.get("schema_version") != "gate1-frozen-config-v1":
        raise ContractValidationError("unsupported Gate 1 config version")
    if config.get("frozen") is not True:
        raise ContractValidationError("Gate 1 config must be frozen")
    binding = as_object(config.get("parameter_binding"), where="parameter_binding")
    binding_method = as_string(binding.get("method"), where="parameter_binding.method")
    if binding_method != _SUPPORTED_PARAMETER_BINDING:
        raise ContractValidationError("unsupported parameter-binding method")
    binding_seed = as_string(binding.get("seed"), where="parameter_binding.seed")
    binding_sentinel = as_string(binding.get("sentinel"), where="parameter_binding.sentinel")
    provenance = as_object(config.get("provenance_contract"), where="provenance_contract")
    primitives, forbidden = parse_primitives(
        load_json(root / as_string(config.get("primitive_registry"), where="primitive_registry"))
    )
    thresholds = as_object(config.get("contract_thresholds"), where="contract_thresholds")
    registry = Gate1Registry(
        payload_source=parse_payload_source(
            load_json(
                root
                / as_string(
                    config.get("payload_source_registry"), where="payload_source_registry"
                )
            )
        ),
        primitives=primitives,
        families=parse_families(
            load_json(
                root
                / as_string(config.get("composition_grammar"), where="composition_grammar")
            ),
            primitives,
            binding_sentinel=binding_sentinel,
        ),
        neutralizers=parse_neutralizers(
            load_json(
                root
                / as_string(config.get("neutralizer_registry"), where="neutralizer_registry")
            )
        ),
        forbidden_neutral_cues=forbidden,
        parameter_binding_method=binding_method,
        parameter_binding_seed=binding_seed,
        parameter_binding_sentinel=binding_sentinel,
        token_provenance_stage=as_string(
            provenance.get("token_offsets_required_stage"),
            where="provenance_contract.token_offsets_required_stage",
        ),
        max_neutralizable_nodes=as_integer(
            thresholds.get("max_neutralizable_nodes"),
            where="max_neutralizable_nodes",
        ),
        minimum_primitive_count=as_integer(
            thresholds.get("minimum_primitive_count"),
            where="minimum_primitive_count",
        ),
        minimum_family_count=as_integer(
            thresholds.get("minimum_family_count"), where="minimum_family_count"
        ),
        minimum_rendered_attacks=as_integer(
            thresholds.get("minimum_rendered_attacks"),
            where="minimum_rendered_attacks",
        ),
    )
    _validate_provenance_contract(provenance)
    validate_registry(registry)
    validate_schema_files(root, registry, config)
    return registry


def _validate_provenance_contract(provenance: JsonObject) -> None:
    if provenance.get("character_offsets") != "required_at_render":
        raise ContractValidationError("character provenance must be required at render")
    if provenance.get("utf8_byte_offsets") != "required_at_render":
        raise ContractValidationError("UTF-8 byte provenance must be required at render")
    if provenance.get("token_offsets") != "required_after_target_tokenizer_freeze":
        raise ContractValidationError("token provenance stage is not frozen")


def validate_registry(registry: Gate1Registry) -> None:
    primary_primitives = [item for item in registry.primitives.values() if item.primary_gate1]
    primary_families = [item for item in registry.families.values() if item.primary_gate1]
    primary_neutralizers = [
        item for item in registry.neutralizers.values() if item.primary_gate1
    ]
    if len(primary_primitives) < registry.minimum_primitive_count:
        raise ContractValidationError("insufficient primary primitives")
    if len(primary_families) < registry.minimum_family_count:
        raise ContractValidationError("insufficient primary composition families")
    if len(primary_neutralizers) != 2:
        raise ContractValidationError("exactly two primary neutralizers are required")
    split_groups = [family.split_group for family in primary_families]
    if len(set(split_groups)) != len(split_groups):
        raise ContractValidationError("primary composition split groups must be unique")
    used_primitives: set[str] = set()
    for family in primary_families:
        count = 0
        for node in family.nodes:
            primitive = registry.primitives[node.primitive_id]
            if not primitive.primary_gate1:
                raise ContractValidationError(
                    f"{family.family_id} uses a non-primary primitive"
                )
            used_primitives.add(node.primitive_id)
            count += int(primitive.neutralizable)
        if count > registry.max_neutralizable_nodes:
            raise ContractValidationError(f"{family.family_id} exceeds the node limit")
    missing = sorted(
        item.primitive_id
        for item in primary_primitives
        if item.primitive_id not in used_primitives
    )
    if missing:
        raise ContractValidationError(f"unused primary primitives: {missing}")
    for neutralizer in primary_neutralizers:
        if not neutralizer.payload_preserving or not neutralizer.typed_rerender_required:
            raise ContractValidationError(f"{neutralizer.neutralizer_id} violates invariants")
        if neutralizer.mode not in {"disable", "neutral_replace"}:
            raise ContractValidationError("a diagnostic neutralizer cannot be primary")
    projected = registry.payload_source.development_count * len(primary_families)
    if projected < registry.minimum_rendered_attacks:
        raise ContractValidationError("contract cannot produce the minimum denominator")


def validate_schema_files(root: Path, registry: Gate1Registry, config: JsonObject) -> None:
    schema_paths = (
        as_string(config.get("payload_registry_schema"), where="payload_registry_schema"),
        as_string(config.get("benchmark_record_schema"), where="benchmark_record_schema"),
        as_string(
            config.get("tokenized_provenance_schema"),
            where="tokenized_provenance_schema",
        ),
    )
    expected_schema = "https://json-schema.org/draft/2020-12/schema"
    for path in schema_paths:
        schema = load_json(root / path)
        if schema.get("$schema") != expected_schema:
            raise ContractValidationError(f"{path} must use JSON Schema 2020-12")
    benchmark = load_json(root / schema_paths[1])
    properties = as_object(benchmark.get("properties"), where="benchmark.properties")
    nodes = as_object(properties.get("program_nodes"), where="benchmark.program_nodes")
    if nodes.get("maxItems") != registry.max_neutralizable_nodes:
        raise ContractValidationError("benchmark node maximum must match the contract")
