from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from jbspan.schemas import PromptPair


def _load_runner_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_phase1_llama_cpp_neutralization_diagnostic.py"
    )
    spec = importlib.util.spec_from_file_location("neutralization_diagnostic_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load neutralization diagnostic runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_runner = _load_runner_module()
_build_variants: Callable[
    [PromptPair, tuple[int, ...]],
    tuple[dict[str, str], dict[str, Any]],
] = _runner._build_variants


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
