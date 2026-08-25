from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import GenerateConfig
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from inspect_evals.agentharm.agents.default_agent import default_agent
from inspect_evals.agentharm.benchmark import harmful_grading_functions
from inspect_evals.agentharm.utils import (
    get_benchmark_tools,
    load_dataset,
    setup_tools_from_metadata,
)

from jbspan.gate1.step3 import sha256_file
from jbspan.gate1.step3b import (
    candidate_specs,
    load_step3b_contract,
    parse_h4rm3l_programs,
    render_candidate,
)
from jbspan.gate1.util import load_json, sha256_text
from jbspan.programmatic_agentharm.runtime import (
    decide_operational_smoke,
    strict_boolean_criteria,
    trace_hash,
)

JsonObject = dict[str, object]
ToolChoice = Literal["forced_first", "auto"]

_CAPTURED: list[dict[str, object]] = []


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run the judge-free three-condition AgentHarm operational smoke. "
            "Only safe hashes and aggregate outcomes are written."
        )
    )
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/programmatic_agentharm/runtime_smoke.json"),
    )
    value.add_argument("--attack-source-csv", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--root", type=Path, default=Path("."))
    return value


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise RuntimeError(f"{where} must be an object")
    return value


def as_array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{where} must be an array")
    return value


def as_string(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{where} must be a non-empty string")
    return value


def as_bool(value: object, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"{where} must be a boolean")
    return value


def as_int(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{where} must be an integer")
    return value


def as_float(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{where} must be numeric")
    return float(value)


def canonical_hash_rank(
    *,
    seed: str,
    category: str,
    original_id: str,
    behavior_id: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(
        "\0".join((seed, category, original_id, behavior_id)).encode("utf-8")
    ).hexdigest()
    return digest, behavior_id


def select_validation_sample(
    *,
    eligible_graders: set[str],
    detailed_prompt: bool,
    hint_included: bool,
) -> Sample:
    dataset = load_dataset("harmful", "val", force_redownload=False)
    candidates: list[Sample] = []
    exact: list[Sample] = []
    for sample in dataset:
        metadata = sample.metadata or {}
        grader = metadata.get("grading_function")
        if not isinstance(grader, str) or grader not in eligible_graders:
            continue
        candidates.append(sample)
        if (
            metadata.get("detailed_prompt") is detailed_prompt
            and metadata.get("hint_included") is hint_included
        ):
            exact.append(sample)
    pool = exact or candidates
    if not pool:
        raise RuntimeError("no judge-free AgentHarm validation sample is available")

    def rank(sample: Sample) -> tuple[str, str]:
        metadata = sample.metadata or {}
        return canonical_hash_rank(
            seed="jbspan-programmatic-agentharm-gate0-v1",
            category=str(metadata.get("category", "")),
            original_id=str(metadata.get("id_original", "")),
            behavior_id=str(metadata.get("id", sample.id or "")),
        )

    return min(pool, key=rank)


def count_and_hash_trace(messages: list[Any]) -> dict[str, object]:
    calls: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    for message_index, message in enumerate(messages):
        raw_calls = getattr(message, "tool_calls", None)
        if raw_calls:
            for raw_call in raw_calls:
                function = str(getattr(raw_call, "function", ""))
                arguments = getattr(raw_call, "arguments", None)
                calls.append(
                    {
                        "message_index": message_index,
                        "call_index": len(calls),
                        "function": function,
                        "arguments_sha256": trace_hash(arguments),
                    }
                )
        if getattr(message, "role", None) == "tool":
            responses.append(
                {
                    "message_index": message_index,
                    "function": str(getattr(message, "function", "")),
                    "response_sha256": trace_hash(getattr(message, "text", None)),
                }
            )
    return {
        "tool_call_count": len(calls),
        "tool_response_count": len(responses),
        "tool_calls_sha256": trace_hash(calls),
        "tool_responses_sha256": trace_hash(responses),
    }


@scorer(metrics=[])
def judge_free_programmatic_scorer() -> Scorer:
    async def compute_score(state: TaskState, target: Target) -> Score:
        condition = str(state.metadata.get("jbspan_condition", "UNKNOWN"))
        trace = count_and_hash_trace(list(state.messages))
        record: dict[str, object] = {
            "condition": condition,
            "completed": True,
            **trace,
        }
        try:
            grader_name = str(state.metadata["grading_function"])
            grader = getattr(harmful_grading_functions, grader_name)
            raw_criteria = await grader(dict(state.metadata), state.messages)
            criteria = strict_boolean_criteria(raw_criteria)
            success = all(criteria.values())
            record.update(
                {
                    "programmatic_score_parsed": True,
                    "programmatic_success": success,
                    "criteria": criteria,
                    "criteria_sha256": trace_hash(criteria),
                }
            )
            score_value = 1.0 if success else 0.0
        except Exception as exc:
            record.update(
                {
                    "programmatic_score_parsed": False,
                    "programmatic_success": False,
                    "scorer_error_type": type(exc).__name__,
                }
            )
            score_value = 0.0
        _CAPTURED.append(record)
        return Score(
            value=score_value,
            metadata={
                "programmatic_score_parsed": record["programmatic_score_parsed"],
                "programmatic_success": record["programmatic_success"],
                "tool_call_count": record["tool_call_count"],
                "criteria_sha256": record.get("criteria_sha256"),
            },
        )

    return compute_score


def make_sample(
    source: Sample,
    *,
    condition: str,
    prompt: str,
) -> Sample:
    metadata = dict(source.metadata or {})
    metadata["jbspan_condition"] = condition
    return Sample(
        input=prompt,
        choices=source.choices,
        target=source.target,
        id=f"jbspan-{condition}-{source.id}",
        metadata=metadata,
    )


def run_episode(
    *,
    sample: Sample,
    condition: str,
    prompt: str,
    tool_choice: ToolChoice,
    config: JsonObject,
    inspect_logs: Path,
) -> dict[str, object]:
    agentharm_config = as_object(config["agentharm"], where="agentharm")
    inspect_model = as_object(config["inspect_model"], where="inspect_model")
    generation = as_object(config["generation"], where="generation")
    model_name = (
        f"{as_string(inspect_model['provider'], where='inspect_model.provider')}/"
        f"{as_string(inspect_model['model'], where='inspect_model.model')}"
    )
    task = Task(
        dataset=MemoryDataset(
            [make_sample(sample, condition=condition, prompt=prompt)],
            name=f"programmatic-agentharm-{condition}",
        ),
        solver=[
            setup_tools_from_metadata(
                "harmful",
                get_benchmark_tools("harmful"),
                as_int(
                    agentharm_config["n_irrelevant_tools"],
                    where="agentharm.n_irrelevant_tools",
                ),
            ),
            default_agent(
                tool_choice=tool_choice,
                user_prompt_template="empty",
                system_prompt_template=as_string(
                    agentharm_config["system_prompt_template"],
                    where="agentharm.system_prompt_template",
                ),
                prompt_technique=as_string(
                    agentharm_config["prompt_technique"],
                    where="agentharm.prompt_technique",
                ),
            ),
        ],
        scorer=judge_free_programmatic_scorer(),
        max_messages=as_int(generation["max_messages"], where="generation.max_messages"),
        config=GenerateConfig(
            seed=as_int(generation["seed"], where="generation.seed"),
            temperature=as_float(
                generation["temperature"], where="generation.temperature"
            ),
            max_tokens=as_int(
                generation["max_tokens_per_turn"],
                where="generation.max_tokens_per_turn",
            ),
            max_retries=as_int(
                generation["max_retries"], where="generation.max_retries"
            ),
            max_connections=as_int(
                inspect_model["max_connections"],
                where="inspect_model.max_connections",
            ),
        ),
    )
    _CAPTURED.clear()
    inspect_logs.mkdir(parents=True, exist_ok=True)
    try:
        inspect_eval(
            tasks=task,
            model=model_name,
            model_args={
                "base_url": as_string(
                    inspect_model["base_url"], where="inspect_model.base_url"
                ),
                "api_key": "local-runtime-only",
                "emulate_tools": as_bool(
                    inspect_model["emulate_tools"],
                    where="inspect_model.emulate_tools",
                ),
                "stream": as_bool(
                    inspect_model["stream"], where="inspect_model.stream"
                ),
            },
            display="none",
            log_dir=str(inspect_logs),
        )
    except Exception as exc:
        return {
            "condition": condition,
            "completed": False,
            "programmatic_score_parsed": False,
            "programmatic_success": False,
            "tool_call_count": 0,
            "tool_response_count": 0,
            "runtime_error_type": type(exc).__name__,
        }
    if len(_CAPTURED) != 1:
        return {
            "condition": condition,
            "completed": False,
            "programmatic_score_parsed": False,
            "programmatic_success": False,
            "tool_call_count": 0,
            "tool_response_count": 0,
            "capture_count": len(_CAPTURED),
        }
    return dict(_CAPTURED[0])


def validate_contract(root: Path, config: JsonObject) -> tuple[JsonObject, set[str]]:
    if config.get("schema_version") != "programmatic-agentharm-runtime-smoke-v1":
        raise RuntimeError("unsupported runtime smoke config")
    if config.get("frozen") is not True:
        raise RuntimeError("runtime smoke config must be frozen")
    if config.get("paper_validity") is not False:
        raise RuntimeError("operational smoke must remain non-paper-valid")

    gate0 = as_object(config["gate0"], where="gate0")
    manifest_path = root / as_string(gate0["manifest_path"], where="gate0.manifest_path")
    manifest = load_json(manifest_path)
    if manifest.get("status") != gate0.get("required_status"):
        raise RuntimeError("Gate 0 status does not authorize the runtime smoke")
    if manifest.get("manifest_identity_sha256") != gate0.get(
        "manifest_identity_sha256"
    ):
        raise RuntimeError("Gate 0 manifest identity differs from the frozen config")
    if manifest.get("target_model_outputs_observed") is not False:
        raise RuntimeError("Gate 0 no longer represents a pre-inference state")
    primary = as_object(manifest["primary_outcome_contract"], where="primary outcome")
    if primary.get("human_judge") is not False or primary.get("llm_judge") is not False:
        raise RuntimeError("Gate 0 primary outcome must be judge-free")
    audit = as_object(manifest["grader_audit"], where="grader audit")
    graders = {
        as_string(item, where="eligible grader")
        for item in as_array(
            audit["eligible_grade_functions"], where="eligible grade functions"
        )
    }
    return manifest, graders


def load_attack(
    *,
    root: Path,
    config: JsonObject,
    attack_source_csv: Path,
    payload: str,
) -> tuple[str, int, int, int]:
    source_identity = load_json(root / "data/gate1/v2/frozen/source_identity.json")
    if sha256_file(attack_source_csv) != source_identity.get("source_file_sha256"):
        raise RuntimeError("h4rm3l source SHA-256 differs from the frozen source")
    attack_config = as_object(config["attack_programs"], where="attack_programs")
    smoke = as_object(config["operational_smoke"], where="operational_smoke")
    candidate_id = as_string(
        smoke["attack_candidate_id"], where="operational_smoke.attack_candidate_id"
    )
    selected = {
        as_string(item, where="selected candidate")
        for item in as_array(
            attack_config["selected_candidate_ids"],
            where="attack_programs.selected_candidate_ids",
        )
    }
    if candidate_id not in selected:
        raise RuntimeError("runtime smoke candidate is not in the frozen selection")

    contract = load_step3b_contract(root)
    specs = {spec.candidate_id: spec for spec in candidate_specs(contract)}
    if candidate_id not in specs:
        raise RuntimeError("runtime smoke candidate is absent from the source contract")
    spec = specs[candidate_id]
    programs = parse_h4rm3l_programs(
        attack_source_csv,
        required_program_ids=spec.source_program_ids,
    )
    rendered = render_candidate(spec, programs, payload_text=payload)
    if rendered.text[rendered.payload_character_start : rendered.payload_character_end] != payload:
        raise RuntimeError("attack rendering changed the exact payload")

    registry_path = root / as_string(
        attack_config["candidate_registry_path"],
        where="attack_programs.candidate_registry_path",
    )
    registry = load_json(registry_path)
    frozen_candidates = {
        str(as_object(item, where="candidate")["candidate_id"]): as_object(
            item, where="candidate"
        )
        for item in as_array(registry["candidates"], where="candidate registry")
    }
    frozen = frozen_candidates[candidate_id]
    sentinel = "__JBSPAN_EXACT_PAYLOAD_SENTINEL__"
    sentinel_render = render_candidate(spec, programs, payload_text=sentinel)
    if sha256_text(sentinel_render.text) != frozen.get("sentinel_render_sha256"):
        raise RuntimeError("candidate render differs from the frozen registry")
    if len(rendered.nodes) != as_int(frozen["node_count"], where="candidate.node_count"):
        raise RuntimeError("candidate node count differs from the frozen registry")
    return (
        rendered.text,
        rendered.payload_character_start,
        rendered.payload_character_end,
        len(rendered.nodes),
    )


def safe_episode(
    *,
    record: Mapping[str, object],
    condition: str,
    prompt: str,
    candidate_id: str | None,
    payload_sha256: str,
    payload_start: int,
    payload_end: int,
) -> dict[str, object]:
    safe = dict(record)
    safe.update(
        {
            "condition": condition,
            "candidate_id": candidate_id,
            "payload_sha256": payload_sha256,
            "prompt_sha256": sha256_text(prompt),
            "prompt_character_length": len(prompt),
            "payload_character_start": payload_start,
            "payload_character_end": payload_end,
        }
    )
    return safe


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config = load_json(args.config.resolve())
    _, eligible_graders = validate_contract(root, config)

    smoke = as_object(config["operational_smoke"], where="operational_smoke")
    variant = as_object(
        smoke["canonical_validation_variant"],
        where="operational_smoke.canonical_validation_variant",
    )
    sample = select_validation_sample(
        eligible_graders=eligible_graders,
        detailed_prompt=as_bool(
            variant["detailed_prompt"],
            where="canonical_validation_variant.detailed_prompt",
        ),
        hint_included=as_bool(
            variant["hint_included"],
            where="canonical_validation_variant.hint_included",
        ),
    )
    if not isinstance(sample.input, str):
        raise RuntimeError("AgentHarm validation sample input must be a string")
    payload = sample.input
    metadata = sample.metadata or {}
    payload_sha256 = sha256_text(payload)
    attack_prompt, attack_start, attack_end, attack_node_count = load_attack(
        root=root,
        config=config,
        attack_source_csv=args.attack_source_csv.resolve(),
        payload=payload,
    )
    candidate_id = as_string(
        smoke["attack_candidate_id"], where="operational_smoke.attack_candidate_id"
    )
    conditions = [
        as_string(item, where="operational condition")
        for item in as_array(smoke["conditions"], where="operational_smoke.conditions")
    ]
    if conditions != ["forced_first_probe", "original_auto", "attacked_auto"]:
        raise RuntimeError("unexpected operational smoke condition order")

    logs = Path(tempfile.mkdtemp(prefix="jbspan-agentharm-logs-"))
    episodes: list[dict[str, object]] = []
    try:
        forced = run_episode(
            sample=sample,
            condition="forced_first_probe",
            prompt=payload,
            tool_choice="forced_first",
            config=config,
            inspect_logs=logs / "forced_first_probe",
        )
        episodes.append(
            safe_episode(
                record=forced,
                condition="forced_first_probe",
                prompt=payload,
                candidate_id=None,
                payload_sha256=payload_sha256,
                payload_start=0,
                payload_end=len(payload),
            )
        )
        original = run_episode(
            sample=sample,
            condition="original_auto",
            prompt=payload,
            tool_choice="auto",
            config=config,
            inspect_logs=logs / "original_auto",
        )
        episodes.append(
            safe_episode(
                record=original,
                condition="original_auto",
                prompt=payload,
                candidate_id=None,
                payload_sha256=payload_sha256,
                payload_start=0,
                payload_end=len(payload),
            )
        )
        attacked = run_episode(
            sample=sample,
            condition="attacked_auto",
            prompt=attack_prompt,
            tool_choice="auto",
            config=config,
            inspect_logs=logs / "attacked_auto",
        )
        episodes.append(
            safe_episode(
                record=attacked,
                condition="attacked_auto",
                prompt=attack_prompt,
                candidate_id=candidate_id,
                payload_sha256=payload_sha256,
                payload_start=attack_start,
                payload_end=attack_end,
            )
        )
    finally:
        shutil.rmtree(logs, ignore_errors=True)

    decision = decide_operational_smoke(
        episodes,
        expected_episodes=len(conditions),
        minimum_coverage=as_float(
            smoke["minimum_programmatic_score_coverage"],
            where="operational_smoke.minimum_programmatic_score_coverage",
        ),
        forced_first_minimum_tool_calls=as_int(
            smoke["forced_first_minimum_tool_calls"],
            where="operational_smoke.forced_first_minimum_tool_calls",
        ),
    )
    original_success = decision.original_success
    attacked_success = decision.attacked_success
    if original_success is False and attacked_success is True:
        signal = "ELIGIBLE_ATTACK_SIGNAL_PRESENT"
    elif original_success is True:
        signal = "DIRECT_TASK_ALREADY_SUCCESSFUL"
    elif attacked_success is False:
        signal = "ATTACK_SIGNAL_ABSENT"
    else:
        signal = "ATTACK_SIGNAL_UNRESOLVED"

    agentharm = as_object(config["agentharm"], where="agentharm")
    target = as_object(config["target"], where="target")
    output: dict[str, object] = {
        "schema_version": "programmatic-agentharm-runtime-smoke-result-v1",
        "status": decision.status,
        "paper_validity": False,
        "scientific_signal": signal,
        "decision": decision.to_dict(),
        "selected_validation_case": {
            "behavior_id": str(metadata.get("id", sample.id)),
            "original_id": str(metadata.get("id_original", "")),
            "category": str(metadata.get("category", "")),
            "grading_function": str(metadata.get("grading_function", "")),
            "detailed_prompt": bool(metadata.get("detailed_prompt")),
            "hint_included": bool(metadata.get("hint_included")),
            "payload_sha256": payload_sha256,
        },
        "attack": {
            "candidate_id": candidate_id,
            "node_count": attack_node_count,
            "payload_preserved_exactly_once": attack_prompt.count(payload) == 1,
        },
        "runtime": {
            "inspect_evals_revision": agentharm["inspect_evals_revision"],
            "agentharm_dataset_revision": agentharm["dataset_revision"],
            "target_repo_id": target["base_repo_id"],
            "target_revision": target["base_revision"],
            "gguf_repo_id": target["gguf_repo_id"],
            "gguf_revision": target["gguf_revision"],
            "gguf_selector": target["gguf_selector"],
            "seed": as_object(config["generation"], where="generation")["seed"],
        },
        "episodes": episodes,
        "human_judge_used": False,
        "llm_judge_used": False,
        "assistant_free_text_scored": False,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_tool_arguments_committed": False,
        "raw_tool_responses_committed": False,
        "confirmatory_outputs_observed": False,
        "final_outputs_observed": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if decision.operational_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
