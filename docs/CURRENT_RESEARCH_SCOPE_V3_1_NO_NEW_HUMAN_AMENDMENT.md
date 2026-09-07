# Current Research Scope v3.1: No-New-Human Amendment

Date: 2026-09-03 (Asia/Seoul)

Status: **CURRENT EVIDENCE CONTRACT / TOPIC UNCHANGED / EMPIRICAL AUTHORIZATION CONDITIONAL**

This amendment updates only the human-evidence clauses of
[`CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md`](CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md).
The research question, immutable-payload boundary, finite intervention
vocabulary, all-minimal enumeration target, neutralizer and seed robustness,
full-response judgment, and capability controls remain unchanged. Where the v3
document requires a newly recruited independent human audit, this amendment
supersedes that requirement for the current study.

## 1. Current decision

The primary study will use **no newly collected human annotations**. This is a
scope decision, not a claim that automatic judges are equivalent to people or
that human evidence is generally unnecessary.

The admissible evidence chain is:

1. qualify each exact evaluator implementation operationally;
2. fix a conservative cross-family decision rule before evaluating outcomes;
3. develop only on public records carrying previously collected human labels;
4. retain `ABSTAIN` whenever the heterogeneous evaluators do not support the
   same decision;
5. pass frozen aggregate, source, fold, and behavior-group gates on development;
6. pass a separately frozen, one-shot behavior-disjoint primary held-out test;
7. only then authorize the jailbreak-intervention and topology experiments.

Thus the correct paper description is **no new human annotation in this
study**, not **human-free ground truth**.

## 2. What does not count as human evidence

- Multiple prompts, roles, or personas run on one language model are rubric
  sensitivity checks only.
- An LLM claiming to act as an expert annotator is still an automatic judge.
- Repeated samples from one judge are not independent annotators.
- Agreement between two automatic evaluators does not establish universal or
  human-equivalent validity.

The historical persona experiments may be reported only as motivation for
abstention and cross-family evaluation. They cannot resolve disagreements or
replace a human audit.

## 3. Required automatic-evaluation safeguards

The no-new-human route remains defensible only while all of the following are
preserved:

- public, provenance-audited human-labelled benchmarks are the external
  reference;
- development and primary held-out behavior groups remain disjoint;
- held-out per-record labels stay sealed until both model axes and the decision
  rule are immutable;
- the primary rule is a conservative intersection, not a post-outcome majority
  vote or selector search;
- abstention, coverage, class-conditional errors, Wilson bounds, source-level
  results, fold stability, and behavior-cluster bootstrap intervals are all
  reported;
- evaluator outputs, exact model revisions, prompts, decoding settings, hashes,
  parser failures, and exclusions remain auditable;
- topology conclusions are accompanied by evaluator-specific and reasonable
  decision-rule sensitivity analyses;
- capability-confounded, malformed, truncated, and unresolved cases cannot be
  silently counted as safe recovery.

E0G-4 is the current full-development gate for these safeguards. Its execution
is evaluator qualification only; even a pass is not evidence that the proposed
minimal-recovery phenomenon exists.

## 4. Claim boundary if the gates pass

Without a new in-domain human audit, the paper may claim that outcomes are
certified by a predeclared, externally benchmarked, conservative automatic
panel under the reported coverage and error bounds. It may not claim:

- human-equivalent ground truth;
- universal safety or jailbreak detection;
- validity outside the evaluated models, attack families, harms, languages, or
  response distributions;
- that abstained cases are safe, harmful, or missing at random;
- that automatic agreement alone proves in-domain construct validity.

The v3 one-sentence formulation is therefore amended to end with:

> ...across neutralizers, sampling seeds, full-response judgments, capability
> controls, and a predeclared abstaining evaluator panel qualified on disjoint
> public human-labelled benchmarks.

This wording replaces `independent human audit` only for the present
no-new-human study.

## 5. Stop and contingency rules

The automatic route does not authorize topology execution if full development
or the one-shot primary held-out qualification fails its frozen mandatory
gates. A failed gate may not be repaired by weakening thresholds after labels
are opened.

A newly recruited human audit becomes a separately governed contingency, not a
post-hoc patch, if any of the following occurs:

- the automatic panel fails or is too narrow for the intended claims;
- causally pivotal topology conclusions are unstable across admitted evaluator
  variants;
- abstention prevents adequate attack-family or harm-category coverage;
- a stronger in-domain construct-validity claim is desired.

Any such audit requires a new prospective protocol, annotator qualifications,
blinding, sampling rules, adjudication, and analysis plan fixed before labels
are collected. The unused historical human-review packet remains archived and
outside the current critical path.

## 6. Immediate authorization state

- E0G-4 full development: **PASS**.
- E0G-5 one-shot primary held-out qualification: **PASS, independently reconstructed**.
- T0 no-new-human topology-transition contract: **PASS and frozen**.
- P3 response outcomes: **sealed**.
- Jailbreak topology outcomes: **not authorized**.
- Paper-valid empirical claim: **none yet**.

The next decision is mechanical: run D1 by applying the unchanged E0G-5 panel to
all 36 frozen P3 responses, then apply the frozen eight-pair routing rule once.
No target response is regenerated, no historical WildGuard result selects a
case, and no human or persona label is added. Exact topology execution begins
only if D1's predeclared gate authorizes it.
