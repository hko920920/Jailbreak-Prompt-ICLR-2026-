from __future__ import annotations

from pathlib import Path

import pytest

from scripts.resume_d3_generation_operational_v1 import (
    retryable_replace_error,
    retrying_atomic_write,
)


def test_retrying_atomic_write_survives_transient_destination_locks(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "checkpoint.safe.jsonl"
    destination.write_bytes(b"old\n")
    calls = 0
    sleeps: list[float] = []

    def replace(source: object, target: object) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            error = PermissionError("transient test lock")
            error.winerror = 5
            raise error
        Path(source).replace(Path(target))

    attempts = retrying_atomic_write(
        destination,
        b"new\n",
        replace=replace,
        sleep=sleeps.append,
    )

    assert attempts == 3
    assert sleeps == [0.1, 0.2]
    assert destination.read_bytes() == b"new\n"


def test_retrying_atomic_write_does_not_retry_unrelated_errors(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "checkpoint.safe.jsonl"
    sleeps: list[float] = []

    def replace(_source: object, _target: object) -> None:
        raise OSError("non-retryable test error")

    with pytest.raises(OSError, match="non-retryable"):
        retrying_atomic_write(
            destination,
            b"new\n",
            replace=replace,
            sleep=sleeps.append,
        )

    assert sleeps == []
    assert retryable_replace_error(OSError("ordinary")) is False
    assert list(tmp_path.glob(".*.tmp"))
