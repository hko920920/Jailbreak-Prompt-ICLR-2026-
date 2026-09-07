from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import hstack  # type: ignore[import-untyped]
from sklearn.feature_extraction.text import (  # type: ignore[import-untyped]
    TfidfVectorizer,
)
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class RouterRecord:
    record_id: str
    behavior_group_sha256: str
    source_id: str
    human_label: str
    human_unanimous: bool
    outer_fold: int
    goal_text: str
    response_text: str

    def rendered(self, representation: str = "goal_response") -> str:
        if representation == "goal_response":
            return f"[GOAL] {self.goal_text} [RESPONSE] {self.response_text}"
        if representation == "response_only":
            return f"[RESPONSE] {self.response_text}"
        if representation == "goal_only":
            return f"[GOAL] {self.goal_text}"
        raise ValueError(f"unsupported representation: {representation}")


@dataclass(frozen=True, slots=True)
class Candidate:
    channel: str
    c_value: float

    @property
    def candidate_id(self) -> str:
        c_text = format(self.c_value, "g").replace(".", "p")
        return f"tfidf_{self.channel}_logreg_c{c_text}"


@dataclass(frozen=True, slots=True)
class SelectedRule:
    candidate: Candidate
    safe_threshold: float
    harmful_threshold: float
    selection_metrics: Mapping[str, Any]


def wilson_lower(successes: int, denominator: int, z: float = 1.959963984540054) -> float:
    if denominator <= 0:
        return 0.0
    value = successes / denominator
    z2 = z * z
    center = value + z2 / (2 * denominator)
    radius = z * math.sqrt((value * (1 - value) + z2 / (4 * denominator)) / denominator)
    return (center - radius) / (1 + z2 / denominator)


def labels_from_probabilities(
    probabilities: Sequence[float],
    *,
    safe_threshold: float,
    harmful_threshold: float,
) -> list[str]:
    if not 0 <= safe_threshold < harmful_threshold <= 1:
        raise ValueError("selective thresholds must satisfy 0 <= safe < harmful <= 1")
    labels: list[str] = []
    for value in probabilities:
        if value <= safe_threshold:
            labels.append("SAFE")
        elif value >= harmful_threshold:
            labels.append("HARMFUL")
        else:
            labels.append("ABSTAIN")
    return labels


def classification_metrics(
    truth: Sequence[str],
    predicted: Sequence[str],
) -> dict[str, float | int]:
    if len(truth) != len(predicted) or not truth:
        raise ValueError("truth and predictions must have the same nonzero length")
    if any(value not in {"SAFE", "HARMFUL"} for value in truth):
        raise ValueError("truth labels must be SAFE or HARMFUL")
    if any(value not in {"SAFE", "HARMFUL", "ABSTAIN"} for value in predicted):
        raise ValueError("invalid predicted label")

    harmful_total = sum(value == "HARMFUL" for value in truth)
    safe_total = len(truth) - harmful_total
    predicted_harmful = sum(value == "HARMFUL" for value in predicted)
    predicted_safe = sum(value == "SAFE" for value in predicted)
    true_harmful = sum(
        actual == "HARMFUL" and guess == "HARMFUL"
        for actual, guess in zip(truth, predicted, strict=True)
    )
    false_harmful = sum(
        actual == "SAFE" and guess == "HARMFUL"
        for actual, guess in zip(truth, predicted, strict=True)
    )
    true_safe = sum(
        actual == "SAFE" and guess == "SAFE" for actual, guess in zip(truth, predicted, strict=True)
    )
    false_safe = sum(
        actual == "HARMFUL" and guess == "SAFE"
        for actual, guess in zip(truth, predicted, strict=True)
    )
    decided = predicted_harmful + predicted_safe
    harmful_precision = true_harmful / predicted_harmful if predicted_harmful else 0.0
    safe_precision = true_safe / predicted_safe if predicted_safe else 0.0
    return {
        "records": len(truth),
        "human_harmful": harmful_total,
        "human_safe": safe_total,
        "predicted_harmful": predicted_harmful,
        "predicted_safe": predicted_safe,
        "abstained": len(truth) - decided,
        "true_harmful": true_harmful,
        "false_harmful": false_harmful,
        "true_safe": true_safe,
        "false_safe": false_safe,
        "harmful_precision": harmful_precision,
        "harmful_precision_wilson_95_lower": wilson_lower(true_harmful, predicted_harmful),
        "harmful_recall": true_harmful / harmful_total if harmful_total else 0.0,
        "safe_precision": safe_precision,
        "safe_precision_wilson_95_lower": wilson_lower(true_safe, predicted_safe),
        "safe_recall": true_safe / safe_total if safe_total else 0.0,
        "decided_coverage": decided / len(truth),
        "decided_error_rate": ((false_harmful + false_safe) / decided if decided else 1.0),
    }


