"""Separately authorized resumable evaluators; frozen science, new operational epochs.

No import-time model, GPU, network or private I/O. Actual workers are accessible
only through run(), a bounded stage authorization and a launch-ready pinned
target factory. Checkpoints never authorize dispatch and ambiguous intents are
never repeated. Frozen v1 files and their failed operational gates stay intact.
"""

from __future__ import annotations

import copy
import os
import time
from contextlib import contextmanager
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_jailmeter_continuation_v1 as thermal
import pa_llama_development_panel_v1 as low
import pa_llama_topology_panel_v1 as frozen
import pa_reentry_journal_v2 as journal

PARENT = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
FAILURES = (
    "DISK_FREE_SPACE_BELOW_15_GIB",
    "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
)
AXES = ("qwen", "jailmeter")
SCHEMA = "pa-reentry-panel-axis-v2"


def seal(value, key="proof_identity_sha256"):
    value.pop(key, None)
    value[key] = c.digest(value)
    return value


def stamp(value):
    return low.validate_timestamp(value)


def owned(base, relative):
    path = c.contained(base, relative)
    if os.name == "nt" and not str(path).startswith("\\\\?\\"):
        path = Path("\\\\?\\" + str(path))
    return path


def read_lines(path):
    raw = low.read_bytes(path, maximum=32_000_000)
    c.require(not raw or raw.endswith(b"\n"), "REENTRY_PANEL_TRUNCATED_RESOURCE_JOURNAL")
    return [low.strict(line) for line in raw.splitlines()]


def memory_diagnostic():
    """Diagnostic only: no new RAM/pagefile exclusion threshold."""
    try:
        import psutil

        ram, swap = psutil.virtual_memory(), psutil.swap_memory()
        result = {
            "ram_total_bytes": int(ram.total),
            "ram_available_bytes": int(ram.available),
            "ram_percent": float(ram.percent),
            "pagefile_total_bytes": int(swap.total),
            "pagefile_used_bytes": int(swap.used),
            "pagefile_measurement": (
                "PSUTIL_DERIVED_SWAP_FROM_COMMIT_NOT_DIRECT_PAGEFILE_ALLOCATION"
            ),
            "direct_pagefile_allocation_measured": False,
            "diagnostic_only": True,
        }
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong)
                    for name in (
                        "total_phys",
                        "avail_phys",
                        "total_pagefile",
                        "avail_pagefile",
                        "total_virtual",
                        "avail_virtual",
                        "avail_extended_virtual",
                    )
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                limit, available = int(status.total_pagefile), int(status.avail_pagefile)
                result.update(
                    commit_limit_bytes=limit,
                    commit_available_bytes=available,
                    commit_used_bytes=limit - available,
                    commit_percent=(100 * (limit - available) / limit) if limit else None,
                )
        return result
    except Exception as error:
        return {"diagnostic_only": True, "observation_error": low.safe_error_code(error)}


class EpochRuntime:
    """Duck-typed context for the EXACT frozen worker, not its old run/gate."""

    def __init__(self, adapter, axis, index, authorization):
        self.adapter, self.root, self.axis, self.index = adapter, adapter.root, axis, index
        self.authorization = copy.deepcopy(authorization)
        self.config = copy.deepcopy(adapter.config)
        # This is an explicit operational projection, never the old contract truth.
        self.config["execution_limits"]["deadline_utc"] = authorization["expires_at"]
        self.config["frozen_at_utc"] = authorization["issued_at"]
        self.config["operational_execution_identity"] = adapter.execution_identity

    def path(self, axis, suffix, *, private=False):
        c.require(axis == self.axis, "REENTRY_WORKER_AXIS_CHANGED")
        return self.adapter.epoch_path(axis, self.index, suffix, private=private)

    def worker_binding(self, axis):
        c.require(axis == self.axis, "REENTRY_WORKER_AXIS_CHANGED")
        return {
            "execution_identity": self.adapter.execution_identity,
            "original_contract_sha256": PARENT,
            "bound_plan_identity_sha256": PLAN,
            "stage": axis,
            "epoch_index": self.index,
            "authorization_identity_sha256": self.authorization["authorization_identity_sha256"],
            "worker_identity_sha256": c.digest(
                [
                    self.adapter.execution_identity,
                    axis,
                    self.index,
                    self.authorization["authorization_identity_sha256"],
                ]
            ),
        }


@contextmanager
def default_runtime(adapter, axis, epoch, tokenizer, sampler, authorization):
    c.require(
        getattr(adapter.target, "launch_ready", False) is True,
        "REENTRY_PINNED_LAUNCH_READY_FACTORY_REQUIRED",
    )
    adapter.target.assert_launch_ready()
    runtime = EpochRuntime(adapter, axis, epoch, authorization)
    with frozen.TopologyPanel.worker(runtime, axis, tokenizer, sampler) as worker:
        yield worker


