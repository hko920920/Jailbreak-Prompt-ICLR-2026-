"""Synthetic trees only: no research/model files or network access."""

import copy
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pa_reentry_evidence_v2 as m  # noqa: E402


def write(root, relative, raw=b"invented harmless bytes"):
    path = m.native(root / relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def reseal(manifest):
    manifest["manifest_identity_sha256"] = m.manifest_identity(manifest)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    # Short synthetic namespaces exercise the same exact-closure algorithm.
    monkeypatch.setattr(
        m, "ARCHIVE_ROOTS", {"safe": "data/new/archive", "private": "artifacts/new/private/archive"}
    )
    monkeypatch.setattr(
        m,
        "UNARCHIVED_ROOTS",
        {"safe": "data/new/original", "private": "artifacts/new/private/original"},
    )
    write(tmp_path, "scripts/frozen.py", b"# invented frozen source\n")
    expected = m.descriptor(tmp_path, "scripts/frozen.py")

    def dependencies(root):
        observed = m.descriptor(root, expected["path"])
        m.require(observed == expected, "EVIDENCE_OLD_DEPENDENCY_CHANGED")
        return {expected["path"]: expected}

    monkeypatch.setattr(m, "_dependency_pins", dependencies)
    write(tmp_path, "data/new/archive/start.safe.json", b'{"invented":true}')
    write(tmp_path, "artifacts/new/private/archive/reply.private.json", b'{"text":"hello"}')
    return tmp_path, m.prepare_manifest(tmp_path)


def test_exact_manifest_and_read_only_preparation(tree):
    root, manifest = tree
    before = sorted(str(path) for path in root.rglob("*"))
    assert m.prepare_manifest(root) == manifest
    proof = m.verify_manifest(root, manifest)
    assert proof == {
        "verified": True,
        "manifest_identity_sha256": m.manifest_identity(manifest),
        "descriptor_count": 3,
        "archive_file_count": 2,
    }
    assert sorted(str(path) for path in root.rglob("*")) == before
    assert manifest["historical_relocation_chain_verified"] is False
    assert manifest["original_operational_gate_passed"] is False
    assert b"hello" not in m.canonical(manifest)


@pytest.mark.parametrize(
    "relative",
    [
        "../outside",
        "/absolute",
        "C:/outside",
        "data\\new\\archive\\x",
        "data/new/../archive/x",
        "data/new/archive/x.",
        "data/new/archive/x ",
        "data//new/archive/x",
        "data/new/archive/x:stream",
        "data/new/archive/\0x",
    ],
)
def test_path_escape_alias_rejected(tree, relative):
    with pytest.raises(m.EvidenceError, match="PATH_ESCAPE_OR_ALIAS"):
        m.checked_path(tree[0], relative)


@pytest.mark.parametrize(
    "relative",
    [
        "artifacts/old/private/raw.json",
        "data/old/file.private.json",
        "artifacts/new/private/unpinned/raw.json",
    ],
)
def test_old_or_unpinned_private_rejected(tree, relative):
    root, _ = tree
    write(root, relative)
    with pytest.raises(m.EvidenceError, match="PRIVATE_PATH_OUTSIDE_ARCHIVE"):
        m.checked_path(root, relative)


@pytest.mark.parametrize("name", ["primary_a60", "reserve_b60", "sealed_cohort"])
def test_sealed_path_rejected(tree, name):
    with pytest.raises(m.EvidenceError, match="SEALED_PATH"):
        m.checked_path(tree[0], f"data/{name}/receipt.json")


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("changed", "FILE_PIN_CHANGED"),
        ("missing", "FILE_MISSING"),
        ("extra", "CLOSURE_MISSING_OR_EXTRA_FILE"),
        ("dependency", "OLD_DEPENDENCY_CHANGED"),
    ],
)
def test_missing_changed_extra_and_frozen_dependency(tree, mutation, code):
    root, manifest = tree
    if mutation == "changed":
        write(root, "artifacts/new/private/archive/reply.private.json", b"changed")
    elif mutation == "missing":
        (root / "data/new/archive/start.safe.json").unlink()
    elif mutation == "extra":
        write(root, "artifacts/new/private/archive/extra.private.json")
    else:
        write(root, "scripts/frozen.py", b"changed")
    with pytest.raises(m.EvidenceError, match=code):
        m.verify_manifest(root, manifest)


