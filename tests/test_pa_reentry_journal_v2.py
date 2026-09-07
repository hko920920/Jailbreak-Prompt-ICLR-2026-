"""Harmless fake transport, temporary trees and process-lock tests only."""

import copy
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_reentry_journal_v2 as j  # noqa: E402

EXECUTION = "a" * 64
BODY = {"prompt": "Reply with the word orange.", "temperature": 0}
BINDING = {"original_contract_sha256": "b" * 64, "ordinal": 1083}
RAW = b'{"content":"orange"}\n'
ADMISSION = {"disk_free_bytes": 32 * j.GIB, "temperature_c": 35}
EPOCH = {"epoch_id": "synthetic-001", "pid": 101}


def parse(raw, meta, intent):
    return {
        "request_id": intent["request_id"],
        "raw_sha256": j.sha_bytes(raw),
        "received_at": meta["received_at"],
        "elapsed_seconds": meta["elapsed_seconds"],
        "result": "UNKNOWN",
    }


def authorization(stage="target", **changes):
    now = datetime.now(timezone.utc)
    fields = {
        "issued_at": (now - timedelta(seconds=5)).isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
        "direction_ref": "synthetic-fixture-not-real-user-authority",
    }
    fields.update(changes)
    return j.make_authorization(EXECUTION, stage, **fields)


@pytest.fixture
def journal(tmp_path):
    return j.Journal(tmp_path / "safe", tmp_path / "private", EXECUTION, "target")


def invoke(journal, calls, **changes):
    def transport():
        calls.append("called")
        return RAW

    arguments = {
        "authorization": authorization(journal.stage),
        "epoch": EPOCH,
        "admission": ADMISSION,
        "transport": transport,
    }
    arguments.update(changes)
    return journal.dispatch("r1083", BODY, BINDING, parse, **arguments)


def fail_at(stage):
    def hook(point):
        if point == stage:
            raise SystemExit("SYNTHETIC_CRASH")

    return hook


@pytest.mark.parametrize("stage", ["target", "qwen", "jailmeter"])
def test_complete_never_repeats_and_unknown_remains(tmp_path, stage):
    journal = j.Journal(tmp_path / "safe", tmp_path / "private", EXECUTION, stage)
    calls = []
    first = invoke(journal, calls)
    assert first == invoke(journal, calls)
    assert len(calls) == 1
    assert first["result"] == "UNKNOWN"
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "COMPLETE"
    assert journal.raw_reply("r1083") == RAW
    assert journal.audit_events()["observed_event_artifacts_valid"]
    assert journal.audit_events()["event_log_completeness_proven"] is False


@pytest.mark.parametrize(
    ("point", "expected", "calls_at_crash"),
    [
        ("request_publication_pending_created", "AMBIGUOUS", 0),
        ("request_publication_pending_written", "UNISSUED", 0),
        ("request_publication_published", "UNISSUED", 0),
        ("before_dispatch", "UNISSUED", 0),
        ("intent_publication_pending_created", "AMBIGUOUS", 0),
        ("intent_publication_pending_written", "AMBIGUOUS", 0),
        ("intent_publication_published", "AMBIGUOUS", 0),
        ("intent_durable", "AMBIGUOUS", 0),
        ("response_received_not_saved", "AMBIGUOUS", 1),
        ("response_publication_pending_created", "AMBIGUOUS", 1),
        ("response_publication_pending_written", "COMPLETE", 1),
        ("response_publication_published", "COMPLETE", 1),
        ("response_durable", "COMPLETE", 1),
        ("row_publication_pending_created", "AMBIGUOUS", 1),
        ("row_publication_pending_written", "COMPLETE", 1),
        ("row_publication_published", "COMPLETE", 1),
        ("row_durable", "COMPLETE", 1),
        ("complete_publication_pending_created", "AMBIGUOUS", 1),
        ("complete_publication_pending_written", "COMPLETE", 1),
        ("complete_publication_published", "COMPLETE", 1),
    ],
)
def test_every_publication_boundary(journal, point, expected, calls_at_crash):
    calls = []
    with pytest.raises(SystemExit, match="SYNTHETIC_CRASH"):
        invoke(journal, calls, crash=fail_at(point))
    assert len(calls) == calls_at_crash
    state = journal.inspect("r1083", BODY, BINDING, parse)
    assert state["state"] == expected
    if expected == "AMBIGUOUS":
        with pytest.raises(ValueError):
            invoke(journal, calls)
        assert len(calls) == calls_at_crash
    else:
        invoke(journal, calls)
        assert len(calls) == 1
        assert journal.inspect("r1083", BODY, BINDING, parse)["repair_required"] is False


