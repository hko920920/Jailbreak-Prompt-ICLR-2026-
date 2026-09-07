"""Synthetic tiny schedules, fake clients/processes, and NEW temporary receipt trees only."""

import ast
import copy
import importlib.util
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "synthetic_topology_target", SCRIPTS / "pa_llama_topology_target_v1.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
c, p = m.c, m.p
STAMPS = count()


def reply(config, *, content="Synthetic full answer", cap=512, finish="stop", prompt=12, used=5):
    return c.canonical(
        {
            "model": config["model"]["alias"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish,
                }
            ],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": used,
                "total_tokens": prompt + used,
            },
        }
    )


def stamp():
    return (
        datetime(2026, 9, 5, 18, tzinfo=timezone.utc) + timedelta(milliseconds=next(STAMPS))
    ).isoformat()


def gpu(temperature=50, used=500):
    return {
        "gpu_name": m.low.GPU_NAME,
        "gpu_total_mib": 8192,
        "gpu_used_mib": used,
        "gpu_temperature_c": temperature,
        "sampled_at": stamp(),
    }


@pytest.fixture
def engine(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("t")
    monkeypatch.setattr(p, "validate_plan", lambda plan, **context: True)
    monkeypatch.setattr(m.low, "check_deadline", lambda config: None)
    monkeypatch.setattr(m.low, "gpu_sample", lambda: gpu())
    monkeypatch.setattr(m.shutil, "disk_usage", lambda path: SimpleNamespace(free=20 * 1024**3))
    config = {
        "schema_version": m.SCHEMA,
        "frozen": True,
        "execution_authorized": True,
        "paper_validity": False,
        "_contract_sha256": "d" * 64,
        "parent_screen_contract_sha256": p.SCREEN_SHA256,
        "model": {"alias": "synthetic-owned", "entry_path": "runtime/model.gguf"},
        "runtime": {
            "server": {"path": "runtime/server.exe"},
            "server_args": [],
            "native_chat_template_sha256": "a" * 64,
            "served_chat_template_sha256": "b" * 64,
            "served_chat_template_utf8_bytes": 12,
        },
        "server": {
            "host": "127.0.0.1",
            "port": 18087,
            "request_timeout_seconds": 240,
            "startup_timeout_seconds": 1,
        },
        "panel": {"synthetic": True},
        "software": {"synthetic": "1"},
        "execution_limits": dict(p.LIMITS),
        "cooldown": copy.deepcopy(m.COOLDOWN),
        "paths": {"safe_root": m.SAFE_ROOT, "private_root": m.PRIVATE_ROOT},
    }
    materials, requests = [], []
    for index, kind in enumerate(("science", "control")):
        prompt = f"Harmless synthetic material {index}."
        mid = c.digest(["material", index])
        materials.append(
            {
                "materialization_id": mid,
                "kind": kind,
                "renderer_row": {
                    "prompt_sha256": c.sha_bytes(prompt.encode()),
                    "prompt_utf8_bytes": len(prompt.encode()),
                },
            }
        )
        seeds = (11, 23, 47) if kind == "science" else (17,)
        for seed in seeds:
            requests.append(
                {
                    "ordinal": len(requests) + 1,
                    "materialization_id": mid,
                    "request_id": c.digest([mid, seed]),
                    "kind": kind,
                    "payload_position": 3,
                    "mask": 1,
                    "operator": p.OPERATORS[0],
                    "task_id": None if kind == "science" else p.TASKS[0],
                    "seed": seed,
                    "payload_sha256": "e" * 64,
                    "generation": {**p.SCIENCE_GENERATION, "seed": seed}
                    if kind == "science"
                    else dict(p.CONTROL_GENERATION),
                    "panel_evaluation_required": kind == "science",
                }
            )
    plan = {
        "materializations_bound": True,
        "plan_identity_sha256": "f" * 64,
        "requests": requests,
        "bound_materializations": materials,
        "metadata_requests": p.metadata_plan(materials),
        "execution_limits": dict(p.LIMITS),
        "metadata_field_contract": {
            "science": {"native_prompt_tokens_max": 3584},
            "control": {"native_prompt_tokens_max": 4048},
        },
        "budgets": {
            "total_target_calls": 4,
            "scientific_target_calls": 3,
            "control_target_calls": 1,
            "metadata_post_calls": 6,
        },
        "prospective_runtime_identity_sha256": c.digest(
            {key: config[key] for key in ("model", "runtime", "server", "panel", "software")}
        ),
    }
    config.update(bound_plan_identity_sha256=plan["plan_identity_sha256"], budgets=plan["budgets"])
    state = SimpleNamespace(
        calls=[],
        metadata=[],
        epochs=0,
        stops=0,
        transport_error=False,
        wrong_usage=False,
        finish="stop",
        content="A full synthetic answer",
    )

    class Process:
        pid = 700

        def poll(self):
            return None

    class Client:
        def get(self, route):
            return {"default_generation_settings": {"n_ctx": 4096}}

        def request(self, route, body, *, timeout):
            rid = next(item["request_id"] for item in requests if item["seed"] == body["seed"])
            assert worker.path("safe", f"target/{rid}.dispatch.safe.json").exists()
            state.calls.append((route, copy.deepcopy(body), timeout))
            if state.transport_error:
                raise OSError("Synthetic transport failure")
            return reply(
                config,
                content=state.content,
                finish=state.finish,
                prompt=99 if state.wrong_usage else 12,
            )

    def check_identity(process, client, config, observer=None):
        if observer:
            observer({"process_id": process.pid, "synthetic_identity": True})
        return {"served_chat_template_sha256": config["runtime"]["served_chat_template_sha256"]}

    def verify_template(config, sha, path, context):
        value = m.read_json(path)
        assert value["contract_sha256"] == sha
        assert all(c.same(value[key], val) for key, val in context.items())

    @contextmanager
    def owned_server(root, config, private, safe, epoch, sha):
        state.epochs += 1
        process = Process()
        process.pid += state.epochs
        start = {
            "contract_sha256": sha,
            "epoch": epoch,
            "pid": process.pid,
            "owned_process_only": True,
            "started_at": stamp(),
            "command_sha256": c.digest(m.low.command_for(root, config)),
        }
        c.write_once(safe / "server-01.started.safe.json", start)
        c.write_once(safe / "server-01.identity.safe.json", start)
        c.write_once(safe / "server-01.tpl.safe.json", {**start, "process_id": process.pid})
        try:
            yield process, Client(), {}
        finally:
            state.stops += 1
            c.write_once(
                safe / "server-01.stopped.safe.json",
                {
                    "contract_sha256": sha,
                    "epoch": epoch,
                    "pid": process.pid,
                    "owned_process_only": True,
                    "stopped_at": stamp(),
                    "returncode": 0,
                },
            )

    def post(client, config, route, body):
        state.metadata.append((route, copy.deepcopy(body)))
        assert len(list(worker.path("safe", "metadata").glob("*.dispatch.safe.json"))) == len(
            state.metadata
        )
        if route == "/apply-template":
            return c.canonical({"prompt": "CHAT " + body["messages"][0]["content"]})
        return c.canonical(
            {"tokens": list(range(12 if body["content"].startswith("CHAT ") else 10))}
        )

    monkeypatch.setattr(m.low, "metadata_request", post)
    helper = SimpleNamespace(
        owned_server=owned_server,
        check_identity=check_identity,
        verify_template_observation=verify_template,
        utc_now=stamp,
        emit=lambda *args, **kwargs: None,
    )
    worker = m.TopologyTarget(root, config, plan, {}, helper=helper)
    prepared = {
        "bound_plan": plan,
        "private_materializations": {
            "rows": [
                {
                    "materialization_id": material["materialization_id"],
                    "prompt": f"Harmless synthetic material {index}.",
                }
                for index, material in enumerate(materials)
            ]
        },
        "new_screen_input_sha256": "9" * 64,
        "historical_private_reads": 0,
        "model_calls": 0,
        "execution_authorized": False,
    }
    worker.stage(prepared)
    return worker, state, prepared


def test_module_has_no_historical_reader_or_parent_highlevel_calls():
    tree = ast.parse((SCRIPTS / "pa_llama_topology_target_v1.py").read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "load_contract",
        "load_inputs",
        "prepare_inputs",
        "phase_for",
        "run_phase",
        "extract_input",
        "source_inventory",
        "paths",
        "system",
    }


def test_complete_native_census_and_target_schedule_no_extra_calls(engine):
    worker, state, _ = engine
    census = worker.census()
    assert census["metadata_post_requests"] == len(state.metadata) == 6
    assert not state.calls
    result = worker.generate()
    assert result["complete"] is True and len(state.calls) == 4
    assert result["science_records"] == 3 and result["control_records"] == 1
    assert result["scientific_gate_evaluated"] is False and result["paper_validity"] is False
    assert state.epochs == state.stops == 2
    assert worker.generate() == result
    assert worker.census() == census
    assert worker.status() == result
    assert len(state.calls) == 4 and len(state.metadata) == 6


def test_exact_per_kind_generation_and_fixed_inflight_timeout(engine):
    worker, state, _ = engine
    worker.census()
    worker.generate()
    for (route, body, timeout), item in zip(state.calls, worker.plan["requests"], strict=True):
        assert route == "/v1/chat/completions" and timeout == 240
        assert body["messages"][0]["role"] == "user" and len(body["messages"]) == 1
        assert {key: body[key] for key in item["generation"]} == item["generation"]
        assert set(body) == {"model", "messages", "stream"} | set(item["generation"])


@pytest.mark.parametrize("finish,content", [("length", "Full partial answer"), ("stop", "  ")])
def test_content_failures_continue_whole_frozen_schedule(engine, finish, content):
    worker, state, _ = engine
    worker.census()
    state.finish, state.content = finish, content
    result = worker.generate()
    assert len(state.calls) == 4 and result["complete"] is True
    assert result["science_eligible_for_panel"] == result["controls_eligible_for_measurement"] == 0


@pytest.mark.parametrize("error", ["transport", "usage"])
def test_ambiguous_or_integrity_failure_aborts_without_resend(engine, error):
    worker, state, _ = engine
    worker.census()
    state.transport_error = error == "transport"
    state.wrong_usage = error == "usage"
    with pytest.raises((OSError, c.DevelopmentError)):
        worker.generate()
    assert len(state.calls) == 1 and state.epochs == state.stops == 2
    assert worker.path("safe", "generate-aborted.safe.json").is_file()
    with pytest.raises(c.DevelopmentError, match="AMBIGUOUS_OR_UNFINALIZED"):
        worker.status()
    with pytest.raises(c.DevelopmentError, match="PRIOR_ABORTED_OPERATION"):
        worker.generate()
    assert len(state.calls) == 1 and state.epochs == 2


@pytest.mark.parametrize("cap,kind", [(48, "control"), (512, "science")])
def test_exact_cap_stop_vs_length_and_complete_hashes(engine, cap, kind):
    worker, _, _ = engine
    item = next(item for item in worker.plan["requests"] if item["kind"] == kind)
    raw = reply(worker.config, content="\r\nWhole\ranswer  ", used=cap)
    parsed = m.parse_reply(worker.config, item, raw, 12)
    assert parsed["completion_cap_reached"] is True
    assert parsed["response_sha256"] == c.sha_bytes(b"Whole\nanswer")
    assert parsed["content_sha256"] == c.sha_bytes(b"\r\nWhole\ranswer  ")
    assert parsed["raw_reply_sha256"] == c.sha_bytes(raw)
    assert parsed["request_max_tokens"] == cap and parsed["ineligible_reason"] is None
    truncated = m.parse_reply(worker.config, item, reply(worker.config, finish="length"), 12)
    assert truncated["ineligible_reason"] == "TRUNCATED_UNKNOWN"
    with pytest.raises(c.DevelopmentError, match="TOKEN_BUDGET"):
        m.parse_reply(worker.config, item, reply(worker.config, used=cap + 1), 12)


@pytest.mark.parametrize(
    "mutation",
    [
        "alias",
        "choices",
        "role",
        "index",
        "tool",
        "refusal",
        "reasoning",
        "empty_usage",
        "bool_usage",
        "zero_tokens",
    ],
)
def test_control_parser_integrity_rejects_malformed_replies(engine, mutation):
    worker, _, _ = engine
    item = next(item for item in worker.plan["requests"] if item["kind"] == "control")
    value = c.strict_json(reply(worker.config))
    if mutation == "alias":
        value["model"] = "wrong"
    elif mutation == "choices":
        value["choices"] *= 2
    elif mutation == "role":
        value["choices"][0]["message"]["role"] = "user"
    elif mutation == "index":
        value["choices"][0]["index"] = False
    elif mutation in {"tool", "refusal", "reasoning"}:
        key = {"tool": "tool_calls", "refusal": "refusal", "reasoning": "reasoning_content"}[
            mutation
        ]
        value["choices"][0]["message"][key] = "not an answer"
    elif mutation == "empty_usage":
        value["usage"] = {}
    elif mutation == "bool_usage":
        value["usage"]["completion_tokens"] = True
    else:
        value["usage"].update(completion_tokens=0, total_tokens=12)
    with pytest.raises(c.DevelopmentError):
        m.parse_reply(worker.config, item, c.canonical(value), 12)


def test_cooldown_waits_before_every_target_and_retains_all_samples(engine, monkeypatch):
    worker, state, _ = engine
    worker.census()
    values = iter([70, 65, 60, 55, 61, 60, 50])
    sleeps = []
    monkeypatch.setattr(m.low, "gpu_sample", lambda: gpu(next(values)))
    monkeypatch.setattr(m.time, "sleep", sleeps.append)
    # First sample is the new epoch's prelaunch resource sample (70 is below 85).
    worker.generate()
    assert len(state.calls) == 4 and sleeps == [0.5, 0.5]
    first = worker.read(
        "safe", f"target/{worker.plan['requests'][0]['request_id']}.cooldown.safe.json"
    )
    assert [row["gpu_temperature_c"] for row in first["samples"]] == [65, 60]


def test_failed_thermal_sample_is_retained_and_does_not_dispatch(engine, monkeypatch):
    worker, state, _ = engine
    worker.census()
    values = iter([50, 85])
    monkeypatch.setattr(m.low, "gpu_sample", lambda: gpu(next(values)))
    with pytest.raises(c.DevelopmentError, match="GPU_TEMPERATURE_LIMIT"):
        worker.generate()
    assert not state.calls and state.epochs == state.stops == 2
    rid = worker.plan["requests"][0]["request_id"]
    receipt = worker.read("safe", f"target/{rid}.cooldown.safe.json")
    assert receipt["cooldown_passed"] is False and receipt["samples"][0]["gpu_temperature_c"] == 85
    with pytest.raises(c.DevelopmentError, match="PRIOR_ABORTED_OPERATION"):
        worker.generate()
    assert state.epochs == 2


@pytest.mark.parametrize(
    "area,suffix",
    [
        ("safe", ".row.safe.json"),
        ("private", ".reply.private.json"),
        ("private", ".request.private.json"),
    ],
)
def test_orphan_or_out_of_frame_receipts_cannot_hide(engine, area, suffix):
    worker, _, _ = engine
    worker.write(area, "target/" + "0" * 64 + suffix, {})
    with pytest.raises(c.DevelopmentError, match="ORPHAN"):
        worker.global_check("target")


@pytest.mark.parametrize(
    "mutation",
    [
        "request",
        "usage",
        "pid",
        "timestamp",
        "cooldown",
        "census",
        "command",
        "native_receipt",
        "raw_reply",
    ],
)
def test_reconciliation_rejects_coherent_receipt_tampering(engine, mutation):
    worker, _, _ = engine
    worker.census()
    worker.generate()
    rid = worker.plan["requests"][0]["request_id"]
    original_read = worker.read
    original_json = m.read_json

    def corrupt(area, relative):
        value = copy.deepcopy(original_read(area, relative))
        if mutation == "request" and relative == f"target/{rid}.request.private.json":
            value["temperature"] = 0
        elif mutation == "usage" and relative == f"target/{rid}.row.safe.json":
            value["usage"]["completion_tokens"] = 6
        elif mutation == "pid" and relative in {
            f"target/{rid}.dispatch.safe.json",
            f"target/{rid}.row.safe.json",
        }:
            value["process_id"] = 999
        elif mutation == "timestamp" and relative == f"target/{rid}.row.safe.json":
            value["received_at"] = "2099-01-01T00:00:00+00:00"
        elif mutation == "cooldown" and relative == f"target/{rid}.cooldown.safe.json":
            value["samples"][-1]["gpu_temperature_c"] = 80
        elif mutation == "census" and relative == "census.safe.json":
            value["metadata_post_requests"] = 5
        return value

    def corrupt_json(path):
        value = copy.deepcopy(original_json(path))
        if mutation == "command" and path.name == "server-01.started.safe.json":
            value["command_sha256"] = "0" * 64
        if mutation == "native_receipt" and path.name.endswith(".tpl.safe.json"):
            value["process_id"] = 999
        return value

    if mutation == "raw_reply":
        # Synthetic-only writer replaced via fixture monkeypatch below: no experimental path.
        raw = worker.path("private", f"target/{rid}.reply.private.json")
        original_bytes = Path.read_bytes
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                Path, "read_bytes", lambda path: b"{}" if path == raw else original_bytes(path)
            )
            with pytest.raises(c.DevelopmentError):
                worker.status()
    else:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(worker, "read", corrupt)
            patch.setattr(m, "read_json", corrupt_json)
            patch.setattr(m.low, "read_json", corrupt_json)
            with pytest.raises((c.DevelopmentError, AssertionError)):
                worker.status()


