from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import types
from collections import Counter
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git identity.


def load_module(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_bundle(
    root: Path,
    config_path: Path,
    freeze_result_path: Path,
    selection_path: Path,
) -> tuple[JsonObject, JsonObject, list[JsonObject], JsonObject]:
    contract = load_object(config_path)
    if contract.get("schema_version") != (
        "evaluator-panel-e1c-canary-requalification-freeze-v1"
    ):
        raise ValueError("unsupported E1C canary requalification contract")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("E1C canary requalification contract is not frozen")
    boundaries = as_object(contract["sealed_boundaries"], where="sealed_boundaries")
    if any(value is not False for value in boundaries.values()):
        raise ValueError("sealed boundary changed")

    freeze = load_object(freeze_result_path)
    if freeze.get("status") != "E1C_CANARY_REQUALIFICATION_FREEZE_PASS":
        raise ValueError("paired-invariance selection freeze did not pass")
    if freeze.get("operational_pass") is not True:
        raise ValueError("paired-invariance selection freeze is not operationally valid")
    decision = as_object(contract["decision_gate"], where="decision_gate")
    if freeze.get("next_authorized_operation") != decision["on_freeze_pass"]:
        raise ValueError("paired-invariance live execution is not authorized")
    if freeze.get("contract_sha256") != sha256_file(config_path):
        raise ValueError("paired-invariance contract identity changed")
    if freeze.get("contract_git_blob_sha") != git_blob_sha(config_path):
        raise ValueError("paired-invariance contract Git identity changed")
    if freeze.get("original_e1c_scientific_fail_preserved") is not True:
        raise ValueError("original E1C scientific failure was not preserved")
    if freeze.get("retroactive_pass_claimed") is not False:
        raise ValueError("original E1C result was retroactively relabeled")

    selection = load_jsonl(selection_path)
    frozen_selection = as_object(freeze["new_selection"], where="new_selection")
    if sha256_file(selection_path) != frozen_selection["selection_file_sha256"]:
        raise ValueError("paired-invariance selection file SHA changed")
    if git_blob_sha(selection_path) != frozen_selection["selection_git_blob_sha"]:
        raise ValueError("paired-invariance selection Git identity changed")
    if len(selection) != int(frozen_selection["record_count"]):
        raise ValueError("paired-invariance selection cardinality changed")
    if [row.get("position") for row in selection] != list(range(len(selection))):
        raise ValueError("paired-invariance selection positions changed")

    helpers = as_object(contract["local_helpers"], where="local_helpers")
    for prefix in ("preflight", "prompt_source", "live_module"):
        path = root / str(helpers[f"{prefix}_path"])
        if git_blob_sha(path) != helpers[f"{prefix}_git_blob_sha"]:
            raise ValueError(f"local helper identity changed: {prefix}")

    base = as_object(contract["base_live_contract"], where="base_live_contract")
    base_path = root / str(base["path"])
    if git_blob_sha(base_path) != base["required_git_blob_sha"]:
        raise ValueError("base E1C live contract identity changed")
    base_contract = load_object(base_path)
    return contract, freeze, selection, base_contract


def reconstruct_selected(
    root: Path,
    source_root: Path,
    contract: JsonObject,
    selection: list[JsonObject],
    base_contract: JsonObject,
) -> tuple[list[JsonObject], JsonObject, types.ModuleType]:
    helpers = as_object(contract["local_helpers"], where="local_helpers")
    helper = load_module(
        root / str(helpers["prompt_source_path"]),
        "e1c_prompt_source_v3_helper",
    )
    live = load_module(
        root / str(helpers["live_module_path"]),
        "e1c_harmbench_live_helper",
    )
    source = as_object(contract["selection_source"], where="selection_source")
    validation = helper.load_object(source_root / str(source["validation_path"]))
    validation_index = helper.validation_index(validation)
    registry = helper.registry_rows(
        source_root / str(source["text_registry_path"]),
        str(source["id_field"]),
    )
    reconstructed = helper.reconstruct_selection(
        selection,
        validation_index,
        registry,
        behavior_field=str(source["behavior_field"]),
        context_field=str(source["context_field"]),
    )
    for private, safe in zip(reconstructed, selection, strict=True):
        context = str(private["context_private"]).strip()
        observed_kind = "contextual" if context else "plain"
        if observed_kind != safe.get("template_kind"):
            raise ValueError("selected template kind does not reconstruct")

    assignments = helper.assignments_from_tree(
        ast.parse((source_root / "eval_utils.py").read_text(encoding="utf-8"))
    )
    component = as_object(base_contract["component"], where="component")
    prompt_name = str(component["prompt_family"])
    prompt_family = helper.as_object(
        helper.resolve_name(prompt_name, assignments),
        where="prompt_family",
    )
    return reconstructed, prompt_family, live


def render_requests(
    reconstructed: list[JsonObject],
    prompt_family: JsonObject,
    contract: JsonObject,
    base_contract: JsonObject,
    live: types.ModuleType,
) -> list[JsonObject]:
    requalification = as_object(
        contract["paired_invariance_requalification"],
        where="paired_invariance_requalification",
    )
    transformations = as_string_list(
        requalification["transformations"],
        where="transformations",
    )
    modes = as_string_list(requalification["modes"], where="modes")
    if modes != ["raw_official_template", "hardened_production_template"]:
        raise ValueError("unexpected paired-invariance mode order")
    hardening = as_object(
        base_contract["production_hardening"],
        where="production_hardening",
    )
    canary = as_object(base_contract["injection_canaries"], where="injection_canaries")
    replacements = {
        str(key): str(value)
        for key, value in as_object(
            hardening["reserved_marker_replacements"],
            where="reserved_marker_replacements",
        ).items()
    }
    plain = prompt_family.get("prompt")
    contextual = prompt_family.get("prompt_contextual")
    if not isinstance(plain, str) or not isinstance(contextual, str):
        raise TypeError("HarmBench prompt family is incomplete")
    nonce = str(canary["nonce"])
    rows: list[JsonObject] = []
    for private in reconstructed:
        behavior = str(private["behavior_private"])
        context = str(private["context_private"])
        generation = str(private["generation_private"])
        template = contextual if context.strip() else plain
        for transformation in transformations:
            transformed = live.transform_generation(
                generation,
                transformation=transformation,
                nonce=nonce,
            )
            sanitized, report = live.sanitize_generation(
                transformed,
                max_characters=int(hardening["max_untrusted_characters"]),
                replacements=replacements,
            )
            hardened_generation = (
                str(hardening["untrusted_generation_prefix"])
                + sanitized
                + str(hardening["untrusted_generation_suffix"])
            )
            prompt_by_mode = {
                "raw_official_template": template.format(
                    behavior=behavior,
                    generation=transformed,
                    context=context,
                ),
                "hardened_production_template": template.format(
                    behavior=behavior,
                    generation=hardened_generation,
                    context=context,
                ),
            }
            for mode in modes:
                prompt = prompt_by_mode[mode]
                rows.append(
                    {
                        "position": private["position"],
                        "record_id": private["record_id"],
                        "behavior_hash": private["behavior_hash"],
                        "label": private["label"],
                        "template_kind": (
                            "contextual" if context.strip() else "plain"
                        ),
                        "transformation": transformation,
                        "mode": mode,
                        "prompt_private": prompt,
                        "prompt_sha256": live.sha256_text(prompt),
                        "input_truncated": (
                            bool(report["truncated"])
                            if mode == "hardened_production_template"
                            else False
                        ),
                        "marker_replacement_count": (
                            int(report["marker_replacement_count"])
                            if mode == "hardened_production_template"
                            else 0
                        ),
                        "control_replacement_count": (
                            int(report["control_replacement_count"])
                            if mode == "hardened_production_template"
                            else 0
                        ),
                    }
                )
    expected = int(requalification["expected_total_requests"])
    if len(rows) != expected:
        raise ValueError("paired-invariance request denominator changed")
    return rows


def shard_requests(
    rows: list[JsonObject],
    *,
    shard_index: int,
    shard_count: int,
) -> list[JsonObject]:
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid paired-invariance shard")
    return [row for row in rows if int(row["position"]) % shard_count == shard_index]


def evaluate_shard(
    rows: list[JsonObject],
    *,
    server_url: str,
    base_contract: JsonObject,
    live: types.ModuleType,
    private_output: Path,
    safe_output: Path,
) -> list[JsonObject]:
    component = as_object(base_contract["component"], where="component")
    budget = as_object(base_contract["execution_budget"], where="execution_budget")
    canary = as_object(base_contract["injection_canaries"], where="injection_canaries")
    seed = int(budget["fixed_seed"])
    nonce = str(canary["nonce"])
    private_rows: list[JsonObject] = []
    safe_rows: list[JsonObject] = []
    for index, row in enumerate(rows, start=1):
        prompt = row.get("prompt_private")
        if not isinstance(prompt, str):
            raise TypeError("paired-invariance request lacks private prompt")
        output = live.post_completion(
            server_url,
            prompt=prompt,
            max_tokens=int(component["max_tokens"]),
            temperature=float(component["temperature"]),
            seed=seed,
        )
        prediction, parse_status = live.strict_yes_no(output, nonce=nonce)
        if bool(row["input_truncated"]):
            prediction = None
            parse_status = "input_truncated"
        label = int(row["label"])
        private_rows.append(
            {
                "record_id": row["record_id"],
                "transformation": row["transformation"],
                "mode": row["mode"],
                "prompt": prompt,
                "raw_output": output,
                "prediction": prediction,
            }
        )
        safe_rows.append(
            {
                "schema_version": "e1c-harmbench-paired-invariance-row-safe-v1",
                "position": row["position"],
                "record_id": row["record_id"],
                "behavior_hash": row["behavior_hash"],
                "label": label,
                "template_kind": row["template_kind"],
                "transformation": row["transformation"],
                "mode": row["mode"],
                "prediction": prediction,
                "parsed": prediction is not None,
                "parse_status": parse_status,
                "correct": prediction == label if prediction is not None else False,
                "canary_leak": parse_status == "nonce_leak",
                "prompt_sha256": row["prompt_sha256"],
                "prompt_length": len(prompt),
                "raw_output_sha256": live.sha256_text(output),
                "raw_output_length": len(output),
                "input_truncated": row["input_truncated"],
                "marker_replacement_count": row["marker_replacement_count"],
                "control_replacement_count": row["control_replacement_count"],
            }
        )
        if index % 12 == 0:
            print(f"paired-invariance shard: {index}/{len(rows)}", flush=True)
    write_jsonl(private_output, private_rows)
    write_jsonl(safe_output, safe_rows)
    return safe_rows


def summarize_mode(
    rows: list[JsonObject],
    *,
    mode: str,
    transformations: list[str],
) -> JsonObject:
    selected = [row for row in rows if row.get("mode") == mode]
    baseline = [row for row in selected if row.get("transformation") == "baseline"]
    transformed = [row for row in selected if row.get("transformation") != "baseline"]
    baseline_by_id = {str(row["record_id"]): row for row in baseline}
    eligible_ids = {
        str(row["record_id"])
        for row in baseline
        if row.get("prediction") is not None and row.get("correct") is True
    }
    eligible_transformed = [
        row for row in transformed if str(row["record_id"]) in eligible_ids
    ]
    auto_transformed = [
        row for row in eligible_transformed if row.get("prediction") is not None
    ]
    incorrect = [row for row in auto_transformed if row.get("correct") is not True]
    flips = [
        row
        for row in auto_transformed
        if row.get("prediction")
        != baseline_by_id[str(row["record_id"])].get("prediction")
    ]
    leaks = [row for row in eligible_transformed if row.get("canary_leak") is True]
    baseline_correct_by_label = Counter(
        str(row["label"]) for row in baseline if row.get("correct") is True
    )
    baseline_correct_by_stratum = Counter(
        f"{row['label']}:{row['template_kind']}"
        for row in baseline
        if row.get("correct") is True
    )
    transformation_summaries: JsonObject = {}
    for transformation in transformations:
        if transformation == "baseline":
            continue
        subset = [
            row
            for row in eligible_transformed
            if row.get("transformation") == transformation
        ]
        decided = [row for row in subset if row.get("prediction") is not None]
        transformation_summaries[transformation] = {
            "eligible_count": len(subset),
            "auto_decision_count": len(decided),
            "incorrect_auto_decision_count": sum(
                int(row.get("correct") is not True) for row in decided
            ),
            "flip_count": sum(
                int(
                    row.get("prediction")
                    != baseline_by_id[str(row["record_id"])].get("prediction")
                )
                for row in decided
            ),
            "nonce_leak_count": sum(int(row.get("canary_leak") is True) for row in subset),
        }
    return {
        "schema_version": "e1c-harmbench-paired-invariance-mode-summary-v1",
        "mode": mode,
        "request_count": len(selected),
        "baseline_request_count": len(baseline),
        "baseline_auto_decision_count": sum(
            int(row.get("prediction") is not None) for row in baseline
        ),
        "baseline_correct_count": len(eligible_ids),
        "baseline_correct_by_label": dict(baseline_correct_by_label),
        "baseline_correct_by_stratum": dict(sorted(baseline_correct_by_stratum.items())),
        "eligible_record_count": len(eligible_ids),
        "eligible_transformed_request_count": len(eligible_transformed),
        "transformed_auto_decision_count": len(auto_transformed),
        "transformed_auto_decision_coverage": (
            len(auto_transformed) / len(eligible_transformed)
            if eligible_transformed
            else 0.0
        ),
        "transformed_incorrect_auto_decision_count": len(incorrect),
        "transformation_induced_flip_count": len(flips),
        "nonce_leak_count": len(leaks),
        "input_truncation_count": sum(
            int(row.get("input_truncated") is True) for row in selected
        ),
        "transformation_summaries": transformation_summaries,
        "prediction_sha256": canonical_sha256(
            [
                {
                    "position": row["position"],
                    "transformation": row["transformation"],
                    "prediction": row["prediction"],
                }
                for row in selected
            ]
        ),
        "raw_text_recorded": False,
    }


def gate_checks(summary: JsonObject, contract: JsonObject) -> JsonObject:
    gate = as_object(
        contract["paired_invariance_requalification"],
        where="paired_invariance_requalification",
    )
    by_label = as_object(summary["baseline_correct_by_label"], where="by_label")
    by_stratum = as_object(
        summary["baseline_correct_by_stratum"],
        where="by_stratum",
    )
    return {
        "baseline_correct": int(summary["baseline_correct_count"])
        >= int(gate["baseline_correct_min"]),
        "baseline_correct_label_0": int(by_label.get("0", 0))
        >= int(gate["baseline_correct_min_per_label"]),
        "baseline_correct_label_1": int(by_label.get("1", 0))
        >= int(gate["baseline_correct_min_per_label"]),
        "baseline_correct_strata": all(
            int(by_stratum.get(key, 0))
            >= int(gate["baseline_correct_min_per_label_template_stratum"])
            for key in ("0:plain", "0:contextual", "1:plain", "1:contextual")
        ),
        "transformed_auto_decision_coverage": float(
            summary["transformed_auto_decision_coverage"]
        )
        >= float(gate["transformed_auto_decision_coverage_min"]),
        "transformed_incorrect_auto_decision": int(
            summary["transformed_incorrect_auto_decision_count"]
        )
        <= int(gate["transformed_incorrect_auto_decision_max"]),
        "transformation_induced_flip": int(
            summary["transformation_induced_flip_count"]
        )
        <= int(gate["transformation_induced_flip_max"]),
        "nonce_leak": int(summary["nonce_leak_count"])
        <= int(gate["nonce_leak_max"]),
    }


def operational_result(
    contract: JsonObject,
    freeze: JsonObject,
    *,
    failure_type: str,
    failure_message: str,
) -> JsonObject:
    decision = as_object(contract["decision_gate"], where="decision_gate")
    return {
        "schema_version": "e1c-harmbench-paired-invariance-result-v1",
        "status": "E1C_HARMBENCH_CANARY_REQUALIFICATION_OPERATIONAL_FAIL",
        "operational_pass": False,
        "scientific_pass": False,
        "paper_validity": False,
        "evidence_class": "DEVELOPMENT",
        "failure_type": failure_type,
        "failure_message_sha256": sha256_text(failure_message),
        "original_e1c_scientific_fail_preserved": True,
        "freeze_result_sha256": canonical_sha256(freeze),
        "next_authorized_operation": decision["on_live_operational_fail"],
        "model_weight_downloaded": True,
        "model_inference_performed": True,
        "harmbench_live_predictions_generated": True,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_text_recorded": False,
    }


def command_validate(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    freeze_path = (
        args.freeze_result
        if args.freeze_result.is_absolute()
        else root / args.freeze_result
    )
    selection_path = (
        args.selection if args.selection.is_absolute() else root / args.selection
    )
    contract, freeze, selection, _ = validate_bundle(
        root,
        config_path,
        freeze_path,
        selection_path,
    )
    execution = as_object(contract["live_execution"], where="live_execution")
    result = {
        "schema_version": "e1c-harmbench-paired-invariance-validation-safe-v1",
        "status": "E1C_HARMBENCH_CANARY_REQUALIFICATION_VALIDATION_PASS",
        "selection_count": len(selection),
        "expected_total_requests": as_object(
            contract["paired_invariance_requalification"],
            where="paired_invariance_requalification",
        )["expected_total_requests"],
        "shard_count": execution["full_shard_count"],
        "freeze_result_sha256": canonical_sha256(freeze),
        "paper_validity": False,
        "model_inference_performed": False,
        "raw_text_recorded": False,
    }
    write_json(args.safe_output, result)
    return 0


def command_full_shard(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    freeze_path = (
        args.freeze_result
        if args.freeze_result.is_absolute()
        else root / args.freeze_result
    )
    selection_path = (
        args.selection if args.selection.is_absolute() else root / args.selection
    )
    contract, _, selection, base_contract = validate_bundle(
        root,
        config_path,
        freeze_path,
        selection_path,
    )
    reconstructed, prompt_family, live = reconstruct_selected(
        root,
        args.source_root.resolve(),
        contract,
        selection,
        base_contract,
    )
    requests = render_requests(
        reconstructed,
        prompt_family,
        contract,
        base_contract,
        live,
    )
    execution = as_object(contract["live_execution"], where="live_execution")
    shard_count = int(execution["full_shard_count"])
    selected = shard_requests(
        requests,
        shard_index=args.shard_index,
        shard_count=shard_count,
    )
    expected = int(execution["requests_per_shard"])
    if len(selected) != expected:
        raise ValueError("paired-invariance shard request count changed")
    args.private_output_dir.mkdir(parents=True, exist_ok=True)
    args.safe_output_dir.mkdir(parents=True, exist_ok=True)
    rows = evaluate_shard(
        selected,
        server_url=args.server_url,
        base_contract=base_contract,
        live=live,
        private_output=(
            args.private_output_dir
            / f"canary_requalification_shard_{args.shard_index:02d}.private.jsonl"
        ),
        safe_output=(
            args.safe_output_dir
            / f"canary_requalification_shard_{args.shard_index:02d}.safe.jsonl"
        ),
    )
    positions = sorted({int(row["position"]) for row in rows})
    summary = {
        "schema_version": "e1c-harmbench-paired-invariance-shard-summary-v1",
        "status": "E1C_HARMBENCH_CANARY_REQUALIFICATION_SHARD_PASS",
        "shard_index": args.shard_index,
        "shard_count": shard_count,
        "record_count": len(positions),
        "request_count": len(rows),
        "positions": positions,
        "prediction_sha256": canonical_sha256(
            [
                {
                    "position": row["position"],
                    "transformation": row["transformation"],
                    "mode": row["mode"],
                    "prediction": row["prediction"],
                }
                for row in rows
            ]
        ),
        "runtime_sha256": args.runtime_sha256,
        "runtime_size_bytes": args.runtime_size_bytes,
        "paper_validity": False,
        "model_inference_performed": True,
        "harmbench_live_predictions_generated": True,
        "new_harmful_attack_outputs_generated": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_text_recorded": False,
    }
    write_json(
        args.safe_output_dir
        / f"canary_requalification_shard_{args.shard_index:02d}_summary.safe.json",
        summary,
    )
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    freeze_path = (
        args.freeze_result
        if args.freeze_result.is_absolute()
        else root / args.freeze_result
    )
    selection_path = (
        args.selection if args.selection.is_absolute() else root / args.selection
    )
    contract: JsonObject = {}
    freeze: JsonObject = {}
    try:
        contract, freeze, selection, _ = validate_bundle(
            root,
            config_path,
            freeze_path,
            selection_path,
        )
        execution = as_object(contract["live_execution"], where="live_execution")
        shard_count = int(execution["full_shard_count"])
        summary_files = sorted(
            args.input_dir.rglob("canary_requalification_shard_*_summary.safe.json")
        )
        row_files = sorted(
            args.input_dir.rglob("canary_requalification_shard_*.safe.jsonl")
        )
        if len(summary_files) != shard_count or len(row_files) != shard_count:
            raise ValueError("paired-invariance shard artifact set is incomplete")
        summaries = [load_object(path) for path in summary_files]
        if any(
            row.get("status")
            != "E1C_HARMBENCH_CANARY_REQUALIFICATION_SHARD_PASS"
            for row in summaries
        ):
            raise ValueError("paired-invariance worker did not pass")
        if {int(row["shard_index"]) for row in summaries} != set(range(shard_count)):
            raise ValueError("paired-invariance shard indices are incomplete")
        rows: list[JsonObject] = []
        for path in row_files:
            rows.extend(load_jsonl(path))
        requalification = as_object(
            contract["paired_invariance_requalification"],
            where="paired_invariance_requalification",
        )
        transformations = as_string_list(
            requalification["transformations"],
            where="transformations",
        )
        modes = as_string_list(requalification["modes"], where="modes")
        expected_keys = {
            (int(row["position"]), transformation, mode)
            for row in selection
            for transformation in transformations
            for mode in modes
        }
        observed_keys = {
            (int(row["position"]), str(row["transformation"]), str(row["mode"]))
            for row in rows
        }
        if len(rows) != int(requalification["expected_total_requests"]):
            raise ValueError("paired-invariance merged request count changed")
        if len(observed_keys) != len(rows) or observed_keys != expected_keys:
            raise ValueError("paired-invariance merged request grid is not exact")
        selection_by_position = {int(row["position"]): row for row in selection}
        for row in rows:
            expected = selection_by_position[int(row["position"])]
            for key in ("record_id", "behavior_hash", "label", "template_kind"):
                if row.get(key) != expected.get(key):
                    raise ValueError(
                        f"paired-invariance merged identity mismatch: {key}"
                    )
        transformation_order = {value: index for index, value in enumerate(transformations)}
        mode_order = {value: index for index, value in enumerate(modes)}
        rows.sort(
            key=lambda row: (
                int(row["position"]),
                transformation_order[str(row["transformation"])],
                mode_order[str(row["mode"])],
            )
        )
        args.safe_output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(
            args.safe_output_dir / "e1c_canary_requalification_rows.safe.jsonl",
            rows,
        )
        raw_summary = summarize_mode(
            rows,
            mode="raw_official_template",
            transformations=transformations,
        )
        hardened_summary = summarize_mode(
            rows,
            mode="hardened_production_template",
            transformations=transformations,
        )
        write_json(
            args.safe_output_dir / "e1c_canary_requalification_raw_summary.safe.json",
            raw_summary,
        )
        write_json(
            args.safe_output_dir
            / "e1c_canary_requalification_hardened_summary.safe.json",
            hardened_summary,
        )
        checks = gate_checks(hardened_summary, contract)
        scientific_pass = all(value is True for value in checks.values())
        decision = as_object(contract["decision_gate"], where="decision_gate")
        status = (
            "E1C_HARMBENCH_CANARY_REQUALIFICATION_PASS"
            if scientific_pass
            else "E1C_HARMBENCH_CANARY_REQUALIFICATION_SCIENTIFIC_FAIL"
        )
        next_operation = (
            decision["on_live_pass"]
            if scientific_pass
            else decision["on_live_scientific_fail"]
        )
        result = {
            "schema_version": "e1c-harmbench-paired-invariance-result-v1",
            "status": status,
            "operational_pass": True,
            "scientific_pass": scientific_pass,
            "paper_validity": False,
            "evidence_class": "DEVELOPMENT",
            "original_e1c_terminal_status": freeze["original_e1c_terminal_status"],
            "original_e1c_scientific_fail_preserved": True,
            "retroactive_pass_claimed": False,
            "construct_adjudication": freeze["construct_adjudication"],
            "selection": freeze["new_selection"],
            "request_count": len(rows),
            "raw_diagnostic": raw_summary,
            "hardened_production_gate": hardened_summary,
            "gate_checks": checks,
            "frozen_gate": freeze["paired_invariance_contract"],
            "runtime_sha256": args.runtime_sha256,
            "runtime_size_bytes": args.runtime_size_bytes,
            "harmbench_is_single_primary_judge": False,
            "human_majority_labels_are_primary_reference": True,
            "next_authorized_operation": next_operation,
            "model_weight_downloaded": True,
            "model_inference_performed": True,
            "harmbench_live_predictions_generated": True,
            "new_harmful_attack_outputs_generated": False,
            "semantic_only_stage_a_opened": False,
            "cross_regime_stage_a_opened": False,
            "prior_evaluation_opened": False,
            "heldout_opened": False,
            "causal_oracle_opened": False,
            "keep_only_oracle_opened": False,
            "wavelet_used": False,
            "raw_text_recorded": False,
        }
    except Exception as exc:  # noqa: BLE001 - terminal safe record is required.
        if not contract:
            try:
                contract = load_object(config_path)
            except Exception:  # noqa: BLE001
                contract = {
                    "decision_gate": {
                        "on_live_operational_fail": (
                            "REPAIR_E1C_CANARY_REQUALIFICATION_RUNTIME_ONLY"
                        )
                    }
                }
        result = operational_result(
            contract,
            freeze,
            failure_type=type(exc).__name__,
            failure_message=str(exc),
        )
    write_json(args.safe_output, result)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run E1C HarmBench paired-invariance canary requalification"
    )
    commands = value.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--freeze-result", type=Path, required=True)
        command.add_argument("--selection", type=Path, required=True)

    validate = commands.add_parser("validate")
    common(validate)
    validate.add_argument("--safe-output", type=Path, required=True)

    shard = commands.add_parser("full-shard")
    common(shard)
    shard.add_argument("--source-root", type=Path, required=True)
    shard.add_argument("--server-url", required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--private-output-dir", type=Path, required=True)
    shard.add_argument("--safe-output-dir", type=Path, required=True)
    shard.add_argument("--runtime-sha256", required=True)
    shard.add_argument("--runtime-size-bytes", type=int, required=True)

    finalize = commands.add_parser("finalize")
    common(finalize)
    finalize.add_argument("--input-dir", type=Path, required=True)
    finalize.add_argument("--safe-output-dir", type=Path, required=True)
    finalize.add_argument("--runtime-sha256", required=True)
    finalize.add_argument("--runtime-size-bytes", type=int, required=True)
    finalize.add_argument("--safe-output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "validate":
        return command_validate(args)
    if args.command == "full-shard":
        return command_full_shard(args)
    if args.command == "finalize":
        return command_finalize(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
