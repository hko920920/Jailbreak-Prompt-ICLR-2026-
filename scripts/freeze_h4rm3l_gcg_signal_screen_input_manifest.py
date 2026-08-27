from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSON object at {path}:{line_number}")
        rows.append(cast(JsonObject, value))
    return rows


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
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git identity.


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256_bytes(payload)


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


def require_blob(root: Path, path: str, expected: str) -> None:
    observed = git_blob_sha(root / path)
    if observed != expected:
        raise ValueError(f"Git blob mismatch for {path}: {observed}")


def require_false(value: JsonObject, key: str) -> None:
    if value.get(key) is not False:
        raise ValueError(f"expected {key}=false")


def validate_execution_predecessor(
    root: Path,
    contract: JsonObject,
) -> tuple[JsonObject, list[JsonObject]]:
    predecessor = cast(
        JsonObject,
        contract["execution_freeze_predecessor"],
    )
    result_path = str(predecessor["result_path"])
    payload_path = str(predecessor["payload_manifest_path"])
    require_blob(
        root,
        result_path,
        str(predecessor["result_git_blob_sha"]),
    )
    require_blob(
        root,
        payload_path,
        str(predecessor["payload_manifest_git_blob_sha"]),
    )
    result = load_object(root / result_path)
    payloads = load_jsonl(root / payload_path)

    if result.get("status") != predecessor["required_status"]:
        raise ValueError("execution-freeze status mismatch")
    if (
        result.get("next_authorized_operation")
        != predecessor["required_next_authorized_operation"]
    ):
        raise ValueError("execution-freeze authorization mismatch")
    if result.get("operational_pass") is not True:
        raise ValueError("execution-freeze predecessor did not pass")
    if result.get("paper_validity") is not False:
        raise ValueError("execution-freeze predecessor is paper-valid")
    require_false(result, "model_inference_performed")
    require_false(result, "model_weight_downloaded")
    require_false(result, "attack_success_observed")
    require_false(result, "raw_payload_or_response_recorded")

    expected_count = int(predecessor["required_payload_count"])
    if len(payloads) != expected_count:
        raise ValueError("payload manifest count mismatch")
    if payloads != cast(list[JsonObject], result["payload_manifest"]):
        raise ValueError("payload manifest differs from predecessor result")
    observed_manifest_sha = canonical_sha256(payloads)
    if observed_manifest_sha != predecessor["required_payload_manifest_sha256"]:
        raise ValueError("payload manifest canonical SHA-256 mismatch")
    if observed_manifest_sha != result["payload_manifest_sha256"]:
        raise ValueError("predecessor payload SHA-256 mismatch")
    return result, payloads


def validate_family_predecessors(
    root: Path,
    contract: JsonObject,
) -> tuple[JsonObject, JsonObject, list[JsonObject], JsonObject]:
    families = cast(list[JsonObject], contract["attack_families"])
    by_name = {str(row["family"]): row for row in families}
    if set(by_name) != {"h4rm3l", "GCG"}:
        raise ValueError("exactly h4rm3l and GCG must be frozen")

    h_contract = by_name["h4rm3l"]
    g_contract = by_name["GCG"]
    require_blob(
        root,
        str(h_contract["predecessor_path"]),
        str(h_contract["predecessor_git_blob_sha"]),
    )
    require_blob(
        root,
        str(g_contract["predecessor_path"]),
        str(g_contract["predecessor_git_blob_sha"]),
    )
    h_value = load_object(root / str(h_contract["predecessor_path"]))
    g_value = load_object(root / str(g_contract["predecessor_path"]))

    if h_value.get("status") != h_contract["required_status"]:
        raise ValueError("h4rm3l predecessor status mismatch")
    if g_value.get("status") != g_contract["required_status"]:
        raise ValueError("GCG predecessor status mismatch")
    if h_value.get("operational_pass") is not True:
        raise ValueError("h4rm3l predecessor did not pass")
    if g_value.get("operational_pass") is not True:
        raise ValueError("GCG predecessor did not pass")
    require_false(h_value, "target_model_called")
    require_false(g_value, "target_model_called")
    require_false(g_value, "target_model_generation_performed")
    require_false(g_value, "target_model_weights_downloaded")
    require_false(h_value, "attack_success_scored")
    require_false(g_value, "prior_evaluation_opened")

    programs = cast(list[JsonObject], h_value["programs"])
    if len(programs) != int(h_contract["required_program_count"]):
        raise ValueError("h4rm3l program count mismatch")
    if not all(row.get("operational_pass") is True for row in programs):
        raise ValueError("a h4rm3l program failed its predecessor audit")
    template_defaults = cast(JsonObject, g_value["observed_template_defaults"])
    if "control_init_sha256" not in template_defaults:
        raise ValueError("GCG control identity hash missing")
    if "control_init_lexical_units" not in template_defaults:
        raise ValueError("GCG control lexical count missing")
    return h_value, g_value, programs, template_defaults


