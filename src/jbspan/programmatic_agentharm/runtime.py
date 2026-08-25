from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from jbspan.programmatic_agentharm.contract import BehaviorRecord, load_behavior_records


@dataclass(frozen=True)
class OperationalEpisode:
    episode_id: str
    condition: str
    behavior_id: str
    original_id: str
    category: str
    grading_function: str
    detailed_prompt: bool
    hint_included: bool
    candidate_id: str | None
    payload_sha256: str
    prompt_sha256: str
    payload_character_start: int
    payload_character_end: int

    def to_dict(self) -> dict[str, object]:
        return dict(asdict(self))


@dataclass(frozen=True)
class OperationalDecision:
    status: str
    completed_episodes: int
    expected_episodes: int
    score_coverage: float
    forced_first_tool_calls: int
    original_success: bool | None
    attacked_success: bool | None
    operational_pass: bool
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return dict(asdict(self))


def canonical_validation_record(
    payload: dict[str, object],
    *,
    eligible_graders: set[str],
    detailed_prompt: bool,
    hint_included: bool,
    fallback_seed: str,
) -> BehaviorRecord:
    records = tuple(
        record
        for record in load_behavior_records(payload)
        if record.grading_function in eligible_graders
    )
    if not records:
        raise ValueError("no programmatic AgentHarm validation record")
    exact = [
        record
        for record in records
        if record.detailed_prompt is detailed_prompt
        and record.hint_included is hint_included
    ]
    candidates = exact or list(records)
    return min(
        candidates,
        key=lambda record: (
            hashlib.sha256(
                "\0".join(
                    (
                        fallback_seed,
                        record.category,
                        record.original_id,
                        record.behavior_id,
                    )
                ).encode()
            ).hexdigest(),
            record.behavior_id,
        ),
    )


def strict_boolean_criteria(value: object) -> dict[str, bool]:
    if not isinstance(value, dict) or not value:
        raise ValueError("programmatic grader must return a non-empty object")
    result: dict[str, bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("programmatic grader criterion names must be strings")
        if not isinstance(item, bool):
            raise ValueError("programmatic grader values must be strict booleans")
        result[key] = item
    return result


def trace_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decide_operational_smoke(
    records: list[dict[str, Any]],
    *,
    expected_episodes: int,
    minimum_coverage: float,
    forced_first_minimum_tool_calls: int,
) -> OperationalDecision:
    by_condition = {
        str(item.get("condition")): item
        for item in records
        if item.get("completed") is True
    }
    completed = len(by_condition)
    scored = sum(item.get("programmatic_score_parsed") is True for item in by_condition.values())
    coverage = scored / expected_episodes if expected_episodes else 0.0
    forced = by_condition.get("forced_first_probe", {})
    forced_calls = int(forced.get("tool_call_count", 0))
    failures: list[str] = []
    if completed < expected_episodes:
        failures.append("INCOMPLETE_EPISODES")
    if coverage < minimum_coverage:
        failures.append("PROGRAMMATIC_SCORE_COVERAGE_FAIL")
    if forced_calls < forced_first_minimum_tool_calls:
        failures.append("FORCED_FIRST_TOOL_PATH_FAIL")
    original = by_condition.get("original_auto")
    attacked = by_condition.get("attacked_auto")
    return OperationalDecision(
        status="PROGRAMMATIC_AGENTHARM_RUNTIME_SMOKE_PASS"
        if not failures
        else "PROGRAMMATIC_AGENTHARM_RUNTIME_SMOKE_FAIL",
        completed_episodes=completed,
        expected_episodes=expected_episodes,
        score_coverage=coverage,
        forced_first_tool_calls=forced_calls,
        original_success=(
            bool(original["programmatic_success"])
            if original is not None and "programmatic_success" in original
            else None
        ),
        attacked_success=(
            bool(attacked["programmatic_success"])
            if attacked is not None and "programmatic_success" in attacked
            else None
        ),
        operational_pass=not failures,
        failures=tuple(failures),
    )
