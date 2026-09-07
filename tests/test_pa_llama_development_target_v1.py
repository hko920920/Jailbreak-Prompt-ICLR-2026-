"""Synthetic-only extraction, native census and target dispatch/lifecycle tests."""

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pa_llama_development_target_v1 as m  # noqa: E402

SPEC = importlib.util.spec_from_file_location("pa_dev_test_pinned_v2", SCRIPTS / m.HELPER[8:])
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
c = m.c
REAL_GPU_SAMPLE = m.gpu_sample


@pytest.fixture(autouse=True)
def synthetic_resources(monkeypatch):
    monkeypatch.setattr(m, "gpu_sample", lambda: {
        "gpu_name": m.GPU_NAME, "gpu_total_mib": 8192, "gpu_used_mib": 500,
        "gpu_temperature_c": 40, "sampled_at": "2026-09-05T16:00:00Z"})
    monkeypatch.setattr(m.shutil, "disk_usage", lambda _: SimpleNamespace(free=20 * 1024 ** 3))


def reply(content="A harmless synthetic answer.", finish="stop", prompt_tokens=12, completion=7):
    return c.canonical({"model": "synthetic-llama", "choices": [{"index": 0,
        "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion,
                  "total_tokens": prompt_tokens + completion}})


def persist(path, value):
    if path.exists():
        path.unlink()
    c.write_once(path, value)


@pytest.fixture
def config():
    template = "synthetic native template"
    return {"_contract_sha256": "c" * 64, "source_inventory": {"sha256": "a" * 64},
            "execution_limits": {"deadline_utc": "2099-01-01T00:00:00Z"},
            "model": {"alias": "synthetic-llama", "entry_path": "synthetic/model.gguf"},
            "generation": dict(c.GENERATION),
            "runtime": {"server": {"path": "synthetic/server.exe"}, "server_args": [],
                        "native_chat_template_sha256": "b" * 64,
                        "served_chat_template_sha256": c.sha_bytes(template.encode()),
                        "served_chat_template_utf8_bytes": len(template.encode())},
            "server": {"host": "127.0.0.1", "port": 18087, "request_timeout_seconds": 5}}


@pytest.fixture
def source_frame(tmp_path_factory):
    root = tmp_path_factory.mktemp("t")
    rows = []
    for position in range(45):
        for condition in c.CONDITIONS:
            payload = f"Synthetic harmless payload {position:02d}."
            prompt = payload if condition == "DIRECT" else f"Prefix\n{payload}\nSuffix"
            identity = {"record_id": c.digest([position, condition]),
                        "target_id": "qwen2.5-7b-instruct-q4-k-m", "seed": 11,
                        "payload_position": position, "condition": condition,
                        "payload_sha256": c.sha_bytes(payload.encode()),
                        "prompt_sha256": c.sha_bytes(prompt.encode())}
            execution = c.digest(identity)
            old = {"schema_version": "local-signal-screen-p3-private-invocation-v1",
                   "execution_identity": identity, "execution_identity_sha256": execution,
                   "payload": payload, "prompt": prompt,
                   "response": "OLD_RESPONSE_MUST_NOT_BE_COPIED",
                   "stdout": "OLD_STDOUT_MUST_NOT_BE_COPIED"}
            raw = c.canonical(old)
            relative = f"{c.OLD_PRIVATE}/{execution}.json"
            # This is an isolated generated tree, never the real historical tree.
            c.write_once(root / relative, raw, raw=True)
            rows.append({"payload_position": position, "condition": condition,
                         "source_target_id": identity["target_id"], "source_seed": 11,
                         "source_record_id": identity["record_id"],
                         "source_execution_identity_sha256": execution,
                         "payload_sha256": identity["payload_sha256"],
                         "prompt_sha256": identity["prompt_sha256"],
                         "prompt_utf8_bytes": len(prompt.encode()),
                         "topic_sha256": c.digest(position // 3),
                         "unit_count": 0 if condition == "DIRECT" else 3,
                         "unit_manifest_sha256": c.digest([condition, "unit"]),
                         "fragment_manifest_sha256": c.digest([condition, "fragment"]),
                         "private_source": {"path": relative, "size_bytes": len(raw),
                                            "sha256": c.sha_bytes(raw)}})
    inventory = {"schema_version": "jbspan-pa-llama-development-source-inventory-v1",
                 "execution_authorized": False, "private_content_access_authorized": False,
                 "selection": "ALL_45_PAYLOADS_BOTH_CONDITIONS_NO_OUTCOME_FILTER",
                 "payloads": 45, "topics": 15, "input_records": 90,
                 "old_private_content_reads": 0, "private_record_metadata_stats": 90,
                 "private_hashes_reused_from_pinned_safe_receipts_not_rehashed": True,
                 "prospective_private_file_reads_if_later_authorized": 90,
                 "prospective_files_also_contain_historical_responses": True,
                 "dataset_core_opened": False, "sealed_A60_B60_opened": False,
                 "model_calls": 0, "rows": rows, "rows_sha256": c.digest(rows)}
    return root, inventory


class FakeResponse:
    status = 200

    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.raw[:limit]


class FakeClient:
    def __init__(self):
        self.opener = self
        self.metadata = []
        self.generations = []
        self.fail_at = None
        self.before_dispatch = None
        self.reply_factory = lambda _: reply()

    def get(self, route):
        if route == "/v1/models":
            return {"data": [{"id": "synthetic-llama"}]}
        if route == "/props":
            return {"chat_template": "synthetic native template",
                    "default_generation_settings": {"n_ctx": 4096}}
        return {"status": "ok"}

    def open(self, request, timeout):
        body = c.strict_json(request.data)
        assert request.full_url.startswith("http://127.0.0.1:18087/")
        assert timeout == 5
        self.metadata.append((request.full_url, body))
        if request.full_url.endswith("/apply-template"):
            value = {"prompt": "[native]" + body["messages"][0]["content"]}
        else:
            assert request.full_url.endswith("/tokenize")
            assert body["add_special"] is True and body["parse_special"] is True
            assert body["with_pieces"] is False
            value = {"tokens": list(range(12 if body["content"].startswith("[native]") else 10))}
        return FakeResponse(c.canonical(value))

    def request(self, route, request, timeout):
        assert route == "/v1/chat/completions" and timeout == 5
        if self.before_dispatch:
            self.before_dispatch(request)
        self.generations.append(request)
        if self.fail_at == len(self.generations):
            raise OSError("synthetic transport failure")
        return self.reply_factory(len(self.generations))


class FakeHelper:
    check_identity = staticmethod(h.check_identity)
    verify_template_observation = staticmethod(h.verify_template_observation)
    utc_now = staticmethod(lambda: "2026-09-05T16:00:00Z")
    emit = staticmethod(lambda *args, **kwargs: None)

    def __init__(self):
        self.client = FakeClient()
        self.started = 0
        self.stopped = 0

    @contextmanager
    def owned_server(self, root, config, private_dir, safe_dir, epoch, contract_sha):
        assert private_dir.is_dir()
        self.started += 1
        process = SimpleNamespace(pid=1000 + self.started, poll=lambda: None)
        event = {"contract_sha256": contract_sha, "epoch": epoch, "pid": process.pid,
                 "owned_process_only": True, "started_at": self.utc_now(),
                 "command_sha256": c.digest(m.command_for(root, config))}
        c.write_once(safe_dir / "server-01.started.safe.json", event)
        properties = self.check_identity(process, self.client, config,
            lambda observed: c.write_once(safe_dir / "server-01.tpl.safe.json",
                                          {**event, **observed}))
        c.write_once(safe_dir / "server-01.identity.safe.json", {**event, **properties})
        try:
            yield process, self.client, properties
        finally:
            self.stopped += 1
            c.write_once(safe_dir / "server-01.stopped.safe.json", {
                **event, "stopped_at": self.utc_now(), "returncode": 0})


@pytest.fixture
def prepared(source_frame, config):
    root, inventory = source_frame
    m.prepare_inputs(root, config, inventory)
    return root, inventory


@pytest.fixture
def censused(prepared, config):
    root, inventory = prepared
    helper = FakeHelper()
    m.census_inputs(root, config, inventory, helper)
    return root, inventory, helper


def test_extract_only_seven_fields_no_historical_response(source_frame):
    root, inventory = source_frame
    source = inventory["rows"][0]
    row = m.extract_input((root / source["private_source"]["path"]).read_bytes(), source)
    assert set(row) == m.INPUT_KEYS
    assert b"OLD_RESPONSE" not in c.canonical(row) and b"OLD_STDOUT" not in c.canonical(row)


@pytest.mark.parametrize("mutation", ["size", "hash", "identity", "payload", "prompt", "schema"])
def test_extract_rejects_identity_content_corruption(source_frame, mutation):
    root, inventory = source_frame
    source = inventory["rows"][0]
    raw = (root / source["private_source"]["path"]).read_bytes()
    if mutation == "size":
        raw += b" "
    elif mutation == "hash":
        source["private_source"]["sha256"] = "0" * 64
    else:
        value = c.strict_json(raw)
        if mutation == "identity":
            value["execution_identity"]["seed"] = 23
        elif mutation == "schema":
            value["schema_version"] = "wrong"
        else:
            value[mutation] += " changed"
        raw = c.canonical(value)
        source["private_source"].update(size_bytes=len(raw), sha256=c.sha_bytes(raw))
    with pytest.raises(c.DevelopmentError):
        m.extract_input(raw, source)


def test_prepare_reads_exact90_once_and_rerun_only_new_inputs(source_frame, config, monkeypatch):
    root, inventory = source_frame
    original = Path.read_bytes
    observed = []

    def spy(path):
        if c.OLD_PRIVATE.replace("/", "\\") in str(path) or c.OLD_PRIVATE in str(path):
            observed.append(str(path))
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", spy)
    receipt = m.prepare_inputs(root, config, inventory)
    assert receipt["historical_private_files_read"] == 90
    assert len(observed) == len(set(observed)) == 90
    m.prepare_inputs(root, config, inventory)
    assert len(observed) == 90
    assert len(m.load_inputs(root, config, inventory)) == 90


def test_partial_extraction_cannot_reread(source_frame, config):
    root, inventory = source_frame
    paths = c.paths(root, config["_contract_sha256"])
    c.write_once(m.own_path(paths, "safe", "extraction-started.safe.json"), {})
    with pytest.raises(FileExistsError):
        m.prepare_inputs(root, config, inventory)


def test_old_path_injection_rejected_before_read(source_frame, config):
    root, inventory = source_frame
    inventory["rows"][0]["private_source"]["path"] = "artifacts/secret.json"
    with pytest.raises(c.DevelopmentError, match="OLD_READ_NOT_INVENTORY_PATH"):
        m.prepare_inputs(root, config, inventory)


def test_input_artifact_response_injection_rejected(prepared, config):
    root, inventory = prepared
    paths = c.paths(root, config["_contract_sha256"])
    private = m.own_path(paths, "private", "inputs.private.json")
    value = m.read_json(private)
    value["rows"][0]["response"] = "forbidden old response"
    persist(private, value)
    persist(m.own_path(paths, "safe", "inputs.safe.json"),
            m.input_receipt(config, inventory, private.read_bytes()))
    with pytest.raises(c.DevelopmentError, match="INPUT_EXTRA_OR_MISSING_FIELD"):
        m.load_inputs(root, config, inventory)


def test_census_all90_zero_generation_and_no_repeat(censused, config):
    root, inventory, helper = censused
    result = m.load_census(root, config, inventory, helper)
    assert len(result["rows"]) == 90 and result["all_inputs_within_context"] is True
    assert len(helper.client.metadata) == 270 and helper.client.generations == []
    assert helper.started == helper.stopped == 1
    m.census_inputs(root, config, inventory, helper)
    assert len(helper.client.metadata) == 270 and helper.started == 1


def test_census_over_budget_blocks_generation(prepared, config):
    root, inventory = prepared
    row = m.load_inputs(root, config, inventory)[0]

    def post(client, cfg, route, body):
        if route == "/apply-template":
            return c.canonical({"prompt": "rendered"})
        return c.canonical({"tokens": [1] * 3585})

    result, _ = m.census_one(config, row, None, post)
    assert result["context_budget_passed"] is False


@pytest.mark.parametrize("tokens", [[True], [-1], [], [1.5], "tokens"])
def test_census_bad_token_lists_rejected(prepared, config, tokens):
    root, inventory = prepared
    row = m.load_inputs(root, config, inventory)[0]

    def post(client, cfg, route, body):
        return c.canonical({"prompt": "rendered"} if route == "/apply-template"
                           else {"tokens": tokens})

    with pytest.raises(c.DevelopmentError, match="TOKENIZATION_REPLY_INVALID"):
        m.census_one(config, row, None, post)


def test_metadata_routes_do_not_allow_generation(config):
    with pytest.raises(c.DevelopmentError, match="METADATA_ROUTE_FORBIDDEN"):
        m.metadata_request(FakeClient(), config, "/v1/chat/completions", {})


@pytest.mark.parametrize("content,finish,eligible,reason", [
    ("long unconstrained prose, with punctuation.", "stop", True, None),
    ("\r\n Text\rMore \n", "stop", True, None),
    ("", "stop", False, "EMPTY_UNKNOWN"),
    (" \n", "stop", False, "EMPTY_UNKNOWN"),
    ("partial answer", "length", False, "TRUNCATED_UNKNOWN")])
def test_full_answer_eligibility_no_harmless_scorer(config, content, finish, eligible, reason):
    result = m.parse_reply(config, reply(content, finish), 12)
    assert result["eligible_for_panel"] is eligible and result["ineligible_reason"] == reason
    assert result["content_sha256"] == c.sha_bytes(content.encode())
    assert result["response_sha256"] == c.sha_bytes(c.normalize_response(content).encode())
    assert "score" not in result and "panel_label" not in result


@pytest.mark.parametrize("mutation", ["model", "choices", "role", "tools", "index", "usagebool",
                                      "tokens", "total", "finish", "content", "census", "zero"])
def test_target_integrity_failures_abort(config, mutation):
    value = c.strict_json(reply())
    if mutation == "model":
        value["model"] = "other"
    elif mutation == "choices":
        value["choices"] *= 2
    elif mutation == "role":
        value["choices"][0]["message"]["role"] = "user"
    elif mutation == "tools":
        value["choices"][0]["message"]["tool_calls"] = [1]
    elif mutation == "index":
        value["choices"][0]["index"] = False
    elif mutation == "finish":
        value["choices"][0]["finish_reason"] = "tool_calls"
    elif mutation == "content":
        value["choices"][0]["message"]["content"] = None
    else:
        key, item = {"usagebool": ("completion_tokens", True),
                     "tokens": ("completion_tokens", 513), "total": ("total_tokens", 1),
                     "census": ("prompt_tokens", 11), "zero": ("completion_tokens", 0)}[mutation]
        value["usage"][key] = item
    with pytest.raises(c.DevelopmentError):
        m.parse_reply(config, c.canonical(value), 12)


def test_all90_targets_exact_requests_and_once_only(censused, config):
    root, inventory, helper = censused
    result = m.run_phase(root, config, inventory, 11, helper)
    assert result["target_records"] == 90 and result["eligible_for_panel"] == 90
    assert len(helper.client.generations) == 90 and helper.started == helper.stopped == 2
    for request in helper.client.generations:
        assert request["seed"] == 11 and request["stream"] is False
        assert len(request["messages"]) == 1 and request["messages"][0]["role"] == "user"
        assert all(c.same(request[key], value) for key, value in c.GENERATION.items())
    again = m.run_phase(root, config, inventory, 11, helper)
    assert again["new_target_generations"] == 0 and len(helper.client.generations) == 90


def test_length_and_empty_failures_do_not_short_circuit(censused, config):
    root, inventory, helper = censused
    helper.client.reply_factory = lambda count: reply("", "stop", completion=0) if count == 1 else (
        reply("partial", "length") if count == 2 else reply())
    result = m.run_phase(root, config, inventory, 11, helper)
    assert result["eligible_for_panel"] == 88 and len(helper.client.generations) == 90


def test_write_ahead_and_ambiguous_dispatch_forbids_retry(censused, config):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    plan = c.phase_plan(config, inventory, 11)

    def before(_):
        item = plan["rows"][len(helper.client.generations)]
        assert m.own_path(paths, "safe", f"target/{item['request_id']}.dispatch.safe.json").exists()

    helper.client.before_dispatch = before
    helper.client.fail_at = 2
    with pytest.raises(OSError):
        m.run_phase(root, config, inventory, 11, helper)
    assert helper.started == helper.stopped == 2 and len(helper.client.generations) == 2
    with pytest.raises(c.DevelopmentError, match="AMBIGUOUS_OR_UNFINALIZED_DISPATCH_NO_RETRY"):
        m.run_phase(root, config, inventory, 11, helper)
    assert len(helper.client.generations) == 2


def test_complete_prefix_continues_only_undispatched(censused, config, monkeypatch):
    root, inventory, helper = censused
    original = m.dispatch_one

    def interrupted(*args, **kwargs):
        if len(helper.client.generations) == 2:
            raise RuntimeError("synthetic interruption BEFORE next dispatch")
        return original(*args, **kwargs)

    monkeypatch.setattr(m, "dispatch_one", interrupted)
    with pytest.raises(RuntimeError):
        m.run_phase(root, config, inventory, 11, helper)
    monkeypatch.setattr(m, "dispatch_one", original)
    result = m.run_phase(root, config, inventory, 11, helper)
    assert result["target_records"] == 90 and len(helper.client.generations) == 90
    assert helper.started == helper.stopped == 3


def test_context_identity_receipt_tampering_blocks(censused, config):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    path = m.own_path(paths, "safe", "epochs/001/server-01.stopped.safe.json")
    changed = m.read_json(path)
    changed["pid"] += 1
    persist(path, changed)
    with pytest.raises(c.DevelopmentError, match="EPOCH_CLEANUP_NOT_VERIFIED"):
        m.run_phase(root, config, inventory, 11, helper)
    assert helper.client.generations == []


def test_new_contract_cannot_reset_global_budget(prepared, config):
    root, _ = prepared
    config["_contract_sha256"] = "d" * 64
    with pytest.raises(c.DevelopmentError, match="ANOTHER_EXPERIMENT_ALREADY_RESERVED"):
        m.reserve_experiment(root, config)


def test_cli_rejects_execute_flag():
    with pytest.raises(SystemExit) as error:
        m.main(["--config-sha256", "a" * 64, "--execute"])
    assert error.value.code == 2


def test_all270_fixed_seed_rows_without_new_sentinel(censused, config):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    prior = None
    for seed in c.SEEDS:
        result = m.run_phase(root, config, inventory, seed, helper)
        assert result["target_records"] == 90
        plan = c.phase_plan(config, inventory, seed, prior)
        decisions = [{"request_id": item["request_id"], "eligible": True,
                      "panel_label": "SAFE" if item["condition"] == "DIRECT" else "HARMFUL"}
                     for item in plan["rows"]]
        prior = c.phase_result(config, inventory, plan, decisions, prior)
        c.write_once(m.own_path(paths, "safe", f"phase_{seed}_result.safe.json"), prior)
        c.write_once(m.own_path(paths, "safe", f"phase_{seed}_verification.safe.json"), {
            "contract_sha256": config["_contract_sha256"], "phase_seed": seed,
            "phase_result_identity_sha256": prior["result_identity_sha256"],
            "raw_axis_receipts_verified": True, "independent_pair_states_verified": True,
            "verification_passed": True, "new_model_calls": 0})
    assert len(helper.client.generations) == 270
    assert [row["seed"] for row in helper.client.generations] == [11] * 90 + [23] * 90 + [47] * 90
    assert helper.started == helper.stopped == 4
    m.run_phase(root, config, inventory, 47, helper)
    assert len(helper.client.generations) == 270


def test_orphan_new_reply_cannot_hide_in_unselected_phase(censused, config):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    rid = c.request_id(config["_contract_sha256"], 0, "DIRECT", 47)
    c.write_once(m.own_path(paths, "private", f"target/{rid}.reply.private.json"),
                 reply(), raw=True)
    with pytest.raises(c.DevelopmentError, match="ORPHAN_TARGET_ARTIFACT_REQUIRES_AUDIT"):
        m.run_phase(root, config, inventory, 11, helper)
    assert helper.client.generations == []


def test_live_context_identity_checked_before_first_census_post(prepared, config):
    root, inventory = prepared
    helper = FakeHelper()
    original = helper.client.get

    def bad_context(route):
        result = original(route)
        if route == "/props":
            result["default_generation_settings"]["n_ctx"] = 2048
        return result

    helper.client.get = bad_context
    with pytest.raises(c.DevelopmentError, match="SERVED_CONTEXT_NOT_4096"):
        m.census_inputs(root, config, inventory, helper)
    assert helper.client.metadata == [] and helper.client.generations == []
    assert helper.started == helper.stopped == 1


def test_deadline_stops_before_dispatch_journal(censused, config):
    root, inventory, helper = censused
    config["execution_limits"]["deadline_utc"] = "2000-01-01T00:00:00Z"
    with pytest.raises(c.DevelopmentError, match="AUTHORIZED_EXECUTION_DEADLINE_REACHED"):
        m.run_phase(root, config, inventory, 11, helper)
    assert helper.client.generations == []
    assert m.global_receipt_check(root, config, inventory) == 0


def test_explicit_stop_at_cap_retains_eligibility_with_visible_flag(config):
    result = m.parse_reply(config, reply(completion=512), 12)
    assert result["eligible_for_panel"] is True and result["completion_cap_reached"] is True


def test_abort_receipt_contains_no_raw_exception_text(prepared, config):
    root, _ = prepared
    record = m.record_abort(root, config, "generate", 11,
                            OSError("SYNTHETIC secret payload / private/path"))
    assert record["error_code"] == "OSError"
    assert b"secret" not in c.canonical(record)
    paths = c.paths(root, config["_contract_sha256"])
    assert len(list(m.own_path(paths, "safe", "failures").glob("*.safe.json"))) == 1


@pytest.mark.parametrize("field", ["command_sha256", "started_at"])
def test_epoch_started_command_or_time_tampering_rejected(censused, config, field):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    epoch_dir, _ = m.epoch_paths(paths, 1)
    for name in ("started", "identity"):
        path = epoch_dir / f"server-01.{name}.safe.json"
        value = m.read_json(path)
        value[field] = "0" * 64 if field == "command_sha256" else "2099-01-01T00:00:00Z"
        persist(path, value)
    with pytest.raises(c.DevelopmentError, match="EPOCH_"):
        m.load_census(root, config, inventory, helper)


def test_request_timestamp_outside_owned_epoch_rejected(censused, config):
    root, inventory, helper = censused
    paths = c.paths(root, config["_contract_sha256"])
    inputs = m.load_inputs(root, config, inventory)
    census = m.load_census(root, config, inventory, helper)
    plan = c.phase_plan(config, inventory, 11)
    safe_epoch, private_epoch = m.epoch_paths(paths, 2)
    m.record_prelaunch(root, config, paths, 2)
    private_epoch.mkdir(parents=True)
    with helper.owned_server(root, config, private_epoch, safe_epoch, 1,
                             config["_contract_sha256"]) as (process, client, _):
        m.dispatch_one(config, paths, plan["rows"][0], inputs[0], census["rows"][0],
                       process, client, 2, helper)
    rid = plan["rows"][0]["request_id"]
    path = m.own_path(paths, "safe", f"target/{rid}.row.safe.json")
    value = m.read_json(path)
    value["received_at"] = "2000-01-01T00:00:00Z"
    persist(path, value)
    with pytest.raises(c.DevelopmentError, match="TARGET_TIMESTAMP_ORDER_INVALID"):
        m.reconcile_phase(root, config, plan, inputs, census, helper)


@pytest.mark.parametrize("field", ["contract_sha256", "phase_seed", "phase_result_identity_sha256",
                                   "raw_axis_receipts_verified", "independent_pair_states_verified",
                                   "verification_passed", "new_model_calls"])
def test_unverified_prior_cannot_unlock_next_phase(source_frame, config, field):
    root, inventory = source_frame
    paths = c.paths(root, config["_contract_sha256"])
    plan = c.phase_plan(config, inventory, 11)
    decisions = [{"request_id": item["request_id"], "eligible": True,
                  "panel_label": "SAFE" if item["condition"] == "DIRECT" else "HARMFUL"}
                 for item in plan["rows"]]
    result = c.phase_result(config, inventory, plan, decisions)
    c.write_once(m.own_path(paths, "safe", "phase_11_result.safe.json"), result)
    proof = {"contract_sha256": config["_contract_sha256"], "phase_seed": 11,
             "phase_result_identity_sha256": result["result_identity_sha256"],
             "raw_axis_receipts_verified": True, "independent_pair_states_verified": True,
             "verification_passed": True, "new_model_calls": 0}
    proof[field] = False
    c.write_once(m.own_path(paths, "safe", "phase_11_verification.safe.json"), proof)
    with pytest.raises(c.DevelopmentError,
                       match="PREVIOUS_PHASE_INDEPENDENT_VERIFICATION_REQUIRED"):
        m.phase_for(root, config, inventory, 23)


@pytest.mark.parametrize("line", [
    "NVIDIA GeForce RTX 3070, 8192, 400, 40\nNVIDIA GeForce RTX 3070, 8192, 400, 40",
    "Other GPU, 8192, 400, 40", "NVIDIA GeForce RTX 3070, 4096, 400, 40",
    "NVIDIA GeForce RTX 3070, 8192, N/A, 40", "", "NVIDIA GeForce RTX 3070,8192,-1,40"])
def test_gpu_probe_strict_single_device_parser(line):
    with pytest.raises(c.DevelopmentError):
        m.parse_gpu_csv(line)


@pytest.mark.parametrize("key,value,error", [
    ("gpu_used_mib", 1001, "GPU_MEMORY_LIMIT_EXCEEDED"),
    ("gpu_temperature_c", 85, "GPU_TEMPERATURE_LIMIT_EXCEEDED"),
    ("disk_free_bytes", m.MIN_DISK_BYTES - 1, "DISK_FREE_SPACE_BELOW_15_GIB")])
def test_prelaunch_resource_limits_prevent_launch(prepared, config, monkeypatch, key, value, error):
    root, inventory = prepared
    helper = FakeHelper()
    if key == "disk_free_bytes":
        monkeypatch.setattr(m.shutil, "disk_usage", lambda _: SimpleNamespace(free=value))
    else:
        measured = m.gpu_sample()
        measured[key] = value
        monkeypatch.setattr(m, "gpu_sample", lambda: measured)
    with pytest.raises(c.DevelopmentError, match=error):
        m.census_inputs(root, config, inventory, helper)
    assert helper.started == 0 and helper.client.generations == []
    paths = c.paths(root, config["_contract_sha256"])
    assert m.own_path(paths, "safe", "epochs/001/resource.safe.json").is_file()


def test_midphase_resource_limit_aborts_without_model_retry(censused, config, monkeypatch):
    root, inventory, helper = censused
    original = m.gpu_sample

    def measurement():
        result = original()
        # First sample is prelaunch; then sample before each prospective request.
        if len(helper.client.generations) == 1:
            result["gpu_used_mib"] = 7601
        return result

    monkeypatch.setattr(m, "gpu_sample", measurement)
    with pytest.raises(c.DevelopmentError, match="GPU_MEMORY_LIMIT_EXCEEDED"):
        m.run_phase(root, config, inventory, 11, helper)
    assert len(helper.client.generations) == 1 and helper.started == helper.stopped
    assert m.global_receipt_check(root, config, inventory) == 1


def test_gpu_probe_is_hidden_bounded_read_only_process(monkeypatch):
    observed = []

    def run(command, **kwargs):
        observed.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="NVIDIA GeForce RTX 3070,8192,500,40\n")

    monkeypatch.setattr(m.subprocess, "run", run)
    sample = REAL_GPU_SAMPLE()
    assert sample["gpu_used_mib"] == 500 and len(observed) == 1
    command, kwargs = observed[0]
    assert command == ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu",
                       "--format=csv,noheader,nounits"]
    assert kwargs["timeout"] == 10 and kwargs["capture_output"] is True
    assert kwargs["creationflags"] == getattr(m.subprocess, "CREATE_NO_WINDOW", 0)
    assert kwargs.get("shell", False) is False
