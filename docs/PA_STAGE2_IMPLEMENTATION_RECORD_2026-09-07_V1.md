# Stage 2 implementation record — 2026-09-07

Status: COMPLETE at04:38:59UTC. Started approximately03:44UTC following the user's
explicit next-stage direction. Allowance: 2–4 hours, to be revised if necessary.
This record is not an experiment authorization or scientific result.

Scope: a separate second operational continuation; immutable reuse of 1082
targets, exact missing 388, durable/recoverable target and two-axis evaluation
records, synthetic interruption tests, archive pins and explicit downstream
verification. No real inference, model launch, download, sealed data, manuscript,
deletion of old evidence, or modification of pinned old code is authorized here.

The original DISK_FREE_SPACE_BELOW_15_GIB and first continuation
CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB remain failures. Existing scientific
request bytes, parsers, judges, controls, UNKNOWN rules and full frame stay fixed.
The missing contemporaneous archive-relocation receipt remains a limitation.

## Implementation coordination

New files will use the `pa_reentry_*_v2` family; old v1 files remain untouched.
Shared journal records requests exclusively before write-ahead dispatch intent,
then a single private response envelope (raw bytes encoded without lossy parsing,
receipt time and latency), reconstructed SAFE row and a completion marker.
Publication is exclusive and durable; ambiguous dispatches cannot be replayed.
Summaries are reconstructible and never dispatch authority.

Request parsing is delegated to frozen scientific parsers. Runtime adapters own
worker identity, lifecycle, complete template/resource checks and stage frame.
Every launch requires a separately supplied stage-specific authorization with
bounded UTC validity and a source reference to the later user direction; stage
2 creates no such launch authorization. Historical windows are not modified.

Updates, tests, failures and final limitations will be appended below. No target
or evaluator calls have been made in stage 2 at creation of this record.

## Interim engineering evidence — approximately 04:24 UTC

- Added separate journal, target, panel, evidence, frozen-entrypoint and pure
  finalization adapters. Old pinned v1 sources/configurations remain untouched.
- Archive manifest: 1,323 descriptors, including 850 SAFE and 421 private archive
  files plus 52 dependencies; 446,633 bytes. Raw SHA-256
  `837ba71a68db3d2bff7aba48b5d4ef9b11bc53e8d62f561002a6a6e60701db35`;
  identity `6318f2f1b5679940e15ae853dc40edd92d50e3787574150455797834e01a93c4`.
- The new bridge completed a full offline replay of all 1082 retained chains,
  reproducing all five stage-1 frame identities and exact missing388. Both old
  operational gates remain false. No new model call occurred.
- First replay attempt used the project's `.venv` and failed at missing Torch
  package metadata. Repeating with the existing qualified
  `C:/Users/SOGANG/anaconda3/python.exe` passed. No environment installation,
  dependency change, source change or scientific observation resulted.
- Intermediate combined subset: 168 passed, 1 skipped in 19.21 seconds. The
  skip was an unavailable Windows symlink privilege; a synthetic reparse-point
  rejection check passed. Later root-only expanded suite: 93 passed in 16.17 s.
  These are intermediate counts, not the final combined acceptance count.
- Panel adapter: 38/38 passed, including both complete synthetic 882-row frames,
  two-axis crash cases, parser/skip preservation, lifecycle/resource tampering
  and target-proof bridge. No actual tokenizer/model/GPU/private-data execution
  occurred in these synthetic tests.
- Target adapter: 22 tests passed. Strong integration separately performed all
  388 harmless fake requests through real durable storage, frozen target parser,
  actual composite verification and the actual panel consumer: 1470 total,
  chunks210/178, science220/controls168, no evaluator launch. After eliminating
  redundant full-context hashing inside already-verified read-only batches,
  this test took 91.72 seconds (previously approximately 150 seconds). Actual
  per-dispatch and public-entry full context checks remain enabled.
- Independent review found and corrected: failure-code adapter mismatch; event
  validity overstated as completeness; authorization expiry during fsync stalls;
  lifecycle verification ordering before derived recovery; completed-after-gap
  prelaunch handling; descendant output reparse paths; missing target-asset
  rehash at launch; two final product provenance joins; and stage6/7 direction
  separation. These are new engineering defects caught before real inference,
  not changes to old scientific findings.
