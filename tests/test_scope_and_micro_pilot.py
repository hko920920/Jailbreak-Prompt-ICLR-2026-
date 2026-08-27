from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "scripts/validate_scope_and_micro_pilot.py"
    spec = importlib.util.spec_from_file_location("scope_validator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_scope_and_pilot_pass() -> None:
    root = Path(__file__).parents[1]
    module = load_module()
    result = module.validate(
        root / "configs/natural_language_localization/paper_scope_decision_v2.json",
        root / "configs/natural_language_localization/topology_micro_pilot_v1.json",
    )
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["next_authorized_operation"] == (
        "FREEZE_TARGET_MODEL_PAYLOAD_HASHES_DECODING_AND_AUDIT_PACKET_FORMAT"
    )
