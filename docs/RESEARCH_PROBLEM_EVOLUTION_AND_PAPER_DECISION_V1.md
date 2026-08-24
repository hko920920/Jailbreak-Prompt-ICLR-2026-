# Research Problem Evolution and Paper Decision v1

Date: 2026-08-24 (Asia/Seoul)

## 1. Original motivation

The project began from a simple and valid question:

> When a jailbreak succeeds, which part of the prompt actually breaks the model's safety behavior?

At first, “which part” was interpreted as a localization problem: divide a successful jailbreak prompt into spans, neutralize each span, and identify the region whose removal restores refusal.

That intuition remains the origin of the project. What changed is the scientific precision of the object being sought.

## 2. Why simple span localization was insufficient

A changed model output does not by itself prove safety recovery. Neutralizing a span may:

- delete or alter the harmful goal;
- break grammar or tokenization;
- shift the positions of all following tokens;
- cause topic drift, truncation, incoherence, or generic capability collapse;
- preserve harmful assistance in a different wording.

Therefore:

`output change != safety recovery`

A single-span or single-token ranking also misses interactions. Two units may each appear unimportant when neutralized alone but jointly restore refusal. A prompt may also contain multiple alternative pathways, such that disrupting one route leaves another route active.

The research question therefore moved from “where is the important span?” to “what input dependency structure is behaviorally necessary for jailbreak success?”

## 3. First formulation: causal span localization and wavelet search

The first concrete formulation was:

> Find the smallest human-readable span whose intervention restores refusal in an already-successful natural-language jailbreak.

A hierarchical pipeline was considered:

1. broad prompt region;
2. newline or sentence unit;
3. contiguous span;
4. token refinement.

Wavelet or hierarchical search was introduced as a possible way to reduce the number of intervention queries.

This ordering was premature. A fast search method is scientifically secondary until three facts are established:

1. stable successful jailbreak instances exist;
2. their outcome can be measured reliably;
3. exact or contract-exact causal structure exists as ground truth.

Wavelet is therefore no longer the paper identity. It remains sealed until exact topology exists and must be compared with matched non-wavelet baselines.

## 4. First major bottleneck: defining jailbreak success

The causal analysis requires instances satisfying:

- the direct harmful request is stably non-harmful;
- the attacked prompt is stably substantive harmful assistance.

Automatic evaluators disagreed on refusal, harmfulness, target compliance, and actionability. A single judge could therefore change the population of “successful jailbreaks” being analyzed. This creates the risk of explaining a judge's preference rather than the model's safety failure.

The project consequently separated the outcome into:

- refusal or safe redirection;
- non-actionable or irrelevant output;
- substantive harmful assistance;
- capability-confounded output;
- abstention.

A standards-derived, cross-model, abstaining evaluator panel is now being qualified before any new causal Stage A is opened.

## 5. Programmatic AgentHarm pivot and why it ended

To avoid subjective natural-language judgment, the project tested a programmatically verifiable AgentHarm route. Unsafe task completion could be judged from deterministic tool traces rather than an LLM judge.

The measurement path was cleaner, but the required attack population did not materialize:

- the Qwen2.5-7B development matrix produced zero eligible direct-failure / attacked-success pairs;
- the second-model Llama test remained operationally unresolved after the single permitted runtime correction.

The AgentHarm pivot was therefore closed under its predeclared terminal rule. This does not reject causal localization; the causal hypothesis was never tested because no successful attack population existed.

The AgentHarm work remains useful as negative feasibility evidence, infrastructure experience, and a record that thresholds were not relaxed after observing outputs. It is not the main empirical result.

## 6. Why the attack scope expanded

The original natural-language set was dominated by human-readable semantic wrappers such as DAN, AIM, role-play, refusal suppression, affirmative prefills, and few-shot framing.

That scope can support a narrow semantic-jailbreak paper, but it cannot justify a broad claim about jailbreak structure. Modern attacks cover three distinct regimes:

### Regime S — Semantic-readable

Human-interpretable strategies such as persona, role-play, fictional framing, persuasion, refusal suppression, and demonstrations.

