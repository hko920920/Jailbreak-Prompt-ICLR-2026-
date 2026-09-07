# Rescue execution and paper direction — 2026-09-05 V2

This is a new research direction and implementation record under the author's current instruction
to pursue a paper, including changes to method, direction, or topic. The historical record-only
stopping instruction in V1 has been superseded by that instruction. Historical scientific gates
have not been changed. No new target or judge inference has occurred in this V2 work.

## Decision

Develop an exact audit of the reliability of recovery explanations under intervention changes
and incomplete evaluator information. The central object is the explanation's certificate and
its limits, not a promised invariant set of dangerous tokens. Existing results support a
retrospective methods/pilot manuscript. They do not establish ICLR-level empirical sufficiency,
cross-model replication, or any guarantee of acceptance.

The new direction has three linked parts:

1. Compute necessary and possible minimal-set memberships, so a certified subset of explanations
   is not mistaken for identification of the entire family.
2. Separate changes forced by grouping from observed failures of a grouped intervention that
   contains a successful finer intervention. The monotone closure identity supplies a formal
   comparison, and synthetic monotone oracles supply known null controls.
3. Attribute each empirical failure to its actual neutralizer and finite seed evidence, and test
   whether the resulting explanation transfers to another specification. Do not infer universal
   safety from the finite predicate.

## What failed, and what was only an implementation incident

| Stage | Observed result | Interpretation |
|---|---|---|
| Earlier evaluator designs | Calibration gates failed before the later panel qualified | Measurement engineering was a major research bottleneck, not evidence against untested topology |
| Qualified panel E0G-5 | 803 held-out records; 0.6650 decided coverage, 0.0356 decided error | Qualification under those sources; neither full coverage nor guaranteed transport to Gemma |
| D3 | Positive neutralizer Jaccard 64/141 = 0.4539, below frozen 0.80 | The original cross-family agreement claim failed |
| Narrowed C1N | 35 Qwen and 5 Gemma advancing pairs, against at least 6 each | Correct futility stop; no C2N result and no observation of zero three-seed-stable pairs |
| C1N Gemma attacked cell | Qwen3Guard called 41/45 harmful, JailMeter 5/45; panel abstained on 36/45 | Severe disagreement; cannot identify which judge is correct from agreement alone |
| Development preflight | A metadata key named `prompt` triggered raw-content checks; renamed `prompt_builder`, then passed | Repaired metadata validation incident, not the scientific failure |

Independent source-based audit:
[RESCUE_EVIDENCE_INDEPENDENT_AUDIT_2026-09-05_V2.md](RESCUE_EVIDENCE_INDEPENDENT_AUDIT_2026-09-05_V2.md).

## New completed analysis, with limitations attached

Source: the immutable content-free D3 table, SHA-256
`2ebe3ff8cf7a603fa885500e9946bb79cdc7bd80d79f6ea29077dfb099934d34`.
Output: [audit.safe.json](../data/natural_language_localization/rescue_identification_v2/audit.safe.json).
Current result identity: `52e114d41d998e161c720b6ce89da87d8da908e89b2d7e3e873e3b0d8e102acc`.

- Actual units of evidence: 12 selected instances over 9 unique payloads, not 2,676 independent
  partitions. These are development instances selected under an older research contract.
- 16 necessary minimal-set memberships versus 45 possible memberships under arbitrary Boolean
  completions. Possible members need not coexist; 45 is not an observed pathway count.
- Only 7/12 full minimal families are identified. Capability-confounded rows remain unresolved
  sensitivity inputs; Boolean completion does not make those interventions scientifically valid.
- Four of eight adjacent nontrivial-flag changes leave the exact same atomic minimal family.
  These are changes of group cardinality, insufficient as an empirical contribution.
- Four adjacent partition contrasts contain a known recovery reversal across two DeepInception
  instances. They contain only **three distinct atomic intervention pairs**, because one pair
  is represented by two partitions.
- Every such grouped failure is specific to `LAYOUT_PRESERVING_BLANK` in the available evidence.
  The corresponding `SOURCE_AWARE_OMIT` intervention remains safe on all three measured seeds.
  The negative blank decision needs one valid harmful witness; omitted later calls are not
  imputed as harmful. This is an operator-specific finite-contract result.