- Current combined seven-file synthetic suite is running. New source static
  checking passes. Prospective execution freeze and final static preflight have
  not yet been reported as completed.

## Recovery limitations retained, not hidden

Valid observed event files do not prove that no event was deleted; their
completeness is explicitly unproven. Request-chain reconciliation is authoritative.
No atomicity guarantee is claimed for every Windows power/filesystem failure.
An ambiguous in-flight request is never replayed automatically. An unknown worker
PID or incomplete lifecycle publication blocks automatic recovery. Missing stops
remain missing after explicit observed-release review. A genuinely missing required
evaluator resource sample/peak proof remains `INCOMPLETE_RESOURCE_EVIDENCE`, even
when its response bytes are retained; it cannot be repaired by replacement calls.
These cases may require a separately reviewed protocol decision, not a hidden
relaxation inside a resumed experiment.

## Final candidate tests and preparation freeze

- Final combined new suite: **219 passed, 1 skipped**, 260.99 seconds; includes
  journal, evidence, target, both panels, entrypoint, pure finalizer and genuine
  388-fake-request integration. Previous combined candidate: 218 passed/1 skipped,
  235.67 seconds. The extra final regression checks target recovery's run lock.
- Frozen v1 target/panel/finalizer/continued-evaluation regression suite:
  **246 passed**, 75.94 seconds. New-source/tests Ruff: pass.
- Final lock/expiry review fixes: target CLI recovery holds the target's run lock
  and revalidates current-stage authority; evaluator recovery revalidates before
  each derived repair; both interruption reviewers revalidate just before writing
  an observed-release receipt. No code/test/protocol edits are permitted after
  the preparation freeze without a separately disclosed new preparation identity.
- Unfrozen read-only candidate replay completed in **284.125 seconds**:
  history1082, missing388, COMPLETE0/UNISSUED388/AMBIGUOUS0 in the new suffix,
  all21 original P byte hashes matched. No output namespace or launch receipt
  was created by that replay.
- Prospective preparation frozen with `execution_authorized:false`:
  `configs/natural_language_localization/pa_reentry_execution_v2.json`, 3126 bytes,
  raw SHA `5f42e6a646f16c3e66596c6c5e31a9d84024456c3c03f356fcdcf687fbec5bae`.
  Execution identity:
  `1f720cab7e9678278e52542cf0ee33e791d9b2e331c4a2b7cb1b25f64e980ab2`.
- Frozen-source verification passed. Final full preflight of this exact frozen
  factory is running, with an exclusive automatic report targeted to
  `docs/PA_STAGE2_PREFLIGHT_2026-09-07_V2.safe.json`.
- Read-only resource snapshot during final validation: C free35,098,304,512 bytes
  (~32.69 GiB), RAM available8,913,891,328 bytes, commit71,081,209,856 /
  81,953,542,144 bytes (~86.7%). RTX3070 observed366/8192MiB and33 C.
  Win32_PageFileUsage reported AllocatedBaseSize45680, CurrentUsage8573,
  PeakUsage15352. No OS/pagefile/fan/driver setting was changed. Resource pressure
  remains a caveat for the separately authorized real stage, not a new exclusion.

## Completion — 2026-09-07 04:38:59 UTC

The exact frozen factory preflight passed in247.047seconds (04:34:52–04:38:59UTC),
exclusively publishing `docs/PA_STAGE2_PREFLIGHT_2026-09-07_V2.safe.json`.
Verified1082 retained targets; new suffix COMPLETE0, UNISSUED388, AMBIGUOUS0,
repair_required0. Current stage model calls0; no launch authorization created.
Source/config pins were rechecked at the end. Disk free35,046,281,216bytes.
Observed events0 is expected before a model stage; event completeness remains
explicitly unproven, not falsely certified from an empty directory.

Stage2 is complete. Approximately55minutes elapsed. Final authority and limits:
[stage2 result](PA_STAGE2_RESULT_2026-09-07_V2.md). Stop here. Stage3 remains
unstarted/unapproved; its revised allowance is45–75minutes for missing388
generation and full1470 verification, with no automatic judge launch.
