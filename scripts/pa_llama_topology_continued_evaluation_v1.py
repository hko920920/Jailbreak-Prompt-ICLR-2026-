"""Explicit TARGET-continuation evaluation boundary, never an original-v1 pass.

The separately frozen continuation loader authenticates the parent closure and
supplies CompositeTarget. Only this module's new load gate admits its full raw-
reverified target frame. Frozen evaluator numerical execution is inherited; the
original target gate stays FALSE. All published products use new schemas and the
continuation namespace. No CLI or implicit execution entry point is provided.
"""

from __future__ import annotations

from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_panel_v1 as low
import pa_llama_topology_analysis_v1 as analysis
import pa_llama_topology_finalize_v1 as frozen_finalizer
import pa_llama_topology_materialize_v1 as materialize
import pa_llama_topology_panel_v1 as frozen_panel

SCRIPT = "scripts/pa_llama_topology_continued_evaluation_v1.py"
PARENT = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
SOURCE_BUNDLE = "fe0af6381817cddc6da856da69fccc2b7a9a282e8a4cce7707c81070f8489a82"
DEADLINE = "2026-09-05T22:55:47+00:00"
SCOPE = "RAW_ALL_1470_TARGET_RECEIPTS_WITH_EXPLICIT_CONTINUATION_NOT_ORIGINAL_OPERATIONAL_PASS"
PROOF_SCHEMA = "jbspan-pa-llama-topology-target-composite-verification-v1"
AXIS_SCHEMA = "jbspan-pa-llama-topology-continued-panel-axis-v1"
DISCLOSURE_KEYS = {
    "target_execution_amendment_sha256",
    "target_composite_verification_identity_sha256",
    "target_operational_amendment_disclosure",
    "original_target_operational_gate_passed",
    "target_continuation_is_not_fresh_scientific_confirmation",
    "retained_prefix_receipt_eligibility_reused_under_explicit_amendment",
    "control_operational_flag_is_not_original_generate_pass",
}
OUTPUTS = {
    "measurements": "continued-measurements.safe.json",
    "analysis": "continued-analysis.safe.json",
    "result": "continued-result.safe.json",
    "verification": "continued-verification.safe.json",
}


def clone(value):
    return c.strict_json(c.canonical(value))


def seal(value, key="result_identity_sha256"):
    value.pop(key, None)
    value[key] = c.digest(value)
    return value


def source_pin(target):
    """Actual use requires this exact executing source in the frozen amendment."""
    pins = target.amendment.get("required_code", {})
    c.require(isinstance(pins, dict), "CONTINUED_EVALUATION_CODE_CLOSURE_REQUIRED")
    matches = [pin for pin in pins.values() if pin.get("path") == SCRIPT]
    c.require(len(matches) == 1, "CONTINUED_EVALUATION_SELF_PIN_REQUIRED")
    c.require(
        c.verify_pin(target.root, matches[0], ("scripts/",)) == Path(__file__).resolve(),
        "CONTINUED_EVALUATION_SELF_PIN_MISMATCH",
    )


def normal_path(path):
    return str(Path(path).resolve()).removeprefix("\\\\?\\").casefold()


def authority(target):
    target.assert_amendment_unchanged()
    amendment = target.amendment
    sha = amendment.get("_amendment_sha256")
    c.require(
        c.valid_sha(sha)
        and amendment.get("frozen") is True
        and amendment.get("execution_authorized") is True,
        "CONTINUED_EVALUATION_FROZEN_AMENDMENT_REQUIRED",
    )
    source_pin(target)
    c.require(
        target.config.get("_contract_sha256") == PARENT
        and target.config.get("source_bundle_identity_sha256") == SOURCE_BUNDLE
        and target.plan.get("plan_identity_sha256") == PLAN
        and target.config.get("bound_plan_identity_sha256") == PLAN
        and target.config["execution_limits"]["deadline_utc"] == DEADLINE,
        "CONTINUED_EVALUATION_PARENT_SCOPE_CHANGED",
    )
    expected = {
        "safe": (
            f"data/natural_language_localization/pa_llama_topology_target_continuation_v1/{sha}"
        ),
        "private": f"artifacts/pa_llama_topology_target_continuation_v1/private/{sha}",
    }
    c.require(
        set(target.paths) == set(expected)
        and all(
            normal_path(target.paths[key]) == normal_path(c.contained(target.root, relative))
            for key, relative in expected.items()
        ),
        "CONTINUED_EVALUATION_SEPARATE_NAMESPACE_REQUIRED",
    )
    return sha


