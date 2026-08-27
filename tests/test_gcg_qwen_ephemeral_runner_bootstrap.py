from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/bootstrap_gcg_qwen_ephemeral_runner.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_runner_release_is_pinned_with_sha256() -> None:
    text = _text()
    assert 'RUNNER_VERSION="2.337.0"' in text
    assert (
        'RUNNER_ARCHIVE_SHA256="70920811a4f8ad4328818682bca5c6469c1c942f'
        'ab52448868071d0063816613"'
    ) in text
    assert "sha256sum --check --status" in text


def test_runner_is_ephemeral_and_label_restricted() -> None:
    text = _text()
    assert 'CUSTOM_LABELS="gpu,a100-80gb,private-research"' in text
    assert "--ephemeral" in text
    assert "--unattended" in text
    assert '"attestation_only": "true"' in text
    assert "gcg_qwen_self_hosted_attestation.yml" in text


def test_registration_token_is_memory_only() -> None:
    text = _text()
    assert "actions/runners/registration-token" in text
    assert "REGISTRATION_TOKEN=\"\"" in text
    assert "set -x" not in text
    assert "echo $GH_TOKEN" not in text
    assert "printf $GH_TOKEN" not in text


def test_local_attestation_precedes_runner_registration() -> None:
    text = _text()
    attest_position = text.index('python3 "$ATTEST_SCRIPT"')
    register_position = text.index("actions/runners/registration-token")
    configure_position = text.index("./config.sh")
    dispatch_position = text.index("/dispatches")
    run_position = text.index("./run.sh")
    assert attest_position < register_position < configure_position < dispatch_position
    assert dispatch_position < run_position


def test_bootstrap_does_not_download_model_or_run_optimizer() -> None:
    text = _text()
    assert "huggingface-cli download" not in text
    assert "snapshot_download" not in text
    assert "run_gcg" not in text
    assert "500-step" not in text
