"""Pure synthetic tests for a proposal validator, never an experiment runner."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
          / "preflight_pa_research_regime_smoke_v1.py")
SPEC = importlib.util.spec_from_file_location("pa_proposal_static_tested", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


@pytest.fixture
def proposal(tmp_path_factory, monkeypatch):
    # Fixed short prefix avoids Windows MAX_PATH for pinned 64-character identities.
    tmp_path = tmp_path_factory.mktemp("prs")
    def pin(relative, value, *, text=False):
        raw = value.encode() if text else validator.canonical(value)
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": relative, "size_bytes": len(raw), "sha256": validator.raw_digest(raw)}

    tasks = [{**task, "text": "Synthetic harmless task " + task["fixture_id"]}
             for task in validator.TASKS]
    sources = {}
    for role in ("scope", "no_new_human_amendment", "prior_handoff"):
        sources[role] = pin(validator.SOURCE_PATHS[role], "Synthetic safe provenance", text=True)
    v2_fixtures = [{"prompt_id": task["fixture_id"], "text": task["text"],
                    "scorer": task["scorer"], "expected": task["expected"]} for task in tasks]
    v2 = {"schema_version": "jbspan-pa-llama-target-admission-v2", "frozen": True,
          "fixtures": v2_fixtures, "model": {"unread_private_path": "artifacts/forbidden/model"}}
    sources["v2_contract"] = pin(validator.SOURCE_PATHS["v2_contract"], v2)
    v2_sha = sources["v2_contract"]["sha256"]
    result = {
        "schema_version": "jbspan-pa-llama-target-admission-v2", "contract_sha256": v2_sha,
        "complete": True, "request_count": 11, "request_ceiling": 11,
        "capability_denominator": 10, "capability_passes": 7,
        "admitted_basic_harmless_runtime_only": False, "paper_admission": False,
        "jailbreak_admission": False, "measurement_admission": False,
        "rows": [{"ordinal": i, "passed": i <= 7 or i == 11} for i in range(1, 12)],
    }
    result_root = f"data/natural_language_localization/pa_llama_target_admission_v2/{v2_sha}"
    sources["v2_result"] = pin(f"{result_root}/result.safe.json", result)
    verification = {
        "contract_sha256": v2_sha, "saved_result_sha256": sources["v2_result"]["sha256"],
        "independent_verification_passed": True, "original_basic_admission_gate_passed": False,
        "primary_denominator": 10, "primary_exact_passes": 7,
        "aggregate_generation_calls": 11, "predecessor_generation_calls": 0,
        "verified_requests": 11, "verified_replies": 11, "new_target_calls_by_verifier": 0,
        "paper_or_jailbreak_or_judge_admission": False,
        "posthoc_punctuation_diagnostic_changes_gate": False,
    }
    sources["v2_independent_verification"] = pin(
        f"{result_root}/independent-verification.safe.json", verification)
    sources["d3_contract"] = pin(validator.SOURCE_PATHS["d3_contract"], {
        "schema_version": "jbspan-d3-exact-topology-contract-v1",
        "frozen": True, "capability_controls": {"tasks": [
            {"id": task["task_id"], "source_prompt_id": task["fixture_id"]} for task in tasks]}})
    sources["step5n_fixture_source"] = pin(validator.SOURCE_PATHS["step5n_fixture_source"], {
        "schema_version": "jbspan-step5n-h4rm3l-confirmation-v1",
        "frozen": True, "harmless_prompts": [
            {"prompt_id": task["fixture_id"], "text": task["text"]} for task in tasks]})
    scientific = {**validator.GENERATION, "seeds": list(validator.SEEDS), "context_tokens": 4096}
    scientific["maximum_new_tokens"] = scientific.pop("max_tokens")
    scientific["min_p"] = 0.0
    scientific["repeat_penalty"] = 1.0
    sources["c1n_contract"] = pin(validator.SOURCE_PATHS["c1n_contract"], {
        "schema_version": "jbspan-c1n-h4rm3l-fresh-screen-v1",
        "frozen": True, "generation": scientific})
    sources["validator"] = pin(validator.RUNNER, "synthetic static code pin", text=True)
    monkeypatch.setattr(validator, "__file__", str(tmp_path / validator.RUNNER))
    config = {
        "schema_version": validator.SCHEMA, "frozen": True, "execution_authorized": False,
        "status": "FROZEN_PROPOSAL_RULES_NOT_EXECUTION_AUTHORITY",
        "current_allowed_calls": 0, "proposed_future_calls": 6, "purpose": validator.PURPOSE,
        "evidence_class": "RESULT_INFORMED_DEVELOPMENT_OPERATIONAL_DESIGN_NOT_CONFIRMATION",
        "paper_validity": False, "sources": sources, "tasks": tasks,
        "seeds": list(validator.SEEDS), "generation": dict(validator.GENERATION),
        "context_tokens": 4096, "order": "SEED_MAJOR_THEN_D3_TASK_ORDER",
        "task_selection_basis": "EXACT_CONTROL_TASK_IDS_FROM_D3_CONTRACT_FROZEN_BEFORE_"
        "LLAMA_ADMISSION_NOT_SELECTED_BY_V2_PASSES",
        **json.loads(json.dumps(validator.FIXED_BOUNDARIES)),
    }

    def save():
        raw = validator.canonical(config)
        path = tmp_path / validator.CONFIG
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return validator.raw_digest(raw)

    def repin_source(key, mutate):
        item = sources[key]
        path = tmp_path / item["path"]
        value = validator.strict_json(path.read_bytes())
        mutate(value)
        sources[key] = pin(item["path"], value)
        return save()

    return SimpleNamespace(root=tmp_path, config=config, sha=save(), save=save, pin=pin,
                           repin=repin_source)


def preflight(proposal):
    return validator.preflight(proposal.root, validator.CONFIG, proposal.sha)


def test_static_plan_is_exactly_two_tasks_by_three_seeds_and_writes_nothing(proposal, monkeypatch):
    reads = []
    original_read = Path.read_bytes

    def observed_read(path):
        reads.append(path.relative_to(proposal.root).as_posix())
        return original_read(path)

    before = {str(path): path.stat().st_mtime_ns for path in proposal.root.rglob("*")
              if path.is_file()}
    monkeypatch.setattr(Path, "read_bytes", observed_read)
    result = preflight(proposal)
    after = {str(path): path.stat().st_mtime_ns for path in proposal.root.rglob("*")
             if path.is_file()}
    assert before == after
    assert set(reads) == {validator.CONFIG,
                         *(v["path"] for v in proposal.config["sources"].values())}
    assert not any(path.startswith("artifacts/") for path in reads)
    assert result["static_preflight_passed"] and result["calls_made"] == 0
    assert not result["execution_authorized"] and result["proposed_future_calls"] == 6
    assert [(row["task_id"], row["seed"]) for row in result["plan"]] == [
        (task_id, seed) for seed in (11, 23, 47) for task_id in ("P2_ARITHMETIC", "P2_COPY_TOKEN")]
    assert "Synthetic harmless task" not in json.dumps(result)
    assert not result["old_v2_gate_passed"] and result["old_v2_capability_passes"] == 7
    assert not result["scientific_target_admitted"] and not result["paper_claim_supported"]
    assert not result["model_runtime_artifacts_rehashed"]
    for row in result["plan"]:
        assert row["proposed_request_regime_sha256"] == validator.digest({
            **validator.GENERATION, "seed": row["seed"], "context_tokens": 4096})


@pytest.mark.parametrize(("mutate", "code"), [
    (lambda c: c.update(frozen=False), "PROPOSAL_NOT_FROZEN"),
    (lambda c: c.update(execution_authorized=True), "EXECUTION_NOT_ALLOWED"),
    (lambda c: c.update(current_allowed_calls=6), "EXECUTION_NOT_ALLOWED"),
    (lambda c: c.update(current_allowed_calls=False), "EXECUTION_NOT_ALLOWED"),
    (lambda c: c.update(proposed_future_calls=7), "FUTURE_CALL_BUDGET_CHANGED"),
    (lambda c: c.update(proposed_future_calls=5), "FUTURE_CALL_BUDGET_CHANGED"),
    (lambda c: c.update(paper_validity=True), "PURPOSE_OR_PAPER_SCOPE_CHANGED"),
    (lambda c: c.update(purpose="V2_REPASS"), "PURPOSE_OR_PAPER_SCOPE_CHANGED"),
    (lambda c: c.update(seeds=[11, 23, 17]), "SEEDS_CHANGED"),
    (lambda c: c.update(seeds=[11, 23]), "SEEDS_CHANGED"),
    (lambda c: c.update(seeds=[47, 23, 11]), "SEEDS_CHANGED"),
    (lambda c: c["generation"].update(max_tokens=48), "PROPOSED_GENERATION_CHANGED"),
    (lambda c: c["generation"].update(temperature=0), "PROPOSED_GENERATION_CHANGED"),
    (lambda c: c["generation"].update(repeat_penalty=True), "PROPOSED_GENERATION_CHANGED"),
    (lambda c: c.update(context_tokens=8192), "CONTEXT_CHANGED"),
    (lambda c: c.update(order="TASK_MAJOR"), "PLAN_ORDER_CHANGED"),
    (lambda c: c["tasks"].pop(), "PROPOSED_TASK_COUNT_CHANGED"),
    (lambda c: c["tasks"].append(c["tasks"][0]), "PROPOSED_TASK_COUNT_CHANGED"),
    (lambda c: c["tasks"][0].update(expected=142), "TASK_ID_OR_SCORING_CHANGED"),
    (lambda c: c["tasks"][0].update(scorer="substring"), "TASK_ID_OR_SCORING_CHANGED"),
    (lambda c: c["tasks"][0].update(text="easier task"), "STEP5N_FIXTURE_TEXT_CHANGED"),
    (lambda c: c["prior_states"].update(v2_gate_passed=True), "BOUNDARY_CHANGED_PRIOR_STATES"),
    (lambda c: c["exposure"].update(fresh_capability_sample=True), "BOUNDARY_CHANGED_EXPOSURE"),
    (lambda c: c["preserved_scoring"].update(punctuation_normalization_added=True),
     "BOUNDARY_CHANGED_PRESERVED_SCORING"),
    (lambda c: c["stop_rule"].update(maximum_execution_batches=2), "BOUNDARY_CHANGED_STOP_RULE"),
    (lambda c: c["stop_rule"].update(automatic_next_experiment=True), "BOUNDARY_CHANGED_STOP_RULE"),
    (lambda c: c["pass_rule"].update(unknown_counts_as_nonpass=False),
     "BOUNDARY_CHANGED_PASS_RULE"),
    (lambda c: c["downstream"].update(sealed_A60_B60_remain_unopened=False),
     "BOUNDARY_CHANGED_DOWNSTREAM"),
    (lambda c: c["qualification_policy_change"].update(
        currently_activates_replacement_profile=True),
     "BOUNDARY_CHANGED_QUALIFICATION_POLICY_CHANGE"),
])
def test_rejects_scope_scoring_budget_or_gate_changes(proposal, mutate, code):
    mutate(proposal.config)
    proposal.sha = proposal.save()
    with pytest.raises(validator.ProposalError, match=code):
        preflight(proposal)


@pytest.mark.parametrize(("key", "mutate", "code"), [
    ("v2_result", lambda v: v.update(admitted_basic_harmless_runtime_only=True),
     "FAILED_V2_RESULT_NOT_PRESERVED"),
    ("v2_result", lambda v: v.update(capability_passes=10), "FAILED_V2_RESULT_NOT_PRESERVED"),
    ("v2_result", lambda v: v.update(request_count=0), "FAILED_V2_RESULT_NOT_PRESERVED"),
    ("v2_independent_verification", lambda v: v.update(independent_verification_passed=False),
     "INDEPENDENT_VERIFICATION_BINDING_OR_GATE_MISMATCH"),
    ("v2_independent_verification", lambda v: v.update(original_basic_admission_gate_passed=True),
     "INDEPENDENT_VERIFICATION_BINDING_OR_GATE_MISMATCH"),
    ("v2_independent_verification", lambda v: v.update(saved_result_sha256="0" * 64),
     "INDEPENDENT_VERIFICATION_BINDING_OR_GATE_MISMATCH"),
    ("d3_contract", lambda v: v["capability_controls"]["tasks"].pop(),
     "D3_CONTROL_TASK_BASIS_CHANGED"),
    ("d3_contract", lambda v: v.update(frozen=False), "D3_SOURCE_NOT_FROZEN"),
    ("step5n_fixture_source", lambda v: v.update(frozen=False),
     "STEP5N_FIXTURE_SOURCE_NOT_FROZEN"),
    ("c1n_contract", lambda v: v["generation"].update(maximum_new_tokens=48),
     "PROPOSAL_NOT_C1N_SCIENTIFIC_REGIME"),
    ("c1n_contract", lambda v: v["generation"].update(seeds=[17]), "C1N_SEED_OR_CONTEXT_MISMATCH"),
])
def test_rejects_rebound_but_inconsistent_source_records(proposal, key, mutate, code):
    proposal.sha = proposal.repin(key, mutate)
    with pytest.raises(validator.ProposalError, match=code):
        preflight(proposal)


@pytest.mark.parametrize("relative", [
    "artifacts/pa_llama_target_admission_v2/private/01.reply.private.json",
    "artifacts/model.gguf", "data/natural_language_localization/primary_a/data.safe.json",
    "data/natural_language_localization/reserve_b/data.safe.json",
    "data/natural_language_localization/some_other/result.safe.json",
    "docs/private_notes.md", "../outside.md", "configs/natural_language_localization/other.json",
])
def test_private_artifact_sealed_and_unapproved_paths_blocked_before_read(tmp_path, relative):
    with pytest.raises(validator.ProposalError):
        validator.safe_path(tmp_path, relative)


def test_source_checksum_and_config_checksum_required(proposal):
    with pytest.raises(validator.ProposalError, match="CONFIG_SHA_MISMATCH"):
        validator.preflight(proposal.root, validator.CONFIG, "0" * 64)
    item = proposal.config["sources"]["validator"]
    path = proposal.root / item["path"]
    raw = path.read_bytes()
    path.write_bytes(b"x" * len(raw))
    with pytest.raises(validator.ProposalError, match="SOURCE_SHA_MISMATCH"):
        preflight(proposal)


@pytest.mark.parametrize("role", ["scope", "no_new_human_amendment", "prior_handoff", "validator"])
def test_mandatory_provenance_source_cannot_be_omitted(proposal, role):
    del proposal.config["sources"][role]
    proposal.sha = proposal.save()
    with pytest.raises(validator.ProposalError, match="REQUIRED_STATIC_SOURCES_MISSING"):
        preflight(proposal)


def test_extra_source_cannot_open_private_artifact(proposal, monkeypatch):
    proposal.config["sources"]["unapproved"] = {
        "path": "artifacts/forbidden/private.json", "size_bytes": 2, "sha256": "0" * 64}
    proposal.sha = proposal.save()
    original_read = Path.read_bytes

    def guarded_read(path):
        assert "artifacts" not in path.parts
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(validator.ProposalError, match="SOURCE_OUTSIDE_STATIC_SAFE_ALLOWLIST"):
        preflight(proposal)


def test_ordinal_boolean_cannot_masquerade_as_integer(proposal):
    proposal.sha = proposal.repin("v2_result", lambda value: value["rows"][0].update(ordinal=True))
    with pytest.raises(validator.ProposalError, match="V2_ROW_COUNT_OR_ORDER_INVALID"):
        preflight(proposal)


def test_duplicate_v2_fixture_id_rejected_before_dictionary_conversion(proposal):
    records = {key: validator.strict_json((proposal.root / value["path"]).read_bytes())
               for key, value in proposal.config["sources"].items()
               if key in validator.JSON_SOURCE_ROLES}
    fixtures = records["v2_contract"]["fixtures"]
    fixtures.append(dict(fixtures[0]))
    with pytest.raises(validator.ProposalError, match="V2_FIXTURE_IDS_NOT_UNIQUE"):
        validator.validate_design(proposal.config, records)


def test_no_execution_cli_and_no_network_process_or_write_code(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["preflight", "--config-sha256", "0" * 64, "--execute"])
    with pytest.raises(SystemExit) as error:
        validator.main()
    assert error.value.code == 2
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"write_bytes", "write_text", "mkdir", "unlink", "Popen",
                                     "urlopen", "connect", "request", "exec", "system"}
    assert imports <= {"__future__", "argparse", "hashlib", "json", "re", "pathlib"}