def verify_target_frame(target):
    """Explicit new readiness gate. Never changes summary().operational_gate_passed."""
    amendment_sha = authority(target)
    verified = target.verify_composite_targets()
    c.require(
        isinstance(verified, dict) and set(verified) == {"rows", "proof"},
        "COMPOSITE_TARGET_VERIFICATION_ENVELOPE_REQUIRED",
    )
    rows, proof = verified["rows"], verified["proof"]
    c.require(
        isinstance(rows, list) and len(rows) == 1470 and isinstance(proof, dict),
        "COMPOSITE_ALL1470_TARGETS_REQUIRED",
    )
    fields = {
        "schema_version",
        "original_contract_sha256",
        "amendment_sha256",
        "bound_plan_identity_sha256",
        "original_generate_operational_gate_passed",
        "original_operational_gate_passed",
        "amended_target_frame_verified",
        "amended_execution_gate_passed",
        "original_prefix_count",
        "continuation_count",
        "rows_identity_sha256",
        "original_prefix_rows_identity_sha256",
        "continuation_rows_identity_sha256",
        "prefix_manifest_sha256",
        "original_abort_pin",
        "failed_predispatch_cooldown_pin",
        "continuation_epoch_proofs",
        "original_prefix_all_reused",
        "no_ambiguous_dispatches",
        "scientific_rules_unchanged",
        "new_model_calls",
        "paper_validity",
        "verification_scope",
        "result_identity_sha256",
    }
    c.require(
        set(proof) == fields
        and c.valid_sha(proof.get("result_identity_sha256"))
        and proof["result_identity_sha256"]
        == c.digest({k: v for k, v in proof.items() if k != "result_identity_sha256"}),
        "COMPOSITE_TARGET_PROOF_SELF_IDENTITY",
    )
    expected = {
        "schema_version": PROOF_SCHEMA,
        "original_contract_sha256": PARENT,
        "amendment_sha256": amendment_sha,
        "bound_plan_identity_sha256": PLAN,
        "original_generate_operational_gate_passed": False,
        "original_operational_gate_passed": False,
        "amended_target_frame_verified": True,
        "amended_execution_gate_passed": True,
        "original_prefix_count": 872,
        "continuation_count": 598,
        "rows_identity_sha256": c.digest(rows),
        "original_prefix_rows_identity_sha256": c.digest(rows[:872]),
        "continuation_rows_identity_sha256": c.digest(rows[872:]),
        "original_prefix_all_reused": True,
        "no_ambiguous_dispatches": True,
        "scientific_rules_unchanged": True,
        "new_model_calls": 0,
        "paper_validity": False,
        "verification_scope": SCOPE,
    }
    c.require(
        all(c.same(proof.get(k), v) for k, v in expected.items()),
        "COMPOSITE_TARGET_READINESS_OR_ORIGINAL_FAILURE_DRIFT",
    )
    c.require(
        c.valid_sha(proof["prefix_manifest_sha256"])
        and proof["prefix_manifest_sha256"] == target.amendment["prefix_manifest"]["sha256"],
        "COMPOSITE_PREFIX_MANIFEST_FROZEN_PIN_DRIFT",
    )
    entries = target.prefix_manifest["files"]
    pins = {(entry["kind"], entry["relative"]): entry for entry in entries}
    c.require(len(pins) == len(entries), "COMPOSITE_DUPLICATE_PREFIX_PIN")
    failed = target.plan["requests"][872]["request_id"]
    for key, relative in (
        ("original_abort_pin", "generate-aborted.safe.json"),
        ("failed_predispatch_cooldown_pin", f"target/{failed}.cooldown.safe.json"),
    ):
        pin = proof[key]
        c.require(
            isinstance(pin, dict)
            and set(pin) == {"kind", "relative", "size_bytes", "sha256"}
            and pin["kind"] == "safe"
            and pin["relative"] == relative
            and type(pin["size_bytes"]) is int
            and pin["size_bytes"] > 0
            and c.valid_sha(pin["sha256"])
            and c.same(pin, pins.get(("safe", relative))),
            "COMPOSITE_EXACT_FAILED_EPOCH_PIN_REQUIRED",
        )
    requests = target.plan["requests"]
    c.require(
        len(requests) == 1470
        and len({item["request_id"] for item in requests}) == 1470
        and [row.get("request_id") for row in rows] == [item["request_id"] for item in requests]
        and all(
            row.get("contract_sha256") == PARENT
            and all(c.same(row.get(k), v) for k, v in item.items())
            for row, item in zip(rows, requests, strict=True)
        ),
        "COMPOSITE_EXACT_ORDERED_TARGET_PLAN_JOIN",
    )
    c.require(
        len(frozen_panel.science_frame(target.plan)) == 882, "COMPOSITE_ALL882_SCIENCE_REQUIRED"
    )
    c.require(
        sum(row["kind"] == "science" for row in rows[:872]) == 536
        and sum(row["kind"] == "control" for row in rows[:872]) == 336
        and sum(row["kind"] == "science" for row in rows[872:]) == 346
        and sum(row["kind"] == "control" for row in rows[872:]) == 252,
        "COMPOSITE_PREFIX_SUFFIX_KIND_COUNTS_CHANGED",
    )
    epoch_proofs = proof["continuation_epoch_proofs"]
    schedule = target.amendment["epoch_schedule"]
    c.require(
        isinstance(epoch_proofs, list)
        and len(epoch_proofs) == len(schedule) == 3
        and [part["epoch_index"] for part in schedule] == [3, 4, 5]
        and schedule[0]["first_ordinal"] == 873
        and schedule[-1]["last_ordinal"] == 1470
        and all(part["last_ordinal"] - part["first_ordinal"] + 1 <= 210 for part in schedule)
        and all(
            left["last_ordinal"] + 1 == right["first_ordinal"]
            for left, right in zip(schedule, schedule[1:], strict=False)
        ),
        "COMPOSITE_FIXED_THREE_EPOCH_FRAME_REQUIRED",
    )
    previous_stop = None
    for part, epoch in zip(schedule, epoch_proofs, strict=True):
        expected_binding = {
            "amendment_sha256": amendment_sha,
            "original_contract_sha256": PARENT,
            "bound_plan_identity_sha256": PLAN,
            **part,
            "prelaunch_minimum_disk_free_bytes": target.amendment[
                "prelaunch_minimum_disk_free_bytes"
            ],
        }
        subset = rows[part["first_ordinal"] - 1 : part["last_ordinal"]]
        c.require(
            isinstance(epoch, dict)
            and set(epoch)
            == {"epoch_binding", "lifecycle", "target_count", "target_rows_identity_sha256"}
            and c.same(epoch["epoch_binding"], expected_binding)
            and c.same(epoch["target_count"], len(subset))
            and epoch["target_rows_identity_sha256"] == c.digest(subset),
            "COMPOSITE_EPOCH_MAPPING_OR_ROW_BINDING_CHANGED",
        )
        life = epoch["lifecycle"]
        c.require(
            isinstance(life, dict)
            and life.get("contract_sha256") == PARENT
            and c.same(life.get("epoch"), 1)
            and life.get("owned_process_only") is True
            and type(life.get("pid")) is int
            and life["pid"] > 0,
            "COMPOSITE_EPOCH_OWNED_LIFECYCLE_REQUIRED",
        )
        start, stop = (
            low.validate_timestamp(life["started_at"]),
            low.validate_timestamp(life["stopped_at"]),
        )
        c.require(
            start <= stop
            and (previous_stop is None or previous_stop <= start)
            and all(
                c.same(row.get("epoch_index"), part["epoch_index"])
                and c.same(row.get("process_id"), life["pid"])
                for row in subset
            ),
            "COMPOSITE_EPOCH_ORDER_OR_PID_CHANGED",
        )
        previous_stop = stop
    status = target.summary(rows)
    c.require(
        status.get("operational_gate_passed") is False
        and status.get("original_generate_operational_gate_passed") is False,
        "ORIGINAL_TARGET_OPERATIONAL_GATE_MUST_REMAIN_FALSE",
    )
    target.assert_amendment_unchanged()
    return rows, clone(proof)


