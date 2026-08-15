from __future__ import annotations

import json
from pathlib import Path

import pytest

from jbspan.dataio import DatasetValidationError, build_dataset_manifest, load_prompt_pairs


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_load_prompt_pairs_and_manifest(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    _write(
        path,
        [
            {
                "id": "x1",
                "behavior": "demo",
                "original_prompt": "original request",
                "jailbreak_prompt": "context. trigger. original request.",
                "attack_family": "toy",
                "metadata": {"source": "unit-test"},
            }
        ],
    )
    pairs = load_prompt_pairs(path)
    manifest = build_dataset_manifest(path, pairs)
    assert pairs[0].id == "x1"
    assert manifest.example_count == 1
    assert manifest.attack_family_counts == {"toy": 1}
    assert len(manifest.source_sha256) == 64


def test_duplicate_error_is_redacted(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    secret = "do-not-leak-this-prompt"
    row = {
        "id": "same",
        "behavior": "demo",
        "original_prompt": secret,
        "jailbreak_prompt": secret,
        "attack_family": "toy",
    }
    _write(path, [row, row])
    with pytest.raises(DatasetValidationError) as exc_info:
        load_prompt_pairs(path)
    assert "DUPLICATE_ID" in str(exc_info.value)
    assert secret not in str(exc_info.value)
