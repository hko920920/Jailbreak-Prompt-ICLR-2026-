"""Temporary safe diagnostics for the AgentHarm runtime smoke.

Python imports this module automatically when the repository root is on
``sys.path``. It wraps Inspect's top-level eval call only to print a redacted
TypeError signature and traceback locations. No prompts, responses, tool
arguments, or tool responses are emitted.
"""

from __future__ import annotations

import re
import traceback
from pathlib import Path
from typing import Any


def _safe_type_error_message(exc: TypeError) -> str:
    value = str(exc).replace("\n", " ")
    # TypeError diagnostics should contain API names and argument names. Redact
    # unusually long quoted values defensively in case an upstream library
    # includes user-controlled text.
    value = re.sub(
        r"(['\"])(.{80,}?)\1",
        lambda match: f"{match.group(1)}<REDACTED>{match.group(1)}",
        value,
    )
    return value[:500]


try:
    import inspect_ai

    _original_eval = inspect_ai.eval

    def _diagnostic_eval(*args: Any, **kwargs: Any) -> Any:
        try:
            return _original_eval(*args, **kwargs)
        except TypeError as exc:
            print(
                "JBSPAN_SAFE_TYPEERROR_MESSAGE:",
                _safe_type_error_message(exc),
                flush=True,
            )
            for frame in traceback.extract_tb(exc.__traceback__)[-12:]:
                print(
                    "JBSPAN_SAFE_TYPEERROR_FRAME:",
                    Path(frame.filename).name,
                    frame.name,
                    frame.lineno,
                    flush=True,
                )
            raise

    inspect_ai.eval = _diagnostic_eval
except Exception:
    # inspect_ai is intentionally unavailable during early dependency setup.
    pass
