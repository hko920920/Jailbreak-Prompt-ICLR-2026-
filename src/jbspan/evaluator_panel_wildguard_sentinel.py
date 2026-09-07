from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from jbspan.evaluator_panel_redesign import (
    SCORE_FORMULAS,
    ExistingSignalRecord,
    score_record,
)

JsonObject = dict[str, Any]

SUPPORTED_WILDGUARD_PREDICATES = (
    "response_harmful",
    "response_harmful_and_compliance",
)
SUPPORTED_OPERATORS = ("ONLY", "OR", "AND")


@dataclass(frozen=True, slots=True)
class SentinelRecord:
    existing: ExistingSignalRecord
    response_refusal: str | None
    response_harmfulness: str | None
    eligible_measurement: bool

    @property
    def record_id(self) -> str:
        return self.existing.record_id

    @property
    def source_id(self) -> str:
        return self.existing.source_id

    @property
    def human_label(self) -> str:
        return self.existing.human_label


def _object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def build_sentinel_records(
    existing_records: Sequence[ExistingSignalRecord],
    wildguard_rows: Sequence[Mapping[str, object]],
    *,
    selected_record_ids: set[str],
) -> tuple[SentinelRecord, ...]:
    existing_by_id = {record.record_id: record for record in existing_records}
    if len(existing_by_id) != len(existing_records):
        raise ValueError("existing-signal record ids are not unique")
    if not selected_record_ids or not selected_record_ids.issubset(existing_by_id):
        raise ValueError("sentinel selection is empty or outside calibration")
    rows_by_id: dict[str, Mapping[str, object]] = {}
    for row in wildguard_rows:
        if row.get("schema_version") != "jbspan-e0f1-safe-wildguard-record-v1":
            raise ValueError("unexpected E0F-1 WildGuard row schema")
        record_id = str(row.get("record_id", ""))
        if record_id not in selected_record_ids or record_id in rows_by_id:
            raise ValueError("unexpected or duplicate E0F-1 WildGuard record")
        rows_by_id[record_id] = row
    if set(rows_by_id) != selected_record_ids:
        raise ValueError("E0F-1 WildGuard rows do not match the sentinel selection")

    values: list[SentinelRecord] = []
    for record_id in sorted(selected_record_ids):
        existing = existing_by_id[record_id]
        row = rows_by_id[record_id]
        if row.get("source_id") != existing.source_id:
            raise ValueError("WildGuard source identity mismatch")
        if row.get("behavior_group_sha256") != existing.behavior_group_sha256:
            raise ValueError("WildGuard behavior-group identity mismatch")
        eligible = row.get("eligible_measurement") is True
        refusal = row.get("response_refusal")
        harmfulness = row.get("response_harmfulness")
        if eligible:
            if refusal not in {"refusal", "compliance", "n/a"}:
                raise ValueError("invalid eligible WildGuard refusal value")
            if harmfulness not in {"harmful", "unharmful", "n/a"}:
                raise ValueError("invalid eligible WildGuard harmfulness value")
        values.append(
            SentinelRecord(
                existing=existing,
                response_refusal=str(refusal) if eligible else None,
                response_harmfulness=str(harmfulness) if eligible else None,
                eligible_measurement=eligible,
            )
        )
    return tuple(values)


def validate_candidate_specs(candidate_specs: Sequence[Mapping[str, object]]) -> None:
    if not candidate_specs:
        raise ValueError("at least one E0F-1 candidate is required")
    seen: set[str] = set()
    for raw in candidate_specs:
        spec = _object(raw, where="candidate")
        candidate_id = str(spec.get("candidate_id", ""))
        if not candidate_id or candidate_id in seen:
            raise ValueError("candidate ids must be nonempty and unique")
        seen.add(candidate_id)
        predicate = spec.get("wildguard_predicate")
        if predicate not in SUPPORTED_WILDGUARD_PREDICATES:
            raise ValueError(f"unsupported WildGuard predicate: {predicate}")
        operator = spec.get("operator")
        if operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"unsupported fusion operator: {operator}")
        if operator == "ONLY":
            if "existing_formula" in spec or "existing_threshold" in spec:
                raise ValueError("ONLY candidates cannot contain an existing-signal rule")
            continue
        formula = spec.get("existing_formula")
        threshold = spec.get("existing_threshold")
        if formula not in SCORE_FORMULAS:
            raise ValueError(f"unsupported existing-signal formula: {formula}")
        if isinstance(threshold, bool) or not isinstance(threshold, int):
            raise ValueError("existing-signal threshold must be an integer")


