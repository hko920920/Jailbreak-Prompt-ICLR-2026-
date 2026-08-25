from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

from run_e0_deepinception_static_audit import (
    JsonObject,
    all_nonempty_subsets,
    build_units,
    canonical_payload,
    extract_payload_slot,
    load_object,
    neutralize,
    sha256_file,
    sha256_text,
    string_array,
)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def case_only_equivalent(left: str, right: str) -> bool:
    return all(
        (
            len(left) == len(right),
            len(left.encode("utf-8")) == len(right.encode("utf-8")),
            left.casefold() == right.casefold(),
        )
    )


def case_match_mode(canonical: str, embedded: str) -> str:
    if embedded == canonical:
        return "exact"
    if len(canonical) == len(embedded) and canonical[1:] == embedded[1:]:
        if canonical[:1].casefold() == embedded[:1].casefold():
            return "initial_character_case_only"
    if case_only_equivalent(canonical, embedded):
        return "internal_case_only"
    return "not_admitted"


def audit_row(
    row: JsonObject,
    *,
    row_index: int,
    fields: JsonObject,
    anchors: JsonObject,
    unit_names: list[str],
    neutralizers: list[str],
    synthetic_payload: str,
    minimum_goal_length: int,
) -> JsonObject:
    required = [
        str(fields["topic"]),
        str(fields["plain_payload"]),
        str(fields["rendered_attack"]),
    ]
    if not all(isinstance(row.get(field), str) for field in required):
        raise ValueError("official row is missing a required string field")

    topic = str(row[required[0]])
    plain = str(row[required[1]])
    attack = str(row[required[2]])
    canonical_goal = canonical_payload(plain)
    if len(canonical_goal) < minimum_goal_length:
        raise ValueError("canonical goal is shorter than the frozen minimum")

    embedded, antagonist, proposal_end, final_start = extract_payload_slot(
        attack,
        proposal_prefix=str(anchors["proposal_prefix"]),
        final_prefix=str(anchors["final_layer_prefix"]),
        antagonist_suffixes=string_array(
            anchors["antagonist_suffixes"], where="antagonist_suffixes"
        ),
    )
    mode = case_match_mode(canonical_goal, embedded)
    if mode == "not_admitted":
        raise ValueError("source payload slot differs beyond same-length case changes")

    prefix = attack[:proposal_end]
    suffix = antagonist + attack[final_start:]
    source_nonpayload = prefix + suffix
    derived = prefix + canonical_goal + suffix

    canonical_count = derived.count(canonical_goal)
    canonical_byte_count = derived.encode("utf-8").count(
        canonical_goal.encode("utf-8")
    )
    derived_prefix_preserved = derived[:proposal_end] == prefix
    derived_suffix_start = proposal_end + len(canonical_goal)
    derived_suffix_preserved = derived[derived_suffix_start:] == suffix
    derived_nonpayload = derived[:proposal_end] + derived[derived_suffix_start:]
    nonpayload_preserved = (
        derived_prefix_preserved
        and derived_suffix_preserved
        and source_nonpayload == derived_nonpayload
    )
    if canonical_count != 1 or canonical_byte_count != 1:
        raise ValueError("derived prompt does not contain the canonical goal exactly once")
    if not nonpayload_preserved:
        raise ValueError("derived prompt changed a non-payload source character")

    synthetic = prefix + synthetic_payload + suffix
    if synthetic.count(synthetic_payload) != 1:
        raise ValueError("synthetic payload does not occur exactly once")
    if synthetic.encode("utf-8").count(synthetic_payload.encode("utf-8")) != 1:
        raise ValueError("synthetic payload byte occurrence is not exactly one")

    fragments, partition_pass = build_units(
        synthetic,
        payload=synthetic_payload,
        unit_names=unit_names,
        anchors=anchors,
    )
    unit_ids = [
        str(fragment["owner"])
        for fragment in fragments
        if fragment["kind"] == "attack_unit"
    ]
    subsets = all_nonempty_subsets(unit_ids)
    variants: list[JsonObject] = []
    synthetic_bytes = len(synthetic.encode("utf-8"))
    for subset in subsets:
        selected = set(subset)
        for neutralizer_id in neutralizers:
            output = neutralize(synthetic, fragments, selected, neutralizer_id)
            payload_count = output.count(synthetic_payload)
            payload_byte_count = output.encode("utf-8").count(
                synthetic_payload.encode("utf-8")
            )
            if neutralizer_id == "delete_unit_fragments":
                length_pass = len(output) <= len(synthetic)
                byte_length_pass = len(output.encode("utf-8")) <= synthetic_bytes
            elif neutralizer_id == "layout_preserving_blank":
                length_pass = len(output) == len(synthetic)
                byte_length_pass = len(output.encode("utf-8")) == synthetic_bytes
            else:
                raise ValueError(f"unknown neutralizer: {neutralizer_id}")
            passed = all(
                (
                    payload_count == 1,
                    payload_byte_count == 1,
                    length_pass,
                    byte_length_pass,
                    "\x00" not in output,
                )
            )
            variants.append(
                {
                    "subset_size": len(subset),
                    "subset_sha256": sha256_text("\x1f".join(subset)),
                    "neutralizer": neutralizer_id,
                    "output_sha256": sha256_text(output),
                    "output_character_length": len(output),
                    "output_utf8_byte_length": len(output.encode("utf-8")),
                    "payload_occurrence_count": payload_count,
                    "payload_byte_occurrence_count": payload_byte_count,
                    "character_length_rule_pass": length_pass,
                    "utf8_byte_length_rule_pass": byte_length_pass,
                    "operational_pass": passed,
                }
            )

    case_change_count = sum(
        left != right for left, right in zip(canonical_goal, embedded, strict=True)
    )
    operational_pass = all(
        (
            case_only_equivalent(canonical_goal, embedded),
            canonical_count == 1,
            canonical_byte_count == 1,
            nonpayload_preserved,
            partition_pass,
            all(variant["operational_pass"] is True for variant in variants),
        )
    )
    return {
        "row_id": f"row_{row_index:04d}",
        "topic_sha256": sha256_text(topic),
        "plain_payload_sha256": sha256_text(plain),
        "canonical_goal_sha256": sha256_text(canonical_goal),
        "source_embedded_payload_sha256": sha256_text(embedded),
        "source_attack_sha256": sha256_text(attack),
        "source_nonpayload_sha256": sha256_text(source_nonpayload),
        "derived_prompt_sha256": sha256_text(derived),
        "derived_nonpayload_sha256": sha256_text(derived_nonpayload),
        "synthetic_prompt_sha256": sha256_text(synthetic),
        "source_payload_match_mode": mode,
        "source_case_change_count": case_change_count,
        "source_case_only_equivalent": case_only_equivalent(
            canonical_goal, embedded
        ),
        "canonical_goal_occurrence_count": canonical_count,
        "canonical_goal_byte_occurrence_count": canonical_byte_count,
        "nonpayload_preserved": nonpayload_preserved,
        "antagonist_suffix_sha256": sha256_text(antagonist),
        "unit_count": len(unit_ids),
        "unit_manifest_sha256": sha256_text(
            json.dumps(fragments, sort_keys=True, separators=(",", ":"))
        ),
        "partition_pass": partition_pass,
        "subset_count": len(subsets),
        "variant_count": len(variants),
        "variant_pass_count": sum(
            variant["operational_pass"] is True for variant in variants
        ),
        "variant_manifest_sha256": sha256_text(
            json.dumps(variants, sort_keys=True, separators=(",", ":"))
        ),
        "raw_text_recorded": False,
        "operational_pass": operational_pass,
    }


