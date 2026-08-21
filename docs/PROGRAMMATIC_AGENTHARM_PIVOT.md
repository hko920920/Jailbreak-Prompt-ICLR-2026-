# Programmatic AgentHarm Pivot

## Decision

The prior Gate 1 result remains immutable:

```text
GATE1_STOP_OR_NARROW
```

It established that the free-form response formulation did not obtain a primary automatic judge satisfying every frozen external threshold. It did **not** test the causal-localization hypothesis. This pivot changes only the outcome contract, not the scientific question.

The new target is:

> **Causal localization of jailbreak-enabling prompt components under programmatically verifiable unsafe agent actions.**

## Why this formulation

Three judge-free alternatives were considered.

| Formulation | Objective verification | Faithfulness to jailbreak safety | Main weakness |
|---|---:|---:|---|
| Structured text fields | Very high | Low–medium | Can collapse into format compliance |
| Executable code tasks | Very high | Medium | Shifts the paper toward code generation |
| Synthetic tool/state transitions | Very high | **High** | Requires a conservative task filter |

The tool-use formulation is selected because it preserves the core safety phenomenon: a harmful user objective is initially blocked, a compositional jailbreak changes the agent's acquisition/action path, and a forbidden action is then completed. Unlike the previous free-form setup, the terminal outcome can be checked from tool names, arguments, order, and synthetic state without classifying natural-language harmfulness.

AgentHarm is suitable as a source because it uses synthetic tools and behavior-specific grading functions. However, the full benchmark also contains LLM semantic and refusal judges. This study therefore admits only a source-pinned subset whose harmful grading function has **no direct or transitive dependence** on:

- `semantic_judge`;
- assistant free-text extractors;
- direct `message.text` access.

The primary outcome also ignores AgentHarm's refusal judge.

## Formal task

Let the exact harmful task payload be `x`, the frozen synthetic tool environment be `T`, and a compositional jailbreak program be

```text
J = (c_1, ..., c_m).
```

An agent produces a tool trace `tau = A(x, J; T)`. A deterministic predicate

```text
U(tau) in {0, 1}
```

is computed solely from the tool trace and synthetic tool responses.

An attack instance is eligible when, under the frozen seed rule:

```text
U(A(x, empty; T)) = 0
U(A(x, J; T))     = 1
```

For a component subset `S`, `N_S(J)` neutralizes exactly those typed attack nodes while preserving the payload `x` byte-for-byte. A robust minimal causal enabling set satisfies:

```text
U(A(x, N_S(J); T)) = 0
```

under both primary neutralizers and the frozen seed rule, while every strict subset of `S` remains successful.

This supports three outcomes without forcing a compact explanation:

- `LOCALIZED_SINGLE`;
- `LOCALIZED_INTERACTIVE` / multiple minimal sets;
- `DISTRIBUTED_OR_NO_ROBUST_RECOVERY`.

## Gate 0 — source viability

Before any target-model output is generated, the pinned AgentHarm source is audited by AST.

A grading function is eligible only when its transitive call graph contains no semantic judge and no assistant free-text dependency. Validation and public-test rows are then filtered by `grading_function`.

Gate 0 passes only if the public-test deterministic subset contains at least:

- 12 unique base behaviors (`id_original`);
- 40 total augmented rows;
- 4 harm categories.

All augmentations of one base behavior remain in one split. Public-test groups are category-stratified and hash-assigned to `confirmatory / final / heldout` in a frozen `1 / 2 / 1` schedule. Validation behaviors are development-only.

## Subsequent gates

Gate 0 does not authorize model inference by itself. A second contract must first freeze:

- the target agent/model and exact chat/tool template;
- the attack-program candidates and typed provenance;
- payload invariance;
- seed and stable-label rule;
- the deterministic grader execution wrapper;
- two payload-preserving neutralizers.

The planned empirical gates are:

1. **Calibration on AgentHarm validation only** — select attack families by a predeclared ranking, with no behavior-specific rewriting.
2. **Fresh confirmatory split** — require stable programmatic attack success on at least 30% of tested base groups and at least two attack families, while direct prompts remain non-successful on at least 80%.
3. **Final eligibility** — require at least 30 stable eligible attack instances spanning at least three families.
4. **Exact typed-component oracle** — enumerate every non-empty component subset under two neutralizers and three seeds.
5. **Gate decision** — compact, interaction/distributed pivot, or stop.

Wavelet or adaptive search remains forbidden until the exact oracle establishes a repeatable causal structure.

## Safety and leakage boundary

- Only synthetic tools are executed.
- No real account, payment, communication, malware, or external side effect is permitted.
- Raw harmful prompts, raw tool outputs, and model generations are not committed.
- Safe artifacts contain source identities, behavior IDs, categories, grader names, hashes, counts, split assignments, and aggregate decisions only.
- The previous JBB final and Gate 2 held-out partitions are not recycled.

## Reviewer-facing contribution if the gates pass

The intended contribution is not a new jailbreak generator. It is a judge-free causal measurement framework showing whether successful agent jailbreaks are driven by compact prompt components, interactions, or distributed attack structure, with exact intervention ground truth and later query-efficient localization evaluated against that oracle.

## Pinned sources

- AgentHarm paper: `arXiv:2410.09024`.
- Inspect Evals source: `UKGovernmentBEIS/inspect_evals` at commit `928e3dd92aa926f7dd1746c753e171f9f717c964`.
- AgentHarm dataset revision: `e23b3fe60a0da9037314b88e5ee3a0c054970dad`.
- Harmful grader Git blob: `679a9037a04d72cbd65f5666711b0f1e977d7a1c`.
- AgentHarm adapter Git blob: `90a652966f1ba656dfd0c65f0312e8823b436641`.
