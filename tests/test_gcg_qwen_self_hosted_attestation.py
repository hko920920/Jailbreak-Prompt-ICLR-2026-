from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/attest_gcg_qwen_self_hosted_runner.py"
SPEC = importlib.util.spec_from_file_location("attest_runner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_nvidia_smi_rows() -> None:
    rows = MODULE._parse_nvidia_smi(
        "NVIDIA A100 80GB PCIe, 81920, 77000, 535.216.03, GPU-abc, Disabled\n"
        "NVIDIA A100 80GB PCIe, 81920, 76000, 535.216.03, GPU-def, Disabled\n"
    )
    assert len(rows) == 2
    assert rows[0]["memory_total_mib"] == 81920
    assert rows[0]["uuid_sha256"] != "GPU-abc"
    assert rows[0]["mig_mode"] == "disabled"
    assert rows[0]["mig_mode_disabled"] is True


def test_enabled_mig_mode_rejected() -> None:
    rows = MODULE._parse_nvidia_smi(
        "NVIDIA A100 80GB PCIe, 81920, 77000, 535.216.03, GPU-abc, Enabled\n"
    )
    with pytest.raises(MODULE.ContractError, match="MIG_MODE_NOT_DISABLED"):
        MODULE._require_mig_disabled(rows)


def test_invalid_driver_version_rejected() -> None:
    with pytest.raises(MODULE.ContractError, match="INVALID_DRIVER_VERSION"):
        MODULE._version_tuple("535.x")


def test_private_root_inside_workspace_rejected(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("PRIVATE_ROOT", str(workspace / "secret"))
    with pytest.raises(MODULE.ContractError, match="PRIVATE_ROOT_INSIDE_WORKSPACE"):
        MODULE._resolve_private_root("PRIVATE_ROOT", "~/.cache/example", workspace)