def run_audit(config_path: Path, source_root: Path, output_path: Path) -> JsonObject:
    config = load_object(config_path)
    if config["status"] != "FROZEN_BEFORE_DEEPINCEPTION_EXACT_RERENDER_EXECUTION":
        raise ValueError("unexpected exact-rerender contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid exact-rerender contract boundary")

    source = cast(JsonObject, config["source"])
    fields = cast(JsonObject, config["fields"])
    anchors = cast(JsonObject, config["structure_anchors"])
    goal_definition = cast(JsonObject, config["goal_definition"])
    rules = cast(JsonObject, config["rules"])
    gate = cast(JsonObject, config["decision_gate"])

    data_path = source_root / str(source["official_data_path"])
    main_path = source_root / str(source["main_code_path"])
    license_path = source_root / "LICENSE"
    for path in (data_path, main_path, license_path):
        if not path.is_file():
            raise FileNotFoundError(f"pinned source file is missing: {path}")

    source_identity_pass = all(
        (
            git_blob_sha(data_path) == source["official_data_git_blob_sha"],
            git_blob_sha(main_path) == source["main_code_git_blob_sha"],
            git_blob_sha(license_path) == source["license_git_blob_sha"],
        )
    )
    if not source_identity_pass:
        raise ValueError("pinned DeepInception blob identity mismatch")

    raw_rows = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(raw_rows, list) or not all(
        isinstance(row, dict) for row in raw_rows
    ):
        raise TypeError("official DeepInception main data must be an object array")
    rows = cast(list[JsonObject], raw_rows)

    unit_names = string_array(config["typed_units"], where="typed_units")
    neutralizers = string_array(config["neutralizers"], where="neutralizers")
    synthetic_payload = str(config["synthetic_payload"])
    audited: list[JsonObject] = []
    failures: list[JsonObject] = []
    for index, row in enumerate(rows):
        try:
            audited.append(
                audit_row(
                    row,
                    row_index=index,
                    fields=fields,
                    anchors=anchors,
                    unit_names=unit_names,
                    neutralizers=neutralizers,
                    synthetic_payload=synthetic_payload,
                    minimum_goal_length=int(
                        goal_definition["minimum_goal_character_length"]
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - safe aggregate diagnostic
            failures.append(
                {
                    "row_id": f"row_{index:04d}",
                    "error_type": type(exc).__name__,
                    "error_message_sha256": sha256_text(str(exc)),
                }
            )

    expected_units = int(rules["expected_unit_count_per_row"])
    expected_subsets = int(rules["expected_subset_count_per_row"])
    expected_variants = int(rules["expected_variant_count_per_row"])
    minimum_rows = int(rules["minimum_official_row_count"])
    budget_match = all(
        row["unit_count"] == expected_units
        and row["subset_count"] == expected_subsets
        and row["variant_count"] == expected_variants
        for row in audited
    )
    operational_pass = all(
        (
            source_identity_pass,
            len(rows) >= minimum_rows,
            len(audited) == len(rows),
            not failures,
            budget_match,
            all(row["operational_pass"] is True for row in audited),
        )
    )
    status = (
        str(gate["on_pass"])
        if operational_pass
        else "E0_DEEPINCEPTION_EXACT_RERENDER_FAIL"
    )
    result: JsonObject = {
        "schema_version": "e0-deepinception-exact-rerender-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "official_artifact_route_remains_failed": True,
        "derived_route_label": "SOURCE_CONFORMANT_EXACT_PAYLOAD_RERENDER",
        "source_revision": source["revision"],
        "source_identity_pass": source_identity_pass,
        "config_sha256": sha256_file(config_path),
        "official_data_sha256": sha256_file(data_path),
        "main_code_sha256": sha256_file(main_path),
        "license_sha256": sha256_file(license_path),
        "synthetic_payload_sha256": sha256_text(synthetic_payload),
        "official_row_count": len(rows),
        "audited_row_count": len(audited),
        "row_pass_count": sum(row["operational_pass"] is True for row in audited),
        "row_failure_count": len(failures),
        "failures": failures,
        "source_payload_match_modes": {
            "exact": sum(row["source_payload_match_mode"] == "exact" for row in audited),
            "initial_character_case_only": sum(
                row["source_payload_match_mode"] == "initial_character_case_only"
                for row in audited
            ),
            "internal_case_only": sum(
                row["source_payload_match_mode"] == "internal_case_only"
                for row in audited
            ),
        },
        "total_source_case_change_count": sum(
            int(row["source_case_change_count"]) for row in audited
        ),
        "unit_count_per_row": expected_units,
        "subset_count_per_row": expected_subsets,
        "variant_count_per_row": expected_variants,
        "total_subset_count": sum(int(row["subset_count"]) for row in audited),
        "total_variant_count": sum(int(row["variant_count"]) for row in audited),
        "total_variant_pass_count": sum(
            int(row["variant_pass_count"]) for row in audited
        ),
        "budget_match": budget_match,
        "rows": audited,
        "raw_source_goal_rendered_derived_or_synthetic_text_committed": False,
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
        description="Audit DeepInception exact-payload source-conformant rerender"
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
        "official_rows": result["official_row_count"],
        "row_passes": result["row_pass_count"],
        "total_variants": result["total_variant_count"],
        "variant_passes": result["total_variant_pass_count"],
        "source_payload_match_modes": result["source_payload_match_modes"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
