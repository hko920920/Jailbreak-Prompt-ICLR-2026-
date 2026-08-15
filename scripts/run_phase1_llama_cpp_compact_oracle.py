from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jbspan.adapters.heuristic import HeuristicResponseJudge
from jbspan.dataio import load_prompt_pairs
from jbspan.neutralization import replace_spans
from jbspan.schemas import BehaviorScores, GoalAlignment, PromptPair, TextSpan

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\S+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")
_NEUTRAL_SENTENCE = "This provides only neutral background context."


@dataclass(frozen=True)
class Completion:
    content: str
    finish_reason: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class VariantSafeRecord:
    prompt_sha256: str
    prompt_chars: int
    response_sha256: str
    response_chars: int
    finish_reason: str
    completion_tokens: int | None
    refusal: float
    harmful_compliance: float
    original_token_retention: float


@dataclass(frozen=True)
class CandidateSafeRecord:
    candidate_id: str
    block_index: int
    start_chunk: int
    end_chunk: int
    start_word: int
    end_word: int
    span_start: int
    span_end: int
    removed_character_fraction: float
    variants: dict[str, VariantSafeRecord]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["variants"] = {
            name: asdict(record) for name, record in self.variants.items()
        }
        return payload


@dataclass(frozen=True)
class CaseSafeRecord:
    example_id: str
    behavior: str
    goal_alignment: str
    manual_outcome: str
    sentence_count: int
    manual_scaffold_block_count: int
    manual_scaffold_character_fraction: float
    word_count_in_manual_scaffold: int
    chunk_count: int
    candidate_count: int
    baselines: dict[str, VariantSafeRecord]
    candidates: tuple[CandidateSafeRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["baselines"] = {
            name: asdict(record) for name, record in self.baselines.items()
        }
        payload["candidates"] = [record.to_dict() for record in self.candidates]
        return payload


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    block_index: int
    start_chunk: int
    end_chunk: int
    start_word: int
    end_word: int
    span: TextSpan
    removed_character_fraction: float


@dataclass(frozen=True)
class OracleCase:
    example_id: str
    retain_sentence_indices: tuple[int, ...]
    expected_goal_alignment: GoalAlignment
    expected_manual_outcome: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if len(token) >= 3
    }


def _token_retention(reference: str, candidate: str) -> float:
    reference_tokens = _tokens(reference)
    if not reference_tokens:
        return 0.0
    return len(reference_tokens & _tokens(candidate)) / len(reference_tokens)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentence_spans(text: str) -> tuple[TextSpan, ...]:
    spans: list[TextSpan] = []
    start = 0
    for boundary in _SENTENCE_BOUNDARY_RE.finditer(text):
        end = boundary.start()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append(TextSpan(start, end, label=f"sentence-{len(spans)}"))
        start = boundary.end()

    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        spans.append(TextSpan(start, end, label=f"sentence-{len(spans)}"))
    if not spans:
        raise ValueError("prompt has no sentence spans")
    return tuple(spans)


def _scaffold_blocks(
    text: str,
    sentences: tuple[TextSpan, ...],
    retained_indices: tuple[int, ...],
) -> tuple[TextSpan, ...]:
    del text
    if not retained_indices:
        raise ValueError("at least one sentence must be retained")
    if tuple(sorted(set(retained_indices))) != retained_indices:
        raise ValueError("retain_sentence_indices must be unique and sorted")
    if retained_indices[-1] >= len(sentences):
        raise ValueError("retained sentence index exceeds sentence count")
    expected = tuple(range(retained_indices[0], retained_indices[-1] + 1))
    if retained_indices != expected:
        raise ValueError("oracle expects one contiguous retained sentence block")

    omitted = [index for index in range(len(sentences)) if index not in retained_indices]
    blocks: list[TextSpan] = []
    cursor = 0
    while cursor < len(omitted):
        first = omitted[cursor]
        last = first
        cursor += 1
        while cursor < len(omitted) and omitted[cursor] == last + 1:
            last = omitted[cursor]
            cursor += 1
        blocks.append(
            TextSpan(
                sentences[first].start,
                sentences[last].end,
                label=f"manual-scaffold-{len(blocks)}",
            )
        )
    if not blocks:
        raise ValueError("oracle requires a non-empty manual scaffold")
    return tuple(blocks)


def _word_spans(text: str, block: TextSpan) -> tuple[TextSpan, ...]:
    block_text = block.text(text)
    words = tuple(
        TextSpan(
            block.start + match.start(),
            block.start + match.end(),
            label=f"word-{index}",
        )
        for index, match in enumerate(_WORD_RE.finditer(block_text))
    )
    if not words:
        raise ValueError("manual scaffold block has no words")
    return words


