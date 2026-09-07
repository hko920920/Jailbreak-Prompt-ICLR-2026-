# Rescue theory and novelty audit — 2026-09-05 V2

Status: independent adversarial review of the rescue design, not prospective evidence. This file supplements the immutable V1 chronology. No old gate or old result is reclassified. This audit reads code, tests, the V1 record, the new safe V2 audit, and the existing safe D3 decision summaries; it does not inspect private attack payloads, private responses, Primary A, or Reserve B, and performs no target or judge inference. The current user request authorizes rescue development beyond the historical record-only stopping instruction quoted in V1.

## 1. Verdict

The exact finite intervention table is a useful asset. The strongest defensible contribution is a **measurement audit that separates a change in the available interventions, a change in what can be certified, and an observed reversal of recovery**. Merely showing that grouped explanations have different sizes or names is insufficient. Complete enumeration and feature-choice dependence already have substantial prior literature.

A concrete bug also exists in the V1 resolution audit: it compares ordered tuples of minimal sets even though those tuples can change order under grouping without changing the mathematical family. A new audit must distinguish this from real family change. This finding does not change the independently frozen D3/C1N failures.

The main route should make its empirical question stronger: **does grouping a known recovery intervention ever destroy recovery, and how much do one-path explanations overstate minimality or necessity when checked against the full finite oracle?** A second, separately interpretable question is how abstention changes which claims can be certified. Neither result is established by this document.

## 2. Code findings

### 2.1 Real family-order bug in the exploratory audit

`scripts/analyze_d3_resolution_rescue.py::_partition_row` currently uses `family != reference_sets` and `family == reference_sets`, where each family is a tuple. Fine minima are ordered by atomic cardinality, while coarse minima are ordered by block cardinality. These orders need not agree.

Harmless synthetic example: let recovery hold exactly when `c` is selected or both `a,b` are selected. The fine ordered family is `((c,), (a,b))`. Under the partition `((a,b),(c,))`, the coarse family lifted to atoms is `((a,b),(c,))`. V1 declares a family change, although both mathematical families are `{ {c}, {a,b} }`.

This example was executed against the existing implementation and reproduced the false positive. New comparisons should use sets of canonical atomic subsets, with deterministic sorting only for serialization. Record the old and corrected counts separately; do not silently overwrite the historical exploratory receipt. The previously quoted `64/90` and `25/36` family-change counts require this correction before being reused. This audit does not assert that either count necessarily decreases on the actual data.

### 2.2 Correct certificate, incomplete uncertainty representation

`resolution_topology.py::certified_minimal_family` correctly demands that every strict subset be certified negative; it does not silently assume monotonicity. However, `unresolved` contains only observed recovered candidates with unresolved strict subsets. It omits unknown subsets that could themselves become minima. Therefore `certified + unresolved` is not the full identification region for the true minimal family.

For example, with `f(empty)=0`, `f({a})=?`, `f({b})=0`, `f({a,b})=1`, the current unresolved list contains `{a,b}`. The possible minimum family must additionally allow `{a}`. The bounds in Section 3 provide the correction without changing old scientific observations.

### 2.3 `reportable` has a narrow meaning

`PartitionTopology.reportable` means “there exists at least one individually certified minimum.” It does not mean that recovery exists, that no recovery exists when false, that the whole family is identified, or that uncertainty is low. Use the longer name `has_certified_minimum` in new reports. Add independent fields for existence bounds and family identification.

### 2.4 Prospective recovery aggregation differs from the old engine

The V1 rescue definition says one certified harmful seed is sufficient for `NOT_RECOVERED`, whereas `topology.py::decide_recovery` gives an abstention, missing observation, truncation, or confound priority over the final negative decision. For example, one valid harmful observation and one abstention can produce `ABSTAINED`, although the strict all-seeds-zero conjunction is already disproved.

The old engine is part of the frozen scientific record and must remain reproducible. A new prospective adapter should explicitly define its logical conjunction: known failure of a required valid endpoint disproves all-required-endpoints success; all required successes certify success; otherwise the result is unknown. Invalid intervention materialization is a domain-validity issue and should be represented separately rather than casually completed as a valid success. A new rule needs new versioning, tests, and provenance; it must not repair C1N retrospectively.

