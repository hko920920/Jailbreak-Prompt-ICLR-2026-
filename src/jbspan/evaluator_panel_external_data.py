from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WHITESPACE_RE = re.compile(r"\s+")
_Key = TypeVar("_Key")


class HumanBinaryLabel(str, Enum):
    SAFE = "SAFE"
    HARMFUL = "HARMFUL"


class ExternalPartition(str, Enum):
    CALIBRATION = "calibration"
    HELDOUT = "heldout"


class ExclusionReason(str, Enum):
    SOURCE_PAIR_LABEL_CONFLICT = "SOURCE_PAIR_LABEL_CONFLICT"
    SOURCE_PAIR_DUPLICATE = "SOURCE_PAIR_DUPLICATE"
    SOURCE_RESPONSE_LABEL_CONFLICT = "SOURCE_RESPONSE_LABEL_CONFLICT"
    SOURCE_RESPONSE_DUPLICATE = "SOURCE_RESPONSE_DUPLICATE"
    CROSS_SOURCE_RESPONSE_OVERLAP = "CROSS_SOURCE_RESPONSE_OVERLAP"


@dataclass(frozen=True, slots=True)
class ExternalHumanRecord:
    """In-memory source record.

    Goal and response text are converted to digests before this object is
    constructed. ``source_locator`` is retained only to recover the selected
    row from an ignored raw cache; safe manifests store only its digest.
    """

    source_id: str
    source_locator: str
    behavior_group_sha256: str
    response_sha256: str
    human_label: HumanBinaryLabel
    human_annotation_count: int
    human_label_support_count: int
    strata: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_locator:
            raise ValueError("source identity and locator must be nonempty")
        _validate_sha256(self.behavior_group_sha256, "behavior_group_sha256")
        _validate_sha256(self.response_sha256, "response_sha256")
        if isinstance(self.human_annotation_count, bool):
            raise ValueError("human_annotation_count must be an integer")
        if self.human_annotation_count <= 0:
            raise ValueError("human_annotation_count must be positive")
        if isinstance(self.human_label_support_count, bool):
            raise ValueError("human_label_support_count must be an integer")
        if not 0 < self.human_label_support_count <= self.human_annotation_count:
            raise ValueError("human label support must be within the annotation count")
        if not self.strata or any(not value for value in self.strata):
            raise ValueError("at least one nonempty reporting stratum is required")

    @property
    def pair_sha256(self) -> str:
        return pair_sha256(
            behavior_group_sha256=self.behavior_group_sha256,
            response_sha256=self.response_sha256,
        )

    @property
    def record_id(self) -> str:
        material = f"{self.source_id}\0{self.pair_sha256}".encode()
        return hashlib.sha256(material).hexdigest()

    @property
    def source_locator_sha256(self) -> str:
        material = f"{self.source_id}\0{self.source_locator}".encode()
        return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True, slots=True)
class ExclusionAudit:
    reason: ExclusionReason
    source_id: str
    excluded_record_count: int
    affected_group_count: int


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    admitted_records: tuple[ExternalHumanRecord, ...]
    exclusions: tuple[ExclusionAudit, ...]


def normalize_external_text(text: str) -> str:
    """Apply the frozen leakage-audit normalization."""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip().casefold()
    if not normalized:
        raise ValueError("external source text must be nonempty after normalization")
    return normalized


def normalized_text_sha256(text: str) -> str:
    return hashlib.sha256(normalize_external_text(text).encode("utf-8")).hexdigest()


def pair_sha256(*, behavior_group_sha256: str, response_sha256: str) -> str:
    _validate_sha256(behavior_group_sha256, "behavior_group_sha256")
    _validate_sha256(response_sha256, "response_sha256")
    material = f"{behavior_group_sha256}\0{response_sha256}".encode()
    return hashlib.sha256(material).hexdigest()


def behavior_partition(
    behavior_group_sha256: str,
    *,
    seed: str,
) -> ExternalPartition:
    """Split a whole normalized behavior group using the first SHA-256 64 bits."""

    _validate_sha256(behavior_group_sha256, "behavior_group_sha256")
    if not seed:
        raise ValueError("split seed must be nonempty")
    digest = hashlib.sha256(f"{seed}|{behavior_group_sha256}".encode()).hexdigest()
    if int(digest[:16], 16) % 2 == 0:
        return ExternalPartition.CALIBRATION
    return ExternalPartition.HELDOUT


