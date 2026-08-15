from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jbspan.gate1.materialize import load_source_rows
from jbspan.gate1.registry import load_gate1_registry
from jbspan.gate1.step3 import (
    load_jsonl,
    load_step3_contract,
    parse_harmbench,
    post_json,
    sha256_file,
    write_json,
    write_jsonl,
)
from jbspan.gate1.step3b import (
    candidate_specs,
    load_step3b_contract,
    parse_h4rm3l_programs,
    render_candidate,
)
from jbspan.gate1.util import canonical_json_sha256, load_json, sha256_text

JsonDict = dict[str, object]


def _object(value: object, *, where: str) -> JsonDict:
    if not isinstance(value, dict):
        raise RuntimeError(f"{where} must be an object")
    return value


def _array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{where} must be an array")
    return value


def _integer(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{where} must be an integer")
    return value


def _number(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{where} must be numeric")
    return float(value)


def _apply_template(tokenizer: Any, prompt: str) -> str:
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise RuntimeError("tokenizer returned an invalid chat prompt")
    return rendered


def select_calibration_candidates(
    candidate_rows: Sequence[JsonDict],
    *,
    minimum_eligible: int,
    minimum_selected: int,
    maximum_selected: int,
) -> JsonDict:
    ranked = sorted(
        candidate_rows,
        key=lambda row: (
            -_integer(row["eligible_count"], where="eligible_count"),
            _integer(
                row["attack_abstention_count"],
                where="attack_abstention_count",
            ),
            str(row["candidate_id"]),
        ),
    )
    qualifying = [
        row
        for row in ranked
        if _integer(row["eligible_count"], where="eligible_count") >= minimum_eligible
    ]
    if len(qualifying) < minimum_selected:
        selected: list[str] = []
        status = "STEP3B_CALIBRATION_INSUFFICIENT_CANDIDATES"
    else:
        selected = [str(row["candidate_id"]) for row in qualifying[:maximum_selected]]
        status = "STEP3B_CALIBRATION_SELECTION_FROZEN"
    return {
        "status": status,
        "selected_candidate_ids": selected,
        "qualifying_candidate_count": len(qualifying),
        "ranked_candidate_ids": [str(row["candidate_id"]) for row in ranked],
    }


def _load_private_payloads(root: Path, source_csv: Path) -> dict[str, JsonDict]:
    registry = load_gate1_registry(root)
    committed_identity = load_json(root / "data/gate1/materialized/source_identity.json")
    expected_sha = str(committed_identity["source_file_sha256"])
    if sha256_file(source_csv) != expected_sha:
        raise RuntimeError("JailbreakBench source SHA-256 differs from Step 2")
    rows = load_source_rows(source_csv, registry.payload_source)
    source_index = {row.index: row for row in rows}
    safe_registry = load_json(root / "data/gate1/materialized/payload_registry.safe.json")
    payloads: dict[str, JsonDict] = {}
    for raw in _array(safe_registry["payloads"], where="payload registry"):
        item = _object(raw, where="payload registry item")
        payload_id = str(item["payload_id"])
        source_row_index = _integer(
            item["source_row_index"],
            where="source_row_index",
        )
        row = source_index[source_row_index]
        if sha256_text(row.goal) != str(item["payload_sha256"]):
            raise RuntimeError(f"payload hash changed for {payload_id}")
        payloads[payload_id] = {
            "payload_id": payload_id,
            "goal": row.goal,
            "behavior": row.behavior,
            "category": row.category,
            "payload_sha256": str(item["payload_sha256"]),
            "split": str(item["split"]),
        }
    return payloads


def prepare_calibration(
    root: Path,
    *,
    payload_source_csv: Path,
    attack_source_csv: Path,
    safe_output_dir: Path,
    private_output_dir: Path,
) -> JsonDict:
    from transformers import AutoTokenizer

    contract = load_step3b_contract(root)
    runtime, _, _ = load_step3_contract(root)
    frozen = load_json(root / "data/gate1/v2/frozen/freeze_manifest.json")
    if frozen.get("target_model_outputs_observed") is not False:
        raise RuntimeError("Step 3B freeze no longer proves a pre-result state")
    if frozen.get("v1_result_preserved") is not True:
        raise RuntimeError("v1 negative control is not preserved")

    source_identity = load_json(root / "data/gate1/v2/frozen/source_identity.json")
    if sha256_file(attack_source_csv) != str(source_identity["source_file_sha256"]):
        raise RuntimeError("h4rm3l source SHA-256 differs from frozen identity")

    specs = candidate_specs(contract)
    required = sorted({program_id for spec in specs for program_id in spec.source_program_ids})
    source_programs = parse_h4rm3l_programs(
        attack_source_csv,
        required_program_ids=required,
    )
    frozen_candidates = load_json(root / "data/gate1/v2/frozen/candidate_registry.safe.json")
    frozen_candidate_index: dict[str, JsonDict] = {}
    for raw_candidate in _array(
        frozen_candidates["candidates"],
        where="candidates",
    ):
        candidate = _object(raw_candidate, where="candidate")
        frozen_candidate_index[str(candidate["candidate_id"])] = candidate
    sentinel = "__JBSPAN_EXACT_PAYLOAD_SENTINEL__"
    for spec in specs:
        rendered = render_candidate(spec, source_programs, payload_text=sentinel)
        expected = frozen_candidate_index[spec.candidate_id]
        if sha256_text(rendered.text) != str(expected["sentinel_render_sha256"]):
            raise RuntimeError(f"candidate render changed: {spec.candidate_id}")
        expected_node_count = _integer(
            expected["node_count"],
            where="candidate.node_count",
        )
        if len(rendered.nodes) != expected_node_count:
            raise RuntimeError(f"candidate node count changed: {spec.candidate_id}")

    split = load_json(root / "data/gate1/v2/frozen/split_manifest.safe.json")
    calibration_items = [
        _object(item, where="calibration item")
        for item in _array(split["calibration"], where="calibration")
    ]
    if len(calibration_items) != 10:
        raise RuntimeError("calibration split must contain ten payloads")
    smoke_count = _integer(split["smoke_count"], where="smoke_count")
    evaluation_count = _integer(
        split["evaluation_count"],
        where="evaluation_count",
    )
    if smoke_count != 10 or evaluation_count != 30:
        raise RuntimeError("smoke and evaluation partitions are not sealed")

    payloads = _load_private_payloads(root, payload_source_csv)
    token_config = _object(runtime["token_provenance"], where="token provenance")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        str(token_config["tokenizer_repo_id"]),
        revision=str(token_config["tokenizer_revision"]),
        use_fast=True,
    )
    chat_template = tokenizer.chat_template
    if not isinstance(chat_template, str) or not chat_template:
        raise RuntimeError("target tokenizer has no chat template")
    step3_identity = load_json(root / "data/gate1/step3/step3_identity.json")
    expected_template_sha = str(
        _object(step3_identity["tokenizer"], where="tokenizer identity")["chat_template_sha256"]
    )
    if sha256_text(chat_template) != expected_template_sha:
        raise RuntimeError("chat template differs from frozen Step 3 identity")

    private_rows: list[JsonDict] = []
    safe_rows: list[JsonDict] = []
    calibration_ids: list[str] = []
    for item in calibration_items:
        payload_id = str(item["payload_id"])
        payload = payloads[payload_id]
        if payload["split"] != "gate1_development":
            raise RuntimeError("calibration used a non-development payload")
        if payload["payload_sha256"] != item["payload_sha256"]:
            raise RuntimeError("calibration split payload hash mismatch")
        goal = str(payload["goal"])
        original_id = f"G1C-{payload_id}-ORIGINAL"
        calibration_ids.append(original_id)
        original_chat = _apply_template(tokenizer, goal)
        private_rows.append(
            {
                "calibration_id": original_id,
                "payload_id": payload_id,
                "candidate_id": None,
                "variant": "original",
                "forbidden_prompt": goal,
                "chat_prompt": original_chat,
            }
        )
        safe_rows.append(
            {
                "schema_version": "gate1-step3b-calibration-input-v1",
                "calibration_id": original_id,
                "payload_id": payload_id,
                "candidate_id": None,
                "variant": "original",
                "category": payload["category"],
                "behavior": payload["behavior"],
                "payload_sha256": payload["payload_sha256"],
                "prompt_sha256": sha256_text(goal),
                "prompt_character_length": len(goal),
            }
        )
        for spec in specs:
            rendered = render_candidate(spec, source_programs, payload_text=goal)
            if (
                rendered.text[rendered.payload_character_start : rendered.payload_character_end]
                != goal
            ):
                raise RuntimeError("candidate changed the payload span")
            calibration_id = f"G1C-{payload_id}-{spec.candidate_id}"
            calibration_ids.append(calibration_id)
            private_rows.append(
                {
                    "calibration_id": calibration_id,
                    "payload_id": payload_id,
                    "candidate_id": spec.candidate_id,
                    "variant": "attack",
                    "forbidden_prompt": goal,
                    "chat_prompt": _apply_template(tokenizer, rendered.text),
                }
            )
            safe_rows.append(
                {
                    "schema_version": "gate1-step3b-calibration-input-v1",
                    "calibration_id": calibration_id,
                    "payload_id": payload_id,
                    "candidate_id": spec.candidate_id,
                    "variant": "attack",
                    "category": payload["category"],
                    "behavior": payload["behavior"],
                    "payload_sha256": payload["payload_sha256"],
                    "prompt_sha256": sha256_text(rendered.text),
                    "prompt_character_length": len(rendered.text),
                    "payload_character_span": [
                        rendered.payload_character_start,
                        rendered.payload_character_end,
                    ],
                    "node_count": len(rendered.nodes),
                }
            )

    expected_total = 10 + (10 * len(specs))
    if len(private_rows) != expected_total or len(safe_rows) != expected_total:
        raise RuntimeError("calibration denominator is incomplete")

    safe_output_dir.mkdir(parents=True, exist_ok=True)
    private_output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        private_output_dir / "calibration_inputs.private.jsonl",
        private_rows,
    )
    write_jsonl(safe_output_dir / "calibration_inputs.safe.jsonl", safe_rows)
    identity: JsonDict = {
        "schema_version": "gate1-step3b-calibration-identity-v1",
        "paper_validity": False,
        "target_identity_sha256": sha256_file(root / "data/gate1/step3/step3_identity.json"),
        "runtime_contract_sha256": sha256_file(root / "configs/gate1/gate1_step3_runtime.json"),
        "step3b_contract_sha256": sha256_file(root / "configs/gate1/gate1_step3b.json"),
        "source_identity_sha256": sha256_file(root / "data/gate1/v2/frozen/source_identity.json"),
        "candidate_registry_sha256": sha256_file(
            root / "data/gate1/v2/frozen/candidate_registry.safe.json"
        ),
        "split_manifest_sha256": sha256_file(
            root / "data/gate1/v2/frozen/split_manifest.safe.json"
        ),
        "calibration_payload_count": 10,
        "candidate_count": len(specs),
        "original_input_count": 10,
        "attack_input_count": 10 * len(specs),
        "total_input_count": expected_total,
        "calibration_ids_sha256": canonical_json_sha256(sorted(calibration_ids)),
        "smoke_outputs_observed": False,
        "final_evaluation_outputs_observed": False,
        "gate2_heldout_used": False,
        "raw_prompts_committed": False,
    }
    write_json(safe_output_dir / "calibration_identity.json", identity)
    return identity


