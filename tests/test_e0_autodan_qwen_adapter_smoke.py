from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_autodan_qwen_adapter_smoke.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "e0_autodan_qwen_adapter_smoke_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_e0_autodan_qwen_adapter_smoke", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load AutoDAN Qwen adapter smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_unique_span_requires_exactly_one_occurrence() -> None:
    module = load_script()
    assert module.find_unique_span("prefix PAYLOAD suffix", "PAYLOAD") == (7, 14)
    with pytest.raises(ValueError, match="exactly one"):
        module.find_unique_span("PAYLOAD and PAYLOAD", "PAYLOAD")
    with pytest.raises(ValueError, match="exactly one"):
        module.find_unique_span("nothing", "PAYLOAD")


def test_token_interval_detects_contiguous_coverage() -> None:
    module = load_script()
    offsets = [(0, 2), (2, 5), (5, 8), (8, 11), (0, 0)]
    result = module.token_interval_for_span(offsets, span_start=3, span_end=9)
    assert result == {
        "nonempty": True,
        "contiguous": True,
        "covers_character_span": True,
        "start": 1,
        "end_exclusive": 4,
        "count": 3,
        "coverage_start": 2,
        "coverage_end": 11,
    }


def test_unit_manifest_excludes_payload_from_intervention_domain() -> None:
    module = load_script()
    rows = module.build_unit_manifest("AA PAYLOAD ZZ", "PAYLOAD")
    assert [row["id"] for row in rows] == [
        "AUTODAN_PREFIX_BEFORE_PAYLOAD",
        "IMMUTABLE_SYNTHETIC_PAYLOAD",
        "AUTODAN_SUFFIX_AFTER_PAYLOAD",
    ]
    assert [row["neutralizable"] for row in rows] == [True, False, True]
    assert all(row["raw_text_recorded"] is False for row in rows)


def test_contract_is_preoutcome_and_tokenizer_only() -> None:
    config = cast(
        dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8"))
    )
    assert config["status"] == "FROZEN_BEFORE_AUTODAN_QWEN_ADAPTER_SMOKE"
    assert config["frozen"] is True
    assert config["paper_validity"] is False

    target = cast(dict[str, object], config["target_tokenizer"])
    assert target["repository"] == "Qwen/Qwen2.5-7B-Instruct"
    assert target["revision"] == "a09a35458c702b33eeacc393d103063234e8bc28"
    allow_patterns = cast(list[str], target["allow_patterns"])
    assert "tokenizer.json" in allow_patterns
    assert "tokenizer_config.json" in allow_patterns
    assert not any(item.endswith(".safetensors") for item in allow_patterns)

    rules = cast(dict[str, object], config["rules"])
    assert rules["real_harmful_payload_allowed"] is False
    assert rules["target_model_weights_allowed"] is False
    assert rules["target_model_generation_allowed"] is False
    assert rules["intervention_domain_must_exclude_payload"] is True

    admission = cast(dict[str, object], config["admission"])
    assert admission["balanced_signal_screen_admission_on_this_step"] is False
    assert len(cast(list[str], admission["remaining_required_before_admission"])) == 4

    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
