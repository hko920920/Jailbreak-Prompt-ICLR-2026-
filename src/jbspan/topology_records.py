from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from jbspan.gate1.util import canonical_json_sha256
from jbspan.topology import (
    BehaviorOutcome,
    InterventionMaterialization,
    JsonObject,
    OutcomeObservation,
    UnitSubset,
    sha256_text,
)


def _sha256(value: object, *, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where} must be a string")
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{where} must be a lowercase SHA-256 digest")
    return value


def _string(value: object, *, where: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{where} must be a string")
    return value


def _boolean(value: object, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{where} must be a boolean")
    return value


def _integer(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} must be an integer")
    return value


def _strings(value: object, *, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{where} must be an array of strings")
    return tuple(value)


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@dataclass(frozen=True)
class ExecutionKey:
    instance_id: str
    selected_unit_ids: UnitSubset
    neutralizer_id: str
    seed: int
    model_identity_sha256: str
    prompt_sha256: str

    def __post_init__(self) -> None:
        if not self.instance_id.strip():
            raise ValueError("execution-key instance_id must be non-empty")
        if not self.neutralizer_id.strip():
            raise ValueError("execution-key neutralizer_id must be non-empty")
        if len(self.selected_unit_ids) != len(set(self.selected_unit_ids)):
            raise ValueError("execution-key unit IDs must be unique")
        _sha256(self.model_identity_sha256, where="model_identity_sha256")
        _sha256(self.prompt_sha256, where="prompt_sha256")

    @property
    def record_id(self) -> str:
        return canonical_json_sha256(
            {
                "instance_id": self.instance_id,
                "selected_unit_ids": list(self.selected_unit_ids),
                "neutralizer_id": self.neutralizer_id,
                "seed": self.seed,
                "model_identity_sha256": self.model_identity_sha256,
                "prompt_sha256": self.prompt_sha256,
            }
        )

    def to_dict(self) -> JsonObject:
        return {
            "instance_id": self.instance_id,
            "selected_unit_ids": list(self.selected_unit_ids),
            "neutralizer_id": self.neutralizer_id,
            "seed": self.seed,
            "model_identity_sha256": self.model_identity_sha256,
            "prompt_sha256": self.prompt_sha256,
            "record_id": self.record_id,
        }


@dataclass(frozen=True)
class PrivateTopologyRecord:
    key: ExecutionKey
    edited_prompt: str
    response: str
    outcome: BehaviorOutcome
    input_valid: bool
    validation_error_codes: tuple[str, ...]
    decision_relevant_truncation: bool
    capability_control_passed: bool

    def __post_init__(self) -> None:
        if sha256_text(self.edited_prompt) != self.key.prompt_sha256:
            raise ValueError("edited prompt does not match execution-key hash")
        if self.input_valid and self.validation_error_codes:
            raise ValueError("valid records cannot contain validation errors")
        if not self.input_valid and not self.validation_error_codes:
            raise ValueError("invalid records must contain validation errors")

    @property
    def response_sha256(self) -> str:
        return sha256_text(self.response)

    def to_private_dict(self) -> JsonObject:
        return {
            "schema_version": "jbspan-topology-private-record-v1",
            "key": self.key.to_dict(),
            "edited_prompt": self.edited_prompt,
            "response": self.response,
            "response_sha256": self.response_sha256,
            "outcome": self.outcome.value,
            "input_valid": self.input_valid,
            "validation_error_codes": list(self.validation_error_codes),
            "decision_relevant_truncation": self.decision_relevant_truncation,
            "capability_control_passed": self.capability_control_passed,
        }

    def to_safe_dict(self) -> JsonObject:
        return {
            "schema_version": "jbspan-topology-safe-record-v1",
            **self.key.to_dict(),
            "subset_size": len(self.key.selected_unit_ids),
            "response_sha256": self.response_sha256,
            "response_character_length": len(self.response),
            "outcome": self.outcome.value,
            "input_valid": self.input_valid,
            "validation_error_codes": list(self.validation_error_codes),
            "decision_relevant_truncation": self.decision_relevant_truncation,
            "capability_control_passed": self.capability_control_passed,
            "raw_prompt_committed": False,
            "raw_response_committed": False,
        }

    def to_observation(self) -> OutcomeObservation:
        return OutcomeObservation(
            instance_id=self.key.instance_id,
            selected_unit_ids=self.key.selected_unit_ids,
            neutralizer_id=self.key.neutralizer_id,
            seed=self.key.seed,
            outcome=self.outcome,
            prompt_sha256=self.key.prompt_sha256,
            response_sha256=self.response_sha256,
            input_valid=self.input_valid,
            validation_error_codes=self.validation_error_codes,
            decision_relevant_truncation=self.decision_relevant_truncation,
            capability_control_passed=self.capability_control_passed,
        )


def build_private_record(
    materialization: InterventionMaterialization,
    *,
    seed: int,
    model_identity: Mapping[str, object],
    response: str,
    outcome: BehaviorOutcome,
    decision_relevant_truncation: bool = False,
    capability_control_passed: bool = True,
) -> PrivateTopologyRecord:
    key = ExecutionKey(
        instance_id=materialization.instance_id,
        selected_unit_ids=materialization.selected_unit_ids,
        neutralizer_id=materialization.neutralizer_id,
        seed=seed,
        model_identity_sha256=canonical_json_sha256(dict(model_identity)),
        prompt_sha256=materialization.prompt_sha256,
    )
    return PrivateTopologyRecord(
        key=key,
        edited_prompt=materialization.edited_prompt,
        response=response,
        outcome=outcome,
        input_valid=materialization.input_valid,
        validation_error_codes=materialization.validation_error_codes,
        decision_relevant_truncation=decision_relevant_truncation,
        capability_control_passed=capability_control_passed,
    )


def private_record_from_dict(value: JsonObject) -> PrivateTopologyRecord:
    if value.get("schema_version") != "jbspan-topology-private-record-v1":
        raise ValueError("unsupported private topology record schema")
    raw_key = value.get("key")
    if not isinstance(raw_key, dict):
        raise ValueError("private record key must be an object")
    selected = _strings(raw_key.get("selected_unit_ids"), where="selected_unit_ids")
    key = ExecutionKey(
        instance_id=_string(raw_key.get("instance_id"), where="instance_id"),
        selected_unit_ids=selected,
        neutralizer_id=_string(raw_key.get("neutralizer_id"), where="neutralizer_id"),
        seed=_integer(raw_key.get("seed"), where="seed"),
        model_identity_sha256=_sha256(
            raw_key.get("model_identity_sha256"),
            where="model_identity_sha256",
        ),
        prompt_sha256=_sha256(raw_key.get("prompt_sha256"), where="prompt_sha256"),
    )
    if raw_key.get("record_id") != key.record_id:
        raise ValueError("private record ID does not match its execution key")
    raw_outcome = _string(value.get("outcome"), where="outcome")
    try:
        outcome = BehaviorOutcome(raw_outcome)
    except ValueError as exc:
        raise ValueError(f"unknown behavior outcome: {raw_outcome}") from exc
    record = PrivateTopologyRecord(
        key=key,
        edited_prompt=_string(
            value.get("edited_prompt"),
            where="edited_prompt",
            allow_empty=True,
        ),
        response=_string(value.get("response"), where="response", allow_empty=True),
        outcome=outcome,
        input_valid=_boolean(value.get("input_valid"), where="input_valid"),
        validation_error_codes=_strings(
            value.get("validation_error_codes"),
            where="validation_error_codes",
        ),
        decision_relevant_truncation=_boolean(
            value.get("decision_relevant_truncation"),
            where="decision_relevant_truncation",
        ),
        capability_control_passed=_boolean(
            value.get("capability_control_passed"),
            where="capability_control_passed",
        ),
    )
    if value.get("response_sha256") != record.response_sha256:
        raise ValueError("private record response hash mismatch")
    return record


@dataclass
class TopologyRecordStore:
    private_root: Path
    safe_root: Path

    def __post_init__(self) -> None:
        private = self.private_root.resolve()
        safe = self.safe_root.resolve()
        if private == safe or private in safe.parents or safe in private.parents:
            raise ValueError("private and safe record roots must be separate directory trees")
        self.private_root.mkdir(parents=True, exist_ok=True)
        self.safe_root.mkdir(parents=True, exist_ok=True)

    def _private_path(self, record_id: str) -> Path:
        return self.private_root / record_id[:2] / f"{record_id}.private.json"

    def _safe_path(self, record_id: str) -> Path:
        return self.safe_root / record_id[:2] / f"{record_id}.safe.json"

    def contains(self, key: ExecutionKey) -> bool:
        private_path = self._private_path(key.record_id)
        safe_path = self._safe_path(key.record_id)
        private_exists = private_path.is_file()
        safe_exists = safe_path.is_file()
        if safe_exists and not private_exists:
            raise RuntimeError("safe topology record exists without its private source")
        if not private_exists:
            return False
        record = private_record_from_dict(_load_json(private_path))
        if record.key != key:
            raise RuntimeError("private topology record does not match the execution key")
        expected_safe = record.to_safe_dict()
        if safe_exists:
            if _load_json(safe_path) != expected_safe:
                raise RuntimeError("safe topology record conflicts with its private source")
        else:
            _write_json_atomic(safe_path, expected_safe)
        return True

    def put(self, record: PrivateTopologyRecord) -> bool:
        private_path = self._private_path(record.key.record_id)
        safe_path = self._safe_path(record.key.record_id)
        expected_private = record.to_private_dict()
        expected_safe = record.to_safe_dict()

        if private_path.is_file():
            observed_private = _load_json(private_path)
            if observed_private != expected_private:
                raise RuntimeError("conflicting private record for the same execution key")
            if safe_path.is_file():
                if _load_json(safe_path) != expected_safe:
                    raise RuntimeError("conflicting safe record for the same execution key")
            else:
                _write_json_atomic(safe_path, expected_safe)
            return False
        if safe_path.is_file():
            raise RuntimeError("safe topology record exists without its private source")

        _write_json_atomic(private_path, expected_private)
        _write_json_atomic(safe_path, expected_safe)
        return True

    def load_records(self, *, instance_id: str | None = None) -> tuple[PrivateTopologyRecord, ...]:
        records = tuple(
            private_record_from_dict(_load_json(path))
            for path in sorted(self.private_root.rglob("*.private.json"))
        )
        record_ids = [record.key.record_id for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise RuntimeError("duplicate private topology record IDs")
        if instance_id is None:
            return records
        return tuple(record for record in records if record.key.instance_id == instance_id)

    def load_observations(
        self,
        *,
        instance_id: str | None = None,
    ) -> tuple[OutcomeObservation, ...]:
        return tuple(
            record.to_observation()
            for record in self.load_records(instance_id=instance_id)
        )
