from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.gate1 import contract_manifest, load_gate1_registry, render_program


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/gate1-contract/contract_manifest.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    registry = load_gate1_registry(root)

    payload_id = "TOY-000"
    payload = "Summarize the lifecycle of a butterfly."
    smoke: list[dict[str, object]] = []
    for family in registry.families.values():
        if not family.primary_gate1:
            continue
        baseline = render_program(
            registry,
            program_id=f"smoke:{family.family_id}",
            family_id=family.family_id,
            payload_id=payload_id,
            payload_text=payload,
        )
        first_node = family.nodes[0].node_id
        variants = {}
        for neutralizer in registry.neutralizers.values():
            if not neutralizer.primary_gate1:
                continue
            rendered = render_program(
                registry,
                program_id=f"smoke:{family.family_id}",
                family_id=family.family_id,
                payload_id=payload_id,
                payload_text=payload,
                neutralized_node_ids=(first_node,),
                neutralizer_id=neutralizer.neutralizer_id,
            )
            variants[neutralizer.neutralizer_id] = rendered.to_safe_dict()
        smoke.append(
            {
                "family_id": family.family_id,
                "baseline": baseline.to_safe_dict(),
                "neutralized_node_id": first_node,
                "variants": variants,
            }
        )

    manifest = contract_manifest(root, registry)
    manifest["smoke_family_count"] = len(smoke)
    manifest["smoke"] = smoke
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    public = {key: value for key, value in manifest.items() if key != "smoke"}
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
