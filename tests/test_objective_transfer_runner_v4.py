"""Harmless offline V4 plan, identity and lifecycle tests; never load real models."""

from __future__ import annotations

import copy
import importlib.util
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from jbspan import objective_transfer as core
from jbspan import rescue_guidedeval_development as support

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "transfer_runner_v4", ROOT / "scripts/run_rescue_objective_transfer_v4.py"
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def config():
    value = copy.deepcopy(support.read_object(ROOT / runner.REFERENCE_CONFIG))
    value.update(
        {
            "schema_version": runner.SCHEMA,
            "reference_v3": {"path": runner.REFERENCE_CONFIG, "sha256": runner.REFERENCE_SHA256},
            "case_manifest_sha256": support.digest(core.build_cases()),
            "strata_manifest_sha256": support.digest(core.build_strata()),
            "recording": {
                "safe_base": "data/natural_language_localization/v4_fixture",
                "private_base": "artifacts/v4_fixture",
            },
        }
    )
    value["limits"].update({"maximum_unique_requests": 1120, "validation_seconds": 3600})
    return value


@pytest.fixture
def helper():
    return runner.frozen_runner(ROOT)


def build(config, helper):
    return runner.build_plan(config, core.build_cases(), core.build_strata(), helper)


def test_reference_requires_exact_protocol_and_every_existing_dependency(config):
    runner.verify_reference(ROOT, config)
    changed = copy.deepcopy(config)
    changed["decoding"]["seed"] = 12
    with pytest.raises(ValueError, match="protocol"):
        runner.verify_reference(ROOT, changed)
    changed = copy.deepcopy(config)
    changed["models"][0]["server_args"].remove("--jinja")
    with pytest.raises(ValueError, match="protocol"):
        runner.verify_reference(ROOT, changed)
    changed = copy.deepcopy(config)
    changed["dependencies"].pop("code_0")
    with pytest.raises(ValueError, match="dependency"):
        runner.verify_reference(ROOT, changed)


def test_complete_frame_1280_views_1120_requests_64_problems(config, helper):
    plan = build(config, helper)
    runner.verify_plan(plan, config)
    assert runner.frame_counts(plan) == {
        "task_data_units": 64,
        "model_task_data_units": 128,
        "stratum_task_data_units": 160,
    }
    logical = Counter(row["stratum_id"] for row in plan)
    assert logical == {
        "qwen_lookup_18": 256,
        "qwen_sort_13": 384,
        "qwen_sort_24": 256,
        "gemma_lookup_2": 192,
        "gemma_sort_2": 192,
    }
    by_model_family = {}
    for model, family in {(r["model_id"], r["task_family"]) for r in plan}:
        by_model_family[(model, family)] = len(
            {
                r["execution_key"]
                for r in plan
                if (r["model_id"], r["task_family"]) == (model, family)
            }
        )
    assert by_model_family == {
        (core.QWEN, "lookup"): 256,
        (core.QWEN, "sort"): 480,
        (core.GEMMA, "lookup"): 192,
        (core.GEMMA, "sort"): 192,
    }
    assert len({row["row_id"] for row in plan}) == 1280
    assert len({row["execution_key"] for row in plan}) == 1120
    support.content_free(runner.public_plan(plan))


def test_each_stratum_has_full_source_subsets_target_and_all_controls(config, helper):
    plan = build(config, helper)
    for stratum in core.build_strata():
        frame = [r for r in plan if r["stratum_id"] == stratum["stratum_id"]]
        assert len({r["task_data_id"] for r in frame}) == 32
        for task_id in {r["task_data_id"] for r in frame}:
            group = [r for r in frame if r["task_data_id"] == task_id]
            source = [r for r in group if r["query_role"].startswith("SOURCE_")]
            witness = stratum["witness_mask"]
            assert {r["removed_mask"] for r in source} == {
                mask for mask in range(32) if mask & witness == mask
            }
            assert all(r["operator"] == "LAYOUT_BLANK" for r in source)
            roles = Counter(r["query_role"] for r in group)
            assert all(
                roles[r] == 1
                for r in ("SOURCE_WITNESS", "TARGET_WITNESS", "CLEAN", "ALL_BLANK", "ALIGNED")
            )
            target = next(r for r in group if r["query_role"] == "TARGET_WITNESS")
            assert target["operator"] == "SOURCE_OMIT" and target["removed_mask"] == witness