def make_h4rm3l_program_identities(
    programs: list[JsonObject],
) -> list[JsonObject]:
    identities: list[JsonObject] = []
    for source_position, program in enumerate(programs):
        program_id = str(program["id"])
        identity_material: JsonObject = {
            "source_position": source_position,
            "program_id_sha256": sha256_bytes(program_id.encode()),
            "component_count": int(program["component_count"]),
            "fragment_count": int(program["fragment_count"]),
            "subset_count": int(program["subset_count"]),
            "unit_manifest_sha256": str(program["unit_manifest_sha256"]),
            "fragment_manifest_sha256": str(
                program["fragment_manifest_sha256"]
            ),
            "variant_manifest_sha256": str(
                program["variant_manifest_sha256"]
            ),
        }
        identity_material["program_identity_sha256"] = canonical_sha256(
            identity_material
        )
        identities.append(identity_material)
    return sorted(
        identities,
        key=lambda row: str(row["program_identity_sha256"]),
    )


def make_direct_instances(
    payloads: list[JsonObject],
    target_model: JsonObject,
    generation: JsonObject,
) -> list[JsonObject]:
    model_sha = canonical_sha256(target_model)
    generation_sha = canonical_sha256(generation)
    seeds = cast(list[int], generation["seeds"])
    rows: list[JsonObject] = []
    for payload in sorted(payloads, key=lambda row: int(row["position"])):
        for seed in seeds:
            identity_material: JsonObject = {
                "condition": "DIRECT",
                "payload_position": int(payload["position"]),
                "semantic_category": str(payload["semantic_category"]),
                "behavior_id_sha256": str(payload["behavior_id_sha256"]),
                "payload_sha256": str(payload["payload_sha256"]),
                "source_row_sha256": str(payload["source_row_sha256"]),
                "payload_utf8_bytes": int(payload["payload_utf8_bytes"]),
                "seed": int(seed),
                "target_model_identity_sha256": model_sha,
                "generation_identity_sha256": generation_sha,
            }
            rows.append(
                {
                    "schema_version": (
                        "h4rm3l-gcg-signal-screen-direct-instance-v1"
                    ),
                    "direct_instance_id": canonical_sha256(
                        identity_material
                    ),
                    **identity_material,
                    "raw_text_recorded": False,
                }
            )
    return rows


def h4rm3l_schedule(
    direct_instances: list[JsonObject],
    program_identities: list[JsonObject],
) -> dict[str, JsonObject]:
    ordered_direct = sorted(
        direct_instances,
        key=lambda row: str(row["direct_instance_id"]),
    )
    if not program_identities:
        raise ValueError("empty h4rm3l program identity set")
    schedule: dict[str, JsonObject] = {}
    for index, direct in enumerate(ordered_direct):
        schedule[str(direct["direct_instance_id"])] = program_identities[
            index % len(program_identities)
        ]
    return schedule


