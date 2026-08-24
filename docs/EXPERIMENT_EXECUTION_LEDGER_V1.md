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
- AutoDAN source/adaptor and tokenizer/chat-template audits: `PROTOCOL` plus `DEVELOPMENT`; they establish provenance and payload-preserving adapter feasibility, not jailbreak success.
- Semantic-only Stage A: `SEALED` and superseded for broad claims.
- Cross-regime Stage A, prior evaluation, held-out, causal oracle, keep-only sufficiency, and wavelet: `SEALED`.

## Executed checkpoints

### E1B — WildGuard live qualification

- active hardened workflow run: `32704859942`;
- job: `97372967617`;
- run source head: `bdf26570ff835498cb9dc85b40eaf379a1080a12`;
- checkout, Python setup, runtime-only startup hardening, and harness validation: passed;
- exact 200-example reproduction plus injection-canary harness: still executing at the latest recorded observation;
- active immutable checkpoint:
  `data/natural_language_localization/evaluator_panel_v1/e1b_active_run_32704859942.safe.json`;
- no next evaluator component, Stage A, held-out partition, causal oracle, or wavelet has been opened.

### E0-F1 — AutoDAN static source/adaptor audit

- upstream: `SheltonLiu-N/AutoDAN@34062e964185693e81a6775b4f0d00bfd7507612`;
- upstream tree: `39ceba6f45e5dec17db8d3099d7281f8673ceb14`;
- workflow run: `32711644171`;
- artifact: `9514302311`;
- artifact digest: `022183567c687a90cce6d1f768077cba0d828241a5e9bec6dcf21b051e332569`;
- mandatory static checks: 12/12 passed;
- decision: `E0_AUTODAN_STATIC_AUDIT_CONDITIONAL_ADVANCE`;
- result commit: `98c7e3abdb45da4fbce4edfc5d0d71e5cf6a85e8`.

The official suffix manager lowercases the instruction while replacing
`[REPLACE]`, so the unmodified upstream route violates the byte-identical
payload contract. A study-side exact-placeholder string route preserved the
synthetic harmless payload exactly once. AutoDAN was not admitted to the signal
screen.

### E0-F2 — AutoDAN-to-Qwen tokenizer/chat-template adapter smoke

The first run, `32712732866`, passed lint, unit tests, AutoDAN source pinning, and
the pinned Qwen tokenizer-only download, but stopped before decision-relevant
rendering because `jinja2` was absent. The operational failure is preserved in:

`data/natural_language_localization/e0_attack_family_provenance_v1/autodan_qwen_adapter_run_32712732866_operational_failure.safe.json`

The scientific contract, source revisions, synthetic payload, and pass rules
were unchanged. Runtime-only remediation pinned `jinja2==3.1.6`.

The unchanged rerun completed successfully:

- workflow run: `32713133181`;
- artifact: `9514871455`;
- artifact digest: `e14ba815942f8ffdd3dd0e256c03ea3e18fba0d991d7a49da79f9d3f572c5efb`;
- decision: `E0_AUTODAN_QWEN_ADAPTER_SMOKE_PASS_REMAIN_CONDITIONAL`;
- mandatory adapter checks: 17/17 passed;
- tokenizer: pinned `Qwen/Qwen2.5-7B-Instruct@a09a35458c702b33eeacc393d103063234e8bc28`;
- synthetic payload after Qwen chat rendering: one contiguous 21-token interval;
- target-model weights downloaded: false;
- target-model generation performed: false;
- admitted to balanced signal screen: false.

This step resolved exact-placeholder materialization and Qwen tokenizer/chat-template compatibility. Remaining AutoDAN admission blockers are:

1. freeze regeneration versus a frozen artifact route;
2. freeze compute and candidate-selection budgets;
3. protect the payload placeholder in every enabled mutation route;
4. run a harmless end-to-end candidate-materialization smoke without target generation.

## Immediate executable sequence

### E1 — Qualify the abstaining evaluator panel

1. `E1A_STATIC_HARDENING`: completed successfully.
2. `E1B_WILDGUARD_LIVE_REPRODUCTION_AND_CANARIES`: active GitHub Actions experiment at the time of this record.
3. If E1B passes, run the next frozen component reproduction/canary step; if it fails, repair only the implementation/runtime under unchanged thresholds.
4. Complete refusal/harmfulness, behavior-compliance, actionability, and capability-confound axes.
5. Run external human-labeled selective-risk and coverage validation.
6. Do not open any attack Stage A unless the panel reaches its frozen GO or permitted NARROW decision.

### E0 — Attack-family provenance audit, with no target outcomes

Safe source, license, payload-slot, tokenizer, chat-template, and unit-manifest
audits may proceed with synthetic harmless payloads while E1 runs. They may not
call a target model or inspect attack success.

Audit at least two candidate families in each regime:

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

At every decision-relevant step:

1. freeze the exact contract and hashes;
2. run one authorized experiment;
3. record run ID, commit, artifact digest, aggregate result, and sealed boundaries;
4. apply the predeclared branch decision;
5. only then prepare the next experiment.

Non-decision source/adaptor audits may be executed in parallel only when they use
synthetic harmless payloads, do not call a target model, and cannot reveal attack
success or causal outcomes.

No threshold relaxation, attack-family substitution, unit redefinition, held-out inspection, causal-oracle opening, or wavelet activation is permitted after observing decision-relevant outputs.

## Current next actions

1. finish and adjudicate active E1B run `32704859942`;
2. freeze the AutoDAN regeneration/artifact route, mutation payload protection,
   and compute-selection budget under a new pre-outcome contract;
3. keep all target-model outcomes and causal interventions closed.
