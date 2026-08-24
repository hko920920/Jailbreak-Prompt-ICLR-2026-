from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

from run_e0_deepinception_exact_rerender import (
    JsonObject,
    git_blob_sha,
    load_object,
    sha256_file,
    sha256_text,
    string_array,
)
from run_e0_deepinception_exact_rerender_v2 import audit_row_v2
from run_e0_deepinception_static_audit import canonical_payload


Setting = tuple[str, int, int]


def parse_parameters(
    question: str,
    *,
    opening_pattern: str,
    depth_pattern: str,
) -> Setting:
    opening = re.search(opening_pattern, question)
    if opening is None or opening.start() != 0:
        raise ValueError("question does not match the frozen opening pattern")
    depths = list(re.finditer(depth_pattern, question))
    if len(depths) != 1:
        raise ValueError("question must contain exactly one frozen depth pattern")
    scene = opening.group("scene").strip()
    characters = int(opening.group("characters"))
    depth = int(depths[0].group("depth"))
    return scene, characters, depth


def setting_object(setting: Setting) -> JsonObject:
    scene, characters, depth = setting
    return {
        "scene": scene,
        "character_count": characters,
        "layer_depth": depth,
        "setting_sha256": sha256_text(f"{scene}\x1f{characters}\x1f{depth}"),
    }


def expected_registries(config: JsonObject) -> tuple[set[Setting], set[Setting]]:
    parser = cast(JsonObject, config["parameter_parser"])
    balanced = cast(JsonObject, config["balanced_sensitivity_registry"])
    baseline_scene = str(parser["baseline_scene"])
    baseline_characters = int(parser["baseline_character_count"])
    baseline_depth = int(parser["baseline_layer_depth"])
    scenes = string_array(parser["expected_scenes"], where="expected_scenes")

    primary_plus_sensitivity: set[Setting] = {
        (scene, baseline_characters, baseline_depth) for scene in scenes
    }
    character_extremes = cast(JsonObject, balanced["character_extremes"])
    for value in cast(list[int], character_extremes["values"]):
        primary_plus_sensitivity.add(
            (baseline_scene, int(value), baseline_depth)
        )
    layer_extremes = cast(JsonObject, balanced["layer_extremes"])
    for value in cast(list[int], layer_extremes["values"]):
        primary_plus_sensitivity.add(
            (baseline_scene, baseline_characters, int(value))
        )

    midpoint = cast(JsonObject, balanced["midpoint_sensitivity_only"])
    midpoint_settings: set[Setting] = set()
    for value in cast(list[int], midpoint["character_counts"]):
        midpoint_settings.add((baseline_scene, int(value), baseline_depth))
    for value in cast(list[int], midpoint["layer_depths"]):
        midpoint_settings.add((baseline_scene, baseline_characters, int(value)))
    return primary_plus_sensitivity, midpoint_settings


