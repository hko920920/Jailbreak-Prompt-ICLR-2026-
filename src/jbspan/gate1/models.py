from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class ContractValidationError(ValueError):
    """Raised when a frozen Gate 1 registry violates the contract."""


@dataclass(frozen=True)
class PayloadSource:
    source_id: str
    repository_id: str
    dataset_config: str
    split: str
    revision: str
    revision_kind: str
    resolve_full_revision_at_materialization: bool
    require_source_file_sha256: bool
    expected_rows: int
    expected_category_count: int
    license: str
    doi: str
    required_columns: tuple[str, ...]
    raw_payloads_committed: bool
    target_count: int
    minimum_count: int
    selection_seed: str
    selected_per_category: int
    development_per_category: int
    heldout_per_category: int

    @property
    def development_count(self) -> int:
        return self.expected_category_count * self.development_per_category

    @property
    def heldout_count(self) -> int:
        return self.expected_category_count * self.heldout_per_category


@dataclass(frozen=True)
class PrimitiveSpec:
    primitive_id: str
    version: str
    family: str
    prefix_template: str
    suffix_template: str
    neutral_prefix_template: str
    neutral_suffix_template: str
    parameters: dict[str, tuple[str, ...]]
    neutralizable: bool
    primary_gate1: bool


@dataclass(frozen=True)
class ProgramNode:
    node_id: str
    primitive_id: str
    parameters: dict[str, str]


@dataclass(frozen=True)
class CompositionFamily:
    family_id: str
    description: str
    nodes: tuple[ProgramNode, ...]
    split_group: str
    primary_gate1: bool


@dataclass(frozen=True)
class NeutralizerSpec:
    neutralizer_id: str
    mode: str
    primary_gate1: bool
    payload_preserving: bool
    typed_rerender_required: bool
    description: str


@dataclass(frozen=True)
class OffsetSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ContractValidationError("invalid offset span")

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class ProvenanceSegment:
    source_kind: str
    source_id: str
    part: str
    character_span: OffsetSpan
    utf8_byte_span: OffsetSpan
    sha256: str


@dataclass(frozen=True)
class RenderedProgram:
    program_id: str
    family_id: str
    payload_id: str
    text: str
    payload_sha256: str
    payload_character_span: OffsetSpan
    payload_utf8_byte_span: OffsetSpan
    provenance: tuple[ProvenanceSegment, ...]
    resolved_nodes: tuple[ProgramNode, ...]
    neutralizer_id: str | None
    neutralized_node_ids: tuple[str, ...]

    def to_safe_dict(self) -> dict[str, Any]:
        from jbspan.gate1.util import sha256_text

        return {
            "program_id": self.program_id,
            "family_id": self.family_id,
            "payload_id": self.payload_id,
            "prompt_sha256": sha256_text(self.text),
            "prompt_character_length": len(self.text),
            "prompt_utf8_byte_length": len(self.text.encode("utf-8")),
            "payload_sha256": self.payload_sha256,
            "payload_character_span": asdict(self.payload_character_span),
            "payload_utf8_byte_span": asdict(self.payload_utf8_byte_span),
            "resolved_nodes": [asdict(node) for node in self.resolved_nodes],
            "provenance": [
                {
                    "source_kind": item.source_kind,
                    "source_id": item.source_id,
                    "part": item.part,
                    "character_span": asdict(item.character_span),
                    "utf8_byte_span": asdict(item.utf8_byte_span),
                    "sha256": item.sha256,
                }
                for item in self.provenance
            ],
            "tokenization_status": "DEFERRED_UNTIL_TARGET_TOKENIZER_FREEZE",
            "neutralizer_id": self.neutralizer_id,
            "neutralized_node_ids": list(self.neutralized_node_ids),
        }


@dataclass(frozen=True)
class Gate1Registry:
    payload_source: PayloadSource
    primitives: dict[str, PrimitiveSpec]
    families: dict[str, CompositionFamily]
    neutralizers: dict[str, NeutralizerSpec]
    forbidden_neutral_cues: tuple[str, ...]
    parameter_binding_method: str
    parameter_binding_seed: str
    parameter_binding_sentinel: str
    token_provenance_stage: str
    max_neutralizable_nodes: int
    minimum_primitive_count: int
    minimum_family_count: int
    minimum_rendered_attacks: int
