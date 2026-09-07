from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from jbspan.gate1.util import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/freeze_topology_transition_t0.py"
CONFIG = ROOT / "configs/natural_language_localization/topology_transition_t0_v1.json"
OUTPUT_ROOT = ROOT / "data/natural_language_localization/topology_transition_t0_v1"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("topology_transition_t0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


def test_replication_seeds_are_deterministic_and_predeclared() -> None:
    observed = RUNNER.derive_replication_seeds(
        "jbspan-topology-fresh-replication-v1",
        7,
        blocked=(11, 23, 47),
    )
    assert observed == (
        790543744,
        1033094226,
        793745811,
        1994540683,
        1909186786,
        1224512528,
        1998511070,
    )
    assert not set(observed).intersection({11, 23, 47})


def test_adjacent_coarsening_is_order_preserving_and_outcome_free() -> None:
    assert RUNNER.coarsen_adjacent(("u0", "u1", "u2")) == (
        ("u0", "u1"),
        ("u2",),
    )
    assert RUNNER.coarsen_adjacent(tuple(f"u{index}" for index in range(7))) == (
        ("u0", "u1"),
        ("u2", "u3"),
        ("u4", "u5"),
        ("u6",),
    )
    with pytest.raises(ValueError, match="unique"):
        RUNNER.coarsen_adjacent(("u0", "u0"))


def test_raw_key_guard_distinguishes_content_from_safe_metadata() -> None:
    safe = {
        "payload_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "human_label_observed": False,
        "nested": [{"stdout_sha256": "c" * 64}],
    }
    assert RUNNER.find_prohibited_keys(safe) == ()
    assert RUNNER.find_prohibited_keys({"nested": [{"response": "hidden"}]}) == (
        "$.nested[0].response",
    )


def test_atomic_write_once_refuses_a_different_frozen_artifact(tmp_path: Path) -> None:
    path = tmp_path / "safe.json"
    assert RUNNER.atomic_write_once(path, b"first\n") == "CREATED"
    assert RUNNER.atomic_write_once(path, b"first\n") == "REUSED_BYTE_IDENTICAL"
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        RUNNER.atomic_write_once(path, b"different\n")
    assert path.read_bytes() == b"first\n"


def test_selection_schema_is_label_blind_and_covers_all_frozen_p3_rows() -> None:
    p3_path = (
        ROOT
        / "data/natural_language_localization/p3_local_signal_screen_v1/p3_generation.safe.json"
    )
    p3 = json.loads(p3_path.read_text(encoding="utf-8"))
    rows = RUNNER.build_selection_rows(p3)
    assert len(rows) == 36
    assert all(set(row) == RUNNER.SELECTION_KEYS for row in rows)
    assert all(RUNNER.find_prohibited_keys(row) == () for row in rows)
    assert all(row["eligible_for_rescore"] is True for row in rows)
    assert len({row["record_id"] for row in rows}) == 36


def test_committed_t0_artifacts_revalidate_byte_identically() -> None:
    result = RUNNER.freeze(ROOT, CONFIG)
    assert result["status"] == "T0_TOPOLOGY_TRANSITION_PREFLIGHT_PASS"
    assert result["record_count"] == 36
    assert result["p3_panel_or_topology_outcome_observed"] is False
    assert set(result["write_actions"].values()) == {"REUSED_BYTE_IDENTICAL"}

    preflight_path = OUTPUT_ROOT / "t0_preflight.safe.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    identity = preflight.pop("result_identity_sha256")
    assert identity == canonical_json_sha256(preflight)
    assert preflight["passes_all"] is True
    assert all(preflight["checks"].values())
