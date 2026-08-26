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


def jsonl_bytes(rows: list[JsonObject]) -> bytes:
    return b"".join(
        (json.dumps(row, sort_keys=True) + "\n").encode("utf-8") for row in rows
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jsonl_bytes(rows))


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


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def git_blob_sha_bytes(payload: bytes) -> str:
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git identity.


def git_blob_sha(path: Path) -> str:
    return git_blob_sha_bytes(path.read_bytes())


def git_tree_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_module(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def validate_local_helpers(root: Path, contract: JsonObject) -> JsonObject:
    helpers = as_object(contract["local_helpers"], where="local_helpers")
    checks: dict[str, bool] = {}
    observed: dict[str, JsonObject] = {}
    for prefix in ("preflight", "prompt_source", "live_module"):
        path = root / str(helpers[f"{prefix}_path"])
        expected = str(helpers[f"{prefix}_git_blob_sha"])
        actual = git_blob_sha(path)
        checks[prefix] = actual == expected
        observed[prefix] = {
            "path": str(helpers[f"{prefix}_path"]),
            "git_blob_sha": actual,
        }
    if not all(checks.values()):
        raise ValueError(f"local helper identity mismatch: {checks}")
    return {
        "checks": checks,
        "helpers": observed,
        "raw_source_recorded": False,
    }


def validate_base_live_contract(root: Path, contract: JsonObject) -> JsonObject:
    frozen = as_object(contract["base_live_contract"], where="base_live_contract")
    path = root / str(frozen["path"])
    if git_blob_sha(path) != frozen["required_git_blob_sha"]:
        raise ValueError("base E1C live contract identity changed")
    live = load_object(path)
    if live.get("schema_version") != frozen["required_schema_version"]:
        raise ValueError("base E1C live contract schema changed")
    component = as_object(live["component"], where="base_live_contract.component")
    canary = as_object(live["injection_canaries"], where="injection_canaries")
    checks = {
        "model_repository": (
            component.get("runtime_model_repository")
            == frozen["required_model_repository"]
        ),
        "model_revision": (
            component.get("runtime_model_revision")
            == frozen["required_model_revision"]
        ),
        "runtime_filename": (
            component.get("runtime_filename") == frozen["required_runtime_filename"]
        ),
        "runtime_sha256": (
            component.get("runtime_sha256") == frozen["required_runtime_sha256"]
        ),
        "prompt_family": (
            component.get("prompt_family") == frozen["required_prompt_family"]
        ),
        "positive_generation_sha256": (
            sha256_text(str(canary.get("positive_generation", "")))
            == frozen["required_positive_generation_sha256"]
        ),
        "positive_generation_length": (
            len(str(canary.get("positive_generation", "")))
            == int(frozen["required_positive_generation_length"])
        ),
        "safe_generation_sha256": (
            sha256_text(str(canary.get("safe_generation", "")))
            == frozen["required_safe_generation_sha256"]
        ),
        "safe_generation_length": (
            len(str(canary.get("safe_generation", "")))
            == int(frozen["required_safe_generation_length"])
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"base E1C live contract mismatch: {checks}")
    return {
        "path": str(frozen["path"]),
        "git_blob_sha": git_blob_sha(path),
        "sha256": sha256_file(path),
        "checks": checks,
        "raw_canary_text_recorded": False,
    }


def validate_canary_failure(
    result: JsonObject,
    rows: list[JsonObject],
    contract: JsonObject,
) -> JsonObject:
    predecessor = as_object(contract["predecessor"], where="predecessor")
    checks = {
        "status": result.get("status") == predecessor["required_status"],
        "operational_pass": (
            result.get("operational_pass") == predecessor["required_operational_pass"]
        ),
        "scientific_pass": (
            result.get("scientific_pass") == predecessor["required_scientific_pass"]
        ),
        "next_operation": (
            result.get("next_authorized_operation")
            == predecessor["required_next_operation"]
        ),
        "row_count": len(rows) == int(predecessor["required_canary_row_count"]),
    }
    gate_checks = as_object(result["gate_checks"], where="gate_checks")
    failed_gates = sorted(key for key, value in gate_checks.items() if value is not True)
    checks["only_failed_gate"] = failed_gates == [
        str(predecessor["required_only_failed_gate"])
    ]

    mode_counts = Counter(str(row.get("mode")) for row in rows)
    condition_counts = Counter(str(row.get("condition")) for row in rows)
    transformations = Counter(str(row.get("transformation")) for row in rows)
    predictions = {row.get("prediction") for row in rows}
    output_hashes = {str(row.get("raw_output_sha256")) for row in rows}
    safe_rows = [row for row in rows if row.get("condition") == "safe"]
    positive_rows = [row for row in rows if row.get("condition") == "positive"]
    expected_transformations = set(
        as_string_list(
            as_object(
                contract["paired_invariance_requalification"],
                where="requalification",
            )["transformations"],
            where="transformations",
        )
    )
    pattern_checks = {
        "mode_counts": mode_counts
        == {"raw_official_template": 12, "hardened_production_template": 12},
        "condition_counts": condition_counts == {"safe": 12, "positive": 12},
        "transformation_set": set(transformations) == expected_transformations,
        "four_rows_per_transformation": all(
            value == 4 for value in transformations.values()
        ),
        "all_predictions_are_zero": predictions == {0},
        "single_expected_output_hash": output_hashes
        == {str(predecessor["required_uniform_output_sha256"])},
        "raw_output_length_not_recorded": all(
            "raw_output_length" not in row for row in rows
        ),
        "no_abstentions": all(row.get("abstained") is False for row in rows),
        "no_nonce_leaks": all(row.get("canary_leak") is False for row in rows),
        "safe_rows_correct": len(safe_rows) == 12
        and all(
            row.get("expected_prediction") == 0
            and row.get("correct_auto_decision") is True
            for row in safe_rows
        ),
        "positive_rows_uniform_false_negative": len(positive_rows) == 12
        and all(
            row.get("expected_prediction") == 1
            and row.get("prediction") == 0
            and row.get("correct_auto_decision") is False
            for row in positive_rows
        ),
    }
    checks.update(pattern_checks)
    if not all(checks.values()):
        raise ValueError(f"E1C canary predecessor pattern mismatch: {checks}")
    return {
        "failed_gate": failed_gates[0],
        "row_count": len(rows),
        "mode_counts": dict(mode_counts),
        "condition_counts": dict(condition_counts),
        "transformation_counts": dict(sorted(transformations.items())),
        "uniform_prediction": 0,
        "uniform_raw_output_sha256": next(iter(output_hashes)),
        "uniform_raw_output_length_recorded": False,
        "safe_correct_count": len(safe_rows),
        "positive_false_negative_count": len(positive_rows),
        "demonstrated_transformation_specific_flip": False,
        "demonstrated_nonce_leak": False,
        "raw_text_recorded": False,
    }


def validate_official_definition(source_root: Path, contract: JsonObject) -> JsonObject:
    source = as_object(contract["official_definition"], where="official_definition")
    path = source_root / str(source["eval_utils_path"])
    text = path.read_text(encoding="utf-8")
    fragments = as_string_list(source["required_rule_fragments"], where="rule_fragments")
    checks = {
        "tree_sha": git_tree_sha(source_root) == source["tree_sha"],
        "eval_utils_blob": git_blob_sha(path) == source["eval_utils_git_blob_sha"],
        "all_rule_fragments_present": all(fragment in text for fragment in fragments),
    }
    if not all(checks.values()):
        raise ValueError(f"official HarmBench definition mismatch: {checks}")
    return {
        "repository": source["repository"],
        "revision": source["revision"],
        "tree_sha": source["tree_sha"],
        "eval_utils_git_blob_sha": source["eval_utils_git_blob_sha"],
        "required_rule_fragment_count": len(fragments),
        "raw_prompt_or_behavior_text_recorded": False,
    }


def select_stratified_unused(
    records: list[JsonObject],
    registry: dict[str, dict[str, str]],
    excluded_record_ids: set[str],
    *,
    per_stratum: int,
    context_field: str,
) -> list[JsonObject]:
    grouped: dict[tuple[int, str], dict[str, deque[JsonObject]]] = defaultdict(
        lambda: defaultdict(deque)
    )
    for row in records:
        record_id = str(row["record_id"])
        if record_id in excluded_record_ids:
            continue
        behavior_id = str(row["behavior_id_private"])
        registry_row = registry.get(behavior_id)
        if registry_row is None:
            continue
        context_value = registry_row.get(context_field)
        if not isinstance(context_value, str):
            continue
        template_kind = "contextual" if context_value.strip() else "plain"
        label = int(row["label"])
        enriched = dict(row)
        enriched["template_kind"] = template_kind
        grouped[(label, template_kind)][behavior_id].append(enriched)

    selected: list[JsonObject] = []
    for label in (0, 1):
        for template_kind in ("plain", "contextual"):
            queues = grouped[(label, template_kind)]
            for behavior_id, queue in queues.items():
                queues[behavior_id] = deque(
                    sorted(queue, key=lambda item: str(item["record_id"]))
                )
            behavior_order = sorted(
                queues,
                key=lambda value: sha256_bytes(
                    f"e1c-canary-v1:{label}:{template_kind}:{value}".encode()
                ),
            )
            stratum: list[JsonObject] = []
            while len(stratum) < per_stratum:
                made_progress = False
                for behavior_id in behavior_order:
                    queue = queues[behavior_id]
                    if queue and len(stratum) < per_stratum:
                        stratum.append(queue.popleft())
                        made_progress = True
                if not made_progress:
                    raise ValueError(
                        f"insufficient unused rows for {label}/{template_kind}"
                    )
            selected.extend(stratum)
    return selected


def safe_selection_rows(selected: list[JsonObject]) -> list[JsonObject]:
    return [
        {
            "position": index,
            "record_id": row["record_id"],
            "behavior_hash": row["behavior_hash"],
            "label": row["label"],
            "template_kind": row["template_kind"],
            "human_unanimous": row["human_unanimous"],
        }
        for index, row in enumerate(selected)
    ]


def run(
    root: Path,
    source_root: Path,
    config_path: Path,
    safe_output: Path,
    selection_output: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("schema_version") != (
        "evaluator-panel-e1c-canary-requalification-freeze-v1"
    ):
        raise ValueError("unsupported E1C canary freeze contract")
    if contract.get("status") != "FROZEN_BEFORE_E1C_CANARY_REQUALIFICATION_SELECTION":
        raise ValueError("unexpected E1C canary freeze status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("E1C canary freeze is not frozen")
    boundaries = as_object(contract["sealed_boundaries"], where="sealed_boundaries")
    if any(value is not False for value in boundaries.values()):
        raise ValueError("sealed boundary changed")

    helper_identity = validate_local_helpers(root, contract)
    base_live_contract = validate_base_live_contract(root, contract)

    predecessor = as_object(contract["predecessor"], where="predecessor")
    result_path = root / str(predecessor["result_path"])
    canary_path = root / str(predecessor["canary_rows_path"])
    if git_blob_sha(result_path) != predecessor["required_git_blob_sha"]:
        raise ValueError("E1C terminal result identity changed")
    if git_blob_sha(canary_path) != predecessor["required_canary_git_blob_sha"]:
        raise ValueError("E1C canary row identity changed")
    predecessor_result = load_object(result_path)
    canary_rows = load_jsonl(canary_path)
    observed_pattern = validate_canary_failure(predecessor_result, canary_rows, contract)
    official_definition = validate_official_definition(source_root, contract)

    selection_source = as_object(contract["selection_source"], where="selection_source")
    excluded_path = root / str(selection_source["excluded_selection_path"])
    if git_blob_sha(excluded_path) != selection_source["excluded_selection_git_blob_sha"]:
        raise ValueError("prior 200-record selection identity changed")
    excluded_rows = load_jsonl(excluded_path)
    excluded_ids = {str(row["record_id"]) for row in excluded_rows}

    helpers = as_object(contract["local_helpers"], where="local_helpers")
    helper = load_module(
        root / str(helpers["preflight_path"]),
        "e1c_preflight_helper",
    )
    validation = helper.load_object(source_root / str(selection_source["validation_path"]))
    records = helper.flatten_validation(validation)
    text_registry = registry_rows(
        source_root / str(selection_source["text_registry_path"]),
        str(selection_source["id_field"]),
    )
    selection_contract = as_object(
        contract["new_canary_selection"], where="new_canary_selection"
    )
    selected = select_stratified_unused(
        records,
        text_registry,
        excluded_ids,
        per_stratum=int(selection_contract["per_label_template_stratum"]),
        context_field=str(selection_source["context_field"]),
    )
    repeat = select_stratified_unused(
        records,
        text_registry,
        excluded_ids,
        per_stratum=int(selection_contract["per_label_template_stratum"]),
        context_field=str(selection_source["context_field"]),
    )
    safe_rows = safe_selection_rows(selected)
    repeat_rows = safe_selection_rows(repeat)
    selection_payload = jsonl_bytes(safe_rows)
    label_counts = Counter(str(row["label"]) for row in safe_rows)
    template_counts = Counter(str(row["template_kind"]) for row in safe_rows)
    stratum_counts = Counter(
        f"{row['label']}:{row['template_kind']}" for row in safe_rows
    )
    selected_ids = {str(row["record_id"]) for row in safe_rows}
    requalification = as_object(
        contract["paired_invariance_requalification"], where="requalification"
    )
    execution = as_object(contract["live_execution"], where="live_execution")
    shard_counts = Counter(
        int(row["position"]) % int(execution["full_shard_count"])
        for row in safe_rows
    )
    checks = {
        "original_scientific_fail_preserved": (
            as_object(contract["construct_adjudication"], where="adjudication")[
                "preserve_original_scientific_fail"
            ]
            is True
        ),
        "selection_count": len(safe_rows) == int(selection_contract["target_count"]),
        "label_counts": label_counts
        == {
            "0": int(selection_contract["per_label"]),
            "1": int(selection_contract["per_label"]),
        },
        "template_counts": template_counts
        == {
            "plain": int(selection_contract["per_template_kind"]),
            "contextual": int(selection_contract["per_template_kind"]),
        },
        "stratum_counts": all(
            value == int(selection_contract["per_label_template_stratum"])
            for value in stratum_counts.values()
        )
        and set(stratum_counts)
        == {"0:plain", "0:contextual", "1:plain", "1:contextual"},
        "selection_unique": len(selected_ids) == len(safe_rows),
        "selection_disjoint_from_prior_200": selected_ids.isdisjoint(excluded_ids),
        "selection_deterministic": safe_rows == repeat_rows,
        "text_registry_only": all(
            str(row["behavior_hash"]) in {sha256_text(key) for key in text_registry}
            for row in safe_rows
        ),
        "no_cached_classifier_output_used": (
            selection_contract["uses_cached_classifier_outputs"] is False
        ),
        "no_live_classifier_output_used": (
            selection_contract["uses_live_classifier_outputs"] is False
        ),
        "request_budget": int(requalification["expected_total_requests"])
        == len(safe_rows) * int(requalification["requests_per_record"]),
        "shard_cardinality": len(shard_counts)
        == int(execution["full_shard_count"])
        and all(
            value == int(execution["records_per_shard"])
            for value in shard_counts.values()
        ),
        "shard_request_budget": int(execution["requests_per_shard"])
        == int(execution["records_per_shard"])
        * int(requalification["requests_per_record"]),
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_new_attack_outputs": True,
    }
    passed = all(checks.values())
    decision = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-canary-requalification-freeze-result-v1",
        "status": (
            "E1C_CANARY_REQUALIFICATION_FREEZE_PASS"
            if passed
            else "E1C_CANARY_REQUALIFICATION_FREEZE_OPERATIONAL_FAIL"
        ),
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "contract_sha256": sha256_file(config_path),
        "contract_git_blob_sha": git_blob_sha(config_path),
        "base_live_contract": base_live_contract,
        "local_helpers": helper_identity,
        "original_e1c_terminal_status": predecessor_result["status"],
        "original_e1c_scientific_fail_preserved": True,
        "retroactive_pass_claimed": False,
        "construct_adjudication": {
            "classification": as_object(
                contract["construct_adjudication"], where="adjudication"
            )["adjudication"],
            "observed_pattern": observed_pattern,
            "official_definition": official_definition,
            "demonstrated_prompt_injection_failure": False,
            "positive_canary_construct_valid": False,
            "raw_canary_text_recorded": False,
        },
        "new_selection": {
            "record_count": len(safe_rows),
            "label_counts": dict(label_counts),
            "template_counts": dict(template_counts),
            "stratum_counts": dict(sorted(stratum_counts.items())),
            "behavior_count": len({str(row["behavior_hash"]) for row in safe_rows}),
            "human_unanimous_count": sum(
                int(row["human_unanimous"] is True) for row in safe_rows
            ),
            "record_ids_sha256": canonical_sha256(
                [row["record_id"] for row in safe_rows]
            ),
            "safe_rows_sha256": canonical_sha256(safe_rows),
            "selection_file_sha256": sha256_bytes(selection_payload),
            "selection_git_blob_sha": git_blob_sha_bytes(selection_payload),
            "prior_selection_overlap_count": len(selected_ids & excluded_ids),
            "deterministic": safe_rows == repeat_rows,
            "shard_record_counts": {
                str(key): value for key, value in sorted(shard_counts.items())
            },
            "raw_records_recorded": False,
        },
        "paired_invariance_contract": {
            "selected_record_count": requalification["selected_record_count"],
            "transformation_count": len(
                as_string_list(requalification["transformations"], where="transformations")
            ),
            "mode_count": len(as_string_list(requalification["modes"], where="modes")),
            "expected_total_requests": requalification["expected_total_requests"],
            "condition_on_baseline_correct_records": requalification[
                "condition_on_baseline_correct_records"
            ],
            "baseline_correct_min": requalification["baseline_correct_min"],
            "baseline_correct_min_per_label": requalification[
                "baseline_correct_min_per_label"
            ],
            "baseline_correct_min_per_label_template_stratum": requalification[
                "baseline_correct_min_per_label_template_stratum"
            ],
            "transformed_auto_decision_coverage_min": requalification[
                "transformed_auto_decision_coverage_min"
            ],
            "transformed_incorrect_auto_decision_max": requalification[
                "transformed_incorrect_auto_decision_max"
            ],
            "transformation_induced_flip_max": requalification[
                "transformation_induced_flip_max"
            ],
            "nonce_leak_max": requalification["nonce_leak_max"],
        },
        "checks": checks,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": (
            decision["on_freeze_pass"]
            if passed
            else decision["on_freeze_operational_fail"]
        ),
    }
    write_json(safe_output, result)
    write_jsonl(selection_output, safe_rows)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Adjudicate and freeze E1C paired-invariance requalification"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--selection-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    result = run(
        root,
        args.source_root.resolve(),
        args.config if args.config.is_absolute() else root / args.config,
        args.safe_output if args.safe_output.is_absolute() else root / args.safe_output,
        (
            args.selection_output
            if args.selection_output.is_absolute()
            else root / args.selection_output
        ),
    )
    print(json.dumps({"status": result["status"]}, sort_keys=True))
    return 0 if result["operational_pass"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
