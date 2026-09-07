"""Development-only GuidedEval transport and crash-conservative checkpoint support.

The default readiness path reads only safe manifests and pinned source code. It
does not rerun the V1 binder, read the full benchmark, or open victim records.
Live execution requires a separately frozen contract and a development-only case
bundle. No target generation interface is provided here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import types
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from jbspan.guided_recovery import (
    GuidelineSpec,
    JudgeEvaluation,
    JudgePointResult,
    classify_single_judge,
    consensus_evaluation,
)

Json = dict[str, Any]
SCHEMA = "jbspan-rescue-guidedeval-development-runtime-v2"
BASE = "data/natural_language_localization/rescue_guidedeval_development_v1"
CONFIG = "configs/natural_language_localization/rescue_guidedeval_development_preflight_v1.json"
PLAN_PATH = f"{BASE}/input_plan.safe.jsonl"
PREFLIGHT_PATH = f"{BASE}/preflight.safe.json"
PINNED = {
    CONFIG: "d1ba99d15e0383e78e12c5c7a40163b609bf7ea93c8db53b922b25986f871af1",
    PLAN_PATH: "e914a2a2bef278c9f3b65bc839c18bfc77a65f59d6fc142a160c0921d2f61f92",
    PREFLIGHT_PATH: "dd5c6133f3fa501cfa029c531d2d90c09dee65d0f78b449c7fe0067f230197a3",
}
RUNTIME_FILES = (
    "src/jbspan/rescue_guidedeval_development.py",
    "scripts/run_rescue_guidedeval_development_v2.py",
    "tests/test_rescue_guidedeval_development_v2.py",
)
PRIVATE_BASE = "artifacts/rescue_guidedeval_development_v2"
SAFE_BASE = "data/natural_language_localization/rescue_guidedeval_development_v2"
SCOPE = {
    "development_c1n_seed11_only": True,
    "primary_a_access_allowed": False,
    "replication_reserve_b_access_allowed": False,
    "target_generation_allowed": False,
    "c1n_reclassification_allowed": False,
}
PROHIBITED = {
    "payload",
    "prompt",
    "response",
    "response_text",
    "question",
    "description",
    "examples",
    "raw_output",
    "stdout",
    "stderr",
    "content",
    "reason",
    "judge_text",
}


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: object) -> str:
    return digest_bytes(encode(value))


def encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def contained(root: Path, relative: str) -> Path:
    path = Path(relative)
    candidate = (root / path).resolve()
    if path.is_absolute() or not candidate.is_relative_to(root.resolve()):
        raise ValueError("path must remain inside the declared root")
    return candidate


def read_object(path: Path) -> Json:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def read_rows(path: Path) -> list[Json]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("expected object rows")
    return rows


def content_free(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in PROHIBITED:
                raise ValueError("raw-content key in safe artifact")
            content_free(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            content_free(child)


def write_once(path: Path, value: object, *, safe: bool = True) -> None:
    """Publish a complete immutable file without an exists/replace race.

    The hard link is an atomic exclusive publish on the supported local NTFS
    filesystem. Unsupported filesystems fail closed; no overwrite fallback.
    """
    if safe:
        content_free(value)
    publish_bytes_once(path, encode(value) + b"\n")


def publish_bytes_once(path: Path, data: bytes) -> None:
    """Internal exclusive publisher; callers enforce safe/private output placement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError("nonidentical write-once artifact already exists")
        return
    descriptor, name = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise RuntimeError("concurrent nonidentical write-once artifact") from None
    finally:
        temporary.unlink(missing_ok=True)


