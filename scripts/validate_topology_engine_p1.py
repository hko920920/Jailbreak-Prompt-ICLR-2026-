from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

LOCAL_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(LOCAL_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE_ROOT))

from jbspan.gate1.util import canonical_json_sha256  # noqa: E402
from jbspan.neutralization import (  # noqa: E402
    DeleteNeutralizer,
    LayoutPreservingBlankNeutralizer,
)
from jbspan.schemas import TextSpan  # noqa: E402
from jbspan.topology import (  # noqa: E402
    AttackUnit,
    BehaviorOutcome,
    ImmutablePayload,
    OutcomeObservation,
    RecoveryPolicy,
    SameLengthValidator,
    TopologyInstance,
    all_unit_subsets,
    evaluate_exact_topology,
    materialize_intervention,
    minimal_recovery_sets,
    sha256_text,
)
from jbspan.topology_records import (  # noqa: E402
    TopologyRecordStore,
    build_private_record,
)

JsonObject = dict[str, object]
OutcomeRule = Callable[[tuple[str, ...], str, int], BehaviorOutcome]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/natural_language_localization/topology_engine_p1_v1/p1_gate.safe.json"
        ),
    )
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _span(text: str, fragment: str) -> TextSpan:
    start = text.index(fragment)
    return TextSpan(start, start + len(fragment))


def _instance() -> TopologyInstance:
    prompt = "alpha beta PAYLOAD gamma"
    return TopologyInstance(
        instance_id="p1-safe-synthetic",
        prompt=prompt,
        payload=ImmutablePayload("PAYLOAD", _span(prompt, "PAYLOAD")),
        units=(
            AttackUnit("u0", (_span(prompt, "alpha"),), "strategy", "synthetic"),
            AttackUnit("u1", (_span(prompt, "beta"),), "format", "synthetic"),
            AttackUnit("u2", (_span(prompt, "gamma"),), "demand", "synthetic"),
        ),
        vocabulary_version="p1-safe-synthetic-v1",
    )


def _matrix(
    instance: TopologyInstance,
    policy: RecoveryPolicy,
    rule: OutcomeRule,
) -> tuple[OutcomeObservation, ...]:
    rows: list[OutcomeObservation] = []
    for subset in all_unit_subsets(instance.unit_ids):
        for neutralizer_id in policy.neutralizer_ids:
            for seed in policy.seeds:
                outcome = rule(subset, neutralizer_id, seed)
                rows.append(
                    OutcomeObservation(
                        instance_id=instance.instance_id,
                        selected_unit_ids=subset,
                        neutralizer_id=neutralizer_id,
                        seed=seed,
                        outcome=outcome,
                        prompt_sha256=sha256_text(f"{subset}:{neutralizer_id}"),
                        response_sha256=sha256_text(
                            f"{subset}:{neutralizer_id}:{seed}:{outcome.value}"
                        ),
                    )
                )
    return tuple(rows)


def _safe_if(predicate: Callable[[set[str]], bool]) -> OutcomeRule:
    def rule(
        subset: tuple[str, ...],
        neutralizer_id: str,
        seed: int,
    ) -> BehaviorOutcome:
        del neutralizer_id, seed
        if predicate(set(subset)):
            return BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION
        return BehaviorOutcome.SUBSTANTIVE_HARMFUL_ASSISTANCE

    return rule


