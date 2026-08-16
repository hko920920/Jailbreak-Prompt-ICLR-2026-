from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "data/gate1/wildguard_validation_payload.b85"


def main() -> int:
    encoded = PAYLOAD.read_text(encoding="utf-8").strip().encode("ascii")
    value = json.loads(zlib.decompress(base64.b85decode(encoded)))
    if not isinstance(value, dict):
        raise RuntimeError("WildGuard bootstrap payload must be an object")
    for raw_path, content in value.items():
        if not isinstance(raw_path, str) or not isinstance(content, str):
            raise RuntimeError("invalid WildGuard bootstrap entry")
        path = ROOT / raw_path
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing path: {raw_path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
