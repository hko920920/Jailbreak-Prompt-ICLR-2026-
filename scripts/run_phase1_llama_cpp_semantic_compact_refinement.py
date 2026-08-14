from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from run_phase1_llama_cpp_compact_oracle import (
    _post_chat_completion,
    _private_variant,
    _safe_variant,
    _write_private_jsonl,
)

from jbspan.adapters.heuristic import HeuristicResponseJudge
from jbspan.dataio import load_prompt_pairs


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _normalize(text: str) -> str:
    value = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return re.sub(r"\s+", " ", value).strip()


def _validate_and_apply(
    prompt: str,
    spans: list[dict[str, Any]],
    operator: str,
) -> str:
    normalized: list[dict[str, Any]] = []
    for raw in spans:
        if not isinstance(raw, dict):
            raise ValueError("semantic span must be an object")
        start = raw.get("start")
        end = raw.get("end")
        expected_sha = raw.get("expected_sha256")
        replacement = raw.get(operator)
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError("semantic span has invalid offsets")
        if end > len(prompt):
            raise ValueError("semantic span exceeds prompt length")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError("semantic span has invalid expected hash")
        if not isinstance(replacement, str):
            raise ValueError(f"semantic span has no {operator} replacement")
        if _sha256(prompt[start:end]) != expected_sha:
            raise ValueError("semantic span source hash mismatch")
        normalized.append({"start": start, "end": end, "replacement": replacement})

    ordered = sorted(normalized, key=lambda value: int(value["start"]))
    for left, right in zip(ordered, ordered[1:], strict=False):
        if int(left["end"]) > int(right["start"]):
            raise ValueError("semantic spans overlap")

    edited = prompt
    for span in sorted(ordered, key=lambda value: int(value["start"]), reverse=True):
        start = int(span["start"])
        end = int(span["end"])
        edited = edited[:start] + str(span["replacement"]) + edited[end:]
    return _normalize(edited)


def _load_cases(path: Path) -> tuple[dict[str, Any], ...]:
    payload = _load_json(path)
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("semantic refinement manifest must contain cases")
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_candidates: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("semantic case must be an object")
        example_id = raw_case.get("example_id")
        prompt_sha = raw_case.get("prompt_sha256")
        raw_candidates = raw_case.get("candidates")
        if not isinstance(example_id, str) or not example_id:
            raise ValueError("semantic case has invalid example_id")
        if example_id in seen_ids:
            raise ValueError(f"duplicate semantic case: {example_id}")
        if not isinstance(prompt_sha, str) or len(prompt_sha) != 64:
            raise ValueError(f"semantic case has invalid prompt hash: {example_id}")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ValueError(f"semantic case has no candidates: {example_id}")
        candidates: list[dict[str, Any]] = []
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                raise ValueError("semantic candidate must be an object")
            candidate_id = raw_candidate.get("candidate_id")
            raw_spans = raw_candidate.get("spans")
            fraction = raw_candidate.get("removed_character_fraction")
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ValueError("semantic candidate has invalid ID")
            if candidate_id in seen_candidates:
                raise ValueError(f"duplicate semantic candidate: {candidate_id}")
            if not isinstance(raw_spans, list) or not raw_spans:
                raise ValueError(f"semantic candidate has no spans: {candidate_id}")
            if not isinstance(fraction, (float, int)) or not 0 < float(fraction) < 1:
                raise ValueError(f"semantic candidate has invalid fraction: {candidate_id}")
            seen_candidates.add(candidate_id)
            candidates.append(dict(raw_candidate))
        seen_ids.add(example_id)
        case = dict(raw_case)
        case["candidates"] = candidates
        cases.append(case)
    return tuple(cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    pair_by_id = {pair.id: pair for pair in load_prompt_pairs(args.data)}
    cases = _load_cases(args.manifest)
    judge = HeuristicResponseJudge()
    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    candidate_count = 0
    generation_count = 0

    for case_index, case in enumerate(cases, 1):
        example_id = str(case["example_id"])
        pair = pair_by_id.get(example_id)
        if pair is None:
            raise ValueError(f"semantic case not found in data: {example_id}")
        if _sha256(pair.jailbreak_prompt) != str(case["prompt_sha256"]):
            raise ValueError(f"semantic case prompt hash mismatch: {example_id}")
        print(
            f"semantic_refinement_case={case_index}/{len(cases)} id={example_id}",
            flush=True,
        )

        private_baselines: dict[str, dict[str, Any]] = {}
        safe_baselines: dict[str, dict[str, Any]] = {}
        for variant_name, prompt in {
            "original": pair.original_prompt,
            "jailbreak": pair.jailbreak_prompt,
        }.items():
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
            generation_count += 1

        private_candidates: list[dict[str, Any]] = []
        safe_candidates: list[dict[str, Any]] = []
        raw_candidates = list(case["candidates"])
        candidate_count += len(raw_candidates)
        for candidate_index, candidate in enumerate(raw_candidates, 1):
            candidate_id = str(candidate["candidate_id"])
            spans = list(candidate["spans"])
            print(
                f"semantic_refinement_progress id={example_id} "
                f"candidate={candidate_index}/{len(raw_candidates)}",
                flush=True,
            )
            private_variants: dict[str, dict[str, Any]] = {}
            safe_variants: dict[str, dict[str, Any]] = {}
            prompt_hashes: dict[str, str] = {}
            for operator in ("neutral_short", "neutral_matched"):
                prompt = _validate_and_apply(pair.jailbreak_prompt, spans, operator)
                completion = _post_chat_completion(
                    base_url=args.base_url,
                    model=args.model,
                    prompt=prompt,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    timeout_seconds=args.timeout_seconds,
                )
                private_variants[operator] = _private_variant(prompt, completion)
                safe_variants[operator] = asdict(_safe_variant(pair, prompt, completion, judge))
                prompt_hashes[operator] = _sha256(prompt)
                generation_count += 1
            metadata = {
                "candidate_id": candidate_id,
                "span_count": int(candidate["span_count"]),
                "removed_character_fraction": float(
                    candidate["removed_character_fraction"]
                ),
                "prompt_sha256": prompt_hashes,
            }
            private_candidates.append({**metadata, "variants": private_variants})
            safe_candidates.append({**metadata, "variants": safe_variants})

        private_cases.append(
            {
                "example_id": example_id,
                "behavior": pair.behavior,
                "baselines": private_baselines,
                "candidates": private_candidates,
            }
        )
        safe_cases.append(
            {
                "example_id": example_id,
                "behavior": pair.behavior,
                "candidate_count": len(raw_candidates),
                "baselines": safe_baselines,
                "candidates": safe_candidates,
            }
        )

    _write_private_jsonl(args.private_output, private_cases)
    safe_payload = {
        "status": "SEMANTIC_COMPACT_REFINEMENT_CAPTURE_COMPLETE",
        "model": args.model,
        "paper_validity": False,
        "review_required": True,
        "raw_prompts_recorded_in_safe_output": False,
        "raw_responses_recorded_in_safe_output": False,
        "operator_names": ["neutral_short", "neutral_matched"],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "case_count": len(safe_cases),
        "candidate_count": candidate_count,
        "generation_count": generation_count,
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
                "candidate_count": candidate_count,
                "generation_count": generation_count,
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
