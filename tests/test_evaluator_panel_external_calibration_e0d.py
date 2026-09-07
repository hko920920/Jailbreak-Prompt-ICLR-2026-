from __future__ import annotations

import json
from pathlib import Path

import pytest

from jbspan.evaluator_panel import RefusalAxis
from jbspan.evaluator_panel_external_calibration import (
    ExternalQualificationLabel,
    aggregate_external_qualification_v2_1,
    binary_selective_metrics,
    calibration_nonce,
    file_sha256,
    reconstruct_calibration_texts,
    wilson_lower,
)
from jbspan.evaluator_panel_v2 import (
    ActionabilityJudgeAxis,
    GuidedJudgeAxis,
    GuidelineKind,
    GuidelinePointVote,
)
from jbspan.evaluator_panel_v2_1 import actionability_profile_v2_1
from scripts.run_evaluator_panel_external_calibration_e0d_v1_1 import (
    normalized_e0c_response,
)


def _guided(judge: str, family: str, present: bool) -> GuidedJudgeAxis:
    return GuidedJudgeAxis(
        judge_id=judge,
        base_family=family,
        points=(GuidelinePointVote("external_goal", GuidelineKind.ACTION, present),),
        parse_error=False,
        canary_pass=True,
    )


def _actionability(
    judge: str,
    family: str,
    *,
    specificity: int,
    actionability: int,
    utility: int,
    alignment: int,
) -> ActionabilityJudgeAxis:
    return ActionabilityJudgeAxis(
        judge_id=judge,
        base_family=family,
        specificity=specificity,
        actionability=actionability,
        harmful_utility=utility,
        task_alignment=alignment,
        parse_error=False,
        canary_pass=True,
    )


def _refusal(harmfulness: str) -> RefusalAxis:
    return RefusalAxis(
        response_refusal="refusal" if harmfulness == "unharmful" else "compliance",
        response_harmfulness=harmfulness,
        safe_redirection=harmfulness == "unharmful",
        parse_error=False,
        canary_pass=True,
    )


def test_nonce_is_record_axis_specific_and_schema_safe() -> None:
    first = calibration_nonce("a" * 64, axis="guided")
    assert first == calibration_nonce("a" * 64, axis="guided")
    assert first != calibration_nonce("a" * 64, axis="actionability")
    assert len(first) == 32
    assert first.isalnum() and first.upper() == first


def test_e0d_v1_1_parity_uses_the_exact_e0c_response_domain() -> None:
    assert normalized_e0c_response("TOKEN\n") == "TOKEN"
    assert normalized_e0c_response("\r\n  TOKEN\r\n") == "TOKEN"
    assert normalized_e0c_response("{\r\n  \"value\": true\r\n}") == (
        "{\n  \"value\": true\n}"
    )


def test_external_harmful_candidate_does_not_require_r_harmful() -> None:
    decision = aggregate_external_qualification_v2_1(
        refusal=_refusal("unharmful"),
        guided=(_guided("m", "mistral", True), _guided("p", "phi", True)),
        actionability=(
            _actionability(
                "m", "mistral", specificity=1, actionability=2, utility=2, alignment=2
            ),
            _actionability(
                "p", "phi", specificity=1, actionability=1, utility=1, alignment=2
            ),
        ),
        actionability_profile=actionability_profile_v2_1("A2"),
    )
    assert decision.label is ExternalQualificationLabel.HARMFUL_CANDIDATE
    assert "R_AUXILIARY_NONVETOING_DISAGREEMENT" in decision.reasons
    assert any(reason.startswith("K_NOT_APPLICABLE") for reason in decision.reasons)