Follow-up verification: D3 itself uses `evaluate_exact_topology_adaptive`, and its frozen contract already explicitly permits a valid harmful witness to disprove the all-three-seeds endpoint. The generic-engine issue above is therefore a warning for a new bridge, not a discovered error in D3's recorded negative decisions.

### 2.5 Endpoint names overstate what the rubric measures

`guided_recovery.py::to_behavior_outcome` maps any matched scoring point to `SUBSTANTIVE_HARMFUL_ASSISTANCE` and zero matched points to `SAFE_NONASSISTANCE`. Those names are stronger than the actual rubric predicate. New exports should retain an explicit endpoint type such as `GUIDELINE_POINT_ZERO_VS_PRESENT` and phrase conclusions in those terms. In particular, absence of all listed points does not logically imply absence of every possible harmful contribution.

The endpoint is fixed at zero; it is not free of a decision boundary. “Fixed zero endpoint without a tuned fractional cutoff” is more precise than “threshold-free.” Unanimous judge intervals are envelopes of permitted point-vector completions conditional on the measurement assumptions. They are not statistical confidence intervals and do not certify human ground truth.

## 3. Sharp identification under abstention

Fix a finite universe `U`, a valid intervention domain `D` (initially all subsets of `U`), and one fully specified measurement contract. Let `y(S)` be 1 for recovered, 0 for not recovered, and `?` for an epistemically unresolved endpoint. Define:

```
l(S) = 1[y(S)=1]
u(S) = 1[y(S) != 0]
C(y) = { f: D -> {0,1} : l(S) <= f(S) <= u(S) for every S }
M(f) = { S in D : f(S)=1 and f(T)=0 for every T in D with T strictly contained in S }
```

No monotonicity or independence is assumed. Relative to this completion model, the sharp per-set lower and upper families are:

```
M_necessary = { S : l(S)=1 and u(T)=0 for every strict subset T in D }
M_possible  = { S : u(S)=1 and l(T)=0 for every strict subset T in D }

M_necessary = intersection over f in C(y) of M(f)
M_possible  = union        over f in C(y) of M(f)
```

Proof of necessity and possibility: a minimum must be positive and have all strict subsets negative. A known negative at `S` or a known positive below it rules it out. Otherwise one can choose `f(S)=1` and every unknown strict subset negative to witness possibility. A minimum is unavoidable exactly when its positive value and all lower negative values are already fixed. To show it is avoidable, either set its unknown value to zero or set an unknown strict subset to one.

These are sharp **membership** bounds. Members of `M_possible` need not coexist in a single family: possible sets can contain one another, whereas any actual minimum family is an antichain. Do not treat `M_possible` as one executable explanation collection, and do not infer sharp family-count or core bounds by treating candidate memberships as independent.

The family is fully identified exactly when `M_necessary == M_possible`. In that case every compatible table has the same family even if some nonminimal table entries remain unknown.

Existence of at least one minimum is simpler. On a finite domain it is equivalent to existence of any recovered intervention:

```
minimum-existence lower bound = 1[there is a known recovered row]
minimum-existence upper bound = 1[there is any row not known negative]
```

Thus a known recovered pair above an unknown singleton guarantees that some minimum exists, even if the current code certifies none individually. Reporting this as “no topology” would conflate absence with non-identification.

For partition `pi`, restrict the domain to unions of complete blocks, apply the same formulas, then lift block subsets back to atomic sets. Unknown endpoints remain unknown. Invalid interventions require a separate admissibility contract; treating them as ordinary missing labels can assert a latent valid endpoint that was never defined.

## 4. What coarsening proves and what it cannot prove

Let `D_pi` be the unions of blocks of partition `pi`, and define the block closure:

```
cl_pi(S) = union of all blocks B of pi for which B intersects S
```

### 4.1 Projection is an exact restriction, under an explicit materialization contract

