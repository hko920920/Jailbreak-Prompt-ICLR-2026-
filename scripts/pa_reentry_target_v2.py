"""Second target continuation: immutable history, exact suffix, explicit authority.

This module has no execution CLI or import-time side effects. Construction requires
the independently verified history context. Only ``run(authorization)`` can launch
the unchanged, locally owned target server. A stage-2 preparation is not authority.
"""

from __future__ import annotations

import ctypes
import hashlib
import math
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_target_v1 as low
import pa_llama_topology_target_v1 as frozen
import pa_reentry_journal_v2 as j

ORIGINAL = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
PREFIX_COUNT = 1082
TOTAL = 1470
PREFIX_ROWS = "46e31aad957c4d75058444242603169d5c0313012d02ae493e8c642d2b1057dc"
SUFFIX = "ead9c678e451700ab9d82a2286cfcd0d98a6a977ba3fa0fbdf1a6d5d36222369"
SUFFIX_IDS = "7d7ddd7ff5bf8ef532db2c09e0e2ca6a9988a90495cf0a757d4fa283e63ece5a"
CHUNKS = ((4, 1083, 1292), (5, 1293, 1470))
SAFE_ROOT = "data/natural_language_localization/pa_reentry_v2"
PRIVATE_ROOT = "artifacts/pa_reentry_v2/private"
PRELAUNCH_BYTES = 20 * 1024**3
FAILURES = [
    "DISK_FREE_SPACE_BELOW_15_GIB",
    "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
]


def _same(actual, expected, code):
    j.require(j.digest(actual) == j.digest(expected), code)


def _identifier(value):
    j.require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value),
              "TARGET_EPOCH_ID_INVALID")
    return value


def memory_diagnostics():
    """Read-only snapshots, not a new scientific exclusion or peak claim."""
    if os.name != "nt":
        return {"available": False, "reason": "WINDOWS_MEMORY_SNAPSHOT_NOT_AVAILABLE"}

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load_percent", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "physical_total", "physical_available", "commit_limit",
                "commit_available", "virtual_total", "virtual_available",
                "extended_virtual_available",
            )
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"available": False, "reason": "GLOBAL_MEMORY_STATUS_QUERY_FAILED"}
    return {
        "available": True,
        "ram_total_bytes": status.physical_total,
        "ram_available_bytes": status.physical_available,
        "commit_limit_bytes": status.commit_limit,
        "commit_available_bytes": status.commit_available,
        "commit_used_bytes": status.commit_limit - status.commit_available,
        "measurement": "GLOBAL_MEMORY_STATUS_SNAPSHOT_NOT_CONTINUOUS_PEAK",
        "pagefile_allocated_bytes": None,
        "pagefile_allocation_not_directly_measured": True,
        "os_settings_changed": False,
    }


def resource_sample(root):
    return {
        **low.gpu_sample(),
        "disk_free_bytes": shutil.disk_usage(root).free,
        "memory_diagnostics": memory_diagnostics(),
    }


def pid_absent(pid):
    """Do not reclaim an existing/reused/inaccessible PID on a guessed identity."""
    j.require(type(pid) is int and pid > 0, "TARGET_PID_INVALID")
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            kernel.CloseHandle(handle)
            return False
        # ERROR_INVALID_PARAMETER is the documented nonexistent-PID case.
        j.require(ctypes.get_last_error() == 87, "TARGET_PROCESS_ABSENCE_UNCERTAIN")
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        raise ValueError("TARGET_PROCESS_ABSENCE_UNCERTAIN") from None
    return False


def safe_error_code(error):
    message = str(error)
    return message if re.fullmatch(r"[A-Z][A-Z0-9_]{0,191}", message) else "TARGET_OPERATION_ERROR"


