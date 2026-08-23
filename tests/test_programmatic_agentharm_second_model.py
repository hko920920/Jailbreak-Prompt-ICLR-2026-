from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jbspan.programmatic_agentharm.development_sweep import parse_behavior_specs

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_qwen_development_decision_is_self_identifying_and_terminal() -> None:
    decision = load_json(
        "data/programmatic_agentharm/development/qwen_development_decision.json"
    )
    recorded = decision.pop("decision_identity_sha256")
    assert recorded == canonical_sha256(decision)
    assert decision["status"] == "NO_ELIGIBLE_ATTACK_SIGNAL_ACROSS_QWEN_DEVELOPMENT"
    assert decision["resolved_behavior_count"] == 6
    assert decision["resolved_episode_count"] == 36
    assert decision["eligible_behavior_count"] == 0
    assert decision["eligible_pairs"] == []
    assert decision["next_operation"] == "RUN_PREDECLARED_LLAMA31_SECOND_MODEL"


def test_llama31_runtime_identity_and_tool_contract_are_frozen() -> None:
    runtime = load_json(
        "configs/programmatic_agentharm/runtime_llama31_second_model.json"
    )
    assert runtime["schema_version"] == "programmatic-agentharm-runtime-smoke-v1"
    assert runtime["frozen"] is True
    assert runtime["paper_validity"] is False

    target = runtime["target"]
    assert isinstance(target, dict)
    assert target["gguf_repo_id"] == "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
    assert target["gguf_revision"] == "bf5b95e96dac0462e2a09145ec66cae9a3f12067"
    assert target["gguf_files"] == [
        {
            "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            "sha256": "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c",
            "size": 4920739232,
        }
    ]

    agentharm = runtime["agentharm"]
    assert isinstance(agentharm, dict)
    assert agentharm["system_prompt_template"] == "llama-3.1"

    inspect_model = runtime["inspect_model"]
    assert isinstance(inspect_model, dict)
    assert inspect_model["emulate_tools"] is True
    assert inspect_model["model"] == "meta-llama-3.1-8b-instruct"

    boundary = runtime["claim_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["second_model_outputs_observed_before_freeze"] is False
    assert boundary["causal_oracle_allowed"] is False
    assert boundary["wavelet_allowed"] is False


def test_second_model_reuses_exact_qwen_development_matrix() -> None:
    qwen = load_json(
        "configs/programmatic_agentharm/development_behavior_sweep.json"
    )
    llama = load_json(
        "configs/programmatic_agentharm/second_model_llama31_sweep.json"
    )
    assert parse_behavior_specs(llama) == parse_behavior_specs(qwen)
    assert llama["candidate_ids"] == qwen["candidate_ids"]
    assert llama["canonical_variant"] == qwen["canonical_variant"]
    assert llama["decision_thresholds"] == qwen["decision_thresholds"]

    provenance = llama["provenance"]
    assert isinstance(provenance, dict)
    decision = load_json(
        "data/programmatic_agentharm/development/qwen_development_decision.json"
    )
    assert (
        provenance["qwen_decision_identity_sha256"]
        == decision["decision_identity_sha256"]
    )
    assert provenance["second_model_outputs_observed"] is False
    assert provenance["final_split_untouched"] is True
    assert provenance["heldout_split_untouched"] is True

    rule = llama["terminal_decision_rule"]
    assert isinstance(rule, dict)
    assert rule["absent_signal"] == (
        "STOP_AGENTHARM_PIVOT_AND_RETURN_TO_NATURAL_LANGUAGE_LOCALIZATION"
    )
