from __future__ import annotations

from scripts.run_gate1_step3b_wildguard_validation import (
    FullRow,
    compute_metrics,
    parse_wildguard_output,
    split_indices,
)


def test_official_parser_and_jailbreak_label() -> None:
    output = (
        "Harmful request: yes\n"
        "Response refusal: no\n"
        "Harmful response: yes"
    )
    assert parse_wildguard_output(output) == (
        "harmful",
        "compliance",
        "harmful",
    )
    assert parse_wildguard_output("malformed") is None


def test_metrics_are_computed_on_parsed_records() -> None:
    value = compute_metrics([(1, 1), (1, 0), (0, 0), (0, 1), (1, None)])
    assert value.count == 5
    assert value.parsed_count == 4
    assert value.parse_coverage == 0.8
    assert value.true_positive == 1
    assert value.true_negative == 1
    assert value.false_positive == 1
    assert value.false_negative == 1
    assert value.accuracy == 0.5
    assert value.balanced_accuracy == 0.5
    assert value.macro_f1 == 0.5


def test_frozen_split_is_deterministic_disjoint_and_complete() -> None:
    rows = tuple(
        FullRow(
            index=index,
            prompt=f"prompt-{index}",
            response=f"response-{index}",
            human_majority=index % 2,
        )
        for index in range(300)
    )
    contract = {
        "split": {
            "seed": "jbspan-gate1-step3b5-jbb-judge-validation-v1",
            "selection_count": 200,
            "validation_count": 100,
        }
    }
    first = split_indices(rows, contract)
    second = split_indices(rows, contract)
    assert first == second
    selection, validation = first
    assert len(selection) == 200
    assert len(validation) == 100
    assert set(selection).isdisjoint(validation)
    assert set(selection) | set(validation) == set(range(300))
    assert sum(index % 2 for index in selection) == 100
    assert sum(index % 2 for index in validation) == 50
