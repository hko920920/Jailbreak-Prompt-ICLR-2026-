"""Synthetic frozen-entrypoint tests; no project evidence, models or private reads."""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_reentry_v2 as m  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "CODE", ["scripts/new.py"])
    monkeypatch.setattr(m, "TESTS", ["tests/new.py"])
    for path in (*m.CODE, *m.TESTS, m.PROTOCOL, m.MANIFEST):
        full = tmp_path / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b"{}\n")
    import pa_reentry_evidence_v2 as evidence

    monkeypatch.setattr(evidence, "verify_manifest", lambda *args: {"verified": True})
    return tmp_path


def test_preparation_grants_no_model_authority_and_is_exclusive(tree):
    result = m.prepare(tree)
    frozen = m.verify_frozen(tree)
    assert result["new_model_calls"] == 0
    assert frozen["execution_authorized"] is False
    assert frozen["stage2_only"] is True
    assert frozen["target_missing"] == 388
    assert frozen["science_rows_per_axis"] == 882
    assert not (tree / "artifacts").exists()
    with pytest.raises(ValueError, match="ALREADY_PUBLISHED"):
        m.prepare(tree)


@pytest.mark.parametrize("key", ["code", "tests", "protocol", "archive_manifest"])
def test_changed_pinned_source_blocks_factory(tree, key):
    m.prepare(tree)
    frozen = m.verify_frozen(tree)
    pin = frozen[key][0] if isinstance(frozen[key], list) else frozen[key]
    (tree / pin["path"]).write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="FROZEN_PIN"):
        m.verify_frozen(tree)


@pytest.mark.parametrize(
    "key",
    [
        "target_missing",
        "automatic_next_stage",
        "scientific_rules_changed",
        "execution_authorized",
        "science_rows_per_axis",
    ],
)
def test_resealed_changed_policy_still_rejected(tree, key):
    m.prepare(tree)
    frozen = m.verify_frozen(tree)
    value = copy.deepcopy(frozen)
    value[key] = not value[key] if type(value[key]) is bool else value[key] - 1
    value.pop("execution_identity")
    (tree / m.CONFIG).write_bytes(m.j.canonical(m.j.seal(value, "execution_identity")))
    with pytest.raises(ValueError, match="FROZEN_PIN_OR_POLICY"):
        m.verify_frozen(tree)


@pytest.mark.parametrize(
    "path", ["../escape", "/absolute", "C:/outside", "a\\b", "a//b", "a/../b", "a./b", "a /b"]
)
def test_output_path_aliases_rejected(tree, path):
    with pytest.raises(ValueError):
        m.owned(tree, path, existing=False)


def test_cli_defaults_readonly_and_rejects_launch_flags(monkeypatch, capsys):
    monkeypatch.setattr(m, "verify_frozen", lambda root: {"execution_identity": "a" * 64})
    monkeypatch.setattr(m, "run_stage", lambda *args: pytest.fail("unexpected inference"))
    assert m.main([]) == 0
    assert '"new_model_calls":0' in capsys.readouterr().out
    with pytest.raises(ValueError, match="LAUNCH_FLAGS"):
        m.main(["verify-freeze", "--stage", "target"])


def test_run_stage_requires_current_direction_before_loading(monkeypatch):
    monkeypatch.setattr(m, "load_context", lambda root: pytest.fail("not authorized"))
    with pytest.raises(ValueError, match="CURRENT_STAGE_DIRECTION"):
        m.run_stage(Path("unused"), "target", None)
    with pytest.raises(ValueError, match="CURRENT_STAGE_DIRECTION"):
        m.run_stage(Path("unused"), "all", "synthetic")


def test_target_entrypoint_stops_at_target_stage(monkeypatch):
    calls = []
    target = SimpleNamespace(
        execution_identity="a" * 64, run=lambda auth: calls.append(auth) or {"complete": True}
    )
    monkeypatch.setattr(m, "load_context", lambda root: ({}, target))
    monkeypatch.setattr(m, "payloads", lambda target: pytest.fail("next stage not allowed"))
    assert m.run_stage(Path("unused"), "target", "synthetic-later-target-direction")["complete"]
    assert len(calls) == 1 and calls[0]["stage"] == "target"


