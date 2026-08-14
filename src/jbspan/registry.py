from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    created_at: str
    config_sha256: str
    python: str
    platform: str
    config: dict[str, Any]


def create_manifest(run_id: str, config: dict[str, Any]) -> RunManifest:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return RunManifest(
        run_id=run_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        config_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        python=sys.version.split()[0],
        platform=platform.platform(),
        config=config,
    )


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
