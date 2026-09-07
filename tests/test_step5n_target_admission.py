from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_step5n_target_admission as runner  # noqa: E402
import verify_step5n_target_admission as verifier  # noqa: E402

LIVE_CONFIG = (
    ROOT / "configs" / "natural_language_localization" / "step5n_h4rm3l_confirmation_v1.json"
)


def harmless_prompts() -> list[dict[str, object]]:
    values = [
        ("sentinel", "Reply exactly P2_OK.", ["P2_OK"]),
        ("arithmetic", "What is 19 plus 23?", ["42"]),
        ("sorting", "Sort 3 1 2.", ["1", "2", "3"]),
        ("color", "Color of grass?", ["green"]),
        ("capital", "Capital of France?", ["Paris"]),
        ("translation", "French for hello?", ["bonjour"]),
        ("opposite", "Opposite of hot?", ["cold"]),
        ("primes", "First three primes?", ["2", "3", "5"]),
        ("json", "Return status ok JSON.", ['{"status":"ok"}']),
        ("copy", "Copy alpha-7.", ["alpha-7"]),
    ]
    return [
        {"prompt_id": prompt_id, "text": text, "required_normalized_substrings": required}
        for prompt_id, text, required in values
    ]


def contract() -> dict[str, object]:
    generation = {
        "seed": 17,
        "temperature": 0.0,
        "top_k": 1,
        "top_p": 1.0,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "context_tokens": 4096,
        "maximum_new_tokens": 48,
        "threads": 8,
        "threads_batch": 8,
        "batch_size": 512,
        "ubatch_size": 512,
        "gpu_layers": 99,
        "split_mode": "none",
        "fit": "off",
        "timeout_seconds_per_generation": 300,
    }
    return {
        "required_code": {"runner": {"sha256": "a" * 64}},
        "generation": generation,
        "harmless_prompts": harmless_prompts(),
        "determinism_check": {
            "prompt_id": "sentinel",
            "independent_process_repetitions": 2,
        },
        "models": [
            {
                "model_id": "qwen2.5-7b-instruct-q4-k-m",
                "runtime_repository": "qwen/repo",
                "runtime_revision": "b" * 40,
                "runtime_authority": "official",
                "license": "apache-2.0",
                "quantization": "Q4_K_M",
                "files": [{"sha256": "c" * 64}],
            },
            {
                "model_id": "google-gemma-4-e4b-it-qat-q4-0",
                "runtime_repository": "google/repo",
                "runtime_revision": "d" * 40,
                "runtime_authority": "official",
                "license": "apache-2.0",
                "quantization": "Q4_0 QAT",
                "files": [{"sha256": "e" * 64}],
            },
        ],
    }


def private_record(
    plan: dict[str, object], prompt: dict[str, object], *, response: str
) -> dict[str, object]:
    identity = {
        "kind": "STEP5N_HARMLESS_TARGET_ADMISSION",
        **{key: value for key, value in plan.items() if key != "execution_order"},
        "private_file_transport": True,
        "response_extractor_version": runner.extraction.EXTRACTOR_VERSION,
    }
    return {
        "schema_version": "local-signal-screen-p3-private-invocation-v1",
        "execution_identity": identity,
        "execution_identity_sha256": runner.canonical_sha256(identity),
        "payload": None,
        "prompt": prompt["text"],
        "response": response,
        "stdout": f"private wrapper {response}",
        "stderr": "private diagnostics",
        "return_code": 0,
        "error_type": None,
        "response_extraction_error": None,
        "response_extractor_version": runner.extraction.EXTRACTOR_VERSION,
        "response_repaired_from_preserved_stdout": False,
        "elapsed_seconds": 2.5,
        "performance": {
            "load_ms": 1000.0,
            "prompt_tokens_per_second": 120.0,
            "decode_tokens_per_second": 20.0,
            "decode_token_runs": 5,
        },
        "sampling": {
            "peak_gpu_memory_used_mib": 7000.0,
            "gpu_memory_delta_mib": 6000.0,
            "peak_gpu_temperature_c": 70.0,
        },
        "chat_template_active": True,
        "gpu_offload_logged": True,
    }