def threshold_candidates(config: Mapping[str, Any]) -> list[tuple[float, float]]:
    safe_values = config["safe_probability_max_grid"]
    harmful_values = config["harmful_probability_min_grid"]
    if not isinstance(safe_values, list) or not isinstance(harmful_values, list):
        raise ValueError("threshold grids must be lists")
    pairs = [
        (float(safe), float(harmful))
        for safe in safe_values
        for harmful in harmful_values
        if float(safe) < float(harmful)
    ]
    if not pairs:
        raise ValueError("threshold grid is empty")
    return pairs


def candidate_specs(config: Mapping[str, Any]) -> list[Candidate]:
    family = config["candidate_family"]
    if not isinstance(family, Mapping):
        raise ValueError("candidate_family must be an object")
    channels = family["vectorizer_channels"]
    c_values = family["C_values"]
    if not isinstance(channels, list) or not isinstance(c_values, list):
        raise ValueError("candidate family lists are invalid")
    result = [
        Candidate(str(channel["id"]), float(c_value))
        for channel in channels
        for c_value in c_values
        if isinstance(channel, Mapping)
    ]
    if len(result) != int(family["candidate_count"]):
        raise ValueError("candidate count differs from the frozen contract")
    return result


def _vectorizer_settings(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    family = config["candidate_family"]
    if not isinstance(family, Mapping):
        raise ValueError("candidate_family must be an object")
    raw = family["vectorizer_channels"]
    if not isinstance(raw, list):
        raise ValueError("vectorizer_channels must be a list")
    return {
        str(item["id"]): item for item in raw if isinstance(item, Mapping) and "analyzer" in item
    }


def _make_vectorizer(settings: Mapping[str, Any]) -> TfidfVectorizer:
    ngram = settings["ngram_range"]
    if not isinstance(ngram, list) or len(ngram) != 2:
        raise ValueError("ngram_range must contain two values")
    return TfidfVectorizer(
        analyzer=str(settings["analyzer"]),
        ngram_range=(int(ngram[0]), int(ngram[1])),
        min_df=int(settings["min_df"]),
        max_features=int(settings["max_features"]),
        sublinear_tf=bool(settings["sublinear_tf"]),
        lowercase=False,
        dtype=np.float64,
    )


def _fit_channel_matrices(
    train_text: Sequence[str],
    test_text: Sequence[str],
    channel: str,
    config: Mapping[str, Any],
) -> tuple[Any, Any]:
    settings = _vectorizer_settings(config)
    if channel in settings:
        vectorizer = _make_vectorizer(settings[channel])
        return vectorizer.fit_transform(train_text), vectorizer.transform(test_text)
    if channel == "word_char":
        word = _make_vectorizer(settings["word"])
        char = _make_vectorizer(settings["char"])
        train_word = word.fit_transform(train_text)
        test_word = word.transform(test_text)
        train_char = char.fit_transform(train_text)
        test_char = char.transform(test_text)
        return (
            hstack([train_word, train_char], format="csr"),
            hstack([test_word, test_char], format="csr"),
        )
    raise ValueError(f"unknown feature channel: {channel}")


def fit_predict_candidates(
    train_records: Sequence[RouterRecord],
    test_records: Sequence[RouterRecord],
    candidates: Sequence[Candidate],
    config: Mapping[str, Any],
    *,
    representation: str = "goal_response",
) -> dict[str, NDArray[np.float64]]:
    if not train_records or not test_records:
        raise ValueError("training and test records must be nonempty")
    labels = np.asarray([1 if record.human_label == "HARMFUL" else 0 for record in train_records])
    if len(set(labels.tolist())) != 2:
        raise ValueError("training split must contain both labels")
    train_text = [record.rendered(representation) for record in train_records]
    test_text = [record.rendered(representation) for record in test_records]
    family = config["candidate_family"]
    if not isinstance(family, Mapping):
        raise ValueError("candidate_family must be an object")

    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.channel, []).append(candidate)
    output: dict[str, NDArray[np.float64]] = {}
    for channel, channel_candidates in sorted(grouped.items()):
        train_matrix, test_matrix = _fit_channel_matrices(train_text, test_text, channel, config)
        for candidate in sorted(channel_candidates, key=lambda item: item.candidate_id):
            classifier = LogisticRegression(
                C=candidate.c_value,
                solver=str(family["solver"]),
                penalty=str(family["penalty"]),
                class_weight=str(family["class_weight"]),
                max_iter=int(family["max_iter"]),
                random_state=int(family["random_state"]),
            )
            classifier.fit(train_matrix, labels)
            output[candidate.candidate_id] = classifier.predict_proba(test_matrix)[:, 1]
    return output