def axis_expected_settings(config: JsonObject, axis: str) -> set[Setting]:
    parser = cast(JsonObject, config["parameter_parser"])
    baseline_scene = str(parser["baseline_scene"])
    baseline_characters = int(parser["baseline_character_count"])
    baseline_depth = int(parser["baseline_layer_depth"])
    if axis == "scene":
        return {
            (scene, baseline_characters, baseline_depth)
            for scene in string_array(
                parser["expected_scenes"], where="expected_scenes"
            )
        }
    if axis == "character_count":
        return {
            (baseline_scene, int(value), baseline_depth)
            for value in cast(list[int], parser["expected_character_counts"])
        }
    if axis == "layer_depth":
        return {
            (baseline_scene, baseline_characters, int(value))
            for value in cast(list[int], parser["expected_layer_depths"])
        }
    raise ValueError(f"unknown axis: {axis}")


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_object(config_path)
    if config["status"] != "FROZEN_BEFORE_DEEPINCEPTION_PARAMETER_BALANCE_EXECUTION":
        raise ValueError("unexpected parameter-balance contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid parameter-balance contract boundary")

    predecessor = cast(JsonObject, config["predecessor"])
    predecessor_path = Path(str(predecessor["result_path"]))
    predecessor_result = load_object(predecessor_path)
    predecessor_pass = all(
        (
            predecessor_result.get("status") == predecessor["required_status"],
            predecessor_result.get("operational_pass")
            is predecessor["required_operational_pass"],
            predecessor_result.get("target_model_called") is False,
            predecessor_result.get("attack_success_scored") is False,
        )
    )
    if not predecessor_pass:
        raise ValueError("DeepInception v2 predecessor gate is not satisfied")

    source = cast(JsonObject, config["source"])
    fields = cast(JsonObject, config["fields"])
    parser = cast(JsonObject, config["parameter_parser"])
    goal_definition = cast(JsonObject, config["goal_definition"])
    slot_extraction = cast(JsonObject, config["slot_extraction"])
    anchors = cast(JsonObject, config["structure_anchors"])
    rules = cast(JsonObject, config["rules"])
    gate = cast(JsonObject, config["decision_gate"])

    license_path = source_root / "LICENSE"
    if git_blob_sha(license_path) != source["license_git_blob_sha"]:
        raise ValueError("DeepInception license blob identity mismatch")

    unit_names = string_array(config["typed_units"], where="typed_units")
    neutralizers = string_array(config["neutralizers"], where="neutralizers")
    synthetic_payload = str(config["synthetic_payload"])
    minimum_goal_length = int(goal_definition["minimum_goal_character_length"])
    minimum_bridge_length = int(slot_extraction["minimum_bridge_character_length"])
    opening_pattern = str(parser["opening_pattern"])
    depth_pattern = str(parser["depth_pattern"])

    file_results: list[JsonObject] = []
    ordered_topic_hashes: list[list[str]] = []
    ordered_goal_hashes: list[list[str]] = []
    all_settings: set[Setting] = set()
    total_questions = 0
    total_subsets = 0
    total_variants = 0
    total_variant_passes = 0
    all_rows: list[JsonObject] = []
    failures: list[JsonObject] = []

    for file_spec_raw in cast(list[JsonObject], source["files"]):
        file_spec = cast(JsonObject, file_spec_raw)
        axis = str(file_spec["axis"])
        data_path = source_root / str(file_spec["path"])
        if not data_path.is_file():
            raise FileNotFoundError(f"missing DeepInception source file: {data_path}")
        if git_blob_sha(data_path) != file_spec["git_blob_sha"]:
            raise ValueError(f"DeepInception source blob mismatch for axis {axis}")
        raw_rows = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(raw_rows, list) or not all(
            isinstance(row, dict) for row in raw_rows
        ):
            raise TypeError(f"DeepInception {axis} data must be an object array")
        rows = cast(list[JsonObject], raw_rows)
        if len(rows) != int(file_spec["expected_row_count"]):
            raise ValueError(f"unexpected row count for axis {axis}")

        axis_topic_hashes: list[str] = []
        axis_goal_hashes: list[str] = []
        axis_settings_by_row: list[set[Setting]] = []
        axis_question_count = 0
        axis_variant_count = 0
        axis_variant_passes = 0
        axis_failures_before = len(failures)

        for row_index, row in enumerate(rows):
            topic_field = str(fields["topic"])
            payload_field = str(fields["plain_payload"])
            questions_field = str(fields["questions"])
            if not isinstance(row.get(topic_field), str):
                raise ValueError(f"missing topic in {axis} row {row_index}")
            if not isinstance(row.get(payload_field), str):
                raise ValueError(f"missing plain payload in {axis} row {row_index}")
            questions = row.get(questions_field)
            if not isinstance(questions, list) or not all(
                isinstance(question, str) for question in questions
            ):
                raise ValueError(f"invalid questions in {axis} row {row_index}")
            if len(questions) != int(file_spec["expected_questions_per_row"]):
                raise ValueError(f"unexpected question count in {axis} row {row_index}")

            topic = str(row[topic_field])
            plain = str(row[payload_field])
            canonical_goal = canonical_payload(plain)
            axis_topic_hashes.append(sha256_text(topic))
            axis_goal_hashes.append(sha256_text(canonical_goal))
            row_settings: set[Setting] = set()
            row_question_records: list[JsonObject] = []

            for question_index, question_raw in enumerate(questions):
                question = str(question_raw)
                try:
                    setting = parse_parameters(
                        question,
                        opening_pattern=opening_pattern,
                        depth_pattern=depth_pattern,
                    )
                    row_settings.add(setting)
                    all_settings.add(setting)
                    question_audit = audit_row_v2(
                        {
                            "topic": topic,
                            "plain_attack": plain,
                            "inception_attack": question,
                        },
                        row_index=question_index,
                        fields={
                            "topic": "topic",
                            "plain_payload": "plain_attack",
                            "rendered_attack": "inception_attack",
                        },
                        anchors=anchors,
                        unit_names=unit_names,
                        neutralizers=neutralizers,
                        synthetic_payload=synthetic_payload,
                        minimum_goal_length=minimum_goal_length,
                        minimum_bridge_length=minimum_bridge_length,
                    )
                    question_record: JsonObject = {
                        "axis": axis,
                        "row_id": f"row_{row_index:04d}",
                        "question_id": f"q_{question_index:02d}",
                        "setting": setting_object(setting),
                        "question_sha256": sha256_text(question),
                        "canonical_goal_sha256": sha256_text(canonical_goal),
                        "bridge_sha256": question_audit["bridge_sha256"],
                        "bridge_character_length": question_audit[
                            "bridge_character_length"
                        ],
                        "source_payload_match_mode": question_audit[
                            "source_payload_match_mode"
                        ],
                        "source_case_change_count": question_audit[
                            "source_case_change_count"
                        ],
                        "nonpayload_preserved": question_audit[
                            "nonpayload_preserved"
                        ],
                        "unit_count": question_audit["unit_count"],
                        "subset_count": question_audit["subset_count"],
                        "variant_count": question_audit["variant_count"],
                        "variant_pass_count": question_audit[
                            "variant_pass_count"
                        ],
                        "operational_pass": question_audit["operational_pass"],
                        "raw_text_recorded": False,
                    }
                    row_question_records.append(question_record)
                    axis_question_count += 1
                    total_questions += 1
                    subset_count = int(question_audit["subset_count"])
                    variant_count = int(question_audit["variant_count"])
                    variant_pass_count = int(question_audit["variant_pass_count"])
                    total_subsets += subset_count
                    total_variants += variant_count
                    total_variant_passes += variant_pass_count
                    axis_variant_count += variant_count
                    axis_variant_passes += variant_pass_count
                except Exception as exc:  # noqa: BLE001 - safe aggregate diagnostic
                    failures.append(
                        {
                            "axis": axis,
                            "row_id": f"row_{row_index:04d}",
                            "question_id": f"q_{question_index:02d}",
                            "error_type": type(exc).__name__,
                            "error_message_sha256": sha256_text(str(exc)),
                        }
                    )

            axis_settings_by_row.append(row_settings)
            all_rows.append(
                {
                    "axis": axis,
                    "row_id": f"row_{row_index:04d}",
                    "topic_sha256": sha256_text(topic),
                    "canonical_goal_sha256": sha256_text(canonical_goal),
                    "settings": [
                        setting_object(setting)
                        for setting in sorted(row_settings)
                    ],
                    "setting_count": len(row_settings),
                    "questions": row_question_records,
                    "raw_text_recorded": False,
                }
            )

        expected_axis_settings = axis_expected_settings(config, axis)
        every_row_axis_complete = all(
            settings == expected_axis_settings for settings in axis_settings_by_row
        )
        ordered_topic_hashes.append(axis_topic_hashes)
        ordered_goal_hashes.append(axis_goal_hashes)
        file_results.append(
            {
                "axis": axis,
                "path": file_spec["path"],
                "git_blob_sha": file_spec["git_blob_sha"],
                "sha256": sha256_file(data_path),
                "row_count": len(rows),
                "question_count": axis_question_count,
                "expected_settings": [
                    setting_object(setting)
                    for setting in sorted(expected_axis_settings)
                ],
                "every_row_axis_complete": every_row_axis_complete,
                "variant_count": axis_variant_count,
                "variant_pass_count": axis_variant_passes,
                "failure_count": len(failures) - axis_failures_before,
            }
        )

    topic_alignment = all(
        hashes == ordered_topic_hashes[0] for hashes in ordered_topic_hashes[1:]
    )
    goal_alignment = all(
        hashes == ordered_goal_hashes[0] for hashes in ordered_goal_hashes[1:]
    )
    primary_plus_sensitivity, midpoint_sensitivity = expected_registries(config)
    expected_all_settings = primary_plus_sensitivity | midpoint_sensitivity
    balanced = cast(JsonObject, config["balanced_sensitivity_registry"])
    registry_match = all_settings == expected_all_settings
    primary_registry_match = len(primary_plus_sensitivity) == int(
        balanced["primary_plus_sensitivity_unique_setting_count"]
    )

    expected_total_questions = int(rules["expected_total_questions"])
    expected_total_subsets = int(rules["expected_total_subset_count"])
    expected_total_variants = int(rules["expected_total_variant_count"])
    operational_pass = all(
        (
            predecessor_pass,
            topic_alignment,
            goal_alignment,
            not failures,
            total_questions == expected_total_questions,
            total_subsets == expected_total_subsets,
            total_variants == expected_total_variants,
            total_variant_passes == expected_total_variants,
            all(file_result["every_row_axis_complete"] is True for file_result in file_results),
            registry_match,
            primary_registry_match,
            len(unit_names) == int(rules["expected_unit_count_per_question"]),
        )
    )
    status = (
        str(gate["on_pass"])
        if operational_pass
        else "E0_DEEPINCEPTION_PARAMETER_BALANCE_FAIL"
    )
    family_representative = cast(JsonObject, config["family_representative"])
    result: JsonObject = {
        "schema_version": "e0-deepinception-parameter-balance-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "predecessor_pass": predecessor_pass,
        "source_revision": source["revision"],
        "config_sha256": sha256_file(config_path),
        "license_sha256": sha256_file(license_path),
        "source_files": file_results,
        "dataset_count": len(file_results),
        "total_source_rows": sum(int(item["row_count"]) for item in file_results),
        "total_questions": total_questions,
        "topic_alignment_across_axes": topic_alignment,
        "canonical_goal_alignment_across_axes": goal_alignment,
        "all_settings": [
            setting_object(setting) for setting in sorted(all_settings)
        ],
        "all_setting_count": len(all_settings),
        "primary_family_representative": {
            "scene": family_representative["scene"],
            "character_count": family_representative["character_count"],
            "layer_depth": family_representative["layer_depth"],
            "setting_sha256": sha256_text(
                f"{family_representative['scene']}\x1f"
                f"{family_representative['character_count']}\x1f"
                f"{family_representative['layer_depth']}"
            ),
            "may_not_be_replaced_after_target_outcomes": True,
        },
        "primary_plus_sensitivity_registry": [
            setting_object(setting)
            for setting in sorted(primary_plus_sensitivity)
        ],
        "primary_plus_sensitivity_setting_count": len(primary_plus_sensitivity),
        "midpoint_sensitivity_registry": [
            setting_object(setting)
            for setting in sorted(midpoint_sensitivity)
        ],
        "midpoint_sensitivity_setting_count": len(midpoint_sensitivity),
        "registry_match": registry_match and primary_registry_match,
        "unit_count_per_question": int(rules["expected_unit_count_per_question"]),
        "subset_count_per_question": int(rules["expected_subset_count_per_question"]),
        "variant_count_per_question": int(rules["expected_variant_count_per_question"]),
        "total_subset_count": total_subsets,
        "total_variant_count": total_variants,
        "total_variant_pass_count": total_variant_passes,
        "failures": failures,
        "rows": all_rows,
        "raw_source_goal_question_derived_or_synthetic_text_committed": False,
        "real_harmful_output_generated": False,
        "target_model_called": False,
        "attack_success_scored": False,
        "cross_regime_stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": (
            gate["on_pass"] if operational_pass else gate["on_fail"]
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit DeepInception source parameters and balanced templates"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_audit(args.config, args.source_root, args.output)
    summary = {
        "status": result["status"],
        "operational_pass": result["operational_pass"],
        "datasets": result["dataset_count"],
        "questions": result["total_questions"],
        "settings": result["all_setting_count"],
        "variants": result["total_variant_count"],
        "variant_passes": result["total_variant_pass_count"],
        "registry_match": result["registry_match"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
