"""Only invented harmless fixtures, fake clients/processes and temporary trees."""

import ast
import copy
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_pa_llama_topology_target_v1 import engine as base_engine  # noqa: F401
from test_pa_llama_topology_target_v1 import reply, stamp

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "synthetic_target_continuation", SCRIPTS / "pa_llama_topology_target_continuation_v1.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
c = m.c


@pytest.fixture
def engine(request, monkeypatch):
    parent, state, prepared = request.getfixturevalue("base_engine")
    monkeypatch.setattr(m, "PARENT_SHA", parent.config["_contract_sha256"])
    monkeypatch.setattr(m, "PLAN_SHA", parent.plan["plan_identity_sha256"])
    monkeypatch.setattr(m, "PREFIX_COUNT", 1)
    monkeypatch.setattr(m, "TOTAL", 4)
    monkeypatch.setattr(
        m,
        "EPOCHS",
        [
            {"epoch_index": 3, "first_ordinal": 2, "last_ordinal": 2},
            {"epoch_index": 4, "first_ordinal": 3, "last_ordinal": 3},
            {"epoch_index": 5, "first_ordinal": 4, "last_ordinal": 4},
        ],
    )
    monkeypatch.setattr(m, "fixed_frame", lambda worker: worker.plan["requests"])
    census = parent.census()
    item = parent.plan["requests"][0]
    prompts = parent.load_materials()
    census_map = {r["materialization_id"]: r for r in census["rows"]}
    with pytest.raises(c.DevelopmentError, match="DISK_FREE_SPACE_BELOW_15_GIB"):
        with parent.operation("generate"):
            with parent.server(2) as (process, client, _):
                parent.dispatch(
                    item,
                    prompts[item["materialization_id"]],
                    census_map[item["materialization_id"]],
                    process,
                    client,
                    2,
                )
                with monkeypatch.context() as patch:
                    patch.setattr(
                        m.old.shutil,
                        "disk_usage",
                        lambda path: SimpleNamespace(free=m.low.MIN_DISK_BYTES - 1),
                    )
                    parent.cooldown(parent.plan["requests"][1], 2)
    for epoch in (1, 2):
        c.write_once(
            parent.path("private", f"epochs/{epoch:03d}/server-01.log.private.txt"), b"", raw=True
        )
    manifest = m.make_prefix_manifest(parent)
    raw = c.canonical(manifest) + b"\n"
    amendment = {
        "_amendment_sha256": "a" * 64,
        "frozen_at_utc": stamp(),
        "prefix_manifest": {
            "path": m.PREFIX_PATH,
            "size_bytes": len(raw),
            "sha256": c.sha_bytes(raw),
        },
        "epoch_schedule": copy.deepcopy(m.EPOCHS),
    }
    worker = m.CompositeTarget(parent, amendment, manifest)
    original_owned = parent.helper.owned_server
    new_calls = []

    class Client:
        def request(self, route, body, *, timeout):
            assert timeout == 240, "An in-flight call retains the frozen timeout"
            item = next(r for r in worker.plan["requests"] if r["seed"] == body["seed"])
            path = worker.path("safe", f"target/{item['request_id']}.dispatch.safe.json")
            assert path.exists(), "Journal must precede HTTP dispatch"
            new_calls.append(item["ordinal"])
            if state.transport_error:
                raise OSError("Invented transport failure")
            return reply(
                worker.config,
                content=state.content,
                finish=state.finish,
                prompt=99 if state.wrong_usage else 12,
            )

    @contextmanager
    def owned(root, config, private, safe, epoch, sha):
        c.write_once(private / "server-01.log.private.txt", b"", raw=True)
        with original_owned(root, config, private, safe, epoch, sha) as (process, _, identity):
            yield process, Client(), identity

    worker.helper = SimpleNamespace(**{**vars(parent.helper), "owned_server": owned})
    return worker, state, new_calls, prepared


def test_real_fixed_frame_schedule_counts_and_wrong_identity_rejection():
    rows = [
        {"ordinal": i + 1, "request_id": c.digest(i), "kind": "science" if i < 882 else "control"}
        for i in range(1470)
    ]
    parent = SimpleNamespace(
        assert_unchanged=lambda: None,
        config={"_contract_sha256": m.PARENT_SHA},
        plan={"plan_identity_sha256": m.PLAN_SHA, "requests": rows},
    )
    assert m.fixed_frame(parent) == rows
    assert [(x["first_ordinal"], x["last_ordinal"]) for x in m.EPOCHS] == [
        (873, 1082),
        (1083, 1292),
        (1293, 1470),
    ]
    assert sum(x["last_ordinal"] - x["first_ordinal"] + 1 for x in m.EPOCHS) == 598
    parent.plan["requests"][872]["ordinal"] = True
    with pytest.raises(c.DevelopmentError, match="FULL_FRAME_CHANGED"):
        m.fixed_frame(parent)


