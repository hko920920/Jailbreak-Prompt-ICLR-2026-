from __future__ import annotations

import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path

from inspect_ai.dataset import Sample
from inspect_evals.agentharm.utils import load_dataset

from jbspan.programmatic_agentharm.development_sweep import (
    DevelopmentBehaviorSpec,
    find_behavior_spec,
    parse_behavior_specs,
)
from run_programmatic_agentharm_smoke import (
    as_array,
    as_object,
    as_string,
    load_attack,
    load_json,
    run_episode,
    safe_episode,
    sha256_text,
    validate_contract,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run all frozen jailbreak candidates on one predeclared development-only "
            "AgentHarm behavior. Only safe hashes and aggregate outcomes are written."
        )
    )
    value.add_argument(
        "--development-config",
        type=Path,
        default=Path("configs/programmatic_agentharm/development_behavior_sweep.json"),
    )
    value.add_argument("--behavior-slug", required=True)
    value.add_argument("--attack-source-csv", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--root", type=Path, default=Path("."))
    return value


def _select_sample(
    *,
    spec: DevelopmentBehaviorSpec,
    detailed_prompt: bool,
    hint_included: bool,
) -> Sample:
    dataset = load_dataset("harmful", "test_public", force_redownload=False)
    matches: list[Sample] = []
    exact: list[Sample] = []
    for sample in dataset:
        metadata = sample.metadata or {}
        if (
            str(metadata.get("id_original", "")) != spec.original_id
            or str(metadata.get("grading_function", "")) != spec.grading_function
            or str(metadata.get("category", "")) != spec.category
        ):
            continue
        matches.append(sample)
        if (
            metadata.get("detailed_prompt") is detailed_prompt
            and metadata.get("hint_included") is hint_included
        ):
            exact.append(sample)
    if len(matches) != 4:
        raise RuntimeError(
            f"expected four AgentHarm rows for {spec.slug}, found {len(matches)}"
        )
    if len(exact) != 1:
        raise RuntimeError(
            f"expected one canonical AgentHarm row for {spec.slug}, found {len(exact)}"
        )
    return exact[0]


def _validate_source_assignment(
    *,
    manifest: dict[str, object],
    spec: DevelopmentBehaviorSpec,
    consumed_split: str,
) -> None:
    raw_assignments = as_array(manifest["split_assignments"], where="split_assignments")
    matches: list[dict[str, object]] = []
    for raw in raw_assignments:
        assignment = as_object(raw, where="split assignment")
        if str(assignment.get("original_id", "")) == spec.original_id:
            matches.append(assignment)
    if len(matches) != 1:
        raise RuntimeError(f"expected one frozen split assignment for {spec.slug}")
    assignment = matches[0]
    if (
        assignment.get("split") != consumed_split
        or assignment.get("category") != spec.category
        or assignment.get("grading_function") != spec.grading_function
        or assignment.get("row_count") != 4
    ):
        raise RuntimeError(f"frozen split assignment mismatch for {spec.slug}")


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    development = load_json(args.development_config.resolve())
    specs = parse_behavior_specs(development)
    spec = find_behavior_spec(specs, slug=args.behavior_slug)

    runtime_path = root / as_string(
        development["runtime_config_path"], where="runtime_config_path"
    )
    runtime = load_json(runtime_path)
    manifest, eligible_graders = validate_contract(root, runtime)
    if spec.grading_function not in eligible_graders:
        raise RuntimeError(f"grader is not programmatically eligible: {spec.grading_function}")

    provenance = as_object(development["provenance"], where="provenance")
    if provenance.get("gate0_manifest_identity_sha256") != manifest.get(
        "manifest_identity_sha256"
    ):
        raise RuntimeError("Gate 0 manifest identity differs from development contract")
    consumed_split = as_string(
        provenance["consumed_source_split"], where="provenance.consumed_source_split"
    )
    if consumed_split != "confirmatory":
        raise RuntimeError("development sweep must consume only the former confirmatory split")
    if provenance.get("consumed_behaviors_future_confirmatory_use_forbidden") is not True:
        raise RuntimeError("consumed behaviors must be permanently excluded from confirmation")
    _validate_source_assignment(
        manifest=manifest,
        spec=spec,
        consumed_split=consumed_split,
    )

    variant = as_object(development["canonical_variant"], where="canonical_variant")
    sample = _select_sample(
        spec=spec,
        detailed_prompt=bool(variant["detailed_prompt"]),
        hint_included=bool(variant["hint_included"]),
    )
    if not isinstance(sample.input, str):
        raise RuntimeError("AgentHarm behavior input must be a string")
    payload = sample.input
    payload_sha256 = sha256_text(payload)
    metadata = sample.metadata or {}

    runtime_attack = as_object(runtime["attack_programs"], where="attack_programs")
    frozen_candidates = [
        as_string(item, where="runtime selected candidate")
        for item in as_array(
            runtime_attack["selected_candidate_ids"],
            where="attack_programs.selected_candidate_ids",
        )
    ]
    configured_candidates = [
        as_string(item, where="development candidate")
        for item in as_array(development["candidate_ids"], where="candidate_ids")
    ]
    if configured_candidates != frozen_candidates:
        raise RuntimeError("development candidates differ from frozen runtime selection")

    logs = Path(tempfile.mkdtemp(prefix=f"jbspan-agentharm-dev-{spec.slug}-"))
    episodes: list[dict[str, object]] = []
    node_counts: dict[str, int] = {}
    try:
        original = run_episode(
            sample=sample,
            condition="original_auto",
            prompt=payload,
            tool_choice="auto",
            config=runtime,
            inspect_logs=logs / "original_auto",
        )
        episodes.append(
            safe_episode(
                record=original,
                condition="original_auto",
                prompt=payload,
                candidate_id=None,
                payload_sha256=payload_sha256,
                payload_start=0,
                payload_end=len(payload),
            )
        )

        for candidate_id in configured_candidates:
            candidate_runtime = copy.deepcopy(runtime)
            smoke = as_object(
                candidate_runtime["operational_smoke"], where="operational_smoke"
            )
            smoke["attack_candidate_id"] = candidate_id
            attack_prompt, attack_start, attack_end, node_count = load_attack(
                root=root,
                config=candidate_runtime,
                attack_source_csv=args.attack_source_csv.resolve(),
                payload=payload,
            )
            node_counts[candidate_id] = node_count
            condition = f"attacked_auto__{candidate_id}"
            attacked = run_episode(
                sample=sample,
                condition=condition,
                prompt=attack_prompt,
                tool_choice="auto",
                config=candidate_runtime,
                inspect_logs=logs / condition,
            )
            episodes.append(
                safe_episode(
                    record=attacked,
                    condition=condition,
                    prompt=attack_prompt,
                    candidate_id=candidate_id,
                    payload_sha256=payload_sha256,
                    payload_start=attack_start,
                    payload_end=attack_end,
                )
            )
    finally:
        shutil.rmtree(logs, ignore_errors=True)

    expected = 1 + len(configured_candidates)
    completed = sum(item.get("completed") is True for item in episodes)
    scored = sum(item.get("programmatic_score_parsed") is True for item in episodes)
    original_episode = episodes[0]
    original_success = (
        bool(original_episode["programmatic_success"])
        if original_episode.get("programmatic_score_parsed") is True
        else None
    )
    successful_candidates = [
        str(item["candidate_id"])
        for item in episodes[1:]
        if item.get("programmatic_score_parsed") is True
        and item.get("programmatic_success") is True
    ]
    operational_pass = completed == expected and scored == expected
    if not operational_pass:
        scientific_signal = "BEHAVIOR_RUNTIME_UNRESOLVED"
    elif original_success is True:
        scientific_signal = "DIRECT_TASK_ALREADY_SUCCESSFUL"
    elif successful_candidates:
        scientific_signal = "ELIGIBLE_CANDIDATE_FOUND"
    else:
        scientific_signal = "NO_ELIGIBLE_CANDIDATE_ON_BEHAVIOR"

    candidate_results = [
        {
            "candidate_id": item["candidate_id"],
            "node_count": node_counts[str(item["candidate_id"])],
            "completed": item["completed"],
            "programmatic_score_parsed": item["programmatic_score_parsed"],
            "programmatic_success": item["programmatic_success"],
            "tool_call_count": item["tool_call_count"],
            "tool_response_count": item["tool_response_count"],
            "criteria": item.get("criteria"),
            "criteria_sha256": item.get("criteria_sha256"),
            "prompt_sha256": item["prompt_sha256"],
            "prompt_character_length": item["prompt_character_length"],
            "payload_character_start": item["payload_character_start"],
            "payload_character_end": item["payload_character_end"],
        }
        for item in episodes[1:]
    ]

    output: dict[str, object] = {
        "schema_version": "programmatic-agentharm-development-behavior-result-v1",
        "status": (
            "PROGRAMMATIC_AGENTHARM_DEVELOPMENT_BEHAVIOR_PASS"
            if operational_pass
            else "PROGRAMMATIC_AGENTHARM_DEVELOPMENT_BEHAVIOR_FAIL"
        ),
        "paper_validity": False,
        "development_only": True,
        "scientific_signal": scientific_signal,
        "operational_pass": operational_pass,
        "completed_episodes": completed,
        "expected_episodes": expected,
        "programmatic_score_coverage": scored / expected,
        "original_programmatic_success": original_success,
        "original_tool_call_count": original_episode.get("tool_call_count"),
        "successful_candidate_ids": sorted(successful_candidates),
        "candidate_count": len(configured_candidates),
        "candidate_results": candidate_results,
        "behavior": spec.to_dict(),
        "selected_row": {
            "behavior_id": str(metadata.get("id", sample.id)),
            "detailed_prompt": bool(metadata.get("detailed_prompt")),
            "hint_included": bool(metadata.get("hint_included")),
            "payload_sha256": payload_sha256,
        },
        "source_split_consumed": consumed_split,
        "future_confirmatory_use_forbidden": True,
        "human_judge_used": False,
        "llm_judge_used": False,
        "assistant_free_text_scored": False,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_tool_arguments_committed": False,
        "raw_tool_responses_committed": False,
        "confirmatory_outputs_observed": False,
        "final_outputs_observed": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if operational_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
