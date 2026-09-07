"""Invented composite targets and fake evaluator I/O only; no live private/model reads."""

import copy
import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "continued_evaluation_synthetic", ROOT / "scripts/pa_llama_topology_continued_evaluation_v1.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
c, p = m.c, m.frozen_finalizer.p
POSITIONS = (0, 3, 4, 10, 11, 14, 15, 16, 18, 21, 22, 23, 24, 25, 33, 34, 36, 37, 42, 43, 44)
EPOCHS = [
    {"epoch_index": 3, "first_ordinal": 873, "last_ordinal": 1082},
    {"epoch_index": 4, "first_ordinal": 1083, "last_ordinal": 1292},
    {"epoch_index": 5, "first_ordinal": 1293, "last_ordinal": 1470},
]


class SyntheticTarget:
    """Trusted-context fake, with explicitly mocked raw verification, never inference."""

    def __init__(self, root):
        self.root = root
        self.amendment = {
            "_amendment_sha256": "a" * 64,
            "frozen": True,
            "execution_authorized": True,
            "frozen_at_utc": "2026-09-05T20:40:00+00:00",
            "required_code": {},
            "epoch_schedule": copy.deepcopy(EPOCHS),
            "prelaunch_minimum_disk_free_bytes": 20 * 1024**3,
        }
        self.paths = {
            "safe": c.contained(
                root,
                "data/natural_language_localization/pa_llama_topology_target_continuation_v1/"
                + "a" * 64,
            ),
            "private": c.contained(
                root, "artifacts/pa_llama_topology_target_continuation_v1/private/" + "a" * 64
            ),
        }
        if os.name == "nt":
            self.paths = {key: Path("\\\\?\\" + str(path)) for key, path in self.paths.items()}
        population = [
            {"payload_position": pos, **{key: c.digest([key, pos]) for key in p.SOURCE_FIELDS}}
            for pos in POSITIONS
        ]
        requests, materials = p._schedule("b" * 64, population)
        self.plan = {
            "plan_identity_sha256": m.PLAN,
            "n": 21,
            "population": population,
            "requests": requests,
            "budgets": p.budgets(21),
            "parent_operational_amendment_disclosure": {
                "screen_amendment": "9" * 64,
                "original_seed11_jailmeter_operational_gate_passed": False,
            },
            "bound_materializations": [
                {
                    "materialization_id": row["materialization_id"],
                    "renderer_row": {"prompt_sha256": c.digest(row), "input_valid": True},
                }
                for row in materials
            ],
        }
        self.config = {
            "schema_version": "jbspan-pa-llama-topology-execution-v1",
            "_contract_sha256": m.PARENT,
            "frozen": True,
            "execution_authorized": True,
            "paper_validity": False,
            "source_bundle_identity_sha256": m.SOURCE_BUNDLE,
            "bound_plan_identity_sha256": m.PLAN,
            "budgets": p.budgets(21),
            "panel_cooldown": copy.deepcopy(m.frozen_panel.COOLDOWN),
            "execution_limits": {"deadline_utc": m.DEADLINE},
            "panel": {
                "qwen": {
                    "max_new_tokens": 128,
                    "do_sample": False,
                    "model_local_path": "synthetic/qwen",
                },
                "jailmeter": {
                    "max_new_tokens": 1536,
                    "temperature": 0,
                    "request_timeout_seconds": 240,
                    "base_metadata_local_path": "synthetic/jm",
                    "runner_path": "synthetic/runner.py",
                },
            },
        }
        self.rows = []
        for item in requests:
            ordinal = item["ordinal"]
            epoch = (
                2
                if ordinal <= 872
                else next(
                    part["epoch_index"]
                    for part in EPOCHS
                    if part["first_ordinal"] <= ordinal <= part["last_ordinal"]
                )
            )
            self.rows.append(
                {
                    **item,
                    "contract_sha256": m.PARENT,
                    "epoch_index": epoch,
                    "process_id": 100 + epoch,
                    "response_sha256": c.digest(["response", ordinal]),
                    "content_sha256": c.digest(["content", ordinal]),
                    "raw_reply_sha256": c.digest(["raw", ordinal]),
                    "eligible_for_panel": item["kind"] == "science",
                    "eligible_for_control": item["kind"] == "control",
                    "completion_cap_reached": False,
                    "finish_reason": "stop",
                }
            )
        self.prefix_manifest = {
            "files": [
                {
                    "kind": "safe",
                    "relative": "generate-aborted.safe.json",
                    "size_bytes": 100,
                    "sha256": "c" * 64,
                },
                {
                    "kind": "safe",
                    "relative": f"target/{requests[872]['request_id']}.cooldown.safe.json",
                    "size_bytes": 200,
                    "sha256": "d" * 64,
                },
            ]
        }
        self.amendment["prefix_manifest"] = {
            "path": "synthetic-prefix.safe.json",
            "size_bytes": len(c.canonical(self.prefix_manifest)) + 1,
            "sha256": c.sha_bytes(c.canonical(self.prefix_manifest) + b"\n"),
        }
        self.proof = self.make_proof()
        self.checked = 0
        self.verified = 0
        self.writes = []
        self.aborted = False
        self.old_gate = False

    def make_proof(self):
        epoch_proofs = []
        for part in EPOCHS:
            index = part["epoch_index"]
            subset = self.rows[part["first_ordinal"] - 1 : part["last_ordinal"]]
            epoch_proofs.append(
                {
                    "epoch_binding": {
                        "amendment_sha256": "a" * 64,
                        "original_contract_sha256": m.PARENT,
                        "bound_plan_identity_sha256": m.PLAN,
                        **part,
                        "prelaunch_minimum_disk_free_bytes": 20 * 1024**3,
                    },
                    "lifecycle": {
                        "contract_sha256": m.PARENT,
                        "epoch": 1,
                        "pid": 100 + index,
                        "owned_process_only": True,
                        "started_at": f"2026-09-05T21:{index:02d}:00+00:00",
                        "stopped_at": f"2026-09-05T21:{index:02d}:59+00:00",
                    },
                    "target_count": len(subset),
                    "target_rows_identity_sha256": c.digest(subset),
                }
            )
        return m.seal(
            {
                "schema_version": m.PROOF_SCHEMA,
                "original_contract_sha256": m.PARENT,
                "amendment_sha256": "a" * 64,
                "bound_plan_identity_sha256": m.PLAN,
                "original_generate_operational_gate_passed": False,
                "original_operational_gate_passed": False,
                "amended_target_frame_verified": True,
                "amended_execution_gate_passed": True,
                "original_prefix_count": 872,
                "continuation_count": 598,
                "rows_identity_sha256": c.digest(self.rows),
                "original_prefix_rows_identity_sha256": c.digest(self.rows[:872]),
                "continuation_rows_identity_sha256": c.digest(self.rows[872:]),
                "prefix_manifest_sha256": self.amendment["prefix_manifest"]["sha256"],
                "original_abort_pin": copy.deepcopy(self.prefix_manifest["files"][0]),
                "failed_predispatch_cooldown_pin": copy.deepcopy(self.prefix_manifest["files"][1]),
                "continuation_epoch_proofs": epoch_proofs,
                "original_prefix_all_reused": True,
                "no_ambiguous_dispatches": True,
                "scientific_rules_unchanged": True,
                "new_model_calls": 0,
                "paper_validity": False,
                "verification_scope": m.SCOPE,
            }
        )

    def assert_amendment_unchanged(self):
        self.checked += 1
        c.require(not self.aborted, "SYNTHETIC_AMENDMENT_ABORTED")

    def verify_composite_targets(self):
        self.verified += 1
        return {"rows": self.rows, "proof": self.proof}

    def summary(self, rows):
        return {
            "operational_gate_passed": self.old_gate,
            "original_generate_operational_gate_passed": False,
            "complete": len(rows) == 1470,
        }

    def path(self, kind, relative):
        if relative.startswith("target/"):
            rid = relative.split("/")[1].split(".")[0]
            ordinal = next(
                item["ordinal"] for item in self.plan["requests"] if item["request_id"] == rid
            )
            if ordinal <= 872:
                return c.contained(self.root, "synthetic-original-private/" + relative)
        return c.contained(self.paths[kind], relative)

    def write(self, kind, relative, value):
        self.writes.append(relative)
        c.write_once(self.path(kind, relative), value)

    @contextmanager
    def operation(self, name):
        self.assert_amendment_unchanged()
        yield