def test_path_containment_and_exclusive_reservation(engine):
    worker, _, _ = engine
    with pytest.raises(c.DevelopmentError):
        worker.path("private", "../outside.json")
    worker.config = {**worker.config, "_contract_sha256": "8" * 64}
    with pytest.raises(c.DevelopmentError, match="ANOTHER_TOPOLOGY_EXPERIMENT"):
        worker.reservation()


def test_complete_prefix_continuation_never_redispatches_prior_records(engine):
    worker, state, _ = engine
    census = worker.census()
    prompts = worker.load_materials()
    census_map = {row["materialization_id"]: row for row in census["rows"]}
    with worker.operation("synthetic-prefix"):
        epoch = worker.epoch()
        with worker.server(epoch) as (process, client, _):
            for item in worker.plan["requests"][:2]:
                mid = item["materialization_id"]
                worker.dispatch(item, prompts[mid], census_map[mid], process, client, epoch)
    assert worker.status()["target_records"] == 2
    assert worker.generate()["complete"] is True
    assert len(state.calls) == 4 and state.epochs == state.stops == 3
    assert [body["seed"] for _, body, _ in state.calls] == [11, 23, 47, 17]


def test_metadata_ambiguous_dispatch_is_never_retried(engine, monkeypatch):
    worker, state, _ = engine
    calls = []

    def fail(*args):
        calls.append(1)
        raise OSError("Synthetic metadata interruption")

    monkeypatch.setattr(m.low, "metadata_request", fail)
    with pytest.raises(OSError):
        worker.census()
    assert len(calls) == 1 and state.epochs == state.stops == 1
    with pytest.raises(c.DevelopmentError, match="PRIOR_ABORTED_OPERATION"):
        worker.census()
    assert len(calls) == 1 and state.epochs == 1 and not state.calls


