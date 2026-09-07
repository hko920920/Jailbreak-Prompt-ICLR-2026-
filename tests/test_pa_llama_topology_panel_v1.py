"""Pure synthetic frames and temporary new receipts; no GPU/model/corpus reads."""

import copy
import importlib.util
import sys
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pa_llama_topology_panel_v1 as m  # noqa: E402
import pa_llama_topology_plan_v1 as plan_module  # noqa: E402

c, low = m.c, m.low
SPEC = importlib.util.spec_from_file_location(
    "topology_synthetic_qualified_fixtures",
    SCRIPTS.parent / "tests/test_pa_llama_development_panel_v1.py",
)
OLD_TESTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OLD_TESTS)
config, functions = OLD_TESTS.config, OLD_TESTS.functions


@pytest.fixture
def frame(config, functions):
    payload = "Synthetic harmless question."
    population = [
        {
            "payload_position": 0,
            "payload_sha256": c.sha_bytes(payload.encode()),
            "prompt_sha256": "1" * 64,
            "unit_manifest_sha256": "2" * 64,
            "fragment_manifest_sha256": "3" * 64,
        }
    ]
    requests, _ = plan_module._schedule("4" * 64, population)
    plan = {
        "requests": requests,
        "population": population,
        "n": 1,
        "plan_identity_sha256": "5" * 64,
        "parent_operational_amendment_disclosure": {
            "original_seed11_jailmeter_operational_gate_passed": False
        },
    }
    config.update(
        schema_version="jbspan-pa-llama-topology-execution-v1",
        frozen=True,
        execution_authorized=True,
        paper_validity=False,
        panel_cooldown=copy.deepcopy(m.COOLDOWN),
        frozen_at_utc="2026-01-01T00:00:00+00:00",
        budgets={"qwen_calls": 42, "jailmeter_calls": 42},
    )
    config["panel"]["jailmeter"]["request_timeout_seconds"] = 240
    config["execution_limits"].update(minimum_free_disk_bytes=1, maximum_prelaunch_gpu_mib=1000)
    targets, raw = [], {}
    science_index = 0
    for item in requests:
        content = "  Synthetic answer\r\nwith two lines.  "
        response = c.normalize_response(content)
        reply = c.canonical({"choices": [{"message": {"content": content}}]})
        eligible = item["kind"] == "science" and science_index < 2
        target = {
            **item,
            "contract_sha256": config["_contract_sha256"],
            "eligible_for_panel": eligible,
            "eligible_for_control": item["kind"] == "control",
            "request_sha256": c.digest(item),
            "raw_reply_sha256": c.sha_bytes(reply),
            "content_sha256": c.sha_bytes(content.encode()),
            "response_sha256": c.sha_bytes(response.encode()),
        }
        targets.append(target)
        if item["kind"] == "science":
            raw[item["request_id"]] = reply
            science_index += 1
    return SimpleNamespace(
        config=config,
        plan=plan,
        targets=targets,
        payloads={0: payload},
        raw=raw,
        helpers=functions,
        tokenizer=OLD_TESTS.Tokenizer(),
    )


def prepared(frame, axis):
    return m.prepare_values(
        frame.config,
        frame.plan,
        frame.targets,
        frame.payloads,
        frame.raw,
        frame.helpers,
        frame.tokenizer,
        axis,
        "Synthetic system",
    )


@pytest.mark.parametrize("axis", low.AXES)
def test_exact42_science_rows_never_controls_and_original_p(frame, axis):
    values = prepared(frame, axis)
    assert len(values) == 42 and len(frame.targets) == 70
    assert all(value["topology_item"]["kind"] == "science" for value in values)
    assert all(value["record"].goal_text == frame.payloads[0] for value in values)
    assert all(
        value["record"].response_text == "Synthetic answer\nwith two lines." for value in values
    )
    assert sum(value["skip_reason"] is None for value in values) == 2
    assert values[0]["item"]["condition"].startswith("TOPOLOGY_SCIENCE:")
    assert "condition" not in values[0]["topology_item"]