def test_manifest_cannot_drop_pin_even_when_resealed(tree):
    root, manifest = tree
    manifest["files"].pop()
    reseal(manifest)
    with pytest.raises(m.EvidenceError, match="CLOSURE_MISSING_OR_EXTRA_FILE"):
        m.verify_manifest(root, manifest)


def test_manifest_cannot_add_unrelated_data_pin(tree):
    root, manifest = tree
    write(root, "data/unrelated.json")
    manifest["files"].append(m.descriptor(root, "data/unrelated.json"))
    reseal(manifest)
    with pytest.raises(m.EvidenceError, match="CLOSURE_MISSING_OR_EXTRA_FILE"):
        m.verify_manifest(root, manifest)


def test_duplicate_pin_rejected_after_resealing(tree):
    root, manifest = tree
    manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    reseal(manifest)
    with pytest.raises(m.EvidenceError, match="DUPLICATE_PATH"):
        m.verify_manifest(root, manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("historical_relocation_chain_verified", True),
        ("historical_relocation_receipt_available", True),
        ("original_operational_gate_passed", True),
        ("first_continuation_operational_gate_passed", True),
        ("full_1470_composite_gate_passed", True),
        ("remaining_count", 389),
    ],
)
def test_manifest_cannot_upgrade_scientific_or_historical_claim(tree, field, value):
    root, manifest = tree
    manifest[field] = value
    reseal(manifest)
    with pytest.raises(m.EvidenceError, match="MANIFEST_BINDING_CHANGED"):
        m.verify_manifest(root, manifest)


def test_manifest_identity_tampering(tree):
    root, manifest = tree
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(m.EvidenceError, match="MANIFEST_IDENTITY_CHANGED"):
        m.verify_manifest(root, manifest)


def test_duplicate_json_key_and_nonfinite_values_rejected():
    with pytest.raises(m.EvidenceError, match="DUPLICATE_JSON_KEY"):
        m._strict_json(b'{"value":1,"value":2}')
    with pytest.raises(m.EvidenceError, match="NONFINITE_JSON"):
        m._strict_json(b'{"value":NaN}')


def test_link_escape_rejected(tree):
    root, manifest = tree
    outside = root / "external"
    outside.mkdir()
    target = outside / "outside.json"
    target.write_text("invented")
    link = root / "data/new/archive/link.json"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("This Windows test account cannot create symlinks")
    with pytest.raises(m.EvidenceError, match="LINK_OR_REPARSE_POINT"):
        m.verify_manifest(root, manifest)


def test_changed_during_hash_rejected(tree, monkeypatch):
    root, _ = tree
    real_sha = hashlib.sha256

    class ChangingHasher:
        def __init__(self):
            self.inner = real_sha()
            self.changed = False

        def update(self, value):
            self.inner.update(value)
            if not self.changed:
                self.changed = True
                with (root / "data/new/archive/start.safe.json").open("ab") as stream:
                    stream.write(b" ")

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(m.hashlib, "sha256", ChangingHasher)
    with pytest.raises(m.EvidenceError, match="CHANGED_DURING_READ"):
        m.descriptor(root, "data/new/archive/start.safe.json")


def test_exclusive_manifest_publication(tree, monkeypatch):
    root, manifest = tree
    monkeypatch.setattr(m, "MANIFEST", "configs/new-manifest.json")
    (root / "configs").mkdir()
    pin = m.write_manifest(root, manifest)
    assert pin == m.descriptor(root, m.MANIFEST)
    assert json.loads((root / m.MANIFEST).read_bytes()) == manifest
    with pytest.raises(m.EvidenceError, match="MANIFEST_ALREADY_EXISTS"):
        m.write_manifest(root, manifest)


