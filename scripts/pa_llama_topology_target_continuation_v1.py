"""Explicit missing-only target continuation; immutable original failure remains FAIL.

No actions on import. Only the root may invoke preparation or execution. Private
reads stay in the explicitly pinned NEW screen/topology evidence closure.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
from contextlib import contextmanager
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_target_v1 as low
import pa_llama_topology_execution_v1 as loader
import pa_llama_topology_target_v1 as old

SCRIPT = "scripts/pa_llama_topology_target_continuation_v1.py"
CONFIG = "configs/natural_language_localization/pa_llama_topology_target_continuation_v1.json"
PROTOCOL = "docs/PA_LLAMA_TOPOLOGY_TARGET_CONTINUATION_PROTOCOL_2026-09-06_V1.md"
SAFE_ROOT = "data/natural_language_localization/pa_llama_topology_target_continuation_v1"
PRIVATE_ROOT = "artifacts/pa_llama_topology_target_continuation_v1/private"
PARENT_SHA = "d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0"
PLAN_SHA = "8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9"
PREFIX_PATH = f"{SAFE_ROOT}/{PARENT_SHA}/prefix-manifest.safe.json"
SCHEMA = "jbspan-pa-llama-topology-target-continuation-v1"
PROOF_SCHEMA = "jbspan-pa-llama-topology-target-composite-verification-v1"
SCOPE = "RAW_ALL_1470_TARGET_RECEIPTS_WITH_EXPLICIT_CONTINUATION_NOT_ORIGINAL_OPERATIONAL_PASS"
PREFIX_COUNT = 872
TOTAL = 1470
PRELAUNCH_BYTES = 20 * 1024**3
EPOCHS = [
    {"epoch_index": 3, "first_ordinal": 873, "last_ordinal": 1082},
    {"epoch_index": 4, "first_ordinal": 1083, "last_ordinal": 1292},
    {"epoch_index": 5, "first_ordinal": 1293, "last_ordinal": 1470},
]
NEW_CODE = (
    SCRIPT,
    "tests/test_pa_llama_topology_target_continuation_v1.py",
    "scripts/pa_llama_topology_continued_evaluation_v1.py",
    "tests/test_pa_llama_topology_continued_evaluation_v1.py",
    "tests/test_pa_llama_topology_continuation_integration_review_v1.py",
)
TARGET_SUFFIXES = (
    ("safe", ".dispatch.safe.json"),
    ("safe", ".row.safe.json"),
    ("safe", ".tpl.safe.json"),
    ("safe", ".cooldown.safe.json"),
    ("private", ".request.private.json"),
    ("private", ".reply.private.json"),
)
EPOCH_FILES = (
    ("safe", "resource.safe.json"),
    ("safe", "server-01.started.safe.json"),
    ("safe", "server-01.identity.safe.json"),
    ("safe", "server-01.stopped.safe.json"),
    ("safe", "server-01.tpl.safe.json"),
    ("private", "server-01.log.private.txt"),
)


def snapshot(path, *, maximum=32_000_000):
    """Byte hashing only; never emits content. Reject file replacement/read races."""
    c.require(path.is_file(), "CONTINUATION_PINNED_FILE_MISSING")
    before = path.stat()
    c.require(0 <= before.st_size <= maximum, "CONTINUATION_FILE_SIZE_INVALID")
    raw = path.read_bytes()
    after = path.stat()
    c.require(
        (before.st_size, before.st_mtime_ns, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_ino)
        and len(raw) == before.st_size,
        "CONTINUATION_FILE_CHANGED_DURING_READ",
    )
    return raw


def fixed_frame(parent):
    parent.assert_unchanged()
    requests = parent.plan["requests"]
    c.require(
        parent.config["_contract_sha256"] == PARENT_SHA
        and parent.plan["plan_identity_sha256"] == PLAN_SHA
        and len(requests) == TOTAL
        and c.same([r["ordinal"] for r in requests], list(range(1, TOTAL + 1)))
        and len({r["request_id"] for r in requests}) == TOTAL
        and sum(r["kind"] == "science" for r in requests) == 882
        and sum(r["kind"] == "control" for r in requests) == 588,
        "CONTINUATION_ORIGINAL_FULL_FRAME_CHANGED",
    )
    return requests


def file_names(directory):
    if not directory.exists():
        return set()
    paths = list(directory.iterdir())
    c.require(all(path.is_file() for path in paths), "UNEXPECTED_RECEIPT_SUBDIRECTORY")
    return {path.name for path in paths}


def parent_entries(parent):
    """Exact exhaustive relevant original receipt names, not an arbitrary path list."""
    requests = fixed_frame(parent)
    entries = [
        ("safe", "materializations.safe.json"),
        ("safe", "census.safe.json"),
        ("safe", "census-started.safe.json"),
        ("private", "materializations.private.json"),
        ("safe", "generate-aborted.safe.json"),
    ]
    for item in requests[:PREFIX_COUNT]:
        entries += [
            (kind, f"target/{item['request_id']}{suffix}") for kind, suffix in TARGET_SUFFIXES
        ]
    failed = f"target/{requests[PREFIX_COUNT]['request_id']}.cooldown.safe.json"
    entries.append(("safe", failed))
    for item in parent.plan["metadata_requests"]:
        entries += [
            (kind, f"metadata/{item['metadata_request_id']}{suffix}")
            for kind, suffix in TARGET_SUFFIXES
            if suffix not in {".tpl.safe.json", ".cooldown.safe.json"}
        ]
    for item in parent.plan["bound_materializations"]:
        entries += [
            ("safe", f"census/{item['materialization_id']}.{suffix}.safe.json")
            for suffix in ("tpl", "row")
        ]
    for epoch in (1, 2):
        entries += [(kind, f"epochs/{epoch:03d}/{name}") for kind, name in EPOCH_FILES]
    c.require(len(entries) == len(set(entries)), "PREFIX_ENTRY_DUPLICATE")
    return sorted(entries)


def verify_parent_names(parent):
    entries = parent_entries(parent)
    top_levels = {
        "safe": {
            "census",
            "census-started.safe.json",
            "census.safe.json",
            "epochs",
            "generate-aborted.safe.json",
            "materializations.safe.json",
            "metadata",
            "target",
        },
        "private": {"epochs", "materializations.private.json", "metadata", "target"},
    }
    for kind in ("safe", "private"):
        c.require(
            {path.name for path in parent.paths[kind].iterdir()} == top_levels[kind],
            "PARENT_ROOT_NAMESPACE_CHANGED",
        )
        for directory in ("target", "metadata", "census"):
            expected = {
                relative.split("/")[-1]
                for area, relative in entries
                if area == kind and relative.startswith(directory + "/")
            }
            c.require(
                file_names(parent.path(kind, directory)) == expected,
                "PARENT_RECEIPT_SET_CHANGED_OR_AMBIGUOUS",
            )
        epochs = parent.path(kind, "epochs")
        c.require(
            epochs.is_dir() and {x.name for x in epochs.iterdir()} == {"001", "002"},
            "PARENT_EPOCH_SET_CHANGED",
        )
        for epoch in (1, 2):
            expected = {name for area, name in EPOCH_FILES if area == kind}
            c.require(
                file_names(parent.path(kind, f"epochs/{epoch:03d}")) == expected,
                "PARENT_EPOCH_FILE_SET_CHANGED",
            )
    for name in (
        "target-operation.lock.safe.json",
        "stage-aborted.safe.json",
        "census-aborted.safe.json",
        "targets.safe.json",
    ):
        c.require(not parent.path("safe", name).exists(), "PARENT_NOT_QUIESCENT_FAILED_PREFIX")
    reservation_path = loader.owned(
        parent.root, old.SAFE_ROOT + "/experiment-reservation.safe.json"
    )
    c.require(
        c.same(
            old.read_json(reservation_path),
            {
                "contract_sha256": PARENT_SHA,
                "bound_plan_identity_sha256": PLAN_SHA,
                "budgets": parent.plan["budgets"],
                "historical_private_reads_allowed": False,
                "ambiguous_dispatch_retry_allowed": False,
            },
        ),
        "PARENT_RESERVATION_CHANGED",
    )
    return entries


def make_prefix_manifest(parent):
    """Read-only hashes of NEW experiment bytes; deliberately not raw certification."""
    entries = verify_parent_names(parent)
    pins = []
    for kind, relative in entries:
        raw = snapshot(parent.path(kind, relative))
        pins.append(
            {"kind": kind, "relative": relative, "size_bytes": len(raw), "sha256": c.sha_bytes(raw)}
        )
    verify_parent_names(parent)
    value = {
        "schema_version": "jbspan-pa-llama-topology-failed-prefix-manifest-v1",
        "original_contract_sha256": PARENT_SHA,
        "bound_plan_identity_sha256": PLAN_SHA,
        "original_prefix_count": PREFIX_COUNT,
        "first_missing_ordinal": PREFIX_COUNT + 1,
        "planned_target_count": TOTAL,
        "files": pins,
        "global_reservation": loader.file_descriptor(
            parent.root, old.SAFE_ROOT + "/experiment-reservation.safe.json"
        ),
        "raw_receipts_verified": False,
        "scientific_gate_evaluated": False,
        "private_content_copied": False,
        "historical_private_reads": 0,
        "new_model_calls": 0,
        "execution_authorized": False,
    }
    value["manifest_identity_sha256"] = c.digest(value)
    return value


def prepare_prefix(parent):
    value = make_prefix_manifest(parent)
    path = loader.owned(parent.root, PREFIX_PATH)
    raw = c.canonical(value) + b"\n"
    if path.exists():
        c.require(snapshot(path) == raw, "EXISTING_PREFIX_MANIFEST_CHANGED")
    else:
        c.write_once(path, raw, raw=True)
    return {"path": PREFIX_PATH, "size_bytes": len(raw), "sha256": c.sha_bytes(raw)}


def make_template(root, parent, prefix_pin):
    fixed_frame(parent)
    c.require(prefix_pin.get("path") == PREFIX_PATH, "PREFIX_PIN_PATH_CHANGED")
    value = {
        "schema_version": SCHEMA,
        "frozen": False,
        "execution_authorized": False,
        "frozen_at_utc": None,
        "original_contract_sha256": PARENT_SHA,
        "bound_plan_identity_sha256": PLAN_SHA,
        "prefix_manifest": prefix_pin,
        "original_prefix_count": PREFIX_COUNT,
        "planned_target_count": TOTAL,
        "continuation_target_count": TOTAL - PREFIX_COUNT,
        "epoch_schedule": EPOCHS,
        "prelaunch_minimum_disk_free_bytes": PRELAUNCH_BYTES,
        "per_dispatch_minimum_disk_free_bytes": low.MIN_DISK_BYTES,
        "cooldown": old.COOLDOWN,
        "execution_limits": parent.config["execution_limits"],
        "budgets": {
            "combined_target_calls": TOTAL,
            "new_target_calls": TOTAL - PREFIX_COUNT,
            "new_metadata_calls": 0,
        },
        "paths": {"safe_root": SAFE_ROOT, "private_root": PRIVATE_ROOT},
        "verification_scope": SCOPE,
        "original_operational_gate_passed": False,
        "scientific_rules_unchanged": True,
        "automatic_retry_allowed": False,
        "historical_private_reads_allowed": False,
        "paper_validity": False,
        "protocol": loader.file_descriptor(root, PROTOCOL),
        "required_code": {name: loader.file_descriptor(root, name) for name in NEW_CODE},
    }
    return c.strict_json(c.canonical(value))


def load_parent(root):
    loaded = loader.validate_execution(root, PARENT_SHA)
    parent = old.TopologyTarget(
        root, loaded["config"], loaded["prepared"]["bound_plan"], loaded["source_context"]
    )
    fixed_frame(parent)
    return parent, loaded


def load_amendment(root, expected_sha):
    c.require(c.valid_sha(expected_sha), "AMENDMENT_EXPECTED_SHA_REQUIRED")
    raw = snapshot(loader.owned(root, CONFIG))
    c.require(c.sha_bytes(raw) == expected_sha, "AMENDMENT_RAW_SHA_MISMATCH")
    amendment = c.strict_json(raw)
    c.require(
        isinstance(amendment, dict)
        and amendment.get("frozen") is True
        and amendment.get("execution_authorized") is True,
        "SEPARATE_FROZEN_AMENDMENT_REQUIRED",
    )
    c.require(
        isinstance(amendment.get("required_code"), dict)
        and set(amendment["required_code"]) == set(NEW_CODE),
        "AMENDMENT_CODE_CLOSURE",
    )
    for name, pin in amendment["required_code"].items():
        c.require(pin.get("path") == name, "AMENDMENT_CODE_PATH_CHANGED")
        c.verify_pin(root, pin, ("scripts/", "tests/"))
    c.require(
        amendment.get("protocol", {}).get("path") == PROTOCOL, "AMENDMENT_PROTOCOL_PATH_CHANGED"
    )
    c.verify_pin(root, amendment["protocol"], ("docs/",))
    c.require(
        c.verify_pin(root, amendment["required_code"][SCRIPT], ("scripts/",))
        == Path(__file__).resolve(),
        "AMENDMENT_SELF_PIN_MISMATCH",
    )
    parent, loaded = load_parent(root)
    prefix_pin = amendment.get("prefix_manifest")
    c.require(
        isinstance(prefix_pin, dict) and prefix_pin.get("path") == PREFIX_PATH,
        "PREFIX_MANIFEST_PIN_REQUIRED",
    )
    prefix_raw = loader.read_pin(root, prefix_pin, PREFIX_PATH)
    expected = make_template(root, parent, prefix_pin)
    frozen_at = low.parse_utc(amendment.get("frozen_at_utc"))
    c.require(
        low.parse_utc(parent.config["frozen_at_utc"])
        <= frozen_at
        < low.parse_utc(parent.config["execution_limits"]["deadline_utc"]),
        "AMENDMENT_TIMESTAMP_OUT_OF_AUTHORITY",
    )
    expected.update(
        frozen=True, execution_authorized=True, frozen_at_utc=amendment["frozen_at_utc"]
    )
    c.require(c.same(amendment, expected), "AMENDMENT_NOT_EXACT_PROSPECTIVE_TEMPLATE")
    amendment["_amendment_sha256"] = expected_sha
    return CompositeTarget(parent, amendment, c.strict_json(prefix_raw), loaded=loaded)


class CompositeTarget(old.TopologyTarget):
    """Explicit composite evidence; the inherited original operational gate stays false."""

    def __init__(self, parent, amendment, prefix_manifest, *, loaded=None):
        fixed_frame(parent)
        self.parent = parent
        self.root = parent.root
        self.config = c.strict_json(c.canonical(parent.config))
        self.plan = c.strict_json(c.canonical(parent.plan))
        self.items = {row["request_id"]: row for row in self.plan["requests"]}
        self.materials = {
            row["materialization_id"]: row for row in self.plan["bound_materializations"]
        }
        self._validated_config_sha256 = c.digest(self.config)
        self._validated_plan_sha256 = c.digest(self.plan)
        self.amendment = c.strict_json(c.canonical(amendment))
        self.prefix_manifest = c.strict_json(c.canonical(prefix_manifest))
        self._amendment_identity = c.digest(self.amendment)
        self._prefix_identity = c.digest(self.prefix_manifest)
        self.amendment_sha = self.amendment["_amendment_sha256"]
        c.require(c.valid_sha(self.amendment_sha), "AMENDMENT_IDENTITY_REQUIRED")
        self.paths = {
            kind: loader.owned(self.root, base + "/" + self.amendment_sha)
            for kind, base in (("safe", SAFE_ROOT), ("private", PRIVATE_ROOT))
        }
        self.helper = parent.helper
        self.loaded = loaded
        self.source_context = loaded["source_context"] if loaded else {}

    def assert_amendment_unchanged(self):
        super().assert_unchanged()
        self.parent.assert_unchanged()
        c.require(
            c.digest(self.amendment) == self._amendment_identity
            and c.digest(self.prefix_manifest) == self._prefix_identity,
            "POSTVALIDATION_AMENDMENT_OR_PREFIX_MUTATION",
        )

    def assert_unchanged(self):
        self.assert_amendment_unchanged()

    def payloads_by_position(self):
        c.require(self.loaded is not None, "PARENT_LOADER_CONTEXT_REQUIRED")
        return loader.payloads_by_position(self.loaded)

    def path(self, kind, relative):
        if relative.startswith("target/"):
            rid = relative.split("/")[1].split(".")[0]
            c.require(rid in self.items, "TARGET_PATH_NOT_IN_ORIGINAL_FRAME")
            if self.items[rid]["ordinal"] <= PREFIX_COUNT:
                return self.parent.path(kind, relative)
        return c.contained(self.paths[kind], relative)

    def write(self, kind, relative, value, *, raw=False):
        if relative.startswith("target/"):
            rid = relative.split("/")[1].split(".")[0]
            c.require(
                rid in self.items and self.items[rid]["ordinal"] > PREFIX_COUNT,
                "IMMUTABLE_PREFIX_WRITE_FORBIDDEN",
            )
        c.write_once(c.contained(self.paths[kind], relative), value, raw=raw)

    def load_materials(self):
        self.assert_amendment_unchanged()
        return self.parent.load_materials()

    def load_census(self, prompts=None):
        self.assert_amendment_unchanged()
        return self.parent.load_census(prompts)

    def census(self):
        raise c.DevelopmentError("CONTINUATION_NO_NEW_METADATA")

    def stage(self, materials):
        raise c.DevelopmentError("CONTINUATION_NO_NEW_MATERIALIZATIONS")

    def metadata_post(self, *args, **kwargs):
        raise c.DevelopmentError("CONTINUATION_NO_NEW_METADATA")

    def dispatch(self, item, prompt, census_row, process, client, epoch):
        self.assert_amendment_unchanged()
        c.require(
            item.get("request_id") in self.items and c.same(item, self.items[item["request_id"]]),
            "CONTINUATION_DISPATCH_ITEM_CHANGED",
        )
        part = self.epoch_binding(epoch)
        c.require(
            part["first_ordinal"] <= item["ordinal"] <= part["last_ordinal"],
            "CONTINUATION_DISPATCH_OUTSIDE_FIXED_EPOCH",
        )
        return super().dispatch(item, prompt, census_row, process, client, epoch)

    def verify_prefix_manifest(self):
        self.assert_amendment_unchanged()
        c.require(
            c.same(make_prefix_manifest(self.parent), self.prefix_manifest),
            "IMMUTABLE_ORIGINAL_PREFIX_BYTES_CHANGED",
        )
        abort = self.parent.read("safe", "generate-aborted.safe.json")
        c.require(
            c.same(
                abort,
                {
                    "contract_sha256": PARENT_SHA,
                    "operation": "generate",
                    "error_code": "DISK_FREE_SPACE_BELOW_15_GIB",
                    "scientific_gate_evaluated": False,
                },
            ),
            "ORIGINAL_DISK_ABORT_NOT_RETAINED",
        )
        failed = self.plan["requests"][PREFIX_COUNT]
        receipt = self.parent.read("safe", f"target/{failed['request_id']}.cooldown.safe.json")
        c.require(
            set(receipt)
            == {
                "contract_sha256",
                "request_id",
                "epoch_index",
                "policy",
                "samples",
                "cooldown_passed",
                "wait_seconds",
                "measurement",
            }
            and receipt.get("contract_sha256") == PARENT_SHA
            and receipt.get("request_id") == failed["request_id"]
            and c.same(receipt.get("epoch_index"), 2)
            and c.same(receipt.get("policy"), old.COOLDOWN)
            and receipt.get("cooldown_passed") is False
            and isinstance(receipt.get("samples"), list)
            and receipt["samples"]
            and type(receipt["samples"][-1].get("disk_free_bytes")) is int
            and receipt["samples"][-1]["disk_free_bytes"] < low.MIN_DISK_BYTES,
            "ORIGINAL_FAILED_PREDISPATCH_EVIDENCE_CHANGED",
        )
        epoch = self.verified_epoch(2)
        c.require(
            receipt["measurement"] == "PREDISPATCH_SNAPSHOTS_NOT_CONTINUOUS_PEAK"
            and type(receipt["wait_seconds"]) in (int, float)
            and math.isfinite(receipt["wait_seconds"])
            and receipt["wait_seconds"] >= 0,
            "FAILED_COOLDOWN_MEASUREMENT_OR_WAIT_INVALID",
        )
        last_prefix = self.plan["requests"][PREFIX_COUNT - 1]
        last_row = self.parent.read("safe", f"target/{last_prefix['request_id']}.row.safe.json")
        previous_time = low.parse_utc(last_row["received_at"])
        for index, sample in enumerate(receipt["samples"]):
            measured_at = low.parse_utc(sample.get("sampled_at"))
            c.require(
                low.parse_utc(epoch["started_at"])
                <= previous_time
                <= measured_at
                <= low.parse_utc(epoch["stopped_at"])
                and measured_at < low.parse_utc(self.config["execution_limits"]["deadline_utc"]),
                "FAILED_COOLDOWN_TIME_CHAIN_INVALID",
            )
            if index == len(receipt["samples"]) - 1:
                # Alter only the temporary validation view; the rejected receipt stays unchanged.
                low.validate_resource_sample(
                    {**sample, "disk_free_bytes": low.MIN_DISK_BYTES}, baseline=False
                )
            else:
                low.validate_resource_sample(sample, baseline=False)
                c.require(
                    sample["gpu_temperature_c"] > 60, "FAILED_COOLDOWN_HAS_EARLIER_ACCEPTED_SAMPLE"
                )
            previous_time = measured_at
        c.require(
            low.parse_utc(epoch["stopped_at"]) < low.parse_utc(self.amendment["frozen_at_utc"]),
            "AMENDMENT_NOT_AFTER_ORIGINAL_CLEANUP",
        )
        return True

    def global_check(self, kind):
        c.require(kind == "target", "CONTINUATION_NO_NEW_METADATA")
        verify_parent_names(self.parent)
        allowed_roots = {
            "safe": {
                "target",
                "epochs",
                "generate-started.safe.json",
                "generate-aborted.safe.json",
                "target-operation.lock.safe.json",
                "targets.safe.json",
                "target-verification.safe.json",
                "panel",
                "finalize-aborted.safe.json",
                "panel-qwen-aborted.safe.json",
                "panel-jailmeter-aborted.safe.json",
                "continued-measurements.safe.json",
                "continued-analysis.safe.json",
                "continued-result.safe.json",
                "continued-verification.safe.json",
            },
            "private": {"target", "epochs", "panel"},
        }
        for area in ("safe", "private"):
            base = self.paths[area]
            if base.exists():
                c.require(
                    {path.name for path in base.iterdir()} <= allowed_roots[area],
                    "UNEXPECTED_CHILD_ROOT_NAMESPACE",
                )
            directory = c.contained(base, "epochs")
            if directory.exists():
                c.require(
                    {path.name for path in directory.iterdir()} <= {"003", "004", "005"},
                    "UNEXPECTED_CHILD_EPOCH",
                )
                for path in directory.iterdir():
                    expected_files = {name for kind, name in EPOCH_FILES if kind == area}
                    if area == "safe":
                        expected_files.add("amendment.safe.json")
                    c.require(file_names(path) <= expected_files, "UNEXPECTED_CHILD_EPOCH_FILE")
        expected = {r["request_id"] for r in self.plan["requests"][PREFIX_COUNT:]}
        observed = set()
        for area, suffix in TARGET_SUFFIXES:
            directory = c.contained(self.paths[area], "target")
            names = file_names(directory)
            allowed_suffixes = [s for a, s in TARGET_SUFFIXES if a == area]
            c.require(
                all(any(name.endswith(s) for s in allowed_suffixes) for name in names),
                "UNEXPECTED_CHILD_TARGET_FILE",
            )
            ids = {name.removesuffix(suffix) for name in names if name.endswith(suffix)}
            c.require(ids <= expected, "CHILD_DISPATCH_OUTSIDE_EXACT598_SUFFIX")
            if suffix == ".dispatch.safe.json":
                observed = ids
            else:
                c.require(ids <= observed, "CHILD_ORPHAN_OR_AMBIGUOUS_NO_RETRY")
        return {r["request_id"] for r in self.plan["requests"][:PREFIX_COUNT]} | observed

    def verified_epoch(self, index):
        c.require(type(index) is int and index in (1, 2, 3, 4, 5), "COMPOSITE_EPOCH_INVALID")
        paths = self.parent.paths if index <= 2 else self.paths
        epoch = low.verify_epoch(self.config, paths, index, self.helper, self.root)
        if index >= 3:
            baseline = old.read_json(
                c.contained(paths["safe"], f"epochs/{index:03d}/resource.safe.json")
            )
            c.require(
                baseline["disk_free_bytes"] >= PRELAUNCH_BYTES,
                "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
            )
            owner = self.read("safe", f"epochs/{index:03d}/amendment.safe.json")
            c.require(c.same(owner, self.epoch_binding(index)), "CHILD_EPOCH_AUTHORITY_CHANGED")
            c.require(
                low.parse_utc(self.amendment["frozen_at_utc"])
                <= low.parse_utc(baseline["sampled_at"]),
                "CHILD_EPOCH_BEFORE_AMENDMENT",
            )
        return epoch

    def epoch_binding(self, index):
        schedule = next((row for row in EPOCHS if row["epoch_index"] == index), None)
        c.require(schedule is not None, "CHILD_EPOCH_NOT_PROSPECTIVELY_FIXED")
        return {
            "amendment_sha256": self.amendment_sha,
            "original_contract_sha256": PARENT_SHA,
            "bound_plan_identity_sha256": PLAN_SHA,
            **schedule,
            "prelaunch_minimum_disk_free_bytes": PRELAUNCH_BYTES,
        }

    def reconcile(self, prompts, census):
        self.verify_prefix_manifest()
        observed = self.global_check("target")
        census_map = {row["materialization_id"]: row for row in census["rows"]}
        previous = self.verified_epoch(census["epoch_index"])
        previous_received = low.parse_utc(previous["stopped_at"])
        previous_stopped = previous_received
        previous_index = census["epoch_index"]
        complete, missing, epochs = [], False, {}
        for item in self.plan["requests"]:
            rid, mid = item["request_id"], item["materialization_id"]
            if rid not in observed:
                missing = True
                continue
            c.require(not missing, "COMPOSITE_DISPATCH_NOT_EXACT_ORDERED_PREFIX")
            stem = f"target/{rid}"
            journal = self.read("safe", stem + ".dispatch.safe.json")
            row = self.read("safe", stem + ".row.safe.json")
            index = journal.get("epoch_index")
            wanted = (
                2
                if item["ordinal"] <= PREFIX_COUNT
                else next(
                    part["epoch_index"]
                    for part in EPOCHS
                    if part["first_ordinal"] <= item["ordinal"] <= part["last_ordinal"]
                )
            )
            c.require(c.same(index, wanted), "TARGET_EPOCH_NOT_FIXED_BY_ORIGINAL_ORDINAL")
            if index not in epochs:
                epochs[index] = self.verified_epoch(index)
            epoch = epochs[index]
            c.require(
                index >= previous_index
                and previous_received <= low.parse_utc(journal.get("dispatch_at")),
                "COMPOSITE_REQUEST_TIME_ORDER_INVALID",
            )
            if index != previous_index:
                c.require(
                    previous_stopped <= low.parse_utc(epoch["started_at"]),
                    "COMPOSITE_OWNED_EPOCHS_OVERLAP",
                )
            request = old.request_for(self.config, item, prompts[mid])
            expected = {
                **item,
                "contract_sha256": PARENT_SHA,
                "request_sha256": c.digest(request),
                "epoch_index": index,
                "process_id": epoch["pid"],
                "census_row_sha256": c.digest(census_map[mid]),
                "served_chat_template_sha256": self.config["runtime"][
                    "served_chat_template_sha256"
                ],
            }
            c.require(
                set(journal) == set(expected) | {"dispatch_at", "cooldown_receipt_sha256"}
                and all(c.same(journal.get(k), v) for k, v in expected.items())
                and c.same(self.read("private", stem + ".request.private.json"), request),
                "COMPOSITE_REQUEST_CENSUS_JOURNAL_MISMATCH",
            )
            self.verify_cooldown(item, epoch, journal, previous_received)
            self.helper.verify_template_observation(
                self.config,
                PARENT_SHA,
                self.path("safe", stem + ".tpl.safe.json"),
                {"request_id": rid, "epoch_index": index, "process_id": epoch["pid"]},
            )
            raw = snapshot(
                self.path("private", stem + ".reply.private.json"), maximum=low.MAX_REPLY_BYTES
            )
            parsed = old.parse_reply(
                self.config, item, raw, census_map[mid]["native_prompt_tokens"]
            )
            expected = {**journal, **parsed}
            c.require(
                set(row) == set(expected) | {"latency_seconds", "received_at"}
                and all(c.same(row.get(k), v) for k, v in expected.items()),
                "COMPOSITE_RAW_TARGET_ROW_MISMATCH",
            )
            self.verify_times(epoch, journal, row)
            previous_received = low.parse_utc(row["received_at"])
            previous_stopped = low.parse_utc(epoch["stopped_at"])
            previous_index = index
            complete.append(row)
        c.require(len(complete) == len(observed), "COMPOSITE_UNRECONCILED_DISPATCH")
        return complete

    @contextmanager
    def operation(self, name):
        self.assert_amendment_unchanged()
        c.require(
            name in {"generate", "panel-qwen", "panel-jailmeter", "finalize"},
            "CONTINUATION_OPERATION_NOT_AUTHORIZED",
        )
        c.require(
            not self.path("safe", "generate-aborted.safe.json").exists()
            and not self.path("safe", f"{name}-aborted.safe.json").exists(),
            "AMENDED_ABORT_NO_AUTOMATIC_RETRY",
        )
        reservation = loader.owned(self.root, SAFE_ROOT + "/experiment-reservation.safe.json")
        binding = self.reservation_binding()
        if reservation.exists():
            c.require(c.same(old.read_json(reservation), binding), "ANOTHER_CONTINUATION_RESERVED")
        else:
            c.write_once(reservation, binding)
        lock = self.path("safe", "target-operation.lock.safe.json")
        c.write_once(lock, {**binding, "operation": name, "pid": os.getpid()})
        try:
            yield
        except BaseException as error:
            abort = self.path("safe", f"{name}-aborted.safe.json")
            if not abort.exists():
                c.write_once(
                    abort,
                    {
                        **binding,
                        "operation": name,
                        "error_code": low.safe_error_code(error),
                        "scientific_gate_evaluated": False,
                    },
                )
            raise
        finally:
            lock.unlink()

    @contextmanager
    def server(self, epoch):
        low.check_deadline(self.config)
        self.write("safe", f"epochs/{epoch:03d}/amendment.safe.json", self.epoch_binding(epoch))
        sample = low.record_prelaunch(self.root, self.config, self.paths, epoch)
        c.require(
            sample["disk_free_bytes"] >= PRELAUNCH_BYTES, "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB"
        )
        safe, private = low.epoch_paths(self.paths, epoch)
        private.mkdir(parents=True, exist_ok=False)
        with self.helper.owned_server(
            self.root, self.config, private, safe, 1, PARENT_SHA
        ) as owned:
            yield owned
        self.verified_epoch(epoch)

    def summary(self, rows):
        result = old.TopologyTarget.summary(self, rows)
        result.update(
            operational_gate_passed=False,
            original_generate_operational_gate_passed=False,
            original_operational_gate_passed=False,
            prior_operation_failures=["original_generate:DISK_FREE_SPACE_BELOW_15_GIB"],
            amendment_sha256=self.amendment_sha,
            verification_scope=SCOPE,
            amended_target_complete=len(rows) == TOTAL,
            amended_execution_gate_passed=len(rows) == TOTAL
            and not self.path("safe", "generate-aborted.safe.json").exists(),
        )
        return result

    def verify_composite_targets(self):
        prompts = self.load_materials()
        census = self.load_census(prompts)
        rows = self.reconcile(prompts, census)
        status = self.summary(rows)
        c.require(
            status["amended_target_complete"] and status["amended_execution_gate_passed"],
            "AMENDED_TARGET_FULL_FRAME_NOT_VERIFIED",
        )
        self.verify_attempt_authority(rows)
        pins = {(x["kind"], x["relative"]): x for x in self.prefix_manifest["files"]}
        failed_rid = self.plan["requests"][PREFIX_COUNT]["request_id"]
        proof = {
            "schema_version": PROOF_SCHEMA,
            "amendment_sha256": self.amendment_sha,
            "original_contract_sha256": PARENT_SHA,
            "bound_plan_identity_sha256": PLAN_SHA,
            "original_generate_operational_gate_passed": False,
            "original_operational_gate_passed": False,
            "amended_target_frame_verified": True,
            "amended_execution_gate_passed": True,
            "original_prefix_count": PREFIX_COUNT,
            "continuation_count": TOTAL - PREFIX_COUNT,
            "rows_identity_sha256": c.digest(rows),
            "original_prefix_rows_identity_sha256": c.digest(rows[:PREFIX_COUNT]),
            "continuation_rows_identity_sha256": c.digest(rows[PREFIX_COUNT:]),
            "prefix_manifest_sha256": self.amendment["prefix_manifest"]["sha256"],
            "original_abort_pin": pins[("safe", "generate-aborted.safe.json")],
            "failed_predispatch_cooldown_pin": pins[
                ("safe", f"target/{failed_rid}.cooldown.safe.json")
            ],
            "continuation_epoch_proofs": [
                {
                    "epoch_binding": self.epoch_binding(part["epoch_index"]),
                    "lifecycle": self.verified_epoch(part["epoch_index"]),
                    "target_count": part["last_ordinal"] - part["first_ordinal"] + 1,
                    "target_rows_identity_sha256": c.digest(
                        rows[part["first_ordinal"] - 1 : part["last_ordinal"]]
                    ),
                }
                for part in EPOCHS
            ],
            "verification_scope": SCOPE,
            "original_prefix_all_reused": True,
            "no_ambiguous_dispatches": True,
            "scientific_rules_unchanged": True,
            "new_model_calls": 0,
            "paper_validity": False,
        }
        proof["result_identity_sha256"] = c.digest(proof)
        return {"rows": rows, "proof": proof}

    def reservation_binding(self):
        return {
            "original_contract_sha256": PARENT_SHA,
            "amendment_sha256": self.amendment_sha,
            "bound_plan_identity_sha256": PLAN_SHA,
            "prefix_manifest_sha256": self.amendment["prefix_manifest"]["sha256"],
            "combined_target_ceiling": TOTAL,
            "new_target_ceiling": TOTAL - PREFIX_COUNT,
        }

    def verify_attempt_authority(self, rows):
        reservation = loader.owned(self.root, SAFE_ROOT + "/experiment-reservation.safe.json")
        c.require(
            c.same(old.read_json(reservation), self.reservation_binding()),
            "COMPOSITE_GLOBAL_RESERVATION_CHANGED",
        )
        started = self.read("safe", "generate-started.safe.json")
        expected = {
            "amendment_sha256": self.amendment_sha,
            "original_contract_sha256": PARENT_SHA,
            "original_prefix_rows_identity_sha256": c.digest(rows[:PREFIX_COUNT]),
            "epoch_schedule": EPOCHS,
            "new_target_ceiling": TOTAL - PREFIX_COUNT,
        }
        c.require(
            set(started) == set(expected) | {"started_at"}
            and all(c.same(started.get(key), value) for key, value in expected.items()),
            "COMPOSITE_GENERATE_AUTHORITY_CHANGED",
        )
        stamp = low.parse_utc(started["started_at"])
        c.require(
            low.parse_utc(self.amendment["frozen_at_utc"])
            <= stamp
            < low.parse_utc(self.config["execution_limits"]["deadline_utc"]),
            "COMPOSITE_GENERATE_AUTHORITY_TIME_INVALID",
        )
        for part in EPOCHS:
            resource = self.read("safe", f"epochs/{part['epoch_index']:03d}/resource.safe.json")
            c.require(
                stamp <= low.parse_utc(resource["sampled_at"]),
                "CHILD_EPOCH_BEFORE_RECORDED_ATTEMPT",
            )

    def generate(self):
        prompts = self.load_materials()
        census = self.load_census(prompts)
        prefix = self.reconcile(prompts, census)
        c.require(len(prefix) == PREFIX_COUNT, "CONTINUATION_ALREADY_ATTEMPTED_NO_RETRY")
        with self.operation("generate"):
            for relative in ("generate-started.safe.json", "target", "epochs"):
                c.require(
                    not c.contained(self.paths["safe"], relative).exists(),
                    "CONTINUATION_ALREADY_ATTEMPTED_NO_RETRY",
                )
            c.require(
                not c.contained(self.paths["private"], "target").exists()
                and not c.contained(self.paths["private"], "epochs").exists(),
                "CONTINUATION_PRIVATE_ATTEMPT_EXISTS",
            )
            self.write(
                "safe",
                "generate-started.safe.json",
                {
                    "amendment_sha256": self.amendment_sha,
                    "original_contract_sha256": PARENT_SHA,
                    "original_prefix_rows_identity_sha256": c.digest(prefix),
                    "epoch_schedule": EPOCHS,
                    "started_at": self.helper.utc_now(),
                    "new_target_ceiling": TOTAL - PREFIX_COUNT,
                },
            )
            census_map = {r["materialization_id"]: r for r in census["rows"]}
            for part in EPOCHS:
                with self.server(part["epoch_index"]) as (process, client, _):
                    for item in self.plan["requests"][
                        part["first_ordinal"] - 1 : part["last_ordinal"]
                    ]:
                        mid = item["materialization_id"]
                        self.dispatch(
                            item,
                            prompts[mid],
                            census_map[mid],
                            process,
                            client,
                            part["epoch_index"],
                        )
            verified = self.verify_composite_targets()
            result = self.summary(verified["rows"])
            self.write("safe", "targets.safe.json", result)
            self.write("safe", "target-verification.safe.json", verified["proof"])
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare-prefix",
            "template",
            "preflight",
            "generate",
            "status",
            "panel",
            "verify-panel",
            "finalize",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--amendment-sha256")
    parser.add_argument("--axis", choices=("qwen", "jailmeter"))
    parser.add_argument("--with-template", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in {"prepare-prefix", "template"}:
            parent, _ = load_parent(args.root)
            if args.command == "prepare-prefix":
                result = prepare_prefix(parent)
                if args.with_template:
                    result = {
                        "prefix_manifest": result,
                        "template": make_template(args.root, parent, result),
                    }
            else:
                pin = loader.file_descriptor(args.root, PREFIX_PATH)
                result = make_template(args.root, parent, pin)
        else:
            worker = load_amendment(args.root, args.amendment_sha256)
            if args.command == "generate":
                result = worker.generate()
            elif args.command in {"panel", "verify-panel", "finalize"}:
                module = importlib.import_module("pa_llama_topology_continued_evaluation_v1")
                payloads = worker.payloads_by_position()
                if args.command == "finalize":
                    result = module.finalize(worker, payloads, worker.source_context)
                else:
                    c.require(args.axis in {"qwen", "jailmeter"}, "EXACT_PANEL_AXIS_REQUIRED")
                    panel = module.AmendedTopologyPanel(worker, payloads)
                    result = (
                        panel.run(args.axis) if args.command == "panel" else panel.verify(args.axis)
                    )
                result = {
                    "amendment_sha256": worker.amendment_sha,
                    "command": args.command,
                    "completed": True,
                    "result_identity_sha256": c.digest(result),
                    "paper_validity": False,
                }
            else:
                result = worker.status()
                result["new_model_calls"] = 0
                result["preflight_passed"] = args.command == "preflight"
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "completed": False,
                    "error_code": low.safe_error_code(error),
                    "paper_validity": False,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
