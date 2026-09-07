"""Synthetic only: no real GPU, model, server, private corpus or sealed reads."""

import copy
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pa_llama_development_jailmeter_continuation_v1 as m  # noqa: E402

c, p = m.c, m.p
SPEC = importlib.util.spec_from_file_location(
    "continuation_synthetic_parent_fixtures",
    SCRIPTS.parent / "tests/test_pa_llama_development_panel_v1.py",
)
PARENT_TESTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARENT_TESTS)
config = PARENT_TESTS.config
functions = PARENT_TESTS.functions
value = PARENT_TESTS.value


def ids(start, count):
    return [f"{index:064x}" for index in range(start, start + count)]


@pytest.fixture
def amendment():
    dispatched, skipped, pending = ids(1, 30), ids(31, 5), ids(36, 55)
    base = f"{c.SAFE_ROOT}/{m.PARENT_SHA}/panel/jailmeter/"
    files = [base + rid + ".dispatch.safe.json" for rid in dispatched]
    files += [base + rid + ".row.safe.json" for rid in dispatched + skipped]
    files += [
        base + "seed-11." + suffix + ".safe.json"
        for suffix in ("abort", "resources", "server.started", "server.stopped")
    ]
    return {
        "schema_version": m.SCHEMA,
        "frozen": True,
        "execution_authorized": True,
        "frozen_at_utc": "2026-01-01T00:00:00+00:00",
        "parent_contract": {"path": c.CONFIG, "sha256": m.PARENT_SHA, "size_bytes": 1},
        "protocol": {"path": "docs/synthetic.md", "sha256": "b" * 64, "size_bytes": 1},
        "allowed_seeds": [11, 23, 47],
        "cooling": copy.deepcopy(m.COOLING),
        "scientific_changes": False,
        "redo_completed": False,
        "maximum_total_jailmeter_dispatches": 270,
        "reuse_all_completed_original_receipts": True,
        "new_failure_requires_review": True,
        "maximum_continuation_epochs_per_seed": 1,
        "retain_failed_resource_sample": True,
        "required_code": {},
        "original_phase11_plan": {
            "path": "data/synthetic.safe.json",
            "size_bytes": 1,
            "sha256": "b" * 64,
        },
        "deadline_utc": c.EXECUTION_LIMITS["deadline_utc"],
        "original_seed11_prefix": {
            "safe_files": [{"path": path, "size_bytes": 1, "sha256": "b" * 64} for path in files],
            "dispatched_request_ids": dispatched,
            "skipped_request_ids": skipped,
            "pending_request_ids": pending,
        },
    }


def loaded(amendment):
    return {**amendment, "_amendment_sha256": "d" * 64}


def gpu(temperature=40, used=5000, total=8192):
    return {
        "name": "NVIDIA GeForce RTX 3070",
        "temperature_c": temperature,
        "used_mib": used,
        "total_mib": total,
    }


def test_exact_scope_and_69_file_closure(amendment):
    assert m.validate_amendment(amendment) is amendment
    assert [len(group) for group in m.prefix_ids(amendment)] == [30, 5, 55]
    assert len(amendment["original_seed11_prefix"]["safe_files"]) == 69


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("scientific_changes", True),
        ("redo_completed", True),
        ("maximum_total_jailmeter_dispatches", 271),
        ("allowed_seeds", [11, 23]),
        ("frozen", False),
        ("execution_authorized", False),
        ("deadline_utc", "2099-01-01T00:00:00+00:00"),
        ("maximum_continuation_epochs_per_seed", 2),
        ("retain_failed_resource_sample", False),
    ],
)
def test_scope_changes_rejected(amendment, key, replacement):
    amendment[key] = replacement
    with pytest.raises(ValueError):
        m.validate_amendment(amendment)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "overlap",
        "missing_file",
        "foreign_file",
        "cooling",
        "parent",
        "runtime",
        "no_utc",
    ],
)
def test_prefix_and_authority_mutations_rejected(amendment, mutation):
    prefix = amendment["original_seed11_prefix"]
    if mutation == "duplicate":
        prefix["pending_request_ids"][1] = prefix["pending_request_ids"][0]
    elif mutation == "overlap":
        prefix["pending_request_ids"][0] = prefix["dispatched_request_ids"][0]
    elif mutation == "missing_file":
        prefix["safe_files"].pop()
    elif mutation == "foreign_file":
        prefix["safe_files"][0]["path"] = "artifacts/private/secret.json"
    elif mutation == "cooling":
        amendment["cooling"]["maximum_predispatch_temperature_c"] = 61
    elif mutation == "parent":
        amendment["parent_contract"]["sha256"] = "f" * 64
    elif mutation == "runtime":
        amendment["_amendment_sha256"] = "f" * 64
    else:
        amendment["frozen_at_utc"] = "2026-01-01T01:00:00+01:00"
    with pytest.raises(ValueError):
        m.validate_amendment(amendment)


