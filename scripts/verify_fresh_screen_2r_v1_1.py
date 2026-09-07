from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import scripts.verify_fresh_screen_2r as parent

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/natural_language_localization/fresh_screen_2r_v1.json"),
    )
    value.add_argument(
        "--amendment",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "fresh_screen_2r_verifier_v1_1_amendment.json"
        ),
    )
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def rooted(root: Path, value: object, *, where: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a nonempty relative path")
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{where} escapes the repository root")
    return path


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def safe_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def verify_dependencies(
    root: Path, amendment: Mapping[str, Any]
) -> dict[str, Path]:
    dependencies = required_mapping(amendment["dependencies"], where="dependencies")
    paths: dict[str, Path] = {}
    for name, raw_spec in dependencies.items():
        spec = required_mapping(raw_spec, where=f"dependencies.{name}")
        path = rooted(root, spec["path"], where=f"dependencies.{name}.path")
        if file_sha256(path) != spec["sha256"]:
            raise ValueError(f"V1.1 dependency hash mismatch: {name}")
        paths[str(name)] = path
    return paths


def sorted_active_pairs(previous: Sequence[Mapping[str, Any]] | None) -> JsonRows:
    if previous is None:
        raise ValueError("later seed requires previous pairs")
    return sorted(
        (dict(row) for row in previous if row["status"] == "ADVANCE"),
        key=lambda row: (int(row["payload_position"]), str(row["attack_family"])),
    )


def verify(root: Path, config_path: Path, amendment_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    amendment_path = (
        amendment_path if amendment_path.is_absolute() else root / amendment_path
    )
    config_path = config_path.resolve()
    amendment_path = amendment_path.resolve()
    amendment = load_object(amendment_path)
    if (
        amendment.get("schema_version")
        != "jbspan-fresh-screen-2r-verifier-v1-1-amendment"
        or amendment.get("status")
        != "FROZEN_POST_OUTCOME_ORDERING_ONLY_VERIFIER_REPAIR"
        or amendment.get("frozen") is not True
    ):
        raise ValueError("unsupported V1.1 ordering-only amendment")
    dependencies = verify_dependencies(root, amendment)
    if dependencies["contract"] != config_path:
        raise ValueError("V1.1 amendment points to another 2R contract")
    if dependencies["v1_1_verifier"] != Path(__file__).resolve():
        raise ValueError("V1.1 verifier self identity mismatch")
    audit = required_mapping(amendment["observed_failure_audit"], where="failure audit")
    if not all(
        audit.get(key) is True
        for key in (
            "seed_11_order_and_content_exact",
            "seed_23_pair_id_sets_exact",
            "seed_23_content_by_pair_id_exact",
            "seed_47_pair_id_sets_exact",
            "seed_47_content_by_pair_id_exact",
            "labels_metrics_routing_or_selection_changed",
        )
        if key != "labels_metrics_routing_or_selection_changed"
    ):
        raise ValueError("V1.1 failure audit lacks required exactness facts")
    if audit.get("labels_metrics_routing_or_selection_changed") is not False:
        raise ValueError("V1.1 amendment is not ordering-only")

    captured: list[tuple[Path, Mapping[str, Any]]] = []
    original_active = parent.active_pairs
    original_write = parent.safe_write

    def capture(path: Path, value: Mapping[str, Any]) -> None:
        captured.append((path, dict(value)))

    parent.active_pairs = sorted_active_pairs
    parent.safe_write = capture
    try:
        base = parent.verify(root, config_path)
    finally:
        parent.active_pairs = original_active
        parent.safe_write = original_write
    if len(captured) != 1:
        raise ValueError("V1.1 parent reconstruction did not yield one verification artifact")
    if base.get("status") != "FRESH_SCREEN_2R_INDEPENDENT_RECONSTRUCTION_PASS":
        raise ValueError("V1.1 parent reconstruction did not pass")
    expected_capture = rooted(
        root,
        amendment["recording"]["parent_capture_target_path"],
        where="parent capture target",
    )
    if captured[0][0].resolve() != expected_capture:
        raise ValueError("V1.1 intercepted an unexpected parent write target")

    parent_identity = base.pop("verification_identity_sha256")
    base.pop("schema_version")
    base.pop("status")
    result: JsonObject = {
        "schema_version": "jbspan-fresh-screen-2r-independent-verification-v1-1",
        "status": "FRESH_SCREEN_2R_INDEPENDENT_RECONSTRUCTION_V1_1_PASS",
        "evidence_class": "SAFE_ARTIFACT_RECONSTRUCTION_NO_MODEL_INFERENCE",
        "amendment_sha256": file_sha256(amendment_path),
        "v1_parent_verifier_sha256": file_sha256(dependencies["v1_verifier"]),
        "v1_1_verifier_sha256": file_sha256(Path(__file__).resolve()),
        "v1_parent_logic_verification_identity_sha256": parent_identity,
        "repair_scope": "SORT_ACTIVE_PAIRS_BY_PAYLOAD_POSITION_THEN_ATTACK_FAMILY",
        "original_v1_failure": "SEQUENCE_COMPARISON_MISMATCH_AT_SEEDS_23_AND_47",
        "pair_id_sets_and_content_by_id_were_exact_before_repair": True,
        "scientific_labels_metrics_routing_or_selection_changed": False,
        **base,
    }
    expected_route = required_mapping(
        amendment["expected_immutable_result"], where="expected immutable result"
    )
    final_result = load_object(dependencies["final_result"])
    if (
        final_result.get("routing", {}).get("route") != expected_route["route"]
        or final_result.get("routing", {}).get("stable_pairs_by_family")
        != expected_route["stable_pairs_by_family"]
    ):
        raise ValueError("V1.1 immutable scientific result differs from amendment")
    result["verification_identity_sha256"] = canonical_sha256(result)
    output = rooted(
        root, amendment["recording"]["verification_path"], where="verification path"
    )
    safe_write(output, result)
    return result


def main() -> int:
    args = parser().parse_args()
    result = verify(args.root.resolve(), args.config, args.amendment)
    print(
        json.dumps(
            {
                "status": result["status"],
                "verified_phase_seeds": result["verified_phase_seeds"],
                "initial_pairs_reconstructed": result["initial_pairs_reconstructed"],
                "scientific_result_changed": result[
                    "scientific_labels_metrics_routing_or_selection_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
