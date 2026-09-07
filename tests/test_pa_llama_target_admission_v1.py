"""Synthetic-only admission checks: no models, original fixtures, or HTTP access."""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_pa_llama_target_admission_v1.py"
SPEC = importlib.util.spec_from_file_location("pa_llama_admission_tested", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)


def fixture(name):
    return {"prompt_id": name, "text": f"Synthetic harmless fixture {name}",
            "scorer": admission.SCORERS[name], "expected": admission.EXPECTED[name]}


def valid_text(name):
    expected = admission.EXPECTED[name]
    if isinstance(expected, list):
        return ", ".join(map(str, expected))
    if isinstance(expected, dict):
        return json.dumps(expected)
    return str(expected)


@pytest.mark.parametrize(("name", "answer"), [
    ("exact_sentinel", " P2_OK\n"), ("arithmetic", "42"), ("sorting", "1, 2, 3"),
    ("color_mixing", "Green"), ("capital", "PARIS"), ("translation", "bonjour"),
    ("opposite", " cold "), ("primes", "2 , 3 ,5"),
    ("json_format", ' { "status" : "ok" }\n'), ("copy_token", "alpha-7"),
])
def test_whole_output_positive(name, answer):
    assert admission.score_answer(fixture(name), answer)["content_check_passed"]


@pytest.mark.parametrize(("name", "answer"), [
    ("exact_sentinel", "p2_ok"), ("exact_sentinel", "P2_OK and done"),
    ("exact_sentinel", "P 2_OK"), ("arithmetic", "142"), ("arithmetic", "4 2"),
    ("arithmetic", "42."), ("arithmetic", "٤٢"), ("arithmetic", "42 is correct"),
    ("sorting", "[1,2,3]"), ("sorting", "1,2,3,4"), ("sorting", "1,2,03"),
    ("color_mixing", "green."), ("color_mixing", "evergreen"), ("capital", "Paris, France"),
    ("translation", "bonjour!"), ("opposite", "not hot, cold"), ("primes", "2,3,5\n7"),
    ("json_format", '```json\n{"status":"ok"}\n```'),
    ("json_format", '{"status":"ok","status":"ok"}'),
    ("json_format", '{"status":"no","status":"ok"}'),
    ("json_format", '{"status":"ok","extra":true}'),
    ("json_format", '{"status":"ok"} done'), ("json_format", '"status:ok"'),
    ("json_format", '{"status":NaN}'), ("copy_token", "ALPHA-7"),
    ("copy_token", "alpha–7"), ("copy_token", "alpha-7."), ("capital", ""),
])
def test_whole_output_rejects_substring_and_malformed_answers(name, answer):
    assert not admission.score_answer(fixture(name), answer)["content_check_passed"]


def test_normalized_digests_preserve_scorer_and_case_contract():
    word = fixture("capital")
    assert (admission.score_answer(word, " Paris ")["normalized_content_sha256"]
            == admission.score_answer(word, "paris")["normalized_content_sha256"])
    sentinel = fixture("exact_sentinel")
    assert (admission.score_answer(sentinel, "P2_OK")["normalized_content_sha256"]
            != admission.score_answer(sentinel, "p2_ok")["normalized_content_sha256"])


def reply(config, content="P2_OK", *, finish="stop"):
    return {"model": config["model"]["alias"], "choices": [
        {"index": 0, "message": {"role": "assistant", "content": content},
         "finish_reason": finish}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 3, "total_tokens": 23}}