def test_context_failure_finishes_metadata_but_never_generates(engine, monkeypatch):
    worker, state, _ = engine
    original = worker.parse_census
    monkeypatch.setattr(
        worker,
        "parse_census",
        lambda item, raw: {**original(item, raw), "context_budget_passed": False},
    )
    with pytest.raises(c.DevelopmentError, match="CENSUS_NOT_COMPLETE_OR_CONTEXT_FAILED"):
        worker.census()
    assert len(state.metadata) == 6 and not state.calls
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert state.epochs == state.stops == 1


def test_deadline_before_new_dispatch_does_not_launch_or_change_timeout(engine, monkeypatch):
    worker, state, _ = engine
    worker.census()

    def expired(config):
        raise c.DevelopmentError("AUTHORIZED_EXECUTION_DEADLINE_REACHED")

    monkeypatch.setattr(m.low, "check_deadline", expired)
    with pytest.raises(c.DevelopmentError, match="DEADLINE"):
        worker.generate()
    assert not state.calls and state.epochs == 1
    assert worker.config["server"]["request_timeout_seconds"] == 240


def test_interrupted_complete_prefix_is_auditable_but_never_silently_resumed(engine):
    worker, state, _ = engine
    census = worker.census()
    prompts = worker.load_materials()
    item = worker.plan["requests"][0]
    mid = item["materialization_id"]
    census_row = next(row for row in census["rows"] if row["materialization_id"] == mid)
    with pytest.raises(KeyboardInterrupt):
        with worker.operation("generate"):
            epoch = worker.epoch()
            with worker.server(epoch) as (process, client, _):
                worker.dispatch(item, prompts[mid], census_row, process, client, epoch)
            raise KeyboardInterrupt()
    status = worker.status()
    assert status["target_records"] == 1
    assert status["prior_operation_failures"] == ["generate"]
    assert status["operational_gate_passed"] is False
    with pytest.raises(c.DevelopmentError, match="PRIOR_ABORTED_OPERATION"):
        worker.generate()
    assert len(state.calls) == 1 and state.epochs == state.stops == 2


