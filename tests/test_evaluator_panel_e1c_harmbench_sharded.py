from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_evaluator_panel_e1c_harmbench_sharded.py"
REMEDIATION = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_runtime_sharding_v1.json"
)
LIVE_CONTRACT = (
    ROOT
    / "configs"
    / "natural_language_localization"
    / "evaluator_panel_e1c_harmbench_live_contract_v1.json"
)


def load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("e1c_sharded", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load sharded E1C script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_position_modulo_shards_are_exact_and_disjoint() -> None:
    module = load_script()
    rows = [
        {
            "position": position,
            "record_id": f"record-{position}",
            "label": position % 2,
        }
        for position in range(200)
    ]
    shards = [
        module.shard_rows(rows, shard_index=index, shard_count=8)
        for index in range(8)
    ]
    assert [len(shard) for shard in shards] == [25] * 8
    observed = [
        int(row["position"])
        for shard in shards
        for row in shard
    ]
    assert len(observed) == 200
    assert len(set(observed)) == 200
    assert sorted(observed) == list(range(200))
    for index, shard in enumerate(shards):
        assert all(int(row["position"]) % 8 == index for row in shard)


def test_merged_metrics_preserve_abstention_denominator() -> None:
    module = load_script()
    live = module.load_live_module(ROOT)
    rows = [
        {"label": 0, "prediction": 0},
        {"label": 0, "prediction": 1},
        {"label": 1, "prediction": 1},
        {"label": 1, "prediction": None},
    ]
    metrics = module.metrics_from_safe_rows(
        live,
        rows,
        mode="hardened_production_template",
    )
    assert metrics["request_count"] == 4
    assert metrics["parsed_count"] == 3
    assert metrics["abstention_count"] == 1
    assert metrics["parse_coverage"] == 0.75
    assert metrics["count"] == 3
    assert metrics["true_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["false_negative"] == 0


def test_runtime_remediation_preserves_frozen_scientific_contract() -> None:
    remediation = cast(
        dict[str, object],
        json.loads(REMEDIATION.read_text(encoding="utf-8")),
    )
    live = cast(
        dict[str, object],
        json.loads(LIVE_CONTRACT.read_text(encoding="utf-8")),
    )
    assert remediation["schema_version"] == (
        "evaluator-panel-e1c-runtime-sharding-v1"
    )
    assert remediation["frozen"] is True
    assert remediation["paper_validity"] is False

    predecessor = cast(
        dict[str, object],
        remediation["predecessor_operational_failure"],
    )
    assert predecessor["required_status"] == (
        "E1C_HARMBENCH_COMPONENT_OPERATIONAL_FAIL"
    )
    assert predecessor["required_failure_exit_code"] == 124
    assert predecessor["scientific_interpretation_allowed"] is False

    topology = cast(dict[str, object], remediation["runtime_only_change"])
    assert topology["assignment"] == "POSITION_MODULO_SHARD_COUNT"
    assert topology["full_selection_shard_count"] == 8
    assert topology["records_per_shard"] == 25
    assert topology["requests_per_full_shard"] == 50
    assert topology["auxiliary_request_count"] == 48

    budget = cast(dict[str, object], live["execution_budget"])
    assert budget["expected_total_classifier_requests"] == 448
    assert budget["full_selection_requests"] == 400
    assert budget["repeatability_requests"] == 24
    assert budget["canary_requests"] == 24

    unchanged = cast(
        dict[str, object],
        remediation["unchanged_scientific_fields"],
    )
    assert unchanged["denominators_changed"] is False
    assert unchanged["thresholds_changed"] is False
    assert unchanged["parser_changed"] is False
    assert unchanged["hardening_changed"] is False

    boundary = cast(dict[str, object], remediation["sealed_boundaries"])
    assert all(value is False for value in boundary.values())
