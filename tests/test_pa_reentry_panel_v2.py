"""Synthetic full frames, real durable journal, fake transports; no models/GPU/data."""

import importlib.util
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pa_llama_topology_plan_v1 as plan_module  # noqa: E402
import pa_reentry_panel_v2 as m  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "reentry_old_pure_test_helpers", ROOT / "tests/test_pa_llama_development_panel_v1.py"
)
OLD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OLD)
c, j = m.c, m.journal


def gpu(baseline=False):
    return {
        "name": "NVIDIA GeForce RTX 3070",
        "used_mib": 500 if baseline else 5000,
        "total_mib": 8192,
        "temperature_c": 40,
    }


class FakeSampler:
    def __init__(self, config, path):
        self.config, self.path = config, path
        self.samples, self.failure_code = [], None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def check(self):
        c.require(self.failure_code is None, "SYNTHETIC_RESOURCE_FAILURE")

    def observe(self, baseline=False):
        self.check()
        sample = {
            "sequence": len(self.samples),
            "recorded_at": j.utc(),
            "baseline": baseline,
            "observed": gpu(baseline),
            "gate_passed": True,
            "error_code": None,
        }
        self.samples.append(sample)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as stream:
            stream.write(c.canonical(sample) + b"\n")
        return sample


class Target:
    def __init__(self, root, eligible=2):
        self.root, self.execution_identity = root, "a" * 64
        self.manifest_identity, self.launch_ready = "e" * 64, False
        self.config = OLD.config.__wrapped__()
        self.helpers = OLD.functions.__wrapped__(self.config)
        self.config.update(_contract_sha256=m.PARENT, frozen_at_utc="2026-09-05T18:59:05+00:00")
        self.config["execution_limits"].update(
            minimum_free_disk_bytes=15 * 1024**3,
            maximum_prelaunch_gpu_mib=1000,
            deadline_utc="2026-09-05T22:55:47+00:00",
        )
        self.config["panel"]["jailmeter"].update(
            request_timeout_seconds=240,
            runner_path="synthetic.py",
            base_metadata_local_path="synthetic/jm",
        )
        self.config["panel"]["qwen"]["model_local_path"] = "synthetic/qwen"
        self.payloads = {pos: f"Harmless synthetic payload {pos}." for pos in range(21)}
        population = [
            {
                "payload_position": pos,
                "payload_sha256": c.sha_bytes(text.encode()),
                "prompt_sha256": "1" * 64,
                "unit_manifest_sha256": "2" * 64,
                "fragment_manifest_sha256": "3" * 64,
            }
            for pos, text in self.payloads.items()
        ]
        requests, _ = plan_module._schedule("4" * 64, population)
        self.plan = {
            "requests": requests,
            "population": population,
            "n": 21,
            "plan_identity_sha256": m.PLAN,
            "parent_operational_amendment_disclosure": {
                "original_seed11_jailmeter_operational_gate_passed": False,
                "screen_amendment_sha256": "9" * 64,
            },
        }
        self.rows, self.raw = [], {}
        count = 0
        for item in requests:
            content = "  Invented benign reply\r\nwith line.  "
            raw = c.canonical({"choices": [{"message": {"content": content}}]})
            science = item["kind"] == "science"
            row = {
                **item,
                "contract_sha256": m.PARENT,
                "eligible_for_panel": science and count < eligible,
                "eligible_for_control": not science,
                "request_sha256": c.digest(item),
                "raw_reply_sha256": c.sha_bytes(raw),
                "content_sha256": c.sha_bytes(content.encode()),
                "response_sha256": c.sha_bytes(c.normalize_response(content).encode()),
            }
            self.rows.append(row)
            if science:
                self.raw[item["request_id"]] = raw
                count += 1
        self.release = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        self.tokenizer = OLD.Tokenizer()

    def proof(self):
        attempts = [
            {"epoch_id": "synthetic-target-004", "status": "COMPLETED", "release_at": self.release}
        ]
        return m.seal(
            {
                "schema_version": "pa-reentry-target-composite-v2",
                "execution_identity": self.execution_identity,
                "original_contract_sha256": m.PARENT,
                "bound_plan_identity_sha256": m.PLAN,
                "archive_manifest_identity_sha256": self.manifest_identity,
                "target_records": 1470,
                "reused_target_records": 1082,
                "new_target_records": 388,
                "target_rows_sha256": c.digest(self.rows),
                "original_operational_gate_passed": False,
                "first_continuation_operational_gate_passed": False,
                "prior_operation_failures": list(m.FAILURES),
                "missing_stop_epochs": [],
                "latest_target_release_at": self.release,
                "composite_target_complete": True,
                "scientific_gate_evaluated": False,
                "paper_validity": False,
                "all_attempts": attempts,
                "all_attempts_sha256": c.digest(attempts),
                "failed_prelaunch_attempts": 0,
                "archive_relocation_contemporaneous_receipt_available": False,
            }
        )

    def verify_complete(self):
        return self.rows, self.proof()

    def raw_reply(self, rid):
        assert rid in self.raw, "controls are never read by evaluator"
        return self.raw[rid]


