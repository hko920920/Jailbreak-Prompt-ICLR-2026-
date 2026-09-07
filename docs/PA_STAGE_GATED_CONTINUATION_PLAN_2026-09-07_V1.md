# P/A research: stage-gated continuation plan — 2026-09-07

Status: STAGES 1–4 COMPLETE; STAGE5 AUTHORIZED/RUNNING after fresh user direction.
No experiment launch is authorized by this document. This is an operational breakdown of the existing original-P/A
route, not a replacement scientific hypothesis or a revival of failed gates.

## User-directed execution cadence

The user requested an ordered list, a time estimate before each stage, a result
report after each stage, and continuation only when they explicitly say to go
to the next stage. Report the plan first. Do not bundle later stages into an
unattended run. Ordinary in-scope fixes belong within an approved stage; a
material change to scientific rules, data access or call budget requires a
new concrete proposal. Report meaningful progress and promptly report delays.

Each stage report must state: actual completed work, observed evidence versus
interpretation, checks/failures and unresolved points, elapsed time, record
paths, and the next stage's scope and revised ETA. Never report transport
eligibility as a safety result or development success as paper acceptance.

## Required interruption recovery and automatic records

The user additionally requires durable automatic recording and the ability to
continue after interruption. These are mandatory stage-2 acceptance criteria,
not a claim that the existing failed-continuation runner already supports them.
Stage 1 is complete; stage 2 was authorized by the user's subsequent "진행".
That direction covered implementation and synthetic verification only. Stages3
and4 have since been authorized separately and completed. Stage5 still requires
its own fresh user direction before JailMeter inference.

- Cover target generation, Qwen evaluation and JailMeter evaluation separately.
  Persist the execution identity, request ID, pre-dispatch intent, received
  response, receipt identity and completion state for every attempted request.
  Preserve original private artifacts and all earlier failures; never overwrite
  responses, reinterpret UNKNOWN as success, or duplicate raw data for logging.
- Automatically emit compact SAFE progress summaries at completion boundaries:
  actual completed/remaining/unknown/ambiguous counts, stage and epoch, last
  verified request, timestamps, elapsed time and storage/GPU measurements.
  Include diagnostic RAM/pagefile observations at defined resource checkpoints.
  Summaries are rebuildable indexes, not substitutes for verified raw receipts.
- Keep an append-only event/error record and an automatically generated stage
  completion or interruption summary. Record resources and exact stop reason
  when graceful shutdown is possible. If the process/PC terminates before it can
  write a stop record, detect that on the next audit; never fabricate one.
  These records must be written by the runner, without relying on an assistant
  turn being available. Retain them even if the chat disconnects or its usage
  limit is reached; continued execution itself is not guaranteed.
- On reentry, reconcile durable records against the frozen full request plan.
  Reuse verified completed requests; run only verified unissued requests.
  A request dispatched without a certifiable response is AMBIGUOUS and must
  not be automatically repeated. Recover an already-written response only
  when its complete identity/receipt chain can be verified. Partial writes,
  changed hashes or unexplained files must produce an explicit incomplete or
  blocked state, never a guessed successful checkpoint.
- Use crash-resistant exclusive/atomic publication as appropriate, and verify
  saved state before admitting subsequent work. Do not claim universal exactly-
  once execution across network/process failures: the no-duplicate guarantee
  comes from refusing to automatically replay ambiguous dispatches.
- Test interruptions before dispatch, in flight, after response receipt and
  during publication, as well as corrupted/partial progress files, stale locks,
  already-completed requests, disk-floor stops, and missing graceful-stop
  records. Use synthetic/fake execution for stage-2 tests. Verify both reuse
  and refusal behavior, and confirm no automatic transition into the next stage.
- A continuation requires the user's current-stage direction and a separately
  valid execution window/binding. A checkpoint does not override a frozen abort,
  expired deadline, sealed-data boundary or the user's instruction to stop.
  Interrupted sessions must be recoverable from project records without asking
  the user to reconstruct the chat history.

If satisfying this requirement changes the stage-2 estimate after stage 1,
report the revised scope and estimate before beginning stage 2. Automated
execution records do not replace the assistant's scientific interpretation
and end-of-stage report.

## Verified starting point