def verify_project(root: Path) -> tuple[Json, list[Json]]:
    """Verify existing safe bindings without reading any dataset/private text."""
    for relative, expected in PINNED.items():
        if file_digest(contained(root, relative)) != expected:
            raise ValueError("pinned V1 safe artifact identity differs")
    config = read_object(root / CONFIG)
    dependencies = {
        key: value for key, value in config["dependencies"].items() if key != "guidedbench_core"
    }
    dependencies.update(config["official_guidedbench_source"]["files"])
    for spec in dependencies.values():
        path = contained(root, spec["path"])
        if file_digest(path) != spec["sha256"] or path.stat().st_size != spec["size_bytes"]:
            raise ValueError("frozen source or safe dependency identity differs")
    plan = read_rows(root / BASE / "input_plan.safe.jsonl")
    content_free(plan)
    if len(plan) != 180 or len({row["record_id"] for row in plan}) != 180:
        raise ValueError("C1N development denominator differs")
    for row in plan:
        identity = row["plan_row_identity_sha256"]
        if (
            digest({key: value for key, value in row.items() if key != "plan_row_identity_sha256"})
            != identity
        ):
            raise ValueError("input plan row identity differs")
        if (
            row["development_origin"] != "C1N_SEED11_VALID_NEGATIVE_REUSE"
            or row["seed"] != 11
            or row["condition"] not in {"DIRECT", "ATTACKED_H4RM3L"}
        ):
            raise ValueError("development scope differs")
    return config, plan


def load_official(root: Path, config: Json) -> Json:
    """Load only pinned pure model/prompt/parser modules, bypassing dataset imports."""
    package_name = "_jbspan_pinned_guidedbench_v2"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    loaded: Json = {}
    for key, module_name in (
        ("models", "models"),
        ("prompt_builder", "prompt"),
        ("parser", "parsing"),
    ):
        frozen = config["official_guidedbench_source"]["files"][key]
        path = contained(root, frozen["path"])
        if file_digest(path) != frozen["sha256"]:
            raise ValueError("official source identity differs")
        name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ValueError("cannot load pinned official source")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded[key] = module
    return loaded


def template(root: Path, plan: Sequence[Json]) -> Json:
    return {
        "schema_version": SCHEMA,
        "frozen": False,
        "scope": dict(SCOPE),
        "input_plan_sha256": PINNED[f"{BASE}/input_plan.safe.jsonl"],
        "runtime_sha256": {name: file_digest(root / name) for name in RUNTIME_FILES},
        "development_cases": {
            "path": f"{PRIVATE_BASE}/development_cases.jsonl",
            "sha256": "REQUIRED_EXACT_45_CASE_DEVELOPMENT_BUNDLE_HASH",
        },
        "judges": [
            {
                "judge_id": "REQUIRED_JUDGE_ID",
                "provider": "REQUIRED_PROVIDER",
                "endpoint": "https://REQUIRED_HOST/v1/chat/completions",
                "requested_model": "REQUIRED_EXACT_MODEL_ID",
                "expected_returned_model": "REQUIRED_EXACT_RETURNED_MODEL_ID",
                "snapshot_evidence": "REQUIRED_IMMUTABILITY_OR_LOCAL_ARTIFACT_EVIDENCE",
                "api_key_env": "REQUIRED_CREDENTIAL_ENVIRONMENT_VARIABLE",
                "auth_required": True,
                "temperature": 0.0,
                "max_tokens": 800,
                "max_request_utf8_bytes": 100000,
                "max_reply_utf8_bytes": 100000,
                "timeout_seconds": 120,
                "max_cost_per_request_usd": None,
                "cost_bound_basis": "REQUIRED_PROVIDER_PRICING_AND_INPUT_BOUND",
            }
        ],
        "budget": {"max_requests": len(plan), "max_cost_usd": None},
        "retry_policy": "NO_AUTOMATIC_RETRY_UNCERTAIN_DISPATCH_REQUIRES_RECONCILIATION",
        "endpoint_rule": "ZERO_VS_ANY_MATCH_WITH_POINTWISE_UNANIMOUS_INTERVAL",
        "endpoint_type": "GUIDELINE_POINT_ZERO_VS_PRESENT",
        "recording": "PRIVATE_JUDGE_TEXT_ONLY_NO_TARGET_RESPONSE_OR_REQUEST_COPY",
    }


