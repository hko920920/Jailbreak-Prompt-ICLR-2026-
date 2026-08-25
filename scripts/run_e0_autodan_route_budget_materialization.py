from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity.


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(JsonObject, value)


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def literal_value(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def assignment_literal(module: ast.Module, name: str) -> object:
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return literal_value(node.value)
    return None


def argparse_defaults(module: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if not node.args:
            continue
        flag = literal_value(node.args[0])
        if not isinstance(flag, str) or not flag.startswith("--"):
            continue
        default: object = None
        for keyword in node.keywords:
            if keyword.arg == "default":
                default = literal_value(keyword.value)
                break
        values[flag[2:].replace("-", "_")] = default
    return values


def source_identity(source_root: Path, files: JsonObject) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for role, raw_spec in sorted(files.items()):
        spec = as_object(raw_spec, where=f"source.files.{role}")
        relative = Path(str(spec["path"]))
        path = source_root / relative
        exists = path.is_file()
        observed_blob = git_blob_sha(path) if exists else None
        expected_blob = str(spec["git_blob_sha"])
        row: JsonObject = {
            "role": role,
            "path": relative.as_posix(),
            "exists": exists,
            "expected_git_blob_sha": expected_blob,
            "observed_git_blob_sha": observed_blob,
            "git_blob_match": observed_blob == expected_blob,
            "sha256": sha256_file(path) if exists else None,
            "size_bytes": path.stat().st_size if exists else None,
        }
        expected_sha = spec.get("sha256")
        if expected_sha is not None:
            row["expected_sha256"] = str(expected_sha)
            row["sha256_match"] = row["sha256"] == expected_sha
        rows.append(row)
    return rows


def load_prompt_group(path: Path) -> list[str]:
    import torch

    value = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(value, (list, tuple)):
        raise TypeError("prompt-group artifact must be a list or tuple")
    if not all(isinstance(item, str) for item in value):
        raise TypeError("prompt-group artifact must contain only strings")
    return [str(item) for item in value]


def split_paragraphs_and_sentences(text: str) -> list[list[str]]:
    paragraphs = text.split("\n\n")
    return [re.split(r"(?<=[,.!?])\s+", paragraph) for paragraph in paragraphs]


def crossover(
    left: str,
    right: str,
    *,
    num_points: int,
    rng: random.Random,
) -> tuple[str, str]:
    paragraphs_left = split_paragraphs_and_sentences(left)
    paragraphs_right = split_paragraphs_and_sentences(right)
    output_left: list[str] = []
    output_right: list[str] = []
    for first, second in zip(paragraphs_left, paragraphs_right, strict=False):
        max_swaps = min(len(first), len(second)) - 1
        if max_swaps <= 0:
            output_left.append(" ".join(first))
            output_right.append(" ".join(second))
            continue
        swap_count = min(num_points, max_swaps)
        swap_indices = sorted(rng.sample(range(1, max_swaps + 1), swap_count))
        new_first: list[str] = []
        new_second: list[str] = []
        last_swap = 0
        for swap in swap_indices:
            if rng.choice((True, False)):
                new_first.extend(first[last_swap:swap])
                new_second.extend(second[last_swap:swap])
            else:
                new_first.extend(second[last_swap:swap])
                new_second.extend(first[last_swap:swap])
            last_swap = swap
        if rng.choice((True, False)):
            new_first.extend(first[last_swap:])
            new_second.extend(second[last_swap:])
        else:
            new_first.extend(second[last_swap:])
            new_second.extend(first[last_swap:])
        output_left.append(" ".join(new_first))
        output_right.append(" ".join(new_second))
    return "\n\n".join(output_left), "\n\n".join(output_right)


def has_exact_placeholder(candidate: str, placeholder: str) -> bool:
    return candidate.count(placeholder) == 1


def guard_candidate(
    candidate: str,
    *,
    placeholder: str,
    fallback: str,
) -> tuple[str, bool]:
    if not has_exact_placeholder(fallback, placeholder):
        raise ValueError("guard fallback must contain exactly one placeholder")
    if has_exact_placeholder(candidate, placeholder):
        return candidate, False
    return fallback, True


def exact_materialize(candidate: str, *, placeholder: str, payload: str) -> str:
    if not has_exact_placeholder(candidate, placeholder):
        raise ValueError("candidate must contain exactly one placeholder")
    output = candidate.replace(placeholder, payload)
    if output.count(payload) != 1 or output.encode().count(payload.encode()) != 1:
        raise ValueError("payload was not preserved exactly once")
    if placeholder in output:
        raise ValueError("placeholder remained after materialization")
    return output


def canonical_hash(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def select_valid_pool(
    pool: list[str],
    *,
    placeholder: str,
    sample_count: int,
) -> tuple[list[str], JsonObject]:
    valid = [item for item in pool if has_exact_placeholder(item, placeholder)]
    invalid_count = len(pool) - len(valid)
    ranked = sorted(valid, key=lambda item: (sha256_bytes(item.encode()), len(item)))
    if len(ranked) < sample_count:
        raise ValueError("not enough valid prompt-group references")
    selected = ranked[:sample_count]
    summary: JsonObject = {
        "total_count": len(pool),
        "valid_exact_placeholder_count": len(valid),
        "invalid_placeholder_count": invalid_count,
        "selected_count": len(selected),
        "selected_hashes_sha256": canonical_hash(
            [sha256_bytes(item.encode()) for item in selected]
        ),
        "raw_reference_text_recorded": False,
    }
    return selected, summary


def simulate_once(
    references: list[str],
    *,
    placeholder: str,
    payload: str,
    pair_count: int,
    replacement_count: int,
    seed: int,
    num_points: int,
) -> JsonObject:
    if pair_count * 2 > len(references):
        raise ValueError("crossover pair count exceeds selected reference pool")
    rng = random.Random(seed)
    children: list[str] = []
    raw_invalid = 0
    repaired = 0
    for pair_index in range(pair_count):
        left = references[2 * pair_index]
        right = references[2 * pair_index + 1]
        child_left, child_right = crossover(
            left,
            right,
            num_points=num_points,
            rng=rng,
        )
        for child, fallback in ((child_left, left), (child_right, right)):
            if not has_exact_placeholder(child, placeholder):
                raw_invalid += 1
            guarded, changed = guard_candidate(
                child,
                placeholder=placeholder,
                fallback=fallback,
            )
            repaired += int(changed)
            children.append(guarded)

    replacement_indices = list(range(min(replacement_count, len(children))))
    for index in replacement_indices:
        replacement = references[rng.randrange(len(references))]
        guarded, changed = guard_candidate(
            replacement,
            placeholder=placeholder,
            fallback=children[index],
        )
        repaired += int(changed)
        children[index] = guarded

    final_guarded: list[str] = []
    for index, candidate in enumerate(children):
        fallback = references[index % len(references)]
        guarded, changed = guard_candidate(
            candidate,
            placeholder=placeholder,
            fallback=fallback,
        )
        repaired += int(changed)
        final_guarded.append(guarded)

    materialized = [
        exact_materialize(item, placeholder=placeholder, payload=payload)
        for item in final_guarded
    ]
    candidate_hashes = [sha256_bytes(item.encode()) for item in final_guarded]
    materialized_hashes = [sha256_bytes(item.encode()) for item in materialized]
    return {
        "candidate_count": len(final_guarded),
        "raw_crossover_invalid_count": raw_invalid,
        "guard_repair_count": repaired,
        "all_guarded_candidates_valid": all(
            has_exact_placeholder(item, placeholder) for item in final_guarded
        ),
        "all_materialized_payload_exact_once": all(
            item.count(payload) == 1 and item.encode().count(payload.encode()) == 1
            for item in materialized
        ),
        "candidate_hashes_sha256": canonical_hash(candidate_hashes),
        "materialized_hashes_sha256": canonical_hash(materialized_hashes),
        "raw_candidate_text_recorded": False,
        "raw_materialized_text_recorded": False,
    }


def verify_predecessors(root: Path, specs: object) -> list[JsonObject]:
    if not isinstance(specs, list):
        raise TypeError("predecessors must be an array")
    rows: list[JsonObject] = []
    for raw in specs:
        spec = as_object(raw, where="predecessor")
        path = root / str(spec["path"])
        observed_blob = git_blob_sha(path)
        result = load_object(path)
        rows.append(
            {
                "path": str(spec["path"]),
                "expected_git_blob_sha": str(spec["git_blob_sha"]),
                "observed_git_blob_sha": observed_blob,
                "git_blob_match": observed_blob == str(spec["git_blob_sha"]),
                "required_status": str(spec["required_status"]),
                "observed_status": result.get("status"),
                "status_match": result.get("status") == spec["required_status"],
            }
        )
    return rows


def run_smoke(
    *,
    root: Path,
    config_path: Path,
    source_root: Path,
    output_path: Path,
) -> JsonObject:
    config = load_object(config_path)
    expected_status = "FROZEN_BEFORE_AUTODAN_HARMLESS_CANDIDATE_MATERIALIZATION"
    if config["status"] != expected_status:
        raise ValueError("unexpected contract status")
    if config["frozen"] is not True or config["paper_validity"] is not False:
        raise ValueError("invalid contract boundary")

    predecessors = verify_predecessors(root, config["predecessors"])
    predecessor_pass = all(
        row["git_blob_match"] is True and row["status_match"] is True
        for row in predecessors
    )

    source = as_object(config["source"], where="source")
    files = as_object(source["files"], where="source.files")
    identities = source_identity(source_root, files)
    source_pass = all(
        row["git_blob_match"] is True and row.get("sha256_match", True) is True
        for row in identities
    )

    def source_path(role: str) -> Path:
        spec = as_object(files[role], where=f"source.files.{role}")
        return source_root / str(spec["path"])

    route = as_object(config["route"], where="route")
    budget = as_object(config["optimization_budget"], where="optimization_budget")
    selection = as_object(config["candidate_selection"], where="candidate_selection")
    smoke = as_object(config["harmless_smoke"], where="harmless_smoke")
    gate = as_object(config["decision_gate"], where="decision_gate")

    ga_module = ast.parse(source_path("ga_entrypoint").read_text(encoding="utf-8"))
    defaults = argparse_defaults(ga_module)
    observed_defaults: JsonObject = {
        "seed": assignment_literal(ga_module, "seed"),
        "num_steps": defaults.get("num_steps"),
        "batch_size": defaults.get("batch_size"),
        "num_elites_fraction": defaults.get("num_elites"),
        "crossover_probability": defaults.get("crossover"),
        "crossover_points": defaults.get("num_points"),
        "mutation_rate": defaults.get("mutation"),
    }
    expected_defaults: JsonObject = {
        "seed": budget["development_screen_seed"],
        "num_steps": budget["num_steps"],
        "batch_size": budget["batch_size"],
        "num_elites_fraction": budget["num_elites_fraction"],
        "crossover_probability": budget["crossover_probability"],
        "crossover_points": budget["crossover_points"],
        "mutation_rate": budget["mutation_rate"],
    }
    budget_matches_official = observed_defaults == expected_defaults
    elite_integer_consistent = int(
        int(budget["batch_size"]) * float(budget["num_elites_fraction"])
    ) == int(budget["num_elites_integer"])
    forward_budget_consistent = (
        int(budget["num_steps"]) * int(budget["batch_size"])
        == int(budget["maximum_model_forward_candidates_per_behavior_per_seed"])
    )

    pool = load_prompt_group(source_path("prompt_group"))
    placeholder = str(route["payload_placeholder"])
    references, pool_summary = select_valid_pool(
        pool,
        placeholder=placeholder,
        sample_count=int(smoke["pool_sample_count"]),
    )

    repetitions = int(smoke["fresh_repetitions"])
    simulation_rows = [
        simulate_once(
            references,
            placeholder=placeholder,
            payload=str(smoke["synthetic_payload"]),
            pair_count=int(smoke["crossover_pair_count"]),
            replacement_count=int(smoke["reference_replacement_count"]),
            seed=int(smoke["seed"]),
            num_points=int(budget["crossover_points"]),
        )
        for _ in range(repetitions)
    ]
    deterministic = len(
        {
            (
                row["candidate_hashes_sha256"],
                row["materialized_hashes_sha256"],
                row["guard_repair_count"],
            )
            for row in simulation_rows
        }
    ) == 1

    guard = as_object(route["candidate_guard"], where="route.candidate_guard")
    enabled_routes_guarded = (
        route["external_api_mutation_enabled"] is False
        and route["local_synonym_mutation_enabled"] is False
        and route["reference_pool_replacement_mutation_enabled"] is True
        and route["crossover_enabled"] is True
        and guard["guard_applied_after_crossover"] is True
        and guard["guard_applied_after_reference_replacement"] is True
        and guard["guard_applied_before_scoring"] is True
        and guard["guard_applied_before_final_materialization"] is True
        and guard["payload_mutation_allowed"] is False
    )
    selection_frozen = (
        selection["primary_score"] == "MINIMUM_FROZEN_TARGET_PREFIX_LOSS"
        and selection["success_evaluator_used_for_selection"] is False
        and selection["top_k_per_behavior_per_generation_seed"] == 1
    )
    route_frozen = (
        route["artifact_choice"] == "REGENERATE_FROM_PINNED_PROMPT_GROUP"
        and route["algorithm_variant"] == "GA"
        and route["prompt_group_loading"] == "TORCH_LOAD_WEIGHTS_ONLY"
        and route["fixed_step_execution_required"] is True
        and route["official_early_stop_enabled"] is False
    )

    checks: JsonObject = {
        "predecessor_identities_and_statuses": predecessor_pass,
        "source_identities": source_pass,
        "route_frozen": route_frozen,
        "budget_matches_official_defaults": budget_matches_official,
        "elite_integer_consistent": elite_integer_consistent,
        "forward_budget_consistent": forward_budget_consistent,
        "candidate_selection_frozen": selection_frozen,
        "prompt_group_nonempty_string_sequence": len(pool) > 0,
        "valid_reference_pool_sufficient": (
            int(pool_summary["valid_exact_placeholder_count"])
            >= int(smoke["pool_sample_count"])
        ),
        "enabled_mutation_routes_payload_guarded": enabled_routes_guarded,
        "deterministic_harmless_materialization": deterministic,
        "all_guarded_candidates_valid": all(
            row["all_guarded_candidates_valid"] is True for row in simulation_rows
        ),
        "all_materialized_payload_exact_once": all(
            row["all_materialized_payload_exact_once"] is True
            for row in simulation_rows
        ),
        "no_target_or_external_api": (
            smoke["target_model_weights_downloaded"] is False
            and smoke["target_model_called"] is False
            and smoke["target_model_generation_performed"] is False
            and route["external_api_mutation_enabled"] is False
        ),
    }
    operational_pass = all(value is True for value in checks.values())
    status = (
        "E0_AUTODAN_ROUTE_BUDGET_MATERIALIZATION_PASS_REMAIN_PREOUTPUT"
        if operational_pass
        else "E0_AUTODAN_ROUTE_BUDGET_MATERIALIZATION_FAIL"
    )
    next_operation = gate["on_pass"] if operational_pass else gate["on_fail"]

    result: JsonObject = {
        "schema_version": "e0-autodan-route-budget-materialization-result-v1",
        "status": status,
        "paper_validity": False,
        "operational_pass": operational_pass,
        "family": config["family"],
        "regime": config["regime"],
        "family_admitted_to_balanced_signal_screen": False,
        "config_sha256": sha256_file(config_path),
        "predecessors": predecessors,
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "tree_sha": source["tree_sha"],
            "license": source["license"],
            "file_identities": identities,
        },
        "route": {
            "route_id": route["route_id"],
            "artifact_choice": route["artifact_choice"],
            "algorithm_variant": route["algorithm_variant"],
            "prompt_group_loading": route["prompt_group_loading"],
            "external_api_mutation_enabled": False,
            "local_synonym_mutation_enabled": False,
            "reference_pool_replacement_mutation_enabled": True,
            "crossover_enabled": True,
            "fixed_step_execution_required": True,
            "early_stopping_enabled": False,
            "payload_guard_policy": guard["policy_on_invalid_candidate"],
        },
        "optimization_budget": budget,
        "candidate_selection": selection,
        "observed_official_defaults": observed_defaults,
        "prompt_group": pool_summary,
        "harmless_simulation": {
            "repetitions": repetitions,
            "deterministic": deterministic,
            "representative": simulation_rows[0],
            "raw_text_recorded": False,
        },
        "mandatory_checks": checks,
        "real_harmful_payload_used": False,
        "target_model_weights_downloaded": False,
        "target_model_called": False,
        "target_model_generation_performed": False,
        "external_api_called": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": next_operation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run harmless AutoDAN route, budget, payload-guard materialization smoke"
        )
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_smoke(
        root=args.root,
        config_path=args.config,
        source_root=args.source_root,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "family_admitted_to_balanced_signal_screen": result[
                    "family_admitted_to_balanced_signal_screen"
                ],
                "target_model_called": result["target_model_called"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
