from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


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
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def git_tree_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def human_label(row: JsonObject) -> tuple[int, bool]:
    votes: list[int] = []
    for key in ("human_0", "human_1", "human_2"):
        value = row.get(key)
        if isinstance(value, bool):
            votes.append(int(value))
        elif isinstance(value, int) and value in (0, 1):
            votes.append(value)
        else:
            raise ValueError(f"invalid human vote in {key}")
    return (1 if sum(votes) >= 2 else 0, len(set(votes)) == 1)


def private_record_id(behavior_id: str, row: JsonObject) -> str:
    private_identity = {
        "behavior_id": behavior_id,
        "test_case": row.get("test_case"),
        "generation": row.get("generation"),
        "model": row.get("model"),
        "method": row.get("method"),
        "experiment": row.get("experiment"),
        "human_0": row.get("human_0"),
        "human_1": row.get("human_1"),
        "human_2": row.get("human_2"),
    }
    if not isinstance(private_identity["test_case"], str):
        raise ValueError("validation row is missing test_case")
    if not isinstance(private_identity["generation"], str):
        raise ValueError("validation row is missing generation")
    return canonical_sha256(private_identity)


def flatten_validation(value: JsonObject) -> list[JsonObject]:
    records: list[JsonObject] = []
    observed_ids: set[str] = set()
    for behavior_id, raw_rows in sorted(value.items()):
        if not isinstance(behavior_id, str) or not isinstance(raw_rows, list):
            raise TypeError("validation set must map behavior IDs to row arrays")
        behavior_hash = sha256_bytes(behavior_id.encode())
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise TypeError("validation row must be an object")
            row = cast(JsonObject, raw_row)
            label, unanimous = human_label(row)
            record_id = private_record_id(behavior_id, row)
            if record_id in observed_ids:
                raise ValueError("duplicate canonical validation record")
            observed_ids.add(record_id)
            records.append(
                {
                    "record_id": record_id,
                    "behavior_id_private": behavior_id,
                    "behavior_hash": behavior_hash,
                    "label": label,
                    "human_unanimous": unanimous,
                }
            )
    return records


def select_balanced(records: list[JsonObject], per_label: int) -> list[JsonObject]:
    selected: list[JsonObject] = []
    for label in (0, 1):
        grouped: dict[str, deque[JsonObject]] = defaultdict(deque)
        for row in records:
            if row["label"] == label:
                behavior = str(row["behavior_id_private"])
                grouped[behavior].append(row)
        for behavior, queue in grouped.items():
            grouped[behavior] = deque(sorted(queue, key=lambda item: str(item["record_id"])))
        behavior_order = sorted(
            grouped,
            key=lambda value: sha256_bytes(f"{label}:{value}".encode()),
        )
        label_rows: list[JsonObject] = []
        while len(label_rows) < per_label:
            made_progress = False
            for behavior in behavior_order:
                queue = grouped[behavior]
                if queue and len(label_rows) < per_label:
                    label_rows.append(queue.popleft())
                    made_progress = True
            if not made_progress:
                raise ValueError(f"insufficient records for label {label}")
        selected.extend(label_rows)
    return selected


def relevant_model_file(name: str) -> bool:
    basename = Path(name).name
    return (
        basename in {
            "config.json",
            "generation_config.json",
            "tokenizer.json",
            "tokenizer.model",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "model.safetensors.index.json",
            "pytorch_model.bin.index.json",
        }
        or name.endswith(".safetensors")
        or name.endswith(".bin")
    )


def model_metadata(repository: str, expected_architecture: str) -> JsonObject:
    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN", "").strip()
    result: JsonObject = {
        "repository": repository,
        "access_ok": False,
        "revision": None,
        "architecture": [],
        "files": [],
        "weight_file_count": 0,
        "weight_bytes": 0,
        "error_type": None,
    }
    if not token:
        result["error_type"] = "MissingHFToken"
        return result
    try:
        api = HfApi(token=token)
        info = api.model_info(repository, files_metadata=True, token=token)
        revision = str(info.sha)
        if len(revision) != 40:
            raise RuntimeError("classifier revision is not immutable")
        files: list[JsonObject] = []
        weight_file_count = 0
        weight_bytes = 0
        for sibling in info.siblings or ():
            name = str(sibling.rfilename)
            if not relevant_model_file(name):
                continue
            entry: JsonObject = {"filename": name}
            size = getattr(sibling, "size", None)
            lfs = getattr(sibling, "lfs", None)
            if isinstance(lfs, dict):
                digest = lfs.get("sha256")
                if isinstance(digest, str):
                    entry["sha256"] = digest
                lfs_size = lfs.get("size")
                if isinstance(lfs_size, int):
                    size = lfs_size
            elif lfs is not None:
                digest = getattr(lfs, "sha256", None)
                if isinstance(digest, str):
                    entry["sha256"] = digest
                lfs_size = getattr(lfs, "size", None)
                if isinstance(lfs_size, int):
                    size = lfs_size
            if isinstance(size, int):
                entry["size"] = size
            if name.endswith((".safetensors", ".bin")) and "tokenizer" not in name:
                weight_file_count += 1
                if isinstance(size, int):
                    weight_bytes += size
            files.append(entry)
        config_path = Path(
            hf_hub_download(
                repo_id=repository,
                revision=revision,
                filename="config.json",
                token=token,
                cache_dir=Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "e1c-hf",
            )
        )
        model_config = load_object(config_path)
        architectures = model_config.get("architectures")
        if not isinstance(architectures, list) or not all(
            isinstance(item, str) for item in architectures
        ):
            raise RuntimeError("classifier config lacks architectures")
        if expected_architecture not in cast(list[str], architectures):
            raise RuntimeError("classifier architecture differs from contract")
        if weight_file_count == 0 or weight_bytes <= 0:
            raise RuntimeError("classifier weight metadata is unavailable")
        result.update(
            {
                "access_ok": True,
                "revision": revision,
                "architecture": architectures,
                "files": sorted(files, key=lambda item: str(item["filename"])),
                "weight_file_count": weight_file_count,
                "weight_bytes": weight_bytes,
            }
        )
    except Exception as exc:  # noqa: BLE001 - safe failure metadata is intentional.
        result["error_type"] = type(exc).__name__
    return result


