"""Temporary import shim for the AgentHarm runtime smoke.

When ``scripts/run_programmatic_agentharm_smoke.py`` imports ``inspect_ai``,
Python sees this module first. We load the real installed package after removing
the scripts directory from the search path, normalize provider arguments for
the installed Inspect version, and retain redacted runtime diagnostics.
"""

from __future__ import annotations

import importlib
import os
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


def _safe_message(exc: Exception) -> str:
    value = str(exc).replace("\n", " | ")
    value = re.sub(
        r"(['\"])(.{80,}?)\1",
        lambda match: f"{match.group(1)}<REDACTED>{match.group(1)}",
        value,
    )
    value = re.sub(r"https?://\S+", "<REDACTED_URL>", value)
    return value[:1200]


def _normalize_provider_arguments(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Move OpenAI-compatible endpoint settings into provider environment."""

    normalized = dict(kwargs)
    raw_model_args = normalized.get("model_args")
    model_args = dict(raw_model_args) if isinstance(raw_model_args, dict) else {}
    environment_names = {
        "base_url": "OPENAI_BASE_URL",
        "api_key": "OPENAI_API_KEY",
    }
    for argument_name, environment_name in environment_names.items():
        value = model_args.pop(argument_name, None)
        if isinstance(value, str) and value:
            os.environ[environment_name] = value
    normalized["model_args"] = model_args
    return normalized


def _diagnostic_eval(*args: Any, **kwargs: Any) -> Any:
    normalized = _normalize_provider_arguments(kwargs)
    try:
        return _original_eval(*args, **normalized)
    except Exception as exc:
        print("JBSPAN_SAFE_EXCEPTION_TYPE:", type(exc).__name__, flush=True)
        print("JBSPAN_SAFE_EXCEPTION_MESSAGE:", _safe_message(exc), flush=True)
        for frame in traceback.extract_tb(exc.__traceback__)[-16:]:
            print(
                "JBSPAN_SAFE_EXCEPTION_FRAME:",
                Path(frame.filename).name,
                frame.name,
                frame.lineno,
                flush=True,
            )
        raise


_real.eval = _diagnostic_eval
globals().update(_real.__dict__)
