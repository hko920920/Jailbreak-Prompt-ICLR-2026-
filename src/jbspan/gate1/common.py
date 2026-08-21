from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from jbspan.gate1.models import ContractValidationError

JsonObject = dict[str, Any]


def as_string(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{where} must be a non-empty string")
    return value


def as_boolean(value: Any, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise ContractValidationError(f"{where} must be a boolean")
    return value


def as_integer(value: Any, *, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractValidationError(f"{where} must be an integer")
    return value


def as_object(value: Any, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{where} must be an object")
    return dict(value)


def as_array(value: Any, *, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{where} must be an array")
    return list(value)


def unique_strings(values: Iterable[Any], *, where: str) -> tuple[str, ...]:
    items = tuple(as_string(value, where=where) for value in values)
    if len(set(items)) != len(items):
        raise ContractValidationError(f"{where} entries must be unique")
    return items
