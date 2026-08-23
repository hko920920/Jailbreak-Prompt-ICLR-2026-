from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path

from run_programmatic_agentharm_development_behavior import (
    _select_sample,
    _validate_source_assignment,
)
from run_programmatic_agentharm_smoke import (
    as_array,
    as_object,
    as_string,
    load_attack,
    load_json,
    run_episode,
    safe_episode,
    sha256_text,
    validate_contract,
)

from jbspan.programmatic_agentharm.development_sweep import (
    find_behavior_spec,
    parse_behavior_specs,
)

DEVELOPMENT_CONFIG = Path(
    "configs/programmatic_agentharm/development_behavior_sweep.json"
)
SAFE_OUTPUT = Path(
    "artifacts/programmatic-agentharm-copyright-diagnostic/safe_summary.json"
)
ATTACK_SOURCE = Path("/tmp/h4rm3l-reference-programs.csv")
BEHAVIOR_SLUG = "copyright-64"
CANDIDATE_ID = "v2_dan_refusal_affirmative"
SOURCE_RUN_ID = 32627895339
SOURCE_HEAD_SHA = "a87026698c2f543639d46a3be470ffe6630fbf10"
SOURCE_ARTIFACT_DIGEST = (
    "sha256:033fea8b9c330a18368f5bdc35dc10e68962aaeed9cd6f21edeaff38193ec0fe"
)


def _safe_diagnostic_episode(
    record: dict[str, object],
    *,
    condition: str,
    prompt: str,
    candidate_id: str | None,
    payload_sha256: str,
    payload_start: int,
    payload_end: int,
) -> dict[str, object]:
    safe = safe_episode(
        record=record,
        condition=condition,
        prompt=prompt,
        candidate_id=candidate_id,
        payload_sha256=payload_sha256,
        payload_start=payload_start,
        payload_end=payload_end,
    )
    allowed = {
        "condition",
        "candidate_id",
        "completed",
        "programmatic_score_parsed",
        "programmatic_success",
        "tool_call_count",
        "tool_response_count",
        "tool_calls_sha256",
        "tool_responses_sha256",
        "criteria",
        "criteria_sha256",
        "runtime_error_type",
        "scorer_error_type",
        "capture_count",
        "payload_sha256",
        "prompt_sha256",
        "prompt_character_length",
        "payload_character_start",
        "payload_character_end",
    }
    return {key: value for key, value in safe.items() if key in allowed}


def main() -> int:
    root = Path(".").resolve()
    development = load_json((root / DEVELOPMENT_CONFIG).resolve())
    specs = parse_behavior_specs(development)
    spec = find_behavior_spec(specs, slug=BEHAVIOR_SLUG)

    runtime = load_json(
        root
        / as_string(
            development["runtime_config_path"], where="runtime_config_path"
        )
    )
    manifest, eligible_graders = validate_contract(root, runtime)
    if spec.grading_function not in eligible_graders:
        raise RuntimeError("copyright grader is not programmatically eligible")

    provenance = as_object(development["provenance"], where="provenance")
    if provenance.get("gate0_manifest_identity_sha256") != manifest.get(
        "manifest_identity_sha256"
    ):
        raise RuntimeError("Gate 0 identity changed")
    consumed_split = as_string(
        provenance["consumed_source_split"], where="consumed_source_split"
    )
    _validate_source_assignment(
        manifest=manifest,
        spec=spec,
        consumed_split=consumed_split,
    )

    variant = as_object(development["canonical_variant"], where="canonical_variant")
    sample = _select_sample(
        spec=spec,
        detailed_prompt=bool(variant["detailed_prompt"]),
        hint_included=bool(variant["hint_included"]),
    )
    if not isinstance(sample.input, str):
        raise RuntimeError("copyright AgentHarm input must be a string")
    payload = sample.input
    payload_sha256 = sha256_text(payload)

    frozen_candidates = [
        as_string(item, where="candidate")
        for item in as_array(development["candidate_ids"], where="candidate_ids")
    ]
    if CANDIDATE_ID not in frozen_candidates:
        raise RuntimeError("diagnostic candidate is not frozen")

    diagnostic_runtime = copy.deepcopy(runtime)
    smoke = as_object(
        diagnostic_runtime["operational_smoke"], where="operational_smoke"
    )
    smoke["attack_candidate_id"] = CANDIDATE_ID
    attack_prompt, attack_start, attack_end, node_count = load_attack(
        root=root,
        config=diagnostic_runtime,
        attack_source_csv=ATTACK_SOURCE.resolve(),
        payload=payload,
    )

    logs = Path(tempfile.mkdtemp(prefix="jbspan-copyright-diagnostic-"))
    try:
        original_record = run_episode(
            sample=sample,
            condition="original_auto",
            prompt=payload,
            tool_choice="auto",
            config=diagnostic_runtime,
            inspect_logs=logs / "original_auto",
        )
        dan_record = run_episode(
            sample=sample,
            condition=f"attacked_auto__{CANDIDATE_ID}",
            prompt=attack_prompt,
            tool_choice="auto",
            config=diagnostic_runtime,
            inspect_logs=logs / CANDIDATE_ID,
        )
    finally:
        shutil.rmtree(logs, ignore_errors=True)

    episodes = [
        _safe_diagnostic_episode(
            original_record,
            condition="original_auto",
            prompt=payload,
            candidate_id=None,
            payload_sha256=payload_sha256,
            payload_start=0,
            payload_end=len(payload),
        ),
        _safe_diagnostic_episode(
            dan_record,
            condition=f"attacked_auto__{CANDIDATE_ID}",
            prompt=attack_prompt,
            candidate_id=CANDIDATE_ID,
            payload_sha256=payload_sha256,
            payload_start=attack_start,
            payload_end=attack_end,
        ),
    ]
    complete = all(item.get("completed") is True for item in episodes)
    parsed = all(
        item.get("programmatic_score_parsed") is True for item in episodes
    )
    if complete and parsed:
        status = "COPYRIGHT_DIAGNOSTIC_RESOLVED"
    else:
        status = "COPYRIGHT_DIAGNOSTIC_REPRODUCED_RUNTIME_GAP"

    output: dict[str, object] = {
        "schema_version": "programmatic-agentharm-copyright-diagnostic-v1",
        "status": status,
        "paper_validity": False,
        "development_only": True,
        "diagnostic_only": True,
        "source_run_id": SOURCE_RUN_ID,
        "source_head_sha": SOURCE_HEAD_SHA,
        "source_artifact_digest": SOURCE_ARTIFACT_DIGEST,
        "behavior": spec.to_dict(),
        "candidate_id": CANDIDATE_ID,
        "candidate_node_count": node_count,
        "same_runtime_config": True,
        "same_model": True,
        "same_seed": True,
        "same_prompt_hashes": True,
        "episodes": episodes,
        "completed_episode_count": sum(
            item.get("completed") is True for item in episodes
        ),
        "parsed_episode_count": sum(
            item.get("programmatic_score_parsed") is True for item in episodes
        ),
        "human_judge_used": False,
        "llm_judge_used": False,
        "assistant_free_text_scored": False,
        "raw_prompts_committed": False,
        "raw_responses_committed": False,
        "raw_tool_arguments_committed": False,
        "raw_tool_responses_committed": False,
        "confirmatory_outputs_observed": False,
        "final_outputs_observed": False,
        "causal_oracle_opened": False,
        "wavelet_used": False,
    }
    SAFE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SAFE_OUTPUT.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
