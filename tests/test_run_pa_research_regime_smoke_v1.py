"""Synthetic contracts and mocked loopback/processes; never use model data."""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


smoke = module("scripts/run_pa_research_regime_smoke_v1.py", "tested_regime_smoke")
helper = module("scripts/run_pa_llama_target_admission_v2.py", "tested_frozen_identity_helpers")


@pytest.fixture
def contract(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("prsrun")

    def pin(relative, value, *, raw=False):
        data = value if raw else smoke.canonical(value)
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": relative, "size_bytes": len(data), "sha256": smoke.raw_digest(data)}

    tasks = [
        {"task_id": "P2_ARITHMETIC", "fixture_id": "arithmetic", "text": "Synthetic arithmetic",
         "scorer": "integer", "expected": 42},
        {"task_id": "P2_COPY_TOKEN", "fixture_id": "copy_token", "text": "Synthetic copy",
         "scorer": "exact_text", "expected": "alpha-7"},
    ]
    code = {
        "runner": pin(smoke.RUNNER, b"synthetic runner pin", raw=True),
        "v2_helper": pin(smoke.HELPER, b"synthetic frozen helper pin", raw=True),
        "proposal_validator": pin(smoke.VALIDATOR, b"synthetic frozen validator pin", raw=True),
        "tests": pin("tests/test_run_pa_research_regime_smoke_v1.py", b"synthetic tests", raw=True),
    }
    monkeypatch.setattr(smoke, "__file__", str(root / smoke.RUNNER))
    server = pin("artifacts/p2_runtime_qualification_v1/runtime/synthetic/server.exe",
                 b"not executable", raw=True)
    library = pin("artifacts/p2_runtime_qualification_v1/runtime/synthetic/model.dll",
                  b"not a DLL", raw=True)
    weights = pin("artifacts/p2_runtime_qualification_v1/models/synthetic/model.gguf",
                  b"not a GGUF", raw=True)
    v2 = {
        "model": {"alias": "synthetic-llama", "entry_path": weights["path"], "files": [weights]},
        "runtime": {
            "server": server, "files": [library],
            "native_chat_template_sha256": smoke.raw_digest(b"synthetic raw template\n"),
            "served_chat_template_sha256": smoke.raw_digest(b"synthetic served template"),
            "served_chat_template_utf8_bytes": len(b"synthetic served template"),
            "server_args": ["--jinja", "--ctx-size", "4096", "--parallel", "1", "--offline",
                            "--no-agent", "--no-webui", "--no-cache-prompt",
                            "--cors-origins", "localhost"],
        },
        "server": {"host": "127.0.0.1", "port": 18087, "startup_timeout_seconds": 3,
                   "request_timeout_seconds": 3},
    }
    v2_pin = pin(smoke.V2_CONTRACT, v2)
    proposal = {
        "sources": {"old_v2_runner": code["v2_helper"], "validator": code["proposal_validator"],
                    "v2_contract": v2_pin},
        "tasks": tasks, "seeds": [11, 23, 47], "generation": dict(smoke.GENERATION),
        "context_tokens": 4096,
    }
    proposal_pin = pin(smoke.PROPOSAL, proposal)
    authority = pin(smoke.AUTHORITY, b"synthetic authority", raw=True)
    decision = pin(smoke.DECISION, b"synthetic decision", raw=True)
    config = {
        "schema_version": smoke.SCHEMA, "frozen": True, "execution_authorized": True,
        "purpose": smoke.PURPOSE,
        "evidence_class": "RESULT_INFORMED_DEVELOPMENT_OPERATIONAL_SMOKE_NOT_CONFIRMATION",
        "paper_validity": False, "request_ceiling": 6, "one_batch_only": True, "no_retries": True,
        "proposal": proposal_pin, "proposal_rule_plan_sha256": "a" * 64,
        "v2_contract": v2_pin, "required_code": code, "sources": [authority, decision],
        "model": v2["model"], "runtime": v2["runtime"], "server": v2["server"],
        "tasks": tasks, "seeds": [11, 23, 47], "generation": dict(smoke.GENERATION),
        "context_tokens": 4096,
        "paths": {"safe_root": smoke.SAFE_ROOT, "private_root": smoke.PRIVATE_ROOT},
    }

    def proposal_preflight(root_arg, path, sha):
        assert root_arg == root and path == smoke.PROPOSAL and sha == proposal_pin["sha256"]
        return {"static_preflight_passed": True, "execution_authorized": False,
                "proposal_plan_sha256": "a" * 64}

    def load_pinned(path, name):
        if str(path).endswith("run_pa_llama_target_admission_v2.py"):
            return helper
        assert str(path).endswith("preflight_pa_research_regime_smoke_v1.py")
        return SimpleNamespace(preflight=proposal_preflight)

    monkeypatch.setattr(smoke, "load_module", load_pinned)

    def save():
        return pin(smoke.CONFIG, config)["sha256"]

    return SimpleNamespace(root=root, config=config, sha=save(), save=save)


def value_reply(config, content, *, finish="stop", completion_tokens=4):
    return {"model": config["model"]["alias"], "choices": [{
        "index": 0, "message": {"role": "assistant", "content": content},
        "finish_reason": finish}], "usage": {"prompt_tokens": 30,
                                               "completion_tokens": completion_tokens,
                                               "total_tokens": 30 + completion_tokens}}


def install_servers(monkeypatch, contract, hook=None):
    calls = []
    epochs = []

    class Client:
        def get(self, route):
            if route == "/v1/models":
                return {"data": [{"id": contract.config["model"]["alias"]}]}
            assert route == "/props"
            return {"chat_template": "synthetic served template"}

        def request(self, route, payload=None, *, timeout=2):
            assert route == "/v1/chat/completions" and timeout == 3
            ordinal = len(calls) + 1
            safe = contract.root / smoke.SAFE_ROOT / contract.sha
            assert (safe / f"{ordinal:02d}.dispatch.safe.json").is_file()
            calls.append(payload)
            content = "42" if ordinal % 2 else "alpha-7"
            value = value_reply(contract.config, content)
            if hook is not None:
                value = hook(ordinal, value)
            return value if isinstance(value, bytes) else smoke.canonical(value)

    @contextmanager
    def owned(root, config, private_dir, safe_dir, epoch, sha):
        assert epoch == 1 and root == contract.root
        epochs.append(epoch)
        process = SimpleNamespace(pid=567, poll=lambda: None)
        event = {"contract_sha256": sha, "epoch": 1, "pid": 567, "owned_process_only": True}
        helper.write_once(safe_dir / "server-01.started.safe.json", event)

        def observer(observation):
            helper.write_once(safe_dir / "server-01.tpl.safe.json", {**event, **observation})

        props = helper.check_identity(process, Client(), config, observer)
        helper.write_once(safe_dir / "server-01.identity.safe.json", {**event, **props})
        try:
            yield process, Client(), props
        finally:
            helper.write_once(safe_dir / "server-01.stopped.safe.json", {**event, "returncode": 0})

    monkeypatch.setattr(helper, "owned_server", owned)
    return calls, epochs


def run(contract, **kwargs):
    return smoke.run(contract.root, smoke.CONFIG, contract.sha, **kwargs)


def test_default_preflight_rehashes_but_never_launches_or_dispatches(contract, monkeypatch):
    calls, epochs = install_servers(monkeypatch, contract)
    result = run(contract)
    assert result["preflight_passed"] and result["calls_made"] == 0
    assert result["model_runtime_artifacts_rehashed"]
    assert len(result["plan"]) == 6 and calls == epochs == []
    assert not (contract.root / smoke.SAFE_ROOT).exists()


def test_exact_six_calls_one_epoch_and_safe_only_summary(contract, monkeypatch, capsys):
    calls, epochs = install_servers(monkeypatch, contract)
    result = run(contract, execute=True)
    assert len(calls) == 6 and epochs == [1]
    assert [row["seed"] for row in calls] == [11, 11, 23, 23, 47, 47]
    assert all(row["max_tokens"] == 512 and row["temperature"] == 0.7 for row in calls)
    assert all(row["top_p"] == 0.9 and row["top_k"] == 50 for row in calls)
    assert result["bare_control_stochastic_regime_smoke_passed"]
    assert result["exact_task_passes"] == 6 and result["pass_denominator"] == 6
    assert not result["prior_v2_basic_admission_gate_passed"]
    assert not result["scientific_target_admitted"] and not result["judge_admitted"]
    assert not result["paper_claim_supported"] and not result["automatic_next_experiment"]
    text = json.dumps(result) + capsys.readouterr().out
    assert "Synthetic arithmetic" not in text and "alpha-7" not in text
    audit = run(contract, audit_only=True)
    assert audit["bare_control_stochastic_regime_smoke_passed"] and len(calls) == 6


@pytest.mark.parametrize("kind", ["wrong", "length", "empty"])
def test_task_or_truncation_failure_keeps_six_denominator(contract, monkeypatch, kind):
    def hook(ordinal, value):
        if ordinal == 1:
            if kind == "wrong":
                value["choices"][0]["message"]["content"] = "142"
            elif kind == "empty":
                value["choices"][0]["message"]["content"] = ""
            else:
                value["choices"][0]["finish_reason"] = "length"
        return value

    calls, _ = install_servers(monkeypatch, contract, hook)
    result = run(contract, execute=True)
    assert len(calls) == 6 and result["exact_task_passes"] == 5
    assert not result["bare_control_stochastic_regime_smoke_passed"]


def test_timeout_journal_prevents_second_batch_with_new_hash(contract, monkeypatch):
    def hook(ordinal, value):
        if ordinal == 3:
            raise TimeoutError("private diagnostic must not leak")
        return value

    calls, epochs = install_servers(monkeypatch, contract, hook)
    with pytest.raises(TimeoutError):
        run(contract, execute=True)
    safe = contract.root / smoke.SAFE_ROOT / contract.sha
    assert len(list(safe.glob("*.dispatch.safe.json"))) == 3
    assert len(list(safe.glob("*.row.safe.json"))) == 2
    assert (safe / "server-01.stopped.safe.json").is_file()
    assert "private diagnostic" not in (safe / "aborted.safe.json").read_text()
    with pytest.raises(smoke.SmokeError, match="AMBIGUOUS_DISPATCH_NO_RETRY"):
        run(contract, audit_only=True)
    with pytest.raises(smoke.SmokeError, match="ONE_BATCH_ALREADY_RESERVED_NO_RETRY"):
        run(contract, execute=True)
    contract.config["annotation"] = "different contract hash does not reset budget"
    contract.sha = contract.save()
    with pytest.raises(smoke.SmokeError, match="ONE_BATCH_ALREADY_RESERVED_NO_RETRY"):
        run(contract, execute=True)
    assert len(calls) == 3 and epochs == [1]


def test_integrity_failure_aborts_immediately_but_keeps_raw_receipt(contract, monkeypatch):
    def hook(_, value):
        value["model"] = "wrong alias"
        return value

    calls, _ = install_servers(monkeypatch, contract, hook)
    with pytest.raises(smoke.SmokeError, match="REPLY_MODEL_MISMATCH"):
        run(contract, execute=True)
    assert len(calls) == 1
    path = contract.root / smoke.PRIVATE_ROOT / contract.sha / "01.reply.private.json"
    assert path.is_file()


def test_unlike_v2_parser_512_regime_does_not_reject_more_than_48_tokens(contract):
    item = smoke.plan_for(contract.config)[0]
    raw = smoke.canonical(value_reply(contract.config, "42", completion_tokens=100))
    assert smoke.parse_reply(contract.config, item, raw, helper)["passed"]
    too_long = smoke.canonical(value_reply(contract.config, "42", completion_tokens=513))
    with pytest.raises(smoke.SmokeError, match="TOKEN_BOUND_VIOLATION"):
        smoke.parse_reply(contract.config, item, too_long, helper)


@pytest.mark.parametrize(("mutate", "code"), [
    (lambda c: c.update(frozen=False), "EXECUTION_CONTRACT_NOT_FROZEN"),
    (lambda c: c.update(execution_authorized=False), "EXECUTION_AUTHORITY_MISSING"),
    (lambda c: c.update(request_ceiling=7), "SIX_CALL_SINGLE_BATCH_RULE_REQUIRED"),
    (lambda c: c.update(no_retries=False), "SIX_CALL_SINGLE_BATCH_RULE_REQUIRED"),
    (lambda c: c.update(paper_validity=True), "EXPERIMENT_SCOPE_MISMATCH"),
    (lambda c: c["sources"].pop(), "AUTHORITY_AND_DECISION_PINS_REQUIRED"),
    (lambda c: c.update(proposal_rule_plan_sha256="0" * 64), "FROZEN_PROPOSAL_PLAN_MISMATCH"),
    (lambda c: c["tasks"][0].update(text="easier question"), "FROZEN_PROPOSAL_DESIGN_CHANGED"),
    (lambda c: c["tasks"][0].update(expected=142), "FROZEN_PROPOSAL_DESIGN_CHANGED"),
    (lambda c: c.update(seeds=[17, 23, 47]), "FROZEN_PROPOSAL_DESIGN_CHANGED"),
    (lambda c: c["generation"].update(max_tokens=48), "FROZEN_PROPOSAL_DESIGN_CHANGED"),
    (lambda c: c["generation"].update(temperature=0), "FROZEN_PROPOSAL_DESIGN_CHANGED"),
    (lambda c: c["model"].update(alias="new-target"), "FROZEN_V2_RUNTIME_IDENTITY_CHANGED"),
    (lambda c: c["server"].update(host="0.0.0.0"), "FROZEN_V2_RUNTIME_IDENTITY_CHANGED"),
    (lambda c: c["paths"].update(private_root="artifacts/old/private"), "OUTPUT_ROOTS_MISMATCH"),
])
def test_changed_contract_rejected_without_dispatch(contract, monkeypatch, mutate, code):
    calls, _ = install_servers(monkeypatch, contract)
    mutate(contract.config)
    contract.sha = contract.save()
    with pytest.raises(smoke.SmokeError, match=code):
        run(contract)
    assert calls == []


@pytest.mark.parametrize("target", ["model", "runtime"])
def test_artifact_rehash_detects_byte_mutation(contract, target):
    item = (contract.config["model"]["files"][0] if target == "model"
            else contract.config["runtime"]["files"][0])
    path = contract.root / item["path"]
    path.write_bytes(b"x" * path.stat().st_size)
    with pytest.raises(smoke.SmokeError, match="SOURCE_SHA_MISMATCH"):
        run(contract)


@pytest.mark.parametrize("target", ["reply", "request", "template", "pid", "max_tokens"])
def test_audit_detects_tampered_own_receipt_binding(contract, monkeypatch, target):
    install_servers(monkeypatch, contract)
    run(contract, execute=True)
    safe = contract.root / smoke.SAFE_ROOT / contract.sha
    private = contract.root / smoke.PRIVATE_ROOT / contract.sha
    if target == "reply":
        path = private / "01.reply.private.json"
        value = smoke.strict_json(path.read_bytes())
        value["choices"][0]["message"]["content"] = "142"
    elif target == "request":
        path = private / "01.request.private.json"
        value = smoke.strict_json(path.read_bytes())
        value["seed"] = 17
    elif target == "template":
        path = safe / "01.tpl.safe.json"
        value = smoke.strict_json(path.read_bytes())
        value["observed_served_chat_template_sha256"] = "0" * 64
    else:
        path = safe / "01.row.safe.json"
        value = smoke.strict_json(path.read_bytes())
        value["process_id" if target == "pid" else "request_max_tokens"] = 999
    path.write_bytes(smoke.canonical(value))
    with pytest.raises((smoke.SmokeError, helper.AdmissionError)):
        run(contract, audit_only=True)


def test_seventh_dispatch_rejected_before_any_network_or_output(contract, monkeypatch):
    calls, _ = install_servers(monkeypatch, contract)
    item = {**smoke.plan_for(contract.config)[0], "ordinal": 7}
    with pytest.raises(smoke.SmokeError, match="SIX_CALL_CEILING_EXCEEDED"):
        smoke.dispatch_one(contract.config, contract.sha, item, None, None,
                           contract.root, contract.root, helper)
    assert calls == []


def test_private_or_parent_descriptor_cannot_escape_scoped_reads(contract):
    item = {"path": "artifacts/private/input.json", "size_bytes": 0, "sha256": "0" * 64}
    with pytest.raises(smoke.SmokeError, match="SOURCE_READ_SCOPE_INVALID"):
        smoke.descriptor(contract.root, item, prefixes=("docs/",))
    with pytest.raises(smoke.SmokeError):
        smoke.contained(contract.root, "../outside")


@pytest.mark.parametrize(("target", "field", "replacement"), [
    ("reservation", "proposal_sha256", "0" * 64),
    ("reservation", "resume_allowed", True),
    ("lock", "resume_allowed", True),
    ("lock", "request_ceiling", 7),
])
def test_audit_binds_global_reservation_and_exact_execution_lock(
    contract, monkeypatch, target, field, replacement
):
    install_servers(monkeypatch, contract)
    run(contract, execute=True)
    safe_root = contract.root / smoke.SAFE_ROOT
    path = (safe_root / "one-batch.reserved.safe.json" if target == "reservation"
            else safe_root / contract.sha / "execution.lock.safe.json")
    value = smoke.strict_json(path.read_bytes())
    value[field] = replacement
    path.write_bytes(smoke.canonical(value))
    with pytest.raises(smoke.SmokeError, match="RESERVATION_MISMATCH|LOCK_BINDING_MISMATCH"):
        run(contract, audit_only=True)
