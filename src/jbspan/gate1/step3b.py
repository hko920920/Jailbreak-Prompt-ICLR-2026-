from __future__ import annotations

import ast
import csv
import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jbspan.gate1.common import (
    JsonObject,
    as_array,
    as_integer,
    as_object,
    as_string,
    unique_strings,
)
from jbspan.gate1.models import ContractValidationError
from jbspan.gate1.step3 import sha256_file, write_json
from jbspan.gate1.util import canonical_json_sha256, load_json, sha256_text


@dataclass(frozen=True)
class WrapperNode:
    source_program_id: str
    source_node_index: int
    prefix: str
    suffix: str


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    source_program_ids: tuple[str, ...]


@dataclass(frozen=True)
class RenderedCandidate:
    candidate_id: str
    text: str
    payload_character_start: int
    payload_character_end: int
    nodes: tuple[WrapperNode, ...]


def load_step3b_contract(root: Path) -> JsonObject:
    payload = load_json(root / "configs/gate1/gate1_step3b.json")
    validate_step3b_contract(payload)
    return payload


def validate_step3b_contract(payload: JsonObject) -> None:
    if payload.get("schema_version") != "gate1-step3b-contract-v1":
        raise ContractValidationError("unsupported Gate 1 Step 3B contract")
    if payload.get("frozen") is not True:
        raise ContractValidationError("Step 3B contract must be frozen")
    source = as_object(payload.get("source"), where="source")
    revision = as_string(source.get("revision"), where="source.revision")
    if len(revision) != 40:
        raise ContractValidationError("source revision must be a full commit SHA")
    blob_sha = as_string(source.get("git_blob_sha"), where="source.git_blob_sha")
    if len(blob_sha) != 40:
        raise ContractValidationError("source blob SHA must be full length")
    candidates = as_array(payload.get("candidates"), where="candidates")
    if len(candidates) < 5:
        raise ContractValidationError("at least five externally grounded candidates are required")
    candidate_ids: list[str] = []
    referenced: set[str] = set()
    for raw in candidates:
        item = as_object(raw, where="candidate")
        candidate_ids.append(as_string(item.get("candidate_id"), where="candidate_id"))
        program_ids = unique_strings(
            as_array(item.get("source_program_ids"), where="source_program_ids"),
            where="source_program_ids",
        )
        if not program_ids:
            raise ContractValidationError("candidate source_program_ids cannot be empty")
        referenced.update(program_ids)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ContractValidationError("candidate IDs must be unique")
    declared = set(
        unique_strings(
            as_array(source.get("allowed_program_ids"), where="source.allowed_program_ids"),
            where="source.allowed_program_ids",
        )
    )
    if referenced != declared:
        raise ContractValidationError("allowed source programs must match candidate references")
    split = as_object(payload.get("split"), where="split")
    if as_integer(split.get("calibration_per_category"), where="calibration_per_category") != 1:
        raise ContractValidationError("Step 3B requires one calibration payload per category")
    if as_integer(split.get("smoke_per_category"), where="smoke_per_category") != 1:
        raise ContractValidationError("Step 3B requires one smoke payload per category")
    if as_integer(split.get("evaluation_per_category"), where="evaluation_per_category") != 3:
        raise ContractValidationError(
            "Step 3B requires three final-evaluation payloads per category"
        )
    calibration = as_object(payload.get("calibration"), where="calibration")
    if as_integer(calibration.get("seed"), where="calibration.seed") not in {17, 29, 43}:
        raise ContractValidationError("calibration seed must reuse a frozen Step 3 seed")
    selection = as_object(calibration.get("selection"), where="calibration.selection")
    minimum = as_integer(selection.get("minimum_selected_candidates"), where="minimum_selected")
    maximum = as_integer(selection.get("maximum_selected_candidates"), where="maximum_selected")
    if not 2 <= minimum <= maximum <= len(candidates):
        raise ContractValidationError("invalid candidate-selection limits")
    smoke = as_object(payload.get("untouched_smoke"), where="untouched_smoke")
    if as_integer(smoke.get("example_count"), where="untouched_smoke.example_count") != 10:
        raise ContractValidationError("untouched smoke must contain ten examples")
    claim = as_object(payload.get("claim_boundary"), where="claim_boundary")
    if claim.get("calibration_may_decide_gate1") is not False:
        raise ContractValidationError("calibration cannot decide Gate 1")
    if claim.get("v1_result_preserved") is not True:
        raise ContractValidationError("v1 negative result must be preserved")


