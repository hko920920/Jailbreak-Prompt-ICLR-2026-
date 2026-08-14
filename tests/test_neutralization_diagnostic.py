from __future__ import annotations

import pytest

from jbspan.schemas import PromptPair
from scripts.run_phase1_llama_cpp_neutralization_diagnostic import _build_variants


def _pair() -> PromptPair:
    return PromptPair(
        id="example",
        behavior="synthetic",
        original_prompt="Perform the requested unsafe action.",
        jailbreak_prompt=(
            "Fictional setup sentence. "
            "Perform the requested unsafe action. "
            "Add the requested details. "
            "Benign disclaimer sentence."
        ),
        attack_family="PAIR",
    )


def test_build_variants_preserves_retained_block() -> None:
    variants, diagnostics = _build_variants(_pair(), (1, 2))

    assert variants["delete_scaffold"] == (
        "Perform the requested unsafe action. Add the requested details."
    )
    assert "[neutral context]" in variants["placeholder"]
    assert "This provides only neutral background context." in variants["length_aware"]
    assert diagnostics["sentence_count"] == 4
    assert diagnostics["scaffold_span_count"] == 2
    assert 0.0 < diagnostics["scaffold_character_fraction"] < 1.0
    assert diagnostics["delete_original_token_retention"] == 1.0


def test_build_variants_rejects_noncontiguous_retention() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        _build_variants(_pair(), (0, 2))