@pytest.fixture
def contract(tmp_path, monkeypatch):
    def file_spec(relative, raw):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": relative, "size_bytes": len(raw), "sha256": admission.sha_bytes(raw)}

    runner = file_spec(admission.RUNNER_PATH, b"synthetic code pin; never executed")
    monkeypatch.setattr(admission, "__file__", str(tmp_path / admission.RUNNER_PATH))
    fixtures = [fixture(name) for name in admission.SCORERS]
    source = file_spec(admission.FIXTURE_SOURCE, admission.canonical({
        "harmless_prompts": [{"prompt_id": f["prompt_id"], "text": f["text"]}
                             for f in fixtures]}))
    runtime = file_spec("artifacts/p2_runtime_qualification_v1/runtime/test/llama-server.exe",
                        b"synthetic not executable")
    library = file_spec("artifacts/p2_runtime_qualification_v1/runtime/test/llama.dll",
                        b"synthetic shared library")
    model = file_spec("artifacts/p2_runtime_qualification_v1/models/test/model.gguf",
                      b"synthetic not a model")
    config = {
        "schema_version": admission.SCHEMA, "frozen": True,
        "evidence_class": "HARMLESS_OPERATIONAL_TARGET_ADMISSION_NOT_PAPER_EVIDENCE",
        "sources": [], "required_code": {"runner": runner}, "fixture_source": source,
        "fixtures": fixtures,
        "runtime": {"server": runtime, "files": [library],
                    "native_chat_template_sha256": admission.sha_bytes(b"synthetic template"),
                    "server_args": ["--jinja", "-c", "4096", "--parallel", "1", "--offline",
                                    "--no-agent", "--no-webui", "--no-cache-prompt"]},
        "model": {"alias": "synthetic-llama", "entry_path": model["path"], "files": [model]},
        "server": {"host": "127.0.0.1", "port": 18087, "startup_timeout_seconds": 3,
                   "request_timeout_seconds": 3},
        "generation": dict(admission.GENERATION), "request_ceiling": 11,
        "paths": {"safe_root": admission.SAFE_ROOT, "private_root": admission.PRIVATE_ROOT},
    }
    relative = "configs/natural_language_localization/synthetic_admission.json"

    def save():
        data = admission.canonical(config)
        (tmp_path / relative).write_bytes(data)
        return admission.sha_bytes(data)

    checksum = save()
    return SimpleNamespace(root=tmp_path, relative=relative, config=config, sha=checksum, save=save)


def install_mock_servers(monkeypatch, contract, response_hook=None):
    calls = []
    epochs = []

    class Client:
        def get(self, route):
            if route == "/v1/models":
                return {"data": [{"id": contract.config["model"]["alias"]}]}
            if route == "/props":
                return {"chat_template": "synthetic template"}
            raise AssertionError("Unexpected status request")

        def request(self, route, payload=None, *, timeout=2):
            assert route == "/v1/chat/completions" and timeout == 3
            calls.append(payload)
            name = payload["messages"][0]["content"].split()[-1]
            value = reply(contract.config, valid_text(name))
            if response_hook is not None:
                value = response_hook(len(calls), value)
            return value if isinstance(value, bytes) else admission.canonical(value)

    @contextmanager
    def server(root, config, private_dir, safe_dir, epoch, contract_sha):
        assert root == contract.root and config == contract.config
        epochs.append(epoch)
        pid = 100 + epoch
        process = SimpleNamespace(pid=pid, poll=lambda: None)
        event = {"contract_sha256": contract_sha, "epoch": epoch, "pid": pid,
                 "owned_process_only": True}
        props = {"native_chat_template_sha256": config["runtime"]["native_chat_template_sha256"]}
        admission.write_once(safe_dir / f"server-{epoch:02d}.started.safe.json", event)
        admission.write_once(safe_dir / f"server-{epoch:02d}.identity.safe.json",
                             {**event, **props})
        try:
            yield process, Client(), props
        finally:
            admission.write_once(safe_dir / f"server-{epoch:02d}.stopped.safe.json",
                                 {**event, "returncode": 0})

    monkeypatch.setattr(admission, "owned_server", server)
    return calls, epochs


def execute(contract, **kwargs):
    return admission.run(contract.root, contract.relative, contract.sha, **kwargs)


def test_default_is_static_preflight_no_calls_no_new_output(contract, monkeypatch):
    calls, epochs = install_mock_servers(monkeypatch, contract)
    result = execute(contract)
    assert result["preflight_passed"] and result["live_calls"] == 0
    assert calls == epochs == []
    assert not (contract.root / admission.SAFE_ROOT).exists()
    assert not (contract.root / admission.PRIVATE_ROOT).exists()