@pytest.mark.parametrize(
    "mutation",
    [
        "payload",
        "control_raw",
        "missing_target",
        "target_reorder",
        "raw_hash",
        "normalized_hash",
        "item",
        "target_control",
        "missing_science",
        "wrong_axis",
    ],
)
def test_input_binding_mutations_fail(frame, mutation):
    science = next(row for row in frame.targets if row["kind"] == "science")
    axis = "qwen"
    if mutation == "payload":
        frame.payloads[0] += " modified"
    elif mutation == "control_raw":
        frame.raw[next(row["request_id"] for row in frame.targets if row["kind"] == "control")] = (
            b"{}"
        )
    elif mutation == "missing_target":
        frame.targets.pop()
    elif mutation == "target_reorder":
        frame.targets.reverse()
    elif mutation == "raw_hash":
        frame.raw[science["request_id"]] += b" "
    elif mutation == "normalized_hash":
        science["response_sha256"] = "0" * 64
    elif mutation == "item":
        science["mask"] = 7
    elif mutation == "target_control":
        science["eligible_for_control"] = True
    elif mutation == "missing_science":
        frame.plan["requests"].pop(0)
    else:
        axis = "invalid"
    with pytest.raises(ValueError):
        prepared(frame, axis)


def test_context_skip_preserves_all_rows(frame):
    frame.config["execution_limits"]["jailmeter_context_tokens"] = 1536
    values = prepared(frame, "jailmeter")
    assert len(values) == 42
    assert [value["skip_reason"] for value in values[:2]] == ["EVALUATOR_CONTEXT_BOUND"] * 2


@pytest.fixture
def engine(tmp_path, monkeypatch, frame):
    paths = {kind: tmp_path / kind for kind in ("safe", "private")}
    for path in paths.values():
        path.mkdir()
    events, state = [], {"error": None}

    @contextmanager
    def operation(name):
        events.append("lock:" + name)
        try:
            yield
        finally:
            events.append("unlock:" + name)

    target = SimpleNamespace(
        root=tmp_path, paths=paths, config=frame.config, plan=frame.plan, operation=operation
    )
    panel = m.TopologyPanel(target, frame.payloads)
    monkeypatch.setattr(
        panel, "load", lambda axis: (prepared(frame, axis), frame.helpers, frame.tokenizer)
    )
    monkeypatch.setattr(low, "jailmeter_command", lambda *args: ["synthetic.exe", "fixed"])
    monkeypatch.setattr(
        low,
        "query_gpu",
        lambda: {
            "name": "NVIDIA GeForce RTX 3070",
            "used_mib": 500,
            "total_mib": 8192,
            "temperature_c": 40,
        },
    )

    @contextmanager
    def worker(axis, tokenizer, sampler):
        sampler.check()
        events.append("start:" + axis)
        command = low.jailmeter_command(tmp_path, frame.config) if axis == "jailmeter" else None
        start = {
            **panel.worker_binding(axis),
            "pid": 7000,
            "started_at": low.utc(),
            "command_sha256": c.digest(command) if command else None,
            "in_process_model": axis == "qwen",
        }
        c.write_once(panel.path(axis, "worker.started.safe.json"), start)
        c.write_once(
            panel.path(axis, "worker.log.private.txt", private=True), b"synthetic log", raw=True
        )

        def call(value, body):
            assert value["topology_item"]["kind"] == "science"
            assert c.same(body, low.request_body(frame.config, value, axis))
            events.append("call:" + axis)
            if state["error"]:
                raise state["error"]
            content = "Safety: Unsafe\nRefusal: No" if axis == "qwen" else "<label>1</label>"
            raw = (
                {"content": content, "output_ids": [ord(char) for char in content]}
                if axis == "qwen"
                else {"content": content, "tokens_predicted": 8, "tokens_evaluated": 10}
            )
            return c.canonical(raw) + b"\n"

        try:
            yield SimpleNamespace(
                pid=7000, command_sha256=start["command_sha256"], call=call, alive=lambda: True
            )
        finally:
            c.write_once(
                panel.path(axis, "worker.stopped.safe.json"),
                {
                    **panel.worker_binding(axis),
                    "pid": 7000,
                    "stopped_at": low.utc(),
                    "model_released": True,
                    "owned_server_stopped": axis == "jailmeter",
                    "returncode": 1 if axis == "jailmeter" else None,
                    "peak_cuda_allocated_bytes": 1000 if axis == "qwen" else None,
                },
            )
            events.append("stop:" + axis)

    monkeypatch.setattr(panel, "worker", worker)
    return SimpleNamespace(panel=panel, frame=frame, events=events, state=state)