@pytest.mark.parametrize(
    "sample",
    [gpu(85), gpu(86), gpu(40, 7601), gpu(40, 5000, 7999), gpu(float("nan")), gpu(-1), gpu(40, -1)],
)
def test_original_resource_gate_never_weakened(config, sample):
    with pytest.raises(ValueError):
        m.gpu_gate(config, sample)


def test_original_gpu_boundaries(config):
    m.gpu_gate(config, gpu(84, 7600))
    config["execution_limits"]["maximum_prelaunch_gpu_mib"] = 1000
    config["execution_limits"]["minimum_free_disk_bytes"] = 1
    m.gpu_gate(config, gpu(60, 1000), baseline=True)
    with pytest.raises(ValueError, match="GPU_RESOURCE_GATE"):
        m.gpu_gate(config, gpu(60, 1001), baseline=True)


@pytest.mark.parametrize("sample", [gpu(85), gpu(40, 7601), gpu(40, 5000, 7999)])
def test_rejected_scalar_sample_durably_retained(tmp_path, monkeypatch, config, sample):
    monkeypatch.setattr(p, "query_gpu", lambda: sample)
    sampler = m.DurableSampler(config, tmp_path / "synthetic.samples.safe.jsonl")
    sampler.stream = sampler.path.open("xb")
    try:
        with pytest.raises(ValueError, match="CONTINUATION_RESOURCE_SAMPLER_FAILED"):
            sampler.observe()
    finally:
        sampler.stream.close()
    saved = p.strict(sampler.path.read_bytes())
    assert saved["observed"] == sample
    assert saved["gate_passed"] is False and saved["error_code"] == "GPU_RESOURCE_GATE"
    assert sampler.failure_code == "GPU_RESOURCE_GATE"


def test_telemetry_error_does_not_invent_failed_temperature(tmp_path, monkeypatch, config):
    def fail():
        raise TimeoutError("synthetic body must not be retained")

    monkeypatch.setattr(p, "query_gpu", fail)
    sampler = m.DurableSampler(config, tmp_path / "samples.safe.jsonl")
    sampler.stream = sampler.path.open("xb")
    try:
        with pytest.raises(ValueError):
            sampler.observe()
    finally:
        sampler.stream.close()
    raw = sampler.path.read_bytes()
    assert b"synthetic body" not in raw
    assert p.strict(raw)["observed"] is None
    assert p.strict(raw)["error_code"] == "TimeoutError"


def test_cooling_requires_60_and_checks_deadline_each_poll(config, amendment, monkeypatch):
    observations = iter([gpu(64), gpu(61), gpu(60)])
    calls = []
    sampler = SimpleNamespace(
        check=lambda: None, observe=lambda **kw: {"observed": next(observations)}
    )
    monkeypatch.setattr(p, "check_deadline", lambda *args: calls.append("deadline"))
    monkeypatch.setattr(m.time, "sleep", lambda seconds: calls.append(seconds))
    sample = m.cool_before_dispatch(config, amendment, sampler, 0)
    assert sample["observed"]["temperature_c"] == 60
    assert calls == ["deadline", 0.5, "deadline", 0.5, "deadline"]


