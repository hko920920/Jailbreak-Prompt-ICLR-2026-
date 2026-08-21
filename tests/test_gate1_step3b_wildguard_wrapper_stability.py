from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def module():
    path = Path("scripts/run_gate1_step3b_wildguard_wrapper_stability.py")
    spec = importlib.util.spec_from_file_location("wg_wrapper", path)
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def test_transformations_preserve_content() -> None:
    value = module()
    original = "alpha\nbeta"
    whitespace = value.transformed_response(original, "whitespace_only")
    assert "".join(whitespace.split()) == "".join(original.split())
    delimited = value.transformed_response(original, "neutral_delimiters")
    assert original in delimited
    assert delimited.startswith(value.DELIMITER_PREFIX)
    assert delimited.endswith(value.DELIMITER_SUFFIX)


def test_metrics_and_parser() -> None:
    value = module()
    parsed = value.parse_wildguard_output(
        "Prompt harmful: yes\nResponse refusal: no\nResponse harmful: yes"
    )
    assert parsed == ("harmful", "compliance", "harmful")
    metrics = value.compute_metrics([(1, 1), (0, 0), (1, 0), (0, 1)])
    assert metrics.parsed_count == 4
    assert metrics.accuracy == 0.5
    assert metrics.macro_f1 == 0.5
