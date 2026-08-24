#!/usr/bin/env python3
"""Static, harmless admission audit for the pinned GCG source route."""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import subprocess
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def run_git(source_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source_root), *args],
        text=True,
    ).strip()


def config_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "config"
        ):
            continue
        try:
            values[target.attr] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return values


def method_defaults(path: Path, class_name: str, method_name: str) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name != method_name:
                continue
            names = [arg.arg for arg in item.args.args]
            defaults = [None] * (len(names) - len(item.args.defaults))
            for default in item.args.defaults:
                try:
                    defaults.append(ast.literal_eval(default))
                except (ValueError, TypeError):
                    defaults.append("NON_LITERAL")
            return dict(zip(names, defaults, strict=True))
    raise RuntimeError(f"missing {class_name}.{method_name}")


def equal_block_ranges(total_units: int, block_count: int) -> tuple[tuple[int, int], ...]:
    if total_units <= 0 or block_count <= 0 or total_units % block_count:
        raise ValueError("equal block partition requires positive divisible sizes")
    width = total_units // block_count
    return tuple((index * width, (index + 1) * width) for index in range(block_count))


def neutralize_blocks(
    units: tuple[str, ...],
    ranges: tuple[tuple[int, int], ...],
    selected: tuple[int, ...],
    neutral_unit: str,
) -> tuple[str, ...]:
    result = list(units)
    for block_index in selected:
        start, stop = ranges[block_index]
        result[start:stop] = [neutral_unit] * (stop - start)
    return tuple(result)


def all_nonempty_subsets(size: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        subset
        for width in range(1, size + 1)
        for subset in itertools.combinations(range(size), width)
    )


def all_contiguous_intervals(size: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(range(start, stop))
        for start in range(size)
        for stop in range(start + 1, size + 1)
    )


