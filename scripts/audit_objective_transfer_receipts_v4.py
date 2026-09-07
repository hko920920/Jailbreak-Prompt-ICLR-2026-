"""Post-freeze QA: replay completed V4 harmless receipts without model calls.

This does not change experimental labels, the frozen plan, or the analysis.
Default is a completed-result-only preflight; --execute reads V4 receipts and
publishes one content-free write-once aggregate. No reply text is copied out.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402

SCHEMA = "jbspan-objective-transfer-receipt-audit-v4"
CONTRACT_SHA256 = "6680768a8ca25bfe8b7b36ef40cbbcaa16af96adce1822ec633c1ca433519030"
DEFAULT_CONFIG = "configs/natural_language_localization/rescue_objective_transfer_v4.json"
RUNNER = "scripts/run_rescue_objective_transfer_v4.py"
AUDIT_TEST = "tests/test_objective_transfer_receipt_audit_v4.py"
SCORE_FIELDS = {
    "status",
    "error_code",
    "score_reason",
    "reply_sha256",
    "output_sha256",
    "finish_reason_sha256",
    "returned_model_sha256",
    "completion_tokens",
}
PUBLIC_FIELDS = SCORE_FIELDS | {"elapsed_seconds", "private_receipt_sha256"}


def emit(status: str, **fields) -> None:
    value = {"schema_version": SCHEMA, "status": status, **fields}
    support.content_free(value)
    print(json.dumps(value, sort_keys=True), flush=True)


def load_runner(root: Path, config: dict):
    dependency = next((s for s in config["dependencies"].values() if s["path"] == RUNNER), None)
    if dependency is None or support.file_digest(root / RUNNER) != dependency["sha256"]:
        raise ValueError("frozen V4 runner dependency differs")
    spec = importlib.util.spec_from_file_location("_v4_receipt_audit_runner", root / RUNNER)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import frozen V4 verification helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed_inputs(root: Path, relative: str, contract_sha: str):
    """This gate completes before any private path enumeration or content read."""
    if contract_sha != CONTRACT_SHA256:
        raise ValueError("only the exact frozen V4 validation contract is permitted")
    path = support.contained(root, relative)
    if support.file_digest(path) != contract_sha:
        raise ValueError("V4 contract file hash differs")
    config = support.read_object(path)
    if config["recording"]["private_base"] != "artifacts/rescue_objective_transfer_v4":
        raise ValueError("only the dedicated V4 harmless receipt directory is permitted")
    runner = load_runner(root, config)
    config, cases, strata, helper = runner.verify_config(root, relative, contract_sha)
    plan = runner.build_plan(config, cases, strata, helper)
    runner.verify_plan(plan, config)
    safe, private = helper.directories(root, config, contract_sha)
    result_path = safe / "validation.safe.json"
    if not result_path.is_file():
        raise RuntimeError("completed V4 result required before any receipt access")
    value = support.read_object(result_path)
    runner.verify_result(value, contract_sha, plan)
    if (
        value.get("logical_rows") != 1280
        or value.get("unique_phase_requests") != 1120
        or value.get("completed_unique_replies") != 1120
        or value.get("total_journaled_unique_requests") != 1120
        or value.get("owned_servers_stopped") is not True
    ):
        raise ValueError("complete stopped V4 validation with all receipts is required")
    indexed = {}
    for row, planned in zip(value["rows"], plan, strict=True):
        if set(row) != set(runner.public_plan([planned])[0]) | PUBLIC_FIELDS:
            raise ValueError("completed safe row fields differ")
        fields = {key: row[key] for key in PUBLIC_FIELDS}
        if indexed.setdefault(row["execution_key"], fields) != fields:
            raise ValueError("shared request has contradictory safe views")
    if len(indexed) != 1120:
        raise ValueError("completed result does not contain all 1,120 unique requests")
    for field, expected in (
        (
            "counts",
            {
                s: sum(r["status"] == s for r in value["rows"])
                for s in ("CORRECT", "INCORRECT", "UNKNOWN")
            },
        ),
        ("unique_request_counts", dict(Counter(r["status"] for r in indexed.values()))),
        ("fixed_frame_counts", runner.frame_counts(plan)),
        ("stratum_views", runner.stratum_views(value["rows"])),
    ):
        if value.get(field) != expected:
            raise ValueError("completed safe aggregate differs from its rows")
    return config, plan, helper, value, result_path, safe, private / "checkpoints"


def verify_receipt(
    checkpoints: Path, identity: dict, observed: dict, model: dict, expected_answer: str, helper
) -> dict:
    key = identity["execution_key"]
    pending = checkpoints / f"{key}.pending.safe.json"
    path = checkpoints / f"{key}.reply.private.json"
    # No alternate checkpoint path, historical corpus, or copied reply is consulted.
    if (
        pending.resolve().parent != checkpoints.resolve()
        or path.resolve().parent != checkpoints.resolve()
    ):
        raise ValueError("receipt or journal escapes the dedicated checkpoint directory")
    stored = support.read_object(path)
    if set(stored) != {"identity", "safe_result", "raw_reply", "receipt_sha256"}:
        raise ValueError("private receipt schema differs")
    if stored["identity"] != identity or support.read_object(pending) != identity:
        raise ValueError("receipt and durable pending identity differ")
    body = {k: v for k, v in stored.items() if k != "receipt_sha256"}
    receipt_sha = support.digest(body)
    if stored["receipt_sha256"] != receipt_sha or observed["private_receipt_sha256"] != receipt_sha:
        raise ValueError("private receipt digest or public commitment differs")
    fields = stored["safe_result"]
    if not isinstance(fields, dict) or set(fields) != SCORE_FIELDS | {"elapsed_seconds"}:
        raise ValueError("stored score metadata schema differs")
    reply = stored["raw_reply"]
    if reply is None:
        replay = {
            "status": "UNKNOWN",
            "error_code": "TRANSPORT_UNCERTAIN_NO_RETRY",
            "score_reason": None,
            "reply_sha256": None,
            "output_sha256": None,
            "finish_reason_sha256": None,
            "returned_model_sha256": None,
            "completion_tokens": None,
        }
    else:
        if not isinstance(reply, dict):
            raise ValueError("recorded provider reply is not an object")
        replay = helper.parse_reply(reply, model, expected_answer)
    if set(replay) != SCORE_FIELDS:
        raise ValueError("frozen reply parser score schema differs")
    if any(fields[k] != replay[k] or observed[k] != replay[k] for k in SCORE_FIELDS):
        raise ValueError("replayed reply score or provenance differs from committed labels")
    elapsed = fields["elapsed_seconds"]
    if (
        type(elapsed) not in (int, float)
        or not math.isfinite(elapsed)
        or elapsed < 0
        or observed["elapsed_seconds"] != elapsed
    ):
        raise ValueError("elapsed metadata is malformed or differs from committed value")
    return {
        "execution_key": key,
        "private_receipt_sha256": receipt_sha,
        "status": replay["status"],
        "error_code": replay["error_code"],
        "provider_reply_replayed": reply is not None,
        "transport_unknown_retained": reply is None,
    }


def audit(root: Path, relative: str, contract_sha: str, *, execute: bool) -> dict:
    config, plan, helper, value, result_path, safe, checkpoints = completed_inputs(
        root, relative, contract_sha
    )
    if not execute:
        result = {
            "contract_sha256": contract_sha,
            "completed_validation_verified": True,
            "logical_rows": 1280,
            "unique_receipts": 1120,
            "private_inputs_read": False,
            "model_files_read": False,
            "network_calls": 0,
        }
        emit("COMPLETED_V4_RECEIPT_AUDIT_READY", **result)
        return result
    expected_keys = {row["execution_key"] for row in plan}
    # Enumerate only this completed contract's dedicated harmless checkpoint folder.
    actual_replies = {
        path.name.removesuffix(".reply.private.json")
        for path in checkpoints.glob("*.reply.private.json")
    }
    actual_pending = {
        path.name.removesuffix(".pending.safe.json")
        for path in checkpoints.glob("*.pending.safe.json")
    }
    if actual_replies != expected_keys or actual_pending != expected_keys:
        raise ValueError("completed V4 checkpoint filename set differs from the frozen plan")
    models = {m["model_id"]: m for m in config["models"]}
    audited = {}
    for observed, planned in zip(value["rows"], plan, strict=True):
        key = planned["execution_key"]
        if key in audited:
            continue  # Duplicate public views were checked before any private access.
        audited[key] = verify_receipt(
            checkpoints,
            helper.request_identity(contract_sha, planned),
            observed,
            models[planned["model_id"]],
            planned["expected_answer"],
            helper,
        )
        if len(audited) % 200 == 0:
            emit(
                "V4_RECEIPT_REPLAY_PROGRESS",
                verified_unique_receipts=len(audited),
                expected_unique_receipts=1120,
            )
    result = {
        "schema_version": SCHEMA,
        "status": "V4_COMPLETED_RECEIPT_REPLAY_AUDIT_PASS",
        "contract_sha256": contract_sha,
        "validation_file_sha256": support.file_digest(result_path),
        "validation_identity_sha256": value["result_identity_sha256"],
        "plan_sha256": value["plan_sha256"],
        "audit_source_sha256": support.file_digest(Path(__file__)),
        "audit_test_sha256": support.file_digest(root / AUDIT_TEST),
        "verified_unique_receipts": len(audited),
        "verified_logical_views": len(plan),
        "replayed_provider_replies": sum(r["provider_reply_replayed"] for r in audited.values()),
        "retained_transport_unknowns": sum(
            r["transport_unknown_retained"] for r in audited.values()
        ),
        "unique_status_counts": dict(Counter(r["status"] for r in audited.values())),
        "unique_error_counts": dict(
            Counter(r["error_code"] for r in audited.values() if r["error_code"] is not None)
        ),
        "receipt_commitments_sha256": support.digest(
            [[key, audited[key]["private_receipt_sha256"]] for key in sorted(audited)]
        ),
        "elapsed_metadata_checked_for_consistency_not_remeasured": True,
        "post_freeze_quality_assurance": True,
        "experimental_labels_changed": False,
        "reply_copies_created": 0,
        "historical_private_corpus_accessed": False,
        "model_files_read": False,
        "network_calls": 0,
    }
    result["result_identity_sha256"] = support.digest(result)
    support.write_once(safe / "audit.safe.json", result)
    emit(
        "V4_COMPLETED_RECEIPT_REPLAY_AUDIT_PASS",
        verified_unique_receipts=len(audited),
        verified_logical_views=len(plan),
        unique_status_counts=result["unique_status_counts"],
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        audit(args.root.resolve(), args.config, args.config_sha256, execute=args.execute)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        emit(
            "V4_RECEIPT_AUDIT_STOPPED",
            error_type=type(exc).__name__,
            experimental_labels_changed=False,
            network_calls=0,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
