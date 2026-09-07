from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "freeze_d3_guidedbench_split.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("freeze_d3_guidedbench_split", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def row(topic: str, index: int) -> dict:
    return {
        "id": f"id-{topic}-{index}",
        "index": index,
        "benchmark_version": "1.0",
        "subset": "core",
        "topic": topic,
        "question": f"BENIGN-QUESTION-{topic}-{index}",
        "target": "BENIGN-TARGET",
        "guidelines": [
            {
                "id": "g0",
                "type": "action",
                "description": "benign description",
                "examples": ["benign example"],
            }
        ],
    }


def test_split_is_one_plus_three_per_topic_and_content_free() -> None:
    rows = [row(topic, index) for topic in ("alpha", "beta") for index in range(5)]
    development, confirmation, metadata = MODULE.select_split(
        rows, required_rows=10, required_topic_count=2
    )
    assert len(development) == 2
    assert len(confirmation) == 6
    assert metadata["remaining_rows"] == 2
    assert metadata["development_confirmation_overlap"] is False
    assert {item["within_topic_ordinal"] for item in development} == {0}
    assert {item["within_topic_ordinal"] for item in confirmation} == {1, 2, 3}
    assert MODULE.find_prohibited_keys(development) == ()
    assert MODULE.find_prohibited_keys(confirmation) == ()


def test_split_selection_is_input_order_invariant() -> None:
    rows = [row(topic, index) for topic in ("alpha", "beta") for index in range(5)]
    first = MODULE.select_split(rows, required_rows=10, required_topic_count=2)
    second = MODULE.select_split(list(reversed(rows)), required_rows=10, required_topic_count=2)
    assert first == second