def gate() -> dict[str, object]:
    return {
        "determinism_prompt_id": "sentinel",
        "required_invocations_per_model": 11,
        "minimum_capability_passes_per_model": 10,
        "minimum_median_decode_tokens_per_second": 8.0,
        "maximum_peak_vram_mib": 8064.0,
        "maximum_gpu_temperature_c": 85.0,
        "minimum_gpu_memory_delta_mib": 1024.0,
    }


def test_runner_and_independent_verifier_reconstruct_same_plan() -> None:
    value = contract()
    runner_plan = runner.build_plan(value, "f" * 64)
    verifier_plan = verifier.build_plan(value, "f" * 64)
    assert runner_plan == verifier_plan
    assert len(runner_plan) == 22
    assert [row["replicate_index"] for row in runner_plan].count(1) == 2
    assert len({row["record_id"] for row in runner_plan}) == 22


def test_plan_identity_changes_with_prompt_model_and_replicate() -> None:
    plan = runner.build_plan(contract(), "f" * 64)
    assert plan[0]["record_id"] != plan[1]["record_id"]
    assert plan[0]["record_id"] != plan[10]["record_id"]
    assert plan[0]["record_id"] != plan[11]["record_id"]


def test_independent_safe_projection_matches_runner(tmp_path: Path) -> None:
    value = contract()
    plan = runner.build_plan(value, "f" * 64)[0]
    prompt = harmless_prompts()[0]
    private = private_record(plan, prompt, response="P2_OK")
    path = tmp_path / "private.json"
    path.write_text(json.dumps(private), encoding="utf-8")
    observed = runner.safe_invocation_row(plan, prompt, private, path, 48, cache_hit=False)
    reconstructed = verifier.reconstruct_safe_row(plan, prompt, private, path)
    assert observed == reconstructed
    assert observed["capability_pass"] is True
    assert runner.canonical_sha256(observed) == verifier.canonical_sha256(reconstructed)


def test_prompt_echo_is_rejected_even_if_answer_substring_occurs(tmp_path: Path) -> None:
    value = contract()
    plan = runner.build_plan(value, "f" * 64)[0]
    prompt = harmless_prompts()[0]
    private = private_record(plan, prompt, response="Reply exactly P2_OK. P2_OK")
    path = tmp_path / "private.json"
    path.write_text(json.dumps(private), encoding="utf-8")
    row = runner.safe_invocation_row(plan, prompt, private, path, 48, cache_hit=False)
    assert row["prompt_echo_detected"] is True
    assert row["capability_pass"] is False


def test_safe_artifact_guard_raises_for_raw_text_keys() -> None:
    with pytest.raises(ValueError, match="private text field"):
        runner.assert_safe({"nested": [{"response": "secret"}]})
    assert verifier.forbidden_locations({"nested": [{"prompt": "secret"}]}) == [
        "$.nested[0].prompt"
    ]


