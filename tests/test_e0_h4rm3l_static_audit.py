from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_e0_h4rm3l_static_audit.py"
CONFIG = ROOT / "configs" / "natural_language_localization" / "e0_h4rm3l_static_audit_v1.json"


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("run_e0_h4rm3l_static_audit", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E0 h4rm3l audit script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_component_parser_preserves_composition_order() -> None:
    module = load_script()
    expression = (
        "RoleplayingDecorator(prefix='x', suffix='y')"
        ".then(RefusalSuppressionDecorator(suppression_message='z'))"
        ".then(AffirmativePrefixInjectionDecorator(affirmative_prefix='a'))"
    )
    allowed = {
        "RoleplayingDecorator",
        "RefusalSuppressionDecorator",
        "AffirmativePrefixInjectionDecorator",
    }
    observed = module.components_from_expression(expression, allowed=allowed)
    assert observed == [
        "RoleplayingDecorator",
        "RefusalSuppressionDecorator",
        "AffirmativePrefixInjectionDecorator",
    ]


def test_component_parser_rejects_non_allowlisted_or_dynamic_code() -> None:
    module = load_script()
    with pytest.raises(ValueError, match="not allowlisted"):
        module.components_from_expression("ReverseDecorator()", allowed={"IdentityDecorator"})
    with pytest.raises(ValueError, match="non-literal"):
        module.components_from_expression(
            "RoleplayingDecorator(prefix=get_prefix(), suffix='x')",
            allowed={"RoleplayingDecorator"},
        )
    with pytest.raises(ValueError, match="only allowlisted"):
        module.components_from_expression(
            "IdentityDecorator().decorate('x')",
            allowed={"IdentityDecorator"},
        )


def test_frozen_contract_manifests_are_preoutcome_and_consistent() -> None:
    module = load_script()
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert config["status"] == "FROZEN_BEFORE_H4RM3L_STATIC_EXECUTION"
    assert config["frozen"] is True
    assert config["paper_validity"] is False

    boundary = cast(dict[str, object], config["sealed_boundaries"])
    assert boundary == {
        "real_harmful_payload_used": False,
        "target_model_called": False,
        "cross_regime_stage_a_opened": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }

    allowed = set(cast(list[str], config["allowed_components"]))
    blocked = set(cast(list[str], config["payload_mutating_or_model_rewriting_components"]))
    assert allowed.isdisjoint(blocked)

    expressions = cast(list[dict[str, object]], config["expressions"])
    assert len(expressions) >= 6
    for row in expressions:
        observed = module.components_from_expression(str(row["expression"]), allowed=allowed)
        assert observed == cast(list[str], row["expected_components"])
        assert blocked.isdisjoint(observed)


def test_synthetic_payload_is_nonempty_and_not_embedded_in_expression() -> None:
    config = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    payload = str(config["synthetic_payload"])
    assert payload.startswith("JBSPAN_E0_SAFE_PAYLOAD_")
    assert len(payload) >= 24
    for row in cast(list[dict[str, object]], config["expressions"]):
        assert payload not in str(row["expression"])