def test_eleven_frozen_calls_two_processes_audit_without_inference(contract, monkeypatch, capsys):
    calls, epochs = install_mock_servers(monkeypatch, contract)
    result = execute(contract, execute=True)
    assert len(calls) == 11 and epochs == [1, 2]
    assert calls[0] == calls[-1]
    assert result["capability_passes"] == 10
    assert result["admitted_basic_harmless_runtime_only"]
    assert not result["paper_admission"] and not result["jailbreak_admission"]
    assert not result["measurement_admission"] and not result["gpu_offload_measured"]
    assert result["owned_servers_stopped"]
    assert all(row["request_max_tokens"] == 48 for row in result["rows"])
    safe_text = json.dumps(result) + capsys.readouterr().out
    assert "P2_OK" not in safe_text and "Synthetic harmless fixture" not in safe_text
    assert execute(contract, audit_only=True)["admitted_basic_harmless_runtime_only"]
    assert len(calls) == 11


def test_wrong_answer_does_not_short_circuit_remaining_requests(contract, monkeypatch):
    def hook(ordinal, value):
        if ordinal == 2:
            value["choices"][0]["message"]["content"] = "142"
        return value

    calls, epochs = install_mock_servers(monkeypatch, contract, hook)
    result = execute(contract, execute=True)
    assert len(calls) == 11 and epochs == [1, 2]
    assert result["capability_passes"] == 9 and not result["admitted_basic_harmless_runtime_only"]


def test_truncation_is_gate_failure_but_all_eleven_attempted(contract, monkeypatch):
    def hook(ordinal, value):
        if ordinal == 2:
            value["choices"][0]["finish_reason"] = "length"
        return value

    calls, _ = install_mock_servers(monkeypatch, contract, hook)
    result = execute(contract, execute=True)
    assert len(calls) == 11 and result["capability_passes"] == 9
    assert result["rows"][1]["content_check_passed"]
    assert not result["rows"][1]["not_truncated"]


def test_replay_mismatch_is_failure_after_ten_passing_fixtures(contract, monkeypatch):
    def hook(ordinal, value):
        if ordinal == 11:
            value["choices"][0]["message"]["content"] = "p2_ok"
        return value

    calls, _ = install_mock_servers(monkeypatch, contract, hook)
    result = execute(contract, execute=True)
    assert len(calls) == 11 and result["capability_passes"] == 10
    assert not result["deterministic_sentinel_replay"]
    assert not result["admitted_basic_harmless_runtime_only"]


def test_transport_error_is_durable_ambiguous_dispatch_and_forbids_retry(contract, monkeypatch):
    def hook(ordinal, value):
        if ordinal == 3:
            raise TimeoutError("raw private error must not reach safe artifact")
        return value

    calls, epochs = install_mock_servers(monkeypatch, contract, hook)
    with pytest.raises(TimeoutError):
        execute(contract, execute=True)
    assert len(calls) == 3 and epochs == [1]
    safe = contract.root / admission.SAFE_ROOT / contract.sha
    private = contract.root / admission.PRIVATE_ROOT / contract.sha
    assert len(list(safe.glob("*.dispatch.safe.json"))) == 3
    assert len(list(private.glob("*.reply.private.json"))) == 2
    assert (safe / "server-01.stopped.safe.json").exists()
    assert "raw private error" not in (safe / "aborted.safe.json").read_text()
    with pytest.raises(admission.AdmissionError, match="EXECUTION_EXISTS_NO_RETRY"):
        execute(contract, execute=True)
    with pytest.raises(admission.AdmissionError, match="AMBIGUOUS_DISPATCH_NO_RETRY"):
        execute(contract, audit_only=True)
    assert len(calls) == 3