def test_cooldown_timeout_preserves_samples_without_inference(engine, monkeypatch):
    worker, state, _ = engine
    worker.census()
    monkeypatch.setattr(m.low, "gpu_sample", lambda: gpu(70))
    ticks = iter([0, 181, 181])
    monkeypatch.setattr(m.time, "monotonic", lambda: next(ticks))
    with pytest.raises(c.DevelopmentError, match="TARGET_COOLDOWN_TIMEOUT"):
        worker.generate()
    assert not state.calls and state.epochs == state.stops == 2
    rid = worker.plan["requests"][0]["request_id"]
    receipt = worker.read("safe", f"target/{rid}.cooldown.safe.json")
    assert receipt["wait_seconds"] == 181 and receipt["cooldown_passed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("frozen", False),
        ("execution_authorized", False),
        ("paper_validity", True),
        ("bound_plan_identity_sha256", "0" * 64),
        ("parent_screen_contract_sha256", "0" * 64),
        ("paths", {"safe_root": "data/other", "private_root": "artifacts/other"}),
        ("cooldown", {}),
        ("budgets", {"total_target_calls": 1000}),
    ],
)
def test_worker_rejects_authority_namespace_budget_or_policy_drift(engine, field, value):
    worker, _, _ = engine
    config = copy.deepcopy(worker.config)
    config[field] = value
    with pytest.raises(c.DevelopmentError):
        m.TopologyTarget(worker.root, config, worker.plan, {}, helper=worker.helper)


