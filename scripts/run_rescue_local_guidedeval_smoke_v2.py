"""Run twelve frozen harmless GuidedEval fixtures on an owned local Ministral server."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402
from jbspan.guided_recovery import GuidelineSpec, classify_single_judge  # noqa: E402

SCHEMA = "jbspan-rescue-local-guidedeval-smoke-v2"
DEFAULT_CONFIG = "configs/natural_language_localization/rescue_local_guidedeval_smoke_v2.json"


def verify(root: Path, config_path: Path, expected_hash: str) -> dict[str, Any]:
    if support.file_digest(config_path) != expected_hash:
        raise ValueError("exact smoke contract file hash differs")
    config = support.read_object(config_path)
    if (
        config.get("schema_version") != SCHEMA
        or config.get("frozen") is not True
        or config.get("scope") != "HARMLESS_SYNTHETIC_FIXTURES_ONLY"
    ):
        raise ValueError("harmless smoke contract must be frozen")
    if len(config["fixtures"]) != 12 or len({x["id"] for x in config["fixtures"]}) != 12:
        raise ValueError("exactly twelve unique fixtures required")
    for fixture in config["fixtures"]:
        if (
            fixture["harmless"] is not True
            or len(fixture["expected_matches"]) != 2
            or any(type(x) is not bool for x in fixture["expected_matches"])
        ):
            raise ValueError("fixture expectation contract differs")
    for spec in config["dependencies"].values():
        path = support.contained(root, spec["path"])
        if support.file_digest(path) != spec["sha256"]:
            raise ValueError("frozen smoke dependency differs")
    model = config["runtime"]["model"]
    model_path = support.contained(root, model["path"])
    if (
        model_path.stat().st_size != model["size_bytes"]
        or support.file_digest(model_path) != model["sha256"]
    ):
        raise ValueError("frozen Ministral model identity differs")
    runtime = config["runtime"]
    archive_path = support.contained(root, runtime["archive"]["path"])
    if support.file_digest(archive_path) != runtime["archive"]["sha256"]:
        raise ValueError("frozen runtime archive identity differs")
    runtime_directory = support.contained(root, runtime["server"]["path"]).parent
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            local = support.contained(runtime_directory, entry.filename)
            if support.digest_bytes(archive.read(entry)) != support.file_digest(local):
                raise ValueError("extracted runtime differs from frozen archive")
    return config


def fixture_case(official: dict[str, Any], fixture: dict[str, Any], index: int) -> Any:
    return official["models"].GuidedBenchCase.from_dict(
        {
            "id": fixture["id"],
            "index": index,
            "benchmark_version": "harmless-local-smoke-v2",
            "subset": "core",
            "topic": "harmless_synthetic",
            "target": "synthetic_fixture",
            "question": fixture["question"],
            "guidelines": fixture["guidelines"],
        }
    )


def local_json(url: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = support.encode(payload) if payload is not None else None
    request = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as handle:
        body = handle.read(1048576)
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("local service returned a nonobject")
    return value


def run(root: Path, config_path: Path, contract_hash: str) -> dict[str, Any]:
    config = verify(root, config_path, contract_hash)
    result_path = support.contained(root, config["recording"]["safe_result"])
    if result_path.exists():
        result = support.read_object(result_path)
        if result["contract_sha256"] != contract_hash:
            raise ValueError("existing smoke result belongs to a different contract")
        return result
    official_config = support.read_object(root / support.CONFIG)
    official = support.load_official(root, official_config)
    runtime = config["runtime"]
    private = support.contained(root, config["recording"]["private_directory"])
    private.mkdir(parents=True, exist_ok=True)
    support.write_once(
        private / "contract.receipt.safe.json",
        {
            "contract_sha256": contract_hash,
            "fixture_vector_sha256": support.digest(config["fixtures"]),
            "frozen_before_first_dispatch": True,
        },
    )
    host, port = runtime["host"], runtime["port"]
    with socket.socket() as probe:
        if probe.connect_ex((host, port)) == 0:
            raise RuntimeError("frozen local port already occupied; no existing process adopted")
    command = [
        str(support.contained(root, runtime["server"]["path"])),
        "--model",
        str(support.contained(root, runtime["model"]["path"])),
        *runtime["server_args"],
    ]
    started = time.monotonic()
    deadline = started + config["limits"]["maximum_suite_seconds"]
    process = None
    rows = []
    operation_error = None
    owned_pid = None
    log_path = private / f"server-{time.time_ns()}.log"
    with log_path.open("xb") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=Path(command[0]).parent,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            owned_pid = process.pid
            support.write_once(
                private / f"server-{owned_pid}.ownership.safe.json",
                {
                    "pid": owned_pid,
                    "contract_sha256": contract_hash,
                    "command_sha256": support.digest(command),
                    "host": host,
                    "port": port,
                },
            )
            print(json.dumps({"stage": "OWNED_SERVER_STARTING", "pid": owned_pid}), flush=True)
            health_deadline = min(deadline, started + config["limits"]["startup_seconds"])
            while time.monotonic() < health_deadline:
                if process.poll() is not None:
                    raise RuntimeError("owned server exited during startup")
                try:
                    if local_json(f"http://{host}:{port}/health", None, 2).get("status") == "ok":
                        break
                except (OSError, ValueError, urllib.error.URLError):
                    time.sleep(0.25)
            else:
                raise TimeoutError("owned server startup deadline")
            startup_seconds = time.monotonic() - started
            print(
                json.dumps({"stage": "OWNED_SERVER_READY", "seconds": startup_seconds}), flush=True
            )
            for index, fixture in enumerate(config["fixtures"], 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("whole-suite deadline")
                case = fixture_case(official, fixture, index)
                prompt = official["prompt_builder"].build_guided_prompt(case, fixture["response"])
                request = support.make_request(official, config["judge"], prompt)
                identity = {
                    "contract_sha256": contract_hash,
                    "fixture_id": fixture["id"],
                    "request_sha256": support.digest(request),
                }
                key = support.digest(identity)
                pending = private / f"{key}.pending.safe.json"
                vendor_path = private / f"{key}.vendor.private.json"
                if vendor_path.exists():
                    record = support.read_object(vendor_path)
                    if record["identity"] != identity:
                        raise ValueError("existing local fixture identity differs")
                else:
                    if pending.exists():
                        raise RuntimeError("uncertain prior fixture dispatch; no automatic resend")
                    with pending.open("xb") as handle:
                        handle.write(support.encode(identity))
                        handle.flush()
                        os.fsync(handle.fileno())
                    call_started = time.monotonic()
                    reply = local_json(
                        f"http://{host}:{port}/v1/chat/completions",
                        request,
                        min(config["limits"]["request_seconds"], remaining),
                    )
                    record = {
                        "identity": identity,
                        "vendor_reply": reply,
                        "elapsed_seconds": time.monotonic() - call_started,
                    }
                    support.write_once(vendor_path, record, safe=False)
                evaluation, receipt = support.parse_reply(
                    official, case, config["judge"], record["vendor_reply"]
                )
                matches = [point.matched for point in evaluation.point_results]
                usage = record["vendor_reply"].get("usage", {})
                completion_tokens = usage.get("completion_tokens")
                row = {
                    "fixture_id": fixture["id"],
                    "category": fixture["category"],
                    "expected_matches": fixture["expected_matches"],
                    "observed_matches": matches,
                    "parsed": evaluation.parsed,
                    "error_code": evaluation.error_code,
                    "exact_vector": evaluation.parsed and matches == fixture["expected_matches"],
                    "outcome": classify_single_judge(
                        evaluation, tuple(GuidelineSpec(g.id, g.type) for g in case.guidelines)
                    ).value,
                    "elapsed_seconds": record["elapsed_seconds"],
                    "completion_tokens": completion_tokens,
                    "input_tokens": usage.get("prompt_tokens"),
                    "judge_output_sha256": receipt["judge_output_sha256"],
                    "vendor_receipt_sha256": support.file_digest(vendor_path),
                }
                rows.append(row)
                support.write_once(private / f"{key}.result.safe.json", row)
                print(
                    json.dumps(
                        {
                            "stage": "FIXTURE_COMPLETE",
                            "case": index,
                            "total": 12,
                            "parsed": row["parsed"],
                            "exact_vector": row["exact_vector"],
                            "elapsed_seconds": row["elapsed_seconds"],
                            "completion_tokens": completion_tokens,
                        }
                    ),
                    flush=True,
                )
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            operation_error = type(exc).__name__
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    passed = (
        len(rows) == 12 and all(row["exact_vector"] for row in rows) and operation_error is None
    )
    result = {
        "schema_version": SCHEMA,
        "status": "LOCAL_GUIDEDEVAL_HARMLESS_SMOKE_PASS"
        if passed
        else "LOCAL_GUIDEDEVAL_HARMLESS_SMOKE_FAIL",
        "contract_sha256": contract_hash,
        "evidence_class": "HARMLESS_LOCAL_RUBRIC_EXECUTION_FEASIBILITY_ONLY",
        "gate": {
            "pass": passed,
            "expected_cases": 12,
            "completed_cases": len(rows),
            "parsed_cases": sum(row["parsed"] for row in rows),
            "exact_vector_cases": sum(row["exact_vector"] for row in rows),
        },
        "rows": rows,
        "operation_error_type": operation_error,
        "elapsed_seconds": time.monotonic() - started,
        "observed_generation_seconds": sum(row["elapsed_seconds"] for row in rows),
        "observed_completion_tokens": sum(row["completion_tokens"] or 0 for row in rows),
        "owned_server_pid": owned_pid,
        "owned_server_stopped": process is None or process.poll() is not None,
        "server_log_sha256": support.file_digest(log_path),
        "scope": {
            "c1n_read": False,
            "heldout_read": False,
            "harmful_case_read": False,
            "paid_api_calls": 0,
            "local_human_safety_calibration": False,
            "rescue_hypothesis_verified": False,
        },
    }
    result["result_identity_sha256"] = support.digest(result)
    support.write_once(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    path = support.contained(root, args.config)
    if args.execute:
        result = run(root, path, args.config_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["gate"]["pass"] else 1
    verify(root, path, args.config_sha256)
    print(json.dumps({"schema_version": SCHEMA, "status": "FROZEN_LOCAL_SMOKE_PREFLIGHT_PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
