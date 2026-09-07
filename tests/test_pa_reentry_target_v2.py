"""Invented harmless tiny frames, fake workers, local temporary receipts only."""

import copy
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_reentry_target_v2 as m  # noqa: E402

j = m.j


def stamp(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()


def response(config, *, content="42", prompt_tokens=12, finish="stop"):
    return j.canonical({
        "model": config["model"]["alias"],
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 2,
                  "total_tokens": prompt_tokens + 2},
    })


@pytest.fixture
def engine(tmp_path, monkeypatch):
    config = {
        "_contract_sha256": "d" * 64,
        "model": {"alias": "invented-harmless-target", "entry_path": "runtime/model.gguf"},
        "runtime": {
            "server": {"path": "runtime/server.exe"}, "server_args": [],
            "native_chat_template_sha256": "a" * 64,
            "served_chat_template_sha256": "b" * 64,
            "served_chat_template_utf8_bytes": 12,
        },
        "server": {"host": "127.0.0.1", "port": 18087, "request_timeout_seconds": 240},
        "execution_limits": {"deadline_utc": "2026-09-05T22:55:47+00:00"},
    }
    generation = {
        "science": {"max_tokens": 512, "temperature": 0.7, "top_p": 0.9,
                    "top_k": 50, "min_p": 0.0, "repeat_penalty": 1.0},
        "control": {"max_tokens": 48, "temperature": 0, "top_p": 1,
                    "top_k": 1, "min_p": 0, "repeat_penalty": 1},
    }
    requests = []
    for ordinal, (kind, seed) in enumerate(
        (("science", 11), ("science", 23), ("control", 17), ("science", 47)), 1
    ):
        requests.append({
            "ordinal": ordinal, "request_id": j.digest(["invented", ordinal]),
            "kind": kind, "seed": seed, "materialization_id": j.digest(kind),
            "generation": {**generation[kind], "seed": seed}, "payload_position": 3,
            "mask": 1, "operator": "SOURCE_AWARE_OMIT",
            "task_id": "arithmetic" if kind == "control" else None,
            "panel_evaluation_required": kind == "science",
        })
    plan = {"plan_identity_sha256": "f" * 64, "requests": requests}
    old_rows = [{**requests[0], "received_at": stamp(-30)}]
    prompts = {j.digest("science"): "Harmless synthetic explanation of addition.",
               j.digest("control"): "What is 6 times 7?"}
    census = {"rows": [{"materialization_id": mid, "native_prompt_tokens": 12}
                       for mid in prompts]}
    monkeypatch.setattr(m, "ORIGINAL", config["_contract_sha256"])
    monkeypatch.setattr(m, "PLAN", plan["plan_identity_sha256"])
    monkeypatch.setattr(m, "PREFIX_COUNT", 1)
    monkeypatch.setattr(m, "TOTAL", 4)
    monkeypatch.setattr(m, "PREFIX_ROWS", j.digest(old_rows))
    monkeypatch.setattr(m, "SUFFIX", j.digest(requests[1:]))
    monkeypatch.setattr(m, "SUFFIX_IDS", j.digest([item["request_id"] for item in requests[1:]]))
    monkeypatch.setattr(m, "CHUNKS", ((4, 2, 3), (5, 4, 4)))
    state = SimpleNamespace(calls=[], launches=0, wrong_usage=False, baseline_disk=20 * 1024**3,
                            dispatch_disk=20 * 1024**3, active=False, no_stop=False,
                            temperature=45, finish="stop", check_count=0)

    def sample():
        return {
            "gpu_name": m.low.GPU_NAME, "gpu_total_mib": 8192,
            "gpu_used_mib": 500, "gpu_temperature_c": state.temperature,
            "sampled_at": stamp(),
            "disk_free_bytes": state.dispatch_disk if state.active else state.baseline_disk,
            "memory_diagnostics": {"available": False, "reason": "INVENTED_TEST"},
        }

    def template_observation(pid):
        return {
            "process_id": pid,
            "native_chat_template_sha256": config["runtime"]["native_chat_template_sha256"],
            "expected_served_chat_template_sha256": "b" * 64,
            "observed_served_chat_template_sha256": "b" * 64,
            "expected_served_chat_template_utf8_bytes": 12,
            "observed_served_chat_template_utf8_bytes": 12,
            "template_source_available": True, "served_template_matches_pin": True,
        }

    def check_identity(process, client, configuration, observer=None):
        assert configuration is config
        state.check_count += 1
        if observer:
            observer(template_observation(process.pid))
        return {"served_chat_template_sha256": "b" * 64}

    def verify_template(configuration, sha, path, context):
        value = j.read_json(path)
        expected = {"contract_sha256": sha, **template_observation(context["process_id"]),
                    **context}
        assert all(value.get(key) == item for key, item in expected.items())

    class Process:
        def __init__(self, pid):
            self.pid = pid

        def poll(self):
            return None

    class Client:
        def request(self, route, body, *, timeout):
            assert route == "/v1/chat/completions"
            assert timeout == 240
            item = next(row for row in requests if row["seed"] == body["seed"])
            assert worker.journal.paths(item["request_id"])["intent"].is_file()
            state.calls.append(copy.deepcopy(body))
            return response(config, prompt_tokens=99 if state.wrong_usage else 12,
                            finish=state.finish)

    @contextmanager
    def owned_server(root, configuration, private, safe, epoch, sha):
        assert configuration is config
        assert configuration["execution_limits"]["deadline_utc"] == "2026-09-05T22:55:47+00:00"
        state.launches += 1
        state.active = True
        process = Process(100_000 + state.launches)
        start = {"contract_sha256": sha, "epoch": epoch, "pid": process.pid,
                 "started_at": stamp(), "owned_process_only": True,
                 "command_sha256": j.digest(m.low.command_for(root, configuration))}
        j.atomic_bytes(private / "server-01.log.private.txt", b"invented harmless worker log\n")
        j.atomic_json(safe / "server-01.started.safe.json", start)
        j.atomic_json(safe / "server-01.identity.safe.json", start)
        j.atomic_json(safe / "server-01.tpl.safe.json",
                      {**start, **template_observation(process.pid)})
        try:
            yield process, Client(), {"served_chat_template_sha256": "b" * 64}
        finally:
            state.active = False
            if not state.no_stop:
                j.atomic_json(safe / "server-01.stopped.safe.json", {
                    "contract_sha256": sha, "epoch": epoch, "pid": process.pid,
                    "owned_process_only": True, "returncode": 0, "stopped_at": stamp(),
                })

    old_raw = tmp_path / "historical.private.json"
    j.atomic_bytes(old_raw, response(config))
    target = SimpleNamespace(root=tmp_path, config=config, plan=plan,
        helper=SimpleNamespace(owned_server=owned_server, check_identity=check_identity,
                               verify_template_observation=verify_template),
        assert_unchanged=lambda: None, path=lambda kind, relative: old_raw)
    history = SimpleNamespace(target=target, rows1082=old_rows, prompts=prompts, census=census,
        manifest_proof={"verified": True, "manifest_identity_sha256": "e" * 64})
    worker = m.TargetContinuation(history, execution_identity="9" * 64, sample=sample)
    worker.launch_ready = True
    worker._launch_verifier = lambda: None
    auth = j.make_authorization(worker.execution_identity, "target", issued_at=stamp(-5),
                               expires_at=stamp(1800), direction_ref="SYNTHETIC TEST DIRECTION")
    return worker, state, auth


