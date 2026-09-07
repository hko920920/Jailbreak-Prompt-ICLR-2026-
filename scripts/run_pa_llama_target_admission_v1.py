"""Frozen, eleven-call harmless runtime admission; preflight is the default.

This standalone runner never imports historical experiment runners. It has no
resume/retry path. A dispatch journal is durable before every inference; an
ambiguous dispatch permanently closes this contract to execution. Audit-only
reconciles this runner's own harmless receipts without sending a request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "jbspan-pa-llama-target-admission-v1"
SAFE_ROOT = "data/natural_language_localization/pa_llama_target_admission_v1"
PRIVATE_ROOT = "artifacts/pa_llama_target_admission_v1/private"
RUNNER_PATH = "scripts/run_pa_llama_target_admission_v1.py"
FIXTURE_SOURCE = "configs/natural_language_localization/step5n_h4rm3l_confirmation_v1.json"
GENERATION = {
    "seed": 17, "temperature": 0, "max_tokens": 48, "top_k": 1,
    "top_p": 1, "min_p": 0, "repeat_penalty": 1,
}
SCORERS = {
    "exact_sentinel": "exact_text", "arithmetic": "integer", "sorting": "integer_list",
    "color_mixing": "word", "capital": "word", "translation": "word", "opposite": "word",
    "primes": "integer_list", "json_format": "json_object", "copy_token": "exact_text",
}
EXPECTED = {
    "exact_sentinel": "P2_OK", "arithmetic": 42, "sorting": [1, 2, 3],
    "color_mixing": "green", "capital": "paris", "translation": "bonjour", "opposite": "cold",
    "primes": [2, 3, 5], "json_format": {"status": "ok"}, "copy_token": "alpha-7",
}
SERVER_PAIRS = {
    "--ctx-size", "-c", "--gpu-layers", "-ngl", "--threads", "-t", "--threads-batch", "-tb",
    "--batch-size", "-b", "--ubatch-size", "-ub", "--split-mode", "--fit", "--parallel", "-np",
    "--flash-attn", "-fa",
    "--device", "--reasoning",
}
SERVER_FLAGS = {
    "--jinja", "--no-webui", "--no-mmap", "--no-kv-offload", "--offline", "--no-agent",
    "--no-cache-prompt",
}
FLAG_ALIASES = {
    "-c": "--ctx-size", "-ngl": "--gpu-layers", "-t": "--threads",
    "-tb": "--threads-batch", "-b": "--batch-size", "-ub": "--ubatch-size",
    "-np": "--parallel", "-fa": "--flash-attn",
}


class AdmissionError(RuntimeError):
    """Only fixed non-content error codes may cross the stdout boundary."""


def require(condition, code):
    if not condition:
        raise AdmissionError(code)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def identity(value):
    return sha_bytes(canonical(value))


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid_constant(_):
        raise AdmissionError("NONFINITE_JSON_CONSTANT")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def contained(root, relative):
    require(isinstance(relative, str) and relative != "", "PATH_INVALID")
    require(not Path(relative).is_absolute(), "ABSOLUTE_PATH_FORBIDDEN")
    require(".." not in Path(relative).parts, "PARENT_PATH_FORBIDDEN")
    path = (root / relative).resolve()
    require(path != root and path.is_relative_to(root), "PATH_ESCAPES_ROOT")
    return path


def descriptor(root, item):
    require(isinstance(item, dict), "DESCRIPTOR_INVALID")
    require(re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is not None,
            "DESCRIPTOR_SHA_INVALID")
    require(type(item.get("size_bytes")) is int and item["size_bytes"] >= 0,
            "DESCRIPTOR_SIZE_INVALID")
    path = contained(root, item["path"])
    require(path.is_file() and path.stat().st_size == item["size_bytes"], "ARTIFACT_SIZE_MISMATCH")
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    require(checksum.hexdigest() == item["sha256"], "ARTIFACT_SHA_MISMATCH")
    return path


def write_once(path, value, *, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if raw else canonical(value) + b"\n"
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def score_answer(fixture, answer):
    """Whole-output typed checks; malformed answers never get substring credit."""
    require(isinstance(answer, str), "CONTENT_NOT_STRING")
    text = answer.strip()
    scorer = fixture["scorer"]
    expected = fixture["expected"]
    normalized = text
    parsed_ok = True
    if scorer == "word":
        normalized = text.casefold()
        parsed_ok = re.fullmatch(r"[A-Za-z]+", text) is not None
    elif scorer == "integer":
        parsed_ok = re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text) is not None
        normalized = int(text) if parsed_ok else text
    elif scorer == "integer_list":
        parsed_ok = re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\s*,\s*-?(?:0|[1-9][0-9]*))*",
                                 text) is not None
        normalized = [int(part.strip()) for part in text.split(",")] if parsed_ok else text
    elif scorer == "json_object":
        try:
            normalized = strict_json(text)
            parsed_ok = isinstance(normalized, dict)
        except (ValueError, AdmissionError):
            parsed_ok = False
            normalized = text
    else:
        require(scorer == "exact_text", "SCORER_INVALID")
    # The type check prevents True == 1 and analogous permissive comparisons.
    correct = parsed_ok and type(normalized) is type(expected) and normalized == expected
    return {
        "content_check_passed": correct,
        "scorer": scorer,
        "parsed_as_required_type": parsed_ok,
        "raw_content_sha256": sha_bytes(answer.encode()),
        "normalized_content_sha256": identity({"scorer": scorer, "value": normalized}),
        "response_characters": len(answer),
    }


def validate_server_args(args):
    require(isinstance(args, list) and all(isinstance(arg, str) for arg in args),
            "SERVER_ARGS_INVALID")
    index = 0
    seen = set()
    while index < len(args):
        key = FLAG_ALIASES.get(args[index], args[index])
        require(key not in seen, "DUPLICATE_SERVER_FLAG")
        seen.add(key)
        if key in SERVER_FLAGS:
            index += 1
        else:
            require(key in SERVER_PAIRS and index + 1 < len(args), "SERVER_FLAG_FORBIDDEN")
            require(not args[index + 1].startswith("--"), "SERVER_VALUE_INVALID")
            index += 2
    require("--jinja" in seen, "NATIVE_JINJA_REQUIRED")
    require({"--offline", "--no-agent", "--no-webui", "--no-cache-prompt"} <= seen,
            "SERVER_ISOLATION_FLAGS_MISSING")


def load_contract(root, config_path, expected_sha):
    root = root.resolve()
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None, "CONFIG_SHA_INVALID")
    config_bytes = contained(root, config_path).read_bytes()
    require(sha_bytes(config_bytes) == expected_sha, "CONFIG_SHA_MISMATCH")
    config = strict_json(config_bytes)
    require(config.get("schema_version") == SCHEMA and config.get("frozen") is True,
            "CONTRACT_NOT_FROZEN")
    require(config.get("evidence_class")
            == "HARMLESS_OPERATIONAL_TARGET_ADMISSION_NOT_PAPER_EVIDENCE",
            "EVIDENCE_SCOPE_INVALID")
    require(config.get("request_ceiling") == 11, "CEILING_MUST_BE_ELEVEN")
    require(identity(config.get("generation")) == identity(GENERATION), "GENERATION_MISMATCH")
    require(config.get("paths") == {"safe_root": SAFE_ROOT, "private_root": PRIVATE_ROOT},
            "OUTPUT_ROOTS_INVALID")
    server = config["server"]
    require(server.get("host") == "127.0.0.1", "ONLY_IPV4_LOOPBACK_ALLOWED")
    require(type(server.get("port")) is int and 1024 <= server["port"] <= 65535,
            "PORT_INVALID")
    for key in ("startup_timeout_seconds", "request_timeout_seconds"):
        require(type(server.get(key)) in (int, float) and math.isfinite(server[key])
                and 1 <= server[key] <= 600, "TIMEOUT_INVALID")
    runner = config["required_code"]["runner"]
    require(runner["path"] == RUNNER_PATH, "RUNNER_PATH_INVALID")
    require(descriptor(root, runner) == Path(__file__).resolve(), "RUNNER_SELF_BINDING_FAILED")
    for key, item in config["required_code"].items():
        if key != "runner":
            require(item["path"].startswith(("scripts/", "tests/")), "CODE_READ_SCOPE_INVALID")
            descriptor(root, item)
    source = config["fixture_source"]
    require(source["path"] == FIXTURE_SOURCE, "FIXTURE_SOURCE_INVALID")
    old = strict_json(descriptor(root, source).read_bytes())["harmless_prompts"]
    for item in config.get("sources", []):
        require(item["path"].startswith(("docs/", "configs/", "scripts/", "tests/")),
                "SOURCE_READ_SCOPE_INVALID")
        descriptor(root, item)
    fixtures = config["fixtures"]
    require(isinstance(fixtures, list) and len(fixtures) == len(old) == 10,
            "FIXTURE_COUNT_INVALID")
    require([fixture.get("prompt_id") for fixture in fixtures] == list(SCORERS),
            "FIXTURE_ORDER_OR_IDS_INVALID")
    for fixture, original in zip(fixtures, old, strict=True):
        require(fixture.get("prompt_id") == original["prompt_id"]
                and fixture.get("text") == original["text"], "FIXTURE_SOURCE_TEXT_MISMATCH")
        require(fixture.get("scorer") == SCORERS[fixture["prompt_id"]], "SCORER_MISMATCH")
        require(identity(fixture.get("expected")) == identity(EXPECTED[fixture["prompt_id"]]),
                "FIXTURE_EXPECTATION_MISMATCH")
    runtime = config["runtime"]
    require(runtime["server"]["path"].startswith("artifacts/p2_runtime_qualification_v1/runtime/"),
            "RUNTIME_READ_SCOPE_INVALID")
    descriptor(root, runtime["server"])
    for item in runtime["files"]:
        require(item["path"].startswith("artifacts/p2_runtime_qualification_v1/runtime/"),
                "RUNTIME_READ_SCOPE_INVALID")
        descriptor(root, item)
    require(re.fullmatch(r"[0-9a-f]{64}", runtime.get("native_chat_template_sha256", ""))
            is not None, "NATIVE_TEMPLATE_PIN_MISSING")
    validate_server_args(runtime["server_args"])
    model = config["model"]
    require(re.fullmatch(r"[A-Za-z0-9._-]+", model.get("alias", "")) is not None,
            "MODEL_ALIAS_INVALID")
    require(model.get("files") and model["entry_path"] in {f["path"] for f in model["files"]},
            "MODEL_ENTRY_NOT_PINNED")
    for item in model["files"]:
        require(item["path"].startswith("artifacts/p2_runtime_qualification_v1/models/"),
                "MODEL_READ_SCOPE_INVALID")
        descriptor(root, item)
    # Resolve output roots before any mutation, including symlink containment.
    contained(root, SAFE_ROOT)
    contained(root, PRIVATE_ROOT)
    return config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AdmissionError("HTTP_REDIRECT_FORBIDDEN")


class LoopbackClient:
    def __init__(self, port):
        self.port = port
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, route, payload=None, *, timeout=2):
        require(route in {"/health", "/props", "/v1/models", "/v1/chat/completions"},
                "HTTP_ROUTE_FORBIDDEN")
        require((route == "/v1/chat/completions") == (payload is not None),
                "HTTP_METHOD_FORBIDDEN")
        body = canonical(payload) if payload is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{route}", data=body,
            headers={"Content-Type": "application/json"}, method="POST" if body else "GET",
        )
        with self.opener.open(request, timeout=timeout) as response:
            require(response.status == 200, "HTTP_STATUS_NOT_200")
            raw = response.read(2_000_001)
        require(len(raw) <= 2_000_000, "HTTP_BODY_LIMIT_EXCEEDED")
        return raw

    def get(self, route):
        value = strict_json(self.request(route))
        require(isinstance(value, dict), "HTTP_OBJECT_REQUIRED")
        return value


def require_free_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise AdmissionError("PORT_OCCUPIED_NO_SERVER_REUSE") from None


def check_identity(process, client, config):
    require(process.poll() is None, "OWNED_PROCESS_EXITED")
    models = client.get("/v1/models")
    data = models.get("data")
    require(isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict)
            and data[0].get("id") == config["model"]["alias"], "SERVED_MODEL_ALIAS_MISMATCH")
    props = client.get("/props")
    template = props.get("chat_template")
    require(isinstance(template, str) and template != "", "NATIVE_TEMPLATE_UNAVAILABLE")
    template_sha = sha_bytes(template.encode())
    require(template_sha == config["runtime"]["native_chat_template_sha256"],
            "NATIVE_TEMPLATE_MISMATCH")
    require(process.poll() is None, "OWNED_PROCESS_EXITED")
    return {"native_chat_template_sha256": template_sha,
            "props_sha256": identity(props), "models_sha256": identity(models)}


@contextmanager
def owned_server(root, config, private_dir, safe_dir, epoch, contract_sha):
    server = config["server"]
    require_free_port(server["port"])
    client = LoopbackClient(server["port"])
    command = [str(contained(root, config["runtime"]["server"]["path"])),
               "--model", str(contained(root, config["model"]["entry_path"])),
               "--alias", config["model"]["alias"], "--host", "127.0.0.1",
               "--port", str(server["port"]), *config["runtime"]["server_args"]]
    environment = {key: value for key, value in os.environ.items()
                   if key.casefold() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
                   and not key.upper().startswith("LLAMA_ARG_")}
    process = None
    with (private_dir / f"server-{epoch:02d}.log.private.txt").open("xb") as log:
        try:
            process = subprocess.Popen(
                command, cwd=str(Path(command[0]).parent), env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            event = {"contract_sha256": contract_sha, "epoch": epoch, "pid": process.pid,
                     "started_at": utc_now(), "command_sha256": identity(command),
                     "owned_process_only": True}
            write_once(safe_dir / f"server-{epoch:02d}.started.safe.json", event)
            emit("OWNED_SERVER_STARTED", epoch=epoch, pid=process.pid)
            deadline = time.monotonic() + server["startup_timeout_seconds"]
            last_update = time.monotonic()
            while True:
                require(process.poll() is None, "SERVER_EXITED_DURING_STARTUP")
                try:
                    healthy = client.get("/health").get("status") == "ok"
                except (OSError, ValueError, urllib.error.URLError):
                    healthy = False
                if healthy:
                    break
                require(time.monotonic() < deadline, "SERVER_STARTUP_TIMEOUT")
                if time.monotonic() - last_update >= 20:
                    emit("OWNED_SERVER_LOADING", epoch=epoch, pid=process.pid)
                    last_update = time.monotonic()
                time.sleep(0.5)
            properties = check_identity(process, client, config)
            write_once(safe_dir / f"server-{epoch:02d}.identity.safe.json", {**event, **properties})
            yield process, client, properties
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                require(process.poll() is not None, "OWNED_SERVER_STOP_FAILED")
                write_once(safe_dir / f"server-{epoch:02d}.stopped.safe.json", {
                    "contract_sha256": contract_sha, "epoch": epoch, "pid": process.pid,
                    "stopped_at": utc_now(), "returncode": process.returncode,
                    "owned_process_only": True,
                })
                emit("OWNED_SERVER_STOPPED", epoch=epoch, pid=process.pid)


def plan_for(config):
    return [{"ordinal": index + 1, "epoch": 1, "fixture": fixture}
            for index, fixture in enumerate(config["fixtures"])] + [
                {"ordinal": 11, "epoch": 2, "fixture": config["fixtures"][0]}]


def request_for(config, item):
    return {"model": config["model"]["alias"],
            "messages": [{"role": "user", "content": item["fixture"]["text"]}],
            "stream": False, **GENERATION}


def parse_reply(config, fixture, raw):
    value = strict_json(raw)
    require(isinstance(value, dict), "REPLY_OBJECT_REQUIRED")
    require(value.get("model") == config["model"]["alias"], "REPLY_MODEL_MISMATCH")
    choices = value.get("choices")
    require(isinstance(choices, list) and len(choices) == 1, "REPLY_CHOICE_COUNT_INVALID")
    choice = choices[0]
    require(isinstance(choice, dict) and choice.get("index") == 0, "REPLY_CHOICE_INDEX_INVALID")
    message = choice.get("message")
    require(isinstance(message, dict) and message.get("role") == "assistant", "REPLY_ROLE_INVALID")
    require(not any(message.get(key) for key in
                    ("tool_calls", "function_call", "refusal", "reasoning_content")),
            "NONANSWER_CHANNEL_PRESENT")
    answer = message.get("content")
    score = score_answer(fixture, answer)
    reason = choice.get("finish_reason")
    require(reason in {"stop", "length"}, "FINISH_REASON_INVALID")
    usage = value.get("usage")
    require(isinstance(usage, dict), "USAGE_MISSING")
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        require(type(usage.get(key)) is int and usage[key] >= 0, "USAGE_INVALID")
    require(usage["prompt_tokens"] > 0 and usage["completion_tokens"] <= 48,
            "TOKEN_BOUND_VIOLATION")
    require(not answer or usage["completion_tokens"] > 0, "NONEMPTY_CONTENT_ZERO_TOKENS")
    require(usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"],
            "USAGE_TOTAL_MISMATCH")
    return {**score, "finish_reason": reason, "not_truncated": reason == "stop",
            "passed": score["content_check_passed"] and reason == "stop",
            "usage": {key: usage[key] for key in
                      ("prompt_tokens", "completion_tokens", "total_tokens")},
            "reply_bytes_sha256": sha_bytes(raw)}


def dispatch_one(config, contract_sha, item, process, client, safe_dir, private_dir, props):
    ordinal = item["ordinal"]
    require(1 <= ordinal <= 11, "DISPATCH_CEILING_EXCEEDED")
    require(process.poll() is None, "OWNED_PROCESS_EXITED")
    current = check_identity(process, client, config)
    require(current["native_chat_template_sha256"] == props["native_chat_template_sha256"],
            "NATIVE_TEMPLATE_CHANGED")
    request = request_for(config, item)
    private_request = private_dir / f"{ordinal:02d}.request.private.json"
    write_once(private_request, request)
    journal = {"contract_sha256": contract_sha, "ordinal": ordinal, "epoch": item["epoch"],
               "fixture_id": item["fixture"]["prompt_id"], "process_id": process.pid,
               "request_sha256": identity(request), "dispatch_at": utc_now(),
               "native_chat_template_sha256": current["native_chat_template_sha256"]}
    write_once(safe_dir / f"{ordinal:02d}.dispatch.safe.json", journal)
    start = time.monotonic()
    # Never retry this call, even if no response bytes are received.
    raw = client.request("/v1/chat/completions", request,
                         timeout=config["server"]["request_timeout_seconds"])
    elapsed = time.monotonic() - start
    write_once(private_dir / f"{ordinal:02d}.reply.private.json", raw, raw=True)
    require(process.poll() is None, "OWNED_PROCESS_EXITED_AFTER_DISPATCH")
    score = parse_reply(config, item["fixture"], raw)
    row = {**journal, **score, "latency_seconds": elapsed, "received_at": utc_now(),
           "request_max_tokens": 48}
    write_once(safe_dir / f"{ordinal:02d}.row.safe.json", row)
    emit("HARMLESS_REQUEST_RECORDED", ordinal=ordinal, total=11, passed=row["passed"],
         finish_reason=row["finish_reason"])
    return row


def reconcile(config, contract_sha, safe_dir, private_dir):
    """Re-score only this contract's own harmless receipts; never issue HTTP."""
    plan = plan_for(config)
    journals = sorted(safe_dir.glob("*.dispatch.safe.json"))
    replies = sorted(private_dir.glob("*.reply.private.json"))
    row_files = sorted(safe_dir.glob("*.row.safe.json"))
    rows = []
    require(len(journals) <= 11 and len(replies) <= 11 and len(row_files) <= 11,
            "RECEIPT_CEILING_VIOLATION")
    for item in plan[:len(journals)]:
        prefix = f"{item['ordinal']:02d}"
        journal_path = safe_dir / f"{prefix}.dispatch.safe.json"
        require(journal_path in journals, "DISPATCH_NOT_PLAN_PREFIX")
        journal = strict_json(journal_path.read_bytes())
        require(journal.get("contract_sha256") == contract_sha
                and journal.get("ordinal") == item["ordinal"]
                and journal.get("epoch") == item["epoch"]
                and journal.get("fixture_id") == item["fixture"]["prompt_id"]
                and journal.get("native_chat_template_sha256")
                == config["runtime"]["native_chat_template_sha256"], "JOURNAL_BINDING_MISMATCH")
        epoch_path = safe_dir / f"server-{item['epoch']:02d}.identity.safe.json"
        require(epoch_path.is_file(), "JOURNAL_SERVER_EPOCH_MISSING")
        epoch = strict_json(epoch_path.read_bytes())
        require(epoch.get("contract_sha256") == contract_sha
                and epoch.get("epoch") == item["epoch"]
                and epoch.get("owned_process_only") is True
                and type(epoch.get("pid")) is int and epoch["pid"] > 0
                and journal.get("process_id") == epoch["pid"]
                and epoch.get("native_chat_template_sha256")
                == config["runtime"]["native_chat_template_sha256"],
                "JOURNAL_SERVER_EPOCH_MISMATCH")
        expected = request_for(config, item)
        request_path = private_dir / f"{prefix}.request.private.json"
        require(request_path.is_file(), "PRIVATE_REQUEST_MISSING")
        require(strict_json(request_path.read_bytes()) == expected
                and journal["request_sha256"] == identity(expected), "REQUEST_BINDING_MISMATCH")
        reply_path = private_dir / f"{prefix}.reply.private.json"
        require(reply_path.is_file(), "AMBIGUOUS_DISPATCH_NO_RETRY")
        measured = parse_reply(config, item["fixture"], reply_path.read_bytes())
        row_path = safe_dir / f"{prefix}.row.safe.json"
        require(row_path.is_file(), "SAFE_ROW_MISSING_NO_RETRY")
        row = strict_json(row_path.read_bytes())
        require(all(row.get(key) == value for key, value in {**journal, **measured}.items()),
                "SAFE_ROW_RECEIPT_MISMATCH")
        require(type(row.get("latency_seconds")) in (int, float)
                and math.isfinite(row["latency_seconds"]) and row["latency_seconds"] >= 0,
                "ROW_LATENCY_INVALID")
        rows.append(row)
    require(len(journals) == len(replies) == len(rows) == len(row_files), "RECEIPT_COUNT_MISMATCH")
    require(len(list(private_dir.glob("*.request.private.json"))) == len(rows),
            "ORPHAN_PRIVATE_REQUEST")
    return rows


