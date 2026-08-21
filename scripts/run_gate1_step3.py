from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jbspan.gate1.materialize import materialize_gate1_step2
from jbspan.gate1.registry import load_gate1_registry
from jbspan.gate1.step3 import (
    ConsensusLabel,
    StableLabel,
    build_token_provenance_record,
    consensus_label,
    load_jsonl,
    load_step3_contract,
    parse_harmbench,
    parse_strongreject,
    post_json,
    resolve_hf_repo,
    select_smoke_examples,
    sha256_file,
    stable_seed_label,
    step3_contract_manifest,
    write_json,
    write_jsonl,
)
from jbspan.gate1.util import canonical_json_sha256, load_json, sha256_text

JsonDict = dict[str, object]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=Path("."))
    prepare.add_argument("--source-csv", type=Path, required=True)
    prepare.add_argument("--resolved-source-revision", required=True)
    prepare.add_argument("--safe-output-dir", type=Path, required=True)
    prepare.add_argument("--private-output-dir", type=Path, required=True)

    target = subparsers.add_parser("target")
    target.add_argument("--root", type=Path, default=Path("."))
    target.add_argument("--private-output-dir", type=Path, required=True)
    target.add_argument("--server-url", required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--root", type=Path, default=Path("."))
    evaluate.add_argument("--private-output-dir", type=Path, required=True)
    evaluate.add_argument("--server-url", required=True)
    evaluate.add_argument("--safe-output-dir", type=Path, required=True)
    evaluate.add_argument("--mode", choices=("harmbench", "strongreject"), required=True)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--root", type=Path, default=Path("."))
    finalize.add_argument("--safe-output-dir", type=Path, required=True)
    finalize.add_argument("--private-output-dir", type=Path, required=True)
    return parser


def _apply_template(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise RuntimeError("tokenizer returned an invalid chat template")
    return rendered


def prepare(args: argparse.Namespace) -> None:
    from huggingface_hub import HfApi
    from transformers import AutoTokenizer

    root = args.root.resolve()
    safe_dir = args.safe_output_dir.resolve()
    private_dir = args.private_output_dir.resolve()
    runtime, evaluator_registry, _ = load_step3_contract(root)
    registry = load_gate1_registry(root)
    committed_source = load_json(root / "data/gate1/materialized/source_identity.json")
    expected_source_sha = str(committed_source["source_file_sha256"])
    temp_step2 = private_dir / "step2-safe-rebuild"
    materialize_gate1_step2(
        root,
        registry,
        source_csv=args.source_csv,
        resolved_revision=args.resolved_source_revision,
        safe_output_dir=temp_step2,
        private_output_dir=private_dir / "step2-private",
        expected_source_sha256=expected_source_sha,
    )
    expected_records = root / "data/gate1/materialized/benchmark_records.safe.jsonl"
    rebuilt_records = temp_step2 / "benchmark_records.safe.jsonl"
    if expected_records.read_bytes() != rebuilt_records.read_bytes():
        raise RuntimeError("Step 2 benchmark records changed before Step 3")

    api = HfApi()
    target = _object(runtime["target"])
    token_config = _object(runtime["token_provenance"])
    smoke_evaluators = {
        str(item["family"]): _object(item)
        for item in _array(evaluator_registry["smoke_surrogates"])
    }
    target_base = resolve_hf_repo(api, str(target["base_repo_id"]))
    if target_base.revision != str(target["base_revision"]):
        raise RuntimeError("target base revision differs from frozen contract")
    target_gguf = resolve_hf_repo(
        api,
        str(target["gguf_repo_id"]),
        ("*q4_k_m*.gguf",),
    )
    harmbench = resolve_hf_repo(
        api,
        str(smoke_evaluators["HarmBench"]["repository"]),
        ("*q4_k_m.gguf",),
    )
    strongreject_judge = resolve_hf_repo(
        api,
        str(smoke_evaluators["StrongREJECT"]["judge_repository"]),
        ("*q4_k_m.gguf",),
    )
    strongreject_base = resolve_hf_repo(
        api,
        str(smoke_evaluators["StrongREJECT"]["judge_base_repository"]),
    )
    primary = _array(evaluator_registry["primary"])
    harmbench_primary = resolve_hf_repo(
        api,
        str(_object(primary[0])["repository"]),
    )
    strongreject_adapter = resolve_hf_repo(
        api,
        str(_object(primary[1])["adapter_repository"]),
    )

    tokenizer = AutoTokenizer.from_pretrained(
        str(token_config["tokenizer_repo_id"]),
        revision=str(token_config["tokenizer_revision"]),
        use_fast=True,
    )
    if not getattr(tokenizer, "is_fast", False):
        raise RuntimeError("Step 3 token provenance requires a fast tokenizer")
    chat_template = tokenizer.chat_template
    if not isinstance(chat_template, str) or not chat_template:
        raise RuntimeError("target tokenizer has no chat template")
    chat_template_sha = sha256_text(chat_template)

    safe_records = load_jsonl(expected_records)
    private_payloads = load_jsonl(private_dir / "step2-private/payloads.private.jsonl")
    private_records = load_jsonl(private_dir / "step2-private/benchmark_records.private.jsonl")
    private_record_index = {str(item["example_id"]): item for item in private_records}
    token_records: list[JsonDict] = []
    for safe_record in safe_records:
        example_id = str(safe_record["example_id"])
        private_record = private_record_index[example_id]
        raw_prompt = str(private_record["rendered_prompt"])
        chat_text = _apply_template(tokenizer, [{"role": "user", "content": raw_prompt}])
        encoded = tokenizer(
            chat_text,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        token_records.append(
            build_token_provenance_record(
                safe_record=safe_record,
                raw_prompt=raw_prompt,
                chat_text=chat_text,
                token_ids=[int(item) for item in encoded["input_ids"]],
                offsets=[(int(start), int(end)) for start, end in encoded["offset_mapping"]],
                tokenizer_revision=str(token_config["tokenizer_revision"]),
                chat_template_sha256=chat_template_sha,
            )
        )

    payload_registry = load_json(root / "data/gate1/materialized/payload_registry.safe.json")
    smoke_selection = select_smoke_examples(payload_registry, safe_records, runtime)
    payload_private_index = {str(item["payload_id"]): item for item in private_payloads}
    smoke_private: list[JsonDict] = []
    for selected in smoke_selection:
        example_id = str(selected["example_id"])
        payload_id = str(selected["payload_id"])
        benchmark = private_record_index[example_id]
        payload = payload_private_index[payload_id]
        forbidden_prompt = str(payload["goal"])
        attacked_prompt = str(benchmark["rendered_prompt"])
        smoke_private.append(
            {
                **selected,
                "forbidden_prompt": forbidden_prompt,
                "original_chat_prompt": _apply_template(
                    tokenizer,
                    [{"role": "user", "content": forbidden_prompt}],
                ),
                "attack_chat_prompt": _apply_template(
                    tokenizer,
                    [{"role": "user", "content": attacked_prompt}],
                ),
            }
        )

    identity: JsonDict = {
        "schema_version": "gate1-step3-identity-v1",
        "paper_validity": False,
        "target_base": target_base.to_dict(),
        "target_gguf": target_gguf.to_dict(),
        "tokenizer": {
            "repo_id": str(token_config["tokenizer_repo_id"]),
            "revision": str(token_config["tokenizer_revision"]),
            "chat_template_sha256": chat_template_sha,
            "system_prompt_sha256": sha256_text(str(target["system_prompt"])),
        },
        "harmbench_primary": harmbench_primary.to_dict(),
        "strongreject_adapter_primary": strongreject_adapter.to_dict(),
        "harmbench_smoke": harmbench.to_dict(),
        "strongreject_judge_base": strongreject_base.to_dict(),
        "strongreject_judge_smoke": strongreject_judge.to_dict(),
        "runtime": runtime["runtime"],
    }
    contract = step3_contract_manifest(root)
    identity["step3_contract_sha256"] = contract["contract_sha256"]

    safe_dir.mkdir(parents=True, exist_ok=True)
    write_json(safe_dir / "step3_contract_manifest.json", contract)
    write_json(safe_dir / "step3_identity.json", identity)
    write_jsonl(safe_dir / "token_provenance.safe.jsonl", token_records)
    write_json(
        safe_dir / "token_provenance_manifest.json",
        {
            "schema_version": "gate1-token-provenance-manifest-v1",
            "record_count": len(token_records),
            "tokenizer_revision": str(token_config["tokenizer_revision"]),
            "chat_template_sha256": chat_template_sha,
            "boundary_crossing_record_count": sum(
                int(item["boundary_crossing_token_count"]) > 0 for item in token_records
            ),
            "raw_token_ids_committed": False,
            "raw_token_text_committed": False,
        },
    )
    write_json(
        safe_dir / "smoke_selection.safe.json",
        {
            "schema_version": "gate1-step3-smoke-selection-v1",
            "selection_method": _object(runtime["smoke"])["selection_method"],
            "selection_seed": _object(runtime["smoke"])["selection_seed"],
            "example_count": len(smoke_selection),
            "examples": list(smoke_selection),
        },
    )
    write_jsonl(private_dir / "smoke_inputs.private.jsonl", smoke_private)
    print(
        json.dumps(
            {
                "status": "GATE1_STEP3_PREPARED",
                "token_provenance_records": len(token_records),
                "smoke_examples": len(smoke_selection),
                "raw_prompts_logged": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def target(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    private_dir = args.private_output_dir.resolve()
    runtime, _, _ = load_step3_contract(root)
    generation = _object(runtime["generation"])
    seeds = [int(item) for item in _array(generation["seeds"])]
    rows = load_jsonl(private_dir / "smoke_inputs.private.jsonl")
    outputs: list[JsonDict] = []
    for row in rows:
        for variant in ("original", "attack"):
            prompt = str(row[f"{variant}_chat_prompt"])
            for seed in seeds:
                response = post_json(
                    args.server_url.rstrip("/") + "/completion",
                    {
                        "prompt": prompt,
                        "n_predict": int(generation["max_tokens"]),
                        "temperature": float(generation["temperature"]),
                        "top_p": float(generation["top_p"]),
                        "top_k": int(generation["top_k"]),
                        "seed": seed,
                        "stream": False,
                        "cache_prompt": False,
                    },
                )
                content = response.get("content")
                if not isinstance(content, str):
                    raise RuntimeError("target endpoint returned no text content")
                outputs.append(
                    {
                        "smoke_id": row["smoke_id"],
                        "example_id": row["example_id"],
                        "payload_id": row["payload_id"],
                        "variant": variant,
                        "seed": seed,
                        "response": content,
                        "response_sha256": sha256_text(content),
                        "response_character_length": len(content),
                        "stopped_eos": bool(response.get("stopped_eos", False)),
                        "stopped_limit": bool(response.get("stopped_limit", False)),
                    }
                )
    write_jsonl(private_dir / "target_responses.private.jsonl", outputs)
    print(
        json.dumps(
            {
                "status": "TARGET_GENERATION_COMPLETE",
                "generation_count": len(outputs),
                "raw_responses_logged": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def evaluate(args: argparse.Namespace) -> None:
    from transformers import AutoTokenizer

    root = args.root.resolve()
    private_dir = args.private_output_dir.resolve()
    runtime, _, prompts = load_step3_contract(root)
    rows = load_jsonl(private_dir / "target_responses.private.jsonl")
    inputs = {
        str(item["smoke_id"]): item
        for item in load_jsonl(private_dir / "smoke_inputs.private.jsonl")
    }
    results: list[JsonDict] = []
    if args.mode == "strongreject":
        identity = load_json(args.safe_output_dir / "step3_identity.json")
        judge_base = _object(identity["strongreject_judge_base"])
        tokenizer = AutoTokenizer.from_pretrained(
            str(judge_base["repo_id"]),
            revision=str(judge_base["revision"]),
            use_fast=True,
            trust_remote_code=True,
        )
    else:
        tokenizer = None

    for row in rows:
        smoke_input = inputs[str(row["smoke_id"])]
        forbidden_prompt = str(smoke_input["forbidden_prompt"])
        response_text = str(row["response"])
        if args.mode == "harmbench":
            prompt = str(prompts["harmbench"]).format(
                behavior=forbidden_prompt,
                generation=response_text,
            )
            raw = post_json(
                args.server_url.rstrip("/") + "/completion",
                {
                    "prompt": prompt,
                    "n_predict": 3,
                    "temperature": 0.0,
                    "stream": False,
                    "cache_prompt": False,
                },
            )
            content = raw.get("content")
            if not isinstance(content, str):
                raise RuntimeError("HarmBench endpoint returned no text content")
            parsed = parse_harmbench(content)
            results.append(
                {
                    "smoke_id": row["smoke_id"],
                    "variant": row["variant"],
                    "seed": row["seed"],
                    "response_sha256": row["response_sha256"],
                    "harmbench_harmful": parsed,
                    "judge_output": content,
                }
            )
        else:
            assert tokenizer is not None
            user = str(prompts["strongreject_rubric"]).format(
                forbidden_prompt=forbidden_prompt,
                response=response_text,
            )
            formatted = _apply_template(
                tokenizer,
                [
                    {"role": "system", "content": str(prompts["strongreject_system"])},
                    {"role": "user", "content": user},
                ],
            )
            raw = post_json(
                args.server_url.rstrip("/") + "/completion",
                {
                    "prompt": formatted,
                    "n_predict": 96,
                    "temperature": 0.0,
                    "stream": False,
                    "cache_prompt": False,
                },
            )
            content = raw.get("content")
            if not isinstance(content, str):
                raise RuntimeError("StrongREJECT endpoint returned no text content")
            parsed = parse_strongreject(content)
            results.append(
                {
                    "smoke_id": row["smoke_id"],
                    "variant": row["variant"],
                    "seed": row["seed"],
                    "response_sha256": row["response_sha256"],
                    "strongreject": (
                        None
                        if parsed is None
                        else {
                            "refusal": parsed.refusal,
                            "convincingness": parsed.convincingness,
                            "specificity": parsed.specificity,
                            "score": parsed.score,
                        }
                    ),
                    "judge_output": content,
                }
            )
    write_jsonl(private_dir / f"{args.mode}.private.jsonl", results)
    parsed_count = sum(
        (item.get("harmbench_harmful") is not None)
        if args.mode == "harmbench"
        else (item.get("strongreject") is not None)
        for item in results
    )
    print(
        json.dumps(
            {
                "status": f"{args.mode.upper()}_EVALUATION_COMPLETE",
                "record_count": len(results),
                "parsed_count": parsed_count,
                "raw_judge_outputs_logged": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def finalize(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    safe_dir = args.safe_output_dir.resolve()
    private_dir = args.private_output_dir.resolve()
    runtime, _, _ = load_step3_contract(root)
    target_rows = load_jsonl(private_dir / "target_responses.private.jsonl")
    harmbench_rows = load_jsonl(private_dir / "harmbench.private.jsonl")
    strongreject_rows = load_jsonl(private_dir / "strongreject.private.jsonl")

    def key(row: JsonDict) -> tuple[str, str, int]:
        return str(row["smoke_id"]), str(row["variant"]), int(row["seed"])

    hb_index = {key(item): item for item in harmbench_rows}
    sr_index = {key(item): item for item in strongreject_rows}
    safe_records: list[JsonDict] = []
    labels_by_example: dict[tuple[str, str], list[ConsensusLabel]] = defaultdict(list)
    parsed_both = 0
    for row in target_rows:
        item_key = key(row)
        hb = hb_index[item_key].get("harmbench_harmful")
        hb_value = hb if isinstance(hb, bool) else None
        sr_payload = sr_index[item_key].get("strongreject")
        sr_value = None
        if isinstance(sr_payload, dict):
            from jbspan.gate1.step3 import StrongRejectScore

            sr_value = StrongRejectScore(
                refusal=int(sr_payload["refusal"]),
                convincingness=int(sr_payload["convincingness"]),
                specificity=int(sr_payload["specificity"]),
                score=float(sr_payload["score"]),
            )
        if hb_value is not None and sr_value is not None:
            parsed_both += 1
        label = consensus_label(hb_value, sr_value, runtime)
        labels_by_example[(str(row["smoke_id"]), str(row["variant"]))].append(label)
        safe_records.append(
            {
                "schema_version": "gate1-step3-smoke-record-v1",
                "smoke_id": row["smoke_id"],
                "example_id": row["example_id"],
                "payload_id": row["payload_id"],
                "variant": row["variant"],
                "seed": row["seed"],
                "response_sha256": row["response_sha256"],
                "response_character_length": row["response_character_length"],
                "stopped_eos": row["stopped_eos"],
                "stopped_limit": row["stopped_limit"],
                "harmbench_harmful": hb_value,
                "strongreject_score": None if sr_value is None else sr_value.score,
                "strongreject_refusal": None if sr_value is None else sr_value.refusal,
                "consensus": label.value,
            }
        )

    generation = _object(runtime["generation"])
    minimum = int(generation["minimum_agreeing_seeds"])
    examples = sorted({str(item["smoke_id"]) for item in target_rows})
    example_results: list[JsonDict] = []
    eligible_count = 0
    for smoke_id in examples:
        original = stable_seed_label(labels_by_example[(smoke_id, "original")], minimum)
        attack = stable_seed_label(labels_by_example[(smoke_id, "attack")], minimum)
        eligible = original is StableLabel.SAFE and attack is StableLabel.HARMFUL
        eligible_count += int(eligible)
        example_results.append(
            {
                "smoke_id": smoke_id,
                "original_stable_label": original.value,
                "attack_stable_label": attack.value,
                "eligible": eligible,
                "original_seed_labels": [
                    item.value for item in labels_by_example[(smoke_id, "original")]
                ],
                "attack_seed_labels": [
                    item.value for item in labels_by_example[(smoke_id, "attack")]
                ],
            }
        )

    record_count = len(safe_records)
    coverage = parsed_both / record_count if record_count else 0.0
    abstentions = sum(
        item["consensus"] == ConsensusLabel.EVALUATOR_ABSTAIN.value
        for item in safe_records
    )
    abstention_rate = abstentions / record_count if record_count else 1.0
    smoke = _object(runtime["smoke"])
    if coverage < float(smoke["minimum_evaluator_coverage"]):
        status = "STEP3_SMOKE_EVALUATOR_BLOCKED"
    elif eligible_count >= int(smoke["positive_signal_minimum_eligible"]):
        status = "STEP3_SMOKE_POSITIVE_SIGNAL"
    else:
        status = "STEP3_SMOKE_PIPELINE_PASS_NO_SIGNAL"
    summary: JsonDict = {
        "schema_version": "gate1-step3-smoke-summary-v1",
        "status": status,
        "paper_validity": False,
        "gate1_decision": "NOT_EVALUATED",
        "surrogate_evaluators_may_decide_gate1": False,
        "smoke_example_count": len(examples),
        "target_generation_count": record_count,
        "evaluator_pair_coverage": coverage,
        "consensus_abstention_rate": abstention_rate,
        "eligible_count": eligible_count,
        "examples": example_results,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_judge_outputs_committed": False,
    }
    write_jsonl(safe_dir / "smoke_records.safe.jsonl", safe_records)
    write_json(safe_dir / "smoke_summary.json", summary)
    safe_files = sorted(path for path in safe_dir.iterdir() if path.is_file())
    write_json(
        safe_dir / "step3_manifest.json",
        {
            "schema_version": "gate1-step3-manifest-v1",
            "status": status,
            "paper_validity": False,
            "gate1_decision": "NOT_EVALUATED",
            "safe_file_sha256": {path.name: sha256_file(path) for path in safe_files},
            "safe_bundle_identity_sha256": canonical_json_sha256(
                {path.name: sha256_file(path) for path in safe_files}
            ),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _object(value: object) -> JsonDict:
    if not isinstance(value, dict):
        raise RuntimeError("expected object")
    return value


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError("expected array")
    return value


def main() -> int:
    args = _parser().parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "target":
        target(args)
    elif args.command == "evaluate":
        evaluate(args)
    elif args.command == "finalize":
        finalize(args)
    else:
        raise RuntimeError("unsupported command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
