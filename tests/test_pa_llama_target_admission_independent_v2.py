"""Independent V2 identity checks; entirely synthetic, with no model/server calls."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


admission = load_module("independent_pa_admission_v2", "run_pa_llama_target_admission_v2.py")
sys.path.insert(0, str(SCRIPTS))
try:
    normalizer = load_module(
        "independent_template_lexer", "inspect_pa_llama_template_normalization_v1.py")
finally:
    sys.path.pop(0)


@pytest.mark.parametrize(("source", "expected"), [
    (b"", b""), (b"x", b"x"), (b"x\n", b"x"), (b"x\r", b"x\n"),
    (b"x\r\n", b"x"), (b"x\n\n", b"x\n"), (b"x\n\r", b"x\n\n"),
    (b"\r\r\n", b"\n"), (b"x\r\ny\rz\n", b"x\ny\nz"),
    (b"x\n \t", b"x\n \t"), (b"x\n\x00", b"x\n\x00"),
    ("한글\r\nλ\n".encode(), "한글\nλ".encode()),
])
def test_exact_upstream_lexer_rule_uses_original_suffix(source, expected):
    assert normalizer.lexer_source_normalization(source) == expected


def synthetic_config():
    raw = b"synthetic-template\n"
    served = b"synthetic-template"
    return {
        "model": {"alias": "synthetic-v2"},
        "runtime": {
            "native_chat_template_sha256": hashlib.sha256(raw).hexdigest(),
            "served_chat_template_sha256": hashlib.sha256(served).hexdigest(),
            "served_chat_template_utf8_bytes": len(served),
        },
        "server": {"request_timeout_seconds": 2},
    }


class MetadataClient:
    def __init__(self, contract, observed):
        self.contract = contract
        self.observed = observed
        self.routes = []

    def get(self, route):
        self.routes.append(route)
        if route == "/v1/models":
            return {"data": [{"id": self.contract["model"]["alias"]}]}
        assert route == "/props"
        return {"chat_template": self.observed}

    def request(self, *_args, **_kwargs):
        raise AssertionError("This identity-only test must never dispatch inference")


def test_distinct_raw_and_served_pins_accept_actual_served_source():
    contract = synthetic_config()
    observed = []
    process = SimpleNamespace(pid=811, poll=lambda: None)
    client = MetadataClient(contract, "synthetic-template")
    properties = admission.check_identity(process, client, contract, observed.append)
    assert contract["runtime"]["native_chat_template_sha256"] != properties[
        "served_chat_template_sha256"]
    assert properties["served_chat_template_sha256"] == contract["runtime"][
        "served_chat_template_sha256"]
    assert len(observed) == 1 and observed[0]["served_template_matches_pin"] is True
    assert observed[0]["observed_served_chat_template_utf8_bytes"] == 18
    assert client.routes == ["/v1/models", "/props"]
    assert "synthetic-template" not in json.dumps(observed)


def test_raw_source_is_not_silently_normalized_to_match_served_pin():
    contract = synthetic_config()
    observed = []
    process = SimpleNamespace(pid=812, poll=lambda: None)
    client = MetadataClient(contract, "synthetic-template\n")
    with pytest.raises(admission.AdmissionError, match="SERVED_TEMPLATE_MISMATCH"):
        admission.check_identity(process, client, contract, observed.append)
    assert len(observed) == 1
    assert observed[0]["observed_served_chat_template_sha256"] == contract["runtime"][
        "native_chat_template_sha256"]
    assert observed[0]["served_template_matches_pin"] is False


@pytest.mark.parametrize("source", [None, "", {"default": "synthetic-template"}])
def test_missing_or_typed_template_is_observed_before_identity_failure(source):
    contract = synthetic_config()
    observed = []
    process = SimpleNamespace(pid=813, poll=lambda: None)
    with pytest.raises(admission.AdmissionError, match="SERVED_TEMPLATE_UNAVAILABLE"):
        admission.check_identity(
            process, MetadataClient(contract, source), contract, observed.append)
    assert len(observed) == 1 and observed[0]["template_source_available"] is False
    assert observed[0]["observed_served_chat_template_sha256"] is None
    assert observed[0]["observed_served_chat_template_utf8_bytes"] is None


def test_mismatch_receipt_is_durable_without_a_dispatch_journal(tmp_path):
    contract = synthetic_config()
    process = SimpleNamespace(pid=814, poll=lambda: None)
    safe, private = tmp_path / "safe", tmp_path / "private"
    safe.mkdir()
    private.mkdir()
    item = {"ordinal": 1, "epoch": 1, "fixture": {
        "prompt_id": "exact_sentinel", "text": "Synthetic harmless probe",
        "scorer": "exact_text", "expected": "P2_OK",
    }}
    with pytest.raises(admission.AdmissionError, match="SERVED_TEMPLATE_MISMATCH"):
        admission.dispatch_one(contract, "a" * 64, item, process,
                               MetadataClient(contract, "wrong-template"), safe, private,
                               {"served_chat_template_sha256": contract["runtime"][
                                   "served_chat_template_sha256"]})
    receipt = json.loads((safe / "01.tpl.safe.json").read_bytes())
    assert receipt["served_template_matches_pin"] is False
    assert receipt["observed_served_chat_template_sha256"] == hashlib.sha256(
        b"wrong-template").hexdigest()
    assert receipt["process_id"] == 814 and receipt["ordinal"] == 1
    assert not list(safe.glob("*.dispatch.safe.json"))
    assert not list(private.iterdir())


@pytest.mark.parametrize("origin", ["*", "https://example.invalid", "localhost,*"])
def test_cors_cannot_be_broadened(origin):
    with pytest.raises(admission.AdmissionError, match="CORS_ORIGIN_NOT_LOCALHOST"):
        admission.validate_server_args([
            "--jinja", "--offline", "--no-agent", "--no-webui", "--no-cache-prompt",
            "--cors-origins", origin,
        ])


@pytest.mark.parametrize(("field", "wrong"), [
    ("native_chat_template_sha256", "f" * 64),
    ("observed_served_chat_template_sha256", "f" * 64),
    ("observed_served_chat_template_utf8_bytes", 19),
    ("process_id", 999), ("served_template_matches_pin", 1),
])
def test_observation_audit_rejects_raw_served_pid_length_or_boolean_tampering(
    tmp_path, field, wrong,
):
    contract = synthetic_config()
    context = {"process_id": 815, "ordinal": 1, "epoch": 1}
    observed = []
    process = SimpleNamespace(pid=815, poll=lambda: None)
    admission.check_identity(
        process, MetadataClient(contract, "synthetic-template"), contract, observed.append)
    record = {**observed[0], **context, "contract_sha256": "b" * 64}
    path = tmp_path / "tpl.safe.json"
    admission.write_once(path, record)
    admission.verify_template_observation(contract, "b" * 64, path, context)
    record[field] = wrong
    path.write_bytes(admission.canonical(record))
    with pytest.raises(admission.AdmissionError, match="TEMPLATE_OBSERVATION_BINDING_MISMATCH"):
        admission.verify_template_observation(contract, "b" * 64, path, context)


def test_v2_does_not_change_fixture_scorers_requests_or_eleven_call_plan():
    def definitions(filename):
        tree = ast.parse((SCRIPTS / filename).read_text(encoding="utf-8"))
        selected = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                "score_answer", "parse_reply", "request_for", "plan_for",
            }:
                selected[node.name] = ast.dump(node, include_attributes=False)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {
                        "GENERATION", "SCORERS", "EXPECTED",
                    }:
                        selected[target.id] = ast.dump(node.value, include_attributes=False)
        return selected

    before = definitions("run_pa_llama_target_admission_v1.py")
    after = definitions("run_pa_llama_target_admission_v2.py")
    assert len(before) == 7 and before == after
