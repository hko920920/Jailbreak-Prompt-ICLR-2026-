"""Default: safe read-only readiness. Live execution requires an exact frozen contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan.rescue_guidedeval_development import (  # noqa: E402
    PRIVATE_BASE,
    SCHEMA,
    TransportFailure,
    contained,
    digest,
    execute,
    file_digest,
    prepare_development_cases,
    read_object,
    template,
    validate_contract,
    verify_project,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--print-contract-template", action="store_true")
    parser.add_argument("--prepare-development-cases", action="store_true")
    parser.add_argument("--contract", type=str)
    parser.add_argument("--contract-sha256")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    stage = "SAFE_SOURCE_AND_INPUT_IDENTITY_VERIFICATION"
    try:
        root = args.root.resolve()
        config, plan = verify_project(root)
        if args.prepare_development_cases:
            stage = "EXPLICIT_DEVELOPMENT_CASE_PREPARATION"
            if args.print_contract_template or args.execute or args.contract:
                raise ValueError("case preparation must be a separate explicit operation")
            result = prepare_development_cases(root)
        elif args.print_contract_template:
            if args.execute or args.contract:
                raise ValueError("template output cannot be combined with contract execution")
            result = template(root, plan)
        elif args.contract:
            stage = "EXACT_FROZEN_CONTRACT_FILE_HASH_VERIFICATION"
            contract_path = contained(root, args.contract)
            if not args.contract_sha256 or file_digest(contract_path) != args.contract_sha256:
                raise ValueError("exact frozen contract file SHA-256 required")
            contract = read_object(contract_path)
            stage = "FROZEN_CONTRACT_VALIDATION"
            validate_contract(root, contract, plan)
            if args.execute:
                stage = "LIVE_DEVELOPMENT_EXECUTION"
                result = execute(root, config, plan, contract)
            else:
                result = {
                    "schema_version": SCHEMA,
                    "status": "CONTRACT_STATIC_CHECK_PASS",
                    "contract_identity_sha256": digest(contract),
                    "private_inputs_read": False,
                    "network_calls": 0,
                }
        elif args.execute:
            stage = "MISSING_EXPLICIT_LIVE_CONTRACT"
            raise ValueError("--execute requires a frozen contract and its SHA-256")
        else:
            bundle_present = (root / PRIVATE_BASE / "development_cases.jsonl").is_file()
            result = {
                "schema_version": SCHEMA,
                "status": "SAFE_INPUT_AND_SOURCE_READINESS_PASS_LIVE_NOT_STARTED",
                "development_response_rows": len(plan),
                "unique_development_cases": len({row["source_id"] for row in plan}),
                "private_inputs_read": False,
                "full_benchmark_read": False,
                "development_bundle_file_present_not_opened": bundle_present,
                "primary_a_opened": False,
                "reserve_b_opened": False,
                "network_calls": 0,
                "still_required": [
                    "frozen_provider_model_endpoint_and_cost_contract",
                    (
                        "bind_prepared_bundle_hash_in_runtime_contract"
                        if bundle_present
                        else "prepare_exact_45_case_development_only_bundle"
                    ),
                    "provider_credential_or_explicit_local_no_auth",
                ],
            }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        # Do not print a traceback that could include private input/provider content.
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA,
                    "status": "STOPPED",
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "uncertain_dispatch": isinstance(exc, TransportFailure),
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
