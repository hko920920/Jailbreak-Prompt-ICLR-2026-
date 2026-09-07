"""Resume D3 generation after bootstrapping a missing later-seed plan.

Version 1 of the bounded operational launcher assumed that the phase plan
already existed.  Seed 11 satisfied that assumption because preflight freezes
its full plan; later adaptive seeds do not.  This launcher creates or verifies
the frozen runner's exact phase plan before delegating unchanged generation to
the version-1 launcher.  It changes no scientific rule or model setting.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import resume_d3_generation_operational_v1 as v1  # noqa: E402
import run_d3_exact_topology as d3  # noqa: E402


def ensure_plan(
    root: Path,
    config_path: Path,
    seed: int,
) -> tuple[int, Path]:
    """Create or verify the adaptive phase plan through the frozen runner."""

    d3.install_engine_patches()
    d3.d3_screen.patch_extractor(root)
    resolved_config, config, verified = d3.load_config(root, config_path)
    plans, _payloads, _raw, _p3, _parent = d3.ensure_phase_plan(
        root,
        resolved_config,
        config,
        verified,
        seed,
    )
    phase: Mapping[str, Any] = d3.engine.phase_paths(root, config, seed)
    plan_path = Path(phase["plan"])
    persisted = d3.engine.load_jsonl(plan_path)
    if persisted != plans:
        raise ValueError("persisted D3 phase plan differs from frozen plan rows")
    return len(plans), plan_path


def main() -> int:
    args = v1.parser().parse_args()
    if args.max_new_records < 1:
        raise SystemExit("--max-new-records must be positive")
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    ensure_plan(root, config_path, args.seed)
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
