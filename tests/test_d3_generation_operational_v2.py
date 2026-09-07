from __future__ import annotations

from pathlib import Path

from scripts import resume_d3_generation_operational_v2 as operational


def test_ensure_plan_uses_frozen_adaptive_planner_and_verifies_bytes(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    plan_path = tmp_path / "phase_23_plan.safe.jsonl"
    plans = [{"record_id": "one"}, {"record_id": "two"}]
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3, "install_engine_patches", lambda: calls.append(("install",))
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3.d3_screen,
        "patch_extractor",
        lambda root: calls.append(("patch", root)),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3,
        "load_config",
        lambda root, path: (path, {"config": True}, {"verified": True}),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3,
        "ensure_phase_plan",
        lambda root, path, config, verified, seed: (
            calls.append(("ensure", root, path, config, verified, seed)) or plans,
            [],
            {},
            object(),
            {},
        ),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3.engine,
        "phase_paths",
        lambda root, config, seed: {"plan": plan_path},
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3.engine, "load_jsonl", lambda path: plans
    )

    count, persisted_path = operational.ensure_plan(tmp_path, config_path, 23)

    assert count == 2
    assert persisted_path == plan_path
    assert calls == [
        ("install",),
        ("patch", tmp_path),
        (
            "ensure",
            tmp_path,
            config_path,
            {"config": True},
            {"verified": True},
            23,
        ),
    ]