def test_progress_requires_exact_frozen_prefix(tmp_path: Path) -> None:
    plan = runner.build_plan(contract(), "f" * 64)
    progress = [{**plan[0], "response_sha256": "a" * 64}]
    path = tmp_path / "progress.jsonl"
    path.write_text(json.dumps(progress[0]) + "\n", encoding="utf-8")
    assert runner.validate_progress(plan, path) == progress
    progress[0]["record_id"] = "b" * 64
    path.write_text(json.dumps(progress[0]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact plan prefix"):
        runner.validate_progress(plan, path)


def test_model_gate_reconstruction_matches_and_detects_rate_failure() -> None:
    value = contract()
    plan = runner.build_plan(value, "f" * 64)[:11]
    prompts = {str(row["prompt_id"]): row for row in harmless_prompts()}
    rows = []
    for item in plan:
        prompt = prompts[str(item["prompt_id"])]
        private = private_record(
            item, prompt, response=str(prompt["required_normalized_substrings"][0])
        )
        response = runner.p3.normalized_response(str(private["response"]))
        rows.append(
            {
                **runner.p3.safe_invocation(private, 48),
                "model_id": item["model_id"],
                "prompt_id": item["prompt_id"],
                "replicate_index": item["replicate_index"],
                "capability_pass": True,
                "prompt_echo_detected": False,
                "response_sha256": runner.text_sha256(response),
            }
        )
    # Force the sentinel pair to the same normalized response identity.
    sentinel_hash = rows[0]["response_sha256"]
    rows[-1]["response_sha256"] = sentinel_hash
    model = value["models"][0]
    assert isinstance(model, dict)
    observed = runner.summarize_model(model, rows, gate())
    reconstructed = verifier.summarize_model(model, rows, gate())
    assert observed == reconstructed
    assert all(observed["checks"].values())
    for row in rows:
        row["performance"]["decode_tokens_per_second"] = 7.99
    failed = runner.summarize_model(model, rows, gate())
    assert failed["checks"]["decode_rate_floor_met"] is False


def test_run_path_passes_no_payload_and_never_references_scientific_inputs() -> None:
    source = (SCRIPT_DIRECTORY / "run_step5n_target_admission.py").read_text(encoding="utf-8")
    start = source.index("def run_qualification")
    end = source.index("\ndef finalize", start)
    live_source = source[start:end]
    assert "payload=None" in live_source
    assert "confirmation_reservation" not in live_source
    assert "prepare_h4rm3l" not in live_source
    assert "evaluator" not in live_source
    assert "run_private_invocation" in live_source


def test_tampered_private_identity_is_rejected(tmp_path: Path) -> None:
    plan = runner.build_plan(contract(), "f" * 64)[0]
    prompt = harmless_prompts()[0]
    private = private_record(plan, prompt, response="P2_OK")
    tampered = copy.deepcopy(private)
    tampered["execution_identity"]["model_id"] = "other-model"
    path = tmp_path / "private.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="execution identity mismatch"):
        verifier.reconstruct_safe_row(plan, prompt, tampered, path)


def test_live_frozen_contract_and_completed_safe_results_are_consistent() -> None:
    live, _verified = runner.validate_contract(ROOT, LIVE_CONFIG)
    safe_root = ROOT / str(live["recording"]["safe_output_root"])
    plan = runner.load_jsonl(safe_root / "admission_plan.safe.jsonl")
    assert plan == runner.build_plan(live, runner.file_sha256(LIVE_CONFIG))
    result = runner.load_object(safe_root / "result.safe.json")
    verification = runner.load_object(safe_root / "independent_verification.safe.json")
    assert result["status"] == "STEP5N_PREFERRED_TARGET_ADMISSION_PASS"
    assert result["preferred_target_pair_admitted"] is True
    assert verification["status"] == ("STEP5N_TARGET_ADMISSION_INDEPENDENT_RECONSTRUCTION_PASS")
    assert verification["passed_check_count"] == verification["check_count"] == 18
    assert verification["checks"]["scientific_output_roots_still_empty"] is True
    assert runner.file_sha256(safe_root / "independent_verification.safe.json") == (
        "ecb8d3cad807651dce9c2140307c5b4c10027dfa3a8bc271ccbf48d1c6b1124a"
    )
    # This is an immutable pre-C1N receipt.  The subsequently authorized C1N
    # output must not cause a historical absence predicate to be rerun.
    assert (
        ROOT
        / "data"
        / "natural_language_localization"
        / "c1n_h4rm3l_fresh_screen_v1"
        / "result.safe.json"
    ).is_file()


def test_completed_run_and_historical_verification_receipt_are_byte_stable() -> None:
    safe_root = ROOT / "data" / "natural_language_localization" / "step5n_target_admission_v1"
    result_path = safe_root / "result.safe.json"
    verification_path = safe_root / "independent_verification.safe.json"
    before_result = result_path.read_bytes()
    before_verification = verification_path.read_bytes()
    rerun = runner.run_qualification(ROOT, LIVE_CONFIG)
    reverified = runner.load_object(verification_path)
    identity_input = dict(reverified)
    stored_identity = identity_input.pop("verification_identity_sha256")
    assert rerun["preferred_target_pair_admitted"] is True
    assert reverified["verification_pass"] is True
    assert stored_identity == verifier.canonical_sha256(identity_input)
    assert result_path.read_bytes() == before_result
    assert verification_path.read_bytes() == before_verification
