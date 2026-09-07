"""Append-only operational continuation; the original failed axis NEVER passes.

Only explicit run() / CLI run dispatch. Verification opens only NEW development
receipts and local tokenizer metadata, never historical responses or sealed data.
Scientific request IDs, prompt construction, numerical settings and parsers are
the frozen parent implementation's. This module owns separate execution proofs.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_panel_v1 as p

CONFIG = "configs/natural_language_localization/pa_llama_development_jailmeter_continuation_v1.json"
SELF = "scripts/pa_llama_development_jailmeter_continuation_v1.py"
AGGREGATE = "scripts/pa_llama_development_continued_aggregate_v1.py"
PARENT_SHA = "49bfa0302681971ed49150a95d3a300d3f8f4bc85e0fe483ec73ebd39e1b7139"
SCHEMA = "jbspan-pa-llama-development-jailmeter-continuation-v1"
SCOPE = "RAW_SCIENTIFIC_RECEIPTS_AND_AMENDED_EXECUTION_NOT_ORIGINAL_OPERATIONAL_PASS"
COOLING = {
    "before_every_new_request": True,
    "maximum_predispatch_temperature_c": 60,
    "poll_seconds": 0.5,
    "maximum_wait_seconds": 180,
}


def prefix_ids(amendment):
    prefix = amendment["original_seed11_prefix"]
    return tuple(
        set(prefix[key])
        for key in ("dispatched_request_ids", "skipped_request_ids", "pending_request_ids")
    )


def validate_amendment(value):
    c.require(
        isinstance(value, dict) and not any(k.startswith("_") for k in value),
        "AMENDMENT_RUNTIME_FIELD_FORBIDDEN",
    )
    fields = {
        "schema_version",
        "frozen",
        "execution_authorized",
        "frozen_at_utc",
        "parent_contract",
        "protocol",
        "required_code",
        "original_phase11_plan",
        "original_seed11_prefix",
        "allowed_seeds",
        "cooling",
        "scientific_changes",
        "redo_completed",
        "reuse_all_completed_original_receipts",
        "new_failure_requires_review",
        "maximum_continuation_epochs_per_seed",
        "retain_failed_resource_sample",
        "maximum_total_jailmeter_dispatches",
        "deadline_utc",
    }
    c.require(set(value) == fields, "CONTINUATION_AMENDMENT_FIELD_CLOSURE")
    fixed = {
        "schema_version": SCHEMA,
        "frozen": True,
        "execution_authorized": True,
        "allowed_seeds": [11, 23, 47],
        "cooling": COOLING,
        "scientific_changes": False,
        "redo_completed": False,
        "maximum_total_jailmeter_dispatches": 270,
        "deadline_utc": c.EXECUTION_LIMITS["deadline_utc"],
    }
    c.require(
        all(c.same(value.get(k), v) for k, v in fixed.items()), "CONTINUATION_FIXED_SCOPE_DRIFT"
    )
    c.require(
        p.validate_timestamp(value.get("frozen_at_utc"))
        < p.validate_timestamp(value["deadline_utc"]),
        "CONTINUATION_FREEZE_AFTER_DEADLINE",
    )
    parent = value.get("parent_contract", {})
    c.require(
        parent.get("path") == c.CONFIG and parent.get("sha256") == PARENT_SHA,
        "CONTINUATION_PARENT_CHANGED",
    )
    for key, expected in (
        ("reuse_all_completed_original_receipts", True),
        ("new_failure_requires_review", True),
        ("maximum_continuation_epochs_per_seed", 1),
        ("retain_failed_resource_sample", True),
    ):
        c.require(c.same(value[key], expected), "CONTINUATION_SAFETY_POLICY_CHANGED")
    prefix = value.get("original_seed11_prefix")
    c.require(isinstance(prefix, dict), "CONTINUATION_PREFIX_REQUIRED")
    c.require(
        set(prefix)
        == {"safe_files", "dispatched_request_ids", "skipped_request_ids", "pending_request_ids"},
        "CONTINUATION_PREFIX_FIELD_CLOSURE",
    )
    for key, count in (
        ("dispatched_request_ids", 30),
        ("skipped_request_ids", 5),
        ("pending_request_ids", 55),
    ):
        ids = prefix.get(key)
        c.require(
            isinstance(ids, list)
            and len(ids) == len(set(ids)) == count
            and all(c.valid_sha(rid) for rid in ids),
            "CONTINUATION_PREFIX_IDS",
        )
    dispatched, skipped, pending = prefix_ids(value)
    c.require(
        not (dispatched & skipped or dispatched & pending or skipped & pending),
        "CONTINUATION_PREFIX_OVERLAP",
    )
    base = f"{c.SAFE_ROOT}/{PARENT_SHA}/panel/jailmeter/"
    required = {base + rid + ".dispatch.safe.json" for rid in dispatched}
    required |= {base + rid + ".row.safe.json" for rid in dispatched | skipped}
    required |= {
        base + "seed-11." + suffix + ".safe.json"
        for suffix in ("abort", "resources", "server.started", "server.stopped")
    }
    pins = prefix.get("safe_files")
    c.require(
        isinstance(pins, list)
        and len(pins) == 69
        and {pin.get("path") for pin in pins} == required,
        "CONTINUATION_PREFIX_FILE_CLOSURE",
    )
    return value


def verify_safe_prefix(root, amendment):
    base = c.paths(root, PARENT_SHA)
    prefix = f"{c.SAFE_ROOT}/{PARENT_SHA}/"
    for pin in amendment["original_seed11_prefix"]["safe_files"]:
        c.require(
            set(pin) == {"path", "size_bytes", "sha256"}
            and type(pin["size_bytes"]) is int
            and pin["size_bytes"] >= 0
            and c.valid_sha(pin["sha256"])
            and pin["path"].startswith(prefix),
            "CONTINUATION_PREFIX_PIN_SCHEMA",
        )
        path = p.owned_path(base, "safe", pin["path"][len(prefix) :])
        raw = p.read_bytes(path)
        c.require(
            len(raw) == pin["size_bytes"] and c.sha_bytes(raw) == pin["sha256"],
            "ORIGINAL_FAILED_PREFIX_CHANGED",
        )
    abort = p.read_json(p.abort_path(base, "jailmeter", 11))
    resource = p.read_json(p.resource_path(base, "jailmeter", 11))
    c.require(
        abort.get("contract_sha256") == PARENT_SHA
        and abort.get("seed") == 11
        and abort.get("axis") == "jailmeter"
        and abort.get("error_code") == "EVALUATOR_RESOURCE_SAMPLER_FAILED"
        and abort.get("retry_ambiguous_request") is False
        and abort.get("review_required") is True
        and resource.get("sampled_resources", {}).get("sampler_failure_code")
        == "GPU_RESOURCE_GATE",
        "ORIGINAL_RESOURCE_STOP_NOT_PRESERVED",
    )
    c.require(
        p.validate_timestamp(abort["recorded_at"])
        <= p.validate_timestamp(amendment["frozen_at_utc"]),
        "AMENDMENT_PREDATES_ORIGINAL_STOP",
    )
    return c.digest(amendment["original_seed11_prefix"])


def load_amendment(root, expected_sha):
    c.require(c.valid_sha(expected_sha), "AMENDMENT_SHA_INVALID")
    raw = p.read_bytes(c.contained(root, CONFIG))
    c.require(c.sha_bytes(raw) == expected_sha, "AMENDMENT_SHA_MISMATCH")
    amendment = validate_amendment(c.strict_json(raw))
    c.verify_pin(root, amendment["parent_contract"], ("configs/",))
    c.verify_pin(root, amendment["protocol"], ("docs/",))
    pins = amendment.get("required_code", {})
    c.require(
        isinstance(pins, dict) and {SELF, AGGREGATE} <= {pin.get("path") for pin in pins.values()},
        "CONTINUATION_SELF_PIN_REQUIRED",
    )
    for pin in pins.values():
        path = c.verify_pin(root, pin, ("scripts/", "tests/", "src/"))
        if pin["path"] == SELF:
            c.require(path == Path(__file__).resolve(), "CONTINUATION_SELF_PATH")
    plan_pin = amendment["original_phase11_plan"]
    c.require(
        plan_pin["path"] == f"{c.SAFE_ROOT}/{PARENT_SHA}/phase_11_plan.safe.json",
        "CONTINUATION_PLAN_PIN_PATH",
    )
    c.verify_pin(root, plan_pin, ("data/",))
    verify_safe_prefix(root, amendment)
    amendment["_amendment_sha256"] = expected_sha
    return amendment


def continuation_path(base, amendment, seed, suffix, *, private=False):
    c.require(
        seed in (11, 23, 47) and c.valid_sha(amendment["_amendment_sha256"]),
        "CONTINUATION_PATH_IDENTITY",
    )
    return p.owned_path(
        base,
        "private" if private else "safe",
        f"panel/jailmeter/continuation-{amendment['_amendment_sha256']}/seed-{seed}.{suffix}",
    )


def ownership_path(base, amendment, seed, rid):
    c.require(c.valid_sha(rid), "CONTINUATION_REQUEST_ID")
    return continuation_path(base, amendment, seed, rid + ".ownership.safe.json")


def result_path(base, seed):
    return p.owned_path(base, "safe", f"phase_{seed}_jailmeter_continued_axis.safe.json")


def assert_authority(root, config, amendment, plan):
    c.require(
        c.same(load_amendment(root, amendment["_amendment_sha256"]), amendment),
        "AMENDMENT_MUTATED_AFTER_LOAD",
    )
    c.require(c.same(c.load_contract(root, PARENT_SHA), config), "PARENT_MUTATED_AFTER_LOAD")
    c.require(
        config["panel"]["jailmeter"]["request_timeout_seconds"] == 240,
        "CONTINUATION_INFLIGHT_TIMEOUT_CHANGED",
    )
    seed = plan["phase_seed"]
    c.require(seed in amendment["allowed_seeds"], "CONTINUATION_SEED_FORBIDDEN")
    inventory = c.source_inventory(root, config)
    target, _ = p.target_helpers(root, config)
    c.require(
        c.same(target.phase_for(root, config, inventory, seed), plan),
        "CONTINUATION_PHASE_PLAN_CHANGED",
    )
    base = c.paths(root, PARENT_SHA)
    c.require(
        c.same(p.read_json(p.owned_path(base, "safe", f"phase_{seed}_plan.safe.json")), plan),
        "CONTINUATION_SAVED_PLAN_CHANGED",
    )
    if seed == 11:
        c.require(
            {row["request_id"] for row in plan["rows"]} == set.union(*prefix_ids(amendment)),
            "CONTINUATION_PREFIX_PLAN_DENOMINATOR",
        )
    else:
        previous_seed = 11 if seed == 23 else 23
        prior_artifacts = {}
        for suffix in ("result", "verification"):
            prior = p.read_json(
                p.owned_path(base, "safe", f"phase_{previous_seed}_{suffix}.safe.json")
            )
            c.require(
                prior.get("operational_amendment_sha256s") == [amendment["_amendment_sha256"]]
                and prior.get("original_seed11_jailmeter_operational_gate_passed") is False
                and prior.get("verification_scope") == SCOPE,
                "CONTINUATION_PREVIOUS_AUTHORITY_NOT_DISCLOSED",
            )
            prior_artifacts[suffix] = prior
        # Deferred import avoids a module-level cycle; this exact new finalizer
        # was already SHA-verified by load_amendment, and its path is rechecked.
        import pa_llama_development_continued_aggregate_v1 as aggregate

        pins = [pin for pin in amendment["required_code"].values() if pin["path"] == AGGREGATE]
        c.require(
            len(pins) == 1
            and c.verify_pin(root, pins[0], ("scripts/",)) == Path(aggregate.__file__).resolve(),
            "CONTINUATION_FINALIZER_IMPORT_PATH",
        )
        aggregate.validate_previous(
            config, amendment, prior_artifacts["result"], prior_artifacts["verification"]
        )
    p.global_panel_receipt_check(root, config, inventory)
    return base, inventory, target


def audit_ownership(root, config, amendment, inventory):
    """Every post-prefix scientific dispatch has exactly one child ownership proof."""
    base = c.paths(root, config["_contract_sha256"])
    counts = p.global_panel_receipt_check(root, config, inventory)
    c.require(
        counts["jailmeter"] <= amendment["maximum_total_jailmeter_dispatches"],
        "CONTINUATION_GLOBAL_DISPATCH_LIMIT",
    )
    directory = p.owned_path(base, "safe", "panel/jailmeter")
    dispatched = {
        path.name.removesuffix(".dispatch.safe.json")
        for path in directory.glob("*.dispatch.safe.json")
    }
    old, _, _ = prefix_ids(amendment)
    child = continuation_path(base, amendment, 11, "unused").parent
    owners = {}
    for path in child.glob("*.ownership.safe.json") if child.exists() else []:
        owner = p.read_json(path)
        rid, seed = owner.get("request_id"), owner.get("seed")
        c.require(
            c.valid_sha(rid)
            and seed in (11, 23, 47)
            and path == ownership_path(base, amendment, seed, rid)
            and rid not in owners,
            "CONTINUATION_OWNERSHIP_FILE_IDENTITY",
        )
        owners[rid] = owner
    c.require(
        set(owners) == dispatched - old and old <= dispatched,
        "CONTINUATION_ORPHAN_OR_UNOWNED_DISPATCH_NO_RETRY",
    )
    return owners


def gpu_gate(config, observed, *, baseline=False):
    c.require(
        isinstance(observed, dict)
        and set(observed) == {"name", "used_mib", "total_mib", "temperature_c"}
        and observed["name"] == "NVIDIA GeForce RTX 3070",
        "GPU_IDENTITY_MISMATCH",
    )
    c.require(
        all(
            type(observed[k]) in (int, float) and math.isfinite(observed[k]) and observed[k] >= 0
            for k in ("used_mib", "total_mib", "temperature_c")
        ),
        "GPU_RESOURCE_SCALAR_INVALID",
    )
    maximum = config["execution_limits"][
        "maximum_prelaunch_gpu_mib" if baseline else "maximum_peak_gpu_mib"
    ]
    c.require(
        observed["used_mib"] <= maximum
        and observed["total_mib"] >= 8000
        and observed["temperature_c"] < 85,
        "GPU_RESOURCE_GATE",
    )


def check_disk(config, base):
    free = shutil.disk_usage(base["safe"]).free
    c.require(
        type(free) is int and free >= config["execution_limits"]["minimum_free_disk_bytes"],
        "CONTINUATION_DISK_FLOOR_NO_DISPATCH",
    )
    return free


class DurableSampler:
    """Content-free append-only scalar telemetry, including the rejected observation."""

    def __init__(self, config, path):
        self.config, self.path = config, path
        self.stop = threading.Event()
        self.mutex = threading.Lock()
        self.thread = None
        self.stream = None
        self.samples = []
        self.failure_code = None

    def observe(self, *, baseline=False):
        with self.mutex:
            self.check()
            observed, error_code = None, None
            try:
                observed = p.query_gpu()
                gpu_gate(self.config, observed, baseline=baseline)
            except Exception as error:
                error_code = p.safe_error_code(error)
            sample = {
                "sequence": len(self.samples),
                "recorded_at": p.utc(),
                "baseline": baseline,
                "observed": observed,
                "gate_passed": error_code is None,
                "error_code": error_code,
            }
            # Write and fsync BEFORE signalling a hardware/resource failure.
            self.stream.write(c.canonical(sample) + b"\n")
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.samples.append(sample)
            if error_code is not None:
                self.failure_code = error_code
            self.check()
            return sample

    def _sample(self):
        while not self.stop.is_set():
            try:
                self.observe()
            except Exception as error:
                if self.failure_code is None:
                    self.failure_code = p.safe_error_code(error)
                break
            self.stop.wait(0.5)

    def check(self):
        c.require(self.failure_code is None, "CONTINUATION_RESOURCE_SAMPLER_FAILED")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("xb")
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop.set()
        self.thread.join(timeout=5)
        try:
            c.require(not self.thread.is_alive(), "CONTINUATION_SAMPLER_CLEANUP_FAILED")
        finally:
            if not self.thread.is_alive():
                self.stream.close()
        if exc_type is None:
            self.check()
            c.require(bool(self.samples), "CONTINUATION_RESOURCE_SAMPLES_ABSENT")


def cool_before_dispatch(config, amendment, sampler, started, *, baseline=False):
    began = time.monotonic()
    while True:
        p.check_deadline(config, "jailmeter", started)
        sampler.check()
        sample = sampler.observe(baseline=baseline)
        if sample["observed"]["temperature_c"] <= 60:
            return sample
        c.require(time.monotonic() - began < 180, "CONTINUATION_COOLDOWN_TIMEOUT_NO_DISPATCH")
        # This is a bounded operational cooling poll, never a model retry.
        time.sleep(amendment["cooling"]["poll_seconds"])


def epoch_binding(config, amendment, seed):
    return {
        "contract_sha256": config["_contract_sha256"],
        "execution_amendment_sha256": amendment["_amendment_sha256"],
        "seed": seed,
        "epoch_index": 1,
        "owned_process_only": True,
    }


@contextmanager
def continuation_server(root, config, amendment, plan, base, *, check_resources):
    runtime, seed = config["panel"]["jailmeter"], plan["phase_seed"]
    command = p.jailmeter_command(root, config)
    log_path = continuation_path(base, amendment, seed, "server.log.private.txt", private=True)
    start_path = continuation_path(base, amendment, seed, "server.started.safe.json")
    stop_path = continuation_path(base, amendment, seed, "server.stopped.safe.json")
    c.require(
        not any(path.exists() for path in (log_path, start_path, stop_path)),
        "CONTINUATION_EPOCH_ALREADY_ATTEMPTED_NO_RELAUNCH",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((runtime["host"], runtime["port"]))
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.casefold() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
        and not k.upper().startswith("LLAMA_ARG_")
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    process = None
    with log_path.open("xb") as log:
        try:
            check_resources()
            p.check_deadline(config)
            process = subprocess.Popen(
                command,
                cwd=str(Path(command[0]).parent),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            c.write_once(
                start_path,
                {
                    **epoch_binding(config, amendment, seed),
                    "pid": process.pid,
                    "command_sha256": c.digest(command),
                    "started_at": p.utc(),
                },
            )
            client = p.LocalJailmeter(runtime["port"])
            health_deadline = time.monotonic() + runtime["health_timeout_seconds"]
            while True:
                check_resources()
                p.check_deadline(config)
                c.require(process.poll() is None, "CONTINUATION_SERVER_EARLY_EXIT")
                try:
                    healthy = p.strict(client.request("/health")).get("status") == "ok"
                except OSError:
                    healthy = False
                if healthy:
                    check_resources()
                    break
                c.require(time.monotonic() < health_deadline, "CONTINUATION_SERVER_STARTUP_TIMEOUT")
                time.sleep(0.25)
            yield client, process
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=15)
                c.require(process.poll() is not None, "CONTINUATION_OWNED_CLEANUP_FAILED")
                c.write_once(
                    stop_path,
                    {
                        **epoch_binding(config, amendment, seed),
                        "pid": process.pid,
                        "returncode": process.returncode,
                        "stopped_at": p.utc(),
                    },
                )


def resource_summary(config, amendment, seed, sampler):
    samples = sampler.samples if sampler is not None else []
    observed = [s["observed"] for s in samples if s["observed"] is not None]
    return {
        **epoch_binding(config, amendment, seed),
        "inference_worker_started": sampler is not None,
        "sample_count": len(samples),
        "sampling_interval_seconds": 0.5,
        "sampler_failure_code": sampler.failure_code if sampler is not None else None,
        "samples_identity_sha256": c.digest(samples),
        "peak_gpu_temperature_c": max((s["temperature_c"] for s in observed), default=None),
        "peak_gpu_used_mib": max((s["used_mib"] for s in observed), default=None),
        "peak_is_sampled_not_continuous": True,
        "rejected_observation_retained": any(not s["gate_passed"] for s in samples),
    }


def read_samples(base, amendment, seed, config):
    path = continuation_path(base, amendment, seed, "samples.safe.jsonl")
    raw = p.read_bytes(path, maximum=32_000_000)
    c.require(raw.endswith(b"\n"), "CONTINUATION_TRUNCATED_RESOURCE_JOURNAL")
    samples, previous = [], None
    for index, line in enumerate(raw.splitlines()):
        sample = p.strict(line)
        c.require(
            set(sample)
            == {"sequence", "recorded_at", "baseline", "observed", "gate_passed", "error_code"}
            and type(sample["sequence"]) is int
            and sample["sequence"] == index
            and type(sample["baseline"]) is bool
            and sample["gate_passed"] is True
            and sample["error_code"] is None,
            "CONTINUATION_FAILED_RESOURCE_JOURNAL",
        )
        timestamp = p.validate_timestamp(sample["recorded_at"])
        c.require(previous is None or previous <= timestamp, "CONTINUATION_RESOURCE_TIME_ORDER")
        c.require(
            timestamp >= p.validate_timestamp(amendment["frozen_at_utc"]),
            "CONTINUATION_RESOURCE_BEFORE_AUTHORITY",
        )
        gpu_gate(config, sample["observed"], baseline=sample["baseline"])
        samples.append(sample)
        previous = timestamp
    c.require(bool(samples), "CONTINUATION_EMPTY_RESOURCE_JOURNAL")
    return samples


def validate_child_lifecycle(root, config, amendment, plan, base, rows, owners):
    seed = plan["phase_seed"]
    paths = {
        suffix: continuation_path(base, amendment, seed, suffix)
        for suffix in (
            "server.started.safe.json",
            "server.stopped.safe.json",
            "resources.safe.json",
            "samples.safe.jsonl",
        )
    }
    log_path = continuation_path(base, amendment, seed, "server.log.private.txt", private=True)
    if not rows:
        c.require(
            not any(path.exists() for path in (*paths.values(), log_path)),
            "CONTINUATION_SKIP_ONLY_HAS_EPOCH",
        )
        return None
    started = p.read_json(paths["server.started.safe.json"])
    stopped = p.read_json(paths["server.stopped.safe.json"])
    common = epoch_binding(config, amendment, seed)
    command_sha = c.digest(p.jailmeter_command(root, config))
    c.require(
        set(started) == set(common) | {"pid", "command_sha256", "started_at"}
        and all(c.same(started.get(k), v) for k, v in common.items())
        and type(started["pid"]) is int
        and started["pid"] > 0
        and started["command_sha256"] == command_sha,
        "CONTINUATION_STARTED_BINDING",
    )
    c.require(
        set(stopped) == set(common) | {"pid", "returncode", "stopped_at"}
        and all(c.same(stopped.get(k), v) for k, v in common.items())
        and c.same(stopped["pid"], started["pid"])
        and type(stopped["returncode"]) is int,
        "CONTINUATION_STOPPED_BINDING",
    )
    begin, end = (
        p.validate_timestamp(started["started_at"]),
        p.validate_timestamp(stopped["stopped_at"]),
    )
    c.require(
        p.validate_timestamp(amendment["frozen_at_utc"]) <= begin <= end and log_path.is_file(),
        "CONTINUATION_LIFECYCLE_INCOMPLETE",
    )
    samples = read_samples(base, amendment, seed, config)
    sample_proxy = type("VerifiedSamples", (), {"samples": samples, "failure_code": None})()
    resource = p.read_json(paths["resources.safe.json"])
    c.require(
        c.same(resource, resource_summary(config, amendment, seed, sample_proxy)),
        "CONTINUATION_RESOURCE_SUMMARY_DRIFT",
    )
    c.require(
        p.validate_timestamp(samples[0]["recorded_at"]) <= begin
        and p.validate_timestamp(samples[-1]["recorded_at"]) >= end,
        "CONTINUATION_RESOURCE_LIFECYCLE_NOT_COVERED",
    )
    baseline = [sample for sample in samples if sample["baseline"]]
    c.require(
        baseline
        and all(p.validate_timestamp(sample["recorded_at"]) <= begin for sample in baseline)
        and baseline[-1]["observed"]["temperature_c"] <= 60,
        "CONTINUATION_PRELAUNCH_BASELINE_PROOF_REQUIRED",
    )
    previous_received, previous_sample_index = begin, -1
    for row in rows:
        rid = row["request_id"]
        owner = owners[rid]
        expected_keys = set(common) | {
            "request_id",
            "process_id",
            "server_command_sha256",
            "predispatch_sample_sequence",
            "predispatch_sample_sha256",
            "original_prefix_identity_sha256",
            "recorded_at",
            "disk_free_bytes",
        }
        c.require(
            set(owner) == expected_keys
            and all(c.same(owner.get(k), v) for k, v in common.items())
            and owner["request_id"] == rid
            and c.same(owner["process_id"], started["pid"])
            and owner["server_command_sha256"] == command_sha
            and owner["original_prefix_identity_sha256"]
            == c.digest(amendment["original_seed11_prefix"]),
            "CONTINUATION_OWNERSHIP_BINDING",
        )
        c.require(
            type(owner["disk_free_bytes"]) is int
            and owner["disk_free_bytes"] >= config["execution_limits"]["minimum_free_disk_bytes"],
            "CONTINUATION_DISK_PROOF_BELOW_FLOOR",
        )
        index = owner["predispatch_sample_sequence"]
        c.require(type(index) is int and 0 <= index < len(samples), "CONTINUATION_SAMPLE_INDEX")
        sample = samples[index]
        c.require(
            owner["predispatch_sample_sha256"] == c.digest(sample)
            and sample["baseline"] is False
            and sample["observed"]["temperature_c"] <= 60,
            "CONTINUATION_PREDISPATCH_COOLING_PROOF",
        )
        c.require(
            index > previous_sample_index
            and p.validate_timestamp(sample["recorded_at"]) >= previous_received,
            "CONTINUATION_STALE_OR_REUSED_COOLING_SAMPLE",
        )
        c.require(
            c.same(row["process_id"], started["pid"])
            and row["server_command_sha256"] == command_sha,
            "CONTINUATION_ROW_PROCESS_BINDING",
        )
        dispatch = p.validate_timestamp(row["dispatch_at"])
        c.require(
            begin
            <= p.validate_timestamp(sample["recorded_at"])
            <= p.validate_timestamp(owner["recorded_at"])
            <= dispatch
            <= p.validate_timestamp(row["received_at"])
            <= end,
            "CONTINUATION_ROW_OUTSIDE_EPOCH",
        )
        c.require(
            dispatch < p.validate_timestamp(config["execution_limits"]["deadline_utc"]),
            "CONTINUATION_DISPATCH_AFTER_DEADLINE",
        )
        previous_received = p.validate_timestamp(row["received_at"])
        previous_sample_index = index
    return {
        "process_id": started["pid"],
        "command_sha256": command_sha,
        "started_receipt_sha256": c.digest(started),
        "stopped_receipt_sha256": c.digest(stopped),
        "resource_summary_sha256": c.digest(resource),
        "samples_identity_sha256": c.digest(samples),
        "new_epoch_resource_gate_passed": True,
        "owned_process_stopped": True,
        "every_new_dispatch_has_cooling_proof": True,
    }


def reconstruct(root, config, amendment, plan, base, inventory, rows):
    seed = plan["phase_seed"]
    c.require(
        not continuation_path(base, amendment, seed, "abort.safe.json").exists(),
        "CONTINUATION_ABORTED_REVIEW_REQUIRED",
    )
    by_id = {row["request_id"]: row for row in rows}
    expected_ids = [item["request_id"] for item in plan["rows"]]
    c.require(
        len(by_id) == len(rows) == len(expected_ids) and set(by_id) == set(expected_ids),
        "CONTINUATION_COMPLETE_DENOMINATOR",
    )
    ordered = [by_id[rid] for rid in expected_ids]
    old_dispatched, old_skipped, pending = prefix_ids(amendment)
    parent_rows = [row for row in ordered if seed == 11 and row["request_id"] in old_dispatched]
    if seed == 11:
        c.require(
            len(parent_rows) == 30
            and {row["request_id"] for row in ordered if not row["dispatched"]} == old_skipped
            and {row["request_id"] for row in ordered if row["dispatched"]}
            == old_dispatched | pending,
            "CONTINUATION_ALL_PREFIX_REUSE_REQUIRED",
        )
        parent_lifecycle = p.validate_jailmeter_lifecycle(root, config, plan, base, parent_rows)
    else:
        c.require(
            not p.abort_path(base, "jailmeter", seed).exists(),
            "UNEXPECTED_ORIGINAL_FUTURE_AXIS_ABORT",
        )
        p.validate_jailmeter_lifecycle(root, config, plan, base, [])
        parent_lifecycle = None
    owners = audit_ownership(root, config, amendment, inventory)
    new_rows = [
        row for row in ordered if row["dispatched"] and row["request_id"] not in old_dispatched
    ]
    child_lifecycle = validate_child_lifecycle(
        root, config, amendment, plan, base, new_rows, owners
    )
    verify_safe_prefix(root, amendment)
    return {
        "schema_version": "jbspan-pa-llama-development-continued-axis-v1",
        "contract_sha256": config["_contract_sha256"],
        "phase_seed": seed,
        "axis": "jailmeter",
        "complete": True,
        "planned_records": len(rows),
        "dispatched": sum(row["dispatched"] is True for row in rows),
        "skipped": sum(row["dispatched"] is False for row in rows),
        "output_limit_stops": sum(row["output_limit_stop"] is True for row in rows),
        "rows_identity_sha256": c.digest(ordered),
        "rows": ordered,
        "execution_amendment_sha256": amendment["_amendment_sha256"],
        "original_prefix_identity_sha256": c.digest(amendment["original_seed11_prefix"]),
        "reused_original_dispatched": len(parent_rows),
        "new_continuation_dispatched": len(new_rows),
        "original_owned_server_lifecycle": parent_lifecycle,
        "continuation_owned_server_lifecycle": child_lifecycle,
        "original_operational_gate_passed": False,
        "original_seed11_jailmeter_operational_gate_passed": False,
        "operational_deviation_disclosed": True,
        "raw_receipts_reverified": True,
        "composite_lifecycle_verified": True,
        "resource_stop_preserved": True,
        "all_original_completed_reused": True,
        "unchanged_scientific_rules": True,
        "failed_original_sample_unavailable": True,
        "original_excursion_cannot_be_assigned_to_specific_response": True,
        "verification_scope": SCOPE,
        "paper_validity": False,
    }


def verify(root, config, amendment, plan):
    """No server, GPU query, torch/model instantiation or scientific calls."""
    base, inventory, _ = assert_authority(root, config, amendment, plan)
    p.preflight(root, config)
    values, helpers, tokenizer = p.load_axis_values(root, config, plan, "jailmeter")
    rows, pending = p.collect_existing(
        config, values, "jailmeter", base, helpers, tokenizer, write_skips=False
    )
    c.require(not pending, "CONTINUATION_VERIFICATION_INCOMPLETE")
    expected = reconstruct(root, config, amendment, plan, base, inventory, rows)
    saved = p.read_json(result_path(base, plan["phase_seed"]))
    c.require(c.same(saved, expected), "CONTINUATION_SAVED_AXIS_RECONSTRUCTION_MISMATCH")
    return saved


def record_abort(base, config, amendment, seed, error):
    path = continuation_path(base, amendment, seed, "abort.safe.json")
    if not path.exists():
        c.write_once(
            path,
            {
                **epoch_binding(config, amendment, seed),
                "error_code": p.safe_error_code(error),
                "recorded_at": p.utc(),
                "retry_ambiguous_request": False,
                "review_required": True,
                "original_operational_gate_passed": False,
                "private_content_included": False,
            },
        )


def run(root, config, amendment, plan):
    base, inventory, target = assert_authority(root, config, amendment, plan)
    seed = plan["phase_seed"]
    with target.operation_lock(base):
        if result_path(base, seed).exists():
            return verify(root, config, amendment, plan)
        c.require(
            not continuation_path(base, amendment, seed, "abort.safe.json").exists(),
            "CONTINUATION_ABORTED_REVIEW_REQUIRED",
        )
        # No second process attempt, including an interrupted attempt with zero dispatches.
        for suffix, private in (
            ("server.log.private.txt", True),
            ("server.started.safe.json", False),
            ("server.stopped.safe.json", False),
            ("samples.safe.jsonl", False),
            ("resources.safe.json", False),
        ):
            c.require(
                not continuation_path(base, amendment, seed, suffix, private=private).exists(),
                "CONTINUATION_EPOCH_ALREADY_ATTEMPTED_NO_RELAUNCH",
            )
        started, sampler = time.monotonic(), None
        try:
            p.preflight(root, config)
            owners = audit_ownership(root, config, amendment, inventory)
            c.require(
                not any(owner["seed"] == seed for owner in owners.values()),
                "CONTINUATION_PREEXISTING_CHILD_ATTEMPT_NO_RETRY",
            )
            values, helpers, tokenizer = p.load_axis_values(root, config, plan, "jailmeter")
            rows, pending = p.collect_existing(
                config, values, "jailmeter", base, helpers, tokenizer, write_skips=True
            )
            if seed == 11:
                old, skips, missing = prefix_ids(amendment)
                c.require(
                    {row["request_id"] for row in rows} == old | skips
                    and {value["item"]["request_id"] for value in pending} == missing,
                    "CONTINUATION_FROZEN_COMPLEMENT_CHANGED",
                )
                p.validate_jailmeter_lifecycle(
                    root, config, plan, base, [row for row in rows if row["dispatched"]]
                )
            else:
                c.require(
                    all(row["dispatched"] is False for row in rows),
                    "CONTINUATION_FUTURE_PARENT_ATTEMPT",
                )
                c.require(
                    not p.abort_path(base, "jailmeter", seed).exists(),
                    "UNEXPECTED_ORIGINAL_FUTURE_AXIS_ABORT",
                )
                p.validate_jailmeter_lifecycle(root, config, plan, base, [])
            if pending:
                sampler = DurableSampler(
                    config, continuation_path(base, amendment, seed, "samples.safe.jsonl")
                )
                try:
                    with sampler:
                        cool_before_dispatch(config, amendment, sampler, started, baseline=True)
                        check_disk(config, base)
                        with continuation_server(
                            root, config, amendment, plan, base, check_resources=sampler.check
                        ) as (
                            client,
                            process,
                        ):
                            for value in pending:
                                sample = cool_before_dispatch(config, amendment, sampler, started)
                                p.check_deadline(config, "jailmeter", started)
                                c.require(process.poll() is None, "CONTINUATION_SERVER_EXITED")
                                free = check_disk(config, base)
                                sampler.check()
                                rid = value["item"]["request_id"]
                                binding = {
                                    "process_id": process.pid,
                                    "server_command_sha256": c.digest(
                                        p.jailmeter_command(root, config)
                                    ),
                                }
                                owner = {
                                    **epoch_binding(config, amendment, seed),
                                    **binding,
                                    "request_id": rid,
                                    "recorded_at": p.utc(),
                                    "disk_free_bytes": free,
                                    "predispatch_sample_sequence": sample["sequence"],
                                    "predispatch_sample_sha256": c.digest(sample),
                                    "original_prefix_identity_sha256": c.digest(
                                        amendment["original_seed11_prefix"]
                                    ),
                                }
                                c.write_once(ownership_path(base, amendment, seed, rid), owner)
                                locations = p.axis_paths(base, "jailmeter", rid)
                                body = p.request_body(config, value, "jailmeter")
                                journal = p.reserve_dispatch(
                                    config, value, "jailmeter", body, locations, binding
                                )
                                sampler.check()
                                before = time.monotonic()
                                raw = client.request(
                                    "/completion",
                                    body,
                                    timeout=config["panel"]["jailmeter"]["request_timeout_seconds"],
                                )
                                c.write_once(locations["reply"], raw, raw=True)
                                c.require(
                                    process.poll() is None,
                                    "CONTINUATION_SERVER_EXITED_AFTER_DISPATCH",
                                )
                                row = p.jailmeter_result(
                                    config, value, helpers, raw, time.monotonic() - before, journal
                                )
                                c.write_once(locations["row"], row)
                                rows.append(row)
                                sampler.check()
                                p.emit(
                                    "DEVELOPMENT_JAILMETER_CONTINUATION_PROGRESS",
                                    seed=seed,
                                    completed=len(rows),
                                    planned=len(values),
                                    original_operational_gate_passed=False,
                                )
                        # Explicit last sample after owned server cleanup proves coverage.
                        sampler.observe()
                finally:
                    c.write_once(
                        continuation_path(base, amendment, seed, "resources.safe.json"),
                        resource_summary(config, amendment, seed, sampler),
                    )
            # Full cached reparse of every old and new raw receipt before publication.
            replayed, absent = p.collect_existing(
                config, values, "jailmeter", base, helpers, tokenizer, write_skips=False
            )
            c.require(not absent, "CONTINUATION_REPLAY_INCOMPLETE")
            result = reconstruct(root, config, amendment, plan, base, inventory, replayed)
            c.write_once(result_path(base, seed), result)
            return result
        except BaseException as error:
            record_abort(base, config, amendment, seed, error)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify", "preflight"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--amendment-sha256", required=True)
    parser.add_argument("--seed", type=int, choices=(11, 23, 47))
    args = parser.parse_args(argv)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        amendment = load_amendment(args.root, args.amendment_sha256)
        config = c.load_contract(args.root, PARENT_SHA)
        if args.command == "preflight":
            result = {
                **p.preflight(args.root, config),
                "execution_amendment_sha256": args.amendment_sha256,
                "original_operational_gate_passed": False,
            }
        else:
            c.require(args.seed in (11, 23, 47), "CONTINUATION_SEED_REQUIRED")
            base = c.paths(args.root, PARENT_SHA)
            plan = p.read_json(p.owned_path(base, "safe", f"phase_{args.seed}_plan.safe.json"))
            result = (run if args.command == "run" else verify)(args.root, config, amendment, plan)
        print(c.canonical({k: v for k, v in result.items() if k != "rows"}).decode(), flush=True)
        return 0
    except BaseException as error:
        p.emit(
            "DEVELOPMENT_CONTINUATION_STOPPED",
            error_code=p.safe_error_code(error),
            retry_ambiguous_request=False,
            original_operational_gate_passed=False,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