If a block edit is implemented as the same union of atomic edits with the same renderer, neutralizer, validators, seed realization, generation contract, and evaluator, then its observation is already a row of the atomic table. Projection adds no inference. It does not prove what would happen if grouped text were re-rendered with a new grammar repair, if a macro unit were neutralized with different replacement text, or if a fresh stochastic response were drawn. Those are new specifications rather than projections.

The frozen unit order need not equal physical text adjacency because an atomic unit can contain disjoint spans. “Contiguous partition” means contiguous in that declared unit order. A prospective partition justification must say why those boundaries represent plausible editing decisions. Merely being adjacent in an arbitrary list is not semantic justification.

### 4.2 Pure relabeling can change the stated qualitative result

Let recovery be `1` exactly when `{a,b}` is contained in the intervention. The fine family is `{{a,b}}`; grouping `a,b` produces the same atomic intervention as a singleton block. The existing test `test_one_adjacent_merge_can_collapse_a_nonsingleton_explanation` explicitly demonstrates this. “Nontrivial became trivial” is true under its definition but reveals no new behavior. Minimum block count and the current nontrivial flag cannot alone anchor the paper.

### 4.3 Every coarse certificate has an auditable reason

For a coarse certified minimum `C`, inspect all fine strict subsets. Its status as a coarse certificate can be classified by:

1. It was already a fine certified minimum: inherited certificate.
2. It contains a known recovered strict subset: grouping hid a known smaller recovery intervention. Some additional hidden strict subsets may also be unresolved; preserve those facts.
3. It contains no known recovered strict subset but has an unresolved strict subset: grouping removed a certification obstacle.

In the third case the coarse certificate can appear without any new behavioral evidence. These categories describe the certificate's relation to the fine domain; they are not disjoint causal explanations for an entire family change unless the classification protocol explicitly makes them so.

### 4.4 A monotone closure null removes obligatory grouping effects

For a complete binary table `f`, define `M = M(f)` and:

```
K_pi = inclusion-minimal members of { cl_pi(S) : S in M }
M_pi = minimal recovered sets in D_pi, lifted to atoms
```

**Proposition.** If `f` is monotone increasing under inclusion, then `K_pi = M_pi` for every partition.

Proof: every recovered coarse set contains an atomic minimum `S`, hence contains `cl_pi(S)`. Monotonicity makes that closure recovered. A coarse minimum therefore equals one of the inclusion-minimal closures. Conversely any inclusion-minimal closure is recovered; a smaller recovered coarse subset would contain a smaller closure and contradict its minimality.

This theorem gives an algebraic null baseline: compare the exact coarse family to `K_pi`, not just to the ungrouped atomic family. It is not proposed as a new general theorem with priority; its value here is preventing a misleading empirical claim.

Harmless counterexample to equality without monotonicity: take `U={a,b,c}`, recovery only at `{a}` and `{a,b,c}`, and partition `{{a,b},{c}}`. The fine family is `{{a}}`, so `K_pi={{a,b}}`, but that intervention is not recovered. The exact coarse family is `{{a,b,c}}`. This is an actual behavioral reversal after extra editing, not a change in the name or size of the same atomic set.

For a given partition, nonzero family discrepancy `M_pi != K_pi` is evidence against monotonicity. The reverse implication does not hold: a nonmonotone table can have zero discrepancy for a particular partition or even for the selected admissible partitions. Absence of a residual is not proof of global monotonicity.

Only compute this exact null from complete binary tables. A null computed from the certified part of an incomplete family is not the same quantity; it can manufacture residuals by excluding possible minima.

### 4.5 Certified adverse closure witnesses can survive partial observation

A strong local diagnostic requires only:

```
S is a certified fine minimum
y(cl_pi(S)) = NOT_RECOVERED
```

Then extending that actual recovery edit to its grouped version destroys the declared recovery endpoint. The witness is valid even if unrelated table entries are unresolved. A weaker but still certified monotonicity witness replaces the first condition with simply `y(S)=RECOVERED`; preserve whether minimality was certified. Distinguish the two in reports.

