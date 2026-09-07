from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from jbspan.neutralization import LayoutPreservingBlankNeutralizer
from jbspan.schemas import TextSpan
from jbspan.topology import (
    AttackUnit,
    BehaviorOutcome,
    ImmutablePayload,
    InterventionMaterialization,
    TopologyInstance,
    materialize_intervention,
)
from jbspan.topology_records import TopologyRecordStore, build_private_record


def fixture() -> tuple[TopologyInstance, InterventionMaterialization]:
    prompt = "wrapper PAYLOAD ending"
    payload_start = prompt.index("PAYLOAD")
    instance = TopologyInstance(
        instance_id="record-fixture",
        prompt=prompt,
        payload=ImmutablePayload(
            "PAYLOAD",
            TextSpan(payload_start, payload_start + len("PAYLOAD")),
        ),
        units=(
            AttackUnit(
                "u0",
                (TextSpan(0, len("wrapper")),),
                "wrapper",
                "synthetic",
            ),
            AttackUnit(
                "u1",
                (TextSpan(prompt.index("ending"), len(prompt)),),
                "ending",
                "synthetic",
            ),
        ),
        vocabulary_version="record-v1",
    )
    materialization = materialize_intervention(
        instance,
        ("u0",),
        LayoutPreservingBlankNeutralizer(),
    )
    return instance, materialization


def test_record_store_is_resumable_deduplicated_and_safe(tmp_path: Path) -> None:
    instance, raw_materialization = fixture()
    materialization = raw_materialization
    record = build_private_record(
        materialization,
        seed=11,
        model_identity={"repository": "synthetic/model", "revision": "abc"},
        response="synthetic safe response",
        outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
    )
    store = TopologyRecordStore(tmp_path / "private", tmp_path / "safe")
    assert not store.contains(record.key)
    assert store.put(record)
    assert store.contains(record.key)
    assert not store.put(record)

    private_text = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "private").rglob("*.json")
    )
    safe_text = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "safe").rglob("*.json")
    )
    assert materialization.edited_prompt in private_text
    assert record.response in private_text
    assert materialization.edited_prompt not in safe_text
    assert record.response not in safe_text
    assert instance.payload.text not in safe_text

    loaded = store.load_records(instance_id=instance.instance_id)
    assert loaded == (record,)
    observations = store.load_observations(instance_id=instance.instance_id)
    assert len(observations) == 1
    assert observations[0].response_sha256 == record.response_sha256


def test_record_store_detects_conflict_and_repairs_missing_safe_copy(tmp_path: Path) -> None:
    _, materialization = fixture()
    record = build_private_record(
        materialization,
        seed=23,
        model_identity={"repository": "synthetic/model", "revision": "abc"},
        response="first response",
        outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
    )
    store = TopologyRecordStore(tmp_path / "private", tmp_path / "safe")
    assert store.put(record)
    safe_path = next((tmp_path / "safe").rglob("*.safe.json"))
    safe_path.unlink()
    assert store.contains(record.key)
    assert safe_path.is_file()
    assert not store.put(record)

    with pytest.raises(RuntimeError, match="conflicting private record"):
        store.put(replace(record, response="different response"))


def test_record_store_rejects_orphan_safe_record(tmp_path: Path) -> None:
    _, materialization = fixture()
    record = build_private_record(
        materialization,
        seed=47,
        model_identity={"repository": "synthetic/model", "revision": "abc"},
        response="response",
        outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
    )
    store = TopologyRecordStore(tmp_path / "private", tmp_path / "safe")
    safe_path = store.safe_root / record.key.record_id[:2] / (
        f"{record.key.record_id}.safe.json"
    )
    safe_path.parent.mkdir(parents=True)
    safe_path.write_text(json.dumps(record.to_safe_dict()), encoding="utf-8")
    with pytest.raises(RuntimeError, match="without its private source"):
        store.contains(record.key)


def test_execution_key_changes_with_model_identity(tmp_path: Path) -> None:
    _, materialization = fixture()
    first = build_private_record(
        materialization,
        seed=11,
        model_identity={"revision": "a"},
        response="response",
        outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
    )
    second = build_private_record(
        materialization,
        seed=11,
        model_identity={"revision": "b"},
        response="response",
        outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
    )
    assert first.key.record_id != second.key.record_id
    store = TopologyRecordStore(tmp_path / "private", tmp_path / "safe")
    assert store.put(first)
    assert store.put(second)