@pytest.mark.parametrize("axis", low.AXES)
def test_full_synthetic_axis_skips_receipts_and_readonly_verification(engine, axis, monkeypatch):
    result = engine.panel.run(axis)
    assert result["complete"] and result["planned_records"] == 42
    assert result["dispatched"] == 2 and result["skipped"] == 40
    assert result["controls_judged"] == 0 and result["raw_receipts_reverified"]
    assert (
        result["parent_operational_amendment_disclosure"][
            "original_seed11_jailmeter_operational_gate_passed"
        ]
        is False
    )
    monkeypatch.setattr(low, "query_gpu", lambda: pytest.fail("verify queried GPU"))
    assert engine.panel.verify(axis) == result
    assert engine.panel.run(axis) == result
    assert engine.events.count("call:" + axis) == 2


@pytest.mark.parametrize("axis", low.AXES)
def test_all42_eligible_requests_no_early_stop(engine, axis):
    for row in engine.frame.targets:
        if row["kind"] == "science":
            row["eligible_for_panel"] = True
    result = engine.panel.run(axis)
    assert result["dispatched"] == 42 and result["skipped"] == 0
    assert engine.events.count("call:" + axis) == 42


@pytest.mark.parametrize("axis", low.AXES)
def test_all_skips_never_query_gpu_or_start_worker(engine, axis, monkeypatch):
    for row in engine.frame.targets:
        row["eligible_for_panel"] = False
    monkeypatch.setattr(low, "query_gpu", lambda: pytest.fail("skip-only GPU"))
    result = engine.panel.run(axis)
    assert result["dispatched"] == 0 and result["skipped"] == 42
    assert result["worker_proof"] is None
    assert "start:" + axis not in engine.events


@pytest.mark.parametrize("axis", low.AXES)
def test_ambiguous_call_stops_without_retry(engine, axis):
    engine.state["error"] = TimeoutError("private transport body")
    with pytest.raises(TimeoutError):
        engine.panel.run(axis)
    abort = engine.panel.path(axis, "abort.safe.json").read_bytes()
    assert b"private transport body" not in abort
    assert low.strict(abort)["retry_ambiguous_request"] is False
    with pytest.raises(ValueError, match="TOPOLOGY_PANEL_ABORTED_NO_RETRY"):
        engine.panel.run(axis)
    assert engine.events.count("call:" + axis) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "row",
        "reply",
        "owner_item",
        "owner_pid",
        "stop_pid",
        "resources",
        "baseline",
        "reused_sample",
        "cuda",
        "control",
    ],
)
def test_full_raw_and_lifecycle_tamper_rejected(engine, mutation):
    axis = "qwen"
    engine.panel.run(axis)
    rows = [value for value in prepared(engine.frame, axis) if value["skip_reason"] is None]
    rid = rows[0]["item"]["request_id"]
    paths = low.axis_paths(engine.panel.paths, axis, rid)
    if mutation == "reply":
        paths["reply"].write_bytes(b"{}")
    elif mutation == "baseline":
        path = engine.panel.path(axis, "samples.safe.jsonl")
        samples = [low.strict(line) for line in path.read_bytes().splitlines()]
        for sample in samples:
            sample["baseline"] = False
        path.write_bytes(b"".join(c.canonical(sample) + b"\n" for sample in samples))
        summary = engine.panel.resources(axis, SimpleNamespace(samples=samples, failure_code=None))
        engine.panel.path(axis, "resources.safe.json").write_bytes(c.canonical(summary))
    elif mutation == "control":
        control = next(row for row in engine.frame.plan["requests"] if row["kind"] == "control")
        c.write_once(
            low.axis_paths(engine.panel.paths, axis, control["request_id"])["dispatch"], {}
        )
    elif mutation == "reused_sample":
        first = low.read_json(engine.panel.path(axis, rid + ".ownership.safe.json"))
        path = engine.panel.path(axis, rows[1]["item"]["request_id"] + ".ownership.safe.json")
        second = low.read_json(path)
        second.update({key: first[key] for key in ("sample_sequence", "sample_sha256")})
        path.write_bytes(c.canonical(second))
    else:
        if mutation == "row":
            path, key, replacement = paths["row"], "safety", "Safe"
        elif mutation in {"owner_item", "owner_pid"}:
            path = engine.panel.path(axis, rid + ".ownership.safe.json")
            key, replacement = (
                ("topology_item", {}) if mutation == "owner_item" else ("process_id", 7001)
            )
        elif mutation == "resources":
            path, key, replacement = (
                engine.panel.path(axis, "resources.safe.json"),
                "sample_count",
                999,
            )
        else:
            path = engine.panel.path(axis, "worker.stopped.safe.json")
            key, replacement = (
                ("pid", 7001) if mutation == "stop_pid" else ("peak_cuda_allocated_bytes", 2**40)
            )
        value = low.read_json(path)
        value[key] = replacement
        path.write_bytes(c.canonical(value))
    with pytest.raises(ValueError):
        engine.panel.verify(axis)


