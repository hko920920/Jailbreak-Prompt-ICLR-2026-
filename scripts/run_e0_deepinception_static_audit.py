from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]
ASCII_WHITESPACE = " \t\r\n\v\f"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(JsonObject, value)


def string_array(value: object, *, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{where} must be a string array")
    return cast(list[str], value)


def canonical_payload(value: str) -> str:
    canonical = value.strip(ASCII_WHITESPACE)
    if canonical.endswith("."):
        canonical = canonical[:-1]
    return canonical


def lower_initial(value: str) -> str:
    if not value:
        return value
    return value[0].lower() + value[1:]


def layout_preserving_blank(value: str) -> str:
    return "".join(character if character.isspace() else " " for character in value)


def all_nonempty_subsets(values: list[str]) -> list[tuple[str, ...]]:
    return [
        subset
        for size in range(1, len(values) + 1)
        for subset in itertools.combinations(values, size)
    ]


def locate_once(text: str, needle: str, *, start: int = 0, label: str) -> int:
    first = text.find(needle, start)
    if first < 0:
        raise ValueError(f"missing anchor: {label}")
    if text.find(needle, first + len(needle)) >= 0:
        raise ValueError(f"repeated anchor: {label}")
    return first


def extract_payload_slot(
    attack: str,
    *,
    proposal_prefix: str,
    final_prefix: str,
    antagonist_suffixes: list[str],
) -> tuple[str, str, int, int]:
    proposal_start = locate_once(attack, proposal_prefix, label="proposal_prefix")
    proposal_end = proposal_start + len(proposal_prefix)
    final_start = locate_once(
        attack,
        final_prefix,
        start=proposal_end,
        label="final_layer_prefix",
    )
    between = attack[proposal_end:final_start]
    matching_suffixes = [suffix for suffix in antagonist_suffixes if between.endswith(suffix)]
    if len(matching_suffixes) != 1:
        raise ValueError(
            "payload slot must end with exactly one declared antagonist suffix"
        )
    antagonist = matching_suffixes[0]
    embedded_payload = between[: -len(antagonist)]
    return embedded_payload, antagonist, proposal_end, final_start


def build_units(
    synthetic: str,
    *,
    payload: str,
    unit_names: list[str],
    anchors: JsonObject,
) -> tuple[list[JsonObject], bool]:
    layer_rule = str(anchors["layer_rule"])
    depth_prefix = str(anchors["depth_prefix"])
    proposal_prefix = str(anchors["proposal_prefix"])
    final_prefix = str(anchors["final_layer_prefix"])
    summary_prefix = str(anchors["summary_prefix"])

    layer_start = locate_once(synthetic, layer_rule, label="layer_rule")
    depth_start = locate_once(
        synthetic,
        depth_prefix,
        start=layer_start + len(layer_rule),
        label="depth_prefix",
    )
    proposal_start = locate_once(
        synthetic,
        proposal_prefix,
        start=depth_start + len(depth_prefix),
        label="proposal_prefix",
    )
    payload_start = locate_once(
        synthetic,
        payload,
        start=proposal_start + len(proposal_prefix),
        label="synthetic_payload",
    )
    payload_end = payload_start + len(payload)
    final_start = locate_once(
        synthetic,
        final_prefix,
        start=payload_end,
        label="final_layer_prefix",
    )
    summary_start = locate_once(
        synthetic,
        summary_prefix,
        start=final_start + len(final_prefix),
        label="summary_prefix",
    )

    boundaries = [
        (0, layer_start),
        (layer_start, depth_start),
        (depth_start, proposal_start),
        (proposal_start, payload_start),
        (payload_end, final_start),
        (final_start, summary_start),
        (summary_start, len(synthetic)),
    ]
    if len(unit_names) != len(boundaries):
        raise ValueError("unit-name count differs from parsed boundary count")

    fragments: list[JsonObject] = []
    for index, (unit, boundary) in enumerate(zip(unit_names, boundaries, strict=True)):
        start, end = boundary
        if end <= start:
            raise ValueError(f"empty or reversed unit: {unit}")
        text = synthetic[start:end]
        fragments.append(
            {
                "id": f"u{index + 1:02d}_{unit}",
                "owner": unit,
                "kind": "attack_unit",
                "start_character": start,
                "end_character": end,
                "character_length": end - start,
                "utf8_byte_length": len(text.encode("utf-8")),
                "sha256": sha256_text(text),
                "raw_text_recorded": False,
            }
        )

    fragments.append(
        {
            "id": "payload",
            "owner": "__payload__",
            "kind": "immutable_payload",
            "start_character": payload_start,
            "end_character": payload_end,
            "character_length": len(payload),
            "utf8_byte_length": len(payload.encode("utf-8")),
            "sha256": sha256_text(payload),
            "raw_text_recorded": False,
        }
    )
    ordered = sorted(fragments, key=lambda row: int(row["start_character"]))
    cursor = 0
    reconstructed: list[str] = []
    for fragment in ordered:
        start = int(fragment["start_character"])
        end = int(fragment["end_character"])
        if start != cursor:
            raise ValueError("typed fragments do not form a contiguous partition")
        reconstructed.append(synthetic[start:end])
        cursor = end
    partition_pass = cursor == len(synthetic) and "".join(reconstructed) == synthetic
    return ordered, partition_pass


def neutralize(
    synthetic: str,
    fragments: list[JsonObject],
    selected_units: set[str],
    neutralizer: str,
) -> str:
    pieces: list[str] = []
    for fragment in fragments:
        start = int(fragment["start_character"])
        end = int(fragment["end_character"])
        text = synthetic[start:end]
        owner = str(fragment["owner"])
        if owner not in selected_units:
            pieces.append(text)
        elif neutralizer == "delete_unit_fragments":
            pieces.append("")
        elif neutralizer == "layout_preserving_blank":
            pieces.append(layout_preserving_blank(text))
        else:
            raise ValueError(f"unknown neutralizer: {neutralizer}")
    return "".join(pieces)


def audit_row(
    row: JsonObject,
    *,
    row_index: int,
    fields: JsonObject,
    anchors: JsonObject,
    unit_names: list[str],
    neutralizers: list[str],
    synthetic_payload: str,
    minimum_payload_length: int,
) -> JsonObject:
    required = [str(fields["topic"]), str(fields["plain_payload"]), str(fields["rendered_attack"])]
    if not all(isinstance(row.get(field), str) for field in required):
        raise ValueError("official row is missing a required string field")

    topic = str(row[required[0]])
    plain = str(row[required[1]])
    attack = str(row[required[2]])
    canonical = canonical_payload(plain)
    if len(canonical) < minimum_payload_length:
        raise ValueError("canonical payload is shorter than the frozen minimum")

    embedded, antagonist, proposal_end, final_start = extract_payload_slot(
        attack,
        proposal_prefix=str(anchors["proposal_prefix"]),
        final_prefix=str(anchors["final_layer_prefix"]),
        antagonist_suffixes=string_array(
            anchors["antagonist_suffixes"], where="antagonist_suffixes"
        ),
    )
    if embedded == canonical:
        match_mode = "exact_canonical"
    elif embedded == lower_initial(canonical):
        match_mode = "initial_character_lowercased"
    else:
        raise ValueError("official payload slot differs beyond declared normalization")

    synthetic = attack[:proposal_end] + synthetic_payload + antagonist + attack[final_start:]
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
    for subset in subsets:
        selected = set(subset)
        for neutralizer_id in neutralizers:
            output = neutralize(synthetic, fragments, selected, neutralizer_id)
            payload_count = output.count(synthetic_payload)
            payload_byte_count = output.encode("utf-8").count(
                synthetic_payload.encode("utf-8")
            )
            length_pass = (
                len(output) <= len(synthetic)
                if neutralizer_id == "delete_unit_fragments"
                else len(output) == len(synthetic)
            )
            passed = all(
                (
                    payload_count == 1,
                    payload_byte_count == 1,
                    length_pass,
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
                    "payload_occurrence_count": payload_count,
                    "payload_byte_occurrence_count": payload_byte_count,
                    "length_rule_pass": length_pass,
                    "operational_pass": passed,
                }
            )

    operational_pass = partition_pass and all(
        variant["operational_pass"] is True for variant in variants
    )
    return {
        "row_id": f"row_{row_index:04d}",
        "topic_sha256": sha256_text(topic),
        "plain_payload_sha256": sha256_text(plain),
        "canonical_payload_sha256": sha256_text(canonical),
        "embedded_payload_sha256": sha256_text(embedded),
        "source_attack_sha256": sha256_text(attack),
        "synthetic_prompt_sha256": sha256_text(synthetic),
        "synthetic_prompt_character_length": len(synthetic),
        "payload_match_mode": match_mode,
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
    if config["status"] != "FROZEN_BEFORE_DEEPINCEPTION_STATIC_EXECUTION":
        raise ValueError("unexpected DeepInception contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid DeepInception contract boundary")

    source = cast(JsonObject, config["source"])
    fields = cast(JsonObject, config["fields"])
    anchors = cast(JsonObject, config["structure_anchors"])
    rules = cast(JsonObject, config["rules"])
    canonicalization = cast(JsonObject, config["payload_canonicalization"])
    data_path = source_root / str(source["official_data_path"])
    main_path = source_root / str(source["main_code_path"])
    license_path = source_root / "LICENSE"
    raw_rows = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(raw_rows, list) or not all(isinstance(row, dict) for row in raw_rows):
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
                    minimum_payload_length=int(
                        canonicalization["minimum_payload_character_length"]
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - aggregate safe E0 diagnostics
            failures.append(
                {
                    "row_id": f"row_{index:04d}",
                    "error_type": type(exc).__name__,
                    "error_message_sha256": sha256_text(str(exc)),
                }
            )

    minimum_rows = int(rules["minimum_official_row_count"])
    expected_units = int(rules["expected_unit_count_per_row"])
    expected_subsets = int(rules["expected_subset_count_per_row"])
    expected_variants = int(rules["expected_variant_count_per_row"])
    budget_match = all(
        row["unit_count"] == expected_units
        and row["subset_count"] == expected_subsets
        and row["variant_count"] == expected_variants
        for row in audited
    )
    operational_pass = all(
        (
            len(rows) >= minimum_rows,
            len(audited) == len(rows),
            not failures,
            budget_match,
            all(row["operational_pass"] is True for row in audited),
        )
    )

    gate = cast(JsonObject, config["decision_gate"])
    status = (
        "E0_DEEPINCEPTION_STATIC_ADAPTER_PASS_"
        "ADVANCE_TO_PARAMETER_AND_BALANCED_TEMPLATE_AUDIT"
        if operational_pass
        else "E0_DEEPINCEPTION_STATIC_ADAPTER_FAIL"
    )
    result: JsonObject = {
        "schema_version": "e0-deepinception-static-audit-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "source_revision": source["revision"],
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
        "payload_match_modes": {
            "exact_canonical": sum(
                row["payload_match_mode"] == "exact_canonical" for row in audited
            ),
            "initial_character_lowercased": sum(
                row["payload_match_mode"] == "initial_character_lowercased"
                for row in audited
            ),
        },
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
        "raw_source_or_rendered_text_committed": False,
        "real_harmful_output_generated": False,
        "target_model_called": False,
        "attack_success_scored": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": gate["on_pass"] if operational_pass else gate["on_fail"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepInception E0 static audit")
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
        "payload_match_modes": result["payload_match_modes"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
