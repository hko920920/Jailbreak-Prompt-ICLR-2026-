# Closest Work and Contribution Matrix v2

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This matrix identifies the papers most likely to be cited by a skeptical reviewer against the proposed jailbreak causal-topology contribution. The objective is not to claim that each ingredient is new. The objective is to isolate the narrow conjunction that remains defensible after accounting for prior token attribution, suffix compression, prompt-feature causality, internal causal explanation, attack-skill decomposition, and generic feature-interaction literature.

## Proposed contribution under review

> Define and measure a robust minimal-recovery hypergraph for each already-successful jailbreak using stable behavioral interventions, multiple neutralizers, payload and capability controls, and exact or contract-exact minimality; then compare singleton, interactive, redundant, multiple-pathway, distributed, and capability-confounded topologies across semantic-readable, fluent-optimized, and non-fluent optimized attack regimes.

## A. Directly closest jailbreak-specific work

| Work | Main object and contribution | What it already occupies | What it does not establish | Required distinction for this project |
|---|---|---|---|---|
| **On the Role of Attention Heads in Large Language Model Safety** — SHIPs/SAHARA, ICLR 2025, arXiv:2410.13708 | Ablates individual attention heads; SHIPs uses output-distribution KL for a harmful query; dataset-level SHIPs and SAHARA greedily find head groups whose ablation degrades safety. | Intervention-based safety attribution; group search; KL-based importance; collaborative components. | Input-editable prompt units; successful-jailbreak-specific explanation; minimal set proof; payload preservation; capability-confound separation; cross-regime input topology. | Treat SHIPs/SAHARA as conceptual inspiration and a greedy baseline only. Do not claim novelty from transferring KL and greedy selection from heads to tokens. |
| **Token Highlighter: Inspecting and Mitigating Jailbreak Prompts for LLMs** — arXiv:2412.18171 | Defines an affirmation loss, ranks tokens by embedding-gradient norm, and softly shrinks top-ranked token embeddings. Evaluates GCG, AutoDAN, PAIR, TAP, Manyshot, and AIM. | Jailbreak-critical token localization; token embedding intervention; refusal-oriented defense across token- and prompt-level attacks. | Exact minimality; higher-order token interactions; all minimal sets; necessity versus sufficiency; robust agreement across neutralizers; instance-level causal topology. | Token Highlighter must be a core baseline. The new result must show when singleton gradients fail, which higher-order cut sets exist, and whether those sets are robust rather than merely high-saliency. |
| **Mask-GCG: Are All Tokens in Adversarial Suffixes Necessary for Jailbreak Attacks?** — arXiv:2509.06350 | Jointly optimizes GCG-family suffix tokens and learnable masks, prunes low-mask tokens, and measures suffix compression while retaining attack loss and ASR. Reports that most suffix tokens are impactful and a minority are redundant. | Token redundancy and compression in GCG, I-GCG, and AmpleGCG; learnable mask importance; attack-efficiency improvement. | Post-hoc exact behavioral cut sets on frozen successful prompts; higher-order interactions; multiple minimal pathways; refusal recovery; capability controls; semantic/fluent/non-fluent regime comparison. | The project cannot claim “first to ask whether all adversarial tokens are needed.” It must distinguish optimization-time compression from frozen-instance behavioral minimal-recovery topology. Mask-GCG masks are a Regime-U baseline. |
| **What Features in Prompts Jailbreak LLMs? Investigating the Mechanisms Behind Attacks** — arXiv:2411.03343 | Builds 10,800 attempts from 35 attacks, probes prompt-token latent representations, finds nonlinear and attack-specific features, and causally steers hidden states. | Broad attack coverage; evidence that jailbreak features are nonlinear and often attack-specific; prompt-side latent causal control. | Human-editable input subsets; exact instance-level minimality; token/block removal topology; multiple neutralizers; direct comparison of semantic and optimized input causal structures. | Cross-regime results should explicitly test its non-universality finding at the **input-intervention topology** level rather than at latent-probe transfer level. |
| **A Causal Perspective for Enhancing Jailbreak Attack and Defense / Causal Analyst** — NDSS 2026, arXiv:2602.04893 | Uses 35k attempts, 37 human-readable prompt features, LLM encoding, and GNN causal discovery to infer feature-level causal graphs; applies them to attack enhancement and guardrail advice. | Causal language for interpretable prompt features; large-scale template-level feature analysis; direct-cause claims over human-readable attributes. | Instance-specific counterfactual minimal sets; exact interventions on original token/block units; strict subset minimality; cross-regime non-fluent token structure. | Avoid “first causal analysis of jailbreak prompts.” Distinguish observational/learned feature-level causal graphs from direct per-instance behavioral interventions and minimal cut-set hypergraphs. |
| **Minimal, Local, Causal Explanations for Jailbreak Success in LLMs / LOCA** — COLM 2026, arXiv:2605.00123 | Finds a minimal set of interpretable intermediate-representation changes that causally induces refusal for a specific successful jailbreak. Evaluates Gemma, Llama, and Qwen. | Local, minimal, causal explanation of individual jailbreak success; refusal restoration; sparse intervention sets. | Input-level editable units; exact prompt-token or block minimality; semantic versus optimized attack topology; multiple minimal pathways over input components. | Do not claim “first minimal local causal explanation of jailbreak success.” The new gap is **input-side**, regime-comparative, and topology/hypergraph based rather than intermediate-representation based. |
| **Adversarial Déjà Vu: Jailbreak Dictionary Learning for Stronger Generalization to Unseen Attacks** — ICLR 2026 | Extracts human-readable adversarial skill primitives from 32 attack papers, represents unseen attacks as sparse skill compositions, and trains on skill compositions for robust defense. | Sparse compositional view of attacks; human-readable skill dictionaries; cross-attack decomposition and generalization. | Whether a skill appearing in a prompt is behaviorally necessary for a particular model-instance; exact minimal cut sets; non-fluent token blocks; recovery under direct neutralization. | Skill primitives can inform Regime-S unit construction, but dictionary inclusion is not causal necessity. Our evidence must come from target-model interventions. |
| **Attention Slipping: A Mechanistic Understanding of Jailbreak Attacks and Defenses** — arXiv:2507.04365 | Reports a cross-attack phenomenon in which attention to the unsafe request decreases during jailbreaks; proposes attention sharpening. | Candidate universal internal mechanism across gradient, prompt-template, and in-context attacks. | Minimal input recovery sets and their topology; necessity of specific input units; exact cross-regime intervention comparison. | The paper should test whether diverse surface topologies coexist with a shared internal attention phenomenon rather than claim the first cross-regime mechanism. |
| **Not All Tokens Are Created Equal: Query-Efficient Jailbreak Fuzzing / TriageFuzz** — arXiv:2603.23269 | Estimates token contributions to refusal using a surrogate and prioritizes token-aware mutations for query-efficient attack fuzzing. | Token-level refusal contribution; cross-model token tendency; efficient attack search. | Post-hoc causal explanation; minimal recovery hypergraphs; capability-preserving neutralization; higher-order interaction ground truth. | Use as a candidate-ranking/search baseline, not as evidence that token contribution equals causal necessity. |

