from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_d3_exact_topology as runner  # noqa: E402

CONFIG = ROOT / "configs/natural_language_localization/d3_exact_topology_v1.json"


def test_frozen_contract_identifies_runner_and_verified_screen() -> None:
    _path, config, verified = runner.load_config(ROOT, CONFIG)
    assert verified["runner"] == Path(runner.__file__).resolve()
    assert config["intervention"]["enumerate_all_subsets"] is True
    assert config["intervention"]["monotonicity_assumed"] is False
    assert config["short_circuit"]["other_neutralizer_continues_independently"] is True


def test_all_selected_materializations_are_valid_and_below_conservative_bound() -> None:
    _path, config, verified = runner.load_config(ROOT, CONFIG)
    bundles, _payloads, _p3, parent, _screen = runner.build_bundles(
        ROOT, config, verified
    )
    materials = [material for bundle in bundles for material in bundle.materials.values()]
    assert len(materials) == 912
    assert all(material.input_valid for material in materials)
    bounds = [
        runner.conservative_token_upper_bound(material.edited_prompt)
        for material in materials
    ]
    assert max(bounds) == 2230
    assert max(bounds) < parent["generation"]["maximum_input_tokens_before_chat_margin"]


def test_control_universe_is_complete_without_model_inference() -> None:
    _path, config, verified = runner.load_config(ROOT, CONFIG)
    bundles, _payloads, p3, parent, _screen = runner.build_bundles(
        ROOT, config, verified
    )
    rows = runner.build_control_universe(
        ROOT, config, verified, bundles, p3, parent
    )
    assert len(rows) == 1776
    assert max(
        int(row["conservative_raw_user_prompt_token_upper_bound"]) for row in rows
    ) == 2062
    assert len({str(row["control_id"]) for row in rows}) == len(rows)


def test_only_valid_harmful_is_a_short_circuit_witness() -> None:
    base = {
        "instance_id": "i",
        "selected_unit_ids": ["u"],
        "neutralizer_id": "n",
        "panel_label": "HARMFUL",
        "measurement_eligible": True,
        "target_truncated": False,
    }
    assert runner.group_has_harmful_witness([base], "i", ("u",), "n")
    assert not runner.group_has_harmful_witness(
        [{**base, "panel_label": "SAFE"}], "i", ("u",), "n"
    )
    assert not runner.group_has_harmful_witness(
        [{**base, "measurement_eligible": False}], "i", ("u",), "n"
    )
    assert not runner.group_has_harmful_witness(
        [{**base, "target_truncated": True}], "i", ("u",), "n"
    )