- Exposed development screen: 45 P, final 21 STABLE_PAIR, 2 NOT_STABLE,
  22 UNRESOLVED across seeds 11/23/47 with the fixed two-judge rules.
- Original topology SAFE target rows: ordinals 1–872, 536 science/336 controls.
- Archived continuation SAFE target rows: 873–1082, 126 science/84 controls.
- SAFE accounting: 1082 unique ordinals, no gaps through 1082 and no duplicate
  request IDs. This audit did not re-certify all raw receipts.
- Total retained targets: 662 science/420 controls; remaining 388 = 220 science
  plus 168 controls. The complete plan remains 1470 targets and an 882-row
  science frame for each evaluator. Actual evaluator calls depend on the
  existing eligibility rules, with every skip recorded separately.
- Retained rows mark 22 scientific and 84 control outputs TRUNCATED_UNKNOWN.
  These are technical states, not observed safety or control-success labels.
- Original stop: DISK_FREE_SPACE_BELOW_15_GIB. Second stop after ordinal 1082:
  CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB. Its next-epoch snapshot was
  18,858,278,912 free bytes at 2026-09-05T21:37:02.613757+00:00.
- The second attempt remains in the `_run1_archived` namespace. The unarchived
  continuation directory was empty when inspected. Archive provenance needs
  explicit reconciliation before reuse; an empty directory is not permission
  to replay already completed requests.
- No topology panel/final-result artifacts or running Python/llama runtime
  were observed. The screen's completed judges are not topology evaluations.
- Four obsolete weights have been deleted, with about 32.8 GiB free afterward.
  See [storage execution record](LOCAL_STORAGE_CLEANUP_EXECUTION_2026-09-07.json).

## Ordered stages and provisional elapsed-time allowances

Estimates exclude waiting for user direction. They are planning allowances,
not promises. Revise them from actual observations at each stage boundary.

| Stage | Scope and required deliverable | Provisional time |
| --- | --- | --- |
| 1 | COMPLETE: all 1082 NEW raw chains verified, exact missing388 reconciled, dependencies passed; [result and limitations](PA_STAGE1_REENTRY_RESULT_2026-09-07_V1.md). No new model calls. | Original allowance 30–60 min; automatic successful audit 4 min 33 sec plus preparation/independent checks/records |
| 2 | COMPLETE: separate frozen continuation, raw archive pins, automatic durable records/recovery, full target/two-judge adapters and explicit downstream acceptance. New tests219pass/1platformskip; old regressions246pass. Frozen actual-data preflight passed; no inference. [Result and limits](PA_STAGE2_RESULT_2026-09-07_V2.md). | Approximately55min actual; allowance was2–4h |
| 3 | COMPLETE: missing388 generated, retained1082 preserved, full1470 verified; independent SAFE consistency passed. New technical UNKNOWN4science/0controls; full-frame26science/84controls. Both new chunks have matching worker-release records; prior failures preserved. No judges. [Result](PA_STAGE3_RESULT_2026-09-07_V2.md). | About41min actual including final checks/records; initial allowance45–75min |
| 4 | COMPLETE: Qwen856 actual responses+26 fixed-rule skips, full882 verified; additional parser/output-limit UNKNOWN0, controls0. Independent SAFE/epoch/resource checks passed. Single-axis labels only, no combined scientific conclusion. [Result](PA_STAGE4_RESULT_2026-09-07_V2.md). | About32min actual including checks/records; allowance20–40min |
| 5 | AUTHORIZED/RUNNING: JailMeter on the same full882 science frame under fixed evaluator/skip rules; preserve all disagreements and unknowns. [Live record](PA_STAGE5_EXECUTION_RECORD_2026-09-07_V2.md). | Initially3–4h; revised4–5h total at07:01UTC from actual timing |
| 6 | Verify full target/panel/control joins and generate the complete per-P, per-mask, operator/seed tables with both primary and control-qualified interpretations. Publish verification last. | 30–60 min |
| 7 | Evaluate the strongest P-dependent ordering-reversal claim: shared-order null, same-witness repetition across all six tables, minimum label-change distance, UNKNOWN sensitivity, control confounding and epoch/time confounding. Report positive, negative or unidentified findings. | 1–2 h |
| 8 | Match those actual findings against the recorded nearest-work matrix, refresh only directly relevant literature as needed, and report whether the original claim merits independent confirmation or needs narrowing/stopping. | 1–2 h |