@pytest.mark.parametrize(
    "name,private",
    [
        ("worker.log.private.txt", True),
        ("worker.started.safe.json", False),
        ("worker.stopped.safe.json", False),
        ("samples.safe.jsonl", False),
        ("resources.safe.json", False),
    ],
)
def test_no_attempted_worker_relaunch(engine, name, private):
    c.write_once(engine.panel.path("qwen", name, private=private), {})
    with pytest.raises(ValueError, match="TOPOLOGY_PANEL_EPOCH_ATTEMPTED_NO_RELAUNCH"):
        engine.panel.run("qwen")
    assert "start:qwen" not in engine.events


def test_no_parent_highlevel_reader_path_or_implicit_authority():
    source = (SCRIPTS / "pa_llama_topology_panel_v1.py").read_text(encoding="utf-8")
    for forbidden in (
        "c.paths(",
        "low.new_records(",
        "low.run_qwen(",
        "low.run_jailmeter(",
        "low.verify_axis(",
        "thermal.assert_authority(",
        "setattr(",
    ):
        assert forbidden not in source


def test_target_operational_failure_blocks_load_before_any_private_read(engine, monkeypatch):
    target = engine.panel.target
    target.load_materials = lambda: {}
    target.load_census = lambda prompts: {}
    target.reconcile = lambda prompts, census: engine.frame.targets
    target.summary = lambda rows: {"complete": True, "operational_gate_passed": False}
    monkeypatch.setattr(low, "preflight", lambda *args: None)
    monkeypatch.setattr(
        low, "read_bytes", lambda *args, **kwargs: pytest.fail("read after failed target")
    )
    with pytest.raises(ValueError, match="TOPOLOGY_TARGET_OPERATIONAL_FAILURE_NO_PANEL"):
        m.TopologyPanel.load(engine.panel, "qwen")


def test_incomplete_target_blocks_load_before_any_private_read(engine, monkeypatch):
    target = engine.panel.target
    target.load_materials = lambda: {}
    target.load_census = lambda prompts: {}
    target.reconcile = lambda prompts, census: engine.frame.targets[:-1]
    monkeypatch.setattr(low, "preflight", lambda *args: None)
    monkeypatch.setattr(
        low, "read_bytes", lambda *args, **kwargs: pytest.fail("read incomplete frame")
    )
    with pytest.raises(ValueError, match="TOPOLOGY_ALL_TARGETS_REQUIRED_BEFORE_PANEL"):
        m.TopologyPanel.load(engine.panel, "qwen")


