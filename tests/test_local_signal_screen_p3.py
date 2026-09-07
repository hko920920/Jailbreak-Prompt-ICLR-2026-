from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_runner() -> ModuleType:
    path = SCRIPTS / "run_local_signal_screen_p3.py"
    spec = importlib.util.spec_from_file_location("p3_runner_test_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load P3 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()
CONFIG_PATH = (
    ROOT / "configs" / "natural_language_localization" / "local_signal_screen_p3_v1.json"
)


def contract() -> dict[str, object]:
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_contract_cardinality_and_pre_outcome_boundary() -> None:
    value = contract()
    RUNNER.validate_contract(ROOT, CONFIG_PATH, value)
    generation = value["generation"]
    assert isinstance(generation, dict)
    assert generation["seeds"] == [11, 23, 47]
    assert generation["total_scientific_generation_count"] == 36
    assert value["status"] == "FROZEN_BEFORE_ANY_P3_TARGET_OUTPUT"
    assert all(item is False for item in value["sealed_boundaries"].values())


def test_family_representatives_are_fixed_across_seeds() -> None:
    value = contract()
    families = {row["family"]: row for row in value["attack_families"]}
    assert families["h4rm3l"]["representative_program_id"] == "aim_refusal_affirmative"
    assert families["h4rm3l"]["same_representative_for_every_payload_and_seed"] is True
    assert families["DeepInception"]["expected_unit_count"] == 7
    assert families["DeepInception"]["p4_unit_decision"] == (
        "KEEP_ALL_SEVEN_SOURCE_DERIVED_UNITS"
    )
    assert families["DeepInception"]["post_outcome_unit_merging_allowed"] is False


def test_payload_selection_is_hash_ordered_and_filters_ineligible_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "payloads.csv"
    csv_path.write_text(
        "Behavior,BehaviorID,FunctionalCategory,SemanticCategory,Tags,ContextString\n"
        "alpha,id-z,standard,cat_a,,\n"
        "beta,id-a,standard,cat_a,,\n"
        "ignored,id-c,standard,cat_a,contextual,\n"
        "gamma,id-g,standard,cat_b,,\n"
        "ignored-context,id-x,standard,cat_b,,context\n",
        encoding="utf-8",
    )
    payload_contract = {
        "semantic_categories": ["cat_a", "cat_b"],
        "excluded_tags": ["contextual", "multimodal"],
        "functional_category_required": "standard",
    }
    rows = RUNNER.select_payloads(csv_path, payload_contract)
    expected_a = min(
        (("alpha", "id-z"), ("beta", "id-a")),
        key=lambda row: RUNNER.sha256_text(f"cat_a:{row[1]}"),
    )
    assert rows[0]["_payload"] == expected_a[0]
    assert rows[1]["_payload"] == "gamma"
    assert [row["position"] for row in rows] == [0, 1]


def test_materialization_requires_exact_single_payload_and_no_chat_marker() -> None:
    payload = "SAFE_PAYLOAD"
    value = RUNNER.materialization_record(
        f"prefix {payload} suffix",
        payload,
        units=[],
        fragments=[],
        partition_pass=True,
        route="TEST",
    )
    assert value["payload_occurrence_count"] == 1
    assert value["payload_byte_occurrence_count"] == 1
    with pytest.raises(ValueError, match="exactly once"):
        RUNNER.materialization_record(
            f"{payload} and {payload}",
            payload,
            units=[],
            fragments=[],
            partition_pass=True,
            route="TEST",
        )
    with pytest.raises(ValueError, match="chat control marker"):
        RUNNER.materialization_record(
            f"<|im_start|>{payload}",
            payload,
            units=[],
            fragments=[],
            partition_pass=True,
            route="TEST",
        )


def test_generation_plan_has_36_unique_fixed_prompt_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    value = contract()
    payloads: list[dict[str, object]] = []
    materials: dict[tuple[int, str], dict[str, object]] = {}
    for position in range(4):
        payloads.append(
            {
                "position": position,
                "payload_sha256": f"payload-{position}",
                "behavior_id_sha256": f"behavior-{position}",
                "semantic_category": f"category-{position}",
            }
        )
        for condition in ("DIRECT", "ATTACKED_H4RM3L", "ATTACKED_DEEPINCEPTION"):
            text = f"prompt-{position}-{condition}"
            materials[(position, condition)] = {
                "_text": text,
                "prompt_sha256": RUNNER.sha256_text(text),
                "prompt_character_length": len(text),
                "prompt_utf8_bytes": len(text.encode()),
                "payload_occurrence_count": 1,
                "payload_byte_occurrence_count": 1,
                "reserved_chat_marker_count": 0,
                "unit_count": 0,
                "unit_manifest_sha256": RUNNER.canonical_sha256([]),
                "fragment_manifest_sha256": RUNNER.canonical_sha256([]),
                "partition_pass": True,
                "materialization_route": "TEST",
            }
    monkeypatch.setattr(RUNNER, "count_tokens", lambda *_: 10)
    _, plan = RUNNER.make_plan(
        "contract-hash",
        value,
        payloads,
        materials,
        Path("tokenizer"),
        Path("model"),
    )
    assert len(plan) == 36
    assert len({row["invocation_id"] for row in plan}) == 36
    for position in range(4):
        for condition in ("DIRECT", "ATTACKED_H4RM3L", "ATTACKED_DEEPINCEPTION"):
            hashes = {
                row["prompt_sha256"]
                for row in plan
                if row["payload_position"] == position and row["condition"] == condition
            }
            assert len(hashes) == 1


def test_safe_result_rejects_raw_fields() -> None:
    RUNNER.assert_safe_result({"prompt_sha256": "abc", "raw_text_recorded": False})
    with pytest.raises(ValueError, match="unsafe raw field"):
        RUNNER.assert_safe_result({"nested": {"prompt": "secret"}})


def test_simple_io_response_extractor_handles_short_prompt() -> None:
    prompt = "Give the harmless confirmation code."
    response = "P3_OK"
    stdout = (
        "safe diagnostic log\n"
        f"> {prompt}\n"
        f"{response}\n\n"
        "[ Prompt: 12.34 t/s | Generation: 56.78 t/s ]\n"
    )
    assert RUNNER.simple_io_displayed_prompt(prompt) == prompt
    assert RUNNER.extract_simple_io_response(stdout, prompt) == response


def test_simple_io_response_extractor_handles_500_character_cli_truncation() -> None:
    prompt = "A" * 501
    displayed = "A" * 500 + " ... (truncated)"
    response = "Harmless parser recovery succeeded."
    stdout = (
        "safe diagnostic log\n"
        f"> {displayed}\n"
        f"{response}\n\n"
        "[ Prompt: 12.34 t/s | Generation: 56.78 t/s ]\n"
    )
    assert RUNNER.simple_io_displayed_prompt(prompt) == displayed
    assert RUNNER.extract_simple_io_response(stdout, prompt) == response


def test_simple_io_response_extractor_handles_truncated_multiline_prompt() -> None:
    prompt = ("harmless line\n" * 50) + "end"
    displayed = RUNNER.simple_io_displayed_prompt(prompt)
    response = "Harmless multiline recovery succeeded."
    stdout = (
        "safe diagnostic log\r\n"
        f"> {displayed}\r\n"
        f"{response}\r\n\r\n"
        "[ Prompt: 12.34 t/s | Generation: 56.78 t/s ]\r\n"
    )
    assert displayed.endswith(RUNNER.SIMPLE_IO_PROMPT_TRUNCATION_SUFFIX)
    assert RUNNER.extract_simple_io_response(stdout, prompt) == response


def test_simple_io_response_extractor_rejects_ambiguous_echo() -> None:
    prompt = "harmless prompt"
    block = f"> {prompt}\nP3_OK\n"
    stdout = block + block + "\n[ Prompt: 1.0 t/s | Generation: 2.0 t/s ]\n"
    with pytest.raises(ValueError, match="marker count mismatch"):
        RUNNER.extract_simple_io_response(stdout, prompt)


def test_heuristic_is_only_refusal_and_length_routing() -> None:
    markers = ("cannot assist",)
    refusal = RUNNER.heuristic_features("I cannot assist with that.", markers, 4)
    possible = RUNNER.heuristic_features("one two three four five", markers, 4)
    ambiguous = RUNNER.heuristic_features("one two", markers, 4)
    assert refusal["rule_state"] == "RULE_REFUSAL_CANDIDATE"
    assert possible["rule_state"] == "RULE_LONG_NONREFUSAL_AUDIT_CANDIDATE"
    assert ambiguous["rule_state"] == "RULE_SHORT_OR_AMBIGUOUS"


def test_frozen_heuristic_module_loads_with_dataclass_metadata() -> None:
    module = RUNNER.load_heuristic_module(ROOT, contract())
    judge = module.HeuristicResponseJudge()
    assert judge.minimum_compliance_tokens > 0


def test_private_cache_reuse_checks_full_identity(tmp_path: Path) -> None:
    identity = {"kind": "test", "seed": 11}
    identity_sha = RUNNER.canonical_sha256(identity)
    record_path = tmp_path / "record.json"
    RUNNER.atomic_write_json(
        record_path,
        {
            "execution_identity": identity,
            "execution_identity_sha256": identity_sha,
            "response": "private",
        },
    )
    record, cache_hit = RUNNER.run_private_invocation(
        identity=identity,
        prompt="unused",
        payload=None,
        private_record_path=record_path,
        staging_root=tmp_path / "staging",
        cli=Path("unused"),
        model=Path("unused"),
        parameters={},
        seed=11,
        device="unused",
        required_gpu_name="unused",
    )
    assert cache_hit is True
    assert record["response"] == "private"
    with pytest.raises(ValueError, match="identity conflict"):
        RUNNER.run_private_invocation(
            identity={"kind": "changed"},
            prompt="unused",
            payload=None,
            private_record_path=record_path,
            staging_root=tmp_path / "staging",
            cli=Path("unused"),
            model=Path("unused"),
            parameters={},
            seed=11,
            device="unused",
            required_gpu_name="unused",
        )
