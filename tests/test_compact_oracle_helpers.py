from jbspan.schemas import TextSpan
from scripts.run_phase1_llama_cpp_compact_oracle import (
    _candidate_specs_for_text,
    _partition_word_spans,
    _word_spans,
)


def test_partition_word_spans_is_contiguous_and_complete() -> None:
    text = "one two three four five six seven"
    block = TextSpan(0, len(text))
    words = _word_spans(text, block)
    chunks = _partition_word_spans(words, requested_chunk_count=3)

    assert len(chunks) == 3
    assert chunks[0][1] == 0
    assert chunks[-1][2] == len(words)
    assert all(left[2] == right[1] for left, right in zip(chunks, chunks[1:], strict=True))


def test_candidate_grid_is_unique_sorted_and_fraction_bounded() -> None:
    text = "one two three four five six"
    block = TextSpan(0, len(text))
    candidates = _candidate_specs_for_text(
        example_id="example",
        text=text,
        blocks=(block,),
        requested_chunk_count=3,
        maximum_fraction=0.6,
    )

    assert candidates
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)
    assert all(candidate.removed_character_fraction <= 0.6 for candidate in candidates)
    fractions = [candidate.removed_character_fraction for candidate in candidates]
    assert fractions == sorted(fractions)
