from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]

FORBIDDEN_KEYS = {
    "raw_fixture",
    "raw_prompt",
    "raw_rendered_prompt",
    "raw_token_ids",
    "raw_control",
    "raw_target",
    "payload",
    "response",
}


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("result must be a JSON object")
    return cast(JsonObject, value)


def walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(walk_keys(child))
    return keys


def validate(result: JsonObject) -> None:
    allowed_statuses = {
        "E0_GCG_QWEN_PREFLIGHT_PASS",
        "E0_GCG_QWEN_PREFLIGHT_COMPATIBILITY_FAIL",
        "E0_GCG_QWEN_PREFLIGHT_OPERATIONAL_FAIL",
    }
    if result.get("status") not in allowed_statuses:
        raise ValueError("unexpected preflight result status")
    for key in (
        "model_weights_downloaded",
        "model_forward_pass",
        "model_generation",
        "real_harmful_payload_used",
        "attack_optimization_performed",
        "attack_success_observed",
        "raw_fixture_recorded",
        "raw_rendered_prompt_recorded",
        "raw_token_ids_recorded",
        "stage_a_opened",
        "heldout_opened",
        "causal_oracle_opened",
        "keep_only_oracle_opened",
        "wavelet_used",
    ):
        if result.get(key) is not False:
            raise ValueError(f"unsafe boundary in result: {key}")
    overlap = walk_keys(result) & FORBIDDEN_KEYS
    if overlap:
        raise ValueError(f"forbidden raw fields in result: {sorted(overlap)}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Install sanitized GCG/Qwen preflight result")
    value.add_argument("--source", type=Path, required=True)
    value.add_argument("--destination", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    result = load_object(args.source)
    validate(result)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.source, args.destination)
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
