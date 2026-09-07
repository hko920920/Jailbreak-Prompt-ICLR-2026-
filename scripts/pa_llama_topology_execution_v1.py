"""Root-only preparation and explicit execution entrypoint for a separate topology contract.

No action occurs on import. Parent evidence verification is read-only and limited
to the NEW development artifacts. Historical extractors, sealed cohorts and
scientific criterion changes are never invoked by this module.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_continued_aggregate_v1 as parent_finalizer
import pa_llama_development_jailmeter_continuation_v1 as continuation
import pa_llama_development_panel_v1 as parent_panel
import pa_llama_development_target_v1 as parent_target
import pa_llama_topology_materialize_v1 as renderer_module
import pa_llama_topology_panel_v1 as panel_module
import pa_llama_topology_plan_v1 as plan_module
import pa_llama_topology_target_v1 as target_module

SCRIPT = "scripts/pa_llama_topology_execution_v1.py"
CONFIG = "configs/natural_language_localization/pa_llama_topology_execution_v1.json"
PROTOCOL = "docs/PA_LLAMA_TOPOLOGY_EXECUTION_PROTOCOL_2026-09-05_V1.md"
PARENT_SHA = plan_module.SCREEN_SHA256
AMENDMENT_SHA = "91895a7ff226a87c31a90b97efc4d020eb0beb31822a75073943d8741841a7d8"
NEW_INPUT_SHA = "9c803db7fa8a5a17a20d2774d8760cae609608b50a3e00fa50e8ec69677adfda"
NEW_INPUT_BYTES = 140072
NEW_INPUT_RECEIPT_SHA = "0ed7444eee47a367cd45802cc6ce5bcf7868cf18b6b5d1fc3da8fdedf3a62688"
PARENT_SAFE = f"{c.SAFE_ROOT}/{PARENT_SHA}"
PARENT_PRIVATE = f"{c.PRIVATE_ROOT}/{PARENT_SHA}"
NEW_INPUT_PATH = PARENT_PRIVATE + "/inputs.private.json"
NEW_INPUT_RECEIPT = PARENT_SAFE + "/inputs.safe.json"
PREP_SAFE = "data/natural_language_localization/pa_llama_topology_preparation_v1"
PREP_PRIVATE = "artifacts/pa_llama_topology_preparation_v1/private"
BUNDLE_SCHEMA = "jbspan-pa-llama-topology-source-bundle-v1"
PREP_SCHEMA = "jbspan-pa-llama-topology-preparation-v1"
MAX_BYTES = 32_000_000
PHASE_KINDS = ("measurements", "result", "verification")
NEW_MODULES = (
    "execution",
    "target",
    "panel",
    "plan",
    "materialize",
    "measurement",
    "analysis",
    "finalize",
)
NEW_CODE = (
    {f"scripts/pa_llama_topology_{name}_v1.py" for name in NEW_MODULES}
    | {f"tests/test_pa_llama_topology_{name}_v1.py" for name in NEW_MODULES}
    | {"tests/test_pa_llama_topology_integration_review_v1.py"}
)


def owned(root, relative):
    path = c.contained(root, relative)
    if os.name == "nt" and not str(path).startswith("\\\\?\\"):
        return Path("\\\\?\\" + str(path))
    return path


def file_descriptor(root, relative):
    path = owned(root, relative)
    c.require(
        path.is_file() and 0 < path.stat().st_size <= MAX_BYTES, "SOURCE_FILE_MISSING_OR_OVERSIZED"
    )
    raw = path.read_bytes()
    return {"path": relative, "size_bytes": len(raw), "sha256": c.sha_bytes(raw)}


def read_pin(root, pin, expected_path):
    c.require(
        isinstance(pin, dict)
        and set(pin) == {"path", "size_bytes", "sha256"}
        and pin.get("path") == expected_path
        and type(pin.get("size_bytes")) is int
        and 0 < pin["size_bytes"] <= MAX_BYTES
        and c.valid_sha(pin.get("sha256")),
        "SOURCE_PIN_PATH_OR_SCHEMA_CHANGED",
    )
    path = owned(root, expected_path)
    c.require(
        path.is_file() and path.stat().st_size == pin["size_bytes"], "SOURCE_PIN_SIZE_CHANGED"
    )
    raw = path.read_bytes()
    c.require(c.sha_bytes(raw) == pin["sha256"], "SOURCE_PIN_BYTES_CHANGED")
    return raw


def phase_path(seed, kind):
    c.require(
        type(seed) is int and seed in (11, 23, 47) and kind in PHASE_KINDS,
        "PARENT_PHASE_PATH_FORBIDDEN",
    )
    return f"{PARENT_SAFE}/phase_{seed}_{kind}.safe.json"


def source_shape(bundle):
    fields = {
        "schema_version",
        "parent_contract",
        "operational_amendment",
        "source_inventory",
        "new_screen_inputs",
        "new_screen_input_receipt",
        "phases",
        "raw_parent_receipts_reverified",
        "historical_private_reads",
        "sealed_reads",
        "new_model_calls",
        "execution_authorized",
        "source_bundle_identity_sha256",
    }
    c.require(
        isinstance(bundle, dict)
        and set(bundle) == fields
        and bundle.get("schema_version") == BUNDLE_SCHEMA
        and bundle.get("raw_parent_receipts_reverified") is True
        and bundle.get("execution_authorized") is False
        and all(
            c.same(bundle.get(key), 0)
            for key in ("historical_private_reads", "sealed_reads", "new_model_calls")
        ),
        "SOURCE_BUNDLE_SCOPE_OR_SCHEMA_CHANGED",
    )
    c.require(
        bundle.get("source_bundle_identity_sha256")
        == c.digest(
            {key: value for key, value in bundle.items() if key != "source_bundle_identity_sha256"}
        ),
        "SOURCE_BUNDLE_IDENTITY_CHANGED",
    )
    c.require(
        bundle["parent_contract"]["sha256"] == PARENT_SHA
        and bundle["operational_amendment"]["sha256"] == AMENDMENT_SHA
        and bundle["new_screen_inputs"]["sha256"] == NEW_INPUT_SHA
        and c.same(bundle["new_screen_inputs"]["size_bytes"], NEW_INPUT_BYTES)
        and bundle["new_screen_input_receipt"]["sha256"] == NEW_INPUT_RECEIPT_SHA
        and c.same(bundle["new_screen_input_receipt"]["size_bytes"], 555),
        "EXACT_APPROVED_PARENT_AMENDMENT_OR_NEW_INPUT_PIN_REQUIRED",
    )
    c.require(
        set(bundle.get("phases", {})) == {"11", "23", "47"}
        and all(set(value) == set(PHASE_KINDS) for value in bundle["phases"].values()),
        "ALL_NINE_PARENT_PHASE_PINS_REQUIRED",
    )


def verify_parent_evidence(root, parent, amendment, inventory, phase_docs):
    """Explicit approved exception: original verifiers read only NEW parent artifacts."""
    helper = parent_target.helper_for(root, parent)
    inputs = parent_target.load_inputs(root, parent, inventory)
    census = parent_target.load_census(root, parent, inventory, helper)
    helpers = parent_panel.load_pure_functions(root, parent)
    previous = previous_proof = None
    seen = set()
    for seed in (11, 23, 47):
        plan = c.phase_plan(parent, inventory, seed, previous)
        saved_plan = c.strict_json(
            owned(root, f"{PARENT_SAFE}/phase_{seed}_plan.safe.json").read_bytes()
        )
        c.require(c.same(plan, saved_plan), "PARENT_SAVED_PHASE_PLAN_CHANGED")
        axes = {
            "qwen": parent_panel.verify_axis(root, parent, plan, "qwen"),
            "jailmeter": continuation.verify(root, parent, amendment, plan),
        }
        generations = parent_target.reconcile_phase(root, parent, plan, inputs, census, helper)
        c.require(len(generations) == len(plan["rows"]), "PARENT_TARGET_PHASE_INCOMPLETE")
        seen.update(row["request_id"] for row in generations)
        rebuilt = parent_finalizer.build_artifacts(
            parent, amendment, inventory, plan, generations, axes, helpers, previous, previous_proof
        )
        expected = phase_docs[str(seed)]
        c.require(
            all(
                c.same(value, expected[kind])
                for value, kind in zip(rebuilt, PHASE_KINDS, strict=True)
            ),
            "PARENT_PHASE_NOT_EXACTLY_REBUILT_FROM_RAW_RECEIPTS",
        )
        previous, previous_proof = expected["result"], expected["verification"]
    c.require(
        parent_target.global_receipt_check(root, parent, inventory) == len(seen),
        "UNRECONCILED_PARENT_TARGET_DISPATCH",
    )
    return inputs


def load_sources(root, bundle):
    source_shape(bundle)
    parent_raw = read_pin(root, bundle["parent_contract"], c.CONFIG)
    read_pin(root, bundle["operational_amendment"], continuation.CONFIG)
    parent = c.load_contract(root, PARENT_SHA)  # Full assets/code rehashed once in this command.
    amendment = continuation.load_amendment(root, AMENDMENT_SHA)
    c.require(
        c.same(bundle["source_inventory"], parent["source_inventory"]),
        "PARENT_SOURCE_INVENTORY_PIN_CHANGED",
    )
    inventory_raw = read_pin(root, bundle["source_inventory"], parent["source_inventory"]["path"])
    inventory = c.strict_json(inventory_raw)
    phase_docs = {
        str(seed): {
            kind: c.strict_json(
                read_pin(root, bundle["phases"][str(seed)][kind], phase_path(seed, kind))
            )
            for kind in PHASE_KINDS
        }
        for seed in (11, 23, 47)
    }
    context = {
        "screen_contract_raw": parent_raw,
        "inventory_raw": inventory_raw,
        "final_result": phase_docs["47"]["result"],
        "final_verification": phase_docs["47"]["verification"],
        "verified_operational_amendment_sha256s": [AMENDMENT_SHA],
    }
    # ALL-stable final47 proof is required before opening even the approved NEW private input.
    plan = plan_module.build_plan(**context)
    for seed in (11, 23, 47):
        parent_finalizer.validate_previous(
            parent,
            amendment,
            phase_docs[str(seed)]["result"],
            phase_docs[str(seed)]["verification"],
        )
    input_raw = read_pin(root, bundle["new_screen_inputs"], NEW_INPUT_PATH)
    input_receipt = c.strict_json(
        read_pin(root, bundle["new_screen_input_receipt"], NEW_INPUT_RECEIPT)
    )
    c.require(
        c.same(input_receipt, parent_target.input_receipt(parent, inventory, input_raw)),
        "EXACT_NEW_SCREEN_INPUT_RECEIPT_REQUIRED",
    )
    inputs = verify_parent_evidence(root, parent, amendment, inventory, phase_docs)
    c.require(
        c.same(inputs, c.strict_json(input_raw)["rows"]), "NEW_INPUT_CHANGED_DURING_VERIFICATION"
    )
    # Detect concurrent mutation of the nine final SAFE artifacts after their raw replay.
    for seed in (11, 23, 47):
        for kind in PHASE_KINDS:
            read_pin(root, bundle["phases"][str(seed)][kind], phase_path(seed, kind))
    return {
        "parent": parent,
        "amendment": amendment,
        "source_context": context,
        "screen_inputs_raw": input_raw,
        "screen_input_receipt": input_receipt,
        "plan": plan,
        "inputs": inputs,
    }


def discover_sources(root):
    """Only fixed SAFE paths plus the explicitly approved NEW input artifact are eligible."""
    c.require(c.valid_sha(NEW_INPUT_SHA), "APPROVED_NEW_INPUT_PIN_NOT_FROZEN")
    parent_pin = file_descriptor(root, c.CONFIG)
    c.require(parent_pin["sha256"] == PARENT_SHA, "PARENT_CONTRACT_CHANGED")
    parent = c.strict_json(read_pin(root, parent_pin, c.CONFIG))
    # Stat and SHA checks occur on the exact approved NEW input path, never a caller path.
    input_path = owned(root, NEW_INPUT_PATH)
    c.require(
        input_path.is_file() and input_path.stat().st_size == NEW_INPUT_BYTES,
        "NEW_SCREEN_INPUT_MISSING_OR_OVERSIZED",
    )
    input_pin = {
        "path": NEW_INPUT_PATH,
        "size_bytes": NEW_INPUT_BYTES,
        "sha256": NEW_INPUT_SHA,
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA,
        "parent_contract": parent_pin,
        "operational_amendment": file_descriptor(root, continuation.CONFIG),
        "source_inventory": parent["source_inventory"],
        "new_screen_inputs": input_pin,
        "new_screen_input_receipt": file_descriptor(root, NEW_INPUT_RECEIPT),
        "phases": {
            str(seed): {kind: file_descriptor(root, phase_path(seed, kind)) for kind in PHASE_KINDS}
            for seed in (11, 23, 47)
        },
        "raw_parent_receipts_reverified": True,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "new_model_calls": 0,
        "execution_authorized": False,
    }
    bundle["source_bundle_identity_sha256"] = c.digest(bundle)
    return bundle


def preparation_paths(root, source_sha):
    c.require(c.valid_sha(source_sha), "PREPARATION_IDENTITY_INVALID")
    return {
        "safe": owned(root, PREP_SAFE + "/" + source_sha),
        "private": owned(root, PREP_PRIVATE + "/" + source_sha),
    }


def prepare(root):
    bundle = discover_sources(root)
    verified = load_sources(root, bundle)
    renderer = renderer_module.load(root)
    materials = target_module.prepare_materials(
        verified["plan"],
        verified["source_context"],
        verified["screen_inputs_raw"],
        verified["screen_input_receipt"],
        renderer,
    )
    source_sha = bundle["source_bundle_identity_sha256"]
    bases = preparation_paths(root, source_sha)
    reservation = owned(root, PREP_SAFE + "/preparation-reservation.safe.json")
    c.write_once(
        reservation,
        {
            "source_bundle_identity_sha256": source_sha,
            "execution_authorized": False,
            "new_model_calls": 0,
        },
    )
    outputs = (
        ("safe", "source-bundle.safe.json", bundle),
        ("safe", "plan.safe.json", verified["plan"]),
        ("safe", "bound-plan.safe.json", materials["bound_plan"]),
        ("private", "materializations.private.json", materials["private_materializations"]),
    )
    pins = {}
    for kind, name, value in outputs:
        path = c.contained(bases[kind], name)
        c.write_once(path, value)
        prefix = PREP_SAFE if kind == "safe" else PREP_PRIVATE
        pins[name] = file_descriptor(root, f"{prefix}/{source_sha}/{name}")
    receipt = {
        "schema_version": PREP_SCHEMA,
        "source_bundle_identity_sha256": source_sha,
        "files": pins,
        "bound_plan_identity_sha256": materials["bound_plan"]["plan_identity_sha256"],
        "n": materials["bound_plan"]["n"],
        "execution_authorized": False,
        "new_model_calls": 0,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "new_screen_input_sha256": NEW_INPUT_SHA,
    }
    c.write_once(bases["safe"] / "preparation.safe.json", receipt)
    return {
        key: receipt[key]
        for key in (
            "source_bundle_identity_sha256",
            "n",
            "execution_authorized",
            "new_model_calls",
            "historical_private_reads",
            "sealed_reads",
        )
    }


def load_preparation(root, source_sha, *, receipt_pin=None):
    bases = preparation_paths(root, source_sha)
    receipt_path = f"{PREP_SAFE}/{source_sha}/preparation.safe.json"
    receipt_pin = receipt_pin if receipt_pin is not None else file_descriptor(root, receipt_path)
    receipt = c.strict_json(read_pin(root, receipt_pin, receipt_path))
    c.require(
        set(receipt)
        == {
            "schema_version",
            "source_bundle_identity_sha256",
            "files",
            "bound_plan_identity_sha256",
            "n",
            "execution_authorized",
            "new_model_calls",
            "historical_private_reads",
            "sealed_reads",
            "new_screen_input_sha256",
        }
        and receipt["schema_version"] == PREP_SCHEMA
        and receipt["source_bundle_identity_sha256"] == source_sha
        and receipt["new_screen_input_sha256"] == NEW_INPUT_SHA
        and receipt["execution_authorized"] is False
        and all(
            c.same(receipt[key], 0)
            for key in ("new_model_calls", "historical_private_reads", "sealed_reads")
        ),
        "PREPARATION_RECEIPT_SCOPE_CHANGED",
    )
    names = {
        "source-bundle.safe.json",
        "plan.safe.json",
        "bound-plan.safe.json",
        "materializations.private.json",
    }
    c.require(set(receipt["files"]) == names, "PREPARATION_FILE_CLOSURE_CHANGED")
    documents = {}
    for name in sorted(names - {"materializations.private.json"}):
        prefix = PREP_SAFE
        documents[name] = c.strict_json(
            read_pin(root, receipt["files"][name], f"{prefix}/{source_sha}/{name}")
        )
    bundle = documents["source-bundle.safe.json"]
    c.require(
        bundle["source_bundle_identity_sha256"] == source_sha, "PREPARATION_SOURCE_BUNDLE_CHANGED"
    )
    verified = load_sources(root, bundle)
    documents["materializations.private.json"] = c.strict_json(
        read_pin(
            root,
            receipt["files"]["materializations.private.json"],
            f"{PREP_PRIVATE}/{source_sha}/materializations.private.json",
        )
    )
    c.require(
        c.same(documents["plan.safe.json"], verified["plan"]),
        "PREPARATION_UNBOUND_PLAN_NOT_RECONSTRUCTED",
    )
    prepared = target_module.prepare_materials(
        verified["plan"],
        verified["source_context"],
        verified["screen_inputs_raw"],
        verified["screen_input_receipt"],
        renderer_module.load(root),
    )
    c.require(
        c.same(prepared["bound_plan"], documents["bound-plan.safe.json"])
        and c.same(prepared["private_materializations"], documents["materializations.private.json"])
        and receipt["bound_plan_identity_sha256"] == prepared["bound_plan"]["plan_identity_sha256"]
        and c.same(receipt["n"], prepared["bound_plan"]["n"]),
        "PREPARATION_NOT_EXACTLY_REPLAYED_FROM_PINNED_RENDERER",
    )
    reservation = c.strict_json(
        owned(root, PREP_SAFE + "/preparation-reservation.safe.json").read_bytes()
    )
    c.require(
        c.same(
            reservation,
            {
                "source_bundle_identity_sha256": source_sha,
                "execution_authorized": False,
                "new_model_calls": 0,
            },
        ),
        "PREPARATION_RESERVATION_CHANGED",
    )
    return {
        **verified,
        "prepared": prepared,
        "bundle": bundle,
        "receipt": receipt,
        "receipt_pin": receipt_pin,
        "bases": bases,
    }


def expected_code_pins(root, parent, amendment):
    pins = {f"parent_{key}": value for key, value in parent["required_code"].items()}
    pins.update({f"amendment_{key}": value for key, value in amendment["required_code"].items()})
    for index, relative in enumerate(sorted(NEW_CODE)):
        pins[f"topology_{index:02d}"] = file_descriptor(root, relative)
    return pins


def make_template(root, preparation):
    parent, amendment = preparation["parent"], preparation["amendment"]
    bound = preparation["prepared"]["bound_plan"]
    template = {
        "schema_version": target_module.SCHEMA,
        "frozen": False,
        "execution_authorized": False,
        "frozen_at_utc": None,
        "evidence_class": "RESULT_INFORMED_EXPOSED_DEVELOPMENT_NOT_CONFIRMATION",
        "paper_validity": False,
        "parent_screen_contract_sha256": PARENT_SHA,
        "bound_plan_identity_sha256": bound["plan_identity_sha256"],
        "source_bundle_identity_sha256": preparation["bundle"]["source_bundle_identity_sha256"],
        "preparation": preparation["receipt_pin"],
        "protocol": file_descriptor(root, PROTOCOL),
        "required_code": expected_code_pins(root, parent, amendment),
        "budgets": bound["budgets"],
        "cooldown": target_module.COOLDOWN,
        "panel_cooldown": panel_module.COOLDOWN,
        "paths": {"safe_root": target_module.SAFE_ROOT, "private_root": target_module.PRIVATE_ROOT},
        "privacy": {
            "historical_private_reads_allowed": False,
            "sealed_reads_allowed": False,
            "new_screen_input_files": 1,
            "private_output_stdout_allowed": False,
        },
        **{
            key: parent[key]
            for key in (
                "model",
                "runtime",
                "server",
                "panel",
                "software",
                "generation",
                "context_tokens",
                "seeds",
                "execution_limits",
            )
        },
    }
    return c.strict_json(c.canonical(template))


def validate_execution(root, expected_sha):
    c.require(c.valid_sha(expected_sha), "EXECUTION_CONFIG_SHA_REQUIRED")
    path = owned(root, CONFIG)
    c.require(
        path.is_file() and 0 < path.stat().st_size <= MAX_BYTES,
        "EXECUTION_CONFIG_MISSING_OR_OVERSIZED",
    )
    raw = path.read_bytes()
    c.require(c.sha_bytes(raw) == expected_sha, "EXECUTION_CONFIG_SHA_MISMATCH")
    config = c.strict_json(raw)
    c.require(
        isinstance(config, dict)
        and not any(key.startswith("_") for key in config)
        and config.get("frozen") is True
        and config.get("execution_authorized") is True,
        "FROZEN_SEPARATE_EXECUTION_AUTHORITY_REQUIRED",
    )
    # Verify code/protocol bytes before invoking any preparation reader or parent verifier.
    c.require(isinstance(config.get("required_code"), dict), "EXECUTION_CODE_CLOSURE_REQUIRED")
    for pin in config["required_code"].values():
        c.verify_pin(root, pin, ("scripts/", "tests/", "src/"))
    c.require(
        {pin["path"] for pin in config["required_code"].values()} >= NEW_CODE,
        "ALL_NEW_TOPOLOGY_CODE_AND_TEST_PINS_REQUIRED",
    )
    c.require(config.get("protocol", {}).get("path") == PROTOCOL, "EXECUTION_PROTOCOL_PATH_CHANGED")
    c.verify_pin(root, config["protocol"], ("docs/",))
    preparation = load_preparation(
        root, config.get("source_bundle_identity_sha256"), receipt_pin=config.get("preparation")
    )
    expected = make_template(root, preparation)
    c.require(set(config) == set(expected), "EXECUTION_CONFIG_FIELD_CLOSURE_CHANGED")
    frozen_at = parent_target.parse_utc(config.get("frozen_at_utc"))
    c.require(
        parent_target.parse_utc(preparation["amendment"]["frozen_at_utc"])
        <= frozen_at
        < parent_target.parse_utc(expected["execution_limits"]["deadline_utc"]),
        "EXECUTION_FREEZE_TIMESTAMP_OUT_OF_SCOPE",
    )
    expected.update(frozen=True, execution_authorized=True, frozen_at_utc=config["frozen_at_utc"])
    c.require(c.same(config, expected), "EXECUTION_CONFIG_NOT_EXACT_APPROVED_TEMPLATE")
    # The self pin's physical location must agree with the code currently executing.
    self_pins = [pin for pin in config["required_code"].values() if pin["path"] == SCRIPT]
    c.require(
        len(self_pins) == 1
        and c.verify_pin(root, self_pins[0], ("scripts/",)) == Path(__file__).resolve(),
        "EXECUTION_LOADER_SELF_PIN_CHANGED",
    )
    config["_contract_sha256"] = expected_sha
    return {**preparation, "config": config}


def payloads_by_position(loaded):
    positions = {row["payload_position"] for row in loaded["prepared"]["bound_plan"]["population"]}
    return {
        row["payload_position"]: row["payload"]
        for row in loaded["inputs"]
        if row["condition"] == "DIRECT" and row["payload_position"] in positions
    }


def execute_command(root, expected_sha, command, *, axis=None, run_analysis=True):
    c.require(
        command in {"preflight", "census", "generate", "panel", "verify", "finalize"},
        "EXECUTION_COMMAND_FORBIDDEN",
    )
    loaded = validate_execution(root, expected_sha)
    if command == "preflight":
        return {
            "contract_sha256": expected_sha,
            "preflight_passed": True,
            "n": loaded["prepared"]["bound_plan"]["n"],
            "new_model_calls": 0,
            "historical_private_reads": 0,
            "sealed_reads": 0,
            "paper_validity": False,
        }
    worker = target_module.TopologyTarget(
        root, loaded["config"], loaded["prepared"]["bound_plan"], loaded["source_context"]
    )
    if command == "census":
        if not worker.path("safe", "materializations.safe.json").exists():
            worker.stage(loaded["prepared"])
        result = worker.census()
        return {
            key: result[key]
            for key in (
                "contract_sha256",
                "metadata_post_requests",
                "target_generations",
                "all_inputs_within_context",
            )
        }
    if command == "generate":
        return worker.generate()
    if command == "finalize":
        module = importlib.import_module("pa_llama_topology_finalize_v1")
        return module.finalize(
            worker,
            payloads_by_position(loaded),
            loaded["source_context"],
            run_analysis=run_analysis,
        )
    panel = panel_module.TopologyPanel(worker, payloads_by_position(loaded))
    if command == "panel":
        c.require(axis in {"qwen", "jailmeter"}, "EXACT_PANEL_AXIS_REQUIRED")
        result = panel.run(axis)
        return {
            "contract_sha256": expected_sha,
            "axis": axis,
            "complete": result["complete"],
            "paper_validity": False,
        }
    target = worker.status()
    verified = {key: panel.verify(key) for key in ("qwen", "jailmeter")}
    return {
        "contract_sha256": expected_sha,
        "target": target,
        "axis_identity_sha256": {key: c.digest(value) for key, value in verified.items()},
        "new_model_calls": 0,
        "paper_validity": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "template",
            "preflight",
            "census",
            "generate",
            "panel",
            "verify",
            "finalize",
        ),
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config-sha256")
    parser.add_argument("--preparation-sha256")
    parser.add_argument("--axis", choices=("qwen", "jailmeter"))
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.root)
        elif args.command == "template":
            result = make_template(args.root, load_preparation(args.root, args.preparation_sha256))
        else:
            result = execute_command(args.root, args.config_sha256, args.command, axis=args.axis)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2))
        return 0
    except BaseException as error:
        print(
            json.dumps(
                {
                    "completed": False,
                    "error_code": parent_target.safe_error_code(error),
                    "paper_validity": False,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
