"""Offline tests only: no model artifacts, subprocesses, or network requests."""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from jbspan import objective_repair as core
from jbspan import rescue_guidedeval_development as support

SPEC = importlib.util.spec_from_file_location(
    "objective_runner_v3",
    Path(__file__).resolve().parents[1] / "scripts/run_rescue_objective_repair_v3.py",
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def config():
    return {
        "decoding": {
            "seed": 11,
            "temperature": 0,
            "max_tokens": 128,
            "top_k": 1,
            "top_p": 1,
            "min_p": 0,
            "repeat_penalty": 1,
        },
        "models": [{"model_id": name, "alias": f"alias-{name}"} for name in ("one", "two")],
        "runtime": {"port": 18881},
        "limits": {
            "per_request_seconds": 90,
            "max_request_utf8_bytes": 100000,
            "max_reply_utf8_bytes": 1000000,
            "maximum_unique_requests": 304,
        },
    }


def reply(text='{"answer":"maple"}', *, alias="alias-one", finish="stop", **metadata):
    return {
        "model": alias,
        "choices": [
            {"finish_reason": finish, "message": {"role": "assistant", "content": text, **metadata}}
        ],
        "usage": {"completion_tokens": 7},
    }


def fabricated_screen(config, *, status="eligible"):
    rows = runner.public_plan(runner.screen_plan(config, core.build_cases()))
    for row in rows:
        row["status"] = "INCORRECT" if row["condition"] == "UNEDITED" else "CORRECT"
        if status == "ineligible":
            row["status"] = "CORRECT"
    return {"rows": rows}


def test_screen_preserves_all_logical_rows_and_explicit_decoding(config):
    plan = runner.screen_plan(config, core.build_cases())
    assert len(plan) == 64
    assert len({r["row_id"] for r in plan}) == 64
    assert len({r["execution_key"] for r in plan}) < 64
    for row in plan:
        assert [m["role"] for m in row["request"]["messages"]] == ["system", "user"]
        assert all(row["request"][k] == v for k, v in config["decoding"].items())
    support.content_free(runner.public_plan(plan))


def test_exact_selects_first_eligible_in_each_task_family_and_preserves_256_rows(config):
    plan, selected = runner.exact_plan(config, core.build_cases(), fabricated_screen(config))
    assert selected == {
        m: ["lookup__format_conflict__0", "sort__format_conflict__0"] for m in ("one", "two")
    }
    assert len(plan) == 256
    assert len({r["row_id"] for r in plan}) == 256
    all_rows = runner.screen_plan(config, core.build_cases()) + plan
    assert len({r["execution_key"] for r in all_rows}) <= 304
    for model in config["models"]:
        for case_id in selected[model["model_id"]]:
            zeros = [
                r
                for r in plan
                if r["model_id"] == model["model_id"]
                and r["case_id"] == case_id
                and r["removed_mask"] == 0
            ]
            assert len(zeros) == 2 and zeros[0]["execution_key"] == zeros[1]["execution_key"]


def test_eligibility_unknown_excludes_and_does_not_fill_other_family(config):
    screen = fabricated_screen(config)
    for row in screen["rows"]:
        if row["case_id"].startswith("lookup") and row["condition"] == "CLEAN":
            row["status"] = "UNKNOWN"
    plan, selected = runner.exact_plan(config, core.build_cases(), screen)
    assert all(ids == ["sort__format_conflict__0"] for ids in selected.values())
    assert len(plan) == 128


def test_no_eligible_case_is_a_zero_call_exact_plan(config):
    plan, selected = runner.exact_plan(
        config, core.build_cases(), fabricated_screen(config, status="ineligible")
    )
    assert plan == [] and selected == {"one": [], "two": []}


def test_incomplete_or_request_mismatched_screen_rejected(config):
    screen = fabricated_screen(config)
    screen["rows"][0]["request_sha256"] = "different"
    with pytest.raises(ValueError, match="frozen request"):
        runner.select_eligible(config, core.build_cases(), screen)
    screen["rows"].pop()
    with pytest.raises(ValueError, match="64"):
        runner.select_eligible(config, core.build_cases(), screen)


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"answer":"maple"}', "CORRECT"),
        ('{"answer":"otter"}', "INCORRECT"),
        ("I cannot complete this task.", "INCORRECT"),
        ('```json\n{"answer":"maple"}\n```', "INCORRECT"),
        ('{"answer":"maple","answer":"maple"}', "INCORRECT"),
        ("", "INCORRECT"),
    ],
)
def test_objective_reply_scores_completed_text_without_semantic_repair(text, expected):
    result = runner.parse_reply(reply(text), {"alias": "alias-one"}, "maple")
    assert result["status"] == expected and result["error_code"] is None
    support.content_free(result)


