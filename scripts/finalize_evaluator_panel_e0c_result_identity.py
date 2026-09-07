from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
MIB = 1024 * 1024
PRIVATE_TEXT_KEYS = {
    "prompt",
    "prompt_text",
    "system_prompt",
    "user_prompt",
    "response",
    "response_text",
    "stdout",
    "stderr",
}


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sorted_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def assert_safe_result(value: object, *, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PRIVATE_TEXT_KEYS:
                raise ValueError(f"private text field in safe result at {location}.{key}")
            assert_safe_result(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_safe_result(child, location=f"{location}[{index}]")


def validate_dependency(root: Path, dependency: JsonObject, *, name: str) -> Path:
    path = root / str(dependency["path"])
    if not path.is_file():
        raise FileNotFoundError(f"missing {name}: {path}")
    if path.stat().st_size != int(dependency["bytes"]):
        raise ValueError(f"{name} byte-size mismatch")
    if sha256_file(path) != dependency["sha256"]:
        raise ValueError(f"{name} SHA-256 mismatch")
    return path


def validate_contract(root: Path, config_path: Path, contract: JsonObject) -> JsonObject:
    if contract.get("status") != "FROZEN_AFTER_E0C_V1_1_PASS_BEFORE_IDENTITY_FINALIZATION":
        raise ValueError("unexpected E0C identity-finalization status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("identity finalization must be frozen and non-paper-valid")
    allowed = as_object(contract["allowed_changes"], where="allowed_changes")
    if allowed != {
        "add_identity_scheme_field": True,
        "add_identity_finalization_audit": True,
        "replace_result_identity_sha256": True,
    }:
        raise ValueError("identity-finalization mutation boundary changed")
    if any(
        value is not False
        for value in as_object(contract["scope_boundary"], where="scope_boundary").values()
    ):
        raise ValueError("identity finalization opens a prohibited boundary")
    dependencies = as_object(contract["dependencies"], where="dependencies")
    paths = {
        name: validate_dependency(
            root,
            as_object(value, where=f"dependencies.{name}"),
            name=name,
        )
        for name, value in dependencies.items()
    }
    predecessor = load_object(paths["e0c_v1_1_result"])
    expected = as_object(
        dependencies["e0c_v1_1_result"], where="dependencies.e0c_v1_1_result"
    )
    if predecessor.get("status") != "E0C_V1_1_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_PASS":
        raise ValueError("E0C V1.1 predecessor is not a PASS result")
    if predecessor.get("operational_pass") is not True:
        raise ValueError("E0C V1.1 predecessor operational pass is false")
    if predecessor.get("result_identity_sha256") != expected["declared_result_identity"]:
        raise ValueError("E0C V1.1 declared predecessor identity mismatch")
    if predecessor.get("contract_sha256") != dependencies["e0c_v1_1_contract"]["sha256"]:
        raise ValueError("E0C V1.1 result-to-contract link mismatch")
    if predecessor.get("runner_sha256") != dependencies["e0c_v1_1_runner"]["sha256"]:
        raise ValueError("E0C V1.1 result-to-runner link mismatch")
    if not config_path.is_file():
        raise FileNotFoundError("identity-finalization config is missing")
    return predecessor


def run(root: Path, config_path: Path, output_path: Path) -> JsonObject:
    contract = load_object(config_path)
    predecessor = validate_contract(root, config_path, contract)
    original_identity = str(predecessor.pop("result_identity_sha256"))
    result = dict(predecessor)
    result["result_identity_scheme"] = (
        "sha256_of_utf8_json_ensure_ascii_false_sort_keys_true_compact_separators_"
        "with_result_identity_sha256_omitted"
    )
    dependencies = as_object(contract["dependencies"], where="dependencies")
    result["identity_finalization_audit"] = {
        "predecessor_file_sha256": dependencies["e0c_v1_1_result"]["sha256"],
        "predecessor_declared_result_identity": original_identity,
        "failure_cause": (
            "The predecessor identity used insertion-order JSON before the result file "
            "was serialized with sorted keys."
        ),
        "model_outputs_changed": False,
        "parsed_values_changed": False,
        "checks_changed": False,
        "metrics_changed": False,
        "status_or_operational_pass_changed": False,
        "model_inference_performed": False,
        "finalization_contract_sha256": sha256_file(config_path),
        "finalizer_sha256": sha256_file(Path(__file__).resolve()),
    }
    result["result_identity_sha256"] = canonical_sorted_sha256(result)
    assert_safe_result(result)
    atomic_write_json(output_path, result)
    reloaded = load_object(output_path)
    observed_identity = str(reloaded.pop("result_identity_sha256"))
    if observed_identity != canonical_sorted_sha256(reloaded):
        raise RuntimeError("finalized result identity is not reproducible after serialization")
    return load_object(output_path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Finalize reproducible E0C result identity")
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/e0c_result_identity_finalization.json"),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = (root / args.config).resolve()
    contract = load_object(config_path)
    output_path = root / str(contract["safe_output_path"])
    result = run(root, config_path, output_path)
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "result_identity_sha256": result["result_identity_sha256"],
                "model_inference_performed_during_finalization": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
