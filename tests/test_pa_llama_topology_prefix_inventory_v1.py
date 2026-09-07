"""Invented SAFE metadata only; never opens an actual experiment or private artifact."""

import ast
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pa_llama_topology_prefix_inventory_v1.py"
SPEC = importlib.util.spec_from_file_location("safe_inventory_under_test", SCRIPT)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def write(root, relative, value=None, *, raw=None):
    path = m.scoped(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw if raw is not None else m.canonical(value) + b"\n")
    return path


def evidence(root, suffix, value):
    return write(root, f"{m.SAFE}/{m.CONFIG_SHA}/{suffix}", value)


@pytest.fixture
def frame(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("i")
    rows = []
    for position in m.POSITIONS:
        for mask in range(1, 8):
            for operator in m.OPERATORS:
                for kind, seed, task in [
                    *(("science", s, None) for s in (11, 23, 47)),
                    *(("control", 17, task) for task in m.TASKS),
                ]:
                    item = {
                        "ordinal": len(rows) + 1,
                        "payload_position": position,
                        "mask": mask,
                        "operator": operator,
                        "kind": kind,
                        "seed": seed,
                        "task_id": task,
                        "panel_evaluation_required": kind == "science",
                        "payload_sha256": "a" * 64,
                    }
                    item["request_id"] = m.sha(m.canonical(item))
                    item["materialization_id"] = m.sha(
                        m.canonical([position, mask, operator, task])
                    )
                    rows.append(item)
    budgets = {
        "total_target_calls": 1470,
        "scientific_target_calls": 882,
        "control_target_calls": 588,
        "qwen_calls": 882,
        "jailmeter_calls": 882,
        "metadata_post_calls": 2646,
    }
    plan = {
        "n": 21,
        "materializations_bound": True,
        "population": [{"payload_position": position} for position in m.POSITIONS],
        "requests": rows,
        "budgets": budgets,
    }
    plan["plan_identity_sha256"] = m.sha(m.canonical(plan))
    plan_raw = m.canonical(plan) + b"\n"
    monkeypatch.setattr(m, "PLAN_ID", plan["plan_identity_sha256"])
    monkeypatch.setattr(m, "PLAN_SHA", m.sha(plan_raw))
    monkeypatch.setattr(m, "PLAN_SIZE", len(plan_raw))
    config = {
        "schema_version": "jbspan-pa-llama-topology-execution-v1",
        "frozen": True,
        "execution_authorized": True,
        "paper_validity": False,
        "source_bundle_identity_sha256": m.SOURCE_SHA,
        "bound_plan_identity_sha256": m.PLAN_ID,
        "paths": {"safe_root": m.SAFE},
        "budgets": budgets,
    }
    config_raw = m.canonical(config) + b"\n"
    monkeypatch.setattr(m, "CONFIG_SHA", m.sha(config_raw))
    monkeypatch.setattr(m, "CONFIG_SIZE", len(config_raw))
    write(root, m.PLAN, raw=plan_raw)
    write(root, m.CONFIG, raw=config_raw)
    return root, config, plan


def scan(frame, **kwargs):
    return m.inventory(frame[0], m.CONFIG_SHA, m.PLAN_SHA, **kwargs)


def target_record(frame, index=0, *, parts=("cooldown", "tpl", "dispatch", "row")):
    root, _, plan = frame
    item = plan["requests"][index]
    rid = item["request_id"]
    second = 3 * index
    begin = f"2026-09-05T20:{second // 60:02d}:{second % 60:02d}+00:00"
    end = f"2026-09-05T20:{second // 60:02d}:{second % 60:02d}.250000+00:00"
    cooldown = {
        "contract_sha256": m.CONFIG_SHA,
        "request_id": rid,
        "cooldown_passed": True,
        "wait_seconds": 0.5,
    }
    journal = {
        **item,
        "contract_sha256": m.CONFIG_SHA,
        "dispatch_at": begin,
        "request_sha256": "b" * 64,
        "cooldown_receipt_sha256": m.sha(m.canonical(cooldown)),
    }
    row = {
        **journal,
        "received_at": end,
        "latency_seconds": 0.25,
        "response_sha256": "c" * 64,
        "raw_reply_sha256": "d" * 64,
        "eligible_for_panel": True,
    }
    values = {
        "cooldown": cooldown,
        "dispatch": journal,
        "row": row,
        "tpl": {"contract_sha256": m.CONFIG_SHA, "request_id": rid},
    }
    for part in parts:
        evidence(root, f"target/{rid}.{part}.safe.json", values[part])
    return item, values


def panel_record(
    frame, axis="qwen", index=0, *, skip=False, parts=("ownership", "dispatch", "row")
):
    item, target = target_record(frame, index)
    rid = item["request_id"]
    bound = {
        "contract_sha256": m.CONFIG_SHA,
        "request_id": rid,
        "payload_position": item["payload_position"],
        "seed": item["seed"],
        "axis": axis,
        "condition": f"TOPOLOGY_SCIENCE:{item['operator']}:MASK_{item['mask']}",
        "target_row_identity_sha256": m.sha(m.canonical(target["row"])),
        "target_raw_reply_sha256": target["row"]["raw_reply_sha256"],
        "target_request_sha256": target["row"]["request_sha256"],
        "response_sha256": target["row"]["response_sha256"],
    }
    owner = {
        "contract_sha256": m.CONFIG_SHA,
        "request_id": rid,
        "axis": axis,
        "bound_plan_identity_sha256": m.PLAN_ID,
        "topology_item": item,
        "target_row_identity_sha256": bound["target_row_identity_sha256"],
        "dispatched": not skip,
    }
    dispatch = {**bound, "dispatch_at": "2026-09-05T21:00:00+00:00", "resume_allowed": False}
    row = (
        {**bound, "dispatched": False, "skip_reason": "TARGET_INELIGIBLE", "inference_seconds": 0.0}
        if skip
        else {
            **dispatch,
            "dispatched": True,
            "received_at": "2026-09-05T21:00:01+00:00",
            "inference_seconds": 1.0,
        }
    )
    row.update(label="DO_NOT_READ_LABEL", safety="DO_NOT_READ_SAFETY")
    values = {"ownership": owner, "dispatch": dispatch, "row": row}
    for part in parts:
        if part != "dispatch" or not skip:
            evidence(frame[0], f"panel/{axis}/{rid}.{part}.safe.json", values[part])
    return item, values


def test_no_worker_network_process_writer_or_runtime_imports():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module)])
    }
    assert imports <= {
        "__future__",
        "argparse",
        "collections",
        "datetime",
        "hashlib",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "sys",
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "write_bytes",
        "write_text",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "Popen",
        "request",
        "connect",
        "load_model",
    } - {"replace"}
    modes = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open"
    ]
    assert modes == ["rb"]