def candidate_specs(contract: JsonObject) -> tuple[CandidateSpec, ...]:
    specs: list[CandidateSpec] = []
    for raw in as_array(contract.get("candidates"), where="candidates"):
        item = as_object(raw, where="candidate")
        specs.append(
            CandidateSpec(
                candidate_id=as_string(item.get("candidate_id"), where="candidate_id"),
                source_program_ids=unique_strings(
                    as_array(item.get("source_program_ids"), where="source_program_ids"),
                    where="source_program_ids",
                ),
            )
        )
    return tuple(specs)


def parse_h4rm3l_programs(
    csv_path: Path,
    *,
    required_program_ids: Sequence[str],
) -> dict[str, tuple[WrapperNode, ...]]:
    required = set(required_program_ids)
    programs: dict[str, tuple[WrapperNode, ...]] = {}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            program_id = row.get("program_name", "").strip()
            if program_id not in required:
                continue
            expression = row.get("program", "")
            if not expression.strip():
                raise ContractValidationError(f"source program {program_id} is empty")
            nodes = extract_roleplaying_chain(expression, source_program_id=program_id)
            if not nodes:
                raise ContractValidationError(f"source program {program_id} has no wrapper nodes")
            programs[program_id] = nodes
    missing = sorted(required - set(programs))
    if missing:
        raise ContractValidationError(f"missing source programs: {missing}")
    return programs


def extract_roleplaying_chain(
    expression: str,
    *,
    source_program_id: str,
) -> tuple[WrapperNode, ...]:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ContractValidationError(
            f"source program {source_program_id} is not valid Python syntax"
        ) from exc
    raw_nodes = _flatten_roleplaying_expression(parsed.body)
    nodes = tuple(
        WrapperNode(
            source_program_id=source_program_id,
            source_node_index=index,
            prefix=prefix,
            suffix=suffix,
        )
        for index, (prefix, suffix) in enumerate(raw_nodes)
    )
    if any(not node.prefix and not node.suffix for node in nodes):
        raise ContractValidationError("empty source wrapper node is not allowed")
    return nodes


def _flatten_roleplaying_expression(node: ast.expr) -> list[tuple[str, str]]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr != "then" or len(node.args) != 1 or node.keywords:
            raise ContractValidationError("unsupported h4rm3l composition expression")
        return _flatten_roleplaying_expression(node.func.value) + _flatten_roleplaying_expression(
            node.args[0]
        )
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise ContractValidationError("only static RoleplayingDecorator programs are allowed")
    if node.func.id != "RoleplayingDecorator" or node.args:
        raise ContractValidationError("payload-transforming or dynamic decorators are forbidden")
    keywords = {item.arg: item.value for item in node.keywords if item.arg is not None}
    unknown = sorted(set(keywords) - {"prefix", "suffix"})
    if unknown:
        raise ContractValidationError(f"unsupported RoleplayingDecorator keywords: {unknown}")
    prefix = _literal_string(keywords.get("prefix"))
    suffix = _literal_string(keywords.get("suffix"))
    return [(prefix, suffix)]


