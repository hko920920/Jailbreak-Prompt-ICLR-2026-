from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol, cast

JsonObject = dict[str, Any]


class TokenizerProtocol(Protocol):
    is_fast: bool
    chat_template: str | None
    vocab_size: int
    init_kwargs: dict[str, Any]

    def apply_chat_template(
        self,
        conversation: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str: ...

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool = False,
    ) -> Any: ...

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...

    def decode(
        self,
        token_ids: list[int],
        *,
        skip_special_tokens: bool,
        clean_up_tokenization_spaces: bool,
    ) -> str: ...


@dataclass(frozen=True)
class TokenSlice:
    start: int
    stop: int

    @property
    def length(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True)
class CandidateAudit:
    candidate_id: str
    passed: bool
    single_token_positions: int
    subset_count: int
    roundtrip_pass_count: int
    mapping_sha256: str
    failure_codes: tuple[str, ...]


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def balanced_ranges(item_count: int, block_count: int) -> list[tuple[int, int]]:
    if item_count <= 0 or block_count <= 0 or block_count > item_count:
        raise ValueError("invalid partition dimensions")
    base, remainder = divmod(item_count, block_count)
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for block_index in range(block_count):
        width = base + (1 if block_index < remainder else 0)
        ranges.append((cursor, cursor + width))
        cursor += width
    if cursor != item_count:
        raise AssertionError("partition did not cover all items")
    return ranges


def enumerate_masks(block_count: int) -> range:
    if block_count <= 0:
        raise ValueError("block_count must be positive")
    return range(1 << block_count)


def selected_positions(
    ranges: list[tuple[int, int]],
    mask: int,
) -> list[int]:
    result: list[int] = []
    for block_index, (start, stop) in enumerate(ranges):
        if mask & (1 << block_index):
            result.extend(range(start, stop))
    return result


def locate_unique_text(rendered: str, text: str) -> tuple[int, int]:
    first = rendered.find(text)
    if first < 0 or rendered.find(text, first + 1) >= 0:
        raise ValueError("fixture text was not uniquely rendered")
    return first, first + len(text)


def token_slice_for_char_span(
    offsets: list[tuple[int, int]],
    char_start: int,
    char_stop: int,
) -> TokenSlice:
    touching: list[int] = []
    for index, (start, stop) in enumerate(offsets):
        if start == stop:
            continue
        if stop > char_start and start < char_stop:
            if start < char_start or stop > char_stop:
                raise ValueError("token overlaps a fixture boundary")
            touching.append(index)
    if not touching:
        raise ValueError("fixture span did not map to tokens")
    expected = list(range(touching[0], touching[-1] + 1))
    if touching != expected:
        raise ValueError("fixture token positions are not contiguous")
    if offsets[touching[0]][0] != char_start:
        raise ValueError("fixture start is not token aligned")
    if offsets[touching[-1]][1] != char_stop:
        raise ValueError("fixture stop is not token aligned")
    return TokenSlice(touching[0], touching[-1] + 1)


def leading_whitespace(value: str) -> str:
    return value[: len(value) - len(value.lstrip())]


