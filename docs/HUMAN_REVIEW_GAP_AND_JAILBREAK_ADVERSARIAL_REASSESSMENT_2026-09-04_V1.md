# Human-Review Gap and Jailbreak Adversarial Reassessment — 2026-09-04 V1

Date: 2026-09-04 (Asia/Seoul)  
Evidence state at review: **T0 complete; D1/P3 panel outcomes and every topology outcome unopened**  
Decision: **KEEP THE TOPIC AND THE TEN-STEP STRUCTURE, BUT ADD EARLY CONTRIBUTION-KILLER GATES**

## 1. Bottom line

The current topic remains worth testing. The bounded literature refresh did not identify prior work
that already combines all of the following in one object: direct intervention on predeclared
attack-added input-text units, byte-identical retention of the explicit harmful payload, enumeration
of every strict-subset-minimal robust recovery set, multiple text neutralizers, repeated sampling,
full-response judgment, and capability-confound handling.

That is a defensible gap, not yet a paper contribution. The central empirical proposition remains
unobserved. The paper becomes credible only if fresh experiments show recurring non-singleton or
multiple-pathway structure that simpler singleton, leave-one-out, or one-path methods miss. If the
results reduce to one obvious refusal-suppression sentence, whole-wrapper destruction, evaluator
artifacts, or one model/family, the correct decision is to stop or narrow rather than complete a
paper around the protocol.

The current ten-step execution structure therefore survives. Two changes are mandatory before
expensive confirmation:

1. compute the simplest-explanation and one-path baselines directly from the exact D2/D3 truth
   tables, not after the full confirmatory run;
2. apply a human-reviewer-style contribution-killer gate before allocating confirmation compute.

No numerical acceptance probability or simulated-review score is authorized by this audit.

## 2. Why previous AI review signals were misleading

### 2.1 PP-Mark

The initial ICML-era AI review was a weak reject and roughly matched the human panel center, but
the later revision loop converted the same irreducible trade-off into an acceptance story.

| Evidence | Recorded judgment | What mattered |
|---|---:|---|
| ICML human reviews | `4,2,3,3`, mean `3.00`, reject | exact-image fragility, signature baseline, cost, missing robust-and-provable mode |
| NeurIPS virtual forecast | mean `4.47`, modal `5` | circuit clarification and dual-mode framing were treated as sufficient repair |
| NeurIPS human reviews | `4,3,3`, mean `3.33` | the same exact-hash, cost, baseline, generality, and deployment trade-offs remained significance problems |

The AI reviews did name exact-pixel fragility, white-box score-mode weakness, proof overhead, and
the signature baseline. The failure was not issue discovery. It was **issue weighting**: once the
manuscript called the two modes complementary and disclosed their limitations, the AI review
treated the tension as managed. Human reviewers asked whether any mode jointly delivered the
claimed practical value. Clarification could not manufacture that joint property.

Sources:

- `C:/Users/SOGANG/Documents/PP-Mark-v0.4/PP-Mark/docs/stanford_ai_review_v1_pre_revision.md`;
- `C:/Users/SOGANG/Documents/PP-Mark-v0.4/PP-Mark/docs/ai_review_v4_post_circuit_fix.md`;
- `C:/Users/SOGANG/Documents/PP-Mark-v0.4/PP-Mark/docs/icml_reviews_full.md`;
- `C:/Users/SOGANG/Documents/NeurIPS_2026_PP-Mark_actual_reviews_raw_2026-07-24.md`.

### 2.2 The Noise Paradox

| Evidence | Recorded judgment | What mattered |
|---|---:|---|
| NeurIPS virtual forecast | mean `4.66`, modal `5` | coherent paradox narrative, repeated explicit acceptance recommendations |
| NeurIPS human reviews | `3,1,3`, mean `2.33` | all three independently asked whether deterministic decision-only A0d already explained the result |
| Post-review source/experiment audit | original defense story failed; controlled recovery only | implementation/label mismatches, missing matched baselines, adverse score-leakage evidence |

