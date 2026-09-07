from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from jbspan.evaluator_heldout_inputs import (
    load_and_validate_identity_manifests,
    reconstruct_label_blind_inputs,
)

ROOT = Path(__file__).resolve().parents[1]


def _identities() -> list[dict[str, object]]:
    return load_and_validate_identity_manifests(
        root=ROOT,
        full_path=Path("data/evaluator_panel_v2/e0b_external_heldout_identity.safe.jsonl"),
        primary_path=Path(
            "data/evaluator_panel_v2/e0f_primary_heldout_identity.safe.jsonl"
        ),
        stress_path=Path(
            "data/evaluator_panel_v2/"
            "e0f_exposed_jailbreakbench_heldout_identity.safe.jsonl"
        ),
    )


def test_sealed_identity_manifests_form_the_exact_primary_stress_partition() -> None:
    rows = _identities()

    assert len(rows) == 947
    assert Counter(row["evaluation_role"] for row in rows) == {
        "PRIMARY": 803,
        "EXPOSED_STRESS": 144,
    }
    assert Counter(row["source_id"] for row in rows) == {
        "harmbench": 289,
        "jailbreakbench": 144,
        "strongreject": 514,
    }
    forbidden = {
        "human_label",
        "human_annotation_count",
        "human_label_support_count",
        "human_unanimous",
    }
    assert all(not forbidden.intersection(row) for row in rows)


def test_raw_inputs_reconstruct_without_using_human_label_or_vote_fields() -> None:
    identities = _identities()
    source_contract = json.loads(
        (ROOT / "configs/evaluator_panel/external_qualification_sources_e0b.json").read_text(
            encoding="utf-8"
        )
    )

    records, audit = reconstruct_label_blind_inputs(
        root=ROOT,
        source_contract=source_contract,
        identities=identities,
    )

    assert len(records) == 947
    assert len({record.record_id for record in records}) == 947
    assert len({record.response_sha256 for record in records}) == 947
    assert audit["source_scan_counts"] == {
        "harmbench": 602,
        "jailbreakbench": 300,
        "strongreject": 1361,
    }
    assert audit["source_match_counts"] == {
        "harmbench": 289,
        "jailbreakbench": 144,
        "strongreject": 514,
    }
    assert audit["human_label_fields_accessed"] is False
    assert audit["human_vote_fields_accessed"] is False
    assert audit["raw_text_written"] is False
    assert all(not hasattr(record, "human_label") for record in records)
    assert all(not hasattr(record, "human_unanimous") for record in records)
