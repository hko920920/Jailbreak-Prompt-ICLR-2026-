"""Independent verifier tests use only freshly generated synthetic receipts."""

import ast
import copy
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/verify_pa_research_regime_smoke_v1.py"
SPEC = importlib.util.spec_from_file_location("independent_smoke_verifier_new", SCRIPT_PATH)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


@pytest.mark.parametrize(
    "text,scorer,expected,correct,parsed",
    [
        ("42", "integer", 42, True, True),
        (" 42\n", "integer", 42, True, True),
        ("142", "integer", 42, False, True),
        ("42.", "integer", 42, False, False),
        ("042", "integer", 42, False, False),
        ("+42", "integer", 42, False, False),
        ("4 2", "integer", 42, False, False),
        ("４２", "integer", 42, False, False),
        ("The answer is 42", "integer", 42, False, False),
        ("", "integer", 42, False, False),
        ("alpha-7", "exact_text", "alpha-7", True, True),
        (" alpha-7\n", "exact_text", "alpha-7", True, True),
        ("Alpha-7", "exact_text", "alpha-7", False, True),
        ("alpha-7.", "exact_text", "alpha-7", False, True),
        ("", "exact_text", "alpha-7", False, True),
    ],
)
def test_independent_whole_answer_scoring(text, scorer, expected, correct, parsed):
    result = v.score(text, {"scorer": scorer, "expected": expected})
    assert result["content_check_passed"] is correct
    assert result["parsed_as_required_type"] is parsed
    assert result["raw_content_sha256"] == v.sha(text.encode())
    assert "alpha-7" not in json.dumps(result)