def test_exact_frozen_scope_constants_without_reading_actual_files():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0" in source
    assert "3a8bc4391f2ba6d02f2de446bd8b4ff61d1c1ac121fb3c57044bee379df1615b" in source
    assert "CONFIG_SIZE = 35000" in source and "PLAN_SIZE = 3577251" in source


def test_empty_snapshot_full_denominators_never_become_judge_abstention(frame):
    value = scan(frame, quiescent=True, details=True)
    assert value["quiescent_safe_accounting_consistent"] is True
    assert value["axes"]["target"]["state_counts"][m.STATES[2]] == 1470
    for axis in ("qwen", "jailmeter"):
        assert value["axes"][axis]["state_counts"][m.STATES[2]] == 882
    assert value["snapshot_is_atomic"] is False
    assert value["missing_judge_is_abstention"] is False
    assert value["scientific_analysis_performed"] is value["raw_receipts_reverified"] is False
    assert value["operational_certification_performed"] is value["execution_authorized"] is False
    assert value["private_files_read"] == value["files_written"] == value["new_model_calls"] == 0
    assert len(value["request_accounting"]["target"]) == 1470


@pytest.mark.parametrize(
    "parts,state",
    [
        (("cooldown",), m.STATES[3]),
        (("cooldown", "tpl"), m.STATES[3]),
        (("cooldown", "tpl", "dispatch"), m.STATES[4]),
        (("cooldown", "tpl", "dispatch", "row"), m.STATES[0]),
        (("row",), m.STATES[5]),
    ],
)
def test_target_lifecycle_states_remain_safe_only(frame, parts, state):
    target_record(frame, parts=parts)
    value = scan(frame, details=True)
    assert value["request_accounting"]["target"][0]["state"] == state
    assert value["transient_states_may_be_inflight"] is True
    assert value["quiescent_safe_accounting_consistent"] is None
    assert scan(frame, quiescent=True)["quiescent_safe_accounting_consistent"] == (
        state == m.STATES[0]
    )