## B. Localization and detection work that can be confused with the project

| Work | Contribution | Overlap risk | Distinction required |
|---|---|---|---|
| **PromptLocate: Localizing Prompt Injection Attacks** — arXiv:2510.12252 | Segments contaminated data and localizes injected instructions and injected data for prompt injection forensics. | Uses the word “localization” and identifies malicious input regions. | Different threat model: trusted command versus injected untrusted data. It recovers attack location, not minimal causal jailbreak-enabling structure under safety-refusal interventions. |
| **Detecting Fluent Optimization-Based Adversarial Prompts via Sequential Entropy Changes / CPD Online** — ICML 2026, arXiv:2605.19966 | Uses entropy change-point detection to detect optimization-based suffixes and localize their onset. | Covers GCG, AutoDAN, AdvPrompter and reports localization inside adversarial suffixes. | Onset detection and statistical anomaly localization are not behavioral necessity or minimality. CPD must be a suffix-onset baseline for Regimes F/U. |
| **SlotGCG: Exploiting Positional Vulnerability in LLMs** — ICLR 2026 | Scores insertion slots and optimizes adversarial tokens at vulnerable positions. | Shows that position is itself a causal-looking attack axis. | The causal-topology protocol must preserve or explicitly manipulate position. Deletion-only token ablation would be invalid for position-sensitive attacks. |

## C. Generic interpretability work that blocks broad novelty claims

| Work | Main contribution | Implication for novelty |
|---|---|---|
| **Sufficient Input Subsets** — AISTATS 2019 | Finds minimal feature subsets whose observed values are sufficient for the same prediction, using backward selection. | Minimal input subsets are not new. The jailbreak contribution must arise from safety-specific outcomes, removal/keep-only distinction, robust neutralizers, stable generation, capability controls, and cross-regime topology. |
| **Shapley-Taylor Interaction Index** and later language-model interaction analyses | Provides axiomatic attribution to higher-order feature interactions; applied to linguistic token interactions. | Pairwise or higher-order token interaction formulas are not new. Shapley-Taylor should be a baseline; the new object is exact stable recovery-cut structure under jailbreak-specific interventions. |
| **TokenSHAP / TokenShapley** | Attributes LLM outputs or context contributions to tokens using Shapley approximations. | Token importance and interaction-aware attribution are occupied. The project must evaluate whether attribution recovers the exact minimal-recovery hypergraph. |

## D. What the SHIPs-inspired draft gets right

The draft correctly emphasizes:

1. intervention rather than saliency alone;
2. refusal recovery direction rather than undirected output change;
3. token-set interactions rather than singleton rankings;
4. strict-subset minimality;
5. multiple neutralization methods;
6. linkage from broad spans to finer units;
7. compression of apparent prompt complexity into causal complexity.

These are retained.

## E. Corrections required before using the draft in a paper

### E.1 The multiplicative J-SHIPs score is diagnostic, not causal ground truth

Multiplying KL divergence by refusal-probability recovery is sensitive to scale, saturation, and off-topic changes. The primary outcome must be stable substantive harmful assistance versus safe recovery, with capability-confounded and abstention states explicitly separated.

### E.2 Full-output KL is underspecified

The exact distribution must be defined. A next-token KL, first-k-step divergence, refusal-token logit statistic, and sequence-level behavior label measure different constructs. The project should keep distributional statistics secondary.

### E.3 The interaction equation needs the baseline

For a directional set function \(F\), pair interaction should use

\[
F(\{i,j\})-F(\{i\})-F(\{j\})+F(\varnothing),
\]

or its conditional version given an existing set. More importantly, strict-set minimality provides stronger discrete interaction evidence than a scalar interaction score.

### E.4 Removal sets are not enabling sets

A minimal set whose neutralization restores safety is a minimal recovery/cut set. A minimal enabling or sufficient set requires keep-only experiments. The paper must not conflate them.

### E.5 Mean-embedding replacement is not automatically human-readable

Embedding replacement can be a position-preserving robustness intervention, but it is off manifold. Human-editable claims require text-level interventions or clearly separated evidence.

### E.6 Compression denominator must exclude the immutable payload

Use attack-added units or attack-token coverage, not total prompt tokens including the harmful goal. Report tokenizer-specific tokens and, where possible, tokenizer-independent character/byte coverage.

### E.7 Greedy SAHARA-style search cannot define the oracle

Pure interactions and redundant pathways can make all singleton marginal gains uninformative. Greedy search is a baseline to be evaluated against exact or contract-exact ground truth.

### E.8 Effect retention needs a keep-only definition

If \(S^*\) denotes tokens neutralized to break the attack, `ASR(S*)` is undefined as a compressed attack. Effect retention must be computed on a separately defined keep-only sufficient set or complementary retained scaffold.

## F. Candidate contribution stack

The paper is strongest if it has the following ordered contributions.

### Contribution 1 — Formal object

A **robust minimal-recovery hypergraph** over regime-specific input units, with explicit definitions for minimal recovery order, multiple minimal sets, higher-order interaction, redundant pathways, budget-relative distributedness, neutralizer stability, and capability confounding.

### Contribution 2 — Cross-regime empirical law

A controlled comparison of this topology across:

- semantic-readable attacks;
- fluent optimized attacks;
- non-fluent optimized attacks;
- at least two attack families per regime;
- at least two target-model families in confirmatory experiments.

The scientific result may be regime-dependent topology, shared sparse topology, or family/model-specific topology. It must not be predetermined.

### Contribution 3 — Robust causal protocol

A payload-preserving, multi-neutralizer, multi-seed intervention protocol with a validated abstaining evaluator panel and explicit capability controls.

### Contribution 4 — Approximate search, only if justified

A SHIPs-inspired, group-testing, hierarchical, or optional wavelet search method that is evaluated against exact/contract-exact hypergraphs. It remains secondary unless it establishes a clear query-efficiency versus recovery-accuracy Pareto improvement.

## G. Minimum result needed for a strong paper

The following result would be genuinely nontrivial:

1. stable successful attacks exist in all three regimes;
2. leave-one-out or Token Highlighter saliency misses a meaningful fraction of pair/higher-order recovery sets;
3. multiple minimal pathways or distributed structures occur repeatedly rather than as isolated anecdotes;
4. causal topology differs systematically across regimes or reveals a surprising common sparse structure;
5. the pattern replicates across at least two model families and multiple harm categories;
6. results survive two neutralizers and capability controls;
7. attribution, Mask-GCG masks, and CPD onset scores are quantitatively compared with exact recovery hypergraphs.

## H. Result patterns that would make the paper weak

- Every semantic attack is broken by deleting an obvious refusal-suppression sentence.
- Every optimized suffix behaves like a single contiguous block with no nontrivial internal structure.
- Minimal sets change drastically across neutralizers or seeds.
- Most apparent recovery is incoherence or truncation.
- Only one attack family or one target model supplies eligible instances.
- The proposed score ranks tokens but no exact minimality or interaction evidence is produced.
- The cross-regime claim is made from incompatible intervention units without normalized coverage and position controls.

## I. Current claim boundary

At this point, the project has a defensible formal gap but no cross-regime empirical result. The existing same-model persona analysis, natural-language calibration, AgentHarm negative feasibility, evaluator-panel E1 work, and legacy span pilots are development evidence only. Stage A, prior held-out data, the causal oracle, and wavelet remain closed until the evaluator and cross-regime attack contracts pass their predeclared gates.