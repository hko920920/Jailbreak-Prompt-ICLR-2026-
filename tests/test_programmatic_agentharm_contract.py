from __future__ import annotations

from jbspan.programmatic_agentharm import (
    BehaviorRecord,
    SourceGate,
    assign_grouped_splits,
    audit_grading_source,
    safe_manifest,
    select_programmatic_records,
    summarize_gate0,
)


def test_audit_rejects_semantic_and_assistant_text_dependencies() -> None:
    source = '''
async def helper(messages):
    return await semantic_judge("x", "y", object())

async def grade_programmatic(metadata, messages):
    return {"called": is_function_called(messages, "transfer")}

async def grade_semantic(metadata, messages):
    return {"meaning": await helper(messages)}

async def grade_free_text(metadata, messages):
    return {"text": "x" in extract_last_text_message(messages)}

async def grade_direct_text(metadata, messages):
    return {"text": messages[-1].text == "x"}
'''
    audits = {audit.name: audit for audit in audit_grading_source(source)}
    assert audits["grade_programmatic"].programmatically_verifiable is True
    assert audits["grade_semantic"].semantic_judge_dependency is True
    assert audits["grade_semantic"].programmatically_verifiable is False
    assert audits["grade_free_text"].assistant_free_text_dependency is True
    assert audits["grade_direct_text"].message_text_attribute_dependency is True


def test_selection_and_gate_summary() -> None:
    source = '''
async def grade_programmatic(metadata, messages):
    return {"called": is_function_called(messages, "transfer")}

async def grade_semantic(metadata, messages):
    return {"meaning": await semantic_judge("x", "y", object())}
'''
    records = (
        BehaviorRecord("a1", "a", "fraud", "grade_programmatic", False, False),
        BehaviorRecord("a2", "a", "fraud", "grade_programmatic", True, False),
        BehaviorRecord("b1", "b", "malware", "grade_semantic", False, False),
    )
    selected = select_programmatic_records(records, audit_grading_source(source))
    assert [record.behavior_id for record in selected] == ["a1", "a2"]
    summary = summarize_gate0(selected, SourceGate(1, 2, 1))
    assert summary.gate_pass is True


def test_grouped_split_is_deterministic_and_group_disjoint() -> None:
    records = tuple(
        BehaviorRecord(
            behavior_id=f"{base}-{variant}",
            original_id=base,
            category="category-a" if int(base[-1]) % 2 else "category-b",
            grading_function="grade_programmatic",
            detailed_prompt=bool(variant),
            hint_included=False,
        )
        for base in ("b1", "b2", "b3", "b4", "b5", "b6")
        for variant in (0, 1)
    )
    first = assign_grouped_splits(records, seed="fixed")
    second = assign_grouped_splits(tuple(reversed(records)), seed="fixed")
    assert first == second
    assert len({item.original_id for item in first}) == 6
    assert all(item.row_count == 2 for item in first)


def test_manifest_has_no_raw_prompt_fields() -> None:
    source = '''
async def grade_programmatic(metadata, messages):
    return {"called": is_function_called(messages, "transfer")}
'''
    audits = audit_grading_source(source)
    records = (
        BehaviorRecord("a1", "a", "fraud", "grade_programmatic", False, False),
    )
    manifest = safe_manifest(
        source_revision="a" * 40,
        dataset_revision="b" * 40,
        grading_source_sha256="c" * 64,
        utils_source_sha256="f" * 64,
        grading_git_blob_sha="1" * 40,
        utils_git_blob_sha="2" * 40,
        validation_source_sha256="d" * 64,
        test_source_sha256="e" * 64,
        audits=audits,
        validation_records=records,
        test_records=records,
        assignments=assign_grouped_splits(records, seed="fixed"),
        gate=SourceGate(1, 1, 1),
    )
    serialized = str(manifest).lower()
    assert "raw_prompts_committed" in serialized
    assert "prompt_text" not in serialized
    assert manifest["status"] == "PROGRAMMATIC_AGENTHARM_GATE0_PASS"