def disclosure(proof):
    return {
        "target_execution_amendment_sha256": proof["amendment_sha256"],
        "target_composite_verification_identity_sha256": proof["result_identity_sha256"],
        "target_operational_amendment_disclosure": clone(proof),
        "original_target_operational_gate_passed": False,
        "target_continuation_is_not_fresh_scientific_confirmation": True,
        "retained_prefix_receipt_eligibility_reused_under_explicit_amendment": True,
        "control_operational_flag_is_not_original_generate_pass": True,
    }


class AmendedTopologyPanel(frozen_panel.TopologyPanel):
    """New readiness gate; same frozen requests/parsers/model settings and lifecycle."""

    def __init__(self, target, payloads_by_position):
        self.amendment_sha256 = authority(target)
        self._target_proof = None
        super().__init__(target, payloads_by_position)

    def load(self, axis):
        c.require(axis in low.AXES, "CONTINUED_PANEL_AXIS_INVALID")
        self.no_axis_abort(axis)
        c.require(
            c.same(self.target.config, self.config)
            and c.same(self.target.plan, self.plan)
            and authority(self.target) == self.amendment_sha256,
            "CONTINUED_PANEL_CONTEXT_MUTATED",
        )
        targets, proof = verify_target_frame(self.target)
        if self._target_proof is not None:
            c.require(c.same(proof, self._target_proof), "CONTINUED_TARGET_PROOF_CHANGED")
        self._target_proof = proof
        # The only changed boundary is above. These are the original load numerics.
        low.preflight(self.root, self.config)
        raw = {
            item["request_id"]: low.read_bytes(
                self.target.path("private", f"target/{item['request_id']}.reply.private.json"),
                2_000_000,
            )
            for item in self.frame
        }
        from transformers import AutoTokenizer

        runtime = self.config["panel"][axis]
        helpers = low.load_pure_functions(self.root, self.config)
        if axis == "qwen":
            tokenizer = AutoTokenizer.from_pretrained(
                c.contained(self.root, runtime["model_local_path"]), local_files_only=True
            )
            system = None
        else:
            tokenizer = AutoTokenizer.from_pretrained(
                c.contained(self.root, runtime["base_metadata_local_path"]),
                local_files_only=True,
                trust_remote_code=True,
            )
            system = helpers.extract_system_prompt(c.contained(self.root, runtime["runner_path"]))
        return (
            frozen_panel.prepare_values(
                self.config,
                self.plan,
                targets,
                self.payloads,
                raw,
                helpers,
                tokenizer,
                axis,
                system,
            ),
            helpers,
            tokenizer,
        )

    def binding(self, axis, value):
        c.require(self._target_proof is not None, "CONTINUED_TARGET_PROOF_NOT_LOADED")
        return {
            **super().binding(axis, value),
            "target_execution_amendment_sha256": self.amendment_sha256,
            "target_composite_verification_identity_sha256": self._target_proof[
                "result_identity_sha256"
            ],
        }

    def worker_binding(self, axis):
        value = super().worker_binding(axis)
        return {
            **value,
            "target_execution_amendment_sha256": self.amendment_sha256,
            "worker_identity_sha256": c.digest([PARENT, self.amendment_sha256, axis, 1]),
        }

    def no_axis_abort(self, axis):
        c.require(
            not self.path(axis, "abort.safe.json").exists()
            and not self.target.path("safe", f"panel-{axis}-aborted.safe.json").exists(),
            "CONTINUED_PANEL_NEW_ABORT_NO_REENTRY",
        )

    def temporal_order(self, axis, result):
        """Additional amendment/phase binding, after unchanged lifecycle validation."""
        frozen = low.validate_timestamp(self.target.amendment["frozen_at_utc"])
        target_stop = max(
            low.validate_timestamp(epoch["lifecycle"]["stopped_at"])
            for epoch in self._target_proof["continuation_epoch_proofs"]
        )
        lower = max(frozen, target_stop)
        if axis == "jailmeter":
            # Qwen verify never calls this JailMeter branch: no recursion cycle.
            qwen = self.verify("qwen")
            if qwen["dispatched"]:
                qwen_stop = low.read_json(self.path("qwen", "worker.stopped.safe.json"))
                lower = max(lower, low.validate_timestamp(qwen_stop["stopped_at"]))
        if not result["dispatched"]:
            # The inherited lifecycle already proves no worker/resources were invented.
            return
        start = low.read_json(self.path(axis, "worker.started.safe.json"))
        c.require(
            low.validate_timestamp(start["started_at"]) >= lower,
            "CONTINUED_PANEL_START_BEFORE_AMENDMENT_OR_PREVIOUS_PHASE_RELEASE",
        )
        samples = low.read_bytes(self.path(axis, "samples.safe.jsonl"), maximum=32_000_000)
        c.require(
            all(
                low.validate_timestamp(low.strict(line)["recorded_at"]) >= lower
                for line in samples.splitlines()
            ),
            "CONTINUED_PANEL_SAMPLE_BEFORE_AMENDMENT_OR_PREVIOUS_PHASE_RELEASE",
        )

    def result(self, axis, rows, values):
        self.no_axis_abort(axis)
        c.require(
            self._target_proof is not None and authority(self.target) == self.amendment_sha256,
            "CONTINUED_AXIS_PROOF_REQUIRED",
        )
        result = super().result(axis, rows, values)
        self.temporal_order(axis, result)
        result.update(schema_version=AXIS_SCHEMA, **disclosure(self._target_proof))
        return result

    def verify(self, axis):
        values, helpers, tokenizer = self.load(axis)
        rows, pending = self.collect(axis, values, helpers, tokenizer, write_skips=False)
        c.require(not pending, "CONTINUED_PANEL_VERIFICATION_INCOMPLETE")
        expected = self.result(axis, rows, values)
        saved = low.read_bytes(self.path(axis, "axis.safe.json"), maximum=32_000_000)
        c.require(saved == c.canonical(expected) + b"\n", "CONTINUED_PANEL_EXACT_SAVED_AXIS_DRIFT")
        return expected

    def run(self, axis):
        # Sequential evaluator order is prospective, not an outcome-based choice.
        if axis == "jailmeter":
            self.verify("qwen")
        return super().run(axis)