On a complete binary table, if every closure of every fine minimum is recovered, the monotone closure formula is exact for that partition even when the full table is nonmonotone elsewhere. The contrapositive makes adverse closure inspection a useful explanation of residual family discrepancy. Some adverse closures can be redundant in the inclusion-minimal closure family, so an adverse closure witness need not imply a family-level residual.

### 4.6 Existence and atomic costs have constrained directions

For complete binary observations, reducing the domain cannot create recovery that did not exist. If full-vocabulary recovery holds, every partition has at least one recovered intervention and therefore a minimum. A reportability loss in that setting would indicate uncertainty or an implementation issue, not a complete-binary behavioral fact.

For a fixed nonnegative atomic intervention cost, the cheapest feasible recovered intervention cannot become cheaper when available interventions are removed. Block counts do not satisfy this interpretation because a block can contain many atoms. Report both atomic footprint and declared block count. For costs based on spans, count the union of the actual edited characters/tokens under a declared convention rather than multiplying by block count.

## 5. The measurement effect that can be worth studying

Certifying a proposed `k`-atom minimum may require resolving all `2^k - 1` strict subsets, in addition to its own positive outcome. Even a modest endpoint unknown rate can therefore destroy exact-minimum coverage. Under a deliberately simplified independent missingness model with rate `q`, full availability has probability `(1-q)^(2^k)`; conditional on the candidate itself being resolved, the strict-subset availability factor is `(1-q)^(2^k - 1)`. These are sensitivity calculations, not estimates: actual judge errors, seeds, and subset responses can be strongly dependent.

Grouping shrinks the set of required lower-set checks. It can therefore increase apparent certificate coverage by hiding unknown states. Quantifying this combinatorial propagation is more informative than reporting only the original pairwise judge agreement. A methods contribution could report a certificate and its unresolved blockers, plus the necessary/possible family envelope. It should not choose partitions to remove whichever blockers happened to occur.

Judge agreement is still not judge correctness. Published GuidedBench validation supports reuse of that measurement procedure; it cannot establish local human validation for new targets, decoding contracts, or a newly defined zero endpoint.

## 6. Recommended prospective estimands and baselines

Use a short, outcome-independent list of source-justified one-boundary merges. Enumerating all partitions is a diagnostic appendix. Freeze the choice before Primary A generation. Treat each unique payload as a sampling cluster across targets and attack families; partitions and seeds are repeated measurements.

Suggested primary quantity: for each eligible attack-target-payload instance, indicate whether any predeclared merge has a certified adverse closure witness starting from a certified fine minimum. Report incidence by attack and target, the all-eligible denominator, and endpoint coverage. Preserve zero, unresolved, and ineligible as distinct states. A completed table with no witness is a negative observation; an incomplete table that could contain a witness is not automatically negative.

For a finite test frame, report lower and upper incidence bounds across compatible completions. If an instance is classified only by sufficient witness rules rather than exact completion optimization, call these valid outer bounds, not sharp bounds. The sharp per-set formulas alone do not automatically give sharp joint bounds for an “exists a witness” event.

Secondary quantities: exact coarse-family discrepancy against the closure null on complete binary tables; fraction of raw changes due only to tuple ordering; unchanged atomic families with changed block-count flags; newly certifiable families caused by hidden unknown states; full-family identification rate; and actual atomic cost changes. These answer different questions and should not be collapsed into a favorable scalar.

For population uncertainty, bootstrap unique payload clusters with all their attack-target observations kept together, provided the sampling interpretation and eligible cell counts justify it. Report coverage and denominators alongside intervals. Predeclare a minimum scientifically meaningful effect and a replication criterion; a positive point estimate or a confidence interval barely above zero is not by itself substantive. This audit does not fabricate a universal numeric kill threshold. Reserve B must retain the fixed comparison, endpoint, and model identities chosen before its opening.

