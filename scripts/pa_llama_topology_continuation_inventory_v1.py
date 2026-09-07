"""Read-only SAFE accounting. No raw, process, operational, or scientific certification.

SAFE JSON files are parsed but only the explicit accounting fields below are
consulted. Private files, logs, prompts, replies and scientific labels are never
opened or projected. A concurrent filesystem snapshot is always non-atomic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

AMENDMENT = "6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0"
PARENT = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN_ID = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
PLAN_SHA = "3a8bc4391f2ba6d02f2de446bd8b4ff61d1c1ac121fb3c57044bee379df1615b"
CONFIG = "configs/natural_language_localization/pa_llama_topology_target_continuation_v1.json"
PLAN = ("data/natural_language_localization/pa_llama_topology_preparation_v1/"
        "fe0af6381817cddc6da856da69fccc2b7a9a282e8a4cce7707c81070f8489a82/bound-plan.safe.json")
SAFE = "data/natural_language_localization/pa_llama_topology_target_continuation_v1"
PREFIX = f"{SAFE}/{PARENT}/prefix-manifest.safe.json"
STATES = ("RECORDED_COMPLETION_SAFE_ONLY", "RECORDED_SKIP_SAFE_ONLY", "NO_SAFE_DISPATCH_OBSERVED",
          "PREDISPATCH_ONLY", "DISPATCH_WITHOUT_COMPLETION_AMBIGUOUS", "INCONSISTENT_METADATA")
PART = re.compile(r"([0-9a-f]{64})\.(dispatch|row|ownership|cooldown|tpl)\.safe\.json\Z")
TOP = {"target-operation.lock.safe.json", "generate-started.safe.json", "generate-aborted.safe.json",
       "panel-qwen-aborted.safe.json", "panel-jailmeter-aborted.safe.json", "finalize-aborted.safe.json"}
NOT_OPENED = {"targets.safe.json", "target-verification.safe.json", "continued-measurements.safe.json",
              "continued-analysis.safe.json", "continued-result.safe.json", "continued-verification.safe.json"}
EPOCH = {"server-01.started.safe.json", "server-01.stopped.safe.json", "resource.safe.json",
         "server-01.identity.safe.json", "server-01.tpl.safe.json", "amendment.safe.json"}
AXIS = {"worker.started.safe.json", "worker.stopped.safe.json", "resources.safe.json", "abort.safe.json"}
MAX_BYTES = 8_000_000


class AccountingError(ValueError):
    """Only fixed, content-free error codes."""


def require(condition, code):
    if not condition:
        raise AccountingError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def same(a, b):
    return canonical(a) == canonical(b)


def utc(value):
    require(isinstance(value, str), "INVALID_UTC")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AccountingError("INVALID_UTC") from None
    require(stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0, "INVALID_UTC")
    return stamp


def scoped(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative
            and all(x not in {"", ".", ".."} for x in relative.split("/")), "PATH_REJECTED")
    base = Path(root).resolve()
    path = base.joinpath(*relative.split("/"))
    try:
        path.resolve().relative_to(base)
    except (ValueError, OSError):
        raise AccountingError("PATH_REJECTED") from None
    for part in (path, *path.parents):
        if part == base.parent:
            break
        if part.exists():
            require(not part.is_symlink() and not (getattr(part.lstat(), "st_file_attributes", 0) & 1024),
                    "LINK_OR_REPARSE_REJECTED")
    return Path("\\\\?\\" + str(path)) if os.name == "nt" else path


def read(path):
    before = path.stat()
    require(path.is_file() and 0 < before.st_size <= MAX_BYTES, "FILE_SIZE_INVALID")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    after = path.stat()
    require(len(raw) == before.st_size and (before.st_size, before.st_mtime_ns, before.st_ino)
            == (after.st_size, after.st_mtime_ns, after.st_ino), "FILE_CHANGED_DURING_READ")
    return raw


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    def nonfinite(_):
        raise AccountingError("NONFINITE_JSON")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
        require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise AccountingError("MALFORMED_JSON") from None


def pinned(root, relative, sha, size=None):
    raw = read(scoped(root, relative))
    require(digest(raw) == sha and (size is None or len(raw) == size), "EXTERNAL_PIN_MISMATCH")
    return strict(raw)


def frame(root, amendment_sha):
    require(amendment_sha == AMENDMENT, "EXACT_FROZEN_AMENDMENT_SHA_REQUIRED")
    config = pinned(root, CONFIG, amendment_sha)
    plan = pinned(root, PLAN, PLAN_SHA)
    require(config.get("frozen") is True and config.get("execution_authorized") is True
            and config.get("original_contract_sha256") == PARENT
            and config.get("bound_plan_identity_sha256") == PLAN_ID
            and plan.get("plan_identity_sha256") == PLAN_ID
            and config.get("original_operational_gate_passed") is False,
            "FRAME_PROVENANCE_CHANGED")
    pin = config.get("prefix_manifest", {})
    require(pin.get("path") == PREFIX, "PREFIX_PATH_CHANGED")
    prefix = pinned(root, PREFIX, pin.get("sha256"), pin.get("size_bytes"))
    require(same(prefix.get("original_prefix_count"), 872)
            and prefix.get("original_contract_sha256") == PARENT, "PREFIX_DECLARATION_CHANGED")
    rows = [{key: row[key] for key in ("request_id", "ordinal", "kind")} for row in plan["requests"]]
    require(same([r["ordinal"] for r in rows], list(range(1, 1471)))
            and len({r["request_id"] for r in rows}) == 1470
            and all(re.fullmatch(r"[0-9a-f]{64}", r["request_id"]) for r in rows)
            and Counter(r["kind"] for r in rows) == {"science": 882, "control": 588}
            and Counter(r["kind"] for r in rows[:872]) == {"science": 536, "control": 336},
            "ALL1470_FRAME_REQUIRED")
    return rows, pin["sha256"]


def manifest(root, base):
    """Enumerate only exact depth/category names; never traverse an unknown directory."""
    entries, issues = {}, []
    directories = {"": TOP | NOT_OPENED, "target": set()}
    directories.update({f"epochs/{i:03d}": EPOCH for i in (3, 4, 5)})
    directories.update({f"panel/{axis}": AXIS | {"axis.safe.json", "samples.safe.jsonl"}
                        for axis in ("qwen", "jailmeter")})
    for relative, names in directories.items():
        directory = scoped(root, base + ("/" + relative if relative else ""))
        if not directory.exists():
            continue
        for candidate in directory.iterdir():
            child = f"{relative}/{candidate.name}".lstrip("/")
            path = scoped(root, base + "/" + child)
            if path.is_dir():
                if relative or candidate.name not in {"target", "epochs", "panel"}:
                    issues.append("UNEXPECTED_DIRECTORY")
                continue
            match = PART.fullmatch(candidate.name)
            allowed_part = match and (relative == "target" and match[2] != "ownership"
                or relative.startswith("panel/") and match[2] in {"dispatch", "row", "ownership"})
            if candidate.name not in names and not allowed_part:
                issues.append("UNEXPECTED_SAFE_FILENAME")
                continue
            stat = path.stat()
            entries[child] = {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    for relative, allowed in (("epochs", {"003", "004", "005"}), ("panel", {"qwen", "jailmeter"})):
        directory = scoped(root, base + "/" + relative)
        if directory.exists() and {p.name for p in directory.iterdir()} - allowed:
            issues.append("UNEXPECTED_CONTAINER_CHILD")
    require(len(entries) <= 9000, "SAFE_METADATA_COUNT_EXCEEDED")
    return entries, issues


def validate_binding(value, item, area):
    require(value.get("contract_sha256") == PARENT and value.get("request_id") == item["request_id"],
            "REQUEST_BINDING_MISMATCH")
    if area == "target":
        require(same(value.get("ordinal"), item["ordinal"]) and value.get("kind") == item["kind"],
                "TARGET_ORDER_OR_KIND_MISMATCH")
    else:
        require(value.get("axis") == area.split("/")[1], "AXIS_BINDING_MISMATCH")


def request_state(item, area, values):
    parts = {part: values.get(f"{area}/{item['request_id']}.{part}.safe.json")
             for part in ("dispatch", "row", "ownership", "cooldown", "tpl")}
    for key in ("dispatch", "row"):
        if parts[key] is not None:
            validate_binding(parts[key], item, area)
    journal, row, owner = parts["dispatch"], parts["row"], parts["ownership"]
    if owner is not None:
        validate_binding(owner, item, area)
        require(owner.get("bound_plan_identity_sha256") == PLAN_ID
                and owner.get("target_execution_amendment_sha256") == AMENDMENT,
                "AXIS_OWNER_AMENDMENT_MISMATCH")
    if journal is not None and row is not None:
        require(utc(journal.get("dispatch_at")) <= utc(row.get("received_at")), "RECEIPT_TIME_ORDER")
        for key in ("request_sha256", "dispatch_at"):
            require(key in journal and same(journal[key], row.get(key)), "ROW_JOURNAL_MISMATCH")
        if area == "target":
            require(parts["cooldown"] is not None and parts["tpl"] is not None, "TARGET_METADATA_MISSING")
        else:
            require(row.get("dispatched") is True and owner is not None
                    and owner.get("dispatched") is True, "AXIS_DISPATCH_OWNER_MISMATCH")
        return STATES[0]
    if journal is not None:
        return STATES[4]
    if row is not None:
        require(area != "target" and row.get("dispatched") is False and owner is not None
                and owner.get("dispatched") is False
                and row.get("skip_reason") in {"TARGET_INELIGIBLE", "EVALUATOR_CONTEXT_BOUND"},
                "ROW_WITHOUT_DISPATCH_NOT_EXPLICIT_SKIP")
        return STATES[1]
    return STATES[3] if any(value is not None for value in parts.values()) else STATES[2]


def lifecycle(values):
    workers, issues = [], []
    pairs = [(f"epochs/{i:03d}/server-01", "target") for i in (3, 4, 5)]
    pairs += [(f"panel/{axis}/worker", axis) for axis in ("qwen", "jailmeter")]
    for stem, kind in pairs:
        start, stop = (values.get(stem + suffix + ".safe.json") for suffix in (".started", ".stopped"))
        if start is None and stop is None:
            continue
        matched = False
        try:
            require(start is not None and stop is not None, "UNCLOSED_WORKER_MARKER")
            keys = ("contract_sha256", "pid", "epoch", "owned_process_only") if kind == "target" else (
                "contract_sha256", "pid", "axis", "epoch_index", "worker_identity_sha256",
                "bound_plan_identity_sha256", "target_execution_amendment_sha256")
            require(all(key in start and same(start[key], stop.get(key)) for key in keys)
                    and start["contract_sha256"] == PARENT and type(start["pid"]) is int
                    and start["pid"] > 0 and utc(start.get("started_at")) <= utc(stop.get("stopped_at")),
                    "WORKER_PAIR_BINDING_MISMATCH")
            require((same(start.get("epoch"), 1) and start.get("owned_process_only") is True)
                    if kind == "target" else (start.get("axis") == kind
                    and same(start.get("epoch_index"), 1) and start.get("bound_plan_identity_sha256") == PLAN_ID
                    and start.get("target_execution_amendment_sha256") == AMENDMENT),
                    "WORKER_EXPECTED_BINDING_MISMATCH")
            matched = True
        except (AccountingError, TypeError, KeyError) as error:
            issues.append(str(error) if isinstance(error, AccountingError) else "WORKER_FIELDS_INVALID")
        workers.append({"scope": stem, "start_marker_present": start is not None,
                        "stop_marker_present": stop is not None, "matching_stopped_marker": matched})
    return workers, issues


def inventory(root, amendment_sha=AMENDMENT, *, quiescent=False):
    began = datetime.now(timezone.utc).isoformat()
    rows, prefix_sha = frame(root, amendment_sha)
    base = f"{SAFE}/{amendment_sha}"
    before, issues = manifest(root, base)
    values, read_errors = {}, set()
    for relative in before:
        name = relative.split("/")[-1]
        if name in NOT_OPENED | {"axis.safe.json", "samples.safe.jsonl"}:
            continue
        try:
            values[relative] = strict(read(scoped(root, base + "/" + relative)))
        except (AccountingError, OSError):
            read_errors.add(relative)
            issues.append("SAFE_FILE_UNREADABLE_OR_CHANGING")
    frames = {"target": rows[872:], **{f"panel/{axis}": [r for r in rows if r["kind"] == "science"]
                                       for axis in ("qwen", "jailmeter")}}
    summaries = {}
    for area, items in frames.items():
        counts, kind_counts, classified = Counter(), {k: Counter() for k in ("science", "control")}, []
        allowed = {item["request_id"] for item in items}
        if any(PART.fullmatch(path.split("/")[-1]) and path.startswith(area + "/")
               and path.split("/")[-1].split(".")[0] not in allowed for path in before):
            issues.append("SAFE_REQUEST_OUTSIDE_FIXED_FRAME")
        for item in items:
            try:
                require(not any(path.startswith(f"{area}/{item['request_id']}.") for path in read_errors),
                        "UNREADABLE_REQUEST_METADATA")
                state = request_state(item, area, values)
            except (AccountingError, TypeError, KeyError, ValueError):
                state = STATES[5]
                issues.append("REQUEST_METADATA_INCONSISTENT")
            counts[state] += 1
            kind_counts[item["kind"]][state] += 1
            classified.append((item["ordinal"], state))
        summaries[area] = {"planned": len(items), "counts": {s: counts[s] for s in STATES},
            "by_kind": {k: dict(v) for k, v in kind_counts.items() if v},
            "first_not_recorded_complete_or_skipped_ordinal": next((i for i, s in classified
                if s not in STATES[:2]), None),
            "ambiguous_ordinals": [i for i, s in classified if s == STATES[4]],
            "predispatch_only_ordinals": [i for i, s in classified if s == STATES[3]]}
    workers, worker_issues = lifecycle(values)
    issues += worker_issues
    aborts = [{"path": path, "error_code": value.get("error_code") if isinstance(value.get("error_code"), str)
               and re.fullmatch(r"[A-Z0-9_]{1,100}", value["error_code"]) else "UNSPECIFIED_SAFE_CODE"}
              for path, value in values.items() if path.endswith("-aborted.safe.json") or path.endswith("/abort.safe.json")]
    after, after_issues = manifest(root, base)
    issues += after_issues
    changed = before != after
    quiet = not (issues or changed or aborts or "target-operation.lock.safe.json" in before
        or any(not w["matching_stopped_marker"] for w in workers)
        or any(v["counts"][s] for v in summaries.values() for s in STATES[3:]))
    return {"schema_version": "jbspan-topology-continuation-safe-accounting-v1", "amendment_sha256": amendment_sha,
        "bound_plan_file_sha256": PLAN_SHA, "prefix_manifest_sha256": prefix_sha,
        "original_baseline_declared": {"records": 872, "science": 536, "control": 336,
            "original_operational_gate_passed": False, "independently_reverified_here": False},
        "frames": summaries, "owned_lifecycle_markers": workers, "aborts": aborts,
        "mode": "QUIESCENT_REQUESTED" if quiescent else "LIVE_OBSERVATION", "snapshot_atomic": False,
        "manifest_changed_during_snapshot": changed, "safe_manifest_identity_sha256": digest(canonical(after)),
        "successful_safe_metadata_reads": len(values), "unreadable_metadata_files": len(read_errors),
        "issues": sorted(set(issues)), "active_lock_marker_present": "target-operation.lock.safe.json" in before,
        "quiescent_safe_accounting_consistent": bool(quiescent and quiet),
        "recorded_target_total_including_declared_baseline": 872 + summaries["target"]["counts"][STATES[0]],
        "process_liveness_checked": False, "raw_receipts_verified": False, "operational_pass_certified": False,
        "scientific_analysis_performed": False, "unrun_judge_is_not_abstain": True,
        "no_safe_dispatch_observed_is_not_proof_of_no_http": True, "private_reads": 0, "new_model_calls": 0,
        "experiment_writes": 0, "paper_validity": False, "started_at": began,
        "finished_at": datetime.now(timezone.utc).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--amendment-sha256", default=AMENDMENT)
    parser.add_argument("--quiescent", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inventory(args.root, args.amendment_sha256, quiescent=args.quiescent)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 2 if args.quiescent and not result["quiescent_safe_accounting_consistent"] else 0
    except (AccountingError, OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"completed": False, "error_code": str(error) if isinstance(error, AccountingError)
                          else "SAFE_ACCOUNTING_INPUT_INVALID", "raw_receipts_verified": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
