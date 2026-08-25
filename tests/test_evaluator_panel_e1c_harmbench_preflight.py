from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_harmbench_preflight.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_harmbench_preflight_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_harmbench_preflight", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load E1C HarmBench preflight script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(index: int, label: int) -> dict[str, object]:
    votes = [label, label, 1 - label]
    return {
        "test_case": f"synthetic request {index}",
        "generation": f"synthetic response {index}",
        "model": "synthetic-model",
        "method": "synthetic-method",
        "experiment": "synthetic-experiment",
        "human_0": votes[0],
        "human_1": votes[1],
        "human_2": votes[2],
    }


def test_majority_label_and_balanced_selection_are_deterministic() -> None:
    module = load_script()
    value = {
        "behavior_a": [row(0, 0), row(1, 1), row(2, 0)],
        "behavior_b": [row(3, 1), row(4, 0), row(5, 1)],
    }
    first = module.flatten_validation(value)
    second = module.flatten_validation(value)
    assert first == second
    selected_a = module.select_balanced(first, 2)
    selected_b = module.select_balanced(second, 2)
    assert selected_a == selected_b
    assert [item["label"] for item in selected_a] == [0, 0, 1, 1]
    assert len({item["record_id"] for item in selected_a}) == 4


def test_safe_selection_excludes_raw_text_and_private_behavior_id() -> None:
    module = load_script()
    records = module.flatten_validation(
        {
            "private_behavior": [
                row(0, 0),
                row(1, 0),
                row(2, 1),
                row(3, 1),
            ]
        }
    )
    safe = module.safe_selection_rows(module.select_balanced(records, 2))
    assert safe
    for item in safe:
        assert set(item) == {"position", "record_id", "behavior_hash", "label"}
        assert "test_case" not in item
        assert "generation" not in item
        assert "behavior_id_private" not in item


def test_model_file_filter_includes_weights_and_required_configs() -> None:
    module = load_script()
    assert module.relevant_model_file("model-00001-of-00003.safetensors") is True
    assert module.relevant_model_file("pytorch_model-00001-of-00003.bin") is True
    assert module.relevant_model_file("config.json") is True
    assert module.relevant_model_file("tokenizer.model") is True
    assert module.relevant_model_file("README.md") is False


def test_contract_is_frozen_after_e1b_and_before_live_outputs() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["schema_version"] == "evaluator-panel-e1c-harmbench-preflight-v1.1"
    assert contract["status"] == "FROZEN_BEFORE_E1C_HARMBENCH_PREFLIGHT"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False
    predecessor = cast(dict[str, object], contract["predecessor"])
    assert predecessor["required_status"] == "EVALUATOR_PANEL_E1B_WILDGUARD_PASS"
    assert predecessor["required_next_operation"] == (
        "E1C_HARMBENCH_COMPONENT_REPRODUCTION_AND_CANARIES"
    )
    source = cast(dict[str, object], contract["harmbench_source"])
    files = cast(dict[str, object], source["files"])
    assert source["revision"] == "8e1604d1171fe8a48d8febecd22f600e462bdcdd"
    assert source["tree_sha"] == "e28303aa064b3a4fdbe5698bc323e43306b7ab74"
    assert files["eval_utils.py"] == "be95edd9523de0cde2a7823217b26983d57c496b"
    assert files["configs/model_configs/models.yaml"] == (
        "024dc7fd61233c6efcd8234bea648e0735d67b72"
    )
    assert files["data/classifier_val_sets/text_behaviors_val_set.json"] == (
        "3d7d0a98742a36b5c7824aadcea433e42a045022"
    )
    correction = cast(dict[str, object], contract["source_identity_correction"])
    assert correction["trigger_run_id"] == 32740398974
    assert correction["scientific_contract_changed"] is False
    assert correction["live_predictions_observed_before_correction"] is False
    assert correction["new_attack_outputs_observed_before_correction"] is False
    assert correction["selection_changed"] is False
    assert correction["threshold_changed"] is False
    classifier = cast(dict[str, object], contract["official_classifier"])
    assert classifier["repository"] == "cais/HarmBench-Llama-2-13b-cls"
    assert classifier["silent_model_substitution_allowed"] is False
    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