def test_existing_history_methods_are_disabled():
    with pytest.raises(m.EvidenceError, match="HISTORY_IS_READ_ONLY"):
        m._deny_operation()


def test_second_abort_changed_is_rejected_before_other_reads():
    target = SimpleNamespace(
        amendment={"prefix_manifest": {"sha256": "1" * 64}},
        read=lambda *args: {"error_code": "wrong failure"},
    )
    frozen = SimpleNamespace(c=SimpleNamespace(same=lambda a, b: a == b), low=None, old=None)
    with pytest.raises(m.EvidenceError, match="SECOND_ABORT_CHANGED"):
        m._verify_failure_chain(target, [], frozen)


@pytest.fixture
def failure_chain(tmp_path):
    epochs = [{"epoch_index": 3, "first_ordinal": 873, "last_ordinal": 1082}]
    rows = [{"synthetic": True}]
    prefix_sha = "1" * 64
    epoch_binding = {"epoch_index": 4, "synthetic": True}
    reservation = {"synthetic_reservation": True}
    records = {
        "generate-aborted.safe.json": {
            "amendment_sha256": m.AMENDMENT_SHA,
            "bound_plan_identity_sha256": m.PLAN_SHA,
            "combined_target_ceiling": 1470,
            "new_target_ceiling": 598,
            "operation": "generate",
            "error_code": "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB",
            "original_contract_sha256": m.PARENT_SHA,
            "prefix_manifest_sha256": prefix_sha,
            "scientific_gate_evaluated": False,
        },
        "generate-started.safe.json": {
            "amendment_sha256": m.AMENDMENT_SHA,
            "original_contract_sha256": m.PARENT_SHA,
            "original_prefix_rows_identity_sha256": m.digest(rows),
            "epoch_schedule": epochs,
            "new_target_ceiling": 598,
            "started_at": "2026-09-05T12:00:00+00:00",
        },
        "epochs/004/resource.safe.json": {
            "baseline": True,
            "contract_sha256": m.PARENT_SHA,
            "epoch_index": 4,
            "disk_free_bytes": 18 * 1024**3,
            "gpu_name": "synthetic",
            "gpu_temperature_c": 33,
            "gpu_total_mib": 8192,
            "gpu_used_mib": 100,
            "sampled_at": "2026-09-05T12:30:00+00:00",
        },
        "epochs/004/amendment.safe.json": epoch_binding,
    }
    for name in ("resource.safe.json", "amendment.safe.json"):
        write(tmp_path, "safe/epochs/004/" + name, b"{}")
    target = SimpleNamespace(
        root=tmp_path,
        amendment={
            "prefix_manifest": {"sha256": prefix_sha},
            "frozen_at_utc": "2026-09-05T11:00:00+00:00",
        },
        config={"execution_limits": {"deadline_utc": "2026-09-05T13:00:00+00:00"}},
        read=lambda area, name: records[name],
        reservation_binding=lambda: {"synthetic_reservation": True},
        verified_epoch=lambda index: {
            "started_at": "2026-09-05T12:01:00+00:00",
            "stopped_at": "2026-09-05T12:29:00+00:00",
        },
        epoch_binding=lambda index: {"epoch_index": 4, "synthetic": True},
        path=lambda area, name: tmp_path / area / name,
    )
    frozen = SimpleNamespace(
        c=SimpleNamespace(same=lambda a, b: m.canonical(a) == m.canonical(b), digest=m.digest),
        low=SimpleNamespace(
            MIN_DISK_BYTES=15 * 1024**3,
            parse_utc=dt.datetime.fromisoformat,
            validate_resource_sample=lambda sample, baseline: m.require(
                sample["gpu_used_mib"] < 1000 and baseline, "SYNTHETIC_GPU_FAILED"
            ),
        ),
        old=SimpleNamespace(read_json=lambda path: reservation),
        loader=SimpleNamespace(owned=lambda root, name: root / name),
        EPOCHS=epochs,
        PRELAUNCH_BYTES=20 * 1024**3,
        file_names=lambda path: {entry.name for entry in path.iterdir()},
    )
    return target, rows, frozen, records, reservation