def test_shared_qwen_sort_views_reuse_requests_without_aliasing_rows(config, helper):
    plan = build(config, helper)
    multiplicities = Counter(row["execution_key"] for row in plan)
    assert Counter(multiplicities.values()) == {1: 960, 2: 160}
    duplicates = {key for key, count in multiplicities.items() if count == 2}
    assert all(
        row["model_id"] == core.QWEN and row["task_family"] == "sort"
        for row in plan
        if row["execution_key"] in duplicates
    )
    for key in duplicates:
        rows = [row for row in plan if row["execution_key"] == key]
        assert rows[0]["row_id"] != rows[1]["row_id"]
        assert rows[0]["request"] == rows[1]["request"]
        assert rows[0]["expected_answer"] == rows[1]["expected_answer"]


def test_plan_preserves_native_roles_all_decoding_and_never_requests_old_cases(config, helper):
    plan = build(config, helper)
    for row in plan:
        assert row["case_id"].startswith("v4_")
        assert [m["role"] for m in row["request"]["messages"]] == ["system", "user"]
        assert all(row["request"][k] == v for k, v in config["decoding"].items())
        assert "request" not in runner.public_plan([row])[0]


def test_changed_expected_request_or_frame_denominator_is_rejected(config, helper):
    plan = build(config, helper)
    changed = copy.deepcopy(plan)
    changed[0]["expected_answer"] = "other"
    with pytest.raises(ValueError, match="identity"):
        runner.verify_plan(changed, config)
    with pytest.raises(ValueError, match="1,280"):
        runner.verify_plan(plan[:-1], config)


def mocked_execution(monkeypatch, config, helper):
    monkeypatch.setattr(
        runner,
        "verify_config",
        lambda *_: (config, core.build_cases(), core.build_strata(), helper),
    )
    monkeypatch.setattr(helper, "verify_execution_files", lambda *_: None)
    events = []

    @contextmanager
    def owned(command, port, alias, timeout):
        events.append(("start", alias))
        try:
            yield SimpleNamespace(pid=77)
        finally:
            events.append(("stop", alias))

    lifecycle = SimpleNamespace(
        owned_server=owned,
        disable_process_proxies=lambda: None,
        local_json=lambda *_: {"chat_template": "test-only"},
    )
    monkeypatch.setattr(helper, "lifecycle_module", lambda *_: lifecycle)
    return events


def test_static_preflight_has_no_execution_or_filesystem_writes(
    tmp_path, monkeypatch, config, helper
):
    mocked_execution(monkeypatch, config, helper)

    def forbidden(*_):
        pytest.fail("static preflight attempted execution")

    monkeypatch.setattr(helper, "verify_execution_files", forbidden)
    monkeypatch.setattr(helper, "lifecycle_module", forbidden)
    result = runner.run(tmp_path, "config.json", "v4-contract", execute=False)
    assert result["logical_rows"] == 1280 and result["unique_phase_requests"] == 1120
    assert result["network_calls"] == 0 and result["model_files_read"] is False
    assert not list(tmp_path.iterdir())


def reply(value: str, alias: str, *, finish="stop"):
    return {
        "model": alias,
        "choices": [
            {
                "finish_reason": finish,
                "message": {"role": "assistant", "content": '{"answer":"' + value + '"}'},
            }
        ],
        "usage": {"completion_tokens": 6},
    }


