from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jbspan.gate1.models import Gate1Registry
from jbspan.gate1.util import canonical_json_sha256, load_json


def contract_manifest(root: Path, registry: Gate1Registry) -> dict[str, Any]:
    config = load_json(root / "configs/gate1/gate1_frozen_config.json")
    paths = [
        "configs/gate1/gate1_frozen_config.json",
        str(config["payload_source_registry"]),
        str(config["payload_registry_schema"]),
        str(config["benchmark_record_schema"]),
        str(config["tokenized_provenance_schema"]),
        str(config["primitive_registry"]),
        str(config["composition_grammar"]),
        str(config["neutralizer_registry"]),
    ]
    hashes = {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in paths
    }
    family_count = sum(item.primary_gate1 for item in registry.families.values())
    return {
        "schema_version": "gate1-contract-manifest-v1",
        "status": "GATE1_CONTRACT_VALIDATED",
        "paper_validity": False,
        "raw_payloads_committed": False,
        "payload_source_id": registry.payload_source.source_id,
        "payload_source_revision": registry.payload_source.revision,
        "full_revision_resolution_required": (
            registry.payload_source.resolve_full_revision_at_materialization
        ),
        "source_file_sha256_required": registry.payload_source.require_source_file_sha256,
        "payload_pool_rows": registry.payload_source.expected_rows,
        "payload_category_count": registry.payload_source.expected_category_count,
        "selected_payload_target": registry.payload_source.target_count,
        "gate1_development_payload_count": registry.payload_source.development_count,
        "gate2_heldout_payload_count": registry.payload_source.heldout_count,
        "primary_primitive_count": sum(
            item.primary_gate1 for item in registry.primitives.values()
        ),
        "primary_family_count": family_count,
        "primary_neutralizer_count": sum(
            item.primary_gate1 for item in registry.neutralizers.values()
        ),
        "parameter_binding_method": registry.parameter_binding_method,
        "token_provenance_required_stage": registry.token_provenance_stage,
        "projected_gate1_attack_count": (
            registry.payload_source.development_count * family_count
        ),
        "max_neutralizable_nodes": registry.max_neutralizable_nodes,
        "file_sha256": hashes,
        "contract_sha256": canonical_json_sha256(hashes),
    }
