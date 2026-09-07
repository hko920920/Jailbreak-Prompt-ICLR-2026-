# D3 fresh screen result and exact-topology handoff

Date: 2026-09-04 (Asia/Seoul)

## Current numbered-stage status

- Step 1: complete.
- Step 2R: complete.
- Step 3 / D2 exact micro-pilot: complete and independently verified.
- Step 4 / D3 fresh screen: complete and independently verified.
- Step 4 / D3 exact topology: revised prospective preflight passed; seed-11 target generation is
  completed all 888/888 seed-11 target records after twelve bounded-resume chunks. The final
  generation artifact passed a full identity/private-hash audit; no panel output has yet been
  opened.

## D3 fresh-screen result

The equal-topic GuidedBench development screen used 15 payloads, two attack families, and seeds
11/23/47 with the unchanged E0G-5 panel. It executed 104 fresh target records rather than the
135-record maximum permitted by the exact early-rejection funnel.

- Stable pairs: 12/30.
- h4rm3l stable pairs: 9.
- DeepInception stable pairs: 3.
- Not stable: 1.
- Unresolved: 17.
- All 104 target records were operational and evaluator-eligible.
- Qwen3Guard and JailMeter parsed all 104 outputs with no output-limit stop.
- Final route: `AUTHORIZE_D3_EXACT_TOPOLOGY_ON_ALL_STABLE_PAIRS`.

Authoritative identities:

- D3 screen result SHA-256:
  `3327735beab35cb142c2c3ec8a92a3c5e95ee928ef87b0f6744dfb696dedbb96`.
- D3 screen result identity:
  `c8089a8f1f67fdb6ef2fcb270b9680c5e921ea14647539f64c20b3df86221086`.
- Independent verification SHA-256:
  `eb7e11e91a51ce9ab8a932f9f55ca09fe0add39cc888c20de75f934718d2a3e9`.
- Independent verification identity:
  `2aacca14a685bd454e1f409648713afadcb3867cfdfaebe143962a6895279434`.

This is candidate-population evidence only. It says nothing yet about the recovery topology of the
12 pairs.

## Prospective D3 exact-topology denominator

Every selected stable pair remains in the denominator; there is no outcome-dependent cap.

- Nine h4rm3l instances: 3 frozen units, 8 subsets including empty.
- Three DeepInception instances: 7 frozen units, 128 subsets including empty.
- Two neutralizers per subset.
- Three primary seeds per nonempty subset unless a valid HARMFUL witness prospectively terminates
  later seeds for that exact `(instance, subset, neutralizer)` group.
- Empty attacked baselines: 72 logical observations from 36 exact screened responses.
- Finite materializations including empty: 912.
- Nonempty subset-neutralizer groups at seed 11: 888.
- New target calls: minimum 888, maximum 2,664.
- Capability-control universe: 1,776 records; only six-SAFE subsets open controls.

The other neutralizer always continues independently. SAFE, ABSTAIN, missing output, invalid input,
or truncation never triggers short-circuiting. Unexecuted seeds are recorded as skips and are never
synthesized as observations. Minimality still requires that every strict subset be conclusively
`NOT_RECOVERED`; no monotonicity assumption is used.

## Pre-output implementation state

The adaptive decision module, resumable runner, independent verifier, and contract tests were
implemented before any D3 topology output. Repository verification at this checkpoint passed 461
tests plus Ruff; four additional D3 contract tests then passed locally.

Current pre-output identities:

- Contract SHA-256:
  `d2824dee65ca65683154795ce52e4bd462a13bb052d19937514dd40a8bbf1ed7`.
- Runner SHA-256:
  `f435c9371c0ec79fcd54f76f6838508b41ef96626d379e36f37180852a15ecd0`.
- Adaptive topology module SHA-256:
  `be6764a7c9e97ce69fd81472fa8c188348821fd094a56bf1797104e00abf44cf`.
- Independent verifier SHA-256:
  `a6fd0f7dbab6fa6c4bf68438c267bbd879ec0fd411ee4d0bf3ce072b7130e9dc`.

## Interrupted preflight and efficiency correction

The first preflight attempt was intentionally interrupted after roughly ten minutes at the user's
request. It had used the already qualified exact GGUF tokenizer helper once per distinct prompt.
That implementation was scientifically safe but operationally inefficient because every call
started a new tokenizer process and remapped the model.

Post-interruption audit found:

- no D3 topology safe-output directory;
- no D3 topology private records;
- no residual Python, tokenizer, or target-generation process;
- therefore no topology outcome was opened and no scientific observation was lost.

Before any scientific output, token-budget validation was replaced by a conservative hard bound:
`UTF-8 byte count + 32 special-token allowance`. Qwen's byte-level BPE starts from at most one
symbol per byte and merges symbols, while the additional allowance covers special-token
bookkeeping. The separate frozen 128-token chat-template margin remains unchanged.

- Maximum scientific materialization: 2,198 UTF-8 bytes, conservative bound 2,230.
- Maximum capability-control materialization: 2,030 UTF-8 bytes, conservative bound 2,062.
- Frozen pre-chat-margin input limit: 3,456 tokens.
- Exact per-prompt token census is no longer claimed.

This correction changes only preflight efficiency and the form of the conservative budget proof.
It changes no prompt, subset, neutralizer, seed, model, decoding setting, panel rule, gate, or
planned scientific observation.

## Revised preflight result

The revised preflight completed in approximately 24 seconds and passed every frozen check.

- Status: `D3_EXACT_TOPOLOGY_PREFLIGHT_PASS`.
- Preflight file SHA-256:
  `09fc74157b4d473514f8d2534f9891791f1a6f009695a64db5c86a6e98594459`.
- Preflight identity:
  `55adb48b33127a0c354c6a69e26beae607422baeb844e2d4a671a7e57ed332ae`.
- Seed-11 plan SHA-256:
  `ef68de81b0f96454f1554ae8f00f95841f4256166134fa20b6394ceae5b5a7d6`.
- All safe preflight artifacts contained zero prohibited raw-content keys.
- Private prompt staging contained zero files.
- Full repository verification after the correction: 465 tests and Ruff passed.

No topology target response or evaluator output had been produced when this preflight passed.

## Seed-11 operational pause and bounded-resume amendment

Seed-11 target generation later reached 127/888 fully validated records before Windows denied one
atomic destination replacement. The completed 127-record temporary checkpoint was validated as an
exact plan prefix, including all corresponding private-record hashes, and promoted to the canonical
progress file. All 127 records are operational and evaluator-eligible with zero possible
maximum-token truncations. No committed record was lost and no experiment process remains active.

Observed mean target inference was 12.503 seconds versus 12.585 seconds mean wall time per record,
so checkpoint overhead was under 0.7%; model inference, not enumeration bookkeeping, dominates the
runtime. A separate operational-only launcher now adds bounded 64-record execution and transient
Windows replace retries without changing any frozen dependency, scientific identity, prompt,
model, decoding rule, denominator, evaluator, or gate.

Authoritative operational record:
`docs/D3_SEED11_OPERATIONAL_PAUSE_AND_RESUME_V1.md`.

## Next operation

Run seed 11's Qwen3Guard axis, JailMeter axis, and phase decision freeze in isolated processes. The
measured seed-11 witness rate will determine the exact seed-23 and seed-47 denominators.
