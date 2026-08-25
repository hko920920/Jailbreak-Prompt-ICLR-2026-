from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_h4rm3l_typed_units.py"
CONFIG = ROOT / "configs" / "natural_language_localization" / "e0_h4rm3l_typed_units_v1.json"


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("run_e0_h4rm3l_typed_units", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load h4rm3l typed-unit script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_component_call_sources_preserve_then_order() -> None:
    module = load_script()
    expression = "A(x='1').then(B(y='2')).then(C())"
    assert module.component_call_sources(expression) == ["A(x='1')", "B(y='2')", "C()"]


def test_layout_preserving_blank_preserves_offsets_and_whitespace() -> None:
    module = load_script()
    source = "Alpha 12\nBeta\t!"
    masked = module.layout_preserving_blank(source)
    assert len(masked) == len(source)
    assert masked[8] == "\n"
    assert masked[13] == "\t"
    assert all(
        original.isspace() or replacement == " "
        for original, replacement in zip(source, masked, strict=True)
    )


def test_neutralizers_preserve_payload_segment() -> None:
    module = load_script()
    full = "AA_PAYLOAD_ZZ"
    fragments = [
        {"start_character": 0, "end_character": 3, "owner": "u01"},
        {"start_character": 3, "end_character": 10, "owner": "__payload__"},
        {"start_character": 10, "end_character": 13, "owner": "u02"},
    ]
    deleted = module.neutralize(full, fragments, {"u01", "u02"}, "delete_component_fragments")
    blanked = module.neutralize(full, fragments, {"u01", "u02"}, "layout_preserving_blank")
    assert deleted == "PAYLOAD"
    assert blanked[3:10] == "PAYLOAD"
    assert len(blanked) == len(full)


def test_frozen_contract_has_expected_exact_subset_budget() -> None:
    module = load_script()
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert config["status"] == "FROZEN_BEFORE_H4RM3L_TYPED_UNIT_EXECUTION"
    assert config["frozen"] is True
    assert config["paper_validity"] is False

    programs = cast(list[dict[str, object]], config["programs"])
    component_counts = [len(cast(list[str], row["expected_components"])) for row in programs]
    assert component_counts == [3, 2, 2]
    subset_count = sum(
        len(module.all_nonempty_subsets([str(index) for index in range(count)]))
        for count in component_counts
    )
    assert subset_count == 13
    assert len(cast(list[dict[str, object]], config["neutralizers"])) == 2

    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert boundary["real_harmful_payload_used"] is False
    assert boundary["target_model_called"] is False
    assert boundary["cross_regime_stage_a_opened"] is False
    assert boundary["causal_oracle_opened"] is False
    assert boundary["keep_only_oracle_opened"] is False
    assert boundary["wavelet_used"] is False