def deduplicate_external_records(
    records: Sequence[ExternalHumanRecord],
) -> DeduplicationResult:
    """Apply the frozen pair, response, and cross-source overlap policy.

    The policy first collapses duplicate prompt-response pairs within a
    source, then collapses repeated normalized responses within a source, and
    finally excludes every response digest appearing in multiple sources.
    Any within-source label conflict excludes the full conflicting group.
    """

    row_counts: Counter[tuple[ExclusionReason, str]] = Counter()
    group_counts: Counter[tuple[ExclusionReason, str]] = Counter()

    pair_groups: defaultdict[tuple[str, str], list[ExternalHumanRecord]] = defaultdict(
        list
    )
    for record in records:
        pair_groups[(record.source_id, record.pair_sha256)].append(record)

    after_pairs: list[ExternalHumanRecord] = []
    for group in _ordered_groups(pair_groups):
        labels = {record.human_label for record in group}
        if len(labels) != 1:
            _record_exclusion(
                group,
                ExclusionReason.SOURCE_PAIR_LABEL_CONFLICT,
                row_counts,
                group_counts,
            )
            continue
        ordered = sorted(group, key=_representative_key)
        after_pairs.append(ordered[0])
        if len(ordered) > 1:
            _record_exclusion(
                ordered[1:],
                ExclusionReason.SOURCE_PAIR_DUPLICATE,
                row_counts,
                group_counts,
            )

    response_groups: defaultdict[
        tuple[str, str], list[ExternalHumanRecord]
    ] = defaultdict(list)
    for record in after_pairs:
        response_groups[(record.source_id, record.response_sha256)].append(record)

    after_source_responses: list[ExternalHumanRecord] = []
    for group in _ordered_groups(response_groups):
        labels = {record.human_label for record in group}
        if len(labels) != 1:
            _record_exclusion(
                group,
                ExclusionReason.SOURCE_RESPONSE_LABEL_CONFLICT,
                row_counts,
                group_counts,
            )
            continue
        ordered = sorted(group, key=_representative_key)
        after_source_responses.append(ordered[0])
        if len(ordered) > 1:
            _record_exclusion(
                ordered[1:],
                ExclusionReason.SOURCE_RESPONSE_DUPLICATE,
                row_counts,
                group_counts,
            )

    cross_source_groups: defaultdict[str, list[ExternalHumanRecord]] = defaultdict(list)
    for record in after_source_responses:
        cross_source_groups[record.response_sha256].append(record)

    admitted: list[ExternalHumanRecord] = []
    for group in _ordered_groups(cross_source_groups):
        if len({record.source_id for record in group}) > 1:
            _record_exclusion(
                group,
                ExclusionReason.CROSS_SOURCE_RESPONSE_OVERLAP,
                row_counts,
                group_counts,
            )
        else:
            admitted.extend(group)

    admitted.sort(
        key=lambda record: (
            record.source_id,
            record.behavior_group_sha256,
            record.response_sha256,
            record.source_locator,
        )
    )
    audits = tuple(
        ExclusionAudit(
            reason=reason,
            source_id=source_id,
            excluded_record_count=row_counts[(reason, source_id)],
            affected_group_count=group_counts[(reason, source_id)],
        )
        for reason, source_id in sorted(
            row_counts,
            key=lambda item: (item[0].value, item[1]),
        )
    )
    return DeduplicationResult(tuple(admitted), audits)


def safe_manifest_record(
    record: ExternalHumanRecord,
    *,
    split_seed: str,
) -> dict[str, object]:
    partition = behavior_partition(record.behavior_group_sha256, seed=split_seed)
    return {
        "schema_version": "jbspan-e0b-external-human-label-record-v1",
        "record_id": record.record_id,
        "source_id": record.source_id,
        "source_locator_sha256": record.source_locator_sha256,
        "behavior_group_sha256": record.behavior_group_sha256,
        "response_sha256": record.response_sha256,
        "human_label": record.human_label.value,
        "human_annotation_count": record.human_annotation_count,
        "human_label_support_count": record.human_label_support_count,
        "human_unanimous": (
            record.human_label_support_count == record.human_annotation_count
        ),
        "partition": partition.value,
        "strata": list(record.strata),
    }


def sealed_heldout_identity_record(
    record: ExternalHumanRecord,
    *,
    split_seed: str,
) -> dict[str, object]:
    """Emit held-out identity and partition data without its human label."""

    safe = safe_manifest_record(record, split_seed=split_seed)
    if safe["partition"] != ExternalPartition.HELDOUT.value:
        raise ValueError("sealed heldout identity requires a heldout record")
    for field in (
        "human_label",
        "human_annotation_count",
        "human_label_support_count",
        "human_unanimous",
    ):
        del safe[field]
    safe["schema_version"] = "jbspan-e0b-external-heldout-identity-v1"
    safe["human_label_sealed"] = True
    return safe


def _validate_sha256(value: str, field: str) -> None:
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _representative_key(record: ExternalHumanRecord) -> tuple[int, str, str]:
    return (
        -record.human_annotation_count,
        record.behavior_group_sha256,
        record.source_locator,
    )


def _ordered_groups(
    groups: Mapping[_Key, list[ExternalHumanRecord]],
) -> Iterable[list[ExternalHumanRecord]]:
    for key in sorted(groups, key=str):
        yield groups[key]


def _record_exclusion(
    records: Sequence[ExternalHumanRecord],
    reason: ExclusionReason,
    row_counts: Counter[tuple[ExclusionReason, str]],
    group_counts: Counter[tuple[ExclusionReason, str]],
) -> None:
    for record in records:
        row_counts[(reason, record.source_id)] += 1
    for source_id in {record.source_id for record in records}:
        group_counts[(reason, source_id)] += 1
