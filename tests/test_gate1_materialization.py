from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from jbspan.gate1.materialize import materialize_gate1_step2
from jbspan.gate1.models import ContractValidationError
from jbspan.gate1.registry import load_gate1_registry


def _write_source(path: Path) -> tuple[str, ...]:
    goals: list[str] = []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("Index", "Goal", "Target", "Behavior", "Category", "Source"))
        for category_index in range(10):
            for item_index in range(10):
                index = category_index * 10 + item_index
                goal = f"Synthetic request {index}"
                goals.append(goal)
                writer.writerow(
                    (
                        index,
                        goal,
                        f"Synthetic target {index}",
                        f"Behavior {index}",
                        f"Category {category_index}",
                        "Synthetic",
                    )
                )
    return tuple(goals)


def test_materialization_is_deterministic_and_safe(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_gate1_registry(root)
    source = tmp_path / "harmful-behaviors.csv"
    goals = _write_source(source)
    revision = registry.payload_source.revision + "0" * (
        40 - len(registry.payload_source.revision)
    )
    safe_a = tmp_path / "safe-a"
    safe_b = tmp_path / "safe-b"
    manifest_a = materialize_gate1_step2(
        root,
        registry,
        source_csv=source,
        resolved_revision=revision,
        safe_output_dir=safe_a,
        private_output_dir=tmp_path / "private-a",
    )
    manifest_b = materialize_gate1_step2(
        root,
        registry,
        source_csv=source,
        resolved_revision=revision,
        safe_output_dir=safe_b,
        private_output_dir=tmp_path / "private-b",
    )
    assert manifest_a["selection_sha256"] == manifest_b["selection_sha256"]
    assert manifest_a["rendered_attack_count"] == 250
    payload_registry = json.loads(
        (safe_a / "payload_registry.safe.json").read_text(encoding="utf-8")
    )
    assert payload_registry["development_count"] == 50
    assert payload_registry["heldout_count"] == 10
    public_text = "\n".join(
        path.read_text(encoding="utf-8") for path in safe_a.iterdir()
    )
    for goal in goals:
        assert goal not in public_text


def test_materialization_rejects_revision_mismatch(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_gate1_registry(root)
    source = tmp_path / "harmful-behaviors.csv"
    _write_source(source)
    with pytest.raises(ContractValidationError, match="revision"):
        materialize_gate1_step2(
            root,
            registry,
            source_csv=source,
            resolved_revision="0" * 40,
            safe_output_dir=tmp_path / "safe",
            private_output_dir=tmp_path / "private",
        )


def test_materialization_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_gate1_registry(root)
    source = tmp_path / "harmful-behaviors.csv"
    _write_source(source)
    revision = registry.payload_source.revision + "0" * (
        40 - len(registry.payload_source.revision)
    )
    with pytest.raises(ContractValidationError, match="SHA-256"):
        materialize_gate1_step2(
            root,
            registry,
            source_csv=source,
            resolved_revision=revision,
            safe_output_dir=tmp_path / "safe",
            private_output_dir=tmp_path / "private",
            expected_source_sha256="0" * 64,
        )
