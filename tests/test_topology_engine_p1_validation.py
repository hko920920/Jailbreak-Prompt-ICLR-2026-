from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_topology_engine_p1.py"
RESULT = (
    ROOT
    / "data/natural_language_localization/topology_engine_p1_v1_1/p1_gate.safe.json"
)
HISTORICAL_RESULT = (
    ROOT
    / "data/natural_language_localization/topology_engine_p1_v1/p1_gate.safe.json"
)


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_topology_engine_p1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_p1_validator_passes_without_target_outputs() -> None:
    result = load_validator().validate(ROOT)
    assert result["status"] == "P1_EXACT_TOPOLOGY_ENGINE_GATE_PASS"
    assert result["paper_validity"] is False
    assert result["target_model_called"] is False
    assert result["harmful_payload_used"] is False
    assert all(result["safe_synthetic_self_checks"].values())


def test_committed_p1_result_matches_fresh_validation() -> None:
    observed = json.loads(RESULT.read_text(encoding="utf-8"))
    assert observed == load_validator().validate(ROOT)


def test_historical_p1_dependency_is_preserved_byte_identically() -> None:
    assert hashlib.sha256(HISTORICAL_RESULT.read_bytes()).hexdigest() == (
        "7aae440ba84398db6958d4f2d6f08e46bf69c3de8b260dc3dd352a41a9f954b3"
    )
    observed = json.loads(HISTORICAL_RESULT.read_text(encoding="utf-8"))
    assert observed["result_identity_sha256"] == (
        "360427235f8954723cb6de4d001f12d4fb541285301096d5b15dd220b5c6d2f4"
    )
