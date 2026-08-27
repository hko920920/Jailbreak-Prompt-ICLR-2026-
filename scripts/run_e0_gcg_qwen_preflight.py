from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from gcg_qwen_adapter import audit_tokenizer

JsonObject = dict[str, Any]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_blob(root: Path, spec: JsonObject) -> JsonObject:
    path = root / str(spec["path"])
    observed = git_blob_sha(path)
    if observed != spec["git_blob_sha"]:
        raise ValueError(f"predecessor blob mismatch: {spec['path']}")
    return load_object(path)


def validate_predecessors(root: Path, contract: JsonObject) -> JsonObject:
    predecessors = cast(JsonObject, contract["predecessors"])
    gcg_contract_spec = cast(JsonObject, predecessors["gcg_contract"])
    gcg_contract = require_blob(root, gcg_contract_spec)
    if gcg_contract.get("status") != gcg_contract_spec["required_status"]:
        raise ValueError("GCG contract status mismatch")

    gcg_result_spec = cast(JsonObject, predecessors["gcg_static_result"])
    gcg_result = require_blob(root, gcg_result_spec)
    if gcg_result.get("status") != gcg_result_spec["required_status"]:
        raise ValueError("GCG result status mismatch")
    if gcg_result.get("next_authorized_operation") != gcg_result_spec["required_next_operation"]:
        raise ValueError("GCG result authorization mismatch")
    if gcg_result.get("family_admitted_to_balanced_signal_screen") is not False:
        raise ValueError("GCG was unexpectedly admitted before tokenizer audit")

    execution_spec = cast(JsonObject, predecessors["execution_freeze"])
    execution = require_blob(root, execution_spec)
    if execution.get("status") != execution_spec["required_status"]:
        raise ValueError("execution-freeze status mismatch")

    manifest_spec = cast(JsonObject, predecessors["signal_screen_manifest"])
    manifest = require_blob(root, manifest_spec)
    if manifest.get("status") != manifest_spec["required_status"]:
        raise ValueError("signal-screen manifest status mismatch")

    expected_target = cast(JsonObject, contract["target_tokenizer"])
    for source in (execution, manifest):
        target = cast(JsonObject, source["target_model"])
        if target.get("canonical_repository") != expected_target["repository"]:
            raise ValueError("target repository mismatch")
        if target.get("tokenizer_revision") != expected_target["revision"]:
            raise ValueError("tokenizer revision mismatch")
        if source.get("model_inference_performed") is not False:
            raise ValueError("predecessor unexpectedly performed model inference")

    return {
        "gcg_contract_git_blob_sha": gcg_contract_spec["git_blob_sha"],
        "gcg_result_git_blob_sha": gcg_result_spec["git_blob_sha"],
        "execution_freeze_git_blob_sha": execution_spec["git_blob_sha"],
        "signal_screen_manifest_git_blob_sha": manifest_spec["git_blob_sha"],
        "all_predecessors_match": True,
    }


def resolve_tokenizer(contract: JsonObject) -> tuple[Any, JsonObject]:
    from huggingface_hub import HfApi
    from transformers import AutoTokenizer

    target = cast(JsonObject, contract["target_tokenizer"])
    repository = str(target["repository"])
    revision = str(target["revision"])
    info = HfApi().model_info(repository, revision=revision, files_metadata=True)
    observed_revision = str(info.sha)
    if observed_revision != revision:
        raise ValueError("tokenizer repository did not resolve to the frozen revision")
    tokenizer = AutoTokenizer.from_pretrained(
        repository,
        revision=revision,
        trust_remote_code=bool(target["trust_remote_code"]),
        use_fast=bool(target["use_fast"]),
    )
    init_revision = tokenizer.init_kwargs.get("_commit_hash")
    if init_revision not in (None, revision):
        raise ValueError("loaded tokenizer commit differs from the frozen revision")
    metadata = {
        "repository": repository,
        "expected_revision": revision,
        "observed_revision": observed_revision,
        "revision_match": True,
        "model_weights_downloaded": False,
        "model_forward_pass": False,
        "model_generation": False,
    }
    return tokenizer, metadata


def build_result(
    root: Path,
    config_path: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_GCG_QWEN_TOKENIZER_PREFLIGHT":
        raise ValueError("unexpected preflight contract status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("invalid preflight contract boundary")
    sealed = cast(JsonObject, contract["sealed_boundaries"])
    if any(value is not False for value in sealed.values()):
        raise ValueError("a sealed boundary was opened before preflight")

    predecessors = validate_predecessors(root, contract)
    tokenizer, tokenizer_metadata = resolve_tokenizer(contract)
    audit = audit_tokenizer(tokenizer, contract)
    compatibility_pass = audit["compatibility_pass"] is True
    decision = cast(JsonObject, contract["decision_gate"])
    return {
        "schema_version": "e0-gcg-qwen-preflight-result-v1",
        "status": (
            "E0_GCG_QWEN_PREFLIGHT_PASS"
            if compatibility_pass
            else "E0_GCG_QWEN_PREFLIGHT_COMPATIBILITY_FAIL"
        ),
        "operational_pass": True,
        "compatibility_pass": compatibility_pass,
        "scientific_pass": False,
        "paper_validity": False,
        "evidence_class": "PROTOCOL_COMPATIBILITY",
        "contract_git_blob_sha": git_blob_sha(config_path),
        "contract_sha256": sha256_file(config_path),
        "predecessors": predecessors,
        "tokenizer": tokenizer_metadata,
        "audit": audit,
        "next_authorized_operation": (
            decision["on_pass"]
            if compatibility_pass
            else decision["on_compatibility_fail"]
        ),
        "model_weights_downloaded": False,
        "model_forward_pass": False,
        "model_generation": False,
        "real_harmful_payload_used": False,
        "attack_optimization_performed": False,
        "attack_success_observed": False,
        "raw_fixture_recorded": False,
        "raw_rendered_prompt_recorded": False,
        "raw_token_ids_recorded": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run tokenizer-only GCG/Qwen compatibility audit")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    output = args.output.resolve()
    try:
        result = build_result(args.root.resolve(), args.config.resolve())
    except Exception as exc:  # noqa: BLE001 - preserve a sanitized terminal record.
        result = {
            "schema_version": "e0-gcg-qwen-preflight-result-v1",
            "status": "E0_GCG_QWEN_PREFLIGHT_OPERATIONAL_FAIL",
            "operational_pass": False,
            "compatibility_pass": False,
            "scientific_pass": False,
            "paper_validity": False,
            "error_type": type(exc).__name__,
            "error_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
            "next_authorized_operation": (
                "REPAIR_PREFLIGHT_RUNTIME_WITHOUT_CHANGING_SCIENTIFIC_CONTRACT"
            ),
            "model_weights_downloaded": False,
            "model_forward_pass": False,
            "model_generation": False,
            "real_harmful_payload_used": False,
            "attack_optimization_performed": False,
            "attack_success_observed": False,
            "raw_fixture_recorded": False,
            "raw_rendered_prompt_recorded": False,
            "raw_token_ids_recorded": False,
            "stage_a_opened": False,
            "heldout_opened": False,
            "causal_oracle_opened": False,
            "keep_only_oracle_opened": False,
            "wavelet_used": False,
        }
    write_json(output, result)
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
