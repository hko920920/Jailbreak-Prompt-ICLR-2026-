"""Temporary import shim for redacted Inspect runtime diagnostics.

When ``scripts/run_programmatic_agentharm_smoke.py`` imports ``inspect_ai``,
Python sees this module first. We then load the real installed package after
removing the scripts directory from the search path, replace only its top-level
``eval`` entry point with a safe diagnostic wrapper, and expose the real package.
"""

from __future__ import annotations

import importlib
import re
import sys
import traceback
from pathlib import Path
from typing import Any

_MODULE_NAME = __name__
_SCRIPT_DIR = Path(__file__).resolve().parent
_ORIGINAL_PATH = list(sys.path)

sys.modules.pop(_MODULE_NAME, None)
sys.path = [
    entry
    for entry in sys.path
    if Path(entry or ".").resolve() != _SCRIPT_DIR
]
try:
    _real = importlib.import_module(_MODULE_NAME)
finally:
    sys.path = _ORIGINAL_PATH
sys.modules[_MODULE_NAME] = _real

_original_eval = _real.eval


def _safe_message(exc: TypeError) -> str:
    value = str(exc).replace("\n", " ")
    value = re.sub(
        r"(['\"])(.{80,}?)\1",
        lambda match: f"{match.group(1)}<REDACTED>{match.group(1)}",
        value,
    )
    return value[:500]


def _diagnostic_eval(*args: Any, **kwargs: Any) -> Any:
    try:
        return _original_eval(*args, **kwargs)
    except TypeError as exc:
        print("JBSPAN_SAFE_TYPEERROR_MESSAGE:", _safe_message(exc), flush=True)
        for frame in traceback.extract_tb(exc.__traceback__)[-12:]:
            print(
                "JBSPAN_SAFE_TYPEERROR_FRAME:",
                Path(frame.filename).name,
                frame.name,
                frame.lineno,
                flush=True,
            )
        raise


_real.eval = _diagnostic_eval
globals().update(_real.__dict__)