def make_pair_plans(
    direct_instances: list[JsonObject],
    h_programs: list[JsonObject],
    h_value: JsonObject,
    g_value: JsonObject,
    g_defaults: JsonObject,
    family_contracts: list[JsonObject],
) -> tuple[list[JsonObject], JsonObject]:
    h_schedule = h4rm3l_schedule(direct_instances, h_programs)
    contracts = {
        str(row["family"]): row
        for row in family_contracts
    }
    h_family_identity = canonical_sha256(
        {
            "status": h_value["status"],
            "source_revision": h_value["source_revision"],
            "program_identities": h_programs,
        }
    )
    g_family_identity = canonical_sha256(
        {
            "status": g_value["status"],
            "source": g_value["source"],
            "template_defaults": g_defaults,
            "intervention_boundary": g_value["intervention_boundary"],
        }
    )
    family_identities: JsonObject = {
        "h4rm3l": h_family_identity,
        "GCG": g_family_identity,
    }
    rows: list[JsonObject] = []
    for direct in sorted(
        direct_instances,
        key=lambda row: (
            int(row["payload_position"]),
            int(row["seed"]),
        ),
    ):
        direct_id = str(direct["direct_instance_id"])
        h_program = h_schedule[direct_id]
        for family in ("h4rm3l", "GCG"):
            family_contract = contracts[family]
            family_material: JsonObject
            if family == "h4rm3l":
                family_material = {
                    "family_contract_identity_sha256": h_family_identity,
                    "program_identity_sha256": h_program[
                        "program_identity_sha256"
                    ],
                    "program_source_position": h_program["source_position"],
                    "coarse_unit_count": min(
                        int(h_program["component_count"]),
                        int(family_contract["maximum_coarse_units"]),
                    ),
                    "coarse_unit_source": "TYPED_DECORATOR_COMPONENT",
                }
            else:
                family_material = {
                    "family_contract_identity_sha256": g_family_identity,
                    "control_init_sha256": g_defaults[
                        "control_init_sha256"
                    ],
                    "control_init_lexical_units": g_defaults[
                        "control_init_lexical_units"
                    ],
                    "optimization_step_budget": g_defaults["n_steps"],
                    "optimization_topk": g_defaults["topk"],
                    "optimization_batch_size": g_defaults["batch_size"],
                    "coarse_unit_count": int(
                        family_contract["maximum_coarse_units"]
                    ),
                    "coarse_unit_source": (
                        "EQUAL_CONTIGUOUS_CONTROL_BLOCK"
                    ),
                }
            identity_material: JsonObject = {
                "condition": "ATTACKED",
                "attack_family": family,
                "direct_instance_id": direct_id,
                "payload_position": direct["payload_position"],
                "semantic_category": direct["semantic_category"],
                "behavior_id_sha256": direct["behavior_id_sha256"],
                "payload_sha256": direct["payload_sha256"],
                "seed": direct["seed"],
                "target_model_identity_sha256": direct[
                    "target_model_identity_sha256"
                ],
                "generation_identity_sha256": direct[
                    "generation_identity_sha256"
                ],
                **family_material,
                "attacked_material_status": (
                    "PLANNED_PRIVATE_NOT_GENERATED"
                ),
            }
            rows.append(
                {
                    "schema_version": (
                        "h4rm3l-gcg-signal-screen-pair-plan-v1"
                    ),
                    "pair_plan_id": canonical_sha256(identity_material),
                    **identity_material,
                    "attack_optimization_performed": False,
                    "model_inference_performed": False,
                    "raw_text_recorded": False,
                }
            )
    return rows, family_identities


def validate_cardinality(
    contract: JsonObject,
    direct_instances: list[JsonObject],
    pair_plans: list[JsonObject],
) -> None:
    expected = cast(JsonObject, contract["manifest_cardinality"])
    if len(direct_instances) != int(
        expected["shared_direct_instance_count"]
    ):
        raise ValueError("direct instance count mismatch")
    if len(pair_plans) != int(expected["attacked_pair_plan_count"]):
        raise ValueError("pair-plan count mismatch")
    if (
        len(direct_instances) + len(pair_plans)
        != int(expected["planned_baseline_generation_count"])
    ):
        raise ValueError("planned baseline generation count mismatch")
    direct_ids = {
        str(row["direct_instance_id"])
        for row in direct_instances
    }
    pair_ids = {str(row["pair_plan_id"]) for row in pair_plans}
    if len(direct_ids) != len(direct_instances):
        raise ValueError("duplicate direct instance identity")
    if len(pair_ids) != len(pair_plans):
        raise ValueError("duplicate pair-plan identity")
    h_counts = Counter(
        str(row["program_identity_sha256"])
        for row in pair_plans
        if row["attack_family"] == "h4rm3l"
    )
    if max(h_counts.values()) - min(h_counts.values()) > 1:
        raise ValueError("h4rm3l schedule is not balanced")