def scientific_axis_projection(axis_result, axis, proof):
    """In-memory adapter solely for frozen PURE scientific joins; never published."""
    c.require(
        isinstance(axis_result, dict)
        and axis_result.get("schema_version") == AXIS_SCHEMA
        and axis_result.get("axis") == axis
        and all(c.same(axis_result.get(k), v) for k, v in disclosure(proof).items()),
        "CONTINUED_AXIS_AMENDMENT_BINDING_REQUIRED",
    )
    core = {k: clone(v) for k, v in axis_result.items() if k not in DISCLOSURE_KEYS}
    core["schema_version"] = "jbspan-pa-llama-topology-panel-axis-v1"
    return core


def decorate_products(products, axes, proof):
    """Rebind every published product after adding the separate TARGET disclosure."""
    products = clone(products)
    shared = disclosure(proof)
    measured, analyzed, result = (products[k] for k in ("measurements", "analysis", "result"))
    tables = measured["tables"]
    tables.update(schema_version="jbspan-pa-llama-topology-continued-measurement-v1", **shared)
    seal(tables)
    if analyzed is not None:
        analyzed.update(schema_version="jbspan-pa-llama-topology-continued-analysis-v1", **shared)
        analyzed["upstream_declared_topology_aggregate_identity_sha256"] = tables[
            "result_identity_sha256"
        ]
        seal(analyzed)
    measured.update(
        schema_version="jbspan-pa-llama-topology-continued-joined-measurements-v1", **shared
    )
    seal(measured)
    result.update(schema_version="jbspan-pa-llama-topology-continued-finalization-v1", **shared)
    result.update(
        measurements_identity_sha256=measured["result_identity_sha256"],
        table_identity_sha256=tables["result_identity_sha256"],
        analysis_identity_sha256=analyzed["result_identity_sha256"]
        if analyzed is not None
        else None,
        axis_identity_sha256={axis: c.digest(value) for axis, value in axes.items()},
        original_v1_finalization_pass_claimed=False,
        epoch_invariance_or_independent_epoch_replication_claimed=False,
    )
    seal(result)
    return products