def test_exact_second_failure_and_original_deadline_are_preserved(failure_chain):
    target, rows, frozen, _, _ = failure_chain
    # Old evidence is accepted against its own historical window, not today's time.
    assert m._verify_failure_chain(target, rows, frozen) is None


@pytest.mark.parametrize(
    "record,field,value,code",
    [
        ("generate-started.safe.json", "new_target_ceiling", 388, "ATTEMPT_BINDING_CHANGED"),
        (
            "generate-started.safe.json",
            "started_at",
            "2026-09-05T14:00:00+00:00",
            "OLD_ATTEMPT_OUTSIDE_WINDOW",
        ),
        (
            "epochs/004/resource.safe.json",
            "disk_free_bytes",
            21 * 1024**3,
            "FAILED_BASELINE_REASON_CHANGED",
        ),
        (
            "epochs/004/resource.safe.json",
            "disk_free_bytes",
            14 * 1024**3,
            "FAILED_BASELINE_REASON_CHANGED",
        ),
        ("epochs/004/resource.safe.json", "epoch_index", 3, "FAILED_BASELINE_BINDING_CHANGED"),
        ("epochs/004/resource.safe.json", "gpu_used_mib", 2000, "SYNTHETIC_GPU_FAILED"),
        (
            "epochs/004/resource.safe.json",
            "sampled_at",
            "2026-09-05T12:02:00+00:00",
            "FAILED_BASELINE_TIME_CHANGED",
        ),
        (
            "epochs/004/resource.safe.json",
            "sampled_at",
            "2026-09-05T14:00:00+00:00",
            "FAILED_BASELINE_TIME_CHANGED",
        ),
        ("epochs/004/amendment.safe.json", "epoch_index", 5, "FAILED_EPOCH_AUTHORITY_CHANGED"),
    ],
)
def test_failure_chain_tampering_rejected(failure_chain, record, field, value, code):
    target, rows, frozen, records, _ = failure_chain
    records[record][field] = value
    with pytest.raises(m.EvidenceError, match=code):
        m._verify_failure_chain(target, rows, frozen)


@pytest.mark.parametrize(
    "area,relative,code",
    [
        ("safe", "epochs/004/unexpected.json", "EXTRA_EPOCH4_FILE"),
        ("private", "epochs/004/reply.private.json", "EPOCH4_PRIVATE_EXISTS"),
        ("safe", "epochs/005/start.safe.json", "UNEXPECTED_FUTURE_STATE"),
        ("safe", "panel/qwen.safe.json", "UNEXPECTED_FUTURE_STATE"),
        ("private", "panel/reply.private.json", "UNEXPECTED_FUTURE_STATE"),
        ("safe", "target-operation.lock.safe.json", "UNEXPECTED_FUTURE_STATE"),
    ],
)
def test_unissued_suffix_cannot_contain_execution_artifacts(failure_chain, area, relative, code):
    target, rows, frozen, _, _ = failure_chain
    write(target.root, area + "/" + relative)
    with pytest.raises(m.EvidenceError, match=code):
        m._verify_failure_chain(target, rows, frozen)


def test_second_reservation_cannot_be_rebound(failure_chain):
    target, rows, frozen, _, reservation = failure_chain
    reservation["synthetic_reservation"] = False
    with pytest.raises(m.EvidenceError, match="RESERVATION_CHANGED"):
        m._verify_failure_chain(target, rows, frozen)


def test_reparse_point_rejected_without_following(tree, monkeypatch):
    root, _ = tree
    original_lstat = Path.lstat

    def flagged_lstat(path):
        observed = original_lstat(path)
        if path.name == "start.safe.json":
            return SimpleNamespace(st_mode=observed.st_mode, st_file_attributes=1024)
        return observed

    monkeypatch.setattr(Path, "lstat", flagged_lstat)
    with pytest.raises(m.EvidenceError, match="LINK_OR_REPARSE_POINT"):
        m.checked_path(root, "data/new/archive/start.safe.json")