The original stages 1–8 allowance was roughly 8.5–15 hours; after stage-1
findings, the remaining stages 2–8 allowance is roughly 8.5–15 hours of active work;
generation/evaluation alone is roughly 4–6 hours. Stage 1 can reveal a repair
that exceeds stage 2's allowance; report that instead of silently overrunning.

After stage2 completion, the current remaining stages3–8 allowance is roughly
6.5–11hours of active work, excluding waits for user directions and any newly
encountered blockers. Stage3 was revised to45–75minutes for the added verified
reentry/durable-write overhead. These remain estimates, not preauthorized runs.

After stage3 completion, stages4–8 remain approximately6–10hours of active
work before any conditional independent confirmation. Stage4 is next,20–40min,
but is not approved by completion of stage3 or by this planning estimate.

After separately authorized stage4 completion, stages5–8 remain approximately
5.5–9hours of active work. Stage5/JailMeter is next,3–4h, and awaits fresh user
direction. Current Qwen results do not preauthorize that run or scientific analysis.

## Conditional downstream work

9. If stage 8 warrants it, design and preregister independent confirmation and
   any second-target replication with a defensible claim, source boundary,
   population, budget and stopping rules. Planning allowance: 2–4 hours.
   Existing sealed Primary A / Reserve B cohorts remain unopened. Neither
   this list nor approval of an earlier stage authorizes accessing them.
10. Execute the approved confirmation stages, then assess the independent
    ICLR main-paper claim, reproducibility artifact and manuscript. Execution
    and writing estimates cannot be responsibly fixed before the new design
    and development result. Report them before each future stage. No PDF or
    manuscript work is scheduled before the evidence warrants it.

## Why direct restart is not the next operation

The previous contract's dispatch deadline was 2026-09-05 22:55:47 UTC. Its
code explicitly rejects a previously aborted/attempted continuation. Preserve
those rules and historical failures. A separate, disclosed second continuation
must bind retained evidence and a new user-approved execution window; never
erase aborts, relabel failures as passes or rely on an emptied namespace.

Scientific P bytes, A ownership, operators, seeds, target/judge settings,
controls, full population, missing-data treatment and scientific criteria stay
as specified in the existing protocol unless a separately justified prospective
change is reviewed. No paid calls, new model downloads or sealed-data access
are part of stages 1–8. Existing 20 GiB prelaunch / 15 GiB dispatch disk gates
remain; any new RAM/pagefile observer is diagnostic, not a post-outcome rule
change. Automatic deletion of experiment evidence is not authorized.

## Timing basis and existing references

- Original 872 topology responses spanned about 78 minutes; the next 210 took
  about 17 minutes. Applying these rates to 388 gives about 31–35 minutes
  before startup/cooling/verification allowance; later masks may differ.
- NEW screen Qwen means for seeds 11/23/47 were approximately 0.66/0.69/0.78
  inference seconds across 85/61/51 calls. 882 rows imply about 10–12 minutes
  of inference alone, not end-to-end topology runtime.
- Uninterrupted NEW screen JailMeter seed 23 took 14.14 minutes for 61 calls;
  seed 47 took 11.78 minutes for 51 calls. Scaling gives about 3.4 hours for
  882 calls. Seed 11's interrupted elapsed time was not used for throughput.
- Actual answer lengths, eligibility, cooling, memory pressure and failures
  may alter these estimates. No topology judge throughput has been measured.

References: [original topology protocol](PA_LLAMA_TOPOLOGY_EXECUTION_PROTOCOL_2026-09-05_V1.md),
[first continuation protocol](PA_LLAMA_TOPOLOGY_TARGET_CONTINUATION_PROTOCOL_2026-09-06_V1.md),
[readiness checklist](PA_LLAMA_TOPOLOGY_PROSPECTIVE_READINESS_2026-09-05_V1.md),
[contribution matrix](PA_ORIGINAL_CONTRIBUTION_EVIDENCE_MATRIX_2026-09-05_V1.md),
and [historical ten-step plan](ICLR2027_REVIEWER_CALIBRATED_TEN_STEP_PLAN_2026-09-04_V1.md).
The historical D3/C1N failures remain unchanged; this plan is not their pass.
