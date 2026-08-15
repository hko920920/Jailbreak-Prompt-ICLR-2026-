from __future__ import annotations

import base64
import json
import lzma
from pathlib import Path


def main() -> None:
    encoded = Path("data/gate1/step3b_payload.b85").read_bytes()
    files = json.loads(lzma.decompress(base64.b85decode(encoded)).decode("utf-8"))
    if not isinstance(files, dict):
        raise RuntimeError("Step 3B bootstrap payload is not an object")
    for name, text in files.items():
        if not isinstance(name, str) or not isinstance(text, str):
            raise RuntimeError("Step 3B bootstrap payload contains an invalid entry")
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