@pytest.mark.parametrize("text", [None, ""])
def test_completed_refusal_metadata_is_incorrect_not_unknown(text):
    result = runner.parse_reply(
        reply(text, refusal="Cannot comply."), {"alias": "alias-one"}, "maple"
    )
    assert result["status"] == "INCORRECT"
    assert result["score_reason"] == "COMPLETED_REFUSAL"


@pytest.mark.parametrize(
    "value,error",
    [
        (reply(finish="length"), "NONSTOP_OR_TRUNCATED_OUTPUT"),
        (reply(alias="unrequested"), "RETURNED_MODEL_MISMATCH"),
        (reply(tool_calls=[{"id": "x"}]), "UNEXPECTED_TOOL_OUTPUT"),
        (reply(reasoning_content="private reasoning"), "UNEXPECTED_SEPARATE_REASONING"),
        (reply(None), "MALFORMED_REPLY"),
        ({"model": "alias-one", "choices": []}, "MALFORMED_REPLY"),
    ],
)
def test_protocol_uncertainty_is_preserved(value, error):
    result = runner.parse_reply(value, {"alias": "alias-one"}, "maple")
    assert result["status"] == "UNKNOWN" and result["error_code"] == error


def test_durable_checkpoint_reuses_identical_requests_and_keeps_raw_private(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    calls = []

    def send(endpoint, request):
        calls.append(request)
        return reply('{"answer":"' + row["expected_answer"] + '"}')

    first = runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row, send=send)
    second = runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row, send=send)
    assert first == second and len(calls) == 1
    assert first["status"] == "CORRECT" and first["private_receipt_sha256"]
    stored = support.read_object(next(tmp_path.glob("*.reply.private.json")))
    assert stored["raw_reply"] == reply('{"answer":"' + row["expected_answer"] + '"}')
    assert "raw_reply" not in first


def test_caught_transport_failure_is_unknown_and_never_retried(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    calls = []

    def fail(endpoint, request):
        calls.append(request)
        raise support.TransportFailure("private provider detail")

    first = runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row, send=fail)
    second = runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row, send=fail)
    assert first == second and len(calls) == 1
    assert first["status"] == "UNKNOWN"
    assert first["error_code"] == "TRANSPORT_UNCERTAIN_NO_RETRY"
    assert "private provider detail" not in str(first)


def test_torn_or_unfinished_dispatch_blocks_resend(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    pending = tmp_path / f"{row['execution_key']}.pending.safe.json"
    pending.write_bytes(b"torn")

    def forbidden(*args):
        pytest.fail("unfinished request was resent")

    with pytest.raises(support.TransportFailure, match="NO_AUTOMATIC_RETRY"):
        runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row, send=forbidden)


