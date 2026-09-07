from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]
import sklearn  # type: ignore[import-untyped]

from jbspan.evaluator_cpu_router import (
    Candidate,
    RouterRecord,
    aggregate_metrics_by,
    candidate_specs,
    classification_metrics,
    diagnostic_gate,
    fit_predict_candidates,
    labels_from_probabilities,
    select_rule,
)
from jbspan.evaluator_panel_external_data import (
    normalize_external_text,
    normalized_text_sha256,
    pair_sha256,
)
from jbspan.gate1.util import canonical_json_sha256

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("preflight", "run"))
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/cpu_learned_router_e0g0_v1.json"),
    )
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            rows.append(value)
    return rows


def verify_identity(root: Path, spec: Mapping[str, Any]) -> Path:
    path = root / str(spec["path"])
    if path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"byte-size mismatch: {path}")
    if file_sha256(path) != str(spec["sha256"]):
        raise ValueError(f"SHA-256 mismatch: {path}")
    return path


def record_id(source_id: str, goal: str, response: str) -> tuple[str, str, str]:
    goal_hash = normalized_text_sha256(goal)
    response_hash = normalized_text_sha256(response)
    pair_hash = pair_sha256(
        behavior_group_sha256=goal_hash,
        response_sha256=response_hash,
    )
    identifier = hashlib.sha256(f"{source_id}\0{pair_hash}".encode()).hexdigest()
    return identifier, goal_hash, response_hash


def add_raw_text(
    index: dict[str, tuple[str, str, str, str]],
    *,
    source_id: str,
    goal: str,
    response: str,
) -> None:
    identifier, goal_hash, response_hash = record_id(source_id, goal, response)
    value = (
        goal_hash,
        response_hash,
        normalize_external_text(goal),
        normalize_external_text(response),
    )
    previous = index.get(identifier)
    if previous is not None and previous != value:
        raise ValueError("record-id collision in raw reconstruction")
    index[identifier] = value