@pytest.fixture
def synthetic_target(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "source_pin", lambda target: None)
    return SyntheticTarget(tmp_path)


def test_full1470_explicit_new_gate_preserves_old_false(synthetic_target):
    rows, proof = m.verify_target_frame(synthetic_target)
    assert len(rows) == 1470 and len(m.frozen_panel.science_frame(synthetic_target.plan)) == 882
    assert proof["original_prefix_count"] == 872 and proof["continuation_count"] == 598
    assert synthetic_target.summary(rows)["operational_gate_passed"] is False
    assert [
        len([r for r in rows[:872] if r["kind"] == kind]) for kind in ("science", "control")
    ] == [536, 336]


@pytest.mark.parametrize(
    "field,value",
    [
        ("original_generate_operational_gate_passed", True),
        ("original_operational_gate_passed", True),
        ("amended_target_frame_verified", False),
        ("amended_execution_gate_passed", False),
        ("original_prefix_count", 871),
        ("continuation_count", 599),
        ("no_ambiguous_dispatches", False),
        ("original_prefix_all_reused", False),
        ("scientific_rules_unchanged", False),
        ("amendment_sha256", "f" * 64),
        ("verification_scope", "ORIGINAL_PASS"),
        ("prefix_manifest_sha256", "f" * 64),
    ],
)
def test_coherently_rehashed_proof_scope_changes_rejected(synthetic_target, field, value):
    synthetic_target.proof[field] = value
    m.seal(synthetic_target.proof)
    with pytest.raises(c.DevelopmentError):
        m.verify_target_frame(synthetic_target)