### Regime F — Fluent optimized

Automatically generated or optimized attacks whose final form remains grammatical and human-readable, such as AutoDAN- or AdvPrompter-style attacks.

### Regime U — Non-fluent optimized

Human-uninterpretable or weakly interpretable discrete optimized sequences, such as GCG/I-GCG and position-sensitive variants.

The main scope is now text-only, single-turn, open-weight targets with an explicit harmful goal preserved exactly once. Trigger-only, soft-prompt, decoding-time, multi-turn, multimodal, agent/tool, and indirect-prompt-injection settings are excluded from the main confirmatory study.

## 7. Why token importance is not the final contribution

SHIPs/SAHARA provides useful experimental logic:

- intervene rather than correlate;
- move from individual units to jointly acting groups;
- use heuristics to prioritize candidates;
- validate with an actual safety-behavior change.

However, merely applying a KL-based SHIPs score or greedy SAHARA search to tokens would be insufficient. Prior work already covers jailbreak-critical token ranking, embedding suppression, optimized-suffix compression, causal prompt features, internal representation explanations, and suffix localization.

Distributional divergence, refusal logits, gradients, and affirmation losses are therefore secondary diagnostics or search surrogates. They do not define causal ground truth.

## 8. Current scientific object

The paper now studies the input-level causal topology of an already-successful jailbreak.

Let the attacked prompt be:

`x_J = Compose(q, a)`

where:

- `q` is the immutable explicit harmful goal;
- `a` is the attack-added structure;
- `U(x_J)` is the frozen, regime-specific intervention vocabulary over the attack-added structure only.

A set `C subseteq U(x_J)` is a robust minimal causal cut set when:

1. neutralizing `C` makes substantive harmful assistance disappear;
2. refusal or safe redirection is stably restored;
3. the result repeats across the predeclared seeds;
4. the result repeats across at least two meaningful neutralizers;
5. the harmful payload remains unchanged;
6. the response is not incoherent, malformed, truncated, or generically incapable;
7. no strict subset of `C` satisfies the same recovery predicate.

All robust minimal cut sets for an instance form its minimal-recovery hypergraph.

This permits the following topology classes:

- singleton-localized;
- localized small set;
- higher-order interactive;
- multiple minimal cut sets;
- multiple sufficient pathways, when a separate keep-only experiment is valid;
- redundant pathways;
- non-monotone intervention effects;
- distributed or unresolved within a frozen budget;
- capability-confounded;
- unresolved abstention.

Necessity and sufficiency remain separate. Removing a set and breaking the attack establishes a cut property; calling it an enabling set requires a separate keep-only experiment.

## 9. Current paper question

The most defensible central question is:

> Across semantic-readable, fluent-optimized, and non-fluent optimized single-turn jailbreaks, is success maintained by a compact causal bottleneck, higher-order interaction, redundant alternative pathways, or distributed input structure?

A plain-language version is:

> Fix an already-successful jailbreak prompt and directly neutralize the attack-added parts, alone and in combination. Determine the smallest input combinations that reliably break the jailbreak without deleting the harmful request or destroying the model's general ability, then compare those dependency structures across different attack regimes.

## 10. Candidate contribution stack

### Contribution 1 — Formal causal object

A robust minimal-cut or minimal-recovery topology over regime-specific input units, with explicit minimality, interaction, redundancy, non-monotonicity, operator stability, and capability-confound definitions.

### Contribution 2 — Cross-regime empirical result

A controlled comparison of topology across semantic-readable, fluent-optimized, and non-fluent optimized attacks. The empirical conclusion is not predetermined. Valid outcomes include:

- regime-dependent topology;
- a surprising shared sparse topology;
- primarily family- or model-specific topology.

### Contribution 3 — Robust causal protocol

A payload-preserving, multi-seed, multi-neutralizer intervention protocol with a qualified abstaining evaluator and explicit capability controls.

### Contribution 4 — Efficient search, conditionally