def test_transport_exception_is_ambiguous_no_retry(journal):
    calls = []

    def transport():
        calls.append(1)
        raise TimeoutError("private request must never reach safe error text")

    with pytest.raises(TimeoutError):
        invoke(journal, calls, transport=transport)
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "AMBIGUOUS"
    with pytest.raises(ValueError, match="INFLIGHT_AMBIGUOUS"):
        invoke(journal, calls)
    assert len(calls) == 1
    assert all(
        b"private request" not in path.read_bytes() for path in (journal.safe / "events").iterdir()
    )


@pytest.mark.parametrize("name", ["request", "intent", "response", "row", "complete"])
def test_changed_saved_artifact_blocks(journal, name):
    calls = []
    invoke(journal, calls)
    path = journal.paths("r1083")[name]
    path.write_bytes(b'{"corrupt":true}\n')
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "AMBIGUOUS"
    with pytest.raises(ValueError):
        invoke(journal, calls)
    assert len(calls) == 1


def test_orphan_completion_is_not_truth(journal):
    j.atomic_json(journal.paths("r1083")["complete"], {"complete": True})
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "AMBIGUOUS"


def test_modified_plan_or_body_prevents_reuse(journal):
    invoke(journal, [])
    assert (
        journal.inspect("r1083", {**BODY, "temperature": 1}, BINDING, parse)["state"] == "AMBIGUOUS"
    )
    assert (
        journal.inspect("r1083", BODY, {**BINDING, "ordinal": 1084}, parse)["state"] == "AMBIGUOUS"
    )


@pytest.mark.parametrize("wrong", ["qwen", "jailmeter"])
def test_stage_boundary_no_implicit_next_stage(journal, wrong):
    calls = []
    with pytest.raises(ValueError, match="WRONG_STAGE"):
        invoke(journal, calls, authorization=authorization(wrong))
    assert not calls
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "UNISSUED"


def test_expired_authorization_blocks_new_dispatch(journal):
    now = datetime.now(timezone.utc)
    auth = authorization(
        issued_at=(now - timedelta(minutes=2)).isoformat(),
        expires_at=(now - timedelta(minutes=1)).isoformat(),
    )
    calls = []
    with pytest.raises(ValueError, match="NOT_CURRENT"):
        invoke(journal, calls, authorization=auth)
    assert not calls


def test_no_unlimited_or_unsigned_authority():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="WINDOW"):
        authorization(expires_at=(now + timedelta(hours=3)).isoformat())
    auth = authorization()
    auth["stage"] = "qwen"
    with pytest.raises(ValueError, match="IDENTITY_CHANGED"):
        j.validate_authorization(auth, EXECUTION, "qwen")
    with pytest.raises(ValueError, match="DIRECTION"):
        authorization(direction_ref="")


def test_late_response_persisted_without_new_dispatch(journal, monkeypatch):
    now = datetime.now(timezone.utc)
    issued, expires = now.isoformat(), (now + timedelta(seconds=5)).isoformat()
    auth = authorization(issued_at=issued, expires_at=expires)
    monkeypatch.setattr(j, "utc", lambda: issued)

    def transport():
        monkeypatch.setattr(j, "utc", lambda: (now + timedelta(seconds=7)).isoformat())
        return RAW

    journal.dispatch(
        "r1083",
        BODY,
        BINDING,
        parse,
        authorization=auth,
        epoch=EPOCH,
        admission=ADMISSION,
        transport=transport,
    )
    state = journal.inspect("r1083", BODY, BINDING, parse)
    assert state["state"] == "COMPLETE" and state["meta"]["response_after_dispatch_window"]
    with pytest.raises(ValueError, match="NOT_CURRENT"):
        journal.dispatch(
            "r1084",
            BODY,
            BINDING,
            parse,
            authorization=auth,
            epoch=EPOCH,
            admission=ADMISSION,
            transport=lambda: pytest.fail("not admitted"),
        )


@pytest.mark.parametrize(
    "admission",
    [
        {"disk_free_bytes": 15 * j.GIB - 1, "temperature_c": 35},
        {"disk_free_bytes": 32 * j.GIB, "temperature_c": 61},
        {"disk_free_bytes": 32 * j.GIB, "temperature_c": float("nan")},
    ],
)
def test_resource_stop_before_dispatch(journal, admission):
    calls = []
    with pytest.raises(ValueError):
        invoke(journal, calls, admission=admission)
    assert not calls
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "UNISSUED"