def build_position_mapping(
    tokenizer: TokenizerProtocol,
    original_ids: list[int],
    candidate_text: str,
) -> tuple[list[int], list[str]]:
    mapping: list[int] = []
    failures: list[str] = []
    for position, token_id in enumerate(original_ids):
        piece = tokenizer.decode(
            [token_id],
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        replacement_text = leading_whitespace(piece) + candidate_text
        replacement_ids = tokenizer.encode(
            replacement_text,
            add_special_tokens=False,
        )
        if len(replacement_ids) != 1:
            failures.append(f"NON_SINGLE_TOKEN_AT_{position}")
            continue
        mapping.append(replacement_ids[0])
    return mapping, failures


def audit_candidate(
    tokenizer: TokenizerProtocol,
    full_ids: list[int],
    control_slice: TokenSlice,
    target_slice: TokenSlice,
    ranges: list[tuple[int, int]],
    candidate_id: str,
    candidate_text: str,
) -> CandidateAudit:
    control_ids = full_ids[control_slice.start : control_slice.stop]
    replacement_ids, failures = build_position_mapping(
        tokenizer,
        control_ids,
        candidate_text,
    )
    if failures:
        return CandidateAudit(
            candidate_id=candidate_id,
            passed=False,
            single_token_positions=len(replacement_ids),
            subset_count=1 << len(ranges),
            roundtrip_pass_count=0,
            mapping_sha256=canonical_sha256(replacement_ids),
            failure_codes=tuple(failures),
        )

    roundtrip_pass_count = 0
    subset_count = 1 << len(ranges)
    for mask in enumerate_masks(len(ranges)):
        mutated = list(full_ids)
        for relative_position in selected_positions(ranges, mask):
            absolute_position = control_slice.start + relative_position
            mutated[absolute_position] = replacement_ids[relative_position]
        if len(mutated) != len(full_ids):
            failures.append("TOKEN_COUNT_CHANGED")
            break
        if target_slice.start <= control_slice.stop:
            failures.append("CONTROL_TARGET_OVERLAP")
            break
        decoded = tokenizer.decode(
            mutated,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        roundtrip = tokenizer.encode(decoded, add_special_tokens=False)
        if roundtrip != mutated:
            failures.append(f"ROUNDTRIP_MISMATCH_MASK_{mask}")
            continue
        roundtrip_pass_count += 1

    return CandidateAudit(
        candidate_id=candidate_id,
        passed=not failures and roundtrip_pass_count == subset_count,
        single_token_positions=len(replacement_ids),
        subset_count=subset_count,
        roundtrip_pass_count=roundtrip_pass_count,
        mapping_sha256=canonical_sha256(replacement_ids),
        failure_codes=tuple(failures),
    )


def audit_tokenizer(
    tokenizer: TokenizerProtocol,
    contract: JsonObject,
) -> JsonObject:
    target = cast(JsonObject, contract["target_tokenizer"])
    fixture = cast(JsonObject, contract["harmless_fixture"])
    partition = cast(JsonObject, contract["coarse_partition"])
    if target["use_fast"] is True and tokenizer.is_fast is not True:
        raise ValueError("a fast tokenizer is required")
    if target["chat_template_required"] is True and not tokenizer.chat_template:
        raise ValueError("chat template is missing")

    control_text = str(fixture["control_separator"]).join(
        [str(fixture["control_lexical_unit"])] * int(fixture["control_lexical_unit_count"])
    )
    synthetic_goal = str(fixture["synthetic_goal"])
    synthetic_target = str(fixture["synthetic_target"])
    user_content = f"{synthetic_goal}\n{control_text}"
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": synthetic_target},
    ]
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    encoded = tokenizer(
        rendered,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    full_ids = list(encoded["input_ids"])
    offsets = [tuple(pair) for pair in encoded["offset_mapping"]]
    control_chars = locate_unique_text(rendered, control_text)
    target_chars = locate_unique_text(rendered, synthetic_target)
    control_slice = token_slice_for_char_span(offsets, *control_chars)
    target_slice = token_slice_for_char_span(offsets, *target_chars)
    required_control_count = int(partition["control_token_count_required"])
    if control_slice.length != required_control_count:
        raise ValueError("GCG control text did not map to the required token count")
    if control_slice.stop > target_slice.start:
        raise ValueError("control and target slices overlap")

    ranges = balanced_ranges(
        control_slice.length,
        int(partition["block_count"]),
    )
    if (1 << len(ranges)) != int(partition["subset_count"]):
        raise ValueError("subset cardinality mismatch")

    candidate_results = []
    for candidate in cast(list[JsonObject], contract["neutralizer_candidates"]):
        result = audit_candidate(
            tokenizer,
            full_ids,
            control_slice,
            target_slice,
            ranges,
            str(candidate["id"]),
            str(candidate["text"]),
        )
        candidate_results.append(
            {
                "candidate_id": result.candidate_id,
                "passed": result.passed,
                "single_token_positions": result.single_token_positions,
                "subset_count": result.subset_count,
                "roundtrip_pass_count": result.roundtrip_pass_count,
                "mapping_sha256": result.mapping_sha256,
                "failure_codes": list(result.failure_codes),
            }
        )

    passing = [row for row in candidate_results if row["passed"] is True]
    required_passing = int(
        cast(JsonObject, contract["compatibility_gate"])[
            "required_position_preserving_neutralizer_count"
        ]
    )
    chat_template = tokenizer.chat_template or ""
    return {
        "tokenizer_class": type(tokenizer).__name__,
        "is_fast": tokenizer.is_fast,
        "vocab_size": int(tokenizer.vocab_size),
        "chat_template_sha256": hashlib.sha256(chat_template.encode()).hexdigest(),
        "rendered_token_count": len(full_ids),
        "rendered_token_ids_sha256": canonical_sha256(full_ids),
        "control_slice": {"start": control_slice.start, "stop": control_slice.stop},
        "control_token_count": control_slice.length,
        "control_token_ids_sha256": canonical_sha256(
            full_ids[control_slice.start : control_slice.stop]
        ),
        "target_slice": {"start": target_slice.start, "stop": target_slice.stop},
        "target_token_count": target_slice.length,
        "target_token_ids_sha256": canonical_sha256(
            full_ids[target_slice.start : target_slice.stop]
        ),
        "block_ranges": [list(value) for value in ranges],
        "subset_count": 1 << len(ranges),
        "candidate_results": candidate_results,
        "passing_candidate_ids": [str(row["candidate_id"]) for row in passing],
        "passing_candidate_count": len(passing),
        "compatibility_pass": len(passing) >= required_passing,
        "raw_fixture_recorded": False,
        "raw_rendered_prompt_recorded": False,
        "raw_token_ids_recorded": False,
    }