def _positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def validate_contract(root: Path, contract: Json, plan: Sequence[Json]) -> None:
    if (
        contract.get("schema_version") != SCHEMA
        or contract.get("frozen") is not True
        or contract.get("scope") != SCOPE
    ):
        raise ValueError("a separately frozen development-only contract is required")
    if contract.get("input_plan_sha256") != PINNED[f"{BASE}/input_plan.safe.jsonl"]:
        raise ValueError("contract does not bind the exact completed C1N plan")
    if contract.get("runtime_sha256") != {name: file_digest(root / name) for name in RUNTIME_FILES}:
        raise ValueError("runtime changed after contract freeze")
    expected = template(root, plan)
    for key in ("retry_policy", "endpoint_rule", "endpoint_type", "recording"):
        if contract.get(key) != expected[key]:
            raise ValueError("checkpoint or endpoint policy differs")
    bundle = contract.get("development_cases", {})
    bundle_path = contained(
        root / PRIVATE_BASE, str(bundle.get("path", "")).removeprefix(f"{PRIVATE_BASE}/")
    )
    if (
        not str(bundle.get("path", "")).startswith(f"{PRIVATE_BASE}/")
        or not re.fullmatch(r"[0-9a-f]{64}", str(bundle.get("sha256", "")))
        or not bundle_path.is_relative_to((root / PRIVATE_BASE).resolve())
    ):
        raise ValueError("a pinned development-only case bundle is required")
    judges = contract.get("judges")
    if not isinstance(judges, list) or not judges:
        raise ValueError("an explicit judge panel is required")
    ids: list[str] = []
    for judge in judges:
        for key in (
            "judge_id",
            "provider",
            "endpoint",
            "requested_model",
            "expected_returned_model",
            "snapshot_evidence",
            "cost_bound_basis",
        ):
            if (
                not isinstance(judge.get(key), str)
                or not judge[key].strip()
                or "REQUIRED" in judge[key]
            ):
                raise ValueError("explicit provider, model, snapshot and budget evidence required")
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", judge["judge_id"]):
            raise ValueError("invalid judge identity")
        ids.append(judge["judge_id"])
        url = urllib.parse.urlsplit(judge["endpoint"])
        local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            (url.scheme != "https" and not local_http)
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("endpoint must use HTTPS or explicit loopback HTTP without secrets")
        if type(judge.get("auth_required")) is not bool:
            raise ValueError("explicit authentication requirement is required")
        if judge["auth_required"] and not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", str(judge.get("api_key_env", ""))
        ):
            raise ValueError("explicit credential environment variable is required")
        for key in ("max_tokens", "max_request_utf8_bytes", "max_reply_utf8_bytes"):
            if type(judge.get(key)) is not int or judge[key] <= 0:
                raise ValueError("positive integer token and byte limits required")
        if not _positive_number(judge.get("timeout_seconds")):
            raise ValueError("positive finite timeout required")
        if (
            type(judge.get("temperature")) not in (int, float)
            or not math.isfinite(judge["temperature"])
            or judge["temperature"] < 0
        ):
            raise ValueError("explicit finite decoding temperature required")
        if not _nonnegative_number(judge.get("max_cost_per_request_usd")):
            raise ValueError("a finite conservative per-request cost bound is required")
    if len(set(ids)) != len(ids):
        raise ValueError("judge IDs must be unique")
    budget = contract.get("budget", {})
    if (
        type(budget.get("max_requests")) is not int
        or budget["max_requests"] < len(plan) * len(judges)
        or not _nonnegative_number(budget.get("max_cost_usd"))
    ):
        raise ValueError("budget must cover the complete frozen development panel")
    bound = len(plan) * sum(Decimal(str(judge["max_cost_per_request_usd"])) for judge in judges)
    if bound > Decimal(str(budget["max_cost_usd"])):
        raise ValueError("complete run exceeds frozen cost ceiling")


def load_development_cases(root: Path, contract: Json, plan: Sequence[Json]) -> Json:
    spec = contract["development_cases"]
    path = contained(root, spec["path"])
    if file_digest(path) != spec["sha256"]:
        raise ValueError("development-only case bundle identity differs")
    rows = read_rows(path)
    cases = {str(row["id"]): row for row in rows}
    expected = {str(row["source_id"]): row for row in plan}
    if len(rows) != 45 or len(cases) != 45 or set(cases) != set(expected):
        raise ValueError("case bundle must contain exactly the 45 C1N development cases")
    for source_id, case in cases.items():
        row = expected[source_id]
        if (
            digest(case) != row["source_row_sha256"]
            or digest(case["guidelines"]) != row["guideline_manifest_sha256"]
            or len(case["guidelines"]) != row["guideline_count"]
            or digest_bytes(case["question"].encode("utf-8")) != row["payload_sha256"]
        ):
            raise ValueError("development case differs from the existing frozen row")
    return cases


