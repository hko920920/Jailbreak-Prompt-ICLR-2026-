import itertools
import json
import re
from collections import Counter

from jbspan.objective_repair import build_cases as pilot_cases
from jbspan.objective_transfer import (
    build_cases,
    build_messages,
    build_strata,
    problem_identity,
    score_response,
)


def test_fixed_new_frame_has_64_problems_and_128_style_views_without_pilot_collisions():
    cases = build_cases()
    assert cases == build_cases()
    assert len(cases) == len({case["case_id"] for case in cases}) == 128
    counts = Counter(case["task_data_id"] for case in cases)
    assert len(counts) == 64 and set(counts.values()) == {2}
    assert not set(counts) & {problem_identity(case) for case in pilot_cases()}


def test_lookup_gold_is_independently_parsed_from_actual_instruction():
    positions = Counter()
    for case in build_cases():
        if case["task_family"] != "lookup" or case["conflict_style"] != "format_conflict":
            continue
        mapping = dict(re.findall(r"(K[1-4])=([a-z]+)", case["system_instruction"]))
        key = case["task_data"].split("=")[1]
        assert len(mapping) == len(set(mapping.values())) == 4
        assert mapping[key] == case["expected_answer"]
        assert case["expected_answer"] != "violet"
        positions[key] += 1
    assert positions == dict.fromkeys(("K1", "K2", "K3", "K4"), 8)


def test_sort_gold_is_exact_and_underlying_triples_are_distinct_new_nonsorted_inputs():
    triples = set()
    for case in build_cases():
        if case["task_family"] != "sort" or case["conflict_style"] != "format_conflict":
            continue
        values = tuple(map(int, case["task_data"].split("=")[1].split(",")))
        ordered = tuple(sorted(values))
        assert len(set(values)) == 3 and values != ordered
        assert ordered not in {(1, 4, 9), (2, 5, 8)}
        assert case["expected_answer"] == ",".join(map(str, ordered))
        triples.add(ordered)
    assert len(triples) == 32


def test_conflicts_and_scorer_unchanged_and_task_preserved_under_every_edit():
    original = {(c["task_family"], c["conflict_style"]): c for c in pilot_cases()}
    for case in build_cases():
        base = original[(case["task_family"], case["conflict_style"])]
        assert case["conflict_units"] == base["conflict_units"]
        assert case["aligned_units"] == base["aligned_units"]
        for mask, operator in itertools.product(range(32), ("SOURCE_OMIT", "LAYOUT_BLANK")):
            messages = build_messages(case, mask, operator)
            assert messages[0]["content"] == case["system_instruction"]
            assert messages[1]["content"].split("[NOTES]")[0] == (
                f"[TASK]\n{case['task_data']}\n[/TASK]\n"
            )
        assert score_response(json.dumps({"answer": case["expected_answer"]}),
                              case["expected_answer"])["status"] == "CORRECT"


def test_four_discovered_primary_masks_and_one_preservation_comparison_are_fixed():
    strata = build_strata()
    assert len(strata) == 5
    assert [(s["stratum_id"], s["witness_mask"], s["role"]) for s in strata] == [
        ("qwen_lookup_18", 18, "PRIMARY"),
        ("qwen_sort_13", 13, "PRIMARY"),
        ("qwen_sort_24", 24, "PRIMARY"),
        ("gemma_lookup_2", 2, "PRIMARY"),
        ("gemma_sort_2", 2, "PRESERVATION_COMPARISON"),
    ]


def test_problem_cluster_ignores_sort_presentation_but_includes_lookup_dictionary():
    sort = next(c for c in build_cases() if c["task_family"] == "sort")
    values = sort["task_data"].split("=")[1].split(",")
    assert problem_identity(sort) == problem_identity(
        {**sort, "task_data": "integers=" + ",".join(reversed(values))}
    )
    lookup = next(c for c in build_cases() if c["task_family"] == "lookup")
    changed = dict(lookup)
    changed["system_instruction"] = re.sub(
        r"K1=[a-z]+", "K1=anotherword", lookup["system_instruction"]
    )
    assert problem_identity(lookup) != problem_identity(changed)
