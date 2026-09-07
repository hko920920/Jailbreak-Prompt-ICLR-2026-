"""Synthetic loader contracts/receipts only; parent verifier/model entrypoints are mocked."""

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "synthetic_topology_execution", SCRIPTS / "pa_llama_topology_execution_v1.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
c = m.c
REAL_PARENT_VERIFY = m.verify_parent_evidence


def seal(value, key):
    value[key] = c.digest({name: item for name, item in value.items() if name != key})


@pytest.fixture
def state(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("x")

    def put(relative, value, *, raw=False):
        c.write_once(m.owned(root, relative), value, raw=raw)
        return m.file_descriptor(root, relative)

    inventory = {"rows": [], "rows_sha256": c.digest([])}
    inventory_pin = put("data/synthetic-inventory.safe.json", inventory)
    inputs = [{"payload_position": 3, "condition": "DIRECT", "payload": "Synthetic P"}]
    input_pin = put(m.NEW_INPUT_PATH, {"rows": inputs})
    receipt = {"private_input_sha256": input_pin["sha256"]}
    receipt_raw = c.canonical(receipt)
    receipt_pin = put(m.NEW_INPUT_RECEIPT, receipt_raw + b" " * (555 - len(receipt_raw)), raw=True)
    parent = {
        "source_inventory": inventory_pin,
        "required_code": {},
        "model": {"alias": "synthetic"},
        "runtime": {"synthetic": True},
        "server": {"host": "127.0.0.1"},
        "panel": {"temperature": 0.0},
        "software": {"synthetic": "1"},
        "generation": {"temperature": 0.7, "top_p": 0.9},
        "context_tokens": 4096,
        "seeds": [11, 23, 47],
        "execution_limits": {"deadline_utc": "2026-09-05T22:55:47+00:00"},
    }
    parent_pin = put(c.CONFIG, parent)
    parent["_contract_sha256"] = parent_pin["sha256"]
    amendment = {"required_code": {}, "frozen_at_utc": "2026-09-05T17:43:37+00:00"}
    amendment_pin = put(m.continuation.CONFIG, amendment)
    amendment["_amendment_sha256"] = amendment_pin["sha256"]
    monkeypatch.setattr(m, "PARENT_SHA", parent_pin["sha256"])
    monkeypatch.setattr(m, "AMENDMENT_SHA", amendment_pin["sha256"])
    monkeypatch.setattr(m, "NEW_INPUT_SHA", input_pin["sha256"])
    monkeypatch.setattr(m, "NEW_INPUT_BYTES", input_pin["size_bytes"])
    monkeypatch.setattr(m, "NEW_INPUT_RECEIPT_SHA", receipt_pin["sha256"])
    phases = {}
    for seed in (11, 23, 47):
        phases[str(seed)] = {
            kind: put(m.phase_path(seed, kind), {"seed": seed, "kind": kind})
            for kind in m.PHASE_KINDS
        }
    bundle = {
        "schema_version": m.BUNDLE_SCHEMA,
        "parent_contract": parent_pin,
        "operational_amendment": amendment_pin,
        "source_inventory": inventory_pin,
        "new_screen_inputs": input_pin,
        "new_screen_input_receipt": receipt_pin,
        "phases": phases,
        "raw_parent_receipts_reverified": True,
        "historical_private_reads": 0,
        "sealed_reads": 0,
        "new_model_calls": 0,
        "execution_authorized": False,
    }
    seal(bundle, "source_bundle_identity_sha256")
    calls = []
    plan = {
        "n": 6,
        "population": [{"payload_position": 3}],
        "plan_identity_sha256": "1" * 64,
        "materializations_bound": False,
        "budgets": {"total_target_calls": 420},
    }
    bound = {**plan, "plan_identity_sha256": "2" * 64, "materializations_bound": True}
    prepared = {
        "bound_plan": bound,
        "private_materializations": {
            "rows": [{"materialization_id": "3" * 64, "prompt": "Synthetic private material"}]
        },
        "new_screen_input_sha256": input_pin["sha256"],
        "historical_private_reads": 0,
        "model_calls": 0,
        "execution_authorized": False,
    }

    def build(**context):
        calls.append("final47_safe_gate")
        assert context["final_result"]["seed"] == 47
        return copy.deepcopy(plan)

    monkeypatch.setattr(c, "load_contract", lambda *args: copy.deepcopy(parent))
    monkeypatch.setattr(m.continuation, "load_amendment", lambda *args: copy.deepcopy(amendment))
    monkeypatch.setattr(m.parent_target, "input_receipt", lambda *args: copy.deepcopy(receipt))
    monkeypatch.setattr(
        m.parent_finalizer, "validate_previous", lambda *args: calls.append("proof")
    )
    monkeypatch.setattr(m.plan_module, "build_plan", build)
    monkeypatch.setattr(
        m, "verify_parent_evidence", lambda *args: calls.append("raw_replay") or inputs
    )
    monkeypatch.setattr(m.renderer_module, "load", lambda root: SimpleNamespace(synthetic=True))
    monkeypatch.setattr(m.target_module, "prepare_materials", lambda *args: copy.deepcopy(prepared))
    for path in sorted(m.NEW_CODE):
        put(path, b"# Synthetic pinned fixture source only\n", raw=True)
    put(m.PROTOCOL, b"Synthetic approved protocol\n", raw=True)
    monkeypatch.setattr(m, "__file__", str(root / m.SCRIPT))
    return SimpleNamespace(
        root=root,
        put=put,
        bundle=bundle,
        parent=parent,
        amendment=amendment,
        inputs=inputs,
        prepared=prepared,
        plan=plan,
        calls=calls,
    )


def frozen_config(state, mutation=None):
    m.prepare(state.root)
    preparation = m.load_preparation(state.root, state.bundle["source_bundle_identity_sha256"])
    config = m.make_template(state.root, preparation)
    config.update(frozen=True, execution_authorized=True, frozen_at_utc="2026-09-05T20:00:00+00:00")
    if mutation:
        mutation(config)
    pin = state.put(m.CONFIG, config)
    return config, pin["sha256"]


def test_literal_parent_and_private_pins_are_explicit():
    assert m.PARENT_SHA == "49bfa0302681971ed49150a95d3a300d3f8f4bc85e0fe483ec73ebd39e1b7139"
    assert m.NEW_INPUT_SHA == "9c803db7fa8a5a17a20d2774d8760cae609608b50a3e00fa50e8ec69677adfda"
    assert m.NEW_INPUT_PATH.endswith("/" + m.PARENT_SHA + "/inputs.private.json")
    assert m.NEW_INPUT_BYTES == 140072


def test_loader_never_calls_historical_extractor_or_parent_execution():
    tree = ast.parse((SCRIPTS / "pa_llama_topology_execution_v1.py").read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {"extract_input", "prepare_inputs", "run_phase", "aggregate", "Popen"}
    parent_runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"parent_target", "parent_panel", "continuation"}
    ]
    assert not parent_runs