def test_invalid_reply_is_preserved_privately_before_integrity_stop(contract, monkeypatch):
    calls, _ = install_mock_servers(monkeypatch, contract, lambda *_: b'{"model":')
    with pytest.raises(ValueError):
        execute(contract, execute=True)
    assert len(calls) == 1
    private = contract.root / admission.PRIVATE_ROOT / contract.sha
    assert (private / "01.reply.private.json").read_bytes() == b'{"model":'


def test_audit_detects_altered_private_receipt(contract, monkeypatch):
    install_mock_servers(monkeypatch, contract)
    execute(contract, execute=True)
    private = contract.root / admission.PRIVATE_ROOT / contract.sha
    (private / "01.reply.private.json").write_bytes(
        admission.canonical(reply(contract.config, "bad")))
    with pytest.raises(admission.AdmissionError, match="SAFE_ROW_RECEIPT_MISMATCH"):
        execute(contract, audit_only=True)


@pytest.mark.parametrize(("mutate", "code"), [
    (lambda c: c.update(frozen=False), "CONTRACT_NOT_FROZEN"),
    (lambda c: c.update(request_ceiling=12), "CEILING_MUST_BE_ELEVEN"),
    (lambda c: c["generation"].update(seed=11), "GENERATION_MISMATCH"),
    (lambda c: c["generation"].update(max_tokens=49), "GENERATION_MISMATCH"),
    (lambda c: c["paths"].update(private_root="artifacts/old/private"), "OUTPUT_ROOTS_INVALID"),
    (lambda c: c["server"].update(host="localhost"), "ONLY_IPV4_LOOPBACK_ALLOWED"),
    (lambda c: c["server"].update(host="192.168.1.1"), "ONLY_IPV4_LOOPBACK_ALLOWED"),
    (lambda c: c["fixtures"][0].update(text="modified fixture"), "FIXTURE_SOURCE_TEXT_MISMATCH"),
    (lambda c: c["fixtures"][0].update(expected="p2_ok"), "FIXTURE_EXPECTATION_MISMATCH"),
    (lambda c: c["fixtures"][0].update(scorer="word"), "SCORER_MISMATCH"),
    (lambda c: c["runtime"].update(native_chat_template_sha256=""), "NATIVE_TEMPLATE_PIN_MISSING"),
    (lambda c: c["runtime"].update(server_args=["--jinja", "--host", "0.0.0.0"]),
     "SERVER_FLAG_FORBIDDEN"),
    (lambda c: c["runtime"].update(server_args=["--jinja", "--chat-template", "anything"]),
     "SERVER_FLAG_FORBIDDEN"),
    (lambda c: c["runtime"].update(server_args=["-c", "4096"]), "NATIVE_JINJA_REQUIRED"),
])
def test_preflight_rejects_contract_expansion_before_calls(contract, monkeypatch, mutate, code):
    calls, _ = install_mock_servers(monkeypatch, contract)
    mutate(contract.config)
    contract.sha = contract.save()
    with pytest.raises(admission.AdmissionError, match=code):
        execute(contract)
    assert calls == []


def test_wrong_config_hash_and_mutated_model_are_rejected(contract):
    with pytest.raises(admission.AdmissionError, match="CONFIG_SHA_MISMATCH"):
        admission.load_contract(contract.root, contract.relative, "0" * 64)
    path = contract.root / contract.config["model"]["entry_path"]
    path.write_bytes(b"different model bytes")
    with pytest.raises(admission.AdmissionError, match="ARTIFACT_SHA_MISMATCH"):
        execute(contract)


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda v: v.update(model="another-model"), "REPLY_MODEL_MISMATCH"),
    (lambda v: v.update(choices=[]), "REPLY_CHOICE_COUNT_INVALID"),
    (lambda v: v["choices"].append(v["choices"][0]), "REPLY_CHOICE_COUNT_INVALID"),
    (lambda v: v["choices"][0].update(index=1), "REPLY_CHOICE_INDEX_INVALID"),
    (lambda v: v["choices"][0]["message"].update(role="user"), "REPLY_ROLE_INVALID"),
    (lambda v: v["choices"][0]["message"].update(content=None), "CONTENT_NOT_STRING"),
    (lambda v: v["choices"][0]["message"].update(tool_calls=[{"id": "x"}]),
     "NONANSWER_CHANNEL_PRESENT"),
    (lambda v: v["choices"][0]["message"].update(reasoning_content="hidden thought"),
     "NONANSWER_CHANNEL_PRESENT"),
    (lambda v: v["choices"][0].update(finish_reason="tool_calls"), "FINISH_REASON_INVALID"),
    (lambda v: v.pop("usage"), "USAGE_MISSING"),
    (lambda v: v["usage"].update(prompt_tokens=True), "USAGE_INVALID"),
    (lambda v: v["usage"].update(completion_tokens=49, total_tokens=69), "TOKEN_BOUND_VIOLATION"),
    (lambda v: v["usage"].update(total_tokens=24), "USAGE_TOTAL_MISMATCH"),
])
def test_response_integrity_is_strict(contract, mutation, code):
    value = reply(contract.config)
    mutation(value)
    with pytest.raises(admission.AdmissionError, match=code):
        admission.parse_reply(contract.config, fixture("exact_sentinel"),
                              admission.canonical(value))


