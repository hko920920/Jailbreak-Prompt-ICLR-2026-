from __future__ import annotations

import argparse
import hashlib
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
for import_root in (PROJECT_ROOT, SOURCE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import run_evaluator_panel_wildguard_e0f2 as e0f2  # noqa: E402

from jbspan.evaluator_panel_redesign import (  # noqa: E402
    SCORE_FORMULAS,
    ExistingSignalRecord,
    canonical_json_bytes,
    score_record,
)
from jbspan.evaluator_panel_wildguard_sentinel import (  # noqa: E402
    SentinelRecord,
    build_sentinel_records,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f2-failure-audit-contract-v1"
EXPECTED_STATUS = "FROZEN_POST_OUTCOME_ZERO_INFERENCE_DIAGNOSTIC_CONTRACT"
EXPECTED_RECORDS = 300
EXPECTED_FOLDS = 5


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    family: str
    atoms: tuple[str, ...]
    complexity: int
    prediction_bits: int


@dataclass(frozen=True, slots=True)
class CandidateUniverse:
    candidates: tuple[Candidate, ...]
    atomic_count: int
    numeric_atomic_count: int
    raw_expression_count: int
    unique_prediction_vector_count: int
    specification_sha256: str
    prediction_commitment_sha256: str


@dataclass(frozen=True, slots=True)
class Masks:
    all_records: int
    human_harmful: int
    human_safe: int
    safe_base: int
    by_source: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class CompactMetrics:
    harmful_precision: float | None
    harmful_recall: float | None
    projected_harmful_precision: float | None
    minimum_source_harmful_recall: float | None
    safe_precision: float | None
    projected_safe_precision: float | None
    safe_precision_wilson_lower: float | None
    decided_coverage: float
    predicted_harmful: int
    predicted_safe: int
    harmful_recall_wilson_upper: float | None
    optimistic_projected_harmful_precision: float | None
    failed_checks: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failed_checks


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("preflight", "run"))
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/e0f2_failure_audit_v1_1.json"),
    )
    value.add_argument("--confirm-reviewed-zero-inference-audit", action="store_true")
    return value


def _object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def _objects(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list):
        raise TypeError(f"{where} must be an array")
    return [_object(item, where=f"{where} item") for item in value]