def test_prefix_manifest_is_exhaustive_hash_only_and_preparation_write_once(engine):
    worker, _, calls, _ = engine
    parent = worker.parent
    before = {
        tuple((r["kind"], r["relative"])): r["sha256"] for r in worker.prefix_manifest["files"]
    }
    assert worker.verify_prefix_manifest() is True
    pin = m.prepare_prefix(parent)
    assert m.prepare_prefix(parent) == pin
    assert len(before) == len(m.parent_entries(parent))
    text = c.canonical(worker.prefix_manifest).decode()
    assert "Synthetic full answer" not in text and "Harmless synthetic material" not in text
    assert worker.prefix_manifest["raw_receipts_verified"] is False
    assert calls == []


def test_complete_composite_runs_only_missing_exact_order_with_three_owned_epochs(engine):
    worker, state, calls, _ = engine
    original = {
        tuple((r["kind"], r["relative"])): m.snapshot(worker.parent.path(r["kind"], r["relative"]))
        for r in worker.prefix_manifest["files"]
    }
    result = worker.generate()
    assert calls == [2, 3, 4]
    assert state.epochs == state.stops == 5
    assert result["complete"] is True
    assert result["amended_execution_gate_passed"] is True
    assert result["operational_gate_passed"] is False
    assert result["original_operational_gate_passed"] is False
    for (kind, relative), raw in original.items():
        assert worker.parent.path(kind, relative).read_bytes() == raw
    verified = worker.verify_composite_targets()
    assert len(verified["rows"]) == 4
    proof = verified["proof"]
    identity = proof.pop("result_identity_sha256")
    assert identity == c.digest(proof)
    assert [x["epoch_binding"]["epoch_index"] for x in proof["continuation_epoch_proofs"]] == [
        3,
        4,
        5,
    ]
    assert all(x["target_count"] == 1 for x in proof["continuation_epoch_proofs"])
    assert worker.parent.summary(verified["rows"])["operational_gate_passed"] is False


def test_prefix_private_content_is_reparsed_not_just_safe_claim(engine, monkeypatch):
    worker, _, calls, _ = engine
    original_parse = m.old.parse_reply
    seen = []

    def parse(*args):
        seen.append(args[1]["ordinal"])
        return original_parse(*args)

    monkeypatch.setattr(m.old, "parse_reply", parse)
    rows = worker.reconcile(worker.load_materials(), worker.load_census())
    assert [r["ordinal"] for r in rows] == [1] and seen == [1] and calls == []


@pytest.mark.parametrize("kind,suffix", m.TARGET_SUFFIXES)
def test_original_first_missing_artifacts_except_frozen_failed_cooldown_block(engine, kind, suffix):
    worker, _, calls, _ = engine
    rid = worker.plan["requests"][1]["request_id"]
    if suffix == ".cooldown.safe.json":
        rid = worker.plan["requests"][2]["request_id"]
    c.write_once(worker.parent.path(kind, f"target/{rid}{suffix}"), {"invented": True})
    with pytest.raises(c.DevelopmentError, match="PARENT_RECEIPT_SET_CHANGED"):
        worker.generate()
    assert calls == []


@pytest.mark.parametrize(
    "relative",
    [
        "generate-aborted.safe.json",
        "materializations.safe.json",
        "epochs/002/server-01.stopped.safe.json",
    ],
)
def test_original_pinned_byte_change_blocks_before_dispatch(engine, relative):
    worker, _, calls, _ = engine
    path = worker.parent.path("safe", relative)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(c.DevelopmentError, match="IMMUTABLE_ORIGINAL_PREFIX_BYTES_CHANGED"):
        worker.generate()
    assert calls == []


def test_original_response_semantics_tamper_after_coherent_manifest_still_fails(engine):
    worker, _, calls, _ = engine
    item = worker.plan["requests"][0]
    path = worker.parent.path("private", f"target/{item['request_id']}.reply.private.json")
    path.write_bytes(reply(worker.config, content="Different harmless response"))
    worker.prefix_manifest = m.make_prefix_manifest(worker.parent)
    worker._prefix_identity = c.digest(worker.prefix_manifest)
    with pytest.raises(c.DevelopmentError, match="COMPOSITE_RAW_TARGET_ROW_MISMATCH"):
        worker.generate()
    assert calls == []


