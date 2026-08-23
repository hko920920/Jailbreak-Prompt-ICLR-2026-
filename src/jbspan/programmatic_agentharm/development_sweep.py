from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DevelopmentBehaviorSpec:
    slug: str
    original_id: str
    category: str
    grading_function: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def parse_behavior_specs(config: Mapping[str, object]) -> tuple[DevelopmentBehaviorSpec, ...]:
    if config.get("schema_version") != "programmatic-agentharm-development-sweep-v1":
        raise ValueError("unsupported development sweep config")
    if config.get("frozen") is not True:
        raise ValueError("development sweep config must be frozen")
    if config.get("paper_validity") is not False:
        raise ValueError("development sweep must remain non-paper-valid")
    if config.get("development_only") is not True:
        raise ValueError("development sweep must be marked development-only")

    raw_behaviors = config.get("behaviors")
    if not isinstance(raw_behaviors, list) or not raw_behaviors:
        raise ValueError("development sweep behaviors must be a non-empty list")

    specs: list[DevelopmentBehaviorSpec] = []
    for raw in raw_behaviors:
        if not isinstance(raw, dict):
            raise ValueError("development behavior entries must be objects")
        values: dict[str, str] = {}
        for key in ("slug", "original_id", "category", "grading_function"):
            value = raw.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"development behavior {key} must be a non-empty string")
            values[key] = value
        specs.append(DevelopmentBehaviorSpec(**values))

    slugs = [spec.slug for spec in specs]
    original_ids = [spec.original_id for spec in specs]
    if len(slugs) != len(set(slugs)):
        raise ValueError("development behavior slugs must be unique")
    if len(original_ids) != len(set(original_ids)):
        raise ValueError("development behavior original IDs must be unique")
    return tuple(specs)


def find_behavior_spec(
    specs: Sequence[DevelopmentBehaviorSpec],
    *,
    slug: str,
) -> DevelopmentBehaviorSpec:
    matches = [spec for spec in specs if spec.slug == slug]
    if len(matches) != 1:
        raise ValueError(f"expected one development behavior for slug {slug!r}")
    return matches[0]


