from __future__ import annotations

import ast
import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_autodan_static_audit.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "e0_autodan_static_audit_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_e0_autodan_static_audit", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E0 AutoDAN audit script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_detects_official_lowercasing_replacement() -> None:
    module = load_script()
    source = ast.parse(
        """
class autodan_SuffixManager:
    def get_prompt(self, adv_string=None):
        if adv_string is not None:
            self.adv_string = adv_string.replace(
                '[REPLACE]', self.instruction.lower()
            )
"""
    )
    assert module.detect_official_payload_replacement(source, "[REPLACE]") is True


def test_materialization_separates_official_and_exact_adapter_routes() -> None:
    module = load_script()
    result = module.materialization_summary(
        "Prefix [REPLACE] suffix",
        "[REPLACE]",
        "JBSPAN_SAFE_PAYLOAD_A7F3",
        3,
    )
    official = cast(dict[str, object], result["official_route"])
    adapter = cast(dict[str, object], result["exact_placeholder_adapter"])
    assert official["byte_invariant"] is False
    assert official["exact_payload_occurrences"] == 0
    assert official["lowercased_payload_occurrences"] == 1
    assert adapter["payload_preserved"] is True
    assert adapter["exact_payload_occurrences"] == 1
    assert adapter["placeholder_occurrences_after_materialization"] == 0


def test_suffix_manager_wiring_requires_frozen_names() -> None:
    module = load_script()
    valid = ast.parse(
        """
suffix_manager = autodan_SuffixManager(
    tokenizer=tokenizer,
    conv_template=conv_template,
    instruction=user_prompt,
    target=target,
    adv_string=adv_suffix,
)
"""
    )
    invalid = ast.parse(
        """
suffix_manager = autodan_SuffixManager(
    tokenizer=tokenizer,
    conv_template=conv_template,
    instruction=rewritten_prompt,
    target=target,
    adv_string=adv_suffix,
)
"""
    )
    assert module.detect_suffix_manager_wiring(valid) is True
    assert module.detect_suffix_manager_wiring(invalid) is False


def test_frozen_contract_is_preoutcome_and_conditional() -> None:
    config = cast(
        dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8"))
    )
    assert config["status"] == "FROZEN_BEFORE_AUTODAN_STATIC_EXECUTION"
    assert config["frozen"] is True
    assert config["paper_validity"] is False
    assert str(config["synthetic_payload"]).startswith(
        "JBSPAN_E0_AUTODAN_SAFE_PAYLOAD_"
    )

    rules = cast(dict[str, object], config["rules"])
    assert rules["official_route_is_byte_invariant"] is False
    assert rules["binary_prompt_group_deserialization_allowed"] is False
    assert rules["real_harmful_payload_allowed"] is False
    assert rules["target_model_calls_allowed"] is False

    target = cast(dict[str, object], config["target_compatibility"])
    assert target["current_project_target_officially_supported"] is False
    assert target["generic_adapter_required_before_signal_screen"] is True

    admission = cast(dict[str, object], config["admission"])
    assert admission["balanced_signal_screen_admission_on_this_step"] is False
    assert len(cast(list[str], admission["required_follow_up"])) == 4

    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