def test_prefix_write_attempt_is_rejected(engine):
    worker, _, _, _ = engine
    rid = worker.plan["requests"][0]["request_id"]
    with pytest.raises(c.DevelopmentError, match="IMMUTABLE_PREFIX_WRITE_FORBIDDEN"):
        worker.write("safe", f"target/{rid}.row.safe.json", {})


@pytest.mark.parametrize("mutation", ["config", "amendment", "prefix", "plan"])
def test_mutable_context_tamper_rejected(engine, mutation):
    worker, _, calls, _ = engine
    value = {
        "config": worker.config,
        "amendment": worker.amendment,
        "prefix": worker.prefix_manifest,
        "plan": worker.plan,
    }[mutation]
    value["invented_extra"] = True
    with pytest.raises(c.DevelopmentError, match="POSTVALIDATION"):
        worker.generate()
    assert calls == []


def test_transport_failure_is_ambiguous_persisted_and_never_retried(engine):
    worker, state, calls, _ = engine
    state.transport_error = True
    with pytest.raises(OSError):
        worker.generate()
    assert calls == [2] and state.epochs == state.stops == 3
    assert worker.path("safe", "generate-aborted.safe.json").exists()
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert calls == [2]
    assert not worker.path("safe", "target-operation.lock.safe.json").exists()


@pytest.mark.parametrize("finish,content", [("length", "Invented truncated reply"), ("stop", "")])
def test_content_or_length_failure_does_not_selectively_stop_tail(engine, finish, content):
    worker, state, calls, _ = engine
    state.finish, state.content = finish, content
    result = worker.generate()
    assert calls == [2, 3, 4] and result["amended_execution_gate_passed"] is True


def test_stricter_20g_prelaunch_failure_retained_with_no_model_launch(engine, monkeypatch):
    worker, state, calls, _ = engine
    monkeypatch.setattr(
        m.old.shutil, "disk_usage", lambda path: SimpleNamespace(free=m.PRELAUNCH_BYTES - 1)
    )
    with pytest.raises(c.DevelopmentError, match="PRELAUNCH_DISK_BELOW_20_GIB"):
        worker.generate()
    assert calls == [] and state.epochs == 2
    sample = worker.read("safe", "epochs/003/resource.safe.json")
    assert sample["disk_free_bytes"] == m.PRELAUNCH_BYTES - 1
    assert worker.path("safe", "generate-aborted.safe.json").exists()
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert state.epochs == 2


def test_second_fixed_epoch_failure_does_not_allow_completed_prefix_resume(engine, monkeypatch):
    worker, state, calls, _ = engine
    original = worker.server

    @contextmanager
    def server(epoch):
        if epoch == 4:
            raise c.DevelopmentError("INVENTED_PRELAUNCH_FAILURE")
        with original(epoch) as owned:
            yield owned

    monkeypatch.setattr(worker, "server", server)
    with pytest.raises(c.DevelopmentError, match="INVENTED_PRELAUNCH_FAILURE"):
        worker.generate()
    assert calls == [2] and state.epochs == state.stops == 3
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert calls == [2]


def test_wrong_usage_integrity_aborts_after_one_dispatch(engine):
    worker, state, calls, _ = engine
    state.wrong_usage = True
    with pytest.raises(c.DevelopmentError, match="NATIVE_CENSUS_USAGE_MISMATCH"):
        worker.generate()
    assert calls == [2] and state.epochs == state.stops == 3


def test_complete_new_run_reentry_cannot_dispatch_again(engine):
    worker, _, calls, _ = engine
    worker.generate()
    with pytest.raises(c.DevelopmentError, match="ALREADY_ATTEMPTED_NO_RETRY"):
        worker.generate()
    assert calls == [2, 3, 4]


def test_incomplete_composite_never_receives_new_full_gate(engine):
    worker, _, _, _ = engine
    status = worker.status()
    assert status["amended_target_complete"] is False
    assert status["amended_execution_gate_passed"] is False
    assert status["operational_gate_passed"] is False
    with pytest.raises(c.DevelopmentError, match="FULL_FRAME_NOT_VERIFIED"):
        worker.verify_composite_targets()


