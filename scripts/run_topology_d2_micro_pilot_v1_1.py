from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_topology_d2_micro_pilot as runner  # noqa: E402

JsonObject = dict[str, Any]
EXTRACTOR_VERSION = (
    "LLAMA_CPP_SIMPLE_IO_DISPLAY_ECHO_V3_TRAILING_NEWLINE_BOUNDARY_AMENDMENT"
)
AMENDMENT_RELATIVE_PATH = Path(
    "configs/natural_language_localization/topology_d2_extraction_v1_1_amendment.json"
)


def validate_amendment(root: Path) -> JsonObject:
    path = root / AMENDMENT_RELATIVE_PATH
    amendment = runner.load_object(path)
    if (
        amendment.get("schema_version")
        != "jbspan-topology-d2-extraction-amendment-v1-1"
        or amendment.get("status")
        != "FROZEN_AFTER_9_TARGET_RECORDS_BEFORE_ANY_D2_PANEL_OUTPUT"
        or amendment.get("frozen") is not True
    ):
        raise ValueError("D2 extraction amendment is not frozen at the supported boundary")
    for key in ("base_contract", "base_preflight", "repair_runner", "repair_tests"):
        spec = amendment["dependencies"][key]
        target = root / str(spec["path"])
        if runner.file_sha256(target) != spec["sha256"]:
            raise ValueError(f"D2 extraction amendment dependency mismatch: {key}")
    audit_path = root / str(amendment["recording"]["repair_audit_path"])
    if not audit_path.is_file():
        progress = root / str(amendment["failure_snapshot"]["progress_path"])
        if (
            runner.file_sha256(progress)
            != amendment["failure_snapshot"]["progress_sha256"]
            or len(runner.load_jsonl(progress))
            != amendment["failure_snapshot"]["record_count"]
        ):
            raise ValueError("D2 extraction failure snapshot changed before repair")
    return amendment


def extract_simple_io_response_v3(stdout: str, prompt: str) -> str:
    normalized = stdout.replace("\r\n", "\n").replace("\r", "\n")
    normalized_prompt = prompt.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized_prompt) <= 500:
        displayed_prompt = normalized_prompt
    else:
        displayed_prompt = normalized_prompt[:500] + " ... (truncated)"
    boundary = "" if displayed_prompt.endswith("\n") else "\n"
    marker = re.compile(
        r"(?:^|\n)>\s*" + re.escape(displayed_prompt) + re.escape(boundary)
    )
    matches = list(marker.finditer(normalized))
    if len(matches) != 1:
        raise ValueError(f"expected one simple-IO prompt marker, got {len(matches)}")
    tail = normalized[matches[0].end() :]
    timing = re.search(r"\n+\[\s*Prompt:\s*[0-9.]+\s*t/s\s*\|", tail)
    if timing is None:
        raise ValueError("simple-IO timing boundary is missing")
    return tail[: timing.start()].strip()


def patch_extractor(root: Path):
    p3 = runner.screen.repo_module(root, "scripts.run_local_signal_screen_p3")
    p3.extract_simple_io_response = extract_simple_io_response_v3
    p3.RESPONSE_EXTRACTOR_VERSION = EXTRACTOR_VERSION
    return p3