def test_actual_load_success_reads_only_science_and_uses_original_p(engine, monkeypatch):
    target, observed = engine.panel.target, []
    target.load_materials = lambda: {"synthetic_material": "synthetic ablated prompt, not P"}
    target.load_census = lambda prompts: {"synthetic_census": True}
    target.reconcile = lambda prompts, census: engine.frame.targets
    target.summary = lambda rows: {"complete": True, "operational_gate_passed": True}

    def path(kind, relative):
        assert kind == "private" and relative.startswith("target/")
        observed.append(relative)
        return low.owned_path(target.paths, kind, relative)

    target.path = path
    for rid, raw in engine.frame.raw.items():
        c.write_once(path("private", f"target/{rid}.reply.private.json"), raw, raw=True)
    observed.clear()
    engine.panel.config["panel"]["qwen"]["model_local_path"] = "synthetic/tokenizer"
    target.config = copy.deepcopy(engine.panel.config)
    monkeypatch.setattr(low, "preflight", lambda *args: None)
    monkeypatch.setattr(low, "load_pure_functions", lambda *args: engine.frame.helpers)

    def tokenizer(directory, **kwargs):
        assert kwargs == {"local_files_only": True}
        return engine.frame.tokenizer

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=tokenizer)),
    )
    values, helpers, token = m.TopologyPanel.load(engine.panel, "qwen")
    assert len(values) == len(observed) == 42
    assert set(observed) == {f"target/{rid}.reply.private.json" for rid in engine.frame.raw}
    assert all(value["record"].goal_text == engine.frame.payloads[0] for value in values)
    assert helpers is engine.frame.helpers and token is engine.frame.tokenizer


@pytest.mark.parametrize("key,value", [("max_new_tokens", 127), ("do_sample", True)])
def test_qwen_numerical_settings_cannot_change(engine, key, value):
    engine.panel.target.config["panel"]["qwen"][key] = value
    with pytest.raises(ValueError, match="TOPOLOGY_QUALIFIED_EVALUATOR_NUMERICS_CHANGED"):
        m.TopologyPanel(engine.panel.target, engine.frame.payloads)


@pytest.mark.parametrize(
    "key,value", [("max_new_tokens", 1535), ("temperature", 0.1), ("request_timeout_seconds", 239)]
)
def test_jailmeter_numerical_settings_cannot_change(engine, key, value):
    engine.panel.target.config["panel"]["jailmeter"][key] = value
    with pytest.raises(ValueError, match="TOPOLOGY_QUALIFIED_EVALUATOR_NUMERICS_CHANGED"):
        m.TopologyPanel(engine.panel.target, engine.frame.payloads)


@pytest.mark.parametrize("axis", low.AXES)
def test_cool_uses_correct_axis_phase_deadline(frame, monkeypatch, axis):
    calls, readings = [], iter([65, 60])
    monkeypatch.setattr(low, "check_deadline", lambda cfg, ax, started: calls.append(ax))
    monkeypatch.setattr(m.time, "sleep", lambda seconds: calls.append(seconds))
    sampler = SimpleNamespace(
        check=lambda: None, observe=lambda **kw: {"observed": {"temperature_c": next(readings)}}
    )
    assert m.cool(frame.config, axis, sampler, 0)["observed"]["temperature_c"] == 60
    assert calls == [axis, 0.5, axis]


class Vector(list):
    def __getitem__(self, value):
        result = super().__getitem__(value)
        return Vector(result) if isinstance(value, slice) else result

    def tolist(self):
        return list(self)


class Encoded(dict):
    def __init__(self, length):
        self.input_ids = SimpleNamespace(shape=(1, length))
        super().__init__(input_ids=self.input_ids)

    def to(self, device):
        assert device == "cuda:0"
        return self


