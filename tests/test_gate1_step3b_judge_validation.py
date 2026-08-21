from pathlib import Path

from jbspan.gate1.jbb_judge_validation_core import (
    JudgeRow,
    load_json,
    metrics,
    passes,
    stratified_split,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def contract() -> dict[str, object]:
    return load_json(ROOT / "configs/gate1/gate1_step3b_judge_validation.json")


def row(index: int) -> JudgeRow:
    value = index % 2
    return JudgeRow(
        index,
        value,
        {
            "harmbench_official_precomputed": value,
            "llamaguard2_official_precomputed": value,
            "jailbreakbench_llama3_70b_precomputed": value,
            "jailbreakbench_gpt4_precomputed": value,
        },
    )


def test_contract_and_split_are_frozen() -> None:
    value = contract()
    validate_contract(value)
    rows = tuple(row(index) for index in range(300))
    selection, validation = stratified_split(rows, value)
    assert len(selection) == 200
    assert len(validation) == 100
    assert set(selection).isdisjoint(validation)
    assert stratified_split(rows, value) == (selection, validation)


def test_perfect_metrics_pass() -> None:
    value = contract()
    observed = metrics(
        tuple(row(index) for index in range(100)),
        "harmbench_official_precomputed",
    )
    assert observed.accuracy == 1.0
    assert observed.macro_f1 == 1.0
    assert observed.false_positive_rate == 0.0
    assert observed.false_negative_rate == 0.0
    assert passes(observed, value)