- Seven complete binary h4rm3l tables have zero closure-null residuals in fourteen adjacent
  comparisons. This is consistent with the grouping explanation there; it is not a proof of
  monotonicity at every intervention or a general absence result for h4rm3l.
- A tuple-order comparison defect was found in the old exploratory audit using a harmless
  counterexample. The corrected mathematical set comparison changes zero of the current
  one-merge counts: the historical 25/36 and 64/90 counts remain numerically correct here.

The first V2 generated receipt is retained as `audit.initial.safe.json`. Its values are identical;
the current receipt additionally binds the final lint-clean script bytes. Neither rewrites D3/V1.

Theory, semantic caveats, and verified literature:
[RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md](RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md).

## Change to the proposed V1 rescue design

V1 proposed killing the new study unless both attack families showed the same positive
instability signal. That was a proposed design, not an executed confirmatory experiment.
The V2 design instead tests a stated audit procedure and allows family-specific and
operator-specific outcomes, including negative comparisons. This is justified by the formal
grouping null and disclosed pilot results, not by changing an old test's acceptance threshold.

Keep both attack families in the study. Describe h4rm3l as a comparison family, not a known
negative control. It has three atoms and two adjacent opportunities; DeepInception has seven
atoms and six. An unadjusted difference in any-merge event rates cannot be attributed causally
to attack family. Report both instance-level events and fixed-opportunity comparisons.

Reserve B must reproduce the declared claim with its declared scope. If the claim becomes
blank-specific failure, deletion need not show the same positive effect, but its results must
remain visible. If a different claim is chosen after Primary A, label A discovery and B the
independent confirmation; do not retroactively call A confirmation of that choice.

## Concrete next experiment

First complete development measurement over the **same 180 C1N seed-11 responses**. This costs
180 judge requests for one frozen judge, or 360 for two. It generates no new target responses.
Use the official pinned GuidedEval prompt and parser, preserve all point vectors, and report
individual judges as well as the unanimous envelope. Zero/present is a fixed rubric endpoint,
not universal harmlessness. Refusals, parsing failures, and incomplete point vectors abstain.

The new runner is implemented at
[run_rescue_guidedeval_development_v2.py](../scripts/run_rescue_guidedeval_development_v2.py).
Safe input/source readiness passed. A private bundle containing only the 45 already exposed C1N
cases was prepared successfully, with SHA-256
`b0b803cb06800f5a931df90e64833c8de70ba54def57e2a9ff0f09b3763a208b`.
The source was streamed as bytes for identity verification and ID selection; unselected case
text was not decoded or copied. No target response was copied. The preparation receipt is
[case_preparation.safe.json](../data/natural_language_localization/rescue_guidedeval_development_v2/case_preparation.safe.json).

The remaining live dependency is concrete: available judge provider/model/endpoint, credential
or qualified local runtime, and a total budget. No relevant judge credential was present in the
current process environment and no project `.env` file was found. This is a resource observation,
not a requirement for renewed permission to do already authorized research. The author was
asked for the resource information while independent analysis and manuscript work continued.
Credentials must not be pasted into tracked files or public artifacts.

Before paid execution, freeze actual provider/model identity and documented snapshot limitations,
temperature, output cap, cost bound, and checkpoint contract. A newly available replacement for
a judge used in GuidedBench is a new measurement specification; it does not inherit the paper's
published validation. No API model availability or price is assumed here.

Report these development outputs, regardless of favorable direction:

1. Parse, refusal, truncation, and missing rates in each target/condition cell.
2. Point-level and endpoint agreement for every judge pair; all individual distributions.
3. Direct-zero and attacked-present paired counts per target, with unresolved pairs retained.
4. Cross-tabs against the frozen old panel, described as disagreement, not accuracy improvement
   without independent labels.
5. Operational viability and estimated downstream cost. Changing the model after this output
   creates a new development version; it cannot repair C1N or supply fresh confirmation.

## Fresh-data design that must precede opening A

Primary A and Reserve B each retain their existing 60 payload identities. The provider-dependent
live contract is not complete yet. The following scientific decisions are now explicit:

