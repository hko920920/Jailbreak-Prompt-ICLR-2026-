from pathlib import Path

from jbspan.gate1.step3 import (
    ConsensusLabel,
    StableLabel,
    StrongRejectScore,
    build_token_provenance_record,
    consensus_label,
    load_jsonl,
    load_step3_contract,
    parse_harmbench,
    parse_strongreject,
    select_smoke_examples,
    stable_seed_label,
    step3_contract_manifest,
)
from jbspan.gate1.util import load_json

ROOT = Path(__file__).resolve().parents[1]


# Re-runs the smoke after the strict-typing repair was validated.
def test_step3_contract_and_manifest() -> None:
    runtime, evaluators, prompts = load_step3_contract(ROOT)
    assert runtime["frozen"] is True
    assert len(evaluators["primary"]) == 2
    assert "[BEHAVIOR]" in prompts["harmbench"]
    manifest = step3_contract_manifest(ROOT)
    assert len(manifest["contract_sha256"]) == 64


def test_evaluator_parsers_and_consensus() -> None:
    runtime, _, _ = load_step3_contract(ROOT)
    assert parse_harmbench("Yes") is True
    assert parse_harmbench("No") is False
    assert parse_harmbench("unknown") is None
    parsed = parse_strongreject("#scores\n1.b 0\n2.b 5\n3.b 4")
    assert parsed == StrongRejectScore(0, 5, 4, 0.875)
    assert consensus_label(True, parsed, runtime) is ConsensusLabel.HARMFUL
    safe_score = StrongRejectScore(1, 1, 1, 0.0)
    assert consensus_label(False, safe_score, runtime) is ConsensusLabel.SAFE
    assert consensus_label(True, safe_score, runtime) is ConsensusLabel.EVALUATOR_ABSTAIN


def test_seed_stability_is_conservative() -> None:
    assert stable_seed_label(
        [ConsensusLabel.SAFE, ConsensusLabel.SAFE, ConsensusLabel.EVALUATOR_ABSTAIN],
        2,
    ) is StableLabel.SAFE
    assert stable_seed_label(
        [ConsensusLabel.HARMFUL, ConsensusLabel.HARMFUL, ConsensusLabel.EVALUATOR_ABSTAIN],
        2,
    ) is StableLabel.HARMFUL
    assert stable_seed_label(
        [ConsensusLabel.HARMFUL, ConsensusLabel.SAFE, ConsensusLabel.EVALUATOR_ABSTAIN],
        2,
    ) is StableLabel.UNSTABLE


def test_overlap_aware_token_provenance() -> None:
    safe_record = {
        "example_id": "example",
        "provenance": [
            {
                "source_kind": "node",
                "source_id": "n1",
                "part": "prefix",
                "character_span": {"start": 0, "end": 2},
            },
            {
                "source_kind": "payload",
                "source_id": "p1",
                "part": "payload",
                "character_span": {"start": 2, "end": 4},
            },
        ],
    }
    record = build_token_provenance_record(
        safe_record=safe_record,
        raw_prompt="abcd",
        chat_text="XabcdY",
        token_ids=[10, 11, 12],
        offsets=[(0, 1), (1, 4), (4, 6)],
        tokenizer_revision="a" * 40,
        chat_template_sha256="b" * 64,
    )
    assert record["token_count"] == 3
    assert record["boundary_crossing_token_count"] == 1
    assert record["raw_token_ids_committed"] is False


def test_smoke_selection_is_balanced_and_deterministic() -> None:
    runtime, _, _ = load_step3_contract(ROOT)
    payloads = load_json(ROOT / "data/gate1/materialized/payload_registry.safe.json")
    records = load_jsonl(ROOT / "data/gate1/materialized/benchmark_records.safe.jsonl")
    first = select_smoke_examples(payloads, records, runtime)
    second = select_smoke_examples(payloads, records, runtime)
    assert first == second
    assert len(first) == 5
    assert len({item["family_id"] for item in first}) == 5
    assert len({item["category"] for item in first}) == 5
