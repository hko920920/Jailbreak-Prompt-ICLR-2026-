from __future__ import annotations

import json
from pathlib import Path

import pytest

from jbspan.gate1.step3 import load_jsonl, write_jsonl
from jbspan.gate1.util import sha256_text
from jbspan.natural_language_calibration import package_blinded_calibration_packet
from jbspan.natural_language_feasibility import load_json_object

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs/natural_language_localization/feasibility_v1.json"
PLAN = ROOT / "data/natural_language_localization/feasibility_v1/plan.safe.json"


def prepare_private_rows(private_dir: Path) -> None:
    plan = load_json_object(PLAN)
    calibration = plan["calibration_items"]
    assert isinstance(calibration, list)
    inputs: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    for raw in calibration:
        assert isinstance(raw, dict)
        item_id = raw["item_id"]
        payload_id = raw["payload_id"]
        category = raw["category"]
        goal = f"synthetic-goal-{payload_id}"
        response = f"synthetic-response-{item_id}"
        inputs.append(
            {
                "item_id": item_id,
                "payload_id": payload_id,
                "candidate_id": raw["candidate_id"],
                "condition": raw["condition"],
                "category": category,
                "original_harmful_goal": goal,
                "full_prompt": goal,
                "chat_prompt": goal,
                "seed": raw["seed"],
            }
        )
        responses.append(
            {
                "item_id": item_id,
                "payload_id": payload_id,
                "candidate_id": raw["candidate_id"],
                "condition": raw["condition"],
                "seed": raw["seed"],
                "model_response": response,
                "response_sha256": sha256_text(response),
                "response_character_length": len(response),
                "stopped_eos": True,
                "stopped_limit": False,
            }
        )
    private_dir.mkdir(parents=True)
    write_jsonl(private_dir / "inputs.private.jsonl", inputs)
    write_jsonl(private_dir / "responses.private.jsonl", responses)


def test_blinded_packet_hides_condition_and_is_self_describing(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    safe_dir = tmp_path / "safe"
    prepare_private_rows(private_dir)
    summary = package_blinded_calibration_packet(
        contract_path=CONTRACT,
        plan_path=PLAN,
        private_output_dir=private_dir,
        safe_output_dir=safe_dir,
        randomization_seed=b"\x01" * 32,
    )
    assert summary["status"] == "NATURAL_LANGUAGE_CALIBRATION_PACKET_READY"
    assert summary["item_count"] == 30
    assert summary["direct_count"] == 10
    assert summary["attacked_count"] == 20
    assert summary["decision_packet_opened"] is False
    assert summary["causal_oracle_opened"] is False
    assert summary["wavelet_used"] is False

    packet = load_jsonl(private_dir / "annotation_packet.private.jsonl")
    key = load_jsonl(private_dir / "annotation_key.private.jsonl")
    assert len(packet) == len(key) == 30
    assert all("condition" not in row for row in packet)
    assert all("candidate_id" not in row for row in packet)
    assert all("seed" not in row for row in packet)
    assert all("original_harmful_goal" in row for row in packet)
    assert all("model_response" in row for row in packet)
    assert {row["annotation_id"] for row in packet} == {
        row["annotation_id"] for row in key
    }

    public = json.loads((safe_dir / "packet_summary.json").read_text(encoding="utf-8"))
    encoded = json.dumps(public)
    assert "synthetic-goal" not in encoded
    assert "synthetic-response" not in encoded


def test_blinded_packet_rejects_non_256_bit_seed(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    safe_dir = tmp_path / "safe"
    prepare_private_rows(private_dir)
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        package_blinded_calibration_packet(
            contract_path=CONTRACT,
            plan_path=PLAN,
            private_output_dir=private_dir,
            safe_output_dir=safe_dir,
            randomization_seed=b"too-short",
        )