def test_full_mock_validation_keeps_all_rows_unknowns_controls_and_1120_receipts(
    tmp_path, monkeypatch, config, helper
):
    events = mocked_execution(monkeypatch, config, helper)
    plan = build(config, helper)
    answers = {row["request_sha256"]: row["expected_answer"] for row in plan}
    roles = {row["request_sha256"]: row["query_role"] for row in plan}
    # A source/target/control mix fails prospectively; no frames are filtered out.
    calls = []

    def send(endpoint, request):
        key = support.digest(request)
        calls.append(key)
        if len(calls) == 2:
            raise support.TransportFailure("test uncertainty")
        answer = "wrong" if roles[key] == "CLEAN" else answers[key]
        return reply(answer, request["model"])

    monkeypatch.setattr(support, "transport", send)
    result = runner.run(tmp_path, "config.json", "v4-contract", execute=True)
    assert result["complete"] is True and result["logical_rows"] == 1280
    assert len(calls) == len(set(calls)) == result["total_journaled_unique_requests"] == 1120
    assert result["counts"]["INCORRECT"] > 0 and result["counts"]["UNKNOWN"] > 0
    assert len(result["stratum_views"]) == 5
    assert all(view["task_data_units"] == 32 for view in result["stratum_views"])
    assert [event[0] for event in events] == ["start", "stop", "start", "stop"]
    assert all(row["private_receipt_sha256"] for row in result["rows"])
    cached = runner.run(tmp_path, "config.json", "v4-contract", execute=True)
    assert cached == result and len(calls) == 1120 and len(events) == 4


def test_pending_dispatch_blocks_resume_before_model_or_server_access(
    tmp_path, monkeypatch, config, helper
):
    events = mocked_execution(monkeypatch, config, helper)
    row = build(config, helper)[0]
    _, private = helper.directories(tmp_path, config, "v4-contract")
    checkpoint = private / "checkpoints" / f"{row['execution_key']}.pending.safe.json"
    support.write_once(checkpoint, helper.request_identity("v4-contract", row))
    with pytest.raises(support.TransportFailure, match="NO_AUTOMATIC_RETRY"):
        runner.run(tmp_path, "config.json", "v4-contract", execute=True)
    assert events == []


def test_wrong_returned_model_stops_then_resume_does_not_resend(
    tmp_path, monkeypatch, config, helper
):
    events = mocked_execution(monkeypatch, config, helper)
    calls = []

    def send(endpoint, request):
        calls.append(request)
        return reply("anything", "different-model")

    monkeypatch.setattr(support, "transport", send)
    with pytest.raises(RuntimeError, match="model mismatch"):
        runner.run(tmp_path, "config.json", "v4-contract", execute=True)
    assert len(calls) == 1 and [event[0] for event in events] == ["start", "stop"]
    with pytest.raises(RuntimeError, match="model mismatch"):
        runner.run(tmp_path, "config.json", "v4-contract", execute=True)
    assert len(calls) == 1 and len(events) == 2


def test_v3_contract_receipt_cannot_be_reused_as_v4(tmp_path, config, helper):
    row = build(config, helper)[0]
    helper.evaluate_once(
        tmp_path,
        runner.REFERENCE_SHA256,
        config,
        config["models"][0],
        row,
        send=lambda _, request: reply(row["expected_answer"], request["model"]),
    )
    with pytest.raises(ValueError, match="identity"):
        helper.evaluate_once(
            tmp_path,
            "v4-contract",
            config,
            config["models"][0],
            row,
            send=lambda *_: pytest.fail("old reply was silently reused"),
        )


def test_helper_refusal_and_truncation_semantics_remain_frozen(helper):
    model = {"alias": "fixture"}
    refused = reply("wrong", "fixture")
    refused["choices"][0]["message"] = {"content": None, "refusal": "Cannot complete."}
    assert helper.parse_reply(refused, model, "right")["score_reason"] == "COMPLETED_REFUSAL"
    assert (
        helper.parse_reply(reply("right", "fixture", finish="length"), model, "right")["status"]
        == "UNKNOWN"
    )