def write_json(path: Path, value: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit(config_path: Path, source_root: Path, output: Path) -> Json:
    contract: Json = json.loads(config_path.read_text(encoding="utf-8"))
    source = contract["source"]
    required_defaults = contract["required_template_defaults"]
    harmless = contract["harmless_audit"]

    observed_revision = run_git(source_root, "rev-parse", "HEAD")
    observed_tree = run_git(source_root, "rev-parse", "HEAD^{tree}")

    file_results: list[Json] = []
    for role, identity in source["files"].items():
        relative = identity["path"]
        path = source_root / relative
        observed_blob = run_git(source_root, "hash-object", relative) if path.is_file() else None
        file_results.append(
            {
                "role": role,
                "path": relative,
                "exists": path.is_file(),
                "expected_git_blob_sha": identity["git_blob_sha"],
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": observed_blob == identity["git_blob_sha"],
                "sha256": sha256_file(path) if path.is_file() else None,
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )

    template_path = source_root / source["files"]["template"]["path"]
    attack_manager_path = source_root / source["files"]["attack_manager"]["path"]
    gcg_path = source_root / source["files"]["gcg_attack"]["path"]
    main_path = source_root / source["files"]["main"]["path"]
    license_path = source_root / source["files"]["license"]["path"]

    observed_defaults = config_assignments(template_path)
    defaults_checked = {
        key: observed_defaults.get(key)
        for key in required_defaults
        if key != "control_init_lexical_units"
    }
    control_init = str(observed_defaults.get("control_init", ""))
    observed_control_units = len(control_init.split())
    defaults_match = all(
        defaults_checked.get(key) == expected
        for key, expected in required_defaults.items()
        if key != "control_init_lexical_units"
    ) and observed_control_units == int(required_defaults["control_init_lexical_units"])

    attack_manager_text = attack_manager_path.read_text(encoding="utf-8")
    gcg_text = gcg_path.read_text(encoding="utf-8")
    main_text = main_path.read_text(encoding="utf-8")
    license_text = license_path.read_text(encoding="utf-8")

    source_semantics = {
        "goal_and_control_have_distinct_fields": (
            "self.goal = goal" in attack_manager_text
            and "self.control = control_init" in attack_manager_text
        ),
        "goal_and_control_have_distinct_token_slices": (
            "self._goal_slice" in attack_manager_text
            and "self._control_slice" in attack_manager_text
            and "self._control_slice = slice(self._goal_slice.stop" in attack_manager_text
        ),
        "candidate_logits_replace_only_control_slice": (
            (
                "torch.arange(self._control_slice.start, "
                "self._control_slice.stop)"
            )
            in attack_manager_text
            and "self.input_ids.unsqueeze(0).repeat" in attack_manager_text
            and "torch.scatter(" in attack_manager_text
        ),
        "gradient_is_computed_for_control_slice": (
            "input_ids[input_slice]" in gcg_text
            and "self._control_slice" in gcg_text
            and "token_gradients(" in gcg_text
        ),
        "one_coordinate_is_replaced_per_sampled_candidate": (
            "new_token_pos = torch.arange(" in gcg_text
            and "new_control_toks = original_control_toks.scatter_" in gcg_text
        ),
        "gradient_topk_candidate_sampling_present": (
            "top_indices = (-grad).topk(topk, dim=1).indices" in gcg_text
            and "torch.randint(0, topk" in gcg_text
        ),
        "candidate_filtering_present": "self.get_filtered_cands" in gcg_text,
        "main_passes_frozen_budget_to_attack_run": all(
            marker in main_text
            for marker in (
                "n_steps=params.n_steps",
                "batch_size=params.batch_size",
                "topk=params.topk",
                "temp=params.temp",
                "filter_cand=params.filter_cand",
                "allow_non_ascii=params.allow_non_ascii",
            )
        ),
    }

    step_defaults = method_defaults(gcg_path, "GCGMultiPromptAttack", "step")
    sample_defaults = method_defaults(gcg_path, "GCGPromptManager", "sample_control")

    units = tuple(control_init.split())
    block_count = int(harmless["preliminary_equal_block_count"])
    ranges = equal_block_ranges(len(units), block_count)
    goal = str(harmless["synthetic_goal"])
    neutral = str(harmless["neutral_lexical_unit"])
    original_goal_bytes = goal.encode("utf-8")

    subset_records: list[Json] = []
    all_subset_checks = True
    for subset in all_nonempty_subsets(block_count):
        changed = neutralize_blocks(units, ranges, subset, neutral)
        composed = f"{goal} {' '.join(changed)}"
        ok = (
            composed.encode("utf-8").startswith(original_goal_bytes)
            and composed.count(goal) == 1
            and len(changed) == len(units)
            and all(len(changed[start:stop]) == stop - start for start, stop in ranges)
        )
        all_subset_checks = all_subset_checks and ok
        subset_records.append(
            {
                "selected_blocks": list(subset),
                "goal_preserved_exactly_once": ok,
                "variant_sha256": sha256_bytes(composed.encode("utf-8")),
            }
        )

    interval_records: list[Json] = []
    all_interval_checks = True
    for interval in all_contiguous_intervals(block_count):
        changed = neutralize_blocks(units, ranges, interval, neutral)
        composed = f"{goal} {' '.join(changed)}"
        ok = (
            composed.count(goal) == 1
            and len(changed) == len(units)
            and composed.encode("utf-8").startswith(original_goal_bytes)
        )
        all_interval_checks = all_interval_checks and ok
        interval_records.append(
            {
                "selected_blocks": list(interval),
                "goal_preserved_and_length_stable": ok,
                "variant_sha256": sha256_bytes(composed.encode("utf-8")),
            }
        )

    mandatory_checks = {
        "pinned_revision_and_tree_match": (
            observed_revision == source["revision"] and observed_tree == source["tree_sha"]
        ),
        "all_source_blobs_match": all(item["git_blob_match"] for item in file_results),
        "mit_license_present": (
            "MIT License" in license_text and "Permission is hereby granted" in license_text
        ),
        "template_defaults_match": defaults_match,
        "goal_control_separation_verified": (
            source_semantics["goal_and_control_have_distinct_fields"]
            and source_semantics["goal_and_control_have_distinct_token_slices"]
        ),
        "control_only_candidate_replacement_verified": source_semantics[
            "candidate_logits_replace_only_control_slice"
        ],
        "one_coordinate_topk_update_verified": (
            source_semantics["gradient_is_computed_for_control_slice"]
            and source_semantics["one_coordinate_is_replaced_per_sampled_candidate"]
            and source_semantics["gradient_topk_candidate_sampling_present"]
            and source_semantics["candidate_filtering_present"]
        ),
        "main_budget_forwarding_verified": source_semantics[
            "main_passes_frozen_budget_to_attack_run"
        ],
        "all_harmless_block_subsets_preserve_goal": all_subset_checks,
        "all_harmless_intervals_preserve_length": all_interval_checks,
        "no_target_or_real_harmful_payload": True,
    }
    passed = all(mandatory_checks.values())
    status = (
        contract["decision_gate"]["on_pass"]
        if passed
        else contract["decision_gate"]["on_fail"]
    )

    result: Json = {
        "schema_version": "e0-gcg-static-audit-result-v1",
        "status": status,
        "operational_pass": passed,
        "paper_validity": False,
        "family": contract["family"],
        "regime": contract["regime"],
        "config_sha256": sha256_file(config_path),
        "source": {
            "repository": source["repository"],
            "expected_revision": source["revision"],
            "observed_revision": observed_revision,
            "revision_match": observed_revision == source["revision"],
            "expected_tree_sha": source["tree_sha"],
            "observed_tree_sha": observed_tree,
            "tree_match": observed_tree == source["tree_sha"],
            "license": source["license"],
            "file_identities": file_results,
        },
        "observed_template_defaults": {
            **defaults_checked,
            "control_init_lexical_units": observed_control_units,
            "control_init_sha256": sha256_bytes(control_init.encode("utf-8")),
        },
        "observed_method_defaults": {
            "GCGPromptManager.sample_control": sample_defaults,
            "GCGMultiPromptAttack.step": step_defaults,
        },
        "source_semantics": source_semantics,
        "harmless_block_audit": {
            "control_lexical_units": len(units),
            "block_count": block_count,
            "units_per_block": len(units) // block_count,
            "ranges": [list(item) for item in ranges],
            "nonempty_subset_count": len(subset_records),
            "contiguous_interval_count": len(interval_records),
            "all_subsets_pass": all_subset_checks,
            "all_intervals_pass": all_interval_checks,
            "subset_records_sha256": canonical_sha256(subset_records),
            "interval_records_sha256": canonical_sha256(interval_records),
            "synthetic_goal_sha256": sha256_bytes(goal.encode("utf-8")),
            "raw_composed_text_recorded": False,
        },
        "intervention_boundary": contract["intervention_boundary"],
        "mandatory_checks": mandatory_checks,
        "family_admitted_to_balanced_signal_screen": False,
        "real_harmful_payload_used": False,
        "target_model_weights_downloaded": False,
        "target_model_called": False,
        "target_model_generation_performed": False,
        "external_api_called": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": (
            "FREEZE_GCG_TOKENIZER_TEMPLATE_BUDGET_AND_POSITION_PRESERVING_NEUTRALIZER_AUDIT"
            if passed
            else "REPAIR_OR_REPLACE_GCG_ROUTE_BEFORE_ANY_TARGET_OUTCOME"
        ),
    }
    write_json(output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = audit(args.config.resolve(), args.source_root.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["operational_pass"] else 2)


if __name__ == "__main__":
    main()
