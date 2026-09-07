"""Synthetic wrapper orchestration checks; never read actual research data."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_pa_stage6_measurements_v2 as m  # noqa: E402


@pytest.fixture
def context(tmp_path, monkeypatch):
    frozen = {"execution_identity": "a" * 64}
    target = SimpleNamespace(safe=tmp_path / "safe" / "target")
    monkeypatch.setattr(m.entry, "verify_frozen", lambda *args: frozen)
    monkeypatch.setattr(m.entry, "load_context", lambda root: (frozen, target))
    monkeypatch.setattr(m.entry, "payloads", lambda target: {})
    monkeypatch.setattr(m.finalizer, "validate_products", lambda products: None)
    observed = []

    def finish(target, payloads, *, direction, run_analysis):
        assert run_analysis is False and direction["stage"] == 6
        observed.append(direction)
        output = target.safe.parent / "finalization" / "measurements-only"
        result = {"result_identity_sha256": "b" * 64}
        measured = {"result_identity_sha256": "c" * 64}
        proof = {
            "analysis_complete": False,
            "verification_identity_sha256": "d" * 64,
            "product_file_sha256": {
                "result": m.j.sha_bytes(m.j.canonical(result) + b"\n"),
                "measurements": m.j.sha_bytes(m.j.canonical(measured) + b"\n"),
            },
        }
        for key, value in (("measurements", measured), ("result", result),
                           ("verification", proof)):
            path = output / m.finalizer.OUTPUTS[key]
            if not path.exists():
                m.j.atomic_json(path, value)
        return proof

    monkeypatch.setattr(m.finalizer, "finalize", finish)
    return tmp_path, observed


def events(root):
    return [m.j.read_json(path) for path in
            (root / m.RUNTIME / "events").glob("*.safe.json")]


def test_stage6_only_records_and_exact_direction_reentry(context):
    root, observed = context
    m.execute(root, "synthetic-current-user-direction")
    m.execute(root, "synthetic-current-user-direction")
    assert observed[0] == observed[1]
    records = events(root)
    assert sum(row["event"] == "STAGE6_COMPLETE" for row in records) == 2
    assert all(row["stage"] == 6 and row["run_analysis"] is False
               and row["new_model_calls"] == 0 for row in records)
    assert len({row["attempt_id"] for row in records}) == 2


def test_changed_direction_rejected_without_finalizer(context):
    root, observed = context
    m.execute(root, "first")
    with pytest.raises(ValueError, match="DIRECTION_REFERENCE_CHANGED"):
        m.execute(root, "different")
    assert len(observed) == 1


def test_exception_hashed_without_private_text(context, monkeypatch):
    root, observed = context

    def fail(root):
        raise ValueError("private fixture text must never reach SAFE output")

    monkeypatch.setattr(m.entry, "load_context", fail)
    with pytest.raises(RuntimeError, match="FAILURE_DETAILS_HASHED"):
        m.execute(root, "direction")
    failures = [row for row in events(root) if row["event"] == "STAGE6_INTERRUPTED"]
    assert len(failures) == 1 and failures[0]["error_code"] is None
    assert "private fixture text" not in str(events(root))
    assert observed == []


def test_expired_receipt_does_not_extend(context, monkeypatch):
    root, observed = context
    m.execute(root, "direction")
    old = (root / m.RUNTIME / "direction.safe.json").read_bytes()

    def expired(*args, **kwargs):
        raise ValueError("FINAL_V2_DIRECTION_WINDOW")

    monkeypatch.setattr(m.finalizer, "validate_direction", expired)
    with pytest.raises(ValueError, match="DIRECTION_WINDOW"):
        m.execute(root, "direction")
    assert len(observed) == 1
    assert (root / m.RUNTIME / "direction.safe.json").read_bytes() == old


def test_verification_whitespace_tamper_rejected(context, monkeypatch):
    root, _ = context
    finish = m.finalizer.finalize

    def tampered(target, payloads, **kwargs):
        proof = finish(target, payloads, **kwargs)
        path = target.safe.parent / "finalization" / "measurements-only" / "verification.safe.json"
        path.write_bytes(path.read_bytes() + b" ")
        return proof

    monkeypatch.setattr(m.finalizer, "finalize", tampered)
    with pytest.raises(RuntimeError, match="PUBLICATION_OR_STAGE_BOUNDARY_CHANGED"):
        m.execute(root, "direction")
    assert not any(row["event"] == "STAGE6_COMPLETE" for row in events(root))


def test_private_error_and_failed_logger_still_sanitized(context, monkeypatch):
    root, _ = context
    publish = m.j.atomic_json

    def fail(root):
        raise ValueError("private fixture text")

    def flaky(path, record):
        if record.get("event") == "STAGE6_INTERRUPTED":
            raise OSError("secondary private diagnostic")
        return publish(path, record)

    monkeypatch.setattr(m.entry, "load_context", fail)
    monkeypatch.setattr(m.j, "atomic_json", flaky)
    with pytest.raises(RuntimeError, match="FAILURE_DETAILS_HASHED") as caught:
        m.execute(root, "direction")
    assert caught.value.__suppress_context__ is True
    assert caught.value.__cause__ is None
    assert not any(row["event"] == "STAGE6_COMPLETE" for row in events(root))