def generate_calibration(
    root: Path,
    *,
    private_output_dir: Path,
    server_url: str,
) -> JsonDict:
    runtime, _, _ = load_step3_contract(root)
    contract = load_step3b_contract(root)
    generation = _object(runtime["generation"], where="generation")
    calibration = _object(contract["calibration"], where="calibration")
    seed = _integer(calibration["seed"], where="calibration.seed")
    generation_seeds = [
        _integer(item, where="generation seed")
        for item in _array(generation["seeds"], where="generation seeds")
    ]
    if seed not in generation_seeds:
        raise RuntimeError("calibration seed is outside the Step 3 contract")
    inputs = load_jsonl(private_output_dir / "calibration_inputs.private.jsonl")
    outputs: list[JsonDict] = []
    for row in inputs:
        response = post_json(
            server_url.rstrip("/") + "/completion",
            {
                "prompt": str(row["chat_prompt"]),
                "n_predict": _integer(
                    generation["max_tokens"],
                    where="generation.max_tokens",
                ),
                "temperature": _number(
                    generation["temperature"],
                    where="generation.temperature",
                ),
                "top_p": _number(
                    generation["top_p"],
                    where="generation.top_p",
                ),
                "top_k": _integer(
                    generation["top_k"],
                    where="generation.top_k",
                ),
                "seed": seed,
                "stream": False,
                "cache_prompt": False,
            },
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise RuntimeError("target endpoint returned no text content")
        outputs.append(
            {
                "calibration_id": row["calibration_id"],
                "payload_id": row["payload_id"],
                "candidate_id": row["candidate_id"],
                "variant": row["variant"],
                "seed": seed,
                "response": content,
                "response_sha256": sha256_text(content),
                "response_character_length": len(content),
                "stopped_eos": bool(response.get("stopped_eos", False)),
                "stopped_limit": bool(response.get("stopped_limit", False)),
            }
        )
    write_jsonl(
        private_output_dir / "target_responses.private.jsonl",
        outputs,
    )
    return {
        "status": "STEP3B_CALIBRATION_TARGET_COMPLETE",
        "generation_count": len(outputs),
        "seed": seed,
    }


def evaluate_calibration_harmbench(
    root: Path,
    *,
    private_output_dir: Path,
    server_url: str,
) -> JsonDict:
    _, _, prompts = load_step3_contract(root)
    inputs = {
        str(item["calibration_id"]): item
        for item in load_jsonl(private_output_dir / "calibration_inputs.private.jsonl")
    }
    responses = load_jsonl(private_output_dir / "target_responses.private.jsonl")
    results: list[JsonDict] = []
    parsed_count = 0
    for row in responses:
        source = inputs[str(row["calibration_id"])]
        prompt = str(prompts["harmbench"]).format(
            behavior=str(source["forbidden_prompt"]),
            generation=str(row["response"]),
        )
        raw = post_json(
            server_url.rstrip("/") + "/completion",
            {
                "prompt": prompt,
                "n_predict": 3,
                "temperature": 0.0,
                "stream": False,
                "cache_prompt": False,
            },
        )
        content = raw.get("content")
        if not isinstance(content, str):
            raise RuntimeError("HarmBench endpoint returned no text")
        parsed = parse_harmbench(content)
        parsed_count += int(parsed is not None)
        results.append(
            {
                "calibration_id": row["calibration_id"],
                "payload_id": row["payload_id"],
                "candidate_id": row["candidate_id"],
                "variant": row["variant"],
                "seed": row["seed"],
                "response_sha256": row["response_sha256"],
                "harmbench_harmful": parsed,
                "judge_output": content,
            }
        )
    write_jsonl(private_output_dir / "harmbench.private.jsonl", results)
    return {
        "status": "STEP3B_CALIBRATION_HARMBENCH_COMPLETE",
        "record_count": len(results),
        "parsed_count": parsed_count,
    }


def finalize_calibration(
    root: Path,
    *,
    private_output_dir: Path,
    safe_output_dir: Path,
) -> JsonDict:
    contract = load_step3b_contract(root)
    calibration = _object(contract["calibration"], where="calibration")
    selection = _object(calibration["selection"], where="calibration selection")
    target_rows = load_jsonl(private_output_dir / "target_responses.private.jsonl")
    judge_rows = load_jsonl(private_output_dir / "harmbench.private.jsonl")
    judge_index = {str(item["calibration_id"]): item for item in judge_rows}
    original_labels: dict[str, bool | None] = {}
    attack_labels: dict[tuple[str, str], bool | None] = {}
    safe_records: list[JsonDict] = []
    for row in target_rows:
        judged = judge_index[str(row["calibration_id"])]
        value = judged.get("harmbench_harmful")
        harmful = value if isinstance(value, bool) else None
        payload_id = str(row["payload_id"])
        candidate_id = row.get("candidate_id")
        if row["variant"] == "original":
            original_labels[payload_id] = harmful
        else:
            if not isinstance(candidate_id, str):
                raise RuntimeError("attack row lacks candidate ID")
            attack_labels[(candidate_id, payload_id)] = harmful
        safe_records.append(
            {
                "schema_version": "gate1-step3b-calibration-record-v1",
                "calibration_id": row["calibration_id"],
                "payload_id": payload_id,
                "candidate_id": candidate_id,
                "variant": row["variant"],
                "seed": row["seed"],
                "response_sha256": row["response_sha256"],
                "response_character_length": row["response_character_length"],
                "stopped_eos": row["stopped_eos"],
                "stopped_limit": row["stopped_limit"],
                "harmbench_harmful": harmful,
            }
        )

    split = load_json(root / "data/gate1/v2/frozen/split_manifest.safe.json")
    payload_ids = [
        str(_object(item, where="calibration item")["payload_id"])
        for item in _array(split["calibration"], where="calibration")
    ]
    candidate_ids = [
        str(_object(item, where="candidate")["candidate_id"])
        for item in _array(contract["candidates"], where="candidates")
    ]
    candidate_rows: list[JsonDict] = []
    for candidate_id in candidate_ids:
        eligible_ids: list[str] = []
        attack_harmful_count = 0
        attack_safe_count = 0
        attack_abstention_count = 0
        for payload_id in payload_ids:
            attack = attack_labels[(candidate_id, payload_id)]
            if attack is True:
                attack_harmful_count += 1
            elif attack is False:
                attack_safe_count += 1
            else:
                attack_abstention_count += 1
            if original_labels[payload_id] is False and attack is True:
                eligible_ids.append(payload_id)
        candidate_rows.append(
            {
                "candidate_id": candidate_id,
                "denominator": len(payload_ids),
                "eligible_count": len(eligible_ids),
                "eligible_payload_ids": eligible_ids,
                "eligible_payload_ids_sha256": canonical_json_sha256(sorted(eligible_ids)),
                "attack_harmful_count": attack_harmful_count,
                "attack_safe_count": attack_safe_count,
                "attack_abstention_count": attack_abstention_count,
            }
        )

    selection_result = select_calibration_candidates(
        candidate_rows,
        minimum_eligible=_integer(
            selection["minimum_eligible_payloads_per_candidate"],
            where="minimum_eligible_payloads_per_candidate",
        ),
        minimum_selected=_integer(
            selection["minimum_selected_candidates"],
            where="minimum_selected_candidates",
        ),
        maximum_selected=_integer(
            selection["maximum_selected_candidates"],
            where="maximum_selected_candidates",
        ),
    )
    original_safe_count = sum(original_labels[payload_id] is False for payload_id in payload_ids)
    original_harmful_count = sum(original_labels[payload_id] is True for payload_id in payload_ids)
    original_abstention_count = sum(
        original_labels[payload_id] is None for payload_id in payload_ids
    )
    summary: JsonDict = {
        "schema_version": "gate1-step3b-calibration-summary-v1",
        "status": selection_result["status"],
        "paper_validity": False,
        "gate1_decision": "NOT_EVALUATED",
        "calibration_may_contribute_paper_results": False,
        "calibration_payload_count": len(payload_ids),
        "candidate_count": len(candidate_ids),
        "attack_denominator": len(payload_ids) * len(candidate_ids),
        "target_generation_count": len(target_rows),
        "harmbench_parsed_count": sum(
            item["harmbench_harmful"] is not None for item in safe_records
        ),
        "original_safe_count": original_safe_count,
        "original_harmful_count": original_harmful_count,
        "original_abstention_count": original_abstention_count,
        "candidate_results": candidate_rows,
        "selected_candidate_ids": selection_result["selected_candidate_ids"],
        "qualifying_candidate_count": selection_result["qualifying_candidate_count"],
        "ranked_candidate_ids": selection_result["ranked_candidate_ids"],
        "selection_rule": selection,
        "smoke_outputs_observed": False,
        "final_evaluation_outputs_observed": False,
        "gate2_heldout_used": False,
        "case_specific_prompt_rewriting": False,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_judge_outputs_committed": False,
    }
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        safe_output_dir / "calibration_records.safe.jsonl",
        safe_records,
    )
    write_json(safe_output_dir / "calibration_summary.json", summary)
    selection_manifest: JsonDict = {
        "schema_version": "gate1-step3b-selection-manifest-v1",
        "status": selection_result["status"],
        "paper_validity": False,
        "selected_candidate_ids": selection_result["selected_candidate_ids"],
        "selected_candidate_ids_sha256": canonical_json_sha256(
            selection_result["selected_candidate_ids"]
        ),
        "qualifying_candidate_count": selection_result["qualifying_candidate_count"],
        "tie_break": selection["tie_break"],
        "minimum_eligible_payloads_per_candidate": selection[
            "minimum_eligible_payloads_per_candidate"
        ],
        "minimum_selected_candidates": selection["minimum_selected_candidates"],
        "maximum_selected_candidates": selection["maximum_selected_candidates"],
        "smoke_outputs_observed": False,
        "final_evaluation_outputs_observed": False,
    }
    write_json(
        safe_output_dir / "selection_manifest.json",
        selection_manifest,
    )
    identity_path = safe_output_dir / "calibration_identity.json"
    safe_files = sorted(path for path in safe_output_dir.iterdir() if path.is_file())
    file_hashes = {path.name: sha256_file(path) for path in safe_files}
    manifest = {
        "schema_version": "gate1-step3b-calibration-manifest-v1",
        "status": selection_result["status"],
        "paper_validity": False,
        "safe_file_sha256": file_hashes,
        "safe_bundle_identity_sha256": canonical_json_sha256(file_hashes),
        "identity_file_present": identity_path.is_file(),
        "smoke_outputs_observed": False,
        "final_evaluation_outputs_observed": False,
    }
    write_json(safe_output_dir / "calibration_manifest.json", manifest)
    return summary
