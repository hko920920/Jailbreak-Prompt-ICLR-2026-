from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from jbspan.topology import (
    BehaviorOutcome,
    OutcomeObservation,
    RecoveryPolicy,
    all_unit_subsets,
    sha256_text,
)
from jbspan.topology_d2 import evaluate_exact_topology_d2

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_topology_d2_micro_pilot.py"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_topology_d2_micro_pilot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


def benign_h4_bundle():
    p3_contract = json.loads(
        (
            ROOT
            / "configs/natural_language_localization/local_signal_screen_p3_v1.json"
        ).read_text(encoding="utf-8")
    )
    p3 = RUNNER.screen.repo_module(ROOT, "scripts.run_local_signal_screen_p3")
    family = p3.family_contract(p3_contract, "h4rm3l")
    static = RUNNER.h4_typed.load_static_audit_module()
    module, _, counter = static.load_h4rm3l(
        ROOT / "artifacts/p3_signal_screen_v1/sources/h4rm3l-lf"
    )
    topology, materials = RUNNER.build_one_h4_materialization_family(
        payload="BENIGN_PAYLOAD_SENTINEL",
        instance_id="benign-test",
        expression=str(family["representative_expression"]),
        components=tuple(family["expected_components"]),
        syntax_version=int(family["syntax_version"]),
        static=static,
        h4_module=module,
    )
    assert counter["calls"] == 0
    return topology, materials


def test_source_aware_omit_and_blank_cover_exact_frozen_lattice() -> None:
    topology, materials = benign_h4_bundle()
    assert len(materials) == 8 * 2
    assert all(material.input_valid for material in materials.values())
    assert materials[((), "SOURCE_AWARE_OMIT")].edited_prompt == topology.prompt
    assert materials[((), "LAYOUT_PRESERVING_BLANK")].edited_prompt == topology.prompt
    full = topology.unit_ids
    assert materials[(full, "SOURCE_AWARE_OMIT")].edited_prompt == topology.payload.text
    assert len(materials[(full, "LAYOUT_PRESERVING_BLANK")].edited_prompt) == len(
        topology.prompt
    )
    assert all(
        material.edited_prompt.count(topology.payload.text) == 1
        for material in materials.values()
    )


def test_provisional_control_selection_requires_both_neutralizers_all_seeds_safe() -> None:
    rows = []
    for neutralizer in RUNNER.NEUTRALIZERS:
        for seed in RUNNER.SEEDS:
            rows.append(
                {
                    "instance_id": "i",
                    "selected_unit_ids": ["u0"],
                    "neutralizer_id": neutralizer,
                    "seed": seed,
                    "panel_label": "SAFE",
                    "measurement_eligible": True,
                }
            )
    assert RUNNER.provisional_recovered_keys(rows) == {("i", ("u0",))}
    rows[-1]["panel_label"] = "ABSTAIN"
    assert RUNNER.provisional_recovered_keys(rows) == set()


def test_required_baseline_derivations_use_only_frozen_truth_table() -> None:
    topology, _materials = benign_h4_bundle()
    policy = RecoveryPolicy(
        neutralizer_ids=RUNNER.NEUTRALIZERS,
        seeds=RUNNER.SEEDS,
        minimum_safe_per_neutralizer=3,
        maximum_harmful_per_neutralizer=0,
    )
    rows = []
    for subset in all_unit_subsets(topology.unit_ids):
        safe = set(subset) >= set(topology.unit_ids[:2])
        for neutralizer in RUNNER.NEUTRALIZERS:
            for seed in RUNNER.SEEDS:
                outcome = (
                    BehaviorOutcome.SAFE_NONASSISTANCE
                    if safe
                    else BehaviorOutcome.SUBSTANTIVE_HARMFUL_ASSISTANCE
                )
                rows.append(
                    OutcomeObservation(
                        instance_id=topology.instance_id,
                        selected_unit_ids=subset,
                        neutralizer_id=neutralizer,
                        seed=seed,
                        outcome=outcome,
                        prompt_sha256=sha256_text(f"{subset}:{neutralizer}"),
                        response_sha256=sha256_text(
                            f"{subset}:{neutralizer}:{seed}:{outcome.value}"
                        ),
                    )
                )
    result = evaluate_exact_topology_d2(topology, rows, policy)
    baselines = RUNNER.derive_baselines(result)
    assert result.minimal_sets == (topology.unit_ids[:2],)
    assert baselines["all_singletons"]["predicted_sets"] == []
    assert baselines["ddmin"]["one_minimal_certificate"] is True
    assert baselines["greedy_backward"]["one_minimal_certificate"] is True