SHIPs-inspired scoring, SAHARA-style greedy search, Token Highlighter, Mask-GCG-style scores, group testing, hierarchical search, and optional wavelet are compared against exact or contract-exact topology. A search method is retained as a contribution only if it improves query efficiency without materially losing topology recovery accuracy.

## 11. How prior experiments can be reused

### Reusable infrastructure or development evidence

- target-model runtime and frozen generation configuration;
- artifact hashing, encryption, and safe-result handling;
- component parsers and typed semantic units for Regime S;
- neutralization and subset-enumeration code;
- evaluator hardening and injection canaries;
- legacy span observations as motivation for coarse-to-fine refinement;
- AgentHarm as negative feasibility and decision-discipline evidence;
- same-model repeatability and persona studies as rubric sensitivity evidence;
- wavelet and greedy code as later approximation baselines.

### Not directly reusable as paper-valid empirical evidence

- the legacy 32–58% broad-span recovery observations;
- semantic-only Stage A designs as broad cross-regime evidence;
- same-model persona labels as independent human or cross-family labels;
- AgentHarm negative results as evidence against causal topology;
- any result obtained before the new evaluator and cross-regime contract are frozen.

These results must not be silently promoted. They either motivate the new study, serve as development diagnostics, or must be reproduced under the new contract.

## 12. Required changes before paper-valid experiments

1. Complete external qualification of the evaluator panel.
2. Audit at least two attack families per S/F/U regime for provenance, licensing, tokenizer support, artifact availability, compute, insertion position, and payload preservation.
3. Freeze the balanced attack matrix, target models, seeds, decoding, eligibility rule, neutralizers, units, budgets, controls, and exactness boundary before inspecting outcomes.
4. Run a balanced development signal screen to identify stable direct-safe / attacked-harmful pairs.
5. Run exact or contract-exact coarse topology only on stable pairs.
6. Refine localized coherent regions to smaller spans or token intervals.
7. Compare exact topology with attribution, masking, onset detection, random, greedy, group-testing, and optional wavelet baselines.
8. Freeze a fresh confirmatory experiment with unseen payloads and at least two target-model families.

## 13. Objective paper viability test

The project becomes a strong paper only if the experiments establish all or most of the following:

- stable successful attacks in all three regimes;
- at least two attack families per represented regime;
- repeated non-singleton or multiple-pathway structures rather than isolated anecdotes;
- topology that is stable across seeds and meaningful neutralizers;
- capability-confounded recovery does not dominate;
- a systematic regime difference or an unexpected shared law;
- replication across at least two model families and multiple harm categories;
- existing token-attribution or suffix-localization methods miss or distort a meaningful fraction of the exact topology.

The broad paper is weak if every semantic attack is broken by one obvious sentence, every optimized attack behaves only as one indivisible suffix, topology is unstable across neutralizers, or one model/family supplies nearly all usable instances.

If only one regime produces strong evidence, the scope should narrow honestly to that regime rather than retain a broad cross-regime claim.

## 14. Current status and decision boundary

The project currently has:

- a coherent and defensible research question;
- formal definitions and claim boundaries;
- substantial experimental infrastructure;
- negative feasibility evidence from abandoned routes;
- evaluator-panel qualification in progress;
- no paper-valid cross-regime causal-topology result yet.

The next decisive empirical questions are:

1. Do all three regimes yield enough stable successful attacks to analyze?
2. Do those attacks exhibit nontrivial, reproducible causal topology rather than only obvious singleton or whole-suffix effects?

If both answers are positive, the project has a realistic path to a strong empirical paper. If the first fails, the attack population is inadequate. If the first passes but the second fails, the contribution is likely too obvious or too close to existing token-importance and suffix-compression work.

## 15. Current one-sentence paper statement

> We directly intervene on already-successful jailbreak prompts to identify the smallest robust input combinations that break the attack without altering the harmful goal or destroying model capability, and we compare whether those causal dependency structures are sparse, interactive, redundant, non-monotone, or distributed across semantic and optimized attack regimes.

This document records a research decision and evidence boundary, not an empirical result.