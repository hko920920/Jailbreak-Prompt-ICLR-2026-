"""Operationally resume frozen D3 target generation in bounded safe chunks.

This launcher does not change the frozen scientific runner, contract, prompts,
models, decoding parameters, plans, or result rules.  It only replaces the two
safe-artifact writers in memory with byte-identical atomic writers that retry
transient Windows destination locks.  Target progress is then intentionally
paused after a bounded number of newly committed records.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_d3_exact_topology as d3  # noqa: E402

JsonRows = Sequence[Mapping[str, Any]]
ReplaceFunction = Callable[[str | bytes | os.PathLike[str], str | bytes | os.PathLike[str]], None]
SleepFunction = Callable[[float], None]


class IntentionalCheckpointPause(RuntimeError):
    """Signal a successful bounded pause immediately after a durable checkpoint."""

    def __init__(self, committed_records: int) -> None:
        super().__init__(f"bounded pause after {committed_records} committed records")
        self.committed_records = committed_records


def retryable_replace_error(error: OSError) -> bool:
    """Return whether an atomic replace failed with a transient Windows lock."""

    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {
        5,
        32,
    }


def retrying_atomic_write(
    path: Path,
    payload: bytes,
    *,
    maximum_attempts: int = 12,
    initial_delay_seconds: float = 0.10,
    replace: ReplaceFunction = os.replace,
    sleep: SleepFunction = time.sleep,
) -> int:
    """Atomically write exact bytes, retrying only transient destination locks.

    The temporary file is deliberately preserved after terminal failure so the
    same recovery audit used for the original interruption remains possible.
    The return value is the number of replace attempts used.
    """

    if maximum_attempts < 1:
        raise ValueError("maximum_attempts must be positive")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds cannot be negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    for attempt in range(1, maximum_attempts + 1):
        try:
            replace(temporary, path)
            return attempt
        except OSError as error:
            if not retryable_replace_error(error) or attempt == maximum_attempts:
                raise
            delay = min(initial_delay_seconds * (2 ** (attempt - 1)), 1.0)
            sleep(delay)
    raise AssertionError("unreachable atomic-write retry state")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=ROOT)
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/natural_language_localization/d3_exact_topology_v1.json"),
    )
    value.add_argument("--seed", type=int, choices=d3.SEEDS, required=True)
    value.add_argument("--max-new-records", type=int, default=64)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.max_new_records < 1:
        raise SystemExit("--max-new-records must be positive")
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config

    # Retain every frozen scientific implementation byte.  Only the imported
    # module's storage functions are replaced for this process.
    d3.install_engine_patches()
    d3.d3_screen.patch_extractor(root)
    config_path, config, _verified = d3.load_config(root, config_path)
    phase = d3.engine.phase_paths(root, config, args.seed)
    plans = d3.engine.load_jsonl(phase["plan"])
    expected_records = len(plans)
    progress_name = phase["generation_progress"].name
    checkpoint_writes = 0
    replace_retries = 0

    def safe_write(path: Path, value: Mapping[str, Any]) -> None:
        nonlocal replace_retries
        payload = (
            json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        attempts = retrying_atomic_write(path, payload)
        replace_retries += attempts - 1

    def safe_write_jsonl(path: Path, rows: JsonRows) -> None:
        nonlocal checkpoint_writes, replace_retries
        attempts = retrying_atomic_write(path, d3.engine.encode_jsonl(rows))
        replace_retries += attempts - 1
        if path.name != progress_name:
            return
        checkpoint_writes += 1
        if checkpoint_writes >= args.max_new_records and len(rows) < expected_records:
            raise IntentionalCheckpointPause(len(rows))

    d3.engine.safe_write = safe_write
    d3.engine.safe_write_jsonl = safe_write_jsonl
    before = (
        len(d3.engine.load_jsonl(phase["generation_progress"]))
        if phase["generation_progress"].is_file()
        else 0
    )
    try:
        result = d3.engine.generate(root, config_path, args.seed)
        status = "D3_GENERATION_COMPLETE"
    except IntentionalCheckpointPause as pause:
        result = {"record_count": pause.committed_records}
        status = "D3_GENERATION_BOUNDED_PAUSE"

    finalized = phase["generation"].is_file()
    progress_path = phase["generation"] if finalized else phase["generation_progress"]
    rows = d3.engine.load_jsonl(progress_path)
    visible = {
        "status": status,
        "phase_seed": args.seed,
        "records_before": before,
        "records_after": len(rows),
        "new_records_committed": len(rows) - before,
        "expected_records": expected_records,
        "next_execution_order": None if finalized else len(rows),
        "replace_retries": replace_retries,
        "finalized": finalized,
        "checkpoint_sha256": d3.engine.file_sha256(progress_path),
        "runner_result_status": result.get("status"),
        "model_output_opened_by_launcher": False,
    }
    print(json.dumps(visible, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
