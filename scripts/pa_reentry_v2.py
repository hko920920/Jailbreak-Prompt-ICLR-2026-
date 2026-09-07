"""Frozen preparation and stage-specific entry point; default is read-only.

prepare/preflight never infer. run-stage requires the actual later user direction,
creates a short-lived single-use receipt and runs exactly one named stage.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pa_reentry_journal_v2 as j

SCRIPT = "scripts/pa_reentry_v2.py"
CONFIG = "configs/natural_language_localization/pa_reentry_execution_v2.json"
PROTOCOL = "docs/PA_SECOND_CONTINUATION_PROTOCOL_2026-09-07_V2.md"
MANIFEST = "configs/natural_language_localization/pa_reentry_archive_manifest_v2.json"
ORIGINAL = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
CODE = [
    SCRIPT,
    "scripts/pa_reentry_journal_v2.py",
    "scripts/pa_reentry_evidence_v2.py",
    "scripts/pa_reentry_target_v2.py",
    "scripts/pa_reentry_panel_v2.py",
    "scripts/pa_reentry_finalize_v2.py",
]
TESTS = [
    "tests/test_pa_reentry_v2.py",
    "tests/test_pa_reentry_journal_v2.py",
    "tests/test_pa_reentry_evidence_v2.py",
    "tests/test_pa_reentry_target_v2.py",
    "tests/test_pa_reentry_panel_v2.py",
    "tests/test_pa_reentry_finalize_v2.py",
    "tests/test_pa_reentry_integration_v2.py",
]


def owned(root, relative, *, existing=True):
    j.require(
        isinstance(relative, str) and "\\" not in relative and ":" not in relative,
        "REENTRY_PATH_NOT_CANONICAL",
    )
    parts = relative.split("/")
    j.require(
        all(part and part not in {".", ".."} and part == part.rstrip(" .") for part in parts),
        "REENTRY_PATH_ESCAPE",
    )
    result = Path(root).resolve()
    for part in parts:
        result /= part
        native = (
            Path("\\\\?\\" + str(result))
            if os.name == "nt" and not str(result).startswith("\\\\?\\")
            else result
        )
        if native.exists() or native.is_symlink():
            observed = native.lstat()
            j.require(
                not stat.S_ISLNK(observed.st_mode)
                and not (getattr(observed, "st_file_attributes", 0) & 1024),
                "REENTRY_LINK_OR_REPARSE_POINT",
            )
        elif existing:
            raise ValueError("REENTRY_REQUIRED_PATH_MISSING")
    return native


def pin(root, relative):
    path = owned(root, relative)
    before = path.stat()
    j.require(path.is_file() and before.st_size <= 32_000_000, "REENTRY_PIN_FILE_INVALID")
    raw = path.read_bytes()
    after = path.stat()
    j.require(
        (before.st_size, before.st_mtime_ns, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_ino),
        "REENTRY_PIN_CHANGED_DURING_READ",
    )
    return {"path": relative, "size_bytes": len(raw), "sha256": j.sha_bytes(raw)}


def _template(root, prepared_at):
    return {
        "schema_version": "pa-reentry-frozen-preparation-v2",
        "prepared_at": prepared_at,
        "frozen": True,
        "execution_authorized": False,
        "stage2_only": True,
        "original_contract_sha256": ORIGINAL,
        "bound_plan_identity_sha256": PLAN,
        "archive_manifest": pin(root, MANIFEST),
        "protocol": pin(root, PROTOCOL),
        "code": [pin(root, path) for path in CODE],
        "tests": [pin(root, path) for path in TESTS],
        "target_total": 1470,
        "target_reused": 1082,
        "target_missing": 388,
        "target_missing_science": 220,
        "target_missing_controls": 168,
        "target_logical_chunks": [[1083, 1292], [1293, 1470]],
        "science_rows_per_axis": 882,
        "separate_stage_max_admission_hours": j.STAGE_HOURS,
        "automatic_next_stage": False,
        "automatic_ambiguous_retry": False,
        "scientific_rules_changed": False,
        "old_operational_failures_preserved": True,
        "archive_relocation_history_reconstructed": False,
        "paper_validity": False,
    }


def prepare(root):
    import pa_reentry_evidence_v2 as evidence

    manifest = j.read_json(owned(root, MANIFEST))
    evidence.verify_manifest(root, manifest)
    value = j.seal(_template(root, j.utc()), "execution_identity")
    j.atomic_json(owned(root, CONFIG, existing=False), value)
    return {
        "prepared": True,
        "execution_identity": value["execution_identity"],
        "config": pin(root, CONFIG),
        "execution_authorized": False,
        "new_model_calls": 0,
    }


def verify_frozen(root, expected=None):
    value = j.read_json(owned(root, CONFIG))
    j.verify_seal(value, "execution_identity")
    j.stamp(value["prepared_at"])
    j.require(
        value == j.seal(_template(root, value["prepared_at"]), "execution_identity"),
        "REENTRY_FROZEN_PIN_OR_POLICY_CHANGED",
    )
    if expected is not None:
        j.require(value == expected, "REENTRY_FROZEN_CONTEXT_CHANGED")
    return value


def verify_target_assets(root, config):
    """Rehash target weights/binaries before launch, not a second history replay."""
    import pa_llama_development_common_v1 as common

    pins = [*config["model"]["files"], *config["runtime"]["files"], config["runtime"]["server"]]
    for value in pins:
        path = owned(root, value["path"])
        before = path.stat()
        common.verify_pin(root, value, ("artifacts/",))
        after = path.stat()
        j.require(
            (before.st_size, before.st_mtime_ns, before.st_ino)
            == (after.st_size, after.st_mtime_ns, after.st_ino),
            "REENTRY_TARGET_ASSET_CHANGED_DURING_VERIFY",
        )
    return len(pins)


def verify_output_tree(root, relative):
    base = owned(root, relative, existing=False)
    if not base.exists():
        return
    # Only the exact NEW execution namespace; no traversal of private old cohorts.
    stack = [base]
    while stack:
        current = stack.pop()
        j.reject_links(current)
        if current.is_dir():
            stack.extend(current.iterdir())
        else:
            j.require(current.is_file(), "REENTRY_OUTPUT_NOT_REGULAR")


def load_context(root):
    """Authenticate old raw evidence and new pins; no tokenizer/model inference."""
    frozen = verify_frozen(root)
    import pa_reentry_evidence_v2 as evidence
    from pa_reentry_target_v2 import TargetContinuation

    history = evidence.load_history(root)
    manifest = j.read_json(owned(root, MANIFEST))
    target = TargetContinuation(history, manifest, execution_identity=frozen["execution_identity"])

    def launch_verifier():
        verify_frozen(root, frozen)
        evidence.verify_manifest(root, manifest)
        verify_target_assets(root, target.config)
        # Check all output ancestors, including Windows junctions, before writes.
        verify_output_tree(
            root,
            f"data/natural_language_localization/pa_reentry_v2/{target.execution_identity}",
        )
        verify_output_tree(root, f"artifacts/pa_reentry_v2/private/{target.execution_identity}")

    target._launch_verifier = launch_verifier
    target.launch_ready = True  # Infrastructure verified, not stage authorization.
    return frozen, target


def payloads(target):
    """Use the already verified, approved NEW materialization context only."""
    result = target.historical.payloads_by_position()
    expected = {row["payload_position"]: row["payload_sha256"] for row in target.plan["population"]}
    j.require(set(result) == set(expected), "REENTRY_PAYLOAD_POPULATION_CHANGED")
    for position, value in result.items():
        j.require(
            isinstance(value, str) and j.sha_bytes(value.encode("utf-8")) == expected[position],
            "REENTRY_ORIGINAL_PAYLOAD_BYTES_CHANGED",
        )
    return result


def preflight(root):
    started_at, began = j.utc(), time.monotonic()
    frozen, target = load_context(root)
    states = target.states(require_released=True)
    counts = {
        kind: sum(state["state"] == kind for state in states)
        for kind in ("COMPLETE", "UNISSUED", "AMBIGUOUS")
    }
    verify_frozen(root, frozen)
    return {
        "schema_version": "pa-reentry-static-preflight-v2",
        "execution_identity": frozen["execution_identity"],
        "started_at": started_at,
        "finished_at": j.utc(),
        "elapsed_seconds": time.monotonic() - began,
        "historical_targets_verified": len(target.historical_rows),
        "new_target_state_counts": counts,
        "repair_required": sum(bool(state["repair_required"]) for state in states),
        "events": target.journal.audit_events(),
        "disk_free_bytes": shutil.disk_usage(root).free,
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "new_model_calls": 0,
        "current_stage_launch_authorized": False,
        "paper_validity": False,
    }


def run_stage(root, stage, direction_ref, *, mode="run", epoch=None):
    j.require(
        stage in j.STAGE_HOURS and isinstance(direction_ref, str) and bool(direction_ref.strip()),
        "REENTRY_CURRENT_STAGE_DIRECTION_REQUIRED",
    )
    j.require(
        mode in {"run", "recover", "review"} and (epoch is not None) == (mode == "review"),
        "REENTRY_STAGE_ACTION_OR_EPOCH_INVALID",
    )
    _, target = load_context(root)
    now = datetime.now(timezone.utc)
    auth = j.make_authorization(
        target.execution_identity,
        stage,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=j.STAGE_HOURS[stage])).isoformat(),
        direction_ref=direction_ref,
    )
    if stage == "target":
        if mode == "review":
            return target.review_interrupted_epoch(epoch, auth)
        if mode == "recover":
            target.assert_launch_ready()
            with j.run_lock(target.safe / "run.lock"):
                j.validate_authorization(auth, target.execution_identity, "target")
                states = target.states(recover=True, require_released=True)
                target.journal.event(
                    "EXPLICIT_RECOVERY_REVIEW", authorization=auth, automatic_dispatch=False
                )
            return {
                "stage": stage,
                "completed": sum(state["state"] == "COMPLETE" for state in states),
                "ambiguous": sum(state["state"] == "AMBIGUOUS" for state in states),
                "new_model_calls": 0,
            }
        return target.run(auth)
    from pa_reentry_panel_v2 import ReentryPanel

    evaluator = ReentryPanel(
        target,
        payloads(target),
        target.safe.parent,
        target.private.parent,
        target.execution_identity,
    )
    if mode == "review":
        j.require(
            isinstance(epoch, str) and epoch.isdecimal(), "REENTRY_PANEL_EPOCH_INTEGER_REQUIRED"
        )
        return evaluator.review_interruption(stage, int(epoch), auth)
    if mode == "recover":
        evaluator.recover(stage, auth)
        return evaluator.inspect(stage)
    # This only completes already verified durable-response publications; it
    # cannot fabricate a stop, waive missing resources or replay ambiguous calls.
    evaluator.recover(stage, auth)
    return evaluator.run(stage, auth)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=(
            "prepare",
            "verify-freeze",
            "preflight",
            "run-stage",
            "recover-stage",
            "review-stage",
        ),
        default="verify-freeze",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", choices=tuple(j.STAGE_HOURS))
    parser.add_argument("--direction-ref")
    parser.add_argument("--epoch")
    parser.add_argument("--report", type=str)
    args = parser.parse_args(argv)
    if args.report is not None:
        j.require(
            args.command == "preflight"
            and args.report.startswith("docs/PA_STAGE2_PREFLIGHT_")
            and args.report.endswith(".safe.json"),
            "REENTRY_REPORT_SCOPE_INVALID",
        )
        owned(args.root, args.report, existing=False)
    stage_commands = {"run-stage": "run", "recover-stage": "recover", "review-stage": "review"}
    if args.command not in stage_commands:
        j.require(
            args.stage is None and args.direction_ref is None and args.epoch is None,
            "REENTRY_LAUNCH_FLAGS_ON_READ_ONLY_COMMAND",
        )
    if args.command == "prepare":
        result = prepare(args.root)
    elif args.command == "preflight":
        result = preflight(args.root)
    elif args.command in stage_commands:
        result = run_stage(
            args.root,
            args.stage,
            args.direction_ref,
            mode=stage_commands[args.command],
            epoch=args.epoch,
        )
    else:
        value = verify_frozen(args.root)
        result = {
            "execution_identity": value["execution_identity"],
            "frozen_pins_verified": True,
            "current_stage_launch_authorized": False,
            "new_model_calls": 0,
        }
    if args.report is not None:
        j.atomic_json(owned(args.root, args.report, existing=False), j.safe(result))
    print(j.canonical(j.safe(result)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
