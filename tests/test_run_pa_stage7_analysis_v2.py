"""Synthetic Stage7 orchestration only; no actual research artifacts or inference."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_pa_stage7_analysis_v2 as m  # noqa: E402


@pytest.fixture
def context(tmp_path, monkeypatch):
    frozen = {"execution_identity": "a" * 64}
    target = SimpleNamespace(safe=tmp_path / "safe" / "target")
    measured = {"result_identity_sha256": "b" * 64}
    prior = {"measurements.safe.json": m.j.sha_bytes(m.j.canonical(measured) + b"\n")}
    monkeypatch.setattr(m.entry, "verify_frozen", lambda *args: frozen)
    monkeypatch.setattr(m.entry, "load_context", lambda root: (frozen, target))
    monkeypatch.setattr(m.entry, "payloads", lambda target: {})
    monkeypatch.setattr(m, "snapshot_stage6", lambda *args: prior)
    monkeypatch.setattr(m.finalizer, "validate_products", lambda products: None)
    observed = []

    def finish(target, payloads, *, direction, run_analysis):
        assert run_analysis is True and direction["stage"] == 7
        observed.append(direction)
        products = {"measurements": measured,
                    "analysis": {"result_identity_sha256": "c" * 64},
                    "result": {"result_identity_sha256": "d" * 64}}
        proof = {"analysis_complete": True, "verification_identity_sha256": "e" * 64,
                 "product_file_sha256": {k: m.j.sha_bytes(m.j.canonical(v) + b"\n")
                                         for k, v in products.items()}}
        products["verification"] = proof
        output = target.safe.parent / "finalization" / "with-analysis"
        for key, value in products.items():
            path = output / m.finalizer.OUTPUTS[key]
            if not path.exists():
                m.j.atomic_json(path, value)
        return proof

    monkeypatch.setattr(m.finalizer, "finalize", finish)
    return tmp_path, target, observed


def events(root):
    return [m.j.read_json(path) for path in
            (root / m.RUNTIME / "events").glob("*.safe.json")]


def test_stage7_only_exact_direction_reentry_and_saved_products(context):
    root, _, observed = context
    m.execute(root, "synthetic-current-direction")
    m.execute(root, "synthetic-current-direction")
    assert observed[0] == observed[1]
    records = events(root)
    assert sum(r["event"] == "STAGE7_FROZEN_ANALYSIS_COMPLETE" for r in records) == 2
    assert all(r["stage"] == 7 and r["run_analysis"] is True
               and r["new_model_calls"] == 0 for r in records)


def test_stage6_drift_rejected_before_context(context, monkeypatch):
    root, _, observed = context

    def drift(*args):
        raise ValueError("STAGE7_STAGE6_FILE_CHANGED")

    monkeypatch.setattr(m, "snapshot_stage6", drift)
    monkeypatch.setattr(m.entry, "load_context", lambda root: pytest.fail("must reject first"))
    with pytest.raises(RuntimeError, match="STAGE6_FILE_CHANGED"):
        m.execute(root, "direction")
    assert observed == []


def test_verification_whitespace_tamper_rejected(context, monkeypatch):
    root, _, _ = context
    finish = m.finalizer.finalize

    def tampered(target, payloads, **kwargs):
        proof = finish(target, payloads, **kwargs)
        path = target.safe.parent / "finalization" / "with-analysis" / "verification.safe.json"
        path.write_bytes(path.read_bytes() + b" ")
        return proof

    monkeypatch.setattr(m.finalizer, "finalize", tampered)
    with pytest.raises(RuntimeError, match="NONCANONICAL_PRODUCT"):
        m.execute(root, "direction")


def test_error_and_logger_failure_still_sanitized(context, monkeypatch):
    root, _, _ = context
    publish = m.j.atomic_json

    def fail(root):
        raise ValueError("private fixture text")

    def flaky(path, record):
        if record.get("event") == "STAGE7_INTERRUPTED":
            raise OSError("secondary private text")
        return publish(path, record)

    monkeypatch.setattr(m.entry, "load_context", fail)
    monkeypatch.setattr(m.j, "atomic_json", flaky)
    with pytest.raises(RuntimeError, match="FAILURE_DETAILS_HASHED") as caught:
        m.execute(root, "direction")
    assert caught.value.__suppress_context__ is True
    assert "private fixture text" not in str(events(root))


def test_changed_reference_or_expired_direction_never_reissued(context, monkeypatch):
    root, _, observed = context
    m.execute(root, "direction")
    receipt = root / m.RUNTIME / "direction.safe.json"
    before = receipt.read_bytes()
    with pytest.raises(ValueError, match="REFERENCE_CHANGED"):
        m.execute(root, "changed")

    def expired(*args, **kwargs):
        raise ValueError("FINAL_V2_DIRECTION_WINDOW")

    monkeypatch.setattr(m.finalizer, "validate_direction", expired)
    with pytest.raises(ValueError, match="DIRECTION_WINDOW"):
        m.execute(root, "direction")
    assert len(observed) == 1 and receipt.read_bytes() == before


def test_real_stage6_snapshot_rejects_unpinned_bytes(tmp_path, monkeypatch):
    for name in (*m.STAGE6_PINS, "publication.lock"):
        (tmp_path / name).write_bytes(b"synthetic fixture")
    monkeypatch.setattr(m.entry, "owned", lambda *args: tmp_path)
    with pytest.raises(ValueError, match="STAGE6_FILE_CHANGED"):
        m.snapshot_stage6(tmp_path, "a" * 64)


def test_stage6_child_link_rejected_before_reads(tmp_path, monkeypatch):
    for name in (*m.STAGE6_PINS, "publication.lock"):
        (tmp_path / name).write_bytes(b"synthetic fixture")
    monkeypatch.setattr(m.entry, "owned", lambda *args: tmp_path)

    def reject(path):
        raise ValueError("SYNTHETIC_CHILD_REPARSE")

    monkeypatch.setattr(m.j, "reject_links", reject)
    monkeypatch.setattr(m.j, "sha_bytes", lambda raw: pytest.fail("must reject before read/hash"))
    with pytest.raises(ValueError, match="CHILD_REPARSE"):
        m.snapshot_stage6(tmp_path, "a" * 64)
