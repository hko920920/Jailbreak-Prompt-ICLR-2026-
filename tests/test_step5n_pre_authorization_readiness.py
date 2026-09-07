from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import audit_step5n_pre_authorization_readiness as audit  # noqa: E402


def test_verify_hashed_file_checks_bytes_and_size(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"step5n")
    specification = {
        "path": "artifact.bin",
        "size_bytes": 6,
        "sha256": hashlib.sha256(b"step5n").hexdigest(),
    }
    result = audit.verify_hashed_file(tmp_path, specification)
    assert result["exists"] is True
    assert result["size_matches"] is True
    assert result["sha256_matches"] is True


def test_parse_nvidia_row_is_strict() -> None:
    result = audit.parse_nvidia_row(
        "NVIDIA GeForce RTX 3070, 536.67, 8192, 375, 7655, 31"
    )
    assert result == {
        "name": "NVIDIA GeForce RTX 3070",
        "driver_version": "536.67",
        "memory_total_mib": 8192,
        "memory_used_mib": 375,
        "memory_free_mib": 7655,
        "temperature_c": 31,
    }


def test_reservation_requires_three_unique_rows_per_topic_and_no_overlap() -> None:
    confirmation = [
        {
            "topic_id": f"topic-{topic}",
            "within_topic_ordinal": ordinal,
            "payload_sha256": f"confirmation-{topic}-{ordinal}",
            "raw_content_recorded": False,
        }
        for topic in range(15)
        for ordinal in (1, 2, 3)
    ]
    development = [
        {
            "topic_id": f"topic-{topic}",
            "payload_sha256": f"development-{topic}",
            "raw_content_recorded": False,
        }
        for topic in range(15)
    ]
    expectations = {
        "rows": 45,
        "topics": 15,
        "rows_per_topic": 3,
        "within_topic_ordinals": [1, 2, 3],
    }
    result = audit.audit_reservation(confirmation, development, expectations)
    assert result["passed"] is True
    assert result["unique_payloads"] == 45
    assert result["development_overlap_count"] == 0


def test_reservation_rejects_development_overlap() -> None:
    confirmation = [
        {
            "topic_id": "topic",
            "within_topic_ordinal": 1,
            "payload_sha256": "same",
            "raw_content_recorded": False,
        }
    ]
    development = [{"payload_sha256": "same"}]
    expectations = {
        "rows": 1,
        "topics": 1,
        "rows_per_topic": 1,
        "within_topic_ordinals": [1],
    }
    result = audit.audit_reservation(confirmation, development, expectations)
    assert result["passed"] is False
    assert result["development_overlap_count"] == 1