def safe_selection_rows(selected: list[JsonObject]) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for index, row in enumerate(selected):
        rows.append(
            {
                "position": index,
                "record_id": row["record_id"],
                "behavior_hash": row["behavior_hash"],
                "label": row["label"],
            }
        )
    return rows


def run(
    config_path: Path,
    source_root: Path,
    safe_output: Path,
    selection_output: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if contract["status"] != "FROZEN_BEFORE_E1C_HARMBENCH_PREFLIGHT":
        raise ValueError("unexpected E1C preflight status")
    if contract["frozen"] is not True or contract["paper_validity"] is not False:
        raise ValueError("E1C preflight contract is not frozen")

    predecessor = as_object(contract["predecessor"], where="predecessor")
    predecessor_result = load_object(Path(str(predecessor["result_path"])))
    if predecessor_result.get("status") != predecessor["required_status"]:
        raise ValueError("E1B predecessor status mismatch")
    if (
        predecessor_result.get("next_authorized_operation")
        != predecessor["required_next_operation"]
    ):
        raise ValueError("E1B predecessor authorization mismatch")

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    expected_files = as_object(source["files"], where="harmbench_source.files")
    observed_tree = git_tree_sha(source_root)
    source_file_rows: list[JsonObject] = []
    source_files_pass = True
    for relative, expected_blob in sorted(expected_files.items()):
        path = source_root / relative
        exists = path.is_file()
        observed_blob = git_blob_sha(path) if exists else None
        matches = observed_blob == expected_blob
        source_files_pass = source_files_pass and matches
        source_file_rows.append(
            {
                "path": relative,
                "exists": exists,
                "expected_git_blob_sha": expected_blob,
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": matches,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": sha256_file(path) if exists else None,
            }
        )
    tree_matches = observed_tree == source["tree_sha"]

    validation_data = as_object(
        contract["validation_data"], where="validation_data"
    )
    validation = load_object(source_root / str(validation_data["path"]))
    records = flatten_validation(validation)
    selection_config = as_object(contract["selection"], where="selection")
    per_label = int(selection_config["per_label_target"])
    selected = select_balanced(records, per_label)
    safe_rows = safe_selection_rows(selected)

    label_counts = {
        str(label): sum(int(row["label"] == label) for row in records) for label in (0, 1)
    }
    selection_label_counts = {
        str(label): sum(int(row["label"] == label) for row in selected) for label in (0, 1)
    }
    behavior_hashes = {str(row["behavior_hash"]) for row in records}
    selection_behavior_hashes = {str(row["behavior_hash"]) for row in selected}

    classifier = as_object(contract["official_classifier"], where="official_classifier")
    model = model_metadata(
        str(classifier["repository"]),
        str(classifier["expected_architecture_contains"]),
    )
    target_count = int(selection_config["target_count"])
    selection_pass = (
        len(selected) == target_count
        and selection_label_counts == {"0": per_label, "1": per_label}
        and len({str(row["record_id"]) for row in selected}) == target_count
    )
    operational_pass = all(
        (
            tree_matches,
            source_files_pass,
            len(records) >= target_count,
            label_counts["0"] >= per_label,
            label_counts["1"] >= per_label,
            selection_pass,
            model["access_ok"] is True,
        )
    )
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-harmbench-preflight-result-v1",
        "status": (
            "E1C_HARMBENCH_PREFLIGHT_PASS"
            if operational_pass
            else "E1C_HARMBENCH_PREFLIGHT_FAIL"
        ),
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "operational_pass": operational_pass,
        "contract_sha256": sha256_file(config_path),
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": source["tree_sha"],
            "observed_tree_sha": observed_tree,
            "tree_match": tree_matches,
            "files": source_file_rows,
        },
        "validation": {
            "record_count": len(records),
            "behavior_count": len(behavior_hashes),
            "label_counts": label_counts,
            "human_unanimous_count": sum(
                int(row["human_unanimous"] is True) for row in records
            ),
            "raw_text_recorded": False,
        },
        "selection": {
            "count": len(selected),
            "label_counts": selection_label_counts,
            "behavior_count": len(selection_behavior_hashes),
            "record_ids_sha256": canonical_sha256(
                [str(row["record_id"]) for row in safe_rows]
            ),
            "safe_rows_sha256": canonical_sha256(safe_rows),
            "deterministic": selection_pass,
            "raw_text_recorded": False,
        },
        "official_classifier": model,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": (
            gate["on_pass"] if operational_pass else gate["on_fail"]
        ),
    }
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    selection_output.parent.mkdir(parents=True, exist_ok=True)
    with selection_output.open("w", encoding="utf-8") as handle:
        for row in safe_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen E1C HarmBench preflight")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--selection-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args.config, args.source_root, args.safe_output, args.selection_output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "record_count": as_object(result["validation"], where="validation")[
                    "record_count"
                ],
                "selection_count": as_object(result["selection"], where="selection")[
                    "count"
                ],
                "classifier_access_ok": as_object(
                    result["official_classifier"], where="official_classifier"
                )["access_ok"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