@pytest.fixture
def complete(tmp_path_factory):
    root = tmp_path_factory.mktemp("v")

    def put(relative, value, raw=False):
        data = value if raw else v.encoded(value) + b"\n"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": relative, "size_bytes": len(data), "sha256": v.sha(data)}

    model = {"alias": "synthetic-llama", "entry_path": "artifacts/unread/model.gguf"}
    runtime = {
        "server": {"path": "artifacts/unread/server.exe"},
        "server_args": ["--jinja", "--ctx-size", "4096"],
        "native_chat_template_sha256": "1" * 64,
        "served_chat_template_sha256": "2" * 64,
        "served_chat_template_utf8_bytes": 123,
    }
    server = {"host": "127.0.0.1", "port": 18087}
    v2 = put(v.V2, {"model": model, "runtime": runtime, "server": server})
    proposal = put(
        v.PROPOSAL,
        {
            "frozen": True,
            "execution_authorized": False,
            "current_allowed_calls": 0,
            "tasks": v.TASKS,
            "seeds": [11, 23, 47],
            "generation": v.GENERATION,
            "context_tokens": 4096,
            "sources": {"v2_contract": v2},
        },
    )
    code = put("scripts/run_pa_research_regime_smoke_v1.py", b"synthetic never imported", raw=True)
    doc = put("docs/SYNTHETIC_AUTHORITY.md", b"synthetic authority", raw=True)
    config = {
        "schema_version": v.SCHEMA,
        "frozen": True,
        "execution_authorized": True,
        "purpose": v.PURPOSE,
        "evidence_class": v.EVIDENCE,
        "paper_validity": False,
        "request_ceiling": 6,
        "one_batch_only": True,
        "no_retries": True,
        "tasks": copy.deepcopy(v.TASKS),
        "seeds": [11, 23, 47],
        "generation": dict(v.GENERATION),
        "context_tokens": 4096,
        "paths": {"safe_root": v.SAFE, "private_root": v.PRIVATE},
        "proposal": proposal,
        "v2_contract": v2,
        "model": model,
        "runtime": runtime,
        "server": server,
        "required_code": {"runner": code},
        "sources": [doc],
    }
    contract_sha = put(v.CONFIG, config)["sha256"]
    safe, private = f"{v.SAFE}/{contract_sha}", f"{v.PRIVATE}/{contract_sha}"
    put(
        f"{v.SAFE}/one-batch.reserved.safe.json",
        {
            "contract_sha256": contract_sha,
            "proposal_sha256": proposal["sha256"],
            "request_ceiling": 6,
            "resume_allowed": False,
            "reserved_at": "2026-09-05T15:20:00+00:00",
        },
    )
    put(
        f"{safe}/execution.lock.safe.json",
        {"contract_sha256": contract_sha, "request_ceiling": 6, "resume_allowed": False},
    )
    command = [
        str((root / runtime["server"]["path"]).resolve()),
        "--model",
        str((root / model["entry_path"]).resolve()),
        "--alias",
        model["alias"],
        "--host",
        "127.0.0.1",
        "--port",
        "18087",
        *runtime["server_args"],
    ]
    started = {
        "contract_sha256": contract_sha,
        "epoch": 1,
        "pid": 777,
        "owned_process_only": True,
        "started_at": "2026-09-05T15:20:01+00:00",
        "command_sha256": v.identity(command),
    }
    put(f"{safe}/server-01.started.safe.json", started)
    put(
        f"{safe}/server-01.identity.safe.json",
        {
            **started,
            "served_chat_template_sha256": runtime["served_chat_template_sha256"],
            "props_sha256": "3" * 64,
            "models_sha256": "4" * 64,
        },
    )
    put(
        f"{safe}/server-01.stopped.safe.json",
        {
            "contract_sha256": contract_sha,
            "epoch": 1,
            "pid": 777,
            "owned_process_only": True,
            "returncode": 1,
            "stopped_at": "2026-09-05T15:20:20+00:00",
        },
    )
    tpl = {
        "contract_sha256": contract_sha,
        "epoch": 1,
        "process_id": 777,
        "native_chat_template_sha256": "1" * 64,
        "expected_served_chat_template_sha256": "2" * 64,
        "observed_served_chat_template_sha256": "2" * 64,
        "expected_served_chat_template_utf8_bytes": 123,
        "observed_served_chat_template_utf8_bytes": 123,
        "template_source_available": True,
        "served_template_matches_pin": True,
    }
    put(f"{safe}/server-01.tpl.safe.json", {**started, **tpl})
    put(f"{private}/server-01.log.private.txt", b"synthetic log must never be read", raw=True)
    rows = []
    for ordinal in range(1, 7):
        seed = [11, 11, 23, 23, 47, 47][ordinal - 1]
        task = v.TASKS[(ordinal - 1) % 2]
        request = {
            "model": "synthetic-llama",
            "stream": False,
            "messages": [{"role": "user", "content": task["text"]}],
            **v.GENERATION,
            "seed": seed,
        }
        put(f"{private}/{ordinal:02d}.request.private.json", request)
        content = "42" if ordinal % 2 else "alpha-7"
        reply = {
            "model": "synthetic-llama",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 4, "total_tokens": 34},
        }
        reply_pin = put(f"{private}/{ordinal:02d}.reply.private.json", reply)
        journal = {
            "contract_sha256": contract_sha,
            "proposal_sha256": proposal["sha256"],
            "ordinal": ordinal,
            "seed": seed,
            "epoch": 1,
            "task_id": task["task_id"],
            "fixture_id": task["fixture_id"],
            "process_id": 777,
            "request_sha256": v.identity(request),
            "served_chat_template_sha256": "2" * 64,
            "dispatch_at": f"2026-09-05T15:20:{ordinal * 2:02d}+00:00",
        }
        put(f"{safe}/{ordinal:02d}.dispatch.safe.json", journal)
        put(f"{safe}/{ordinal:02d}.tpl.safe.json", {**tpl, "ordinal": ordinal})
        row = {
            **journal,
            "content_check_passed": True,
            "scorer": task["scorer"],
            "parsed_as_required_type": True,
            "raw_content_sha256": v.sha(content.encode()),
            "normalized_content_sha256": v.identity(
                {"scorer": task["scorer"], "value": task["expected"]}
            ),
            "response_characters": len(content),
            "finish_reason": "stop",
            "not_truncated": True,
            "passed": True,
            "usage": reply["usage"],
            "reply_bytes_sha256": reply_pin["sha256"],
            "request_max_tokens": 512,
            "latency_seconds": 0.5,
            "received_at": f"2026-09-05T15:20:{ordinal * 2 + 1:02d}+00:00",
        }
        put(f"{safe}/{ordinal:02d}.row.safe.json", row)
        rows.append(row)
    put(f"{safe}/result.safe.json", v.expected_summary(config, contract_sha, rows))

    def mutate(relative, change):
        path = root / relative
        value = v.decode(path.read_bytes())
        change(value)
        put(relative, value)

    return {
        "root": root,
        "sha": contract_sha,
        "safe": safe,
        "private": private,
        "config": config,
        "put": put,
        "mutate": mutate,
    }


def test_complete_independently_verified_no_model_or_log_reads(complete, monkeypatch):
    opened = []
    original = Path.read_bytes

    def track(path):
        relative = path.relative_to(complete["root"]).as_posix()
        assert not relative.startswith("artifacts/unread/")
        assert not relative.endswith(".log.private.txt")
        opened.append(relative)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", track)
    output = v.verify(complete["root"], complete["sha"])
    assert output["independent_verification_passed"] and output["smoke_gate_passed"]
    assert output["exact_task_passes"] == 6 and output["verified_template_observations"] == 7
    assert sum(path.startswith(v.PRIVATE) for path in opened) == 12
    assert not output["scientific_target_admitted"] and not output["prior_v2_gate_passed"]
    assert output["new_model_calls"] == 0 and not output["live_process_absence_checked"]
    assert "alpha-7" not in json.dumps(output)


