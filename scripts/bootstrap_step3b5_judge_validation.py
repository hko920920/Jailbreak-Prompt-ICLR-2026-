from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = (
    ROOT / "data/gate1/step3b5_source.part01",
    ROOT / "data/gate1/step3b5_source.part02",
)
EXPECTED = {
    "src/jbspan/gate1/jbb_judge_validation_core.py",
    "src/jbspan/gate1/jbb_judge_validation.py",
    "scripts/run_gate1_step3b_judge_validation.py",
    "tests/test_gate1_step3b_judge_validation.py",
    "docs/GATE1_STEP3B_JUDGE_COMPARISON_PROTOCOL.md",
}


def main() -> int:
    encoded = "".join(path.read_text(encoding="ascii") for path in PARTS)
    payload = base64.b85decode(encoded.encode("ascii"))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        observed = set(archive.namelist())
        if observed != EXPECTED:
            raise RuntimeError(f"unexpected payload paths: {sorted(observed ^ EXPECTED)}")
        for name in sorted(observed):
            target = (ROOT / name).resolve()
            if ROOT.resolve() not in target.parents:
                raise RuntimeError(f"unsafe payload path: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    print(f"materialized {len(EXPECTED)} frozen Step 3B.5 source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