def authorization(target, axis, *, fresh=False):
    now = datetime.now(timezone.utc)
    return j.make_authorization(
        target.execution_identity,
        axis,
        issued_at=(now if fresh else now - timedelta(seconds=30)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        direction_ref="SYNTHETIC_TEST_ONLY_FRESH" if fresh else "SYNTHETIC_TEST_ONLY",
    )


@pytest.fixture
def engine(tmp_path, monkeypatch):
    target = Target(tmp_path)
    panel = m.ReentryPanel(
        target,
        target.payloads,
        tmp_path / "data/natural_language_localization/pa_reentry_v2" / target.execution_identity,
        tmp_path / "artifacts/pa_reentry_v2/private" / target.execution_identity,
        target.execution_identity,
    )
    calls = []

    def load(axis):
        rows, _ = panel.verify_targets()
        return (
            m.frozen.prepare_values(
                target.config,
                target.plan,
                rows,
                target.payloads,
                target.raw,
                target.helpers,
                target.tokenizer,
                axis,
                "Synthetic system",
            ),
            target.helpers,
            target.tokenizer,
        )

    monkeypatch.setattr(panel, "load", load)
    monkeypatch.setattr(m.low, "jailmeter_command", lambda *_: ["synthetic.exe", "fixed"])
    monkeypatch.setattr(m.thermal, "check_disk", lambda *_: 30 * 1024**3)

    @contextmanager
    def runtime(adapter, axis, index, tokenizer, sampler, auth):
        rt = m.EpochRuntime(adapter, axis, index, auth)
        command = m.low.jailmeter_command(tmp_path, target.config) if axis == "jailmeter" else None
        start = {
            **rt.worker_binding(axis),
            "pid": 7000 + index,
            "started_at": j.utc(),
            "command_sha256": c.digest(command) if command else None,
            "in_process_model": axis == "qwen",
        }
        c.write_once(rt.path(axis, "worker.started.safe.json"), start)
        c.write_once(
            rt.path(axis, "worker.log.private.txt", private=True), b"synthetic log", raw=True
        )

        def call(value, body):
            assert c.same(body, m.low.request_body(target.config, value, axis))
            calls.append((axis, value["item"]["request_id"]))
            content = "Safety: Unsafe\nRefusal: No" if axis == "qwen" else "<label>1</label>"
            raw = (
                {"content": content, "output_ids": [ord(ch) for ch in content]}
                if axis == "qwen"
                else {"content": content, "tokens_predicted": 8, "tokens_evaluated": 10}
            )
            return c.canonical(raw) + b"\n"

        try:
            yield SimpleNamespace(
                pid=start["pid"],
                command_sha256=start["command_sha256"],
                call=call,
                alive=lambda: True,
            )
        finally:
            c.write_once(
                rt.path(axis, "worker.stopped.safe.json"),
                {
                    **rt.worker_binding(axis),
                    "pid": start["pid"],
                    "stopped_at": j.utc(),
                    "model_released": True,
                    "owned_server_stopped": axis == "jailmeter",
                    "returncode": 0 if axis == "jailmeter" else None,
                    "peak_cuda_allocated_bytes": 1000 if axis == "qwen" else None,
                },
            )

    return SimpleNamespace(panel=panel, target=target, calls=calls, runtime=runtime)


def run(engine, axis, auth=None, **kw):
    return engine.panel.run(
        axis,
        auth or authorization(engine.target, axis),
        runtime_factory=engine.runtime,
        sampler_factory=FakeSampler,
        diagnostic=lambda: {"diagnostic_only": True},
        **kw,
    )


def fast_verified_skips(engine, monkeypatch):
    """Crash unit tests isolate 2 real journal chains; full-frame test does not use this."""
    actual = engine.panel.state

    def state(axis, value, helpers, tokenizer, *, recover=False):
        if value["skip_reason"]:
            return {
                "state": "COMPLETE",
                "repair_required": False,
                "dispatched": False,
                "row": m.low.skipped_row(engine.panel.config, value, axis),
                "request_id": value["item"]["request_id"],
                "reason": "EXPLICIT_TEST_PREVERIFIED_SKIP",
            }
        return actual(axis, value, helpers, tokenizer, recover=recover)

    monkeypatch.setattr(engine.panel, "state", state)


def allow_prior_qwen_for_jm_unit_test(engine, monkeypatch):
    actual = engine.panel.verify

    def verify(axis):
        if axis == "qwen":
            return {"latest_evaluator_release_at": engine.target.release}
        return actual(axis)

    monkeypatch.setattr(engine.panel, "verify", verify)


def test_full_real_journal_both882_frames_and_no_automatic_stage_transition(engine, monkeypatch):
    qwen = run(engine, "qwen")
    assert qwen["planned_records"] == 882 and qwen["dispatched"] == 2 and qwen["skipped"] == 880
    assert len(engine.calls) == 2 and all(axis == "qwen" for axis, _ in engine.calls)
    jm = run(engine, "jailmeter")
    assert jm["planned_records"] == 882 and jm["dispatched"] == 2 and jm["skipped"] == 880
    assert len(engine.calls) == 4 and jm["controls_judged"] == 0
    monkeypatch.setattr(m.low, "query_gpu", lambda: pytest.fail("verification must not query GPU"))
    assert engine.panel.verify("qwen") == qwen
    assert engine.panel.verify("jailmeter") == jm
    assert qwen["original_operational_gate_passed"] is False
    assert jm["first_continuation_operational_gate_passed"] is False
    assert jm["prior_operation_failures"] == list(m.FAILURES)
    assert engine.panel.axis_path(
        "qwen", f"proofs/{qwen['proof_identity_sha256']}.safe.json"
    ).is_file()
    assert engine.panel.axis_path(
        "jailmeter", f"proofs/{jm['proof_identity_sha256']}.safe.json"
    ).is_file()
    assert engine.target.config["execution_limits"]["deadline_utc"] == "2026-09-05T22:55:47+00:00"


@pytest.mark.parametrize("axis", m.AXES)
@pytest.mark.parametrize(
    "crash_at,ambiguous,calls_before",
    [
        ("before_dispatch", False, 0),
        ("intent_durable", True, 0),
        ("response_received_not_saved", True, 1),
        ("response_durable", False, 1),
        ("row_durable", False, 1),
        ("response_publication_pending_written", False, 1),
    ],
)
def test_crash_recovery_no_replacement_or_ambiguous_retry(
    engine, monkeypatch, axis, crash_at, ambiguous, calls_before
):
    fast_verified_skips(engine, monkeypatch)
    if axis == "jailmeter":
        allow_prior_qwen_for_jm_unit_test(engine, monkeypatch)
    auth = authorization(engine.target, axis)

    def crash(label):
        if label == crash_at:
            raise RuntimeError("SYNTHETIC_CRASH")

    with pytest.raises(RuntimeError, match="SYNTHETIC_CRASH"):
        run(engine, axis, auth, crash=crash)
    assert len(engine.calls) == calls_before
    inventory = engine.panel.inspect(axis)
    first = inventory["states"][0]
    if ambiguous:
        assert first["state"] == "AMBIGUOUS"
        with pytest.raises(ValueError, match="AMBIGUOUS_NO_RETRY"):
            run(engine, axis, authorization(engine.target, axis, fresh=True))
        assert len(engine.calls) == calls_before
    else:
        if first["repair_required"]:
            engine.panel.recover(axis, authorization(engine.target, axis, fresh=True))
        with pytest.raises(ValueError):
            run(engine, axis, auth)
        result = run(engine, axis, authorization(engine.target, axis, fresh=True))
        assert result["dispatched"] == 2 and len(engine.calls) == 2
        assert len(set(engine.calls)) == 2
        assert result["epochs"][0]["prior_interruption_retained"] is True


@pytest.mark.parametrize("axis", m.AXES)
def test_invalid_stage_authority_stops_before_prepare_or_worker(engine, monkeypatch, axis):
    wrong = "jailmeter" if axis == "qwen" else "qwen"
    monkeypatch.setattr(engine.panel, "load", lambda _: pytest.fail("must reject before load"))
    with pytest.raises(ValueError, match="WRONG_STAGE"):
        run(engine, axis, authorization(engine.target, wrong))
    assert not engine.calls


def test_default_runtime_requires_pinned_launch_factory_before_gpu(engine, monkeypatch):
    monkeypatch.setattr(engine.panel, "load", lambda _: pytest.fail("must reject before load"))
    with pytest.raises(ValueError, match="LAUNCH_READY"):
        engine.panel.run("qwen", authorization(engine.target, "qwen"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("original_operational_gate_passed", True),
        ("first_continuation_operational_gate_passed", True),
        ("new_target_records", 387),
        ("target_records", 1469),
        ("archive_manifest_identity_sha256", "f" * 64),
        ("prior_operation_failures", []),
    ],
)
def test_coherent_target_proof_drift_rejected(engine, monkeypatch, field, value):
    proof = engine.target.proof()
    proof[field] = value
    m.seal(proof)
    monkeypatch.setattr(engine.target, "verify_complete", lambda: (engine.target.rows, proof))
    with pytest.raises(ValueError):
        engine.panel.verify_targets()


@pytest.mark.parametrize("axis", m.AXES)
def test_saved_raw_hash_or_token_content_tamper_blocks(engine, monkeypatch, axis):
    fast_verified_skips(engine, monkeypatch)
    if axis == "jailmeter":
        allow_prior_qwen_for_jm_unit_test(engine, monkeypatch)
    run(engine, axis)
    rid = engine.panel.frame[0]["request_id"]
    path = engine.panel.journal(axis).paths(rid)["response"]
    envelope = j.read_json(path)
    envelope["meta"]["raw_sha256"] = "f" * 64
    envelope.pop("identity_sha256")
    path.write_bytes(j.canonical(j.seal(envelope)) + b"\n")
    assert engine.panel.inspect(axis)["states"][0]["state"] == "AMBIGUOUS"
    with pytest.raises(ValueError, match="NOT_COMPLETE"):
        engine.panel.verify(axis)


def test_disk_floor_prevents_worker_and_retains_failed_epoch(engine, monkeypatch):
    fast_verified_skips(engine, monkeypatch)
    monkeypatch.setattr(m.thermal, "check_disk", lambda *_: 19 * 1024**3)
    with pytest.raises(ValueError, match="PRELAUNCH_DISK"):
        run(engine, "qwen")
    assert not engine.calls
    summary = j.read_json(engine.panel.epoch_path("qwen", 1, "summary.safe.json"))
    assert summary["error_code"] == "REENTRY_PANEL_PRELAUNCH_DISK_BELOW_20_GIB"
    monkeypatch.setattr(m.thermal, "check_disk", lambda *_: 30 * 1024**3)
    result = run(engine, "qwen", authorization(engine.target, "qwen", fresh=True))
    assert result["epochs"][0]["worker_never_started"] is True
    assert result["epochs"][0]["prior_interruption_retained"] is True


def test_low_worker_and_scientific_functions_are_frozen_references():
    assert m.frozen.qwen_reply.__module__ == "pa_llama_topology_panel_v1"
    assert m.low.qwen_result.__module__ == "pa_llama_development_panel_v1"
    assert m.low.jailmeter_result.__module__ == "pa_llama_development_panel_v1"


def test_real_target_proof_producer_to_panel_consumer_full1470(engine, monkeypatch):
    """Production proof builder; only invented raw/epoch-verifier outputs are injected."""
    import pa_reentry_target_v2 as target_module

    original = engine.target
    target = object.__new__(target_module.TargetContinuation)
    target.root, target.config, target.plan = original.root, original.config, original.plan
    target.execution_identity, target.manifest_identity = (
        original.execution_identity,
        original.manifest_identity,
    )
    target.historical_rows = original.rows[:1082]
    states = [
        {
            "state": "COMPLETE",
            "repair_required": False,
            "row": row,
            "intent": {"epoch": {"epoch_id": "0004" if row["ordinal"] <= 1292 else "0005"}},
        }
        for row in original.rows[1082:]
    ]
    monkeypatch.setattr(target, "states", lambda **_: states)
    monkeypatch.setattr(target, "_assert_prior_epochs_released", lambda: None)
    monkeypatch.setattr(
        target, "verify_epoch", lambda eid, **_: {"epoch_id": eid, "clean_stop_observed": True}
    )
    monkeypatch.setattr(
        target,
        "attempt_inventory",
        lambda: [
            {"epoch_id": "0004", "status": "COMPLETED", "release_at": original.release},
            {"epoch_id": "0005", "status": "COMPLETED", "release_at": original.release},
        ],
    )
    engine.panel.target = target
    rows, proof = engine.panel.verify_targets()
    assert len(rows) == 1470 and sum(row["kind"] == "science" for row in rows) == 882
    assert proof["new_target_records"] == 388
    assert proof["all_attempts_sha256"] == c.digest(proof["all_attempts"])
    assert proof["archive_relocation_contemporaneous_receipt_available"] is False


def test_real_load_uses_only_original_science_raw_and_local_metadata(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(m.low, "preflight", lambda *_: None)
    monkeypatch.setattr(m.low, "load_pure_functions", lambda *_: engine.target.helpers)
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoTokenizer=SimpleNamespace(
                from_pretrained=lambda *args, **kw: calls.append(kw) or engine.target.tokenizer
            )
        ),
    )
    values, helpers, tokenizer = m.ReentryPanel.load(engine.panel, "qwen")
    assert (
        len(values) == 882
        and helpers is engine.target.helpers
        and tokenizer is engine.target.tokenizer
    )
    assert calls == [{"local_files_only": True}]
    assert sum(v["skip_reason"] is None for v in values) == 2
    assert all(
        v["record"].goal_text == engine.target.payloads[v["item"]["payload_position"]]
        for v in values
    )


