from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_prompt_source_freeze_v3.py"
CONFIG = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_prompt_source_freeze_v3.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_prompt_source_v3", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load prompt-source v3 script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validation_row(
    *,
    test_case: str,
    generation: str,
    votes: tuple[int, int, int],
) -> dict[str, object]:
    return {
        "test_case": test_case,
        "generation": generation,
        "model": "synthetic-model",
        "method": "synthetic-method",
        "experiment": "synthetic-experiment",
        "human_0": votes[0],
        "human_1": votes[1],
        "human_2": votes[2],
        "cls": int(sum(votes) >= 2),
    }


def test_private_record_id_matches_preflight_field_contract() -> None:
    module = load_script()
    row = validation_row(
        test_case="case-a",
        generation="harmless generation placeholder",
        votes=(1, 0, 1),
    )
    observed = module.private_record_id("behavior-a", row)
    expected = module.canonical_sha256(
        {
            "behavior_id": "behavior-a",
            "test_case": "case-a",
            "generation": "harmless generation placeholder",
            "model": "synthetic-model",
            "method": "synthetic-method",
            "experiment": "synthetic-experiment",
            "human_0": 1,
            "human_1": 0,
            "human_2": 1,
        }
    )
    assert observed == expected
    assert len(observed) == 64


def test_manifest_uses_contextual_template_without_recording_raw_text() -> None:
    module = load_script()
    prompt = {
        "description": "synthetic",
        "prompt": "B={behavior}; G={generation}",
        "prompt_contextual": "C={context}; B={behavior}; G={generation}",
    }
    reconstructed = [
        {
            "position": 0,
            "record_id": "a" * 64,
            "behavior_hash": "b" * 64,
            "label": 0,
            "behavior_private": "plain behavior",
            "context_private": "",
            "generation_private": "plain generation",
        },
        {
            "position": 1,
            "record_id": "c" * 64,
            "behavior_hash": "d" * 64,
            "label": 1,
            "behavior_private": "context behavior",
            "context_private": "context value",
            "generation_private": "context generation",
        },
    ]
    manifest = module.safe_prompt_manifest(
        reconstructed,
        prompt,
        plain_key="prompt",
        contextual_key="prompt_contextual",
    )
    assert manifest[0]["template_key"] == "prompt"
    assert manifest[0]["context_present"] is False
    assert manifest[1]["template_key"] == "prompt_contextual"
    assert manifest[1]["context_present"] is True
    serialized = json.dumps(manifest)
    for raw_text in (
        "plain behavior",
        "plain generation",
        "context behavior",
        "context value",
        "context generation",
    ):
        assert raw_text not in serialized


def test_reconstruction_rejects_selection_label_drift() -> None:
    module = load_script()
    row = validation_row(
        test_case="case-a",
        generation="generation-a",
        votes=(1, 1, 0),
    )
    record_id = module.private_record_id("behavior-a", row)
    validation = module.validation_index({"behavior-a": [row]})
    selection = [
        {
            "position": 0,
            "record_id": record_id,
            "behavior_hash": module.sha256_text("behavior-a"),
            "label": 0,
        }
    ]
    registry = {
        "behavior-a": {"Behavior": "placeholder", "ContextString": ""},
    }
    try:
        module.reconstruct_selection(
            selection,
            validation,
            registry,
            behavior_field="Behavior",
            context_field="ContextString",
        )
    except ValueError as exc:
        assert "label mismatch" in str(exc)
    else:
        raise AssertionError("label drift was not rejected")