@pytest.fixture
def preparation(monkeypatch):
    inputs, sources = [], []
    for position in range(45):
        payload = f"Synthetic P {position:02d}."
        for condition in p.CONDITIONS:
            prompt = payload if condition == "DIRECT" else "Wrapper " + payload + " End."
            source = {
                "payload_position": position,
                "condition": condition,
                "payload_sha256": c.sha_bytes(payload.encode()),
                "prompt_sha256": c.sha_bytes(prompt.encode()),
                "prompt_utf8_bytes": len(prompt.encode()),
                "unit_manifest_sha256": c.digest([position, "unit"]),
                "fragment_manifest_sha256": c.digest([position, "fragment"]),
                "private_source": {"sha256": c.digest([position, condition, "old"])},
            }
            sources.append(source)
            inputs.append(
                {
                    "payload_position": position,
                    "condition": condition,
                    "payload": payload,
                    "prompt": prompt,
                    "payload_sha256": source["payload_sha256"],
                    "prompt_sha256": source["prompt_sha256"],
                    "source_private_record_sha256": source["private_source"]["sha256"],
                }
            )
    inventory = {"rows": sources, "rows_sha256": c.digest(sources)}
    config = {"source_inventory": {"sha256": "a" * 64}, "_contract_sha256": p.SCREEN_SHA256}
    population = [
        {
            key: sources[2 * position + 1][key]
            for key in (
                "payload_position",
                "payload_sha256",
                "prompt_sha256",
                "unit_manifest_sha256",
                "fragment_manifest_sha256",
            )
        }
        for position in (3, 7, 8, 10, 22, 44)
    ]
    plan = {"population": population, "n": 6, "materializations_bound": False}
    calls = []

    class Renderer:
        def prepare_bound_bundle(self, payload, prompt, anchor, position):
            calls.append(position)
            safe, private = [], []
            for mask in range(8):
                for operator in p.OPERATORS:
                    for kind, task in (
                        ("science", None),
                        ("control", p.TASKS[0]),
                        ("control", p.TASKS[1]),
                    ):
                        key = {
                            "payload_position": position,
                            "mask": mask,
                            "operator": operator,
                            "kind": kind,
                            "task_id": task,
                        }
                        text = prompt if kind == "science" else "Synthetic harmless control."
                        safe.append(
                            {
                                **key,
                                "prompt_sha256": c.sha_bytes(text.encode()),
                                "prompt_utf8_bytes": len(text.encode()),
                            }
                        )
                        private.append({**key, "prompt": text})
            return {
                "source_identity": anchor,
                "safe_rows": safe,
                "private_rows": private,
                "execution_authorized": False,
                "model_calls": 0,
            }

    def bind(plan, rows, identity, **context):
        return {
            **plan,
            "materializations_bound": True,
            "bound_materializations": [
                {
                    **p.materialization_key(row),
                    "materialization_id": c.digest(p.materialization_key(row)),
                    "renderer_row": row,
                }
                for row in rows
                if row["mask"] != 0
            ],
        }

    monkeypatch.setattr(p, "validate_plan", lambda plan, **context: True)
    monkeypatch.setattr(p, "validate_inputs", lambda *args: (config, inventory))
    monkeypatch.setattr(p, "bind_materializations", bind)
    return SimpleNamespace(
        inputs=inputs,
        inventory=inventory,
        config=config,
        plan=plan,
        renderer=Renderer(),
        calls=calls,
        context={"screen_contract_raw": b"synthetic", "inventory_raw": b"safe"},
    )