class TargetContinuation:
    """The loader owns code/asset/manifest pins; this adapter rechecks its frame.

    A root frozen loader must construct ``history`` through
    ``pa_reentry_evidence_v2.load_history``. Test contexts use invented small frames
    by monkeypatching the module constants; production never selects a subset.
    """

    def __init__(self, history, manifest=None, *, execution_identity, sample=None):
        self.history = history
        self.historical = history.target
        self.root = self.historical.root
        self.config = self.historical.config
        self.plan = self.historical.plan
        self.helper = self.historical.helper
        self.prompts = history.prompts
        self.census = history.census
        self.historical_rows = history.rows1082
        self.execution_identity = execution_identity
        j.require(isinstance(execution_identity, str)
                  and re.fullmatch(r"[0-9a-f]{64}", execution_identity),
                  "TARGET_EXECUTION_IDENTITY_INVALID")
        self.manifest_proof = history.manifest_proof
        j.require(self.manifest_proof.get("verified") is True,
                  "VERIFIED_ARCHIVE_MANIFEST_REQUIRED")
        self.manifest_identity = self.manifest_proof["manifest_identity_sha256"]
        self.launch_ready = False
        self._launch_verifier = None
        if manifest is not None:
            _same(manifest.get("manifest_identity_sha256"), self.manifest_identity,
                  "TARGET_MANIFEST_CONTEXT_MISMATCH")
        self.paths = {
            "safe": c.contained(self.root, f"{SAFE_ROOT}/{execution_identity}/target"),
            "private": c.contained(self.root, f"{PRIVATE_ROOT}/{execution_identity}/target"),
        }
        if os.name == "nt":
            self.paths = {key: value if str(value).startswith("\\\\?\\")
                          else Path("\\\\?\\" + str(value.resolve()))
                          for key, value in self.paths.items()}
        self.safe, self.private = self.paths["safe"], self.paths["private"]
        self.journal = j.Journal(self.safe, self.private, execution_identity, "target")
        self.sample = sample or (lambda: resource_sample(self.root))
        self._frame_digest = j.digest(self._frame())
        self._validate_frame()
        self.items = self.plan["requests"][PREFIX_COUNT:]
        self.census_map = {row["materialization_id"]: row for row in self.census["rows"]}

    def assert_launch_ready(self):
        """Only the root frozen loader installs a prospective pin verifier."""
        j.require(self.launch_ready is True and callable(self._launch_verifier),
                  "TARGET_FROZEN_LAUNCH_FACTORY_REQUIRED")
        self._launch_verifier()
        self.assert_unchanged()

    def _frame(self):
        return {"config": self.config, "plan": self.plan, "rows": self.historical_rows,
                "prompts": self.prompts, "census": self.census,
                "manifest_proof": self.manifest_proof}

    def _validate_frame(self):
        _same(self.config["_contract_sha256"], ORIGINAL, "TARGET_ORIGINAL_ID_CHANGED")
        _same(self.plan["plan_identity_sha256"], PLAN, "TARGET_PLAN_ID_CHANGED")
        requests = self.plan["requests"]
        j.require(len(requests) == TOTAL and len(self.historical_rows) == PREFIX_COUNT,
                  "TARGET_FRAME_COUNT_CHANGED")
        _same([item["ordinal"] for item in requests], list(range(1, TOTAL + 1)),
              "TARGET_FROZEN_ORDINALS_CHANGED")
        _same([row["request_id"] for row in self.historical_rows],
              [item["request_id"] for item in requests[:PREFIX_COUNT]],
              "TARGET_HISTORY_NOT_EXACT_PREFIX")
        _same(j.digest(self.historical_rows), PREFIX_ROWS, "TARGET_HISTORY_ROWS_CHANGED")
        _same(j.digest(requests[PREFIX_COUNT:]), SUFFIX, "TARGET_SUFFIX_PLAN_CHANGED")
        _same(j.digest([item["request_id"] for item in requests[PREFIX_COUNT:]]),
              SUFFIX_IDS, "TARGET_SUFFIX_IDS_CHANGED")
        j.require(self.config["server"]["host"] == "127.0.0.1",
                  "TARGET_ONLY_LOOPBACK_ALLOWED")

    def assert_unchanged(self):
        _same(j.digest(self._frame()), self._frame_digest, "TARGET_CONTEXT_MUTATED")
        self.historical.assert_unchanged()

    def chunk(self, item):
        matches = [number for number, first, last in CHUNKS
                   if first <= item["ordinal"] <= last]
        j.require(len(matches) == 1, "TARGET_OUTSIDE_MISSING_SUFFIX")
        return matches[0]

    def body_binding_parser(self, item):
        self.assert_unchanged()
        return self._body_binding_parser(item)

    def _body_binding_parser(self, item):
        """Internal batch path: caller has just validated the whole context once.

        Public parsing and dispatch paths retain their independent context check.
        Read-only batch reconciliation avoids rehashing every other request's
        materialization hundreds of times while verifying each exact row chain.
        """
        mid = item["materialization_id"]
        body = frozen.request_for(self.config, item, self.prompts[mid])
        census = self.census_map[mid]
        binding = {
            "original_contract_sha256": ORIGINAL,
            "bound_plan_identity_sha256": PLAN,
            "archive_manifest_identity_sha256": self.manifest_identity,
            "planned_request_sha256": j.digest(item),
            "census_row_sha256": j.digest(census),
            "served_chat_template_sha256": self.config["runtime"][
                "served_chat_template_sha256"],
            "logical_chunk": self.chunk(item),
        }

        def parse(raw, meta, intent):
            j.require(isinstance(raw, bytes) and len(raw) <= low.MAX_REPLY_BYTES,
                      "TARGET_REPLY_OVERSIZED")
            _same(intent["binding"], binding, "TARGET_INTENT_BINDING_CHANGED")
            _same(intent["request_id"], item["request_id"], "TARGET_INTENT_ID_CHANGED")
            epoch = intent["epoch"]
            _same(epoch["logical_chunk"], self.chunk(item), "TARGET_CHUNK_CHANGED")
            j.validate_authorization(intent["authorization"], self.execution_identity,
                                     "target", now=intent["dispatch_at"])
            started, dispatched, received = map(low.parse_utc,
                (epoch["started_at"], intent["dispatch_at"], meta["received_at"]))
            j.require(started <= dispatched <= received, "TARGET_REPLY_TIME_ORDER_INVALID")
            latency = meta["elapsed_seconds"]
            j.require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0,
                      "TARGET_REPLY_LATENCY_INVALID")
            parsed = frozen.parse_reply(self.config, item, raw, census["native_prompt_tokens"])
            return {
                **item, "contract_sha256": ORIGINAL,
                "request_sha256": j.digest(body),
                "execution_identity": self.execution_identity,
                "execution_epoch_id": epoch["epoch_id"],
                "epoch_index": self.chunk(item),
                "process_id": epoch["process_id"],
                "dispatch_at": intent["dispatch_at"],
                "received_at": meta["received_at"], "latency_seconds": latency,
                "response_after_dispatch_window": meta["response_after_dispatch_window"],
                "census_row_sha256": j.digest(census),
                "served_chat_template_sha256": binding["served_chat_template_sha256"],
                "operational_authorization_sha256": j.digest(intent["authorization"]),
                **parsed,
            }

        return body, binding, parse

    def _epoch_path(self, epoch_id, name):
        return self.safe / "epochs" / _identifier(epoch_id) / name

    def verify_epoch(self, epoch_id, *, require_released=False):
        """Open/abrupt epochs never acquire an invented clean stop receipt."""
        epoch_id = _identifier(epoch_id)
        base = self._epoch_path(epoch_id, "")
        binding = j.read_json(base / "binding.safe.json")
        j.require(set(binding) == {"execution_identity", "epoch_id", "logical_chunk",
                  "authorization", "scientific_contract_sha256", "historical_deadline_unchanged"},
                  "TARGET_EPOCH_BINDING_FIELDS_CHANGED")
        _same(binding["scientific_contract_sha256"], ORIGINAL,
              "TARGET_EPOCH_SCIENTIFIC_ID_CHANGED")
        _same(binding["historical_deadline_unchanged"],
              self.config["execution_limits"]["deadline_utc"],
              "TARGET_HISTORICAL_DEADLINE_MUTATED")
        _same(binding["execution_identity"], self.execution_identity,
              "TARGET_EPOCH_EXECUTION_CHANGED")
        _same(binding["epoch_id"], epoch_id, "TARGET_EPOCH_ID_CHANGED")
        j.require(binding["logical_chunk"] in {chunk[0] for chunk in CHUNKS},
                  "TARGET_EPOCH_CHUNK_INVALID")
        auth = binding["authorization"]
        baseline = j.read_json(base / "resource.safe.json")
        low.validate_resource_sample(baseline, baseline=True)
        j.require(baseline["disk_free_bytes"] >= PRELAUNCH_BYTES,
                  "TARGET_PRELAUNCH_DISK_BELOW_20_GIB")
        j.validate_authorization(auth, self.execution_identity, "target",
                                 now=baseline["sampled_at"])
        start = j.read_json(base / "server-01.started.safe.json")
        identity = j.read_json(base / "server-01.identity.safe.json")
        j.require(set(start) == {"contract_sha256", "epoch", "pid", "started_at",
                                "command_sha256", "owned_process_only"},
                  "TARGET_WORKER_START_SCHEMA_CHANGED")
        for key, expected in start.items():
            _same(identity.get(key), expected, "TARGET_WORKER_IDENTITY_CHANGED")
        _same(start["contract_sha256"], ORIGINAL, "TARGET_WORKER_CONTRACT_CHANGED")
        _same(start["command_sha256"], c.digest(low.command_for(self.root, self.config)),
              "TARGET_WORKER_COMMAND_CHANGED")
        j.require(start["owned_process_only"] is True and start["epoch"] == 1
                  and type(start["pid"]) is int and start["pid"] > 0,
                  "TARGET_WORKER_OWNERSHIP_INVALID")
        j.require(low.parse_utc(baseline["sampled_at"]) <= low.parse_utc(start["started_at"]),
                  "TARGET_PRELAUNCH_TIME_ORDER_INVALID")
        j.validate_authorization(auth, self.execution_identity, "target", now=start["started_at"])
        self.helper.verify_template_observation(
            self.config, ORIGINAL, base / "server-01.tpl.safe.json",
            {"epoch": 1, "process_id": start["pid"]})
        private_log = self.private / "epochs" / epoch_id / "server-01.log.private.txt"
        j.require(private_log.is_file(), "TARGET_WORKER_LOG_MISSING")
        result = {
            "epoch_id": epoch_id, "logical_chunk": binding["logical_chunk"],
            "process_id": start["pid"], "started_at": start["started_at"],
            "identity_sha256": j.digest(identity),
            "epoch_binding_sha256": j.digest(binding),
            "served_chat_template_sha256": self.config["runtime"][
                "served_chat_template_sha256"],
        }
        stop_path = base / "server-01.stopped.safe.json"
        release_path = base / "interrupted-release.safe.json"
        j.require(not (stop_path.exists() and release_path.exists()),
                  "TARGET_CONTRADICTORY_EPOCH_RELEASE")
        if stop_path.exists():
            stop = j.read_json(stop_path)
            for key in ("contract_sha256", "epoch", "pid", "owned_process_only"):
                _same(stop.get(key), start[key], "TARGET_WORKER_STOP_BINDING_CHANGED")
            j.require(type(stop.get("returncode")) is int, "TARGET_WORKER_STOP_INVALID")
            result.update(clean_stop_observed=True, release_at=stop["stopped_at"])
        elif release_path.exists():
            release = j.read_json(release_path)
            j.require(set(release) == {"schema_version", "execution_identity", "epoch_id",
                      "epoch_binding_sha256", "process_id", "observed_at", "authorization",
                      "pid_absent_observed", "clean_stop_observed",
                      "missing_stop_receipt_preserved"}
                      and release["schema_version"] == "pa-reentry-interrupted-worker-release-v2"
                      and release["execution_identity"] == self.execution_identity
                      and release["epoch_id"] == epoch_id
                      and release["missing_stop_receipt_preserved"] is True,
                      "TARGET_INTERRUPTED_RELEASE_SCHEMA_CHANGED")
            _same(release.get("epoch_binding_sha256"), j.digest(binding),
                  "TARGET_INTERRUPTED_RELEASE_BINDING_CHANGED")
            _same(release.get("process_id"), start["pid"], "TARGET_RELEASE_PID_CHANGED")
            j.require(release.get("clean_stop_observed") is False
                      and release.get("pid_absent_observed") is True,
                      "TARGET_INTERRUPTED_RELEASE_INVALID")
            j.validate_authorization(release["authorization"], self.execution_identity,
                                     "target", now=release["observed_at"])
            j.require(release["authorization"]["authorization_identity_sha256"]
                      != auth["authorization_identity_sha256"]
                      and low.parse_utc(release["authorization"]["issued_at"])
                      >= low.parse_utc(start["started_at"]),
                      "TARGET_INTERRUPTED_RELEASE_REQUIRES_FRESH_DIRECTION")
            result.update(clean_stop_observed=False, release_at=release["observed_at"])
        else:
            result.update(clean_stop_observed=False, release_at=None)
        if result["release_at"] is not None:
            j.require(low.parse_utc(start["started_at"]) <= low.parse_utc(result["release_at"]),
                      "TARGET_RELEASE_TIME_INVALID")
        if require_released:
            j.require(result["release_at"] is not None,
                      "TARGET_UNCLOSED_EPOCH_REQUIRES_EXPLICIT_REVIEW")
        return result

    def _verify_completed(self, item, state, *, require_released=False):
        intent, row = state["intent"], state["row"]
        epoch = self.verify_epoch(intent["epoch"]["epoch_id"], require_released=require_released)
        expected = {key: value for key, value in epoch.items()
                    if key not in {"clean_stop_observed", "release_at"}}
        _same(intent["epoch"], expected, "TARGET_DISPATCH_WORKER_BINDING_CHANGED")
        worker_binding = j.read_json(self._epoch_path(epoch["epoch_id"], "binding.safe.json"))
        auth = worker_binding["authorization"]
        _same(intent["authorization"], auth, "TARGET_DISPATCH_AUTH_WORKER_CHANGED")
        admission = intent["admission"]
        attempt = _identifier(admission["admission_id"])
        receipt_base = self.safe / "admissions" / attempt
        cooldown = j.read_json(receipt_base / "cooldown.safe.json")
        _same(cooldown["execution_identity"], self.execution_identity,
              "TARGET_COOLDOWN_EXECUTION_CHANGED")
        _same(j.digest(cooldown), admission["cooldown_receipt_sha256"],
              "TARGET_COOLDOWN_CHANGED")
        _same(cooldown["request_id"], item["request_id"], "TARGET_COOLDOWN_REQUEST_CHANGED")
        _same(cooldown["epoch_id"], epoch["epoch_id"], "TARGET_COOLDOWN_EPOCH_CHANGED")
        _same(cooldown["policy"], frozen.COOLDOWN, "TARGET_COOLDOWN_POLICY_CHANGED")
        j.require(cooldown["cooldown_passed"] is True and cooldown["samples"],
                  "TARGET_COOLDOWN_NOT_PASSED")
        wait = cooldown["wait_seconds"]
        j.require(type(wait) in (int, float) and math.isfinite(wait) and 0 <= wait <= 180,
                  "TARGET_COOLDOWN_WAIT_INVALID")
        previous = low.parse_utc(epoch["started_at"])
        for index, sample in enumerate(cooldown["samples"]):
            low.validate_resource_sample(sample, baseline=False)
            stamp = low.parse_utc(sample["sampled_at"])
            j.require(previous <= stamp <= low.parse_utc(intent["dispatch_at"]),
                      "TARGET_COOLDOWN_TIME_INVALID")
            j.require(index == len(cooldown["samples"]) - 1
                      or sample["gpu_temperature_c"] > 60,
                      "TARGET_COOLDOWN_CONTINUED_AFTER_ACCEPT")
            previous = stamp
        final_sample = cooldown["samples"][-1]
        j.require(final_sample["gpu_temperature_c"] <= 60,
                  "TARGET_COOLDOWN_REQUIRED_BEFORE_DISPATCH")
        _same(admission["disk_free_bytes"], final_sample["disk_free_bytes"],
              "TARGET_ADMISSION_DISK_CHANGED")
        _same(admission["temperature_c"], final_sample["gpu_temperature_c"],
              "TARGET_ADMISSION_TEMPERATURE_CHANGED")
        for key in ("memory_diagnostics", "sampled_at", "gpu_used_mib"):
            _same(admission[key], final_sample[key], "TARGET_ADMISSION_RESOURCE_CHANGED")
        self.helper.verify_template_observation(
            self.config, ORIGINAL, receipt_base / "template.safe.json",
            {"epoch_id": epoch["epoch_id"], "request_id": item["request_id"],
             "process_id": epoch["process_id"]})
        _same(j.digest(j.read_json(receipt_base / "template.safe.json")),
              admission["template_receipt_sha256"], "TARGET_ADMISSION_TEMPLATE_CHANGED")
        if epoch["release_at"]:
            j.require(low.parse_utc(row["received_at"]) <= low.parse_utc(epoch["release_at"]),
                      "TARGET_RESPONSE_AFTER_RELEASE")
        return row

    def states(self, *, recover=False, require_released=False):
        self.assert_unchanged()
        result, missing, previous_epoch = [], False, None
        previous_received = low.parse_utc(
            self.historical_rows[-1]["received_at"])
        ids = {item["request_id"] for item in self.items}
        for directory in (self.safe / "requests", self.private / "requests"):
            if directory.exists():
                j.require(all(path.is_dir() and path.name in ids for path in directory.iterdir()),
                          "TARGET_UNPLANNED_REQUEST_NAMESPACE")
        for item in self.items:
            body, binding, parse = self._body_binding_parser(item)
            state = self.journal.inspect(item["request_id"], body, binding, parse)
            if recover and state["repair_required"]:
                # Verify the existing worker/cooling chain before repairing derived artifacts.
                if state["state"] == "COMPLETE":
                    self._verify_completed(item, state, require_released=require_released)
                state = self.journal.recover(item["request_id"], body, binding, parse)
                if "state" not in state:
                    state = self.journal.inspect(item["request_id"], body, binding, parse)
            if state["state"] == "COMPLETE":
                j.require(not missing, "TARGET_COMPLETED_REQUEST_AFTER_GAP")
                row = self._verify_completed(item, state, require_released=require_released)
                current_epoch = self.verify_epoch(state["intent"]["epoch"]["epoch_id"],
                                                  require_released=require_released)
                if previous_epoch and previous_epoch["epoch_id"] != current_epoch["epoch_id"]:
                    j.require(previous_epoch["release_at"] is not None
                              and low.parse_utc(previous_epoch["release_at"])
                              <= low.parse_utc(current_epoch["started_at"]),
                              "TARGET_WORKER_EPOCHS_OVERLAP")
                previous_epoch = current_epoch
                j.require(previous_received <= low.parse_utc(row["dispatch_at"]),
                          "TARGET_ORDERED_RECEIPTS_OVERLAP")
                cooldown = j.read_json(self.safe / "admissions" /
                    state["intent"]["admission"]["admission_id"] / "cooldown.safe.json")
                j.require(previous_received <= low.parse_utc(cooldown["samples"][0]["sampled_at"]),
                          "TARGET_COOLDOWN_NOT_FRESH_AFTER_PREVIOUS")
                previous_received = low.parse_utc(row["received_at"])
            else:
                missing = True
            result.append({"request_id": item["request_id"], **state})
        return result

    def review_interrupted_epoch(self, epoch_id, authorization, *, absent_probe=pid_absent):
        """Explicit later direction + actual absence; never forge a worker stop."""
        self.assert_launch_ready()
        j.validate_authorization(authorization, self.execution_identity, "target")
        with j.run_lock(self.safe / "run.lock"):
            epoch = self.verify_epoch(epoch_id)
            j.require(epoch["release_at"] is None, "TARGET_EPOCH_ALREADY_RELEASED")
            original = j.read_json(self._epoch_path(epoch_id, "binding.safe.json"))["authorization"]
            j.require(authorization["authorization_identity_sha256"]
                      != original["authorization_identity_sha256"]
                      and low.parse_utc(authorization["issued_at"])
                      >= low.parse_utc(epoch["started_at"]),
                      "TARGET_INTERRUPTED_RELEASE_REQUIRES_FRESH_DIRECTION")
            j.require(absent_probe(epoch["process_id"]) is True,
                      "TARGET_PRIOR_PROCESS_STILL_PRESENT_OR_REUSED")
            receipt = {
                "schema_version": "pa-reentry-interrupted-worker-release-v2",
                "execution_identity": self.execution_identity,
                "epoch_id": epoch_id,
                "epoch_binding_sha256": epoch["epoch_binding_sha256"],
                "process_id": epoch["process_id"],
                "observed_at": j.utc(), "authorization": authorization,
                "pid_absent_observed": True, "clean_stop_observed": False,
                "missing_stop_receipt_preserved": True,
            }
            j.validate_authorization(authorization, self.execution_identity, "target")
            j.atomic_json(self._epoch_path(epoch_id, "interrupted-release.safe.json"), receipt)
            self.journal.event("INTERRUPTED_EPOCH_REVIEWED", epoch_id=epoch_id,
                               clean_stop_observed=False)
            return self.verify_epoch(epoch_id, require_released=True)

    def _assert_prior_epochs_released(self):
        directory = self.safe / "epochs"
        if directory.exists():
            for path in directory.iterdir():
                _identifier(path.name)
                # Rejected baseline before process creation consumes no model call.
                if (path / "server-01.started.safe.json").exists():
                    self.verify_epoch(path.name, require_released=True)
                else:
                    j.require((path / "prelaunch-rejected.safe.json").exists(),
                              "TARGET_PARTIAL_PRELAUNCH_REQUIRES_REVIEW")

    def attempt_inventory(self):
        """Include every failed/zero-output attempt, not only epochs with responses."""
        self.assert_unchanged()
        inventory = []
        counts = {}
        for item in self.items:
            body, binding, parse = self._body_binding_parser(item)
            state = self.journal.inspect(item["request_id"], body, binding, parse)
            j.require(state["state"] != "AMBIGUOUS", "TARGET_ATTEMPT_INVENTORY_AMBIGUOUS")
            if state.get("intent"):
                eid = state["intent"]["epoch"]["epoch_id"]
                counts[eid] = counts.get(eid, 0) + 1
        directory = self.safe / "epochs"
        if not directory.exists():
            return inventory
        allowed_safe = {
            "binding.safe.json", "resource.safe.json", "prelaunch-rejected.safe.json",
            "server-01.started.safe.json", "server-01.identity.safe.json",
            "server-01.tpl.safe.json", "server-01.stopped.safe.json",
            "interrupted-release.safe.json",
        }
        for path in directory.iterdir():
            eid = _identifier(path.name)
            binding = j.read_json(path / "binding.safe.json")
            _same(binding["execution_identity"], self.execution_identity,
                  "TARGET_ATTEMPT_EXECUTION_CHANGED")
            _same(binding["epoch_id"], eid, "TARGET_ATTEMPT_ID_CHANGED")
            j.require(binding["logical_chunk"] in {chunk[0] for chunk in CHUNKS},
                      "TARGET_ATTEMPT_CHUNK_INVALID")
            private = self.private / "epochs" / eid
            entries = []
            for kind, parent, allowed in (("safe", path, allowed_safe),
                    ("private", private, {"server-01.log.private.txt"})):
                j.require(parent.is_dir(), "TARGET_ATTEMPT_NAMESPACE_MISSING")
                for artifact in parent.iterdir():
                    j.require(artifact.name in allowed and artifact.is_file()
                              and not artifact.is_symlink(), "TARGET_ATTEMPT_UNKNOWN_ARTIFACT")
                    before = artifact.stat()
                    digest = hashlib.sha256()
                    with artifact.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    after = artifact.stat()
                    j.require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                              (after.st_size, after.st_mtime_ns, after.st_ino),
                              "TARGET_ATTEMPT_ARTIFACT_CHANGED_DURING_READ")
                    entries.append({"kind": kind, "name": artifact.name,
                                    "size_bytes": after.st_size, "sha256": digest.hexdigest()})
            if (path / "prelaunch-rejected.safe.json").exists():
                rejected = j.read_json(path / "prelaunch-rejected.safe.json")
                j.require(not (path / "server-01.started.safe.json").exists()
                          and not list(private.iterdir()), "TARGET_REJECTED_ATTEMPT_HAS_PROCESS")
                _same(rejected["epoch_id"], eid, "TARGET_REJECTION_ID_CHANGED")
                _same(rejected["execution_identity"], self.execution_identity,
                      "TARGET_REJECTION_EXECUTION_CHANGED")
                j.require(rejected.get("model_calls") == 0, "TARGET_REJECTION_CALL_COUNT_CHANGED")
                status, release = "REJECTED_PRELAUNCH", rejected["rejected_at"]
            else:
                epoch = self.verify_epoch(eid, require_released=True)
                status = "CLEAN_STOP" if epoch["clean_stop_observed"] else "INTERRUPTED_RELEASE"
                release = epoch["release_at"]
            inventory.append({
                "epoch_id": eid, "logical_chunk": binding["logical_chunk"],
                "status": status, "release_at": release,
                "completed_target_requests": counts.get(eid, 0),
                "authorization_identity_sha256": binding["authorization"][
                    "authorization_identity_sha256"],
                "artifacts": sorted(entries, key=lambda item: (item["kind"], item["name"])),
            })
        return sorted(inventory, key=lambda item: (low.parse_utc(item["release_at"]),
                                                   item["epoch_id"]))

    def progress(self, states, started, last_row=None, admission=None):
        rows = [state["row"] for state in states
                if state["state"] == "COMPLETE" and state.get("row") is not None]
        self.journal.progress(
            states, historical_complete=PREFIX_COUNT, planned_total=TOTAL,
            science_unknown_records=sum(
                row.get("kind") == "science" and row.get("ineligible_reason") is not None
                for row in rows),
            control_unknown_records=sum(
                row.get("kind") == "control" and row.get("ineligible_reason") is not None
                for row in rows),
            last_verified_request_id=last_row["request_id"] if last_row else
                (rows[-1]["request_id"] if rows else None),
            last_verified_ordinal=last_row["ordinal"] if last_row else
                (rows[-1]["ordinal"] if rows else PREFIX_COUNT),
            latest_resource_snapshot=admission,
            elapsed_seconds=max(0, time.monotonic() - started),
            scientific_gate_evaluated=False,
        )

    @contextmanager
    def server(self, logical_chunk, authorization):
        self.assert_launch_ready()
        j.validate_authorization(authorization, self.execution_identity, "target")
        self._assert_prior_epochs_released()
        epoch_id = uuid.uuid4().hex
        safe = self.safe / "epochs" / epoch_id
        private = self.private / "epochs" / epoch_id
        safe.mkdir(parents=True, exist_ok=False)
        private.mkdir(parents=True, exist_ok=False)
        j.atomic_json(safe / "binding.safe.json", {
            "execution_identity": self.execution_identity, "epoch_id": epoch_id,
            "logical_chunk": logical_chunk, "authorization": authorization,
            "scientific_contract_sha256": ORIGINAL,
            "historical_deadline_unchanged": self.config["execution_limits"]["deadline_utc"],
        })
        try:
            baseline = self.sample()
            j.atomic_json(safe / "resource.safe.json", baseline)
            low.validate_resource_sample(baseline, baseline=True)
            j.require(baseline["disk_free_bytes"] >= PRELAUNCH_BYTES,
                      "TARGET_PRELAUNCH_DISK_BELOW_20_GIB")
            j.validate_authorization(authorization, self.execution_identity, "target")
        except BaseException as error:
            j.atomic_json(safe / "prelaunch-rejected.safe.json", {
                "execution_identity": self.execution_identity,
                "epoch_id": epoch_id, "rejected_at": j.utc(),
                "error_type": type(error).__name__, "error_code": safe_error_code(error),
                "model_calls": 0,
            })
            raise
        # No config projection or old deadline override: helper has no overall-deadline
        # gate, and fixed command/model/template stay exactly the old contract's.
        with self.helper.owned_server(self.root, self.config, private, safe, 1, ORIGINAL) as owned:
            epoch = self.verify_epoch(epoch_id)
            epoch = {key: value for key, value in epoch.items()
                     if key not in {"clean_stop_observed", "release_at"}}
            self.journal.event("TARGET_EPOCH_READY", epoch_id=epoch_id,
                               logical_chunk=logical_chunk, process_id=epoch["process_id"])
            yield (*owned, epoch)
        self.verify_epoch(epoch_id, require_released=True)

    def admission(self, item, process, client, epoch, authorization):
        aid = uuid.uuid4().hex
        base = self.safe / "admissions" / aid
        samples, started, passed = [], time.monotonic(), False
        try:
            while True:
                j.validate_authorization(authorization, self.execution_identity, "target")
                j.require(process.poll() is None, "TARGET_OWNED_PROCESS_EXITED")
                sample = self.sample()
                samples.append(sample)
                low.validate_resource_sample(sample, baseline=False)
                elapsed = time.monotonic() - started
                j.require(elapsed <= 180, "TARGET_COOLDOWN_TIMEOUT")
                if sample["gpu_temperature_c"] <= 60:
                    passed = True
                    break
                if len(samples) % 20 == 0:
                    self.journal.event("TARGET_COOLDOWN_WAIT", request_id=item["request_id"],
                                       temperature_c=sample["gpu_temperature_c"])
                time.sleep(0.5)
        finally:
            cooldown = {
                "execution_identity": self.execution_identity,
                "request_id": item["request_id"], "epoch_id": epoch["epoch_id"],
                "policy": frozen.COOLDOWN, "samples": samples,
                "cooldown_passed": passed, "wait_seconds": time.monotonic() - started,
                "measurement": "PREDISPATCH_SNAPSHOTS_NOT_CONTINUOUS_PEAK",
            }
            j.atomic_json(base / "cooldown.safe.json", cooldown)

        def observe(value):
            j.atomic_json(base / "template.safe.json", {
                "contract_sha256": ORIGINAL, "epoch_id": epoch["epoch_id"],
                "request_id": item["request_id"], **value,
            })

        self.helper.check_identity(process, client, self.config, observe)
        j.validate_authorization(authorization, self.execution_identity, "target")
        return {
            "admission_id": aid, "disk_free_bytes": samples[-1]["disk_free_bytes"],
            "temperature_c": samples[-1]["gpu_temperature_c"],
            "sampled_at": samples[-1]["sampled_at"],
            "gpu_used_mib": samples[-1]["gpu_used_mib"],
            "memory_diagnostics": samples[-1]["memory_diagnostics"],
            "cooldown_receipt_sha256": j.digest(cooldown),
            "template_receipt_sha256": j.digest(j.read_json(base / "template.safe.json")),
        }

    def run(self, authorization, *, crash=None):
        """Explicit target stage only. Complete/uncertain requests are never replayed."""
        self.assert_launch_ready()
        j.validate_authorization(authorization, self.execution_identity, "target")
        with j.run_lock(self.safe / "run.lock"):
            self.journal.claim_authorization(authorization)
            started = time.monotonic()
            try:
                self._assert_prior_epochs_released()
                states = self.states(recover=True, require_released=True)
                j.require(not any(state["state"] == "AMBIGUOUS" for state in states),
                          "TARGET_AMBIGUOUS_REQUEST_NO_RETRY")
                self.progress(states, started)
                done = sum(state["state"] == "COMPLETE" for state in states)
                for chunk, first, last in CHUNKS:
                    pending = [item for item in self.items[done:]
                               if first <= item["ordinal"] <= last]
                    if not pending:
                        continue
                    with self.server(chunk, authorization) as (process, client, _, epoch):
                        for item in pending:
                            body, binding, parse = self.body_binding_parser(item)
                            admission = self.admission(item, process, client, epoch, authorization)

                            def transport(body=body):
                                j.require(process.poll() is None, "TARGET_OWNED_PROCESS_EXITED")
                                return client.request("/v1/chat/completions", body,
                                    timeout=self.config["server"]["request_timeout_seconds"])

                            row = self.journal.dispatch(item["request_id"], body, binding, parse,
                                authorization=authorization, epoch=epoch, admission=admission,
                                transport=transport, crash=crash)
                            done += 1
                            states[done - 1] = {"state": "COMPLETE", "row": row,
                                                "repair_required": False}
                            self.journal.event("TARGET_ROW_RECORDED", ordinal=item["ordinal"],
                                kind=item["kind"], total_verified=PREFIX_COUNT + done,
                                finish_reason=row["finish_reason"])
                            self.progress(states, started, row, admission)
                rows, proof = self.verify_complete()
                path = self.safe / "complete.safe.json"
                if path.exists():
                    _same(j.read_json(path), proof, "TARGET_FINAL_PROOF_CHANGED")
                else:
                    j.atomic_json(path, proof)
                self.journal.event("TARGET_STAGE_COMPLETE", target_records=len(rows),
                                   next_stage_started=False, scientific_gate_evaluated=False)
                return proof
            except BaseException as error:
                try:
                    self.journal.event("TARGET_STAGE_STOPPED", error_type=type(error).__name__,
                                       error_code=safe_error_code(error),
                                       automatic_retry=False, next_stage_started=False)
                    self.progress(self.states(), started)
                except (OSError, ValueError, KeyError):
                    # An unwritable disk or corrupt receipt is not repaired by a summary.
                    pass
                raise

    def verify_complete(self):
        states = self.states(require_released=True)
        j.require(len(states) == TOTAL - PREFIX_COUNT
                  and all(state["state"] == "COMPLETE" and not state["repair_required"]
                          for state in states),
                  "TARGET_FULL_FRAME_INCOMPLETE")
        self._assert_prior_epochs_released()
        rows = self.historical_rows + [state["row"] for state in states]
        epochs = [self.verify_epoch(eid, require_released=True) for eid in sorted({
            state["intent"]["epoch"]["epoch_id"] for state in states})]
        attempts = self.attempt_inventory()
        proof = {
            "schema_version": "pa-reentry-target-composite-v2",
            "execution_identity": self.execution_identity,
            "original_contract_sha256": ORIGINAL,
            "bound_plan_identity_sha256": PLAN,
            "archive_manifest_identity_sha256": self.manifest_identity,
            "target_records": len(rows), "reused_target_records": PREFIX_COUNT,
            "new_target_records": len(states), "target_rows_sha256": j.digest(rows),
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
            "prior_operation_failures": FAILURES,
            "missing_stop_epochs": [epoch["epoch_id"] for epoch in epochs
                                    if not epoch["clean_stop_observed"]],
            "latest_target_release_at": max((attempt["release_at"] for attempt in attempts),
                                            key=low.parse_utc),
            "epoch_release_evidence_sha256": j.digest(epochs),
            "all_attempts": attempts,
            "all_attempts_sha256": j.digest(attempts),
            "failed_prelaunch_attempts": sum(item["status"] == "REJECTED_PRELAUNCH"
                                              for item in attempts),
            "archive_relocation_contemporaneous_receipt_available": False,
            "composite_target_complete": True,
            "scientific_gate_evaluated": False, "paper_validity": False,
        }
        return rows, {**proof, "proof_identity_sha256": j.digest(proof)}

    def raw_reply(self, request_id):
        matches = [item for item in self.plan["requests"] if item["request_id"] == request_id]
        j.require(len(matches) == 1, "TARGET_RAW_REPLY_OUTSIDE_FRAME")
        if matches[0]["ordinal"] <= PREFIX_COUNT:
            return self.historical.path("private",
                f"target/{request_id}.reply.private.json").read_bytes()
        body, binding, parse = self.body_binding_parser(matches[0])
        state = self.journal.inspect(request_id, body, binding, parse)
        j.require(state["state"] == "COMPLETE", "TARGET_RAW_REPLY_NOT_VERIFIED_COMPLETE")
        self._verify_completed(matches[0], state, require_released=True)
        return self.journal.raw_reply(request_id)