def source_specs(source_contract: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = source_contract["sources"]
    if not isinstance(raw, list):
        raise ValueError("source contract sources must be a list")
    output = {str(item["source_id"]): item for item in raw if isinstance(item, Mapping)}
    if set(output) != {"strongreject", "jailbreakbench", "harmbench"}:
        raise ValueError("unexpected E0B source set")
    return output


def verify_raw_file(path: Path, spec: Mapping[str, Any]) -> None:
    if "artifact_bytes" in spec and path.stat().st_size != int(spec["artifact_bytes"]):
        raise ValueError(f"raw source byte-size mismatch: {path}")
    if "artifact_sha256" in spec and file_sha256(path) != str(spec["artifact_sha256"]):
        raise ValueError(f"raw source SHA-256 mismatch: {path}")


def load_strongreject_text(
    root: Path,
    spec: Mapping[str, Any],
    index: dict[str, tuple[str, str, str, str]],
) -> int:
    path = root / str(spec["local_path"])
    verify_raw_file(path, spec)
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            add_raw_text(
                index,
                source_id="strongreject",
                goal=row["forbidden_prompt"],
                response=row["response"],
            )
            count += 1
    if count != int(spec["raw_rows"]):
        raise ValueError("StrongREJECT row-count mismatch")
    return count


def load_jailbreakbench_text(
    root: Path,
    spec: Mapping[str, Any],
    index: dict[str, tuple[str, str, str, str]],
) -> int:
    path = root / str(spec["local_path"])
    verify_raw_file(path, spec)
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            add_raw_text(
                index,
                source_id="jailbreakbench",
                goal=row["goal"],
                response=row["target_response"],
            )
            count += 1
    if count != int(spec["raw_rows"]):
        raise ValueError("JailbreakBench row-count mismatch")
    return count


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def load_harmbench_text(
    root: Path,
    spec: Mapping[str, Any],
    index: dict[str, tuple[str, str, str, str]],
) -> int:
    repo = root / str(spec["local_repository_path"])
    if git(repo, "rev-parse", "HEAD") != str(spec["repository_revision"]):
        raise ValueError("HarmBench repository revision mismatch")
    validation_relative = str(spec["validation_artifact_path"])
    behavior_relative = str(spec["behavior_artifact_path"])
    expected_blobs = {
        "LICENSE": str(spec["repository_license_blob_sha1"]),
        validation_relative: str(spec["validation_artifact_git_blob_sha1"]),
        behavior_relative: str(spec["behavior_artifact_git_blob_sha1"]),
    }
    for relative, expected in expected_blobs.items():
        if git(repo, "rev-parse", f"HEAD:{relative}") != expected:
            raise ValueError(f"HarmBench Git-blob mismatch: {relative}")
    if git(
        repo,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        "LICENSE",
        validation_relative,
        behavior_relative,
    ):
        raise ValueError("HarmBench frozen source has local modifications")

    behaviors: dict[str, str] = {}
    with (repo / behavior_relative).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            behaviors[row["BehaviorID"]] = row["Behavior"]
    raw: object = json.loads((repo / validation_relative).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("HarmBench validation source must be an object")
    raw_count = 0
    joined_count = 0
    for behavior_id, items in raw.items():
        if not isinstance(behavior_id, str) or not isinstance(items, list):
            raise ValueError("invalid HarmBench validation grouping")
        for item in items:
            raw_count += 1
            if behavior_id not in behaviors:
                continue
            if not isinstance(item, dict) or not isinstance(item.get("generation"), str):
                raise ValueError("invalid HarmBench generation")
            add_raw_text(
                index,
                source_id="harmbench",
                goal=behaviors[behavior_id],
                response=str(item["generation"]),
            )
            joined_count += 1
    if raw_count != int(spec["raw_validation_entries"]):
        raise ValueError("HarmBench raw entry-count mismatch")
    if joined_count != int(spec["expected_joined_entries"]):
        raise ValueError("HarmBench joined entry-count mismatch")
    return joined_count


def reconstruct_records(
    root: Path, config: Mapping[str, Any]
) -> tuple[list[RouterRecord], JsonObject]:
    inputs = config["inputs"]
    if not isinstance(inputs, Mapping):
        raise ValueError("inputs must be an object")
    calibration_path = verify_identity(root, inputs["calibration_labels"])
    fold_path = verify_identity(root, inputs["outer_folds"])
    source_contract_path = verify_identity(root, inputs["source_contract"])
    verify_identity(root, inputs["source_preflight"])
    source_contract = load_object(source_contract_path)
    specs = source_specs(source_contract)

    raw_index: dict[str, tuple[str, str, str, str]] = {}
    raw_counts = {
        "strongreject": load_strongreject_text(root, specs["strongreject"], raw_index),
        "jailbreakbench": load_jailbreakbench_text(root, specs["jailbreakbench"], raw_index),
        "harmbench": load_harmbench_text(root, specs["harmbench"], raw_index),
    }

    calibration = load_jsonl(calibration_path)
    folds = load_jsonl(fold_path)
    fold_by_id = {str(row["record_id"]): row for row in folds}
    if len(calibration) != 889 or len(fold_by_id) != 889:
        raise ValueError("frozen calibration denominator mismatch")
    records: list[RouterRecord] = []
    for row in calibration:
        identifier = str(row["record_id"])
        raw_text = raw_index.get(identifier)
        if raw_text is None:
            raise ValueError(f"could not reconstruct frozen record: {identifier}")
        goal_hash, response_hash, goal_text, response_text = raw_text
        if goal_hash != str(row["behavior_group_sha256"]):
            raise ValueError("reconstructed behavior digest mismatch")
        if response_hash != str(row["response_sha256"]):
            raise ValueError("reconstructed response digest mismatch")
        fold = fold_by_id.get(identifier)
        if fold is None:
            raise ValueError("missing frozen outer-fold identity")
        if fold["behavior_group_sha256"] != row["behavior_group_sha256"]:
            raise ValueError("fold behavior identity mismatch")
        if fold["source_id"] != row["source_id"]:
            raise ValueError("fold source identity mismatch")
        records.append(
            RouterRecord(
                record_id=identifier,
                behavior_group_sha256=goal_hash,
                source_id=str(row["source_id"]),
                human_label=str(row["human_label"]),
                human_unanimous=bool(row["human_unanimous"]),
                outer_fold=int(fold["outer_fold"]),
                goal_text=goal_text,
                response_text=response_text,
            )
        )
    records.sort(key=lambda item: item.record_id)
    if len({record.record_id for record in records}) != 889:
        raise ValueError("duplicate reconstructed record identity")
    for group in {record.behavior_group_sha256 for record in records}:
        if (
            len({record.outer_fold for record in records if record.behavior_group_sha256 == group})
            != 1
        ):
            raise ValueError("behavior group crosses frozen outer folds")
    summary: JsonObject = {
        "records": len(records),
        "behavior_groups": len({record.behavior_group_sha256 for record in records}),
        "human_harmful": sum(record.human_label == "HARMFUL" for record in records),
        "human_safe": sum(record.human_label == "SAFE" for record in records),
        "sources": {
            source: sum(record.source_id == source for record in records)
            for source in sorted({record.source_id for record in records})
        },
        "raw_source_rows_verified": raw_counts,
        "raw_text_written": False,
        "heldout_read": False,
    }
    if summary["behavior_groups"] != 265:
        raise ValueError("behavior-group denominator mismatch")
    if summary["human_harmful"] != 290 or summary["human_safe"] != 599:
        raise ValueError("human-label denominator mismatch")
    return records, summary


def inner_probabilities(
    records: Sequence[RouterRecord],
    candidates: Sequence[Candidate],
    config: Mapping[str, Any],
) -> dict[str, list[float]]:
    output = {candidate.candidate_id: [float("nan")] * len(records) for candidate in candidates}
    folds = sorted({record.outer_fold for record in records})
    if len(folds) < 3:
        raise ValueError("inner selection requires at least three group folds")
    for fold in folds:
        train_indices = [index for index, record in enumerate(records) if record.outer_fold != fold]
        test_indices = [index for index, record in enumerate(records) if record.outer_fold == fold]
        predicted = fit_predict_candidates(
            [records[index] for index in train_indices],
            [records[index] for index in test_indices],
            candidates,
            config,
        )
        for candidate_id, values in predicted.items():
            for index, probability in zip(test_indices, values.tolist(), strict=True):
                output[candidate_id][index] = float(probability)
    if any(np.isnan(value) for values in output.values() for value in values):
        raise ValueError("inner OOF prediction matrix is incomplete")
    return output


def selected_rule_record(fold: int | str, selected: Any) -> JsonObject:
    if selected is None:
        return {"fold": fold, "selection_defined": False}
    return {
        "fold": fold,
        "selection_defined": True,
        "candidate_id": selected.candidate.candidate_id,
        "safe_threshold": selected.safe_threshold,
        "harmful_threshold": selected.harmful_threshold,
        "inner_oof_metrics": dict(selected.selection_metrics),
    }


def nested_oof(
    records: Sequence[RouterRecord],
    config: Mapping[str, Any],
) -> tuple[list[str], dict[str, list[str]], list[JsonObject]]:
    candidates = candidate_specs(config)
    output = ["ABSTAIN"] * len(records)
    ablations = {
        "response_only": ["ABSTAIN"] * len(records),
        "goal_only": ["ABSTAIN"] * len(records),
    }
    selections: list[JsonObject] = []
    for outer_fold in range(5):
        train_indices = [
            index for index, record in enumerate(records) if record.outer_fold != outer_fold
        ]
        test_indices = [
            index for index, record in enumerate(records) if record.outer_fold == outer_fold
        ]
        training = [records[index] for index in train_indices]
        testing = [records[index] for index in test_indices]
        probabilities = inner_probabilities(training, candidates, config)
        selected = select_rule(training, probabilities, candidates, config)
        selections.append(selected_rule_record(outer_fold, selected))
        if selected is None:
            continue
        primary_probability = fit_predict_candidates(
            training,
            testing,
            [selected.candidate],
            config,
        )[selected.candidate.candidate_id]
        primary_labels = labels_from_probabilities(
            primary_probability.tolist(),
            safe_threshold=selected.safe_threshold,
            harmful_threshold=selected.harmful_threshold,
        )
        for index, label in zip(test_indices, primary_labels, strict=True):
            output[index] = label
        for representation in ablations:
            values = fit_predict_candidates(
                training,
                testing,
                [selected.candidate],
                config,
                representation=representation,
            )[selected.candidate.candidate_id]
            labels = labels_from_probabilities(
                values.tolist(),
                safe_threshold=selected.safe_threshold,
                harmful_threshold=selected.harmful_threshold,
            )
            for index, label in zip(test_indices, labels, strict=True):
                ablations[representation][index] = label
    return output, ablations, selections


def leave_one_source_out(
    records: Sequence[RouterRecord],
    config: Mapping[str, Any],
) -> list[JsonObject]:
    candidates = candidate_specs(config)
    results: list[JsonObject] = []
    for source in sorted({record.source_id for record in records}):
        training = [record for record in records if record.source_id != source]
        testing = [record for record in records if record.source_id == source]
        probabilities = inner_probabilities(training, candidates, config)
        selected = select_rule(training, probabilities, candidates, config)
        row = selected_rule_record(source, selected)
        row["heldout_source"] = source
        row["training_records"] = len(training)
        row["test_records"] = len(testing)
        if selected is None:
            row["metrics"] = classification_metrics(
                [record.human_label for record in testing],
                ["ABSTAIN"] * len(testing),
            )
        else:
            values = fit_predict_candidates(
                training,
                testing,
                [selected.candidate],
                config,
            )[selected.candidate.candidate_id]
            labels = labels_from_probabilities(
                values.tolist(),
                safe_threshold=selected.safe_threshold,
                harmful_threshold=selected.harmful_threshold,
            )
            row["metrics"] = classification_metrics(
                [record.human_label for record in testing], labels
            )
        results.append(row)
    return results


def safe_write(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"refusing to overwrite different frozen output: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def preflight(root: Path, config_path: Path) -> JsonObject:
    config = load_object(config_path)
    if config.get("schema_version") != "jbspan-e0g0-cpu-learned-router-diagnostic-v1":
        raise ValueError("unsupported E0G-0 contract")
    if config.get("frozen") is not True or config.get("paper_validity") is not False:
        raise ValueError("E0G-0 must remain frozen and development-only")
    role = config["scientific_role"]
    if not isinstance(role, Mapping):
        raise ValueError("scientific_role must be an object")
    if role.get("standalone_primary_judge_allowed") is not False:
        raise ValueError("learned router cannot be a standalone primary judge")
    protected = config["protected_boundaries"]
    if not isinstance(protected, Mapping) or any(protected.values()):
        raise ValueError("all E0G-0 protected-boundary observations must be false")
    records, reconstruction = reconstruct_records(root, config)
    recording = config["recording"]
    if not isinstance(recording, Mapping):
        raise ValueError("recording must be an object")
    result: JsonObject = {
        "schema_version": "jbspan-e0g0-cpu-learned-router-preflight-v1",
        "status": "E0G0_CPU_LEARNED_ROUTER_PREFLIGHT_PASS",
        "contract": {
            "path": config_path.relative_to(root).as_posix(),
            "bytes": config_path.stat().st_size,
            "sha256": file_sha256(config_path),
        },
        "implementation": {
            "script": {
                "path": Path(__file__).resolve().relative_to(root).as_posix(),
                "bytes": Path(__file__).stat().st_size,
                "sha256": file_sha256(Path(__file__)),
            },
            "module": {
                "path": "src/jbspan/evaluator_cpu_router.py",
                "bytes": (root / "src/jbspan/evaluator_cpu_router.py").stat().st_size,
                "sha256": file_sha256(root / "src/jbspan/evaluator_cpu_router.py"),
            },
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "reconstruction": reconstruction,
        "candidate_count": len(candidate_specs(config)),
        "protected_boundaries": dict(protected),
        "raw_text_printed": False,
        "raw_text_written": False,
    }
    result["preflight_identity_sha256"] = canonical_json_sha256(result)
    safe_write(root / str(recording["preflight_path"]), result)
    _ = records
    return result


def run(root: Path, config_path: Path) -> JsonObject:
    config = load_object(config_path)
    preflight_result = preflight(root, config_path)
    records, reconstruction = reconstruct_records(root, config)
    predictions, ablations, selections = nested_oof(records, config)
    truth = [record.human_label for record in records]
    pooled = classification_metrics(truth, predictions)
    per_source = aggregate_metrics_by(records, predictions, "source")
    per_unanimity = aggregate_metrics_by(records, predictions, "unanimity")
    selected_count = sum(bool(row["selection_defined"]) for row in selections)
    gate = diagnostic_gate(pooled, per_source, selected_count, config)
    ablation_metrics = {
        key: classification_metrics(truth, values) for key, values in sorted(ablations.items())
    }
    loso = leave_one_source_out(records, config)
    status = (
        "E0G0_CPU_LEARNED_ROUTER_DIAGNOSTIC_PASS"
        if gate["passes_all"]
        else "E0G0_CPU_LEARNED_ROUTER_DIAGNOSTIC_FAIL"
    )
    recording = config["recording"]
    if not isinstance(recording, Mapping):
        raise ValueError("recording must be an object")
    result: JsonObject = {
        "schema_version": "jbspan-e0g0-cpu-learned-router-result-v1",
        "status": status,
        "evidence_class": "DEVELOPMENT_ONLY_NESTED_OOF_ROUTER_DIAGNOSTIC_NOT_PANEL_QUALIFICATION",
        "contract_sha256": file_sha256(config_path),
        "preflight_identity_sha256": preflight_result["preflight_identity_sha256"],
        "reconstruction": reconstruction,
        "nested_oof": {
            "outer_fold_selections": selections,
            "pooled_metrics": pooled,
            "per_source_metrics": per_source,
            "per_human_agreement_metrics": per_unanimity,
            "diagnostic_gate": gate,
        },
        "stress_tests": {
            "field_ablation_metrics": ablation_metrics,
            "leave_one_source_out": loso,
            "may_override_primary_gate": False,
        },
        "interpretation": (
            config["diagnostic_gate"]["interpretation_on_pass"]
            if gate["passes_all"]
            else config["diagnostic_gate"]["interpretation_on_fail"]
        ),
        "next_operation": (
            config["next_operation_on_pass"]
            if gate["passes_all"]
            else config["next_operation_on_fail"]
        ),
        "protected_boundaries": dict(config["protected_boundaries"]),
        "new_foundation_model_inference": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "raw_text_printed": False,
        "raw_text_written": False,
        "per_record_predictions_written": False,
        "panel_qualified": False,
        "paper_valid_result": False,
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(root / str(recording["result_path"]), result)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = root / config_path
    result = preflight(root, config_path) if args.command == "preflight" else run(root, config_path)
    safe_summary = {
        "status": result["status"],
        "identity": result.get("result_identity_sha256") or result.get("preflight_identity_sha256"),
    }
    print(json.dumps(safe_summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
