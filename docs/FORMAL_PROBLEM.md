# Formal Problem and Method v0

## Setting

For each example, assume:

- an original request `x_o` that the target model refuses;
- a successful jailbreak prompt `x_j` associated with the same requested behavior;
- a target model `M`;
- a response judge producing refusal and harmful-compliance scores;
- an intent judge comparing an intervened prompt with `x_o`;
- a family of neutralization operators.

## Candidate span set

A candidate `S` is a set of one or more non-overlapping character spans in `x_j`. A neutralizer `n` produces the counterfactual prompt `n(x_j, S)`.

A valid explanation should satisfy:

1. **Refusal recovery:** neutralizing `S` substantially increases refusal or decreases harmful compliance.
2. **Intent preservation:** the underlying requested behavior remains represented after intervention.
3. **Robustness:** the effect persists across neutralizers, decoding seeds, and judge variants.
4. **Minimality:** no lower-cost subset satisfies the same constraints within tolerance.

## Robust causal score

For a refusal score `r`, define the estimated effect

```text
Delta_ref(S) = E[r(M(n(x_j, S)))] - E[r(M(x_j))]
```

where the expectation is over neutralizers and decoding seeds. Selection should use a conservative lower confidence bound, not a single deterministic output.

The cost is provisionally

```text
cost(S) = token_fraction(S) + lambda_set * (number_of_spans(S) - 1)
```

The method returns either a minimal valid span set or an abstention status such as `ABSTAIN_DISTRIBUTED`.

## Search v0

1. Split the prompt into deterministic atomic clauses and construct a balanced semantic interval tree.
2. Evaluate coarse span interventions.
3. Expand nodes with high refusal-recovery effect or high tree-Haar contrast.
4. Verify candidate leaves and limited two-span combinations.
5. Prune redundant spans by subset testing.
6. Re-evaluate final candidates across all neutralizers and seeds.

## Why tree-Haar is provisional

The causal effect of a span is not guaranteed to be additive. Tree-Haar coefficients are therefore used only to prioritize queries; every selected explanation must pass direct behavioral intervention tests. Interaction residuals between parent and children are recorded rather than assumed away.

## Required statuses

- `LOCALIZED`
- `ABSTAIN_DISTRIBUTED`
- `BASELINE_ATTACK_FAILED`
- `ORIGINAL_NOT_REFUSED`
- `INTENT_NOT_PRESERVED`
- `QUERY_BUDGET_EXHAUSTED`