def test_receipt_or_expectation_mutation_is_rejected(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    runner.evaluate_once(
        tmp_path, "contract", config, config["models"][0], row, send=lambda *_: reply()
    )
    changed = {**row, "expected_answer_sha256": "other"}
    with pytest.raises(ValueError, match="identity"):
        runner.evaluate_once(tmp_path, "contract", config, config["models"][0], changed)


def test_request_byte_limit_is_checked_before_pending_or_send(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    config["limits"]["max_request_utf8_bytes"] = 1
    with pytest.raises(ValueError, match="byte bound"):
        runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row)
    assert not list(tmp_path.iterdir())


def test_budget_checked_before_new_pending_or_send(tmp_path, config):
    row = runner.screen_plan(config, core.build_cases())[0]
    config["limits"]["maximum_unique_requests"] = 0
    with pytest.raises(RuntimeError, match="ceiling"):
        runner.evaluate_once(tmp_path, "contract", config, config["models"][0], row)
    assert not list(tmp_path.iterdir())


def orchestration_setup(tmp_path, monkeypatch, config):
    config["recording"] = {"safe_base": "data/safe", "private_base": "artifacts/private"}
    config["runtime"].update({"server": {"path": "runtime/server.exe"}, "startup_seconds": 90})
    config["limits"].update({"screen_seconds": 1200, "exact_seconds": 2400})
    for model in config["models"]:
        model.update({"model": {"path": f"models/{model['model_id']}.gguf"}, "server_args": []})
    monkeypatch.setattr(runner, "verify_config", lambda *_: (config, core.build_cases()))
    monkeypatch.setattr(runner, "verify_execution_files", lambda *_: None)
    events = []

    @contextmanager
    def owned(command, port, alias, timeout):
        events.append(("started", alias))
        try:
            yield SimpleNamespace(pid=123)
        finally:
            events.append(("stopped", alias))

    lifecycle = SimpleNamespace(
        owned_server=owned,
        disable_process_proxies=lambda: None,
        local_json=lambda *_: {"chat_template": "fixture-only"},
    )
    monkeypatch.setattr(runner, "lifecycle_module", lambda *_: lifecycle)
    return events


def test_static_preflight_does_not_touch_execution_files_or_launch(tmp_path, monkeypatch, config):
    orchestration_setup(tmp_path, monkeypatch, config)

    def forbidden(*args):
        pytest.fail("preflight crossed into execution")

    monkeypatch.setattr(runner, "verify_execution_files", forbidden)
    monkeypatch.setattr(runner, "lifecycle_module", forbidden)
    result = runner.run(tmp_path, "config.json", "contract", "screen", execute=False)
    assert result["logical_rows"] == 64
    assert result["model_files_read"] is False and result["network_calls"] == 0
    assert list(tmp_path.iterdir()) == []


def test_mock_full_phases_preserve_rows_cache_and_stop_each_owned_server(
    tmp_path, monkeypatch, config
):
    events = orchestration_setup(tmp_path, monkeypatch, config)
    answers = {}
    for row in runner.screen_plan(config, core.build_cases()):
        answers[row["request_sha256"]] = (
            "wrong" if row["condition"] == "UNEDITED" else row["expected_answer"]
        )
    calls = []

    def send(endpoint, request):
        key = support.digest(request)
        calls.append(key)
        return reply('{"answer":"' + answers[key] + '"}', alias=request["model"])

    monkeypatch.setattr(support, "transport", send)
    screen = runner.run(tmp_path, "config.json", "contract", "screen", execute=True)
    assert screen["logical_rows"] == 64 and screen["complete"] is True
    assert len(events) == 4 and events[0][0] == "started" and events[1][0] == "stopped"
    exact_plan, _ = runner.exact_plan(config, core.build_cases(), screen)
    for row in exact_plan:
        answers.setdefault(row["request_sha256"], row["expected_answer"])
    exact = runner.run(tmp_path, "config.json", "contract", "exact", execute=True)
    assert exact["logical_rows"] == 256 and exact["complete"] is True
    assert len(calls) == len(set(calls)) == exact["total_journaled_unique_requests"] <= 304
    assert len(events) == 8 and all(events[i][0] == "stopped" for i in (1, 3, 5, 7))
    assert all(row["private_receipt_sha256"] for row in exact["rows"])
    cached = runner.run(tmp_path, "config.json", "contract", "exact", execute=True)
    assert cached == exact and len(events) == 8


def test_model_mismatch_is_journaled_stops_owned_server_and_blocks_resume(
    tmp_path, monkeypatch, config
):
    events = orchestration_setup(tmp_path, monkeypatch, config)
    calls = []

    def mismatched(endpoint, request):
        calls.append(request)
        return reply(alias="wrong-snapshot")

    monkeypatch.setattr(support, "transport", mismatched)
    with pytest.raises(RuntimeError, match="model mismatch"):
        runner.run(tmp_path, "config.json", "contract", "screen", execute=True)
    assert len(calls) == 1 and [e[0] for e in events] == ["started", "stopped"]
    with pytest.raises(RuntimeError, match="model mismatch"):
        runner.run(tmp_path, "config.json", "contract", "screen", execute=True)
    assert len(calls) == 1 and len(events) == 2


def test_exact_cannot_run_without_completed_screen(tmp_path, monkeypatch, config):
    events = orchestration_setup(tmp_path, monkeypatch, config)
    with pytest.raises(FileNotFoundError):
        runner.run(tmp_path, "config.json", "contract", "exact", execute=True)
    assert events == []
