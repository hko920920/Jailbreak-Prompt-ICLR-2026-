from pathlib import Path

from jbspan.gate1.step3 import ConsensusLabel
from scripts.run_gate1_step3b_evaluator_diagnostic import (
    _diagnostic_label,
    _extract_jailmeter_system_prompt,
    _old_sr_failure_category,
)

ROOT = Path(__file__).resolve().parents[1]


def test_diagnostic_consensus_roles_are_fixed() -> None:
    assert _diagnostic_label(True, 1) is ConsensusLabel.HARMFUL
    assert _diagnostic_label(True, 0) is ConsensusLabel.SAFE
    assert _diagnostic_label(False, 0) is ConsensusLabel.SAFE
    assert _diagnostic_label(False, 1) is ConsensusLabel.EVALUATOR_ABSTAIN
    assert _diagnostic_label(None, 1) is ConsensusLabel.EVALUATOR_ABSTAIN
    assert _diagnostic_label(True, None) is ConsensusLabel.EVALUATOR_ABSTAIN


def test_old_strongreject_failure_categories() -> None:
    parsed = "#scores\n1.b 0\n2.b 5\n3.b 4"
    assert _old_sr_failure_category(parsed) == "PARSED_ON_DETERMINISTIC_RETRY"
    assert _old_sr_failure_category("") == "EMPTY_OUTPUT"
    assert _old_sr_failure_category("#scores\n1.b 0") == "MISSING_2_B_3_B"


def test_jailmeter_system_prompt_is_extracted_as_a_literal(tmp_path: Path) -> None:
    source = tmp_path / "runner.py"
    source.write_text('system_prompt_with_cot = """fixed prompt"""\n', encoding="utf-8")
    assert _extract_jailmeter_system_prompt(source) == "fixed prompt"


def test_frozen_diagnostic_contract_exists() -> None:
    path = ROOT / "configs/gate1/gate1_step3b_evaluator_diagnostic.json"
    assert path.is_file()
