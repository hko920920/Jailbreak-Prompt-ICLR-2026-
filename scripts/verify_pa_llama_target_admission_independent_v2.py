"""Independent, read-only verification of exactly the new harmless V2 receipts.

No runner imports, model/process launch, HTTP, old private inputs, or raw output.
The optional write creates only the fixed new verification artifact, exclusively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CONTRACT = "f40be2cf24ddf6141c0e5a27ce888ee67d0183b4a7321f2f178b8808d53ae1ea"
PREDECESSOR = "f18847551904811a620ce8a3cad4263cc902f22ebb12feffe142f2db2948012f"
RAW_PIN = "e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65"
SERVED_PIN = "93c0e9aa3629bbd77e68dbc0f5621f6e6b23aa8d74b932595cdb8d64684526d7"
EXPECTED = {
    "exact_sentinel": ("exact_text", "P2_OK"), "arithmetic": ("integer", 42),
    "sorting": ("integer_list", [1, 2, 3]), "color_mixing": ("word", "green"),
    "capital": ("word", "paris"), "translation": ("word", "bonjour"),
    "opposite": ("word", "cold"), "primes": ("integer_list", [2, 3, 5]),
    "json_format": ("json_object", {"status": "ok"}),
    "copy_token": ("exact_text", "alpha-7"),
}
GENERATION = {
    "seed": 17, "temperature": 0, "max_tokens": 48, "top_k": 1,
    "top_p": 1, "min_p": 0, "repeat_penalty": 1,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def check(condition, code):
    if not condition:
        raise ValueError(code)


def parse(raw):
    def pairs(items):
        value = {}
        for key, content in items:
            check(key not in value, "duplicate_json_key")
            value[key] = content
        return value

    def constant(_):
        raise ValueError("nonfinite_json")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def read(path):
    return parse(path.read_bytes())


def independent_score(name, answer):
    check(isinstance(answer, str), "nonstring_answer")
    kind, expected = EXPECTED[name]
    value = answer.strip()
    valid = True
    if kind == "word":
        valid = bool(re.fullmatch("[a-zA-Z]+", value))
        value = value.casefold()
    elif kind == "integer":
        valid = bool(re.fullmatch(r"-?(0|[1-9][0-9]*)", value))
        if valid:
            value = int(value)
    elif kind == "integer_list":
        parts = value.split(",")
        valid = all(re.fullmatch(r"-?(0|[1-9][0-9]*)", part.strip()) for part in parts)
        if valid:
            value = [int(part.strip()) for part in parts]
    elif kind == "json_object":
        try:
            value = parse(value)
            valid = type(value) is dict
        except ValueError:
            value, valid = answer.strip(), False
    correct = valid and encode(value) == encode(expected)
    diagnostic = None
    if not correct and kind == "word":
        match = re.fullmatch(r"([a-zA-Z]+)([.!?])", answer.strip())
        if match and match[1].casefold() == expected:
            diagnostic = ("EXPECTED_WORD_PLUS_TERMINAL_PERIOD" if match[2] == "."
                          else "EXPECTED_WORD_PLUS_TERMINAL_PUNCTUATION")
    return {
        "content_check_passed": bool(correct), "scorer": kind,
        "parsed_as_required_type": bool(valid), "response_characters": len(answer),
        "raw_content_sha256": sha(answer.encode()),
        "normalized_content_sha256": sha(encode({"scorer": kind, "value": value})),
    }, diagnostic


def check_template(value, context):
    expected = {
        "contract_sha256": CONTRACT, "native_chat_template_sha256": RAW_PIN,
        "expected_served_chat_template_sha256": SERVED_PIN,
        "observed_served_chat_template_sha256": SERVED_PIN,
        "expected_served_chat_template_utf8_bytes": 4613,
        "observed_served_chat_template_utf8_bytes": 4613,
        "template_source_available": True, "served_template_matches_pin": True,
        **context,
    }
    check(all(encode(value.get(key)) == encode(item) for key, item in expected.items()),
          "template_observation_binding")


def verify(root):
    root = root.resolve(strict=True)
    config_path = root / "configs/natural_language_localization/pa_llama_target_admission_v2.json"
    check(sha(config_path.read_bytes()) == CONTRACT, "contract_pin")
    config = read(config_path)
    check(encode(config["generation"]) == encode(GENERATION), "generation_pin")
    check([f["prompt_id"] for f in config["fixtures"]] == list(EXPECTED), "fixture_order")
    safe = root / "data/natural_language_localization/pa_llama_target_admission_v2" / CONTRACT
    private = root / "artifacts/pa_llama_target_admission_v2/private" / CONTRACT
    for path in (safe, private):
        check(path.resolve().is_relative_to(root), "contained_artifact_root")
    check(len(list(safe.glob("*.dispatch.safe.json"))) == 11, "dispatch_count")
    check(len(list(safe.glob("*.row.safe.json"))) == 11, "row_count")
    check(len(list(safe.glob("*.tpl.safe.json"))) == 13, "template_count")
    check(len(list(private.glob("*.request.private.json"))) == 11, "request_count")
    check(len(list(private.glob("*.reply.private.json"))) == 11, "reply_count")
    pids = {1: 50760, 2: 56040}
    epoch_records = {}
    for epoch, pid in pids.items():
        records = [read(safe / f"server-{epoch:02d}.{part}.safe.json")
                   for part in ("started", "identity", "stopped")]
        for record in records:
            check(record["contract_sha256"] == CONTRACT and record["pid"] == pid
                  and record["epoch"] == epoch and record["owned_process_only"] is True,
                  "owned_epoch_identity")
        check(type(records[2]["returncode"]) is int, "observed_process_stop")
        check(records[1]["served_chat_template_sha256"] == SERVED_PIN, "epoch_served_pin")
        check_template(read(safe / f"server-{epoch:02d}.tpl.safe.json"),
                       {"epoch": epoch, "pid": pid, "process_id": pid})
        epoch_records[epoch] = records
    check(datetime.fromisoformat(epoch_records[1][2]["stopped_at"])
          <= datetime.fromisoformat(epoch_records[2][0]["started_at"]), "fresh_process_order")
    rows, scored, failures = [], [], []
    for index in range(11):
        ordinal = index + 1
        epoch = 1 if index < 10 else 2
        fixture = config["fixtures"][index if index < 10 else 0]
        name = fixture["prompt_id"]
        kind, expected = EXPECTED[name]
        check(fixture["scorer"] == kind and encode(fixture["expected"]) == encode(expected),
              "declared_expectation")
        request = read(private / f"{ordinal:02d}.request.private.json")
        wanted = {"model": config["model"]["alias"], "stream": False,
                  "messages": [{"role": "user", "content": fixture["text"]}], **GENERATION}
        check(encode(request) == encode(wanted), "exact_request_fields")
        journal = read(safe / f"{ordinal:02d}.dispatch.safe.json")
        context = {"contract_sha256": CONTRACT, "ordinal": ordinal, "epoch": epoch,
                   "process_id": pids[epoch], "fixture_id": name,
                   "request_sha256": sha(encode(wanted)), "served_chat_template_sha256": SERVED_PIN}
        check(all(journal.get(key) == value for key, value in context.items()), "journal_binding")
        check_template(read(safe / f"{ordinal:02d}.tpl.safe.json"),
                       {"ordinal": ordinal, "epoch": epoch, "process_id": pids[epoch]})
        raw = (private / f"{ordinal:02d}.reply.private.json").read_bytes()
        reply = parse(raw)
        check(reply["model"] == config["model"]["alias"], "reply_alias")
        check(isinstance(reply["choices"], list) and len(reply["choices"]) == 1, "one_choice")
        choice = reply["choices"][0]
        check(choice["index"] == 0 and choice["finish_reason"] == "stop", "untruncated_choice")
        message = choice["message"]
        check(message["role"] == "assistant" and not any(message.get(key) for key in
              ("refusal", "tool_calls", "function_call", "reasoning_content")), "answer_channel")
        usage = reply["usage"]
        check(all(type(usage[key]) is int and usage[key] > 0 for key in
                  ("prompt_tokens", "completion_tokens", "total_tokens")), "usage_types")
        check(usage["completion_tokens"] <= 48
              and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"],
              "usage_bounds")
        result, diagnostic = independent_score(name, message["content"])
        row = read(safe / f"{ordinal:02d}.row.safe.json")
        measured = {**journal, **result, "reply_bytes_sha256": sha(raw), "finish_reason": "stop",
                    "not_truncated": True, "passed": result["content_check_passed"],
                    "usage": {key: usage[key] for key in
                              ("prompt_tokens", "completion_tokens", "total_tokens")},
                    "request_max_tokens": 48}
        check(all(encode(row.get(key)) == encode(value) for key, value in measured.items()),
              "independent_score_row_binding")
        if not result["content_check_passed"]:
            failures.append({"ordinal": ordinal, "fixture_id": name,
                             "posthoc_diagnostic": diagnostic or "NOT_ADJUDICATED",
                             "original_scoring_failure_preserved": True})
        scored.append(result)
        rows.append(row)
    saved = read(safe / "result.safe.json")
    check(saved["rows"] == rows and saved["capability_passes"] == 7
          and saved["admitted_basic_harmless_runtime_only"] is False, "saved_result_consistency")
    predecessor = root / "data/natural_language_localization/pa_llama_target_admission_v1"
    predecessor /= PREDECESSOR
    aborted = read(predecessor / "aborted.safe.json")
    check(aborted["journaled_dispatches"] == aborted["reply_receipts"] == 0
          and not list(predecessor.glob("*.dispatch.safe.json")), "predecessor_zero_output")
    return {
        "schema_version": "jbspan-pa-llama-target-admission-independent-verification-v2",
        "contract_sha256": CONTRACT, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "verifier_sha256": sha(Path(__file__).read_bytes()),
        "saved_result_sha256": sha((safe / "result.safe.json").read_bytes()),
        "independent_verification_passed": True, "new_target_calls_by_verifier": 0,
        "old_private_inputs_accessed": False, "raw_content_copied_or_emitted": False,
        "verified_requests": 11, "verified_replies": 11, "verified_template_observations": 13,
        "primary_exact_passes": sum(x["content_check_passed"] for x in scored[:10]),
        "primary_denominator": 10, "all_eleven_finish_stop": True,
        "sentinel_raw_digest_identical": scored[0]["raw_content_sha256"]
        == scored[10]["raw_content_sha256"],
        "sentinel_normalized_digest_identical": scored[0]["normalized_content_sha256"]
        == scored[10]["normalized_content_sha256"],
        "raw_template_sha256": RAW_PIN, "served_template_sha256": SERVED_PIN,
        "served_template_utf8_bytes": 4613,
        "owned_process_ids": list(pids.values()), "stop_receipts_verified": True,
        "fresh_process_order_verified": True, "live_pid_absence_not_checked_by_this_script": True,
        "predecessor_generation_calls": 0, "aggregate_generation_calls": 11,
        "failed_fixtures": failures, "original_basic_admission_gate_passed": False,
        "posthoc_punctuation_diagnostic_changes_gate": False,
        "paper_or_jailbreak_or_judge_admission": False,
    }


def self_test():
    examples = [("capital", "Paris", True), ("capital", "Paris.", False),
                ("color_mixing", "Green.", False), ("opposite", "Cold.", False),
                ("arithmetic", "142", False), ("arithmetic", "42", True),
                ("sorting", "1, 2, 3", True), ("sorting", "1,2,3,4", False),
                ("json_format", '{"status":"ok","status":"ok"}', False),
                ("json_format", '{"status":"ok"}', True),
                ("exact_sentinel", "P2_OK", True), ("exact_sentinel", "p2_ok", False)]
    for name, answer, expected in examples:
        score, _ = independent_score(name, answer)
        check(score["content_check_passed"] is expected, "synthetic_scoring")
    check(independent_score("capital", "Paris.")[1] == "EXPECTED_WORD_PLUS_TERMINAL_PERIOD",
          "synthetic_punctuation_diagnostic")
    return {"synthetic_checks_passed": len(examples) + 1, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--write-safe", action="store_true")
    args = parser.parse_args()
    result = self_test() if args.self_test else verify(args.root)
    if args.write_safe:
        check(not args.self_test, "self_test_cannot_write")
        path = args.root / "data/natural_language_localization/pa_llama_target_admission_v2"
        path = path / CONTRACT / "independent-verification.safe.json"
        check(path.resolve().is_relative_to(args.root.resolve()), "safe_output_containment")
        with path.open("xb") as stream:
            stream.write(encode(result) + b"\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
