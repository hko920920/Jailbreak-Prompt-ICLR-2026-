from __future__ import annotations

import ast
import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_prompt_source_freeze_v2.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_prompt_source_freeze_v2.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_prompt_source_freeze_v2", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E1C prompt-source freeze v2 script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def code_cell(source: str, execution_count: int) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def markdown_cell(source: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [source],
    }


def synthetic_notebook(path: Path) -> None:
    prompt_source = '''
LLAMA2_CLS_PROMPT = {
    "prompt": "llama {behavior} {generation}",
    "prompt_contextual": "llama contextual",
}
MISTRAL_CLS_PROMPT = {
    "prompt": "mistral {behavior} {generation}",
    "prompt_contextual": "mistral contextual",
}
'''
    text_classifier = '''
test_classifier_path = "cais/HarmBench-Llama-2-13b-cls"
val_classifier_path = "cais/HarmBench-Mistral-7b-val-cls"
classifier_path = val_classifier_path
cls = LLM(model=test_classifier_path, tensor_parallel_size=1)
cls_params = SamplingParams(temperature=0.0, max_tokens=1)
'''
    text_execution = '''
PROMPT = LLAMA2_CLS_PROMPT if classifier_path == test_classifier_path else MISTRAL_CLS_PROMPT
input_file = "../data/classifier_val_sets/text_behaviors_val_set.json"
'''
    later_multimodal = '''
test_classifier_path = "cais/HarmBench-Llama-2-13b-cls-multimodal-behaviors"
classifier_path = test_classifier_path
cls = LLM(model=test_classifier_path, tensor_parallel_size=1)
PROMPT = LLAMA2_CLS_PROMPT
input_file = "../data/classifier_val_sets/multimodal_behaviors_val_set.json"
'''
    notebook = {
        "cells": [
            code_cell(prompt_source, 1),
            markdown_cell("## Text Behaviors Val Set"),
            code_cell(text_classifier, 3),
            code_cell(text_execution, 5),
            markdown_cell("## Multimodal Behaviors Val Set"),
            code_cell(later_multimodal, 9),
        ]
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")


def test_section_replay_stops_before_later_multimodal_overwrites(tmp_path: Path) -> None:
    module = load_script()
    notebook_path = tmp_path / "notebook.ipynb"
    synthetic_notebook(notebook_path)
    assignments, index, execution_count = module.replay_until_text_input(
        notebook_path,
        "## Text Behaviors Val Set",
        "../data/classifier_val_sets/text_behaviors_val_set.json",
    )
    assert index == 3
    assert execution_count == 5
    assert module.resolve_name("test_classifier_path", assignments) == (
        "cais/HarmBench-Llama-2-13b-cls"
    )
    assert module.resolve_name("classifier_path", assignments) == (
        "cais/HarmBench-Mistral-7b-val-cls"
    )
    assert module.call_keyword("cls", "model", assignments) == (
        "cais/HarmBench-Llama-2-13b-cls"
    )
    assert module.selected_ifexp_family("PROMPT", assignments) == (
        "MISTRAL_CLS_PROMPT"
    )


def test_registry_coverage_gates_selected_rows_but_reports_full_missing() -> None:
    module = load_script()
    text_registry = {
        "text_a": {"Behavior": "safe placeholder", "ContextString": ""},
    }
    multimodal_registry = {
        "multi_b": {"Behavior": "safe placeholder", "ImageDescription": "placeholder"},
    }
    selection = [
        {
            "record_id": "record-a",
            "behavior_hash": module.sha256_text("text_a"),
            "label": 0,
        }
    ]
    coverage = module.registry_coverage(
        {"text_a", "multi_b", "missing_c"},
        selection,
        text_registry,
        multimodal_registry,
        "Behavior",
        "ContextString",
    )
    assert coverage["full_validation_missing_from_text_count"] == 2
    assert coverage["full_validation_missing_from_union_count"] == 1
    assert coverage["full_validation_notebook_unusable_count"] == 1
    assert coverage["selected_missing_registry_row_count"] == 0
    assert coverage["selected_notebook_unusable_row_count"] == 0
    serialized = json.dumps(coverage)
    assert "text_a" not in serialized
    assert "multi_b" not in serialized
    assert "missing_c" not in serialized


def test_resolver_selects_if_expression_from_execution_state() -> None:
    module = load_script()
    tree = ast.parse(
        '''
left = "mistral"
right = "llama"
MISTRAL = {"prompt": "m", "prompt_contextual": "mc"}
LLAMA = {"prompt": "l", "prompt_contextual": "lc"}
PROMPT = LLAMA if left == right else MISTRAL
'''
    )
    assignments = module.assignments_from_tree(tree)
    assert module.selected_ifexp_family("PROMPT", assignments) == "MISTRAL"
    assert module.resolve_name("PROMPT", assignments) == {
        "prompt": "m",
        "prompt_contextual": "mc",
    }


def test_v2_contract_preserves_v1_failure_and_live_boundaries() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["status"] == "FROZEN_BEFORE_E1C_TEXT_SECTION_SOURCE_REPLAY"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False

    predecessors = cast(dict[str, object], contract["predecessors"])
    v1 = cast(dict[str, object], predecessors["source_freeze_v1_failure"])
    assert v1["required_status"] == "E1C_PROMPT_SOURCE_FREEZE_FAIL"
    assert v1["required_operational_pass"] is False
    assert v1["required_live_predictions"] is False

    replay = cast(dict[str, object], contract["text_section_replay"])
    assert replay["required_markdown_heading"] == "## Text Behaviors Val Set"
    assert replay["expected_test_classifier_path"] == (
        "cais/HarmBench-Llama-2-13b-cls"
    )
    assert replay["expected_classifier_path"] == (
        "cais/HarmBench-Mistral-7b-val-cls"
    )
    assert replay["expected_effective_prompt_family"] == "MISTRAL_CLS_PROMPT"
    assert replay["expected_model_prompt_family_mismatch"] is True

    source = cast(dict[str, object], contract["harmbench_source"])
    files = cast(dict[str, object], source["files"])
    assert files["data/behavior_datasets/harmbench_behaviors_multimodal_all.csv"] == (
        "d39d6c6b4ad68e37e60a408d3181791b49740221"
    )

    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
