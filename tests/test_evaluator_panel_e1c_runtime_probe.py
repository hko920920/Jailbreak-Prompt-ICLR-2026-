from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_runtime_probe.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_runtime_artifact_probe_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_runtime_probe", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E1C runtime probe script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLfs:
    def __init__(self, sha256: str, size: int) -> None:
        self.sha256 = sha256
        self.size = size


class FakeSibling:
    def __init__(self, lfs: object) -> None:
        self.rfilename = "candidate.gguf"
        self.size = None
        self.lfs = lfs


def test_immutable_revision_requires_exact_hex_commit() -> None:
    module = load_script()
    assert module.immutable_revision("a" * 40) is True
    assert module.immutable_revision("A1" * 20) is True
    assert module.immutable_revision("g" * 40) is False
    assert module.immutable_revision("a" * 39) is False
    assert module.immutable_revision(None) is False


def test_sibling_metadata_reads_object_and_mapping_lfs() -> None:
    module = load_script()
    digest = "b" * 64
    object_metadata = module.sibling_metadata(FakeSibling(FakeLfs(digest, 7_500_000_000)))
    mapping_metadata = module.sibling_metadata(
        FakeSibling({"sha256": digest, "size": 7_500_000_000})
    )
    expected = {
        "filename": "candidate.gguf",
        "size": 7_500_000_000,
        "sha256": digest,
    }
    assert object_metadata == expected
    assert mapping_metadata == expected


def test_runtime_probe_contract_is_frozen_before_live_outputs() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["status"] == "FROZEN_BEFORE_E1C_RUNTIME_ARTIFACT_METADATA_QUERY"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False
    predecessor = cast(dict[str, object], contract["predecessor"])
    assert predecessor["required_status"] == "E1C_HARMBENCH_PREFLIGHT_PASS"
    assert predecessor["required_next_operation"] == (
        "FREEZE_E1C_HARMBENCH_LIVE_REPRODUCTION_AND_CANARY_CONTRACT"
    )
    candidate = cast(dict[str, object], contract["candidate_runtime_artifact"])
    assert candidate["repository"] == "tensorblock/HarmBench-Llama-2-13b-cls-GGUF"
    assert candidate["filename"] == "HarmBench-Llama-2-13b-cls-Q4_K_M.gguf"
    assert candidate["quantization"] == "Q4_K_M"
    assert candidate["silent_artifact_substitution_allowed"] is False
    assert candidate["fallback_quantization_allowed_without_new_contract"] is False
    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
