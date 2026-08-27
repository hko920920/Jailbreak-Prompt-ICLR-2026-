from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("freeze", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_selection_is_deterministic_and_hash_only(tmp_path: Path) -> None:
    module = load_module(Path("scripts/run_topology_micro_pilot_execution_freeze.py"))
    source = tmp_path / "behaviors.csv"
    fields = ["Behavior", "FunctionalCategory", "SemanticCategory", "Tags", "ContextString", "BehaviorID"]
    rows = []
    categories = ["chemical_biological", "cybercrime_intrusion", "misinformation_disinformation", "illegal"]
    for index, category in enumerate(categories):
        rows.extend([
            {"Behavior": f"private payload {category} z", "FunctionalCategory": "standard", "SemanticCategory": category, "Tags": "", "ContextString": "", "BehaviorID": f"{category}_z"},
            {"Behavior": f"private payload {category} a", "FunctionalCategory": "standard", "SemanticCategory": category, "Tags": "", "ContextString": "", "BehaviorID": f"{category}_a"},
        ])
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    contract = {"development_payload_source": {"semantic_categories": categories, "excluded_tags": ["copyright", "hash_check"], "functional_category_required": "standard"}}
    first = module.select_payloads(source, contract)
    second = module.select_payloads(source, contract)
    assert first == second
    assert len(first) == 4
    encoded = json.dumps(first)
    assert "private payload" not in encoded
    assert all("payload_sha256" in row for row in first)


def test_budget_identity() -> None:
    contract = json.loads(Path("configs/natural_language_localization/topology_micro_pilot_execution_freeze_v1.json").read_text())
    budget = contract["causal_budget"]
    assert 2 ** budget["maximum_coarse_units_per_instance"] == budget["maximum_subsets_per_instance"]
    assert budget["maximum_subsets_per_instance"] * len(budget["neutralizers"]) * budget["seed_count"] == budget["maximum_intervened_generations_per_stable_pair"]
    assert contract["sealed_boundaries"] == {key: False for key in contract["sealed_boundaries"]}