def test_cli_invalid_report_does_not_launch(monkeypatch):
    monkeypatch.setattr(
        m, "run_stage", lambda *args, **kwargs: pytest.fail("invalid flags must not launch")
    )
    with pytest.raises(ValueError, match="REPORT_SCOPE"):
        m.main(
            [
                "run-stage",
                "--stage",
                "target",
                "--direction-ref",
                "synthetic",
                "--report",
                "outside.json",
            ]
        )


def test_review_only_entrypoint_does_not_dispatch(monkeypatch):
    observed = []
    target = SimpleNamespace(
        execution_identity="a" * 64,
        review_interrupted_epoch=lambda epoch, auth: observed.append((epoch, auth["stage"]))
        or {"reviewed": True},
        run=lambda auth: pytest.fail("review is not a launch"),
    )
    monkeypatch.setattr(m, "load_context", lambda root: ({}, target))
    assert m.run_stage(
        Path("unused"), "target", "synthetic-reviewed-direction", mode="review", epoch="e" * 32
    )["reviewed"]
    assert observed == [("e" * 32, "target")]


def test_bad_review_arguments_rejected_before_loading(monkeypatch):
    monkeypatch.setattr(m, "load_context", lambda root: pytest.fail("invalid action"))
    with pytest.raises(ValueError, match="ACTION_OR_EPOCH"):
        m.run_stage(Path("unused"), "target", "synthetic", mode="review")


def test_target_recovery_uses_same_run_lock(tmp_path, monkeypatch):
    from contextlib import contextmanager

    held = []

    @contextmanager
    def lock(path):
        assert path == tmp_path / "run.lock"
        held.append(True)
        try:
            yield
        finally:
            held.pop()

    def recover(**kwargs):
        assert held and kwargs == {"recover": True, "require_released": True}
        return [{"state": "COMPLETE"}]

    target = SimpleNamespace(
        execution_identity="a" * 64,
        safe=tmp_path,
        assert_launch_ready=lambda: None,
        states=recover,
        journal=SimpleNamespace(event=lambda *a, **k: None),
    )
    monkeypatch.setattr(m, "load_context", lambda root: ({}, target))
    monkeypatch.setattr(m.j, "run_lock", lock)
    result = m.run_stage(tmp_path, "target", "synthetic-current-direction", mode="recover")
    assert result["completed"] == 1 and not held


def test_payloads_are_original_bytes_not_rerendered():
    original = "An invented harmless request.\n"
    target = SimpleNamespace(
        historical=SimpleNamespace(payloads_by_position=lambda: {3: original}),
        plan={
            "population": [
                {"payload_position": 3, "payload_sha256": m.j.sha_bytes(original.encode())}
            ]
        },
    )
    assert m.payloads(target) == {3: original}
    target.historical.payloads_by_position = lambda: {3: original.strip()}
    with pytest.raises(ValueError, match="PAYLOAD_BYTES_CHANGED"):
        m.payloads(target)


def test_target_weights_are_rehashed_at_launch(tmp_path):
    path = tmp_path / "artifacts" / "model.bin"
    path.parent.mkdir()
    path.write_bytes(b"fake weights")
    pin = m.pin(tmp_path, "artifacts/model.bin")
    config = {"model": {"files": [pin]}, "runtime": {"files": [], "server": pin}}
    assert m.verify_target_assets(tmp_path, config) == 2
    path.write_bytes(b"fake weight!")
    with pytest.raises(ValueError, match="PIN_SHA"):
        m.verify_target_assets(tmp_path, config)


def test_descendant_reparse_output_rejected_without_symlink_privilege(tmp_path, monkeypatch):
    base = tmp_path / "output" / "target"
    base.mkdir(parents=True)
    old = Path.lstat

    def observe(path, *args, **kwargs):
        result = old(path, *args, **kwargs)
        if path.name == "target":
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=1024)
        return result

    monkeypatch.setattr(Path, "lstat", observe)
    with pytest.raises(ValueError, match="REPARSE"):
        m.verify_output_tree(tmp_path, "output")