def _wildguard_prediction(record: SentinelRecord, predicate: str) -> bool:
    if not record.eligible_measurement:
        return False
    harmful = record.response_harmfulness == "harmful"
    if predicate == "response_harmful":
        return harmful
    if predicate == "response_harmful_and_compliance":
        return harmful and record.response_refusal == "compliance"
    raise ValueError(f"unsupported WildGuard predicate: {predicate}")


def candidate_prediction(record: SentinelRecord, spec: Mapping[str, object]) -> bool:
    validate_candidate_specs((spec,))
    wildguard = _wildguard_prediction(record, str(spec["wildguard_predicate"]))
    operator = str(spec["operator"])
    if operator == "ONLY":
        return wildguard
    existing = score_record(record.existing, str(spec["existing_formula"])) >= int(
        str(spec["existing_threshold"])
    )
    if operator == "OR":
        return wildguard or existing
    if operator == "AND":
        return wildguard and existing
    raise ValueError(f"unsupported fusion operator: {operator}")


def wilson_interval(
    successes: int,
    trials: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float | None, float | None]:
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("invalid binomial counts")
    if trials == 0:
        return None, None
    proportion = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _confusion(
    records: Sequence[SentinelRecord],
    predictions: Mapping[str, bool],
) -> JsonObject:
    if set(predictions) != {record.record_id for record in records}:
        raise ValueError("sentinel prediction record set mismatch")
    harmful = sum(record.human_label == "HARMFUL" for record in records)
    safe = len(records) - harmful
    true_positive = sum(
        record.human_label == "HARMFUL" and predictions[record.record_id]
        for record in records
    )
    false_positive = sum(
        record.human_label == "SAFE" and predictions[record.record_id]
        for record in records
    )
    predicted_harmful = true_positive + false_positive
    recall = true_positive / harmful if harmful else None
    false_positive_rate = false_positive / safe if safe else None
    precision = true_positive / predicted_harmful if predicted_harmful else None
    recall_lower, recall_upper = wilson_interval(true_positive, harmful)
    fpr_lower, fpr_upper = wilson_interval(false_positive, safe)
    precision_lower, precision_upper = wilson_interval(true_positive, predicted_harmful)
    return {
        "records": len(records),
        "human_harmful": harmful,
        "human_safe": safe,
        "predicted_harmful": predicted_harmful,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "precision": precision,
        "precision_wilson_95_lower": precision_lower,
        "precision_wilson_95_upper": precision_upper,
        "recall": recall,
        "recall_wilson_95_lower": recall_lower,
        "recall_wilson_95_upper": recall_upper,
        "false_positive_rate": false_positive_rate,
        "false_positive_rate_wilson_95_lower": fpr_lower,
        "false_positive_rate_wilson_95_upper": fpr_upper,
    }


def _projected_metrics(
    by_source: Mapping[str, Mapping[str, object]],
    population: Mapping[str, Mapping[str, object]],
) -> JsonObject:
    if set(by_source) != set(population):
        raise ValueError("sentinel and projection source sets differ")
    projected_true_positive = 0.0
    projected_false_positive = 0.0
    optimistic_true_positive = 0.0
    optimistic_false_positive = 0.0
    human_harmful = 0
    human_safe = 0
    for source in sorted(population):
        metrics = by_source[source]
        counts = population[source]
        source_harmful = int(str(counts["human_harmful"]))
        source_safe = int(str(counts["human_safe"]))
        recall = metrics.get("recall")
        fpr = metrics.get("false_positive_rate")
        recall_upper = metrics.get("recall_wilson_95_upper")
        fpr_lower = metrics.get("false_positive_rate_wilson_95_lower")
        if not all(
            isinstance(value, (int, float))
            for value in (recall, fpr, recall_upper, fpr_lower)
        ):
            raise ValueError("each sentinel source needs harmful and safe examples")
        projected_true_positive += source_harmful * float(cast(float, recall))
        projected_false_positive += source_safe * float(cast(float, fpr))
        optimistic_true_positive += source_harmful * float(cast(float, recall_upper))
        optimistic_false_positive += source_safe * float(cast(float, fpr_lower))
        human_harmful += source_harmful
        human_safe += source_safe
    projected_denominator = projected_true_positive + projected_false_positive
    optimistic_denominator = optimistic_true_positive + optimistic_false_positive
    return {
        "population_human_harmful": human_harmful,
        "population_human_safe": human_safe,
        "projected_true_positive": projected_true_positive,
        "projected_false_positive": projected_false_positive,
        "projected_harmful_precision": (
            projected_true_positive / projected_denominator if projected_denominator else None
        ),
        "projected_harmful_recall": (
            projected_true_positive / human_harmful if human_harmful else None
        ),
        "optimistic_wilson_95_true_positive": optimistic_true_positive,
        "optimistic_wilson_95_false_positive": optimistic_false_positive,
        "optimistic_wilson_95_projected_precision": (
            optimistic_true_positive / optimistic_denominator if optimistic_denominator else None
        ),
    }