@pytest.mark.parametrize("axis", m.AXES)
def test_nonprefix_completed_state_stops_before_any_worker(engine, monkeypatch, axis):
    fast_verified_skips(engine, monkeypatch)
    if axis == "jailmeter":
        allow_prior_qwen_for_jm_unit_test(engine, monkeypatch)
    actual = engine.panel.state
    second = engine.panel.frame[1]["request_id"]

    def state(selected, value, *args, **kw):
        if value["item"]["request_id"] == second:
            return {
                "state": "COMPLETE",
                "repair_required": False,
                "dispatched": True,
                "row": {"synthetic_contradiction": True},
            }
        return actual(selected, value, *args, **kw)

    monkeypatch.setattr(engine.panel, "state", state)
    with pytest.raises(ValueError, match="NONPREFIX_COMPLETION"):
        run(engine, axis)
    assert not engine.calls and engine.panel.epochs(axis) == []


def test_recovery_validates_epoch_before_writing_derived_marker(engine, monkeypatch):
    fast_verified_skips(engine, monkeypatch)

    def crash(label):
        if label == "response_durable":
            raise RuntimeError("SYNTHETIC_CRASH")

    with pytest.raises(RuntimeError):
        run(engine, "qwen", crash=crash)
    paths = engine.panel.journal("qwen").paths(engine.panel.frame[0]["request_id"])
    assert not paths["row"].exists()
    path = engine.panel.epoch_path("qwen", 1, "worker.started.safe.json")
    value = j.read_json(path)
    value["pid"] = 999
    path.write_bytes(j.canonical(value) + b"\n")
    with pytest.raises(ValueError):
        engine.panel.recover("qwen", authorization(engine.target, "qwen", fresh=True))
    assert not paths["row"].exists() and not paths["complete"].exists()


