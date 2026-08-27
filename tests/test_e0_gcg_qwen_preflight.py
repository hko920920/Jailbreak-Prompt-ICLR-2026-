from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_balanced_partition_is_exact() -> None:
    adapter = load_module("adapter", "scripts/gcg_qwen_adapter.py")
    ranges = adapter.balanced_ranges(20, 6)
    assert ranges == [(0, 4), (4, 8), (8, 11), (11, 14), (14, 17), (17, 20)]
    assert sum(stop - start for start, stop in ranges) == 20


def test_all_masks_and_positions_are_deterministic() -> None:
    adapter = load_module("adapter_masks", "scripts/gcg_qwen_adapter.py")
    ranges = adapter.balanced_ranges(20, 6)
    assert list(adapter.enumerate_masks(6)) == list(range(64))
    assert adapter.selected_positions(ranges, 0) == []
    assert adapter.selected_positions(ranges, 63) == list(range(20))


def test_token_slice_rejects_boundary_overlap() -> None:
    adapter = load_module("adapter_slice", "scripts/gcg_qwen_adapter.py")
    offsets = [(0, 2), (2, 4), (4, 6)]
    value = adapter.token_slice_for_char_span(offsets, 2, 6)
    assert (value.start, value.stop, value.length) == (1, 3, 2)
    try:
        adapter.token_slice_for_char_span(offsets, 1, 4)
    except ValueError as exc:
        assert "boundary" in str(exc)
    else:
        raise AssertionError("overlapping token boundary was not rejected")


def test_contract_preserves_sealed_boundaries() -> None:
    contract = json.loads(
        Path("configs/natural_language_localization/e0_gcg_qwen_preflight_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["coarse_partition"]["block_count"] == 6
    assert contract["coarse_partition"]["subset_count"] == 64
    assert contract["compatibility_gate"]["required_position_preserving_neutralizer_count"] == 2
    assert all(value is False for value in contract["sealed_boundaries"].values())


def test_installer_rejects_raw_fields() -> None:
    installer = load_module(
        "installer",
        "scripts/install_gcg_qwen_preflight_result.py",
    )
    safe = {
        "status": "E0_GCG_QWEN_PREFLIGHT_PASS",
        "model_weights_downloaded": False,
        "model_forward_pass": False,
        "model_generation": False,
        "real_harmful_payload_used": False,
        "attack_optimization_performed": False,
        "attack_success_observed": False,
        "raw_fixture_recorded": False,
        "raw_rendered_prompt_recorded": False,
        "raw_token_ids_recorded": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
    }
    installer.validate(safe)
    unsafe = dict(safe)
    unsafe["raw_prompt"] = "forbidden"
    try:
        installer.validate(unsafe)
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("raw field was not rejected")