def test_template_is_unfrozen_and_preserves_numeric_types(engine, monkeypatch):
    worker, _, _, _ = engine
    monkeypatch.setattr(
        m.loader,
        "file_descriptor",
        lambda root, path: {"path": path, "size_bytes": 1, "sha256": "1" * 64},
    )
    value = m.make_template(worker.root, worker.parent, worker.amendment["prefix_manifest"])
    assert value["frozen"] is False and value["execution_authorized"] is False
    assert value["frozen_at_utc"] is None
    assert value["epoch_schedule"] == m.EPOCHS
    assert value["budgets"]["new_metadata_calls"] == 0
    assert value["original_operational_gate_passed"] is False
    assert value["prelaunch_minimum_disk_free_bytes"] == 20 * 1024**3


def test_cli_rejects_unknown_execute_and_missing_sha(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        m.main(["--execute"])
    monkeypatch.setattr(
        m,
        "load_amendment",
        lambda root, sha: c.require(c.valid_sha(sha), "AMENDMENT_EXPECTED_SHA_REQUIRED"),
    )
    assert m.main(["generate"]) == 1
    assert "AMENDMENT_EXPECTED_SHA_REQUIRED" in capsys.readouterr().out


def test_no_direct_network_or_process_creation_and_no_old_generation_calls():
    tree = ast.parse((SCRIPTS / "pa_llama_topology_target_continuation_v1.py").read_text())
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {"Popen", "system", "run_phase", "extract_input", "prepare_inputs"}
    assert "generate" not in {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "parent"
    }


@pytest.mark.parametrize("where", ["first_launch", "after_cooling", "next_fixed_chunk"])
def test_deadline_rejects_before_dispatch_and_retains_completed_inflight(
    engine, monkeypatch, where
):
    worker, state, calls, _ = engine
    checks = []

    def deadline(config):
        checks.append(True)
        if (
            where == "first_launch"
            or (where == "after_cooling" and len(checks) == 3)
            or (where == "next_fixed_chunk" and calls)
        ):
            raise c.DevelopmentError("AUTHORIZED_DEADLINE_REACHED")

    monkeypatch.setattr(m.low, "check_deadline", deadline)
    with pytest.raises(c.DevelopmentError, match="AUTHORIZED_DEADLINE_REACHED"):
        worker.generate()
    assert calls == ([2] if where == "next_fixed_chunk" else [])
    assert state.epochs == state.stops
    assert worker.path("safe", "generate-aborted.safe.json").exists()
    if calls:
        rid = worker.plan["requests"][1]["request_id"]
        assert worker.path("private", f"target/{rid}.reply.private.json").is_file()
        assert worker.path("safe", f"target/{rid}.row.safe.json").is_file()


@pytest.mark.parametrize(
    "change", ["schema", "measurement", "wait", "sample_time", "gpu", "prior_accepted"]
)
def test_coherently_pinned_failed_cooling_must_retain_exact_disk_only_failure(engine, change):
    worker, _, calls, _ = engine
    rid = worker.plan["requests"][1]["request_id"]
    path = worker.parent.path("safe", f"target/{rid}.cooldown.safe.json")
    value = m.old.read_json(path)
    if change == "schema":
        value["unexplained"] = True
    elif change == "measurement":
        value["measurement"] = "continuous maximum"
    elif change == "wait":
        value["wait_seconds"] = -1
    elif change == "sample_time":
        value["samples"][-1]["sampled_at"] = "2026-09-05T23:59:59+00:00"
    elif change == "gpu":
        value["samples"][-1]["gpu_temperature_c"] = 85
    else:
        accepted = {**value["samples"][0], "disk_free_bytes": m.PRELAUNCH_BYTES}
        value["samples"].insert(0, accepted)
    path.write_bytes(c.canonical(value) + b"\n")
    worker.prefix_manifest = m.make_prefix_manifest(worker.parent)
    worker._prefix_identity = c.digest(worker.prefix_manifest)
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert calls == []


@pytest.mark.parametrize(
    "area,relative",
    [
        ("safe", "epochs/006/unknown.safe.json"),
        ("safe", "epochs/003/unknown.safe.json"),
        ("safe", "metadata/unplanned.dispatch.safe.json"),
        ("private", "metadata/unplanned.request.private.json"),
        ("private", "target/outside.request.private.json"),
    ],
)
def test_extra_child_epochs_metadata_and_out_of_frame_private_receipts_block(
    engine, area, relative
):
    worker, _, calls, _ = engine
    c.write_once(c.contained(worker.paths[area], relative), {"invented": True})
    with pytest.raises(c.DevelopmentError):
        worker.generate()
    assert calls == []


@pytest.mark.parametrize("which", ["reservation", "generate_start", "epoch_binding"])
def test_completed_composite_reverifies_stored_attempt_authority(engine, which):
    worker, _, _, _ = engine
    worker.generate()
    if which == "reservation":
        path = m.loader.owned(worker.root, m.SAFE_ROOT + "/experiment-reservation.safe.json")
    elif which == "generate_start":
        path = worker.path("safe", "generate-started.safe.json")
    else:
        path = worker.path("safe", "epochs/003/amendment.safe.json")
    value = m.old.read_json(path)
    value["unexplained"] = True
    path.write_bytes(c.canonical(value) + b"\n")
    with pytest.raises(c.DevelopmentError):
        worker.verify_composite_targets()


@pytest.mark.parametrize("method,args", [("stage", ({},)), ("census", ()), ("metadata_post", ())])
def test_no_new_materialization_or_metadata_generation_interface(engine, method, args):
    worker, _, calls, _ = engine
    with pytest.raises(c.DevelopmentError, match="CONTINUATION_NO_NEW"):
        getattr(worker, method)(*args)
    assert calls == []


@pytest.fixture
def authority_tree(engine, monkeypatch):
    worker, _, _, _ = engine
    parent = worker.parent
    parent.config["frozen_at_utc"] = "2026-09-05T17:00:00+00:00"
    parent._validated_config_sha256 = c.digest(parent.config)
    prefix_pin = m.prepare_prefix(parent)
    for relative in (*m.NEW_CODE, m.PROTOCOL):
        c.write_once(
            m.loader.owned(worker.root, relative), b"Synthetic public code pin\n", raw=True
        )
    template = m.make_template(worker.root, parent, prefix_pin)
    template.update(frozen=True, execution_authorized=True, frozen_at_utc=stamp())
    path = m.loader.owned(worker.root, m.CONFIG)
    c.write_once(path, c.canonical(template) + b"\n", raw=True)
    monkeypatch.setattr(m, "load_parent", lambda root: (parent, {"source_context": {}}))
    monkeypatch.setattr(m, "__file__", str(worker.root / m.SCRIPT))
    return worker.root, path, template


def test_actual_amendment_loader_accepts_only_exact_frozen_template(authority_tree):
    root, path, _ = authority_tree
    worker = m.load_amendment(root, c.sha_bytes(path.read_bytes()))
    assert worker.parent.config["_contract_sha256"] == m.PARENT_SHA
    assert worker.status()["amended_target_complete"] is False


@pytest.mark.parametrize(
    "change",
    ["frozen", "authorized", "count_bool", "epoch", "cap", "deadline", "extra", "code", "prefix"],
)
def test_actual_loader_rejects_changed_authority_types_bytes_and_scope(authority_tree, change):
    root, path, value = authority_tree
    if change == "frozen":
        value["frozen"] = False
    elif change == "authorized":
        value["execution_authorized"] = False
    elif change == "count_bool":
        value["original_prefix_count"] = True
    elif change == "epoch":
        value["epoch_schedule"][0]["last_ordinal"] += 1
    elif change == "cap":
        value["budgets"]["new_target_calls"] += 1
    elif change == "deadline":
        value["execution_limits"]["deadline_utc"] = "2026-09-06T22:55:47+00:00"
    elif change == "extra":
        value["ignore_old_failure"] = True
    elif change == "code":
        m.loader.owned(root, m.NEW_CODE[1]).write_bytes(b"Changed synthetic code")
    else:
        m.loader.owned(root, m.PREFIX_PATH).write_bytes(b"{}\n")
    path.write_bytes(c.canonical(value) + b"\n")
    with pytest.raises(c.DevelopmentError):
        m.load_amendment(root, c.sha_bytes(path.read_bytes()))


def test_loader_wrong_raw_sha_rejects_before_any_parent_loading(authority_tree, monkeypatch):
    root, _, _ = authority_tree
    monkeypatch.setattr(m, "load_parent", lambda root: pytest.fail("Must not load parent"))
    with pytest.raises(c.DevelopmentError, match="AMENDMENT_RAW_SHA_MISMATCH"):
        m.load_amendment(root, "0" * 64)


def test_prepare_prefix_with_template_cli_emits_small_descriptor_and_template(
    engine, monkeypatch, capsys
):
    worker, _, _, _ = engine
    monkeypatch.setattr(m, "load_parent", lambda root: (worker.parent, {}))
    monkeypatch.setattr(m, "make_template", lambda *args: {"frozen": False})
    assert m.main(["prepare-prefix", "--root", str(worker.root), "--with-template"]) == 0
    value = c.strict_json(capsys.readouterr().out.encode())
    assert set(value) == {"prefix_manifest", "template"}
    assert "files" not in value["prefix_manifest"]
