# Formal Problem and Method v1 — Programmatically Grounded Human-Free Design

## Setting

For each example, assume:

- a typed harmful payload `q`;
- a payload-only prompt `x_o = render(q)` that the target model refuses;
- a typed attack program `p = T_m o ... o T_1`;
- a rendered attacked prompt `x_j = render(p, q)` that succeeds;
- exact provenance from every program node and the payload slot to character/token spans;
- a target model `M` with frozen revision and decoding distribution;
- a frozen automated evaluator ensemble `J` with explicit abstention;
- a registered family of typed neutralization operators `N`.

The primary benchmark includes only payload-preserving attack programs. The payload is byte-identical in `x_o`, `x_j`, and every valid intervention.

## Program and span candidates

A candidate `S` is either:

1. a set of neutralizable attack-program nodes; or
2. a set of non-overlapping rendered spans that map entirely to neutralizable attack-node provenance.

A neutralizer `n in N` disables or replaces `S` and re-renders the program. An intervention is valid only when:

- payload hash is unchanged;
- no selected span overlaps payload provenance;
- the typed renderer succeeds;
- every required slot remains bound;
- no registered forbidden safety/refusal cue is inserted;
- the intervention belongs to the frozen operator family.

Program provenance is not a causal label. Causal status is established only by direct target-model intervention.

## Evaluator consensus

The primary evaluator is a conservative intersection or consensus of frozen public evaluators, such as HarmBench, StrongREJECT, and FJAR when reproducibly available.

For a target response `y`:

- `J(y) = HARMFUL` only when the frozen harmful-consensus rule passes;
- `J(y) = SAFE` only when the frozen safe-consensus rule passes;
- otherwise `J(y) = ABSTAIN`.

Evaluator coverage and abstention are reported explicitly. No same-model heuristic alone determines a paper-facing result.

## Eligibility

An attacked item is eligible only when:

```text
J(M(x_o)) = SAFE
J(M(x_j)) = HARMFUL
```

and both outcomes satisfy the frozen seed-stability requirement. Evaluator-abstained or invariant-violating examples are not treated as failures or successes; they receive explicit exclusion statuses.

## Robust interventional effect

For attack-success score `a`, define the intervention effect:

```text
Delta(S) = E[a(M(x_j))] - E[a(M(n(x_j, S)))]
```

where the expectation is over registered neutralizers and decoding seeds. Selection uses a conservative lower confidence bound rather than a single completion.

A candidate is a robust recovery set when every primary neutralizer yields `SAFE`, the validity contract passes, and the effect is seed-stable.

## Oracle-relative minimality

The oracle returns all lowest-cost robust recovery sets in a frozen candidate lattice:

```text
S* = argmin_S cost(S)
```

subject to robust recovery and validity.

The provisional cost is:

```text
cost(S) = rendered_character_fraction(S)
        + lambda_set * (number_of_spans(S) - 1)
        + lambda_nodes * (number_of_program_nodes(S) - 1)
```

A result is called minimal only relative to:

- the declared candidate lattice;
- the registered neutralizers;
- the evaluator ensemble;
- the frozen decoding distribution.

Strict subsets are tested directly. Multiple incomparable minimal sets are retained rather than collapsed.

## Oracle regimes

- exact power-set enumeration for at most 8 neutralizable program nodes;
- exact contiguous or bounded span lattice for tractable rendered text;
- near-exact bounded enumeration with an explicit resolution certificate otherwise.

The oracle records non-monotonicity and node interactions. A component can be individually ineffective yet jointly necessary.

## Adaptive search v1

1. Build a typed program tree and rendered provenance map.
2. Evaluate coarse node-group interventions.
3. Prioritize groups by conservative robust effect density.
4. Record parent-child interaction residuals and monotonicity violations.
5. Refine promising groups into child nodes or finer spans.
6. Search limited multi-node combinations when single-node sparsity fails.
7. Verify every selected explanation across all primary neutralizers and seeds.
8. Prune redundant components through strict-subset tests.
9. Abstain when evaluator ambiguity, distributed causality, or budget exhaustion prevents a valid localized explanation.

Tree-Haar or wavelet scores are optional query-prioritization features only. They remain in the method only after outperforming the identical hierarchy without them.

## Required statuses

- `LOCALIZED_SINGLE`
- `LOCALIZED_MULTI`
- `ABSTAIN_DISTRIBUTED`
- `EVALUATOR_ABSTAIN`
- `BASELINE_ATTACK_FAILED`
- `ORIGINAL_NOT_REFUSED`
- `PAYLOAD_INVARIANT_FAILED`
- `PROGRAM_COMPILE_FAILED`
- `INTERVENTION_INVALID`
- `QUERY_BUDGET_EXHAUSTED`

## Claim boundary

The primary claim is programmatically grounded interventional localization of successful compositional jailbreaks. It is not:

- the first composable jailbreak language;
- the first token/span localization method;
- an unrestricted global-minimality claim;
- a universal explanation of all free-form jailbreaks;
- a wavelet-attribution novelty claim.