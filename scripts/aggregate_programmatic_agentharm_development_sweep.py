from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.programmatic_agentharm.development_sweep import (
    aggregate_development_results,
    parse_behavior_specs,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Aggregate safe development-only AgentHarm behavior sweep artifacts."
    )
    value.add_argument(
        "--development-config",
        type=Path,
        default=Path("configs/programmatic_agentharm/development_behavior_sweep.json"),
    )
    value.add_argument("--inputs-dir", type=Path, required=True)
    value.add_argument("--safe-output", type=Path, required=True)
    return value


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def main() -> int:
    args = parser().parse_args()
    config = load_json(args.development_config.resolve())
    specs = parse_behavior_specs(config)
    thresholds = config.get("decision_thresholds")
    if not isinstance(thresholds, dict):
        raise RuntimeError("decision_thresholds must be an object")
    minimum_behaviors = thresholds.get("broad_minimum_eligible_behaviors")
    minimum_candidates = thresholds.get("broad_minimum_distinct_candidates")
    if (
        isinstance(minimum_behaviors, bool)
        or not isinstance(minimum_behaviors, int)
        or minimum_behaviors < 1
    ):
        raise RuntimeError("invalid broad_minimum_eligible_behaviors")
    if (
        isinstance(minimum_candidates, bool)
        or not isinstance(minimum_candidates, int)
        or minimum_candidates < 1
    ):
        raise RuntimeError("invalid broad_minimum_distinct_candidates")

    paths = sorted(args.inputs_dir.resolve().rglob("safe_summary.json"))
    results = [load_json(path) for path in paths]
    output = aggregate_development_results(
        results,
        expected_specs=specs,
        broad_minimum_eligible_behaviors=minimum_behaviors,
        broad_minimum_distinct_candidates=minimum_candidates,
    )
    output["input_artifact_count"] = len(paths)
    output["source_split_consumed"] = "confirmatory"
    output["consumed_behaviors_future_confirmatory_use_forbidden"] = True
    output["raw_prompts_committed"] = False
    output["raw_responses_committed"] = False
    output["raw_tool_arguments_committed"] = False
    output["raw_tool_responses_committed"] = False

    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["operational_pass"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
