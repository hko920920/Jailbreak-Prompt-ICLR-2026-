from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import types
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def load_module(path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_preflight", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSONL object: {path}")
        rows.append(cast(JsonObject, value))
    return rows


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def as_string_list(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def git_tree_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def registry_rows(path: Path, id_field: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        behavior_id = row.get(id_field)
        if not behavior_id:
            raise ValueError(f"registry row lacks {id_field}: {path}")
        if behavior_id in result:
            raise ValueError(f"duplicate registry ID: {behavior_id}")
        result[behavior_id] = dict(row)
    return result


def resolvable_behavior_ids(
    text_registry: dict[str, dict[str, str]],
    multimodal_registry: dict[str, dict[str, str]],
    behavior_field: str,
    context_field: str,
) -> set[str]:
    registry = dict(text_registry)
    registry.update(multimodal_registry)
    return {
        behavior_id
        for behavior_id, row in registry.items()
        if behavior_field in row and context_field in row
    }


def select_balanced(
    records: list[JsonObject],
    *,
    per_label: int,
    allowed_behavior_ids: set[str],
) -> list[JsonObject]:
    eligible = [
        row for row in records
        if str(row["behavior_id_private"]) in allowed_behavior_ids
    ]
    selected: list[JsonObject] = []
    for label in (0, 1):
        grouped: dict[str, deque[JsonObject]] = defaultdict(deque)
        for row in eligible:
            if row["label"] == label:
                grouped[str(row["behavior_id_private"])].append(row)
        for behavior, queue in grouped.items():
            grouped[behavior] = deque(
                sorted(queue, key=lambda item: str(item["record_id"]))
            )
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
                raise ValueError(f"insufficient resolvable records for label {label}")
        selected.extend(label_rows)
    return selected


def label_counts(rows: list[JsonObject]) -> dict[str, int]:
    counts: Counter[int] = Counter()
    for row in rows:
        label = row.get("label")
        if not isinstance(label, int) or isinstance(label, bool) or label not in (0, 1):
            raise ValueError("invalid binary label")
        counts[label] += 1
    return {"0": counts[0], "1": counts[1]}


def safe_rows(selected: list[JsonObject]) -> list[JsonObject]:
    return [
        {
            "position": index,
            "record_id": row["record_id"],
            "behavior_hash": row["behavior_hash"],
            "label": row["label"],
        }
        for index, row in enumerate(selected)
    ]


def source_identity(source_root: Path, files: JsonObject) -> tuple[list[JsonObject], bool]:
    rows: list[JsonObject] = []
    passed = True
    for relative, expected in sorted(files.items()):
        path = source_root / relative
        observed = git_blob_sha(path) if path.is_file() else None
        match = observed == expected
        passed = passed and match
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "expected_git_blob_sha": expected,
                "observed_git_blob_sha": observed,
                "git_blob_match": match,
                "sha256": sha256_file(path) if path.is_file() else None,
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    return rows, passed


def run(
    root: Path,
    source_root: Path,
    config_path: Path,
    safe_output: Path,
    selection_output: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if contract["status"] != "FROZEN_BEFORE_E1C_SELECTION_REPAIR":
        raise ValueError("unexpected repair contract status")
    if contract["frozen"] is not True or contract["paper_validity"] is not False:
        raise ValueError("invalid frozen boundary")

    predecessor = as_object(contract["predecessor"], where="predecessor")
    predecessor_result = load_object(root / str(predecessor["result_path"]))
    for key, expected in (
        ("status", predecessor["required_status"]),
        ("operational_pass", predecessor["required_operational_pass"]),
        ("next_authorized_operation", predecessor["required_next_operation"]),
        ("harmbench_live_predictions_generated", predecessor["required_live_predictions"]),
    ):
        if predecessor_result.get(key) != expected:
            raise ValueError(f"predecessor mismatch: {key}")

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    observed_tree = git_tree_sha(source_root)
    source_rows, source_pass = source_identity(
        source_root, as_object(source["files"], where="harmbench_source.files")
    )

    registry = as_object(contract["registry"], where="registry")
    id_field = str(registry["required_id_field"])
    behavior_field = str(registry["required_behavior_field"])
    context_field = str(registry["required_context_field"])
    text_registry = registry_rows(source_root / str(registry["text_csv"]), id_field)
    multimodal_registry = registry_rows(
        source_root / str(registry["multimodal_csv"]), id_field
    )
    allowed_ids = resolvable_behavior_ids(
        text_registry, multimodal_registry, behavior_field, context_field
    )
    allowed_hashes = {
        sha256_bytes(behavior_id.encode("utf-8")) for behavior_id in allowed_ids
    }

    helper = load_module(root / "scripts/run_evaluator_panel_e1c_harmbench_preflight.py")
    validation = as_object(contract["validation"], where="validation")
    records = helper.flatten_validation(
        load_object(source_root / str(validation["path"]))
    )
    old_contract = as_object(contract["old_selection"], where="old_selection")
    old_rows = load_jsonl(root / str(old_contract["path"]))
    old_record_ids = [str(row["record_id"]) for row in old_rows]
    old_identity = canonical_sha256(old_record_ids)
    old_missing = [
        row for row in old_rows if str(row.get("behavior_hash")) not in allowed_hashes
    ]
    old_missing_hashes = sorted(
        {str(row.get("behavior_hash")) for row in old_missing}
    )

    new_contract = as_object(contract["new_selection"], where="new_selection")
    per_label = int(new_contract["per_label_target"])
    selected = select_balanced(
        records, per_label=per_label, allowed_behavior_ids=allowed_ids
    )
    selected_repeat = select_balanced(
        records, per_label=per_label, allowed_behavior_ids=allowed_ids
    )
    new_rows = safe_rows(selected)
    new_rows_repeat = safe_rows(selected_repeat)
    new_record_ids = [str(row["record_id"]) for row in new_rows]
    old_set = set(old_record_ids)
    new_set = set(new_record_ids)
    dropped = sorted(old_set - new_set)
    added = sorted(new_set - old_set)
    new_missing = [
        row for row in new_rows if str(row["behavior_hash"]) not in allowed_hashes
    ]

    predecessor_expected_hashes = sorted(
        as_string_list(
            predecessor["expected_selected_missing_behavior_hashes"],
            where="predecessor.expected_selected_missing_behavior_hashes",
        )
    )
    expected_old_labels = as_object(
        old_contract["required_label_counts"],
        where="old_selection.required_label_counts",
    )
    expected_new_labels = {"0": per_label, "1": per_label}
    checks = {
        "source_tree_matches": observed_tree == source["tree_sha"],
        "source_files_match": source_pass,
        "old_count_matches": len(old_rows) == old_contract["required_record_count"],
        "old_labels_match": label_counts(old_rows) == expected_old_labels,
        "old_identity_matches": old_identity == old_contract["required_record_ids_sha256"],
        "old_missing_count_matches": (
            len(old_missing)
            == predecessor["expected_selected_missing_registry_row_count"]
        ),
        "old_missing_hashes_match": old_missing_hashes == predecessor_expected_hashes,
        "new_count_matches": len(new_rows) == new_contract["target_count"],
        "new_labels_match": label_counts(new_rows) == expected_new_labels,
        "new_ids_unique": len(new_set) == len(new_rows),
        "new_selection_deterministic": new_rows == new_rows_repeat,
        "new_rows_resolve": len(new_missing) == 0,
        "dropped_count_matches": (
            len(dropped) == new_contract["expected_dropped_record_count"]
        ),
        "added_count_matches": len(added) == new_contract["expected_added_record_count"],
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_live_predictions": True,
    }
    passed = all(checks.values())
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-selection-repair-result-v1",
        "status": "E1C_SELECTION_REPAIR_PASS" if passed else "E1C_SELECTION_REPAIR_FAIL",
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": sha256_file(config_path),
        "predecessor_status": predecessor_result["status"],
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": source["tree_sha"],
            "observed_tree_sha": observed_tree,
            "files": source_rows,
        },
        "registry": {
            "text_count": len(text_registry),
            "multimodal_count": len(multimodal_registry),
            "resolvable_behavior_count": len(allowed_ids),
            "raw_behavior_ids_or_text_recorded": False,
        },
        "old_selection": {
            "record_count": len(old_rows),
            "label_counts": label_counts(old_rows),
            "record_ids_sha256": old_identity,
            "missing_registry_row_count": len(old_missing),
            "missing_behavior_hashes": old_missing_hashes,
            "raw_records_recorded": False,
        },
        "new_selection": {
            "record_count": len(new_rows),
            "label_counts": label_counts(new_rows),
            "behavior_count": len({str(row["behavior_hash"]) for row in new_rows}),
            "record_ids_sha256": canonical_sha256(new_record_ids),
            "safe_rows_sha256": canonical_sha256(new_rows),
            "dropped_record_count": len(dropped),
            "dropped_record_ids_sha256": canonical_sha256(dropped),
            "added_record_count": len(added),
            "added_record_ids_sha256": canonical_sha256(added),
            "missing_registry_row_count": len(new_missing),
            "deterministic": new_rows == new_rows_repeat,
            "raw_records_recorded": False,
        },
        "checks": checks,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["on_pass"] if passed else gate["on_fail"],
    }

    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    selection_output.parent.mkdir(parents=True, exist_ok=True)
    with selection_output.open("w", encoding="utf-8") as handle:
        for row in new_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair E1C selection source coverage")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--selection-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        args.root.resolve(),
        args.source_root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
        args.selection_output.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "old_selection": result["old_selection"],
                "new_selection": result["new_selection"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
