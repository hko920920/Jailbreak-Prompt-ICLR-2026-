"""Stage6-only logging wrapper around the unchanged, frozen v2 finalizer.

No model calls, scientific rule changes, analysis mode or automatic retry.
Existing valid direction is reused on explicit reentry within its original
window. Partial/conflicting frozen publications fail closed and are retained.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pa_reentry_finalize_v2 as finalizer
import pa_reentry_journal_v2 as j
import pa_reentry_v2 as entry

RUNTIME = "docs/PA_STAGE6_RUNTIME_2026-09-07_V2"


def execute(root, direction_ref):
    root = Path(root).resolve()
    frozen = entry.verify_frozen(root)
    directory = entry.owned(root, RUNTIME, existing=False)
    started = time.monotonic()
    attempt = uuid.uuid4().hex
    script_sha = j.sha_bytes(Path(__file__).read_bytes())

    def event(name, **fields):
        record = j.seal(j.safe({
            "schema_version": "pa-stage6-wrapper-event-v2",
            "execution_identity": frozen["execution_identity"],
            "attempt_id": attempt,
            "event": name,
            "at": j.utc(),
            "elapsed_seconds": time.monotonic() - started,
            "pid": os.getpid(),
            "wrapper_sha256": script_sha,
            "stage": 6,
            "run_analysis": False,
            "new_model_calls": 0,
            **fields,
        }))
        j.atomic_json(directory / "events" / f"{uuid.uuid4().hex}.safe.json", record)
        print(j.canonical(record).decode(), flush=True)

    with j.run_lock(directory / "run.lock"):
        direction_path = directory / "direction.safe.json"
        j.reject_links(direction_path)
        if direction_path.exists():
            direction = j.read_json(direction_path)
            j.require(direction_path.read_bytes() == j.canonical(direction) + b"\n",
                      "STAGE6_DIRECTION_FILE_NOT_CANONICAL")
            j.require(direction["direction_ref"] == direction_ref,
                      "STAGE6_EXISTING_DIRECTION_REFERENCE_CHANGED")
            finalizer.validate_direction(
                direction, frozen["execution_identity"], run_analysis=False
            )
        else:
            now = datetime.now(timezone.utc)
            direction = finalizer.make_direction(
                frozen["execution_identity"], 6,
                issued_at=now.isoformat(),
                expires_at=(now + timedelta(hours=2)).isoformat(),
                direction_ref=direction_ref,
            )
            j.atomic_json(direction_path, direction)
        event("STAGE6_STARTED", direction=direction,
              disk_free_bytes=shutil.disk_usage(root).free)
        try:
            event("FROZEN_CONTEXT_LOAD_STARTED")
            loaded, target = entry.load_context(root)
            j.require(loaded == frozen, "STAGE6_FROZEN_CONTEXT_CHANGED")
            event("FROZEN_CONTEXT_VERIFIED")
            payloads = entry.payloads(target)
            event("MEASUREMENTS_FINALIZATION_STARTED")
            verification = finalizer.finalize(
                target, payloads, direction=direction, run_analysis=False
            )
            output = target.safe.parent / "finalization" / "measurements-only"
            products = {
                key: None if key == "analysis" else j.read_json(output / name)
                for key, name in finalizer.OUTPUTS.items()
            }
            finalizer.validate_products(products)
            j.require(products["verification"] == verification
                      and (output / finalizer.OUTPUTS["verification"]).read_bytes()
                      == j.canonical(verification) + b"\n"
                      and verification["analysis_complete"] is False
                      and not (output / finalizer.OUTPUTS["analysis"]).exists(),
                      "STAGE6_PUBLICATION_OR_STAGE_BOUNDARY_CHANGED")
            for key, expected in verification["product_file_sha256"].items():
                j.require(j.sha_bytes((output / finalizer.OUTPUTS[key]).read_bytes())
                          == expected, "STAGE6_PUBLISHED_FILE_HASH_CHANGED")
            entry.verify_frozen(root, frozen)
            event("STAGE6_COMPLETE", verification_identity_sha256=
                  verification["verification_identity_sha256"],
                  result_identity_sha256=products["result"]["result_identity_sha256"],
                  disk_free_bytes=shutil.disk_usage(root).free,
                  automatic_next_stage=False, paper_validity=False)
            return verification
        except BaseException as error:
            message = str(error)
            code = message if re.fullmatch(r"[A-Z][A-Z0-9_]{0,191}", message) else None
            try:
                event("STAGE6_INTERRUPTED", error_type=type(error).__name__,
                      error_code=code, error_message_sha256=j.sha_bytes(message.encode()),
                      automatic_retry=False, evidence_preserved=True)
            except BaseException:
                # Logging failure must not expose unsanitized exception context.
                pass
            raise RuntimeError(code or "STAGE6_FAILURE_DETAILS_HASHED") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--direction-ref", required=True)
    args = parser.parse_args(argv)
    execute(args.root, args.direction_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