def summarize(config, contract_sha, rows, *, stopped):
    complete = len(rows) == 11
    capability = sum(row["passed"] for row in rows[:10])
    replay = complete and rows[0]["normalized_content_sha256"] == rows[10][
        "normalized_content_sha256"]
    same_template = complete and len({row["native_chat_template_sha256"] for row in rows}) == 1
    epochs = complete and [row["epoch"] for row in rows] == [1] * 10 + [2]
    admitted = (complete and capability == 10 and all(row["passed"] for row in rows)
                and replay and same_template and epochs and stopped)
    return {"schema_version": SCHEMA, "contract_sha256": contract_sha,
            "gate_name": "NEW_DEVELOPMENT_TARGET_BASIC_ADMISSION",
            "evidence_class": config["evidence_class"], "complete": complete,
            "request_count": len(rows), "request_ceiling": 11,
            "capability_passes": capability, "capability_denominator": 10,
            "deterministic_sentinel_replay": replay, "same_native_chat_template": same_template,
            "two_owned_process_epochs": epochs, "owned_servers_stopped": stopped,
            "admitted_basic_harmless_runtime_only": admitted,
            "paper_admission": False, "jailbreak_admission": False,
            "measurement_admission": False, "gpu_offload_measured": False,
            "rows": rows}


