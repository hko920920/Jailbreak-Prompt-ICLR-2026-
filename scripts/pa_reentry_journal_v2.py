"""Durable, fail-closed local request journal; no model or network implementation.

Dispatch authorization is a bounded *admission* window, not permission to discard
late responses. A durable intent without a fully verifiable response is ambiguous
and is never automatically retried. This is not universal exactly-once execution.
All scientific parsing and process/resource verification belong to frozen adapters.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
import re
import stat
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

GIB = 1024**3
STAGE_HOURS = {"target": 2, "qwen": 2, "jailmeter": 6}
AUTH_SCHEMA = "pa-reentry-stage-authorization-v2"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,191}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
SAFE_FORBIDDEN = {
    "prompt",
    "content",
    "response",
    "raw",
    "raw_base64",
    "goal_text",
    "response_text",
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def stamp(value):
    require(isinstance(value, str), "JOURNAL_TIME_TYPE")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("JOURNAL_TIME_FORMAT") from None
    require(
        result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
        "JOURNAL_TIME_NOT_UTC",
    )
    return result


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "JOURNAL_DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("JOURNAL_NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json(path, maximum=32_000_000):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "JOURNAL_FILE_MISSING_OR_LINK")
    require(path.stat().st_size <= maximum, "JOURNAL_FILE_OVERSIZED")
    return strict_json(path.read_bytes())


def safe(value):
    if isinstance(value, dict):
        for key, item in value.items():
            require(
                isinstance(key, str) and key not in SAFE_FORBIDDEN, "JOURNAL_PRIVATE_FIELD_IN_SAFE"
            )
            safe(item)
    elif isinstance(value, list):
        for item in value:
            safe(item)
    canonical(value)
    return value


def seal(value, field="identity_sha256"):
    require(field not in value, "JOURNAL_ALREADY_SEALED")
    return {**value, field: digest(value)}


def verify_seal(value, field="identity_sha256"):
    require(
        isinstance(value, dict)
        and value.get(field) == digest({k: v for k, v in value.items() if k != field}),
        "JOURNAL_IDENTITY_CHANGED",
    )
    return value


def make_authorization(execution_identity, stage, *, issued_at, expires_at, direction_ref):
    """Return a receipt only; callers must have a real, later stage direction.

    Hashing a reference does not authenticate the user. The orchestrator must
    supply that direction; stage-2 preparation must not mint launch receipts.
    """
    result = seal(
        {
            "schema_version": AUTH_SCHEMA,
            "execution_identity": execution_identity,
            "stage": stage,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "direction_ref": direction_ref,
        },
        "authorization_identity_sha256",
    )
    validate_authorization(result, execution_identity, stage, now=issued_at)
    return result


def validate_authorization(auth, execution_identity, stage, now=None):
    require(
        stage in STAGE_HOURS
        and isinstance(execution_identity, str)
        and SHA.fullmatch(execution_identity),
        "JOURNAL_EXECUTION_OR_STAGE_INVALID",
    )
    verify_seal(auth, "authorization_identity_sha256")
    require(
        set(auth)
        == {
            "schema_version",
            "execution_identity",
            "stage",
            "issued_at",
            "expires_at",
            "direction_ref",
            "authorization_identity_sha256",
        },
        "JOURNAL_AUTH_FIELDS",
    )
    require(
        auth["schema_version"] == AUTH_SCHEMA
        and auth["execution_identity"] == execution_identity
        and auth["stage"] == stage,
        "JOURNAL_AUTH_WRONG_STAGE_OR_EXECUTION",
    )
    require(
        isinstance(auth["direction_ref"], str)
        and 1 <= len(auth["direction_ref"]) <= 512
        and not any(ch in auth["direction_ref"] for ch in "\r\n\0"),
        "JOURNAL_USER_DIRECTION_REFERENCE_REQUIRED",
    )
    issued, expires = stamp(auth["issued_at"]), stamp(auth["expires_at"])
    require(
        0 < (expires - issued).total_seconds() <= STAGE_HOURS[stage] * 3600,
        "JOURNAL_AUTH_WINDOW_TOO_LONG_OR_EMPTY",
    )
    observed = stamp(now or utc()) if not isinstance(now, datetime) else now
    require(
        observed.tzinfo is not None and observed.utcoffset().total_seconds() == 0,
        "JOURNAL_AUTH_OBSERVATION_NOT_UTC",
    )
    require(issued <= observed <= expires, "JOURNAL_AUTH_NOT_CURRENT")
    return auth


def pending_path(path):
    path = Path(path)
    return path.with_name(path.name + ".pending")


def reject_links(path):
    """Reject existing symlink/reparse ancestors before following an output path."""
    path = Path(os.path.abspath(path))
    for candidate in (path, *path.parents):
        try:
            observed = candidate.lstat()
        except FileNotFoundError:
            continue
        require(
            not stat.S_ISLNK(observed.st_mode)
            and not (getattr(observed, "st_file_attributes", 0) & 1024),
            "JOURNAL_OUTPUT_LINK_OR_REPARSE_POINT",
        )


def _sync_directory(path):
    # Windows lacks a portable directory fsync. Do not claim power-loss proof.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_bytes(path, raw, *, crash=None):
    """Exclusive publication through one owned pending leaf; never replace data."""
    path = Path(path)
    reject_links(path)
    require(isinstance(raw, bytes), "JOURNAL_BYTES_REQUIRED")
    require(not path.exists() and not path.is_symlink(), "JOURNAL_ALREADY_PUBLISHED")
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_links(path.parent)
    temporary = pending_path(path)
    with temporary.open("xb") as handle:
        if crash:
            crash("publication_pending_created")
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        if crash:
            crash("publication_pending_written")
    # A hard link atomically creates the destination without clobbering it.
    # An interrupted duplicate link is reconciled by exact bytes, never guessed.
    os.link(temporary, path)
    _sync_directory(path.parent)
    if crash:
        crash("publication_published")
    temporary.unlink()
    _sync_directory(path.parent)


def atomic_json(path, value, *, crash=None):
    atomic_bytes(path, canonical(value) + b"\n", crash=crash)


def _artifact(path, maximum=32_000_000):
    """Read published/pending bytes, detecting conflicting duplicate publications."""
    path = Path(path)
    temporary = pending_path(path)
    copies = [
        candidate for candidate in (path, temporary) if candidate.exists() or candidate.is_symlink()
    ]
    if not copies:
        return None, False
    for candidate in copies:
        require(not candidate.is_symlink() and candidate.is_file(), "JOURNAL_ARTIFACT_NOT_REGULAR")
        require(candidate.stat().st_size <= maximum, "JOURNAL_FILE_OVERSIZED")
    raw = copies[0].read_bytes()
    require(
        all(candidate.read_bytes() == raw for candidate in copies[1:]),
        "JOURNAL_CONFLICTING_PUBLICATION",
    )
    return raw, temporary in copies


def _finish_pending(path, expected):
    """Only called after semantic verification of the exact complete artifact."""
    path = Path(path)
    observed, _ = _artifact(path)
    require(observed == expected, "JOURNAL_PENDING_BYTES_CHANGED")
    temporary = pending_path(path)
    if not path.exists():
        os.link(temporary, path)
        _sync_directory(path.parent)
    if temporary.exists():
        require(
            temporary.read_bytes() == path.read_bytes() == expected,
            "JOURNAL_PENDING_DUPLICATE_CHANGED",
        )
        temporary.unlink()
        _sync_directory(path.parent)


@contextmanager
def run_lock(path):
    """Kernel lock, not PID-file ownership; crashes release it without stealing."""
    path = Path(path)
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_links(path.parent)
    require(not path.is_symlink(), "JOURNAL_LOCK_SYMLINK")
    handle = path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise ValueError("JOURNAL_LIVE_LOCK_NO_CONCURRENT_RUN") from None
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def validate_admission(value):
    safe(value)
    require(isinstance(value, dict), "JOURNAL_ADMISSION_REQUIRED")
    require(
        type(value.get("disk_free_bytes")) is int and value["disk_free_bytes"] >= 15 * GIB,
        "JOURNAL_DISK_BELOW_15_GIB",
    )
    temperature = value.get("temperature_c")
    require(
        type(temperature) in (int, float) and math.isfinite(temperature) and 0 <= temperature <= 60,
        "JOURNAL_DISPATCH_NOT_COOL",
    )


class Journal:
    def __init__(self, safe, private, execution_identity, stage):
        require(
            stage in STAGE_HOURS and SHA.fullmatch(execution_identity),
            "JOURNAL_EXECUTION_OR_STAGE_INVALID",
        )
        self.safe, self.private = Path(safe), Path(private)
        reject_links(self.safe)
        reject_links(self.private)
        require(self.safe.resolve() != self.private.resolve(), "JOURNAL_PRIVATE_SAFE_OVERLAP")
        self.execution_identity, self.stage = execution_identity, stage

    def paths(self, rid):
        require(
            isinstance(rid, str) and ID.fullmatch(rid) and rid not in {".", ".."},
            "JOURNAL_REQUEST_ID_INVALID",
        )
        return {
            "request": self.private / "requests" / rid / "request.private.json",
            "intent": self.safe / "requests" / rid / "intent.safe.json",
            "response": self.private / "requests" / rid / "response.private.json",
            "row": self.safe / "requests" / rid / "row.safe.json",
            "complete": self.safe / "requests" / rid / "complete.safe.json",
            "skip": self.safe / "requests" / rid / "skip.safe.json",
        }

    def audit_ids(self, allowed_ids):
        expected = set(allowed_ids)
        require(len(expected) == len(allowed_ids), "JOURNAL_DUPLICATE_FRAME_ID")
        for base in (self.safe, self.private):
            directory = base / "requests"
            if not directory.exists():
                continue
            require(not directory.is_symlink(), "JOURNAL_REQUEST_ROOT_LINK")
            for child in directory.iterdir():
                require(
                    child.is_dir() and not child.is_symlink() and child.name in expected,
                    "JOURNAL_UNEXPLAINED_REQUEST_ID",
                )
                self._closure(child.name)

    def _closure(self, rid):
        locations = self.paths(rid)
        allowed = set(locations.values()) | {pending_path(path) for path in locations.values()}
        for directory in {path.parent for path in locations.values()}:
            if directory.exists():
                require(not directory.is_symlink(), "JOURNAL_REQUEST_DIRECTORY_LINK")
                require(
                    all(
                        path in allowed and path.is_file() and not path.is_symlink()
                        for path in directory.iterdir()
                    ),
                    "JOURNAL_UNEXPLAINED_REQUEST_FILE",
                )

    def event(self, name, **fields):
        require(
            isinstance(name, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", name),
            "JOURNAL_EVENT_NAME",
        )
        forbidden = {
            "schema_version",
            "execution_identity",
            "stage",
            "event",
            "recorded_at",
            "event_identity_sha256",
        }
        require(not (forbidden & fields.keys()), "JOURNAL_EVENT_RESERVED_FIELDS")
        value = seal(
            safe(
                {
                    "schema_version": "pa-reentry-event-v2",
                    "execution_identity": self.execution_identity,
                    "stage": self.stage,
                    "event": name,
                    "recorded_at": utc(),
                    **fields,
                }
            ),
            "event_identity_sha256",
        )
        filename = f"{time.time_ns():020d}_{uuid.uuid4().hex}.safe.json"
        atomic_json(self.safe / "events" / filename, value)
        return value

    def progress(self, states, **fields):
        counts = {
            state: sum(value["state"] == state for value in states)
            for state in ("COMPLETE", "UNISSUED", "AMBIGUOUS")
        }
        require(sum(counts.values()) == len(states), "JOURNAL_INVALID_PROGRESS_STATE")
        return self.event(
            "PROGRESS",
            total=len(states),
            completed=counts["COMPLETE"],
            unissued=counts["UNISSUED"],
            ambiguous=counts["AMBIGUOUS"],
            repair_required=sum(bool(row.get("repair_required")) for row in states),
            checkpoint_authoritative=False,
            **fields,
        )

    def audit_events(self):
        """Report damaged summaries without using them to authorize requests."""
        directory = self.safe / "events"
        verified, invalid, pending = 0, 0, 0
        if directory.exists():
            require(not directory.is_symlink(), "JOURNAL_EVENT_DIRECTORY_LINK")
            for path in directory.iterdir():
                if path.name.endswith(".pending"):
                    pending += 1
                    continue
                try:
                    event = verify_seal(read_json(path), "event_identity_sha256")
                    require(
                        event.get("schema_version") == "pa-reentry-event-v2"
                        and event.get("execution_identity") == self.execution_identity
                        and event.get("stage") == self.stage,
                        "JOURNAL_EVENT_BINDING_CHANGED",
                    )
                    safe(event)
                    verified += 1
                except (ValueError, KeyError, TypeError, OSError, UnicodeError):
                    invalid += 1
        return {
            "verified_events": verified,
            "invalid_events": invalid,
            "pending_events": pending,
            "checkpoint_authoritative": False,
            "observed_event_artifacts_valid": invalid == pending == 0,
            "event_log_completeness_proven": False,
        }

    def _base(self, rid, body, binding):
        safe(binding)
        return {
            "execution_identity": self.execution_identity,
            "stage": self.stage,
            "request_id": rid,
            "request_sha256": digest(body),
            "binding": binding,
        }

    def claim_authorization(self, authorization):
        """One stage invocation per current user-direction receipt, even on failure."""
        validate_authorization(authorization, self.execution_identity, self.stage)
        identity = authorization["authorization_identity_sha256"]
        path = self.safe / "authorizations" / (identity + ".safe.json")
        require(
            not path.exists() and not pending_path(path).exists(),
            "JOURNAL_AUTH_ALREADY_ACTIVATED_NEW_DIRECTION_REQUIRED",
        )
        value = seal(
            {
                "schema_version": "pa-reentry-authorization-activation-v2",
                "execution_identity": self.execution_identity,
                "stage": self.stage,
                "authorization": authorization,
                "activated_at": utc(),
                "pid": os.getpid(),
                "next_stage_authorized": False,
            }
        )
        atomic_json(path, value)
        return value

    def inspect(self, rid, body, binding, parse, skip_row=None):
        """Read-only classification. COMPLETE can require derived publication repair."""
        try:
            return self._inspect(rid, body, binding, parse, skip_row)
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            OSError,
            UnicodeError,
            binascii.Error,
        ) as error:
            message = str(error)
            code = (
                message
                if re.fullmatch(r"[A-Z][A-Z0-9_]{0,191}", message)
                else "JOURNAL_INVALID_OR_PARTIAL_ARTIFACT"
            )
            return {
                "state": "AMBIGUOUS",
                "repair_required": False,
                "row": None,
                "reason": code,
                "request_id": rid,
            }

    def _inspect(self, rid, body, binding, parse, skip_row):
        self._closure(rid)
        paths = self.paths(rid)
        artifacts = {key: _artifact(path) for key, path in paths.items()}
        blobs = {key: value[0] for key, value in artifacts.items()}
        repairs = any(value[1] for value in artifacts.values())
        base = self._base(rid, body, binding)
        common = {
            "request_id": rid,
            "repair_required": repairs,
            "row": None,
            "reason": "VERIFIED_UNISSUED",
        }
        if blobs["skip"] is not None:
            require(
                skip_row is not None
                and all(
                    blobs[k] is None for k in ("request", "intent", "response", "row", "complete")
                ),
                "JOURNAL_SKIP_CONFLICTS_WITH_DISPATCH",
            )
            expected = seal({"schema_version": "pa-reentry-skip-v2", **base, "row": safe(skip_row)})
            require(strict_json(blobs["skip"]) == expected, "JOURNAL_SKIP_BINDING_OR_ROW_CHANGED")
            return {
                **common,
                "state": "COMPLETE",
                "reason": "VERIFIED_SKIP",
                "row": skip_row,
                "dispatched": False,
            }
        if skip_row is not None:
            require(all(raw is None for raw in blobs.values()), "JOURNAL_SKIP_WITH_PRIOR_ARTIFACT")
            return {**common, "state": "UNISSUED", "dispatched": False}
        if blobs["request"] is not None:
            require(blobs["request"] == canonical(body) + b"\n", "JOURNAL_REQUEST_BYTES_CHANGED")
        if blobs["intent"] is None:
            require(
                all(blobs[key] is None for key in ("response", "row", "complete")),
                "JOURNAL_ORPHAN_RESPONSE_OR_MARKER",
            )
            return {**common, "state": "UNISSUED"}
        require(blobs["request"] is not None, "JOURNAL_INTENT_WITHOUT_REQUEST")
        intent = verify_seal(strict_json(blobs["intent"]))
        require(
            intent.get("schema_version") == "pa-reentry-dispatch-v2"
            and all(intent.get(key) == value for key, value in base.items()),
            "JOURNAL_DISPATCH_BINDING_CHANGED",
        )
        require(
            set(intent)
            == {
                "schema_version",
                *base.keys(),
                "authorization",
                "epoch",
                "admission",
                "dispatch_at",
                "identity_sha256",
            },
            "JOURNAL_DISPATCH_FIELDS_CHANGED",
        )
        validate_authorization(
            intent["authorization"], self.execution_identity, self.stage, now=intent["dispatch_at"]
        )
        validate_admission(intent["admission"])
        require(
            isinstance(intent["epoch"], dict) and bool(intent["epoch"]), "JOURNAL_EPOCH_REQUIRED"
        )
        safe(intent["epoch"])
        require(blobs["response"] is not None, "JOURNAL_INFLIGHT_AMBIGUOUS_NO_RETRY")
        envelope = verify_seal(strict_json(blobs["response"]))
        require(
            set(envelope)
            == {"schema_version", "intent_identity_sha256", "meta", "raw_base64", "identity_sha256"}
            and envelope["schema_version"] == "pa-reentry-response-v2"
            and envelope["intent_identity_sha256"] == intent["identity_sha256"],
            "JOURNAL_RESPONSE_INTENT_CHANGED",
        )
        raw = base64.b64decode(envelope["raw_base64"], validate=True)
        require(0 < len(raw) <= 2_000_000, "JOURNAL_REPLY_SIZE")
        meta = envelope["meta"]
        require(
            set(meta)
            == {"received_at", "elapsed_seconds", "raw_sha256", "response_after_dispatch_window"},
            "JOURNAL_RECEIPT_META_CHANGED",
        )
        require(meta["raw_sha256"] == sha_bytes(raw), "JOURNAL_RESPONSE_HASH_CHANGED")
        require(
            type(meta["elapsed_seconds"]) in (int, float)
            and math.isfinite(meta["elapsed_seconds"])
            and meta["elapsed_seconds"] >= 0,
            "JOURNAL_LATENCY_INVALID",
        )
        require(
            stamp(meta["received_at"]) >= stamp(intent["dispatch_at"]),
            "JOURNAL_RECEIVE_PRECEDES_DISPATCH",
        )
        require(
            meta["response_after_dispatch_window"]
            is (stamp(meta["received_at"]) > stamp(intent["authorization"]["expires_at"])),
            "JOURNAL_LATE_RECEIPT_DISCLOSURE_CHANGED",
        )
        row = safe(parse(raw, meta, intent))
        require(isinstance(row, dict), "JOURNAL_PARSED_ROW_REQUIRED")
        if blobs["row"] is not None:
            require(strict_json(blobs["row"]) == row, "JOURNAL_ROW_RAW_REPLAY_CHANGED")
        marker = seal(
            {
                "schema_version": "pa-reentry-complete-v2",
                **base,
                "intent_identity_sha256": intent["identity_sha256"],
                "response_identity_sha256": envelope["identity_sha256"],
                "row_sha256": digest(row),
            }
        )
        if blobs["complete"] is not None:
            require(
                blobs["row"] is not None and strict_json(blobs["complete"]) == marker,
                "JOURNAL_COMPLETION_CHANGED_OR_ORPHANED",
            )
        return {
            **common,
            "state": "COMPLETE",
            "reason": "VERIFIED_RESPONSE",
            "row": row,
            "intent": intent,
            "meta": meta,
            "marker": marker,
            "dispatched": True,
            "repair_required": repairs or blobs["row"] is None or blobs["complete"] is None,
        }

    def recover(self, rid, body, binding, parse, skip_row=None):
        state = self.inspect(rid, body, binding, parse, skip_row)
        require(state["state"] != "AMBIGUOUS", state["reason"])
        paths = self.paths(rid)
        # Re-read and compare to the parsed chain before moving any pending leaf.
        for path in paths.values():
            raw, pending = _artifact(path)
            if raw is not None and pending:
                require(
                    self.inspect(rid, body, binding, parse, skip_row)["state"] == state["state"],
                    "JOURNAL_RECOVERY_STATE_CHANGED",
                )
                _finish_pending(path, raw)
        if state["state"] == "COMPLETE" and state.get("dispatched"):
            for key, value in (("row", state["row"]), ("complete", state["marker"])):
                if not paths[key].exists():
                    atomic_json(paths[key], value)
        result = self.inspect(rid, body, binding, parse, skip_row)
        require(
            result["state"] == state["state"] and not result["repair_required"],
            "JOURNAL_RECOVERY_VERIFICATION_FAILED",
        )
        if state["repair_required"]:
            self.event(
                "DERIVED_PUBLICATION_RECOVERED",
                request_id=rid,
                state=result["state"],
                raw_replaced=False,
                new_dispatch=False,
            )
        return result

    def skip(self, rid, body, binding, row):
        state = self.recover(rid, body, binding, None, skip_row=row)
        if state["state"] == "COMPLETE":
            return state["row"]
        value = seal(
            {
                "schema_version": "pa-reentry-skip-v2",
                **self._base(rid, body, binding),
                "row": safe(row),
            }
        )
        atomic_json(self.paths(rid)["skip"], value)
        self.event("REQUEST_SKIPPED", request_id=rid, skip_row_sha256=digest(row), dispatched=False)
        return self.inspect(rid, body, binding, None, row)["row"]

    def dispatch(
        self, rid, body, binding, parse, *, authorization, epoch, admission, transport, crash=None
    ):
        def checkpoint(name):
            if crash:
                crash(name)

        state = self.recover(rid, body, binding, parse)
        if state["state"] == "COMPLETE":
            return state["row"]
        validate_authorization(authorization, self.execution_identity, self.stage)
        validate_admission(admission)
        safe(epoch)
        require(isinstance(epoch, dict) and bool(epoch), "JOURNAL_EPOCH_REQUIRED")
        locations = self.paths(rid)
        try:
            if not locations["request"].exists():
                atomic_json(
                    locations["request"], body, crash=lambda label: checkpoint("request_" + label)
                )
            checkpoint("before_dispatch")
            dispatch_at = utc()
            validate_authorization(
                authorization, self.execution_identity, self.stage, now=dispatch_at
            )
            intent = seal(
                {
                    "schema_version": "pa-reentry-dispatch-v2",
                    **self._base(rid, body, binding),
                    "authorization": authorization,
                    "epoch": epoch,
                    "admission": admission,
                    "dispatch_at": dispatch_at,
                }
            )
            atomic_json(
                locations["intent"], intent, crash=lambda label: checkpoint("intent_" + label)
            )
            self.event(
                "DISPATCH_INTENT_DURABLE",
                request_id=rid,
                intent_identity_sha256=intent["identity_sha256"],
            )
            checkpoint("intent_durable")
            # If publication or event fsync stalled, no invocation may start
            # outside the admission window. Retain intent, conservatively ambiguous.
            validate_authorization(authorization, self.execution_identity, self.stage)
            started = time.monotonic()
            raw = transport()
            elapsed = time.monotonic() - started
            received_at = utc()
            checkpoint("response_received_not_saved")
            require(isinstance(raw, bytes) and 0 < len(raw) <= 2_000_000, "JOURNAL_REPLY_SIZE")
            meta = {
                "received_at": received_at,
                "elapsed_seconds": elapsed,
                "raw_sha256": sha_bytes(raw),
                "response_after_dispatch_window": stamp(received_at)
                > stamp(authorization["expires_at"]),
            }
            envelope = seal(
                {
                    "schema_version": "pa-reentry-response-v2",
                    "intent_identity_sha256": intent["identity_sha256"],
                    "meta": meta,
                    "raw_base64": base64.b64encode(raw).decode("ascii"),
                }
            )
            atomic_json(
                locations["response"], envelope, crash=lambda label: checkpoint("response_" + label)
            )
            self.event(
                "RESPONSE_DURABLE",
                request_id=rid,
                raw_sha256=meta["raw_sha256"],
                response_after_dispatch_window=meta["response_after_dispatch_window"],
            )
            checkpoint("response_durable")
            state = self.inspect(rid, body, binding, parse)
            require(state["state"] == "COMPLETE", state["reason"])
            atomic_json(
                locations["row"], state["row"], crash=lambda label: checkpoint("row_" + label)
            )
            checkpoint("row_durable")
            atomic_json(
                locations["complete"],
                state["marker"],
                crash=lambda label: checkpoint("complete_" + label),
            )
            verified = self.inspect(rid, body, binding, parse)
            require(
                verified["state"] == "COMPLETE" and not verified["repair_required"],
                "JOURNAL_POST_DISPATCH_REPLAY_FAILED",
            )
            self.event(
                "REQUEST_COMPLETE",
                request_id=rid,
                row_sha256=digest(verified["row"]),
                received_at=received_at,
                elapsed_seconds=elapsed,
            )
            return verified["row"]
        except BaseException as error:
            # Logs are helpful, never stronger than the request artifacts. A hard
            # power/process kill can prevent this record; reentry detects absence.
            code = str(error)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,191}", code):
                code = "JOURNAL_REQUEST_INTERRUPTED"
            try:
                self.event(
                    "REQUEST_INTERRUPTED",
                    request_id=rid,
                    error_code=code,
                    error_type=type(error).__name__,
                    automatic_retry=False,
                )
            except (OSError, ValueError):
                pass
            raise

    def raw_reply(self, rid):
        """Read exact response bytes; callers must first verify the request chain."""
        raw, _ = _artifact(self.paths(rid)["response"])
        require(raw is not None, "JOURNAL_RESPONSE_MISSING")
        envelope = verify_seal(strict_json(raw))
        result = base64.b64decode(envelope["raw_base64"], validate=True)
        require(
            envelope["meta"]["raw_sha256"] == sha_bytes(result), "JOURNAL_RESPONSE_HASH_CHANGED"
        )
        return result
