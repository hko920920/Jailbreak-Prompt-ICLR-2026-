from __future__ import annotations

import ast
import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_prompt_source_freeze.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_prompt_source_freeze_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_prompt_source_freeze", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E1C prompt source freeze script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_notebook_assignments(module: types.ModuleType) -> dict[str, ast.AST]:
    source = '''
LLAMA2_CLS_PROMPT = {"prompt": "llama {behavior} {generation}", "prompt_contextual": "llama contextual"}
MISTRAL_CLS_PROMPT = {"prompt": "mistral {behavior} {generation}", "prompt_contextual": "mistral contextual"}
test_classifier_path = "cais/HarmBench-Llama-2-13b-cls"
val_classifier_path = "cais/HarmBench-Mistral-7b-val-cls"
classifier_path = val_classifier_path
cls = LLM(model=test_classifier_path, tensor_parallel_size=1)
cls_params = SamplingParams(temperature=0.0, max_tokens=1)
PROMPT = LLAMA2_CLS_PROMPT if classifier_path == test_classifier_path else MISTRAL_CLS_PROMPT
'''
    return module.assignments_from_tree(ast.parse(source))


def test_effective_notebook_prompt_follows_actual_control_flow() -> None:
    module = load_script()
    assignments = synthetic_notebook_assignments(module)
    assert module.resolve_name("classifier_path", assignments) == (
        "cais/HarmBench-Mistral-7b-val-cls"
    )
    assert module.call_keyword("cls", "model", assignments) == (
        "cais/HarmBench-Llama-2-13b-cls"
    )
    assert module.selected_ifexp_family("PROMPT", assignments) == "MISTRAL_CLS_PROMPT"
    effective = module.resolve_name("PROMPT", assignments)
    assert effective == {
        "prompt": "mistral {behavior} {generation}",
        "prompt_contextual": "mistral contextual",
    }
    assert module.call_keyword("cls_params", "temperature", assignments) == 0.0
    assert module.call_keyword("cls_params", "max_tokens", assignments) == 1


def test_prompt_summary_records_hashes_but_not_raw_template() -> None:
    module = load_script()
    prompt = {
        "prompt": "template {behavior} {generation}",
        "prompt_contextual": "contextual {context}",
    }
    summary = module.prompt_summary(prompt)
    assert summary["raw_prompt_recorded"] is False
    assert summary["prompt_length"] == len(prompt["prompt"])
    assert summary["prompt_contextual_length"] == len(prompt["prompt_contextual"])
    assert "template" not in json.dumps(summary)
    assert len(str(summary["prompt_sha256"])) == 64
    assert len(str(summary["canonical_family_sha256"])) == 64


def test_prompt_source_contract_freezes_mismatch_before_live_outputs() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["status"] == "FROZEN_BEFORE_E1C_PROMPT_SOURCE_EXTRACTION"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False

    source = cast(dict[str, object], contract["harmbench_source"])
    files = cast(dict[str, object], source["files"])
    assert source["revision"] == "8e1604d1171fe8a48d8febecd22f600e462bdcdd"
    assert source["tree_sha"] == "e28303aa064b3a4fdbe5698bc323e43306b7ab74"
    assert files["notebooks/run_classifier_val_set.ipynb"] == (
        "f6b3cf674ec940d2384e277d77867f2293489595"
    )
    assert files["eval_utils.py"] == "be95edd9523de0cde2a7823217b26983d57c496b"

    notebook = cast(dict[str, object], contract["notebook_effective_execution"])
    assert notebook["expected_loaded_model_argument"] == (
        "cais/HarmBench-Llama-2-13b-cls"
    )
    assert notebook["expected_classifier_path"] == (
        "cais/HarmBench-Mistral-7b-val-cls"
    )
    assert notebook["expected_effective_prompt_family"] == "MISTRAL_CLS_PROMPT"
    assert notebook["expected_model_prompt_family_mismatch"] is True
    assert notebook["expected_temperature"] == 0.0
    assert notebook["expected_max_tokens"] == 1

    production = cast(dict[str, object], contract["production_execution"])
    assert production["prompt_family"] == "LLAMA2_CLS_PROMPT"
    assert production["not_assumed_equivalent_to_notebook_effective_prompt"] is True

    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