@pytest.mark.parametrize("axis", ["qwen", "jailmeter"])
@pytest.mark.parametrize("skip", [False, True])
def test_panel_completion_or_recorded_skip_never_reads_labels(frame, axis, skip):
    panel_record(frame, axis, skip=skip)
    value = scan(frame, details=True)
    row = value["request_accounting"][axis][0]
    assert row["state"] == (m.STATES[1] if skip else m.STATES[0])
    text = m.canonical(value).decode()
    assert "DO_NOT_READ_LABEL" not in text and "DO_NOT_READ_SAFETY" not in text
    assert '"label"' not in text and '"safety"' not in text


@pytest.mark.parametrize(
    "parts,expected",
    [
        (("ownership",), m.STATES[3]),
        (("ownership", "dispatch"), m.STATES[4]),
        (("dispatch", "row"), m.STATES[5]),
    ],
)
def test_panel_owner_dispatch_prefix_and_missing_owner(frame, parts, expected):
    panel_record(frame, parts=parts)
    assert scan(frame, details=True)["request_accounting"]["qwen"][0]["state"] == expected


@pytest.mark.parametrize("part", ["row", "ownership"])
def test_panel_target_safe_hash_link_is_checked_without_reading_private_output(frame, part):
    item, values = panel_record(frame)
    values[part]["target_row_identity_sha256"] = "f" * 64
    evidence(frame[0], f"panel/qwen/{item['request_id']}.{part}.safe.json", values[part])
    result = scan(frame, details=True)
    assert result["request_accounting"]["qwen"][0]["state"] == m.STATES[5]
    assert result["private_files_read"] == 0


@pytest.mark.parametrize(
    "change",
    [
        "id",
        "contract",
        "kind",
        "ordinal",
        "time",
        "latency",
        "dispatch_binding",
        "cooldown",
        "duplicate_json",
        "bad_json",
    ],
)
def test_malformed_or_inconsistent_metadata_is_never_a_verified_completion(frame, change):
    item, values = target_record(frame)
    row = values["row"]
    if change in {"duplicate_json", "bad_json"}:
        raw = b'{"a":1,"a":2}' if change == "duplicate_json" else b'{"a":'
        write(
            frame[0], f"{m.SAFE}/{m.CONFIG_SHA}/target/{item['request_id']}.row.safe.json", raw=raw
        )
    else:
        if change == "id":
            row["request_id"] = "e" * 64
        elif change == "contract":
            row["contract_sha256"] = "e" * 64
        elif change == "kind":
            row["kind"] = "control"
        elif change == "ordinal":
            row["ordinal"] = True
        elif change == "time":
            row["received_at"] = "2026-09-05T19:59:59+00:00"
        elif change == "latency":
            row["latency_seconds"] = True
        elif change == "dispatch_binding":
            row["request_sha256"] = "e" * 64
        else:
            values["cooldown"]["wait_seconds"] = 5
            evidence(
                frame[0], f"target/{item['request_id']}.cooldown.safe.json", values["cooldown"]
            )
        evidence(frame[0], f"target/{item['request_id']}.row.safe.json", row)
    value = scan(frame, quiescent=True, details=True)
    assert value["request_accounting"]["target"][0]["state"] == m.STATES[5]
    assert value["quiescent_safe_accounting_consistent"] is False


def test_out_of_frame_id_and_control_sent_to_judge_are_accounted(frame):
    evidence(frame[0], "target/" + "f" * 64 + ".dispatch.safe.json", {})
    item = next(row for row in frame[2]["requests"] if row["kind"] == "control")
    evidence(frame[0], f"panel/qwen/{item['request_id']}.row.safe.json", {})
    value = scan(frame, quiescent=True)
    assert value["out_of_frame_safe_files_by_axis"] == {"target": 1, "qwen": 1}
    assert value["quiescent_safe_accounting_consistent"] is False


