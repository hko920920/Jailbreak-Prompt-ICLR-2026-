from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_topology_d2_micro_pilot_v1_1.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("d2_extraction_v1_1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def test_v3_extracts_prompt_ending_in_newline_without_extra_separator() -> None:
    prompt = "instruction\n"
    stdout = f"header\n\n> {prompt}answer text\n\n[ Prompt: 10.0 t/s | Generation: 20.0 t/s ]\n"
    assert MODULE.extract_simple_io_response_v3(stdout, prompt) == "answer text"


def test_v3_preserves_legacy_non_trailing_newline_and_truncated_routes() -> None:
    prompt = "instruction"
    stdout = f"> {prompt}\nanswer\n[ Prompt: 1.0 t/s | Generation: 2.0 t/s ]\n"
    assert MODULE.extract_simple_io_response_v3(stdout, prompt) == "answer"
    long_prompt = "x" * 600
    displayed = long_prompt[:500] + " ... (truncated)"
    long_stdout = f"> {displayed}\nlong answer\n[ Prompt: 1.0 t/s | Generation: 2.0 t/s ]\n"
    assert MODULE.extract_simple_io_response_v3(long_stdout, long_prompt) == "long answer"
