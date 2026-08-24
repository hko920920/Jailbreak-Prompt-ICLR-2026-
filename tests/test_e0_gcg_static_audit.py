from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_gcg_static_audit.py"


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("run_e0_gcg_static_audit", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load GCG static audit script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_config_assignments_extract_literal_values(tmp_path: Path) -> None:
    module = load_script()
    source = tmp_path / "template.py"
    source.write_text(
        "def get_config():\n"
        "    config = object()\n"
        "    config.attack = 'gcg'\n"
        "    config.n_steps = 500\n"
        "    config.allow_non_ascii = False\n"
        "    config.dynamic = make_value()\n"
        "    return config\n",
        encoding="utf-8",
    )
    assert module.config_assignments(source) == {
        "attack": "gcg",
        "n_steps": 500,
        "allow_non_ascii": False,
    }


def test_equal_block_ranges_require_divisibility() -> None:
    module = load_script()
    assert module.equal_block_ranges(20, 4) == (
        (0, 5),
        (5, 10),
        (10, 15),
        (15, 20),
    )
    with pytest.raises(ValueError):
        module.equal_block_ranges(19, 4)


def test_nonempty_subsets_and_intervals_are_complete() -> None:
    module = load_script()
    subsets = module.all_nonempty_subsets(4)
    intervals = module.all_contiguous_intervals(4)
    assert len(subsets) == 15
    assert len(set(subsets)) == 15
    assert len(intervals) == 10
    assert (0, 1, 2, 3) in subsets
    assert (1, 2) in intervals
    assert (0, 2) not in intervals


def test_position_preserving_neutralization_changes_only_selected_blocks() -> None:
    module = load_script()
    units = tuple(f"u{index}" for index in range(20))
    ranges = module.equal_block_ranges(20, 4)
    changed = module.neutralize_blocks(units, ranges, (1, 3), ".")
    assert len(changed) == len(units)
    assert changed[:5] == units[:5]
    assert changed[5:10] == (".",) * 5
    assert changed[10:15] == units[10:15]
    assert changed[15:20] == (".",) * 5


def test_goal_bytes_remain_prefix_and_exactly_once() -> None:
    module = load_script()
    goal = "JBSPAN_GCG_SAFE_GOAL_TEST"
    units = tuple("!" for _ in range(20))
    ranges = module.equal_block_ranges(20, 4)
    for subset in module.all_nonempty_subsets(4):
        changed = module.neutralize_blocks(units, ranges, subset, ".")
        composed = f"{goal} {' '.join(changed)}"
        assert composed.encode().startswith(goal.encode())
        assert composed.count(goal) == 1
        assert len(changed) == 20
