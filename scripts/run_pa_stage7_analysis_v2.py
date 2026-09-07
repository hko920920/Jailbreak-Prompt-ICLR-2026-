"""Stage7-only durable wrapper; unchanged frozen analysis, no inference/Stage8.

Prior Stage6 bytes are pinned and preserved. Explicit reentry may reuse the
same still-valid direction without extending it; publication conflicts remain.
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

RUNTIME = "docs/PA_STAGE7_RUNTIME_2026-09-07_V2"
STAGE6_PINS = {
    "measurements.safe.json": "b9ce483fbb633d5bd533190f1d7b2324c45caedd16ed3e83f69d324fbdb41ac1",
    "result.safe.json": "b427c21a70700d7ad0995df48b7d79a378e374d629ff8f1b0716c204b747eda3",
    "verification.safe.json": "c4f91f03091b5a9675de8594e275a92ee786c5fec41cb875a2d7ecf68086cf1f",
}


def snapshot_stage6(root, execution_identity):
    directory = entry.owned(root, "data/natural_language_localization/pa_reentry_v2/"
                            f"{execution_identity}/finalization/measurements-only")
    j.require({p.name for p in directory.iterdir()} == set(STAGE6_PINS) | {"publication.lock"},
              "STAGE7_STAGE6_UNEXPECTED_FILE")
    for name in (*STAGE6_PINS, "publication.lock"):
        j.reject_links(directory / name)
    actual = {name: j.sha_bytes((directory / name).read_bytes()) for name in STAGE6_PINS}
    j.require(actual == STAGE6_PINS, "STAGE7_STAGE6_FILE_CHANGED")
    products = {key: None if key == "analysis" else j.read_json(directory / name)
                for key, name in finalizer.OUTPUTS.items()}
    finalizer.validate_products(products)
    j.require(products["verification"]["actual_raw_verification_by_entrypoint"] is True,
              "STAGE7_STAGE6_RAW_REPLAY_PROOF_REQUIRED")
    return actual


def execute(root, direction_ref):
    root = Path(root).resolve()
    frozen = entry.verify_frozen(root)
    directory = entry.owned(root, RUNTIME, existing=False)
    started, attempt = time.monotonic(), uuid.uuid4().hex
    script_sha = j.sha_bytes(Path(__file__).read_bytes())

    def event(name, **fields):
        record = j.seal(j.safe({
            "schema_version": "pa-stage7-wrapper-event-v2",
            "execution_identity": frozen["execution_identity"],
            "attempt_id": attempt, "event": name, "at": j.utc(),
            "elapsed_seconds": time.monotonic() - started,
            "pid": os.getpid(), "wrapper_sha256": script_sha,
            "stage": 7, "run_analysis": True, "new_model_calls": 0, **fields,
        }))
        j.atomic_json(directory / "events" / f"{uuid.uuid4().hex}.safe.json", record)
        print(j.canonical(record).decode(), flush=True)

    with j.run_lock(directory / "run.lock"):
        direction_path = directory / "direction.safe.json"
        j.reject_links(direction_path)
        if direction_path.exists():
            direction = j.read_json(direction_path)
            j.require(direction_path.read_bytes() == j.canonical(direction) + b"\n",
                      "STAGE7_DIRECTION_FILE_NOT_CANONICAL")
            j.require(direction["direction_ref"] == direction_ref,
                      "STAGE7_EXISTING_DIRECTION_REFERENCE_CHANGED")
            finalizer.validate_direction(direction, frozen["execution_identity"], run_analysis=True)
        else:
            now = datetime.now(timezone.utc)
            direction = finalizer.make_direction(
                frozen["execution_identity"], 7, issued_at=now.isoformat(),
                expires_at=(now + timedelta(hours=2)).isoformat(), direction_ref=direction_ref,
            )
            j.atomic_json(direction_path, direction)
        event("STAGE7_STARTED", direction=direction,
              disk_free_bytes=shutil.disk_usage(root).free)
        try:
            prior = snapshot_stage6(root, frozen["execution_identity"])
            event("STAGE6_INPUTS_VERIFIED", stage6_file_sha256=prior)
            event("FROZEN_CONTEXT_LOAD_STARTED")
            loaded, target = entry.load_context(root)
            j.require(loaded == frozen, "STAGE7_FROZEN_CONTEXT_CHANGED")
            event("FROZEN_CONTEXT_VERIFIED")
            payloads = entry.payloads(target)
            event("ANALYSIS_FINALIZATION_STARTED")
            verification = finalizer.finalize(
                target, payloads, direction=direction, run_analysis=True
            )
            output = target.safe.parent / "finalization" / "with-analysis"
            for name in (*finalizer.OUTPUTS.values(), "publication.lock"):
                j.reject_links(output / name)
            products = {key: j.read_json(output / name) for key, name in finalizer.OUTPUTS.items()}
            finalizer.validate_products(products)
            j.require(products["verification"] == verification
                      and verification["analysis_complete"] is True
                      and products["analysis"] is not None,
                      "STAGE7_PUBLICATION_OR_STAGE_BOUNDARY_CHANGED")
            for key, value in products.items():
                saved = (output / finalizer.OUTPUTS[key]).read_bytes()
                j.require(saved == j.canonical(value) + b"\n", "STAGE7_NONCANONICAL_PRODUCT")
                if key != "verification":
                    j.require(j.sha_bytes(saved) == verification["product_file_sha256"][key],
                              "STAGE7_PUBLISHED_FILE_HASH_CHANGED")
            j.require(j.sha_bytes((output / "measurements.safe.json").read_bytes())
                      == prior["measurements.safe.json"], "STAGE7_MEASUREMENTS_CHANGED")
            j.require(snapshot_stage6(root, frozen["execution_identity"]) == prior,
                      "STAGE7_PRIOR_PRODUCTS_CHANGED")
            entry.verify_frozen(root, frozen)
            event("STAGE7_FROZEN_ANALYSIS_COMPLETE",
                  verification_identity_sha256=verification["verification_identity_sha256"],
                  result_identity_sha256=products["result"]["result_identity_sha256"],
                  analysis_identity_sha256=products["analysis"]["result_identity_sha256"],
                  disk_free_bytes=shutil.disk_usage(root).free,
                  stage6_preserved=True, automatic_next_stage=False, paper_validity=False)
            return verification
        except BaseException as error:
            message = str(error)
            code = message if re.fullmatch(r"[A-Z][A-Z0-9_]{0,191}", message) else None
            try:
                event("STAGE7_INTERRUPTED", error_type=type(error).__name__, error_code=code,
                      error_message_sha256=j.sha_bytes(message.encode()),
                      automatic_retry=False, evidence_preserved=True)
            except BaseException:
                pass
            raise RuntimeError(code or "STAGE7_FAILURE_DETAILS_HASHED") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--direction-ref", required=True)
    args = parser.parse_args(argv)
    execute(args.root, args.direction_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