def publish(target, products):
    """New names and namespace, exact-byte replay, validate all before proof-last writes."""
    authority(target)
    c.require(
        set(products) == set(OUTPUTS) and list(products)[-1] == "verification",
        "CONTINUED_PUBLICATION_PROOF_LAST_REQUIRED",
    )
    validate_products(target, products)
    if target.path("safe", OUTPUTS["verification"]).exists():
        c.require(
            all(
                target.path("safe", OUTPUTS[key]).is_file()
                for key, value in products.items()
                if value is not None
            ),
            "CONTINUED_ORPHAN_PROOF_NO_REPAIR",
        )
    for key, value in products.items():
        path = target.path("safe", OUTPUTS[key])
        if value is None:
            c.require(not path.exists(), "CONTINUED_DEFERRED_ANALYSIS_ALREADY_EXISTS")
        elif path.exists():
            c.require(
                low.read_bytes(path, maximum=32_000_000) == c.canonical(value) + b"\n",
                "CONTINUED_EXISTING_PRODUCT_BYTES_CHANGED",
            )
    for key in OUTPUTS:
        value = products[key]
        if value is not None and not target.path("safe", OUTPUTS[key]).exists():
            target.write("safe", OUTPUTS[key], value)


def validate_products(target, products):
    """Check new disclosure and all product joins before any publication write."""
    measured, analyzed, result, proof = (
        products[key] for key in ("measurements", "analysis", "result", "verification")
    )
    tables = measured["tables"]
    target_proof = proof["target_operational_amendment_disclosure"]
    shared = disclosure(target_proof)
    c.require(
        target_proof["amendment_sha256"] == target.amendment["_amendment_sha256"]
        and target_proof["result_identity_sha256"]
        == c.digest({k: v for k, v in target_proof.items() if k != "result_identity_sha256"}),
        "CONTINUED_PUBLICATION_TARGET_PROOF_CHANGED",
    )
    expected_schemas = (
        (tables, "measurement"),
        (measured, "joined-measurements"),
        (result, "finalization"),
        (analyzed, "analysis"),
    )
    for value, kind in expected_schemas:
        if value is None:
            continue
        c.require(
            value.get("schema_version") == f"jbspan-pa-llama-topology-continued-{kind}-v1"
            and all(c.same(value.get(k), v) for k, v in shared.items())
            and value.get("result_identity_sha256")
            == c.digest({k: v for k, v in value.items() if k != "result_identity_sha256"}),
            "CONTINUED_PUBLICATION_PRODUCT_SCHEMA_IDENTITY_OR_DISCLOSURE",
        )
    c.require(
        proof.get("schema_version") == "jbspan-pa-llama-topology-continued-final-verification-v1"
        and all(c.same(proof.get(k), v) for k, v in shared.items())
        and proof.get("verification_identity_sha256")
        == c.digest({k: v for k, v in proof.items() if k != "verification_identity_sha256"}),
        "CONTINUED_PUBLICATION_PROOF_IDENTITY_OR_DISCLOSURE",
    )
    c.require(
        result.get("measurements_identity_sha256") == measured["result_identity_sha256"]
        and result.get("table_identity_sha256") == tables["result_identity_sha256"]
        and result.get("analysis_identity_sha256")
        == (analyzed["result_identity_sha256"] if analyzed is not None else None)
        and result.get("analysis_complete") is (analyzed is not None)
        and proof.get("analysis_complete") is (analyzed is not None)
        and (
            analyzed is None
            or analyzed.get("upstream_declared_topology_aggregate_identity_sha256")
            == tables["result_identity_sha256"]
        ),
        "CONTINUED_PUBLICATION_INNER_PRODUCT_JOIN_CHANGED",
    )
    core = {
        key: value for key, value in products.items() if key != "verification" and value is not None
    }
    c.require(
        proof.get("result_identity_sha256") == result["result_identity_sha256"]
        and c.same(
            proof.get("product_identity_sha256"),
            {key: value["result_identity_sha256"] for key, value in core.items()},
        )
        and c.same(
            proof.get("product_file_sha256"),
            {key: c.sha_bytes(c.canonical(value) + b"\n") for key, value in core.items()},
        )
        and c.same(proof.get("axis_identity_sha256"), result.get("axis_identity_sha256"))
        and all(
            c.same(
                value.get("parent_operational_amendment_disclosure"),
                target.plan["parent_operational_amendment_disclosure"],
            )
            for value in (result, proof)
        )
        and all(
            value.get("original_v1_finalization_pass_claimed") is False
            and value.get("epoch_invariance_or_independent_epoch_replication_claimed") is False
            for value in (result, proof)
        )
        and proof.get("original_target_operational_pass_claimed") is False,
        "CONTINUED_PUBLICATION_PROOF_JOINS_OR_FAILURE_DISCLOSURE_CHANGED",
    )