The most damaging question was elementary: what does Bucket-Memo add if A0d already obtains the
headline security result? That question was not answered before the long experiment. Later work
showed why this mattered. Route A stopped with balanced exploratory `0/32` persistent successes.
Route B passed its utility gate, but the complete B2-S0 sentinel produced Tree-Ring forgery
`2/5` versus `0/5` and improved the attack margin in all ten Tree-Ring matched pairs. The original
catastrophic threshold did not fire, yet the continuous direction supported the reviewer's leakage
concern. The defensible scientific story moved from a secure defense toward a utility--security
paradox.

Sources:

- `C:/Users/SOGANG/Documents/NeurIPS_2026_Noise_Paradox_actual_reviews_raw_2026-07-24.md`;
- `C:/Users/SOGANG/Documents/NOISE_PARADOX_HISTORICAL_CAPSULE_2026-08-23/key_records/NOISE_PARADOX_ITEM6_CONTRIBUTION_KILLER_STATUS.md`;
- `C:/Users/SOGANG/Documents/NOISE_PARADOX_HISTORICAL_CAPSULE_2026-08-23/key_records/NOISE_PARADOX_POST_B2S0_STRATEGIC_HOLD_MEMO_2026-07-28.md`.

### 2.3 AAAI audit and compiler/route papers

The virtual means `4.60` and `4.69` are untested forecasts, not calibration evidence. The
source-first reaudit opened because of the PP-Mark/Noise gap and found that both polished PDFs had
received strong positive AI signals while source execution exposed major contradictions. The audit
paper was rated serious/major and the compiler paper critical/major before repair.

The user's distinction between the two current topics is reasonable:

- **Audit/reporting route:** the research object is legible: given frozen evidence for a completed
  run and a requested privacy sentence, decide exactly which wording is licensed or block it. Its
  factor-two adjacency consequence and same-run/different-query outputs give a concrete decision.
  Its risk is limited technical novelty, finite-registry scope, author-designed conformance cases,
  and honest-evidence assumptions.
- **Compiler/route-registration route:** after correctly disclaiming new mechanisms, accountants,
  privacy proofs, generic provenance, and arbitrary-plugin guarantees, the residual contribution is
  a route-label registration predicate plus finite authored splice/conformance tests. It may still
  be publishable as a systems result, but a human reviewer can plausibly call it an engineering
  wrapper around established owner-level DP components. Its topic-level variance is therefore
  materially higher than the AI `4.69` forecast suggests.

This comparison is a calibration lesson, not evidence for or against the jailbreak paper.

Sources:

- `C:/Users/SOGANG/Documents/AAAI27_7p_compressed/AAAI27_DP_PAPERS_SOURCE_FIRST_REAUDIT_MASTER_2026-07-24.md`;
- `C:/Users/SOGANG/Documents/AAAI27_7p_compressed/01_audit_reporting_paper/main_audit_aaai27_v24_candidate.tex`;
- `C:/Users/SOGANG/Documents/AAAI27_7p_compressed/02_algorithm_compiler_paper/main_aaai27_v42_candidate.tex`.

## 3. Recurring failure pattern to prevent

The historical records support seven operational lessons.

1. **Correlated AI reviews are one instrument, not independent reviewers.** Rephrasing prompts,
   roles, personas, or review order does not create an empirical panel.
2. **Naming a limitation does not make it nonfatal.** Ask whether it removes the claimed utility,
   novelty, or significance.
3. **The simplest competing explanation must be tested first.** A0d and the bare signature were
   not optional baselines; they challenged the reason the proposed method existed.
4. **A persuasive narrative can coexist with a false or unsupported technical center.** Source,
   execution, and negative tests outrank prose coherence.
5. **Rebuttal-resolvable and paper-resolvable are different.** A reviewer can accept a clarification
   while keeping the score because the empirical or design trade-off remains.
6. **Harsh specialist tails must be represented.** A score-1/high-confidence review is possible even
   when several generalist reviews like the paper.
