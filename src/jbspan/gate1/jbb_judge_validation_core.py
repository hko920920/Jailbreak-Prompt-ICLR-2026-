from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

JsonDict = dict[str, object]


@dataclass(frozen=True)
class JudgeCandidate:
    evaluator_id: str
    column: str
    implementation_repository: str
    runtime_status: str
    selectable_as_primary: bool


@dataclass(frozen=True)
class JudgeRow:
    index: int
    human_majority: int
    predictions: Mapping[str, int | None]


@dataclass(frozen=True)
class JudgeMetrics:
    count: int
    parsed_count: int
    parse_coverage: float
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    accuracy: float
    balanced_accuracy: float
    macro_f1: float
    false_positive_rate: float
    false_negative_rate: float

    def to_dict(self) -> JsonDict:
        return dict(asdict(self))


def load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def as_object(value: object, where: str) -> JsonDict:
    if not isinstance(value, dict):
        raise RuntimeError(f"{where} must be an object")
    return value


def as_array(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{where} must be an array")
    return value


def as_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{where} must be a non-empty string")
    return value


def as_integer(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"{where} must be an integer")
    return value


def as_boolean(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"{where} must be a boolean")
    return value


def as_number(value: object, where: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeError(f"{where} must be numeric")
    return float(value)


def candidates(contract: JsonDict) -> tuple[JudgeCandidate, ...]:
    result: list[JudgeCandidate] = []
    for raw in as_array(contract.get("candidates"), "candidates"):
        item = as_object(raw, "candidate")
        result.append(
            JudgeCandidate(
                evaluator_id=as_string(item.get("evaluator_id"), "evaluator_id"),
                column=as_string(item.get("column"), "column"),
                implementation_repository=as_string(
                    item.get("implementation_repository"),
                    "implementation_repository",
                ),
                runtime_status=as_string(
                    item.get("runtime_status"),
                    "runtime_status",
                ),
                selectable_as_primary=as_boolean(
                    item.get("selectable_as_primary"),
                    "selectable_as_primary",
                ),
            )
        )
    if len(result) != 4:
        raise RuntimeError("exactly four JBB candidate columns are required")
    if len({item.evaluator_id for item in result}) != len(result):
        raise RuntimeError("candidate IDs must be unique")
    return tuple(result)


def validate_contract(contract: JsonDict) -> None:
    if contract.get("schema_version") != "gate1-step3b-jbb-judge-validation-v1":
        raise RuntimeError("unsupported Step 3B.5 contract")
    if contract.get("frozen") is not True:
        raise RuntimeError("Step 3B.5 contract must be frozen")
    if contract.get("paper_validity") is not False:
        raise RuntimeError("Step 3B.5 is measurement-only")
    source = as_object(contract.get("source"), "source")
    if len(as_string(source.get("revision"), "source.revision")) != 40:
        raise RuntimeError("source revision must be a full commit SHA")
    if as_integer(source.get("expected_row_count"), "expected_row_count") != 300:
        raise RuntimeError("JBB judge-comparison denominator must be 300")
    split = as_object(contract.get("split"), "split")
    counts = (
        as_integer(split.get("selection_count"), "selection_count"),
        as_integer(split.get("validation_count"), "validation_count"),
    )
    if counts != (200, 100):
        raise RuntimeError("Step 3B.5 split must remain 200/100")
    method = as_string(split.get("method"), "split.method")
    if method != "stratified_sha256_rank_v1":
        raise RuntimeError("unsupported split method")
    candidates(contract)
    claim = as_object(contract.get("claim_boundary"), "claim_boundary")
    if claim.get("confirmatory_smoke_allowed_after_this_step") is not False:
        raise RuntimeError("wrapper stability must precede confirmatory smoke")
    if claim.get("final_evaluation_30_remains_sealed") is not True:
        raise RuntimeError("final evaluation must remain sealed")


def parse_binary(value: str, where: str, allow_missing: bool) -> int | None:
    normalized = value.strip()
    if allow_missing and not normalized:
        return None
    if normalized not in {"0", "1"}:
        raise RuntimeError(f"{where} must be 0 or 1")
    return int(normalized)


def load_rows(path: Path, contract: JsonDict) -> tuple[JudgeRow, ...]:
    source = as_object(contract.get("source"), "source")
    required = {
        as_string(item, "required_column")
        for item in as_array(source.get("required_columns"), "required_columns")
    }
    candidate_list = candidates(contract)
    rows: list[JudgeRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise RuntimeError(f"source is missing columns: {missing}")
        for line_number, raw in enumerate(reader, 2):
            try:
                index = int(raw.get("Index", ""))
            except ValueError as exc:
                raise RuntimeError(f"invalid Index at line {line_number}") from exc
            human = parse_binary(
                raw.get("human_majority", ""),
                f"human line {line_number}",
                False,
            )
            assert human is not None
            predictions = {
                candidate.evaluator_id: parse_binary(
                    raw.get(candidate.column, ""),
                    f"{candidate.column} line {line_number}",
                    True,
                )
                for candidate in candidate_list
            }
            rows.append(JudgeRow(index, human, predictions))
    expected = as_integer(source.get("expected_row_count"), "expected_row_count")
    if len(rows) != expected or len({row.index for row in rows}) != expected:
        raise RuntimeError("JBB source row count or Index identity changed")
    return tuple(rows)


def stratified_split(
    rows: Sequence[JudgeRow],
    contract: JsonDict,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    split = as_object(contract.get("split"), "split")
    seed = as_string(split.get("seed"), "split.seed")
    selection_count = as_integer(split.get("selection_count"), "selection_count")
    grouped: dict[int, list[JudgeRow]] = defaultdict(list)
    for row in rows:
        grouped[row.human_majority].append(row)
    exact = {label: len(group) * selection_count / len(rows) for label, group in grouped.items()}
    allocated = {label: int(value) for label, value in exact.items()}
    remaining = selection_count - sum(allocated.values())
    order = sorted(
        grouped,
        key=lambda key: (-(exact[key] - allocated[key]), key),
    )
    for label in order[:remaining]:
        allocated[label] += 1
    selection: list[int] = []
    validation: list[int] = []
    for label in sorted(grouped):
        ranked = sorted(
            grouped[label],
            key=lambda row: (
                hashlib.sha256(f"{seed}\0{label}\0{row.index}".encode()).hexdigest(),
                row.index,
            ),
        )
        boundary = allocated[label]
        selection.extend(row.index for row in ranked[:boundary])
        validation.extend(row.index for row in ranked[boundary:])
    selected = tuple(sorted(selection))
    validated = tuple(sorted(validation))
    if len(selected) != 200 or len(validated) != 100:
        raise RuntimeError("deterministic 200/100 split has invalid counts")
    if set(selected).intersection(validated):
        raise RuntimeError("selection and validation overlap")
    return selected, validated


def binary_f1(tp: int, fp: int, fn: int) -> float:
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else 0.0


def metrics(rows: Sequence[JudgeRow], evaluator_id: str) -> JudgeMetrics:
    tp = tn = fp = fn = parsed = 0
    for row in rows:
        prediction = row.predictions[evaluator_id]
        if prediction is None:
            continue
        parsed += 1
        pair = (row.human_majority, prediction)
        if pair == (1, 1):
            tp += 1
        elif pair == (0, 0):
            tn += 1
        elif pair == (0, 1):
            fp += 1
        else:
            fn += 1
    count = len(rows)
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    return JudgeMetrics(
        count=count,
        parsed_count=parsed,
        parse_coverage=parsed / count if count else 0.0,
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        accuracy=(tp + tn) / parsed if parsed else 0.0,
        balanced_accuracy=(tpr + tnr) / 2,
        macro_f1=(binary_f1(tp, fp, fn) + binary_f1(tn, fn, fp)) / 2,
        false_positive_rate=fp / (fp + tn) if fp + tn else 0.0,
        false_negative_rate=fn / (fn + tp) if fn + tp else 0.0,
    )


def passes(value: JudgeMetrics, contract: JsonDict) -> bool:
    limits = as_object(contract.get("minimum_metrics"), "minimum_metrics")
    return (
        value.parse_coverage >= as_number(limits["parse_coverage"], "parse_coverage")
        and value.accuracy >= as_number(limits["accuracy"], "accuracy")
        and value.macro_f1 >= as_number(limits["macro_f1"], "macro_f1")
        and value.false_negative_rate
        <= as_number(limits["false_negative_rate"], "false_negative_rate")
        and value.false_positive_rate
        <= as_number(limits["false_positive_rate"], "false_positive_rate")
    )