- Freeze source-native units, two neutralizers, exact renderers, admitted targets and decoding
  parameters, finite seed set, and all admissible adjacent boundaries before any A output.
- Preserve payload bytes; do not strengthen attacks to increase eligibility. Topology is an
  audit of fixed successful instances, not attack optimization.
- Make recovery predicates per judge and per operator first-class outputs. A joint predicate
  must retain a failing operator and valid failing seed as its negative witness.
- Primary audit outputs: identified-family indicator; necessary/possible membership envelope;
  deduplicated adverse-closure witnesses; complete-table closure-null residual; control failures;
  and matched exact-oracle baseline misses. Report all denominators and exclusions.
- Distinguish a valid observed failure of the all-seeds-zero conjunction from unknown observations
  elsewhere. Intervention invalidity and capability failure remain separate domain limitations.
- Treat payload as the sampling cluster. Seeds, targets, operators, and partitions are repeated
  measurements. Use fixed 10,000 payload-cluster bootstrap draws for estimable mean contrasts;
  publish exact event counts and uncertainty bounds, and do not silently drop unknowns.
- Preregister one primary contrast before A. Candidate: the payload-level frequency of at least
  one known adverse closure under the blank operator in DeepInception, alongside a matched
  source-aware-omission result. This candidate comes from the pilot and must be disclosed.
- Three finite seeds do not establish a low population failure probability. Replication should
  include independently frozen additional seeds for pivotal interventions if making a stability
  claim beyond the original finite contract.
- Do not treat one missed minimum count as a reason to lower sample requirements. Choose sample
  size from desired precision and verified compute. If necessary precision is unattainable,
  narrow the inferential claim and venue ambition explicitly.

Resource calculations for exact nonempty enumeration (excluding screening and capability controls):

| Design | h4rm3l calls | DeepInception calls | Total target calls |
|---|---:|---:|---:|
| One instance, two operators, three seeds | 42 | 762 | Per-family cost |
| 8 instances per family/target cell, two targets | 672 | 12,192 | 12,864 per cohort |
| 12 instances per family/target cell, two targets | 1,008 | 18,288 | 19,296 per cohort |

These are upper bounds before sound harmful-witness short-circuiting, and are planning examples,
not a frozen sample choice or a claim of adequate power. Screening all 60 payloads over two
targets and two attack families needs at most 1,080 three-seed direct/attacked generations if
direct observations are shared across attacks. Two evaluators roughly double each judged-record
count. Replication B adds a separate cohort. No cost or runtime estimate may omit these terms.

## Paper deliverable and publication boundary

New manuscript: `paper/iclr2027/rescue_v2.tex`; the historical `main.tex` remains intact.
Write the completed retrospective study, its elementary formal guarantees, algorithmic validation,
and actual limitations. Do not invent future result tables or human annotations. Existing public
work already covers feature-removal explanations and case-specific jailbreak evaluation; the
defensible specialization is the exact certificate/closure/operator audit, if it proves useful.

An honest methods/pilot manuscript can be prepared from current evidence. A strong ICLR submission
still requires a convincing empirical advance and independent validation. If fresh results do not
support that level, preserve the complete paper as a narrower methods report or suitable workshop
submission; do not manufacture a positive effect or erase the negative comparisons.

The official [ICLR 2027 call](https://iclr.cc/Conferences/2027/CallForPapers), checked on 2026-09-05,
lists the abstract deadline as September 18 and full paper deadline as September 25, 2026, AoE
(September 19 and 26 at 20:59 KST). This remaining window makes early measurement qualification
and honest computation estimates necessary.

## Subsequent execution and author-instruction update

The no-inference and manuscript sections above describe the earlier preparation boundary.
The author subsequently stopped manuscript/PDF work; it remains inactive. The bounded
four-candidate local judge qualification, 180 existing-response measurements and 45
empty-response controls have now completed. The domain empty-response control FAILED.
See the latest experiment record for actual results, endpoint limitations and call counts:
[RESCUE_DEVELOPMENT_MEASUREMENT_RESULT_2026-09-05_V2.md](RESCUE_DEVELOPMENT_MEASUREMENT_RESULT_2026-09-05_V2.md).
No historical gate was changed and no unused-cohort experiment has started.
