# Stage 1 reentry repair specification — 2026-09-07

Prepared during the user-authorized reentry audit. This is a specification for
stage 2, not implemented continuation code, execution authorization, or a
scientific finding. The final stage-1 result must report actual raw verification
separately. Preserve all original contracts, code and failure records.

## Concrete evidence boundaries

Original scientific execution identity:
`d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0`.
First operational continuation:
`6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0`.

Use the original 1–872 records at their original paths. Locate the later
873–1082 records only through an explicit mapping from the first continuation's
recorded SAFE/private namespaces to their current `_run1_archived` directories.
Do not move them back, delete their abort, or treat the empty nonarchived
directory as an unused scientific budget. Record that no contemporaneous
relocation receipt was found; today's content verification cannot manufacture
that missing historical record.

Freeze a new second-continuation manifest covering exact current paths, file
sizes and hashes for every reused archived request/reply, SAFE row/dispatch/
template/cooldown, epoch lifecycle/log, rejected epoch-004 baseline, start/abort
and reservation. Bind the old 872-prefix manifest and unchanged code closures.
The stage-1 read-only path mapping is not itself this prospective manifest.

The exact missing suffix is 1083–1470, 388 targets (220 science/168 controls).
Its complete ordered plan-list digest is
`ead9c678e451700ab9d82a2286cfcd0d98a6a977ba3fa0fbdf1a6d5d36222369`;
its ordered request-ID digest is
`7d7ddd7ff5bf8ef532db2c09e0e2ca6a9988a90495cf0a757d4fa283e63ece5a`.
Keep all 1470 planned targets, 882 science rows per evaluator, the two existing
remaining process chunks, and the fixed order. No criterion, case selection,
decoding request or token cap may change to improve the observed result.

## Separate historical and future execution windows

Validate old records against the original 2026-09-05 deadline. That expired
window cannot admit new calls. Stage 2 must define a separate, explicitly bound
future launch window under the user's stage-specific direction, without
backdating or mutating old configurations. Stage 3/4/5 authorizations remain
separate; no next-stage launch is implied by completing an earlier stage.

Choose a design that can tolerate the user's pause between stages: an old
preparation time must not silently become unlimited execution authority, and
a late launch must not silently modify an expired frozen deadline. Historical
raw verification and new dispatch admission must use their correct separate
operational identities while retaining byte-identical scientific requests.

## Durable request accounting and interruption recovery

Implement the acceptance criteria in the
[stage-gated plan](PA_STAGE_GATED_CONTINUATION_PLAN_2026-09-07_V1.md): write-ahead
dispatch evidence, exclusive durable responses, verifiable completion and
automatic SAFE progress/error summaries for the target and both evaluators.
Do not require assistant turns to save progress. Allow recorded, reviewed
continuations from verified completed states, not automatic replay after abort.

Use three distinct reentry classes: verified complete, verified unissued, and
ambiguous. Retain complete first responses regardless of their content. Run
only verified unissued requests. In-flight calls without certifiable responses
are ambiguous and cannot be repeated automatically. A response written before
its final completion marker may be recovered only by validating the complete
existing chain; never generate replacement scientific observations to fill a
logging gap. An abrupt stop may leave no final stop receipt; mark that fact.

Prove all these cases with fake transport/crash tests before actual launch.
Test corrupted checkpoints, mid-publication interruption, stale lock/PID,
changed hashes, confirmed prior requests, disk-floor stops and stage-boundary
enforcement. A progress summary must be reconstructible and non-authoritative.

## Downstream interpretation and resource safeguards

The original operation and first continuation remain failed. New composite
verification must name both failures and the second continuation explicitly,
and certify completeness only when all 1470 targets are reconciled. Adapt
both evaluator entry paths and final verification to this explicit proof;
never return an old unqualified operational PASS. Keep both original judges,
eligibility rules, controls, UNKNOWN handling and scientific analysis fixed.

Disk/GPU snapshots pass existing numeric thresholds after cleanup, but memory
commit is already approximately 84.6% at the dependency snapshot. Preserve
20 GiB prelaunch and 15 GiB per-dispatch disk gates and existing cooling rules.
Record diagnostic RAM/pagefile/commit observations at agreed checkpoints;
do not alter OS settings or quietly invent post-outcome exclusion rules.

Reuse existing local weights; no download, paid inference, historical private
cohort or sealed60/60 access is in scope. Avoid raw-response duplicates.
Automatic cleanup may not delete original receipts, failed evidence or current
model dependencies. Stop and disclose unresolved provenance/resource problems.

## Stage-2 handoff criterion

Begin stage 2 only after reporting stage 1 and receiving the user's direction.
Deliver new code, synthetic failure/reentry tests, pinned archive manifest,
separate operational binding and reviewed downstream verifier design. A new
model call remains a stage-3-or-later action. Reassess stage-2 duration from the
actual stage-1 findings; implementation has not been started by this document.
