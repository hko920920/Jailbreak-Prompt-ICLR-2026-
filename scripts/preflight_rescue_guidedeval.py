"""Bind completed C1N responses to GuidedBench cases without judge inference.

The resulting plan is content-free and safe to version.  Raw victim responses
remain in their original gitignored records, so the preflight adds no duplicate
response corpus and no meaningful storage burden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
SCHEMA = "jbspan-rescue-guidedeval-development-preflight-v1"
STATUS = "FROZEN_BEFORE_DEVELOPMENT_GUIDEDEVAL_INPUT_BINDING"
PROHIBITED_KEYS = {
    "payload",
    "prompt",
    "response",
    "response_text",
    "question",
    "description",
    "examples",
    "raw_output",
    "stdout",
    "stderr",
    "content",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "rescue_guidedeval_development_preflight_v1.json"
        ),
    )
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    values = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(value, dict) for value in values):
        raise ValueError(f"expected JSON object rows: {path}")
    return values


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root) and not path.is_absolute():
        raise ValueError("relative path escapes repository root")
    return resolved


def verify_file(root: Path, specification: Mapping[str, Any], *, where: str) -> Path:
    path = resolve(root, str(specification["path"]))
    if not path.is_file():
        raise ValueError(f"missing frozen dependency: {where}")
    if file_sha256(path) != specification["sha256"]:
        raise ValueError(f"frozen dependency hash mismatch: {where}")
    expected_size = specification.get("size_bytes")
    if expected_size is not None and path.stat().st_size != int(expected_size):
        raise ValueError(f"frozen dependency size mismatch: {where}")
    return path


def assert_content_free(value: object, location: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in PROHIBITED_KEYS:
                field = ".".join((*location, key))
                raise ValueError(f"raw-content field in safe artifact: {field}")
            assert_content_free(child, (*location, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_content_free(child, (*location, str(index)))


def _guideline_type_counts(guidelines: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(guideline.get("type")) for guideline in guidelines)
    if set(counts) - {"entity", "action"}:
        raise ValueError("GuidedBench row has an unknown guideline type")
    return {kind: counts.get(kind, 0) for kind in ("entity", "action")}


def build(
    root: Path, config_path: Path
) -> tuple[JsonObject, JsonRows]:
    root = root.resolve()
    config_file = resolve(root, config_path)
    config = load_object(config_file)
    if (
        config.get("schema_version") != SCHEMA
        or config.get("status") != STATUS
        or config.get("frozen") is not True
    ):
        raise ValueError("development GuidedEval preflight config is not frozen")
    authority = config.get("authority")
    if not isinstance(authority, dict) or any(
        authority.get(key) is not False
        for key in (
            "judge_inference_allowed",
            "primary_a_access_allowed",
            "replication_reserve_b_access_allowed",
            "c1n_reclassification_allowed",
        )
    ):
        raise ValueError("preflight authority boundary differs")

    dependencies = config.get("dependencies")
    if not isinstance(dependencies, dict):
        raise ValueError("dependencies must be an object")
    verified = {
        str(name): verify_file(root, specification, where=f"dependencies.{name}")
        for name, specification in dependencies.items()
        if isinstance(specification, dict)
    }
    if len(verified) != len(dependencies):
        raise ValueError("dependency specification is malformed")

    official = config.get("official_guidedbench_source")
    if not isinstance(official, dict):
        raise ValueError("official_guidedbench_source must be an object")
    official_files = official.get("files")
    if not isinstance(official_files, dict):
        raise ValueError("official source files must be an object")
    verified_official = {
        str(name): verify_file(root, specification, where=f"official_source.{name}")
        for name, specification in official_files.items()
        if isinstance(specification, dict)
    }
    if len(verified_official) != len(official_files):
        raise ValueError("official source specification is malformed")

    core = load_jsonl(verified["guidedbench_core"])
    reservation = load_jsonl(verified["confirmation_reservation"])
    generations = load_jsonl(verified["c1n_seed11_generation"])
    if len(core) != int(config["expected_counts"]["guidedbench_core_rows"]):
        raise ValueError("GuidedBench core denominator differs")
    if len(reservation) != int(config["expected_counts"]["reserved_cases"]):
        raise ValueError("C1N reservation denominator differs")
    if len(generations) != int(config["expected_counts"]["victim_responses"]):
        raise ValueError("C1N response denominator differs")

    by_payload: dict[str, JsonObject] = {}
    for row in core:
        question = row.get("question")
        guidelines = row.get("guidelines")
        if not isinstance(question, str) or not isinstance(guidelines, list):
            raise ValueError("GuidedBench source row is malformed")
        payload_sha = text_sha256(question)
        if payload_sha in by_payload:
            raise ValueError("GuidedBench core payloads are not unique")
        by_payload[payload_sha] = row

    reserved_by_payload = {str(row["payload_sha256"]): row for row in reservation}
    if len(reserved_by_payload) != len(reservation):
        raise ValueError("reservation payloads are not unique")

    private_root = resolve(root, str(config["private_record_root"]))
    plan: JsonRows = []
    for safe in generations:
        payload_sha = str(safe["payload_sha256"])
        source = by_payload.get(payload_sha)
        reserved = reserved_by_payload.get(payload_sha)
        if source is None or reserved is None:
            raise ValueError("C1N generation is not in the frozen reservation")
        if source.get("id") != reserved.get("source_id"):
            raise ValueError("GuidedBench source ID differs from reservation")
        guidelines = source.get("guidelines")
        if not isinstance(guidelines, list) or not all(
            isinstance(guideline, dict) for guideline in guidelines
        ):
            raise ValueError("GuidedBench guideline vector is malformed")
        typed_guidelines = list(guidelines)
        if (
            canonical_sha256(typed_guidelines) != reserved["guideline_manifest_sha256"]
            or len(typed_guidelines) != int(reserved["guideline_count"])
            or _guideline_type_counts(typed_guidelines) != reserved["guideline_type_counts"]
        ):
            raise ValueError("GuidedBench guideline identity differs from reservation")

        target_id = str(safe["target_id"])
        identity = str(safe["execution_identity_sha256"])
        private_path = private_root / target_id / f"{identity}.json"
        if (
            not private_path.is_file()
            or file_sha256(private_path) != safe["private_record_sha256"]
        ):
            raise ValueError("C1N private target record identity differs")
        private = load_object(private_path)
        response = private.get("response")
        payload = private.get("payload")
        if not isinstance(response, str) or not isinstance(payload, str):
            raise ValueError("C1N private target record lacks text fields")
        if (
            text_sha256(response) != safe["response_sha256"]
            or len(response.encode("utf-8")) != int(safe["response_utf8_bytes"])
            or text_sha256(payload) != payload_sha
            or private.get("execution_identity_sha256") != identity
        ):
            raise ValueError("C1N private target text identity differs")

        row: JsonObject = {
            "schema_version": "jbspan-rescue-guidedeval-input-plan-row-v1",
            "development_origin": "C1N_SEED11_VALID_NEGATIVE_REUSE",
            "source_id": source["id"],
            "source_id_sha256": text_sha256(str(source["id"])),
            "source_row_sha256": canonical_sha256(source),
            "guideline_manifest_sha256": canonical_sha256(typed_guidelines),
            "guideline_count": len(typed_guidelines),
            "guideline_type_counts": _guideline_type_counts(typed_guidelines),
            "payload_sha256": payload_sha,
            "record_id": safe["record_id"],
            "execution_identity_sha256": identity,
            "target_id": target_id,
            "condition": safe["condition"],
            "seed": safe["seed"],
            "response_sha256": safe["response_sha256"],
            "response_utf8_bytes": safe["response_utf8_bytes"],
            "private_record_sha256": safe["private_record_sha256"],
            "raw_content_recorded": False,
            "judge_inference_completed": False,
        }
        row["plan_row_identity_sha256"] = canonical_sha256(row)
        plan.append(row)

    expected = config["expected_counts"]
    cell_counts = Counter((row["target_id"], row["condition"]) for row in plan)
    target_counts = Counter(str(row["target_id"]) for row in plan)
    condition_counts = Counter(str(row["condition"]) for row in plan)
    if (
        len({str(row["record_id"]) for row in plan}) != len(plan)
        or len({str(row["payload_sha256"]) for row in plan})
        != int(expected["reserved_cases"])
        or set(target_counts.values()) != {int(expected["responses_per_target"])}
        or set(condition_counts.values()) != {int(expected["responses_per_condition"])}
        or set(cell_counts.values()) != {int(expected["responses_per_target_condition_cell"])}
        or {int(row["seed"]) for row in plan} != {11}
    ):
        raise ValueError("development input plan cell denominators differ")

    result: JsonObject = {
        "schema_version": SCHEMA,
        "status": "RESCUE_GUIDEDEVAL_DEVELOPMENT_INPUT_PREFLIGHT_PASS",
        "evidence_class": "DEVELOPMENT_INPUT_BINDING_NO_JUDGE_OR_TARGET_INFERENCE",
        "config_sha256": file_sha256(config_file),
        "verified_dependency_sha256": {
            name: file_sha256(path) for name, path in sorted(verified.items())
        },
        "verified_official_source_sha256": {
            name: file_sha256(path) for name, path in sorted(verified_official.items())
        },
        "counts": {
            "guidedbench_core_rows": len(core),
            "reserved_cases": len(reservation),
            "victim_responses": len(plan),
            "unique_response_hashes": len({row["response_sha256"] for row in plan}),
            "target": dict(sorted(target_counts.items())),
            "condition": dict(sorted(condition_counts.items())),
            "target_condition": {
                f"{target}|{condition}": count
                for (target, condition), count in sorted(cell_counts.items())
            },
        },
        "input_plan_identity_sha256": canonical_sha256(plan),
        "scope": {
            "target_inference_performed": False,
            "judge_inference_performed": False,
            "raw_content_read_for_identity_validation_only": True,
            "raw_content_written_to_safe_artifact": False,
            "raw_response_corpus_duplicated": False,
            "c1n_reclassified": False,
            "primary_a_opened": False,
            "replication_reserve_b_opened": False,
            "paper_valid_evidence": False,
        },
        "next_operation": (
            "FREEZE_JUDGE_RUNTIME_THEN_SCORE_ONLY_THE_COMPLETED_DEVELOPMENT_RESPONSES"
        ),
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    assert_content_free(plan)
    assert_content_free(result)
    return result, plan


def encode_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def write_once(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"refusing to overwrite nonidentical preflight artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def main() -> None:
    arguments = parser().parse_args()
    root = arguments.root.resolve()
    config_path = resolve(root, arguments.config)
    config = load_object(config_path)
    result, plan = build(root, config_path)
    recording = config["recording"]
    plan_path = resolve(root, str(recording["safe_input_plan"]))
    result_path = resolve(root, str(recording["safe_preflight_result"]))
    write_once(plan_path, encode_jsonl(plan))
    write_once(
        result_path,
        (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
