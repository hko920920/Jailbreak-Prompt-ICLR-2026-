from __future__ import annotations

import importlib.util
from pathlib import Path

from jbspan.gate1.step3b import WrapperNode


def module():
    path = Path("scripts/run_gate1_exact_oracle.py")
    spec = importlib.util.spec_from_file_location("oracle", path)
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_subsets_and_minimal_sets() -> None:
    value = module()
    subsets = value.all_nonempty_subsets(3)
    assert len(subsets) == 7
    assert value.minimal_sets([(0,), (0, 1), (1, 2)]) == [(0,), (1, 2)]


def test_both_neutralizers_preserve_payload() -> None:
    value = module()
    nodes = (
        WrapperNode("a", 0, "A<", ">A"),
        WrapperNode("b", 0, "B<", ">B"),
    )
    payload = "PAYLOAD"
    disabled, selected = value.render_intervention(
        candidate_id="candidate",
        payload_text=payload,
        nodes=nodes,
        selected_positions=(0,),
        neutralizer="typed_disable_v1",
    )
    replaced, _ = value.render_intervention(
        candidate_id="candidate",
        payload_text=payload,
        nodes=nodes,
        selected_positions=(0,),
        neutralizer="typed_neutral_replace_v1",
    )
    assert disabled.count(payload) == 1
    assert replaced.count(payload) == 1
    assert selected == ("n0:a:0",)