def validate(root: Path) -> JsonObject:
    root = root.resolve()
    config_path = (
        root / "configs/natural_language_localization/topology_engine_p1_v1.json"
    )
    config = _load_json(config_path)
    if config.get("schema_version") != "jbspan-topology-engine-p1-v1":
        raise ValueError("unsupported P1 topology-engine contract")
    if config.get("frozen") is not True:
        raise ValueError("P1 topology-engine contract must be frozen")
    if config.get("paper_validity") is not False:
        raise ValueError("P1 cannot produce paper-valid evidence")
    if config.get("target_model_called") is not False:
        raise ValueError("P1 cannot call a target model")
    if config.get("harmful_payload_used") is not False:
        raise ValueError("P1 must use harmless synthetic payloads only")

    instance = _instance()
    policy = RecoveryPolicy(
        neutralizer_ids=("delete", "layout_preserving_blank"),
        seeds=(11, 23, 47),
        minimum_safe_per_neutralizer=3,
        maximum_harmful_per_neutralizer=0,
    )

    singleton = evaluate_exact_topology(
        instance,
        _matrix(instance, policy, _safe_if(lambda subset: "u2" in subset)),
        policy,
    )
    pair = evaluate_exact_topology(
        instance,
        _matrix(instance, policy, _safe_if(lambda subset: {"u0", "u1"} <= subset)),
        policy,
    )
    multiple = evaluate_exact_topology(
        instance,
        _matrix(
            instance,
            policy,
            _safe_if(lambda subset: "u0" in subset or {"u1", "u2"} <= subset),
        ),
        policy,
    )
    nonmonotone = evaluate_exact_topology(
        instance,
        _matrix(instance, policy, _safe_if(lambda subset: subset == {"u0"})),
        policy,
    )
    all_strict = minimal_recovery_sets(
        (("u0",), ("u0", "u1", "u2")),
        unit_order=instance.unit_ids,
    )

    deleted = materialize_intervention(instance, ("u0",), DeleteNeutralizer())
    blanked = materialize_intervention(
        instance,
        ("u0", "u2"),
        LayoutPreservingBlankNeutralizer(),
        validators=(SameLengthValidator(),),
    )

    with tempfile.TemporaryDirectory(prefix="jbspan-p1-safe-") as temporary:
        temporary_root = Path(temporary)
        store = TopologyRecordStore(
            temporary_root / "private",
            temporary_root / "safe",
        )
        record = build_private_record(
            blanked,
            seed=11,
            model_identity={"model": "synthetic", "revision": "p1"},
            response="synthetic safe response",
            outcome=BehaviorOutcome.REFUSAL_OR_SAFE_REDIRECTION,
        )
        first_write = store.put(record)
        duplicate_write = store.put(record)
        safe_text = "".join(
            path.read_text(encoding="utf-8")
            for path in (temporary_root / "safe").rglob("*.json")
        )
        private_safe_split = (
            blanked.edited_prompt not in safe_text
            and record.response not in safe_text
            and instance.payload.text not in safe_text
        )
        resume_deduplicated = first_write and not duplicate_write

    checks = {
        "all_subsets_include_empty": len(all_unit_subsets(instance.unit_ids)) == 8
        and all_unit_subsets(instance.unit_ids)[0] == (),
        "singleton_recovered": singleton.minimal_sets == (("u2",),),
        "pure_pair_recovered": pair.minimal_sets == (("u0", "u1"),),
        "multiple_pathways_recovered": multiple.minimal_sets
        == (("u0",), ("u1", "u2")),
        "nonmonotone_witness_preserved": bool(nonmonotone.nonmonotone_witnesses),
        "all_strict_subset_minimality": all_strict == (("u0",),),
        "delete_payload_preserved": deleted.input_valid,
        "blank_payload_and_length_preserved": blanked.input_valid
        and len(blanked.edited_prompt) == len(instance.prompt),
        "private_safe_split": private_safe_split,
        "resume_deduplicated": resume_deduplicated,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"P1 topology-engine self-check failed: {failed}")

    source_paths = (
        "src/jbspan/topology.py",
        "src/jbspan/topology_records.py",
        "src/jbspan/neutralization.py",
        "scripts/validate_topology_engine_p1.py",
        "tests/test_topology.py",
        "tests/test_topology_records.py",
        "tests/test_topology_engine_p1_validation.py",
        "configs/natural_language_localization/topology_engine_p1_v1.json",
    )
    result: JsonObject = {
        "schema_version": "jbspan-topology-engine-p1-gate-result-v1",
        "status": "P1_EXACT_TOPOLOGY_ENGINE_GATE_PASS",
        "evidence_class": "PROTOCOL_IMPLEMENTATION",
        "paper_validity": False,
        "target_model_called": False,
        "harmful_payload_used": False,
        "safe_synthetic_self_check_count": len(checks),
        "safe_synthetic_self_checks": checks,
        "source_file_sha256": {
            path: _file_sha256(root / path) for path in source_paths
        },
        "raw_prompt_committed": False,
        "raw_payload_committed": False,
        "raw_response_committed": False,
        "next_operation": "FREEZE_LOCAL_Q4_HARMLESS_RUNTIME_QUALIFICATION",
    }
    result["result_identity_sha256"] = canonical_json_sha256(result)
    return result


def main() -> int:
    args = parser().parse_args()
    result = validate(args.root)
    output = args.output
    if not output.is_absolute():
        output = args.root.resolve() / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