@pytest.mark.parametrize(
    "mutation",
    ["missing_admission_sample", "lost_tail", "wrong_pid", "old_start", "unexplained_epoch_file"],
)
def test_resource_and_worker_tamper_never_certifies_complete_axis(engine, monkeypatch, mutation):
    fast_verified_skips(engine, monkeypatch)
    run(engine, "qwen")
    if mutation in {"missing_admission_sample", "lost_tail"}:
        path = engine.panel.epoch_path("qwen", 1, "samples.safe.jsonl")
        samples = m.read_lines(path)
        if mutation == "missing_admission_sample":
            samples[1]["observed"]["temperature_c"] = 41
        else:
            samples.pop()
        path.write_bytes(b"".join(j.canonical(row) + b"\n" for row in samples))
        summary_path = engine.panel.epoch_path("qwen", 1, "summary.safe.json")
        summary = j.read_json(summary_path)
        summary.update(samples_sha256=c.digest(samples), sample_count=len(samples))
        summary_path.write_bytes(j.canonical(summary) + b"\n")
    elif mutation == "unexplained_epoch_file":
        c.write_once(
            engine.panel.epoch_path("qwen", 1, "unexplained.safe.json"), {"invented": True}
        )
    else:
        path = engine.panel.epoch_path("qwen", 1, "worker.started.safe.json")
        value = j.read_json(path)
        value["pid" if mutation == "wrong_pid" else "started_at"] = (
            999 if mutation == "wrong_pid" else "2026-01-01T00:00:00+00:00"
        )
        path.write_bytes(j.canonical(value) + b"\n")
    with pytest.raises(ValueError):
        engine.panel.verify("qwen")
    assert len(engine.calls) == 2