def repair_existing_failed_records(
    root: Path,
    config_path: Path,
    p3: Any,
) -> JsonObject:
    config_path, config, _verified = runner.load_config(root, config_path)
    output = runner.paths(root, config)
    audit_path = output["preflight"].parent / "extraction_repair_v1_1.safe.json"
    if audit_path.is_file():
        existing = runner.load_object(audit_path)
        if (
            existing.get("status") != "D2_EXTRACTION_REPAIR_APPLIED"
            or existing.get("contract_sha256") != runner.file_sha256(config_path)
        ):
            raise ValueError("existing D2 extraction repair audit is invalid")
        return existing
    progress_path = output["generation_progress"]
    if not progress_path.is_file():
        result: JsonObject = {
            "schema_version": "jbspan-d2-extraction-repair-v1-1",
            "status": "D2_EXTRACTION_REPAIR_NO_EXISTING_PROGRESS",
            "contract_sha256": runner.file_sha256(config_path),
            "inspected_progress_records": 0,
            "repair_count": 0,
            "model_inference_performed": False,
            "panel_output_observed": False,
            "raw_response_content_reported": False,
        }
        result["result_identity_sha256"] = runner.canonical_sha256(result)
        runner.screen.safe_write(audit_path, result)
        return result
    rows = runner.load_jsonl(progress_path)
    plans = {
        str(row["record_id"]): row for row in runner.load_jsonl(output["primary_plan"])
    }
    privacy = runner.required_mapping(config["privacy"], where="privacy")
    private_root = runner.screen.rooted(
        root, privacy["private_root"], where="private root"
    )
    original_root = private_root / "extraction_repair_v1_1" / "original_records"
    repaired_rows: list[JsonObject] = []
    repaired_audit: list[JsonObject] = []
    for row in rows:
        if row.get("operational_pass") is True:
            repaired_rows.append(row)
            continue
        if not (
            row.get("return_code") == 0
            and row.get("error_type") is None
            and row.get("response_extraction_error") == "ValueError"
            and row.get("response_character_length") == 0
            and row.get("chat_template_active") is True
            and row.get("gpu_offload_logged") is True
        ):
            raise ValueError("D2 failed record does not match the frozen repair signature")
        execution_sha = str(row["execution_identity_sha256"])
        private_path = private_root / "scientific_generations" / f"{execution_sha}.json"
        original_sha = runner.file_sha256(private_path)
        if original_sha != row["private_record_sha256"]:
            raise ValueError("D2 failed private record differs from its safe checkpoint")
        private = runner.load_object(private_path)
        prompt = str(private.get("prompt", ""))
        stdout = str(private.get("stdout", ""))
        if not (
            0 < len(prompt) <= 500
            and prompt.replace("\r\n", "\n").replace("\r", "\n").endswith("\n")
            and private.get("response") == ""
            and private.get("response_extraction_error") == "ValueError"
        ):
            raise ValueError("D2 private record does not match trailing-newline signature")
        response = extract_simple_io_response_v3(stdout, prompt)
        if not response:
            raise ValueError("D2 repaired response is empty")
        backup_path = original_root / f"{execution_sha}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if backup_path.is_file():
            if runner.file_sha256(backup_path) != original_sha:
                raise ValueError("D2 original-record backup conflicts")
        else:
            temporary = backup_path.with_name(f".{backup_path.name}.{os.getpid()}.tmp")
            shutil.copyfile(private_path, temporary)
            temporary.replace(backup_path)
        private["response"] = response
        private["response_extraction_error"] = None
        private["response_extractor_version"] = EXTRACTOR_VERSION
        private["response_repaired_from_preserved_stdout"] = True
        private["extraction_repair_provenance"] = {
            "amendment": "D2_EXTRACTION_V1_1_TRAILING_NEWLINE_ONLY",
            "original_private_record_sha256": original_sha,
            "original_backup_sha256": runner.file_sha256(backup_path),
            "model_rerun": False,
        }
        p3.atomic_write_json(private_path, private)
        repaired_sha = runner.file_sha256(private_path)
        safe = p3.safe_invocation(
            private,
            int(private["execution_identity"]["generation_parameters"]["maximum_new_tokens"]),
        )
        plan = plans[str(row["record_id"])]
        repaired = {
            "record_id": row["record_id"],
            "execution_order": row["execution_order"],
            "instance_id": plan["instance_id"],
            "pair_id": plan["pair_id"],
            "selected_unit_ids": plan["selected_unit_ids"],
            "subset_size": plan["subset_size"],
            "neutralizer_id": plan["neutralizer_id"],
            **safe,
            "private_record_sha256": repaired_sha,
            "eligible_for_panel": safe["eligible_for_screening"],
        }
        if repaired["operational_pass"] is not True:
            raise ValueError("D2 repaired record remains operationally ineligible")
        repaired_rows.append(repaired)
        repaired_audit.append(
            {
                "record_id": row["record_id"],
                "execution_order": row["execution_order"],
                "execution_identity_sha256": execution_sha,
                "prompt_sha256": row["prompt_sha256"],
                "original_private_record_sha256": original_sha,
                "original_backup_sha256": runner.file_sha256(backup_path),
                "repaired_private_record_sha256": repaired_sha,
                "repaired_response_sha256": safe["response_sha256"],
                "repaired_response_utf8_bytes": safe["response_utf8_bytes"],
                "model_rerun": False,
            }
        )
    repaired_rows.sort(key=lambda value: int(value["execution_order"]))
    runner.screen.safe_write_jsonl(progress_path, repaired_rows)
    result = {
        "schema_version": "jbspan-d2-extraction-repair-v1-1",
        "status": "D2_EXTRACTION_REPAIR_APPLIED",
        "contract_sha256": runner.file_sha256(config_path),
        "inspected_progress_records": len(rows),
        "repair_count": len(repaired_audit),
        "repair_signature": {
            "return_code_zero": True,
            "runtime_error_absent": True,
            "legacy_extraction_error": "ValueError",
            "legacy_response_empty": True,
            "prompt_character_length_maximum": 500,
            "prompt_ends_normalized_lf": True,
            "exact_prompt_marker_required": 1,
            "exact_timing_boundary_required": 1,
        },
        "repairs": repaired_audit,
        "model_inference_performed": False,
        "panel_output_observed": False,
        "raw_response_content_reported": False,
    }
    result["result_identity_sha256"] = runner.canonical_sha256(result)
    runner.screen.safe_write(audit_path, result)
    return result


def main() -> int:
    root = Path(".").resolve()
    config_path = (
        root
        / "configs/natural_language_localization/topology_d2_micro_pilot_v1.json"
    )
    validate_amendment(root)
    p3 = patch_extractor(root)
    repair_existing_failed_records(root, config_path, p3)
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
