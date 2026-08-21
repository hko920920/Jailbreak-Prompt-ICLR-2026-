from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence, Set
from pathlib import Path

from jbspan.gate1.materialize import SourceRow
from jbspan.gate1.models import ContractValidationError
from jbspan.gate1.util import canonical_json_sha256, load_json, sha256_text

JsonDict = dict[str, object]


def payload_id(index: int) -> str:
    if index < 0:
        raise ContractValidationError("payload index cannot be negative")
    return f"JBB-{index:03d}"


def select_confirmatory_rows(
    rows: Sequence[SourceRow],
    *,
    excluded_payload_ids: Set[str],
    selection_seed: str,
) -> tuple[JsonDict, ...]:
    if not selection_seed:
        raise ContractValidationError("confirmatory selection seed cannot be empty")
    grouped: dict[str, list[SourceRow]] = defaultdict(list)
    for row in rows:
        if payload_id(row.index) not in excluded_payload_ids:
            grouped[row.category].append(row)
    if len(grouped) != 10:
        raise ContractValidationError("confirmatory pool must cover exactly ten categories")
    if sum(len(items) for items in grouped.values()) != 40:
        raise ContractValidationError("confirmatory pool must contain exactly forty unused rows")

    selected: list[JsonDict] = []
    for category in sorted(grouped):
        ranked = sorted(
            grouped[category],
            key=lambda row: sha256_text(
                "\0".join((selection_seed, category, payload_id(row.index)))
            ),
        )
        if len(ranked) != 4:
            raise ContractValidationError(
                "each category must contribute exactly four unused rows"
            )
        row = ranked[0]
        item_id = payload_id(row.index)
        selected.append(
            {
                "payload_id": item_id,
                "source_row_index": row.index,
                "category": row.category,
                "behavior": row.behavior,
                "payload_sha256": sha256_text(row.goal),
                "selection_sha256": sha256_text(
                    "\0".join((selection_seed, row.category, item_id))
                ),
            }
        )
    selected.sort(key=lambda item: str(item["category"]))
    if len(selected) != 10:
        raise ContractValidationError("confirmatory selection must contain ten rows")
    if len({str(item["payload_id"]) for item in selected}) != 10:
        raise ContractValidationError("confirmatory payload IDs must be unique")
    return tuple(selected)


def assign_candidates(
    selected: Sequence[JsonDict],
    *,
    candidate_ids: Sequence[str],
    assignment_seed: str,
) -> tuple[JsonDict, ...]:
    if len(selected) != 10:
        raise ContractValidationError("candidate assignment requires ten selected rows")
    if len(candidate_ids) != 5 or len(set(candidate_ids)) != 5:
        raise ContractValidationError("candidate assignment requires five unique candidates")
    if not assignment_seed:
        raise ContractValidationError("assignment seed cannot be empty")

    ranked = sorted(
        selected,
        key=lambda item: sha256_text(
            "\0".join(
                (
                    assignment_seed,
                    str(item["category"]),
                    str(item["payload_id"]),
                )
            )
        ),
    )
    assigned: list[JsonDict] = []
    for index, item in enumerate(ranked):
        assigned.append(
            {
                **item,
                "confirmatory_id": f"G1S3B-C{index:02d}",
                "candidate_id": candidate_ids[index % len(candidate_ids)],
                "assignment_sha256": sha256_text(
                    "\0".join(
                        (
                            assignment_seed,
                            str(item["category"]),
                            str(item["payload_id"]),
                        )
                    )
                ),
            }
        )
    counts = Counter(str(item["candidate_id"]) for item in assigned)
    if set(counts) != set(candidate_ids) or set(counts.values()) != {2}:
        raise ContractValidationError("each candidate must be assigned exactly twice")
    return tuple(assigned)


def build_confirmatory_manifest(
    rows: Sequence[SourceRow],
    *,
    excluded_payload_ids: Set[str],
    candidate_ids: Sequence[str],
    selection_seed: str,
    assignment_seed: str,
    payload_source_revision: str,
    payload_source_sha256: str,
) -> JsonDict:
    selected = select_confirmatory_rows(
        rows,
        excluded_payload_ids=excluded_payload_ids,
        selection_seed=selection_seed,
    )
    assigned = assign_candidates(
        selected,
        candidate_ids=candidate_ids,
        assignment_seed=assignment_seed,
    )
    selected_ids = [str(item["payload_id"]) for item in assigned]
    return {
        "schema_version": "gate1-step3b-confirmatory-split-v1",
        "status": "CONFIRMATORY_SPLIT_FROZEN_BEFORE_TARGET_OUTPUT",
        "payload_source_revision": payload_source_revision,
        "payload_source_sha256": payload_source_sha256,
        "selection_seed": selection_seed,
        "assignment_seed": assignment_seed,
        "unused_source_row_count": 40,
        "selected_count": 10,
        "category_count": 10,
        "selected_payload_ids_sha256": canonical_json_sha256(selected_ids),
        "candidate_ids_sha256": canonical_json_sha256(list(candidate_ids)),
        "items": list(assigned),
        "target_outputs_observed_at_freeze": False,
        "original_smoke_reused": False,
        "final_evaluation_outputs_observed": False,
        "gate2_heldout_used": False,
        "raw_payloads_committed": False,
    }


def load_confirmatory_contract(root: Path) -> JsonDict:
    value = load_json(root / "configs/gate1/gate1_step3b_confirmatory_smoke.json")
    validate_confirmatory_contract(value)
    return value


def validate_confirmatory_contract(value: JsonDict) -> None:
    if value.get("schema_version") != "gate1-step3b-confirmatory-smoke-contract-v1":
        raise ContractValidationError("unsupported confirmatory-smoke contract")
    if value.get("frozen") is not True or value.get("paper_validity") is not False:
        raise ContractValidationError(
            "confirmatory-smoke contract must be frozen and non-paper-valid"
        )
    boundary = value.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ContractValidationError("confirmatory claim boundary is missing")
    false_fields = (
        "old_smoke_may_be_reused_as_confirmation",
        "final_evaluation_may_open_before_pass",
        "gate2_heldout_may_be_used",
        "case_specific_prompt_rewriting_allowed",
        "threshold_tuning_after_outputs_allowed",
        "causal_oracle_enabled",
        "wavelet_enabled",
    )
    if any(boundary.get(field) is not False for field in false_fields):
        raise ContractValidationError("confirmatory claim boundary was weakened")