def test_out_of_order_dispatch_does_not_hide_unrun_prefix(frame):
    target_record(frame, 1)
    value = scan(frame, quiescent=True)
    assert "DISPATCH_AFTER_UNRECORDED_PLAN_ITEM" in value["metadata_issue_codes"]
    assert value["axes"]["target"]["terminal_metadata_prefix_records"] == 0


def test_active_lock_and_open_worker_prevent_quiescent_claim(frame):
    evidence(frame[0], "target-operation.lock.safe.json", {"contract_sha256": m.CONFIG_SHA})
    evidence(
        frame[0],
        "epochs/002/server-01.started.safe.json",
        {"contract_sha256": m.CONFIG_SHA, "started_at": "2026-09-05T20:00:00+00:00"},
    )
    value = scan(frame, quiescent=True)
    assert value["active_operation_lock_observed"] is True
    assert value["unclosed_worker_markers"] == 1
    assert value["quiescent_safe_accounting_consistent"] is False
    assert value["transient_states_may_be_inflight"] is True


def test_orphan_worker_stop_is_inconsistent_even_with_no_active_lock(frame):
    evidence(
        frame[0],
        "panel/qwen/worker.stopped.safe.json",
        {"contract_sha256": m.CONFIG_SHA, "stopped_at": "2026-09-05T21:00:00+00:00"},
    )
    value = scan(frame, quiescent=True)
    assert "WORKER_STOP_WITHOUT_START" in value["metadata_issue_codes"]
    assert value["quiescent_safe_accounting_consistent"] is False


def test_flat_panel_abort_is_attributed_to_correct_axis(frame):
    evidence(
        frame[0],
        "panel-jailmeter-aborted.safe.json",
        {"contract_sha256": m.CONFIG_SHA, "error_code": "DEADLINE_EXCEEDED"},
    )
    assert scan(frame)["abort_records"] == [
        {"area": "jailmeter", "reason_code": "DEADLINE_EXCEEDED"}
    ]


def test_stopped_worker_and_abort_are_reported_without_repair_or_certification(frame):
    for part, stamp in (("started", "20:00:00"), ("stopped", "20:01:00")):
        evidence(
            frame[0],
            f"epochs/002/server-01.{part}.safe.json",
            {
                "contract_sha256": m.CONFIG_SHA,
                f"{part}_at": f"2026-09-05T{stamp}+00:00",
                "pid": 123,
                "epoch": 1,
                "owned_process_only": True,
            },
        )
    evidence(
        frame[0],
        "generate-aborted.safe.json",
        {"contract_sha256": m.CONFIG_SHA, "error_code": "DEADLINE_EXCEEDED"},
    )
    value = scan(frame, quiescent=True)
    assert value["abort_records"] == [{"area": "target", "reason_code": "DEADLINE_EXCEEDED"}]
    assert value["unclosed_worker_markers"] == 0
    assert value["operational_certification_performed"] is False


@pytest.mark.parametrize(
    "area,field,changed",
    [
        ("target", "pid", 124),
        ("target", "pid", True),
        ("target", "epoch", 2),
        ("target", "owned_process_only", False),
        ("target", "owned_process_only", 1),
        ("qwen", "pid", 124),
        ("qwen", "axis", "jailmeter"),
        ("qwen", "epoch_index", 2),
        ("qwen", "worker_identity_sha256", "e" * 64),
        ("qwen", "bound_plan_identity_sha256", "e" * 64),
        ("jailmeter", "worker_identity_sha256", "e" * 64),
    ],
)
def test_wrong_worker_identity_cannot_close_started_marker(frame, area, field, changed):
    fixed = {"contract_sha256": m.CONFIG_SHA, "pid": 123}
    if area == "target":
        stem = "epochs/002/server-01"
        fixed.update(epoch=1, owned_process_only=True)
    else:
        stem = f"panel/{area}/worker"
        fixed.update(
            axis=area,
            epoch_index=1,
            bound_plan_identity_sha256=m.PLAN_ID,
            worker_identity_sha256=m.sha(m.canonical([m.CONFIG_SHA, area, 1])),
        )
    evidence(
        frame[0], stem + ".started.safe.json", {**fixed, "started_at": "2026-09-05T20:00:00+00:00"}
    )
    evidence(
        frame[0],
        stem + ".stopped.safe.json",
        {**fixed, "stopped_at": "2026-09-05T20:01:00+00:00", field: changed},
    )
    value = scan(frame, quiescent=True)
    assert "WORKER_PAIR_IDENTITY_MISMATCH" in value["metadata_issue_codes"]
    assert value["unclosed_worker_markers"] == 1
    assert value["quiescent_safe_accounting_consistent"] is False