def _strings(value: object, *, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return tuple(cast(list[str], value))


def _rooted(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("configured path must be a nonempty string")
    return (root / value).resolve()


def _dependency_path(root: Path, contract: Mapping[str, object], name: str) -> Path:
    dependencies = _object(contract["dependencies"], where="dependencies")
    spec = _object(dependencies[name], where=f"dependencies.{name}")
    return e0f2.base.verify_file(root, spec, label=f"failure-audit {name}")


def validate_contract(root: Path, config_path: Path) -> JsonObject:
    contract = e0f2.base.load_object(config_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-2 failure-audit schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-2 failure-audit contract is not frozen")
    if _rooted(root, contract["contract_path"]) != config_path.resolve():
        raise ValueError("failure-audit contract self-path mismatch")
    if contract.get("new_model_inference_authorized") is not False:
        raise ValueError("failure audit must prohibit model inference")
    if int(str(contract.get("development_records"))) != EXPECTED_RECORDS:
        raise ValueError("failure audit must use exactly 300 development records")

    implementation = _object(contract["implementation"], where="implementation")
    runner_path = e0f2.base.verify_file(
        root, implementation["runner"], label="failure-audit runner"
    )
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected failure-audit runner path")
    for name in ("e0f2_runner", "redesign_module", "sentinel_module"):
        e0f2.base.verify_file(root, implementation[name], label=name)
    for name in _object(contract["dependencies"], where="dependencies"):
        _dependency_path(root, contract, name)

    family = _object(contract["candidate_family"], where="candidate family")
    formulas = _strings(family["score_formulas"], where="score formulas")
    if formulas != tuple(SCORE_FORMULAS):
        raise ValueError("failure audit must use the complete inherited score-formula order")
    if _strings(family["wildguard_atoms"], where="WildGuard atoms") != (
        "response_harmful",
        "response_compliance",
        "response_harmful_and_compliance",
    ):
        raise ValueError("unexpected WildGuard atomic family")
    if family.get("source_as_prediction_feature") is not False:
        raise ValueError("source must not be a prediction feature")
    if family.get("human_label_as_prediction_feature") is not False:
        raise ValueError("human label must not be a prediction feature")

    protected = _object(contract["protected_boundary"], where="protected boundary")
    if any(protected.get(name) is not False for name in protected):
        raise ValueError("all failure-audit protected boundaries must remain false")
    return contract


def load_inputs(
    root: Path, contract: Mapping[str, object]
) -> tuple[
    JsonObject,
    tuple[ExistingSignalRecord, ...],
    tuple[SentinelRecord, ...],
    dict[str, int],
]:
    e0f2_contract_path = _dependency_path(root, contract, "e0f2_contract")
    _, base_contract, _, _ = e0f2.validate_contract(root, e0f2_contract_path)
    existing = e0f2.base.load_existing_records(root, base_contract)

    result = e0f2.base.load_object(_dependency_path(root, contract, "e0f2_result"))
    e0f2.base.verify_result_identity(result, label="E0F-2 terminal result")
    result_spec = _object(
        _object(contract["dependencies"], where="dependencies")["e0f2_result"],
        where="E0F-2 result dependency",
    )
    if result.get("result_identity_sha256") != result_spec.get("result_identity_sha256"):
        raise ValueError("E0F-2 result identity differs from the diagnostic freeze")
    if result.get("status") != "E0F2_PROSPECTIVE_FAIL_STOP_EXACT_PANEL_PATH":
        raise ValueError("failure audit requires the terminal E0F-2 scientific failure")
    if any(
        result.get(name) is not False for name in ("heldout_opened", "p3_opened", "topology_opened")
    ):
        raise ValueError("a protected boundary was opened before the failure audit")

    rows = e0f2.base.load_jsonl(_dependency_path(root, contract, "e0f2_cumulative_axis"))
    if e0f2.base.integrity_summary(rows, EXPECTED_RECORDS)["pass"] is not True:
        raise ValueError("cumulative 300 axis fails integrity")
    record_ids = {str(row["record_id"]) for row in rows}
    records = build_sentinel_records(existing, rows, selected_record_ids=record_ids)
    if len(records) != EXPECTED_RECORDS:
        raise ValueError("failure audit record count mismatch")

    fold_rows = e0f2.base.load_jsonl(_dependency_path(root, contract, "fold_manifest"))
    folds_all = {str(row["record_id"]): int(str(row["outer_fold"])) for row in fold_rows}
    folds = {record.record_id: folds_all[record.record_id] for record in records}
    if set(folds.values()) != set(range(EXPECTED_FOLDS)):
        raise ValueError("failure audit does not contain all five frozen folds")
    group_folds: dict[str, set[int]] = {}
    for record in records:
        group_folds.setdefault(record.existing.behavior_group_sha256, set()).add(
            folds[record.record_id]
        )
    if any(len(values) != 1 for values in group_folds.values()):
        raise ValueError("a behavior group crosses frozen folds")
    return base_contract, existing, records, folds


def _numeric_value(record: ExistingSignalRecord, feature: str) -> int:
    if feature.startswith("formula:"):
        return score_record(record, feature.removeprefix("formula:"))
    if feature.startswith("axis:"):
        value = getattr(record, feature.removeprefix("axis:"))
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"numeric axis is not an integer: {feature}")
        return value
    raise ValueError(f"unsupported numeric feature: {feature}")


def _bits(values: Sequence[bool]) -> int:
    result = 0
    for index, value in enumerate(values):
        if value:
            result |= 1 << index
    return result


def build_candidate_universe(
    all_existing: Sequence[ExistingSignalRecord],
    records: Sequence[SentinelRecord],
    family: Mapping[str, object],
) -> CandidateUniverse:
    formulas = _strings(family["score_formulas"], where="score formulas")
    raw_axes = _strings(family["raw_numeric_axes"], where="raw numeric axes")
    numeric_features = tuple(f"formula:{name}" for name in formulas) + tuple(
        f"axis:{name}" for name in raw_axes
    )
    existing_by_id = {record.record_id: record for record in all_existing}
    ordered_existing = [record.existing for record in records]

    numeric_atoms: list[Candidate] = []
    for feature in numeric_features:
        thresholds = sorted({_numeric_value(record, feature) for record in all_existing})
        for threshold in thresholds:
            atom_id = f"{feature}>={threshold}"
            prediction_bits = _bits(
                [_numeric_value(record, feature) >= threshold for record in ordered_existing]
            )
            numeric_atoms.append(Candidate(atom_id, "NUMERIC_ATOM", (atom_id,), 1, prediction_bits))

    wg_values: dict[str, list[bool]] = {
        "wg:response_harmful": [
            record.eligible_measurement and record.response_harmfulness == "harmful"
            for record in records
        ],
        "wg:response_compliance": [
            record.eligible_measurement and record.response_refusal == "compliance"
            for record in records
        ],
        "wg:response_harmful_and_compliance": [
            record.eligible_measurement
            and record.response_harmfulness == "harmful"
            and record.response_refusal == "compliance"
            for record in records
        ],
    }
    wg_atoms = [
        Candidate(name, "WILDGUARD_ATOM", (name,), 1, _bits(values))
        for name, values in sorted(wg_values.items())
    ]
    all_atoms = sorted((*numeric_atoms, *wg_atoms), key=lambda candidate: candidate.candidate_id)
    numeric_atoms.sort(key=lambda candidate: candidate.candidate_id)

    by_vector: dict[int, Candidate] = {}
    raw_expression_count = 0

    def register(candidate: Candidate) -> None:
        nonlocal raw_expression_count
        raw_expression_count += 1
        previous = by_vector.get(candidate.prediction_bits)
        preference = (candidate.complexity, candidate.candidate_id)
        if previous is None or preference < (previous.complexity, previous.candidate_id):
            by_vector[candidate.prediction_bits] = candidate

    for atom in all_atoms:
        register(atom)
    for left, right in combinations(all_atoms, 2):
        atom_ids = (left.candidate_id, right.candidate_id)
        register(
            Candidate(
                f"AND({atom_ids[0]},{atom_ids[1]})",
                "PAIR_AND",
                atom_ids,
                2,
                left.prediction_bits & right.prediction_bits,
            )
        )
        register(
            Candidate(
                f"OR({atom_ids[0]},{atom_ids[1]})",
                "PAIR_OR",
                atom_ids,
                2,
                left.prediction_bits | right.prediction_bits,
            )
        )

    wg_harmful = next(
        candidate for candidate in wg_atoms if candidate.candidate_id == "wg:response_harmful"
    )
    for left, right in combinations(numeric_atoms, 2):
        atom_ids = (wg_harmful.candidate_id, left.candidate_id, right.candidate_id)
        register(
            Candidate(
                f"OR({atom_ids[0]},AND({atom_ids[1]},{atom_ids[2]}))",
                "WG_OR_NUMERIC_PAIR_AND",
                atom_ids,
                3,
                wg_harmful.prediction_bits | (left.prediction_bits & right.prediction_bits),
            )
        )
        register(
            Candidate(
                f"AND({atom_ids[0]},OR({atom_ids[1]},{atom_ids[2]}))",
                "WG_AND_NUMERIC_PAIR_OR",
                atom_ids,
                3,
                wg_harmful.prediction_bits & (left.prediction_bits | right.prediction_bits),
            )
        )

    candidates = tuple(sorted(by_vector.values(), key=lambda candidate: candidate.candidate_id))
    specs = [
        {
            "candidate_id": candidate.candidate_id,
            "family": candidate.family,
            "atoms": list(candidate.atoms),
            "complexity": candidate.complexity,
        }
        for candidate in candidates
    ]
    prediction_hash = hashlib.sha256()
    width = max(1, (len(records) + 7) // 8)
    for candidate in candidates:
        prediction_hash.update(candidate.candidate_id.encode("utf-8"))
        prediction_hash.update(b"\0")
        prediction_hash.update(candidate.prediction_bits.to_bytes(width, "little"))
        prediction_hash.update(b"\n")
    if set(existing_by_id) != {record.record_id for record in all_existing}:
        raise ValueError("existing record ids are not unique")
    return CandidateUniverse(
        candidates=candidates,
        atomic_count=len(all_atoms),
        numeric_atomic_count=len(numeric_atoms),
        raw_expression_count=raw_expression_count,
        unique_prediction_vector_count=len(candidates),
        specification_sha256=hashlib.sha256(canonical_json_bytes(specs)).hexdigest(),
        prediction_commitment_sha256=prediction_hash.hexdigest(),
    )


def build_masks(records: Sequence[SentinelRecord]) -> Masks:
    all_records = (1 << len(records)) - 1
    harmful = _bits([record.human_label == "HARMFUL" for record in records])
    safe = all_records ^ harmful
    safe_base = _bits(
        [
            record.eligible_measurement
            and record.response_harmfulness == "unharmful"
            and record.response_refusal == "refusal"
            for record in records
        ]
    )
    by_source = {
        source: _bits([record.source_id == source for record in records])
        for source in sorted({record.source_id for record in records})
    }
    return Masks(all_records, harmful, safe, safe_base, by_source)


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _wilson(successes: int, trials: int) -> tuple[float | None, float | None]:
    if trials == 0:
        return None, None
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _number(value: float | None, *, default: float = -1.0) -> float:
    return default if value is None else value


def _counts(prediction_bits: int, subset: int, masks: Masks) -> JsonObject:
    selected = subset & masks.all_records
    harmful_predictions = prediction_bits & selected
    safe_predictions = masks.safe_base & ~prediction_bits & selected
    human_harmful = (masks.human_harmful & selected).bit_count()
    human_safe = (masks.human_safe & selected).bit_count()
    harmful_tp = (harmful_predictions & masks.human_harmful).bit_count()
    harmful_fp = (harmful_predictions & masks.human_safe).bit_count()
    safe_tp = (safe_predictions & masks.human_safe).bit_count()
    safe_fp = (safe_predictions & masks.human_harmful).bit_count()
    predicted_harmful = harmful_tp + harmful_fp
    predicted_safe = safe_tp + safe_fp
    decided = predicted_harmful + predicted_safe
    return {
        "records": selected.bit_count(),
        "human_harmful": human_harmful,
        "human_safe": human_safe,
        "harmful_true_positive": harmful_tp,
        "harmful_false_positive": harmful_fp,
        "predicted_harmful": predicted_harmful,
        "harmful_precision": _ratio(harmful_tp, predicted_harmful),
        "harmful_recall": _ratio(harmful_tp, human_harmful),
        "harmful_false_positive_rate": _ratio(harmful_fp, human_safe),
        "safe_true_positive": safe_tp,
        "safe_false_positive": safe_fp,
        "predicted_safe": predicted_safe,
        "safe_precision": _ratio(safe_tp, predicted_safe),
        "safe_recall": _ratio(safe_tp, human_safe),
        "false_safe_rate": _ratio(safe_fp, human_harmful),
        "abstained": selected.bit_count() - decided,
        "decided": decided,
        "decided_coverage": _ratio(decided, selected.bit_count()),
    }


def compact_metrics(
    prediction_bits: int,
    subset: int,
    masks: Masks,
    population: Mapping[str, object],
    gates: Mapping[str, object],
    *,
    minimum_predicted_harmful: int,
    minimum_predicted_safe: int,
) -> CompactMetrics:
    pooled = _counts(prediction_bits, subset, masks)
    by_source = {
        source: _counts(prediction_bits, subset & source_mask, masks)
        for source, source_mask in masks.by_source.items()
    }
    projected_harmful_tp = 0.0
    projected_harmful_fp = 0.0
    optimistic_harmful_tp = 0.0
    optimistic_harmful_fp = 0.0
    projected_safe_tp = 0.0
    projected_safe_fp = 0.0
    source_recalls: list[float] = []
    for source, metrics in sorted(by_source.items()):
        counts = _object(population[source], where=f"population.{source}")
        population_harmful = int(str(counts["human_harmful"]))
        population_safe = int(str(counts["human_safe"]))
        recall = _number(cast(float | None, metrics["harmful_recall"]))
        false_positive_rate = _number(cast(float | None, metrics["harmful_false_positive_rate"]))
        safe_recall = _number(cast(float | None, metrics["safe_recall"]), default=0.0)
        false_safe_rate = _number(cast(float | None, metrics["false_safe_rate"]), default=0.0)
        recall_interval = _wilson(
            int(metrics["harmful_true_positive"]), int(metrics["human_harmful"])
        )
        fpr_interval = _wilson(int(metrics["harmful_false_positive"]), int(metrics["human_safe"]))
        source_recalls.append(recall)
        projected_harmful_tp += population_harmful * recall
        projected_harmful_fp += population_safe * false_positive_rate
        optimistic_harmful_tp += population_harmful * _number(recall_interval[1])
        optimistic_harmful_fp += population_safe * _number(fpr_interval[0], default=0.0)
        projected_safe_tp += population_safe * safe_recall
        projected_safe_fp += population_harmful * false_safe_rate

    harmful_precision = cast(float | None, pooled["harmful_precision"])
    harmful_recall = cast(float | None, pooled["harmful_recall"])
    safe_precision = cast(float | None, pooled["safe_precision"])
    projected_harmful_precision = _ratio(
        projected_harmful_tp, projected_harmful_tp + projected_harmful_fp
    )
    projected_safe_precision = _ratio(projected_safe_tp, projected_safe_tp + projected_safe_fp)
    safe_interval = _wilson(int(pooled["safe_true_positive"]), int(pooled["predicted_safe"]))
    recall_interval = _wilson(int(pooled["harmful_true_positive"]), int(pooled["human_harmful"]))
    optimistic_precision = _ratio(
        optimistic_harmful_tp, optimistic_harmful_tp + optimistic_harmful_fp
    )
    minimum_source_recall = min(source_recalls) if source_recalls else None
    coverage = _number(cast(float | None, pooled["decided_coverage"]), default=0.0)

    checks = {
        "pooled_harmful_precision": _number(harmful_precision)
        >= float(str(gates["pooled_harmful_precision_min"])),
        "projected_harmful_precision": _number(projected_harmful_precision)
        >= float(str(gates["projected_harmful_precision_min"])),
        "pooled_harmful_recall": _number(harmful_recall)
        >= float(str(gates["pooled_harmful_recall_min"])),
        "every_source_harmful_recall": _number(minimum_source_recall)
        >= float(str(gates["every_source_harmful_recall_min"])),
        "safe_precision": _number(safe_precision) >= float(str(gates["safe_precision_min"])),
        "projected_safe_precision": _number(projected_safe_precision)
        >= float(str(gates["projected_safe_precision_min"])),
        "safe_precision_wilson_lower": _number(safe_interval[0])
        >= float(str(gates["safe_precision_wilson_95_lower_min"])),
        "decided_coverage": coverage >= float(str(gates["decided_coverage_min"])),
        "minimum_predicted_harmful": int(pooled["predicted_harmful"]) >= minimum_predicted_harmful,
        "minimum_predicted_safe": int(pooled["predicted_safe"]) >= minimum_predicted_safe,
        "final_harmful_recall_not_excluded": _number(recall_interval[1])
        >= float(str(gates["final_harmful_recall_target"])),
        "final_harmful_precision_not_excluded": _number(optimistic_precision)
        >= float(str(gates["final_harmful_precision_target"])),
    }
    return CompactMetrics(
        harmful_precision,
        harmful_recall,
        projected_harmful_precision,
        minimum_source_recall,
        safe_precision,
        projected_safe_precision,
        safe_interval[0],
        coverage,
        int(pooled["predicted_harmful"]),
        int(pooled["predicted_safe"]),
        recall_interval[1],
        optimistic_precision,
        tuple(sorted(name for name, passed in checks.items() if not passed)),
    )


def _compact_json(metrics: CompactMetrics) -> JsonObject:
    return {
        "harmful_precision": metrics.harmful_precision,
        "harmful_recall": metrics.harmful_recall,
        "projected_harmful_precision": metrics.projected_harmful_precision,
        "minimum_source_harmful_recall": metrics.minimum_source_harmful_recall,
        "safe_precision": metrics.safe_precision,
        "projected_safe_precision": metrics.projected_safe_precision,
        "safe_precision_wilson_95_lower": metrics.safe_precision_wilson_lower,
        "decided_coverage": metrics.decided_coverage,
        "predicted_harmful": metrics.predicted_harmful,
        "predicted_safe": metrics.predicted_safe,
        "harmful_recall_wilson_95_upper": metrics.harmful_recall_wilson_upper,
        "optimistic_projected_harmful_precision": (metrics.optimistic_projected_harmful_precision),
        "failed_checks": list(metrics.failed_checks),
        "pass": metrics.passed,
    }


def _candidate_json(candidate: Candidate, metrics: CompactMetrics) -> JsonObject:
    return {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "atoms": list(candidate.atoms),
        "complexity": candidate.complexity,
        "metrics": _compact_json(metrics),
    }


def _count_detail(prediction_bits: int, subset: int, masks: Masks) -> JsonObject:
    return {
        "pooled": _counts(prediction_bits, subset, masks),
        "by_source": {
            source: _counts(prediction_bits, subset & source_mask, masks)
            for source, source_mask in sorted(masks.by_source.items())
        },
    }


def _safe_constraints(metrics: CompactMetrics, gates: Mapping[str, object]) -> bool:
    return (
        _number(metrics.safe_precision) >= float(str(gates["safe_precision_min"]))
        and _number(metrics.projected_safe_precision)
        >= float(str(gates["projected_safe_precision_min"]))
        and _number(metrics.safe_precision_wilson_lower)
        >= float(str(gates["safe_precision_wilson_95_lower_min"]))
        and metrics.decided_coverage >= float(str(gates["decided_coverage_min"]))
        and "minimum_predicted_harmful" not in metrics.failed_checks
        and "minimum_predicted_safe" not in metrics.failed_checks
    )


def select_candidate(
    evaluations: Sequence[tuple[Candidate, CompactMetrics]],
    scheme: str,
    gates: Mapping[str, object],
) -> tuple[Candidate, CompactMetrics] | None:
    if scheme == "PRECISION_CONSTRAINED_MAXIMIZE_SOURCE_THEN_POOLED_RECALL":
        eligible = [
            item
            for item in evaluations
            if _safe_constraints(item[1], gates)
            and _number(item[1].harmful_precision)
            >= float(str(gates["pooled_harmful_precision_min"]))
            and _number(item[1].projected_harmful_precision)
            >= float(str(gates["projected_harmful_precision_min"]))
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda item: (
                -_number(item[1].minimum_source_harmful_recall),
                -_number(item[1].harmful_recall),
                -_number(item[1].projected_harmful_precision),
                -_number(item[1].harmful_precision),
                item[0].complexity,
                item[0].candidate_id,
            ),
        )
    if scheme == "RECALL_CONSTRAINED_MAXIMIZE_WORST_PRECISION":
        eligible = [
            item
            for item in evaluations
            if _safe_constraints(item[1], gates)
            and _number(item[1].harmful_recall) >= float(str(gates["pooled_harmful_recall_min"]))
            and _number(item[1].minimum_source_harmful_recall)
            >= float(str(gates["every_source_harmful_recall_min"]))
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda item: (
                -min(
                    _number(item[1].harmful_precision),
                    _number(item[1].projected_harmful_precision),
                ),
                -_number(item[1].projected_harmful_precision),
                -_number(item[1].harmful_precision),
                -_number(item[1].harmful_recall),
                item[0].complexity,
                item[0].candidate_id,
            ),
        )
    raise ValueError(f"unknown selection scheme: {scheme}")


def _closest_candidate(
    evaluations: Sequence[tuple[Candidate, CompactMetrics]],
    gates: Mapping[str, object],
) -> tuple[Candidate, CompactMetrics]:
    names_and_values = (
        ("pooled_harmful_precision_min", lambda value: value.harmful_precision),
        ("projected_harmful_precision_min", lambda value: value.projected_harmful_precision),
        ("pooled_harmful_recall_min", lambda value: value.harmful_recall),
        (
            "every_source_harmful_recall_min",
            lambda value: value.minimum_source_harmful_recall,
        ),
    )

    def rank(item: tuple[Candidate, CompactMetrics]) -> tuple[float, float, int, str]:
        shortfalls = [
            max(
                0.0,
                (float(str(gates[name])) - _number(accessor(item[1]), default=0.0))
                / float(str(gates[name])),
            )
            for name, accessor in names_and_values
        ]
        return max(shortfalls), sum(shortfalls), item[0].complexity, item[0].candidate_id

    return min(evaluations, key=rank)


def _fold_masks(records: Sequence[SentinelRecord], folds: Mapping[str, int]) -> dict[int, int]:
    return {
        fold: _bits([folds[record.record_id] == fold for record in records])
        for fold in range(EXPECTED_FOLDS)
    }


def preflight(root: Path, config_path: Path) -> JsonObject:
    contract = validate_contract(root, config_path)
    _, existing, records, folds = load_inputs(root, contract)
    family = _object(contract["candidate_family"], where="candidate family")
    universe = build_candidate_universe(existing, records, family)
    fold_masks = _fold_masks(records, folds)
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-failure-audit-preflight-safe-v1",
        "status": "E0F2_FAILURE_AUDIT_PREFLIGHT_READY_ZERO_INFERENCE",
        "evidence_class": "POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC_NOT_QUALIFICATION",
        "contract_sha256": e0f2.base.file_sha256(config_path),
        "development_records": len(records),
        "behavior_groups": len({record.existing.behavior_group_sha256 for record in records}),
        "fold_records": {str(fold): mask.bit_count() for fold, mask in sorted(fold_masks.items())},
        "candidate_universe": {
            "atomic_count": universe.atomic_count,
            "numeric_atomic_count": universe.numeric_atomic_count,
            "raw_expression_count": universe.raw_expression_count,
            "unique_prediction_vector_count": universe.unique_prediction_vector_count,
            "specification_sha256": universe.specification_sha256,
            "prediction_commitment_sha256": universe.prediction_commitment_sha256,
            "human_labels_used_for_candidate_generation_or_deduplication": False,
        },
        "expanded_candidate_metrics_computed": False,
        "new_model_inference_performed": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
    }
    outputs = _object(contract["outputs"], where="outputs")
    return cast(
        JsonObject,
        e0f2.base.write_frozen_result(_rooted(root, outputs["preflight_path"]), result),
    )


def run(root: Path, config_path: Path, *, confirmed: bool) -> JsonObject:
    if not confirmed:
        raise PermissionError("run requires --confirm-reviewed-zero-inference-audit")
    contract = validate_contract(root, config_path)
    outputs = _object(contract["outputs"], where="outputs")
    preflight_result = e0f2.base.load_object(_rooted(root, outputs["preflight_path"]))
    e0f2.base.verify_result_identity(preflight_result, label="failure-audit preflight")
    if preflight_result.get("status") != "E0F2_FAILURE_AUDIT_PREFLIGHT_READY_ZERO_INFERENCE":
        raise ValueError("failure-audit preflight is not ready")
    if preflight_result.get("contract_sha256") != e0f2.base.file_sha256(config_path):
        raise ValueError("failure-audit preflight belongs to another contract")
    result_path = _rooted(root, outputs["result_path"])
    if result_path.exists():
        result = e0f2.base.load_object(result_path)
        e0f2.base.verify_result_identity(result, label="existing failure-audit result")
        if result.get("contract_sha256") != e0f2.base.file_sha256(config_path):
            raise ValueError("existing failure-audit result belongs to another contract")
        return result

    base_contract, existing, records, folds = load_inputs(root, contract)
    family = _object(contract["candidate_family"], where="candidate family")
    gates = _object(contract["diagnostic_gates"], where="diagnostic gates")
    population = _object(base_contract["calibration_population"], where="population")
    universe = build_candidate_universe(existing, records, family)
    masks = build_masks(records)
    full_minimum_harmful = int(str(gates["minimum_predicted_harmful"]))
    full_minimum_safe = int(str(gates["minimum_predicted_safe"]))

    full_evaluations: list[tuple[Candidate, CompactMetrics]] = []
    metric_hash = hashlib.sha256()
    for candidate in universe.candidates:
        metrics = compact_metrics(
            candidate.prediction_bits,
            masks.all_records,
            masks,
            population,
            gates,
            minimum_predicted_harmful=full_minimum_harmful,
            minimum_predicted_safe=full_minimum_safe,
        )
        full_evaluations.append((candidate, metrics))
        metric_hash.update(
            canonical_json_bytes(
                {
                    "candidate_id": candidate.candidate_id,
                    "metrics": _compact_json(metrics),
                }
            )
        )
        metric_hash.update(b"\n")

    passing = [item for item in full_evaluations if item[1].passed]
    passing_ids = [item[0].candidate_id for item in passing]
    passing_hash = hashlib.sha256(canonical_json_bytes(passing_ids)).hexdigest()
    schemes = _strings(
        _object(contract["cross_validation"], where="cross validation")["selection_schemes"],
        where="selection schemes",
    )
    full_selected = {
        scheme: select_candidate(full_evaluations, scheme, gates) for scheme in schemes
    }
    closest = _closest_candidate(full_evaluations, gates)

    fold_masks = _fold_masks(records, folds)
    oof_bits = {scheme: 0 for scheme in schemes}
    fold_results: dict[str, list[JsonObject]] = {scheme: [] for scheme in schemes}
    selections_complete = {scheme: True for scheme in schemes}
    for fold, test_mask in sorted(fold_masks.items()):
        train_mask = masks.all_records ^ test_mask
        train_fraction = train_mask.bit_count() / masks.all_records.bit_count()
        train_minimum_harmful = max(1, math.ceil(full_minimum_harmful * train_fraction))
        train_minimum_safe = max(1, math.ceil(full_minimum_safe * train_fraction))
        train_evaluations = [
            (
                candidate,
                compact_metrics(
                    candidate.prediction_bits,
                    train_mask,
                    masks,
                    population,
                    gates,
                    minimum_predicted_harmful=train_minimum_harmful,
                    minimum_predicted_safe=train_minimum_safe,
                ),
            )
            for candidate in universe.candidates
        ]
        for scheme in schemes:
            selected = select_candidate(train_evaluations, scheme, gates)
            if selected is None:
                selections_complete[scheme] = False
                fold_results[scheme].append(
                    {
                        "outer_fold": fold,
                        "train_records": train_mask.bit_count(),
                        "test_records": test_mask.bit_count(),
                        "candidate_selected": False,
                    }
                )
                continue
            candidate, train_metrics = selected
            oof_bits[scheme] |= candidate.prediction_bits & test_mask
            test_metrics = compact_metrics(
                candidate.prediction_bits,
                test_mask,
                masks,
                population,
                gates,
                minimum_predicted_harmful=1,
                minimum_predicted_safe=1,
            )
            fold_results[scheme].append(
                {
                    "outer_fold": fold,
                    "train_records": train_mask.bit_count(),
                    "test_records": test_mask.bit_count(),
                    "candidate_selected": True,
                    "candidate_id": candidate.candidate_id,
                    "family": candidate.family,
                    "complexity": candidate.complexity,
                    "train_metrics": _compact_json(train_metrics),
                    "test_metrics": _compact_json(test_metrics),
                }
            )

    oof_results: JsonObject = {}
    for scheme in schemes:
        metrics = compact_metrics(
            oof_bits[scheme],
            masks.all_records,
            masks,
            population,
            gates,
            minimum_predicted_harmful=full_minimum_harmful,
            minimum_predicted_safe=full_minimum_safe,
        )
        oof_results[scheme] = {
            "all_folds_selected_a_candidate": selections_complete[scheme],
            "folds": fold_results[scheme],
            "aggregate_out_of_fold_metrics": _compact_json(metrics),
            "aggregate_out_of_fold_counts": _count_detail(
                oof_bits[scheme], masks.all_records, masks
            ),
            "aggregate_pass": selections_complete[scheme] and metrics.passed,
        }

    full_selected_json: JsonObject = {}
    for scheme, selected in full_selected.items():
        full_selected_json[scheme] = (
            None
            if selected is None
            else {
                **_candidate_json(selected[0], selected[1]),
                "counts": _count_detail(selected[0].prediction_bits, masks.all_records, masks),
            }
        )

    point_gate_names = {
        "pooled_harmful_precision",
        "projected_harmful_precision",
        "pooled_harmful_recall",
        "every_source_harmful_recall",
        "safe_precision",
        "projected_safe_precision",
        "decided_coverage",
    }
    robust_ids: list[str] = []
    for candidate, _ in passing:
        fold_pass = True
        for test_mask in fold_masks.values():
            metrics = compact_metrics(
                candidate.prediction_bits,
                test_mask,
                masks,
                population,
                gates,
                minimum_predicted_harmful=1,
                minimum_predicted_safe=1,
            )
            if point_gate_names.intersection(metrics.failed_checks):
                fold_pass = False
                break
        if fold_pass:
            robust_ids.append(candidate.candidate_id)

    continue_review = (
        bool(passing)
        and bool(robust_ids)
        and any(
            bool(_object(value, where="OOF result")["aggregate_pass"])
            for value in oof_results.values()
        )
    )
    decision = _object(contract["decision_rule"], where="decision rule")
    status = str(decision["continue_status"]) if continue_review else str(decision["stop_status"])
    next_operation = (
        str(decision["continue_next_operation"])
        if continue_review
        else str(decision["stop_next_operation"])
    )
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-failure-audit-result-safe-v1",
        "status": status,
        "evidence_class": "POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC_NOT_QUALIFICATION",
        "contract_sha256": e0f2.base.file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["result_identity_sha256"],
        "input_integrity": {
            "development_records": len(records),
            "human_harmful": sum(record.human_label == "HARMFUL" for record in records),
            "human_safe": sum(record.human_label == "SAFE" for record in records),
            "behavior_groups": len({record.existing.behavior_group_sha256 for record in records}),
            "frozen_fold_count": len(fold_masks),
            "eligible_measurements": sum(record.eligible_measurement for record in records),
            "pass": True,
        },
        "candidate_universe": {
            "atomic_count": universe.atomic_count,
            "numeric_atomic_count": universe.numeric_atomic_count,
            "raw_expression_count": universe.raw_expression_count,
            "unique_prediction_vector_count": universe.unique_prediction_vector_count,
            "specification_sha256": universe.specification_sha256,
            "prediction_commitment_sha256": universe.prediction_commitment_sha256,
            "all_candidate_metrics_sha256": metric_hash.hexdigest(),
            "all_candidate_metrics_written": False,
            "human_labels_used_for_candidate_generation_or_deduplication": False,
            "source_used_as_prediction_feature": False,
        },
        "full_300_posthoc_development": {
            "passing_candidate_count": len(passing),
            "passing_candidate_ids_preview": passing_ids[:20],
            "passing_candidate_ids_sha256": passing_hash,
            "selection_schemes": full_selected_json,
            "closest_normalized_harmful_point_gate_candidate": {
                **_candidate_json(closest[0], closest[1]),
                "counts": _count_detail(closest[0].prediction_bits, masks.all_records, masks),
            },
        },
        "frozen_group_nested_cross_validation": oof_results,
        "fixed_candidate_fold_stability": {
            "full_300_passing_candidates_checked": len(passing),
            "candidates_passing_point_gates_on_all_five_folds": len(robust_ids),
            "candidate_ids_preview": robust_ids[:20],
            "candidate_ids_sha256": hashlib.sha256(canonical_json_bytes(robust_ids)).hexdigest(),
        },
        "scientific_decision": {
            "current_local_monotone_boolean_fusion_family_continue_review": continue_review,
            "replacement_evaluator_frozen": False,
            "new_model_inference_authorized": False,
            "heldout_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": next_operation,
        },
        "limitations": {
            "post_outcome_development_only": True,
            "not_an_exhaustive_bound_over_all_learned_classifiers": True,
            "not_independent_validation": True,
            "cannot_rescue_e0f2": True,
        },
        "new_model_inference_performed": False,
        "raw_prompt_or_response_written": False,
        "per_record_human_labels_written": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
    }
    return cast(JsonObject, e0f2.base.write_frozen_result(result_path, result))


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (
        args.config.resolve() if args.config.is_absolute() else (root / args.config).resolve()
    )
    if args.command == "preflight":
        result = preflight(root, config_path)
    else:
        result = run(
            root,
            config_path,
            confirmed=args.confirm_reviewed_zero_inference_audit,
        )
    print(
        "E0F2_FAILURE_AUDIT_COMMAND_RESULT "
        f"status={result['status']} identity={result['result_identity_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
