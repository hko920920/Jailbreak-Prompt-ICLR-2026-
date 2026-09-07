# Evaluator Panel Runtime Qualification E0C

Date: 2026-09-01 (Asia/Seoul)

Decision: **E0C_V1_1_TWO_JUDGE_CPU_RUNTIME_QUALIFICATION_PASS / PANEL_NOT_YET_SCIENTIFICALLY_QUALIFIED**

Evidence class: **DEVELOPMENT RUNTIME QUALIFICATION**

## Meaning of the result

The exact pinned Ministral and Phi-4 Mini judge artifacts can now be used through the frozen local CPU runtime. Both models loaded, applied their model chat templates, produced strict parser-valid outputs, withheld nonce canaries, resisted the two harmless untrusted-data instruction probes, and reproduced every response byte-for-byte in independent processes.

This admits the runtime implementation only. It does not establish judge accuracy, select an actionability profile, qualify the evaluator panel, score P3, or support a paper-valid claim. The 889-record external calibration stage is the next operation. The 947-record held-out partition and all P3 responses remain sealed.

## Exact retained model artifacts

| Judge | Publisher | Bytes | SHA-256 |
|---|---|---:|---|
| `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` | official Mistral organization | 2,147,023,008 | `9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8` |
| `microsoft_Phi-4-mini-instruct-Q4_K_M.gguf` | pinned Bartowski conversion of the exact Microsoft base | 2,491,874,688 | `01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2` |

Only these two model files were downloaded. Their combined retained size is 4,638,897,696 bytes (4.320 GiB). Each remote repository revision, remote LFS size and SHA-256, local byte size, and local SHA-256 matched the pre-outcome contract.

The reused llama.cpp runtime is build 10441 at revision `0177dcc7300bad8914bb838baabce87899812491`. Its source archive SHA-256 is `7fdbac5860ad1c64bf1e5703e4491612562e953a709a9f190affd6141147c6aa`. All 52 extracted files matched the pinned archive byte-for-byte; the extracted bundle-manifest identity is `8394050efbfc2e387651cc1a11010583169e3bb0bfcd8a6a2a67d9a7ef281ae0`.

## Frozen qualification cases and gates

Five harmless synthetic cases were run twice per model in separate processes:

1. unconstrained exact benign capability token;
2. Guided criterion with one present and one absent point;
3. Guided instruction-injection data with both points absent;
4. aligned, actionable benign response with zero harmful utility;
5. unaligned instruction-injection data with zero harmful utility and zero task alignment.

Every run used `device=none`, zero GPU layers, disabled operation offload, temperature zero, top-k one, a fixed seed, the exact frozen system/user prompt bytes, and reasoning disabled. Guided and actionability outputs retained JSON-schema constrained decoding plus the already-frozen exact V2 parsers. The schema constrained only syntax; the substantive booleans and scores remained model decisions.

## V1 failure and governed repair

The first complete run was retained as an explicit failure, identity `19278f920708024a5e8910354e9c2c39672a8f1b90b2fbbef22e90b264ffbc3a`:

- llama-cli abbreviated long displayed prompts, so the V1 extractor missed otherwise valid terminal Ministral JSON;
- Phi-4's Jinja chat-parser path passed its assistant generation prompt into the JSON grammar, causing sampler initialization failure.

A separate repair probe froze three compatibility candidates in priority order before testing. Candidate selection used only process success, strict parsing, nonce non-disclosure, chat-template activation, zero GPU layers, and byte determinism. Parsed numeric scores were excluded from selection. The first candidate failed; the second, `native_template_without_jinja_with_json_schema`, passed and was frozen for V1.1. The JSON schema, prompts, cases, expected semantics, model pair, seed, and gate were not relaxed.

The V1.1 terminal-JSON extractor also handles CLI display abbreviation. It does not search arbitrary prose for a favorable answer: it requires one complete JSON object at the terminal generation boundary, after which the exact V2 parser remains authoritative.

## V1.1 result

| Judge | Invocations | All gates | Median process time | Median prompt rate | Median decode rate |
|---|---:|---|---:|---:|---:|
| Ministral 3 3B | 10 | PASS | 9.149 s | 89.815 tok/s | 13.575 tok/s |
| Phi-4 Mini | 10 | PASS | 11.664 s | 66.425 tok/s | 12.020 tok/s |

For each model, all of the following are true:

- 10/10 executions and output extractions passed;
- 10/10 strict parses and canary checks passed;
- 10/10 frozen harmless semantic expectations passed;
- all five cases were byte-identical across two independent processes;
- the model chat template was active on every run;
- no source input or generated output hit its truncation limit;
- zero GPU layers were logged on every run;
- decode rates were observed for every run;
- atomic resume-cache replay passed.

No post-hoc throughput floor was introduced. The measured rates are feasibility measurements, not a scientific quality criterion.

## Result-identity finalization

The V1 lineage computed its result identity from insertion-order JSON in memory and then wrote sorted-key JSON. That made the declared V1.1 identity non-recomputable from the saved file, although no model output, parsed value, check, or metric was affected.

The predecessor PASS file remains immutable. A separate no-inference finalizer copied every substantive field unchanged, added an explicit identity scheme and audit record, and replaced only the identity. The authoritative final result identity is:

`5e57e4fafd2102f4c76cc4669fd0ddd16812c9103dd7e79e5b45e6b24636be7e`

It exactly recomputes from UTF-8, `ensure_ascii=false`, sorted keys, compact separators, with the `result_identity_sha256` field omitted. The authoritative final result file SHA-256 is `b4277f3ef7c533716d3037767b733e857bba5f037c97cfc007a275b2056cff36`.

## Storage hygiene

After finalization:

- both transient Hugging Face download metadata directories were removed;
- two empty model-local `.cache` parents were removed;
- 20 failed-V1 private records and four repair-probe private records were removed after their safe hash-only audit results were retained, deleting 3,913,995 bytes;
- the two verified GGUF files and the 20 final V1.1 harmless private records remain;
- retained final private records occupy 4,209,693 bytes and are gitignored;
- free C-drive space after cleanup was 88,843,014,144 bytes (82.742 GiB).

The deleted private records are reproducible harmless diagnostics, not unique scientific data. The safe V1 failure and repair-probe results remain tracked.

## Artifacts and identities

- authoritative final result: [e0c_runtime_qualification_final.safe.json](../data/evaluator_panel_v2/e0c_runtime_qualification_final.safe.json), identity `5e57e4fafd2102f4c76cc4669fd0ddd16812c9103dd7e79e5b45e6b24636be7e`;
- V1.1 contract: [runtime_qualification_e0c_v1_1.json](../configs/evaluator_panel/runtime_qualification_e0c_v1_1.json), SHA-256 `5400cda7cea4bc1b564a63bd7fdc2ada765ca93eb105cda7b282766d60ca3b98`;
- V1.1 runner: [run_evaluator_panel_runtime_qualification_e0c_v1_1.py](../scripts/run_evaluator_panel_runtime_qualification_e0c_v1_1.py), SHA-256 `3115b26ef500223ad1c8cec851a6b2dd165eeb998b95a8b2b56efe564425522e`;
- repair-probe result: [e0c_runtime_repair_probe.safe.json](../data/evaluator_panel_v2/e0c_runtime_repair_probe.safe.json), recorded identity `a087069ec154c7acda549f2e62a0222a094c144534ce59454801f5d425796045`;
- identity-finalization contract: [e0c_result_identity_finalization.json](../configs/evaluator_panel/e0c_result_identity_finalization.json), SHA-256 `70ab70b73c450aa555fafb763ff947751063a9024f53a643817c9b5da62a1814`;
- finalizer: [finalize_evaluator_panel_e0c_result_identity.py](../scripts/finalize_evaluator_panel_e0c_result_identity.py), SHA-256 `30cf36cced36c70d26febcf00cb734e05bf09b6afb4aaa02894a22048ec996fb`.

## Verification

- E0C-focused tests: 13 passed;
- full repository regression after the final identity-only tests: 332 passed;
- Ruff over source, tests, and scripts: passed;
- mypy over 51 package source files: passed;
- Git whitespace check: passed, with existing Windows LF/CRLF notices only;
- finalized result identity recomputation: exact match;
- substantive predecessor-versus-final result field equality after removing the three authorized identity fields: exact match.

## Sealed boundary and next operation

- external calibration judge outputs observed: false;
- A profile selected: false;
- external held-out panel outputs observed: false;
- held-out human labels reconstructed or compared: false;
- P3 rescored under panel V2.1: false;
- topology oracle opened: false;
- paper-valid result: false.

Next, freeze and run **E0D external calibration only** over the 889 labeled calibration records. Select at most one of A1/A2/A3 under the already-frozen rule. Do not reconstruct or open the 947 held-out labels until that profile and the complete E0D execution identities are sealed.
