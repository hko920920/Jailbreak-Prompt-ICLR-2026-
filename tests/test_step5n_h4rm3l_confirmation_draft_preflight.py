from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import preflight_step5n_h4rm3l_confirmation_draft as preflight  # noqa: E402

CONFIG_PATH = (
    ROOT / "configs" / "natural_language_localization" / "step5n_h4rm3l_confirmation_draft_v1.json"
)
T0_PATH = ROOT / "configs" / "natural_language_localization" / "topology_transition_t0_v1.json"


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_cli_exposes_only_read_only_draft_audit() -> None:
    arguments = preflight.parser().parse_args(["audit-draft"])
    assert arguments.command == "audit-draft"
    with pytest.raises(SystemExit):
        preflight.parser().parse_args(["freeze"])
    with pytest.raises(SystemExit):
        preflight.parser().parse_args(["audit-draft", "--generate"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frozen", True),
        ("author_narrow_decision_recorded", True),
        ("target_pair_selected", True),
        ("may_generate_confirmatory_target_outputs", True),
    ],
)
def test_changed_authorization_boundary_is_refused(field: str, value: object) -> None:
    config = load(CONFIG_PATH)
    if field == "frozen":
        config[field] = value
    else:
        authorization = config["authorization_boundary"]
        assert isinstance(authorization, dict)
        authorization[field] = value
    with pytest.raises(preflight.DraftBoundaryError):
        preflight.require_unauthorized_draft(config)


def test_t0_constants_and_exact_call_budgets_match() -> None:
    config = load(CONFIG_PATH)
    t0 = load(T0_PATH)
    t0_checks = preflight.validate_t0_constants(config, t0)
    assert t0_checks
    assert all(t0_checks.values())

    budgets = preflight.validate_call_budgets(config)
    assert budgets["passed"] is True
    assert budgets["derived"] == {
        "c1_maximum_target_calls": 540,
        "c2_nonempty_subsets": 7,
        "c2_maximum_lattice_calls_per_instance": 42,
        "c2_maximum_control_calls_per_instance": 28,
        "c2_maximum_total_new_calls_per_instance": 70,
    }


def test_budget_tampering_fails_closed() -> None:
    config = copy.deepcopy(load(CONFIG_PATH))
    c2 = config["c2n_exact_confirmatory_topology"]
    assert isinstance(c2, dict)
    c2["maximum_additional_capability_control_calls_per_instance"] = 0
    result = preflight.validate_call_budgets(config)
    assert result["passed"] is False
    assert result["checks"]["c2_control_maximum_is_28"] is False


def test_historical_preflight_receipt_remains_valid_after_authorized_transition() -> None:
    output_path = (
        ROOT
        / "data"
        / "natural_language_localization"
        / "step5n_h4rm3l_confirmation_draft_v1"
        / "draft_preflight.safe.json"
    )
    before = output_path.read_bytes()
    result = preflight.validated_existing_result(
        output_path, config_sha256=preflight.file_sha256(CONFIG_PATH)
    )
    assert result is not None
    assert output_path.read_bytes() == before
    assert preflight.file_sha256(output_path) == (
        "7075a0b10c8d6cec1a9eb7d6cf013c8dba42bf2c6e42479e0c293613c97a8443"
    )
    assert result["status"] == preflight.PASS_STATUS
    assert result["draft_preflight_pass"] is True
    assert result["author_narrow_decision_recorded"] is False
    assert result["target_pair_selected"] is False
    assert result["confirmatory_contract_frozen"] is False
    assert result["model_download_performed"] is False
    assert result["harmless_admission_performed"] is False
    assert result["confirmatory_target_output_opened"] is False
    assert result["confirmatory_evaluator_output_opened"] is False
    assert result["confirmatory_topology_opened"] is False
    assert result["raw_prompt_payload_or_response_recorded"] is False
    assert result["paper_validity"] is False
    assert all(result["checks"].values())
    # A preauthorization absence receipt is a historical snapshot.  Once the
    # separately authorized Step 5N result exists, rerunning its temporal
    # absence predicate would be invalid; the immutable receipt is verified
    # instead.
    assert (
        ROOT
        / "data"
        / "natural_language_localization"
        / "step5n_target_admission_v1"
        / "result.safe.json"
    ).is_file()