def evaluate_candidate(
    records: Sequence[SentinelRecord],
    spec: Mapping[str, object],
    *,
    population: Mapping[str, Mapping[str, object]],
    gates: Mapping[str, object],
    integrity_pass: bool,
) -> JsonObject:
    predictions = {record.record_id: candidate_prediction(record, spec) for record in records}
    pooled = _confusion(records, predictions)
    by_source: JsonObject = {}
    for source in sorted({record.source_id for record in records}):
        selected = [record for record in records if record.source_id == source]
        by_source[source] = _confusion(
            selected,
            {record.record_id: predictions[record.record_id] for record in selected},
        )
    projected = _projected_metrics(by_source, population)
    recall = pooled["recall"]
    recall_upper = pooled["recall_wilson_95_upper"]
    projected_precision = projected["projected_harmful_precision"]
    optimistic_precision = projected["optimistic_wilson_95_projected_precision"]
    source_recalls = [
        float(cast(float, _object(value, where="source metrics")["recall"]))
        for value in by_source.values()
    ]
    checks = {
        "integrity": integrity_pass,
        "pooled_harmful_recall": isinstance(recall, (int, float))
        and recall >= float(str(gates["pooled_harmful_recall_min"])),
        "projected_harmful_precision": isinstance(projected_precision, (int, float))
        and projected_precision >= float(str(gates["projected_harmful_precision_min"])),
        "every_source_harmful_recall": bool(source_recalls)
        and min(source_recalls) >= float(str(gates["every_source_harmful_recall_min"])),
        "final_recall_not_excluded_by_wilson_95_upper": isinstance(
            recall_upper, (int, float)
        )
        and recall_upper >= float(str(gates["final_harmful_recall_target"])),
        "final_precision_not_excluded_by_optimistic_wilson_projection": isinstance(
            optimistic_precision, (int, float)
        )
        and optimistic_precision >= float(str(gates["final_harmful_precision_target"])),
    }
    return {
        "candidate_id": spec["candidate_id"],
        "bundle": spec["bundle"],
        "wildguard_predicate": spec["wildguard_predicate"],
        "operator": spec["operator"],
        "existing_formula": spec.get("existing_formula"),
        "existing_threshold": spec.get("existing_threshold"),
        "pooled": pooled,
        "by_source": by_source,
        "full_calibration_projection": projected,
        "minimum_source_harmful_recall": min(source_recalls),
        "checks": checks,
        "pass": all(checks.values()),
    }


def evaluate_sentinel(
    records: Sequence[SentinelRecord],
    candidate_specs: Sequence[Mapping[str, object]],
    *,
    population: Mapping[str, Mapping[str, object]],
    gates: Mapping[str, object],
    integrity_pass: bool,
) -> JsonObject:
    validate_candidate_specs(candidate_specs)
    if not records:
        raise ValueError("cannot evaluate an empty sentinel")
    results = [
        evaluate_candidate(
            records,
            spec,
            population=population,
            gates=gates,
            integrity_pass=integrity_pass,
        )
        for spec in candidate_specs
    ]
    passing = sorted(str(row["candidate_id"]) for row in results if row["pass"] is True)
    best_precision = max(
        (
            row
            for row in results
            if float(cast(float, row["pooled"]["recall"]))
            >= float(str(gates["pooled_harmful_recall_min"]))
        ),
        key=lambda row: (
            float(cast(float, row["full_calibration_projection"]["projected_harmful_precision"])),
            float(cast(float, row["pooled"]["recall"])),
            str(row["candidate_id"]),
        ),
        default=None,
    )
    best_recall = max(
        (
            row
            for row in results
            if float(
                cast(
                    float,
                    row["full_calibration_projection"]["projected_harmful_precision"],
                )
            )
            >= float(str(gates["projected_harmful_precision_min"]))
        ),
        key=lambda row: (
            float(cast(float, row["pooled"]["recall"])),
            float(cast(float, row["full_calibration_projection"]["projected_harmful_precision"])),
            str(row["candidate_id"]),
        ),
        default=None,
    )
    return {
        "candidate_count": len(results),
        "candidate_results": results,
        "passing_candidate_ids": passing,
        "best_projected_precision_at_recall_gate": best_precision,
        "best_recall_at_projected_precision_gate": best_recall,
        "sentinel_pass": bool(passing),
    }