@pytest.mark.parametrize("key", ["original_abort_pin", "failed_predispatch_cooldown_pin"])
def test_coherently_rehashed_wrong_failure_pin_rejected(synthetic_target, key):
    synthetic_target.proof[key]["sha256"] = "e" * 64
    m.seal(synthetic_target.proof)
    with pytest.raises(c.DevelopmentError, match="FAILED_EPOCH_PIN"):
        m.verify_target_frame(synthetic_target)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["continuation_epoch_proofs"].pop(),
        lambda p: p["continuation_epoch_proofs"].reverse(),
        lambda p: p["continuation_epoch_proofs"][0]["epoch_binding"].update(first_ordinal=874),
        lambda p: p["continuation_epoch_proofs"][0].update(target_count=209),
        lambda p: p["continuation_epoch_proofs"][0].update(target_rows_identity_sha256="e" * 64),
        lambda p: p["continuation_epoch_proofs"][0]["lifecycle"].update(pid=999),
    ],
)
def test_coherent_epoch_proof_tamper_rejected(synthetic_target, mutation):
    mutation(synthetic_target.proof)
    m.seal(synthetic_target.proof)
    with pytest.raises(c.DevelopmentError):
        m.verify_target_frame(synthetic_target)


@pytest.mark.parametrize(
    "reason",
    ["partial", "duplicate", "raw_digest", "old_gate", "aborted", "unfrozen", "wrong_namespace"],
)
def test_invalid_context_stops_before_evaluator_work(synthetic_target, monkeypatch, reason):
    if reason == "partial":
        synthetic_target.rows.pop()
    elif reason == "duplicate":
        synthetic_target.rows[1] = copy.deepcopy(synthetic_target.rows[0])
        synthetic_target.proof = synthetic_target.make_proof()
    elif reason == "raw_digest":
        synthetic_target.rows[0]["raw_reply_sha256"] = "e" * 64
    elif reason == "old_gate":
        synthetic_target.old_gate = True
    elif reason == "aborted":
        synthetic_target.aborted = True
    elif reason == "unfrozen":
        synthetic_target.amendment["frozen"] = False
    else:
        synthetic_target.paths["safe"] = c.contained(synthetic_target.root, "original-v1")
    monkeypatch.setattr(m.low, "preflight", lambda *_: pytest.fail("no evaluator work before gate"))
    with pytest.raises(c.DevelopmentError):
        panel = m.AmendedTopologyPanel(synthetic_target, {})
        panel.load("qwen")


