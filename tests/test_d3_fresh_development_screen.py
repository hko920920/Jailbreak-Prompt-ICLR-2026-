from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_d3_fresh_development_screen.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_d3_fresh_screen", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def pairs(status: str, h4: int, deep: int) -> list[dict]:
    rows = []
    for family, count in (("h4rm3l", h4), ("DeepInception", deep)):
        for index in range(count):
            rows.append(
                {
                    "pair_id": f"{family}-{index}",
                    "payload_position": index,
                    "payload_sha256": f"payload-{family}-{index}",
                    "attack_family": family,
                    "status": status,
                    "completed_seeds": [11],
                    "reason_codes": [],
                }
            )
    return rows


def test_early_route_requires_six_total_and_two_per_family() -> None:
    passing = MODULE.routing(pairs("ADVANCE", 4, 2), completed_seed=11)
    assert passing["route"] == "ADVANCE_D3_TO_SEED_23"
    assert passing["may_execute_next_seed"] is True
    too_few_total = MODULE.routing(pairs("ADVANCE", 3, 2), completed_seed=11)
    assert too_few_total["route"] == "STOP_D3_SCREEN_STABLE_PAIR_GATE_NO_LONGER_REACHABLE"
    too_few_family = MODULE.routing(pairs("ADVANCE", 5, 1), completed_seed=11)
    assert too_few_family["may_execute_next_seed"] is False


def test_terminal_route_and_all_stable_selection() -> None:
    rows = pairs("STABLE_PAIR", 4, 2)
    route = MODULE.routing(rows, completed_seed=47)
    assert route["route"] == "AUTHORIZE_D3_EXACT_TOPOLOGY_ON_ALL_STABLE_PAIRS"
    selected = MODULE.stable_pairs(rows)
    assert len(selected) == 6
    assert {row["attack_family"] for row in selected} == {
        "h4rm3l",
        "DeepInception",
    }


def test_terminal_route_rejects_unreachable_family_balance() -> None:
    route = MODULE.routing(pairs("STABLE_PAIR", 5, 1), completed_seed=47)
    assert route["route"] == "STOP_D3_SCREEN_STABLE_PAIR_GATE_FAILED"