def test_pure_preparation_uses_only_new_supplied_bytes_and_all_stable_positions(preparation):
    state = preparation
    raw = c.canonical({"rows": state.inputs})
    receipt = m.low.input_receipt(state.config, state.inventory, raw)
    result = m.prepare_materials(state.plan, state.context, raw, receipt, state.renderer)
    assert state.calls == [3, 7, 8, 10, 22, 44]
    assert len(result["private_materializations"]["rows"]) == 42 * 6
    assert result["historical_private_reads"] == result["model_calls"] == 0
    assert result["execution_authorized"] is False
    assert all(
        set(row) == {"materialization_id", "prompt"}
        for row in result["private_materializations"]["rows"]
    )
    assert b"Synthetic P" not in c.canonical(result["bound_plan"])


@pytest.mark.parametrize(
    "mutation", ["drop", "extra_reply", "raw_change", "wrong_source", "direct"]
)
def test_pure_preparation_rejects_changed_new_input_frame_before_render(preparation, mutation):
    state = preparation
    if mutation == "drop":
        state.inputs.pop()
    elif mutation == "extra_reply":
        state.inputs[0]["response"] = "Old replies must never be accepted"
    elif mutation == "raw_change":
        state.inputs[0]["payload"] = "Changed"
    elif mutation == "wrong_source":
        state.inputs[0]["source_private_record_sha256"] = "0" * 64
    else:
        state.inputs[0]["prompt"] = "Not exact P"
    raw = c.canonical({"rows": state.inputs})
    receipt = m.low.input_receipt(state.config, state.inventory, raw)
    with pytest.raises(c.DevelopmentError):
        m.prepare_materials(state.plan, state.context, raw, receipt, state.renderer)
    assert not state.calls