def test_source_bundle_all_nine_pins_and_raw_replay(state):
    discovered = m.discover_sources(state.root)
    assert discovered == state.bundle
    loaded = m.load_sources(state.root, discovered)
    assert loaded["inputs"] == state.inputs
    assert loaded["source_context"]["verified_operational_amendment_sha256s"] == [m.AMENDMENT_SHA]
    assert state.calls[0] == "final47_safe_gate" and state.calls[-1] == "raw_replay"


def test_failed_final47_gate_precedes_every_new_private_read(state, monkeypatch):
    opened = []
    original = m.read_pin

    def observe(root, pin, path):
        opened.append(path)
        return original(root, pin, path)

    def reject(**context):
        raise c.DevelopmentError("FEWER_THAN_SIX_CERTIFIED_PAIRS_NO_TOPOLOGY")

    monkeypatch.setattr(m, "read_pin", observe)
    monkeypatch.setattr(m.plan_module, "build_plan", reject)
    with pytest.raises(c.DevelopmentError, match="FEWER_THAN_SIX"):
        m.load_sources(state.root, state.bundle)
    assert m.NEW_INPUT_PATH not in opened and not any("private" in path for path in opened)
    assert "raw_replay" not in state.calls


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_phase",
        "drop_proof",
        "old_private",
        "changed_input",
        "promote",
        "bool_count",
        "extra_raw",
        "wrong_receipt",
    ],
)
def test_source_bundle_scope_cannot_be_coherently_rehashed(state, mutation):
    bundle = copy.deepcopy(state.bundle)
    if mutation == "drop_phase":
        bundle["phases"].pop("23")
    elif mutation == "drop_proof":
        bundle["phases"]["47"].pop("verification")
    elif mutation == "old_private":
        bundle["new_screen_inputs"]["path"] = "artifacts/original/private/old.json"
    elif mutation == "changed_input":
        bundle["new_screen_inputs"]["sha256"] = "0" * 64
    elif mutation == "promote":
        bundle["execution_authorized"] = True
    elif mutation == "bool_count":
        bundle["new_model_calls"] = False
    elif mutation == "extra_raw":
        bundle["prompt"] = "Forbidden"
    else:
        bundle["new_screen_input_receipt"]["sha256"] = "0" * 64
    seal(bundle, "source_bundle_identity_sha256")
    with pytest.raises(c.DevelopmentError):
        m.load_sources(state.root, bundle)


