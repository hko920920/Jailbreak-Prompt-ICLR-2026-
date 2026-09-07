"""Read-only, SAFE-only progress accounting; never a scientific or execution verifier.

Only the separately pinned d05 execution config, preparation bound plan, and an
explicit NEW SAFE metadata allowlist are opened. No worker imports, private reads,
model access, repair, output files, outcome analysis, or execution authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CONFIG = "configs/natural_language_localization/pa_llama_topology_execution_v1.json"
CONFIG_SHA = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
CONFIG_SIZE = 35000
SOURCE_SHA = "fe0af6381817cddc6da856da69fccc2b7a9a282e8a4cce7707c81070f8489a82"
PLAN = (
    "data/natural_language_localization/pa_llama_topology_preparation_v1/"
    f"{SOURCE_SHA}/bound-plan.safe.json"
)
PLAN_SHA = "3a8bc4391f2ba6d02f2de446bd8b4ff61d1c1ac121fb3c57044bee379df1615b"
PLAN_SIZE = 3577251
PLAN_ID = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
SAFE = "data/natural_language_localization/pa_llama_topology_v1"
POSITIONS = (0, 3, 4, 10, 11, 14, 15, 16, 18, 21, 22, 23, 24, 25, 33, 34, 36, 37, 42, 43, 44)
OPERATORS = ("SOURCE_AWARE_OMIT", "LAYOUT_PRESERVING_BLANK")
TASKS = ("P2_ARITHMETIC", "P2_COPY_TOKEN")
STATES = (
    "RECORDED_COMPLETION_SAFE_ONLY",
    "RECORDED_DETERMINISTIC_SKIP_SAFE_ONLY",
    "NO_SAFE_DISPATCH_OBSERVED",
    "PREDISPATCH_ONLY",
    "DISPATCH_WITHOUT_COMPLETION_AMBIGUOUS",
    "MALFORMED_OR_INCONSISTENT_METADATA",
)
MAX_FILE = 8_000_000
MAX_FILES = 16000
ID = r"[0-9a-f]{64}"
REQUEST_PATH = re.compile(
    rf"(?P<area>target|panel/qwen|panel/jailmeter)/(?P<rid>{ID})\."
    r"(?P<part>dispatch|row|ownership|cooldown|tpl)\.safe\.json\Z"
)
EPOCH_PATH = re.compile(
    r"epochs/[0-9]{3}/(?:server-01\.(?:started|stopped|identity)|resource)\.safe\.json\Z"
)
PANEL_PATH = re.compile(
    r"panel/(?:qwen|jailmeter)/(?:worker\.(?:started|stopped)|resources|abort|axis)\.safe\.json\Z"
)
TOP_FILES = {
    "target-operation.lock.safe.json",
    "targets.safe.json",
    *{
        f"{name}-aborted.safe.json"
        for name in ("stage", "census", "generate", "panel-qwen", "panel-jailmeter", "finalize")
    },
}


class InventoryError(ValueError):
    """Fixed content-free error codes only."""


def require(value, code):
    if not value:
        raise InventoryError(code)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def same(first, second):
    return canonical(first) == canonical(second)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_):
        raise InventoryError("NONFINITE_JSON_NUMBER")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise InventoryError("MALFORMED_JSON") from error


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def utc(value):
    require(isinstance(value, str), "UTC_TIMESTAMP_REQUIRED")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InventoryError("UTC_TIMESTAMP_INVALID") from error
    require(
        stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0,
        "UTC_TIMESTAMP_REQUIRED",
    )
    return stamp


def scoped(root, relative):
    """Validate canonical scope first, then adapt only this validated Windows path."""
    require(
        isinstance(relative, str)
        and relative
        and "\\" not in relative
        and ":" not in relative
        and not relative.startswith("/")
        and all(part not in {"", ".", ".."} for part in relative.split("/")),
        "RELATIVE_PATH_REJECTED",
    )
    base = Path(root).resolve()
    candidate = base.joinpath(*relative.split("/"))
    try:
        candidate.resolve().relative_to(base)
    except (ValueError, OSError) as error:
        raise InventoryError("PATH_OUTSIDE_ROOT") from error
    for part in (candidate, *candidate.parents):
        if part == base.parent:
            break
        if part.exists():
            info = part.lstat()
            require(
                not part.is_symlink() and not (getattr(info, "st_file_attributes", 0) & 1024),
                "LINK_OR_REPARSE_POINT_REJECTED",
            )
    return Path("\\\\?\\" + str(candidate)) if os.name == "nt" else candidate


def read_bytes(path, maximum=MAX_FILE):
    before = path.stat()
    require(path.is_file() and before.st_size <= maximum, "FILE_NOT_REGULAR_OR_OVERSIZED")
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    after = path.stat()
    require(len(raw) <= maximum, "FILE_OVERSIZED")
    require(
        (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
        "FILE_CHANGED_DURING_READ",
    )
    return raw


def pinned(root, relative, expected_sha, expected_size):
    raw = read_bytes(scoped(root, relative))
    require(len(raw) == expected_size and sha(raw) == expected_sha, "EXTERNAL_PIN_MISMATCH")
    return strict(raw)


def load_frame(root, config_sha, plan_sha):
    require(config_sha == CONFIG_SHA and plan_sha == PLAN_SHA, "KNOWN_EXTERNAL_PINS_REQUIRED")
    config = pinned(root, CONFIG, CONFIG_SHA, CONFIG_SIZE)
    plan = pinned(root, PLAN, PLAN_SHA, PLAN_SIZE)
    require(
        config.get("schema_version") == "jbspan-pa-llama-topology-execution-v1"
        and config.get("frozen") is True
        and config.get("execution_authorized") is True
        and config.get("paper_validity") is False
        and config.get("source_bundle_identity_sha256") == SOURCE_SHA
        and config.get("bound_plan_identity_sha256") == PLAN_ID
        and config.get("paths", {}).get("safe_root") == SAFE,
        "CONFIG_FRAME_CHANGED",
    )
    require(
        plan.get("plan_identity_sha256") == PLAN_ID
        and sha(canonical({k: v for k, v in plan.items() if k != "plan_identity_sha256"}))
        == PLAN_ID
        and plan.get("n") == 21
        and plan.get("materializations_bound") is True,
        "PLAN_IDENTITY_CHANGED",
    )
    require(
        same([row["payload_position"] for row in plan["population"]], list(POSITIONS)),
        "ALL_21_POPULATION_REQUIRED",
    )
    rows = plan["requests"]
    require(
        isinstance(rows, list)
        and len(rows) == 1470
        and same([row.get("ordinal") for row in rows], list(range(1, 1471))),
        "EXACT_TARGET_ORDER_REQUIRED",
    )
    ids = [row.get("request_id") for row in rows]
    require(
        all(isinstance(rid, str) and re.fullmatch(ID, rid) for rid in ids)
        and len(set(ids)) == 1470,
        "REQUEST_IDS_INVALID_OR_DUPLICATED",
    )
    expected = Counter()
    for position in POSITIONS:
        for mask in range(1, 8):
            for operator in OPERATORS:
                for seed in (11, 23, 47):
                    expected[(position, mask, operator, "science", seed, None)] += 1
                for task in TASKS:
                    expected[(position, mask, operator, "control", 17, task)] += 1
    keys = ("payload_position", "mask", "operator", "kind", "seed", "task_id")
    require(
        Counter(tuple(row.get(key) for key in keys) for row in rows) == expected
        and all(
            type(row.get("panel_evaluation_required")) is bool
            and row["panel_evaluation_required"] == (row["kind"] == "science")
            for row in rows
        ),
        "FULL_CARTESIAN_FRAME_REQUIRED",
    )
    for key, value in (
        ("total_target_calls", 1470),
        ("scientific_target_calls", 882),
        ("control_target_calls", 588),
        ("qwen_calls", 882),
        ("jailmeter_calls", 882),
        ("metadata_post_calls", 2646),
    ):
        require(
            same(config["budgets"].get(key), value) and same(plan["budgets"].get(key), value),
            "FULL_BUDGETS_REQUIRED",
        )
    return config, plan


def allowed(relative):
    match = REQUEST_PATH.fullmatch(relative)
    if match:
        permitted = (
            {"dispatch", "row", "cooldown", "tpl"}
            if match["area"] == "target"
            else {"dispatch", "row", "ownership"}
        )
        return match["part"] in permitted
    return relative in TOP_FILES or bool(
        EPOCH_PATH.fullmatch(relative) or PANEL_PATH.fullmatch(relative)
    )


def manifest(root):
    """No recursive traversal: only fixed SAFE areas and numeric epoch directories."""
    relative_base = f"{SAFE}/{CONFIG_SHA}"
    scoped(root, relative_base)
    result = {}
    directories = ["", "target", "panel/qwen", "panel/jailmeter"]
    epochs = scoped(root, relative_base + "/epochs")
    if epochs.exists():
        for child in epochs.iterdir():
            if re.fullmatch(r"[0-9]{3}", child.name):
                directories.append("epochs/" + child.name)
    for directory in directories:
        path = scoped(root, relative_base + ("/" + directory if directory else ""))
        if not path.exists():
            continue
        require(path.is_dir(), "METADATA_DIRECTORY_REQUIRED")
        for child in path.iterdir():
            relative = (directory + "/" if directory else "") + child.name
            if not allowed(relative):
                continue  # Never open private, raw, samples, census, or analysis products.
            checked = scoped(root, relative_base + "/" + relative)
            info = checked.stat()
            require(checked.is_file(), "SAFE_METADATA_FILE_REQUIRED")
            result[relative] = (info.st_size, info.st_mtime_ns)
            require(len(result) <= MAX_FILES, "SAFE_FILE_COUNT_LIMIT")
    return result


def safe_code(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value)
        else "UNRECOGNIZED_ERROR_CODE_REDACTED"
    )


def base_binding(value, item, axis):
    require(
        value.get("contract_sha256") == CONFIG_SHA
        and value.get("request_id") == item["request_id"],
        "RECORD_IDENTITY_MISMATCH",
    )
    if axis == "target":
        require(
            all(same(value.get(key), expected) for key, expected in item.items()),
            "TARGET_PLAN_BINDING_MISMATCH",
        )
    else:
        require(
            value.get("axis") == axis
            and same(value.get("seed"), item["seed"])
            and same(value.get("payload_position"), item["payload_position"])
            and value.get("condition")
            == f"TOPOLOGY_SCIENCE:{item['operator']}:MASK_{item['mask']}",
            "AXIS_PLAN_BINDING_MISMATCH",
        )


def classify(item, axis, parts):
    """Metadata relations only. Never inspect judge labels, scores or target eligibility."""
    output = {
        "ordinal": item["ordinal"],
        "kind": item["kind"],
        "state": STATES[2],
        "issue_codes": [],
    }
    if not parts:
        return output
    try:
        require(all("error" not in value for value in parts.values()), "UNREADABLE_METADATA")
        values = {part: receipt["value"] for part, receipt in parts.items()}
        for part, value in values.items():
            require(
                value.get("contract_sha256") == CONFIG_SHA
                and value.get("request_id") == item["request_id"],
                "RECORD_IDENTITY_MISMATCH",
            )
            if part in {"dispatch", "row"}:
                base_binding(value, item, axis)
        dispatch, row = values.get("dispatch"), values.get("row")
        owner = values.get("ownership")
        if axis != "target" and owner is not None:
            require(
                owner.get("axis") == axis
                and owner.get("bound_plan_identity_sha256") == PLAN_ID
                and same(owner.get("topology_item"), item)
                and type(owner.get("dispatched")) is bool,
                "OWNER_BINDING_MISMATCH",
            )
        if row is None:
            output["state"] = STATES[4] if dispatch is not None else STATES[3]
        elif axis != "target" and row.get("dispatched") is False:
            require(
                dispatch is None
                and owner is not None
                and owner["dispatched"] is False
                and row.get("skip_reason") in {"TARGET_INELIGIBLE", "EVALUATOR_CONTEXT_BOUND"}
                and same(row.get("inference_seconds"), 0.0),
                "SKIP_METADATA_INCONSISTENT",
            )
            output.update(state=STATES[1], skip_reason=row["skip_reason"])
        else:
            require(dispatch is not None, "COMPLETION_WITHOUT_DISPATCH")
            require(
                all(same(row.get(key), value) for key, value in dispatch.items()),
                "DISPATCH_ROW_BINDING_MISMATCH",
            )
            if axis != "target":
                require(
                    row.get("dispatched") is True
                    and owner is not None
                    and owner["dispatched"] is True,
                    "COMPLETION_OWNER_MISSING_OR_CHANGED",
                )
            else:
                cool = values.get("cooldown")
                require(
                    cool is not None
                    and cool.get("cooldown_passed") is True
                    and sha(canonical(cool)) == dispatch.get("cooldown_receipt_sha256"),
                    "COMPLETION_COOLDOWN_METADATA_MISMATCH",
                )
            seconds = row.get("latency_seconds" if axis == "target" else "inference_seconds")
            require(number(seconds), "LATENCY_METADATA_INVALID")
            begin, end = utc(row.get("dispatch_at")), utc(row.get("received_at"))
            require(begin <= end, "COMPLETION_TIMESTAMPS_REVERSED")
            output.update(
                state=STATES[0],
                latency_seconds=seconds,
                dispatch_at=begin.isoformat(),
                received_at=end.isoformat(),
            )
        if dispatch is not None:
            output["dispatch_at"] = utc(dispatch.get("dispatch_at")).isoformat()
        if "cooldown" in values:
            wait = values["cooldown"].get("wait_seconds")
            require(number(wait), "COOLDOWN_TIMING_INVALID")
            output["cooldown_seconds"] = wait
    except (InventoryError, KeyError, TypeError, ValueError, OverflowError) as error:
        output = {
            "ordinal": item["ordinal"],
            "kind": item["kind"],
            "state": STATES[5],
            "issue_codes": [
                safe_code(str(error))
                if isinstance(error, InventoryError)
                else "METADATA_SCHEMA_INVALID"
            ],
        }
    return output


def ranges(numbers):
    output = []
    for number_ in sorted(numbers):
        if output and number_ == output[-1][1] + 1:
            output[-1][1] = number_
        else:
            output.append([number_, number_])
    return output


def summarize(rows):
    counts = Counter(row["state"] for row in rows)
    grouped = {
        state: ranges(row["ordinal"] for row in rows if row["state"] == state) for state in STATES
    }
    terminal = {STATES[0], STATES[1]}
    prefix = 0
    for row in rows:
        if row["state"] not in terminal:
            break
        prefix += 1
    return {
        "planned_records": len(rows),
        "state_counts": {s: counts[s] for s in STATES},
        "ordinal_ranges_by_state": grouped,
        "terminal_metadata_prefix_records": prefix,
        "recorded_completion_by_kind": dict(
            Counter(row["kind"] for row in rows if row["state"] == STATES[0])
        ),
        "recorded_answer_seconds": sum(row.get("latency_seconds", 0) for row in rows),
        "recorded_cooldown_seconds": sum(row.get("cooldown_seconds", 0) for row in rows),
    }


def worker_pair(relative, started, stopped):
    """Check identities asserted by the paired SAFE markers, not process liveness."""
    require(type(started.get("pid")) is int and started["pid"] > 0, "WORKER_PAIR_IDENTITY_MISMATCH")
    fixed = {"contract_sha256": CONFIG_SHA, "pid": started["pid"]}
    if relative.startswith("epochs/"):
        # The frozen target helper owns server-01 inside each outer numeric epoch.
        fixed.update(epoch=1, owned_process_only=True)
    else:
        axis = relative.split("/")[1]
        fixed.update(
            axis=axis,
            epoch_index=1,
            bound_plan_identity_sha256=PLAN_ID,
            worker_identity_sha256=sha(canonical([CONFIG_SHA, axis, 1])),
        )
    require(
        all(
            same(value.get(key), expected)
            for value in (started, stopped)
            for key, expected in fixed.items()
        ),
        "WORKER_PAIR_IDENTITY_MISMATCH",
    )
    require(utc(started["started_at"]) <= utc(stopped["stopped_at"]), "WORKER_TIMESTAMPS_REVERSED")


def inventory(root, config_sha=CONFIG_SHA, plan_sha=PLAN_SHA, *, quiescent=False, details=False):
    require(type(quiescent) is bool and type(details) is bool, "BOOLEAN_OPTIONS_REQUIRED")
    _, plan = load_frame(root, config_sha, plan_sha)
    began = datetime.now(timezone.utc).isoformat()
    before = manifest(root)
    receipts, read_errors = {}, []
    for relative in sorted(before):
        try:
            raw = read_bytes(scoped(root, f"{SAFE}/{CONFIG_SHA}/{relative}"))
            receipts[relative] = {"value": strict(raw), "file_sha256": sha(raw)}
        except (InventoryError, OSError) as error:
            code = (
                safe_code(str(error))
                if isinstance(error, InventoryError)
                else "FILE_READ_RACE_OR_IO"
            )
            receipts[relative] = {"error": code}
            read_errors.append(code)
    after = manifest(root)
    rows_by_axis = {}
    observed = {"target": {}, "qwen": {}, "jailmeter": {}}
    extras = Counter()
    known = {row["request_id"]: row for row in plan["requests"]}
    for relative, receipt in receipts.items():
        match = REQUEST_PATH.fullmatch(relative)
        if match:
            axis, rid = match["area"].split("/")[-1], match["rid"]
            if rid not in known or (axis != "target" and known[rid]["kind"] != "science"):
                extras[axis] += 1
            else:
                observed[axis].setdefault(rid, {})[match["part"]] = receipt
    for axis in observed:
        frame = [row for row in plan["requests"] if axis == "target" or row["kind"] == "science"]
        rows_by_axis[axis] = [
            classify(item, axis, observed[axis].get(item["request_id"], {})) for item in frame
        ]
        if axis != "target":
            for item, accounting in zip(frame, rows_by_axis[axis], strict=True):
                rid = item["request_id"]
                parts = observed[axis].get(rid, {})
                if accounting["state"] not in {STATES[0], STATES[1]}:
                    continue
                try:
                    source = observed["target"].get(rid, {}).get("row", {}).get("value")
                    require(source is not None, "AXIS_TARGET_SAFE_ROW_MISSING")
                    bound = {
                        "target_row_identity_sha256": sha(canonical(source)),
                        "target_raw_reply_sha256": source.get("raw_reply_sha256"),
                        "target_request_sha256": source.get("request_sha256"),
                        "response_sha256": source.get("response_sha256"),
                    }
                    require(
                        all(
                            same(parts["row"]["value"].get(key), value)
                            for key, value in bound.items()
                        ),
                        "AXIS_TARGET_SAFE_HASH_MISMATCH",
                    )
                    require(
                        parts["ownership"]["value"].get("target_row_identity_sha256")
                        == bound["target_row_identity_sha256"],
                        "OWNER_TARGET_SAFE_HASH_MISMATCH",
                    )
                except (InventoryError, KeyError, TypeError):
                    accounting.update(
                        state=STATES[5], issue_codes=["AXIS_TARGET_SAFE_LINK_INVALID"]
                    )
                    for key in ("latency_seconds", "dispatch_at", "received_at", "skip_reason"):
                        accounting.pop(key, None)
    issues, aborts, open_workers = [], [], []
    for relative, receipt in receipts.items():
        if "error" in receipt:
            continue
        value = receipt["value"]
        if (
            relative in TOP_FILES
            or EPOCH_PATH.fullmatch(relative)
            or PANEL_PATH.fullmatch(relative)
        ):
            if value.get("contract_sha256") != CONFIG_SHA:
                issues.append("GLOBAL_METADATA_CONTRACT_MISMATCH")
            if "abort" in relative:
                area = (
                    relative.split("/")[1]
                    if relative.startswith("panel/")
                    else "qwen"
                    if relative.startswith("panel-qwen-")
                    else "jailmeter"
                    if relative.startswith("panel-jailmeter-")
                    else "target"
                )
                aborts.append(
                    {
                        "area": area,
                        "reason_code": safe_code(value.get("error_code")),
                    }
                )
            if relative.endswith(".started.safe.json"):
                stopped = relative.replace(".started.safe.json", ".stopped.safe.json")
                if stopped not in receipts:
                    open_workers.append(relative)
                elif "error" not in receipts[stopped]:
                    stop = receipts[stopped]["value"]
                    try:
                        worker_pair(relative, value, stop)
                    except (InventoryError, KeyError, TypeError) as error:
                        issues.append(
                            safe_code(str(error))
                            if isinstance(error, InventoryError)
                            else "WORKER_PAIR_METADATA_INVALID"
                        )
                        open_workers.append(relative)
                else:
                    open_workers.append(relative)
            elif relative.endswith(".stopped.safe.json"):
                if relative.replace(".stopped.safe.json", ".started.safe.json") not in receipts:
                    issues.append("WORKER_STOP_WITHOUT_START")
    # Judges pre-record skips throughout the frame; only actual dispatches must keep plan order.
    for rows in rows_by_axis.values():
        last = None
        missing_dispatch = False
        for row in rows:
            if "dispatch_at" in row:
                if last is not None and utc(row["dispatch_at"]) < last:
                    issues.append("DISPATCH_TIME_ORDER_INCONSISTENT")
                if missing_dispatch:
                    issues.append("DISPATCH_AFTER_UNRECORDED_PLAN_ITEM")
                last = utc(row.get("received_at", row["dispatch_at"]))
            elif row["state"] != STATES[1]:
                missing_dispatch = True
    changed = before != after or "FILE_CHANGED_DURING_READ" in read_errors
    active_lock = (
        "target-operation.lock.safe.json" in before or "target-operation.lock.safe.json" in after
    )
    malformed = sum(row["state"] == STATES[5] for rows in rows_by_axis.values() for row in rows)
    unresolved = sum(
        row["state"] in {STATES[3], STATES[4]} for rows in rows_by_axis.values() for row in rows
    )
    strict_accounting = not (
        changed
        or active_lock
        or open_workers
        or read_errors
        or issues
        or extras
        or malformed
        or unresolved
    )
    result = {
        "schema_version": "jbspan-pa-llama-topology-safe-prefix-inventory-v1",
        "purpose": "PROGRESS_ACCOUNTING_ONLY_NOT_PARTIAL_SCIENTIFIC_ANALYSIS",
        "config_file_sha256": CONFIG_SHA,
        "bound_plan_file_sha256": PLAN_SHA,
        "bound_plan_identity_sha256": PLAN_ID,
        "all_stable_population_count": 21,
        "snapshot_started_at": began,
        "snapshot_finished_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_is_atomic": False,
        "quiescent_mode_requested": quiescent,
        "directory_metadata_changed_during_snapshot": changed,
        "active_operation_lock_observed": active_lock,
        "unclosed_worker_markers": len(open_workers),
        "quiescent_safe_accounting_consistent": strict_accounting if quiescent else None,
        "transient_states_may_be_inflight": bool(
            not quiescent or changed or active_lock or open_workers or read_errors
        ),
        "safe_file_read_attempts": len(receipts),
        "safe_files_read": sum("value" in value for value in receipts.values()),
        "successful_safe_file_reads": sum("value" in value for value in receipts.values()),
        "safe_file_content_manifest_sha256": sha(
            canonical(
                {
                    key: value.get("file_sha256", value.get("error"))
                    for key, value in receipts.items()
                }
            )
        ),
        "axes": {axis: summarize(rows) for axis, rows in rows_by_axis.items()},
        "out_of_frame_safe_files_by_axis": dict(extras),
        "metadata_issue_codes": sorted(set(issues)),
        "read_error_counts": dict(Counter(read_errors)),
        "abort_records": aborts,
        "raw_receipts_reverified": False,
        "operational_certification_performed": False,
        "scientific_analysis_performed": False,
        "judge_labels_read_for_analysis": False,
        "missing_judge_is_abstention": False,
        "paper_validity": False,
        "execution_authorized": False,
        "new_model_calls": 0,
        "private_files_read": 0,
        "historical_data_files_read": 0,
        "files_written": 0,
        "limitations": [
            "SAFE_ROWS_ARE_RECORDED_CLAIMS_NOT_RAW_VERIFICATION",
            "NO_SAFE_DISPATCH_OBSERVED_DOES_NOT_PROVE_NO_HTTP_OR_PRIVATE_ACTIVITY",
            "DETERMINISTIC_SKIP_REASON_RECORDED_NOT_RECOMPUTED",
            "NO_PROCESS_LIVENESS_CHECK_OR_AUTOMATIC_RETRY",
            "STABLE_DIRECTORY_MANIFEST_IS_NOT_AN_ATOMIC_SNAPSHOT",
        ],
    }
    if details:
        result["request_accounting"] = rows_by_axis
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--bound-plan-sha256", required=True)
    parser.add_argument("--quiescent", action="store_true")
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args(argv)
    try:
        value = inventory(
            args.root,
            args.config_sha256,
            args.bound_plan_sha256,
            quiescent=args.quiescent,
            details=args.details,
        )
        print(canonical(value).decode("utf-8"))
        return 2 if args.quiescent and not value["quiescent_safe_accounting_consistent"] else 0
    except (InventoryError, OSError, KeyError, TypeError, ValueError) as error:
        code = (
            safe_code(str(error))
            if isinstance(error, InventoryError)
            else "SAFE_INVENTORY_INPUT_ERROR"
        )
        print(
            canonical(
                {
                    "error_code": code,
                    "files_written": 0,
                    "new_model_calls": 0,
                    "scientific_analysis_performed": False,
                }
            ).decode()
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
