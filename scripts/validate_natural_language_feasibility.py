from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.natural_language_feasibility import (
    load_json_object,
    validate_feasibility_contract,
    validate_safe_plan,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--contract",
        type=Path,
        default=Path("configs/natural_language_localization/feasibility_v1.json"),
    )
    value.add_argument(
        "--plan",
        type=Path,
        default=Path(
            "data/natural_language_localization/feasibility_v1/plan.safe.json"
        ),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract_path = root / args.contract
    plan_path = root / args.plan
    contract = load_json_object(contract_path)
    plan = load_json_object(plan_path)
    validate_feasibility_contract(contract)
    validate_safe_plan(plan, contract)
    summary = {
        "status": "NATURAL_LANGUAGE_FEASIBILITY_CONTRACT_VALID",
        "contract_identity_sha256": contract["contract_identity_sha256"],
        "plan_identity_sha256": plan["plan_identity_sha256"],
        "calibration_item_count": plan["calibration_item_count"],
        "screening_item_count": plan["screening_item_count"],
        "primary_outcome": contract["human_measurement"]["primary_outcome"],
        "automatic_judges_define_primary_success": False,
        "causal_oracle_opened": False,
        "wavelet_allowed": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
