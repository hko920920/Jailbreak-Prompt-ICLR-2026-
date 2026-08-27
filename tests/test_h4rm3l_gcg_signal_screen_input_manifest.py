from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from types import ModuleType


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("manifest_freeze", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_fixture(
    tmp_path: Path,
    module: ModuleType,
) -> tuple[Path, Path]:
    root = tmp_path / "root"
    payloads = [
        {
            "position": index,
            "semantic_category": category,
            "behavior_id_sha256": f"{index + 1:064x}",
            "payload_sha256": f"{index + 11:064x}",
            "payload_utf8_bytes": 70 + index,
            "source_row_sha256": f"{index + 21:064x}",
        }
        for index, category in enumerate(
            (
                "chemical_biological",
                "cybercrime_intrusion",
                "misinformation_disinformation",
                "illegal",
            )
        )
    ]
    generation = {
        "seeds": [11, 23, 47],
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 50,
        "max_new_tokens": 512,
    }
    target_model = {
        "canonical_repository": "fixture/model",
        "canonical_revision": "a" * 40,
        "development_runtime_files": [
            {
                "filename": "fixture.gguf",
                "sha256": "b" * 64,
                "size_bytes": 123,
            }
        ],
    }
    audit = {
        "wildguard_role": "CONSERVATIVE_SCREENING_SIGNAL_ONLY",
        "harmbench_role": "NONVOTING_DIAGNOSTIC_ONLY",
        "independent_annotators": 2,
        "third_adjudicator_on_disagreement": True,
        "screen_positive_is_final_label": False,
    }
    predecessor = {
        "status": "TOPOLOGY_MICRO_PILOT_EXECUTION_FREEZE_PASS",
        "next_authorized_operation": (
            "FREEZE_H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST"
        ),
        "operational_pass": True,
        "paper_validity": False,
        "model_inference_performed": False,
        "model_weight_downloaded": False,
        "attack_success_observed": False,
        "raw_payload_or_response_recorded": False,
        "payload_manifest": payloads,
        "payload_manifest_sha256": module.canonical_sha256(payloads),
        "target_model": target_model,
        "generation": generation,
        "screening_and_audit": audit,
    }
    h4rm3l = {
        "status": (
            "E0_H4RM3L_REAL_TEMPLATES_PASS_FREEZE_REGIME_S_"
            "H4RM3L_ADAPTER"
        ),
        "operational_pass": True,
        "target_model_called": False,
        "attack_success_scored": False,
        "source_revision": "c" * 40,
        "programs": [
            {
                "id": f"program-{index}",
                "component_count": 1 + (index % 3),
                "fragment_count": 2 + (index % 3),
                "subset_count": (2 ** (1 + (index % 3))) - 1,
                "unit_manifest_sha256": f"{index + 31:064x}",
                "fragment_manifest_sha256": f"{index + 41:064x}",
                "variant_manifest_sha256": f"{index + 51:064x}",
                "operational_pass": True,
            }
            for index in range(7)
        ],
    }
    gcg = {
        "status": (
            "E0_GCG_STATIC_AUDIT_PASS_ADVANCE_TO_TOKENIZER_"
            "TEMPLATE_BUDGET_AUDIT"
        ),
        "operational_pass": True,
        "target_model_called": False,
        "target_model_generation_performed": False,
        "target_model_weights_downloaded": False,
        "prior_evaluation_opened": False,
        "source": {
            "repository": "fixture/gcg",
            "observed_revision": "d" * 40,
            "observed_tree_sha": "e" * 40,
        },
        "observed_template_defaults": {
            "control_init_sha256": "f" * 64,
            "control_init_lexical_units": 20,
            "n_steps": 500,
            "topk": 256,
            "batch_size": 512,
        },
        "intervention_boundary": {
            "primary_preliminary_unit": (
                "EQUAL_CONTIGUOUS_CONTROL_BLOCK"
            )
        },
    }

    result_path = root / "data/freeze.safe.json"
    payload_path = root / "data/payloads.safe.jsonl"
    h_path = root / "data/h4rm3l.safe.json"
    g_path = root / "data/gcg.safe.json"
    write_json(result_path, predecessor)
    write_jsonl(payload_path, payloads)
    write_json(h_path, h4rm3l)
    write_json(g_path, gcg)

    contract = {
        "status": (
            "FROZEN_BEFORE_SIGNAL_SCREEN_ATTACK_MATERIALIZATION_"
            "OR_TARGET_OUTCOMES"
        ),
        "frozen": True,
        "paper_validity": False,
        "execution_freeze_predecessor": {
            "result_path": "data/freeze.safe.json",
            "result_git_blob_sha": module.git_blob_sha(result_path),
            "required_status": predecessor["status"],
            "required_next_authorized_operation": predecessor[
                "next_authorized_operation"
            ],
            "payload_manifest_path": "data/payloads.safe.jsonl",
            "payload_manifest_git_blob_sha": module.git_blob_sha(
                payload_path
            ),
            "required_payload_manifest_sha256": predecessor[
                "payload_manifest_sha256"
            ],
            "required_payload_count": 4,
        },
        "attack_families": [
            {
                "family": "h4rm3l",
                "predecessor_path": "data/h4rm3l.safe.json",
                "predecessor_git_blob_sha": module.git_blob_sha(h_path),
                "required_status": h4rm3l["status"],
                "required_program_count": 7,
                "maximum_coarse_units": 6,
            },
            {
                "family": "GCG",
                "predecessor_path": "data/gcg.safe.json",
                "predecessor_git_blob_sha": module.git_blob_sha(g_path),
                "required_status": gcg["status"],
                "maximum_coarse_units": 6,
            },
        ],
        "manifest_cardinality": {
            "shared_direct_instance_count": 12,
            "attacked_pair_plan_count": 24,
            "planned_baseline_generation_count": 36,
        },
        "evaluator_runtime_gate": {
            "exact_evaluator_runtime_revisions_required_before_first_automated_label": (
                True
            )
        },
        "safe_output_policy": {
            "payload_identity_mode": "HASH_ONLY",
            "raw_payload_recording_allowed": False,
        },
        "sealed_boundaries": {
            "target_model_called": False,
            "attack_optimization_performed": False,
            "attack_success_observed": False,
        },
        "decision_gate": {
            "on_manifest_freeze_pass": (
                "FREEZE_PRIVATE_SIGNAL_SCREEN_RUNTIME_BUNDLE_"
                "AND_EVALUATOR_REVISIONS"
            ),
            "on_operational_fail": "REPAIR_ONLY",
        },
    }
    config_path = root / "config.json"
    write_json(config_path, contract)
    return root, config_path


def test_manifest_is_deterministic_balanced_and_hash_only(
    tmp_path: Path,
) -> None:
    module = load_module(
        Path(
            "scripts/"
            "freeze_h4rm3l_gcg_signal_screen_input_manifest.py"
        )
    )
    root, config_path = build_fixture(tmp_path, module)
    outputs = []
    for run_index in (1, 2):
        safe = tmp_path / f"safe-{run_index}.json"
        direct = tmp_path / f"direct-{run_index}.jsonl"
        pairs = tmp_path / f"pairs-{run_index}.jsonl"
        result = module.run(root, config_path, safe, direct, pairs)
        outputs.append(
            (
                result,
                safe.read_text(encoding="utf-8"),
                direct.read_text(encoding="utf-8"),
                pairs.read_text(encoding="utf-8"),
            )
        )

    assert outputs[0] == outputs[1]
    result = outputs[0][0]
    assert result["status"] == (
        "H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST_FREEZE_PASS"
    )
    assert result["manifest_cardinality"][
        "shared_direct_instance_count"
    ] == 12
    assert result["manifest_cardinality"][
        "attacked_pair_plan_count"
    ] == 24
    direct_rows = [
        json.loads(line)
        for line in outputs[0][2].splitlines()
    ]
    pair_rows = [
        json.loads(line)
        for line in outputs[0][3].splitlines()
    ]
    assert len({row["direct_instance_id"] for row in direct_rows}) == 12
    assert len({row["pair_plan_id"] for row in pair_rows}) == 24
    assert all(
        row["attacked_material_status"]
        == "PLANNED_PRIVATE_NOT_GENERATED"
        for row in pair_rows
    )
    h_counts = Counter(
        row["program_identity_sha256"]
        for row in pair_rows
        if row["attack_family"] == "h4rm3l"
    )
    assert max(h_counts.values()) - min(h_counts.values()) <= 1
    serialized = "\n".join(outputs[0][1:])
    for forbidden in (
        '"payload_text":',
        '"raw_payload":',
        '"raw_prompt":',
        '"raw_response":',
        '"rendered_prompt":',
        '"control_init":',
        '"program_id":',
    ):
        assert forbidden not in serialized


def test_repository_contract_cardinality_and_seals() -> None:
    contract = json.loads(
        Path(
            "configs/natural_language_localization/"
            "h4rm3l_gcg_signal_screen_input_manifest_v1.json"
        ).read_text(encoding="utf-8")
    )
    cardinality = contract["manifest_cardinality"]
    assert cardinality["shared_direct_instance_count"] == 4 * 3
    assert cardinality["attacked_pair_plan_count"] == 4 * 2 * 3
    assert cardinality["planned_baseline_generation_count"] == 36
    assert contract["sealed_boundaries"] == {
        key: False
        for key in contract["sealed_boundaries"]
    }
