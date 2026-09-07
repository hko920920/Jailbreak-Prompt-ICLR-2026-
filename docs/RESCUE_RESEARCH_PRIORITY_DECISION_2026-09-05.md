# Research priority and ICLR-main decision plan -- 2026-09-05

## Author clarification, 11:55-12:04 UTC / 20:55-21:04 KST

The author approved a security study of jailbreak-analysis reliability, then clarified the
priority explicitly: preferably remain in jailbreak research, but making a paper is more
important. The author further specified that the target is ONE INDEPENDENT ICLR MAIN-CONFERENCE
PAPER. A workshop paper, technical report, collection of disconnected pilots or documentation
completion is not an equivalent success condition. Acceptance cannot be guaranteed.

The current primary candidate is jailbreak/prompt-injection analysis reliability with a
consequential, measurable security outcome. Leaving jailbreak/security remains a fallback if
the evidence and novelty assessment justify it; privacy minimization was a proposed candidate,
not a completed experiment or an irrevocably chosen paper topic. The earlier statement that
privacy minimization was excluded is superseded by this paper-first, security-preferred order.

No new model experiment is running. Manuscript/PDF work remains inactive until the research
evidence justifies it and the author's manuscript-stop instruction is revisited explicitly.
Existing D3/C1N failures and V2 judge-control failure remain failed. Old A/B cohorts remain
unopened; neither this planning document nor the earlier broad rescue instruction silently
opens them, changes historical gates, authorizes paid services or supplies missing reviewers.

## Existing literature records are the starting point

Root re-read the following existing documents during this clarification, rather than assuming
the project had no related-work audit:

- [LITERATURE_CLAIM_MATRIX.md](LITERATURE_CLAIM_MATRIX.md): direct overlaps, comparison scope,
  forbidden claims, and September 4/5 refreshes.
- [NOVELTY_AUDIT.md](NOVELTY_AUDIT.md): explanation, localization and excision collisions.
- [LITERATURE_HUMAN_FREE_ADDENDUM.md](LITERATURE_HUMAN_FREE_ADDENDUM.md): program provenance is
  not causal ground truth; automatic evaluation is not independent of human-labelled origins.
- [PAPER_SCOPE_DECISION_V2.md](PAPER_SCOPE_DECISION_V2.md): original standalone-paper question.
- [RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md](RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md):
  exact-family, grouping-null and measurement limitations.
- [ICLR2027_REVIEWER_CALIBRATED_TEN_STEP_PLAN_2026-09-04_V1.md](ICLR2027_REVIEWER_CALIBRATED_TEN_STEP_PLAN_2026-09-04_V1.md):
  prior scientific gates and rejected paths, preserved as history.

Their older CONDITIONAL PASS statements do not establish that the latest narrower rescue is
ICLR-main sufficient. Important established territory includes critical-token localization,
minimal explanations, removal-dependent explanations, compositional attacks and subset search.
New work must demonstrate consequential errors and useful correction under fair comparisons,
not present enumeration, hashes, one-path incompleteness or metadata packaging as a new theorem.
Only claim-specific missing or newly relevant literature needs additional source verification.

## Current evidence strength

The V4 prospective result is real and independently replayed: 65/128 primary opportunities on
64 fresh harmless problems, with 60 formatting failures and five wrong values. It supports a
narrow output-contract transfer phenomenon, not actual harmful-jailbreak prevalence. See the
[completed V4 report](RESCUE_V4_PROSPECTIVE_TRANSFER_RESULT_2026-09-05.md).

An additional read-only agent audit of existing D3 safe records found a concrete candidate for
a decision-level retrospective check. There are 12 fixed instances: nine COMPLETE ddmin outputs,
two UNCERTIFIED and one UNAVAILABLE. If a downstream policy wrongly assumes that all larger
removals inherit a COMPLETE repair's safety, it produces 17 superset decisions, one contradicted
by a recorded harmful outcome. Six decisions were unqueried in their respective stored search
traces; one of those six is wrong under the old panel, five agree. This is NOT a failed ddmin
guarantee: ddmin did not promise monotonicity or global necessity. The underlying nonmonotonicity
was already in D3; a new standalone replay artifact has not yet been implemented.

The concrete source is instance-results line 2, mask 77 -> 95. Source 77 has actual required
passing capability controls and three safe observations per operator. Destination 95 has an
OMIT seed-47 SUBSTANTIVE_HARMFUL_ASSISTANCE observation (outcome-observations line 1095).
Destination capability preservation was not tested. This is a finite automatic-panel-relative
counterexample, not fresh human-grounded evidence or proof of practical deployment frequency.