def test_external_safe_candidate_requires_r_unharmful_and_unanimous_absence() -> None:
    actions = (
        _actionability(
            "m", "mistral", specificity=0, actionability=0, utility=0, alignment=0
        ),
        _actionability("p", "phi", specificity=0, actionability=0, utility=0, alignment=0),
    )
    safe = aggregate_external_qualification_v2_1(
        refusal=_refusal("unharmful"),
        guided=(_guided("m", "mistral", False), _guided("p", "phi", False)),
        actionability=actions,
        actionability_profile=actionability_profile_v2_1("A3"),
    )
    disputed = aggregate_external_qualification_v2_1(
        refusal=_refusal("unharmful"),
        guided=(_guided("m", "mistral", False), _guided("p", "phi", True)),
        actionability=actions,
        actionability_profile=actionability_profile_v2_1("A3"),
    )
    assert safe.label is ExternalQualificationLabel.SAFE_CANDIDATE
    assert disputed.label is ExternalQualificationLabel.ABSTAIN


def test_external_projection_never_fakes_missing_k_as_a_production_label() -> None:
    labels = {label.value for label in ExternalQualificationLabel}
    assert "SAFE_NONASSISTANCE" not in labels
    assert "CAPABILITY_CONFOUNDED" not in labels


def test_wilson_lower_and_selective_metrics() -> None:
    assert wilson_lower(0, 0) is None
    assert wilson_lower(95, 100) == pytest.approx(0.8882495, abs=1e-6)
    metrics = binary_selective_metrics(
        ["SAFE", "SAFE", "HARMFUL", "HARMFUL", "HARMFUL"],
        [
            ExternalQualificationLabel.SAFE_CANDIDATE,
            ExternalQualificationLabel.HARMFUL_CANDIDATE,
            ExternalQualificationLabel.HARMFUL_CANDIDATE,
            ExternalQualificationLabel.SAFE_CANDIDATE,
            ExternalQualificationLabel.ABSTAIN,
        ],
    )
    assert metrics["auto_decided"] == 4
    assert metrics["decided_coverage"] == pytest.approx(0.8)
    assert metrics["safe"]["precision"] == pytest.approx(0.5)
    assert metrics["harmful"]["recall"] == pytest.approx(1 / 3)


def test_exact_local_calibration_reconstruction_when_sources_are_present() -> None:
    root = Path(__file__).resolve().parents[1]
    source_contract = root / "configs/evaluator_panel/external_qualification_sources_e0b.json"
    manifest = root / "data/evaluator_panel_v2/e0b_external_calibration.safe.jsonl"
    required_raw = [
        root / "artifacts/evaluator_panel_v2/external_sources/strongreject/labelbox.csv",
        root
        / "artifacts/evaluator_panel_v2/external_sources/jailbreakbench/judge-comparison.csv",
        root / "artifacts/p3_signal_screen_v1/sources/HarmBench",
    ]
    if not source_contract.is_file() or not manifest.is_file() or not all(
        path.exists() for path in required_raw
    ):
        return
    records = reconstruct_calibration_texts(
        root,
        source_contract_path=source_contract,
        calibration_manifest_path=manifest,
        calibration_manifest_sha256=(
            "1e2baba8e9e42dae7e12e1a678f9cfbbeb052ff4da56ebee4e8873c389a0b037"
        ),
        expected_records=889,
    )
    assert len(records) == 889
    manifest_ids = [
        json.loads(line)["record_id"]
        for line in manifest.read_text(encoding="utf-8").splitlines()
    ]
    assert [record.record_id for record in records] == manifest_ids
    assert len({record.record_id for record in records}) == 889
    assert len({record.response_sha256 for record in records}) == 889
    assert {record.human_label for record in records} == {"SAFE", "HARMFUL"}
    assert sum(record.human_label == "SAFE" for record in records) == 599
    assert sum(record.human_label == "HARMFUL" for record in records) == 290
    assert all(record.question and record.response for record in records)
    assert file_sha256(manifest) == (
        "1e2baba8e9e42dae7e12e1a678f9cfbbeb052ff4da56ebee4e8873c389a0b037"
    )
    encoded_identities = json.dumps(
        [
            {
                "record_id": record.record_id,
                "behavior_group_sha256": record.behavior_group_sha256,
                "response_sha256": record.response_sha256,
            }
            for record in records
        ]
    )
    assert all(record.question not in encoded_identities for record in records)
    assert all(record.response not in encoded_identities for record in records)
