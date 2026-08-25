from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_runtime_probe_v2.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_runtime_artifact_probe_v2.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_runtime_probe_v2", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E1C runtime probe v2 script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLfs:
    def __init__(self, sha256: str, size: int) -> None:
        self.sha256 = sha256
        self.size = size


class FakeSibling:
    def __init__(self, filename: str, lfs: object) -> None:
        self.rfilename = filename
        self.size = None
        self.lfs = lfs


def test_sibling_metadata_preserves_exact_identity() -> None:
    module = load_script()
    digest = "a" * 64
    sibling = FakeSibling(
        "HarmBench-Llama-2-13b-cls.Q4_K_M.gguf",
        FakeLfs(digest, 7_900_000_000),
    )
    assert module.sibling_metadata(sibling) == {
        "filename": "HarmBench-Llama-2-13b-cls.Q4_K_M.gguf",
        "size": 7_900_000_000,
        "sha256": digest,
    }


def test_immutable_revision_is_exactly_a_hex_commit() -> None:
    module = load_script()
    assert module.immutable_revision("a1" * 20) is True
    assert module.immutable_revision("a" * 39) is False
    assert module.immutable_revision("z" * 40) is False
    assert module.immutable_revision(None) is False


def test_v2_contract_follows_candidate_1_rejection_before_live_outputs() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["status"] == "FROZEN_BEFORE_E1C_RUNTIME_ARTIFACT_V2_METADATA_QUERY"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False

    predecessors = cast(dict[str, object], contract["predecessors"])
    rejected = cast(dict[str, object], predecessors["candidate_1_rejection"])
    assert rejected["required_status"] == "E1C_RUNTIME_ARTIFACT_PROBE_FAIL"
    assert rejected["required_operational_pass"] is False
    assert rejected["required_next_operation"] == (
        "SELECT_NEW_RUNTIME_ARTIFACT_BEFORE_ANY_E1C_LIVE_OUTPUT"
    )
    assert rejected["rejected_repository"] == (
        "tensorblock/HarmBench-Llama-2-13b-cls-GGUF"
    )

    candidate = cast(dict[str, object], contract["candidate_runtime_artifact"])
    selection = cast(dict[str, object], candidate["filename_selection"])
    assert candidate["repository"] == "mradermacher/HarmBench-Llama-2-13b-cls-GGUF"
    assert candidate["quantization"] == "Q4_K_M"
    assert selection["required_prefix"] == "HarmBench-Llama-2-13b-cls."
    assert selection["required_suffix"] == ".Q4_K_M.gguf"
    assert selection["required_match_count"] == 1
    assert candidate["silent_artifact_substitution_allowed"] is False
    assert candidate["fallback_quantization_allowed_without_new_contract"] is False

    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
