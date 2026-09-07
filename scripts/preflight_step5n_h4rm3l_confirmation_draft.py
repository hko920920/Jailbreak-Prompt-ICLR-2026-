"""Audit the nonfrozen Step 5N confirmation draft without opening scientific output.

This program intentionally has no model, evaluator, download, or freeze command.  It
only validates a draft and writes a safe metadata receipt.  A later author decision
must materialize a new, frozen contract version; this draft is never promoted in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

DRAFT_STATUS = "DRAFT_AWAITING_EXPLICIT_AUTHOR_NARROW_AND_TARGET_PAIR_DECISION"
PASS_STATUS = "STEP5N_DRAFT_PREFLIGHT_PASS_NO_AUTHORITY"
FAIL_STATUS = "STEP5N_DRAFT_PREFLIGHT_FAIL_NO_AUTHORITY"


class DraftBoundaryError(ValueError):
    """Raised before output when the file is no longer an unauthorized draft."""


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    audit = commands.add_parser(
        "audit-draft",
        help="read-only validation; performs no download, inference, freeze, or result opening",
    )
    audit.add_argument("--root", type=Path, default=Path.cwd())
    audit.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "step5n_h4rm3l_confirmation_draft_v1.json"
        ),
    )
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[JsonObject]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return rows


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def relative_display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validated_existing_result(path: Path, *, config_sha256: str) -> JsonObject | None:
    if not path.exists():
        return None
    existing = load_object(path)
    identity = existing.get("result_identity_sha256")
    body = dict(existing)
    body.pop("result_identity_sha256", None)
    if (
        existing.get("schema_version")
        != "jbspan-step5n-h4rm3l-confirmation-draft-preflight-v1"
        or existing.get("config_sha256") != config_sha256
        or not isinstance(identity, str)
        or canonical_sha256(body) != identity
    ):
        raise RuntimeError("existing Step 5N draft preflight identity is invalid")
    return existing


def require_unauthorized_draft(config: Mapping[str, Any]) -> None:
    authorization = config.get("authorization_boundary")
    if not isinstance(authorization, dict):
        raise DraftBoundaryError("authorization_boundary must be an object")
    checks = {
        "status_is_draft": config.get("status") == DRAFT_STATUS,
        "frozen_is_false": config.get("frozen") is False,
        "author_narrow_is_false": authorization.get("author_narrow_decision_recorded")
        is False,
        "target_pair_selected_is_false": authorization.get("target_pair_selected") is False,
        "selected_targets_empty": authorization.get("selected_target_ids") == [],
        "contract_frozen_is_false": authorization.get("contract_frozen") is False,
        "download_forbidden": authorization.get("may_download_or_modify_model_artifacts")
        is False,
        "admission_forbidden": authorization.get("may_run_harmless_target_admission") is False,
        "target_inference_forbidden": authorization.get(
            "may_generate_confirmatory_target_outputs"
        )
        is False,
        "evaluator_inference_forbidden": authorization.get(
            "may_call_confirmatory_evaluators"
        )
        is False,
        "attack_outcome_forbidden": authorization.get(
            "may_observe_confirmatory_attack_success"
        )
        is False,
        "topology_outcome_forbidden": authorization.get(
            "may_observe_confirmatory_topology"
        )
        is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise DraftBoundaryError(
            "refusing draft audit because authorization boundary changed: "
            + ", ".join(failed)
        )


def audit_dependency(root: Path, specification: Mapping[str, Any]) -> JsonObject:
    path = resolve(root, str(specification["path"]))
    exists = path.is_file()
    observed_sha256 = file_sha256(path) if exists else None
    return {
        "path": relative_display(root, path),
        "exists": exists,
        "expected_sha256": specification["sha256"],
        "observed_sha256": observed_sha256,
        "sha256_matches": observed_sha256 == specification["sha256"],
    }


def semantic_dependency_checks(
    config: Mapping[str, Any], loaded: Mapping[str, Mapping[str, Any]]
) -> JsonObject:
    specifications = config["dependencies"]
    checks: JsonObject = {}
    for name, specification in specifications.items():
        required_status = specification.get("required_status")
        required_identity = specification.get("required_identity")
        if required_status is not None:
            checks[f"{name}_status_matches"] = (
                loaded[name].get("status") == required_status
            )
        if required_identity is not None:
            checks[f"{name}_identity_matches"] = (
                loaded[name].get("result_identity_sha256") == required_identity
            )

    d3_result = loaded["d3_official_result"]
    d3_verification = loaded["d3_independent_verification"]
    narrow = loaded["d3_postoutcome_narrow_audit"]
    split = loaded["guidedbench_split_audit"]
    e0g5 = loaded["e0g5_panel_result"]
    e0g5_verification = loaded["e0g5_independent_verification"]
    p2 = loaded["p2_runtime_result"]
    readiness = loaded["step5n_static_readiness"]

    checks.update(
        {
            "official_cross_family_d3_remains_failed": d3_result.get(
                "d3_core_gate_pass"
            )
            is specifications["d3_official_result"]["required_d3_core_gate_pass"],
            "d3_verification_binds_official_identity": d3_verification.get(
                "result_identity_sha256"
            )
            == d3_result.get("result_identity_sha256"),
            "postoutcome_route_is_narrow": narrow.get("project_route_decision", {}).get(
                "classification"
            )
            == specifications["d3_postoutcome_narrow_audit"]["required_project_route"],
            "narrow_audit_did_no_new_inference": narrow.get("new_target_inference") is False
            and narrow.get("new_evaluator_inference") is False,
            "development_confirmation_overlap_absent": split.get(
                "development_confirmation_overlap"
            )
            is False,
            "split_called_no_target_or_evaluator": split.get("target_model_called") is False
            and split.get("evaluator_called") is False,
            "e0g5_primary_panel_qualified": e0g5.get(
                "primary_panel_qualified_for_topology_candidate"
            )
            is True,
            "e0g5_verification_binds_result": e0g5_verification.get(
                "result_identity_sha256"
            )
            == e0g5.get("result_identity_sha256"),
            "p2_operational_pass": p2.get("operational_pass") is True,
            "p2_used_harmless_prompts_only": p2.get("harmless_prompts_only") is True,
            "readiness_static_pass": readiness.get("static_readiness_pass") is True,
            "readiness_opened_no_confirmation": readiness.get(
                "confirmatory_output_opened"
            )
            is False,
            "readiness_granted_no_authority": readiness.get(
                "scientific_confirmation_authorized"
            )
            is False,
            "readiness_contract_not_frozen": readiness.get("confirmatory_contract_frozen")
            is False,
        }
    )
    return checks


def audit_reservation(
    confirmation_rows: Sequence[Mapping[str, Any]],
    development_rows: Sequence[Mapping[str, Any]],
    population: Mapping[str, Any],
) -> JsonObject:
    topics = Counter(str(row["topic_id"]) for row in confirmation_rows)
    payloads = [str(row["payload_sha256"]) for row in confirmation_rows]
    development_payloads = {str(row["payload_sha256"]) for row in development_rows}
    raw_absent = all(row.get("raw_content_recorded") is False for row in confirmation_rows)
    checks = {
        "row_count_matches": len(confirmation_rows) == population["reservation_rows"],
        "topic_count_matches": len(topics) == population["topic_count"],
        "rows_per_topic_match": set(topics.values()) == {population["rows_per_topic"]},
        "payloads_unique": len(payloads) == len(set(payloads)),
        "development_overlap_absent": not (set(payloads) & development_payloads),
        "safe_manifest_contains_no_raw_content": raw_absent,
    }
    return {
        "rows": len(confirmation_rows),
        "topics": len(topics),
        "unique_payloads": len(set(payloads)),
        "development_overlap_count": len(set(payloads) & development_payloads),
        "checks": checks,
        "passed": all(checks.values()),
    }


def expected_from_t0(t0: Mapping[str, Any]) -> JsonObject:
    h4 = t0["intervention_contract"]["unitization"]["h4rm3l"]
    neutralizers = [item["id"] for item in t0["intervention_contract"]["neutralizers"]]
    tasks = t0["capability_controls"]["tasks"]
    panel = t0["qualified_panel"]
    confirmation_gate = t0["stage_gates"]["confirmatory_population"]
    return {
        "unit_order": h4["unit_order"],
        "unit_count": h4["expected_unit_count"],
        "subsets_including_empty": h4["expected_subsets_including_empty"],
        "neutralizers": neutralizers,
        "primary_seeds": t0["seed_contract"]["primary_topology_seeds"],
        "replication_seeds": t0["seed_contract"]["fresh_replication_seed_derivation"][
            "seeds"
        ],
        "controls": [
            {
                "id": item["id"],
                "source_prompt_id": item["source_prompt_id"],
                "required_normalized_substring": item["required_normalized_substring"],
            }
            for item in tasks
        ],
        "control_generation": {
            key: t0["capability_controls"]["generation"][key]
            for key in ("seed", "temperature", "top_k", "top_p", "maximum_new_tokens")
        },
        "panel_axes": panel["axes"],
        "panel_input_mapping": panel["input_mapping"],
        "qwen_harmful": panel["fixed_rule"]["qwen_harmful"],
        "qwen_safe": panel["fixed_rule"]["qwen_safe"],
        "panel_harmful": panel["fixed_rule"]["panel_harmful"],
        "panel_safe": panel["fixed_rule"]["panel_safe"],
        "panel_abstain": panel["fixed_rule"]["panel_abstain"],
        "reportable_min": confirmation_gate["reportable_instances_min"],
        "unique_payloads_min": confirmation_gate["unique_payloads_min"],
        "target_instances": confirmation_gate["target_instances"],
        "target_unique_payloads": confirmation_gate["target_unique_payloads"],
        "nontrivial_min": confirmation_gate["nontrivial_instances_min"],
        "nontrivial_cells_min": confirmation_gate[
            "nontrivial_attack_model_cells_min"
        ],
        "nontrivial_payloads_min": confirmation_gate[
            "nontrivial_unique_payloads_min"
        ],
        "replication_min": confirmation_gate[
            "fresh_seed_minimal_edge_replication_rate_min"
        ],
        "jaccard_min": confirmation_gate[
            "positive_decision_neutralizer_jaccard_min"
        ],
        "confound_abstain_max": confirmation_gate[
            "capability_confounded_plus_abstained_fraction_max_exclusive"
        ],
        "recall_gap_min": confirmation_gate[
            "best_singleton_or_one_path_minimal_family_recall_gap_min"
        ],
    }


def validate_t0_constants(config: Mapping[str, Any], t0: Mapping[str, Any]) -> JsonObject:
    expected = expected_from_t0(t0)
    intervention = config["intervention_contract"]
    controls = config["capability_control_contract"]
    panel = config["panel_contract"]
    c1_gate = config["c1n_fresh_stable_pair_screen"]["gate"]
    c2_gate = config["c2n_exact_confirmatory_topology"]["gate"]
    c3 = config["c3n_fresh_seed_edge_replication"]
    exact_t0 = t0["exact_topology_contract"]
    checks = {
        "unit_order_matches_t0": intervention["unit_order"] == expected["unit_order"],
        "unit_count_matches_t0": intervention["unit_count"] == expected["unit_count"],
        "subset_count_matches_t0": intervention["subsets_including_empty"]
        == expected["subsets_including_empty"],
        "neutralizers_match_t0": intervention["neutralizers"]
        == expected["neutralizers"],
        "primary_seeds_match_t0": intervention["primary_seeds"]
        == expected["primary_seeds"],
        "replication_seeds_match_t0": c3["replication_seeds"]
        == expected["replication_seeds"],
        "controls_match_t0": controls["tasks"] == expected["controls"],
        "control_generation_matches_t0": controls["generation"]
        == expected["control_generation"],
        "panel_axes_match_t0": panel["axes"] == expected["panel_axes"],
        "panel_input_mapping_matches_t0": panel["input_mapping"]
        == expected["panel_input_mapping"],
        "panel_rules_match_t0": all(
            panel[name] == expected[name]
            for name in (
                "qwen_harmful",
                "qwen_safe",
                "panel_harmful",
                "panel_safe",
                "panel_abstain",
            )
        ),
        "exact_enumeration_matches_t0": intervention[
            "enumerate_all_subsets_including_empty"
        ]
        == exact_t0["enumerate_all_subsets_including_empty"],
        "no_monotonicity_matches_t0": intervention["monotonicity_assumption_allowed"]
        == exact_t0["monotonicity_assumption_allowed"],
        "no_immediate_only_matches_t0": intervention[
            "immediate_subset_only_minimality_allowed"
        ]
        == exact_t0["immediate_subset_only_minimality_allowed"],
        "minimality_definition_matches_t0": intervention["minimal_recovery_set"]
        == exact_t0["minimal_recovery_set"],
        "unresolved_invalidates_matches_t0": intervention[
            "unresolved_strict_subset_invalidates_minimality_certificate"
        ]
        == exact_t0["unresolved_strict_subset_invalidates_minimality_certificate"],
        "empty_baseline_rule_matches_t0": intervention[
            "attacked_empty_intervention_must_be_not_recovered"
        ]
        == exact_t0["attacked_empty_intervention_must_be_not_recovered"],
        "c1_population_min_matches_t0": c1_gate["eligible_stable_pairs_min"]
        == expected["reportable_min"],
        "c1_unique_min_matches_t0": c1_gate["unique_payloads_min"]
        == expected["unique_payloads_min"],
        "c1_targets_match_t0": c1_gate["target_eligible_stable_pairs"]
        == expected["target_instances"]
        and c1_gate["target_unique_payloads"] == expected["target_unique_payloads"],
        "c2_population_min_matches_t0": c2_gate["reportable_instances_min"]
        == expected["reportable_min"],
        "c2_unique_min_matches_t0": c2_gate["unique_payloads_min"]
        == expected["unique_payloads_min"],
        "c2_targets_match_t0": c2_gate["target_reportable_instances"]
        == expected["target_instances"]
        and c2_gate["target_unique_payloads"] == expected["target_unique_payloads"],
        "c2_nontrivial_gates_match_t0": c2_gate["nontrivial_instances_min"]
        == expected["nontrivial_min"]
        and c2_gate["nontrivial_target_model_cells_min"]
        == expected["nontrivial_cells_min"]
        and c2_gate["nontrivial_unique_payloads_min"]
        == expected["nontrivial_payloads_min"],
        "c2_validity_gates_match_t0": c2_gate[
            "positive_decision_neutralizer_jaccard_min"
        ]
        == expected["jaccard_min"]
        and c2_gate["capability_confounded_plus_abstained_fraction_max_exclusive"]
        == expected["confound_abstain_max"]
        and c2_gate["best_singleton_or_one_path_minimal_family_recall_gap_min"]
        == expected["recall_gap_min"],
        "c3_gates_match_t0": c3["fresh_seed_minimal_edge_replication_rate_min"]
        == expected["replication_min"]
        and c3["positive_decision_neutralizer_jaccard_min"]
        == expected["jaccard_min"]
        and c3["capability_confounded_plus_abstained_fraction_max_exclusive"]
        == expected["confound_abstain_max"]
        and c3["best_singleton_or_one_path_minimal_family_recall_gap_min"]
        == expected["recall_gap_min"],
    }
    return checks


def validate_call_budgets(config: Mapping[str, Any]) -> JsonObject:
    population = config["population_contract"]
    intervention = config["intervention_contract"]
    controls = config["capability_control_contract"]
    c1 = config["c1n_fresh_stable_pair_screen"]
    c2 = config["c2n_exact_confirmatory_topology"]
    nonempty = 2 ** int(intervention["unit_count"]) - 1
    c1_expected = (
        int(population["reservation_rows"])
        * len(config["target_pair_strategy_draft"]["preferred_pair"])
        * len(c1["conditions"])
        * len(intervention["primary_seeds"])
    )
    lattice_expected = (
        nonempty
        * len(intervention["neutralizers"])
        * len(intervention["primary_seeds"])
    )
    controls_expected = (
        nonempty * len(controls["neutralizers"]) * len(controls["tasks"])
    )
    checks = {
        "c1_maximum_is_540": c1_expected == 540
        and c1["maximum_target_calls"] == c1_expected,
        "c2_nonempty_subsets_is_7": nonempty == 7
        and c2["nonempty_subsets_per_instance"] == nonempty,
        "c2_lattice_maximum_is_42": lattice_expected == 42
        and c2["maximum_new_lattice_target_calls_per_instance"] == lattice_expected,
        "c2_control_maximum_is_28": controls_expected == 28
        and c2["maximum_additional_capability_control_calls_per_instance"]
        == controls_expected,
        "c2_total_maximum_is_70": c2["maximum_total_new_target_calls_per_instance"]
        == lattice_expected + controls_expected
        == 70,
        "controls_per_candidate_is_4": controls[
            "controls_per_provisional_candidate_subset"
        ]
        == len(controls["neutralizers"]) * len(controls["tasks"])
        == 4,
    }
    return {
        "derived": {
            "c1_maximum_target_calls": c1_expected,
            "c2_nonempty_subsets": nonempty,
            "c2_maximum_lattice_calls_per_instance": lattice_expected,
            "c2_maximum_control_calls_per_instance": controls_expected,
            "c2_maximum_total_new_calls_per_instance": lattice_expected
            + controls_expected,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def bytes_contain_ascii(path: Path, marker: bytes) -> bool:
    marker = marker.lower()
    overlap = max(0, len(marker) - 1)
    tail = b""
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            combined = tail + block
            if marker in combined.lower():
                return True
            tail = combined[-overlap:] if overlap else b""
    return False


def audit_runtime_support(root: Path, config: Mapping[str, Any]) -> JsonObject:
    runtime = config["runtime_contract_draft"]
    cli_path = resolve(root, runtime["cli_path"])
    runtime_dir = cli_path.parent
    cli_exists = cli_path.is_file()
    cli_hash = file_sha256(cli_path) if cli_exists else None
    marker_files = ["llama-common.dll", "llama.dll", "mtmd.dll"]
    markers = {}
    for name in marker_files:
        path = runtime_dir / name
        markers[name] = {
            "exists": path.is_file(),
            "contains_gemma4_marker": path.is_file()
            and bytes_contain_ascii(path, b"gemma4"),
        }
    checks = {
        "runtime_cli_exists": cli_exists,
        "runtime_cli_hash_matches": cli_hash == runtime["cli_sha256"],
        "all_three_runtime_libraries_contain_gemma4_marker": all(
            value["exists"] and value["contains_gemma4_marker"]
            for value in markers.values()
        ),
        "actual_gemma_load_not_misrepresented": runtime[
            "gemma4_static_source_support_audit"
        ]["actual_model_load_and_chat_template_qualification_completed"]
        is False,
    }
    return {
        "runtime_cli_path": relative_display(root, cli_path),
        "expected_cli_sha256": runtime["cli_sha256"],
        "observed_cli_sha256": cli_hash,
        "binary_marker_checks": markers,
        "checks": checks,
        "passed": all(checks.values()),
        "interpretation": (
            "STATIC_SUPPORT_SIGNAL_ONLY_NOT_A_GEMMA_MODEL_LOAD_OR_"
            "TEMPLATE_QUALIFICATION"
        ),
    }


def validate_target_strategy(
    config: Mapping[str, Any], readiness: Mapping[str, Any]
) -> JsonObject:
    strategy = config["target_pair_strategy_draft"]
    preferred = strategy["preferred_pair"]
    qwen = preferred[0]
    gemma = preferred[1]
    fallback = strategy["preoutput_operational_fallback"]
    readiness_models = {item["model_id"]: item for item in readiness["models"]}
    qwen_ready = readiness_models.get(qwen["model_id"], {})
    llama_ready = readiness_models.get(fallback["model_id"], {})
    qwen_expected_files = [
        (item["path"], item["size_bytes"], item["sha256"]) for item in qwen["files"]
    ]
    qwen_observed_files = [
        (
            item["path"],
            item["expected_size_bytes"],
            item["expected_sha256"],
        )
        for item in qwen_ready.get("files", [])
    ]
    llama_files = llama_ready.get("files", [])
    llama_match = len(llama_files) == 1 and (
        llama_files[0].get("path") == fallback["entry_file"]
        and llama_files[0].get("expected_size_bytes") == fallback["size_bytes"]
        and llama_files[0].get("expected_sha256") == fallback["sha256"]
    )
    gemma_file = gemma["files"][0]
    checks = {
        "preferred_pair_has_two_distinct_models": len(preferred) == 2
        and len({item["model_id"] for item in preferred}) == 2,
        "preferred_pair_is_qwen_then_gemma": [item["model_id"] for item in preferred]
        == ["qwen2.5-7b-instruct-q4-k-m", "google-gemma-4-e4b-it-qat-q4-0"],
        "qwen_metadata_binds_readiness": qwen_expected_files == qwen_observed_files
        and qwen_ready.get("passed") is True,
        "llama_fallback_metadata_binds_readiness": llama_match
        and llama_ready.get("passed") is True,
        "gemma_metadata_is_exact": gemma["runtime_revision"]
        == "4b4a2c1d584be7264f87aac328a1bc739ce81b6c"
        and gemma_file["filename"] == "gemma-4-E4B_q4_0-it.gguf"
        and gemma_file["size_bytes"] == 5154941280
        and gemma_file["sha256"]
        == "676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee",
        "gemma_not_claimed_local_or_qualified": gemma[
            "locally_present_and_harmless_qualified"
        ]
        is False,
        "fallback_is_preoutput_only": "before any Gemma C1N output is opened"
        in strategy["fallback_rule"],
        "outcome_motivated_substitution_forbidden": "unattractive scientific result"
        in strategy["fallback_rule"],
    }
    return {"checks": checks, "passed": all(checks.values())}


def scientific_output_absence(root: Path, config: Mapping[str, Any]) -> JsonObject:
    planned = config["planned_recording"]
    keys = (
        "future_harmless_admission_root",
        "future_c1n_root",
        "future_c2n_root",
        "future_c3n_root",
        "future_private_root",
    )
    paths = {}
    for key in keys:
        path = resolve(root, planned[key])
        files = [item for item in path.rglob("*") if item.is_file()] if path.exists() else []
        paths[key] = {
            "path": relative_display(root, path),
            "file_count": len(files),
            "scientific_files_absent": not files,
        }
    gemma_entry = resolve(
        root,
        config["target_pair_strategy_draft"]["preferred_pair"][1]["entry_file"],
    )
    paths["preferred_gemma_artifact"] = {
        "path": relative_display(root, gemma_entry),
        "file_count": int(gemma_entry.is_file()),
        "scientific_files_absent": not gemma_entry.is_file(),
    }
    return {
        "paths": paths,
        "passed": all(value["scientific_files_absent"] for value in paths.values()),
    }


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path)
    config = load_object(config_path)
    require_unauthorized_draft(config)
    config_sha256 = file_sha256(config_path)
    output_path = resolve(root, config["planned_recording"]["draft_preflight_path"])
    if not output_path.is_relative_to(root):
        raise ValueError("draft preflight output escapes repository root")
    existing = validated_existing_result(output_path, config_sha256=config_sha256)

    dependencies = config["dependencies"]
    dependency_audits = {
        name: audit_dependency(root, specification)
        for name, specification in dependencies.items()
    }
    dependency_hashes_pass = all(
        audit["exists"] and audit["sha256_matches"]
        for audit in dependency_audits.values()
    )
    loaded = {
        name: load_object(resolve(root, specification["path"]))
        for name, specification in dependencies.items()
        if str(specification["path"]).endswith(".json")
    }
    semantic_checks = semantic_dependency_checks(config, loaded)
    semantic_pass = all(semantic_checks.values())

    confirmation_rows = load_jsonl(
        resolve(root, dependencies["confirmation_reservation"]["path"])
    )
    development_rows = load_jsonl(
        resolve(root, dependencies["development_payload_manifest"]["path"])
    )
    reservation = audit_reservation(
        confirmation_rows, development_rows, config["population_contract"]
    )
    t0_checks = validate_t0_constants(config, loaded["t0_frozen_transition_contract"])
    t0_pass = all(t0_checks.values())
    budgets = validate_call_budgets(config)
    runtime = audit_runtime_support(root, config)
    target_strategy = validate_target_strategy(config, loaded["step5n_static_readiness"])
    output_absence = scientific_output_absence(root, config)

    boundary_checks = {
        "draft_is_not_frozen": config["frozen"] is False,
        "author_decision_is_not_recorded": config["authorization_boundary"][
            "author_narrow_decision_recorded"
        ]
        is False,
        "target_pair_is_not_selected": config["authorization_boundary"][
            "target_pair_selected"
        ]
        is False,
        "paper_claim_is_not_allowed": config["claim_contract"][
            "paper_claim_allowed_before_c3n_pass"
        ]
        is False,
        "draft_cannot_create_scientific_output": config["planned_recording"][
            "draft_preflight_may_create_scientific_output"
        ]
        is False,
        "safe_artifacts_forbid_raw_content": config["planned_recording"][
            "raw_prompt_payload_or_response_allowed_in_safe_artifacts"
        ]
        is False,
    }
    preflight_pass = all(
        (
            dependency_hashes_pass,
            semantic_pass,
            reservation["passed"],
            t0_pass,
            budgets["passed"],
            runtime["passed"],
            target_strategy["passed"],
            output_absence["passed"],
            all(boundary_checks.values()),
        )
    )
    result: JsonObject = {
        "schema_version": "jbspan-step5n-h4rm3l-confirmation-draft-preflight-v1",
        "status": PASS_STATUS if preflight_pass else FAIL_STATUS,
        "captured_at": (
            existing["captured_at"]
            if existing is not None
            else datetime.now().astimezone().isoformat(timespec="seconds")
        ),
        "config_path": relative_display(root, config_path),
        "config_sha256": config_sha256,
        "checks": {
            "all_dependency_hashes_match": dependency_hashes_pass,
            "all_dependency_semantics_match": semantic_pass,
            "reservation_passed": reservation["passed"],
            "t0_constants_match": t0_pass,
            "call_budgets_passed": budgets["passed"],
            "runtime_static_support_passed": runtime["passed"],
            "target_strategy_metadata_passed": target_strategy["passed"],
            "scientific_output_absent": output_absence["passed"],
            "authorization_boundary_passed": all(boundary_checks.values()),
        },
        "boundary_checks": boundary_checks,
        "dependency_audits": dependency_audits,
        "dependency_semantic_checks": semantic_checks,
        "reservation": reservation,
        "t0_constant_checks": t0_checks,
        "call_budgets": budgets,
        "runtime_static_support": runtime,
        "target_strategy": target_strategy,
        "scientific_output_absence": output_absence,
        "draft_preflight_pass": preflight_pass,
        "author_narrow_decision_recorded": False,
        "target_pair_selected": False,
        "confirmatory_contract_frozen": False,
        "model_download_performed": False,
        "harmless_admission_performed": False,
        "confirmatory_target_output_opened": False,
        "confirmatory_evaluator_output_opened": False,
        "confirmatory_topology_opened": False,
        "raw_prompt_payload_or_response_recorded": False,
        "paper_validity": False,
        "next_operation": config["next_operation_if_draft_preflight_passes"],
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    if existing is not None:
        if existing != result:
            raise RuntimeError(
                "refusing to overwrite a nonidentical Step 5N draft preflight result"
            )
    else:
        write_json_atomic(output_path, result)
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        result = run(arguments.root, arguments.config)
    except DraftBoundaryError as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_identity_sha256": result["result_identity_sha256"],
                "scientific_output_opened": result[
                    "confirmatory_target_output_opened"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if result["draft_preflight_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
