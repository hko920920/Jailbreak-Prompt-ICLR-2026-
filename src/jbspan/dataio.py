from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jbspan.schemas import PromptPair

_REQUIRED_STRING_FIELDS = (
    "id",
    "behavior",
    "original_prompt",
    "jailbreak_prompt",
    "attack_family",
)


@dataclass(frozen=True)
class DatasetIssue:
    code: str
    line: int | None
    detail: str


class DatasetValidationError(ValueError):
    def __init__(self, issues: tuple[DatasetIssue, ...]) -> None:
        self.issues = issues
        summary = "; ".join(
            f"{issue.code}@{issue.line if issue.line is not None else '-'}: {issue.detail}"
            for issue in issues[:10]
        )
        if len(issues) > 10:
            summary += f"; ... {len(issues) - 10} more"
        super().__init__(summary)


@dataclass(frozen=True)
class DatasetManifest:
    source_path: str
    source_sha256: str
    example_count: int
    ids_sha256: str
    attack_family_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_prompt_pairs(path: Path, *, redact_errors: bool = True) -> tuple[PromptPair, ...]:
    """Load and strictly validate paired original/jailbreak examples from JSONL.

    The default error mode never includes raw prompt text. This keeps malformed
    datasets from leaking sensitive examples into CI logs or exception traces.
    """

    issues: list[DatasetIssue] = []
    pairs: list[PromptPair] = []
    seen_ids: set[str] = set()

    if not path.is_file():
        raise DatasetValidationError((DatasetIssue("FILE_NOT_FOUND", None, str(path)),))

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            issues.append(
                DatasetIssue(
                    "INVALID_JSON",
                    line_number,
                    f"column {exc.colno}" if redact_errors else exc.msg,
                )
            )
            continue

        if not isinstance(payload, dict):
            issues.append(
                DatasetIssue("NOT_AN_OBJECT", line_number, "JSON value must be an object")
            )
            continue

        invalid = False
        values: dict[str, str] = {}
        for field_name in _REQUIRED_STRING_FIELDS:
            value = payload.get(field_name)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    DatasetIssue(
                        "INVALID_REQUIRED_FIELD",
                        line_number,
                        field_name,
                    )
                )
                invalid = True
            else:
                values[field_name] = value

        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            issues.append(
                DatasetIssue("INVALID_METADATA", line_number, "metadata must be an object")
            )
            invalid = True

        if invalid:
            continue

        example_id = values["id"]
        if example_id in seen_ids:
            issues.append(DatasetIssue("DUPLICATE_ID", line_number, example_id))
            continue
        seen_ids.add(example_id)

        try:
            pairs.append(
                PromptPair(
                    id=example_id,
                    behavior=values["behavior"],
                    original_prompt=values["original_prompt"],
                    jailbreak_prompt=values["jailbreak_prompt"],
                    attack_family=values["attack_family"],
                    metadata=dict(metadata),
                )
            )
        except ValueError as exc:
            detail = "PromptPair validation failed" if redact_errors else str(exc)
            issues.append(DatasetIssue("PAIR_VALIDATION_FAILED", line_number, detail))

    if not pairs and not issues:
        issues.append(DatasetIssue("EMPTY_DATASET", None, "no JSONL records found"))
    if issues:
        raise DatasetValidationError(tuple(issues))
    return tuple(pairs)


def build_dataset_manifest(path: Path, pairs: tuple[PromptPair, ...]) -> DatasetManifest:
    source_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical_ids = "\n".join(sorted(pair.id for pair in pairs)).encode("utf-8")
    family_counts = dict(sorted(Counter(pair.attack_family for pair in pairs).items()))
    return DatasetManifest(
        source_path=str(path),
        source_sha256=source_digest,
        example_count=len(pairs),
        ids_sha256=hashlib.sha256(canonical_ids).hexdigest(),
        attack_family_counts=family_counts,
    )


def write_dataset_manifest(path: Path, manifest: DatasetManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