def test_stale_cooldown_cannot_be_coherently_rebound_to_later_request(engine, monkeypatch):
    worker, _, _ = engine
    worker.census()
    worker.generate()
    first, second = worker.plan["requests"][:2]
    first_cooldown = worker.read("safe", f"target/{first['request_id']}.cooldown.safe.json")
    second_stem = f"target/{second['request_id']}"
    cooldown = worker.read("safe", second_stem + ".cooldown.safe.json")
    cooldown["samples"] = first_cooldown["samples"]
    replacements = {second_stem + ".cooldown.safe.json": cooldown}
    for suffix in (".dispatch.safe.json", ".row.safe.json"):
        value = worker.read("safe", second_stem + suffix)
        value["cooldown_receipt_sha256"] = c.digest(cooldown)
        replacements[second_stem + suffix] = value
    original = worker.read
    monkeypatch.setattr(
        worker,
        "read",
        lambda area, relative: copy.deepcopy(replacements[relative])
        if area == "safe" and relative in replacements
        else original(area, relative),
    )
    with pytest.raises(c.DevelopmentError, match="COOLDOWN_SAMPLE_NOT_FRESH"):
        worker.status()


@pytest.mark.parametrize("kind", ["metadata", "target"])
def test_coherently_swapped_request_times_cannot_change_frozen_dispatch_order(
    engine, monkeypatch, kind
):
    worker, _, _ = engine
    worker.census()
    worker.generate()
    items = worker.plan["metadata_requests"] if kind == "metadata" else worker.plan["requests"]
    key = "metadata_request_id" if kind == "metadata" else "request_id"
    stems = [f"{kind}/{item[key]}" for item in items[:2]]
    original_rows = [worker.read("safe", stem + ".row.safe.json") for stem in stems]
    replacements = {}
    for index, stem in enumerate(stems):
        other = original_rows[1 - index]
        for suffix in (".dispatch.safe.json", ".row.safe.json"):
            value = worker.read("safe", stem + suffix)
            value["dispatch_at"] = other["dispatch_at"]
            if suffix == ".row.safe.json":
                value["received_at"] = other["received_at"]
            replacements[stem + suffix] = value
    original = worker.read
    monkeypatch.setattr(
        worker,
        "read",
        lambda area, relative: copy.deepcopy(replacements[relative])
        if area == "safe" and relative in replacements
        else original(area, relative),
    )
    with pytest.raises(c.DevelopmentError, match="NOT_IN_FROZEN_PLAN_TIME_ORDER"):
        worker.status()


