from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jbspan.adapters.heuristic import HeuristicResponseJudge, TokenRetentionIntentJudge
from jbspan.adapters.hf import HuggingFaceCausalLMAdapter
from jbspan.cache import CachedTargetModel, ResponseCache
from jbspan.dataio import build_dataset_manifest, load_prompt_pairs, write_dataset_manifest
from jbspan.neutralization import LengthAwareNeutralizer, Neutralizer, PlaceholderNeutralizer
from jbspan.pilot import run_localizability_pilot, summarize_pilot, write_pilot_artifacts
from jbspan.registry import create_manifest, write_manifest
from jbspan.search.common import SearchConfig
from jbspan.search.hierarchical import GreedyHierarchicalSearch


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configuration must be a JSON object")
    return payload


def _neutralizers(names: list[str]) -> tuple[Neutralizer, ...]:
    registry: dict[str, Neutralizer] = {
        "placeholder": PlaceholderNeutralizer(),
        "length_aware": LengthAwareNeutralizer(),
    }
    unknown = sorted(set(names) - set(registry))
    if unknown:
        raise ValueError(f"unsupported neutralizers: {unknown}")
    return tuple(registry[name] for name in names)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate data and freeze manifests without loading a model",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    data_path = Path(str(config["data_path"]))
    output_dir = Path(str(config["output_dir"]))
    pairs = load_prompt_pairs(data_path)
    max_examples = int(config.get("max_examples", len(pairs)))
    pairs = pairs[:max_examples]

    dataset_manifest = build_dataset_manifest(data_path, pairs)
    write_dataset_manifest(output_dir / "data_manifest.json", dataset_manifest)
    write_manifest(
        output_dir / "run_manifest.json",
        create_manifest(str(config["experiment_id"]), config),
    )

    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "VALIDATED_ONLY",
                    "examples": len(pairs),
                    "paper_validity": bool(config.get("paper_validity", False)),
                    "output_dir": str(output_dir),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if bool(config.get("paper_validity", False)):
        raise ValueError(
            "This runner uses heuristic judges and must not be marked paper-valid. "
            "Replace both judges with validated adapters first."
        )

    model_config = dict(config["model"])
    target = HuggingFaceCausalLMAdapter(**model_config)
    cached_target = CachedTargetModel(
        target=target,
        cache=ResponseCache(Path(str(config["cache_dir"]))),
        fingerprint=model_config,
    )

    eligibility_config = dict(config["eligibility"])
    localization_config = dict(config["localization"])
    gate_config = dict(config["gate"])
    seeds = tuple(int(seed) for seed in eligibility_config["seeds"])
    neutralizers = _neutralizers(list(localization_config["neutralizers"]))

    records = run_localizability_pilot(
        pairs,
        cached_target,
        HeuristicResponseJudge(),
        TokenRetentionIntentJudge(),
        neutralizers,
        GreedyHierarchicalSearch(),
        SearchConfig(
            effect_threshold=float(localization_config["effect_threshold"]),
            intent_threshold=float(localization_config["intent_threshold"]),
            max_queries=int(localization_config["max_queries"]),
            span_set_penalty=float(localization_config["span_set_penalty"]),
        ),
        seeds=seeds,
        minimum_seed_agreement=float(eligibility_config["minimum_seed_agreement"]),
    )
    summary = summarize_pilot(
        records,
        minimum_localizable_fraction=float(gate_config["minimum_localizable_fraction"]),
        maximum_median_span_fraction=float(gate_config["maximum_median_span_fraction"]),
        minimum_cross_neutralizer_agreement=float(
            gate_config["minimum_cross_neutralizer_agreement"]
        ),
    )
    write_pilot_artifacts(output_dir, records, summary)

    print(
        json.dumps(
            {
                **summary.to_dict(),
                "cache_hits": cached_target.cache_hits,
                "cache_misses": cached_target.cache_misses,
                "paper_validity": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
