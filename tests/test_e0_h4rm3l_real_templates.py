from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_h4rm3l_real_templates.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "e0_h4rm3l_real_templates_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("run_e0_h4rm3l_real_templates", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load h4rm3l real-template script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_template_contract_has_frozen_budget() -> None:
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert config["status"] == "FROZEN_BEFORE_H4RM3L_REAL_TEMPLATE_EXECUTION"
    assert config["frozen"] is True
    assert config["paper_validity"] is False

    programs = cast(list[dict[str, object]], config["programs"])
    component_counts = [
        len(cast(list[str], program["expected_components"])) for program in programs
    ]
    assert component_counts == [3, 2, 2, 2, 1, 1, 1]
    expected_subsets = sum((2**count) - 1 for count in component_counts)
    assert expected_subsets == 19

    budget = cast(dict[str, object], config["subset_budget"])
    assert budget["expected_program_count"] == 7
    assert budget["expected_component_count"] == 12
    assert budget["expected_subset_count"] == 19
    assert budget["expected_neutralized_variant_count"] == 38


def test_real_templates_use_only_allowlisted_deterministic_components() -> None:
    typed_path = ROOT / "scripts" / "run_e0_h4rm3l_typed_units.py"
    spec = importlib.util.spec_from_file_location("typed_support_for_test", typed_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load typed-unit support")
    typed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(typed)
    static = typed.load_static_audit_module()

    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    allowed = set(cast(list[str], config["allowed_components"]))
    for program in cast(list[dict[str, object]], config["programs"]):
        expression = str(program["expression"])
        expected = cast(list[str], program["expected_components"])
        observed = static.components_from_expression(expression, allowed=allowed)
        assert observed == expected
        assert len(typed.component_call_sources(expression)) == len(expected)


def test_real_template_boundary_forbids_scoring_and_target_calls() -> None:
    module = load_script()
    assert callable(module.run_audit)
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert boundary == {
        "real_harmful_payload_used": False,
        "target_model_called": False,
        "attack_success_scored": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
    }
    assert config["synthetic_payload"] == "JBSPAN_E0_SAFE_PAYLOAD_7B3F_DO_NOT_TRANSFORM"