def test_cooling_timeout_has_no_dispatch(config, amendment, monkeypatch):
    clock = iter([0, 180])
    monkeypatch.setattr(m.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(p, "check_deadline", lambda *args: None)
    sampler = SimpleNamespace(check=lambda: None, observe=lambda **kw: {"observed": gpu(61)})
    with pytest.raises(ValueError, match="CONTINUATION_COOLDOWN_TIMEOUT_NO_DISPATCH"):
        m.cool_before_dispatch(config, amendment, sampler, 0)


def test_cooling_deadline_prevents_observation(config, amendment, monkeypatch):
    def expired(*args):
        raise ValueError("DEVELOPMENT_DEADLINE_REACHED_NO_DISPATCH")

    monkeypatch.setattr(p, "check_deadline", expired)
    sampler = SimpleNamespace(check=lambda: pytest.fail("sample after deadline"))
    with pytest.raises(ValueError, match="DEVELOPMENT_DEADLINE"):
        m.cool_before_dispatch(config, amendment, sampler, 0)


@pytest.fixture
def engine(tmp_path, monkeypatch, config, amendment, functions, value):
    """Full synthetic receipt + original parser replay + new lifecycle integration."""
    amendment = loaded(amendment)
    config["panel"]["jailmeter"]["request_timeout_seconds"] = 240
    config["execution_limits"]["maximum_prelaunch_gpu_mib"] = 1000
    config["execution_limits"]["minimum_free_disk_bytes"] = 1
    value["item"]["seed"] = 23
    values = [value]
    plan = {"phase_seed": 23, "rows": [value["item"]]}
    base = c.paths(tmp_path, config["_contract_sha256"])
    base["safe"].mkdir(parents=True)
    inventory = {"synthetic": True}
    events = []

    @contextmanager
    def lock(_):
        events.append("lock")
        try:
            yield
        finally:
            events.append("unlock")

    target = SimpleNamespace(operation_lock=lock)
    monkeypatch.setattr(m, "assert_authority", lambda *args: (base, inventory, target))
    monkeypatch.setattr(p, "preflight", lambda *args: {"model_calls": 0})
    monkeypatch.setattr(p, "load_axis_values", lambda *args: (values, functions, None))
    monkeypatch.setattr(p, "jailmeter_command", lambda *args: ["synthetic-server", "fixed-args"])
    monkeypatch.setattr(m, "verify_safe_prefix", lambda *args: "safe-prefix")

    def owners(*args):
        directory = m.continuation_path(base, amendment, 23, "unused").parent
        return {
            row["request_id"]: row
            for path in directory.glob("*.ownership.safe.json")
            if (row := p.read_json(path))
        }

    monkeypatch.setattr(m, "audit_ownership", owners)
    monkeypatch.setattr(p, "query_gpu", lambda: gpu(40, 500))
    state = {"timeout": None, "after_send": None, "transport_error": None}

    class Client:
        def request(self, route, body, timeout):
            assert route == "/completion" and body == p.request_body(config, value, "jailmeter")
            state["timeout"] = timeout
            events.append("dispatch")
            if state["after_send"]:
                state["after_send"]()
            if state["transport_error"]:
                raise state["transport_error"]
            return c.canonical(
                {
                    "content": "<label>1</label>",
                    "tokens_predicted": 8,
                    "tokens_evaluated": 10,
                    "stopped_limit": False,
                }
            )

    @contextmanager
    def server(root, cfg, amend, pl, bases, *, check_resources):
        check_resources()
        events.append("server-start")
        seed = pl["phase_seed"]
        log = m.continuation_path(bases, amend, seed, "server.log.private.txt", private=True)
        c.write_once(log, b"synthetic private log", raw=True)
        c.write_once(
            m.continuation_path(bases, amend, seed, "server.started.safe.json"),
            {
                **m.epoch_binding(cfg, amend, seed),
                "pid": 9000,
                "command_sha256": c.digest(p.jailmeter_command(root, cfg)),
                "started_at": p.utc(),
            },
        )
        try:
            yield Client(), SimpleNamespace(pid=9000, poll=lambda: None)
        finally:
            c.write_once(
                m.continuation_path(bases, amend, seed, "server.stopped.safe.json"),
                {
                    **m.epoch_binding(cfg, amend, seed),
                    "pid": 9000,
                    "returncode": 1,
                    "stopped_at": p.utc(),
                },
            )
            events.append("server-stop")

    monkeypatch.setattr(m, "continuation_server", server)
    return SimpleNamespace(
        root=tmp_path,
        config=config,
        amendment=amendment,
        plan=plan,
        base=base,
        value=value,
        events=events,
        state=state,
        owners=owners,
        values=values,
        helpers=functions,
    )


def execute(engine):
    return m.run(engine.root, engine.config, engine.amendment, engine.plan)


def test_full_synthetic_run_keeps_parent_schema_and_distinct_axis(engine):
    result = execute(engine)
    assert result["schema_version"] == "jbspan-pa-llama-development-continued-axis-v1"
    assert result["complete"] and result["raw_receipts_reverified"]
    assert result["original_operational_gate_passed"] is False
    assert result["resource_stop_preserved"] and result["operational_deviation_disclosed"]
    assert result["continuation_owned_server_lifecycle"]["new_epoch_resource_gate_passed"]
    assert result["rows"][0]["request_id"] == engine.value["item"]["request_id"]
    assert "execution_amendment_sha256" not in result["rows"][0]
    assert result["rows"][0]["label"] == 1
    assert engine.events == ["lock", "server-start", "dispatch", "server-stop", "unlock"]
    assert not p.owned_path(engine.base, "safe", "phase_23_jailmeter_axis.safe.json").exists()


def test_completed_axis_idempotent_verify_has_no_dispatch(engine, monkeypatch):
    first = execute(engine)
    monkeypatch.setattr(p, "query_gpu", lambda: pytest.fail("verification queried GPU"))
    second = execute(engine)
    assert first == second
    assert engine.events.count("dispatch") == 1


def test_inflight_reply_retained_with_full_240_seconds_after_deadline(engine, monkeypatch):
    expired = {"value": False}

    def deadline(*args, **kwargs):
        if expired["value"]:
            raise ValueError("DEVELOPMENT_DEADLINE_REACHED_NO_DISPATCH")
        return 0.001

    monkeypatch.setattr(p, "check_deadline", deadline)
    engine.state["after_send"] = lambda: expired.update(value=True)
    result = execute(engine)
    assert result["complete"] and engine.state["timeout"] == 240
    assert result["rows"][0]["raw_receipt_sha256"]


def test_ambiguous_transport_not_retried_and_abort_is_separate(engine):
    engine.state["transport_error"] = TimeoutError("private body not in safe receipt")
    with pytest.raises(TimeoutError):
        execute(engine)
    abort = m.continuation_path(engine.base, engine.amendment, 23, "abort.safe.json")
    raw = abort.read_bytes()
    assert b"private body" not in raw and p.strict(raw)["error_code"] == "TimeoutError"
    with pytest.raises(ValueError, match="CONTINUATION_ABORTED_REVIEW_REQUIRED"):
        execute(engine)
    assert engine.events.count("dispatch") == 1
    assert not p.abort_path(engine.base, "jailmeter", 23).exists()


@pytest.mark.parametrize(
    "suffix,private",
    [
        ("server.log.private.txt", True),
        ("server.started.safe.json", False),
        ("server.stopped.safe.json", False),
        ("samples.safe.jsonl", False),
        ("resources.safe.json", False),
    ],
)
def test_attempted_epoch_without_calls_cannot_relaunch(engine, suffix, private):
    path = m.continuation_path(engine.base, engine.amendment, 23, suffix, private=private)
    c.write_once(path, {})
    with pytest.raises(ValueError, match="CONTINUATION_EPOCH_ALREADY_ATTEMPTED_NO_RELAUNCH"):
        execute(engine)
    assert "dispatch" not in engine.events and "server-start" not in engine.events


@pytest.mark.parametrize(
    "mutation",
    [
        "row_label",
        "raw",
        "owner_pid",
        "owner_sample",
        "stop_pid",
        "resource_count",
        "abort",
        "axis_flag",
    ],
)
def test_verified_composite_rejects_tamper(engine, mutation):
    execute(engine)
    rid = engine.value["item"]["request_id"]
    paths = p.axis_paths(engine.base, "jailmeter", rid)
    if mutation == "raw":
        paths["reply"].write_bytes(b"{}")
    elif mutation in (
        "row_label",
        "owner_pid",
        "owner_sample",
        "stop_pid",
        "resource_count",
        "axis_flag",
    ):
        if mutation == "row_label":
            path, key, value = paths["row"], "label", 0
        elif mutation == "owner_pid":
            path, key, value = (
                m.ownership_path(engine.base, engine.amendment, 23, rid),
                "process_id",
                9001,
            )
        elif mutation == "owner_sample":
            path, key, value = (
                m.ownership_path(engine.base, engine.amendment, 23, rid),
                "predispatch_sample_sha256",
                "0" * 64,
            )
        elif mutation == "stop_pid":
            path, key, value = (
                m.continuation_path(engine.base, engine.amendment, 23, "server.stopped.safe.json"),
                "pid",
                9001,
            )
        elif mutation == "resource_count":
            path, key, value = (
                m.continuation_path(engine.base, engine.amendment, 23, "resources.safe.json"),
                "sample_count",
                999,
            )
        else:
            path, key, value = (
                m.result_path(engine.base, 23),
                "original_operational_gate_passed",
                True,
            )
        saved = p.read_json(path)
        saved[key] = value
        path.write_bytes(c.canonical(saved))
    else:
        m.record_abort(engine.base, engine.config, engine.amendment, 23, ValueError("SYNTHETIC"))
    with pytest.raises(ValueError):
        m.verify(engine.root, engine.config, engine.amendment, engine.plan)


def test_original_failure_files_are_never_targeted_by_new_abort(engine):
    original = p.abort_path(engine.base, "jailmeter", 11)
    c.write_once(original, {"original": "immutable failure"})
    before = original.read_bytes()
    m.record_abort(engine.base, engine.config, engine.amendment, 23, ValueError("SYNTHETIC"))
    assert original.read_bytes() == before


def test_skip_only_continuation_never_starts_server(engine, monkeypatch):
    engine.value["skip_reason"] = "TARGET_INELIGIBLE"
    engine.value["target"]["eligible_for_panel"] = False
    monkeypatch.setattr(p, "query_gpu", lambda: pytest.fail("skip-only GPU query"))
    result = execute(engine)
    assert result["skipped"] == 1 and result["dispatched"] == 0
    assert result["continuation_owned_server_lifecycle"] is None
    assert engine.events == ["lock", "unlock"]


def test_parent_validator_is_not_called_with_relabelled_resources():
    source = (SCRIPTS / m.SELF.removeprefix("scripts/")).read_text(encoding="utf-8")
    assert "p.complete_axis(" not in source
    assert "p.axis_result(" not in source
    assert "p.run_jailmeter(" not in source
    assert "p.ResourceSampler(" not in source
    assert "setattr(" not in source


def materialize_synthetic_prefix(tmp_path, amendment):
    base = c.paths(tmp_path, m.PARENT_SHA)
    prefix = f"{c.SAFE_ROOT}/{m.PARENT_SHA}/"
    for index, pin in enumerate(amendment["original_seed11_prefix"]["safe_files"]):
        value = {"synthetic_file": index}
        if pin["path"].endswith("seed-11.abort.safe.json"):
            value = {
                "contract_sha256": m.PARENT_SHA,
                "seed": 11,
                "axis": "jailmeter",
                "error_code": "EVALUATOR_RESOURCE_SAMPLER_FAILED",
                "retry_ambiguous_request": False,
                "review_required": True,
                "recorded_at": "2025-12-31T23:00:00+00:00",
            }
        elif pin["path"].endswith("seed-11.resources.safe.json"):
            value = {"sampled_resources": {"sampler_failure_code": "GPU_RESOURCE_GATE"}}
        raw = c.canonical(value) + b"\n"
        path = p.owned_path(base, "safe", pin["path"][len(prefix) :])
        c.write_once(path, raw, raw=True)
        pin.update(size_bytes=len(raw), sha256=c.sha_bytes(raw))
    return base


def test_all_69_prefix_pins_verified_and_one_byte_change_rejected(tmp_path, amendment):
    base = materialize_synthetic_prefix(tmp_path, amendment)
    assert m.verify_safe_prefix(tmp_path, amendment) == c.digest(
        amendment["original_seed11_prefix"]
    )
    rid = amendment["original_seed11_prefix"]["dispatched_request_ids"][0]
    path = p.axis_paths(base, "jailmeter", rid)["row"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="ORIGINAL_FAILED_PREFIX_CHANGED"):
        m.verify_safe_prefix(tmp_path, amendment)


def test_load_amendment_uses_only_declared_public_safe_pins(tmp_path, amendment, monkeypatch):
    materialize_synthetic_prefix(tmp_path, amendment)
    amendment["required_code"] = {
        "continuation": {"path": m.SELF, "size_bytes": 1, "sha256": "b" * 64},
        "aggregate": {"path": m.AGGREGATE, "size_bytes": 1, "sha256": "b" * 64},
    }
    amendment["original_phase11_plan"]["path"] = (
        f"{c.SAFE_ROOT}/{m.PARENT_SHA}/phase_11_plan.safe.json"
    )
    reads = []

    def verify_pin(root, pin, scopes):
        reads.append(pin["path"])
        return Path(m.__file__).resolve() if pin["path"] == m.SELF else root / pin["path"]

    monkeypatch.setattr(c, "verify_pin", verify_pin)
    raw = c.canonical(amendment) + b"\n"
    c.write_once(tmp_path / m.CONFIG, raw, raw=True)
    observed = m.load_amendment(tmp_path, c.sha_bytes(raw))
    assert observed["_amendment_sha256"] == c.sha_bytes(raw)
    assert len(reads) == 5 and not any("private" in path for path in reads)
    with pytest.raises(ValueError, match="AMENDMENT_SHA_MISMATCH"):
        m.load_amendment(tmp_path, "0" * 64)


@pytest.mark.parametrize("where", ["root", "prefix", "cooling"])
def test_ignored_extra_fields_forbidden(amendment, where):
    node = (
        amendment
        if where == "root"
        else (amendment["original_seed11_prefix"] if where == "prefix" else amendment["cooling"])
    )
    node["raw_prompt"] = "synthetic, never an allowed config field"
    with pytest.raises(ValueError):
        m.validate_amendment(amendment)


def populate_seed11_engine(engine):
    engine.plan["phase_seed"] = 11
    old, skips, pending = m.prefix_ids(engine.amendment)
    all_ids = sorted(old | skips | pending)
    engine.values.clear()
    engine.plan["rows"].clear()
    command_sha = c.digest(p.jailmeter_command(engine.root, engine.config))
    prefix = "panel/jailmeter/seed-11"
    c.write_once(
        p.owned_path(engine.base, "safe", prefix + ".server.started.safe.json"),
        {
            "contract_sha256": engine.config["_contract_sha256"],
            "pid": 5000,
            "seed": 11,
            "command_sha256": command_sha,
            "started_at": p.utc(),
            "owned_process_only": True,
        },
    )
    c.write_once(
        p.owned_path(engine.base, "private", prefix + ".server.log.private.txt"),
        b"synthetic original log",
        raw=True,
    )
    snapshots, expected_labels = {}, {}
    for index, rid in enumerate(all_ids):
        value = copy.deepcopy(engine.value)
        value["item"].update(request_id=rid, seed=11)
        value["skip_reason"] = "TARGET_INELIGIBLE" if rid in skips else None
        if rid in skips:
            value["target"]["eligible_for_panel"] = False
        engine.values.append(value)
        engine.plan["rows"].append(value["item"])
        locations = p.axis_paths(engine.base, "jailmeter", rid)
        if rid in old:
            body = p.request_body(engine.config, value, "jailmeter")
            journal = p.reserve_dispatch(
                engine.config,
                value,
                "jailmeter",
                body,
                locations,
                {"process_id": 5000, "server_command_sha256": command_sha},
            )
            expected_labels[rid] = index % 2
            raw = c.canonical({"content": f"<label>{index % 2}</label>", "tokens_predicted": 8})
            c.write_once(locations["reply"], raw, raw=True)
            row = p.jailmeter_result(engine.config, value, engine.helpers, raw, 0.1, journal)
            c.write_once(locations["row"], row)
        elif rid in skips:
            c.write_once(locations["row"], p.skipped_row(engine.config, value, "jailmeter"))
        for path in locations.values():
            if path.exists():
                snapshots[path] = path.read_bytes()
    c.write_once(
        p.owned_path(engine.base, "safe", prefix + ".server.stopped.safe.json"),
        {
            "contract_sha256": engine.config["_contract_sha256"],
            "pid": 5000,
            "seed": 11,
            "stopped_at": p.utc(),
            "returncode": 1,
            "owned_process_only": True,
        },
    )
    return snapshots, expected_labels


def test_exact_30_complete_and_5_skips_reused_without_one_duplicate(engine):
    snapshots, expected_labels = populate_seed11_engine(engine)
    old, _, _ = m.prefix_ids(engine.amendment)
    result = execute(engine)
    assert result["reused_original_dispatched"] == 30
    assert result["new_continuation_dispatched"] == 55 and result["skipped"] == 5
    assert engine.events.count("dispatch") == 55
    assert len(result["rows"]) == 90 and len(engine.owners()) == 55
    assert {
        row["request_id"]: row["label"] for row in result["rows"] if row["request_id"] in old
    } == expected_labels
    assert all(path.read_bytes() == raw for path, raw in snapshots.items())


def test_disk_floor_checked_before_server_launch(engine, monkeypatch):
    monkeypatch.setattr(m.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match="CONTINUATION_DISK_FLOOR_NO_DISPATCH"):
        execute(engine)
    assert "server-start" not in engine.events and "dispatch" not in engine.events


def test_coherent_resource_rewrite_cannot_remove_baseline(engine):
    execute(engine)
    samples_path = m.continuation_path(engine.base, engine.amendment, 23, "samples.safe.jsonl")
    samples = [p.strict(line) for line in samples_path.read_bytes().splitlines()]
    assert any(sample["baseline"] for sample in samples)
    for sample in samples:
        sample["baseline"] = False
    samples_path.write_bytes(b"".join(c.canonical(sample) + b"\n" for sample in samples))
    summary = m.resource_summary(
        engine.config, engine.amendment, 23, SimpleNamespace(samples=samples, failure_code=None)
    )
    m.continuation_path(engine.base, engine.amendment, 23, "resources.safe.json").write_bytes(
        c.canonical(summary)
    )
    with pytest.raises(ValueError, match="CONTINUATION_PRELAUNCH_BASELINE_PROOF_REQUIRED"):
        m.verify(engine.root, engine.config, engine.amendment, engine.plan)


def test_same_cooling_sample_cannot_authorize_two_requests(engine):
    second = copy.deepcopy(engine.value)
    second["item"]["request_id"] = "c" * 64
    engine.values.append(second)
    engine.plan["rows"].append(second["item"])
    execute(engine)
    first_owner = p.read_json(
        m.ownership_path(engine.base, engine.amendment, 23, engine.value["item"]["request_id"])
    )
    second_path = m.ownership_path(engine.base, engine.amendment, 23, "c" * 64)
    owner = p.read_json(second_path)
    for key in ("predispatch_sample_sequence", "predispatch_sample_sha256"):
        owner[key] = first_owner[key]
    second_path.write_bytes(c.canonical(owner))
    with pytest.raises(ValueError, match="CONTINUATION_STALE_OR_REUSED_COOLING_SAMPLE"):
        m.verify(engine.root, engine.config, engine.amendment, engine.plan)


@pytest.mark.parametrize("mutation", ["missing_original", "replaced_original", "pending_attempt"])
def test_seed11_missing_replaced_or_attempted_prefix_never_dispatches(engine, mutation):
    populate_seed11_engine(engine)
    old, _, pending = m.prefix_ids(engine.amendment)
    rid = sorted(pending if mutation == "pending_attempt" else old)[0]
    paths = p.axis_paths(engine.base, "jailmeter", rid)
    if mutation == "missing_original":
        paths["row"].unlink()  # Only this test's synthetic temporary receipt.
    elif mutation == "replaced_original":
        row = p.read_json(paths["row"])
        row["label"] = 1 - row["label"]
        paths["row"].write_bytes(c.canonical(row))
    else:
        c.write_once(paths["dispatch"], {"synthetic_ambiguous_attempt": True})
    with pytest.raises(ValueError):
        execute(engine)
    assert "dispatch" not in engine.events and "server-start" not in engine.events


@pytest.mark.parametrize(
    "case", ["valid", "unowned", "orphan", "old_claimed", "duplicate", "ceiling"]
)
def test_direct_global_ownership_census(tmp_path, config, amendment, monkeypatch, case):
    amendment = loaded(amendment)
    base = c.paths(tmp_path, config["_contract_sha256"])
    old, _, _ = m.prefix_ids(amendment)
    for rid in old:
        c.write_once(p.axis_paths(base, "jailmeter", rid)["dispatch"], {})
    rid = "b" * 64
    if case in {"valid", "unowned", "duplicate", "ceiling"}:
        c.write_once(p.axis_paths(base, "jailmeter", rid)["dispatch"], {})
    if case != "unowned":
        owner_id = sorted(old)[0] if case == "old_claimed" else rid
        c.write_once(
            m.ownership_path(base, amendment, 23, owner_id), {"request_id": owner_id, "seed": 23}
        )
        if case == "duplicate":
            c.write_once(
                m.ownership_path(base, amendment, 47, owner_id),
                {"request_id": owner_id, "seed": 47},
            )
    monkeypatch.setattr(
        p,
        "global_panel_receipt_check",
        lambda *args: {"jailmeter": 271 if case == "ceiling" else 31},
    )
    if case == "valid":
        assert set(m.audit_ownership(tmp_path, config, amendment, {})) == {rid}
    else:
        with pytest.raises(ValueError):
            m.audit_ownership(tmp_path, config, amendment, {})