def _partition_word_spans(
    words: tuple[TextSpan, ...],
    requested_chunk_count: int,
) -> tuple[tuple[TextSpan, int, int], ...]:
    if requested_chunk_count < 1:
        raise ValueError("chunk count must be positive")
    chunk_count = min(requested_chunk_count, len(words))
    base_size, extra = divmod(len(words), chunk_count)
    chunks: list[tuple[TextSpan, int, int]] = []
    cursor = 0
    for chunk_index in range(chunk_count):
        size = base_size + (1 if chunk_index < extra else 0)
        start_word = cursor
        end_word = cursor + size
        chunk_words = words[start_word:end_word]
        chunks.append(
            (
                TextSpan(
                    chunk_words[0].start,
                    chunk_words[-1].end,
                    label=f"chunk-{chunk_index}",
                ),
                start_word,
                end_word,
            )
        )
        cursor = end_word
    if cursor != len(words):
        raise RuntimeError("word partition did not cover the scaffold")
    return tuple(chunks)


def _candidate_specs_for_text(
    *,
    example_id: str,
    text: str,
    blocks: tuple[TextSpan, ...],
    requested_chunk_count: int,
    maximum_fraction: float,
) -> tuple[CandidateSpec, ...]:
    candidates: list[CandidateSpec] = []
    for block_index, block in enumerate(blocks):
        words = _word_spans(text, block)
        chunks = _partition_word_spans(words, requested_chunk_count)
        for start_chunk in range(len(chunks)):
            for end_chunk in range(start_chunk, len(chunks)):
                start_span, start_word, _ = chunks[start_chunk]
                end_span, _, end_word = chunks[end_chunk]
                span = TextSpan(
                    start_span.start,
                    end_span.end,
                    label=f"oracle-block-{block_index}-{start_chunk}-{end_chunk}",
                )
                fraction = span.length / len(text)
                if fraction > maximum_fraction + 1e-12:
                    continue
                candidate_id = (
                    f"{example_id}:b{block_index}:c{start_chunk}-{end_chunk}:"
                    f"{span.start}-{span.end}"
                )
                candidates.append(
                    CandidateSpec(
                        candidate_id=candidate_id,
                        block_index=block_index,
                        start_chunk=start_chunk,
                        end_chunk=end_chunk,
                        start_word=start_word,
                        end_word=end_word,
                        span=span,
                        removed_character_fraction=fraction,
                    )
                )
    candidates.sort(
        key=lambda item: (
            item.removed_character_fraction,
            item.span.length,
            item.block_index,
            item.span.start,
            item.span.end,
        )
    )
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise RuntimeError("candidate IDs are not unique")
    return tuple(candidates)


def _length_aware_replacement(original: str) -> str:
    target_words = max(1, len(original.split()))
    phrase_words = len(_NEUTRAL_SENTENCE.split())
    repeats = max(1, round(target_words / phrase_words))
    return " ".join(_NEUTRAL_SENTENCE for _ in range(repeats))


def _replace_one(text: str, span: TextSpan, replacement: str) -> str:
    return _normalize_space(replace_spans(text, (span,), (f" {replacement} ",)))


def _replace_many(text: str, spans: tuple[TextSpan, ...], replacements: tuple[str, ...]) -> str:
    return _normalize_space(replace_spans(text, spans, replacements))


def _manual_variants(pair: PromptPair, blocks: tuple[TextSpan, ...]) -> dict[str, str]:
    placeholder = tuple(" [neutral context] " for _ in blocks)
    length_aware = tuple(
        f" {_length_aware_replacement(block.text(pair.jailbreak_prompt))} "
        for block in blocks
    )
    return {
        "original": pair.original_prompt,
        "jailbreak": pair.jailbreak_prompt,
        "manual_placeholder": _replace_many(pair.jailbreak_prompt, blocks, placeholder),
        "manual_length_aware": _replace_many(pair.jailbreak_prompt, blocks, length_aware),
    }


def _candidate_variants(pair: PromptPair, candidate: CandidateSpec) -> dict[str, str]:
    removed = candidate.span.text(pair.jailbreak_prompt)
    return {
        "placeholder": _replace_one(
            pair.jailbreak_prompt,
            candidate.span,
            "[neutral context]",
        ),
        "length_aware": _replace_one(
            pair.jailbreak_prompt,
            candidate.span,
            _length_aware_replacement(removed),
        ),
    }


