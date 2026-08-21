from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.gate1.materialize import materialize_gate1_step2
from jbspan.gate1.registry import load_gate1_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--resolved-revision", required=True)
    parser.add_argument("--safe-output-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-sha256")
    args = parser.parse_args()

    root = args.root.resolve()
    registry = load_gate1_registry(root)
    manifest = materialize_gate1_step2(
        root,
        registry,
        source_csv=args.source_csv,
        resolved_revision=args.resolved_revision,
        safe_output_dir=args.safe_output_dir,
        private_output_dir=args.private_output_dir,
        expected_source_sha256=args.expected_source_sha256,
    )
    source_identity = manifest["source_identity"]
    public = {
        "status": manifest["status"],
        "contract_sha256": manifest["contract_sha256"],
        "source_file_sha256": source_identity["source_file_sha256"],
        "development_payload_count": manifest["development_payload_count"],
        "heldout_payload_count": manifest["heldout_payload_count"],
        "rendered_attack_count": manifest["rendered_attack_count"],
        "exclusion_count": manifest["exclusion_count"],
        "raw_payloads_logged": False,
        "raw_rendered_prompts_logged": False,
    }
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
