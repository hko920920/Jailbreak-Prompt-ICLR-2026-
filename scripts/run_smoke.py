from __future__ import annotations

import json

from jbspan.cli import run_smoke

if __name__ == "__main__":
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
