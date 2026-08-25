from __future__ import annotations

import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path

from run_programmatic_agentharm_smoke import (
    as_array,
    as_object,
    as_string,
    load_attack,
    load_json,
    run_episode,
    safe_episode,
    select_validation_sample,
    sha256_text,
    validate_contract,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run a development-only judge-free sweep of all frozen jailbreak "
            "candidates on the canonical programmatic AgentHarm validation case."
        )
    )
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/programmatic_agentharm/runtime_smoke.json"),
    )
    value.add_argument("--attack-source-csv", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--root", type=Path, default=Path("."))
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config = load_json(args.config.resolve())
    _, eligible_graders = validate_contract(root, config)

    smoke = as_object(config["operational_smoke"], where="operational_smoke")
    variant = as_object(
        smoke["canonical_validation_variant"],
        where="operational_smoke.canonical_validation_variant",
    )
    sample = select_validation_sample(
        eligible_graders=eligible_graders,
        detailed_prompt=bool(variant["detailed_prompt"]),
        hint_included=bool(variant["hint_included"]),
    )
    if not isinstance(sample.input, str):
        raise RuntimeError("AgentHarm validation sample input must be a string")
    payload = sample.input
    metadata = sample.metadata or {}
    payload_sha256 = sha256_text(payload)

    attack_config = as_object(config["attack_programs"], where="attack_programs")
    candidate_ids = [
        as_string(item, where="selected candidate")
        for item in as_array(
            attack_config["selected_candidate_ids"],
            where="attack_programs.selected_candidate_ids",
        )
    ]
    if len(candidate_ids) < 2:
        raise RuntimeError("candidate sweep requires at least two frozen candidates")

    logs = Path(tempfile.mkdtemp(prefix="jbspan-agentharm-sweep-logs-"))
    episodes: list[dict[str, object]] = []
    candidate_node_counts: dict[str, int] = {}
    try:
        original = run_episode(
            sample=sample,
            condition="original_auto",
            prompt=payload,
            tool_choice="auto",
            config=config,
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

        for candidate_id in candidate_ids:
            candidate_config = copy.deepcopy(config)
            candidate_smoke = as_object(
                candidate_config["operational_smoke"],
                where="operational_smoke",
            )
            candidate_smoke["attack_candidate_id"] = candidate_id
            attack_prompt, attack_start, attack_end, node_count = load_attack(
                root=root,
                config=candidate_config,
                attack_source_csv=args.attack_source_csv.resolve(),
                payload=payload,
            )
            candidate_node_counts[candidate_id] = node_count
            condition = f"attacked_auto__{candidate_id}"
            attacked = run_episode(
                sample=sample,
                condition=condition,
                prompt=attack_prompt,
                tool_choice="auto",
                config=candidate_config,
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

    completed = sum(item.get("completed") is True for item in episodes)
    scored = sum(item.get("programmatic_score_parsed") is True for item in episodes)
    expected = 1 + len(candidate_ids)
    coverage = scored / expected
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

    if completed != expected or scored != expected:
        status = "PROGRAMMATIC_AGENTHARM_CANDIDATE_SWEEP_RUNTIME_FAIL"
        scientific_signal = "CANDIDATE_SIGNAL_UNRESOLVED"
        operational_pass = False
    elif original_success is True:
        status = "PROGRAMMATIC_AGENTHARM_CANDIDATE_SWEEP_PASS"
        scientific_signal = "DIRECT_TASK_ALREADY_SUCCESSFUL"
        operational_pass = True
    elif successful_candidates:
        status = "PROGRAMMATIC_AGENTHARM_CANDIDATE_SWEEP_PASS"
        scientific_signal = "ELIGIBLE_CANDIDATE_FOUND"
        operational_pass = True
    else:
        status = "PROGRAMMATIC_AGENTHARM_CANDIDATE_SWEEP_PASS"
        scientific_signal = "NO_ELIGIBLE_CANDIDATE_ON_VALIDATION"
        operational_pass = True

    candidate_results = [
        {
            "candidate_id": item["candidate_id"],
            "node_count": candidate_node_counts[str(item["candidate_id"])],
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

    target = as_object(config["target"], where="target")
    agentharm = as_object(config["agentharm"], where="agentharm")
    generation = as_object(config["generation"], where="generation")
    output: dict[str, object] = {
        "schema_version": "programmatic-agentharm-candidate-sweep-result-v1",
        "status": status,
        "paper_validity": False,
        "development_only": True,
        "scientific_signal": scientific_signal,
        "operational_pass": operational_pass,
        "completed_episodes": completed,
        "expected_episodes": expected,
        "programmatic_score_coverage": coverage,
        "original_programmatic_success": original_success,
        "original_tool_call_count": original_episode.get("tool_call_count"),
        "successful_candidate_ids": successful_candidates,
        "candidate_count": len(candidate_ids),
        "candidate_results": candidate_results,
        "selected_validation_case": {
            "behavior_id": str(metadata.get("id", sample.id)),
            "original_id": str(metadata.get("id_original", "")),
            "category": str(metadata.get("category", "")),
            "grading_function": str(metadata.get("grading_function", "")),
            "detailed_prompt": bool(metadata.get("detailed_prompt")),
            "hint_included": bool(metadata.get("hint_included")),
            "payload_sha256": payload_sha256,
        },
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