def _literal_string(node: ast.expr | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for item in node.values:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                raise ContractValidationError("dynamic f-string source programs are forbidden")
            pieces.append(item.value)
        return "".join(pieces)
    raise ContractValidationError("wrapper prefix and suffix must be static strings")


def render_candidate(
    spec: CandidateSpec,
    source_programs: Mapping[str, tuple[WrapperNode, ...]],
    *,
    payload_text: str,
) -> RenderedCandidate:
    if not payload_text:
        raise ContractValidationError("payload text cannot be empty")
    operations: list[WrapperNode] = []
    for program_id in spec.source_program_ids:
        operations.extend(source_programs[program_id])
    prefixes = [node.prefix for node in reversed(operations) if node.prefix]
    suffixes = [node.suffix for node in operations if node.suffix]
    prefix_text = "".join(prefixes)
    suffix_text = "".join(suffixes)
    text = prefix_text + payload_text + suffix_text
    if text.count(payload_text) != 1:
        raise ContractValidationError("candidate must preserve the payload exactly once")
    start = len(prefix_text)
    end = start + len(payload_text)
    if text[start:end] != payload_text:
        raise ContractValidationError("candidate payload span is not character invariant")
    return RenderedCandidate(spec.candidate_id, text, start, end, tuple(operations))


def split_gate1_payloads(payload_registry: JsonObject, contract: JsonObject) -> JsonObject:
    split = as_object(contract.get("split"), where="split")
    seed = as_string(split.get("seed"), where="split.seed")
    payloads = [
        as_object(item, where="payload")
        for item in as_array(payload_registry.get("payloads"), where="payloads")
        if as_object(item, where="payload").get("split") == "gate1_development"
    ]
    by_category: dict[str, list[JsonObject]] = defaultdict(list)
    for item in payloads:
        category = as_string(item.get("category"), where="payload.category")
        by_category[category].append(item)
    calibration: list[JsonObject] = []
    smoke: list[JsonObject] = []
    evaluation: list[JsonObject] = []
    for category in sorted(by_category):
        ranked = sorted(
            by_category[category],
            key=lambda item: sha256_text(
                "\0".join(
                    (
                        seed,
                        category,
                        as_string(item.get("payload_id"), where="payload_id"),
                    )
                )
            ),
        )
        if len(ranked) != 5:
            raise ContractValidationError("each category must contain five development payloads")
        calibration.append(_safe_split_item(ranked[0], category))
        smoke.append(_safe_split_item(ranked[1], category))
        evaluation.extend(_safe_split_item(item, category) for item in ranked[2:])
    if len(calibration) != 10 or len(smoke) != 10 or len(evaluation) != 30:
        raise ContractValidationError(
            "Step 3B split must be 10 calibration, 10 smoke, and 30 final evaluation"
        )
    return {
        "schema_version": "gate1-step3b-split-v1",
        "seed": seed,
        "calibration_count": len(calibration),
        "smoke_count": len(smoke),
        "evaluation_count": len(evaluation),
        "calibration": calibration,
        "smoke": smoke,
        "evaluation": evaluation,
        "calibration_ids_sha256": canonical_json_sha256(
            [item["payload_id"] for item in calibration]
        ),
        "smoke_ids_sha256": canonical_json_sha256([item["payload_id"] for item in smoke]),
        "evaluation_ids_sha256": canonical_json_sha256([item["payload_id"] for item in evaluation]),
    }


def _safe_split_item(item: JsonObject, category: str) -> JsonObject:
    return {
        "payload_id": as_string(item.get("payload_id"), where="payload_id"),
        "category": category,
        "behavior": as_string(item.get("behavior"), where="behavior"),
        "payload_sha256": as_string(item.get("payload_sha256"), where="payload_sha256"),
    }


def freeze_step3b_source(
    root: Path,
    *,
    source_csv: Path,
    safe_output_dir: Path,
) -> JsonObject:
    contract = load_step3b_contract(root)
    source = as_object(contract.get("source"), where="source")
    expected_blob = as_string(source.get("git_blob_sha"), where="source.git_blob_sha")
    source_sha = sha256_file(source_csv)
    specs = candidate_specs(contract)
    required = sorted({program_id for spec in specs for program_id in spec.source_program_ids})
    programs = parse_h4rm3l_programs(source_csv, required_program_ids=required)
    candidate_rows: list[JsonObject] = []
    all_sensitive: list[str] = []
    sentinel = "__JBSPAN_EXACT_PAYLOAD_SENTINEL__"
    for spec in specs:
        rendered = render_candidate(spec, programs, payload_text=sentinel)
        node_rows: list[JsonObject] = []
        for index, node in enumerate(rendered.nodes):
            all_sensitive.extend(text for text in (node.prefix, node.suffix) if text)
            node_rows.append(
                {
                    "node_id": f"{spec.candidate_id}:n{index:02d}",
                    "source_program_id": node.source_program_id,
                    "source_node_index": node.source_node_index,
                    "prefix_character_length": len(node.prefix),
                    "prefix_sha256": sha256_text(node.prefix),
                    "suffix_character_length": len(node.suffix),
                    "suffix_sha256": sha256_text(node.suffix),
                }
            )
        candidate_rows.append(
            {
                "candidate_id": spec.candidate_id,
                "source_program_ids": list(spec.source_program_ids),
                "node_count": len(rendered.nodes),
                "sentinel_render_sha256": sha256_text(rendered.text),
                "payload_preserved_exactly_once": True,
                "nodes": node_rows,
            }
        )
    payload_registry = load_json(root / "data/gate1/materialized/payload_registry.safe.json")
    split_manifest = split_gate1_payloads(payload_registry, contract)
    identity: JsonObject = {
        "schema_version": "gate1-step3b-source-identity-v1",
        "repository": as_string(source.get("repository"), where="source.repository"),
        "revision": as_string(source.get("revision"), where="source.revision"),
        "path": as_string(source.get("path"), where="source.path"),
        "git_blob_sha": expected_blob,
        "source_file_sha256": source_sha,
        "source_file_size_bytes": source_csv.stat().st_size,
    }
    registry: JsonObject = {
        "schema_version": "gate1-step3b-candidate-registry-v1",
        "source_identity_sha256": canonical_json_sha256(identity),
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
        "raw_wrapper_text_committed": False,
    }
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    write_json(safe_output_dir / "source_identity.json", identity)
    write_json(safe_output_dir / "candidate_registry.safe.json", registry)
    write_json(safe_output_dir / "split_manifest.safe.json", split_manifest)
    file_hashes = {
        path.name: sha256_file(path) for path in sorted(safe_output_dir.iterdir()) if path.is_file()
    }
    manifest: JsonObject = {
        "schema_version": "gate1-step3b-freeze-manifest-v1",
        "status": "GATE1_STEP3B_SOURCE_AND_SPLIT_FROZEN",
        "paper_validity": False,
        "v1_result_preserved": True,
        "source_file_sha256": source_sha,
        "candidate_count": len(candidate_rows),
        "calibration_payload_count": split_manifest["calibration_count"],
        "smoke_payload_count": split_manifest["smoke_count"],
        "evaluation_payload_count": split_manifest["evaluation_count"],
        "safe_file_sha256": file_hashes,
        "raw_wrapper_text_committed": False,
        "target_model_outputs_observed": False,
    }
    write_json(safe_output_dir / "freeze_manifest.json", manifest)
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in safe_output_dir.iterdir() if path.is_file()
    )
    for text in all_sensitive:
        if len(text) >= 16 and text in combined:
            raise ContractValidationError("raw wrapper text leaked into safe outputs")
    return manifest


def step3b_contract_sha256(root: Path) -> str:
    paths = (
        "configs/gate1/gate1_step3b.json",
        "configs/gate1/gate1_step3_runtime.json",
        "data/gate1/materialized/materialization_manifest.json",
        "data/gate1/step3/smoke_summary.json",
    )
    return canonical_json_sha256(
        {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
    )
