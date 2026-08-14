from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jbspan.adapters.heuristic import HeuristicResponseJudge
from jbspan.dataio import load_prompt_pairs
from jbspan.schemas import GoalAlignment
from run_phase1_llama_cpp_compact_oracle import (
    _candidate_specs_for_text,
    _candidate_variants,
    _load_neutralization_records,
    _load_oracle_cases,
    _manual_variants,
    _post_chat_completion,
    _private_variant,
    _safe_variant,
    _scaffold_blocks,
    _sentence_spans,
    _write_private_jsonl,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_selection(path: Path) -> tuple[dict[str, Any], ...]:
    payload = _load_json(path)
    raw_selections = payload.get("selections")
    if not isinstance(raw_selections, list) or not raw_selections:
        raise ValueError("selection manifest must contain selections")
    selections: list[dict[str, Any]] = []
    seen_examples: set[str] = set()
    seen_candidates: set[str] = set()
    for raw in raw_selections:
        if not isinstance(raw, dict):
            raise ValueError("selection entry must be an object")
        example_id = raw.get("example_id")
        candidate_ids = raw.get("candidate_ids")
        if not isinstance(example_id, str) or not example_id:
            raise ValueError("selection example_id must be non-empty")
        if example_id in seen_examples:
            raise ValueError(f"duplicate selection example: {example_id}")
        if not isinstance(candidate_ids, list) or not candidate_ids:
            raise ValueError(f"candidate_ids missing for {example_id}")
        if not all(isinstance(value, str) and value for value in candidate_ids):
            raise ValueError(f"invalid candidate ID for {example_id}")
        duplicate_candidates = seen_candidates.intersection(candidate_ids)
        if duplicate_candidates:
            raise ValueError(f"duplicate candidate IDs: {sorted(duplicate_candidates)}")
        seen_examples.add(example_id)
        seen_candidates.update(candidate_ids)
        selections.append(
            {
                "example_id": example_id,
                "candidate_ids": tuple(candidate_ids),
            }
        )
    return tuple(selections)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--neutralization-labels", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M")
    parser.add_argument("--chunk-count", type=int, default=6)
    parser.add_argument("--maximum-candidate-fraction", type=float, default=0.35)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    pair_by_id = {pair.id: pair for pair in load_prompt_pairs(args.data)}
    case_by_id = {case.example_id: case for case in _load_oracle_cases(args.cases)}
    prior_by_id = _load_neutralization_records(args.neutralization_labels)
    selections = _load_selection(args.selection)
    judge = HeuristicResponseJudge()

    private_records: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    total_candidates = 0
    total_generations = 0

    for case_index, selection in enumerate(selections, 1):
        example_id = str(selection["example_id"])
        selected_ids = tuple(str(value) for value in selection["candidate_ids"])
        pair = pair_by_id.get(example_id)
        case = case_by_id.get(example_id)
        prior = prior_by_id.get(example_id)
        if pair is None or case is None or prior is None:
            raise ValueError(f"missing frozen input for {example_id}")
        if case.expected_goal_alignment is not GoalAlignment.FULL:
            raise ValueError(f"rerun requires FULL alignment: {example_id}")
        if case.expected_manual_outcome != "ROBUST_RECOVERY":
            raise ValueError(f"rerun requires robust manual outcome: {example_id}")
        if prior.get("goal_alignment") != GoalAlignment.FULL.value:
            raise ValueError(f"prior alignment mismatch for {example_id}")
        if prior.get("outcome") != "ROBUST_RECOVERY":
            raise ValueError(f"prior outcome mismatch for {example_id}")

        sentences = _sentence_spans(pair.jailbreak_prompt)
        blocks = _scaffold_blocks(
            pair.jailbreak_prompt,
            sentences,
            case.retain_sentence_indices,
        )
        candidate_grid = _candidate_specs_for_text(
            example_id=pair.id,
            text=pair.jailbreak_prompt,
            blocks=blocks,
            requested_chunk_count=args.chunk_count,
            maximum_fraction=args.maximum_candidate_fraction,
        )
        candidate_by_id = {candidate.candidate_id: candidate for candidate in candidate_grid}
        missing = sorted(set(selected_ids) - set(candidate_by_id))
        if missing:
            raise ValueError(f"selected candidates not in frozen grid for {example_id}: {missing}")
        selected_candidates = tuple(candidate_by_id[value] for value in selected_ids)
        total_candidates += len(selected_candidates)

        print(
            f"compact_audit_case={case_index}/{len(selections)} id={example_id} "
            f"candidates={len(selected_candidates)}",
            flush=True,
        )

        private_baselines: dict[str, dict[str, Any]] = {}
        safe_baselines: dict[str, dict[str, Any]] = {}
        for variant_name, prompt in _manual_variants(pair, blocks).items():
            completion = _post_chat_completion(
                base_url=args.base_url,
                model=args.model,
                prompt=prompt,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                timeout_seconds=args.timeout_seconds,
            )
            private_baselines[variant_name] = _private_variant(prompt, completion)
            safe_baselines[variant_name] = asdict(_safe_variant(pair, prompt, completion, judge))
            total_generations += 1

        private_candidates: list[dict[str, Any]] = []
        safe_candidates: list[dict[str, Any]] = []
        for candidate_index, candidate in enumerate(selected_candidates, 1):
            print(
                f"compact_audit_progress id={example_id} "
                f"candidate={candidate_index}/{len(selected_candidates)}",
                flush=True,
            )
            private_variants: dict[str, dict[str, Any]] = {}
            safe_variants: dict[str, dict[str, Any]] = {}
            for variant_name, prompt in _candidate_variants(pair, candidate).items():
                completion = _post_chat_completion(
                    base_url=args.base_url,
                    model=args.model,
                    prompt=prompt,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    timeout_seconds=args.timeout_seconds,
                )
                private_variants[variant_name] = _private_variant(prompt, completion)
                safe_variants[variant_name] = asdict(
                    _safe_variant(pair, prompt, completion, judge)
                )
                total_generations += 1
            metadata = {
                "candidate_id": candidate.candidate_id,
                "block_index": candidate.block_index,
                "start_chunk": candidate.start_chunk,
                "end_chunk": candidate.end_chunk,
                "start_word": candidate.start_word,
                "end_word": candidate.end_word,
                "span_start": candidate.span.start,
                "span_end": candidate.span.end,
                "removed_character_fraction": candidate.removed_character_fraction,
            }
            private_candidates.append({**metadata, "variants": private_variants})
            safe_candidates.append({**metadata, "variants": safe_variants})

        private_records.append(
            {
                "example_id": example_id,
                "behavior": pair.behavior,
                "goal_alignment": GoalAlignment.FULL.value,
                "retain_sentence_indices": list(case.retain_sentence_indices),
                "manual_scaffold_blocks": [
                    {"start": block.start, "end": block.end} for block in blocks
                ],
                "baselines": private_baselines,
                "candidates": private_candidates,
            }
        )
        safe_cases.append(
            {
                "example_id": example_id,
                "behavior": pair.behavior,
                "goal_alignment": GoalAlignment.FULL.value,
                "manual_scaffold_block_count": len(blocks),
                "selected_candidate_count": len(selected_candidates),
                "baselines": safe_baselines,
                "candidates": safe_candidates,
            }
        )

    _write_private_jsonl(args.private_output, private_records)
    safe_payload = {
        "status": "COMPACT_ORACLE_LONGER_DECODE_AUDIT_CAPTURE_COMPLETE",
        "model": args.model,
        "paper_validity": False,
        "review_required": True,
        "raw_prompts_recorded_in_safe_output": False,
        "raw_responses_recorded_in_safe_output": False,
        "source_oracle_run": 31804204494,
        "chunk_count": args.chunk_count,
        "maximum_candidate_fraction": args.maximum_candidate_fraction,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "case_count": len(safe_cases),
        "candidate_count": total_candidates,
        "generation_count": total_generations,
        "cases": safe_cases,
    }
    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(safe_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": safe_payload["status"],
                "case_count": len(safe_cases),
                "candidate_count": total_candidates,
                "generation_count": total_generations,
                "raw_prompts_logged": False,
                "raw_responses_logged": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
