from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

RESPONSE_FIELDS = ("response_label", "confidence")
PROMPT_FIELDS = (
    "goal_alignment",
    "behavior_retained",
    "payload_not_deleted",
    "coherent",
    "explicit_safety_instruction_added",
    "confidence",
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _index_annotations(payload: dict[str, Any], expected_kind: str) -> dict[str, dict[str, Any]]:
    if payload.get("kind") != expected_kind:
        raise ValueError(f"expected kind={expected_kind}")
    values = payload.get("annotations")
    if not isinstance(values, list):
        raise ValueError("annotations must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("annotation must be an object")
        audit_id = raw.get("audit_id")
        if not isinstance(audit_id, str) or not audit_id:
            raise ValueError("invalid audit_id")
        if audit_id in indexed:
            raise ValueError(f"duplicate audit_id: {audit_id}")
        indexed[audit_id] = raw
    return indexed


def _kappa(values_a: list[str], values_b: list[str]) -> float | None:
    if len(values_a) != len(values_b) or not values_a:
        raise ValueError("kappa input mismatch")
    n = len(values_a)
    observed = sum(a == b for a, b in zip(values_a, values_b, strict=True)) / n
    counts_a = Counter(values_a)
    counts_b = Counter(values_b)
    labels = set(counts_a) | set(counts_b)
    expected = sum((counts_a[label] / n) * (counts_b[label] / n) for label in labels)
    if expected >= 1.0 - 1e-15:
        return None
    return (observed - expected) / (1.0 - expected)


def _field_report(
    ids: list[str],
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    usable: list[str] = []
    values_a: list[str] = []
    values_b: list[str] = []
    missing: list[str] = []
    for audit_id in ids:
        left = a[audit_id].get(field)
        right = b[audit_id].get(field)
        if not isinstance(left, str) or not left or not isinstance(right, str) or not right:
            missing.append(audit_id)
            continue
        usable.append(audit_id)
        values_a.append(left)
        values_b.append(right)
    agreement = (
        sum(x == y for x, y in zip(values_a, values_b, strict=True)) / len(values_a)
        if values_a
        else None
    )
    return {
        "field": field,
        "n": len(values_a),
        "exact_agreement": agreement,
        "cohen_kappa": _kappa(values_a, values_b) if values_a else None,
        "missing_ids": missing,
        "disagreement_ids": [
            audit_id
            for audit_id, left, right in zip(usable, values_a, values_b, strict=True)
            if left != right
        ],
        "reviewer_1_counts": dict(sorted(Counter(values_a).items())),
        "reviewer_2_counts": dict(sorted(Counter(values_b).items())),
    }


def _kind_report(
    kind: str,
    path_a: Path,
    path_b: Path,
    mapping: dict[str, Any],
) -> dict[str, Any]:
    reviewer_a = _index_annotations(_load(path_a), kind)
    reviewer_b = _index_annotations(_load(path_b), kind)
    if set(reviewer_a) != set(reviewer_b):
        raise ValueError(f"{kind} reviewer audit IDs differ")
    audit_ids = sorted(reviewer_a)
    unknown = sorted(set(audit_ids) - set(mapping))
    if unknown:
        raise ValueError(f"unknown mapped audit IDs: {unknown}")
    fields = RESPONSE_FIELDS if kind == "response" else PROMPT_FIELDS
    field_reports = [
        _field_report(audit_ids, reviewer_a, reviewer_b, field) for field in fields
    ]
    primary_field = "response_label" if kind == "response" else "goal_alignment"
    primary = next(report for report in field_reports if report["field"] == primary_field)
    disagreements = []
    for audit_id in primary["disagreement_ids"]:
        meta = mapping[audit_id]
        disagreements.append(
            {
                "audit_id": audit_id,
                "reviewer_1": reviewer_a[audit_id].get(primary_field),
                "reviewer_2": reviewer_b[audit_id].get(primary_field),
                "example_id": meta.get("example_id"),
                "candidate_id": meta.get("candidate_id"),
                "operator": meta.get("operator"),
                "removed_character_fraction": meta.get("removed_character_fraction"),
            }
        )
    return {
        "kind": kind,
        "item_count": len(audit_ids),
        "field_reports": field_reports,
        "primary_disagreements": disagreements,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--response-reviewer-1", type=Path, required=True)
    parser.add_argument("--response-reviewer-2", type=Path, required=True)
    parser.add_argument("--prompt-reviewer-1", type=Path, required=True)
    parser.add_argument("--prompt-reviewer-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    mapping = _load(args.mapping)
    report = {
        "schema_version": "phase1-step8-agreement-v1",
        "paper_validity": False,
        "requires_adjudication": True,
        "response": _kind_report(
            "response",
            args.response_reviewer_1,
            args.response_reviewer_2,
            mapping,
        ),
        "prompt_validity": _kind_report(
            "prompt",
            args.prompt_reviewer_1,
            args.prompt_reviewer_2,
            mapping,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
