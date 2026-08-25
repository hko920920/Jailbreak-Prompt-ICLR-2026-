from __future__ import annotations

import argparse
import hashlib
import json
import os
import string
from pathlib import Path
from typing import Protocol, cast

JsonObject = dict[str, object]


class RepoSibling(Protocol):
    rfilename: str
    size: int | None
    lfs: object


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
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def immutable_revision(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in string.hexdigits for character in value)
    )


def sibling_metadata(sibling: object) -> JsonObject:
    entry = cast(RepoSibling, sibling)
    filename = str(entry.rfilename)
    size = entry.size
    sha256 = None
    lfs = entry.lfs
    if isinstance(lfs, dict):
        digest = lfs.get("sha256")
        if isinstance(digest, str):
            sha256 = digest
        lfs_size = lfs.get("size")
        if isinstance(lfs_size, int):
            size = lfs_size
    elif lfs is not None:
        digest = getattr(lfs, "sha256", None)
        if isinstance(digest, str):
            sha256 = digest
        lfs_size = getattr(lfs, "size", None)
        if isinstance(lfs_size, int):
            size = lfs_size
    return {
        "filename": filename,
        "size": size,
        "sha256": sha256,
    }


def run(root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    from huggingface_hub import HfApi, hf_hub_download

    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_E1C_RUNTIME_ARTIFACT_METADATA_QUERY":
        raise ValueError("unexpected E1C runtime artifact probe status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("runtime artifact probe contract must be frozen and non-paper-valid")

    predecessor = as_object(contract["predecessor"], where="predecessor")
    predecessor_path = root / str(predecessor["result_path"])
    predecessor_result = load_object(predecessor_path)
    if predecessor_result.get("status") != predecessor["required_status"]:
        raise ValueError("E1C preflight predecessor status mismatch")
    if predecessor_result.get("operational_pass") is not predecessor["required_operational_pass"]:
        raise ValueError("E1C preflight predecessor operational gate mismatch")
    if (
        predecessor_result.get("next_authorized_operation")
        != predecessor["required_next_operation"]
    ):
        raise ValueError("E1C preflight predecessor authorization mismatch")

    candidate = as_object(
        contract["candidate_runtime_artifact"], where="candidate_runtime_artifact"
    )
    official = as_object(contract["official_source_model"], where="official_source_model")
    repository = str(candidate["repository"])
    filename = str(candidate["filename"])
    minimum_size = int(candidate["minimum_size_bytes"])
    maximum_size = int(candidate["maximum_size_bytes"])
    token = os.environ.get("HF_TOKEN", "").strip() or None

    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-runtime-artifact-probe-result-v1",
        "status": "E1C_RUNTIME_ARTIFACT_PROBE_FAIL",
        "operational_pass": False,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "candidate_repository": repository,
        "candidate_revision": None,
        "candidate_file": {
            "filename": filename,
            "size": None,
            "sha256": None,
        },
        "official_source_repository": official["repository"],
        "official_source_revision": official["revision"],
        "model_card": {
            "downloaded": False,
            "sha256": None,
            "names_official_source": False,
            "names_candidate_filename": False,
        },
        "checks": {},
        "error_type": None,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
    }

    try:
        api = HfApi(token=token)
        info = api.model_info(repository, files_metadata=True, token=token)
        revision = str(info.sha)
        siblings = list(info.siblings or ())
        matches = [item for item in siblings if str(item.rfilename) == filename]
        exact_file_present = len(matches) == 1
        metadata = sibling_metadata(matches[0]) if exact_file_present else result["candidate_file"]
        metadata_object = as_object(metadata, where="candidate_file")
        size = metadata_object.get("size")
        digest = metadata_object.get("sha256")

        readme_path = Path(
            hf_hub_download(
                repo_id=repository,
                revision=revision,
                filename="README.md",
                token=token,
                cache_dir=Path(os.environ.get("RUNNER_TEMP", "/tmp"))
                / "e1c-runtime-probe",
            )
        )
        readme = readme_path.read_text(encoding="utf-8", errors="replace")
        names_source = str(official["repository"]) in readme
        names_filename = filename in readme
        checks = {
            "candidate_repository_accessible": True,
            "candidate_revision_immutable": immutable_revision(revision),
            "exact_filename_present": exact_file_present,
            "file_size_within_frozen_bounds": (
                isinstance(size, int) and minimum_size <= size <= maximum_size
            ),
            "file_sha256_visible": (
                isinstance(digest, str)
                and len(digest) == 64
                and all(character in string.hexdigits for character in digest)
            ),
            "model_card_names_official_source": names_source,
            "model_card_names_candidate_filename": names_filename,
            "no_model_weight_download": True,
            "no_model_inference": True,
        }
        passed = all(checks.values())
        result.update(
            {
                "status": (
                    "E1C_RUNTIME_ARTIFACT_PROBE_PASS"
                    if passed
                    else "E1C_RUNTIME_ARTIFACT_PROBE_FAIL"
                ),
                "operational_pass": passed,
                "candidate_revision": revision,
                "candidate_file": metadata_object,
                "model_card": {
                    "downloaded": True,
                    "sha256": sha256_file(readme_path),
                    "names_official_source": names_source,
                    "names_candidate_filename": names_filename,
                },
                "checks": checks,
            }
        )
    except Exception as exc:  # noqa: BLE001 - safe failure metadata is intentional.
        result["error_type"] = type(exc).__name__

    gate = as_object(contract["decision_gate"], where="decision_gate")
    result["next_authorized_operation"] = (
        gate["on_pass"] if result["operational_pass"] is True else gate["on_fail"]
    )
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe E1C GGUF runtime artifact metadata")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args.root.resolve(), args.config.resolve(), args.safe_output.resolve())
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "candidate_revision": result["candidate_revision"],
                "candidate_file": result["candidate_file"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