@pytest.mark.parametrize(
    "location,change,code",
    [
        ("01.dispatch.safe.json", lambda x: x.update(seed=17), "DISPATCH_BINDING"),
        ("01.dispatch.safe.json", lambda x: x.update(ordinal=True), "DISPATCH_BINDING"),
        ("01.dispatch.safe.json", lambda x: x.update(process_id=778), "DISPATCH_BINDING"),
        ("01.row.safe.json", lambda x: x.update(request_max_tokens=48), "SAFE_ROW_RECONSTRUCTION"),
        ("01.row.safe.json", lambda x: x.update(latency_seconds=True), "LATENCY_INVALID"),
        (
            "01.row.safe.json",
            lambda x: x.update(received_at="2026-09-05T15:19:00+00:00"),
            "REQUEST_TIME_ORDER",
        ),
        (
            "01.tpl.safe.json",
            lambda x: x.update(observed_served_chat_template_sha256="0" * 64),
            "TEMPLATE_BINDING",
        ),
        ("execution.lock.safe.json", lambda x: x.update(resume_allowed=True), "EXECUTION_LOCK"),
        (
            "server-01.started.safe.json",
            lambda x: x.update(command_sha256="0" * 64),
            "COMMAND_IDENTITY",
        ),
        ("server-01.stopped.safe.json", lambda x: x.update(pid=778), "EPOCH_BINDING"),
        (
            "server-01.stopped.safe.json",
            lambda x: x.update(returncode=False),
            "NO_STOP_RETURN_CODE",
        ),
        (
            "server-01.stopped.safe.json",
            lambda x: x.update(stopped_at="2026-09-05T15:19:59+00:00"),
            "EPOCH_TIME_ORDER",
        ),
        (
            "result.safe.json",
            lambda x: x.update(scientific_target_admitted=True),
            "RESULT_RECONSTRUCTION",
        ),
    ],
)
def test_tampered_safe_bindings_rejected(complete, location, change, code):
    complete["mutate"](f"{complete['safe']}/{location}", change)
    with pytest.raises(v.VerificationError, match=code):
        v.verify(complete["root"], complete["sha"])


@pytest.mark.parametrize(
    "suffix,change,code",
    [
        ("request", lambda x: x.update(seed=17), "PRIVATE_REQUEST_BINDING"),
        ("request", lambda x: x.update(max_tokens=48), "PRIVATE_REQUEST_BINDING"),
        ("reply", lambda x: x.update(model="wrong"), "REPLY_MODEL_OR_SHAPE"),
        (
            "reply",
            lambda x: x["choices"][0]["message"].update(content="142"),
            "SAFE_ROW_RECONSTRUCTION",
        ),
        (
            "reply",
            lambda x: x["usage"].update(completion_tokens=513, total_tokens=543),
            "USAGE_BOUNDS",
        ),
        ("reply", lambda x: x["usage"].update(total_tokens=1), "USAGE_SUM"),
        (
            "reply",
            lambda x: x["choices"][0]["message"].update(reasoning_content="hidden"),
            "NONANSWER_CHANNEL",
        ),
    ],
)
def test_private_receipt_mutations_rejected(complete, suffix, change, code):
    complete["mutate"](f"{complete['private']}/01.{suffix}.private.json", change)
    with pytest.raises(v.VerificationError, match=code):
        v.verify(complete["root"], complete["sha"])


def test_extra_seventh_dispatch_is_not_ignored(complete):
    complete["put"](f"{complete['safe']}/07.dispatch.safe.json", {})
    with pytest.raises(v.VerificationError, match="UNEXPECTED_OR_INCOMPLETE_SAFE_SET"):
        v.verify(complete["root"], complete["sha"])


def test_reservation_proposal_binding(complete):
    complete["mutate"](
        f"{v.SAFE}/one-batch.reserved.safe.json", lambda x: x.update(proposal_sha256="0" * 64)
    )
    with pytest.raises(v.VerificationError, match="BATCH_RESERVATION"):
        v.verify(complete["root"], complete["sha"])


def test_truthful_failed_result_is_verified_not_promoted(complete):
    relative = f"{complete['private']}/01.reply.private.json"
    complete["mutate"](relative, lambda x: x["choices"][0]["message"].update(content="142"))
    raw = (complete["root"] / relative).read_bytes()
    measured = v.reply(raw, v.plan(complete["config"])[0], "synthetic-llama")
    complete["mutate"](f"{complete['safe']}/01.row.safe.json", lambda x: x.update(measured))
    rows = [
        v.decode((complete["root"] / f"{complete['safe']}/{n:02d}.row.safe.json").read_bytes())
        for n in range(1, 7)
    ]
    complete["put"](
        f"{complete['safe']}/result.safe.json",
        v.expected_summary(complete["config"], complete["sha"], rows),
    )
    output = v.verify(complete["root"], complete["sha"])
    assert output["independent_verification_passed"] and not output["smoke_gate_passed"]
    assert output["exact_task_passes"] == 5 and output["pass_denominator"] == 6


def test_no_runner_import_process_network_or_write_api():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
        if isinstance(node, ast.Attribute):
            assert node.attr not in {
                "write_bytes",
                "write_text",
                "mkdir",
                "Popen",
                "run",
                "connect",
                "request",
                "urlopen",
            }
    assert imports <= {
        "__future__",
        "argparse",
        "hashlib",
        "json",
        "math",
        "re",
        "datetime",
        "pathlib",
    }
