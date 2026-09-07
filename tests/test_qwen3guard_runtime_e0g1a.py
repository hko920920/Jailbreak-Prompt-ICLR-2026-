from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).parents[1] / "scripts/qualify_qwen3guard_runtime_e0g1a.py"
    spec = importlib.util.spec_from_file_location("qwen3guard_runtime_e0g1a", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parser_accepts_exact_official_response_schema() -> None:
    module = _module()
    parsed = module.parse_output(
        "Safety: Safe\nCategories: None\nRefusal: No",
        {
            "safety_regex": r"Safety: (Safe|Unsafe|Controversial)",
            "category_regex": r"(Violent|None)",
            "refusal_regex": r"Refusal: (Yes|No)",
            "require_exactly_one_safety_match": True,
            "require_exactly_one_refusal_match": True,
        },
    )
    assert parsed == {"safety": "Safe", "categories": ["None"], "refusal": "No"}


def test_parser_rejects_missing_or_duplicated_decision_fields() -> None:
    module = _module()
    parser = {
        "safety_regex": r"Safety: (Safe|Unsafe|Controversial)",
        "category_regex": r"(Violent|None)",
        "refusal_regex": r"Refusal: (Yes|No)",
        "require_exactly_one_safety_match": True,
        "require_exactly_one_refusal_match": True,
    }
    with pytest.raises(ValueError, match="safety"):
        module.parse_output("Categories: None\nRefusal: No", parser)
    with pytest.raises(ValueError, match="refusal"):
        module.parse_output("Safety: Safe\nRefusal: No\nRefusal: Yes", parser)


def test_git_blob_sha1_matches_git_object_identity() -> None:
    module = _module()
    content = b"hello\n"
    assert module.git_blob_sha1(content) == "ce013625030ba8dba906f756967f9e9ca394464a"