@pytest.fixture
def synthetic_history(tree, monkeypatch):
    root, manifest = tree
    plan = {"requests": [{"ordinal": i, "request_id": f"invented-{i}"} for i in range(1, 1471)]}
    rows = copy.deepcopy(plan["requests"][:1082])
    missing = plan["requests"][1082:]
    identities = {
        "original_prefix_rows_identity_sha256": m.digest(rows[:872]),
        "archived_suffix_rows_identity_sha256": m.digest(rows[872:]),
        "combined_rows_identity_sha256": m.digest(rows),
        "remaining_plan_identity_sha256": m.digest(missing),
        "remaining_request_ids_identity_sha256": m.digest([row["request_id"] for row in missing]),
    }
    monkeypatch.setattr(m, "IDENTITIES", identities)
    manifest["retained_identities"] = dict(identities)
    reseal(manifest)
    prompts, census = {"synthetic": "harmless"}, {"rows": [{"synthetic": True}]}
    calls = []
    target = SimpleNamespace(
        root=root,
        paths={area: root / name for area, name in m.UNARCHIVED_ROOTS.items()},
        parent=SimpleNamespace(),
        plan=plan,
        source_context={"synthetic": True},
        load_materials=lambda: prompts,
        load_census=lambda value: census,
        reconcile=lambda materials, measured: rows,
    )
    frozen = SimpleNamespace(
        load_amendment=lambda where, sha: target, c=SimpleNamespace(digest=m.digest)
    )
    monkeypatch.setitem(sys.modules, "pa_llama_topology_target_continuation_v1", frozen)
    monkeypatch.setattr(m, "_verify_failure_chain", lambda *args: calls.append("failure_chain"))
    return root, manifest, target, rows, calls


def test_history_bridge_preserves_context_and_disables_old_mutators(synthetic_history):
    root, manifest, target, rows, calls = synthetic_history
    history = m.load_history(root, manifest)
    assert history.target is target
    assert history.rows1082 == rows
    assert history.prompts == {"synthetic": "harmless"}
    assert history.census == {"rows": [{"synthetic": True}]}
    assert history.source_context == {"synthetic": True}
    assert history.manifest_proof["verified"] is True
    assert calls == ["failure_chain"]
    for worker in (target, target.parent):
        for name in ("write", "dispatch", "generate", "server", "operation"):
            with pytest.raises(m.EvidenceError, match="HISTORY_IS_READ_ONLY"):
                getattr(worker, name)()


def test_history_bridge_rejects_nonempty_original_namespace(synthetic_history):
    root, manifest, _, _, _ = synthetic_history
    write(root, m.UNARCHIVED_ROOTS["safe"] + "/unexpected.json")
    with pytest.raises(m.EvidenceError, match="UNARCHIVED_NAMESPACE_NOT_EMPTY"):
        m.load_history(root, manifest)


@pytest.mark.parametrize("change", ["gap", "duplicate_request", "missing_row", "changed_content"])
def test_history_bridge_rejects_changed_reconciled_frame(synthetic_history, change):
    root, manifest, _, rows, _ = synthetic_history
    if change == "gap":
        rows[-1]["ordinal"] = 1083
    elif change == "duplicate_request":
        rows[-1]["request_id"] = rows[0]["request_id"]
    elif change == "missing_row":
        rows.pop()
    else:
        rows[-1]["new_field"] = "invented"
    with pytest.raises(
        m.EvidenceError, match="RETAINED_PREFIX_NOT_EXACT_1082|STAGE1_IDENTITIES_CHANGED"
    ):
        m.load_history(root, manifest)


def test_archive_mutation_during_raw_verification_is_rejected(synthetic_history):
    root, manifest, target, rows, _ = synthetic_history

    def mutate(materials, census):
        write(root, m.ARCHIVE_ROOTS["safe"] + "/start.safe.json", b"changed during verification")
        return rows

    target.reconcile = mutate
    with pytest.raises(m.EvidenceError, match="FILE_PIN_CHANGED"):
        m.load_history(root, manifest)
