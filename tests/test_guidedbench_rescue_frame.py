from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import audit_guidedbench_rescue_frame as audit  # noqa: E402

CONFIG = ROOT / (
    "configs/natural_language_localization/guidedbench_rescue_frame_r0_v1.json"
)
RESULT = ROOT / (
    "data/natural_language_localization/guidedbench_rescue_frame_r0_v1/"
    "audit.safe.json"
)


def test_balanced_alternating_split_is_exact_and_deterministic() -> None:
    rows = []
    position = 0
    for topic_position, count in enumerate((1, 5, 6)):
        for local in range(count):
            rows.append(
                {
                    "position": position,
                    "topic_position": topic_position,
                    "topic_sha256": f"{topic_position:064x}",
                    "topic_id": f"T{topic_position}",
                    "within_topic_ordinal": local + 4,
                    "payload_sha256": f"{position + 100:064x}",
                }
            )
            position += 1
    primary, replication = audit.split_balanced_alternating(rows)
    assert len(primary) == len(replication) == 6
    assert {row["payload_sha256"] for row in primary}.isdisjoint(
        row["payload_sha256"] for row in replication
    )
    assert [row["position"] for row in primary] == list(range(6))
    assert [row["position"] for row in replication] == list(range(6))


def test_live_rescue_frame_is_60_60_and_preinference() -> None:
    result = audit.run(ROOT, CONFIG)
    assert result["status"] == "GUIDEDBENCH_UNUSED_FRAME_60_60_FREEZE_PASS"
    assert result["unused_frame"]["rows"] == 120
    assert result["unused_frame"]["prior_safe_output_collision_count"] == 0
    assert result["unused_frame"]["prior_private_record_collision_count"] == 0
    assert result["cohorts"]["primary_a"]["rows"] == 60
    assert result["cohorts"]["replication_reserve_b"]["rows"] == 60
    assert result["cohorts"]["overlap_count"] == 0
    assert result["cohorts"]["union_equals_unused_frame"] is True
    assert result["scope"]["target_model_called"] is False
    assert result["scope"]["evaluator_called"] is False


def test_stored_rescue_frame_receipt_matches_reconstruction() -> None:
    stored = json.loads(RESULT.read_text(encoding="utf-8"))
    assert stored == audit.run(ROOT, CONFIG)