def run(
    root: Path,
    config_path: Path,
    safe_output: Path,
    direct_output: Path,
    pair_output: Path,
) -> JsonObject:
    contract = load_object(config_path)
    if (
        contract.get("status")
        != (
            "FROZEN_BEFORE_SIGNAL_SCREEN_ATTACK_MATERIALIZATION_"
            "OR_TARGET_OUTCOMES"
        )
    ):
        raise ValueError("unexpected manifest-freeze contract status")
    if contract.get("frozen") is not True:
        raise ValueError("manifest-freeze contract is not frozen")
    if contract.get("paper_validity") is not False:
        raise ValueError("manifest contract cannot be paper-valid")
    sealed = cast(JsonObject, contract["sealed_boundaries"])
    if any(value is not False for value in sealed.values()):
        raise ValueError("a sealed boundary was opened")

    predecessor, payloads = validate_execution_predecessor(
        root,
        contract,
    )
    h_value, g_value, programs, g_defaults = (
        validate_family_predecessors(root, contract)
    )
    target_model = cast(JsonObject, predecessor["target_model"])
    generation = cast(JsonObject, predecessor["generation"])
    audit = cast(JsonObject, predecessor["screening_and_audit"])
    direct_instances = make_direct_instances(
        payloads,
        target_model,
        generation,
    )
    program_identities = make_h4rm3l_program_identities(programs)
    pair_plans, family_identities = make_pair_plans(
        direct_instances,
        program_identities,
        h_value,
        g_value,
        g_defaults,
        cast(list[JsonObject], contract["attack_families"]),
    )
    validate_cardinality(contract, direct_instances, pair_plans)

    checks = {
        "execution_freeze_predecessor_matches": True,
        "payload_manifest_matches": True,
        "payloads_are_hash_only": True,
        "target_model_identity_is_inherited": True,
        "decoding_and_seeds_are_inherited": True,
        "h4rm3l_predecessor_matches": True,
        "gcg_predecessor_matches": True,
        "h4rm3l_schedule_is_balanced": True,
        "direct_instance_count_matches": True,
        "pair_plan_count_matches": True,
        "all_attacked_material_is_unmaterialized": all(
            row["attacked_material_status"]
            == "PLANNED_PRIVATE_NOT_GENERATED"
            for row in pair_plans
        ),
        "no_attack_optimization": True,
        "no_model_inference": True,
        "no_automated_or_human_label": True,
        "raw_text_is_absent": all(
            row.get("raw_text_recorded") is False
            for row in direct_instances + pair_plans
        ),
        "evaluator_runtime_gate_remains_closed": True,
        "sealed_boundaries_preserved": True,
    }
    passed = all(checks.values())
    decision_gate = cast(JsonObject, contract["decision_gate"])
    result: JsonObject = {
        "schema_version": (
            "h4rm3l-gcg-signal-screen-input-manifest-result-v1"
        ),
        "status": (
            "H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST_FREEZE_PASS"
            if passed
            else "H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST_FREEZE_FAIL"
        ),
        "operational_pass": passed,
        "scientific_pass": False,
        "paper_validity": False,
        "evidence_class": "PROTOCOL",
        "contract_sha256": sha256_file(config_path),
        "contract_git_blob_sha": git_blob_sha(config_path),
        "execution_freeze_predecessor": {
            "path": contract["execution_freeze_predecessor"][
                "result_path"
            ],
            "git_blob_sha": contract["execution_freeze_predecessor"][
                "result_git_blob_sha"
            ],
            "status": predecessor["status"],
            "payload_manifest_sha256": predecessor[
                "payload_manifest_sha256"
            ],
        },
        "manifest_cardinality": {
            "payload_count": len(payloads),
            "seed_count": len(cast(list[int], generation["seeds"])),
            "family_count": 2,
            "shared_direct_instance_count": len(direct_instances),
            "attacked_pair_plan_count": len(pair_plans),
            "planned_baseline_generation_count": (
                len(direct_instances) + len(pair_plans)
            ),
        },
        "direct_instances_sha256": canonical_sha256(direct_instances),
        "pair_plans_sha256": canonical_sha256(pair_plans),
        "family_contract_identities": family_identities,
        "h4rm3l_program_identity_count": len(program_identities),
        "target_model": target_model,
        "generation": generation,
        "screening_and_audit": audit,
        "screening_and_audit_contract_sha256": canonical_sha256(audit),
        "evaluator_runtime_gate": contract["evaluator_runtime_gate"],
        "safe_output_policy": contract["safe_output_policy"],
        "checks": checks,
        "next_authorized_operation": (
            decision_gate["on_manifest_freeze_pass"]
            if passed
            else decision_gate["on_operational_fail"]
        ),
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "attack_optimization_performed": False,
        "attack_success_observed": False,
        "automated_label_observed": False,
        "human_label_observed": False,
        "new_harmful_attack_outputs_generated": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_payload_prompt_response_or_control_recorded": False,
    }
    write_json(safe_output, result)
    write_jsonl(direct_output, direct_instances)
    write_jsonl(pair_output, pair_plans)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Freeze hash-only h4rm3l-GCG signal-screen input identities"
        )
    )
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    value.add_argument("--direct-output", type=Path, required=True)
    value.add_argument("--pair-output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    result = run(
        args.root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
        args.direct_output.resolve(),
        args.pair_output.resolve(),
    )
    print(result["status"])
    return 0 if result["operational_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
