# E0 AutoDAN Route, Budget, and Harmless Materialization v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This is a pre-output admission step for the fluent-optimized (`F`) regime. It closes four blockers left by the pinned AutoDAN static and Qwen tokenizer/chat-template audits:

1. choose regeneration or an immutable final-artifact route;
2. freeze compute and candidate-selection budgets;
3. protect the immutable payload slot across every enabled mutation route;
4. execute a harmless candidate-materialization smoke without target generation.

This step does not test jailbreak success and cannot produce paper-valid causal evidence.

## Frozen route

The pinned upstream repository does not provide an immutable final optimized prompt artifact for every behavior in the planned matrix. The selected route is therefore:

```text
pinned AutoDAN prompt group
        -> fixed-budget GA regeneration
        -> exact placeholder guard after every enabled transformation
        -> fixed target-prefix-loss selection
        -> Qwen chat-template adapter
```

The route identity is:

```text
AUTODAN_GA_REGENERATE_FIXED_BUDGET_QWEN_V1
```

Only the GA route is enabled. External GPT/API mutation and local synonym mutation are disabled. The enabled variation operations are crossover and reference-pool replacement. Every candidate must contain exactly one `[REPLACE]` placeholder after each operation and before scoring or materialization. An invalid candidate is rejected and deterministically replaced by a valid parent or pinned reference.

## Frozen budget

The development generation budget preserves the pinned upstream GA defaults:

- seed: `20`;
- steps: `100`;
- batch size: `256`;
- elite fraction: `0.05` (`12` candidates);
- crossover probability: `0.5`;
- crossover points: `5`;
- mutation rate: `0.01`;
- maximum scored candidates per behavior and generation seed: `25,600`.

The official refusal-prefix early stop is disabled because it would let an unqualified success heuristic alter the candidate population. Every authorized run must use the full fixed budget.

Positive-pair confirmation generation seeds are frozen as `29` and `43`; they are not opened unless the initial development screen is positive.

## Frozen selection rule

Candidate selection may not use attack success, evaluator labels, or generated response inspection. It is frozen as:

1. minimum target-prefix loss across all guarded candidates and all fixed steps;
2. earliest optimization step;
3. lowest batch index;
4. lexicographic SHA-256.

Exactly one candidate is retained per behavior and generation seed.

## Harmless smoke

The executable smoke:

- verifies both predecessor result identities and statuses;
- verifies the pinned AutoDAN source and artifact identities;
- loads `assets/prompt_group.pth` with `torch.load(..., weights_only=True)`;
- admits only string references containing exactly one placeholder;
- hash-ranks a frozen 32-reference sample;
- runs 16 deterministic crossover pairs and 8 reference replacements;
- applies the payload guard after each enabled transformation;
- materializes only a synthetic harmless mixed-case payload;
- repeats the entire operation three times and compares aggregate hashes;
- records no raw candidate or materialized text.

No target-model weights, target generation, external API, real harmful payload, success evaluator, held-out data, or causal intervention is used.

## Interpretation

A pass establishes only that the AutoDAN family has a pinned, deterministic, payload-preserving generation/materialization contract with a fixed compute and selection budget. It does not admit the family to the balanced signal screen by itself. Admission still requires evaluator-panel authorization and a separately frozen balanced S/F/U signal-screen contract.

A failure permits implementation repair or replacement of the AutoDAN route while all target outcomes remain unopened. It does not permit changing the paper claim, opening Stage A, or relaxing any success threshold.