@pytest.mark.parametrize("axis", ["qwen", "jailmeter"])
def test_actual_load_reads_only_science_and_uses_original_preparation(
    synthetic_target, monkeypatch, axis
):
    reads, tokenizer_calls, prepared = [], [], []
    monkeypatch.setattr(m.low, "preflight", lambda *_: None)
    monkeypatch.setattr(
        m.low, "read_bytes", lambda path, *_args, **_kw: reads.append(str(path)) or b"synthetic"
    )
    helper = SimpleNamespace(extract_system_prompt=lambda path: "frozen synthetic system")
    monkeypatch.setattr(m.low, "load_pure_functions", lambda *_: helper)
    token = object()
    tokenizer = SimpleNamespace(
        from_pretrained=lambda *args, **kw: tokenizer_calls.append((args, kw)) or token
    )
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=tokenizer))

    def prepare(*args):
        prepared.append(args)
        return ["prepared"]

    monkeypatch.setattr(m.frozen_panel, "prepare_values", prepare)
    payloads = {pos: "unchanged synthetic original P" for pos in POSITIONS}
    panel = m.AmendedTopologyPanel(synthetic_target, payloads)
    assert panel.load(axis) == (["prepared"], helper, token)
    assert len(reads) == 882
    science = m.frozen_panel.science_frame(synthetic_target.plan)
    assert {Path(path).name.split(".")[0] for path in reads} == {r["request_id"] for r in science}
    assert sum("synthetic-original-private" in path for path in reads) == 536
    assert prepared[0][3] == payloads and prepared[0][7] == axis
    assert tokenizer_calls[0][1] == (
        {"local_files_only": True}
        if axis == "qwen"
        else {"local_files_only": True, "trust_remote_code": True}
    )


def test_inherited_numerical_execution_is_exact_same_function():
    for name in ("worker", "lifecycle", "collect", "census", "resources"):
        assert getattr(m.AmendedTopologyPanel, name) is getattr(m.frozen_panel.TopologyPanel, name)


def test_jailmeter_requires_qwen_first(synthetic_target, monkeypatch):
    panel = m.AmendedTopologyPanel(synthetic_target, {})
    called = []
    monkeypatch.setattr(panel, "verify", lambda axis: called.append(("verify", axis)))
    monkeypatch.setattr(
        m.frozen_panel.TopologyPanel, "run", lambda self, axis: called.append(("run", axis))
    )
    panel.run("jailmeter")
    assert called == [("verify", "qwen"), ("run", "jailmeter")]


@pytest.mark.parametrize("where", ["axis", "operation"])
def test_new_axis_abort_rejects_before_any_evaluator_work(synthetic_target, monkeypatch, where):
    panel = m.AmendedTopologyPanel(synthetic_target, {})
    path = (
        panel.path("qwen", "abort.safe.json")
        if where == "axis"
        else synthetic_target.path("safe", "panel-qwen-aborted.safe.json")
    )
    c.write_once(path, {"synthetic_abort": True})
    monkeypatch.setattr(m.low, "preflight", lambda *_: pytest.fail("must not load evaluator"))
    with pytest.raises(c.DevelopmentError, match="NEW_ABORT_NO_REENTRY"):
        panel.load("qwen")


@pytest.mark.parametrize(
    "axis,start,sample,qwen_dispatched,expected_error",
    [
        ("qwen", "20:39:59", "20:39:58", 0, "START_BEFORE"),
        ("qwen", "21:05:58", "21:05:58", 0, "START_BEFORE"),
        ("qwen", "21:06:00", "21:05:58", 0, "SAMPLE_BEFORE"),
        ("qwen", "21:06:00", "21:05:59", 0, None),
        ("jailmeter", "21:09:59", "21:09:59", 1, "START_BEFORE"),
        ("jailmeter", "21:10:01", "21:09:59", 1, "SAMPLE_BEFORE"),
        ("jailmeter", "21:10:01", "21:10:00", 1, None),
        ("jailmeter", "21:06:00", "21:05:59", 0, None),
    ],
)
def test_explicit_amendment_and_target_and_qwen_release_time_lower_bounds(
    synthetic_target, monkeypatch, axis, start, sample, qwen_dispatched, expected_error
):
    panel = m.AmendedTopologyPanel(synthetic_target, {})
    panel._target_proof = synthetic_target.proof
    verified = []
    monkeypatch.setattr(
        panel,
        "verify",
        lambda selected: verified.append(selected) or {"dispatched": qwen_dispatched},
    )

    def read(path):
        return (
            {"started_at": f"2026-09-05T{start}+00:00"}
            if path.name == "worker.started.safe.json"
            else {"stopped_at": "2026-09-05T21:10:00+00:00"}
        )

    monkeypatch.setattr(m.low, "read_json", read)
    monkeypatch.setattr(
        m.low,
        "read_bytes",
        lambda *_a, **_kw: c.canonical({"recorded_at": f"2026-09-05T{sample}+00:00"}) + b"\n",
    )
    if expected_error:
        with pytest.raises(c.DevelopmentError, match=expected_error):
            panel.temporal_order(axis, {"dispatched": 1})
    else:
        panel.temporal_order(axis, {"dispatched": 1})
    assert verified == (["qwen"] if axis == "jailmeter" else [])


