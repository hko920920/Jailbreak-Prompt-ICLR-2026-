from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from jbspan.natural_language_feasibility import (
    HumanResponseLabel,
    JsonObject,
    canonical_json_sha256,
    load_json_object,
    validate_feasibility_contract,
)


@dataclass(frozen=True)
class AnnotationRecord:
    annotation_id: str
    label: HumanResponseLabel
    confidence: str
    notes: str


@dataclass(frozen=True)
class ReliabilityResult:
    item_count: int
    agreement_count: int
    raw_agreement: float
    expected_agreement: float
    cohen_kappa: float
    cohen_kappa_defined: bool
    disagreement_count: int
    uncertain_union_count: int
    adjudication_required_count: int
    adjudication_ids: tuple[str, ...]
    annotator_a_label_counts: Mapping[str, int]
    annotator_b_label_counts: Mapping[str, int]

    def to_safe_dict(self) -> JsonObject:
        result = dict(asdict(self))
        result.pop("adjudication_ids")
        return result


def _object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _string(value: object, *, where: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ValueError(f"{where} must be {qualifier}")
    return value


def _number(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be numeric")
    return float(value)


def _load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path} contains no annotation rows")
    return rows


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_packet_rows(path: Path) -> dict[str, JsonObject]:
    packet: dict[str, JsonObject] = {}
    for row in _load_jsonl(path):
        annotation_id = _string(row.get("annotation_id"), where="annotation_id")
        if annotation_id in packet:
            raise ValueError(f"duplicate annotation_id in packet: {annotation_id}")
        _string(row.get("original_harmful_goal"), where="original_harmful_goal")
        _string(row.get("model_response"), where="model_response", allow_empty=True)
        packet[annotation_id] = row
    return packet


def load_annotation_records(
    path: Path,
    *,
    expected_ids: set[str],
    require_complete: bool = True,
) -> dict[str, AnnotationRecord]:
    records: dict[str, AnnotationRecord] = {}
    for row in _load_jsonl(path):
        annotation_id = _string(row.get("annotation_id"), where="annotation_id")
        if annotation_id in records:
            raise ValueError(f"duplicate annotation_id in {path}: {annotation_id}")
        raw_label = _string(
            row.get("label"),
            where=f"{annotation_id}.label",
            allow_empty=not require_complete,
        )
        if not raw_label and not require_complete:
            continue
        try:
            label = HumanResponseLabel(raw_label)
        except ValueError as exc:
            raise ValueError(f"unknown label for {annotation_id}: {raw_label}") from exc
        confidence = _string(
            row.get("confidence", ""),
            where=f"{annotation_id}.confidence",
            allow_empty=True,
        )
        notes = _string(
            row.get("notes", ""),
            where=f"{annotation_id}.notes",
            allow_empty=True,
        )
        records[annotation_id] = AnnotationRecord(
            annotation_id=annotation_id,
            label=label,
            confidence=confidence,
            notes=notes,
        )

    observed_ids = set(records)
    if require_complete and observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise ValueError(f"annotation ID mismatch in {path}: missing={missing}, extra={extra}")
    if not observed_ids.issubset(expected_ids):
        raise ValueError(f"{path} contains annotation IDs outside the frozen packet")
    return records


def calculate_nominal_reliability(
    annotator_a: Mapping[str, AnnotationRecord],
    annotator_b: Mapping[str, AnnotationRecord],
) -> ReliabilityResult:
    if set(annotator_a) != set(annotator_b):
        raise ValueError("the two primary annotation ID sets differ")
    annotation_ids = sorted(annotator_a)
    if not annotation_ids:
        raise ValueError("reliability requires at least one annotation")

    labels_a = [annotator_a[item].label for item in annotation_ids]
    labels_b = [annotator_b[item].label for item in annotation_ids]
    agreement_count = sum(left == right for left, right in zip(labels_a, labels_b, strict=True))
    item_count = len(annotation_ids)
    raw_agreement = agreement_count / item_count

    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    expected_agreement = sum(
        (counts_a[label] / item_count) * (counts_b[label] / item_count)
        for label in HumanResponseLabel
    )
    denominator = 1.0 - expected_agreement
    cohen_kappa_defined = denominator > 1e-12
    cohen_kappa = (
        (raw_agreement - expected_agreement) / denominator
        if cohen_kappa_defined
        else 0.0
    )

    uncertain = HumanResponseLabel.UNCERTAIN
    disagreement_ids = {
        item
        for item in annotation_ids
        if annotator_a[item].label != annotator_b[item].label
    }
    uncertain_ids = {
        item
        for item in annotation_ids
        if annotator_a[item].label is uncertain or annotator_b[item].label is uncertain
    }
    adjudication_ids = tuple(sorted(disagreement_ids | uncertain_ids))

    return ReliabilityResult(
        item_count=item_count,
        agreement_count=agreement_count,
        raw_agreement=raw_agreement,
        expected_agreement=expected_agreement,
        cohen_kappa=cohen_kappa,
        cohen_kappa_defined=cohen_kappa_defined,
        disagreement_count=len(disagreement_ids),
        uncertain_union_count=len(uncertain_ids),
        adjudication_required_count=len(adjudication_ids),
        adjudication_ids=adjudication_ids,
        annotator_a_label_counts={label.value: counts_a[label] for label in HumanResponseLabel},
        annotator_b_label_counts={label.value: counts_b[label] for label in HumanResponseLabel},
    )


def _load_key_rows(path: Path, *, expected_ids: set[str]) -> dict[str, JsonObject]:
    key_rows: dict[str, JsonObject] = {}
    for row in _load_jsonl(path):
        annotation_id = _string(row.get("annotation_id"), where="key.annotation_id")
        if annotation_id in key_rows:
            raise ValueError(f"duplicate annotation_id in annotation key: {annotation_id}")
        _string(row.get("item_id"), where=f"{annotation_id}.item_id")
        key_rows[annotation_id] = row
    if set(key_rows) != expected_ids:
        raise ValueError("annotation key does not match the frozen packet")
    return key_rows


def _calibration_thresholds(contract: JsonObject) -> tuple[float, float, str]:
    measurement = _object(contract.get("human_measurement"), where="human_measurement")
    calibration = _object(measurement.get("calibration_gate"), where="calibration_gate")
    minimum_agreement = _number(
        calibration.get("minimum_raw_agreement"),
        where="minimum_raw_agreement",
    )
    minimum_kappa = _number(
        calibration.get("minimum_cohen_kappa"),
        where="minimum_cohen_kappa",
    )
    failure_action = _string(calibration.get("failure_action"), where="failure_action")
    return minimum_agreement, minimum_kappa, failure_action


def _build_adjudication_queue(
    packet: Mapping[str, JsonObject],
    annotator_a: Mapping[str, AnnotationRecord],
    annotator_b: Mapping[str, AnnotationRecord],
    adjudication_ids: Sequence[str],
) -> list[JsonObject]:
    queue: list[JsonObject] = []
    for annotation_id in adjudication_ids:
        source = packet[annotation_id]
        left = annotator_a[annotation_id]
        right = annotator_b[annotation_id]
        queue.append(
            {
                "annotation_id": annotation_id,
                "original_harmful_goal": source.get("original_harmful_goal"),
                "model_response": source.get("model_response"),
                "annotator_a_label": left.label.value,
                "annotator_a_confidence": left.confidence,
                "annotator_a_notes": left.notes,
                "annotator_b_label": right.label.value,
                "annotator_b_confidence": right.confidence,
                "annotator_b_notes": right.notes,
                "label": "",
                "confidence": "",
                "notes": "",
            }
        )
    return queue


def score_calibration_annotations(
    *,
    contract_path: Path,
    packet_summary_path: Path,
    annotation_packet_path: Path,
    annotation_key_path: Path,
    annotator_a_path: Path,
    annotator_b_path: Path,
    safe_output_path: Path,
    private_output_dir: Path,
    adjudicator_path: Path | None = None,
) -> JsonObject:
    contract = load_json_object(contract_path)
    validate_feasibility_contract(contract)
    packet_summary = load_json_object(packet_summary_path)
    if packet_summary.get("status") != "NATURAL_LANGUAGE_CALIBRATION_PACKET_READY":
        raise ValueError("calibration packet summary is not ready")
    if packet_summary.get("contract_identity_sha256") != contract.get(
        "contract_identity_sha256"
    ):
        raise ValueError("packet summary points to a different contract")
    if packet_summary.get("decision_packet_opened") is not False:
        raise ValueError("decision packet must remain unopened during calibration")

    packet = load_packet_rows(annotation_packet_path)
    expected_ids = set(packet)
    if len(expected_ids) != 30:
        raise ValueError("calibration packet must contain exactly thirty items")
    expected_identity = _string(
        packet_summary.get("annotation_ids_sha256"),
        where="annotation_ids_sha256",
    )
    if canonical_json_sha256(sorted(expected_ids)) != expected_identity:
        raise ValueError("annotation ID commitment mismatch")

    key_rows = _load_key_rows(annotation_key_path, expected_ids=expected_ids)
    annotator_a = load_annotation_records(annotator_a_path, expected_ids=expected_ids)
    annotator_b = load_annotation_records(annotator_b_path, expected_ids=expected_ids)
    reliability = calculate_nominal_reliability(annotator_a, annotator_b)

    minimum_agreement, minimum_kappa, failure_action = _calibration_thresholds(contract)
    reliability_pass = (
        reliability.cohen_kappa_defined
        and reliability.raw_agreement >= minimum_agreement
        and reliability.cohen_kappa >= minimum_kappa
    )

    private_output_dir.mkdir(parents=True, exist_ok=True)
    queue = _build_adjudication_queue(
        packet,
        annotator_a,
        annotator_b,
        reliability.adjudication_ids,
    )
    queue_path = private_output_dir / "adjudication_queue.private.jsonl"
    _write_jsonl(queue_path, queue)

    adjudication_complete = not queue
    resolved_rows: list[JsonObject] = []
    if adjudicator_path is not None:
        adjudicator: dict[str, AnnotationRecord] = load_annotation_records(
            adjudicator_path,
            expected_ids=set(reliability.adjudication_ids),
        )
        if any(record.label is HumanResponseLabel.UNCERTAIN for record in adjudicator.values()):
            raise ValueError("adjudicator labels must resolve UNCERTAIN")
        adjudication_complete = True
    else:
        adjudicator = {}

    for annotation_id in sorted(expected_ids):
        left = annotator_a[annotation_id]
        if annotation_id in reliability.adjudication_ids:
            final_label = adjudicator.get(annotation_id)
            if final_label is None:
                continue
            label = final_label.label
            resolution = "adjudicator"
        else:
            label = left.label
            resolution = "primary_agreement"
        key = key_rows[annotation_id]
        resolved_rows.append(
            {
                "annotation_id": annotation_id,
                "item_id": key.get("item_id"),
                "payload_id": key.get("payload_id"),
                "candidate_id": key.get("candidate_id"),
                "condition": key.get("condition"),
                "category": key.get("category"),
                "seed": key.get("seed"),
                "label": label.value,
                "resolution": resolution,
            }
        )

    if adjudication_complete and len(resolved_rows) != len(expected_ids):
        raise ValueError("adjudication was marked complete but resolved labels are incomplete")
    resolved_path = private_output_dir / "resolved_labels.private.jsonl"
    _write_jsonl(resolved_path, resolved_rows)

    if not reliability_pass:
        status = "NATURAL_LANGUAGE_CALIBRATION_RELIABILITY_FAIL"
        next_operation = failure_action
    elif not adjudication_complete:
        status = "NATURAL_LANGUAGE_CALIBRATION_RELIABILITY_PASS_ADJUDICATION_REQUIRED"
        next_operation = "COMPLETE_CALIBRATION_ADJUDICATION"
    else:
        status = "NATURAL_LANGUAGE_CALIBRATION_GATE_PASS"
        next_operation = "GENERATE_ENCRYPTED_STAGE_A_DECISION_PACKET"

    safe_summary: JsonObject = {
        "schema_version": "natural-language-calibration-reliability-v1",
        "status": status,
        "paper_validity": False,
        "contract_identity_sha256": contract.get("contract_identity_sha256"),
        "packet_response_set_sha256": packet_summary.get("response_set_sha256"),
        "packet_annotation_ids_sha256": expected_identity,
        **reliability.to_safe_dict(),
        "minimum_raw_agreement": minimum_agreement,
        "minimum_cohen_kappa": minimum_kappa,
        "reliability_pass": reliability_pass,
        "adjudication_complete": adjudication_complete,
        "resolved_label_count": len(resolved_rows),
        "annotator_a_file_sha256": sha256_file(annotator_a_path),
        "annotator_b_file_sha256": sha256_file(annotator_b_path),
        "adjudicator_file_sha256": (
            sha256_file(adjudicator_path) if adjudicator_path is not None else None
        ),
        "adjudication_queue_sha256": sha256_file(queue_path),
        "resolved_labels_sha256": sha256_file(resolved_path),
        "next_operation": next_operation,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "item_level_labels_committed": False,
        "decision_packet_opened": False,
        "gate1_evaluation_30_opened": False,
        "gate2_heldout_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    _write_json(safe_output_path, safe_summary)
    return safe_summary
