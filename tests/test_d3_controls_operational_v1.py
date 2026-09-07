from __future__ import annotations

from pathlib import Path

from scripts import run_d3_controls_operational_v1 as operational


def test_run_preserves_frozen_control_operation_and_reports_counts(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "contract.json"
    controls = tmp_path / "controls.safe.jsonl"
    summary = tmp_path / "summary.safe.json"
    selected = tmp_path / "selected.safe.jsonl"
    progress = tmp_path / "progress.safe.jsonl"
    paths = {
        "controls": controls,
        "control_summary": summary,
        "selected_controls": selected,
        "control_progress": progress,
    }
    rows = [{"record_id": "one"}, {"record_id": "two"}]
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
        lambda root, path: (path, {"contract": True}, {"verified": True}),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3, "extra_paths", lambda root, config: paths
    )

    def fake_controls(root: Path, path: Path) -> dict[str, object]:
        calls.append(("controls", root, path))
        controls.write_text("complete\n", encoding="utf-8")
        summary.write_text("complete\n", encoding="utf-8")
        selected.write_text("selected\n", encoding="utf-8")
        return {
            "status": "D3_EXACT_TOPOLOGY_CAPABILITY_CONTROLS_COMPLETE",
            "provisional_recovered_subset_count": 1,
            "capability_pass_count": 2,
            "capability_fail_count": 0,
        }

    monkeypatch.setattr(operational.d3, "run_controls", fake_controls)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3.engine,
        "load_jsonl",
        lambda path: rows if path in (controls, selected) else [],
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        operational.d3.engine, "file_sha256", lambda path: "a" * 64
    )

    result = operational.run(tmp_path, config_path)

    assert result["records_before"] == 0
    assert result["records_after"] == 2
    assert result["selected_control_records"] == 2
    assert result["provisional_candidate_subsets"] == 1
    assert result["capability_pass_count"] == 2
    assert result["capability_fail_count"] == 0
    assert result["replace_retries"] == 0
    assert result["scientific_rule_changed"] is False
    assert calls == [
        ("install",),
        ("patch", tmp_path),
        ("controls", tmp_path, config_path),
    ]
