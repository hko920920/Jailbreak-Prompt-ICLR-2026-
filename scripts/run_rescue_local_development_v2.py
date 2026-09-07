"""Run the frozen C1N development judge only after its local harmless smoke passes.

The wrapper owns one loopback-only server process. It never selects a different
model, port, evaluator, or payload cohort, and never modifies the frozen runtime.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as runtime  # noqa: E402

SCHEMA = "jbspan-rescue-local-development-wrapper-v2"
REFERENCE_SMOKE_CONFIG = (
    "configs/natural_language_localization/rescue_local_guidedeval_smoke_v2.json"
)
REFERENCE_SMOKE_SHA256 = "51e2887ec683c91e50330e311eaebf05c1438fee8abc1fe4a8844bd0e82840e1"
SMOKE_SCHEMA = "jbspan-rescue-local-guidedeval-smoke-v2"
PREPARATION = (
    "data/natural_language_localization/rescue_guidedeval_development_v2/case_preparation.safe.json"
)
BUNDLE_SHA256 = "b0b803cb06800f5a931df90e64833c8de70ba54def57e2a9ff0f09b3763a208b"
WRAPPER = "scripts/run_rescue_local_development_v2.py"


def emit(status: str, **fields: object) -> None:
    value = {"schema_version": SCHEMA, "status": status, **fields}
    runtime.content_free(value)
    print(json.dumps(value, sort_keys=True), flush=True)


def local_json(port: int, route: str) -> dict:
    """The only wrapper HTTP reads; proxies and redirects cannot leave loopback."""
    if not route.startswith("/") or "?" in route or "#" in route:
        raise ValueError("invalid local status route")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), runtime._NoRedirect())
    with opener.open(f"http://127.0.0.1:{port}{route}", timeout=2) as handle:
        raw = handle.read(1000001)
    if len(raw) > 1000000:
        raise ValueError("local status byte bound exceeded")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("local status is not an object")
    return value


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                "frozen local port is occupied; no existing server is reused"
            ) from None


def stop_owned(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    emit("OWNED_LOCAL_SERVER_STOPPED", process_id=process.pid, returncode=process.poll())


def await_ready(process: subprocess.Popen, port: int, alias: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    next_update = time.monotonic()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("owned local server exited during startup")
        try:
            healthy = local_json(port, "/health").get("status") == "ok"
            models = local_json(port, "/v1/models") if healthy else {}
            aliases = {row.get("id") for row in models.get("data", []) if isinstance(row, dict)}
            if healthy and alias in aliases and process.poll() is None:
                return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        if time.monotonic() >= next_update:
            emit("WAITING_FOR_OWNED_LOCAL_SERVER", process_id=process.pid)
            next_update = time.monotonic() + 30
        time.sleep(1)
    raise TimeoutError("owned local server did not become ready")


@contextmanager
def owned_server(command: list[str], port: int, alias: str, timeout: float):
    require_free_port(port)
    process = subprocess.Popen(
        command,
        cwd=str(Path(command[0]).parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    emit("OWNED_LOCAL_SERVER_STARTED", process_id=process.pid)
    try:
        await_ready(process, port, alias, timeout)
        yield process
    finally:
        stop_owned(process)


@contextmanager
def report_progress(directory: Path, expected: int):
    """Count checkpoint filenames only; do not inspect private receipt contents."""
    stopped = threading.Event()

    def report() -> None:
        while not stopped.is_set():
            completed = len(list(directory.glob("*.judge.private.json")))
            journaled = len(list(directory.glob("*.pending.safe.json")))
            emit(
                "DEVELOPMENT_CHECKPOINT_PROGRESS",
                completed_judge_results=completed,
                journaled_dispatches=journaled,
                unfinished_dispatches=max(0, journaled - completed),
                expected_judge_results=expected,
            )
            stopped.wait(30)

    thread = threading.Thread(target=report, name="safe-checkpoint-progress", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


def disable_process_proxies() -> None:
    """Constrain this wrapper process and its child to direct localhost transport."""
    for key in list(os.environ):
        if key.casefold() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}:
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"


class QualificationFailure(RuntimeError):
    """No model, case bundle, private response, or live execution may follow."""


def verify_smoke_evidence(
    root: Path, config_relative: str, expected_sha256: str
) -> tuple[dict, dict]:
    """Read only the explicitly selected harmless contract and its safe result."""
    path = runtime.contained(root, config_relative)
    if runtime.file_digest(path) != expected_sha256:
        raise QualificationFailure("selected smoke contract digest differs")
    config = runtime.read_object(path)
    reference_path = runtime.contained(root, REFERENCE_SMOKE_CONFIG)
    if runtime.file_digest(reference_path) != REFERENCE_SMOKE_SHA256:
        raise QualificationFailure("original harmless fixture freeze differs")
    reference = runtime.read_object(reference_path)
    if (
        config.get("schema_version") != SMOKE_SCHEMA
        or config.get("frozen") is not True
        or config.get("scope") != "HARMLESS_SYNTHETIC_FIXTURES_ONLY"
        or config.get("fixtures") != reference["fixtures"]
        or config.get("gate") != reference["gate"]
    ):
        raise QualificationFailure("qualification does not preserve the exact twelve-case gate")
    result_path = runtime.contained(root, config["recording"]["safe_result"])
    if not result_path.as_posix().startswith(
        (root / "data/natural_language_localization").resolve().as_posix() + "/"
    ):
        raise QualificationFailure("smoke result is outside safe records")
    if not result_path.is_file():
        raise QualificationFailure("harmless smoke has not completed")
    result = runtime.read_object(result_path)
    runtime.content_free(result)
    if (
        result.get("schema_version") != SMOKE_SCHEMA
        or result.get("contract_sha256") != expected_sha256
        or result.get("result_identity_sha256")
        != runtime.digest(
            {key: value for key, value in result.items() if key != "result_identity_sha256"}
        )
    ):
        raise QualificationFailure("smoke result does not bind the selected frozen contract")
    gate = result.get("gate", {})
    if (
        result.get("status") != "LOCAL_GUIDEDEVAL_HARMLESS_SMOKE_PASS"
        or gate.get("pass") is not True
        or any(
            gate.get(key) != 12
            for key in ("expected_cases", "completed_cases", "parsed_cases", "exact_vector_cases")
        )
        or result.get("operation_error_type") is not None
        or result.get("owned_server_stopped") is not True
    ):
        raise QualificationFailure("selected local judge failed harmless qualification")
    rows = result.get("rows", [])
    if len(rows) != 12:
        raise QualificationFailure("smoke receipt does not contain all twelve cases")
    for fixture, row in zip(config["fixtures"], rows, strict=True):
        if (
            row.get("fixture_id") != fixture["id"]
            or row.get("expected_matches") != fixture["expected_matches"]
            or row.get("observed_matches") != fixture["expected_matches"]
            or row.get("parsed") is not True
            or row.get("exact_vector") is not True
            or row.get("error_code") is not None
        ):
            raise QualificationFailure("smoke result contradicts an exact fixture expectation")
    spec = config["runtime"]
    if spec.get("host") != "127.0.0.1" or type(spec.get("port")) is not int:
        raise QualificationFailure("qualification must select an explicit loopback server")
    args = spec.get("server_args", [])
    for flag, value in (
        ("--host", "127.0.0.1"),
        ("--port", str(spec["port"])),
        ("--alias", spec["alias"]),
    ):
        if args.count(flag) != 1 or args[args.index(flag) + 1] != value:
            raise QualificationFailure("frozen server command differs from endpoint identity")
    if "--offline" not in args or not 1 <= spec["port"] <= 65535:
        raise QualificationFailure("local execution must be offline on a valid fixed port")
    if (
        config["judge"]["requested_model"] != spec["alias"]
        or config["judge"]["expected_returned_model"] != spec["alias"]
    ):
        raise QualificationFailure("judge and local model alias differ")
    return config, result


def verify_runtime_after_pass(
    root: Path, config_relative: str, config: dict, expected_hash: str
) -> None:
    """Reuse the frozen smoke verifier for model, executable, archive, and all DLLs."""
    for dependency in config["dependencies"].values():
        if runtime.file_digest(runtime.contained(root, dependency["path"])) != dependency["sha256"]:
            raise ValueError("code or source changed since harmless qualification")
    runner_path = runtime.contained(root, config["dependencies"]["runner"]["path"])
    spec = importlib.util.spec_from_file_location(
        "_frozen_rescue_local_smoke_verifier", runner_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen local runtime verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.verify(root, runtime.contained(root, config_relative), expected_hash) != config:
        raise ValueError("frozen smoke runtime verification returned another contract")
    server = config["runtime"]["server"]
    if runtime.file_digest(runtime.contained(root, server["path"])) != server["sha256"]:
        raise ValueError("local server executable differs from the qualified identity")


def build_contract(
    root: Path,
    plan: list[dict],
    smoke: dict,
    result: dict,
    smoke_path: str,
    smoke_hash: str,
    preparation: dict,
) -> dict:
    if (
        len(plan) != 180
        or preparation.get("status") != "DEVELOPMENT_ONLY_CASE_BUNDLE_PREPARED"
        or preparation.get("case_rows") != 45
        or preparation.get("development_cases")
        != {"path": f"{runtime.PRIVATE_BASE}/development_cases.jsonl", "sha256": BUNDLE_SHA256}
    ):
        raise ValueError("exact prepared C1N development bundle is required")
    contract = runtime.template(root, plan)
    contract["frozen"] = True
    contract["development_cases"] = preparation["development_cases"]
    judge = dict(smoke["judge"])
    judge.update(
        {
            "judge_id": smoke["judge"]["judge_id"].removesuffix("-smoke") + "-development",
            "provider": "LOCAL_LLAMA_SERVER_NO_BILLED_API",
            "endpoint": f"http://127.0.0.1:{smoke['runtime']['port']}/v1/chat/completions",
            "snapshot_evidence": "Model, runtime archive and executable hashes from passed smoke.",
            "api_key_env": "LOCAL_NO_AUTH",
            "auth_required": False,
            "max_request_utf8_bytes": 100000,
            "max_reply_utf8_bytes": 1000000,
            "timeout_seconds": smoke["limits"]["request_seconds"],
            "max_cost_per_request_usd": 0,
            "cost_bound_basis": "Owned offline local model; no paid provider or model download.",
        }
    )
    contract["judges"] = [judge]
    contract["budget"] = {"max_requests": 180, "max_cost_usd": 0}
    contract["local_qualification"] = {
        "contract_path": smoke_path,
        "contract_file_sha256": smoke_hash,
        "result_path": smoke["recording"]["safe_result"],
        "result_file_sha256": runtime.file_digest(
            runtime.contained(root, smoke["recording"]["safe_result"])
        ),
        "result_identity_sha256": result["result_identity_sha256"],
        "wrapper_sha256": runtime.file_digest(root / WRAPPER),
        "runtime": smoke["runtime"],
        "decoding": smoke["decoding"],
        "case_preparation_sha256": runtime.file_digest(root / PREPARATION),
        "harmless_feasibility_only_not_local_human_calibration": True,
    }
    runtime.validate_contract(root, contract, plan)
    runtime.content_free(contract)
    return contract


def execute(root: Path, smoke_path: str, smoke_hash: str) -> dict:
    # This guard must remain before model, bundle, private-response reads or process creation.
    smoke, result = verify_smoke_evidence(root, smoke_path, smoke_hash)
    emit("HARMLESS_QUALIFICATION_PASS_VERIFIED", smoke_contract_sha256=smoke_hash)
    verify_runtime_after_pass(root, smoke_path, smoke, smoke_hash)
    config, plan = runtime.verify_project(root)
    preparation = runtime.read_object(root / PREPARATION)
    contract = build_contract(root, plan, smoke, result, smoke_path, smoke_hash, preparation)
    bundle = runtime.contained(root, contract["development_cases"]["path"])
    if runtime.file_digest(bundle) != BUNDLE_SHA256:
        raise ValueError("prepared development bundle changed")
    contract_relative = (
        f"configs/natural_language_localization/rescue_guidedeval_local_{smoke_hash}_v2.json"
    )
    contract_path = runtime.contained(root, contract_relative)
    runtime.write_once(contract_path, contract)
    contract_identity = runtime.digest(contract)
    safe_relative = f"{runtime.SAFE_BASE}/{contract_identity}"
    safe_directory = runtime.contained(root, safe_relative)
    checkpoints = runtime.contained(root, f"{runtime.PRIVATE_BASE}/{contract_identity}/checkpoints")
    emit(
        "LOCAL_DEVELOPMENT_CONTRACT_FROZEN",
        contract_path=contract_relative,
        contract_file_sha256=runtime.file_digest(contract_path),
        contract_identity_sha256=contract_identity,
        safe_result_directory=safe_relative,
        expected_judge_results=180,
        maximum_paid_cost_usd=0,
    )
    spec = smoke["runtime"]
    command = [
        str(runtime.contained(root, spec["server"]["path"])),
        "--model",
        str(runtime.contained(root, spec["model"]["path"])),
        *spec["server_args"],
    ]
    disable_process_proxies()
    with owned_server(
        command, spec["port"], spec["alias"], smoke["limits"]["startup_seconds"]
    ) as process:
        runtime.write_once(
            safe_directory / f"owned_server_{process.pid}_{time.time_ns()}.safe.json",
            {
                "process_id": process.pid,
                "command_sha256": runtime.digest(command),
                "contract_sha256": contract_identity,
                "smoke_contract_sha256": smoke_hash,
                "host": "127.0.0.1",
                "port": spec["port"],
                "owned_process_only": True,
            },
        )
        with report_progress(checkpoints, 180):
            summary = runtime.execute(root, config, plan, contract)
    emit(
        "LOCAL_DEVELOPMENT_FINISHED",
        safe_result_directory=safe_relative,
        completed_judge_results=summary["judge_results"],
        records=summary["records"],
    )
    return {"safe_result_directory": safe_relative, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--smoke-config", required=True)
    parser.add_argument("--smoke-config-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.execute:
            execute(root, args.smoke_config, args.smoke_config_sha256)
        else:
            config, result = verify_smoke_evidence(
                root, args.smoke_config, args.smoke_config_sha256
            )
            emit(
                "LOCAL_QUALIFICATION_PASS_READY_FOR_REVIEW",
                smoke_contract_sha256=args.smoke_config_sha256,
                judge_id=config["judge"]["judge_id"],
                gate=result["gate"],
                private_inputs_read=False,
                model_loaded=False,
                network_calls=0,
            )
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        emit(
            "STOPPED_LOCAL_QUALIFICATION_NOT_PASSED"
            if isinstance(exc, QualificationFailure)
            else "STOPPED_LOCAL_DEVELOPMENT",
            error_type=type(exc).__name__,
            uncertain_dispatch=isinstance(exc, runtime.TransportFailure),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