def test_preparation_is_write_once_new_namespace_and_execution_disabled(state):
    report = m.prepare(state.root)
    assert report["execution_authorized"] is False and report["new_model_calls"] == 0
    assert "Synthetic private material" not in json.dumps(report)
    sha = report["source_bundle_identity_sha256"]
    loaded = m.load_preparation(state.root, sha)
    assert loaded["prepared"] == state.prepared
    assert loaded["receipt"]["execution_authorized"] is False
    with pytest.raises(FileExistsError):
        m.prepare(state.root)


def test_template_preserves_decimal_lexical_identity_without_authority(state):
    m.prepare(state.root)
    template = m.make_template(
        state.root, m.load_preparation(state.root, state.bundle["source_bundle_identity_sha256"])
    )
    assert template["frozen"] is False and template["execution_authorized"] is False
    assert type(template["panel"]["temperature"]) is float
    assert '"temperature": 0.0' in json.dumps(template)
    assert template["paths"]["safe_root"] == m.target_module.SAFE_ROOT
    assert {pin["path"] for pin in template["required_code"].values()} == m.NEW_CODE


def test_exact_frozen_contract_validates_without_execution(state):
    config, sha = frozen_config(state)
    loaded = m.validate_execution(state.root, sha)
    assert loaded["config"] == {**config, "_contract_sha256": sha}
    result = m.execute_command(state.root, sha, "preflight")
    assert result["preflight_passed"] is True and result["new_model_calls"] == 0
    assert not m.owned(state.root, m.target_module.SAFE_ROOT).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("frozen", False),
        ("execution_authorized", False),
        ("paper_validity", True),
        ("generation", {"temperature": 0}),
        ("budgets", {"total_target_calls": 999}),
        ("context_tokens", 8192),
        ("seeds", [11]),
        ("cooldown", {}),
        ("panel_cooldown", {}),
        ("raw_prompt", "Forbidden"),
        ("_contract_sha256", "0" * 64),
        ("frozen_at_utc", "2026-09-05T23:00:00+00:00"),
        ("paths", {"safe_root": "data/old", "private_root": "artifacts/old"}),
    ],
)
def test_frozen_execution_contract_rejects_changed_policy_or_authority(state, field, value):
    _, sha = frozen_config(state, lambda config: config.update({field: value}))
    with pytest.raises(c.DevelopmentError):
        m.validate_execution(state.root, sha)


def test_wrong_raw_config_sha_stops_before_new_input_reads(state, monkeypatch):
    frozen_config(state)
    monkeypatch.setattr(
        m, "load_preparation", lambda *args, **kwargs: pytest.fail("No source reads")
    )
    with pytest.raises(c.DevelopmentError, match="EXECUTION_CONFIG_SHA_MISMATCH"):
        m.validate_execution(state.root, "0" * 64)


def test_missing_required_code_rejected_before_preparation(state, monkeypatch):
    _, sha = frozen_config(
        state, lambda config: config["required_code"].pop(next(iter(config["required_code"])))
    )
    monkeypatch.setattr(
        m, "load_preparation", lambda *args, **kwargs: pytest.fail("No source reads")
    )
    with pytest.raises(c.DevelopmentError, match="ALL_NEW_TOPOLOGY_CODE"):
        m.validate_execution(state.root, sha)


def test_changed_code_bytes_rejected_before_preparation(state, monkeypatch):
    _, sha = frozen_config(
        state,
        lambda config: config["required_code"][next(iter(config["required_code"]))].update(
            sha256="0" * 64
        ),
    )
    monkeypatch.setattr(
        m, "load_preparation", lambda *args, **kwargs: pytest.fail("No source reads")
    )
    with pytest.raises(c.DevelopmentError, match="PIN_SHA_MISMATCH"):
        m.validate_execution(state.root, sha)


def test_cli_failure_never_prints_private_exception_text(monkeypatch, capsys):
    monkeypatch.setattr(
        m,
        "prepare",
        lambda root: (_ for _ in ()).throw(ValueError("Sensitive private text must not appear")),
    )
    assert m.main(["prepare", "--root", "synthetic"]) == 1
    value = capsys.readouterr().out
    assert "Sensitive" not in value and json.loads(value)["completed"] is False