def select_development_cases(
    source: Path, expected_sha256: str, plan: Sequence[Json]
) -> list[Json]:
    """Stream frozen JSONL bytes, decoding only IDs already admitted by the safe plan.

    Unselected lines pass only through the byte hash and an ID-field regex. They
    are never decoded as text/JSON, printed, selected by content, or retained.
    The source hash and selected canonical row hashes must both match exactly.
    """
    if file_digest(source) != expected_sha256:
        raise ValueError("frozen full-source byte identity differs")
    expected = {str(row["source_id"]): row for row in plan}
    allowed = {source_id.encode("ascii"): source_id for source_id in expected}
    source_hash = hashlib.sha256()
    selected: Json = {}
    identifier = re.compile(rb'(?<!\\)"id"\s*:\s*"(guidedbench-[0-9]+)"')
    with source.open("rb") as handle:
        for raw_line in handle:
            source_hash.update(raw_line)
            matches = identifier.findall(raw_line)
            if len(matches) != 1:
                raise ValueError("source JSONL does not expose exactly one selectable case ID")
            if matches[0] not in allowed:
                continue
            source_id = allowed[matches[0]]
            row = json.loads(raw_line)
            if (
                source_id in selected
                or row.get("id") != source_id
                or digest(row) != expected[source_id]["source_row_sha256"]
            ):
                raise ValueError("selected development row identity differs")
            selected[source_id] = row
    if source_hash.hexdigest() != expected_sha256:
        raise ValueError("frozen full-source byte identity differs")
    if set(selected) != set(expected):
        raise ValueError("not every frozen development case was found")
    return [selected[source_id] for source_id in expected]


def prepare_development_cases(root: Path) -> Json:
    """Explicit preparation operation; never called by readiness or template printing."""
    config, plan = verify_project(root)
    source = config["dependencies"]["guidedbench_core"]
    source_path = Path(source["path"])
    if not source_path.is_absolute():
        source_path = contained(root, source["path"])
    selected = select_development_cases(source_path, source["sha256"], plan)
    if len(selected) != 45:
        raise ValueError("exactly 45 C1N development cases are required")
    relative = f"{PRIVATE_BASE}/development_cases.jsonl"
    path = contained(root, relative)
    publish_bytes_once(path, b"".join(encode(row) + b"\n" for row in selected))
    return {
        "schema_version": SCHEMA,
        "status": "DEVELOPMENT_ONLY_CASE_BUNDLE_PREPARED",
        "development_cases": {"path": relative, "sha256": file_digest(path)},
        "case_rows": len(selected),
        "target_responses_copied": 0,
        "network_calls": 0,
        "full_source_bytes_streamed_for_integrity": True,
        "unselected_cases_json_decoded": False,
        "unselected_cases_copied": False,
        "selection_rule": "FROZEN_C1N_SOURCE_IDS_AND_EXACT_EXISTING_ROW_HASHES",
    }


def load_existing_response(root: Path, config: Json, row: Json) -> str:
    relative = f"{row['target_id']}/{row['execution_identity_sha256']}.json"
    path = contained(contained(root, config["private_record_root"]), relative)
    if file_digest(path) != row["private_record_sha256"]:
        raise ValueError("existing C1N private record identity differs")
    private = read_object(path)
    response = private.get("response")
    payload = private.get("payload")
    if (
        not isinstance(response, str)
        or not isinstance(payload, str)
        or digest_bytes(response.encode("utf-8")) != row["response_sha256"]
        or len(response.encode("utf-8")) != row["response_utf8_bytes"]
        or digest_bytes(payload.encode("utf-8")) != row["payload_sha256"]
        or private.get("execution_identity_sha256") != row["execution_identity_sha256"]
    ):
        raise ValueError("existing C1N text identity differs")
    return response


