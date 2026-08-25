from __future__ import annotations

import importlib.util
import json
import types
from collections import Counter
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_selection_repair.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_selection_repair_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_selection_repair", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load selection-repair script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(record_id: str, behavior: str, label: int) -> dict[str, object]:
    return {
        "record_id": record_id,
        "behavior_id_private": behavior,
        "behavior_hash": behavior,
        "label": label,
        "human_unanimous": True,
    }


def test_balanced_selection_filters_unresolvable_behavior() -> None:
    module = load_script()
    records = [
        row("a0", "a", 0),
        row("b0", "b", 0),
        row("x0", "missing", 0),
        row("a1", "a", 0),
        row("b1", "b", 0),
        row("c1", "c", 1),
        row("d1", "d", 1),
        row("c2", "c", 1),
        row("d2", "d", 1),
    ]
    selected = module.select_balanced(
        records,
        per_label=2,
        allowed_behavior_ids={"a", "b", "c", "d"},
    )
    assert len(selected) == 4
    assert all(item["behavior_id_private"] != "missing" for item in selected)
    assert Counter(int(item["label"]) for item in selected) == Counter({0: 2, 1: 2})
    assert selected == module.select_balanced(
        records,
        per_label=2,
        allowed_behavior_ids={"a", "b", "c", "d"},
    )


def test_resolvable_registry_requires_declared_fields() -> None:
    module = load_script()
    text = {
        "ok": {"Behavior": "x", "ContextString": ""},
        "no_context": {"Behavior": "x"},
    }
    multimodal = {
        "multi": {"Behavior": "y", "ContextString": "ctx"},
    }
    observed = module.resolvable_behavior_ids(
        text,
        multimodal,
        "Behavior",
        "ContextString",
    )
    assert observed == {"ok", "multi"}


def test_frozen_contract_preserves_no_live_output_boundary() -> None:
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert config["status"] == "FROZEN_BEFORE_E1C_SELECTION_REPAIR"
    assert config["frozen"] is True
    assert config["paper_validity"] is False
    predecessor = cast(dict[str, object], config["predecessor"])
    assert predecessor["expected_selected_missing_registry_row_count"] == 3
    assert len(cast(list[str], predecessor["expected_selected_missing_behavior_hashes"])) == 2
    new_selection = cast(dict[str, object], config["new_selection"])
    assert new_selection["expected_dropped_record_count"] == 3
    assert new_selection["expected_added_record_count"] == 3
    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
