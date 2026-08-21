from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jbspan.gate1.manifest import contract_manifest
from jbspan.gate1.models import ContractValidationError, Gate1Registry, PayloadSource
from jbspan.gate1.render import render_program
from jbspan.gate1.util import canonical_json_sha256, sha256_text

JsonDict = dict[str, Any]
_SOURCE_PATH = "data/harmful-behaviors.csv"
_SELECTION_METHOD = "per_category_sha256_rank_v1"


@dataclass(frozen=True)
class SourceRow:
    index: int
    goal: str
    target: str
    behavior: str
    category: str
    source_label: str


@dataclass(frozen=True)
class SelectedPayload:
    row: SourceRow
    payload_id: str
    split: str
    category_rank: int
    selection_sha256: str


@dataclass(frozen=True)
class SourceIdentity:
    repository_id: str
    requested_revision: str
    resolved_revision: str
    source_file_path: str
    source_file_sha256: str
    source_file_size_bytes: int
    row_count: int
    category_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_source_rows(path: Path, source: PayloadSource) -> tuple[SourceRow, ...]:
    if not path.is_file():
        raise ContractValidationError(f"source CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractValidationError("source CSV has no header")
        if tuple(reader.fieldnames) != source.required_columns:
            raise ContractValidationError("source CSV columns differ from frozen contract")
        rows = tuple(_parse_row(raw, line_number) for line_number, raw in enumerate(reader, 2))
    _validate_source_rows(rows, source)
    return rows


def _parse_row(raw: dict[str, str | None], line_number: int) -> SourceRow:
    def required(name: str) -> str:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ContractValidationError(f"source row {line_number} has invalid {name}")
        return value

    try:
        index = int(required("Index"))
    except ValueError as exc:
        raise ContractValidationError(f"source row {line_number} has invalid Index") from exc
    return SourceRow(
        index=index,
        goal=required("Goal"),
        target=required("Target"),
        behavior=required("Behavior"),
        category=required("Category"),
        source_label=required("Source"),
    )


def _validate_source_rows(rows: tuple[SourceRow, ...], source: PayloadSource) -> None:
    if len(rows) != source.expected_rows:
        raise ContractValidationError("source row count differs from frozen contract")
    indexes = [row.index for row in rows]
    if len(set(indexes)) != len(indexes):
        raise ContractValidationError("source Index values must be unique")
    if sorted(indexes) != list(range(source.expected_rows)):
        raise ContractValidationError("source Index values must be contiguous from zero")
    category_counts = Counter(row.category for row in rows)
    if len(category_counts) != source.expected_category_count:
        raise ContractValidationError("source category count differs from frozen contract")
    expected_per_category, remainder = divmod(
        source.expected_rows, source.expected_category_count
    )
    if remainder or set(category_counts.values()) != {expected_per_category}:
        raise ContractValidationError("source categories are not uniformly populated")


def resolve_source_identity(
    path: Path,
    source: PayloadSource,
    *,
    resolved_revision: str,
    source_file_path: str = _SOURCE_PATH,
    expected_source_sha256: str | None = None,
) -> SourceIdentity:
    valid_hex = all(character in "0123456789abcdef" for character in resolved_revision)
    if len(resolved_revision) != 40 or not valid_hex:
        raise ContractValidationError("resolved source revision must be a 40-character hex SHA")
    if not resolved_revision.startswith(source.revision):
        raise ContractValidationError("resolved source revision does not match requested prefix")
    if source_file_path != _SOURCE_PATH:
        raise ContractValidationError("source file path differs from the frozen Step 2 path")
    source_file_sha256 = sha256_file(path)
    if expected_source_sha256 is not None and source_file_sha256 != expected_source_sha256:
        raise ContractValidationError("source file SHA-256 differs from frozen identity")
    rows = load_source_rows(path, source)
    return SourceIdentity(
        repository_id=source.repository_id,
        requested_revision=source.revision,
        resolved_revision=resolved_revision,
        source_file_path=source_file_path,
        source_file_sha256=source_file_sha256,
        source_file_size_bytes=path.stat().st_size,
        row_count=len(rows),
        category_count=len({row.category for row in rows}),
    )


def _selection_digest(source: PayloadSource, row: SourceRow) -> str:
    identity = "\0".join(
        (
            source.selection_seed,
            row.category,
            str(row.index),
            sha256_text(row.goal),
            sha256_text(row.behavior),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def select_payloads(
    rows: tuple[SourceRow, ...], source: PayloadSource
) -> tuple[SelectedPayload, ...]:
    grouped: dict[str, list[SourceRow]] = defaultdict(list)
    for row in rows:
        grouped[row.category].append(row)
    selected: list[SelectedPayload] = []
    for category in sorted(grouped):
        ranked = sorted(
            ((_selection_digest(source, row), row.index, row) for row in grouped[category]),
            key=lambda item: (item[0], item[1]),
        )
        if len(ranked) < source.selected_per_category:
            raise ContractValidationError(f"category has too few rows: {category}")
        for rank, (digest, _, row) in enumerate(ranked[: source.selected_per_category]):
            split = (
                "gate1_development"
                if rank < source.development_per_category
                else "gate2_heldout"
            )
            selected.append(
                SelectedPayload(
                    row=row,
                    payload_id=f"JBB-{row.index:03d}",
                    split=split,
                    category_rank=rank,
                    selection_sha256=digest,
                )
            )
    selected.sort(key=lambda item: (item.split, item.row.category, item.category_rank))
    _validate_selection(selected, source)
    return tuple(selected)


def _validate_selection(selected: list[SelectedPayload], source: PayloadSource) -> None:
    if len(selected) != source.target_count:
        raise ContractValidationError("selected payload count differs from frozen target")
    if len({item.payload_id for item in selected}) != len(selected):
        raise ContractValidationError("selected payload IDs must be unique")
    split_counts = Counter(item.split for item in selected)
    if split_counts["gate1_development"] != source.development_count:
        raise ContractValidationError("development payload count differs from contract")
    if split_counts["gate2_heldout"] != source.heldout_count:
        raise ContractValidationError("heldout payload count differs from contract")
    category_split = Counter((item.row.category, item.split) for item in selected)
    for category in {item.row.category for item in selected}:
        if category_split[(category, "gate1_development")] != source.development_per_category:
            raise ContractValidationError("development category allocation is invalid")
        if category_split[(category, "gate2_heldout")] != source.heldout_per_category:
            raise ContractValidationError("heldout category allocation is invalid")


def safe_payload_registry(
    selected: tuple[SelectedPayload, ...],
    source: PayloadSource,
    identity: SourceIdentity,
) -> JsonDict:
    payloads = [
        {
            "payload_id": item.payload_id,
            "source_row_index": item.row.index,
            "behavior": item.row.behavior,
            "category": item.row.category,
            "source_label": item.row.source_label,
            "payload_sha256": sha256_text(item.row.goal),
            "payload_character_length": len(item.row.goal),
            "payload_utf8_byte_length": len(item.row.goal.encode("utf-8")),
            "split": item.split,
        }
        for item in sorted(selected, key=lambda value: value.payload_id)
    ]
    return {
        "schema_version": "gate1-payload-registry-v1",
        "source_id": source.source_id,
        "requested_source_revision": source.revision,
        "resolved_source_revision": identity.resolved_revision,
        "source_file_sha256": identity.source_file_sha256,
        "selection_method": _SELECTION_METHOD,
        "selection_seed": source.selection_seed,
        "category_count": identity.category_count,
        "development_count": source.development_count,
        "heldout_count": source.heldout_count,
        "payloads": payloads,
    }


def _benchmark_record(
    *,
    registry: Gate1Registry,
    contract_sha256: str,
    payload: SelectedPayload,
    family_id: str,
) -> tuple[JsonDict, JsonDict]:
    program_id = f"G1-{payload.payload_id}-{family_id}"
    rendered = render_program(
        registry,
        program_id=program_id,
        family_id=family_id,
        payload_id=payload.payload_id,
        payload_text=payload.row.goal,
    )
    safe_rendered = rendered.to_safe_dict()
    record: JsonDict = {
        "schema_version": "gate1-benchmark-record-v1",
        "contract_sha256": contract_sha256,
        "example_id": program_id,
        "payload_id": payload.payload_id,
        "payload_sha256": rendered.payload_sha256,
        "program_id": program_id,
        "family_id": family_id,
        "program_nodes": safe_rendered["resolved_nodes"],
        "rendered_prompt_sha256": safe_rendered["prompt_sha256"],
        "rendered_prompt_character_length": safe_rendered["prompt_character_length"],
        "rendered_prompt_utf8_byte_length": safe_rendered["prompt_utf8_byte_length"],
        "payload_character_span": safe_rendered["payload_character_span"],
        "payload_utf8_byte_span": safe_rendered["payload_utf8_byte_span"],
        "provenance": safe_rendered["provenance"],
        "tokenization_status": safe_rendered["tokenization_status"],
        "split": payload.split,
        "invariants": {
            "payload_byte_identical": True,
            "payload_overlap_count": 0,
            "typed_compile_passed": True,
            "inserted_forbidden_safety_cue_count": 0,
        },
    }
    private: JsonDict = {
        "example_id": program_id,
        "payload_id": payload.payload_id,
        "payload_text": payload.row.goal,
        "target_text": payload.row.target,
        "rendered_prompt": rendered.text,
        "family_id": family_id,
        "split": payload.split,
    }
    return record, private


def materialize_benchmark(
    root: Path,
    registry: Gate1Registry,
    selected: tuple[SelectedPayload, ...],
) -> tuple[tuple[JsonDict, ...], tuple[JsonDict, ...]]:
    contract_sha256 = str(contract_manifest(root, registry)["contract_sha256"])
    primary_families = sorted(
        family.family_id for family in registry.families.values() if family.primary_gate1
    )
    safe_records: list[JsonDict] = []
    private_records: list[JsonDict] = []
    for payload in selected:
        if payload.split != "gate1_development":
            continue
        for family_id in primary_families:
            safe, private = _benchmark_record(
                registry=registry,
                contract_sha256=contract_sha256,
                payload=payload,
                family_id=family_id,
            )
            safe_records.append(safe)
            private_records.append(private)
    projected = registry.payload_source.development_count * len(primary_families)
    if len(safe_records) != projected:
        raise ContractValidationError("rendered attack denominator differs from contract")
    if len({str(item["example_id"]) for item in safe_records}) != len(safe_records):
        raise ContractValidationError("rendered attack IDs must be unique")
    return tuple(safe_records), tuple(private_records)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: Iterable[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def materialize_gate1_step2(
    root: Path,
    registry: Gate1Registry,
    *,
    source_csv: Path,
    resolved_revision: str,
    safe_output_dir: Path,
    private_output_dir: Path,
    expected_source_sha256: str | None = None,
) -> JsonDict:
    rows = load_source_rows(source_csv, registry.payload_source)
    identity = resolve_source_identity(
        source_csv,
        registry.payload_source,
        resolved_revision=resolved_revision,
        expected_source_sha256=expected_source_sha256,
    )
    selected = select_payloads(rows, registry.payload_source)
    payload_registry = safe_payload_registry(selected, registry.payload_source, identity)
    safe_records, private_records = materialize_benchmark(root, registry, selected)

    source_identity_path = safe_output_dir / "source_identity.json"
    payload_registry_path = safe_output_dir / "payload_registry.safe.json"
    records_path = safe_output_dir / "benchmark_records.safe.jsonl"
    denominator_path = safe_output_dir / "denominator_manifest.json"
    exclusions_path = safe_output_dir / "exclusion_ledger.safe.json"
    write_json(source_identity_path, identity.to_dict())
    write_json(payload_registry_path, payload_registry)
    write_jsonl(records_path, safe_records)
    write_json(
        exclusions_path,
        {
            "schema_version": "gate1-step2-exclusion-ledger-v1",
            "stage": "pre_inference_materialization",
            "count": 0,
            "exclusions": [],
        },
    )

    development = [item for item in selected if item.split == "gate1_development"]
    heldout = [item for item in selected if item.split == "gate2_heldout"]
    family_counts = Counter(str(item["family_id"]) for item in safe_records)
    category_counts = Counter(item.row.category for item in development)
    denominator: JsonDict = {
        "schema_version": "gate1-step2-denominator-v1",
        "status": "GATE1_STEP2_DENOMINATOR_MATERIALIZED",
        "target_model_inference_performed": False,
        "generated_attack_count": len(safe_records),
        "development_payload_count": len(development),
        "heldout_payload_count": len(heldout),
        "category_counts": dict(sorted(category_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "render_failures": 0,
        "exclusion_count": 0,
    }
    write_json(denominator_path, denominator)

    write_jsonl(
        private_output_dir / "payloads.private.jsonl",
        (
            {
                "payload_id": item.payload_id,
                "source_row_index": item.row.index,
                "goal": item.row.goal,
                "target": item.row.target,
                "behavior": item.row.behavior,
                "category": item.row.category,
                "source_label": item.row.source_label,
                "split": item.split,
            }
            for item in selected
        ),
    )
    write_jsonl(private_output_dir / "benchmark_records.private.jsonl", private_records)

    safe_files = (
        source_identity_path,
        payload_registry_path,
        records_path,
        denominator_path,
        exclusions_path,
    )
    manifest: JsonDict = {
        "schema_version": "gate1-step2-materialization-manifest-v1",
        "status": "GATE1_STEP2_MATERIALIZED",
        "paper_validity": False,
        "target_model_inference_performed": False,
        "raw_payloads_committed": False,
        "raw_rendered_prompts_committed": False,
        "contract_sha256": contract_manifest(root, registry)["contract_sha256"],
        "source_identity": identity.to_dict(),
        "selection_sha256": canonical_json_sha256(
            [
                {
                    "payload_id": item.payload_id,
                    "split": item.split,
                    "category_rank": item.category_rank,
                    "selection_sha256": item.selection_sha256,
                }
                for item in selected
            ]
        ),
        "payload_registry_sha256": canonical_json_sha256(payload_registry),
        "development_payload_count": len(development),
        "heldout_payload_count": len(heldout),
        "rendered_attack_count": len(safe_records),
        "safe_file_sha256": {path.name: sha256_file(path) for path in safe_files},
        "private_file_count": 2,
        "exclusion_count": 0,
    }
    write_json(safe_output_dir / "materialization_manifest.json", manifest)
    return manifest
