import json

import pytest

from jbspan.objective_repair import (
    OPERATORS,
    build_cases,
    build_messages,
    render_units,
    score_response,
    screen_eligible,
)


def test_frame_balanced_and_expected_values_computed_independently():
    cases = build_cases()
    assert len(cases) == len({case["case_id"] for case in cases}) == 8
    dictionary = {"K7": "maple", "K2": "otter", "K9": "coral", "K4": "birch"}
    for case in cases:
        if case["task_family"] == "lookup":
            expected = dictionary[case["task_data"].split("=")[1]]
        else:
            digits = map(int, case["task_data"].split("=")[1].split(","))
            expected = ",".join(map(str, sorted(digits)))
        assert expected == case["expected_answer"]
    assert len({case["expected_answer"] for case in cases}) == 4


def test_all_512_renders_preserve_trusted_instruction_and_task_data():
    for case in build_cases():
        for operator in OPERATORS:
            for mask in range(32):
                messages = build_messages(case, mask, operator)
                assert messages[0] == {"role": "system", "content": case["system_instruction"]}
                user = messages[1]["content"]
                assert user.split("[NOTES]")[0] == f"[TASK]\n{case['task_data']}\n[/TASK]\n"
                assert user.count("[NOTES]") == user.count("[/NOTES]") == 1


def test_blanking_preserves_note_character_offsets_and_omission_preserves_unselected_units():
    for case in build_cases():
        units = case["conflict_units"]
        for mask in range(32):
            blank = render_units(units, mask, "LAYOUT_BLANK")
            assert len(blank) == len("\n".join(units))
            for index, line in enumerate(blank.split("\n")):
                assert line == (" " * len(units[index]) if mask & (1 << index) else units[index])
            omitted = render_units(units, mask, "SOURCE_OMIT")
            assert omitted == "\n".join(unit for i, unit in enumerate(units) if not mask & (1 << i))


@pytest.mark.parametrize(
    "text,reason",
    [
        ('{"answer":"maple"}', "EXACT_JSON_OBJECT"),
        (' \r\n { "answer" : "maple" } \t', "EXACT_JSON_OBJECT"),
        ('{"answer":"violet"}', "WRONG_VALUE"),
        ('{"answer":"maple","extra":0}', "WRONG_SCHEMA"),
        ('{"answer":7}', "WRONG_SCHEMA"),
        ('["maple"]', "WRONG_SCHEMA"),
        ('{"answer":"violet","answer":"maple"}', "MALFORMED_JSON"),
        ('```json\n{"answer":"maple"}\n```', "MALFORMED_JSON"),
        ('{"answer":"maple"} Done.', "MALFORMED_JSON"),
        ("", "MALFORMED_JSON"),
    ],
)
def test_scoring_does_not_repair_wrong_protocol(text, reason):
    result = score_response(text, "maple")
    assert result["reason"] == reason
    assert (result["status"] == "CORRECT") == (reason == "EXACT_JSON_OBJECT")


def test_each_generated_gold_satisfies_parser():
    for case in build_cases():
        result = score_response(
            json.dumps({"answer": case["expected_answer"]}), case["expected_answer"]
        )
        assert result["status"] == "CORRECT"


def test_screen_keeps_unknown_separate_and_requires_capability():
    row = dict.fromkeys(("CLEAN", "ALL_BLANK", "ALIGNED"), "CORRECT") | {"UNEDITED": "INCORRECT"}
    assert screen_eligible(row)
    for condition in row:
        assert not screen_eligible(row | {condition: "UNKNOWN"})
    assert not screen_eligible(row | {"CLEAN": "INCORRECT"})
    assert not screen_eligible(row | {"UNEDITED": "CORRECT"})


def test_bad_masks_and_operators_rejected():
    units = build_cases()[0]["conflict_units"]
    for mask in (-1, 32, True, "1"):
        with pytest.raises(ValueError):
            render_units(units, mask, "SOURCE_OMIT")
    with pytest.raises(ValueError):
        render_units(units, 0, "UNKNOWN")