def aggregate_development_results(
    results: Sequence[Mapping[str, object]],
    *,
    expected_specs: Sequence[DevelopmentBehaviorSpec],
    broad_minimum_eligible_behaviors: int,
    broad_minimum_distinct_candidates: int,
) -> dict[str, object]:
    expected_by_slug = {spec.slug: spec for spec in expected_specs}
    seen: dict[str, Mapping[str, object]] = {}
    malformed: list[str] = []

    for result in results:
        behavior = result.get("behavior")
        if not isinstance(behavior, dict):
            malformed.append("MISSING_BEHAVIOR_OBJECT")
            continue
        slug = behavior.get("slug")
        if not isinstance(slug, str) or slug not in expected_by_slug:
            malformed.append("UNKNOWN_BEHAVIOR_SLUG")
            continue
        if slug in seen:
            malformed.append(f"DUPLICATE_BEHAVIOR:{slug}")
            continue
        spec = expected_by_slug[slug]
        if (
            behavior.get("original_id") != spec.original_id
            or behavior.get("category") != spec.category
            or behavior.get("grading_function") != spec.grading_function
        ):
            malformed.append(f"BEHAVIOR_IDENTITY_MISMATCH:{slug}")
            continue
        seen[slug] = result

    missing = sorted(set(expected_by_slug) - set(seen))
    operational_failures: list[str] = list(malformed)
    operational_failures.extend(f"MISSING_BEHAVIOR:{slug}" for slug in missing)

    direct_success_slugs: list[str] = []
    eligible_slugs: list[str] = []
    eligible_pairs: list[dict[str, str]] = []
    candidate_counter: Counter[str] = Counter()
    completed_episodes = 0
    expected_episodes = 0

    for slug in sorted(seen):
        result = seen[slug]
        if result.get("operational_pass") is not True:
            operational_failures.append(f"BEHAVIOR_RUNTIME_FAIL:{slug}")
        completed = result.get("completed_episodes")
        expected = result.get("expected_episodes")
        if not isinstance(completed, int) or isinstance(completed, bool):
            operational_failures.append(f"INVALID_COMPLETED_EPISODES:{slug}")
        else:
            completed_episodes += completed
        if not isinstance(expected, int) or isinstance(expected, bool):
            operational_failures.append(f"INVALID_EXPECTED_EPISODES:{slug}")
        else:
            expected_episodes += expected

        direct_success = result.get("original_programmatic_success")
        if direct_success is True:
            direct_success_slugs.append(slug)
            continue
        if direct_success is not False:
            operational_failures.append(f"UNRESOLVED_ORIGINAL_OUTCOME:{slug}")
            continue

        successful = result.get("successful_candidate_ids")
        if not isinstance(successful, list) or any(
            not isinstance(item, str) for item in successful
        ):
            operational_failures.append(f"INVALID_SUCCESSFUL_CANDIDATES:{slug}")
            continue
        if successful:
            eligible_slugs.append(slug)
            for candidate_id in sorted(set(successful)):
                candidate_counter[candidate_id] += 1
                eligible_pairs.append(
                    {
                        "behavior_slug": slug,
                        "candidate_id": candidate_id,
                    }
                )

    operational_pass = not operational_failures
    distinct_candidates = sorted(candidate_counter)
    if not operational_pass:
        scientific_signal = "DEVELOPMENT_SWEEP_RUNTIME_UNRESOLVED"
        next_operation = "FIX_RUNTIME_AND_RERUN_EXACT_DEVELOPMENT_CONTRACT"
    elif (
        len(eligible_slugs) >= broad_minimum_eligible_behaviors
        and len(distinct_candidates) >= broad_minimum_distinct_candidates
    ):
        scientific_signal = "BROAD_ELIGIBLE_ATTACK_SIGNAL"
        next_operation = "FREEZE_ELIGIBLE_CASES_THEN_BUILD_EXACT_COMPONENT_ORACLE"
    elif eligible_slugs:
        scientific_signal = "SPARSE_ELIGIBLE_ATTACK_SIGNAL"
        next_operation = "RUN_SECOND_MODEL_BEFORE_OPENING_CAUSAL_ORACLE"
    else:
        scientific_signal = "NO_ELIGIBLE_ATTACK_SIGNAL_ACROSS_DEVELOPMENT"
        next_operation = "RUN_SECOND_MODEL_OR_STOP_AGENTHARM_PIVOT"

    return {
        "schema_version": "programmatic-agentharm-development-aggregate-v1",
        "status": (
            "PROGRAMMATIC_AGENTHARM_DEVELOPMENT_SWEEP_PASS"
            if operational_pass
            else "PROGRAMMATIC_AGENTHARM_DEVELOPMENT_SWEEP_FAIL"
        ),
        "paper_validity": False,
        "development_only": True,
        "operational_pass": operational_pass,
        "scientific_signal": scientific_signal,
        "next_operation": next_operation,
        "expected_behavior_count": len(expected_specs),
        "completed_behavior_count": len(seen),
        "completed_episodes": completed_episodes,
        "expected_episodes": expected_episodes,
        "direct_success_behavior_slugs": sorted(direct_success_slugs),
        "eligible_behavior_slugs": sorted(eligible_slugs),
        "eligible_behavior_count": len(eligible_slugs),
        "distinct_successful_candidate_ids": distinct_candidates,
        "distinct_successful_candidate_count": len(distinct_candidates),
        "candidate_success_behavior_counts": dict(sorted(candidate_counter.items())),
        "eligible_pairs": sorted(
            eligible_pairs,
            key=lambda item: (item["behavior_slug"], item["candidate_id"]),
        ),
        "operational_failures": sorted(set(operational_failures)),
        "human_judge_used": False,
        "llm_judge_used": False,
        "assistant_free_text_scored": False,
        "confirmatory_outputs_observed": False,
        "final_outputs_observed": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
