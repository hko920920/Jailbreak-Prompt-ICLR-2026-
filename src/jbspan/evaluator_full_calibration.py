from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from jbspan.evaluator_cpu_router import classification_metrics

JsonObject = dict[str, Any]


def deterministic_execution_order(
    rows: Sequence[Mapping[str, Any]], *, seed: str
) -> list[JsonObject]:
    record_ids = [str(row["record_id"]) for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("full-calibration records contain duplicate IDs")
    ordered: list[JsonObject] = []
    for row in rows:
        value = dict(row)
        value["execution_score"] = hashlib.sha256(
            f"{seed}|{row['record_id']}".encode()
        ).hexdigest()
        ordered.append(value)
    ordered.sort(key=lambda row: (str(row["execution_score"]), str(row["record_id"])))
    for index, row in enumerate(ordered):
        row["execution_order"] = index
    return ordered


def behavior_group_decision_metrics(
    truth: Sequence[str], predicted: Sequence[str], groups: Sequence[str]
) -> JsonObject:
    if not truth or len(truth) != len(predicted) or len(truth) != len(groups):
        raise ValueError("truth, prediction, and behavior-group denominators differ")
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        grouped[str(group)].append(index)
    group_coverages: list[float] = []
    groups_with_decision = 0
    groups_with_error = 0
    for indices in grouped.values():
        decided = [index for index in indices if predicted[index] != "ABSTAIN"]
        group_coverages.append(len(decided) / len(indices))
        if decided:
            groups_with_decision += 1
            if any(predicted[index] != truth[index] for index in decided):
                groups_with_error += 1
    group_count = len(grouped)
    return {
        "records": len(truth),
        "behavior_groups": group_count,
        "groups_with_at_least_one_decision": groups_with_decision,
        "behavior_group_decision_coverage": groups_with_decision / group_count,
        "mean_within_group_record_coverage": sum(group_coverages) / group_count,
        "groups_with_at_least_one_decided_error": groups_with_error,
        "decided_group_error_incidence": (
            groups_with_error / groups_with_decision if groups_with_decision else 1.0
        ),
    }


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile input is empty")
    if not 0 <= probability <= 1:
        raise ValueError("percentile probability must be in [0, 1]")
    position = probability * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def behavior_cluster_bootstrap(
    truth: Sequence[str],
    predicted: Sequence[str],
    groups: Sequence[str],
    *,
    seed: str,
    replicates: int,
    metric_names: Sequence[str],
) -> JsonObject:
    if not truth or len(truth) != len(predicted) or len(truth) != len(groups):
        raise ValueError("bootstrap denominators differ")
    if replicates < 100:
        raise ValueError("bootstrap requires at least 100 replicates")
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        grouped[str(group)].append(index)
    group_ids = sorted(grouped)
    if len(group_ids) < 2:
        raise ValueError("bootstrap requires at least two behavior groups")
    seed_value = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    generator = random.Random(seed_value)
    samples: dict[str, list[float]] = {name: [] for name in metric_names}
    for _ in range(replicates):
        sampled_indices: list[int] = []
        for _group_index in group_ids:
            sampled_group = group_ids[generator.randrange(len(group_ids))]
            sampled_indices.extend(grouped[sampled_group])
        metrics = classification_metrics(
            [truth[index] for index in sampled_indices],
            [predicted[index] for index in sampled_indices],
        )
        for name in metric_names:
            value = metrics.get(name)
            if not isinstance(value, (float, int)):
                raise ValueError(f"bootstrap metric is unavailable: {name}")
            samples[name].append(float(value))
    intervals: JsonObject = {}
    for name, values in samples.items():
        ordered = sorted(values)
        intervals[name] = {
            "lower_2_5": _percentile(ordered, 0.025),
            "median": _percentile(ordered, 0.5),
            "upper_97_5": _percentile(ordered, 0.975),
        }
    return {
        "method": "nonparametric_percentile_cluster_bootstrap",
        "cluster_unit": "behavior_group_sha256",
        "replicates": replicates,
        "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "behavior_groups": len(group_ids),
        "intervals": intervals,
    }