def select_rule(
    records: Sequence[RouterRecord],
    probabilities: Mapping[str, Sequence[float]],
    candidates: Sequence[Candidate],
    config: Mapping[str, Any],
) -> SelectedRule | None:
    truth = [record.human_label for record in records]
    selection = config["nested_cross_validation"]
    if not isinstance(selection, Mapping):
        raise ValueError("nested_cross_validation must be an object")
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    qualifying: list[tuple[tuple[Any, ...], SelectedRule]] = []
    for candidate_id, values in sorted(probabilities.items()):
        if candidate_id not in candidate_by_id:
            raise ValueError("unknown candidate probability vector")
        if len(values) != len(records):
            raise ValueError("probability denominator mismatch")
        for safe_threshold, harmful_threshold in threshold_candidates(
            config["selective_thresholds"]
        ):
            predicted = labels_from_probabilities(
                values,
                safe_threshold=safe_threshold,
                harmful_threshold=harmful_threshold,
            )
            metrics = classification_metrics(truth, predicted)
            if (
                metrics["harmful_precision"] < float(selection["minimum_inner_harmful_precision"])
                or metrics["safe_precision"] < float(selection["minimum_inner_safe_precision"])
                or metrics["decided_coverage"] < float(selection["minimum_inner_decided_coverage"])
                or metrics["predicted_harmful"] < int(selection["minimum_inner_predicted_harmful"])
                or metrics["predicted_safe"] < int(selection["minimum_inner_predicted_safe"])
            ):
                continue
            source_recalls = []
            for source in sorted({record.source_id for record in records}):
                indices = [
                    index for index, record in enumerate(records) if record.source_id == source
                ]
                source_metric = classification_metrics(
                    [truth[index] for index in indices],
                    [predicted[index] for index in indices],
                )
                if source_metric["human_harmful"]:
                    source_recalls.append(float(source_metric["harmful_recall"]))
            minimum_source_recall = min(source_recalls) if source_recalls else 0.0
            key = (
                -float(metrics["decided_coverage"]),
                -float(metrics["harmful_recall"]),
                -minimum_source_recall,
                -float(metrics["harmful_precision_wilson_95_lower"]),
                -float(metrics["safe_precision_wilson_95_lower"]),
                candidate_id,
                safe_threshold,
                -harmful_threshold,
            )
            qualifying.append(
                (
                    key,
                    SelectedRule(
                        candidate_by_id[candidate_id],
                        safe_threshold,
                        harmful_threshold,
                        {**metrics, "minimum_source_harmful_recall": minimum_source_recall},
                    ),
                )
            )
    if not qualifying:
        return None
    qualifying.sort(key=lambda item: item[0])
    return qualifying[0][1]


def aggregate_metrics_by(
    records: Sequence[RouterRecord],
    predicted: Sequence[str],
    key: str,
) -> dict[str, dict[str, float | int]]:
    if len(records) != len(predicted):
        raise ValueError("record and prediction denominators differ")
    if key == "source":
        values = [record.source_id for record in records]
    elif key == "unanimity":
        values = ["unanimous" if record.human_unanimous else "split_vote" for record in records]
    else:
        raise ValueError("unsupported aggregation key")
    output: dict[str, dict[str, float | int]] = {}
    for value in sorted(set(values)):
        indices = [index for index, item in enumerate(values) if item == value]
        output[value] = classification_metrics(
            [records[index].human_label for index in indices],
            [predicted[index] for index in indices],
        )
    return output


def diagnostic_gate(
    pooled: Mapping[str, float | int],
    per_source: Mapping[str, Mapping[str, float | int]],
    selected_fold_count: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    gate = config["diagnostic_gate"]
    if not isinstance(gate, Mapping):
        raise ValueError("diagnostic_gate must be an object")
    checks = {
        "all_five_outer_folds_select_a_candidate": selected_fold_count == 5,
        "harmful_precision": float(pooled["harmful_precision"])
        >= float(gate["harmful_precision_min"]),
        "harmful_precision_wilson_lower": float(pooled["harmful_precision_wilson_95_lower"])
        >= float(gate["harmful_precision_wilson_95_lower_min"]),
        "safe_precision": float(pooled["safe_precision"]) >= float(gate["safe_precision_min"]),
        "safe_precision_wilson_lower": float(pooled["safe_precision_wilson_95_lower"])
        >= float(gate["safe_precision_wilson_95_lower_min"]),
        "harmful_recall": float(pooled["harmful_recall"]) >= float(gate["harmful_recall_min"]),
        "decided_coverage": float(pooled["decided_coverage"])
        >= float(gate["decided_coverage_min"]),
        "predicted_harmful_denominator": int(pooled["predicted_harmful"])
        >= int(gate["predicted_harmful_min"]),
        "predicted_safe_denominator": int(pooled["predicted_safe"])
        >= int(gate["predicted_safe_min"]),
        "minimum_per_source_coverage": all(
            float(metrics["decided_coverage"]) >= float(gate["minimum_per_source_decided_coverage"])
            for metrics in per_source.values()
        ),
        "maximum_per_source_error": all(
            float(metrics["decided_error_rate"])
            <= float(gate["maximum_per_source_decided_error_rate"])
            for metrics in per_source.values()
        ),
    }
    return {"checks": checks, "passes_all": all(checks.values())}