def stopped_epochs(config, safe_dir, contract_sha):
    for epoch in (1, 2):
        start = safe_dir / f"server-{epoch:02d}.started.safe.json"
        stop = safe_dir / f"server-{epoch:02d}.stopped.safe.json"
        binding = safe_dir / f"server-{epoch:02d}.identity.safe.json"
        if not all(path.is_file() for path in (start, stop, binding)):
            return False
        records = [strict_json(path.read_bytes()) for path in (start, stop, binding)]
        require(all(row.get("contract_sha256") == contract_sha and row.get("epoch") == epoch
                    and row.get("owned_process_only") is True for row in records),
                "SERVER_EPOCH_BINDING_MISMATCH")
        require(len({row.get("pid") for row in records}) == 1, "SERVER_EPOCH_PID_MISMATCH")
        require(records[2].get("native_chat_template_sha256")
                == config["runtime"]["native_chat_template_sha256"],
                "SERVER_EPOCH_TEMPLATE_MISMATCH")
        require(type(records[1].get("returncode")) is int, "SERVER_STOP_NOT_OBSERVED")
    return True


def run(root, config_path, expected_sha, *, execute=False, audit_only=False):
    require(not (execute and audit_only), "EXECUTE_AUDIT_MUTUALLY_EXCLUSIVE")
    root = root.resolve()
    config = load_contract(root, config_path, expected_sha)
    safe_dir = contained(root, f"{SAFE_ROOT}/{expected_sha}")
    private_dir = contained(root, f"{PRIVATE_ROOT}/{expected_sha}")
    if not execute and not audit_only:
        return {"schema_version": SCHEMA, "contract_sha256": expected_sha,
                "preflight_passed": True, "live_calls": 0, "request_ceiling": 11,
                "execution_already_locked": (safe_dir / "execution.lock.safe.json").exists()}
    if audit_only:
        require((safe_dir / "execution.lock.safe.json").is_file(), "NO_EXECUTION_TO_AUDIT")
        rows = reconcile(config, expected_sha, safe_dir, private_dir)
        result = summarize(config, expected_sha, rows,
                           stopped=stopped_epochs(config, safe_dir, expected_sha))
        saved = safe_dir / "result.safe.json"
        if saved.is_file():
            recorded = strict_json(saved.read_bytes())
            require(recorded == result, "SAVED_RESULT_MISMATCH")
        return {"audit_only": True, **result}
    # The contract directory itself is exclusive; even an early interrupted run
    # is never resumed or silently assigned a new output directory.
    require(not safe_dir.exists() and not private_dir.exists(), "EXECUTION_EXISTS_NO_RETRY")
    safe_dir.mkdir(parents=True, exist_ok=False)
    private_dir.mkdir(parents=True, exist_ok=False)
    write_once(safe_dir / "execution.lock.safe.json", {
        "contract_sha256": expected_sha, "started_at": utc_now(), "request_ceiling": 11,
        "resume_allowed": False, "paid_calls_allowed": False,
    })
    try:
        plan = plan_for(config)
        for epoch in (1, 2):
            with owned_server(root, config, private_dir, safe_dir, epoch, expected_sha) as owned:
                process, client, props = owned
                for item in (item for item in plan if item["epoch"] == epoch):
                    dispatch_one(config, expected_sha, item, process, client,
                                 safe_dir, private_dir, props)
        rows = reconcile(config, expected_sha, safe_dir, private_dir)
        result = summarize(config, expected_sha, rows,
                           stopped=stopped_epochs(config, safe_dir, expected_sha))
        write_once(safe_dir / "result.safe.json", result)
        return result
    except Exception as error:
        code = str(error) if isinstance(error, AdmissionError) else type(error).__name__
        write_once(safe_dir / "aborted.safe.json", {
            "contract_sha256": expected_sha, "stopped_at": utc_now(), "error_code": code,
            "journaled_dispatches": len(list(safe_dir.glob("*.dispatch.safe.json"))),
            "reply_receipts": len(list(private_dir.glob("*.reply.private.json"))),
            "resume_allowed": False,
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.root, args.config, args.config_sha256,
                     execute=args.execute, audit_only=args.audit_only)
        print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                         sort_keys=True, indent=2), flush=True)
        if args.execute and not result.get("admitted_basic_harmless_runtime_only"):
            return 2
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, AdmissionError) else type(error).__name__
        emit("HARMLESS_ADMISSION_STOPPED", error_code=code, resume_allowed=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
