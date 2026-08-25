from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import types
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSONL object: {path}")
        rows.append(cast(JsonObject, value))
    return rows


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[JsonObject]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_live_module(root: Path) -> types.ModuleType:
    path = root / "scripts/run_evaluator_panel_e1c_harmbench_live.py"
    spec = importlib.util.spec_from_file_location("e1c_harmbench_live", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load live module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def validate_runtime_remediation(
    root: Path,
    remediation_path: Path,
) -> tuple[JsonObject, JsonObject]:
    remediation = load_object(remediation_path)
    if remediation.get("schema_version") != "evaluator-panel-e1c-runtime-sharding-v1":
        raise ValueError("unsupported E1C runtime remediation")
    if remediation.get("frozen") is not True:
        raise ValueError("runtime remediation is not frozen")
    if remediation.get("paper_validity") is not False:
        raise ValueError("runtime remediation has invalid evidence boundary")

    predecessor = as_object(
        remediation["predecessor_operational_failure"],
        where="predecessor_operational_failure",
    )
    predecessor_path = root / str(predecessor["result_path"])
    predecessor_result = load_object(predecessor_path)
    checks = {
        "status": predecessor_result.get("status")
        == predecessor["required_status"],
        "operational_pass": predecessor_result.get("operational_pass")
        == predecessor["required_operational_pass"],
        "scientific_pass": predecessor_result.get("scientific_pass")
        == predecessor["required_scientific_pass"],
        "failure_stage": predecessor_result.get("failure_stage")
        == predecessor["required_failure_stage"],
        "failure_exit_code": predecessor_result.get("failure_exit_code")
        == predecessor["required_failure_exit_code"],
        "next_operation": predecessor_result.get("next_authorized_operation")
        == predecessor["required_next_operation"],
        "result_sha256": sha256_file(predecessor_path)
        == predecessor["required_result_sha256"],
    }
    if not all(checks.values()):
        raise ValueError(f"predecessor operational failure mismatch: {checks}")

    scientific = as_object(
        remediation["frozen_scientific_contract"],
        where="frozen_scientific_contract",
    )
    scientific_path = root / str(scientific["path"])
    scientific_contract = load_object(scientific_path)
    if sha256_file(scientific_path) != scientific["required_sha256"]:
        raise ValueError("frozen scientific contract identity mismatch")
    budget = as_object(
        scientific_contract["execution_budget"],
        where="execution_budget",
    )
    expected = {
        "expected_total_classifier_requests": 448,
        "full_selection_requests": 400,
        "repeatability_requests": 24,
        "canary_requests": 24,
    }
    for key, value in expected.items():
        if int(budget[key]) != value or int(scientific[key]) != value:
            raise ValueError(f"frozen request denominator mismatch: {key}")

    topology = as_object(
        remediation["runtime_only_change"],
        where="runtime_only_change",
    )
    if int(topology["full_selection_shard_count"]) != 8:
        raise ValueError("unexpected shard count")
    if int(topology["records_per_shard"]) != 25:
        raise ValueError("unexpected records per shard")
    if int(topology["requests_per_full_shard"]) != 50:
        raise ValueError("unexpected requests per full shard")
    if int(topology["auxiliary_request_count"]) != 48:
        raise ValueError("unexpected auxiliary request count")
    if topology["assignment"] != "POSITION_MODULO_SHARD_COUNT":
        raise ValueError("unexpected shard assignment")
    boundaries = as_object(
        remediation["sealed_boundaries"],
        where="sealed_boundaries",
    )
    if any(value is not False for value in boundaries.values()):
        raise ValueError("sealed boundary changed")
    return remediation, scientific_contract


def shard_rows(
    rows: list[JsonObject],
    *,
    shard_index: int,
    shard_count: int,
) -> list[JsonObject]:
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard specification")
    selected = [
        row
        for row in rows
        if int(row["position"]) % shard_count == shard_index
    ]
    return sorted(selected, key=lambda row: int(row["position"]))


def metrics_from_safe_rows(
    live: types.ModuleType,
    rows: list[JsonObject],
    *,
    mode: str,
) -> JsonObject:
    parsed = [row for row in rows if row.get("prediction") is not None]
    if parsed:
        metrics = live.binary_metrics(
            [int(row["label"]) for row in parsed],
            [int(row["prediction"]) for row in parsed],
        )
    else:
        metrics = {
            "count": 0,
            "true_positive": 0,
            "true_negative": 0,
            "false_positive": 0,
            "false_negative": 0,
            "accuracy": 0.0,
            "balanced_accuracy": 0.0,
            "macro_f1": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
        }
    metrics.update(
        {
            "schema_version": "e1c-harmbench-live-metrics-v1",
            "mode": mode,
            "request_count": len(rows),
            "parsed_count": len(parsed),
            "parse_coverage": len(parsed) / len(rows) if rows else 0.0,
            "abstention_count": len(rows) - len(parsed),
            "prediction_sha256": live.canonical_sha256(
                [row.get("prediction") for row in rows]
            ),
            "raw_text_recorded": False,
        }
    )
    return cast(JsonObject, metrics)


def command_validate(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    remediation_path = (
        args.remediation
        if args.remediation.is_absolute()
        else root / args.remediation
    )
    remediation, scientific = validate_runtime_remediation(
        root,
        remediation_path,
    )
    summary = {
        "schema_version": "e1c-runtime-sharding-validation-safe-v1",
        "status": "E1C_RUNTIME_SHARDING_VALIDATION_PASS",
        "shard_count": remediation["runtime_only_change"][
            "full_selection_shard_count"
        ],
        "expected_total_classifier_requests": scientific["execution_budget"][
            "expected_total_classifier_requests"
        ],
        "scientific_contract_sha256": sha256_file(
            root
            / str(
                as_object(
                    remediation["frozen_scientific_contract"],
                    where="frozen_scientific_contract",
                )["path"]
            )
        ),
        "paper_validity": False,
        "model_inference_performed": False,
        "raw_text_recorded": False,
    }
    write_json(args.safe_output, summary)
    return 0


def command_full_shard(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    remediation_path = (
        args.remediation
        if args.remediation.is_absolute()
        else root / args.remediation
    )
    remediation, _ = validate_runtime_remediation(root, remediation_path)
    live = load_live_module(root)
    contract_path = root / str(
        as_object(
            remediation["frozen_scientific_contract"],
            where="frozen_scientific_contract",
        )["path"]
    )
    contract, _ = live.validate_contract(root, contract_path)
    reconstructed, manifest, prompt_family = live.source_rows(
        root,
        args.source_root.resolve(),
        contract,
    )
    requests = live.render_requests(
        reconstructed,
        manifest,
        prompt_family,
        contract,
    )
    topology = as_object(
        remediation["runtime_only_change"],
        where="runtime_only_change",
    )
    shard_count = int(topology["full_selection_shard_count"])
    selected = shard_rows(
        requests,
        shard_index=args.shard_index,
        shard_count=shard_count,
    )
    if len(selected) != int(topology["records_per_shard"]):
        raise ValueError("full-selection shard cardinality changed")

    component = live.as_object(contract["component"], where="component")
    seed = int(
        live.as_object(
            contract["execution_budget"],
            where="execution_budget",
        )["fixed_seed"]
    )
    args.private_output_dir.mkdir(parents=True, exist_ok=True)
    args.safe_output_dir.mkdir(parents=True, exist_ok=True)
    mode_summaries: JsonObject = {}
    for mode in (
        "raw_official_template",
        "hardened_production_template",
    ):
        stem = f"full_shard_{args.shard_index:02d}_{mode}"
        metrics = live.evaluate_rows(
            selected,
            mode=mode,
            server_url=args.server_url,
            component=component,
            seed=seed,
            nonce=None,
            private_output=args.private_output_dir / f"{stem}.private.jsonl",
            safe_output=args.safe_output_dir / f"{stem}.safe.jsonl",
        )
        live.write_json(
            args.safe_output_dir / f"{stem}_metrics.safe.json",
            metrics,
        )
        mode_summaries[mode] = metrics

    summary = {
        "schema_version": "e1c-harmbench-full-shard-summary-v1",
        "status": "E1C_HARMBENCH_FULL_SHARD_PASS",
        "shard_index": args.shard_index,
        "shard_count": shard_count,
        "record_count": len(selected),
        "request_count": len(selected) * 2,
        "positions": [int(row["position"]) for row in selected],
        "record_ids_sha256": live.canonical_sha256(
            [row["record_id"] for row in selected]
        ),
        "mode_summaries": mode_summaries,
        "runtime_sha256": args.runtime_sha256,
        "runtime_size_bytes": args.runtime_size_bytes,
        "paper_validity": False,
        "model_inference_performed": True,
        "harmbench_live_predictions_generated": True,
        "new_harmful_attack_outputs_generated": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_text_recorded": False,
    }
    write_json(
        args.safe_output_dir
        / f"full_shard_{args.shard_index:02d}_summary.safe.json",
        summary,
    )
    return 0


def command_merge_full(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    remediation_path = (
        args.remediation
        if args.remediation.is_absolute()
        else root / args.remediation
    )
    remediation, scientific_contract = validate_runtime_remediation(
        root,
        remediation_path,
    )
    live = load_live_module(root)
    topology = as_object(
        remediation["runtime_only_change"],
        where="runtime_only_change",
    )
    shard_count = int(topology["full_selection_shard_count"])
    selection_contract = as_object(
        scientific_contract["selection"],
        where="selection",
    )
    expected_selection = live.load_jsonl(
        root / str(selection_contract["path"])
    )
    expected_by_position = {
        int(row["position"]): row for row in expected_selection
    }
    expected_positions = set(range(int(selection_contract["record_count"])))
    args.safe_output_dir.mkdir(parents=True, exist_ok=True)

    mode_metrics: JsonObject = {}
    for mode in (
        "raw_official_template",
        "hardened_production_template",
    ):
        files = sorted(
            args.input_dir.rglob(f"full_shard_*_{mode}.safe.jsonl")
        )
        if len(files) != shard_count:
            raise ValueError(f"missing {mode} shard artifacts")
        rows: list[JsonObject] = []
        for path in files:
            rows.extend(load_jsonl(path))
        rows.sort(key=lambda row: int(row["position"]))
        positions = [int(row["position"]) for row in rows]
        if len(rows) != 200 or set(positions) != expected_positions:
            raise ValueError(f"{mode} does not cover exact 200 positions")
        if len(positions) != len(set(positions)):
            raise ValueError(f"{mode} contains duplicate positions")
        for row in rows:
            expected = expected_by_position[int(row["position"])]
            for key in ("record_id", "behavior_hash", "label"):
                if row.get(key) != expected.get(key):
                    raise ValueError(
                        f"{mode} merged row mismatch at "
                        f"position {row['position']}: {key}"
                    )
            if row.get("mode") != mode:
                raise ValueError(f"{mode} mode field mismatch")
        output = args.safe_output_dir / f"harmbench_{mode}.safe.jsonl"
        write_jsonl(output, rows)
        metrics = metrics_from_safe_rows(live, rows, mode=mode)
        write_json(
            args.safe_output_dir
            / f"harmbench_{mode}_metrics.safe.json",
            metrics,
        )
        mode_metrics[mode] = metrics

    summary = {
        "schema_version": "e1c-harmbench-full-merge-summary-v1",
        "status": "E1C_HARMBENCH_FULL_MERGE_PASS",
        "shard_count": shard_count,
        "record_count_per_mode": 200,
        "request_count": 400,
        "positions_sha256": live.canonical_sha256(list(range(200))),
        "record_ids_sha256": live.canonical_sha256(
            [row["record_id"] for row in expected_selection]
        ),
        "mode_metrics": mode_metrics,
        "paper_validity": False,
        "model_inference_performed": True,
        "harmbench_live_predictions_generated": True,
        "new_harmful_attack_outputs_generated": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_text_recorded": False,
    }
    write_json(
        args.safe_output_dir / "harmbench_full_merge_summary.safe.json",
        summary,
    )
    return 0


def command_auxiliary(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    remediation_path = (
        args.remediation
        if args.remediation.is_absolute()
        else root / args.remediation
    )
    remediation, _ = validate_runtime_remediation(root, remediation_path)
    live = load_live_module(root)
    contract_path = root / str(
        as_object(
            remediation["frozen_scientific_contract"],
            where="frozen_scientific_contract",
        )["path"]
    )
    contract, frozen = live.validate_contract(root, contract_path)
    reconstructed, manifest, prompt_family = live.source_rows(
        root,
        args.source_root.resolve(),
        contract,
    )
    requests = live.render_requests(
        reconstructed,
        manifest,
        prompt_family,
        contract,
    )
    first = load_jsonl(args.merged_hardened)
    if len(first) != 200:
        raise ValueError("merged hardened predictions do not contain 200 rows")
    expected_ids = {str(row["record_id"]) for row in requests}
    if {str(row["record_id"]) for row in first} != expected_ids:
        raise ValueError("merged hardened prediction identity mismatch")

    component = live.as_object(contract["component"], where="component")
    seed = int(
        live.as_object(
            contract["execution_budget"],
            where="execution_budget",
        )["fixed_seed"]
    )
    threshold = live.as_object(
        frozen["frozen_live_thresholds"],
        where="frozen_live_thresholds",
    )
    repeat_rows = live.repeatability_rows(
        requests,
        int(threshold["repeatability_subset_count"]),
    )
    args.private_output_dir.mkdir(parents=True, exist_ok=True)
    args.safe_output_dir.mkdir(parents=True, exist_ok=True)
    repeatability = live.evaluate_repeatability(
        repeat_rows,
        first,
        server_url=args.server_url,
        component=component,
        seed=seed,
        private_output=(
            args.private_output_dir / "harmbench_repeat.private.jsonl"
        ),
        safe_output=args.safe_output_dir / "harmbench_repeat.safe.jsonl",
    )
    live.write_json(
        args.safe_output_dir / "harmbench_repeat_summary.safe.json",
        repeatability,
    )

    canary_contract = live.as_object(
        contract["injection_canaries"],
        where="injection_canaries",
    )
    canary_rows = live.canary_requests(contract, prompt_family)
    canaries = live.evaluate_canaries(
        canary_rows,
        server_url=args.server_url,
        component=component,
        seed=seed,
        nonce=str(canary_contract["nonce"]),
        private_output=(
            args.private_output_dir / "harmbench_canaries.private.jsonl"
        ),
        safe_output=args.safe_output_dir / "harmbench_canaries.safe.jsonl",
    )
    live.write_json(
        args.safe_output_dir / "harmbench_canary_summary.safe.json",
        canaries,
    )
    summary = {
        "schema_version": "e1c-harmbench-auxiliary-summary-v1",
        "status": "E1C_HARMBENCH_AUXILIARY_PASS",
        "repeatability_request_count": int(repeatability["count"]),
        "canary_request_count": int(canaries["request_count"]),
        "total_request_count": (
            int(repeatability["count"]) + int(canaries["request_count"])
        ),
        "runtime_sha256": args.runtime_sha256,
        "runtime_size_bytes": args.runtime_size_bytes,
        "paper_validity": False,
        "model_inference_performed": True,
        "harmbench_live_predictions_generated": True,
        "new_harmful_attack_outputs_generated": False,
        "stage_a_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "raw_text_recorded": False,
    }
    if summary["total_request_count"] != 48:
        raise ValueError("auxiliary request denominator changed")
    write_json(
        args.safe_output_dir / "harmbench_auxiliary_summary.safe.json",
        summary,
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run sharded E1C HarmBench runtime remediation"
    )
    commands = value.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument("--remediation", type=Path, required=True)

    validate = commands.add_parser("validate")
    common(validate)
    validate.add_argument("--safe-output", type=Path, required=True)

    shard = commands.add_parser("full-shard")
    common(shard)
    shard.add_argument("--source-root", type=Path, required=True)
    shard.add_argument("--server-url", required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--private-output-dir", type=Path, required=True)
    shard.add_argument("--safe-output-dir", type=Path, required=True)
    shard.add_argument("--runtime-sha256", required=True)
    shard.add_argument("--runtime-size-bytes", type=int, required=True)

    merge = commands.add_parser("merge-full")
    common(merge)
    merge.add_argument("--input-dir", type=Path, required=True)
    merge.add_argument("--safe-output-dir", type=Path, required=True)

    auxiliary = commands.add_parser("auxiliary")
    common(auxiliary)
    auxiliary.add_argument("--source-root", type=Path, required=True)
    auxiliary.add_argument("--server-url", required=True)
    auxiliary.add_argument("--merged-hardened", type=Path, required=True)
    auxiliary.add_argument("--private-output-dir", type=Path, required=True)
    auxiliary.add_argument("--safe-output-dir", type=Path, required=True)
    auxiliary.add_argument("--runtime-sha256", required=True)
    auxiliary.add_argument("--runtime-size-bytes", type=int, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "validate":
        return command_validate(args)
    if args.command == "full-shard":
        return command_full_shard(args)
    if args.command == "merge-full":
        return command_merge_full(args)
    if args.command == "auxiliary":
        return command_auxiliary(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
