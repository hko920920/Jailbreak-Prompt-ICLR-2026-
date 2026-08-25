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
    return {"filename": filename, "size": size, "sha256": sha256}


def validate_predecessors(root: Path, contract: JsonObject) -> None:
    predecessors = as_object(contract["predecessors"], where="predecessors")
    e1c = as_object(predecessors["e1c_preflight"], where="e1c_preflight")
    e1c_result = load_object(root / str(e1c["result_path"]))
    if e1c_result.get("status") != e1c["required_status"]:
        raise ValueError("E1C preflight status mismatch")
    if e1c_result.get("operational_pass") is not e1c["required_operational_pass"]:
        raise ValueError("E1C preflight gate mismatch")

    rejected = as_object(
        predecessors["candidate_1_rejection"], where="candidate_1_rejection"
    )
    rejected_result = load_object(root / str(rejected["result_path"]))
    if rejected_result.get("status") != rejected["required_status"]:
        raise ValueError("candidate 1 rejection status mismatch")
    if (
        rejected_result.get("operational_pass")
        is not rejected["required_operational_pass"]
    ):
        raise ValueError("candidate 1 rejection gate mismatch")
    if (
        rejected_result.get("next_authorized_operation")
        != rejected["required_next_operation"]
    ):
        raise ValueError("candidate 1 rejection authorization mismatch")
    if rejected_result.get("candidate_repository") != rejected["rejected_repository"]:
        raise ValueError("candidate 1 repository mismatch")


def run(root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    from huggingface_hub import HfApi, hf_hub_download

    contract = load_object(config_path)
    if contract.get("status") != "FROZEN_BEFORE_E1C_RUNTIME_ARTIFACT_V2_METADATA_QUERY":
        raise ValueError("unexpected E1C runtime artifact v2 probe status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("runtime artifact v2 probe must be frozen and non-paper-valid")
    validate_predecessors(root, contract)

    candidate = as_object(
        contract["candidate_runtime_artifact"], where="candidate_runtime_artifact"
    )
    selection = as_object(candidate["filename_selection"], where="filename_selection")
    official = as_object(contract["official_source_model"], where="official_source_model")
    repository = str(candidate["repository"])
    prefix = str(selection["required_prefix"])
    suffix = str(selection["required_suffix"])
    required_match_count = int(selection["required_match_count"])
    minimum_size = int(candidate["minimum_size_bytes"])
    maximum_size = int(candidate["maximum_size_bytes"])
    token = os.environ.get("HF_TOKEN", "").strip() or None

    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-runtime-artifact-probe-v2-result-v1",
        "status": "E1C_RUNTIME_ARTIFACT_V2_PROBE_FAIL",
        "operational_pass": False,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "candidate_repository": repository,
        "candidate_revision": None,
        "selection_rule": {
            "required_prefix": prefix,
            "required_suffix": suffix,
            "required_match_count": required_match_count,
        },
        "matching_files": [],
        "selected_file": None,
        "official_source_repository": official["repository"],
        "official_source_revision": official["revision"],
        "model_card": {
            "downloaded": False,
            "sha256": None,
            "names_official_source": False,
            "names_selected_file": False,
            "states_static_quantization": False,
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
        all_files = [sibling_metadata(item) for item in list(info.siblings or ())]
        matches = [
            item
            for item in all_files
            if str(item["filename"]).startswith(prefix)
            and str(item["filename"]).endswith(suffix)
        ]
        selected = matches[0] if len(matches) == required_match_count else None
        size = selected.get("size") if selected is not None else None
        digest = selected.get("sha256") if selected is not None else None
        selected_filename = str(selected["filename"]) if selected is not None else ""

        readme_path = Path(
            hf_hub_download(
                repo_id=repository,
                revision=revision,
                filename="README.md",
                token=token,
                cache_dir=Path(os.environ.get("RUNNER_TEMP", "/tmp"))
                / "e1c-runtime-probe-v2",
            )
        )
        readme = readme_path.read_text(encoding="utf-8", errors="replace")
        readme_lower = readme.lower()
        names_source = str(official["repository"]) in readme
        names_selected = bool(selected_filename) and selected_filename in readme
        static_quantization = "static quants" in readme_lower
        checks = {
            "candidate_repository_accessible": True,
            "candidate_revision_immutable": immutable_revision(revision),
            "selection_rule_has_exactly_one_match": len(matches) == required_match_count,
            "file_size_within_frozen_bounds": (
                isinstance(size, int) and minimum_size <= size <= maximum_size
            ),
            "file_sha256_visible": (
                isinstance(digest, str)
                and len(digest) == 64
                and all(character in string.hexdigits for character in digest)
            ),
            "model_card_names_official_source": names_source,
            "model_card_names_selected_file": names_selected,
            "model_card_states_static_quantization": static_quantization,
            "no_model_weight_download": True,
            "no_model_inference": True,
        }
        passed = all(checks.values())
        result.update(
            {
                "status": (
                    "E1C_RUNTIME_ARTIFACT_V2_PROBE_PASS"
                    if passed
                    else "E1C_RUNTIME_ARTIFACT_V2_PROBE_FAIL"
                ),
                "operational_pass": passed,
                "candidate_revision": revision,
                "matching_files": matches,
                "selected_file": selected,
                "model_card": {
                    "downloaded": True,
                    "sha256": sha256_file(readme_path),
                    "names_official_source": names_source,
                    "names_selected_file": names_selected,
                    "states_static_quantization": static_quantization,
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
    parser = argparse.ArgumentParser(description="Probe E1C runtime artifact candidate v2")
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
                "selected_file": result["selected_file"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