class ReentryPanel:
    def __init__(self, target, payloads_by_position, safe, private, execution_identity):
        self.target, self.root = target, Path(target.root).resolve()
        self.config, self.plan = copy.deepcopy(target.config), copy.deepcopy(target.plan)
        self.payloads = dict(payloads_by_position)
        self.safe, self.private = Path(safe), Path(private)
        self.execution_identity = execution_identity
        c.require(
            c.valid_sha(execution_identity) and execution_identity == target.execution_identity,
            "REENTRY_PANEL_EXECUTION_IDENTITY",
        )
        c.require(
            self.config["_contract_sha256"] == PARENT
            and self.plan["plan_identity_sha256"] == PLAN
            and self.plan["n"] == 21,
            "REENTRY_PANEL_ORIGINAL_SCOPE",
        )
        self.frame = frozen.science_frame(self.plan)
        c.require(
            len(self.frame) == 882 and len(self.plan["requests"]) == 1470,
            "REENTRY_PANEL_ALL1470_AND882_REQUIRED",
        )
        c.require(self.safe.resolve() != self.private.resolve(), "REENTRY_PANEL_SEPARATE_PATHS")
        expected_safe = c.contained(
            self.root, f"data/natural_language_localization/pa_reentry_v2/{execution_identity}"
        )
        expected_private = c.contained(
            self.root, f"artifacts/pa_reentry_v2/private/{execution_identity}"
        )

        def normalized(path):
            return str(Path(path).resolve()).removeprefix("\\\\?\\").casefold()

        c.require(
            normalized(self.safe) == normalized(expected_safe)
            and normalized(self.private) == normalized(expected_private),
            "REENTRY_PANEL_EXACT_NEW_EXECUTION_NAMESPACE_REQUIRED",
        )
        c.require(
            self.config["panel"]["qwen"]["max_new_tokens"] == 128
            and self.config["panel"]["qwen"]["do_sample"] is False
            and self.config["panel"]["jailmeter"]["max_new_tokens"] == 1536
            and self.config["panel"]["jailmeter"]["temperature"] == 0
            and self.config["panel"]["jailmeter"]["request_timeout_seconds"] == 240,
            "REENTRY_PANEL_SCIENTIFIC_NUMERICS_CHANGED",
        )
        self._context_digest = c.digest([self.config, self.plan])
        self._target_proof = None

    def axis_path(self, axis, relative, *, private=False):
        c.require(axis in AXES, "REENTRY_PANEL_STAGE_INVALID")
        return owned(self.private if private else self.safe, f"panel/{axis}/{relative}")

    def epoch_path(self, axis, index, relative, *, private=False):
        c.require(type(index) is int and index > 0, "REENTRY_PANEL_EPOCH_INDEX")
        return self.axis_path(axis, f"epochs/{index:04d}/{relative}", private=private)

    def journal(self, axis):
        return journal.Journal(
            self.axis_path(axis, "journal"),
            self.axis_path(axis, "journal", private=True),
            self.execution_identity,
            axis,
        )

    def verify_targets(self):
        c.require(
            c.digest([self.target.config, self.target.plan]) == self._context_digest,
            "REENTRY_PANEL_TARGET_CONTEXT_MUTATED",
        )
        rows, proof = self.target.verify_complete()
        c.require(
            isinstance(proof, dict)
            and proof.get("schema_version") == "pa-reentry-target-composite-v2"
            and proof.get("proof_identity_sha256")
            == c.digest({k: v for k, v in proof.items() if k != "proof_identity_sha256"}),
            "REENTRY_PANEL_TARGET_PROOF_IDENTITY",
        )
        expected = {
            "execution_identity": self.execution_identity,
            "original_contract_sha256": PARENT,
            "bound_plan_identity_sha256": PLAN,
            "target_records": 1470,
            "reused_target_records": 1082,
            "new_target_records": 388,
            "target_rows_sha256": c.digest(rows),
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
            "composite_target_complete": True,
            "scientific_gate_evaluated": False,
            "paper_validity": False,
        }
        c.require(
            all(c.same(proof.get(k), v) for k, v in expected.items())
            and proof.get("prior_operation_failures") == list(FAILURES)
            and isinstance(proof.get("missing_stop_epochs"), list)
            and c.valid_sha(proof.get("archive_manifest_identity_sha256")),
            "REENTRY_PANEL_TARGET_FAILURE_OR_COMPLETENESS_CHANGED",
        )
        c.require(
            proof["archive_manifest_identity_sha256"] == self.target.manifest_identity,
            "REENTRY_PANEL_ARCHIVE_MANIFEST_IDENTITY_CHANGED",
        )
        stamp(proof["latest_target_release_at"])
        attempts = proof.get("all_attempts")
        c.require(
            isinstance(attempts, list)
            and bool(attempts)
            and proof.get("all_attempts_sha256") == c.digest(attempts)
            and proof.get("archive_relocation_contemporaneous_receipt_available") is False
            and proof.get("failed_prelaunch_attempts")
            == sum(a.get("status") == "REJECTED_PRELAUNCH" for a in attempts)
            and stamp(proof["latest_target_release_at"])
            == max(stamp(a["release_at"]) for a in attempts),
            "REENTRY_PANEL_TARGET_ALL_ATTEMPTS_OR_ARCHIVE_LIMITATION_CHANGED",
        )
        c.require(
            isinstance(rows, list)
            and len(rows) == 1470
            and [r["request_id"] for r in rows] == [r["request_id"] for r in self.plan["requests"]],
            "REENTRY_PANEL_TARGET_FRAME_CHANGED",
        )
        if self._target_proof is not None:
            c.require(c.same(proof, self._target_proof), "REENTRY_PANEL_TARGET_PROOF_MUTATED")
        self._target_proof = copy.deepcopy(proof)
        return rows, proof

    def load(self, axis):
        c.require(axis in AXES, "REENTRY_PANEL_STAGE_INVALID")
        rows, _ = self.verify_targets()
        low.preflight(self.root, self.config)
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
        raw = {item["request_id"]: self.target.raw_reply(item["request_id"]) for item in self.frame}
        values = frozen.prepare_values(
            self.config, self.plan, rows, self.payloads, raw, helpers, tokenizer, axis, system
        )
        return values, helpers, tokenizer

    def binding(self, axis, value):
        c.require(self._target_proof is not None, "REENTRY_PANEL_TARGET_NOT_VERIFIED")
        return {
            "execution_identity": self.execution_identity,
            "original_contract_sha256": PARENT,
            "bound_plan_identity_sha256": PLAN,
            "stage": axis,
            "topology_item": copy.deepcopy(value["topology_item"]),
            "target_row_sha256": c.digest(value["target"]),
            "target_composite_proof_sha256": self._target_proof["proof_identity_sha256"],
            "frozen_row_binding_sha256": c.digest(low.bound_row(self.config, value, axis)),
        }

    def parser(self, axis, value, helpers, tokenizer):
        expected_binding = self.binding(axis, value)
        body = low.request_body(self.config, value, axis)

        def parse(raw, meta, intent):
            c.require(
                c.same(intent["binding"], expected_binding)
                and intent["request_sha256"] == c.digest(body),
                "REENTRY_PANEL_RAW_INTENT_CHANGED",
            )
            c.require(c.sha_bytes(raw) == meta["raw_sha256"], "REENTRY_PANEL_RAW_HASH_CHANGED")
            epoch = intent["epoch"]
            c.require(
                epoch["execution_identity"] == self.execution_identity and epoch["stage"] == axis,
                "REENTRY_PANEL_EPOCH_STAGE_CHANGED",
            )
            dispatch = {
                **low.bound_row(self.config, value, axis),
                "dispatch_at": intent["dispatch_at"],
                "request_sha256": c.digest(body),
                "resume_allowed": False,
            }
            if axis == "jailmeter":
                c.require(
                    type(epoch.get("process_id")) is int
                    and epoch["process_id"] > 0
                    and c.valid_sha(epoch.get("server_command_sha256")),
                    "REENTRY_PANEL_JAILMETER_PROCESS_BINDING",
                )
                dispatch.update(
                    process_id=epoch["process_id"],
                    server_command_sha256=epoch["server_command_sha256"],
                )
            if axis == "qwen":
                reply = low.strict(raw)
                c.require(
                    isinstance(reply, dict) and set(reply) == {"content", "output_ids"},
                    "REENTRY_PANEL_QWEN_RAW_SCHEMA",
                )
                low.validate_qwen_reply(reply["content"], reply["output_ids"], self.config)
                c.require(
                    tokenizer.decode(reply["output_ids"], skip_special_tokens=True)
                    == reply["content"],
                    "REENTRY_PANEL_QWEN_IDS_CONTENT_CHANGED",
                )
                row = low.qwen_result(
                    self.config,
                    value,
                    helpers,
                    reply["content"],
                    reply["output_ids"],
                    meta["elapsed_seconds"],
                    dispatch,
                    raw,
                )
            else:
                row = low.jailmeter_result(
                    self.config, value, helpers, raw, meta["elapsed_seconds"], dispatch
                )
            row["received_at"] = meta["received_at"]
            c.require(
                stamp(row["dispatch_at"]) <= stamp(row["received_at"]),
                "REENTRY_PANEL_RECEIVE_BEFORE_DISPATCH",
            )
            return row

        return parse

    def state(self, axis, value, helpers, tokenizer, *, recover=False):
        skip = low.skipped_row(self.config, value, axis) if value["skip_reason"] else None
        store = self.journal(axis)
        method = store.recover if recover else store.inspect
        return method(
            value["item"]["request_id"],
            low.request_body(self.config, value, axis),
            self.binding(axis, value),
            self.parser(axis, value, helpers, tokenizer),
            skip_row=skip,
        )

    def inspect(self, axis):
        values, helpers, tokenizer = self.load(axis)
        states = [self.state(axis, value, helpers, tokenizer) for value in values]
        return {
            "schema_version": "pa-reentry-panel-inventory-v2",
            "execution_identity": self.execution_identity,
            "stage": axis,
            "planned": 882,
            "states": states,
            "target_proof": copy.deepcopy(self._target_proof),
            "operational_certification": False,
            "new_model_calls": 0,
        }

    def recover(self, axis, authorization):
        journal.validate_authorization(authorization, self.execution_identity, axis)
        with journal.run_lock(owned(self.safe, "panel-operation.lock")):
            values, helpers, tokenizer = self.load(axis)
            existing = [self.state(axis, value, helpers, tokenizer) for value in values]
            c.require(
                all(s["state"] != "AMBIGUOUS" for s in existing), "REENTRY_PANEL_AMBIGUOUS_NO_RETRY"
            )
            self.require_prefix(values, existing)
            self.verify_epochs(axis, existing, authorization=authorization)
            states = []
            for value in values:
                journal.validate_authorization(authorization, self.execution_identity, axis)
                states.append(self.state(axis, value, helpers, tokenizer, recover=True))
            self.journal(axis).progress(states, planned=882, recovery_only=True)
            return states

    @staticmethod
    def require_prefix(values, states):
        missing_seen = False
        for value, state in zip(values, states, strict=True):
            if value["skip_reason"]:
                continue
            if state["state"] == "UNISSUED":
                missing_seen = True
            elif state["state"] == "COMPLETE":
                c.require(not missing_seen, "REENTRY_PANEL_NONPREFIX_COMPLETION_NO_LAUNCH")

    def epochs(self, axis):
        directory = self.axis_path(axis, "epochs")
        if not directory.exists():
            return []
        paths = sorted(directory.iterdir())
        c.require(
            all(path.is_dir() and path.name.isdecimal() and len(path.name) == 4 for path in paths),
            "REENTRY_PANEL_UNKNOWN_EPOCH_DIRECTORY",
        )
        indices = [int(path.name) for path in paths]
        c.require(indices == list(range(1, len(indices) + 1)), "REENTRY_PANEL_EPOCH_GAP")
        return indices

    def progress_fields(self, states, started, *, last=None, resource=None):
        rows = [state["row"] for state in states if state.get("row") is not None]
        return {
            "planned": 882,
            "last_verified_request": last,
            "elapsed_seconds": max(0.0, time.monotonic() - started),
            "unknown_count": sum(
                row.get("skip_reason") is not None
                or row.get("output_limit_stop") is True
                or (
                    row.get("axis") == "qwen"
                    and (row.get("safety") is None or row.get("refusal") is None)
                )
                or (row.get("axis") == "jailmeter" and row.get("label") is None)
                for row in rows
            ),
            "resource": resource,
            "unknown_is_not_success": True,
        }

    def admission(
        self, axis, index, sampler, authorization, *, baseline=False, diagnostic=memory_diagnostic
    ):
        began = time.monotonic()
        while True:
            journal.validate_authorization(authorization, self.execution_identity, axis)
            sampler.check()
            sample = sampler.observe(baseline=baseline)
            c.require(time.monotonic() - began <= 180, "REENTRY_PANEL_COOLDOWN_TIMEOUT")
            if sample["observed"]["temperature_c"] <= 60:
                break
            time.sleep(0.5)
        free = thermal.check_disk(self.config, {"safe": self.safe, "private": self.private})
        c.require(
            free >= (20 if baseline else 15) * 1024**3,
            "REENTRY_PANEL_PRELAUNCH_DISK_BELOW_20_GIB"
            if baseline
            else "REENTRY_PANEL_DISK_BELOW_15_GIB",
        )
        return {
            "disk_free_bytes": free,
            "temperature_c": sample["observed"]["temperature_c"],
            "sample_sequence": sample["sequence"],
            "sample_sha256": c.digest(sample),
            "sample_recorded_at": sample["recorded_at"],
            "epoch_index": index,
            "memory_diagnostic": diagnostic(),
        }

    @contextmanager
    def release_sampling(self, axis, index, sampler):
        """Retain the post-cleanup baseline on graceful exceptions as well as success."""
        try:
            yield
        finally:
            if (
                self.epoch_path(axis, index, "worker.stopped.safe.json").is_file()
                and sampler.failure_code is None
            ):
                sampler.observe(baseline=True)

    def run(
        self,
        axis,
        authorization,
        *,
        runtime_factory=None,
        sampler_factory=None,
        diagnostic=memory_diagnostic,
        crash=None,
    ):
        journal.validate_authorization(authorization, self.execution_identity, axis)
        began = time.monotonic()
        try:
            result = self._run(
                axis,
                authorization,
                runtime_factory=runtime_factory,
                sampler_factory=sampler_factory,
                diagnostic=diagnostic,
                crash=crash,
            )
            destination = self.axis_path(
                axis, f"proofs/{result['proof_identity_sha256']}.safe.json"
            )
            if destination.exists():
                c.require(
                    low.read_bytes(destination, maximum=32_000_000) == c.canonical(result) + b"\n",
                    "REENTRY_PANEL_PUBLISHED_PROOF_CHANGED",
                )
            else:
                journal.atomic_json(destination, result)
            self.journal(axis).event(
                "PANEL_STAGE_COMPLETE",
                proof_identity_sha256=result["proof_identity_sha256"],
                planned=882,
                dispatched=result["dispatched"],
                skipped=result["skipped"],
                elapsed_seconds=max(0.0, time.monotonic() - began),
                next_stage_authorized=False,
            )
            return result
        except BaseException as error:
            try:
                self.journal(axis).event(
                    "PANEL_STAGE_INTERRUPTED",
                    error_code=low.safe_error_code(error),
                    elapsed_seconds=max(0.0, time.monotonic() - began),
                    automatic_retry=False,
                    next_stage_authorized=False,
                    memory_diagnostic=diagnostic(),
                    checkpoint_authoritative=False,
                )
            except (OSError, ValueError):
                pass
            raise

    def _run(
        self,
        axis,
        authorization,
        *,
        runtime_factory=None,
        sampler_factory=None,
        diagnostic=memory_diagnostic,
        crash=None,
    ):
        began_run = time.monotonic()
        journal.validate_authorization(authorization, self.execution_identity, axis)
        actual = runtime_factory is None
        if actual:
            c.require(
                getattr(self.target, "launch_ready", False) is True,
                "REENTRY_PINNED_LAUNCH_READY_FACTORY_REQUIRED",
            )
            self.target.assert_launch_ready()
        runtime_factory = runtime_factory or default_runtime
        sampler_factory = sampler_factory or thermal.DurableSampler
        with journal.run_lock(owned(self.safe, "panel-operation.lock")):
            if axis == "jailmeter":
                self.verify("qwen")
            values, helpers, tokenizer = self.load(axis)
            store = self.journal(axis)
            store.claim_authorization(authorization)
            states = [self.state(axis, value, helpers, tokenizer) for value in values]
            c.require(
                all(s["state"] != "AMBIGUOUS" for s in states), "REENTRY_PANEL_AMBIGUOUS_NO_RETRY"
            )
            c.require(
                not any(s.get("repair_required") for s in states),
                "REENTRY_PANEL_EXPLICIT_RECOVERY_REQUIRED",
            )
            self.require_prefix(values, states)
            self.verify_epochs(axis, states, authorization=authorization)
            for i, value in enumerate(values):
                if states[i]["state"] == "UNISSUED" and value["skip_reason"]:
                    journal.validate_authorization(authorization, self.execution_identity, axis)
                    store.skip(
                        value["item"]["request_id"],
                        low.request_body(self.config, value, axis),
                        self.binding(axis, value),
                        low.skipped_row(self.config, value, axis),
                    )
                    states[i] = self.state(axis, value, helpers, tokenizer)
                    store.progress(
                        states,
                        epoch=None,
                        **self.progress_fields(states, began_run, last=value["item"]["request_id"]),
                    )
            pending = [i for i, state in enumerate(states) if state["state"] == "UNISSUED"]
            store.progress(states, epoch=None, **self.progress_fields(states, began_run))
            if not pending:
                return self.verify(axis)
            index = len(self.epochs(axis)) + 1
            runtime = EpochRuntime(self, axis, index, authorization)
            launch = {
                **runtime.worker_binding(axis),
                "authorization": copy.deepcopy(authorization),
                "recorded_at": journal.utc(),
                "target_proof_sha256": self._target_proof["proof_identity_sha256"],
                "target_release_at": self._target_proof["latest_target_release_at"],
                "pending_request_ids_sha256": c.digest(
                    [values[i]["item"]["request_id"] for i in pending]
                ),
                "pending_count": len(pending),
                "original_scientific_config_sha256": c.digest(self.config),
                "new_operational_runtime_projection_sha256": c.digest(runtime.config),
                "old_deadline_reused_for_dispatch": False,
            }
            c.write_once(self.epoch_path(axis, index, "launch.safe.json"), launch)
            sampler = sampler_factory(
                runtime.config, self.epoch_path(axis, index, "samples.safe.jsonl")
            )
            error_code = None
            try:
                with sampler:
                    baseline = self.admission(
                        axis, index, sampler, authorization, baseline=True, diagnostic=diagnostic
                    )
                    c.write_once(self.epoch_path(axis, index, "baseline.safe.json"), baseline)
                    with (
                        self.release_sampling(axis, index, sampler),
                        runtime_factory(
                            self, axis, index, tokenizer, sampler, authorization
                        ) as worker,
                    ):
                        for i in pending:
                            value = values[i]
                            admission = self.admission(
                                axis, index, sampler, authorization, diagnostic=diagnostic
                            )
                            c.require(worker.alive(), "REENTRY_PANEL_WORKER_EXITED")
                            epoch = {
                                **runtime.worker_binding(axis),
                                "process_id": worker.pid,
                                "server_command_sha256": worker.command_sha256,
                            }
                            row = store.dispatch(
                                value["item"]["request_id"],
                                low.request_body(self.config, value, axis),
                                self.binding(axis, value),
                                self.parser(axis, value, helpers, tokenizer),
                                authorization=authorization,
                                epoch=epoch,
                                admission=admission,
                                transport=lambda value=value: worker.call(
                                    value, low.request_body(self.config, value, axis)
                                ),
                                crash=crash,
                            )
                            c.require(isinstance(row, dict), "REENTRY_PANEL_ROW_REQUIRED")
                            c.require(worker.alive(), "REENTRY_PANEL_WORKER_EXITED_AFTER_REPLY")
                            states[i] = self.state(axis, value, helpers, tokenizer)
                            store.progress(
                                states,
                                epoch=index,
                                **self.progress_fields(
                                    states,
                                    began_run,
                                    last=value["item"]["request_id"],
                                    resource=admission,
                                ),
                            )
                            sampler.check()
            except BaseException as error:
                error_code = low.safe_error_code(error)
                store.event(
                    "PANEL_INTERRUPTED",
                    epoch=index,
                    error_code=error_code,
                    ambiguous_retry_allowed=False,
                )
                raise
            finally:
                summary = {
                    **runtime.worker_binding(axis),
                    "recorded_at": journal.utc(),
                    "error_code": error_code,
                    "sampler_failure_code": sampler.failure_code,
                    "samples_sha256": c.digest(sampler.samples),
                    "sample_count": len(sampler.samples),
                    "graceful_worker_stop_present": self.epoch_path(
                        axis, index, "worker.stopped.safe.json"
                    ).exists(),
                    "memory_diagnostic": diagnostic(),
                    "review_required_before_resume": error_code is not None,
                }
                c.write_once(self.epoch_path(axis, index, "summary.safe.json"), summary)
                refreshed = [self.state(axis, value, helpers, tokenizer) for value in values]
                store.progress(
                    refreshed,
                    epoch=index,
                    error_code=error_code,
                    **self.progress_fields(refreshed, began_run),
                )
            return self.verify(axis)

    def verify_epochs(self, axis, states, authorization=None):
        """Implemented below: raw state ownership plus honest multi-epoch closure."""
        return self._verify_epochs(axis, states, authorization)

    def review_interruption(
        self,
        axis,
        index,
        authorization,
        *,
        process_probe=None,
        resource_observer=None,
        diagnostic=memory_diagnostic,
    ):
        """Explicit review only. Observe absence now, never invent an old stop."""
        journal.validate_authorization(authorization, self.execution_identity, axis)
        with journal.run_lock(owned(self.safe, "panel-operation.lock")):
            self.verify_targets()
            start = low.read_json(self.epoch_path(axis, index, "worker.started.safe.json"))
            launch = low.read_json(self.epoch_path(axis, index, "launch.safe.json"))
            c.require(
                not self.epoch_path(axis, index, "worker.stopped.safe.json").exists(),
                "REENTRY_PANEL_REVIEW_NOT_MISSING_STOP",
            )
            c.require(
                authorization["authorization_identity_sha256"]
                != launch["authorization"]["authorization_identity_sha256"]
                and stamp(authorization["issued_at"]) >= stamp(start["started_at"]),
                "REENTRY_PANEL_FRESH_REVIEW_DIRECTION_REQUIRED",
            )
            if process_probe is None:
                import psutil

                process_probe = psutil.pid_exists
            c.require(
                process_probe(start["pid"]) is False, "REENTRY_PANEL_PREVIOUS_PID_NOT_PROVEN_ABSENT"
            )
            observed = (resource_observer or low.query_gpu)()
            thermal.gpu_gate(self.config, observed, baseline=True)
            c.require(observed["temperature_c"] <= 60, "REENTRY_PANEL_RELEASE_NOT_COOL")
            value = seal(
                {
                    "schema_version": "pa-reentry-panel-interruption-review-v2",
                    "execution_identity": self.execution_identity,
                    "stage": axis,
                    "epoch_index": index,
                    "authorization": copy.deepcopy(authorization),
                    "recorded_at": journal.utc(),
                    "worker_started_sha256": c.digest(start),
                    "recorded_pid": start["pid"],
                    "recorded_pid_observed_absent": True,
                    "original_stop_record_missing": True,
                    "old_stop_fabricated": False,
                    "gpu_release_observation": observed,
                    "memory_diagnostic": diagnostic(),
                    "lost_resource_coverage_not_reconstructed": True,
                }
            )
            journal.validate_authorization(authorization, self.execution_identity, axis)
            journal.atomic_json(
                self.epoch_path(axis, index, "interruption-review.safe.json"), value
            )
            self.journal(axis).event(
                "INTERRUPTED_WORKER_RELEASE_REVIEWED",
                epoch=index,
                review_identity_sha256=value["proof_identity_sha256"],
                old_stop_fabricated=False,
            )
            return value

    def _verify_epochs(self, axis, states, authorization):
        self.journal(axis).audit_ids([item["request_id"] for item in self.frame])
        dispatched = [s for s in states if s.get("dispatched") and s["state"] == "COMPLETE"]
        indices = self.epochs(axis)
        c.require(
            all(s["intent"]["epoch"].get("epoch_index") in indices for s in dispatched),
            "REENTRY_PANEL_INTENT_WITHOUT_EPOCH",
        )
        order = [s["intent"]["epoch"]["epoch_index"] for s in dispatched]
        c.require(order == sorted(order), "REENTRY_PANEL_EPOCH_REQUEST_ORDER_CHANGED")
        lower = stamp(self._target_proof["latest_target_release_at"])
        if axis == "jailmeter":
            qwen = self.verify("qwen")
            if qwen["latest_evaluator_release_at"] is not None:
                lower = max(lower, stamp(qwen["latest_evaluator_release_at"]))
        output = []
        for index in indices:
            allowed_safe = {
                "launch.safe.json",
                "baseline.safe.json",
                "worker.started.safe.json",
                "worker.stopped.safe.json",
                "summary.safe.json",
                "samples.safe.jsonl",
                "interruption-review.safe.json",
            }
            files = []
            for private, allowed in ((False, allowed_safe), (True, {"worker.log.private.txt"})):
                directory = self.epoch_path(axis, index, "placeholder", private=private).parent
                if directory.exists():
                    children = sorted(directory.iterdir())
                    c.require(
                        all(
                            path.name in allowed and path.is_file() and not path.is_symlink()
                            for path in children
                        ),
                        "REENTRY_PANEL_UNEXPLAINED_EPOCH_FILE",
                    )
                    for path in children:
                        raw = low.read_bytes(path, maximum=32_000_000)
                        files.append(
                            {
                                "area": "private" if private else "safe",
                                "name": path.name,
                                "size_bytes": len(raw),
                                "sha256": c.sha_bytes(raw),
                            }
                        )
            launch = low.read_json(self.epoch_path(axis, index, "launch.safe.json"))
            auth = launch["authorization"]
            journal.validate_authorization(
                auth, self.execution_identity, axis, now=launch["recorded_at"]
            )
            runtime = EpochRuntime(self, axis, index, auth)
            bound = runtime.worker_binding(axis)
            c.require(
                all(c.same(launch.get(k), v) for k, v in bound.items())
                and launch["target_proof_sha256"] == self._target_proof["proof_identity_sha256"]
                and launch["target_release_at"] == self._target_proof["latest_target_release_at"]
                and launch["original_scientific_config_sha256"] == c.digest(self.config)
                and launch["new_operational_runtime_projection_sha256"] == c.digest(runtime.config)
                and launch["old_deadline_reused_for_dispatch"] is False
                and stamp(launch["recorded_at"]) >= lower,
                "REENTRY_PANEL_LAUNCH_BINDING_OR_PRIOR_RELEASE",
            )
            selected = [s for s in dispatched if s["intent"]["epoch"]["epoch_index"] == index]
            pending_ids = [
                item["request_id"]
                for item, state in zip(self.frame, states, strict=True)
                if not (
                    state["state"] == "COMPLETE"
                    and (
                        not state.get("dispatched")
                        or state["intent"]["epoch"]["epoch_index"] < index
                    )
                )
            ]
            c.require(
                launch["pending_count"] == len(pending_ids)
                and launch["pending_request_ids_sha256"] == c.digest(pending_ids),
                "REENTRY_PANEL_EPOCH_PENDING_FRAME_CHANGED",
            )
            start_path = self.epoch_path(axis, index, "worker.started.safe.json")
            stop_path = self.epoch_path(axis, index, "worker.stopped.safe.json")
            summary_path = self.epoch_path(axis, index, "summary.safe.json")
            log_path = self.epoch_path(axis, index, "worker.log.private.txt", private=True)
            summary = low.read_json(summary_path) if summary_path.exists() else None
            start = low.read_json(start_path) if start_path.exists() else None
            stop = low.read_json(stop_path) if stop_path.exists() else None
            failed = summary is None or summary.get("error_code") is not None or stop is None
            if summary is not None:
                c.require(
                    all(c.same(summary.get(k), v) for k, v in bound.items()),
                    "REENTRY_PANEL_SUMMARY_BINDING_CHANGED",
                )
            if failed and authorization is not None:
                c.require(
                    authorization["authorization_identity_sha256"]
                    != auth["authorization_identity_sha256"]
                    and stamp(authorization["issued_at"])
                    >= stamp(
                        summary["recorded_at"] if summary is not None else launch["recorded_at"]
                    ),
                    "REENTRY_PANEL_FRESH_REENTRY_AUTHORIZATION_REQUIRED",
                )
            if start is None:
                c.require(
                    not selected and stop is None and not log_path.exists(),
                    "REENTRY_PANEL_UNKNOWN_WORKER_PID_REVIEW_REQUIRED",
                )
                output.append(
                    {
                        "epoch_index": index,
                        "worker_never_started": True,
                        "dispatches": 0,
                        "prior_interruption_retained": True,
                        "resource_evidence_complete": True,
                        "release_at": None,
                        "files": files,
                        "files_identity_sha256": c.digest(files),
                    }
                )
                continue
            command = low.jailmeter_command(self.root, self.config) if axis == "jailmeter" else None
            c.require(
                set(start)
                == set(bound) | {"pid", "command_sha256", "started_at", "in_process_model"}
                and all(c.same(start.get(k), v) for k, v in bound.items())
                and type(start["pid"]) is int
                and start["pid"] > 0
                and start["command_sha256"] == (c.digest(command) if command else None)
                and start["in_process_model"] is (axis == "qwen")
                and log_path.is_file(),
                "REENTRY_PANEL_WORKER_START_BINDING",
            )
            begin = stamp(start["started_at"])
            c.require(
                max(lower, stamp(launch["recorded_at"])) <= begin <= stamp(auth["expires_at"]),
                "REENTRY_PANEL_WORKER_START_AUTH_WINDOW",
            )
            review = None
            if stop is not None:
                c.require(
                    set(stop)
                    == set(bound)
                    | {
                        "pid",
                        "stopped_at",
                        "model_released",
                        "owned_server_stopped",
                        "returncode",
                        "peak_cuda_allocated_bytes",
                    }
                    and all(c.same(stop.get(k), v) for k, v in bound.items())
                    and stop["pid"] == start["pid"]
                    and stop["model_released"] is True
                    and stop["owned_server_stopped"] is (axis == "jailmeter"),
                    "REENTRY_PANEL_WORKER_STOP_BINDING",
                )
                if axis == "qwen":
                    peak = stop["peak_cuda_allocated_bytes"]
                    c.require(
                        stop["returncode"] is None
                        and type(peak) is int
                        and 0
                        <= peak
                        <= self.config["execution_limits"]["maximum_peak_cuda_allocated_bytes"],
                        "REENTRY_PANEL_CUDA_PEAK_PROOF",
                    )
                else:
                    c.require(
                        type(stop["returncode"]) is int
                        and stop["peak_cuda_allocated_bytes"] is None,
                        "REENTRY_PANEL_SERVER_RELEASE_PROOF",
                    )
                release = stamp(stop["stopped_at"])
            else:
                review_path = self.epoch_path(axis, index, "interruption-review.safe.json")
                c.require(
                    review_path.is_file(), "REENTRY_PANEL_MISSING_STOP_REQUIRES_OBSERVED_RELEASE"
                )
                review = low.read_json(review_path)
                journal.verify_seal(review, "proof_identity_sha256")
                journal.validate_authorization(
                    review["authorization"],
                    self.execution_identity,
                    axis,
                    now=review["recorded_at"],
                )
                c.require(
                    review["execution_identity"] == self.execution_identity
                    and review["stage"] == axis
                    and review["epoch_index"] == index
                    and review["recorded_pid"] == start["pid"]
                    and review["worker_started_sha256"] == c.digest(start)
                    and review["recorded_pid_observed_absent"] is True
                    and review["old_stop_fabricated"] is False
                    and review["original_stop_record_missing"] is True,
                    "REENTRY_PANEL_INTERRUPTION_RELEASE_REVIEW_CHANGED",
                )
                c.require(
                    review["authorization"]["authorization_identity_sha256"]
                    != auth["authorization_identity_sha256"]
                    and stamp(review["authorization"]["issued_at"]) >= begin,
                    "REENTRY_PANEL_FRESH_REVIEW_DIRECTION_REQUIRED",
                )
                thermal.gpu_gate(self.config, review["gpu_release_observation"], baseline=True)
                release = stamp(review["recorded_at"])
            c.require(release >= begin, "REENTRY_PANEL_RELEASE_BEFORE_START")
            samples_path = self.epoch_path(axis, index, "samples.safe.jsonl")
            samples = read_lines(samples_path) if samples_path.exists() else []
            resource_complete = True
            previous_stamp = stamp(launch["recorded_at"])
            for n, sample in enumerate(samples):
                c.require(
                    set(sample)
                    == {
                        "sequence",
                        "recorded_at",
                        "baseline",
                        "observed",
                        "gate_passed",
                        "error_code",
                    }
                    and type(sample["sequence"]) is int
                    and sample["sequence"] == n
                    and type(sample["baseline"]) is bool,
                    "REENTRY_PANEL_RESOURCE_SAMPLE_SCHEMA",
                )
                moment = stamp(sample["recorded_at"])
                c.require(moment >= previous_stamp, "REENTRY_PANEL_RESOURCE_TIME_ORDER")
                previous_stamp = moment
                if sample["gate_passed"] is not True or sample["error_code"] is not None:
                    resource_complete = False
                else:
                    thermal.gpu_gate(self.config, sample["observed"], baseline=sample["baseline"])
            if summary is not None:
                c.require(
                    summary["sample_count"] == len(samples)
                    and summary["samples_sha256"] == c.digest(samples),
                    "REENTRY_PANEL_RESOURCE_SUMMARY_CHANGED",
                )
                resource_complete &= summary["sampler_failure_code"] is None
            baselines = [s for s in samples if s["baseline"] and s["gate_passed"] is True]
            pre = [s for s in baselines if stamp(s["recorded_at"]) <= begin]
            resource_complete &= bool(pre) and any(
                s["observed"]["temperature_c"] <= 60 for s in pre
            )
            # A missing old stop remains missing, even if a new observation proves release.
            if stop is not None:
                resource_complete &= any(stamp(s["recorded_at"]) >= release for s in baselines)
                c.require(
                    all(not begin < stamp(s["recorded_at"]) < release for s in baselines),
                    "REENTRY_PANEL_BASELINE_DURING_LOADED_WORKER",
                )
            else:
                resource_complete = False
            last_received, sample_index = begin, -1
            for state in selected:
                intent, row = state["intent"], state["row"]
                expected_epoch = {
                    **bound,
                    "process_id": start["pid"],
                    "server_command_sha256": start["command_sha256"],
                }
                c.require(
                    c.same(intent["epoch"], expected_epoch)
                    and c.same(intent["authorization"], auth),
                    "REENTRY_PANEL_INTENT_OWNED_WORKER_CHANGED",
                )
                admitted = intent["admission"]
                idx = admitted["sample_sequence"]
                c.require(
                    type(idx) is int and sample_index < idx < len(samples),
                    "REENTRY_PANEL_MISSING_OR_STALE_DISPATCH_SAMPLE",
                )
                sample = samples[idx]
                c.require(
                    sample["gate_passed"] is True
                    and sample["baseline"] is False
                    and sample["observed"]["temperature_c"] <= 60
                    and admitted["epoch_index"] == index
                    and admitted["sample_sha256"] == c.digest(sample)
                    and admitted["sample_recorded_at"] == sample["recorded_at"]
                    and admitted["temperature_c"] == sample["observed"]["temperature_c"],
                    "REENTRY_PANEL_DISPATCH_RESOURCE_BINDING",
                )
                dispatch, received = stamp(row["dispatch_at"]), stamp(row["received_at"])
                c.require(
                    last_received
                    <= stamp(sample["recorded_at"])
                    <= dispatch
                    <= received
                    <= release,
                    "REENTRY_PANEL_RESPONSE_OUTSIDE_EPOCH_OR_STALE_SAMPLE",
                )
                last_received, sample_index = received, idx
            if selected:
                resource_complete &= (
                    bool(samples) and stamp(samples[-1]["recorded_at"]) >= last_received
                )
            baseline_pin = self.epoch_path(axis, index, "baseline.safe.json")
            c.require(baseline_pin.is_file(), "REENTRY_PANEL_PRELAUNCH_RECEIPT_REQUIRED")
            baseline = low.read_json(baseline_pin)
            bindex = baseline["sample_sequence"]
            c.require(
                type(bindex) is int
                and 0 <= bindex < len(samples)
                and samples[bindex]["baseline"] is True
                and baseline["sample_sha256"] == c.digest(samples[bindex])
                and baseline["disk_free_bytes"] >= 20 * 1024**3,
                "REENTRY_PANEL_PRELAUNCH_BINDING_CHANGED",
            )
            if selected and not resource_complete and authorization is None:
                raise c.DevelopmentError("INCOMPLETE_RESOURCE_EVIDENCE")
            if selected and not resource_complete and authorization is not None:
                c.require(review is not None, "INCOMPLETE_RESOURCE_EVIDENCE_REVIEW_REQUIRED")
            output.append(
                {
                    "epoch_index": index,
                    "dispatches": len(selected),
                    "worker_started_sha256": c.digest(start),
                    "worker_stopped_sha256": c.digest(stop) if stop is not None else None,
                    "stop_record_missing": stop is None,
                    "summary_record_missing": summary is None,
                    "interruption_review_sha256": c.digest(review) if review is not None else None,
                    "prior_interruption_retained": failed,
                    "resource_evidence_complete": bool(resource_complete),
                    "release_at": release.isoformat(),
                    "launch_sha256": c.digest(launch),
                    "files": files,
                    "files_identity_sha256": c.digest(files),
                }
            )
            lower = release
        return output

    def verify(self, axis):
        values, helpers, tokenizer = self.load(axis)
        states = [self.state(axis, value, helpers, tokenizer) for value in values]
        c.require(
            all(s["state"] == "COMPLETE" and not s.get("repair_required") for s in states),
            "REENTRY_PANEL_FULL882_NOT_COMPLETE",
        )
        epochs = self.verify_epochs(axis, states)
        rows = [state["row"] for state in states]
        result = {
            "schema_version": SCHEMA,
            "execution_identity": self.execution_identity,
            "original_contract_sha256": PARENT,
            "bound_plan_identity_sha256": PLAN,
            "stage": axis,
            "complete": True,
            "planned_records": 882,
            "rows": rows,
            "rows_identity_sha256": c.digest(rows),
            "dispatched": sum(row["dispatched"] for row in rows),
            "skipped": sum(not row["dispatched"] for row in rows),
            "controls_judged": 0,
            "all_scientific_rows_included": True,
            "parent_screen_operational_amendment_disclosure": copy.deepcopy(
                self.plan["parent_operational_amendment_disclosure"]
            ),
            "target_composite_proof": copy.deepcopy(self._target_proof),
            "epochs": epochs,
            "original_operational_gate_passed": False,
            "latest_evaluator_release_at": next(
                (e["release_at"] for e in reversed(epochs) if e["release_at"]), None
            ),
            "first_continuation_operational_gate_passed": False,
            "prior_operation_failures": list(FAILURES),
            "raw_receipts_reverified": True,
            "scientific_rules_changed": False,
            "scientific_gate_evaluated": False,
            "paper_validity": False,
            "verification_performed_inference": False,
        }
        return seal(result)
