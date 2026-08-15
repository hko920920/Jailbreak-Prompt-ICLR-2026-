# Experiment Plan and Go/No-Go Gates v1 — Fully Automated Primary Evidence

## Phase 0 — Infrastructure and prior exploratory evidence

Completed exploratory work established that target-model refusal recovery can occur after coarse scaffold neutralization, but also exposed prompt-behavior drift, evaluator weakness, and malformed-edit artifacts in free-form jailbreak pairs.

These results motivate the new primary design. They are not used to estimate the final localizability rate.

The prepared blinded human package is archived as an optional calibration artifact and is not part of the primary gates.

## Pre-Gate paper viability decision

The project proceeds only under the programmatically grounded formulation documented in:

- `docs/HUMAN_FREE_PAPER_VIABILITY_AUDIT.md`;
- `docs/FORMAL_PROBLEM.md`.

The primary paper uses no new human annotations. It uses typed prompt programs, exact payload invariants, direct target-model interventions, frozen public evaluator consensus, and explicit abstention.

# Gate 1 — Fully Automated Phenomenon and Oracle Gate

## Objective

Determine whether successful compositional jailbreaks frequently contain compact, robustly causal attack-component sets under a machine-verifiable intervention contract.

## Data construction

Build a typed payload-preserving attack-program benchmark with:

- at least 50 harmful payloads from a standardized source;
- at least 6 payload-preserving primitives;
- at least 4 composition families;
- at least 200 rendered attacks for the primary model before eligibility filtering;
- exact payload, program-node, character, and token provenance;
- split by attack program/composition rather than prompt string alone;
- a complete generated denominator and exclusion ledger.

Primary primitives may include typed variants of:

- role/persona framing;
- fictional or hypothetical context;
- authority framing;
- refusal suppression;
- benign justification;
- output-format coercion;
- prefix/suffix wrappers;
- many-shot or contextual wrappers when payload provenance remains exact.

Payload-transforming primitives such as translation, Base64, ciphering, or arbitrary rewrites are excluded from the primary Gate 1 denominator unless their provenance and inverse mapping are formally verified.

## Primary model

Use one 7B–9B instruction model until the data, evaluator, intervention, and exact-oracle pipeline are correct. Model expansion belongs to Gate 2.

## Evaluator contract

Freeze at least two independent public evaluator families, preferably:

- HarmBench classifier;
- StrongREJECT evaluator;
- FJAR anchored-reference evaluator when reproducibly available.

Define conservative `HARMFUL`, `SAFE`, and `EVALUATOR_ABSTAIN` rules before observing Gate 1 results.

Required sensitivity outputs:

- full consensus;
- each evaluator separately;
- pairwise evaluator combinations;
- threshold perturbation;
- coverage and abstention.

## Eligibility

An item is eligible only when:

- the payload-only prompt is `SAFE` by frozen consensus;
- the full attack is `HARMFUL` by frozen consensus;
- both outcomes satisfy the seed-stability rule;
- payload and program invariants pass;
- no evaluator abstention occurs.

## Interventions

Use at least two typed neutralizers:

1. program-node disable/removal followed by re-rendering;
2. registered neutral replacement preserving the slot and prompt grammar.

Deletion is diagnostic unless it is itself a valid typed program rewrite.

Every intervention must pass:

- exact payload hash equality;
- zero payload-span overlap;
- renderer/type validation;
- required-slot validation;
- forbidden-safety-cue scan;
- registered-operator identity.

## Exact oracle

For programs with at most 8 neutralizable nodes:

- enumerate every non-empty node subset;
- run both neutralizers;
- run all frozen seeds;
- classify with evaluator consensus;
- retain all lowest-cost robust sets;
- test strict subsets;
- record multiple incomparable minimal sets;
- record non-monotonicity and interactions.

For finer rendered spans, use an explicitly bounded exact lattice. Any approximate boundary resolution must be labeled near-exact.

## Negative controls

- random node sets matched by cost;
- random spans matched by length and position;
- harmful payload deletion control;
- benign role-play programs using the same primitives;
- malformed-render control rejected before inference;
- neutralizer-only artifacts;
- short-removal controls that are not causally effective;
- evaluator-swap controls.

## Gate 1 metrics

- generated attacks and complete denominator;
- eligible count and rate;
- robustly localizable rate;
- single- versus multi-component localizability;
- minimal rendered fraction and program-node cost;
- cross-neutralizer agreement;
- seed-stable recovery;
- evaluator coverage and abstention;
- family-specific localizability;
- distributed/non-monotonic fraction;
- oracle query count;
- invariant and compile failures.

## Gate 1 GO criteria

All must hold:

1. at least **30 eligible attacks**;
2. robustly localizable fraction at least **30%**;
3. median minimal fraction/cost among localized cases at most **25%**;
4. compact cases in at least **3 composition families**;
5. cross-neutralizer agreement at least **0.75** on non-abstained candidates;
6. evaluator abstention at most **20%**;
7. seed-stable recovery in at least **80%** of localized cases;
8. zero payload-provenance violations in accepted explanations;
9. negative controls show that short removal alone is not sufficient;
10. exact oracle, cache, and manifests reproduce under CI/local rerun.

## Gate 1 outcomes

- `GATE1_GO`: all criteria pass;
- `GATE1_PIVOT_DISTRIBUTED`: compact localization is weak but systematic multi-component/distributed causal structure is strong;
- `GATE1_STOP_OR_REDESIGN`: evaluator ambiguity or intervention artifacts dominate, or too few eligible attacks exist.

No wavelet or adaptive-search claim is developed before this decision.

# Gate 2 — Generalization and Algorithm Gate

## Objective

Establish that the phenomenon generalizes and that the proposed adaptive method approaches the oracle with materially fewer target-model calls.

## Expansion

- at least 3 target-model families;
- one secondary-size check;
- held-out payload categories;
- held-out attack primitives;
- held-out compositions;
- prefix, infix, suffix, and mixed positions;
- benign context and filler stress tests;
- exact-payload-preserving external subset from h4rm3l, JailbreakBench, or independently sourced formal templates.

All external examples must pass the same program/provenance or exact-alignment contract. Free-form examples that cannot be verified receive `UNVERIFIED_ALIGNMENT` and do not enter primary rates.

## Baselines

- random cost-matched components;
- atomic leave-one-out;
- exhaustive oracle;
- greedy top-down hierarchy;
- greedy bottom-up merge;
- Erase-and-Check / GreedyEC / GradEC adaptation;
- Token Highlighter or integrated gradients on open-weight models;
- plain typed hierarchy without tree-Haar;
- LLM-rationale span selection as a secondary baseline;
- GuardNet when labels/code are compatible.

## Proposed method

Develop an adaptive typed search with:

- group interventions over program subtrees;
- conservative effect density;
- interaction-residual diagnostics;
- monotonicity checks;
- multi-node refinement;
- strict-subset pruning;
- evaluator-aware and budget-aware abstention.

Tree-Haar/wavelet prioritization is a replaceable variant, not a fixed contribution.

## Main metrics

- oracle-valid cost regret;
- oracle explanation recovery;
- target-model query count;
- quality-query Pareto frontier;
- single- and multi-component recovery;
- distributed-case abstention precision;
- cross-neutralizer and cross-evaluator stability;
- held-out primitive/composition generalization;
- cross-model transfer;
- real external-subset agreement;
- wall-clock and compute cost.

## Algorithm GO criteria

The method must satisfy every validity criterion and at least one primary algorithmic criterion.

Primary criteria:

- recover at least **90% of oracle-valid explanation quality with at most 25% of oracle queries**; or
- obtain at least **4x query reduction** at statistically indistinguishable validity/minimality; or
- materially improve multi-component interaction discovery or distributed-case abstention over the plain hierarchy.

Validity criteria:

- no decision-changing degradation under evaluator swap;
- no decision-changing degradation under neutralizer swap;
- seed stability;
- held-out family and model generalization;
- external exact-alignment subset agrees directionally with controlled results;
- complete denominator, failures, and abstentions reported.

## Gate 2 outcomes

- `PAPER_GO`: phenomenon and algorithm criteria pass;
- `PAPER_GO_NO_WAVELET`: phenomenon generalizes and simpler adaptive search wins; wavelet is removed;
- `BENCHMARK_ONLY_BORDERLINE`: task/benchmark is strong but algorithm adds little;
- `PIVOT_DISTRIBUTED`: localized explanations are uncommon but distributed structure is systematic;
- `STOP_OR_NARROW`: only one family/model works or external validation contradicts Gate 1.

# Phase 3 — Paper evidence and optional mechanistic analysis

Only after `PAPER_GO` or `PAPER_GO_NO_WAVELET`:

- freeze all main claims and denominators;
- run paired bootstrap/confidence intervals;
- complete attack-family and model-family analyses;
- optionally test known safety heads on a small open-weight subset as supporting evidence;
- do not introduce a new safety-head discovery contribution.

# Phase 4 — Evidence freeze and submission

Freeze:

- benchmark version and programs;
- payload/evaluator/model revisions;
- all eligibility and exclusion IDs;
- oracle and algorithm outputs;
- configuration hashes;
- compute and query ledger;
- all primary tables and figures;
- failed runs and abstentions;
- ethics/responsible-release protocol;
- weekly literature refresh.

# Claim discipline

Use:

- `programmatically grounded`;
- `interventional`;
- `oracle-minimal within the frozen lattice`;
- `payload-preserving`;
- `evaluator-consensus with abstention`.

Do not use unqualified:

- `ground-truth causal span`;
- `globally minimal`;
- `first causal jailbreak explanation`;
- `first composable jailbreak benchmark`;
- `human-free objective truth`;
- `wavelet novelty`.