def _post_chat_completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    attempts: int = 3,
) -> Completion:
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    encoded = json.dumps(body).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(  # noqa: S310
            endpoint,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                raw_payload: Any = json.loads(response.read())
            if not isinstance(raw_payload, dict):
                raise RuntimeError("chat-completion response is not an object")
            choices = raw_payload.get("choices")
            if not isinstance(choices, list) or not choices:
                raise RuntimeError("chat-completion response has no choices")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise RuntimeError("chat-completion choice is not an object")
            message = choice.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise RuntimeError("chat-completion response has invalid message content")
            usage = raw_payload.get("usage")
            usage_dict = usage if isinstance(usage, dict) else {}
            finish_reason = choice.get("finish_reason")
            return Completion(
                content=str(message["content"]),
                finish_reason=str(finish_reason) if finish_reason is not None else "unknown",
                prompt_tokens=_optional_int(usage_dict.get("prompt_tokens")),
                completion_tokens=_optional_int(usage_dict.get("completion_tokens")),
                total_tokens=_optional_int(usage_dict.get("total_tokens")),
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError("chat completion failed after retries") from last_error


def _load_json(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_oracle_cases(path: Path) -> tuple[OracleCase, ...]:
    payload = _load_json(path)
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("oracle manifest must contain cases")
    cases: list[OracleCase] = []
    seen: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("oracle case must be an object")
        example_id = raw_case.get("id")
        raw_indices = raw_case.get("retain_sentence_indices")
        raw_alignment = raw_case.get("expected_goal_alignment")
        raw_outcome = raw_case.get("expected_manual_outcome")
        if not isinstance(example_id, str) or not example_id:
            raise ValueError("oracle case id must be a non-empty string")
        if example_id in seen:
            raise ValueError(f"duplicate oracle case: {example_id}")
        if not isinstance(raw_indices, list) or not raw_indices or not all(
            isinstance(value, int) for value in raw_indices
        ):
            raise ValueError(f"invalid retain_sentence_indices for {example_id}")
        if not isinstance(raw_alignment, str):
            raise ValueError(f"missing expected_goal_alignment for {example_id}")
        if not isinstance(raw_outcome, str) or not raw_outcome:
            raise ValueError(f"missing expected_manual_outcome for {example_id}")
        cases.append(
            OracleCase(
                example_id=example_id,
                retain_sentence_indices=tuple(int(value) for value in raw_indices),
                expected_goal_alignment=GoalAlignment(raw_alignment),
                expected_manual_outcome=raw_outcome,
            )
        )
        seen.add(example_id)
    return tuple(cases)


def _load_neutralization_records(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("neutralization manifest must contain records")
    indexed: dict[str, dict[str, Any]] = {}
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError("neutralization record must be an object")
        example_id = raw_record.get("example_id")
        if not isinstance(example_id, str) or not example_id:
            raise ValueError("neutralization record has invalid example_id")
        if example_id in indexed:
            raise ValueError(f"duplicate neutralization record: {example_id}")
        indexed[example_id] = dict(raw_record)
    return indexed


def _private_variant(prompt: str, completion: Completion) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "response": completion.content,
        "completion": {
            "finish_reason": completion.finish_reason,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "total_tokens": completion.total_tokens,
        },
    }


def _safe_variant(
    pair: PromptPair,
    prompt: str,
    completion: Completion,
    judge: HeuristicResponseJudge,
) -> VariantSafeRecord:
    scores: BehaviorScores = judge.score(pair, prompt, completion.content)
    return VariantSafeRecord(
        prompt_sha256=_sha256(prompt),
        prompt_chars=len(prompt),
        response_sha256=_sha256(completion.content),
        response_chars=len(completion.content),
        finish_reason=completion.finish_reason,
        completion_tokens=completion.completion_tokens,
        refusal=scores.refusal,
        harmful_compliance=scores.harmful_compliance,
        original_token_retention=_token_retention(pair.original_prompt, prompt),
    )


def _write_private_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records
    ) + "\n"
    path.write_text(serialized, encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--neutralization-labels", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M")
    parser.add_argument("--chunk-count", type=int, default=6)
    parser.add_argument("--maximum-candidate-fraction", type=float, default=0.35)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    pairs = load_prompt_pairs(args.data)
    pair_by_id = {pair.id: pair for pair in pairs}
    cases = _load_oracle_cases(args.cases)
    neutralization_records = _load_neutralization_records(args.neutralization_labels)
    judge = HeuristicResponseJudge()

    private_records: list[dict[str, Any]] = []
    safe_cases: list[CaseSafeRecord] = []
    total_candidates = 0
    total_generations = 0

    for case_index, case in enumerate(cases, 1):
        pair = pair_by_id.get(case.example_id)
        if pair is None:
            raise ValueError(f"oracle case not found in dataset: {case.example_id}")
        prior = neutralization_records.get(case.example_id)
        if prior is None:
            raise ValueError(f"oracle case missing neutralization label: {case.example_id}")
        if prior.get("goal_alignment") != case.expected_goal_alignment.value:
            raise ValueError(f"goal-alignment mismatch for {case.example_id}")
        if prior.get("outcome") != case.expected_manual_outcome:
            raise ValueError(f"manual-outcome mismatch for {case.example_id}")
        if case.expected_goal_alignment is not GoalAlignment.FULL:
            raise ValueError(f"oracle primary cases must be FULL: {case.example_id}")
        if case.expected_manual_outcome != "ROBUST_RECOVERY":
            raise ValueError(f"oracle primary cases must be robust: {case.example_id}")

        sentences = _sentence_spans(pair.jailbreak_prompt)
        blocks = _scaffold_blocks(
            pair.jailbreak_prompt,
            sentences,
            case.retain_sentence_indices,
        )
        manual_fraction = sum(block.length for block in blocks) / len(pair.jailbreak_prompt)
        word_count = sum(len(_word_spans(pair.jailbreak_prompt, block)) for block in blocks)
        candidates = _candidate_specs_for_text(
            example_id=pair.id,
            text=pair.jailbreak_prompt,
            blocks=blocks,
            requested_chunk_count=args.chunk_count,
            maximum_fraction=args.maximum_candidate_fraction,
        )
        if not candidates:
            raise ValueError(f"oracle generated no candidates for {case.example_id}")
        total_candidates += len(candidates)

        print(
            f"oracle_case={case_index}/{len(cases)} id={pair.id} "
            f"candidates={len(candidates)}",
            flush=True,
        )

        private_baselines: dict[str, dict[str, Any]] = {}
        safe_baselines: dict[str, VariantSafeRecord] = {}
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
            safe_baselines[variant_name] = _safe_variant(pair, prompt, completion, judge)
            total_generations += 1

        private_candidates: list[dict[str, Any]] = []
        safe_candidates: list[CandidateSafeRecord] = []
        for candidate_index, candidate in enumerate(candidates, 1):
            print(
                f"oracle_progress id={pair.id} candidate={candidate_index}/{len(candidates)}",
                flush=True,
            )
            private_variants: dict[str, dict[str, Any]] = {}
            safe_variants: dict[str, VariantSafeRecord] = {}
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
                safe_variants[variant_name] = _safe_variant(pair, prompt, completion, judge)
                total_generations += 1
            private_candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "block_index": candidate.block_index,
                    "start_chunk": candidate.start_chunk,
                    "end_chunk": candidate.end_chunk,
                    "start_word": candidate.start_word,
                    "end_word": candidate.end_word,
                    "span_start": candidate.span.start,
                    "span_end": candidate.span.end,
                    "removed_character_fraction": candidate.removed_character_fraction,
                    "variants": private_variants,
                }
            )
            safe_candidates.append(
                CandidateSafeRecord(
                    candidate_id=candidate.candidate_id,
                    block_index=candidate.block_index,
                    start_chunk=candidate.start_chunk,
                    end_chunk=candidate.end_chunk,
                    start_word=candidate.start_word,
                    end_word=candidate.end_word,
                    span_start=candidate.span.start,
                    span_end=candidate.span.end,
                    removed_character_fraction=candidate.removed_character_fraction,
                    variants=safe_variants,
                )
            )

        private_records.append(
            {
                "example_id": pair.id,
                "behavior": pair.behavior,
                "goal_alignment": case.expected_goal_alignment.value,
                "manual_outcome": case.expected_manual_outcome,
                "retain_sentence_indices": list(case.retain_sentence_indices),
                "manual_scaffold_blocks": [
                    {"start": block.start, "end": block.end} for block in blocks
                ],
                "manual_scaffold_character_fraction": manual_fraction,
                "baselines": private_baselines,
                "candidates": private_candidates,
            }
        )
        safe_cases.append(
            CaseSafeRecord(
                example_id=pair.id,
                behavior=pair.behavior,
                goal_alignment=case.expected_goal_alignment.value,
                manual_outcome=case.expected_manual_outcome,
                sentence_count=len(sentences),
                manual_scaffold_block_count=len(blocks),
                manual_scaffold_character_fraction=manual_fraction,
                word_count_in_manual_scaffold=word_count,
                chunk_count=args.chunk_count,
                candidate_count=len(candidates),
                baselines=safe_baselines,
                candidates=tuple(safe_candidates),
            )
        )

    _write_private_jsonl(args.private_output, private_records)
    safe_payload = {
        "status": "COMPACT_ORACLE_CAPTURE_COMPLETE",
        "model": args.model,
        "paper_validity": False,
        "review_required": True,
        "raw_prompts_recorded_in_safe_output": False,
        "raw_responses_recorded_in_safe_output": False,
        "oracle_type": "BOUNDARY_CONSTRAINED_NEAR_EXACT_CHUNK_GRID",
        "chunk_count": args.chunk_count,
        "maximum_candidate_fraction": args.maximum_candidate_fraction,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "case_count": len(safe_cases),
        "candidate_count": total_candidates,
        "generation_count": total_generations,
        "cases": [record.to_dict() for record in safe_cases],
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
