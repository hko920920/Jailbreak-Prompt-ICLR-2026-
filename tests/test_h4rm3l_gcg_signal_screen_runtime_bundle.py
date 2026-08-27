from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/freeze_h4rm3l_gcg_signal_screen_runtime_bundle.py"
SPEC = importlib.util.spec_from_file_location("runtime_bundle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_git_blob_sha_matches_git_object_framing(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("abc\n", encoding="utf-8")
    assert MODULE.git_blob_sha(path) == "8baef1b4abc478178b004d62031cf7fe6db6f903"


def test_readiness_blocks_unfrozen_gpu_contract() -> None:
    contract = {
        "target_model": {
            "differentiable_optimizer_runtime": {
                "gradient_enabled": True,
                "quantization": "none",
                "device_type": "cuda",
                "runner_contract_frozen": False,
                "runner_labels": [],
                "minimum_free_device_memory_bytes": None,
                "maximum_wall_clock_minutes": None,
                "private_cache_contract_frozen": False,
            }
        }
    }
    result = MODULE.evaluate_readiness(contract)
    assert result["execution_ready"] is False
    assert result["checks"]["gradient_enabled"] is True
    assert result["checks"]["runner_contract_frozen"] is False


def test_safe_result_rejects_raw_fields() -> None:
    MODULE.assert_safe_result({"payload_sha256": "0" * 64})
    try:
        MODULE.assert_safe_result({"raw_response": "unsafe"})
    except ValueError as exc:
        assert "unsafe field" in str(exc)
    else:
        raise AssertionError("raw response field should be rejected")


def test_target_manifest_is_hash_only() -> None:
    row = {
        "position": 0,
        "semantic_category": "synthetic",
        "behavior_id_sha256": "a" * 64,
        "payload_sha256": "b" * 64,
        "optimizer_target_sha256": "c" * 64,
        "optimizer_target_utf8_bytes": 12,
        "raw_payload_or_target_recorded": False,
    }
    text = json.dumps(row)
    assert "optimizer_target_text" not in text
    assert '"raw_payload"' not in text
