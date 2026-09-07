"""Read-only compact SAFE monitor. Never dispatch authority or raw-data reader."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

IDENTITY = "1f720cab7e9678278e52542cf0ee33e791d9b2e331c4a2b7cb1b25f64e980ab2"


def native(path):
    value = str(path.absolute())
    return Path("\\\\?\\" + value) if os.name == "nt" and not value.startswith("\\\\?\\") else path


def snapshot(root, stage="target"):
    if stage not in ("target", "qwen", "jailmeter"):
        raise ValueError("unsupported SAFE monitor stage")
    execution = root / "data/natural_language_localization/pa_reentry_v2" / IDENTITY
    base = native(execution / "target" if stage == "target" else execution / "panel" / stage)
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "non_authoritative_safe_monitor": True,
        "execution_identity": IDENTITY,
        "stage": stage,
        "safe_namespace_exists": base.exists(),
        "disk_free_bytes": shutil.disk_usage(root).free,
    }
    journal_base = base if stage == "target" else base / "journal"
    requests = journal_base / "requests"
    for key, filename in (
        ("intent_files", "intent.safe.json"),
        ("row_files", "row.safe.json"),
        ("completion_files", "complete.safe.json"),
        ("skip_files", "skip.safe.json"),
    ):
        result[key] = len(list(requests.glob("*/" + filename))) if requests.exists() else 0
    result["pending_safe_request_files"] = (
        len(list(requests.glob("*/*.pending"))) if requests.exists() else 0
    )
    result["observed_accounted_files"] = result["completion_files"] + result["skip_files"]
    events = journal_base / "events"
    files = sorted(events.glob("*.safe.json"), reverse=True) if events.exists() else []
    result["event_files"] = len(files)
    observed = []
    for path in files[:64]:
        try:
            value = json.loads(path.read_bytes())
        except (OSError, ValueError):
            result["tail_read_incomplete"] = True
            continue
        if len(observed) < 4:
            observed.append(
                {
                    key: value[key]
                    for key in ("event", "recorded_at", "error_code", "ordinal")
                    if key in value
                }
            )
        if value.get("event") == "PROGRESS" and "last_progress" not in result:
            allowed = (
                "recorded_at",
                "completed",
                "unissued",
                "ambiguous",
                "repair_required",
                "historical_complete",
                "science_unknown_records",
                "control_unknown_records",
                "last_verified_ordinal",
                "last_verified_request",
                "elapsed_seconds",
                "latest_resource_snapshot",
                "planned",
                "total",
                "unknown_count",
                "unknown_is_not_success",
                "resource",
                "epoch",
                "recovery_only",
                "error_code",
            )
            result["last_progress"] = {key: value[key] for key in allowed if key in value}
    result["event_tail"] = observed
    proofs = (
        [base / "complete.safe.json"]
        if stage == "target" and (base / "complete.safe.json").exists()
        else sorted((base / "proofs").glob("*.safe.json"))
        if stage != "target"
        else []
    )
    result["stage_proof_exists"] = bool(proofs)
    result["stage_proof_files"] = len(proofs)
    if len(proofs) == 1:
        proof = proofs[0]
        try:
            value = json.loads(proof.read_bytes())
        except (OSError, ValueError):
            result["proof_read_incomplete"] = True
            return result
        result["stage_proof_summary"] = {
            key: value[key]
            for key in (
                "target_records",
                "reused_target_records",
                "new_target_records",
                "composite_target_complete",
                "proof_identity_sha256",
                "missing_stop_epochs",
                "failed_prelaunch_attempts",
                "stage",
                "planned_records",
                "dispatched",
                "skipped",
                "complete",
                "controls_judged",
                "scientific_gate_evaluated",
            )
            if key in value
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", choices=("target", "qwen", "jailmeter"), default="target")
    args = parser.parse_args()
    print(json.dumps(snapshot(args.root.resolve(), args.stage), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
