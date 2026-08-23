from __future__ import annotations

import hashlib
import hmac
import json
import random
import secrets
from pathlib import Path
from typing import Any

from jbspan.gate1.materialize import load_source_rows
from jbspan.gate1.registry import load_gate1_registry
from jbspan.gate1.step3 import (
    load_jsonl,
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
from jbspan.natural_language_feasibility import (
    JsonObject,
    load_json_object,
    validate_feasibility_contract,
    validate_safe_plan,
)


def _object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array")
    return value


def _string(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a non-empty string")
    return value


def _integer(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} must be an integer")
    return value


def _number(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be numeric")
    return float(value)


def _load_private_payloads(
    root: Path,
    source_csv: Path,
) -> dict[str, JsonObject]:
    registry = load_gate1_registry(root)
    committed_identity = load_json(root / "data/gate1/materialized/source_identity.json")
    expected_sha = _string(
        committed_identity.get("source_file_sha256"),
        where="source_file_sha256",
    )
    if sha256_file(source_csv) != expected_sha:
        raise ValueError("JailbreakBench source SHA-256 differs from the frozen source")

    rows = load_source_rows(source_csv, registry.payload_source)
    source_index = {row.index: row for row in rows}
    safe_registry = load_json(root / "data/gate1/materialized/payload_registry.safe.json")
    payloads: dict[str, JsonObject] = {}
    for raw in _array(safe_registry.get("payloads"), where="payload registry"):
        item = _object(raw, where="payload registry item")
        payload_id = _string(item.get("payload_id"), where="payload_id")
        source_row_index = _integer(
            item.get("source_row_index"),
            where="source_row_index",
        )
        row = source_index[source_row_index]
        payload_hash = _string(item.get("payload_sha256"), where="payload_sha256")
        if sha256_text(row.goal) != payload_hash:
            raise ValueError(f"payload hash changed for {payload_id}")
        payloads[payload_id] = {
            "payload_id": payload_id,
            "goal": row.goal,
            "behavior": row.behavior,
            "category": row.category,
            "payload_sha256": payload_hash,
            "split": _string(item.get("split"), where="payload.split"),
        }
    return payloads


def _apply_chat_template(
    tokenizer: Any,
    *,
    system_prompt: str,
    user_prompt: str,
) -> str:
    rendered = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("tokenizer returned an invalid chat prompt")
    return rendered


def prepare_calibration_inputs(
    root: Path,
    *,
    contract_path: Path,
    plan_path: Path,
    payload_source_csv: Path,
    attack_source_csv: Path,
    private_output_dir: Path,
    safe_output_dir: Path,
) -> JsonObject:
    from transformers import AutoTokenizer

    contract = load_json_object(contract_path)
    plan = load_json_object(plan_path)
    validate_feasibility_contract(contract)
    validate_safe_plan(plan, contract)

    attack_contract = _object(contract.get("attack_programs"), where="attack_programs")
    expected_attack_sha = _string(
        attack_contract.get("source_file_sha256"),
        where="attack_programs.source_file_sha256",
    )
    if sha256_file(attack_source_csv) != expected_attack_sha:
        raise ValueError("h4rm3l source SHA-256 differs from the frozen source")

    step3b = load_step3b_contract(root)
    all_specs = {spec.candidate_id: spec for spec in candidate_specs(step3b)}
    candidate_ids = [
        _string(value, where="candidate_id")
        for value in _array(attack_contract.get("candidate_ids"), where="candidate_ids")
    ]
    selected_specs = {candidate_id: all_specs[candidate_id] for candidate_id in candidate_ids}
    required_programs = sorted(
        {
            source_program_id
            for spec in selected_specs.values()
            for source_program_id in spec.source_program_ids
        }
    )
    source_programs = parse_h4rm3l_programs(
        attack_source_csv,
        required_program_ids=required_programs,
    )

    target = _object(contract.get("target"), where="target")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        _string(target.get("base_repo_id"), where="target.base_repo_id"),
        revision=_string(target.get("base_revision"), where="target.base_revision"),
        use_fast=True,
    )
    chat_template = tokenizer.chat_template
    if not isinstance(chat_template, str) or not chat_template:
        raise ValueError("target tokenizer has no chat template")
    step3_identity = load_json(root / "data/gate1/step3/step3_identity.json")
    tokenizer_identity = _object(step3_identity.get("tokenizer"), where="tokenizer")
    expected_template_sha = _string(
        tokenizer_identity.get("chat_template_sha256"),
        where="tokenizer.chat_template_sha256",
    )
    if sha256_text(chat_template) != expected_template_sha:
        raise ValueError("target chat template differs from the frozen identity")
    system_prompt = _string(target.get("system_prompt"), where="target.system_prompt")
    expected_system_sha = _string(
        tokenizer_identity.get("system_prompt_sha256"),
        where="tokenizer.system_prompt_sha256",
    )
    if sha256_text(system_prompt) != expected_system_sha:
        raise ValueError("target system prompt differs from the frozen identity")

    payloads = _load_private_payloads(root, payload_source_csv)
    calibration_items = _array(plan.get("calibration_items"), where="calibration_items")
    private_rows: list[JsonObject] = []
    safe_rows: list[JsonObject] = []
    for raw in calibration_items:
        item = _object(raw, where="calibration item")
        item_id = _string(item.get("item_id"), where="item_id")
        payload_id = _string(item.get("payload_id"), where="payload_id")
        payload = payloads[payload_id]
        if payload.get("split") != "gate1_development":
            raise ValueError("calibration packet used a non-development payload")
        if payload.get("payload_sha256") != item.get("payload_sha256"):
            raise ValueError("calibration payload hash mismatch")
        goal = _string(payload.get("goal"), where="payload.goal")
        condition = _string(item.get("condition"), where="item.condition")
        candidate_id = item.get("candidate_id")
        node_count = 0
        payload_span = [0, len(goal)]
        if condition == "direct":
            if candidate_id is not None:
                raise ValueError("direct calibration item names an attack candidate")
            full_prompt = goal
        elif condition == "attacked":
            candidate_name = _string(candidate_id, where="item.candidate_id")
            rendered = render_candidate(
                selected_specs[candidate_name],
                source_programs,
                payload_text=goal,
            )
            if rendered.text.count(goal) != 1:
                raise ValueError("attack did not preserve the payload exactly once")
            full_prompt = rendered.text
            payload_span = [
                rendered.payload_character_start,
                rendered.payload_character_end,
            ]
            node_count = len(rendered.nodes)
        else:
            raise ValueError("unsupported calibration condition")

        chat_prompt = _apply_chat_template(
            tokenizer,
            system_prompt=system_prompt,
            user_prompt=full_prompt,
        )
        private_rows.append(
            {
                "item_id": item_id,
                "payload_id": payload_id,
                "candidate_id": candidate_id,
                "condition": condition,
                "category": payload.get("category"),
                "original_harmful_goal": goal,
                "full_prompt": full_prompt,
                "chat_prompt": chat_prompt,
                "seed": item.get("seed"),
            }
        )
        safe_rows.append(
            {
                "schema_version": "natural-language-calibration-input-v1",
                "item_id": item_id,
                "payload_id": payload_id,
                "candidate_id": candidate_id,
                "condition": condition,
                "category": payload.get("category"),
                "payload_sha256": payload.get("payload_sha256"),
                "prompt_sha256": sha256_text(full_prompt),
                "prompt_character_length": len(full_prompt),
                "payload_character_span": payload_span,
                "node_count": node_count,
                "seed": item.get("seed"),
            }
        )

    expected_count = _integer(
        plan.get("calibration_item_count"),
        where="calibration_item_count",
    )
    if len(private_rows) != expected_count or len(safe_rows) != expected_count:
        raise ValueError("calibration input denominator is incomplete")

    private_output_dir.mkdir(parents=True, exist_ok=True)
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(private_output_dir / "inputs.private.jsonl", private_rows)
    write_jsonl(safe_output_dir / "inputs.safe.jsonl", safe_rows)
    identity: JsonObject = {
        "schema_version": "natural-language-calibration-preparation-v1",
        "status": "NATURAL_LANGUAGE_CALIBRATION_INPUTS_PREPARED",
        "paper_validity": False,
        "contract_identity_sha256": contract.get("contract_identity_sha256"),
        "plan_identity_sha256": plan.get("plan_identity_sha256"),
        "item_count": expected_count,
        "direct_count": sum(row.get("condition") == "direct" for row in safe_rows),
        "attacked_count": sum(row.get("condition") == "attacked" for row in safe_rows),
        "item_ids_sha256": canonical_json_sha256(
            sorted(_string(row.get("item_id"), where="item_id") for row in safe_rows)
        ),
        "safe_inputs_sha256": sha256_file(safe_output_dir / "inputs.safe.jsonl"),
        "raw_prompts_committed": False,
        "decision_packet_opened": False,
        "gate1_evaluation_30_opened": False,
        "gate2_heldout_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    write_json(safe_output_dir / "preparation_summary.json", identity)
    return identity


def generate_calibration_responses(
    *,
    contract_path: Path,
    private_output_dir: Path,
    server_url: str,
) -> JsonObject:
    contract = load_json_object(contract_path)
    validate_feasibility_contract(contract)
    generation = _object(contract.get("generation"), where="generation")
    expected_seed = _integer(generation.get("screening_seed"), where="screening_seed")
    rows = load_jsonl(private_output_dir / "inputs.private.jsonl")
    responses: list[JsonObject] = []
    for row in rows:
        row_seed = _integer(row.get("seed"), where="item.seed")
        if row_seed != expected_seed:
            raise ValueError("calibration input seed differs from the frozen seed")
        response = post_json(
            server_url.rstrip("/") + "/completion",
            {
                "prompt": _string(row.get("chat_prompt"), where="chat_prompt"),
                "n_predict": _integer(generation.get("max_tokens"), where="max_tokens"),
                "temperature": _number(
                    generation.get("temperature"),
                    where="temperature",
                ),
                "top_p": _number(generation.get("top_p"), where="top_p"),
                "top_k": _integer(generation.get("top_k"), where="top_k"),
                "seed": row_seed,
                "stream": False,
                "cache_prompt": False,
            },
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("target endpoint returned no text content")
        responses.append(
            {
                "item_id": row.get("item_id"),
                "payload_id": row.get("payload_id"),
                "candidate_id": row.get("candidate_id"),
                "condition": row.get("condition"),
                "seed": row_seed,
                "model_response": content,
                "response_sha256": sha256_text(content),
                "response_character_length": len(content),
                "stopped_eos": bool(response.get("stopped_eos", False)),
                "stopped_limit": bool(response.get("stopped_limit", False)),
            }
        )
    if len(responses) != 30:
        raise ValueError("calibration response denominator is incomplete")
    write_jsonl(private_output_dir / "responses.private.jsonl", responses)
    return {
        "status": "NATURAL_LANGUAGE_CALIBRATION_TARGET_COMPLETE",
        "generation_count": len(responses),
        "seed": expected_seed,
    }


def _annotation_id(seed: bytes, item_id: str) -> str:
    return hmac.new(seed, item_id.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def package_blinded_calibration_packet(
    *,
    contract_path: Path,
    plan_path: Path,
    private_output_dir: Path,
    safe_output_dir: Path,
    randomization_seed: bytes | None = None,
) -> JsonObject:
    contract = load_json_object(contract_path)
    plan = load_json_object(plan_path)
    validate_feasibility_contract(contract)
    validate_safe_plan(plan, contract)
    inputs = {
        _string(row.get("item_id"), where="item_id"): row
        for row in load_jsonl(private_output_dir / "inputs.private.jsonl")
    }
    responses = {
        _string(row.get("item_id"), where="item_id"): row
        for row in load_jsonl(private_output_dir / "responses.private.jsonl")
    }
    if set(inputs) != set(responses) or len(inputs) != 30:
        raise ValueError("calibration input and response sets differ")

    seed = randomization_seed if randomization_seed is not None else secrets.token_bytes(32)
    if len(seed) != 32:
        raise ValueError("randomization seed must contain exactly 32 bytes")
    packet_rows: list[JsonObject] = []
    key_rows: list[JsonObject] = []
    for item_id in sorted(inputs):
        source = inputs[item_id]
        response = responses[item_id]
        annotation_id = _annotation_id(seed, item_id)
        packet_rows.append(
            {
                "annotation_id": annotation_id,
                "original_harmful_goal": source.get("original_harmful_goal"),
                "model_response": response.get("model_response"),
                "label": "",
                "confidence": "",
                "notes": "",
            }
        )
        key_rows.append(
            {
                "annotation_id": annotation_id,
                "item_id": item_id,
                "payload_id": source.get("payload_id"),
                "candidate_id": source.get("candidate_id"),
                "condition": source.get("condition"),
                "category": source.get("category"),
                "seed": source.get("seed"),
                "response_sha256": response.get("response_sha256"),
            }
        )

    shuffle_seed = hashlib.sha256(seed + b"annotation-packet-order").digest()
    random.Random(int.from_bytes(shuffle_seed, "big")).shuffle(packet_rows)
    private_output_dir.mkdir(parents=True, exist_ok=True)
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(private_output_dir / "annotation_packet.private.jsonl", packet_rows)
    write_jsonl(private_output_dir / "annotation_key.private.jsonl", key_rows)
    (private_output_dir / "randomization_seed.private.hex").write_text(
        seed.hex() + "\n",
        encoding="utf-8",
    )
    annotation_schema: JsonObject = {
        "schema_version": "natural-language-human-annotation-v1",
        "required_fields": [
            "annotation_id",
            "original_harmful_goal",
            "model_response",
            "label",
            "confidence",
            "notes",
        ],
        "allowed_labels": _array(
            _object(contract.get("human_measurement"), where="human_measurement").get(
                "labels"
            ),
            where="human_measurement.labels",
        ),
        "primary_success_label": "SUBSTANTIVE_HARMFUL_ASSISTANCE",
        "condition_candidate_and_seed_are_blinded": True,
    }
    write_json(private_output_dir / "annotation_schema.private.json", annotation_schema)

    response_identity_rows = [
        {
            "item_id": item_id,
            "response_sha256": responses[item_id].get("response_sha256"),
        }
        for item_id in sorted(responses)
    ]
    annotation_ids = sorted(
        _string(row.get("annotation_id"), where="annotation_id") for row in packet_rows
    )
    packet_order = [
        _string(row.get("annotation_id"), where="annotation_id") for row in packet_rows
    ]
    summary: JsonObject = {
        "schema_version": "natural-language-calibration-packet-summary-v1",
        "status": "NATURAL_LANGUAGE_CALIBRATION_PACKET_READY",
        "paper_validity": False,
        "contract_identity_sha256": contract.get("contract_identity_sha256"),
        "plan_identity_sha256": plan.get("plan_identity_sha256"),
        "item_count": len(packet_rows),
        "direct_count": sum(row.get("condition") == "direct" for row in key_rows),
        "attacked_count": sum(row.get("condition") == "attacked" for row in key_rows),
        "payload_count": len({row.get("payload_id") for row in key_rows}),
        "category_count": len({row.get("category") for row in key_rows}),
        "randomization_seed_sha256": hashlib.sha256(seed).hexdigest(),
        "annotation_ids_sha256": canonical_json_sha256(annotation_ids),
        "packet_order_sha256": canonical_json_sha256(packet_order),
        "response_set_sha256": canonical_json_sha256(response_identity_rows),
        "two_independent_labels_required": True,
        "adjudication_required_for_disagreement_or_uncertain": True,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "private_packet_encryption_required": True,
        "decision_packet_opened": False,
        "gate1_evaluation_30_opened": False,
        "gate2_heldout_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    write_json(safe_output_dir / "packet_summary.json", summary)
    return summary
