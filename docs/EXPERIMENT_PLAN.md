# Experiment Plan and Go/No-Go Gates

## Phase 0 — Infrastructure smoke

Purpose: verify all data and code paths without model downloads or harmful text.

Deliverables:

- paired-example schema;
- segmentation and intervention primitives;
- query accounting;
- exhaustive and adaptive search interfaces;
- deterministic toy test;
- config and artifact manifests;
- CI.

Pass condition: CPU-only tests and the toy end-to-end run succeed.

## Phase 1 — Phenomenon viability

### Data

Start with 100 frozen original/jailbreak pairs spanning at least eight attack families. Use existing paired datasets where licenses permit. No threshold tuning on the frozen evaluation IDs.

### Models

Primary:

- Llama-3.1-8B-Instruct
- Qwen2.5-7B-Instruct

Secondary only after the gate:

- Gemma-2-9B-it or a comparably sized third family

This scope is compatible with a DGX Spark-class system using careful batching and optional quantized inference.

### Baseline eligibility

Keep only examples where:

- the original request is refused;
- the jailbreak prompt succeeds under the chosen full-response judge;
- both outcomes are reproducible under the frozen generation setting.

### Candidate neutralizers

- deletion;
- typed placeholder replacement;
- length-aware neutral filler;
- neutral paraphrase after the deterministic operators are validated.

### Gate metrics

- localizable fraction;
- median selected token fraction;
- full-response refusal recovery;
- harmful-intent preservation;
- agreement across neutralizers;
- stability across generation seeds;
- benign false-localization rate.

### Go criteria

Proceed only if all provisional thresholds hold:

- localizable fraction at least 35%;
- median selected span fraction at most 25%;
- cross-neutralizer agreement at least 0.60;
- no evidence that success is driven mainly by deleting the harmful payload;
- manual audit confirms the judge is not rewarding broken or incoherent prompts.

## Phase 2 — Algorithm comparison

### Baselines

- random length-matched spans;
- atomic leave-one-out;
- exhaustive contiguous spans on tractable prompts;
- greedy top-down interval search;
- gradient token attribution for open-weight models, where feasible;
- Token Highlighter-style ranking or the closest reproducible implementation;
- wavelet-free version of the same hierarchical search.

### Proposed variants

- tree-Haar prioritization;
- interaction-residual prioritization;
- robust multi-neutralizer score;
- abstention-aware stopping.

### Main metrics

- best-valid-cost regret relative to exhaustive search;
- refusal-recovery effect;
- intent preservation;
- localization overlap on controlled ground-truth prompts;
- target-model query count;
- wall-clock time;
- abstention precision;
- seed and neutralizer stability.

### Algorithm gate

Tree-Haar remains in the paper only if it provides at least one defensible advantage:

- at least 4x query reduction at comparable explanation quality;
- materially better recovery of heterogeneous span scales;
- materially better boundary/position stability;
- better interaction candidate discovery.

Otherwise replace it with the simpler adaptive search and keep the task contribution.

## Phase 3 — Generalization and findings

- held-out attack families;
- held-out harmful-behavior categories;
- cross-model span transfer;
- prompt paraphrase and position-shift stress tests;
- localizable versus distributed attack taxonomy;
- optional safety-head or residual-stream validation on a small open-weight subset.

## Phase 4 — Paper evidence freeze

Freeze:

- main claims;
- evaluation IDs;
- all primary tables and figures;
- configuration hashes;
- model and judge revisions;
- compute accounting;
- exclusions and failed runs;
- paired-bootstrap confidence intervals.

## Required negative controls

- random spans matched by length and position;
- benign prompts with superficially similar role-play language;
- harmful payload deletion control;
- malformed-prompt control;
- neutralization-only judge without target-model generation;
- judge swap or human audit subset.