def crash_once(label):
    fired = False

    def crash(observed):
        nonlocal fired
        if not fired and observed == label:
            fired = True
            raise RuntimeError("INVENTED_CRASH")

    return crash


def renew(auth):
    return j.make_authorization(auth["execution_identity"], "target", issued_at=stamp(),
        expires_at=stamp(1800), direction_ref="SYNTHETIC FRESH EXPLICIT DIRECTION " + stamp())


def test_success_exact_scientific_bytes_chunks_and_original_failure_disclosure(engine):
    worker, state, auth = engine
    proof = worker.run(renew(auth))
    assert len(state.calls) == 3 and state.launches == 2
    for item, body in zip(worker.items, state.calls, strict=True):
        assert body == m.frozen.request_for(worker.config, item,
                                            worker.prompts[item["materialization_id"]])
    assert proof["target_records"] == 4 and proof["reused_target_records"] == 1
    assert proof["new_target_records"] == 3
    assert proof["original_operational_gate_passed"] is False
    assert proof["first_continuation_operational_gate_passed"] is False
    assert len(proof["prior_operation_failures"]) == 2
    assert proof["scientific_gate_evaluated"] is False and proof["paper_validity"] is False
    assert proof["missing_stop_epochs"] == []
    assert proof["proof_identity_sha256"] == j.digest({key: value for key, value in proof.items()
                                                       if key != "proof_identity_sha256"})
    assert worker.run(renew(auth)) == proof
    assert len(state.calls) == 3 and state.launches == 2
    assert worker.raw_reply(worker.plan["requests"][0]["request_id"]) == response(worker.config)