7. **Do not forecast acceptance from generated prose.** Future internal reviews must produce a
   reject case, claim-evidence map, and stop decision, not a pseudo-calibrated venue score.

## 4. Bounded literature refresh through 2026-09-04

No exact collision was found in the refreshed primary-source search. This is not proof of priority.
The nearest ownership boundaries remain:

| Work | Already occupied | Residual distinction, if the experiment succeeds |
|---|---|---|
| [LOCA](https://arxiv.org/abs/2605.00123) | minimal local causal refusal restoration via internal representation changes | editable input text and complete minimal-set family |
| [Beyond “I'm Sorry, I Can't”](https://arxiv.org/abs/2509.09708) | minimal interacting/redundant SAE feature sets | direct payload-preserving text interventions |
| [Token Highlighter](https://ojs.aaai.org/index.php/AAAI/article/view/34943) | gradient token ranking and soft embedding suppression | exact typed-unit interaction and all-minimal completeness |
| [Mask-GCG](https://arxiv.org/abs/2509.06350) | suffix-token necessity/redundancy and optimization-time compression | frozen successful-prompt recovery topology rather than attack optimization |
| [Causal Analyst](https://www.ndss-symposium.org/ndss-paper/a-causal-perspective-for-enhancing-jailbreak-attack-and-defense/) | population-level learned graph over human-readable attack features | direct per-instance interventions and strict-subset certificates |
| [Adversarial Déjà Vu](https://openreview.net/forum?id=WFo8P1gQBh) | sparse reusable attack-skill compositions across 32 attack papers | whether displayed units are behaviorally necessary in one fixed instance |
| [Breaking Refusal in the First Half](https://arxiv.org/abs/2607.14147) | localized response-site account of a one-line prefill jailbreak | input-side complete recovery family; also a warning that an obvious local cause can trivialize a study |
| [TriageFuzz](https://arxiv.org/abs/2603.23269) | token-sensitive query-efficient attack search | post-hoc exact recovery rather than attack generation |

Two accepted ICLR comparators illustrate the evidence bar. [GuidedBench](https://openreview.net/forum?id=ZVg8y3ibyM)
supports an evaluation/measurement contribution with a systematic audit of 37 studies and a
case-specific benchmark. Adversarial Déjà Vu supports a compositional jailbreak claim with 1,494
original--mutated prompt pairs from 32 attack papers. The present project cannot match that breadth
while also exhaustively enumerating subsets; it must earn significance through exactness,
counterfactual validity, recurring interactions/pathways, and a clear demonstration that cheaper
explanations miss them.

## 5. Human-reviewer-style assessment of the current jailbreak topic

### 5.1 What is genuinely stronger than the historical projects

- T0 fixed the outcome map, full denominator, units, neutralizers, seeds, controls, minimality,
  abstention, and stop gates before opening P3 outcomes.
- The harmful payload is immutable and excluded from editable units, blocking the easiest fake
  recovery.
- Every subset is evaluated without a monotonicity assumption, so pure interactions, redundant
  paths, and nonmonotone cases can be observed rather than inferred from a ranking.
- Two text interventions, repeated seeds, strict full-response judgments, and matched capability
  controls directly address deletion artifacts.
- Development and confirmation are disjoint and failure cannot be repaired by changing thresholds.

These are real improvements. They reduce researcher degrees of freedom; they do not make the
phenomenon important automatically.

### 5.2 Strongest plausible rejection case today

A skeptical reviewer can currently say:

> The paper exhaustively ablates three or seven hand-defined blocks in old quantized models and two
> semantic jailbreak templates. Exhaustive search over such a small authored vocabulary is brute
> force, not a new algorithm. Any recovery may be caused by deleting an obvious refusal-suppression
> instruction or damaging prompt fluency. The outcome judge was validated out of domain and is weak
> on its exposed JailbreakBench stress set. Without recurrent baseline-missing topology across fresh
> models, attacks, payloads, neutralizers, and seeds, the work is a careful case study rather than an
> ICLR-level contribution.

Nothing in T0 refutes this. D2--C3 must refute it empirically.

### 5.3 Risk register

| Risk | Current severity | What would close or bound it |
|---|---|---|
| obvious singleton/whole-wrapper explanation | fatal if dominant | D2/D3 exact truth tables plus named-unit and one-path baseline audit |
| brute-force enumeration has no scientific payoff | fatal to method/significance claim | repeated interactions or alternative minimal paths missed by cheaper baselines |
| unit vocabulary is authored and scale-dependent | high | source-derived provenance, frozen coarsening sensitivity, vocabulary-relative claims |
| neutralization destroys syntax/conditioning | high | both omit and layout-blank agreement, validity checks, matched capabilities, exclusions |
| evaluator distribution shift | high, bounded but unresolved | per-axis/rule sensitivity, abstention, error-bound disclosure; optional prospective human audit only if later feasible |
| only two Q4 models and two semantic attacks | high for broad claims | explicit Q4 semantic scope; later GPU optimized/canonical extension is reinforcement, not a substitute for local controls |
| exponential cost | medium | disclose finite-vocabulary exactness and query cost; evaluate one-path approximations against the exact oracle |
| “causal mechanism” overclaim | high | call results behavioral text-intervention topology, not model-internal mechanism or enabling sufficiency |

### 5.4 No-new-human decision

Omitting a new annotation study is scientifically defensible only for the narrow claim that outcomes
are certified by the predeclared selective automatic panel under its reported coverage and external
error bounds. It is not equivalent to human safety judgment. E0G5 decided 66.5% of its primary
held-out set at 3.56% decided error, but split-vote records had 22.39% decided error and the exposed
JailbreakBench stress set had 47.22% coverage and 10.29% decided error. A reviewer can reasonably
question transfer to edited topology responses.

Therefore:

- a new human annotation study is not a core prerequisite for D1--D3;
- all central conclusions must survive both evaluator axes and reasonable frozen rule sensitivity;
- the paper must say automatic-panel-defined recovery, not human-confirmed recovery;
- a small independent human **cold read of the paper** is strongly useful before submission and is
  distinct from recruiting annotators for the experiment;
- if pivotal topology results change under evaluator variants, the no-new-human route stops or
  triggers a separate prospective audit rather than post-hoc hand labeling.

## 6. Final decision

Status: **CONDITIONAL GO, HIGH EMPIRICAL RISK, NO PAPER YET.**

Keep fixed:

- immutable harmful payload;
- source-derived finite attack-unit vocabulary;
- all strict-subset-minimal recovery sets rather than one importance ranking/path;
- two neutralizers, common seeds, full responses, capability controls, abstention;
- fresh development/confirmation and exact denominators;
- Q4/local scope as the core feasible route, with GPU work only as later reinforcement.

Change now, before D1:

- move the simplest-explanation and required one-unit/one-path baseline audit into D2 and D3;
- require an early contribution-killer decision before C1/C2;
- replace future acceptance-score forecasts with reject-case and claim-evidence audits;
- keep the evaluator limitation visible as a construct boundary, not a footnote.

Step 1 remains valid and complete. Step 2 remains the next operation, but it should start only after
the reviewer-calibration amendment and ten-step map are frozen.

## 7. Amendment identity verification

The pre-D1 amendment parsed successfully and matched the exact frozen T0 parent.

- amendment SHA-256: `2cfe5cb274b2da80bf5d7d7537574bd4f250aad5298b6549877f1b0b3a27f5c6`;
- observed and declared T0 SHA-256:
  `d395d5cf971e65030bca1fc6646460744951375db34cba78e1ab773633b30ce3`;
- parent status match: pass;
- unchanged-contract entries: 10;
- D2 early contribution-killer checks: 8;
- D3 pre-confirmation checks: 5;
- P3 panel, stable-pair, and topology outcomes observed during this audit: none.

Safe validation artifact:
[`preflight.safe.json`](../data/natural_language_localization/reviewer_calibration_pre_d1_amendment_v1/preflight.safe.json).