def test_skip_not_an_observed_model_response(journal):
    row = {
        "request_id": "r1083",
        "dispatched": False,
        "skip_reason": "TARGET_INELIGIBLE",
        "label": "UNKNOWN",
    }
    assert journal.skip("r1083", BODY, BINDING, row) == row
    assert journal.skip("r1083", BODY, BINDING, row) == row
    state = journal.inspect("r1083", BODY, BINDING, None, row)
    assert state["state"] == "COMPLETE" and not state["dispatched"]
    assert not journal.paths("r1083")["request"].exists()
    with pytest.raises(ValueError):
        invoke(journal, [])


def test_corrupt_progress_does_not_authorize_calls_and_is_reported(journal):
    journal.event("PROGRESS", completed=388)
    event = next((journal.safe / "events").iterdir())
    event.write_bytes(b'{"completed":388')
    audit = journal.audit_events()
    assert audit["invalid_events"] == 1 and not audit["observed_event_artifacts_valid"]
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "UNISSUED"


def test_unexplained_id_or_file_blocks(journal):
    invoke(journal, [])
    with pytest.raises(ValueError, match="UNEXPLAINED_REQUEST_ID"):
        journal.audit_ids(["r1084"])
    path = journal.paths("r1083")["row"].parent / "unexplained.safe.json"
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="UNEXPLAINED_REQUEST_FILE"):
        journal.audit_ids(["r1083"])


def test_conflicting_pending_copy_blocks(journal):
    invoke(journal, [])
    j.pending_path(journal.paths("r1083")["response"]).write_bytes(b"{}")
    assert (
        journal.inspect("r1083", BODY, BINDING, parse)["reason"]
        == "JOURNAL_CONFLICTING_PUBLICATION"
    )


def test_kernel_lock_not_stale_pid_file(tmp_path):
    path = tmp_path / "stage.lock"
    path.write_bytes(b"old arbitrary PID 123456")
    with j.run_lock(path):
        with pytest.raises(ValueError, match="LIVE_LOCK"):
            with j.run_lock(path):
                pytest.fail("concurrent owner")
    with j.run_lock(path):
        pass


def test_hard_process_exit_releases_kernel_lock(tmp_path):
    path = tmp_path / "stage.lock"
    script = (
        "import sys,os;sys.path.insert(0,sys.argv[1]);"
        "import pa_reentry_journal_v2 as j;"
        "ctx=j.run_lock(sys.argv[2]);ctx.__enter__();os._exit(7)"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(Path(j.__file__).parent), str(path)],
        check=False,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 7
    with j.run_lock(path):
        pass


def test_exclusive_write_does_not_overwrite(tmp_path):
    path = tmp_path / "one.safe.json"
    j.atomic_json(path, {"first": True})
    with pytest.raises(ValueError, match="ALREADY_PUBLISHED"):
        j.atomic_json(path, {"first": False})
    assert j.read_json(path) == {"first": True}


def test_authorization_is_one_stage_invocation_not_automatic_retry(journal):
    auth = authorization()
    journal.claim_authorization(auth)
    with pytest.raises(ValueError, match="NEW_DIRECTION_REQUIRED"):
        journal.claim_authorization(auth)
    current = authorization(direction_ref="synthetic-reviewed-current-direction-two")
    journal.claim_authorization(current)


def test_atomic_write_and_lock_reject_descendant_reparse(tmp_path, monkeypatch):
    parent = tmp_path / "child"
    parent.mkdir()
    old = Path.lstat

    def observe(path, *args, **kwargs):
        result = old(path, *args, **kwargs)
        if path.name == "child":
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=1024)
        return result

    monkeypatch.setattr(Path, "lstat", observe)
    with pytest.raises(ValueError, match="REPARSE"):
        j.atomic_json(parent / "receipt.safe.json", {})
    with pytest.raises(ValueError, match="REPARSE"):
        with j.run_lock(parent / "stage.lock"):
            pytest.fail("must not enter")


def test_safe_event_rejects_raw_content(journal):
    with pytest.raises(ValueError, match="PRIVATE_FIELD"):
        journal.event("ERROR", details={"prompt": "secret"})
    with pytest.raises(ValueError, match="RESERVED"):
        journal.event("ERROR", stage="qwen")


def test_resealed_intent_wrong_epoch_requires_adapter_verification(journal):
    # The core binds epoch bytes and completion; adapters must additionally
    # authenticate the referenced worker receipts. No invented lifecycle proof.
    invoke(journal, [])
    original = j.read_json(journal.paths("r1083")["intent"])
    mutated = copy.deepcopy(original)
    mutated["epoch"]["pid"] += 1
    mutated.pop("identity_sha256")
    mutated = j.seal(mutated)
    journal.paths("r1083")["intent"].write_bytes(j.canonical(mutated))
    assert journal.inspect("r1083", BODY, BINDING, parse)["state"] == "AMBIGUOUS"
