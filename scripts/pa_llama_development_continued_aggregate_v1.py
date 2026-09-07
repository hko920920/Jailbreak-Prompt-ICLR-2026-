"""No-inference finalizer for an explicitly amended P/A execution.

Original resource failures remain failures. Only the new composite verifier
can supply the JailMeter axis; the original frozen axis verifier is untouched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pa_llama_development_aggregate_v1 as original
import pa_llama_development_common_v1 as c
import pa_llama_development_panel_v1 as panel
import pa_llama_development_target_v1 as target

SCRIPT = "scripts/pa_llama_development_continued_aggregate_v1.py"
SCOPE = "RAW_SCIENTIFIC_RECEIPTS_AND_AMENDED_EXECUTION_NOT_ORIGINAL_OPERATIONAL_PASS"
CONTINUED_SCHEMA = "jbspan-pa-llama-development-continued-axis-v1"


def disclosure(amendment):
    sha = amendment.get("_amendment_sha256")
    c.require(c.valid_sha(sha), "AMENDMENT_IDENTITY_REQUIRED")
    return {
        "operational_amendment_sha256s": [sha],
        "original_seed11_jailmeter_operational_gate_passed": False,
        "verification_scope": SCOPE,
        "scientific_rules_unchanged": True,
    }


def validate_previous(config, amendment, previous, proof):
    c.require(isinstance(previous, dict) and isinstance(proof, dict), "AMENDED_PRIOR_REQUIRED")
    fields = disclosure(amendment)
    proof_keys = set(fields) | {
        "schema_version",
        "contract_sha256",
        "phase_seed",
        "phase_result_identity_sha256",
        "raw_axis_receipts_verified",
        "independent_pair_states_verified",
        "independent_panel_rule_verified",
        "verification_passed",
        "verified_axis_identities",
        "target_rows_sha256",
        "measurement_rows_sha256",
        "pair_states_checked",
        "phase_decisions_checked",
        "new_model_calls",
        "historical_private_reads",
        "sealed_reads",
        "finalizer_source_path",
        "verification_identity_sha256",
    }
    c.require(set(proof) == proof_keys, "AMENDED_PRIOR_PROOF_SCHEMA")
    fixed = {
        "schema_version": "jbspan-pa-llama-development-phase-verification-v1",
        "finalizer_source_path": SCRIPT,
        "pair_states_checked": 45,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "phase_decisions_checked": previous.get("phase_request_count"),
    }
    c.require(all(c.same(proof.get(k), v) for k, v in fixed.items()), "AMENDED_PRIOR_PROOF_VALUES")
    identities = proof.get("verified_axis_identities")
    c.require(
        isinstance(identities, dict)
        and set(identities) == {"qwen", "jailmeter"}
        and all(c.valid_sha(value) for value in identities.values())
        and c.valid_sha(proof.get("target_rows_sha256"))
        and c.valid_sha(proof.get("measurement_rows_sha256")),
        "AMENDED_PRIOR_RECEIPT_IDENTITIES",
    )
    c.require(
        all(c.same(previous.get(k), v) and c.same(proof.get(k), v) for k, v in fields.items()),
        "AMENDED_PRIOR_DISCLOSURE_REQUIRED",
    )
    c.require(
        proof.get("contract_sha256") == config["_contract_sha256"]
        and proof.get("phase_seed") == previous.get("phase_seed")
        and proof.get("phase_result_identity_sha256") == previous.get("result_identity_sha256")
        and proof.get("raw_axis_receipts_verified") is True
        and proof.get("independent_pair_states_verified") is True
        and proof.get("independent_panel_rule_verified") is True
        and proof.get("verification_passed") is True
        and type(proof.get("new_model_calls")) is int
        and proof["new_model_calls"] == 0,
        "AMENDED_PRIOR_PROOF_BINDING",
    )
    body = {k: v for k, v in proof.items() if k != "verification_identity_sha256"}
    c.require(
        proof.get("verification_identity_sha256") == c.digest(body), "AMENDED_PRIOR_PROOF_HASH"
    )
    original.independent_state_check(previous)


def validate_composite(config, amendment, plan, axis):
    c.require(isinstance(axis, dict), "COMPOSITE_AXIS_REQUIRED")
    expected = {
        "schema_version": CONTINUED_SCHEMA,
        "execution_amendment_sha256": amendment["_amendment_sha256"],
        "contract_sha256": config["_contract_sha256"],
        "phase_seed": plan["phase_seed"],
        "axis": "jailmeter",
        "complete": True,
        "raw_receipts_reverified": True,
        "composite_lifecycle_verified": True,
        "resource_stop_preserved": True,
        "all_original_completed_reused": True,
    }
    c.require(all(c.same(axis.get(k), v) for k, v in expected.items()), "COMPOSITE_AXIS_AUTHORITY")


def build_artifacts(
    config,
    amendment,
    inventory,
    plan,
    generations,
    axes,
    helpers,
    previous=None,
    previous_proof=None,
):
    """Pure assembly after separate full raw verification; all inputs supplied."""
    if plan["phase_seed"] == 11:
        c.require(previous is None and previous_proof is None, "FIRST_PHASE_HAS_PRIOR")
    else:
        validate_previous(config, amendment, previous, previous_proof)
    expected_plan = c.phase_plan(config, inventory, plan["phase_seed"], previous)
    c.require(c.same(plan, expected_plan), "AMENDED_COMPLETE_PLAN_BINDING")
    validate_composite(config, amendment, plan, axes["jailmeter"])
    decisions, measurements = original.assemble_decisions(config, plan, generations, axes, helpers)
    result = c.phase_result(config, inventory, plan, decisions, previous)
    result.update(disclosure(amendment))
    result.pop("result_identity_sha256")
    result["result_identity_sha256"] = c.digest(result)
    checked = original.independent_state_check(
        result, plan=plan, decisions=decisions, previous=previous, inventory=inventory
    )
    prefix_list = amendment["original_seed11_prefix"]["dispatched_request_ids"]
    c.require(isinstance(prefix_list, list) and len(prefix_list) == 30, "PREFIX_EXACT30_REQUIRED")
    prefix = set(prefix_list)
    c.require(
        len(prefix) == 30 and all(c.valid_sha(rid) for rid in prefix), "PREFIX_EXACT30_REQUIRED"
    )
    original_plan_ids = {item["request_id"] for item in c.phase_plan(config, inventory, 11)["rows"]}
    c.require(prefix <= original_plan_ids, "PREFIX_OUTSIDE_EXACT_SEED11_PLAN")
    dependent = []
    for state in result["pair_states"]:
        first = state["seed_observations"][0]
        if any(first[key]["request_id"] in prefix for key in ("direct", "attacked")):
            dependent.append(state["payload_position"])
    stable_without_prefix = [
        position for position in result["stable_positions"] if position not in dependent
    ]
    sensitivity = {
        "original_failed_epoch_request_count": 30,
        "positions_with_an_original_failed_epoch_judge_response": dependent,
        "primary_stable_positions": result["stable_positions"],
        "stable_positions_not_depending_on_original_failed_epoch": stable_without_prefix,
        "diagnostic_only_not_primary_population_selection": True,
        "original_failed_epoch_reliability_established": False,
    }
    if plan["phase_seed"] == 11:
        pessimistic = [
            {**row, "panel_label": "ABSTAIN", "eligible": False}
            if row["request_id"] in prefix
            else dict(row)
            for row in decisions
        ]
        hypothetical = c.phase_result(config, inventory, plan, pessimistic)
        sensitivity["hypothetical_all_original30_unknown"] = {
            key: hypothetical[key] for key in ("status_counts", "advance_positions", "route")
        }
        sensitivity["hypothetical_labels_are_not_observations"] = True
    measurement = {
        "schema_version": "jbspan-pa-llama-development-measurements-v1",
        "contract_sha256": config["_contract_sha256"],
        "phase_seed": plan["phase_seed"],
        "planned_records": len(measurements),
        "rows": measurements,
        "rows_identity_sha256": c.digest(measurements),
        "panel_counts": {
            label: sum(row["panel_label"] == label for row in decisions)
            for label in ("SAFE", "HARMFUL", "ABSTAIN")
        },
        "measurement_eligible": sum(row["eligible"] for row in decisions),
        "new_model_calls": 0,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "paper_validity": False,
        "failed_epoch_sensitivity": sensitivity,
        **disclosure(amendment),
    }
    proof = {
        "schema_version": "jbspan-pa-llama-development-phase-verification-v1",
        "contract_sha256": config["_contract_sha256"],
        "phase_seed": plan["phase_seed"],
        "phase_result_identity_sha256": result["result_identity_sha256"],
        "raw_axis_receipts_verified": True,
        "independent_pair_states_verified": True,
        "independent_panel_rule_verified": True,
        "verification_passed": True,
        "verified_axis_identities": {axis: c.digest(value) for axis, value in axes.items()},
        "target_rows_sha256": c.digest(generations),
        "measurement_rows_sha256": c.digest(measurements),
        "pair_states_checked": checked["pair_states_checked"],
        "phase_decisions_checked": checked["phase_decisions_checked"],
        "new_model_calls": 0,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "finalizer_source_path": SCRIPT,
        **disclosure(amendment),
    }
    proof["verification_identity_sha256"] = c.digest(proof)
    return measurement, result, proof


def aggregate(root, config, amendment, seed):
    import pa_llama_development_jailmeter_continuation_v1 as continued

    base = c.paths(root, config["_contract_sha256"])
    inventory = c.source_inventory(root, config)
    helper = target.helper_for(root, config)
    with target.operation_lock(base):
        previous = previous_proof = None
        if seed != 11:
            prior_seed = 11 if seed == 23 else 23
            previous = target.read_json(base["safe"] / f"phase_{prior_seed}_result.safe.json")
            previous_proof = target.read_json(
                base["safe"] / f"phase_{prior_seed}_verification.safe.json"
            )
            validate_previous(config, amendment, previous, previous_proof)
        plan = c.phase_plan(config, inventory, seed, previous)
        c.require(
            c.same(target.read_json(base["safe"] / f"phase_{seed}_plan.safe.json"), plan),
            "AMENDED_SAVED_PLAN_CHANGED",
        )
        axes = {
            "qwen": panel.verify_axis(root, config, plan, "qwen"),
            "jailmeter": continued.verify(root, config, amendment, plan),
        }
        inputs = target.load_inputs(root, config, inventory)
        census = target.load_census(root, config, inventory, helper)
        generations = target.reconcile_phase(root, config, plan, inputs, census, helper)
        helpers = panel.load_pure_functions(root, config)
        measurement, result, proof = build_artifacts(
            config, amendment, inventory, plan, generations, axes, helpers, previous, previous_proof
        )
        original.write_or_verify(base["safe"] / f"phase_{seed}_measurements.safe.json", measurement)
        original.write_or_verify(base["safe"] / f"phase_{seed}_result.safe.json", result)
        original.write_or_verify(base["safe"] / f"phase_{seed}_verification.safe.json", proof)
        return {
            "phase_seed": seed,
            "status_counts": result["status_counts"],
            "route": result["route"],
            "next_seed": result["next_seed"],
            "panel_counts": measurement["panel_counts"],
            "phase_result_identity_sha256": result["result_identity_sha256"],
            "failed_epoch_sensitivity": measurement["failed_epoch_sensitivity"],
            "verification_passed": True,
            "new_model_calls": 0,
            "paper_validity": False,
            **disclosure(amendment),
        }


def main():
    import pa_llama_development_jailmeter_continuation_v1 as continued

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--amendment-sha256", required=True)
    parser.add_argument("--seed", required=True, type=int, choices=(11, 23, 47))
    args = parser.parse_args()
    try:
        amendment = continued.load_amendment(args.root, args.amendment_sha256)
        config = c.load_contract(args.root, amendment["parent_contract"]["sha256"])
        own = [pin for pin in amendment["required_code"].values() if pin["path"] == SCRIPT]
        c.require(
            len(own) == 1
            and c.verify_pin(args.root, own[0], ("scripts/",)) == Path(__file__).resolve(),
            "CONTINUED_FINALIZER_SELF_PIN",
        )
        print(
            json.dumps(aggregate(args.root, config, amendment, args.seed), sort_keys=True, indent=2)
        )
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, c.DevelopmentError) else type(error).__name__
        print(json.dumps({"verification_passed": False, "error_code": code, "new_model_calls": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