def test_real_qwen_worker_with_fake_torch_checks_dtype_generation_and_cleanup(engine, monkeypatch):
    calls = []
    value = prepared(engine.frame, "qwen")[0]
    content = "Safety: Safe\nRefusal: Yes"

    class Tokenizer(OLD_TESTS.Tokenizer):
        def __call__(self, texts, return_tensors):
            assert texts == [value["prompt"]["prompt"]] and return_tensors == "pt"
            return Encoded(value["prompt"]["input_tokens"])

    class Model:
        def to(self, device):
            calls.append(("model_to", device))
            return self

        def eval(self):
            calls.append("eval")

        def generate(self, **kwargs):
            assert kwargs["do_sample"] is False and kwargs["max_new_tokens"] == 128
            assert kwargs["pad_token_id"] == Tokenizer.eos_token_id
            calls.append("generate")
            return [Vector([0] * value["prompt"]["input_tokens"] + [ord(char) for char in content])]

    def load_model(path, **kwargs):
        assert kwargs == {
            "dtype": "synthetic-float16",
            "local_files_only": True,
            "low_cpu_mem_usage": True,
        }
        calls.append("load-fp16")
        return Model()

    cuda = SimpleNamespace(
        init=lambda: calls.append("cuda_init"),
        set_device=lambda n: calls.append(("cuda_device", n)),
        empty_cache=lambda: calls.append("empty_cache"),
        reset_peak_memory_stats=lambda n: calls.append("reset_peak"),
        max_memory_allocated=lambda n: 1000,
    )
    torch = SimpleNamespace(
        cuda=cuda,
        float16="synthetic-float16",
        device=lambda device: device,
        inference_mode=nullcontext,
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoModelForCausalLM=SimpleNamespace(from_pretrained=load_model)),
    )
    engine.panel.config["panel"]["qwen"]["model_local_path"] = "synthetic/model"
    sampler = SimpleNamespace(check=lambda: calls.append("resource-check"))
    with m.TopologyPanel.worker(engine.panel, "qwen", Tokenizer(), sampler) as worker:
        raw = worker.call(value, low.request_body(engine.panel.config, value, "qwen"))
        assert low.strict(raw) == {
            "content": content,
            "output_ids": [ord(char) for char in content],
        }
        assert worker.alive()
    stop = low.read_json(engine.panel.path("qwen", "worker.stopped.safe.json"))
    assert stop["peak_cuda_allocated_bytes"] == 1000 and stop["model_released"] is True
    assert stop["owned_server_stopped"] is False and stop["returncode"] is None
    assert calls.count("empty_cache") == 2 and calls.count("generate") == 1


@pytest.mark.parametrize("fail_health", [False, True])
def test_real_jailmeter_context_owns_cleanup_and_fixed_timeout(engine, monkeypatch, fail_health):
    events, captured = [], {}
    runtime = engine.panel.config["panel"]["jailmeter"]
    runtime.update(
        host="127.0.0.1", port=18082, runtime_directory="synthetic", health_timeout_seconds=1
    )

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def setsockopt(self, *args):
            pass

        def bind(self, address):
            assert address == ("127.0.0.1", 18082)

    class Process:
        pid, returncode = 8123, None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 1
            events.append("terminate-owned")

        def wait(self, timeout):
            assert timeout == 15

    process = Process()

    def popen(command, **kwargs):
        assert command == ["synthetic.exe", "fixed"]
        captured.update(kwargs)
        events.append("spawn-owned")
        return process

    class Client:
        def __init__(self, port):
            assert port == 18082

        def request(self, route, body=None, timeout=2):
            events.append(route)
            if route == "/health":
                return b'{"status":"ok"}'
            assert timeout == 240
            return b'{"content":"<label>0</label>","tokens_predicted":8}'

    checks = []

    def check():
        checks.append(True)
        if fail_health and len(checks) == 2:
            raise ValueError("CONTINUATION_RESOURCE_SAMPLER_FAILED")

    monkeypatch.setattr(m.socket, "socket", lambda *args: Socket())
    monkeypatch.setattr(m.subprocess, "Popen", popen)
    monkeypatch.setattr(low, "LocalJailmeter", Client)
    monkeypatch.setenv("HTTPS_PROXY", "http://synthetic.invalid")
    monkeypatch.setenv("LLAMA_ARG_PROMPT", "synthetic hidden override")
    sampler = SimpleNamespace(check=check)
    if fail_health:
        with pytest.raises(ValueError, match="CONTINUATION_RESOURCE_SAMPLER_FAILED"):
            with m.TopologyPanel.worker(engine.panel, "jailmeter", None, sampler):
                pytest.fail("worker yielded after resource failure")
    else:
        with m.TopologyPanel.worker(engine.panel, "jailmeter", None, sampler) as worker:
            raw = worker.call(None, {"prompt": "synthetic"})
            assert low.strict(raw)["content"] == "<label>0</label>"
    assert events[0] == "spawn-owned" and events[-1] == "terminate-owned"
    assert "HTTPS_PROXY" not in captured["env"] and "LLAMA_ARG_PROMPT" not in captured["env"]
    assert low.read_json(engine.panel.path("jailmeter", "worker.stopped.safe.json"))["pid"] == 8123
