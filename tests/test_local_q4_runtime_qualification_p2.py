from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/run_local_q4_runtime_qualification_p2.py"
SPEC = importlib.util.spec_from_file_location("local_q4_p2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalization_and_capability_are_whitespace_insensitive() -> None:
    assert MODULE.comparison_text('  {"STATUS": "ok"}\r\n') == '{"status":"ok"}'
    assert MODULE.capability_pass('  {"STATUS": "ok"}\r\n', ['{"status":"ok"}'])
    assert not MODULE.capability_pass("41", ["42"])


def test_perf_parser_separates_prompt_and_decode_rates() -> None:
    value = MODULE.parse_perf(
        "\n".join(
            [
                "llama_perf_context_print: load time = 1234.50 ms",
                "llama_perf_context_print: prompt eval time = 20.00 ms / 10 tokens "
                "(500.00 tokens per second)",
                "llama_perf_context_print: eval time = 100.00 ms / 5 runs "
                "(20.00 ms per token, 50.00 tokens per second)",
            ]
        )
    )
    assert value == {
        "load_ms": 1234.5,
        "prompt_tokens_per_second": 500.0,
        "decode_tokens_per_second": 50.0,
        "decode_token_runs": 5,
    }


def test_simple_io_response_and_summary_are_extracted() -> None:
    prompt = "Reply with exactly P2_OK and nothing else."
    stdout = (
        "Loading model...\r\n\r\n"
        f"> {prompt}\r\n"
        "P2_OK\r\n\r\n"
        "[ Prompt: 290.0 t/s | Generation: 56.8 t/s ]\r\n\r\nExiting..."
    )
    assert MODULE.extract_simple_io_response(stdout, prompt) == "P2_OK"
    perf = MODULE.parse_perf(stdout)
    assert perf["prompt_tokens_per_second"] == 290.0
    assert perf["decode_tokens_per_second"] == 56.8


def test_invocation_identity_changes_with_replicate() -> None:
    model = {
        "model_id": "model",
        "files": [{"sha256": "a" * 64}],
    }
    common = {
        "contract_sha256": "b" * 64,
        "runtime_revision": "c" * 40,
        "runner_sha256": "d" * 64,
        "model": model,
        "prompt_id": "sentinel",
        "seed": 17,
        "generation": {"temperature": 0.0},
    }
    first = MODULE.invocation_identity(**common, replicate_index=0)
    second = MODULE.invocation_identity(**common, replicate_index=1)
    assert MODULE.canonical_sha256(first) != MODULE.canonical_sha256(second)


def test_atomic_cache_replays_without_executor(tmp_path: Path) -> None:
    identity = {"model_id": "model", "prompt_id": "p"}
    path = tmp_path / "record.json"
    first, first_hit = MODULE.load_or_execute_record(
        path,
        identity,
        lambda: {"response": "P2_OK"},
    )
    second, second_hit = MODULE.load_or_execute_record(path, identity, None)
    assert first_hit is False
    assert second_hit is True
    assert first == second


def test_safe_result_rejects_private_text() -> None:
    MODULE.assert_safe_result({"response_sha256": "a" * 64})
    try:
        MODULE.assert_safe_result({"response": "private"})
    except ValueError as exc:
        assert "private text field" in str(exc)
    else:
        raise AssertionError("private response must not enter the safe result")


def test_contract_is_frozen_before_generation() -> None:
    contract = json.loads(
        (
            ROOT
            / "configs/natural_language_localization/"
            "local_q4_runtime_qualification_p2_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert contract["status"] == "FROZEN_BEFORE_ANY_P2_MODEL_GENERATION"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False
    assert len(contract["models"]) == 2
    assert len(contract["harmless_prompts"]) == 10
    assert all(value is False for value in contract["scope_boundary"].values())
    assert all(
        len(file_spec["sha256"]) == 64
        for model in contract["models"]
        for file_spec in model["files"]
    )