def test_missing_stop_requires_real_absence_review_and_stays_resource_incomplete(
    engine, monkeypatch
):
    fast_verified_skips(engine, monkeypatch)
    run(engine, "qwen")
    # Invent a hard-crash fixture: only temporary synthetic stop/summary are removed.
    engine.panel.epoch_path("qwen", 1, "worker.stopped.safe.json").unlink()
    engine.panel.epoch_path("qwen", 1, "summary.safe.json").unlink()
    with pytest.raises(ValueError, match="MISSING_STOP"):
        engine.panel.verify("qwen")
    auth = authorization(engine.target, "qwen", fresh=True)
    with pytest.raises(ValueError, match="PID_NOT_PROVEN_ABSENT"):
        engine.panel.review_interruption(
            "qwen",
            1,
            auth,
            process_probe=lambda _: True,
            resource_observer=lambda: pytest.fail("must not observe yet"),
        )
    review = engine.panel.review_interruption(
        "qwen",
        1,
        auth,
        process_probe=lambda _: False,
        resource_observer=lambda: gpu(True),
        diagnostic=lambda: {"diagnostic_only": True},
    )
    assert review["old_stop_fabricated"] is False
    assert not engine.panel.epoch_path("qwen", 1, "worker.stopped.safe.json").exists()
    with pytest.raises(ValueError, match="INCOMPLETE_RESOURCE_EVIDENCE"):
        engine.panel.verify("qwen")
    assert len(engine.calls) == 2


def test_unexplained_control_request_directory_rejected(engine, monkeypatch):
    fast_verified_skips(engine, monkeypatch)
    run(engine, "qwen")
    control = next(
        r["request_id"] for r in engine.target.plan["requests"] if r["kind"] == "control"
    )
    engine.panel.journal("qwen").paths(control)["intent"].parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="UNEXPLAINED_REQUEST_ID"):
        engine.panel.verify("qwen")
