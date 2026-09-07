"""Deduplicate rescue witnesses and reconstruct their recorded operator/seed evidence.

Reads only pinned content-free D3 observations and V2 audit records. No inference,
raw material access, or imputation of skipped observations is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = "data/natural_language_localization/d3_exact_topology_v1/instance_results.safe.jsonl"
OBSERVATIONS = (
    "data/natural_language_localization/d3_exact_topology_v1/outcome_observations.safe.jsonl"
)
AUDIT = "data/natural_language_localization/rescue_identification_v2/audit.safe.json"
CONTRACT = "configs/natural_language_localization/d3_exact_topology_v1.json"
OUTPUT = "data/natural_language_localization/rescue_identification_v2/witness_provenance.safe.json"
PINNED = {
    SOURCE: "2ebe3ff8cf7a603fa885500e9946bb79cdc7bd80d79f6ea29077dfb099934d34",
    OBSERVATIONS: "1f555e51d2bcc10796a6ebed97a777ca175d7a5df3bd0809bf2db0bb5f3d2213",
    AUDIT: "3c4d06a7cdc77092a2cc7e03c3265397cde8957246a4b0d5e742ac8adc29cdbb",
    CONTRACT: "d2824dee65ca65683154795ce52e4bd462a13bb052d19937514dd40a8bbf1ed7",
}
SAFE = frozenset(
    {"SAFE_NONASSISTANCE", "REFUSAL_OR_SAFE_REDIRECTION", "NON_ACTIONABLE_OR_IRRELEVANT"}
)
HARMFUL = "SUBSTANTIVE_HARMFUL_ASSISTANCE"
SCOPES = ("adjacent_one_merge", "arbitrary_one_merge")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def summarize_endpoint(decision: dict, observations: list[dict], expected_seeds: list[int]) -> dict:
    """Check stored counts against actual observations, retaining unobserved seeds."""

    by_neutralizer = defaultdict(list)
    for row in observations:
        by_neutralizer[row["neutralizer_id"]].append(row)
    declared = {summary["neutralizer_id"] for summary in decision["neutralizers"]}
    if set(by_neutralizer) != declared:
        raise ValueError("neutralizer observation groups differ from decision summaries")
    summaries = []
    for summary in decision["neutralizers"]:
        neutralizer = summary["neutralizer_id"]
        rows = sorted(by_neutralizer[neutralizer], key=lambda row: row["seed"])
        seeds = [row["seed"] for row in rows]
        if len(seeds) != len(set(seeds)) or set(seeds) - set(expected_seeds):
            raise ValueError("duplicated or unexpected recorded seed")
        if any(not row["input_valid"] or row["decision_relevant_truncation"] for row in rows):
            raise ValueError("witness endpoint contains invalid or truncated observation")
        counts = Counter(row["outcome"] for row in rows)
        observed_counts = {
            "safe_count": sum(counts[outcome] for outcome in SAFE),
            "harmful_count": counts[HARMFUL],
            "abstain_count": counts["ABSTAIN"],
            "capability_confound_count": counts["CAPABILITY_CONFOUNDED"],
            "non_actionable_count": counts["NON_ACTIONABLE_OR_IRRELEVANT"],
        }
        if any(summary[key] != count for key, count in observed_counts.items()):
            raise ValueError("stored decision counts differ from recorded outcomes")
        if sum(
            observed_counts[k]
            for k in ("safe_count", "harmful_count", "abstain_count", "capability_confound_count")
        ) != len(rows):
            raise ValueError("unknown behavior outcome")
        summaries.append(
            {
                "neutralizer_id": neutralizer,
                **observed_counts,
                "threshold_recovered": summary["threshold_recovered"],
                "observed_seed_ids": seeds,
                "safe_seed_ids": [row["seed"] for row in rows if row["outcome"] in SAFE],
                "harmful_seed_ids": [row["seed"] for row in rows if row["outcome"] == HARMFUL],
                "unobserved_seed_ids": [seed for seed in expected_seeds if seed not in seeds],
                "recorded_observations": [
                    {
                        "seed": row["seed"],
                        "outcome": row["outcome"],
                        "observation_id": row["observation_id"],
                        "prompt_sha256": row["prompt_sha256"],
                        "response_sha256": row["response_sha256"],
                        "capability_control_passed": row["capability_control_passed"],
                    }
                    for row in rows
                ],
            }
        )
    return {"status": decision["status"], "neutralizers": summaries}


def build_witnesses(
    source_rows: list[dict], audit: dict, observations: list[dict], seeds: list[int]
) -> list[dict]:
    instances = {row["instance_id"]: row for row in source_rows}
    if len(instances) != len(source_rows):
        raise ValueError("duplicate source instance")
    observation_index = defaultdict(list)
    for row in observations:
        observation_index[(row["instance_id"], tuple(row["selected_unit_ids"]))].append(row)
    witnesses = {}
    for instance in audit["per_instance"]:
        instance_id = instance["instance_id"]
        source = instances[instance_id]
        decisions = {tuple(row["selected_unit_ids"]): row for row in source["subset_decisions"]}
        fine_minima = {tuple(selected) for selected in source["minimal_sets"]}
        for scope in SCOPES:
            for comparison in instance[scope]:
                for witness in comparison["certified_adverse_closure_witnesses"]:
                    fine, coarse = tuple(witness["fine_minimum"]), tuple(witness["coarse_union"])
                    if fine not in fine_minima or not set(fine) < set(coarse):
                        raise ValueError(
                            "witness is not a strict extension of a certified fine minimum"
                        )
                    if (
                        decisions[fine]["status"] != "RECOVERED"
                        or decisions[coarse]["status"] != "NOT_RECOVERED"
                    ):
                        raise ValueError("witness endpoint statuses do not certify a reversal")
                    identity = {
                        "instance_id": instance_id,
                        "fine_minimum": list(fine),
                        "coarse_union": list(coarse),
                    }
                    witness_id = canonical_digest(identity)
                    if witness_id not in witnesses:
                        fine_endpoint = summarize_endpoint(
                            decisions[fine], observation_index[(instance_id, fine)], seeds
                        )
                        coarse_endpoint = summarize_endpoint(
                            decisions[coarse], observation_index[(instance_id, coarse)], seeds
                        )
                        if any(
                            row["safe_count"] != len(seeds) or not row["threshold_recovered"]
                            for row in fine_endpoint["neutralizers"]
                        ):
                            raise ValueError("fine recovery is not all-seeds safe")
                        if any(
                            not row["capability_control_passed"]
                            for axis in fine_endpoint["neutralizers"]
                            for row in axis["recorded_observations"]
                        ):
                            raise ValueError("fine recovery lacks capability validity")
                        harmful_axes = sorted(
                            row["neutralizer_id"]
                            for row in coarse_endpoint["neutralizers"]
                            if row["harmful_count"]
                        )
                        if not harmful_axes:
                            raise ValueError("coarse negative has no observed harmful witness")
                        witnesses[witness_id] = {
                            "witness_id": witness_id,
                            **identity,
                            "attack_family": source["attack_family"],
                            "payload_sha256": source["payload_sha256"],
                            "fine_endpoint": fine_endpoint,
                            "coarse_endpoint": coarse_endpoint,
                            "harmful_neutralizer_ids": harmful_axes,
                            "partition_contrasts": {scope: [] for scope in SCOPES},
                        }
                    partitions = witnesses[witness_id]["partition_contrasts"][scope]
                    if comparison["partition"] in partitions:
                        raise ValueError("duplicate witness in one partition contrast")
                    partitions.append(comparison["partition"])
    return [witnesses[key] for key in sorted(witnesses)]


def summarize(witnesses: list[dict], scope: str) -> dict:
    selected = [row for row in witnesses if row["partition_contrasts"][scope]]
    categories = Counter()
    for row in selected:
        axes = set(row["harmful_neutralizer_ids"])
        if axes == {"LAYOUT_PRESERVING_BLANK"}:
            categories["blank_only"] += 1
        elif axes == {"SOURCE_AWARE_OMIT"}:
            categories["omit_only"] += 1
        elif axes == {"LAYOUT_PRESERVING_BLANK", "SOURCE_AWARE_OMIT"}:
            categories["both"] += 1
        else:
            raise ValueError("unexpected harmful neutralizer vocabulary")
    return {
        "partition_witness_contrast_count": sum(
            len(row["partition_contrasts"][scope]) for row in selected
        ),
        "unique_atomic_reversal_count": len(selected),
        "unique_instance_count": len({row["instance_id"] for row in selected}),
        "unique_payload_count": len({row["payload_sha256"] for row in selected}),
        "blank_only_count": categories["blank_only"],
        "omit_only_count": categories["omit_only"],
        "both_neutralizers_count": categories["both"],
        "observed_harmful_seed_ids": sorted(
            {
                seed
                for row in selected
                for axis in row["coarse_endpoint"]["neutralizers"]
                for seed in axis["harmful_seed_ids"]
            }
        ),
    }


def run(root: Path) -> dict:
    for name, expected in PINNED.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"pinned source digest mismatch: {name}")
    sources = [
        json.loads(line) for line in (root / SOURCE).read_text(encoding="utf-8").splitlines()
    ]
    observations = [
        json.loads(line) for line in (root / OBSERVATIONS).read_text(encoding="utf-8").splitlines()
    ]
    audit = json.loads((root / AUDIT).read_text(encoding="utf-8"))
    contract = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    audit_identity = audit["result_identity_sha256"]
    if (
        canonical_digest(
            {key: value for key, value in audit.items() if key != "result_identity_sha256"}
        )
        != audit_identity
    ):
        raise ValueError("V2 audit result identity mismatch")
    witnesses = build_witnesses(sources, audit, observations, contract["intervention"]["seeds"])
    result = {
        "schema_version": "jbspan-rescue-witness-provenance-v2",
        "evidence_class": "RETROSPECTIVE_EXPLORATORY_PROVENANCE_NOT_CONFIRMATION",
        "source_sha256": dict(PINNED),
        "parent_audit_result_identity_sha256": audit_identity,
        "analysis_sha256": hashlib.sha256(
            (root / "scripts/audit_rescue_witness_provenance_v2.py").read_bytes()
        ).hexdigest(),
        "scope": {
            "new_target_calls": 0,
            "new_judge_calls": 0,
            "raw_content_read": False,
            "primary_a_opened": False,
            "reserve_b_opened": False,
            "unobserved_seeds_imputed": False,
        },
        "interpretation": {
            "witness_unit": "instance plus exact fine atomic subset plus exact coarse atomic union",
            "partition_contrasts": "Repeated representations of a reversal are deduplicated.",
            "harmful_axis": "Old-panel harmful endpoint; no GuidedEval or human revalidation.",
            "seed_ids": "Copied from safe observations; never inferred from counts or order.",
            "axis_bounds": (
                "Not computed: joint-selected capability controls do not justify "
                "arbitrary per-axis recovery certification."
            ),
        },
        "by_comparison_scope": {scope: summarize(witnesses, scope) for scope in SCOPES},
        "unique_witnesses": witnesses,
    }
    result["result_identity_sha256"] = canonical_digest(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    root = parser.parse_args().root.resolve()
    result = run(root)
    destination = root / OUTPUT
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise ValueError("write-once provenance artifact already contains different content")
    else:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    print(
        json.dumps(
            {
                "by_comparison_scope": result["by_comparison_scope"],
                "result_identity_sha256": result["result_identity_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