def test_postvalidation_mutation_cannot_reach_operation_entry(engine):
    worker, state, prepared = engine
    prepared["bound_plan"]["requests"][0]["generation"]["temperature"] = 999
    # Constructor copies prevent a caller's original object from mutating the worker.
    assert worker.plan["requests"][0]["generation"]["temperature"] == 0.7
    worker.plan["requests"][0]["generation"]["temperature"] = 999
    with pytest.raises(c.DevelopmentError, match="POSTVALIDATION_CONTRACT_OR_PLAN_MUTATION"):
        with worker.operation("generate"):
            raise AssertionError("Must never enter operation body")
    assert not state.calls and state.epochs == 0


def test_verifier_rejects_dispatch_at_deadline_even_with_consistent_epoch_times(engine):
    worker, _, _ = engine
    deadline = m.low.parse_utc(worker.config["execution_limits"]["deadline_utc"])
    epoch = {
        "started_at": (deadline - timedelta(seconds=1)).isoformat(),
        "stopped_at": (deadline + timedelta(seconds=2)).isoformat(),
    }
    journal = {"dispatch_at": deadline.isoformat()}
    row = {"received_at": (deadline + timedelta(seconds=1)).isoformat(), "latency_seconds": 1}
    with pytest.raises(c.DevelopmentError, match="DISPATCH_NOT_BEFORE_AUTHORIZED_DEADLINE"):
        worker.verify_times(epoch, journal, row)


def test_coherent_epoch_stop_overlap_is_not_hidden_by_ordered_responses(engine, monkeypatch):
    worker, _, _ = engine
    census = worker.census()
    prompts = worker.load_materials()
    item = worker.plan["requests"][0]
    mid = item["materialization_id"]
    census_row = next(row for row in census["rows"] if row["materialization_id"] == mid)
    with worker.operation("synthetic-prefix"):
        epoch = worker.epoch()
        with worker.server(epoch) as (process, client, _):
            worker.dispatch(item, prompts[mid], census_row, process, client, epoch)
    worker.generate()
    next_epoch = worker.read("safe", "epochs/003/server-01.started.safe.json")
    overlap = (m.low.parse_utc(next_epoch["started_at"]) + timedelta(microseconds=1)).isoformat()
    original = m.low.read_json

    def corrupt(path):
        value = original(path)
        if path.parent.name == "002" and path.name == "server-01.stopped.safe.json":
            value["stopped_at"] = overlap
        return value

    monkeypatch.setattr(m.low, "read_json", corrupt)
    with pytest.raises(c.DevelopmentError, match="OWNED_EPOCHS_OVERLAP"):
        worker.status()