class TransportFailure(RuntimeError):
    """Dispatch may have occurred; no automatic retry is safe."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def transport(judge: Json, request: Json) -> Json:
    """One request to the explicit chat-completions-compatible endpoint, no retries."""
    headers = {"Content-Type": "application/json"}
    if judge["auth_required"]:
        credential = os.environ.get(judge["api_key_env"])
        if not credential:
            raise ValueError("frozen judge credential is unavailable")
        headers["Authorization"] = f"Bearer {credential}"
    request_bytes = encode(request)
    if len(request_bytes) > judge["max_request_utf8_bytes"]:
        raise ValueError("request exceeds frozen byte bound")
    connection = urllib.request.Request(judge["endpoint"], request_bytes, headers, method="POST")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(connection, timeout=judge["timeout_seconds"]) as handle:
            raw = handle.read(judge["max_reply_utf8_bytes"] + 1)
        if len(raw) > judge["max_reply_utf8_bytes"]:
            raise TransportFailure("REPLY_BYTE_BOUND_EXCEEDED")
        reply = json.loads(raw)
        if not isinstance(reply, dict):
            raise TransportFailure("MALFORMED_PROVIDER_REPLY")
        return reply
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # Never put provider bodies, request text, URL credentials or exceptions in stdout.
        raise TransportFailure("DISPATCH_UNCERTAIN_RECONCILIATION_REQUIRED") from exc


def parse_reply(
    official: Json, case: Any, judge: Json, reply: Json
) -> tuple[JudgeEvaluation, Json]:
    text = ""
    failure = None
    finish = None
    if reply.get("model") != judge["expected_returned_model"]:
        failure = "RETURNED_MODEL_MISMATCH"
    choices = reply.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        failure = failure or "MALFORMED_PROVIDER_REPLY"
    else:
        choice = choices[0]
        finish = choice.get("finish_reason")
        message = choice.get("message")
        if not isinstance(message, dict):
            failure = failure or "MALFORMED_PROVIDER_REPLY"
        else:
            text = message.get("content") if isinstance(message.get("content"), str) else ""
            if message.get("refusal"):
                failure = failure or "JUDGE_REFUSAL"
            if message.get("tool_calls") or message.get("function_call"):
                failure = failure or "UNEXPECTED_TOOL_OUTPUT"
            if finish != "stop":
                failure = failure or "NONSTOP_OR_TRUNCATED_OUTPUT"
            if not text.strip():
                failure = failure or "EMPTY_JUDGE_OUTPUT"
    if failure is None:
        try:
            parsed = official["parser"].parse_guided_response(text, case, judge=judge["judge_id"])
        except official["parser"].EvaluationParseError:
            failure = "POINT_VECTOR_PARSE_FAILURE"
    if failure:
        evaluation = JudgeEvaluation(judge["judge_id"], str(case.id), error_code=failure)
    else:
        evaluation = JudgeEvaluation(
            judge["judge_id"],
            str(case.id),
            tuple(
                JudgePointResult(point.guideline_id, point.guideline_type, point.matched)
                for point in parsed.point_results
            ),
        )
    receipt = {
        "judge_text": text,
        "judge_output_sha256": digest_bytes(text.encode("utf-8")),
        "finish_reason_sha256": digest(finish),
        "returned_model_sha256": digest(reply.get("model")),
    }
    return evaluation, receipt


def evaluate_once(
    directory: Path,
    execution_key: str,
    identity: Json,
    judge: Json,
    request: Json,
    official: Json,
    case: Any,
    *,
    send: Callable[[Json, Json], Json] = transport,
) -> Json:
    """Reuse a completed receipt; an uncertain dispatched request is never resent."""
    directory.mkdir(parents=True, exist_ok=True)
    pending = directory / f"{execution_key}.pending.safe.json"
    private_path = directory / f"{execution_key}.judge.private.json"
    if private_path.exists():
        stored = read_object(private_path)
        body = {key: value for key, value in stored.items() if key != "receipt_sha256"}
        if stored.get("identity") != identity or stored.get("receipt_sha256") != digest(body):
            raise ValueError("completed checkpoint identity differs")
        if not pending.exists() or read_object(pending) != identity:
            raise ValueError("completed checkpoint lacks its matching dispatch journal")
        return stored["safe_result"]
    if pending.exists():
        raise TransportFailure("UNFINISHED_DISPATCH_NO_AUTOMATIC_RETRY")
    if len(encode(request)) > judge["max_request_utf8_bytes"]:
        raise ValueError("request exceeds frozen byte bound")
    # Exclusive ownership, durable before dispatch; a torn marker also blocks retries.
    with pending.open("xb") as handle:
        handle.write(encode(identity))
        handle.flush()
        os.fsync(handle.fileno())
    reply = send(judge, request)
    evaluation, receipt = parse_reply(official, case, judge, reply)
    guidelines = tuple(GuidelineSpec(item.id, item.type) for item in case.guidelines)
    safe = {
        "identity": identity,
        "error_code": evaluation.error_code,
        "outcome": classify_single_judge(evaluation, guidelines).value,
        "points": [
            {
                "guideline_id": item.guideline_id,
                "guideline_type": item.guideline_type,
                "matched": item.matched,
            }
            for item in evaluation.point_results
        ],
        "judge_output_sha256": receipt["judge_output_sha256"],
    }
    content_free(safe)
    stored = {"identity": identity, "safe_result": safe, **receipt}
    stored["receipt_sha256"] = digest(stored)
    write_once(private_path, stored, safe=False)
    return safe


def aggregate(plan: Sequence[Json], judges: Sequence[Json], results: Sequence[Json]) -> Json:
    expected = {
        (row["plan_row_identity_sha256"], judge["judge_id"]) for row in plan for judge in judges
    }
    indexed = {
        (item["identity"]["plan_row_identity_sha256"], item["identity"]["judge_id"]): item
        for item in results
    }
    if set(indexed) != expected or len(indexed) != len(results):
        raise ValueError("aggregate requires the complete unique frozen panel")
    cells: dict[str, Counter[str]] = defaultdict(Counter)
    agreement: dict[str, Counter[str]] = defaultdict(Counter)
    interval_counts: dict[str, Counter[str]] = defaultdict(Counter)
    errors: Counter[str] = Counter()
    for row in plan:
        evaluations = []
        specifications = None
        for judge in judges:
            item = indexed[(row["plan_row_identity_sha256"], judge["judge_id"])]
            cell = f"{judge['judge_id']}|{row['target_id']}|{row['condition']}"
            cells[cell][item["outcome"]] += 1
            if item["error_code"]:
                errors[item["error_code"]] += 1
            points = tuple(JudgePointResult(**point) for point in item["points"])
            evaluations.append(
                JudgeEvaluation(
                    judge["judge_id"], str(row["source_id"]), points, item["error_code"]
                )
            )
            if points:
                specifications = tuple(
                    GuidelineSpec(p.guideline_id, p.guideline_type) for p in points
                )
        if specifications is None:
            outcome = "ABSTAIN"
            interval_counts[f"{row['target_id']}|{row['condition']}"]["all_judges_failed"] += 1
        else:
            consensus = consensus_evaluation(
                tuple(evaluations),
                specifications,
                required_judge_ids=tuple(judge["judge_id"] for judge in judges),
            )
            outcome = consensus.outcome.value
            interval = consensus.score_interval
            interval_cell = interval_counts[f"{row['target_id']}|{row['condition']}"]
            interval_cell["lower_matched_points"] += interval.lower_matched_points
            interval_cell["upper_matched_points"] += interval.upper_matched_points
            interval_cell["total_points_on_rows_with_a_valid_vector"] += interval.total_points
        for left, evaluation in enumerate(evaluations):
            for other in evaluations[left + 1 :]:
                pair = (
                    f"{evaluation.judge_id}|{other.judge_id}|{row['target_id']}|{row['condition']}"
                )
                agreement[pair]["response_pairs"] += 1
                if evaluation.parsed and other.parsed:
                    agreement[pair]["both_parsed_response_pairs"] += 1
                    for first, second in zip(
                        evaluation.point_results, other.point_results, strict=True
                    ):
                        agreement[pair]["paired_points"] += 1
                        agreement[pair]["agreed_points"] += first.matched == second.matched
        cells[f"CONSENSUS|{row['target_id']}|{row['condition']}"][outcome] += 1
    result = {
        "schema_version": SCHEMA,
        "status": "DEVELOPMENT_MEASUREMENT_COMPLETE_NO_RESCUE_OR_CALIBRATION_CLAIM",
        "evidence_class": "POSTOUTCOME_C1N_DEVELOPMENT_MEASUREMENT_ONLY",
        "records": len(plan),
        "judge_results": len(results),
        "cells": {key: dict(sorted(value.items())) for key, value in sorted(cells.items())},
        "error_counts": dict(sorted(errors.items())),
        "judge_pair_agreement": {key: dict(value) for key, value in sorted(agreement.items())},
        "consensus_point_bounds": {
            key: dict(value) for key, value in sorted(interval_counts.items())
        },
        "scope": dict(SCOPE),
        "endpoint_type": "GUIDELINE_POINT_ZERO_VS_PRESENT",
        "paper_valid_confirmation": False,
        "local_human_calibration_performed": False,
    }
    content_free(result)
    return result


def execute(root: Path, config: Json, plan: list[Json], contract: Json) -> Json:
    """The only live entry point; callers must first check the contract file hash."""
    verified_config, verified_plan = verify_project(root)
    if config != verified_config or plan != verified_plan:
        raise ValueError("live inputs differ from the pinned development manifests")
    validate_contract(root, contract, plan)
    for judge in contract["judges"]:
        if judge["auth_required"] and not os.environ.get(judge["api_key_env"]):
            raise ValueError("frozen judge credential is unavailable")
    cases = load_development_cases(root, contract, plan)
    official = load_official(root, config)
    contract_hash = digest(contract)
    destination = contained(root, f"{PRIVATE_BASE}/{contract_hash}/checkpoints")
    results = []
    # Validate every source record before the first paid request without copying text.
    for row in plan:
        case = official["models"].GuidedBenchCase.from_dict(cases[str(row["source_id"])])
        response = load_existing_response(root, config, row)
        prompt = official["prompt_builder"].build_guided_prompt(case, response)
        for judge in contract["judges"]:
            request = make_request(official, judge, prompt)
            if len(encode(request)) > judge["max_request_utf8_bytes"]:
                raise ValueError("development request exceeds frozen byte bound before dispatch")
    for row in plan:
        case = official["models"].GuidedBenchCase.from_dict(cases[str(row["source_id"])])
        response = load_existing_response(root, config, row)
        prompt = official["prompt_builder"].build_guided_prompt(case, response)
        for judge in contract["judges"]:
            request = make_request(official, judge, prompt)
            identity = {
                "contract_sha256": contract_hash,
                "plan_row_identity_sha256": row["plan_row_identity_sha256"],
                "judge_id": judge["judge_id"],
                "request_sha256": digest(request),
            }
            results.append(
                evaluate_once(
                    destination, digest(identity), identity, judge, request, official, case
                )
            )
            if results[-1]["error_code"] == "RETURNED_MODEL_MISMATCH":
                raise RuntimeError("returned model differs; checkpoint saved and dispatch stopped")
    summary = aggregate(plan, contract["judges"], results)
    summary["contract_sha256"] = contract_hash
    summary["results_identity_sha256"] = digest(results)
    summary["reserved_cost_bound_usd"] = len(plan) * sum(
        judge["max_cost_per_request_usd"] for judge in contract["judges"]
    )
    safe_directory = contained(root, f"{SAFE_BASE}/{contract_hash}")
    write_once(safe_directory / "point_results.safe.json", results)
    write_once(safe_directory / "summary.safe.json", summary)
    return summary


def make_request(official: Json, judge: Json, prompt: str) -> Json:
    return {
        "model": judge["requested_model"],
        "temperature": judge["temperature"],
        "max_tokens": judge["max_tokens"],
        "messages": [
            {"role": "system", "content": official["prompt_builder"].JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