def finalize(target, payloads_by_position, source_context, *, run_analysis=True):
    """All targets AND both complete axes required even when analysis is deferred."""
    c.require(type(run_analysis) is bool, "CONTINUED_ANALYSIS_FLAG_BOOLEAN_REQUIRED")
    with target.operation("finalize"):
        targets, target_proof = verify_target_frame(target)
        evaluator = AmendedTopologyPanel(target, payloads_by_position)
        axes = {axis: evaluator.verify(axis) for axis in ("qwen", "jailmeter")}
        c.require(
            c.same(evaluator._target_proof, target_proof), "CONTINUED_FINAL_TARGET_PROOF_DRIFT"
        )
        helpers = low.load_pure_functions(target.root, target.config)
        renderer = materialize.load(target.root)
        tasks = {task["id"]: task["text"] for task in renderer.tasks}
        control_raw = {
            item["request_id"]: low.read_bytes(
                target.path("private", f"target/{item['request_id']}.reply.private.json"), 2_000_000
            )
            for item in target.plan["requests"]
            if item["kind"] == "control"
        }
        products = frozen_finalizer.build_artifacts(
            target.config,
            target.plan,
            source_context,
            targets,
            {
                axis: scientific_axis_projection(value, axis, target_proof)
                for axis, value in axes.items()
            },
            helpers,
            control_raw,
            tasks,
            reference=analysis.load_reference_functions(target.root) if run_analysis else None,
            run_analysis=run_analysis,
        )
        products = decorate_products(products, axes, target_proof)
        proof = {
            "schema_version": "jbspan-pa-llama-topology-continued-final-verification-v1",
            "original_contract_sha256": PARENT,
            "finalizer_source_path": SCRIPT,
            **disclosure(target_proof),
            "result_identity_sha256": products["result"]["result_identity_sha256"],
            "product_identity_sha256": {
                key: value["result_identity_sha256"]
                for key, value in products.items()
                if value is not None
            },
            "product_file_sha256": {
                key: c.sha_bytes(c.canonical(value) + b"\n")
                for key, value in products.items()
                if value is not None
            },
            "axis_identity_sha256": products["result"]["axis_identity_sha256"],
            "parent_operational_amendment_disclosure": target.plan[
                "parent_operational_amendment_disclosure"
            ],
            "source_bundle_identity_sha256": SOURCE_BUNDLE,
            "target_composite_raw_receipts_reverified": True,
            "new_evaluator_raw_receipts_reverified": True,
            "new_panel_lifecycle_and_resource_receipts_verified": True,
            "independent_frozen_panel_rule_verified": True,
            "control_raw_hash_and_content_rechecked": True,
            "all1470_targets_and_both882_science_axes_retained": True,
            "original_target_operational_pass_claimed": False,
            "original_v1_finalization_pass_claimed": False,
            "epoch_invariance_or_independent_epoch_replication_claimed": False,
            "analysis_complete": run_analysis,
            "paper_validity": False,
            "execution_authorized": False,
            "new_model_calls": 0,
            "historical_private_reads": 0,
            "sealed_reads": 0,
        }
        seal(proof, "verification_identity_sha256")
        products["verification"] = proof
        authority(target)
        publish(target, products)
        return {
            **products["result"],
            "verification_identity_sha256": proof["verification_identity_sha256"],
        }
