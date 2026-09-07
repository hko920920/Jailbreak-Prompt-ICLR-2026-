"""Synthetic-only QA tests; never inspect live V4 outputs or private receipts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jbspan import rescue_guidedeval_development as support

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


audit = module("synthetic_receipt_audit", ROOT / "scripts/audit_objective_transfer_receipts_v4.py")
helper = module("synthetic_receipt_helper", ROOT / "scripts/run_rescue_objective_repair_v3.py")


def reply(text='{"answer":"maple"}', *, finish="stop"):
    return {
        "model": "fixture-model",
        "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": text}}],
        "usage": {"completion_tokens": 9},
    }


@pytest.fixture
def receipt(tmp_path):
    model = {"model_id": "fixture", "alias": "fixture-model"}
    request = {"model": model["alias"], "messages": [{"role": "user", "content": "harmless"}]}
    sha = support.digest(request)
    row = {
        "model_id": model["model_id"],
        "request": request,
        "request_sha256": sha,
        "execution_key": support.digest({"model_id": model["model_id"], "request_sha256": sha}),
        "expected_answer": "maple",
        "expected_answer_sha256": support.digest("maple"),
    }
    config = {
        "runtime": {"port": 18881},
        "limits": {
            "maximum_unique_requests": 1120,
            "max_request_utf8_bytes": 100000,
            "max_reply_utf8_bytes": 1000000,
            "per_request_seconds": 90,
        },
    }

    def create(value=None, *, transport_unknown=False):
        if value is None:
            value = reply()

        def send(*_):
            if transport_unknown:
                raise support.TransportFailure("synthetic uncertainty")
            return value

        observed = helper.evaluate_once(tmp_path, "fixture-contract", config, model, row, send=send)
        identity = helper.request_identity("fixture-contract", row)
        path = tmp_path / f"{row['execution_key']}.reply.private.json"
        return observed, identity, path

    return tmp_path, model, row, create


def check(receipt, observed, identity):
    directory, model, row, _ = receipt
    return audit.verify_receipt(
        directory, identity, observed, model, row["expected_answer"], helper
    )


def rewrite(path, value):
    # Intentional corruption of synthetic test data, never production artifacts.
    path.write_text(json.dumps(value), encoding="utf-8")


def recommit(path, stored, observed):
    stored["receipt_sha256"] = support.digest(
        {k: v for k, v in stored.items() if k != "receipt_sha256"}
    )
    observed["private_receipt_sha256"] = stored["receipt_sha256"]
    rewrite(path, stored)


def test_valid_receipt_replays_without_copying_text(receipt):
    observed, identity, _ = receipt[3]()
    result = check(receipt, observed, identity)
    assert result["status"] == "CORRECT" and result["provider_reply_replayed"] is True
    assert "maple" not in json.dumps(result)
    support.content_free(result)


def test_changed_raw_reply_with_recomputed_receipt_hash_cannot_hide_score_change(receipt):
    observed, identity, path = receipt[3]()
    stored = support.read_object(path)
    stored["raw_reply"]["choices"][0]["message"]["content"] = '{"answer":"wrong"}'
    recommit(path, stored, observed)
    with pytest.raises(ValueError, match="replayed reply"):
        check(receipt, observed, identity)


def test_changed_stored_and_public_status_still_fails_frozen_parser_replay(receipt):
    observed, identity, path = receipt[3]()
    stored = support.read_object(path)
    for value in (stored["safe_result"], observed):
        value.update({"status": "INCORRECT", "score_reason": "WRONG_VALUE"})
    recommit(path, stored, observed)
    with pytest.raises(ValueError, match="replayed reply"):
        check(receipt, observed, identity)


def test_changed_reply_metadata_with_recomputed_receipt_hash_is_detected(receipt):
    observed, identity, path = receipt[3]()
    stored = support.read_object(path)
    stored["raw_reply"]["usage"]["completion_tokens"] = 10
    recommit(path, stored, observed)
    with pytest.raises(ValueError, match="provenance"):
        check(receipt, observed, identity)


def test_elapsed_is_checked_separately_not_replayed(receipt):
    observed, identity, path = receipt[3]()
    stored = support.read_object(path)
    stored["safe_result"]["elapsed_seconds"] = observed["elapsed_seconds"] + 1
    recommit(path, stored, observed)
    with pytest.raises(ValueError, match="elapsed"):
        check(receipt, observed, identity)


def test_pending_identity_and_public_receipt_commitment_are_checked(receipt):
    observed, identity, path = receipt[3]()
    observed["private_receipt_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="commitment"):
        check(receipt, observed, identity)
    observed["private_receipt_sha256"] = support.read_object(path)["receipt_sha256"]
    pending = receipt[0] / f"{identity['execution_key']}.pending.safe.json"
    rewrite(pending, {**identity, "contract_sha256": "other-contract"})
    with pytest.raises(ValueError, match="pending identity"):
        check(receipt, observed, identity)


def test_truncation_unknown_is_preserved_and_replayed(receipt):
    observed, identity, _ = receipt[3](reply(finish="length"))
    result = check(receipt, observed, identity)
    assert result["status"] == "UNKNOWN"
    assert result["error_code"] == "NONSTOP_OR_TRUNCATED_OUTPUT"
    assert result["provider_reply_replayed"] is True


def test_transport_unknown_is_retained_without_inventing_a_reply(receipt):
    observed, identity, _ = receipt[3](transport_unknown=True)
    result = check(receipt, observed, identity)
    assert result["status"] == "UNKNOWN" and result["transport_unknown_retained"] is True
    assert result["provider_reply_replayed"] is False


def test_absent_reply_cannot_be_relabeled_as_another_unknown_type(receipt):
    observed, identity, path = receipt[3](transport_unknown=True)
    stored = support.read_object(path)
    for value in (stored["safe_result"], observed):
        value["error_code"] = "NONSTOP_OR_TRUNCATED_OUTPUT"
    recommit(path, stored, observed)
    with pytest.raises(ValueError, match="replayed reply"):
        check(receipt, observed, identity)


def test_other_contract_is_rejected_without_reading_any_file(tmp_path):
    with pytest.raises(ValueError, match="only the exact frozen V4"):
        audit.completed_inputs(tmp_path, "not-present.json", "other")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("incomplete_exists", [False, True])
def test_completed_gate_blocks_before_private_access(tmp_path, monkeypatch, incomplete_exists):
    config = {"recording": {"private_base": "artifacts/rescue_objective_transfer_v4"}}
    path = tmp_path / "config.json"
    support.write_once(path, config)
    sha = support.file_digest(path)
    monkeypatch.setattr(audit, "CONTRACT_SHA256", sha)
    safe = tmp_path / "data"
    private = tmp_path / "artifacts" / "rescue_objective_transfer_v4"
    if incomplete_exists:
        support.write_once(safe / "validation.safe.json", {"complete": False})

    def verify_result(*_):
        raise ValueError("incomplete result")

    mocked = SimpleNamespace(
        verify_config=lambda *_: (
            config,
            [],
            [],
            SimpleNamespace(directories=lambda *_: (safe, private)),
        ),
        build_plan=lambda *_: [],
        verify_plan=lambda *_: None,
        verify_result=verify_result,
    )
    monkeypatch.setattr(audit, "load_runner", lambda *_: mocked)
    with pytest.raises((RuntimeError, ValueError), match="completed V4|incomplete result"):
        audit.completed_inputs(tmp_path, "config.json", sha)
    assert not private.exists()


def test_readiness_does_not_enumerate_receipts_or_write_output(monkeypatch, tmp_path):
    class NoPrivateAccess:
        def glob(self, *_):
            pytest.fail("readiness enumerated private receipts")

    monkeypatch.setattr(
        audit,
        "completed_inputs",
        lambda *_: (
            {},
            [],
            None,
            {},
            tmp_path / "completed.safe.json",
            tmp_path,
            NoPrivateAccess(),
        ),
    )
    result = audit.audit(tmp_path, "config.json", audit.CONTRACT_SHA256, execute=False)
    assert result["private_inputs_read"] is False
    assert not list(tmp_path.iterdir())