@pytest.mark.parametrize("axis", ["qwen", "jailmeter"])
def test_matching_panel_worker_pair_is_metadata_consistent_not_operational_proof(frame, axis):
    fixed = {
        "contract_sha256": m.CONFIG_SHA,
        "pid": 123,
        "axis": axis,
        "epoch_index": 1,
        "bound_plan_identity_sha256": m.PLAN_ID,
        "worker_identity_sha256": m.sha(m.canonical([m.CONFIG_SHA, axis, 1])),
    }
    for part, stamp in (("started", "20:00:00"), ("stopped", "20:01:00")):
        evidence(
            frame[0],
            f"panel/{axis}/worker.{part}.safe.json",
            {**fixed, f"{part}_at": f"2026-09-05T{stamp}+00:00"},
        )
    value = scan(frame, quiescent=True)
    assert value["unclosed_worker_markers"] == 0
    assert value["quiescent_safe_accounting_consistent"] is True
    assert value["operational_certification_performed"] is False


def test_abort_unstructured_exception_content_is_redacted(frame):
    evidence(
        frame[0],
        "generate-aborted.safe.json",
        {"contract_sha256": m.CONFIG_SHA, "error_code": "Sensitive /path and prompt text"},
    )
    value = scan(frame)
    assert value["abort_records"][0]["reason_code"] == "UNRECOGNIZED_ERROR_CODE_REDACTED"
    assert b"Sensitive" not in m.canonical(value)


def test_concurrent_manifest_change_is_explicitly_nonatomic(frame, monkeypatch):
    real = m.manifest
    calls = []

    def racing(root):
        calls.append(None)
        result = real(root)
        if len(calls) == 2:
            result["target/new.safe.json"] = (1, 1)
        return result

    monkeypatch.setattr(m, "manifest", racing)
    value = scan(frame, quiescent=True)
    assert value["directory_metadata_changed_during_snapshot"] is True
    assert value["snapshot_is_atomic"] is False
    assert value["quiescent_safe_accounting_consistent"] is False


def test_changed_during_single_read_detected_without_any_retry():
    calls = []

    def stat():
        calls.append(None)
        return SimpleNamespace(st_size=2, st_mtime_ns=len(calls))

    fake = SimpleNamespace(stat=stat, is_file=lambda: True, open=lambda mode: io.BytesIO(b"{}"))
    with pytest.raises(m.InventoryError, match="FILE_CHANGED_DURING_READ"):
        m.read_bytes(fake)
    assert len(calls) == 2


def test_changed_during_snapshot_read_is_provisional_and_counted_as_attempt(frame, monkeypatch):
    target_record(frame)
    original = m.read_bytes

    def changed(path, *args):
        if str(path).endswith(".row.safe.json"):
            raise m.InventoryError("FILE_CHANGED_DURING_READ")
        return original(path, *args)

    monkeypatch.setattr(m, "read_bytes", changed)
    value = scan(frame, quiescent=True)
    assert value["safe_file_read_attempts"] == 4
    assert value["safe_files_read"] == value["successful_safe_file_reads"] == 3
    assert value["read_error_counts"] == {"FILE_CHANGED_DURING_READ": 1}
    assert value["directory_metadata_changed_during_snapshot"] is True
    assert value["transient_states_may_be_inflight"] is True
    assert value["quiescent_safe_accounting_consistent"] is False


