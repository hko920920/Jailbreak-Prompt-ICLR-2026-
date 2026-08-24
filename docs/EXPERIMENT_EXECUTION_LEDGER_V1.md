# Experiment Execution Ledger v1

Date: 2026-08-24 (Asia/Seoul)

## Paper identity now fixed

The paper studies **input-element combinations**, not a single-token ranking.

> For an already-successful jailbreak, identify the smallest attack-added input combinations whose intervention reliably restores safe behavior without altering the harmful goal or destroying model capability; then compare singleton, interactive, redundant, non-monotone, and distributed structures across semantic-readable, fluent-optimized, and non-fluent optimized attacks.

Token-level analysis is the finest refinement stage. The primary object is the robust minimal recovery/cut-set topology over a frozen, regime-specific intervention vocabulary.

## Evidence classes

Every result must be assigned exactly one class:

- `PROTOCOL`: definitions, thresholds, splits, units, budgets, and claim boundaries frozen before outcomes;
- `DEVELOPMENT`: implementation checks and feasibility evidence that cannot become paper-valid confirmatory evidence;
- `NEGATIVE`: predeclared failed routes or hypotheses;
- `PAPER_VALID`: fresh confirmatory evidence generated under the final frozen contract;
- `SEALED`: data or experiments not yet authorized for inspection.

## Current evidence ledger

- AgentHarm Qwen/Llama route: `NEGATIVE`; useful for feasibility history, not causal-topology evidence.
- Legacy broad-span 32%--58% observations: `DEVELOPMENT`; motivation only and must be reproduced.
- Same-model two-pass and persona calibration: `DEVELOPMENT`; rubric sensitivity only.
- Standards-derived evaluator panel contracts and hardening: `PROTOCOL` plus `DEVELOPMENT` until external validation passes.
- Semantic-only Stage A: `SEALED` and superseded for broad claims.
- Cross-regime Stage A, prior evaluation, held-out, causal oracle, keep-only sufficiency, and wavelet: `SEALED`.

## Immediate executable sequence

### E1 — Qualify the abstaining evaluator panel

1. `E1A_STATIC_HARDENING`: completed successfully.
2. `E1B_WILDGUARD_LIVE_REPRODUCTION_AND_CANARIES`: active GitHub Actions experiment at the time of this record.
3. If E1B passes, run the next frozen component reproduction/canary step; if it fails, repair only the implementation/runtime under unchanged thresholds.
4. Complete refusal/harmfulness, behavior-compliance, actionability, and capability-confound axes.
5. Run external human-labeled selective-risk and coverage validation.
6. Do not open any attack Stage A unless the panel reaches its frozen GO or permitted NARROW decision.

### E0 — Attack-family provenance audit, with no target outcomes

After evaluator authorization, audit at least two candidate families in each regime:

- `S`: semantic-readable;
- `F`: fluent optimized;
- `U`: non-fluent optimized.

Freeze official repository, immutable revision, license, artifact route, tokenizer, insertion position, payload-preservation rule, compute budget, and intervention vocabulary before target outputs.

### D1 — Balanced development signal screen

Use a balanced S/F/U matrix to identify stable direct-safe / attacked-harmful pairs. This is population discovery only; no causal topology is inferred from unstable pairs.

### D2 — Stability confirmation

Repeat only screen-positive pairs under frozen seeds and generation settings. Exclude direct-harmful, attack-unstable, capability-confounded, and unresolved-abstention cases.

### D3 — Coarse causal-topology pilot

For stable pairs:

- S: strategy-node subsets;
- F: generated clause/block subsets;
- U: frozen token-block/interval vocabulary.

Enumerate all subsets where tractable and verify every reported minimal set against all strict subsets. Use at least two meaningful neutralizers and preserve the harmful payload.

### D4 — GO / NARROW / STOP

- `GO`: stable population across regimes plus repeated nontrivial topology and neutralizer stability;
- `NARROW`: defensible signal in only one or two regimes, requiring an honestly narrowed paper;
- `STOP`: inadequate stable population, evaluator failure, capability collapse, or only trivial/unstable structure.

### D5 — Fine refinement and baselines

Refine only predeclared stratified coarse cases to words, character/byte spans, token blocks, or token combinations. Compare exact/contract-exact topology with leave-one-out, Token Highlighter-style attribution, Mask-GCG-style scores where applicable, suffix-onset detection, random same-size intervention, and greedy/group-testing search.

SHIPs/SAHARA-inspired scoring and wavelet are approximation baselines only. Wavelet remains closed until exact or contract-exact topology exists.

### C1 — Fresh paper-valid confirmation

Freeze a new contract with unseen payloads, at least two model families, at least two attack families per represented regime, fixed thresholds, multi-neutralizer controls, uncertainty intervals, and an audit route. Only this stage may produce broad paper claims.

## One-at-a-time execution rule

At every step:

1. freeze the exact contract and hashes;
2. run one authorized experiment;
3. record run ID, commit, artifact digest, aggregate result, and sealed boundaries;
4. apply the predeclared branch decision;
5. only then prepare the next experiment.

No threshold relaxation, attack-family substitution, unit redefinition, held-out inspection, causal-oracle opening, or wavelet activation is permitted after observing decision-relevant outputs.

## Current next action

Finish and adjudicate the active E1B WildGuard reproduction/canary run. Stage A and all causal interventions remain closed.