"""Offline stage-1 audit only; never launches, resumes, or judges an experiment.

The original frozen verifiers are reused unchanged. An explicit read-only path
mapping locates the archived first continuation. Only new audit records may be
written. No historical raw cohort or sealed data is admissible.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

AMENDMENT = "6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0"
REPORT = "docs/PA_STAGE1_REENTRY_AUDIT_2026-09-07_V3.safe.json"
EVENTS = "docs/PA_STAGE1_REENTRY_EVENTS_2026-09-07_V3.jsonl"
SCRATCH = "artifacts/pa_stage1_reentry_audit_v1/runtime_tmp_v3"
NEW_PRIVATE_PREFIXES = (
    "artifacts/pa_llama_development_screen_v1/private/"
    "49bfa0302681971ed49150a95d3a300d3f8f4bc85e0fe483ec73ebd39e1b7139/",
    "artifacts/pa_llama_topology_preparation_v1/private/"
    "fe0af6381817cddc6da856da69fccc2b7a9a282e8a4cce7707c81070f8489a82/",
    "artifacts/pa_llama_topology_v1/private/"
    "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0/",
    "artifacts/pa_llama_topology_target_continuation_v1/private/" + AMENDMENT + "/",
    "artifacts/pa_llama_topology_target_continuation_v1/private/"
    + AMENDMENT + "_run1_archived/",
)


def normalized(path):
    value = os.path.realpath(os.path.abspath(os.fspath(path))).replace("\\", "/")
    if value.startswith("//?/"):
        value = value[4:]
    return value.casefold()


class AuditPolicy:
    def __init__(self, root):
        self.root = normalized(root).rstrip("/") + "/"
        self.outputs = {normalized(root / name) for name in (REPORT, EVENTS)}
        self.null_device = normalized(os.devnull)
        self.scratch = normalized(root / SCRATCH).rstrip("/") + "/"
        self.read_paths = set()
        self.external_read_paths = set()
        self.denied = collections.Counter()

    def reject(self, reason):
        self.denied[reason] += 1
        raise PermissionError(reason)

    def __call__(self, event, args):
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                     "os.spawn", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            self.reject("AUDIT_PROCESS_OR_NETWORK_FORBIDDEN")
        if event in {"os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.link",
                     "os.symlink", "os.truncate", "os.chmod", "os.utime"}:
            paths = args[:2] if event in {"os.rename", "os.link", "os.symlink"} else args[:1]
            if paths and all(isinstance(path, (str, bytes, os.PathLike)) and
                             normalized(os.fsdecode(path)).startswith(self.scratch)
                             for path in paths):
                return
            self.reject("AUDIT_FILESYSTEM_MUTATION_FORBIDDEN")
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = normalized(os.fsdecode(args[0]))
        mode = args[1] or ""
        flags = args[2] or 0
        writing = any(letter in mode for letter in "wax+") or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
        if writing:
            # dill probes Python file types through NUL; no data file is written.
            if path == self.null_device:
                return
            if path.startswith(self.scratch):
                return
            if path not in self.outputs:
                self.reject("AUDIT_WRITE_OUTSIDE_NEW_REPORTS")
            return
        if path.startswith(self.root):
            relative = path[len(self.root):]
            is_private = "/private/" in relative or ".private." in relative
            if is_private and not relative.startswith(NEW_PRIVATE_PREFIXES):
                self.reject("AUDIT_PRIVATE_READ_OUTSIDE_NEW_CLOSURE")
            if any(part in relative for part in ("primary_a60", "reserve_b60", "sealed_")):
                self.reject("AUDIT_SEALED_PATH_FORBIDDEN")
            self.read_paths.add(relative)
        else:
            if "/private/" in path or ".private." in path:
                self.reject("AUDIT_EXTERNAL_PRIVATE_READ_FORBIDDEN")
            self.external_read_paths.add(path)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def emit(root, event, **fields):
    value = {"at_utc": utc_now(), "event": event, **fields}
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
    with (root / EVENTS).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(raw + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(raw, flush=True)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def policy_self_test(root):
    policy = AuditPolicy(root)
    cases = [
        ("open", (str(root / "configs/example.json"), "r", os.O_RDONLY), False),
        ("open", (str(root / NEW_PRIVATE_PREFIXES[0] / "example.private.json"), "r", 0), False),
        ("open", (str(root / "artifacts/c1n_h4rm3l_fresh_screen_v1/private/x.json"), "r", 0), True),
        ("open", (str(root / "configs/example.json"), "w", os.O_WRONLY), True),
        ("open", (str(root / EVENTS), "a", os.O_APPEND), False),
        ("open", (os.devnull, "wb", os.O_WRONLY), False),
        ("open", (str(root / SCRATCH / "library-probe"), "w", os.O_WRONLY), False),
        ("open", (str(root / "artifacts/pa_llama_development_screen_v1/private/unpinned/x.json"),
                  "r", os.O_RDONLY), True),
        ("socket.connect", (), True),
        ("subprocess.Popen", (), True),
        ("os.remove", (), True),
        ("os.rename", (), True),
    ]
    for event, args, denied in cases:
        rejected = False
        try:
            policy(event, args)
        except PermissionError:
            rejected = True
        require(rejected == denied, "AUDIT_POLICY_SELF_TEST_FAILED")
    return len(cases)


def audit(root, policy):
    # Imports contain only definitions. The policy remains installed throughout.
    import pa_llama_topology_target_continuation_v1 as frozen

    c, low, old = frozen.c, frozen.low, frozen.old
    emit(root, "FROZEN_LOADER_AND_NEW_SCREEN_RAW_VERIFICATION_STARTED")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        target = frozen.load_amendment(root, AMENDMENT)
    emit(root, "FROZEN_LOADER_AND_NEW_SCREEN_RAW_VERIFICATION_PASSED",
         admitted_p=target.plan["n"], planned_targets=len(target.plan["requests"]))

    mapping = {}
    for area in ("safe", "private"):
        original = target.paths[area]
        archived = original.with_name(original.name + "_run1_archived")
        require(archived.is_dir(), "ARCHIVED_CONTINUATION_DIRECTORY_MISSING")
        require(not original.exists() or not list(original.iterdir()),
                "UNARCHIVED_CONTINUATION_NOT_EMPTY")
        mapping[area] = {
            "original": str(original).replace("\\", "/"),
            "archived": str(archived).replace("\\", "/"),
        }
        # Read-only relocation, explicitly disclosed; no stored artifact changes.
        target.paths[area] = archived
    emit(root, "ARCHIVE_READ_MAPPING_ESTABLISHED", areas=sorted(mapping))

    # Deny accidental calls even if future audit code accidentally uses them.
    def deny_operation(*args, **kwargs):
        raise PermissionError("AUDIT_INFERENCE_OR_MUTATING_OPERATION_FORBIDDEN")

    target.dispatch = deny_operation
    target.generate = deny_operation
    target.operation = deny_operation
    target.write = deny_operation
    target.server = deny_operation
    target.parent.write = deny_operation
    target.parent.dispatch = deny_operation
    target.parent.generate = deny_operation
    target.parent.server = deny_operation
    emit(root, "MATERIALIZATION_AND_NATIVE_CENSUS_REVERIFICATION_STARTED")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        prompts = target.load_materials()
        census = target.load_census(prompts)
    emit(root, "MATERIALIZATION_AND_NATIVE_CENSUS_REVERIFICATION_PASSED",
         materializations=len(prompts), census_rows=len(census["rows"]))
    emit(root, "RAW_1082_REQUEST_RESPONSE_CHAIN_VERIFICATION_STARTED")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rows = target.reconcile(prompts, census)
    require(len(rows) == 1082, "RETAINED_PREFIX_NOT_1082")
    require([row["ordinal"] for row in rows] == list(range(1, 1083)), "RETAINED_PREFIX_GAP")
    require(len({row["request_id"] for row in rows}) == 1082, "RETAINED_DUPLICATE_REQUEST")
    missing = target.plan["requests"][1082:]
    require(len(missing) == 388, "REMAINING_NOT_388")
    emit(root, "RAW_1082_REQUEST_RESPONSE_CHAIN_VERIFICATION_PASSED",
         raw_targets_verified=1082, remaining=388)

    expected_abort = {
        "amendment_sha256": AMENDMENT,
        "bound_plan_identity_sha256": frozen.PLAN_SHA,
        "combined_target_ceiling": 1470,
        "error_code": "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
        "new_target_ceiling": 598,
        "operation": "generate",
        "original_contract_sha256": frozen.PARENT_SHA,
        "prefix_manifest_sha256": target.amendment["prefix_manifest"]["sha256"],
        "scientific_gate_evaluated": False,
    }
    require(c.same(target.read("safe", "generate-aborted.safe.json"), expected_abort),
            "SECOND_ABORT_NOT_EXACTLY_RETAINED")
    require(c.same(old.read_json(frozen.loader.owned(root, frozen.SAFE_ROOT +
            "/experiment-reservation.safe.json")), target.reservation_binding()),
            "CONTINUATION_RESERVATION_CHANGED")
    started = target.read("safe", "generate-started.safe.json")
    expected_started = {
        "amendment_sha256": AMENDMENT,
        "original_contract_sha256": frozen.PARENT_SHA,
        "original_prefix_rows_identity_sha256": c.digest(rows[:872]),
        "epoch_schedule": frozen.EPOCHS,
        "new_target_ceiling": 598,
        "started_at": started.get("started_at"),
    }
    require(c.same(started, expected_started), "CONTINUATION_START_BINDING_CHANGED")
    started_at = low.parse_utc(started["started_at"])
    require(low.parse_utc(target.amendment["frozen_at_utc"]) <= started_at <
            low.parse_utc(target.config["execution_limits"]["deadline_utc"]),
            "CONTINUATION_START_OUTSIDE_ORIGINAL_WINDOW")
    epoch3 = target.verified_epoch(3)
    require(started_at <= low.parse_utc(epoch3["started_at"]), "EPOCH3_BEFORE_ATTEMPT")
    failed = target.read("safe", "epochs/004/resource.safe.json")
    require(set(failed) == {"baseline", "contract_sha256", "disk_free_bytes", "epoch_index",
                           "gpu_name", "gpu_temperature_c", "gpu_total_mib", "gpu_used_mib",
                           "sampled_at"}, "FAILED_BASELINE_SCHEMA_CHANGED")
    require(failed["baseline"] is True and failed["contract_sha256"] == frozen.PARENT_SHA
            and type(failed["epoch_index"]) is int and failed["epoch_index"] == 4,
            "FAILED_BASELINE_BINDING_CHANGED")
    require(type(failed["disk_free_bytes"]) is int and
            low.MIN_DISK_BYTES <= failed["disk_free_bytes"] < frozen.PRELAUNCH_BYTES,
            "FAILED_BASELINE_DISK_REASON_CHANGED")
    low.validate_resource_sample(failed, baseline=True)
    require(low.parse_utc(epoch3["stopped_at"]) <= low.parse_utc(failed["sampled_at"]) <
            low.parse_utc(target.config["execution_limits"]["deadline_utc"]),
            "FAILED_BASELINE_TIME_CHAIN_CHANGED")
    require(c.same(target.read("safe", "epochs/004/amendment.safe.json"),
                   target.epoch_binding(4)), "FAILED_BASELINE_AUTHORITY_CHANGED")
    require(frozen.file_names(target.path("safe", "epochs/004")) ==
            {"resource.safe.json", "amendment.safe.json"}, "UNEXPECTED_EPOCH4_FILE")
    require(not target.path("private", "epochs/004").exists(), "UNEXPECTED_EPOCH4_PRIVATE")
    for area in ("safe", "private"):
        require(not target.path(area, "epochs/005").exists(), "UNEXPECTED_EPOCH5")
        require(not target.path(area, "panel").exists(), "UNEXPECTED_TOPOLOGY_PANEL")
        require(not target.path(area, "target-operation.lock.safe.json").exists(),
                "ACTIVE_CONTINUATION_LOCK")
    emit(root, "SECOND_ABORT_AND_UNISSUED_SUFFIX_VERIFIED", unissued=388)
    return {
        "raw_retained_targets_verified": len(rows),
        "original_prefix_rows_identity_sha256": c.digest(rows[:872]),
        "archived_suffix_rows_identity_sha256": c.digest(rows[872:]),
        "combined_rows_identity_sha256": c.digest(rows),
        "remaining_plan_identity_sha256": c.digest(missing),
        "retained_kind_counts": dict(collections.Counter(row["kind"] for row in rows)),
        "remaining_kind_counts": dict(collections.Counter(row["kind"] for row in missing)),
        "remaining_count": len(missing),
        "first_remaining_ordinal": missing[0]["ordinal"],
        "last_remaining_ordinal": missing[-1]["ordinal"],
        "remaining_request_ids": [row["request_id"] for row in missing],
        "archive_read_mapping": mapping,
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "full_1470_composite_gate_passed": False,
        "second_abort_error_code": expected_abort["error_code"],
        "second_abort_free_disk_bytes": failed["disk_free_bytes"],
        "last_retained_received_at": rows[-1]["received_at"],
        "deadline_utc": target.config["execution_limits"]["deadline_utc"],
        "reentry_requires_new_binding": True,
        "new_model_calls": 0,
        "scientific_gate_evaluated": False,
        "raw_content_copied_to_audit": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    checks = policy_self_test(root)
    if args.self_test:
        print(json.dumps({"policy_self_tests_passed": checks}))
        return 0
    require(not (root / REPORT).exists() and not (root / EVENTS).exists(),
            "AUDIT_OUTPUT_ALREADY_EXISTS_USE_NEW_RECORDED_ATTEMPT")
    scratch = root / SCRATCH
    scratch.mkdir(parents=True, exist_ok=False)
    os.environ["TMP"] = str(scratch)
    os.environ["TEMP"] = str(scratch)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sys.dont_write_bytecode = True
    source_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    policy = AuditPolicy(root)
    sys.addaudithook(policy)
    started, before = utc_now(), time.monotonic()
    report = {"schema_version": "pa-stage1-reentry-audit-v1", "started_at": started,
              "stage": 1, "stage2_started": False, "policy_self_tests_passed": checks,
              "new_model_calls": 0, "scientific_gate_evaluated": False}
    emit(root, "STAGE1_OFFLINE_AUDIT_STARTED")
    try:
        report["verification"] = audit(root, policy)
        report["status"] = "RAW_PREFIX_VERIFIED_NEW_REENTRY_IMPLEMENTATION_REQUIRED"
        exit_code = 0
    except Exception as error:
        report["status"] = "AUDIT_INCOMPLETE"
        report["error_type"] = type(error).__name__
        message = str(error)
        report["error_code"] = message if message and all(
            char.isupper() or char.isdigit() or char == "_" for char in message
        ) else type(error).__name__
        report["trace_locations"] = [
            {"file": Path(frame.filename).name, "line": frame.lineno,
             "function": frame.name} for frame in traceback.extract_tb(error.__traceback__)
        ]
        exit_code = 1
    report["completed_at"] = utc_now()
    report["elapsed_seconds"] = round(time.monotonic() - before, 3)
    report["audit_policy_denials"] = dict(policy.denied)
    report["read_path_count"] = len(policy.read_paths)
    report["external_system_or_library_read_path_count"] = len(policy.external_read_paths)
    report["read_policy_scope"] = (
        "Scoped CPython audit hook plus unchanged frozen verifiers, not a universal OS sandbox. "
        "Private reads restricted to exact NEW namespaces; external system/library reads allowed."
    )
    report["temporary_import_workspace"] = SCRATCH
    report["read_path_inventory_sha256"] = hashlib.sha256(
        json.dumps(sorted(policy.read_paths), separators=(",", ":")).encode()
    ).hexdigest()
    report["audit_script_sha256_before"] = source_before
    report["audit_script_sha256_after"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["audit_script_unchanged_during_execution"] = (
        report["audit_script_sha256_after"] == source_before
    )
    if not report["audit_script_unchanged_during_execution"]:
        report["status"] = "AUDIT_SOURCE_CHANGED_DURING_EXECUTION"
        exit_code = 1
    raw = json.dumps(report, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    with (root / REPORT).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    emit(root, "STAGE1_OFFLINE_AUDIT_FINISHED", status=report["status"],
         elapsed_seconds=report["elapsed_seconds"], error_code=report.get("error_code"),
         report=REPORT)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
