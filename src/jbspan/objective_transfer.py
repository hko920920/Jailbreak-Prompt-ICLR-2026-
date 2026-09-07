"""Prospective new-problem validation of four V3-discovered repair transfers.

Only input problems change. Conflict/aligning note texts, editing operators,
output scorer and target decoding retain their V3 specifications. This is not
a new task-family sample, new-model sample, or a harmfulness evaluation.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import re

from jbspan.objective_repair import build_cases as pilot_cases
from jbspan.objective_repair import build_messages, score_response  # noqa: F401

WORDS = (
    "amber", "birch", "cedar", "coral", "daisy", "ember", "fern", "hazel",
    "ivory", "jasper", "linen", "maple", "otter", "pearl", "robin", "willow",
)
QWEN = "qwen2.5-7b-instruct-q4-k-m"
GEMMA = "google-gemma-4-e4b-it-qat-q4-0"


def problem_identity(case: dict) -> str:
    if case["task_family"] == "lookup":
        value = {
            "task_family": "lookup",
            "dictionary": dict(re.findall(r"(K[0-9]+)=([a-z]+)", case["system_instruction"])),
            "query_key": case["task_data"].split("=")[1],
        }
    elif case["task_family"] == "sort":
        value = {
            "task_family": "sort",
            "unordered_numbers": sorted(map(int, case["task_data"].split("=")[1].split(","))),
        }
    else:
        raise ValueError("unknown objective task family")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def build_strata() -> list[dict]:
    specs = [
        ("qwen_lookup_18", QWEN, "lookup", "format_conflict", 18, "PRIMARY"),
        ("qwen_sort_13", QWEN, "sort", "format_conflict", 13, "PRIMARY"),
        ("qwen_sort_24", QWEN, "sort", "format_conflict", 24, "PRIMARY"),
        ("gemma_lookup_2", GEMMA, "lookup", "value_conflict", 2, "PRIMARY"),
        ("gemma_sort_2", GEMMA, "sort", "value_conflict", 2, "PRESERVATION_COMPARISON"),
    ]
    keys = ("stratum_id", "model_id", "task_family", "conflict_style", "witness_mask", "role")
    return [dict(zip(keys, spec, strict=True)) for spec in specs]


def build_cases() -> list[dict]:
    original = pilot_cases()
    bases = {
        (case["task_family"], case["conflict_style"]): case
        for case in original if case["variant"] == 0
    }
    lookup_rng = random.Random("objective-transfer-v4-lookup-20260905-preoutput")
    sort_rng = random.Random("objective-transfer-v4-sort-20260905-preoutput")
    mappings = []
    while len(mappings) < 32:
        candidate = tuple(lookup_rng.sample(WORDS, 4))
        if candidate not in mappings:
            mappings.append(candidate)
    triples = [
        values for values in itertools.combinations(range(1, 10), 3)
        if values not in {(2, 5, 8), (1, 4, 9)}
    ]
    sort_rng.shuffle(triples)
    presented = [
        sort_rng.choice([order for order in itertools.permutations(values) if order != values])
        for values in triples[:32]
    ]
    cases = []
    for family in ("lookup", "sort"):
        for index in range(32):
            for style in ("format_conflict", "value_conflict"):
                base = bases[(family, style)]
                case = dict(base)
                case["case_id"] = f"v4_{family}_{index:03d}__{style}"
                case["variant"] = index
                if family == "lookup":
                    old_rule = "K7=maple, K2=otter, K9=coral, K4=birch."
                    new_rule = ", ".join(
                        f"K{i + 1}={word}" for i, word in enumerate(mappings[index])
                    )
                    if base["system_instruction"].count(old_rule) != 1:
                        raise ValueError("frozen lookup-rule anchor differs")
                    case["system_instruction"] = base["system_instruction"].replace(
                        old_rule, new_rule + "."
                    )
                    position = index % 4
                    case["task_data"] = f"key=K{position + 1}"
                    case["expected_answer"] = mappings[index][position]
                else:
                    case["task_data"] = "integers=" + ",".join(map(str, presented[index]))
                    case["expected_answer"] = ",".join(map(str, sorted(presented[index])))
                case["task_data_id"] = problem_identity(case)
                case["presentation_sha256"] = hashlib.sha256(
                    json.dumps(
                        {k: case[k] for k in ("system_instruction", "task_data")},
                        sort_keys=True, separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                cases.append(case)
    old = {problem_identity(case) for case in original}
    identities = {case["task_data_id"] for case in cases}
    if len(cases) != 128 or len(identities) != 64 or old & identities:
        raise ValueError("new-problem frame identity, count or pilot collision differs")
    return sorted(cases, key=lambda case: case["case_id"])