def test_cli_does_not_have_implicit_resume_or_unbounded_extra_call_flags(capsys):
    with pytest.raises(SystemExit):
        m.main(["generate", "--root", "synthetic", "--resume", "--extra-calls", "5"])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "fault", [None, "measurement", "result", "proof", "missing_target", "global"]
)
def test_real_parent_verifier_orchestration_rebuilds_all_three_phases(state, monkeypatch, fault):
    observed = []
    phases = {
        str(seed): {kind: {"seed": seed, "kind": kind} for kind in m.PHASE_KINDS}
        for seed in (11, 23, 47)
    }

    def phase_plan(parent, inventory, seed, previous):
        observed.append(("plan", seed, previous))
        return {"phase_seed": seed, "rows": [{"request_id": c.digest([seed, "target"])}]}

    for seed in (11, 23, 47):
        state.put(f"{m.PARENT_SAFE}/phase_{seed}_plan.safe.json", phase_plan({}, {}, seed, None))
    observed.clear()
    monkeypatch.setattr(c, "phase_plan", phase_plan)
    monkeypatch.setattr(m.parent_target, "helper_for", lambda *args: "synthetic_helper")
    monkeypatch.setattr(m.parent_target, "load_inputs", lambda *args: state.inputs)
    monkeypatch.setattr(m.parent_target, "load_census", lambda *args: {"synthetic_census": True})
    monkeypatch.setattr(m.parent_panel, "load_pure_functions", lambda *args: "synthetic_functions")

    def qwen(root, parent, plan, axis):
        observed.append(("axis", plan["phase_seed"], axis))
        return {"axis": axis, "seed": plan["phase_seed"]}

    def jailmeter(root, parent, amendment, plan):
        observed.append(("axis", plan["phase_seed"], "jailmeter"))
        return {"axis": "jailmeter", "seed": plan["phase_seed"]}

    def target(root, parent, plan, inputs, census, helper):
        assert inputs == state.inputs and census == {"synthetic_census": True}
        assert helper == "synthetic_helper"
        observed.append(("target", plan["phase_seed"]))
        return [] if fault == "missing_target" else plan["rows"]

    def rebuild(
        parent, amendment, inventory, plan, targets, axes, helpers, previous, previous_proof
    ):
        seed = plan["phase_seed"]
        assert helpers == "synthetic_functions" and len(targets) == 1
        assert set(axes) == {"qwen", "jailmeter"}
        prior = None if seed == 11 else str(11 if seed == 23 else 23)
        assert previous == (phases[prior]["result"] if prior else None)
        assert previous_proof == (phases[prior]["verification"] if prior else None)
        observed.append(("rebuild", seed))
        outputs = [copy.deepcopy(phases[str(seed)][kind]) for kind in m.PHASE_KINDS]
        if seed == 23 and fault in {"measurement", "result", "proof"}:
            outputs[{"measurement": 0, "result": 1, "proof": 2}[fault]]["changed"] = True
        return outputs

    monkeypatch.setattr(m.parent_panel, "verify_axis", qwen)
    monkeypatch.setattr(m.continuation, "verify", jailmeter)
    monkeypatch.setattr(m.parent_target, "reconcile_phase", target)
    monkeypatch.setattr(m.parent_finalizer, "build_artifacts", rebuild)
    monkeypatch.setattr(
        m.parent_target, "global_receipt_check", lambda *args: 4 if fault == "global" else 3
    )
    if fault:
        with pytest.raises(c.DevelopmentError):
            REAL_PARENT_VERIFY(state.root, state.parent, state.amendment, {}, phases)
    else:
        result = REAL_PARENT_VERIFY(state.root, state.parent, state.amendment, {}, phases)
        assert result == state.inputs
        assert [(row[1], row[2]) for row in observed if row[0] == "axis"] == [
            (seed, axis) for seed in (11, 23, 47) for axis in ("qwen", "jailmeter")
        ]
        assert [row[1] for row in observed if row[0] == "rebuild"] == [11, 23, 47]


@pytest.mark.parametrize(
    "name", ["plan.safe.json", "bound-plan.safe.json", "materializations.private.json"]
)
def test_coherently_repinned_preparation_still_requires_exact_reconstruction(
    state, monkeypatch, name
):
    m.prepare(state.root)
    original = m.read_pin

    def simulate_repinned_artifact(root, pin, path):
        # Simulate a matching new descriptor at the low-level pin boundary; scientific
        # reconstruction must still reject altered material bytes or selected plans.
        raw = original(root, pin, path)
        if path.endswith("/" + name):
            value = c.strict_json(raw)
            if name == "materializations.private.json":
                value["rows"][0]["prompt"] = "Altered synthetic private material"
            else:
                value["n"] = 7
            return c.canonical(value)
        return raw

    monkeypatch.setattr(m, "read_pin", simulate_repinned_artifact)
    with pytest.raises(c.DevelopmentError, match="NOT_RECONSTRUCTED|NOT_EXACTLY_REPLAYED"):
        m.load_preparation(state.root, state.bundle["source_bundle_identity_sha256"])