def test_skip_only_axis_has_no_invented_temporal_worker(synthetic_target, monkeypatch):
    panel = m.AmendedTopologyPanel(synthetic_target, {})
    panel._target_proof = synthetic_target.proof
    monkeypatch.setattr(panel, "verify", lambda _: {"dispatched": 0})
    monkeypatch.setattr(m.low, "read_json", lambda *_: pytest.fail("no invented worker"))
    monkeypatch.setattr(m.low, "read_bytes", lambda *_a, **_kw: pytest.fail("no invented samples"))
    panel.temporal_order("qwen", {"dispatched": 0})
    panel.temporal_order("jailmeter", {"dispatched": 0})


def test_actual_source_pin_missing_stops(tmp_path):
    target = SyntheticTarget(tmp_path)
    with pytest.raises(c.DevelopmentError, match="SELF_PIN_REQUIRED"):
        m.source_pin(target)


def fake_axis(target, axis):
    return {
        "schema_version": m.AXIS_SCHEMA,
        "axis": axis,
        **m.disclosure(target.proof),
        "rows": [],
        "complete": True,
    }


def pure_products(target, analysis=True):
    tables = m.seal(
        {
            "schema_version": "old-table",
            "primary_rows": [],
            "slice_rows": [],
            "control_qualified_slice_rows": [],
        }
    )
    measured = m.seal(
        {
            "schema_version": "old-measured",
            "tables": tables,
            "scientific_rows": [],
            "control_rows": [],
        }
    )
    analyzed = (
        m.seal(
            {
                "schema_version": "old-analysis",
                "upstream_declared_topology_aggregate_identity_sha256": tables[
                    "result_identity_sha256"
                ],
                "normalized_analysis_input_identity_sha256": "f" * 64,
            }
        )
        if analysis
        else None
    )
    result = m.seal(
        {
            "schema_version": "old-result",
            "measurements_identity_sha256": measured["result_identity_sha256"],
            "table_identity_sha256": tables["result_identity_sha256"],
            "analysis_identity_sha256": analyzed["result_identity_sha256"] if analyzed else None,
            "analysis_complete": analysis,
            "parent_operational_amendment_disclosure": target.plan[
                "parent_operational_amendment_disclosure"
            ],
        }
    )
    return {"measurements": measured, "analysis": analyzed, "result": result}


