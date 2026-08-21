from __future__ import annotations

from jbspan.gate1.common import (
    JsonObject,
    as_array,
    as_boolean,
    as_integer,
    as_object,
    as_string,
    unique_strings,
)
from jbspan.gate1.models import ContractValidationError, PayloadSource


def parse_payload_source(payload: JsonObject) -> PayloadSource:
    sources = as_array(payload.get("sources"), where="payload_source_registry.sources")
    if len(sources) != 1:
        raise ContractValidationError("exactly one primary payload source is required")
    source = as_object(sources[0], where="payload_source")
    selection = as_object(source.get("selection"), where="payload_source.selection")
    parsed = PayloadSource(
        source_id=as_string(source.get("source_id"), where="payload_source.source_id"),
        repository_id=as_string(
            source.get("repository_id"), where="payload_source.repository_id"
        ),
        dataset_config=as_string(
            source.get("dataset_config"), where="payload_source.dataset_config"
        ),
        split=as_string(source.get("split"), where="payload_source.split"),
        revision=as_string(source.get("revision"), where="payload_source.revision"),
        revision_kind=as_string(
            source.get("revision_kind"), where="payload_source.revision_kind"
        ),
        resolve_full_revision_at_materialization=as_boolean(
            source.get("resolve_full_revision_at_materialization"),
            where="payload_source.resolve_full_revision_at_materialization",
        ),
        require_source_file_sha256=as_boolean(
            source.get("require_source_file_sha256"),
            where="payload_source.require_source_file_sha256",
        ),
        expected_rows=as_integer(
            source.get("expected_rows"), where="payload_source.expected_rows"
        ),
        expected_category_count=as_integer(
            source.get("expected_category_count"),
            where="payload_source.expected_category_count",
        ),
        license=as_string(source.get("license"), where="payload_source.license"),
        doi=as_string(source.get("doi"), where="payload_source.doi"),
        required_columns=unique_strings(
            as_array(source.get("required_columns"), where="payload_source.required_columns"),
            where="payload_source.required_columns",
        ),
        raw_payloads_committed=as_boolean(
            source.get("raw_payloads_committed"),
            where="payload_source.raw_payloads_committed",
        ),
        target_count=as_integer(
            selection.get("target_count"), where="payload_selection.target_count"
        ),
        minimum_count=as_integer(
            selection.get("minimum_count"), where="payload_selection.minimum_count"
        ),
        selection_seed=as_string(selection.get("seed"), where="payload_selection.seed"),
        selected_per_category=as_integer(
            selection.get("selected_per_category"),
            where="payload_selection.selected_per_category",
        ),
        development_per_category=as_integer(
            selection.get("development_per_category"),
            where="payload_selection.development_per_category",
        ),
        heldout_per_category=as_integer(
            selection.get("heldout_per_category"),
            where="payload_selection.heldout_per_category",
        ),
    )
    validate_payload_source(parsed)
    return parsed


def validate_payload_source(source: PayloadSource) -> None:
    if source.raw_payloads_committed:
        raise ContractValidationError("raw harmful payload text must not be committed")
    if source.revision_kind != "hf_commit_prefix":
        raise ContractValidationError("unsupported payload revision kind")
    if not source.resolve_full_revision_at_materialization:
        raise ContractValidationError("full source revision resolution is required")
    if not source.require_source_file_sha256:
        raise ContractValidationError("source-file SHA-256 is required")
    if source.minimum_count < 50:
        raise ContractValidationError("Gate 1 requires at least 50 development payloads")
    expected_target = source.expected_category_count * source.selected_per_category
    if source.target_count != expected_target:
        raise ContractValidationError("target_count must equal category-stratified selection")
    if source.selected_per_category != (
        source.development_per_category + source.heldout_per_category
    ):
        raise ContractValidationError("development and heldout counts must partition selection")
    if source.development_count < source.minimum_count:
        raise ContractValidationError("development payload count is below the hard minimum")
    if source.target_count > source.expected_rows:
        raise ContractValidationError("payload target_count exceeds source rows")