def test_unfrozen_factory_blocks_even_valid_stage_authorization(engine):
    worker, state, auth = engine
    worker.launch_ready = False
    with pytest.raises(ValueError, match="FROZEN_LAUNCH_FACTORY"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == 0


def test_wrong_stage_and_expired_authority_never_launch(engine):
    worker, state, auth = engine
    wrong = j.make_authorization(worker.execution_identity, "qwen", issued_at=stamp(-5),
                                expires_at=stamp(100), direction_ref="SYNTHETIC")
    with pytest.raises(ValueError, match="WRONG_STAGE"):
        worker.run(wrong)
    expired = j.make_authorization(worker.execution_identity, "target", issued_at=stamp(-100),
                                  expires_at=stamp(-50), direction_ref="SYNTHETIC")
    with pytest.raises(ValueError, match="NOT_CURRENT"):
        worker.run(expired)
    assert state.calls == [] and state.launches == 0


def test_before_dispatch_interrupt_reuses_valid_request_without_duplicate(engine):
    worker, state, auth = engine
    with pytest.raises(RuntimeError, match="INVENTED_CRASH"):
        worker.run(renew(auth), crash=crash_once("before_dispatch"))
    assert state.calls == []
    assert worker.states()[0]["state"] == "UNISSUED"
    assert worker.run(renew(auth))["composite_target_complete"] is True
    assert len(state.calls) == 3


def test_inflight_intent_is_ambiguous_and_not_replayed(engine):
    worker, state, auth = engine
    with pytest.raises(RuntimeError):
        worker.run(renew(auth), crash=crash_once("intent_durable"))
    assert worker.states()[0]["state"] == "AMBIGUOUS"
    launches = state.launches
    with pytest.raises(ValueError, match="AMBIGUOUS_REQUEST_NO_RETRY"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == launches


@pytest.mark.parametrize("point", ["response_durable", "row_durable",
                                  "response_publication_pending_written",
                                  "complete_publication_published"])
def test_persisted_reply_recovered_without_new_observation(engine, point):
    worker, state, auth = engine
    with pytest.raises(RuntimeError):
        worker.run(renew(auth), crash=crash_once(point))
    assert len(state.calls) == 1
    before = worker.states()[0]
    assert before["state"] == "COMPLETE" and before["repair_required"] is True
    assert worker.run(renew(auth))["composite_target_complete"] is True
    assert len(state.calls) == 3


def test_response_received_not_persisted_is_not_regenerated(engine):
    worker, state, auth = engine
    with pytest.raises(RuntimeError):
        worker.run(renew(auth), crash=crash_once("response_received_not_saved"))
    assert len(state.calls) == 1
    with pytest.raises(ValueError, match="AMBIGUOUS_REQUEST_NO_RETRY"):
        worker.run(renew(auth))
    assert len(state.calls) == 1


def test_wrong_raw_usage_retained_and_blocks_replay(engine):
    worker, state, auth = engine
    state.wrong_usage = True
    with pytest.raises(ValueError, match="NATIVE_CENSUS_USAGE_MISMATCH"):
        worker.run(renew(auth))
    assert len(state.calls) == 1
    path = worker.journal.paths(worker.items[0]["request_id"])["response"]
    assert path.is_file()
    with pytest.raises(ValueError, match="AMBIGUOUS_REQUEST_NO_RETRY"):
        worker.run(renew(auth))
    assert len(state.calls) == 1


def test_prelaunch_20gib_and_dispatch_15gib_are_distinct(engine):
    worker, state, auth = engine
    state.baseline_disk = 19 * 1024**3
    with pytest.raises(ValueError, match="PRELAUNCH_DISK_BELOW_20_GIB"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == 0
    state.baseline_disk = 20 * 1024**3
    state.dispatch_disk = 14 * 1024**3
    with pytest.raises(ValueError, match="DISK_FREE_SPACE_BELOW_15_GIB"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == 1
    assert all(row["state"] == "UNISSUED" for row in worker.states())
    state.dispatch_disk = 20 * 1024**3
    proof = worker.run(renew(auth))
    assert proof["composite_target_complete"] is True
    assert proof["failed_prelaunch_attempts"] == 1
    assert len(proof["all_attempts"]) == 4
    assert [attempt["completed_target_requests"] for attempt in proof["all_attempts"]] == [
        0, 0, 2, 1]


def test_completed_negative_or_truncated_reply_not_selected_away(engine):
    worker, state, auth = engine
    state.finish = "length"
    worker.run(renew(auth))
    rows, proof = worker.verify_complete()
    assert len(state.calls) == 3 and proof["composite_target_complete"] is True
    assert all(row["finish_reason"] == "length" for row in rows[1:])
    assert all(row["eligible_for_panel"] is False for row in rows[1:])
    assert all(row["ineligible_reason"] == "TRUNCATED_UNKNOWN" for row in rows[1:])


def test_interrupted_worker_requires_explicit_pid_absence_review(engine):
    worker, state, auth = engine
    state.no_stop = True
    with pytest.raises(RuntimeError):
        worker.run(renew(auth), crash=crash_once("response_durable"))
    eid = worker.states()[0]["intent"]["epoch"]["epoch_id"]
    with pytest.raises(ValueError, match="UNCLOSED_EPOCH_REQUIRES_EXPLICIT_REVIEW"):
        worker.run(renew(auth))
    with pytest.raises(ValueError, match="STILL_PRESENT_OR_REUSED"):
        worker.review_interrupted_epoch(eid, renew(auth), absent_probe=lambda pid: False)
    release = worker.review_interrupted_epoch(eid, renew(auth), absent_probe=lambda pid: True)
    assert release["clean_stop_observed"] is False
    assert not worker._epoch_path(eid, "server-01.stopped.safe.json").exists()
    state.no_stop = False
    proof = worker.run(renew(auth))
    assert proof["missing_stop_epochs"] == [eid]
    assert len(state.calls) == 3


def test_modified_history_or_scientific_frame_blocks_before_launch(engine):
    worker, state, auth = engine
    worker.plan["requests"][-1]["generation"]["temperature"] = 0.01
    with pytest.raises(ValueError, match="CONTEXT_MUTATED"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == 0


def test_foreign_request_namespace_blocks(engine):
    worker, state, auth = engine
    (worker.safe / "requests" / "foreign").mkdir(parents=True)
    with pytest.raises(ValueError, match="UNPLANNED_REQUEST_NAMESPACE"):
        worker.run(renew(auth))
    assert state.calls == [] and state.launches == 0


def test_missing_completion_marker_never_certifies_full_frame(engine):
    worker, state, auth = engine
    count = 0

    def last_reply_crash(point):
        nonlocal count
        if point == "response_durable":
            count += 1
            if count == 3:
                raise RuntimeError("INVENTED_CRASH")

    with pytest.raises(RuntimeError):
        worker.run(renew(auth), crash=last_reply_crash)
    with pytest.raises(ValueError, match="FULL_FRAME_INCOMPLETE"):
        worker.verify_complete()
    assert worker.run(renew(auth))["composite_target_complete"] is True
    assert len(state.calls) == 3


def test_one_direction_receipt_cannot_restart_failed_attempt(engine):
    worker, state, auth = engine
    with pytest.raises(RuntimeError):
        worker.run(auth, crash=crash_once("before_dispatch"))
    launches = state.launches
    with pytest.raises(ValueError, match="AUTH_ALREADY_ACTIVATED_NEW_DIRECTION_REQUIRED"):
        worker.run(auth)
    assert state.launches == launches and state.calls == []
    assert worker.run(renew(auth))["composite_target_complete"] is True


def test_completed_worker_binding_tamper_is_rejected(engine):
    worker, state, auth = engine
    worker.run(renew(auth))
    eid = worker.states()[0]["intent"]["epoch"]["epoch_id"]
    path = worker._epoch_path(eid, "binding.safe.json")
    binding = j.read_json(path)
    binding["logical_chunk"] = 5
    path.write_bytes(j.canonical(binding))
    with pytest.raises(ValueError, match="WORKER_BINDING_CHANGED"):
        worker.verify_complete()
    assert len(state.calls) == 3


def test_cooling_receipt_tamper_is_rejected_without_replay(engine):
    worker, state, auth = engine
    worker.run(renew(auth))
    item = worker.states()[0]
    path = worker.safe / "admissions" / item["intent"]["admission"]["admission_id"]
    path = path / "cooldown.safe.json"
    receipt = j.read_json(path)
    receipt["samples"][-1]["gpu_temperature_c"] = 61
    path.write_bytes(j.canonical(receipt))
    with pytest.raises(ValueError, match="COOLDOWN_CHANGED"):
        worker.verify_complete()
    assert len(state.calls) == 3


def test_progress_and_failure_logs_have_safe_diagnostic_values(engine):
    worker, state, auth = engine
    state.dispatch_disk = 14 * 1024**3
    with pytest.raises(ValueError, match="DISK_FREE_SPACE_BELOW_15_GIB"):
        worker.run(renew(auth))
    events = [j.read_json(path) for path in (worker.safe / "events").glob("*.safe.json")]
    stopped = [event for event in events if event["event"] == "TARGET_STAGE_STOPPED"]
    assert stopped[0]["error_code"] == "DISK_FREE_SPACE_BELOW_15_GIB"
    state.dispatch_disk = 20 * 1024**3
    worker.run(renew(auth))
    events = [j.read_json(path) for path in (worker.safe / "events").glob("*.safe.json")]
    progress = [event for event in events if event["event"] == "PROGRESS"
                and event.get("latest_resource_snapshot")]
    assert len(progress) == 3
    for event in progress:
        assert event["checkpoint_authoritative"] is False
        assert event["latest_resource_snapshot"]["disk_free_bytes"] == 20 * 1024**3
        assert event["last_verified_request_id"] is not None
        assert event["elapsed_seconds"] >= 0
    assert worker.journal.audit_events()["observed_event_artifacts_valid"] is True
    assert worker.journal.audit_events()["event_log_completeness_proven"] is False


def test_read_only_batches_validate_full_context_once_but_public_parser_still_checks(
    engine, monkeypatch
):
    worker, _, _ = engine
    checks = []
    original = worker.assert_unchanged

    def counted_check():
        checks.append(True)
        original()

    monkeypatch.setattr(worker, "assert_unchanged", counted_check)
    worker.states()
    assert len(checks) == 1
    checks.clear()
    worker.attempt_inventory()
    assert len(checks) == 1
    checks.clear()
    for item in worker.items:
        worker.body_binding_parser(item)
    assert len(checks) == len(worker.items)
    worker.prompts[worker.items[0]["materialization_id"]] = "Changed invented material"
    with pytest.raises(ValueError, match="CONTEXT_MUTATED"):
        worker.states()
    with pytest.raises(ValueError, match="CONTEXT_MUTATED"):
        worker.body_binding_parser(worker.items[0])