@pytest.mark.parametrize("analysis", [True, False])
def test_all_products_new_schemas_and_cross_hashes(synthetic_target, analysis):
    axes = {axis: fake_axis(synthetic_target, axis) for axis in ("qwen", "jailmeter")}
    before = pure_products(synthetic_target, analysis)
    after = m.decorate_products(before, axes, synthetic_target.proof)
    for _key, value in after.items():
        if value is None:
            continue
        assert "continued" in value["schema_version"]
        assert value["target_operational_amendment_disclosure"] == synthetic_target.proof
        assert value["original_target_operational_gate_passed"] is False
        assert value["result_identity_sha256"] == c.digest(
            {k: v for k, v in value.items() if k != "result_identity_sha256"}
        )
    tables = after["measurements"]["tables"]
    assert (
        tables["result_identity_sha256"]
        != before["measurements"]["tables"]["result_identity_sha256"]
    )
    assert after["result"]["table_identity_sha256"] == tables["result_identity_sha256"]
    assert (
        after["result"]["measurements_identity_sha256"]
        == after["measurements"]["result_identity_sha256"]
    )
    assert after["result"]["axis_identity_sha256"] == {
        axis: c.digest(value) for axis, value in axes.items()
    }
    assert (
        after["result"]["parent_operational_amendment_disclosure"]
        != after["result"]["target_operational_amendment_disclosure"]
    )
    if analysis:
        assert (
            after["analysis"]["upstream_declared_topology_aggregate_identity_sha256"]
            == tables["result_identity_sha256"]
        )
        assert (
            after["result"]["analysis_identity_sha256"]
            == after["analysis"]["result_identity_sha256"]
        )
        assert (
            after["analysis"]["normalized_analysis_input_identity_sha256"]
            == before["analysis"]["normalized_analysis_input_identity_sha256"]
        )
    else:
        assert after["analysis"] is None and after["result"]["analysis_identity_sha256"] is None


def test_scientific_projection_never_publishes_old_axis_or_erases_original_failure(
    synthetic_target,
):
    axis = fake_axis(synthetic_target, "qwen")
    before = copy.deepcopy(axis)
    projected = m.scientific_axis_projection(axis, "qwen", synthetic_target.proof)
    assert projected["schema_version"] == "jbspan-pa-llama-topology-panel-axis-v1"
    assert not set(projected) & m.DISCLOSURE_KEYS
    assert axis == before and axis["original_target_operational_gate_passed"] is False
    axis["target_execution_amendment_sha256"] = "e" * 64
    with pytest.raises(c.DevelopmentError):
        m.scientific_axis_projection(axis, "qwen", synthetic_target.proof)


def published_products(target):
    axes = {axis: fake_axis(target, axis) for axis in ("qwen", "jailmeter")}
    products = m.decorate_products(pure_products(target), axes, target.proof)
    products["verification"] = {
        "schema_version": "jbspan-pa-llama-topology-continued-final-verification-v1",
        **m.disclosure(target.proof),
        "parent_operational_amendment_disclosure": target.plan[
            "parent_operational_amendment_disclosure"
        ],
        "original_target_operational_pass_claimed": False,
        "original_v1_finalization_pass_claimed": False,
        "epoch_invariance_or_independent_epoch_replication_claimed": False,
        "analysis_complete": True,
    }
    reseal_publication(products)
    return products


def reseal_publication(products):
    """Coherent outer hash changes must not erase inner join contradictions."""
    proof = products["verification"]
    core = {k: v for k, v in products.items() if k != "verification" and v is not None}
    for value in core.values():
        m.seal(value)
    proof.update(
        result_identity_sha256=products["result"]["result_identity_sha256"],
        product_identity_sha256={k: v["result_identity_sha256"] for k, v in core.items()},
        product_file_sha256={k: c.sha_bytes(c.canonical(v) + b"\n") for k, v in core.items()},
        axis_identity_sha256=products["result"]["axis_identity_sha256"],
    )
    m.seal(proof, "verification_identity_sha256")


def test_publish_proof_last_and_idempotent_exact_bytes(synthetic_target):
    products = published_products(synthetic_target)
    m.publish(synthetic_target, products)
    assert synthetic_target.writes == list(m.OUTPUTS.values())
    m.publish(synthetic_target, products)
    assert len(synthetic_target.writes) == 4


@pytest.mark.parametrize("key", m.OUTPUTS)
@pytest.mark.parametrize("suffix", [b"\r\n", b" \n"])
def test_noncanonical_existing_product_never_overwritten(synthetic_target, key, suffix):
    products = published_products(synthetic_target)
    m.publish(synthetic_target, products)
    path = synthetic_target.path("safe", m.OUTPUTS[key])
    path.write_bytes(c.canonical(products[key]) + suffix)
    synthetic_target.writes.clear()
    with pytest.raises(c.DevelopmentError, match="EXISTING_PRODUCT_BYTES_CHANGED"):
        m.publish(synthetic_target, products)
    assert not synthetic_target.writes


