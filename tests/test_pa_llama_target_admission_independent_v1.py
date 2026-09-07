"""Independent synthetic-only admission QA; never load a model or open a socket."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_pa_llama_target_admission_v1.py"
SPEC = importlib.util.spec_from_file_location("independent_pa_admission_qa", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)

ANSWERS = [
    ("exact_sentinel", "exact_text", "P2_OK", "P2_OK"),
    ("arithmetic", "integer", 42, "42"),
    ("sorting", "integer_list", [1, 2, 3], "1,2,3"),
    ("color_mixing", "word", "green", "green"),
    ("capital", "word", "paris", "Paris"),
    ("translation", "word", "bonjour", "Bonjour"),
    ("opposite", "word", "cold", "cold"),
    ("primes", "integer_list", [2, 3, 5], "2,3,5"),
    ("json_format", "json_object", {"status": "ok"}, '{"status":"ok"}'),
    ("copy_token", "exact_text", "alpha-7", "alpha-7"),
]


def config():
    return {
        "model": {"alias": "independent-synthetic-model"},
        "runtime": {"native_chat_template_sha256": admission.sha_bytes(b"synthetic-template")},
        "server": {"request_timeout_seconds": 2},
        "evidence_class": "HARMLESS_OPERATIONAL_TARGET_ADMISSION_NOT_PAPER_EVIDENCE",
        "fixtures": [
            {"prompt_id": name, "scorer": scorer, "expected": copy.deepcopy(expected),
             "text": f"Synthetic independent fixture {name}."}
            for name, scorer, expected, _ in ANSWERS
        ],
    }


def response(contract, text):
    return {
        "model": contract["model"]["alias"],
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 17, "completion_tokens": 3, "total_tokens": 20},
    }


@pytest.mark.parametrize(("fixture_index", "text"), [
    (0, "Ｐ２＿ＯＫ"), (0, "P2_OK\u200b"), (0, '"P2_OK"'),
    (1, "４２"), (1, "٤٢"), (1, "4e1+2"), (1, "042"), (1, "42\n43"),
    (2, "1，2，3"), (2, "1,2,3,"), (2, "1,2,3\nExplanation"),
    (4, "Paris\u200b"), (4, "Ρaris"),
    (8, '{"status":"ok","status":"ok"}'), (8, '{"status":"ok"}\n{}'),
    (8, '{"status":true}'), (8, '{"status":"ok","extra":Infinity}'),
    (9, "alpha−7"), (9, "alpha-7\x00"),
])
def test_unicode_and_whole_response_fail_closed(fixture_index, text):
    assert not admission.score_answer(config()["fixtures"][fixture_index], text)[
        "content_check_passed"]


def test_nonempty_answer_with_zero_generation_tokens_is_integrity_failure():
    contract = config()
    value = response(contract, "P2_OK")
    value["usage"].update(completion_tokens=0, total_tokens=17)
    with pytest.raises(admission.AdmissionError):
        admission.parse_reply(contract, contract["fixtures"][0], admission.canonical(value))


def test_request_has_only_frozen_generation_and_single_user_message():
    contract = config()
    request = admission.request_for(contract, admission.plan_for(contract)[0])
    assert request == {
        "model": "independent-synthetic-model",
        "messages": [{"role": "user", "content": "Synthetic independent fixture exact_sentinel."}],
        "stream": False, "seed": 17, "temperature": 0, "max_tokens": 48,
        "top_k": 1, "top_p": 1, "min_p": 0, "repeat_penalty": 1,
    }


def test_loopback_transport_serializes_once_and_obeys_response_byte_limit():
    client = admission.LoopbackClient(18087)
    observed = []

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, limit):
            observed.append(("read", limit))
            return b"{}"

    class Opener:
        def open(self, request, timeout):
            observed.append((request.full_url, request.get_method(), request.data, timeout))
            return Reply()

    client.opener = Opener()
    assert client.request("/v1/chat/completions", {"probe": "synthetic"}, timeout=2) == b"{}"
    assert observed == [
        ("http://127.0.0.1:18087/v1/chat/completions", "POST", b'{"probe":"synthetic"}', 2),
        ("read", 2_000_001),
    ]


def test_dispatch_journal_and_private_request_exist_before_only_post(tmp_path):
    contract = config()
    safe = tmp_path / "safe"
    private = tmp_path / "private"
    safe.mkdir()
    private.mkdir()
    process = SimpleNamespace(pid=301, poll=lambda: None)
    posts = []

    class Client:
        def get(self, route):
            return ({"data": [{"id": contract["model"]["alias"]}]} if route == "/v1/models"
                    else {"chat_template": "synthetic-template"})

        def request(self, route, payload, *, timeout):
            journal = json.loads((safe / "01.dispatch.safe.json").read_bytes())
            request = json.loads((private / "01.request.private.json").read_bytes())
            assert journal["request_sha256"] == admission.identity(payload)
            assert request == payload and journal["process_id"] == 301
            assert not (private / "01.reply.private.json").exists()
            posts.append(route)
            return admission.canonical(response(contract, "P2_OK"))

    item = admission.plan_for(contract)[0]
    admission.dispatch_one(contract, "1" * 64, item, process, Client(), safe, private,
                           contract["runtime"])
    assert posts == ["/v1/chat/completions"]
    assert (safe / "01.row.safe.json").is_file()
    assert (private / "01.reply.private.json").is_file()


def make_receipts(tmp_path):
    contract = config()
    contract_sha = "2" * 64
    safe = tmp_path / "safe"
    private = tmp_path / "private"
    safe.mkdir()
    private.mkdir()
    for epoch in (1, 2):
        event = {"contract_sha256": contract_sha, "epoch": epoch, "pid": 400 + epoch,
                 "owned_process_only": True}
        admission.write_once(safe / f"server-{epoch:02d}.started.safe.json", event)
        admission.write_once(safe / f"server-{epoch:02d}.identity.safe.json", {
            **event,
            "native_chat_template_sha256": contract["runtime"]["native_chat_template_sha256"],
        })
        admission.write_once(safe / f"server-{epoch:02d}.stopped.safe.json", {
            **event, "returncode": 0,
        })
    for index, item in enumerate(admission.plan_for(contract)):
        text = ANSWERS[index if index < 10 else 0][3]
        request = admission.request_for(contract, item)
        raw = admission.canonical(response(contract, text))
        journal = {
            "contract_sha256": contract_sha, "ordinal": item["ordinal"], "epoch": item["epoch"],
            "fixture_id": item["fixture"]["prompt_id"], "process_id": 400 + item["epoch"],
            "native_chat_template_sha256": contract["runtime"]["native_chat_template_sha256"],
            "request_sha256": admission.identity(request),
        }
        prefix = f"{item['ordinal']:02d}"
        admission.write_once(safe / f"{prefix}.dispatch.safe.json", journal)
        admission.write_once(private / f"{prefix}.request.private.json", request)
        admission.write_once(private / f"{prefix}.reply.private.json", raw, raw=True)
        admission.write_once(safe / f"{prefix}.row.safe.json", {
            **journal, **admission.parse_reply(contract, item["fixture"], raw),
            "latency_seconds": 0.01, "request_max_tokens": 48,
        })
    return contract, contract_sha, safe, private


def test_synthetic_complete_receipts_reconcile(tmp_path):
    contract, checksum, safe, private = make_receipts(tmp_path)
    rows = admission.reconcile(contract, checksum, safe, private)
    assert len(rows) == 11 and all(row["passed"] for row in rows)


def test_coherent_row_and_journal_pid_tampering_cannot_fake_owned_epoch(tmp_path):
    contract, checksum, safe, private = make_receipts(tmp_path)
    for suffix in ("dispatch", "row"):
        path = safe / f"01.{suffix}.safe.json"
        value = json.loads(path.read_bytes())
        value["process_id"] = 999
        path.write_bytes(admission.canonical(value))
    with pytest.raises(admission.AdmissionError):
        admission.reconcile(contract, checksum, safe, private)


def test_epoch_template_binding_must_match_request_and_config(tmp_path):
    contract, checksum, safe, private = make_receipts(tmp_path)
    path = safe / "server-02.identity.safe.json"
    value = json.loads(path.read_bytes())
    value["native_chat_template_sha256"] = "f" * 64
    path.write_bytes(admission.canonical(value))
    with pytest.raises(admission.AdmissionError):
        admission.reconcile(contract, checksum, safe, private)
