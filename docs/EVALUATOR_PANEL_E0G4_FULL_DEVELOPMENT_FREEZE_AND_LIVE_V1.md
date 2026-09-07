# E0G-4 Full Development Qualification Freeze and Live Record V1

Date: 2026-09-03 (Asia/Seoul)  
Evidence class: **FULL PUBLIC-DEVELOPMENT QUALIFICATION; NOT HELD-OUT OR PAPER EVIDENCE**

Final state: **BOTH AXES COMPLETE; AUTHORITATIVE V1.1 QUALIFICATION PASS**

## Prospective design

The E0G-2 panel rule is unchanged. All 889 public development records are included: 290
human-harmful, 599 human-safe, 728 unanimous, 161 split-vote, and 265 behavior groups. The
source/group denominators are HarmBench 303/149, JailbreakBench 152/101, and StrongREJECT
434/15. Execution order is a frozen record-ID hash order so an interruption does not produce a
source-ordered partial run.

The exact 60 completed E0G-2 records per axis are reused only after reconstructing and matching
their input SHA-256 and token counts. Every new record is written through an atomic metadata-only
checkpoint; raw goal/response text and raw model output remain memory-only. Completed progress
files are replaced by immutable axis files and removed.

The qualification gate was frozen before the 829 new Qwen or JailMeter measurements. It covers
strict parse and limit-stop integrity; class decision denominators; precision, Wilson lower
bounds, recall, and coverage; source, fold, unanimity, and behavior-group robustness; and a
10,000-replicate behavior-cluster bootstrap. A pass only authorizes a separately frozen untouched
held-out evaluator gate.

## Preflight and capacity

- selection: 889/889 records and 265/265 behavior groups;
- exact public-source reconstruction: pass;
- existing cache input identity: 60/60 for each axis;
- exact model/source/runtime artifacts: pass;
- fixed device continuity: RTX 3070, driver 536.67;
- JailMeter input tokens: min 668, median 878, empirical p95 1,347, max 1,698;
- maximum input plus full generation allowance: 3,234/4,096, leaving 862 tokens;
- records exceeding the context budget: zero.

Preflight identity:
`b709d68bc640f9806fab1b4084516fe776bf486521131aebc9750f6a1f54175e`.

## Completed Qwen3Guard axis

- records: 889/889, comprising 60 exact cache records and 829 new sequential records;
- strict parse coverage: 1.0000;
- output-limit stops: zero;
- Safety counts: 575 Unsafe, 286 Safe, 28 Controversial;
- Refusal counts: 602 No, 287 Yes;
- new invocation wall time: 523.23 seconds;
- peak CUDA allocation: 1,752,734,720 bytes;
- raw text/model output persisted: false;
- progress checkpoint retained after finalization: false.

Qwen axis identity:
`ec8e26b9324a826c561f20b1fff39f4d3752517ca868841f4b26f39641687934`.

## Completed JailMeter axis

The exact one-slot sequential configuration completed all 889 records with 60 verified cache
records and 829 new records. Strict parse coverage was 885/889, peak GPU memory was 5,086 MiB,
and the resumed invocation took 6,920.35 seconds. The progress checkpoint was removed only after
the immutable axis and summary were written. Four unparsed rows reached the exact 1,536-token
boundary and are conservatively counted as effective output-limit stops under the amendment.

### Pre-outcome output-limit instrumentation amendment

At 487 progress rows, a metadata-only integrity check found that the backend can report
`stopped_limit=false` at the exact 1,536-token generation boundary. The affected rows were
already unparsed and therefore already abstentions. Before the axis or panel outcome existed, a
V1.1 amendment was frozen at the 544/889 status point: an effective stop is the raw flag OR an
integer output-token count at least as large as the fixed maximum. This changes no model output,
label, panel rule, threshold, selection, or bootstrap. The parent V1 result is now a computational
precursor only; the V1.1 integrity-amended result is authoritative. See
[EVALUATOR_PANEL_E0G4_OUTPUT_LIMIT_INTEGRITY_AMENDMENT_V1_1.md](EVALUATOR_PANEL_E0G4_OUTPUT_LIMIT_INTEGRITY_AMENDMENT_V1_1.md).

## Frozen identities

- contract SHA-256:
  `9c458031ae3196727a8b6e60d5384c24928c52c70bf6318e841f7fa84aeeeed7`;
- selection identity:
  `e5a38990c4c5f5d15133e0c846691194b712cc29df7f73488806ac138d05b1a6`;
- runner SHA-256:
  `d10e37768021813c9c956c6d0dd56073d9ddcc8e4844429cc766074af823108d`;
- metric module SHA-256:
  `443ee8cca9eb002a53fa14787b33c674b3378ae0afe147d3b55773d18d3eca18`.

Held-out labels, P3 responses, and topology outcomes remain unopened. No new human annotation
has been collected and no paper-valid metric exists.

## Final decision

The authoritative V1.1 result passed all 27 frozen checks. It made 507 decisions at 0.5703
coverage with 0.0316 decided error, 0.9200 harmful precision, 1.0000 safe precision, 0.6345
harmful recall, and 0.5125 safe recall. This authorizes only a separately frozen one-shot
held-out gate. See
[EVALUATOR_PANEL_E0G4_FULL_DEVELOPMENT_RESULT_V1_1.md](EVALUATOR_PANEL_E0G4_FULL_DEVELOPMENT_RESULT_V1_1.md)
for uncertainty, source weaknesses, identities, and non-claim boundaries.
