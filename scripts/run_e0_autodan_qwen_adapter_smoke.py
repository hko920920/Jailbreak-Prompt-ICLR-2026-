from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity is SHA-1.


def load_json_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_string_list(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def find_unique_span(text: str, value: str) -> tuple[int, int]:
    count = text.count(value)
    if count != 1:
        raise ValueError(f"expected exactly one value occurrence, observed {count}")
    start = text.index(value)
    return start, start + len(value)


def token_interval_for_span(
    offsets: list[tuple[int, int]],
    *,
    span_start: int,
    span_end: int,
) -> JsonObject:
    indices = [
        index
        for index, (start, end) in enumerate(offsets)
        if end > start and start < span_end and end > span_start
    ]
    if not indices:
        return {
            "nonempty": False,
            "contiguous": False,
            "covers_character_span": False,
            "start": None,
            "end_exclusive": None,
            "count": 0,
            "coverage_start": None,
            "coverage_end": None,
        }
    contiguous = indices == list(range(indices[0], indices[-1] + 1))
    coverage_start = min(offsets[index][0] for index in indices)
    coverage_end = max(offsets[index][1] for index in indices)
    return {
        "nonempty": True,
        "contiguous": contiguous,
        "covers_character_span": (
            coverage_start <= span_start and coverage_end >= span_end
        ),
        "start": indices[0],
        "end_exclusive": indices[-1] + 1,
        "count": len(indices),
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
    }


def build_unit_manifest(materialized: str, payload: str) -> list[JsonObject]:
    start, end = find_unique_span(materialized, payload)
    prefix = materialized[:start]
    suffix = materialized[end:]
    values = [
        ("AUTODAN_PREFIX_BEFORE_PAYLOAD", prefix, True),
        ("IMMUTABLE_SYNTHETIC_PAYLOAD", payload, False),
        ("AUTODAN_SUFFIX_AFTER_PAYLOAD", suffix, True),
    ]
    return [
        {
            "id": unit_id,
            "character_length": len(text),
            "byte_length": len(text.encode()),
            "sha256": sha256_bytes(text.encode()),
            "neutralizable": neutralizable,
            "raw_text_recorded": False,
        }
        for unit_id, text, neutralizable in values
    ]


def tokenizer_file_rows(tokenizer_dir: Path, allow_patterns: list[str]) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for relative in allow_patterns:
        path = tokenizer_dir / relative
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else None,
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    return rows


def run_smoke(
    *,
    root: Path,
    config_path: Path,
    autodan_source: Path,
    tokenizer_dir: Path,
    output_path: Path,
) -> JsonObject:
    config = load_json_object(config_path)
    if config["status"] != "FROZEN_BEFORE_AUTODAN_QWEN_ADAPTER_SMOKE":
        raise ValueError("unexpected contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid contract boundary")

    predecessor_spec = as_object(config["predecessor"], where="predecessor")
    predecessor_path = root / str(predecessor_spec["path"])
    if git_blob_sha(predecessor_path) != str(predecessor_spec["git_blob_sha"]):
        raise ValueError("predecessor Git blob mismatch")
    predecessor = load_json_object(predecessor_path)
    if predecessor["status"] != predecessor_spec["required_status"]:
        raise ValueError("predecessor status mismatch")
    if predecessor["next_authorized_operation"] != predecessor_spec[
        "required_next_operation"
    ]:
        raise ValueError("predecessor next-operation mismatch")

    autodan = as_object(config["autodan"], where="autodan")
    initial_path = autodan_source / str(autodan["initial_prompt_path"])
    if git_blob_sha(initial_path) != str(autodan["initial_prompt_git_blob_sha"]):
        raise ValueError("AutoDAN initial prompt Git blob mismatch")
    initial_prompt = initial_path.read_text(encoding="utf-8")

    target = as_object(config["target_tokenizer"], where="target_tokenizer")
    allow_patterns = as_string_list(
        target["allow_patterns"], where="target_tokenizer.allow_patterns"
    )
    tokenizer_files = tokenizer_file_rows(tokenizer_dir, allow_patterns)

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_dir,
        use_fast=bool(target["use_fast"]),
        local_files_only=True,
        trust_remote_code=False,
    )

    payload = str(config["synthetic_payload"])
    placeholder = str(autodan["placeholder"])
    repetitions = int(config["fresh_render_repetitions"])
    messages_spec = target["messages"]
    if not isinstance(messages_spec, list) or len(messages_spec) != 1:
        raise TypeError("exactly one user-message specification is required")
    message_spec = as_object(messages_spec[0], where="target_tokenizer.messages[0]")
    if message_spec["role"] != "user":
        raise ValueError("only a user-message adapter is permitted")

    materialized_outputs: list[str] = []
    rendered_outputs: list[str] = []
    for _ in range(repetitions):
        materialized = initial_prompt.replace(placeholder, payload)
        messages = [{"role": "user", "content": materialized}]
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=bool(target["add_generation_prompt"]),
        )
        if not isinstance(rendered, str):
            raise TypeError("chat template returned a non-string")
        materialized_outputs.append(materialized)
        rendered_outputs.append(rendered)

    materialized_hashes = [sha256_bytes(item.encode()) for item in materialized_outputs]
    rendered_hashes = [sha256_bytes(item.encode()) for item in rendered_outputs]
    materialized = materialized_outputs[0]
    rendered = rendered_outputs[0]

    payload_attack_start, payload_attack_end = find_unique_span(materialized, payload)
    payload_chat_start, payload_chat_end = find_unique_span(rendered, payload)
    encoded = tokenizer(
        rendered,
        add_special_tokens=bool(
            target["add_special_tokens_when_encoding_rendered_chat"]
        ),
        return_offsets_mapping=True,
    )
    input_ids_raw = encoded["input_ids"]
    offsets_raw = encoded["offset_mapping"]
    if not isinstance(input_ids_raw, list) or not isinstance(offsets_raw, list):
        raise TypeError("tokenizer output must be list-based")
    input_ids = [int(item) for item in input_ids_raw]
    offsets = [(int(item[0]), int(item[1])) for item in offsets_raw]
    interval = token_interval_for_span(
        offsets,
        span_start=payload_chat_start,
        span_end=payload_chat_end,
    )
    interval_start = interval["start"]
    interval_end = interval["end_exclusive"]
    payload_token_ids: list[int] = []
    if isinstance(interval_start, int) and isinstance(interval_end, int):
        payload_token_ids = input_ids[interval_start:interval_end]

    unit_manifest = build_unit_manifest(materialized, payload)
    chat_template = tokenizer.chat_template
    if not isinstance(chat_template, str) or not chat_template:
        raise ValueError("Qwen tokenizer chat template is unavailable")

    rules = as_object(config["rules"], where="rules")
    checks = {
        "predecessor_authorized": True,
        "autodan_source_identity": True,
        "tokenizer_files_present": all(row["exists"] is True for row in tokenizer_files),
        "tokenizer_is_fast": tokenizer.is_fast is bool(rules["tokenizer_must_be_fast"]),
        "source_placeholder_count": (
            initial_prompt.count(placeholder)
            == int(rules["placeholder_occurrence_count_in_source"])
        ),
        "materialized_payload_count": (
            materialized.count(payload)
            == int(rules["payload_occurrence_count_in_materialized_attack"])
        ),
        "materialized_payload_byte_count": (
            materialized.encode().count(payload.encode())
            == int(rules["payload_occurrence_count_in_materialized_attack"])
        ),
        "rendered_payload_count": (
            rendered.count(payload)
            == int(rules["payload_occurrence_count_in_rendered_chat"])
        ),
        "rendered_payload_byte_count": (
            rendered.encode().count(payload.encode())
            == int(rules["payload_occurrence_count_in_rendered_chat"])
        ),
        "placeholder_removed": placeholder not in materialized and placeholder not in rendered,
        "deterministic_materialization": len(set(materialized_hashes)) == 1,
        "deterministic_chat_render": len(set(rendered_hashes)) == 1,
        "payload_token_interval_nonempty": interval["nonempty"] is True,
        "payload_token_interval_contiguous": interval["contiguous"] is True,
        "payload_span_covered": interval["covers_character_span"] is True,
        "intervention_domain_excludes_payload": (
            [row["neutralizable"] for row in unit_manifest] == [True, False, True]
        ),
        "no_model_weights_in_allowlist": all(
            "model" not in item or item == "config.json" for item in allow_patterns
        ),
    }
    operational_pass = all(checks.values())

    admission = as_object(config["admission"], where="admission")
    gate = as_object(config["decision_gate"], where="decision_gate")
    status = (
        "E0_AUTODAN_QWEN_ADAPTER_SMOKE_PASS_REMAIN_CONDITIONAL"
        if operational_pass
        else "E0_AUTODAN_QWEN_ADAPTER_SMOKE_FAIL"
    )
    next_operation = gate["on_pass"] if operational_pass else gate["on_fail"]

    result: JsonObject = {
        "schema_version": "e0-autodan-qwen-adapter-smoke-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "family": admission["family"],
        "regime": admission["regime"],
        "family_admitted_to_balanced_signal_screen": False,
        "predecessor": {
            "path": predecessor_spec["path"],
            "git_blob_sha": predecessor_spec["git_blob_sha"],
            "status": predecessor["status"],
        },
        "autodan": {
            "repository": autodan["repository"],
            "revision": autodan["revision"],
            "tree_sha": autodan["tree_sha"],
            "initial_prompt_git_blob_sha": autodan["initial_prompt_git_blob_sha"],
        },
        "target_tokenizer": {
            "repository": target["repository"],
            "revision": target["revision"],
            "license": target["license"],
            "tokenizer_class": type(tokenizer).__name__,
            "is_fast": tokenizer.is_fast,
            "vocab_size": int(tokenizer.vocab_size),
            "chat_template_sha256": sha256_bytes(chat_template.encode()),
            "special_tokens_map_sha256": sha256_bytes(
                json.dumps(
                    tokenizer.special_tokens_map,
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode()
            ),
            "files": tokenizer_files,
            "model_weights_downloaded": False,
        },
        "synthetic_payload_sha256": sha256_bytes(payload.encode()),
        "synthetic_payload_character_length": len(payload),
        "synthetic_payload_byte_length": len(payload.encode()),
        "materialized_attack": {
            "sha256": materialized_hashes[0],
            "deterministic": len(set(materialized_hashes)) == 1,
            "character_length": len(materialized),
            "byte_length": len(materialized.encode()),
            "payload_character_span": [payload_attack_start, payload_attack_end],
            "raw_text_recorded": False,
        },
        "rendered_chat": {
            "sha256": rendered_hashes[0],
            "deterministic": len(set(rendered_hashes)) == 1,
            "character_length": len(rendered),
            "byte_length": len(rendered.encode()),
            "payload_character_span": [payload_chat_start, payload_chat_end],
            "total_token_count": len(input_ids),
            "payload_token_interval": interval,
            "payload_token_ids_sha256": sha256_bytes(
                json.dumps(payload_token_ids, separators=(",", ":")).encode()
            ),
            "raw_text_recorded": False,
        },
        "unit_manifest": unit_manifest,
        "mandatory_checks": checks,
        "resolved_this_step": admission["resolved_if_pass"] if operational_pass else [],
        "remaining_before_admission": admission[
            "remaining_required_before_admission"
        ],
        "real_harmful_payload_used": False,
        "target_model_weights_downloaded": False,
        "target_model_called": False,
        "target_model_generation_performed": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": next_operation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synthetic AutoDAN-to-Qwen tokenizer/chat-template adapter smoke"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--autodan-source", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_smoke(
        root=args.root,
        config_path=args.config,
        autodan_source=args.autodan_source,
        tokenizer_dir=args.tokenizer_dir,
        output_path=args.output,
    )
    summary = {
        "status": result["status"],
        "operational_pass": result["operational_pass"],
        "family_admitted_to_balanced_signal_screen": result[
            "family_admitted_to_balanced_signal_screen"
        ],
        "payload_token_count": as_object(
            as_object(result["rendered_chat"], where="rendered_chat")[
                "payload_token_interval"
            ],
            where="payload_token_interval",
        )["count"],
        "next_authorized_operation": result["next_authorized_operation"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
