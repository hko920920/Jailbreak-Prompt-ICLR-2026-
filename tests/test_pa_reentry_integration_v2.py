"""Genuine 388-request journal/worker/proof bridge, entirely invented harmless data.

Only raw historical verification and the hardware/HTTP boundary use fixtures.
The real continuation constructor, original request/parser functions, durable
journal, resource/lifecycle verifier, full proof and panel consumer all execute.
No real dataset, model process, GPU query, download or inference is accessed.
"""

import copy
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pa_reentry_panel_v2 as panel_module  # noqa: E402
import pa_reentry_target_v2 as target_module  # noqa: E402
from test_pa_reentry_panel_v2 import Target as InventedPanelTarget  # noqa: E402
from test_pa_reentry_target_v2 import engine as small_engine  # noqa: E402,F401
from test_pa_reentry_target_v2 import renew, response, stamp  # noqa: E402

j = target_module.j


@pytest.fixture
def full_bridge(request, monkeypatch):
    small, runtime_state, auth = request.getfixturevalue("small_engine")
    original_config = small.config
    invented = InventedPanelTarget(small.root)
    original_config.update(
        _contract_sha256=panel_module.PARENT,
        panel=copy.deepcopy(invented.config["panel"]),
    )
    original_config["execution_limits"].update(invented.config["execution_limits"])
    plan = copy.deepcopy(invented.plan)
    requests = plan["requests"]
    prompts = {item["materialization_id"]:
               "A harmless synthetic question identified by " + item["materialization_id"]
               for item in requests}
    census = {"rows": [{"materialization_id": mid, "native_prompt_tokens": 12}
                       for mid in prompts]}
    historical_rows = []
    harmless_raw = response(original_config)
    for item in requests[:1082]:
        parsed = target_module.frozen.parse_reply(original_config, item, harmless_raw, 12)
        historical_rows.append({
            **item, **parsed, "contract_sha256": panel_module.PARENT,
            "request_sha256": j.digest(target_module.frozen.request_for(
                original_config, item, prompts[item["materialization_id"]])),
            "dispatch_at": stamp(-60), "received_at": stamp(-30),
        })
    for key, value in {
        "ORIGINAL": panel_module.PARENT,
        "PLAN": panel_module.PLAN,
        "PREFIX_COUNT": 1082,
        "TOTAL": 1470,
        "PREFIX_ROWS": j.digest(historical_rows),
        "SUFFIX": j.digest(requests[1082:]),
        "SUFFIX_IDS": j.digest([item["request_id"] for item in requests[1082:]]),
        "CHUNKS": ((4, 1083, 1292), (5, 1293, 1470)),
    }.items():
        monkeypatch.setattr(target_module, key, value)
    helper = small.helper
    original_owned = helper.owned_server
    body_to_item = {
        j.digest(target_module.frozen.request_for(
            original_config, item, prompts[item["materialization_id"]])): item
        for item in requests
    }
    assert len(body_to_item) == 1470
    observed_ordinals = []

    class Client:
        def request(self, route, body, *, timeout):
            assert route == "/v1/chat/completions" and timeout == 240
            item = body_to_item[j.digest(body)]
            assert item["ordinal"] >= 1083
            assert worker.journal.paths(item["request_id"])["intent"].is_file()
            observed_ordinals.append(item["ordinal"])
            return response(original_config)

    @contextmanager
    def owned(root, config, private, safe, epoch, sha):
        with original_owned(root, config, private, safe, epoch, sha) as (process, _, identity):
            yield process, Client(), identity

    helper.owned_server = owned
    history = SimpleNamespace(
        target=SimpleNamespace(
            root=small.root, config=original_config, plan=plan, helper=helper,
            assert_unchanged=lambda: None,
            path=small.historical.path,
        ),
        rows1082=historical_rows, prompts=prompts, census=census,
        manifest_proof={"verified": True, "manifest_identity_sha256": "e" * 64,
                        "descriptor_count": 1323, "archive_file_count": 1271},
    )
    manifest = {"manifest_identity_sha256": "e" * 64}
    worker = target_module.TargetContinuation(history, manifest,
        execution_identity=small.execution_identity, sample=small.sample)
    worker.launch_ready = True
    worker._launch_verifier = lambda: None
    return worker, runtime_state, renew(auth), invented.payloads, observed_ordinals


def test_all388_real_journal_to_all1470_target_proof_to_panel_consumer(full_bridge):
    worker, runtime, auth, payloads, observed = full_bridge
    proof = worker.run(auth)
    assert observed == list(range(1083, 1471))
    assert runtime.launches == 2
    assert proof["target_records"] == 1470 and proof["new_target_records"] == 388
    assert proof["reused_target_records"] == 1082
    assert [attempt["completed_target_requests"] for attempt in proof["all_attempts"]] == [210, 178]
    assert [attempt["logical_chunk"] for attempt in proof["all_attempts"]] == [4, 5]
    consumer = panel_module.ReentryPanel(worker, payloads, worker.safe.parent,
                                        worker.private.parent, worker.execution_identity)
    rows, accepted = consumer.verify_targets()
    assert accepted == proof and len(rows) == 1470
    assert sum(row["kind"] == "science" for row in rows) == 882
    assert sum(row["kind"] == "control" for row in rows) == 588
    assert sum(row["kind"] == "science" for row in rows[1082:]) == 220
    assert sum(row["kind"] == "control" for row in rows[1082:]) == 168
    assert accepted["prior_operation_failures"] == list(panel_module.FAILURES)
    assert accepted["original_operational_gate_passed"] is False
    assert accepted["first_continuation_operational_gate_passed"] is False
    assert accepted["paper_validity"] is False
    assert worker.journal.audit_events()["invalid_events"] == 0
    assert not (worker.safe.parent / "panel").exists(), "Proof read never starts a judge"
    assert not (worker.private.parent / "panel").exists()
    assert len(list((worker.private / "requests").iterdir())) == 388
    assert len(list((worker.safe / "requests").iterdir())) == 388
    assert worker.config["execution_limits"]["deadline_utc"] == "2026-09-05T22:55:47+00:00"
    assert all(row["request_id"] == item["request_id"]
               for row, item in zip(rows, worker.plan["requests"], strict=True))
