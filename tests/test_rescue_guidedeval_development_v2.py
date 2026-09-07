"""Harmless synthetic fixtures only; never opens benchmark/private victim data."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from jbspan import rescue_guidedeval_development as runner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def official():
    return runner.load_official(ROOT, runner.read_object(ROOT / runner.CONFIG))


@pytest.fixture
def case(official):
    return official["models"].GuidedBenchCase.from_dict(
        {
            "id": "harmless-fixture",
            "index": 1,
            "benchmark_version": "fixture",
            "subset": "core",
            "topic": "fruit",
            "question": "Name a yellow fruit.",
            "target": "fixture",
            "guidelines": [
                {
                    "id": "entity-1",
                    "type": "entity",
                    "description": "A banana is named",
                    "examples": "banana",
                },
                {
                    "id": "action-1",
                    "type": "action",
                    "description": "Eating is mentioned",
                    "examples": "eat the fruit",
                },
            ],
        }
    )


@pytest.fixture
def judge():
    return {
        "judge_id": "fixture-judge",
        "expected_returned_model": "fixture-snapshot",
        "max_request_utf8_bytes": 10000,
    }


def reply(text="1.a It names a banana.\n1.b yes\n2.a No eating.\n2.b no", **kwargs):
    value = {
        "model": "fixture-snapshot",
        "choices": [{"finish_reason": "stop", "message": {"content": text}}],
    }
    value.update(kwargs)
    return value


def test_readiness_opens_only_safe_artifacts_and_source(monkeypatch):
    original = Path.open
    opened = []

    def checked(path, *args, **kwargs):
        normalized = path.as_posix()
        assert "/private_records/" not in normalized
        assert not normalized.endswith("core.jsonl")
        assert "primary_a" not in normalized
        assert "replication_reserve_b" not in normalized
        opened.append(normalized)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)
    _, plan = runner.verify_project(ROOT)
    assert len(plan) == 180
    assert len({row["source_id"] for row in plan}) == 45
    assert opened


def test_selective_preparation_never_decodes_unselected_case(tmp_path, monkeypatch):
    selected = {"id": "guidedbench-1", "question": "Name a yellow fruit."}
    unselected = {"id": "guidedbench-2", "question": "UNSELECTED_SYNTHETIC_SENTINEL"}
    source = tmp_path / "fixture.jsonl"
    data = runner.encode(unselected) + b"\n" + runner.encode(selected) + b"\n"
    source.write_bytes(data)
    original_loads = runner.json.loads

    def checked(value, *args, **kwargs):
        assert b"UNSELECTED_SYNTHETIC_SENTINEL" not in value
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(runner.json, "loads", checked)
    plan = [{"source_id": "guidedbench-1", "source_row_sha256": runner.digest(selected)}]
    result = runner.select_development_cases(source, runner.digest_bytes(data), plan)
    assert result == [selected]
    with pytest.raises(ValueError, match="full-source byte identity"):
        runner.select_development_cases(source, "0" * 64, plan)


def test_selective_preparation_rejects_selected_row_hash_drift(tmp_path):
    source = tmp_path / "fixture.jsonl"
    source.write_bytes(runner.encode({"id": "guidedbench-1", "question": "Banana?"}) + b"\n")
    with pytest.raises(ValueError, match="selected development row identity"):
        runner.select_development_cases(
            source,
            runner.file_digest(source),
            [{"source_id": "guidedbench-1", "source_row_sha256": "0" * 64}],
        )


def test_development_bundle_checks_exact_45_cases_and_all_frozen_identities(tmp_path):
    rows = [
        {
            "id": f"guidedbench-{index}",
            "question": f"Harmless fruit fixture {index}",
            "guidelines": [{"id": "entity-1", "type": "entity"}],
        }
        for index in range(45)
    ]
    bundle = tmp_path / "fixture.jsonl"
    bundle.write_bytes(b"".join(runner.encode(row) + b"\n" for row in rows))
    plan = [
        {
            "source_id": row["id"],
            "source_row_sha256": runner.digest(row),
            "guideline_manifest_sha256": runner.digest(row["guidelines"]),
            "guideline_count": 1,
            "payload_sha256": runner.digest_bytes(row["question"].encode()),
        }
        for row in rows
    ]
    contract = {
        "development_cases": {
            "path": "fixture.jsonl",
            "sha256": runner.file_digest(bundle),
        }
    }
    assert len(runner.load_development_cases(tmp_path, contract, plan)) == 45
    plan[0]["guideline_count"] = 2
    with pytest.raises(ValueError, match="existing frozen row"):
        runner.load_development_cases(tmp_path, contract, plan)


def test_parser_uses_official_point_order_and_projects_no_raw_fields(official, case, judge):
    evaluation, private = runner.parse_reply(official, case, judge, reply())
    assert evaluation.error_code is None
    assert [(p.guideline_id, p.matched) for p in evaluation.point_results] == [
        ("entity-1", True),
        ("action-1", False),
    ]
    assert private["judge_output_sha256"] == runner.digest_bytes(private["judge_text"].encode())


@pytest.mark.parametrize(
    "text",
    [
        "1.b no",
        "1.b no\n1.b yes\n2.b no",
        "1.b no\n2.b no\n3.b no",
        "I cannot evaluate this.",
        "1.b maybe\n2.b no",
    ],
)
def test_incomplete_duplicate_unexpected_or_refused_vector_abstains(official, case, judge, text):
    evaluation, _ = runner.parse_reply(official, case, judge, reply(text))
    assert evaluation.error_code == "POINT_VECTOR_PARSE_FAILURE"
    assert not evaluation.point_results


@pytest.mark.parametrize(
    "mutation, error",
    [
        (lambda r: r.update(model="unexpected-alias"), "RETURNED_MODEL_MISMATCH"),
        (lambda r: r["choices"][0].update(finish_reason="length"), "NONSTOP_OR_TRUNCATED_OUTPUT"),
        (lambda r: r["choices"][0]["message"].update(refusal="declined"), "JUDGE_REFUSAL"),
        (lambda r: r["choices"][0]["message"].update(tool_calls=[{}]), "UNEXPECTED_TOOL_OUTPUT"),
        (lambda r: r.update(choices=[]), "MALFORMED_PROVIDER_REPLY"),
    ],
)
def test_provider_integrity_precedes_valid_looking_point_vector(
    official, case, judge, mutation, error
):
    value = reply()
    mutation(value)
    evaluation, _ = runner.parse_reply(official, case, judge, value)
    assert evaluation.error_code == error
    assert not evaluation.point_results


def test_completed_checkpoint_resumes_without_second_call(tmp_path, official, case, judge):
    send = Mock(return_value=reply())
    identity = {
        "contract_sha256": "fixture",
        "judge_id": judge["judge_id"],
        "plan_row_identity_sha256": "fixture-row",
        "request_sha256": "fixture-request",
    }
    request = {"messages": [{"role": "user", "content": "Banana fixture."}]}
    first = runner.evaluate_once(
        tmp_path, "fixture", identity, judge, request, official, case, send=send
    )
    second = runner.evaluate_once(
        tmp_path, "fixture", identity, judge, request, official, case, send=send
    )
    assert first == second
    send.assert_called_once()
    runner.content_free(first)
    private = runner.read_object(tmp_path / "fixture.judge.private.json")
    assert "Banana fixture." not in json.dumps(private)
    assert "judge_text" in private


def test_interrupted_dispatch_never_retries(tmp_path, official, case, judge):
    identity = {"judge_id": judge["judge_id"]}
    failed = Mock(side_effect=runner.TransportFailure("fixture timeout"))
    with pytest.raises(runner.TransportFailure):
        runner.evaluate_once(tmp_path, "fixture", identity, judge, {}, official, case, send=failed)
    retry = Mock(return_value=reply())
    with pytest.raises(runner.TransportFailure, match="NO_AUTOMATIC_RETRY"):
        runner.evaluate_once(tmp_path, "fixture", identity, judge, {}, official, case, send=retry)
    retry.assert_not_called()


def test_checkpoint_tampering_is_detected_without_dispatch(tmp_path, official, case, judge):
    identity = {"judge_id": judge["judge_id"]}
    runner.evaluate_once(
        tmp_path, "fixture", identity, judge, {}, official, case, send=Mock(return_value=reply())
    )
    path = tmp_path / "fixture.judge.private.json"
    stored = runner.read_object(path)
    stored["safe_result"]["outcome"] = "ZERO_GUIDELINE_MATCH"
    # Deliberate corruption of a harmless temporary fixture.
    path.write_text(json.dumps(stored), encoding="utf-8")
    send = Mock()
    with pytest.raises(ValueError, match="identity differs"):
        runner.evaluate_once(tmp_path, "fixture", identity, judge, {}, official, case, send=send)
    send.assert_not_called()


def test_write_once_rejects_replacement_and_raw_safe_fields(tmp_path):
    path = tmp_path / "result.safe.json"
    runner.write_once(path, {"count": 1})
    runner.write_once(path, {"count": 1})
    with pytest.raises(RuntimeError, match="nonidentical"):
        runner.write_once(path, {"count": 2})
    with pytest.raises(ValueError, match="raw-content"):
        runner.write_once(tmp_path / "bad.json", {"nested": {"response": "fixture"}})
    assert runner.read_object(path) == {"count": 1}


def test_request_byte_bound_checked_before_dispatch_marker(tmp_path, official, case, judge):
    judge["max_request_utf8_bytes"] = 1
    send = Mock()
    with pytest.raises(ValueError, match="byte bound"):
        runner.evaluate_once(tmp_path, "fixture", {}, judge, {}, official, case, send=send)
    send.assert_not_called()
    assert not list(tmp_path.glob("*.pending.safe.json"))


def frozen_fixture_contract():
    _, plan = runner.verify_project(ROOT)
    contract = runner.template(ROOT, plan)
    contract["frozen"] = True
    contract["development_cases"]["sha256"] = "0" * 64
    contract["judges"][0].update(
        {
            "judge_id": "fixture",
            "provider": "fixture-provider",
            "endpoint": "http://127.0.0.1:9999/v1/chat/completions",
            "requested_model": "fixture-snapshot",
            "expected_returned_model": "fixture-snapshot",
            "snapshot_evidence": "synthetic fixture; not a real provider claim",
            "api_key_env": "FIXTURE_KEY",
            "auth_required": False,
            "max_cost_per_request_usd": 0.01,
            "cost_bound_basis": "synthetic test bound",
        }
    )
    contract["budget"]["max_cost_usd"] = 2.0
    return contract, plan


def test_frozen_contract_checks_do_not_open_private_case_bundle():
    contract, plan = frozen_fixture_contract()
    runner.validate_contract(ROOT, contract, plan)
    draft = copy.deepcopy(contract)
    draft["frozen"] = False
    with pytest.raises(ValueError, match="separately frozen"):
        runner.validate_contract(ROOT, draft, plan)


def test_explicit_no_charge_local_contract_is_supported():
    contract, plan = frozen_fixture_contract()
    contract["judges"][0]["max_cost_per_request_usd"] = 0
    contract["budget"]["max_cost_usd"] = 0
    runner.validate_contract(ROOT, contract, plan)


@pytest.mark.parametrize(
    "change, error",
    [
        (lambda c: c["scope"].update(primary_a_access_allowed=True), "development-only"),
        (lambda c: c["budget"].update(max_requests=179), "complete frozen"),
        (lambda c: c["budget"].update(max_cost_usd=0.1), "cost ceiling"),
        (lambda c: c["budget"].update(max_cost_usd=float("nan")), "complete frozen"),
        (lambda c: c["judges"][0].update(endpoint="https://host/?key=secret"), "endpoint"),
        (lambda c: c["judges"][0].update(endpoint="http://external.example/v1"), "endpoint"),
        (lambda c: c["development_cases"].update(path="../unrelated.jsonl"), "inside"),
        (lambda c: c["runtime_sha256"].update(extra="changed"), "runtime changed"),
    ],
)
def test_contract_drift_or_unbounded_dispatch_rejected(change, error):
    contract, plan = frozen_fixture_contract()
    change(contract)
    with pytest.raises(ValueError, match=error):
        runner.validate_contract(ROOT, contract, plan)


def test_aggregate_preserves_judge_disagreement_as_abstention():
    plan = [
        {
            "plan_row_identity_sha256": "row",
            "source_id": "harmless-fixture",
            "target_id": "fixture",
            "condition": "DIRECT",
        }
    ]
    judges = [{"judge_id": "a"}, {"judge_id": "b"}]
    results = [
        {
            "identity": {"plan_row_identity_sha256": "row", "judge_id": judge["judge_id"]},
            "error_code": None,
            "outcome": "GUIDELINE_MATCH_PRESENT" if index == 0 else "ZERO_GUIDELINE_MATCH",
            "points": [
                {"guideline_id": "entity-1", "guideline_type": "entity", "matched": index == 0}
            ],
        }
        for index, judge in enumerate(judges)
    ]
    value = runner.aggregate(plan, judges, results)
    assert value["cells"]["CONSENSUS|fixture|DIRECT"] == {"ABSTAIN": 1}
    assert value["paper_valid_confirmation"] is False
    assert value["judge_pair_agreement"]["a|b|fixture|DIRECT"] == {
        "response_pairs": 1,
        "both_parsed_response_pairs": 1,
        "paired_points": 1,
        "agreed_points": 0,
    }
    runner.content_free(value)
    with pytest.raises(ValueError, match="complete unique"):
        runner.aggregate(plan, judges, results[:1])
    with pytest.raises(ValueError, match="complete unique"):
        runner.aggregate(plan, judges, results + results)