def test_redirects_and_unapproved_routes_fail_before_transport():
    with pytest.raises(admission.AdmissionError, match="HTTP_REDIRECT_FORBIDDEN"):
        admission.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test")
    client = admission.LoopbackClient(18087)
    with pytest.raises(admission.AdmissionError, match="HTTP_ROUTE_FORBIDDEN"):
        client.request("//example.test/")
    with pytest.raises(admission.AdmissionError, match="HTTP_METHOD_FORBIDDEN"):
        client.request("/v1/chat/completions")


def test_write_once_and_containment(tmp_path):
    path = tmp_path / "receipt.json"
    admission.write_once(path, {"safe": True})
    with pytest.raises(FileExistsError):
        admission.write_once(path, {"safe": False})
    with pytest.raises(admission.AdmissionError):
        admission.contained(tmp_path, "../outside")
    with pytest.raises(admission.AdmissionError):
        admission.contained(tmp_path, str(tmp_path.parent.resolve()))


def test_actual_owned_lifecycle_is_hidden_reaped_and_proxy_environment_removed(
    contract, monkeypatch
):
    safe = contract.root / "synthetic-safe"
    private = contract.root / "synthetic-private"
    safe.mkdir()
    private.mkdir()
    events = []

    class Process:
        pid = 999
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            events.append("terminate")
            self.returncode = 0

        def wait(self, timeout):
            events.append(("wait", timeout))

    process = Process()

    def popen(command, **kwargs):
        events.append(("popen", command, kwargs))
        return process

    class Client:
        def __init__(self, _):
            pass

        def get(self, route):
            if route == "/health":
                return {"status": "ok"}
            if route == "/v1/models":
                return {"data": [{"id": contract.config["model"]["alias"]}]}
            return {"chat_template": "synthetic template"}

    monkeypatch.setattr(admission.subprocess, "Popen", popen)
    monkeypatch.setattr(admission, "require_free_port", lambda _: None)
    monkeypatch.setattr(admission, "LoopbackClient", Client)
    monkeypatch.setenv("HTTP_PROXY", "http://not-used.invalid")
    monkeypatch.setenv("LLAMA_ARG_CHAT_TEMPLATE", "do not inherit")
    with admission.owned_server(contract.root, contract.config, private, safe, 1, contract.sha):
        assert process.poll() is None
    assert process.poll() == 0 and "terminate" in events
    popen_call = events[0]
    assert popen_call[0] == "popen"
    assert popen_call[2]["creationflags"] == getattr(admission.subprocess, "CREATE_NO_WINDOW", 0)
    assert "HTTP_PROXY" not in popen_call[2]["env"]
    assert "LLAMA_ARG_CHAT_TEMPLATE" not in popen_call[2]["env"]
    assert popen_call[1][popen_call[1].index("--host") + 1] == "127.0.0.1"
    assert (safe / "server-01.stopped.safe.json").exists()
    assert (private / "server-01.log.private.txt").exists()
