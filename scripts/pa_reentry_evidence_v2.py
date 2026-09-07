"""Pinned, read-only evidence bridge for a separately authorized second continuation.

No model/server operations occur on import, manifest preparation, or history
loading. Old artifacts and scientific verification rules are never rewritten.
The new operational freeze must independently pin the manifest's raw bytes.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

PARENT_SHA = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
AMENDMENT_SHA = "6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0"
PLAN_SHA = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
SCRIPT = "scripts/pa_reentry_evidence_v2.py"
MANIFEST = "configs/natural_language_localization/pa_reentry_archive_manifest_v2.json"
SCHEMA = "pa-reentry-archive-manifest-v2"
OLD_CONFIGS = {
    "configs/natural_language_localization/pa_llama_topology_execution_v1.json": PARENT_SHA,
    "configs/natural_language_localization/pa_llama_topology_target_continuation_v1.json": (
        AMENDMENT_SHA
    ),
}
SAFE_BASE = "data/natural_language_localization/pa_llama_topology_target_continuation_v1"
PRIVATE_BASE = "artifacts/pa_llama_topology_target_continuation_v1/private"
ORIGINAL_SAFE = "data/natural_language_localization/pa_llama_topology_v1"
ARCHIVE_ROOTS = {
    "safe": f"{SAFE_BASE}/{AMENDMENT_SHA}_run1_archived",
    "private": f"{PRIVATE_BASE}/{AMENDMENT_SHA}_run1_archived",
}
UNARCHIVED_ROOTS = {
    "safe": f"{SAFE_BASE}/{AMENDMENT_SHA}",
    "private": f"{PRIVATE_BASE}/{AMENDMENT_SHA}",
}
IDENTITIES = {
    "original_prefix_rows_identity_sha256": (
        "2d6c912215422b269fd9680d429cf5fa8f79c34dca39c47f1655ec03fbdf79bd"
    ),
    "archived_suffix_rows_identity_sha256": (
        "fe4640066a4c6ac29ef0fec3afdf515fca00423b8dec62f9521ac6c7b1ff9280"
    ),
    "combined_rows_identity_sha256": (
        "46e31aad957c4d75058444242603169d5c0313012d02ae493e8c642d2b1057dc"
    ),
    "remaining_plan_identity_sha256": (
        "ead9c678e451700ab9d82a2286cfcd0d98a6a977ba3fa0fbdf1a6d5d36222369"
    ),
    "remaining_request_ids_identity_sha256": (
        "7d7ddd7ff5bf8ef532db2c09e0e2ca6a9988a90495cf0a757d4fa283e63ece5a"
    ),
}
MAX_MANIFEST_BYTES = 16_000_000


class EvidenceError(ValueError):
    """Safe machine-readable error; never includes a response or prompt."""


def require(condition, code):
    if not condition:
        raise EvidenceError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def native(path):
    value = os.path.abspath(os.fspath(path))
    return (
        Path("\\\\?\\" + value)
        if os.name == "nt" and not value.startswith("\\\\?\\")
        else Path(value)
    )


def _root(root):
    value = os.fspath(root)
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value).resolve()


def checked_path(root, relative):
    """Exact canonical relative paths, no Windows aliases, links or reparse points."""
    require(isinstance(relative, str) and bool(relative), "EVIDENCE_PATH_REQUIRED")
    parts = relative.split("/")
    require(
        not any(x in relative for x in ("\\", ":", "\0"))
        and all(part not in {"", ".", ".."} and part.rstrip(" .") == part for part in parts)
        and not PurePosixPath(relative).is_absolute(),
        "EVIDENCE_PATH_ESCAPE_OR_ALIAS",
    )
    require(
        not any(x in relative.casefold() for x in ("primary_a60", "reserve_b60", "sealed_")),
        "EVIDENCE_SEALED_PATH",
    )
    if "/private/" in relative.casefold() or ".private." in relative.casefold():
        require(
            relative == ARCHIVE_ROOTS["private"]
            or relative.startswith(ARCHIVE_ROOTS["private"] + "/"),
            "EVIDENCE_PRIVATE_PATH_OUTSIDE_ARCHIVE",
        )
    cursor = _root(root)
    for part in parts:
        cursor = cursor / part
        try:
            observed = native(cursor).lstat()
        except FileNotFoundError:
            raise EvidenceError("EVIDENCE_FILE_MISSING") from None
        require(
            not stat.S_ISLNK(observed.st_mode)
            and not (
                getattr(observed, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            ),
            "EVIDENCE_LINK_OR_REPARSE_POINT",
        )
    return native(cursor)


def _relative(root, path):
    value = os.fspath(path)
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value).relative_to(_root(root)).as_posix()


def descriptor(root, relative):
    path = checked_path(root, relative)
    require(path.is_file(), "EVIDENCE_EXPECTED_FILE")
    before = path.stat()
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            hasher.update(block)
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_ino),
        "EVIDENCE_CHANGED_DURING_READ",
    )
    return {"path": relative, "size_bytes": before.st_size, "sha256": hasher.hexdigest()}


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "EVIDENCE_DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                EvidenceError("EVIDENCE_NONFINITE_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EvidenceError("EVIDENCE_INVALID_JSON") from None


def _read_small(root, relative):
    path = checked_path(root, relative)
    require(path.stat().st_size <= MAX_MANIFEST_BYTES, "EVIDENCE_JSON_TOO_LARGE")
    return _strict_json(path.read_bytes())


def _walk_descriptors(value):
    if isinstance(value, dict):
        if {"path", "size_bytes", "sha256"} <= set(value):
            yield {key: value[key] for key in ("path", "size_bytes", "sha256")}
        for nested in value.values():
            yield from _walk_descriptors(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_descriptors(nested)


def _dependency_pins(root):
    """Trusted old configuration hashes fix the required small dependency closure."""
    pins = {}
    for relative, expected_sha in OLD_CONFIGS.items():
        pin = descriptor(root, relative)
        require(pin["sha256"] == expected_sha, "EVIDENCE_OLD_CONFIG_CHANGED")
        pins[relative] = pin
        config = _read_small(root, relative)
        selected = [config["required_code"], config["protocol"]]
        selected += [config[key] for key in ("preparation", "prefix_manifest") if key in config]
        if "panel" in config:
            selected += [
                config["panel"]["pure_function_sources"],
                config["panel"]["runtime_contract"],
            ]
        for old_pin in _walk_descriptors(selected):
            name = old_pin["path"]
            require(name not in pins or pins[name] == old_pin, "EVIDENCE_CONFLICTING_OLD_PIN")
            require(descriptor(root, name) == old_pin, "EVIDENCE_OLD_DEPENDENCY_CHANGED")
            pins[name] = old_pin
    for relative in (
        f"{ORIGINAL_SAFE}/{PARENT_SHA}/generate-aborted.safe.json",
        f"{ORIGINAL_SAFE}/experiment-reservation.safe.json",
        f"{SAFE_BASE}/experiment-reservation.safe.json",
        SCRIPT,
    ):
        pins[relative] = descriptor(root, relative)
    return pins


def _archive_files(root, relative):
    base = checked_path(root, relative)
    require(base.is_dir(), "EVIDENCE_ARCHIVE_DIRECTORY_MISSING")
    result = []
    pending = [base]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            name = _relative(root, path)
            validated = checked_path(root, name)
            if validated.is_dir():
                pending.append(validated)
            else:
                require(validated.is_file(), "EVIDENCE_ARCHIVE_NONFILE")
                result.append(name)
    require(len({name.casefold() for name in result}) == len(result), "EVIDENCE_DUPLICATE_PATH")
    return sorted(result)


def _mapping():
    return {
        area: {"original": UNARCHIVED_ROOTS[area], "archived": ARCHIVE_ROOTS[area]}
        for area in ("safe", "private")
    }


def _base_manifest():
    return {
        "schema_version": SCHEMA,
        "original_contract_sha256": PARENT_SHA,
        "first_continuation_sha256": AMENDMENT_SHA,
        "bound_plan_identity_sha256": PLAN_SHA,
        "archive_read_mapping": _mapping(),
        "historical_relocation_receipt_available": False,
        "historical_relocation_chain_verified": False,
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "full_1470_composite_gate_passed": False,
        "retained_count": 1082,
        "remaining_count": 388,
        "retained_identities": dict(IDENTITIES),
        "scope": "CURRENT_ARCHIVE_BYTES_AND_FROZEN_DEPENDENCIES_NOT_RELOCATION_HISTORY",
    }


def manifest_identity(manifest):
    return digest(
        {key: value for key, value in manifest.items() if key != "manifest_identity_sha256"}
    )


def prepare_manifest(root):
    """Return a new manifest in memory; hash only, never copy private contents."""
    pins = _dependency_pins(root)
    archives = {area: _archive_files(root, relative) for area, relative in ARCHIVE_ROOTS.items()}
    for names in archives.values():
        for name in names:
            require(name not in pins, "EVIDENCE_DUPLICATE_PATH")
            pins[name] = descriptor(root, name)
    manifest = {
        **_base_manifest(),
        "archive_file_counts": {area: len(names) for area, names in archives.items()},
        "files": [pins[name] for name in sorted(pins)],
    }
    manifest["manifest_identity_sha256"] = manifest_identity(manifest)
    return manifest


def verify_manifest(root, manifest):
    """Verify exact archive membership and pins; caller must trust/pin manifest bytes."""
    require(isinstance(manifest, dict), "EVIDENCE_MANIFEST_OBJECT_REQUIRED")
    expected = _base_manifest()
    require(
        set(manifest)
        == set(expected) | {"files", "archive_file_counts", "manifest_identity_sha256"},
        "EVIDENCE_MANIFEST_SCHEMA_CHANGED",
    )
    require(
        all(canonical(manifest.get(key)) == canonical(value) for key, value in expected.items()),
        "EVIDENCE_MANIFEST_BINDING_CHANGED",
    )
    require(
        manifest_identity(manifest) == manifest["manifest_identity_sha256"],
        "EVIDENCE_MANIFEST_IDENTITY_CHANGED",
    )
    require(isinstance(manifest["files"], list), "EVIDENCE_FILE_LIST_REQUIRED")
    pins = {}
    for pin in manifest["files"]:
        require(
            isinstance(pin, dict)
            and set(pin) == {"path", "size_bytes", "sha256"}
            and type(pin["size_bytes"]) is int
            and pin["size_bytes"] >= 0
            and isinstance(pin["sha256"], str)
            and len(pin["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in pin["sha256"]),
            "EVIDENCE_PIN_SCHEMA_CHANGED",
        )
        name = pin["path"]
        checked_path(root, name)
        require(
            name.casefold() not in {path.casefold() for path in pins}, "EVIDENCE_DUPLICATE_PATH"
        )
        pins[name] = pin
    dependencies = _dependency_pins(root)
    archives = {area: _archive_files(root, relative) for area, relative in ARCHIVE_ROOTS.items()}
    expected_names = set(dependencies) | {name for names in archives.values() for name in names}
    require(set(pins) == expected_names, "EVIDENCE_CLOSURE_MISSING_OR_EXTRA_FILE")
    require(
        manifest["archive_file_counts"] == {area: len(names) for area, names in archives.items()},
        "EVIDENCE_ARCHIVE_COUNTS_CHANGED",
    )
    for name, pin in pins.items():
        observed = dependencies.get(name) or descriptor(root, name)
        require(observed == pin, "EVIDENCE_FILE_PIN_CHANGED")
    return {
        "verified": True,
        "manifest_identity_sha256": manifest["manifest_identity_sha256"],
        "descriptor_count": len(pins),
        "archive_file_count": sum(map(len, archives.values())),
    }


def _deny_operation(*args, **kwargs):
    raise EvidenceError("EVIDENCE_HISTORY_IS_READ_ONLY")


def _verify_failure_chain(target, rows, frozen):
    c, low, old = frozen.c, frozen.low, frozen.old
    expected_abort = {
        "amendment_sha256": AMENDMENT_SHA,
        "bound_plan_identity_sha256": PLAN_SHA,
        "combined_target_ceiling": 1470,
        "new_target_ceiling": 598,
        "operation": "generate",
        "error_code": "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
        "original_contract_sha256": PARENT_SHA,
        "prefix_manifest_sha256": target.amendment["prefix_manifest"]["sha256"],
        "scientific_gate_evaluated": False,
    }
    require(
        c.same(target.read("safe", "generate-aborted.safe.json"), expected_abort),
        "EVIDENCE_SECOND_ABORT_CHANGED",
    )
    reservation = old.read_json(
        frozen.loader.owned(target.root, SAFE_BASE + "/experiment-reservation.safe.json")
    )
    require(c.same(reservation, target.reservation_binding()), "EVIDENCE_RESERVATION_CHANGED")
    started = target.read("safe", "generate-started.safe.json")
    expected_started = {
        "amendment_sha256": AMENDMENT_SHA,
        "original_contract_sha256": PARENT_SHA,
        "original_prefix_rows_identity_sha256": c.digest(rows[:872]),
        "epoch_schedule": frozen.EPOCHS,
        "new_target_ceiling": 598,
        "started_at": started.get("started_at"),
    }
    require(c.same(started, expected_started), "EVIDENCE_ATTEMPT_BINDING_CHANGED")
    started_at = low.parse_utc(started["started_at"])
    deadline = low.parse_utc(target.config["execution_limits"]["deadline_utc"])
    require(
        low.parse_utc(target.amendment["frozen_at_utc"]) <= started_at < deadline,
        "EVIDENCE_OLD_ATTEMPT_OUTSIDE_WINDOW",
    )
    epoch = target.verified_epoch(3)
    require(started_at <= low.parse_utc(epoch["started_at"]), "EVIDENCE_EPOCH_BEFORE_ATTEMPT")
    failed = target.read("safe", "epochs/004/resource.safe.json")
    require(
        set(failed)
        == {
            "baseline",
            "contract_sha256",
            "disk_free_bytes",
            "epoch_index",
            "gpu_name",
            "gpu_temperature_c",
            "gpu_total_mib",
            "gpu_used_mib",
            "sampled_at",
        },
        "EVIDENCE_FAILED_BASELINE_SCHEMA_CHANGED",
    )
    require(
        failed["baseline"] is True
        and failed["contract_sha256"] == PARENT_SHA
        and type(failed["epoch_index"]) is int
        and failed["epoch_index"] == 4,
        "EVIDENCE_FAILED_BASELINE_BINDING_CHANGED",
    )
    require(
        type(failed["disk_free_bytes"]) is int
        and low.MIN_DISK_BYTES <= failed["disk_free_bytes"] < frozen.PRELAUNCH_BYTES,
        "EVIDENCE_FAILED_BASELINE_REASON_CHANGED",
    )
    low.validate_resource_sample(failed, baseline=True)
    require(
        low.parse_utc(epoch["stopped_at"]) <= low.parse_utc(failed["sampled_at"]) < deadline,
        "EVIDENCE_FAILED_BASELINE_TIME_CHANGED",
    )
    require(
        c.same(target.read("safe", "epochs/004/amendment.safe.json"), target.epoch_binding(4)),
        "EVIDENCE_FAILED_EPOCH_AUTHORITY_CHANGED",
    )
    require(
        frozen.file_names(target.path("safe", "epochs/004"))
        == {"resource.safe.json", "amendment.safe.json"},
        "EVIDENCE_EXTRA_EPOCH4_FILE",
    )
    require(not target.path("private", "epochs/004").exists(), "EVIDENCE_EPOCH4_PRIVATE_EXISTS")
    for area in ("safe", "private"):
        for relative in ("epochs/005", "panel", "target-operation.lock.safe.json"):
            require(not target.path(area, relative).exists(), "EVIDENCE_UNEXPECTED_FUTURE_STATE")


@dataclass
class HistoryContext:
    target: Any
    rows1082: list
    prompts: dict
    census: dict
    source_context: Any
    manifest_proof: dict


def load_history(root, manifest=None):
    """Reverify original 872 + archived 210 using unchanged frozen raw verifiers."""
    root = _root(root)
    if manifest is None:
        manifest = _read_small(root, MANIFEST)
    proof = verify_manifest(root, manifest)
    import pa_llama_topology_target_continuation_v1 as frozen

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        target = frozen.load_amendment(root, AMENDMENT_SHA)
        for area, archive in ARCHIVE_ROOTS.items():
            require(
                _relative(root, target.paths[area]) == UNARCHIVED_ROOTS[area],
                "EVIDENCE_ORIGINAL_NAMESPACE_CHANGED",
            )
            original = target.paths[area]
            require(
                not original.exists() or not list(original.iterdir()),
                "EVIDENCE_UNARCHIVED_NAMESPACE_NOT_EMPTY",
            )
            target.paths[area] = checked_path(root, archive)
        for worker in (target, target.parent):
            for name in ("write", "dispatch", "generate", "server", "operation"):
                setattr(worker, name, _deny_operation)
        prompts = target.load_materials()
        census = target.load_census(prompts)
        rows = target.reconcile(prompts, census)
        require(
            len(rows) == 1082
            and [row["ordinal"] for row in rows] == list(range(1, 1083))
            and len({row["request_id"] for row in rows}) == 1082,
            "EVIDENCE_RETAINED_PREFIX_NOT_EXACT_1082",
        )
        missing = target.plan["requests"][1082:]
        require(len(missing) == 388, "EVIDENCE_REMAINING_NOT_388")
        identities = {
            "original_prefix_rows_identity_sha256": frozen.c.digest(rows[:872]),
            "archived_suffix_rows_identity_sha256": frozen.c.digest(rows[872:]),
            "combined_rows_identity_sha256": frozen.c.digest(rows),
            "remaining_plan_identity_sha256": frozen.c.digest(missing),
            "remaining_request_ids_identity_sha256": frozen.c.digest(
                [row["request_id"] for row in missing]
            ),
        }
        require(identities == IDENTITIES, "EVIDENCE_STAGE1_IDENTITIES_CHANGED")
        _verify_failure_chain(target, rows, frozen)
    # Recheck prospective byte pins after raw verification; no weights are reread here.
    require(verify_manifest(root, manifest) == proof, "EVIDENCE_MANIFEST_CHANGED_DURING_LOAD")
    return HistoryContext(target, rows, prompts, census, target.source_context, proof)


def write_manifest(root, manifest):
    """Explicitly publish only the fixed NEW manifest, exclusively and durably."""
    verify_manifest(root, manifest)
    parent = checked_path(root, str(PurePosixPath(MANIFEST).parent))
    path = parent / PurePosixPath(MANIFEST).name
    require(not path.exists(), "EVIDENCE_MANIFEST_ALREADY_EXISTS")
    raw = canonical(manifest) + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": MANIFEST, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("prepare-manifest", "verify-manifest", "verify-history")
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-manifest":
        result = write_manifest(args.root, prepare_manifest(args.root))
    elif args.command == "verify-manifest":
        result = verify_manifest(args.root, _read_small(args.root, MANIFEST))
    else:
        history = load_history(args.root)
        result = {
            **history.manifest_proof,
            "retained_targets": len(history.rows1082),
            "remaining_targets": 388,
            "new_model_calls": 0,
            "historical_relocation_chain_verified": False,
            "original_operational_gate_passed": False,
            "first_continuation_operational_gate_passed": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