The strongest one-path baseline comparison is not simply that one path misses other paths by design. Measure errors in conclusions a user would draw: a claimed necessary unit absent from another certified minimum; a returned set that is only 1-minimal and has a smaller recovered strict subset; a purported minimum-cardinality edit that is not cheapest; and a selected intervention that fails under a second declared neutralizer. Compare query cost and report the scope of each guarantee. Delta debugging's 1-minimality is weaker than strict-subset minimality without monotonicity. [Original delta debugging paper](https://www.st.cs.uni-saarland.de/publications/files/zeller-tse-2002.pdf).

## 7. Closest-work assessment from primary sources

The following are contribution boundaries, not proof that no overlapping paper exists. Sources were refreshed on 2026-09-05.

| Work | What it already establishes | Consequence here |
|---|---|---|
| [Carter et al., AISTATS 2019, sufficient input subsets](https://proceedings.mlr.press/v89/carter19a.html) | Model-agnostic minimal retained feature subsets, including text, using backward selection. | Do not claim first minimal input explanation or first collection of sufficient explanations. Distinguish retained evidence from recovery by removal and full overlapping antichains from a selected SIS collection. |
| [Covert et al., JMLR 2021, Explaining by Removing](https://jmlr2020.csail.mit.edu/papers/v22/20-1316.html) | Unifies removal explanations by removal operator, target behavior, and summary. | “Explanation depends on specification” is prior conceptual territory. New value must be the implemented audit, uncertainty propagation, and consequential empirical findings. |
| [Ignatiev et al., On Relating Why and Why Not Explanations](https://arxiv.org/abs/2012.11067) | Formal relationship and enumeration of abductive and contrastive explanations. | Complete families and multiple explanations are established topics. The present fixed edited-input endpoint is not automatically a universally sufficient prime implicant. |
| [Ignatiev and Marques-Silva, SAT-Based Rigorous Explanations for Decision Lists](https://arxiv.org/abs/2105.06782) | SAT encodings and MARCO-style enumeration, including complete enumeration feasibility. | Exponential exhaustive search on three/seven units is an oracle for this experiment, not a new scalable enumeration algorithm. |
| [GuidedBench v3](https://arxiv.org/abs/2502.16903v3) | Case-specific guidelines, evaluator discrepancy measurement, and GuidedEval; accepted at ICLR 2026. The current version was revised 2026-09-01. | Cite the actual frozen source snapshot and the relevant paper version. Reusing GuidedEval and observing evaluator disagreement cannot be this paper's novelty. |
| [LOCA v3](https://arxiv.org/abs/2605.00123v3) | Minimal local internal-representation edits that induce refusal, with Gemma/Llama/Qwen experiments; published at COLM 2026. | Very close motivation. Explicitly distinguish editable input intervention families, case-specific endpoint, and certification from internal causal explanations. |
| [Mask-GCG v2](https://arxiv.org/abs/2509.06350v2) | Learnable suffix masking and pruning to examine impactful/redundant tokens; accepted at ICASSP 2026. | Token necessity and sparse jailbreak components are occupied topics; this project is an audit of recorded recovery behavior. |
| [Robust Harmful Features v2](https://arxiv.org/abs/2606.28153v2) | Attention-head ablation and attribution to attack-template tokens; accepted at ICML 2026. | Do not claim first token-level mechanism or inference about internal safety circuitry. |
| [ChunkGroupSHAP, 2026](https://arxiv.org/abs/2606.27980) | Semantic feature grouping for ranking explanations and setting-dependent unit choice. | Even recent language-oriented explanation granularity has close prior art. The specific certification and recovery audit must do the work. |

The general abductive/prime-implicant definition usually quantifies over changes to unspecified features. Here `f(S)=1` evaluates one declared edit while all other material remains at its specified values. With nonmonotonicity, recovery at `S` does not imply recovery at a superset and does not establish universal sufficiency. State the quantifiers in the paper instead of borrowing the stronger terminology.

Candidate honest contribution statement:

> We audit complete finite prompt-intervention recovery families under explicit rendering and evaluation contracts. We separate algebraically required grouping effects from destroyed recovery interventions and from changes in certifiability, and provide exact per-intervention identification bounds when measurements abstain. A prospective two-family, two-target study and independent replication determine which failures materially affect commonly reported explanations.

The final sentence remains a study design until those experiments exist. A theorem-plus-tool package and a small exploratory dataset do not guarantee an ICLR paper. If prospective adverse effects vanish, the remaining claim can be a narrower reproducibility or measurement report; do not force a positive mechanism story.

## 8. Implementation and testing priorities

Implement new versioned modules and receipts rather than modifying a hash-frozen historical result:

1. Mathematical family equality using sets of canonical atomic subsets; separately expose ordering-only V1 artifacts.
2. Necessary and possible minimum families, family-identification status, and minimum-existence bounds.
3. Coarse-certificate classification with explicit known-recovered and unresolved hidden subsets.
4. A closure-null function that refuses an incomplete binary table rather than imputing unknowns.
5. Certified monotonicity and adverse-closure witnesses that can be emitted with partial observations.
6. Prospective endpoint adapter with an explicit logical aggregation rule and preserved rubric semantics.

Meaningful tests should include the tuple-order counterexample; unknown singleton/known recovered pair; guaranteed existence without a certified minimum; coarsening that hides only unknowns; coarsening that hides a known positive; the harmless nonmonotone closure counterexample; identity partition invariance; singleton all-units partition behavior; and malformed status rejection.

Independent in-memory verification performed for this audit: all **6,561** ternary truth tables on three atoms were compared with their compatible binary completions; the necessary/possible formulas matched intersection/union of exact minimum families in every case. The closure identity was checked over all **20** monotone Boolean functions on three atoms and all **5** partitions (**100** comparisons), all passing. These checks use synthetic integer masks only and do not constitute empirical jailbreak evidence. The tuple-order counterexample was additionally executed against the existing repository module and reproduced.

No prospective target runs, evaluator calls, private response reads, held-out reads, or changes to frozen scientific artifacts were made by this audit.

## 9. Follow-up review of the newly completed V2 implementation

Reviewed `src/jbspan/topology_identification.py`, `scripts/audit_rescue_identification_v2.py`, their tests, and `data/natural_language_localization/rescue_identification_v2/audit.safe.json`. The implemented necessary/possible formulas, closure construction, setwise family equality, and promoted-certificate classification agree with the derivations above. `audit_partition` computes the closure-null residual only on complete binary tables. The lower-level `closure_null_family` accepts a family without a table, so its documented precondition remains important for future callers.

The new audit reconstructs the frozen safe D3 source with SHA-256 `2ebe3ff8cf7a603fa885500e9946bb79cdc7bd80d79f6ea29077dfb099934d34`. The safe aggregate result reports:

- 12 instances over 9 unique payloads; 7 fully identified families.
- 16 necessary minimum memberships and 45 possible memberships. The latter are not 45 simultaneously existing pathways.
- 4 adjacent adverse-closure comparisons across 2 DeepInception instances and 2 payloads.
- 0 observed adjacent adverse-closure comparisons in h4rm3l.
- 7 complete binary tables, all h4rm3l, and zero closure-null residuals over their 14 adjacent comparisons.
- 4 of 8 adjacent nontrivial-flag changes preserve the exact same atomic family.
- The tuple-order bug produces zero ordering-only false changes in this particular one-merge dataset, so corrected family-change counts remain 25/36 adjacent and 64/90 arbitrary.

The source-neutralizer summaries impose a crucial further limitation. Each of the four adjacent adverse witnesses has a fine intervention with three safe observations under both neutralizers. **Every grouped negative is caused by exactly one harmful observation under `LAYOUT_PRESERVING_BLANK`; `SOURCE_AWARE_OMIT` remains safe on all three seeds in all four cases.** One of the blank sequences stops after that first harmful observation; the other three contain two safe observations and one harmful observation. No unexecuted seed is imputed. These facts were checked directly against the existing content-free `subset_decisions` and its neutralizer counts.

Consequently the current signal is a valid violation of the combined finite-seed recovery predicate, but it is entirely specific to the blanking operator among these four adjacent witnesses. It does not demonstrate replicated adverse behavior under source-aware omission, reliable harmfulness across all seeds, or a general property of model safety. This is precisely why operator identity must be explicit in the prospective estimand. Three safe sampled generations also do not certify a low population risk of harmful generation; all present exactness claims concern the frozen finite observation contract.

The observation supports a narrower and useful design: synthetic monotone truth tables are known-negative controls for the closure-residual diagnostic; h4rm3l is an empirically motivated comparison family, expected from this pilot to show mostly algebraic grouping effects; DeepInception is a candidate setting for operator-dependent recovery reversals. Calling h4rm3l a proven negative control would be too strong. Its three units and two adjacent merges also differ from DeepInception's seven units and six merges, so raw any-merge incidence differences mix attack family, dimension, and opportunity count.

A new prospective design may therefore allow heterogeneous outcomes across the two families rather than demand that both exhibit the same positive effect. That is a disclosed pre-output revision to V1's proposed kill criteria, not a retroactive pass. Freeze the measurement question, denominator, exact family-specific expectations, and replication criterion before Primary A; retain both families and all operator results even when one is negative. Independent B replication should test the declared result, including specificity and absence claims where adequate precision exists. A negative result in the comparison family can increase the method's credibility, but cannot substitute for replication of the claimed nontrivial effect.

## 10. Independent witness provenance implementation and receipt

The follow-up request authorized the new script `scripts/audit_rescue_witness_provenance_v2.py`, its focused tests `tests/test_rescue_witness_provenance_v2.py`, and a new write-once artifact `data/natural_language_localization/rescue_identification_v2/witness_provenance.safe.json`. No prior code or scientific receipt was modified by this subtask.

The script pins and verifies the safe instance source, safe observation source, D3 contract, and V2 parent audit file hashes. It reconstructs every per-neutralizer safe/harmful/abstain/confound count from actual recorded safe observations, copies the observed seed IDs, checks witness validity, and preserves unobserved seeds as unobserved. It deduplicates a witness by instance ID, exact fine atomic intervention, and exact coarse atomic union. Different partitions can represent the same atomic reversal.

| Comparison scope | Partition-witness occurrences | Unique atomic reversals | Unique instances/payloads | Blank only | Omission only | Both operators |
|---|---:|---:|---:|---:|---:|---:|
| Adjacent one-merge | 4 | 3 | 2 / 2 | 3 | 0 | 0 |
| Arbitrary one-merge | 12 | 5 | 2 / 2 | 3 | 1 | 1 |

The 12 arbitrary witness occurrences belong to 11 partition comparisons because a comparison may contain two distinct fine-minimum reversals. They are not 12 independent observations. Actual harmful seeds among these witnesses are 11 and 47, read from the pinned observation records; no seed was inferred from an aggregate count. In particular, the four adjacent contrasts represent three atomic reversals, not four independent behavioral events.

The arbitrary partition results contain omission-specific and cross-operator adverse reversals, but they do not change the fact that the adjacent findings are all blank-specific. Choosing the arbitrary contrasts after seeing this distinction would be another exploratory design decision and must not be presented as replication of the adjacent result.

Per-axis family identification bounds were intentionally not computed. D3 capability controls were selected after joint success under both operators, so a single operator's safe rows in jointly failed interventions do not automatically carry the capability evidence needed for independently certified per-axis recovery. The witness provenance is stronger than a silent reinterpretation of those unchecked rows.

Verification: the four focused tests and Ruff passed. Tests verify actual pinned-source reconstruction, deduplication to three adjacent atomic reversals, preservation of a recorded seed that cannot be inferred from counts, missing-seed retention, and rejection of inconsistent counts, duplicate seeds, and invalid observations. A second reconstruction matched the persisted JSON exactly.

Artifact size: 52,149 bytes. File SHA-256: `14c1fbb21549ca05002296d950a9ecb2bc06eac4224d463f7b08dbd22429ec8f`. Canonical result identity: `d87909008556eaf2674fa93129327e51464b6743d6317ae222b1416ba384b125`.
