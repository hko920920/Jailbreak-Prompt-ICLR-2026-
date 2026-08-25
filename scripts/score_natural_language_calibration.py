from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.natural_language_annotation import score_calibration_annotations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score two blinded natural-language calibration annotations.",
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--packet-summary", type=Path, required=True)
    parser.add_argument("--annotation-packet", type=Path, required=True)
    parser.add_argument("--annotation-key", type=Path, required=True)
    parser.add_argument("--annotator-a", type=Path, required=True)
    parser.add_argument("--annotator-b", type=Path, required=True)
    parser.add_argument("--adjudicator", type=Path)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = score_calibration_annotations(
        contract_path=args.contract.resolve(),
        packet_summary_path=args.packet_summary.resolve(),
        annotation_packet_path=args.annotation_packet.resolve(),
        annotation_key_path=args.annotation_key.resolve(),
        annotator_a_path=args.annotator_a.resolve(),
        annotator_b_path=args.annotator_b.resolve(),
        adjudicator_path=(args.adjudicator.resolve() if args.adjudicator else None),
        private_output_dir=args.private_output_dir.resolve(),
        safe_output_path=args.safe_output.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