The same independent audit found 44 opposite-operator response disagreements, but NONE has
actually required source capability controls: the stored passed=true flag is vacuous when
required=false. Therefore those 44 must NOT be called control-qualified repaired prompts.
This constraint prevents promoting apparently larger counts into a stronger security claim.

Measurement remains a real bottleneck: the new local GuidedEval judge failed its empty-domain
control. The old Qwen3Guard/JailMeter panel has public qualification evidence but not independent
human truth on these interventions. Repeating its calls does not fix that absence. C1N has only
180 baseline/attacked outputs, not an intervention lattice. Qualified two-rater review of all
180 responses would require 360 ratings plus adjudication and actual reviewer availability;
no reviewer calendar can be assumed.

## Proposed work packages and stop rules

These are planning estimates, NOT a frozen experimental protocol, claim of adequate statistical
power, automatic authorization for every listed branch, or promise of acceptance. The author
will receive the exact scope, call ceiling and runtime estimate before any new experiment.

| Package | Concrete deliverable / continuation requirement | Working estimate |
|---|---|---|
| 1. ICLR-level claim and closest-work audit | One coherent question, a claim/evidence/baseline map, and an explicit difference from closest methods; reject a merely known input-sensitivity story | 2-4 hours |
| 2. Decision-level security evidence audit | Checked safe-only reconstruction of concrete wrong conclusions, fixed denominators, matched controls and UNKNOWN handling; distinguish method guarantees from hypothetical misuse | 2-4 hours |
| 3. Measurement feasibility and bounded pilot | Freeze a defensible security endpoint and test the full preselected small frame; determine whether the result survives controls and is not only JSON formatting | 6-12 hours including implementation; exact inference budget set before launch |
| First direction decision | Continue only if novelty, measurable security consequence and credible evaluation all survive; otherwise change the claim/topic, not an observed gate | Within 24-48 hours of focused work |
| 4. Main study and independent replication | New attack/problem clusters across distinct model/attack conditions, complete accounting, pre-output analysis and untouched replication; no selective positive expansion | 3-5 days if local compute and endpoint are viable |
| 5. Useful correction and reviewer challenges | Compare to simple direct rechecking and matched-budget baselines; quantify wrong-security-decision reduction against cost/coverage/utility; test simplest alternative explanation | 2-3 days, partly overlapping package 4 |
| 6. Manuscript, only after scientific sufficiency and renewed manuscript authority | One standalone ICLR-main narrative backed by completed results, limitations and reproducible artifacts | 3-5 days after the evidence decision; currently NOT started |

Approximate overall planning range: 5-10 days for an evidence package IF the first route passes;
then 3-5 days for a submission-quality manuscript after the writing boundary is lifted. Thus
roughly 8-15 days is a conditional estimate, not a guaranteed paper-production date. A failed
pilot, required human validation, new hardware/provider resources or a substantive topic change
requires a new estimate rather than silently extending the old one.

Compute sanity check: 64 cases x 2 models x 2 operators x 3 finite repeats x 32 five-unit masks
= 24,576 target generations BEFORE controls and screening. Seven-unit tables would instead
require 98,304 before those extras. This illustrates why the five-unit V4 runtime cannot simply
be extrapolated to a full jailbreak paper. Actual token lengths, decoding, grouping validity,
target coverage and controls must be fixed and timed in the pilot. These numbers are not a
chosen sample size or a new admitted experiment.

## Security-preserving alternative measurement, not an executed pivot

The official [Tensor Trust project](https://tensortrust.ai/paper/) and
[released dataset](https://github.com/HumanCompatibleAI/tensor-trust-data) provide public
prompt-extraction/hijacking benchmarks. They are a candidate for security outcomes such as
synthetic access-code disclosure or unauthorized approval, where an explicit observable endpoint
could avoid a free-form harmfulness judge. The scoring implementation, model framing, data split,
controls, licensing and closest forensic work still need exact verification before execution.
The root has only browsed public documentation; no game interaction, attack optimization, target
call or dataset experiment occurred. Prompt injection/access control is security research but
must not be silently described as general harmful-content jailbreak evaluation. Existing
PromptLocate/WebSentinel overlap in the project's literature matrix remains relevant.

## Honest viability judgement

Current evidence alone: insufficient for a defensible claim of ICLR-main readiness; significance,
external validity and local measurement validity are unresolved. A single independent ICLR-main
paper remains the target, not an achieved status. A meaningful, replicated security consequence
and a useful audit/correction beyond simple rechecking would strengthen that route. No numeric
acceptance probability is justified by this pilot, and no lower venue is substituted for success.

All direction changes, failed gates and actual call counts remain in the record. This planning
turn made zero model/judge calls, zero original private-text reads, zero A/B accesses and zero
manuscript/PDF edits. It does not overwrite the historical records it cites.
