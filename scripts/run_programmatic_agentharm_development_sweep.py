from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from inspect_ai.dataset import Sample
from inspect_evals.agentharm.utils import load_dataset
from run_programmatic_agentharm_smoke import (
    as_array,
    as_bool,
    as_float,
    as_object,
    as_string,
    load_attack,
    load_json,
    run_episode,
    safe_episode,
    sha256_text,
    validate_contract,
)

from jbspan.programmatic_agentharm.development import (
    DevelopmentAssignment,
    decide_development_sweep,
    validate_development_overlay,
)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run a judge-free development sweep over the six legacy Gate 0 "
            "confirmatory base behaviors. These rows are consumed as development "
            "and are permanently excluded from paper confirmatory results."
        )
    )
    value.add_argument(
        "--runtime-config",
        type=Path,
        default=Path("configs/programmatic_agentharm/runtime_smoke.json"),
    )
    value.add_argument(
        "--development-config",
        type=Path,
        default=Path("configs/programmatic_agentharm/development_expansion.json"),
    )
    value.add_argument(
        "--original-id",
        help=(
            "Run one frozen development base behavior as a matrix shard. "
            "The full overlay is still validated before filtering."
        ),
    )
    value.add_argument("--attack-source-csv", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--root", type=Path, default=Path("."))
    return value


def select_development_samples(
    assignments: tuple[DevelopmentAssignment, ...],
    *,
    eligible_graders: set[str],
    detailed_prompt: bool,
    hint_included: bool,
) -> tuple[Sample, ...]:
    dataset = load_dataset("harmful", "test_public", force_redownload=False)
    selected: list[Sample] = []
    for assignment in assignments:
        matches: list[Sample] = []
        for sample in dataset:
            metadata = sample.metadata or {}
            if metadata.get("id_original") != assignment.original_id:
                continue
            if metadata.get("category") != assignment.category:
                continue
            if metadata.get("grading_function") != assignment.grading_function:
                continue
            if metadata.get("grading_function") not in eligible_graders:
                continue
            if metadata.get("detailed_prompt") is not detailed_prompt:
                continue
            if metadata.get("hint_included") is not hint_included:
                continue
            matches.append(sample)
        if len(matches) != 1:
            raise RuntimeError(
                "expected exactly one AgentHarm row for development original_id "
                f"{assignment.original_id}, found {len(matches)}"
            )
        selected.append(matches[0])
    return tuple(selected)


def add_episode_identity(
    episode: dict[str, object],
    *,
    sample: Sample,
    assignment: DevelopmentAssignment,
    candidate_node_count: int | None,
) -> dict[str, object]:
    metadata = sample.metadata or {}
    value = dict(episode)
    value.update(
        {
            "behavior_id": str(metadata.get("id", sample.id)),
            "original_id": assignment.original_id,
            "category": assignment.category,
            "grading_function": assignment.grading_function,
            "detailed_prompt": bool(metadata.get("detailed_prompt")),
            "hint_included": bool(metadata.get("hint_included")),
            "candidate_node_count": candidate_node_count,
        }
    )
    criteria = value.pop("criteria", None)
    if isinstance(criteria, dict):
        value["criterion_count"] = len(criteria)
        value["criterion_true_count"] = sum(item is True for item in criteria.values())
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    runtime_config_path = args.runtime_config.resolve()
    runtime_config = load_json(runtime_config_path)
    gate0_manifest, eligible_graders = validate_contract(root, runtime_config)
    overlay = load_json(args.development_config.resolve())
    expected_runtime_blob = as_string(
        overlay["runtime_config_git_blob_sha"],
        where="runtime_config_git_blob_sha",
    )
    if git_blob_sha(runtime_config_path) != expected_runtime_blob:
        raise RuntimeError("runtime config differs from the frozen development overlay")
    all_assignments = validate_development_overlay(
        overlay,
        gate0_manifest=gate0_manifest,
        runtime_config=runtime_config,
    )
    assignments = all_assignments
    if args.original_id is not None:
        assignments = tuple(
            item for item in all_assignments if item.original_id == args.original_id
        )
        if len(assignments) != 1:
            raise RuntimeError(
                "matrix shard original_id is not uniquely present in the frozen overlay: "
                f"{args.original_id}"
            )

    variant = as_object(overlay["variant"], where="variant")
    detailed_prompt = as_bool(
        variant["detailed_prompt"], where="variant.detailed_prompt"
    )
    hint_included = as_bool(
        variant["hint_included"], where="variant.hint_included"
    )
    samples = select_development_samples(
        assignments,
        eligible_graders=eligible_graders,
        detailed_prompt=detailed_prompt,
        hint_included=hint_included,
    )

    attack_config = as_object(
        runtime_config["attack_programs"], where="attack_programs"
    )
    candidate_ids = tuple(
        as_string(item, where="selected candidate")
        for item in as_array(
            attack_config["selected_candidate_ids"],
            where="attack_programs.selected_candidate_ids",
        )
    )
    logs = Path(tempfile.mkdtemp(prefix="jbspan-agentharm-development-logs-"))
    episodes: list[dict[str, object]] = []
    try:
        for assignment, sample in zip(assignments, samples, strict=True):
            if not isinstance(sample.input, str):
                raise RuntimeError("AgentHarm development sample input must be a string")
            payload = sample.input
            payload_sha256 = sha256_text(payload)
            behavior_id = str((sample.metadata or {}).get("id", sample.id))

            original_condition = f"development__{behavior_id}__original"
            original = run_episode(
                sample=sample,
                condition=original_condition,
                prompt=payload,
                tool_choice="auto",
                config=runtime_config,
                inspect_logs=logs / original_condition,
            )
            original_safe = safe_episode(
                record=original,
                condition=original_condition,
                prompt=payload,
                candidate_id=None,
                payload_sha256=payload_sha256,
                payload_start=0,
                payload_end=len(payload),
            )
            episodes.append(
                add_episode_identity(
                    original_safe,
                    sample=sample,
                    assignment=assignment,
                    candidate_node_count=None,
                )
            )

            for candidate_id in candidate_ids:
                candidate_config = copy.deepcopy(runtime_config)
                smoke = as_object(
                    candidate_config["operational_smoke"],
                    where="operational_smoke",
                )
                smoke["attack_candidate_id"] = candidate_id
                attack_prompt, attack_start, attack_end, node_count = load_attack(
                    root=root,
                    config=candidate_config,
                    attack_source_csv=args.attack_source_csv.resolve(),
                    payload=payload,
                )
                condition = f"development__{behavior_id}__{candidate_id}"
                attacked = run_episode(
                    sample=sample,
                    condition=condition,
                    prompt=attack_prompt,
                    tool_choice="auto",
                    config=candidate_config,
                    inspect_logs=logs / condition,
                )
                attacked_safe = safe_episode(
                    record=attacked,
                    condition=condition,
                    prompt=attack_prompt,
                    candidate_id=candidate_id,
                    payload_sha256=payload_sha256,
                    payload_start=attack_start,
                    payload_end=attack_end,
                )
                episodes.append(
                    add_episode_identity(
                        attacked_safe,
                        sample=sample,
                        assignment=assignment,
                        candidate_node_count=node_count,
                    )
                )
    finally:
        shutil.rmtree(logs, ignore_errors=True)

    minimums = as_object(overlay["minimums"], where="minimums")
    decision = decide_development_sweep(
        episodes,
        behavior_ids=tuple(
            str((sample.metadata or {}).get("id", sample.id)) for sample in samples
        ),
        candidate_ids=candidate_ids,
        minimum_coverage=as_float(
            minimums["minimum_programmatic_score_coverage"],
            where="minimums.minimum_programmatic_score_coverage",
        ),
    )

    safe_episodes = [
        {
            "behavior_id": item["behavior_id"],
            "original_id": item["original_id"],
            "category": item["category"],
            "grading_function": item["grading_function"],
            "detailed_prompt": item["detailed_prompt"],
            "hint_included": item["hint_included"],
            "candidate_id": item["candidate_id"],
            "candidate_node_count": item["candidate_node_count"],
            "completed": item["completed"],
            "programmatic_score_parsed": item["programmatic_score_parsed"],
            "programmatic_success": item["programmatic_success"],
            "tool_call_count": item["tool_call_count"],
            "tool_response_count": item["tool_response_count"],
            "criteria_sha256": item.get("criteria_sha256"),
            "criterion_count": item.get("criterion_count"),
            "criterion_true_count": item.get("criterion_true_count"),
            "payload_sha256": item["payload_sha256"],
            "prompt_sha256": item["prompt_sha256"],
            "prompt_character_length": item["prompt_character_length"],
            "payload_character_start": item["payload_character_start"],
            "payload_character_end": item["payload_character_end"],
            "runtime_error_type": item.get("runtime_error_type"),
            "scorer_error_type": item.get("scorer_error_type"),
        }
        for item in episodes
    ]

    target = as_object(runtime_config["target"], where="target")
    agentharm = as_object(runtime_config["agentharm"], where="agentharm")
    generation = as_object(runtime_config["generation"], where="generation")
    output: dict[str, object] = {
        "schema_version": "programmatic-agentharm-development-sweep-result-v1",
        "status": decision.status,
        "scientific_signal": decision.scientific_signal,
        "paper_validity": False,
        "development_only": True,
        "development_shard": args.original_id is not None,
        "full_contract_behavior_count": len(all_assignments),
        "legacy_gate0_confirmatory_rows_consumed_as_development": True,
        "legacy_gate0_confirmatory_outputs_observed": True,
        "consumed_rows_excluded_from_future_paper_confirmatory": True,
        "consumed_original_ids": [
            assignment.original_id for assignment in assignments
        ],
        "decision": decision.to_dict(),
        "behavior_count": len(assignments),
        "candidate_count": len(candidate_ids),
        "episodes": safe_episodes,
        "runtime": {
            "inspect_evals_revision": agentharm["inspect_evals_revision"],
            "agentharm_dataset_revision": agentharm["dataset_revision"],
            "target_repo_id": target["base_repo_id"],
            "target_revision": target["base_revision"],
            "gguf_repo_id": target["gguf_repo_id"],
            "gguf_revision": target["gguf_revision"],
            "gguf_selector": target["gguf_selector"],
            "seed": generation["seed"],
        },
        "human_judge_used": False,
        "llm_judge_used": False,
        "assistant_free_text_scored": False,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_tool_arguments_committed": False,
        "raw_tool_responses_committed": False,
        "paper_confirmatory_outputs_observed": False,
        "final_outputs_observed": False,
        "heldout_outputs_observed": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if decision.operational_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