def test_orphan_proof_never_repaired(synthetic_target):
    products = published_products(synthetic_target)
    synthetic_target.write("safe", m.OUTPUTS["verification"], products["verification"])
    synthetic_target.writes.clear()
    with pytest.raises(c.DevelopmentError, match="ORPHAN_PROOF"):
        m.publish(synthetic_target, products)
    assert not synthetic_target.writes


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["result"].update(table_identity_sha256="e" * 64),
        lambda p: p["result"].update(measurements_identity_sha256="e" * 64),
        lambda p: p["result"].update(analysis_identity_sha256="e" * 64),
        lambda p: p["analysis"].update(
            upstream_declared_topology_aggregate_identity_sha256="e" * 64
        ),
        lambda p: p["result"].update(analysis_complete=False),
        lambda p: p["result"].update(original_v1_finalization_pass_claimed=True),
        lambda p: p["verification"].update(parent_operational_amendment_disclosure={}),
        lambda p: p["verification"].update(original_target_operational_pass_claimed=True),
        lambda p: p["measurements"]["tables"].update(target_execution_amendment_sha256="e" * 64),
    ],
)
def test_coherent_outer_hashes_cannot_hide_inner_joins_or_failure_drift(synthetic_target, mutation):
    products = published_products(synthetic_target)
    mutation(products)
    m.seal(products["measurements"]["tables"])
    reseal_publication(products)
    with pytest.raises(c.DevelopmentError):
        m.publish(synthetic_target, products)
    assert not synthetic_target.writes


def test_missing_evaluator_prevents_any_finalization(synthetic_target, monkeypatch):
    class Incomplete:
        def __init__(self, *_):
            pass

        def verify(self, axis):
            raise c.DevelopmentError("SYNTHETIC_AXIS_INCOMPLETE")

    monkeypatch.setattr(m, "AmendedTopologyPanel", Incomplete)
    monkeypatch.setattr(
        m.frozen_finalizer, "build_artifacts", lambda *_a, **_k: pytest.fail("cannot build")
    )
    with pytest.raises(c.DevelopmentError, match="AXIS_INCOMPLETE"):
        m.finalize(synthetic_target, {}, {})
    assert not synthetic_target.writes


def test_finalizer_orchestration_full_target_both_axes_disclosure_and_proof_last(
    synthetic_target, monkeypatch
):
    observed = []

    class Complete:
        def __init__(self, target, _payloads):
            self._target_proof = target.proof

        def verify(self, axis):
            observed.append(axis)
            return fake_axis(synthetic_target, axis)

    monkeypatch.setattr(m, "AmendedTopologyPanel", Complete)
    monkeypatch.setattr(m.low, "load_pure_functions", lambda *_: object())
    monkeypatch.setattr(
        m.materialize,
        "load",
        lambda *_: SimpleNamespace(
            tasks=[{"id": task, "text": "synthetic benign"} for task in p.TASKS]
        ),
    )
    reads = []
    monkeypatch.setattr(
        m.low,
        "read_bytes",
        lambda path, *_a, **_kw: reads.append(str(path)) or b"synthetic benign raw",
    )

    def build(config, plan, context, rows, axes, helpers, raw, tasks, **kw):
        assert len(rows) == 1470 and len(raw) == 588
        assert axes["qwen"]["schema_version"] == "jbspan-pa-llama-topology-panel-axis-v1"
        assert not kw["run_analysis"]
        return pure_products(synthetic_target, analysis=False)

    monkeypatch.setattr(m.frozen_finalizer, "build_artifacts", build)
    output = m.finalize(synthetic_target, {}, {}, run_analysis=False)
    assert observed == ["qwen", "jailmeter"] and len(reads) == 588
    assert sum("synthetic-original-private" in path for path in reads) == 336
    assert output["analysis_complete"] is False and output["analysis_identity_sha256"] is None
    assert output["original_target_operational_gate_passed"] is False
    assert synthetic_target.writes[-1] == m.OUTPUTS["verification"]
    proof = c.strict_json(synthetic_target.path("safe", m.OUTPUTS["verification"]).read_bytes())
    assert proof["original_target_operational_pass_claimed"] is False
    assert set(proof["product_file_sha256"]) == {"measurements", "result"}
    for key, sha in proof["product_file_sha256"].items():
        assert c.sha_bytes(synthetic_target.path("safe", m.OUTPUTS[key]).read_bytes()) == sha