def test_unapproved_private_analysis_census_and_samples_are_never_opened(frame, monkeypatch):
    for relative in (
        "target/unapproved.private.json",
        "analysis.safe.json",
        "census/a.safe.json",
        "panel/qwen/samples.safe.jsonl",
        "panel/qwen/worker.log.private.txt",
    ):
        evidence(frame[0], relative, {"private_marker": "NEVER_OPEN"})
    seen = []
    original = m.read_bytes

    def spy(path, *args):
        seen.append(str(path))
        return original(path, *args)

    monkeypatch.setattr(m, "read_bytes", spy)
    value = scan(frame)
    assert len(seen) == 2 and value["safe_files_read"] == 0
    assert not any("private.json" in path or "samples.safe.jsonl" in path for path in seen)


@pytest.mark.parametrize(
    "relative", ["../private.json", "/tmp/private", "a/../b", "a\\b", "C:/private", "a//b"]
)
def test_scoped_paths_reject_escape_and_aliases(frame, relative):
    with pytest.raises(m.InventoryError):
        m.scoped(frame[0], relative)


@pytest.mark.parametrize("kind", ["symlink", "reparse"])
def test_simulated_link_or_reparse_is_rejected_before_open(frame, monkeypatch, kind):
    write(frame[0], "blocked.safe.json", {"synthetic": True})
    if kind == "symlink":
        original = m.Path.is_symlink
        monkeypatch.setattr(
            m.Path, "is_symlink", lambda path: path.name == "blocked.safe.json" or original(path)
        )
    else:
        original = m.Path.lstat

        class ReparseInfo:
            st_file_attributes = 1024

            def __init__(self, observed):
                self.observed = observed

            def __getattr__(self, name):
                return getattr(self.observed, name)

        monkeypatch.setattr(
            m.Path,
            "lstat",
            lambda path: ReparseInfo(original(path))
            if path.name == "blocked.safe.json"
            else original(path),
        )
    with pytest.raises(m.InventoryError, match="LINK_OR_REPARSE_POINT_REJECTED"):
        m.scoped(frame[0], "blocked.safe.json")


def test_windows_long_paths_for_new_synthetic_safe_artifacts(frame):
    nested = frame[0] / ("x" * 110)
    nested.mkdir()
    relative = f"{m.SAFE}/{m.CONFIG_SHA}/target/" + "a" * 64 + ".row.safe.json"
    path = write(nested, relative, {"synthetic": True})
    assert len(str(path)) > 260
    assert m.strict(m.read_bytes(path)) == {"synthetic": True}


def test_wrong_external_hash_blocks_any_metadata_snapshot(frame, monkeypatch):
    monkeypatch.setattr(m, "manifest", lambda root: pytest.fail("must stop before metadata"))
    with pytest.raises(m.InventoryError, match="KNOWN_EXTERNAL_PINS_REQUIRED"):
        m.inventory(frame[0], "0" * 64, m.PLAN_SHA)


def test_changed_frozen_plan_bytes_are_rejected(frame):
    path = m.scoped(frame[0], m.PLAN)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(m.InventoryError, match="EXTERNAL_PIN_MISMATCH"):
        scan(frame)


def test_cli_has_no_execute_or_output_write_mode(frame, capsys):
    with pytest.raises(SystemExit) as error:
        m.main(["--execute"])
    assert error.value.code == 2
    capsys.readouterr()
    assert (
        m.main(
            [
                "--root",
                str(frame[0]),
                "--config-sha256",
                m.CONFIG_SHA,
                "--bound-plan-sha256",
                m.PLAN_SHA,
                "--quiescent",
            ]
        )
        == 0
    )
    value = m.strict(capsys.readouterr().out.encode())
    assert value["new_model_calls"] == value["files_written"] == 0


def test_cli_quiescent_ambiguous_dispatch_is_nonzero_without_retry(frame, capsys):
    target_record(frame, parts=("dispatch",))
    assert (
        m.main(
            [
                "--root",
                str(frame[0]),
                "--config-sha256",
                m.CONFIG_SHA,
                "--bound-plan-sha256",
                m.PLAN_SHA,
                "--quiescent",
            ]
        )
        == 2
    )
    value = m.strict(capsys.readouterr().out.encode())
    assert value["axes"]["target"]["state_counts"][m.STATES[4]] == 1
    assert value["new_model_calls"] == 0