def git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_synthetic_end_to_end_freezes_hash_manifest(tmp_path: Path) -> None:
    module = load_script()
    root = tmp_path / "repo"
    source = root / "upstream" / "HarmBench"
    source.mkdir(parents=True)
    git("init", cwd=source)
    git("config", "user.name", "Synthetic Test", cwd=source)
    git("config", "user.email", "synthetic@example.test", cwd=source)

    eval_utils = source / "eval_utils.py"
    eval_utils.write_text(
        "LLAMA2_CLS_PROMPT = {\n"
        "    'description': 'synthetic llama',\n"
        "    'prompt': 'B={behavior}; G={generation}',\n"
        "    'prompt_contextual': 'C={context}; B={behavior}; G={generation}',\n"
        "}\n",
        encoding="utf-8",
    )
    notebook = source / "notebooks" / "run_classifier_val_set.ipynb"
    notebook.parent.mkdir(parents=True)
    notebook.write_text("{}\n", encoding="utf-8")

    rows_by_behavior = {
        "behavior-a": [
            validation_row(test_case="a0", generation="generation-a0", votes=(0, 0, 1))
        ],
        "behavior-b": [
            validation_row(test_case="b1", generation="generation-b1", votes=(1, 1, 0))
        ],
    }
    validation_path = source / "data" / "classifier_val_sets" / "text.json"
    validation_path.parent.mkdir(parents=True)
    validation_path.write_text(json.dumps(rows_by_behavior), encoding="utf-8")
    text_csv = source / "data" / "behavior_datasets" / "text.csv"
    multimodal_csv = source / "data" / "behavior_datasets" / "multi.csv"
    write_csv(
        text_csv,
        ["BehaviorID", "Behavior", "ContextString"],
        [
            {"BehaviorID": "behavior-a", "Behavior": "behavior A", "ContextString": ""},
            {
                "BehaviorID": "behavior-b",
                "Behavior": "behavior B",
                "ContextString": "context B",
            },
        ],
    )
    write_csv(
        multimodal_csv,
        ["BehaviorID", "Behavior", "ContextString"],
        [],
    )
    git("add", ".", cwd=source)
    git("commit", "-m", "synthetic source", cwd=source)
    tree_sha = git("rev-parse", "HEAD^{tree}", cwd=source)

    selection_rows: list[dict[str, object]] = []
    for position, behavior_id in enumerate(("behavior-a", "behavior-b")):
        row = cast(dict[str, object], rows_by_behavior[behavior_id][0])
        label, _ = module.human_label(row)
        selection_rows.append(
            {
                "position": position,
                "record_id": module.private_record_id(behavior_id, row),
                "behavior_hash": module.sha256_text(behavior_id),
                "label": label,
            }
        )
    selection_path = root / "data" / "selection.safe.jsonl"
    selection_path.parent.mkdir(parents=True)
    selection_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selection_rows),
        encoding="utf-8",
    )

    result_dir = root / "data" / "results"
    result_dir.mkdir(parents=True)
    record_ids_hash = module.canonical_sha256(
        [str(row["record_id"]) for row in selection_rows]
    )
    safe_rows_hash = module.canonical_sha256(selection_rows)
    repair = {
        "status": "E1C_SELECTION_REPAIR_PASS",
        "operational_pass": True,
        "next_authorized_operation": "FREEZE_E1C_PROMPT_SOURCE_V3_WITH_REPAIRED_SELECTION",
        "harmbench_live_predictions_generated": False,
        "new_selection": {
            "record_count": 2,
            "label_counts": {"0": 1, "1": 1},
            "behavior_count": 2,
            "record_ids_sha256": record_ids_hash,
            "safe_rows_sha256": safe_rows_hash,
        },
    }
    runtime = {
        "status": "E1C_RUNTIME_ARTIFACT_V2_PROBE_PASS",
        "operational_pass": True,
        "official_source_repository": "official/model",
        "official_source_revision": "1" * 40,
        "candidate_repository": "runtime/model",
        "candidate_revision": "2" * 40,
        "selected_file": {
            "filename": "model.gguf",
            "sha256": "3" * 64,
            "size": 123,
        },
    }
    v2 = {
        "status": "E1C_PROMPT_SOURCE_FREEZE_V2_FAIL",
        "operational_pass": False,
        "harmbench_live_predictions_generated": False,
        "next_authorized_operation": (
            "STOP_E1C_AND_RESOLVE_REMAINING_SOURCE_OR_SELECTION_AMBIGUITY_"
            "BEFORE_LIVE_OUTPUTS"
        ),
        "text_section_execution": {
            "effective_prompt_family": "MISTRAL_CLS_PROMPT",
            "loaded_model_argument": "official/model",
            "classifier_path": "diagnostic/model",
            "model_prompt_family_mismatch": True,
            "effective_prompt": {"canonical_family_sha256": "4" * 64},
        },
        "behavior_registry": {
            "selected_missing_registry_row_count": 3,
            "selected_notebook_unusable_row_count": 0,
        },
        "checks": {
            "all_selected_rows_resolve_in_notebook_registry": False,
            "source_tree_matches": True,
        },
    }
    (result_dir / "repair.json").write_text(json.dumps(repair), encoding="utf-8")
    (result_dir / "runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    (result_dir / "v2.json").write_text(json.dumps(v2), encoding="utf-8")

    prompt = {
        "description": "synthetic llama",
        "prompt": "B={behavior}; G={generation}",
        "prompt_contextual": "C={context}; B={behavior}; G={generation}",
    }
    prompt_summary = module.prompt_summary(prompt)
    config = {
        "status": "FROZEN_BEFORE_E1C_PROMPT_SOURCE_V3",
        "frozen": True,
        "paper_validity": False,
        "predecessors": {
            "selection_repair": {
                "result_path": "data/results/repair.json",
                "required_status": repair["status"],
                "required_operational_pass": True,
                "required_next_operation": repair["next_authorized_operation"],
                "required_live_predictions": False,
                "required_selection_record_count": 2,
                "required_selection_label_counts": {"0": 1, "1": 1},
                "required_selection_behavior_count": 2,
                "required_selection_record_ids_sha256": record_ids_hash,
                "required_selection_safe_rows_sha256": safe_rows_hash,
            },
            "runtime_artifact_v2": {
                "result_path": "data/results/runtime.json",
                "required_status": runtime["status"],
                "required_operational_pass": True,
                "required_official_source_repository": "official/model",
                "required_official_source_revision": "1" * 40,
                "required_candidate_repository": "runtime/model",
                "required_candidate_revision": "2" * 40,
                "required_filename": "model.gguf",
                "required_sha256": "3" * 64,
                "required_size": 123,
            },
            "prompt_source_v2": {
                "result_path": "data/results/v2.json",
                "required_status": v2["status"],
                "required_operational_pass": False,
                "required_live_predictions": False,
                "required_next_operation": v2["next_authorized_operation"],
                "required_false_checks": [
                    "all_selected_rows_resolve_in_notebook_registry"
                ],
                "required_selected_missing_registry_row_count": 3,
                "required_selected_notebook_unusable_row_count": 0,
                "required_notebook_effective_prompt_family": "MISTRAL_CLS_PROMPT",
                "required_notebook_loaded_model": "official/model",
                "required_notebook_classifier_path": "diagnostic/model",
                "required_notebook_model_prompt_family_mismatch": True,
                "required_notebook_prompt_canonical_sha256": "4" * 64,
            },
        },
        "harmbench_source": {
            "repository": "synthetic/HarmBench",
            "revision": git("rev-parse", "HEAD", cwd=source),
            "tree_sha": tree_sha,
            "files": {
                "eval_utils.py": git("hash-object", "eval_utils.py", cwd=source),
                "notebooks/run_classifier_val_set.ipynb": git(
                    "hash-object", "notebooks/run_classifier_val_set.ipynb", cwd=source
                ),
                "data/classifier_val_sets/text.json": git(
                    "hash-object", "data/classifier_val_sets/text.json", cwd=source
                ),
                "data/behavior_datasets/text.csv": git(
                    "hash-object", "data/behavior_datasets/text.csv", cwd=source
                ),
                "data/behavior_datasets/multi.csv": git(
                    "hash-object", "data/behavior_datasets/multi.csv", cwd=source
                ),
            },
        },
        "selection": {
            "path": "data/selection.safe.jsonl",
            "required_file_sha256": module.sha256_file(selection_path),
            "required_record_count": 2,
            "required_label_counts": {"0": 1, "1": 1},
            "required_behavior_count": 2,
            "required_record_ids_sha256": record_ids_hash,
            "required_safe_rows_sha256": safe_rows_hash,
        },
        "validation": {"path": "data/classifier_val_sets/text.json"},
        "registry": {
            "text_csv": "data/behavior_datasets/text.csv",
            "multimodal_csv": "data/behavior_datasets/multi.csv",
            "update_order": ["text_csv", "multimodal_csv"],
            "required_id_field": "BehaviorID",
            "required_behavior_field": "Behavior",
            "required_context_field": "ContextString",
        },
        "primary_execution": {
            "model_repository": "official/model",
            "model_revision": "1" * 40,
            "prompt_source_file": "eval_utils.py",
            "prompt_family": "LLAMA2_CLS_PROMPT",
            "plain_template_key": "prompt",
            "contextual_template_key": "prompt_contextual",
            "decoder_temperature": 0.0,
            "decoder_max_tokens": 1,
            "expected_prompt_summary": {
                key: value
                for key, value in prompt_summary.items()
                if key != "raw_prompt_recorded"
            },
        },
        "notebook_diagnostic": {
            "role": "PROVENANCE_DIAGNOSTIC_NOT_PRIMARY_LIVE_EXECUTION",
            "effective_prompt_family": "MISTRAL_CLS_PROMPT",
            "loaded_model_argument": "official/model",
            "classifier_path": "diagnostic/model",
            "model_prompt_family_mismatch": True,
            "effective_prompt_canonical_sha256": "4" * 64,
        },
        "safe_manifest": {
            "output_filename": "manifest.safe.jsonl",
            "required_fields": [
                "position",
                "record_id",
                "behavior_hash",
                "label",
                "template_key",
                "context_present",
                "behavior_sha256",
                "behavior_length",
                "context_sha256",
                "context_length",
                "generation_sha256",
                "generation_length",
                "rendered_prompt_sha256",
                "rendered_prompt_length",
            ]
        },
        "decision_gate": {
            "on_pass": "FREEZE_LIVE_CONTRACT",
            "on_fail": "STOP",
        },
    }
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    safe_output = root / "artifacts" / "result.safe.json"
    manifest_output = root / "artifacts" / "manifest.safe.jsonl"
    result = module.run(root, source, config_path, safe_output, manifest_output)
    assert result["status"] == "E1C_PROMPT_SOURCE_FREEZE_V3_PASS"
    assert result["operational_pass"] is True
    assert result["safe_manifest"]["record_count"] == 2
    assert result["safe_manifest"]["plain_record_count"] == 1
    assert result["safe_manifest"]["contextual_record_count"] == 1
    assert result["next_authorized_operation"] == "FREEZE_LIVE_CONTRACT"
    serialized = safe_output.read_text(encoding="utf-8") + manifest_output.read_text(
        encoding="utf-8"
    )
    for raw_text in (
        "generation-a0",
        "generation-b1",
        "behavior A",
        "behavior B",
        "context B",
    ):
        assert raw_text not in serialized


def test_production_contract_preserves_frozen_identities_and_boundaries() -> None:
    contract = cast(dict[str, object], json.loads(CONFIG.read_text(encoding="utf-8")))
    assert contract["status"] == "FROZEN_BEFORE_E1C_PROMPT_SOURCE_V3"
    assert contract["frozen"] is True
    assert contract["paper_validity"] is False
    selection = cast(dict[str, object], contract["selection"])
    assert selection["required_record_count"] == 200
    assert selection["required_label_counts"] == {"0": 100, "1": 100}
    assert selection["required_behavior_count"] == 166
    assert selection["required_file_sha256"] == (
        "8e897219ce0fa12cd10a95091275f4f22c4528748f15ef1f601ceef4fd834510"
    )
    primary = cast(dict[str, object], contract["primary_execution"])
    assert primary["prompt_family"] == "LLAMA2_CLS_PROMPT"
    diagnostic = cast(dict[str, object], contract["notebook_diagnostic"])
    assert diagnostic["effective_prompt_family"] == "MISTRAL_CLS_PROMPT"
    assert diagnostic["model_prompt_family_mismatch"] is True
    boundary = cast(dict[str, object], contract["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
