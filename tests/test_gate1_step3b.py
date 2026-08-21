from pathlib import Path

from jbspan.gate1.step3b import (
    CandidateSpec,
    extract_roleplaying_chain,
    render_candidate,
    split_gate1_payloads,
)
from jbspan.gate1.util import load_json

ROOT = Path(__file__).resolve().parents[1]


def test_static_h4rm3l_chain_and_nested_render() -> None:
    source = (
        'RoleplayingDecorator(prefix="A", suffix="a").then('
        'RoleplayingDecorator(prefix=f"B", suffix="b"))'
    )
    nodes = extract_roleplaying_chain(source, source_program_id="source")
    assert len(nodes) == 2
    rendered = render_candidate(
        CandidateSpec("candidate", ("source",)),
        {"source": nodes},
        payload_text="PAYLOAD",
    )
    assert rendered.text == "BAPAYLOADab"
    payload = rendered.text[rendered.payload_character_start : rendered.payload_character_end]
    assert payload == "PAYLOAD"


def test_dynamic_or_payload_transforming_program_is_rejected() -> None:
    source = 'TransformFxDecorator(transform_fx="dynamic")'
    try:
        extract_roleplaying_chain(source, source_program_id="dynamic")
    except Exception as exc:
        assert "forbidden" in str(exc) or "RoleplayingDecorator" in str(exc)
    else:
        raise AssertionError("dynamic source should be rejected")


def test_split_is_deterministic_and_keeps_gate2_out() -> None:
    contract = load_json(ROOT / "configs/gate1/gate1_step3b.json")
    registry = load_json(ROOT / "data/gate1/materialized/payload_registry.safe.json")
    first = split_gate1_payloads(registry, contract)
    second = split_gate1_payloads(registry, contract)
    assert first == second
    assert first["calibration_count"] == 10
    assert first["smoke_count"] == 10
    assert first["evaluation_count"] == 30
    calibration = {item["payload_id"] for item in first["calibration"]}
    smoke = {item["payload_id"] for item in first["smoke"]}
    evaluation = {item["payload_id"] for item in first["evaluation"]}
    assert calibration.isdisjoint(smoke)
    assert calibration.isdisjoint(evaluation)
    assert smoke.isdisjoint(evaluation)
    assert len(calibration | smoke | evaluation) == 50
