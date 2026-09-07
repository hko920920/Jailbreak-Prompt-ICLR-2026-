# Second operational continuation — v2 prospective protocol

This is stage-2 preparation, not target/evaluator launch authority. The scientific
execution contract remains `d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0`;
the bound plan remains `8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9`.
The old UTC deadline is historical, not silently extended or reused for new calls.

## Fixed evidence and scientific frame

Reuse original ordinals 1–872 and explicitly mapped archived 873–1082, including
all raw receipts, failures and immutable old verifiers. The new archive manifest
pins exact current paths/bytes. The contemporaneous relocation receipt remains
unavailable. Today's verification cannot establish that missing historical chain.
The original DISK_FREE_SPACE_BELOW_15_GIB and first continuation
CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB remain failures, never original PASS.

Only ordinals 1083–1470 may be newly generated: 388 = 220 science + 168 controls.
Preserve chunks 1083–1292 and 1293–1470 and within-chunk order; a reviewed resume
can create an additional owned worker epoch inside the same logical chunk.
Reuse all 1082 completed observations, including truncations and UNKNOWNs.
No outcome-dependent retry, replacement, selection or omission is permitted.

Keep byte-exact P and scientific request bodies, renderer ownership rules, both
operators, masks, 11/23/47 science seeds, benign controls, token caps, decoding,
target, both judges, pure parsers, context limits, eligibility and UNKNOWN rules.
Both evaluation axes account for the full 882 science rows; skipped records are
explicitly not observed judge responses. Controls are never sent to judges.
No sealed60/60, historical C1N/D3 raw cohorts, downloads or paid APIs are allowed.

## Explicit stage authority

The frozen preparation object is content-addressed and sets
`execution_authorized: false`. It pins all new sources, tests, this protocol,
the archive manifest and the original contract. Its identity defines the new
SAFE/private output namespace. Verification never grants inference by itself.

After the user separately directs stage 3, 4 or 5, the responsible orchestrator
may create a stage-specific receipt referencing that actual direction. A string
and hash are an audit record, not cryptographic authentication of the user.
Receipt stages are `target`, `qwen`, `jailmeter`; admission windows are bounded
to at most 2, 2, 6 hours respectively. Preparation now creates none. Each stage
invocation exclusively consumes its receipt; reentry requires a fresh reviewed
direction and receipt, not reuse of an old failed launch token.

No call is admitted before issue time or after expiry. Already dispatched calls
retain their original in-flight timeout. Late responses are saved first and
explicitly marked as received after the admission window; they are never discarded
or reissued to conceal a delay. No later stage starts automatically.

## Durable request and process state

Write the original request privately before a durable SAFE dispatch intent.
Persist each received response exactly once in a private JSON envelope containing
lossless base64 raw bytes, receive time, latency and identity binding. This is a
single response store, not a raw-copy log. SAFE records contain hashes/metadata,
not prompts or response content. Rebuild the row through unchanged parsers and
publish its completion marker last. Preserve all earlier artifacts.

Use exclusive pending-file creation, fsync, atomic no-overwrite publication and
kernel-held stage locks. Completed pending publications may be reconciled only
after full byte/identity/parser verification. Unknown, inconsistent or partial
artifacts fail closed. Windows has no portable directory-fsync guarantee here;
this is tested crash-resistant publication, not proof against every power-loss
or filesystem failure. Raw hashes are integrity checks, not external signatures.

Reentry classes are COMPLETE, UNISSUED, AMBIGUOUS. COMPLETE may require repair
of missing derived publications after the complete response and process chain
have been verified. Only UNISSUED may dispatch. An intent without a certifiable
response is AMBIGUOUS, never automatically retried. A partially written response
cannot be guessed. Saved progress files never override request evidence.

Worker epochs are distinct on resume. A missing stop receipt stays missing;
an explicit later review may record a currently absent PID, not fabricate a
historical clean shutdown. Live, reused, inaccessible or unknown PID states
block automatic reclamation. A verified raw response is retained even when
resource/lifecycle evidence is insufficient for a complete scientific artifact.
Such insufficiency must remain a verifier blocker or explicit incomplete state,
not an operational PASS obtained by relaxing the old checks.

## Resources and automatic records

Retain 20 GiB free-disk prelaunch and 15 GiB per-dispatch floors. Retain the
original GPU/VRAM/temperature guards, per-request cooling to at most 60 C,
180-second cooling wait cap and 0.5-second polling. Do not change the OS,
pagefile, fan policy, drivers or model settings. Record RAM/commit/pagefile
diagnostics at stage/epoch boundaries; diagnostics are not new exclusion rules.

The runner automatically writes append-only SAFE event files, request completion
and interruption records and reconstructible progress/stop summaries. Record
counts, remaining/ambiguous/UNKNOWN accounting, last verified request, timestamps,
elapsed time and resource checkpoints. A process kill can prevent a final event;
reentry discloses its absence. Logs do not require an available assistant turn,
but a disconnected app/host cannot be promised uninterrupted computation.
Never automatically delete research receipts, failures or active dependencies.

## Downstream acceptance and stage boundary

A new composite target proof must reverify all 1470 rows and disclose both old
failures, the archive limitation, all new epochs and missing stops. Both axes
must independently verify all 882 rows, parser/request bindings, worker/resource
chains, target proof and target → Qwen → JailMeter order. Partial frames fail.
The final join may call only the unchanged pure scientific join/analysis through
an in-memory schema adapter; it cannot publish the old unqualified schema/PASS.
Publish v2-disclosed measurements and identities with verification last.

Stage 2 validates these paths using harmless synthetic transports and static NEW
evidence replay only. Stages 3–5 inference and stages 6–8 joins/claim judgment
remain separate user-directed work. No PDF, paper acceptance claim or independent
confirmation claim follows from completion of this engineering stage.

## Operational entry points for later directed stages

Use the existing qualified `C:/Users/SOGANG/anaconda3/python.exe`, Python `-B`,
from the project root. Do not use the project `.venv` with missing Torch metadata.
`scripts/pa_reentry_v2.py` defaults to `verify-freeze` (read-only).
`preflight` replays verified history and request status without model inference.
Its optional `--report docs/PA_STAGE2_PREFLIGHT_<label>.safe.json` writes only a
new exclusive SAFE report. `prepare` freezes infrastructure, not model authority.

Only after the actual next-stage user direction, `run-stage --stage target`
(or `qwen` / `jailmeter`) with `--direction-ref <actual-current-direction-reference>`
creates a fresh bounded receipt and runs that one stage. Do not pre-create these
receipts during stage 2. `recover-stage` performs validated derived-publication
recovery only. `review-stage` additionally requires the exact `--epoch` and
records observed release only; it cannot dispatch. Reviewed target epoch IDs are
32-hex identifiers; evaluator epochs are integer indices. A normal evaluator run
first recovers only complete, already verified durable responses under that
current direction. Ambiguous calls and missing release/resource evidence still
block and must be reported; these commands never silently broaden authority.

The finalizer has a separate `make_direction` / `validate_direction` receipt for
stage 6 (measurements) or stage 7 (analysis), bound to this execution identity and
a maximum two-hour window. A stage-6 receipt cannot enable analysis. Stage 7 also
requires published, verified stage-6 products matching the current target and
both axes. It writes a distinct `with-analysis` namespace, preserving the earlier
`measurements-only` products. This receipt is likewise an orchestrator record of
actual user direction, not authentication manufactured by a hash.
