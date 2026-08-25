# Jailbreak Attack-Regime Scope v2

Date: 2026-08-24 (Asia/Seoul)

## Executive decision

The main paper will no longer be framed as causal localization only for
human-readable DAN/AIM-style wrappers. The revised scientific question is:

> Across semantic-readable, fluent-optimized, and non-fluent optimized
> single-turn jailbreaks, do successful attacks depend on compact causal input
> components, higher-order interactions, redundant pathways, or distributed
> prompt structure?

This is a scope reset before Stage A, held-out evaluation, the causal oracle,
and wavelet are opened. The previous human-readable feasibility contract remains
an immutable predecessor and is not silently promoted into cross-regime evidence.

## Why the reset is necessary

Recent top-venue work has moved beyond a simple manual-versus-gibberish split.
The relevant progression is:

1. optimization-based non-fluent suffixes such as GCG and I-GCG;
2. fluent and human-readable optimized attacks such as AutoDAN and AdvPrompter;
3. automatic strategy discovery and compositional skill representations such as
   AutoDAN-Turbo and Adversarial Deja Vu;
4. position-aware optimization such as SlotGCG;
5. evidence that apparently unnatural language can carry latent features for
   language models.

A DAN/AIM-only study could still support a narrow semantic-jailbreak paper, but
it would not justify a broad claim about jailbreak causal structure. The new
scope therefore compares causal topology across attack regimes rather than
assuming that human-readable spans are the universal object.

## Main empirical scope

The main study remains:

- text-only;
- single-turn;
- open-weight target models;
- an explicit harmful goal preserved exactly once in every attacked prompt;
- behavioral counterfactual interventions on already-successful attacks;
- no model-internal circuit claim;
- no claim that generating a stronger jailbreak is the contribution.

### Regime S: semantic-readable attacks

Attacks whose strategy and functional components are interpretable to a human.
Examples include persona/role-play, refusal suppression, affirmative prefills,
few-shot demonstrations, fictional framing, persuasion, and compositional
strategy wrappers.

Primary intervention hierarchy:

1. typed strategy node;
2. sentence or newline unit;
3. exhaustive contiguous character/token span inside a localized node.

### Regime F: fluent optimized attacks

Attacks generated or optimized automatically while remaining grammatical and
human-readable. Candidate families include AutoDAN, AdvPrompter, and
strategy-discovery attacks whose final prompt is fluent.

Primary intervention hierarchy:

1. provenance-preserving generated clause or strategy block;
2. sentence or clause;
3. contiguous token block.

A fluent attack is not treated as equivalent to a hand-written semantic attack;
its generation provenance and optimization objective remain explicit factors.

### Regime U: non-fluent optimized or latent-language attacks

Discrete optimized token sequences that are difficult for humans to interpret,
including GCG/I-GCG-style suffixes and position-aware variants such as SlotGCG.

Primary intervention hierarchy:

1. fixed contiguous token blocks defined before outcomes are observed;
2. recursive sub-blocks;
3. contiguous token intervals.

The paper will claim exactness only with respect to the frozen intervention
vocabulary. It will not claim an exhaustive power-set oracle over all individual
tokens when that is computationally infeasible.

## Explicitly excluded from the main paper

The following require different outcome or intervention objects and are excluded
from the main confirmatory scope:

- trigger-only strings with no explicit harmful goal;
- soft prompts or continuous embedding-only attacks;
- decoding-time attacks that modify logits or use auxiliary unsafe models;
- multi-turn, many-shot, or conversational escalation attacks;
- multimodal attacks;
- agent/tool trajectories;
- indirect prompt injection and retrieved-document attacks.

A trigger-only unnatural-language experiment may appear only as a clearly
labeled boundary or appendix study. Multi-turn attacks may appear only as a small
external-validity extension after the single-turn cross-regime result is stable.

## Primary hypotheses

### H1: regime-dependent causal topology

Semantic-readable attacks will more often admit compact human-interpretable
minimal sets, whereas non-fluent optimized attacks will more often exhibit
block-level distributed or redundant structure. Fluent optimized attacks may
occupy an intermediate regime.

### H2: shared sparse structure

An alternative result is that all three regimes contain compact minimal causal
sets despite radically different surface forms. This would support a common
sparse enabling-structure hypothesis.

### H3: family-specific topology

A third valid outcome is that causal topology is primarily attack-family- and
model-specific. This would argue against treating jailbreaks as one homogeneous
threat class.

All three outcomes are publishable only if supported by stable successful
attacks, exact intervention evidence, capability controls, and cross-model
replication.

## Measurement path

The standards-derived, cross-model, abstaining evaluator panel remains the
measurement-development path. It must be externally validated before Stage A.
The same-model persona study remains sensitivity evidence only and contributes
no production votes.

The panel must separate:

- refusal and safe redirection;
- behavior-specific compliance;
- actionability and harmful utility;
- capability-confounded or malformed outputs;
- abstention.

## Required pre-output protocol before attack execution

A new cross-regime experiment contract must be frozen before any new Stage A
outputs are inspected. It must specify:

1. at least two attack families per regime;
2. official source repository, immutable revision, and artifact hash;
3. whether attacks are regenerated or drawn from frozen official artifacts;
4. payload preservation and insertion-position rules;
5. target models and tokenizer versions;
6. seeds and decoding configuration;
7. success and stability rules;
8. regime-specific intervention vocabulary;
9. matched random and non-causal controls;
10. GO/NARROW/STOP thresholds by regime and overall;
11. compute and query budgets;
12. held-out and confirmatory data boundaries.

## Minimum main-paper evidence

A broad cross-regime claim requires all of the following:

- all three regimes represented;
- at least two attack families in each represented regime;
- at least two target-model families in confirmatory experiments;
- stable direct-safe / attacked-harmful pairs;
- two neutralization operators where semantically meaningful;
- capability-confound controls;
- exact or contract-exact minimality;
- leave-one-out, random same-size, and attribution/localization baselines;
- reporting of single, interactive, multiple-minimal-set, distributed, and
  capability-confounded outcomes;
- uncertainty intervals and category-stratified results.

## Position of wavelet search

Wavelet is not the paper identity. It remains closed until cross-regime exact
or contract-exact ground truth exists. It is retained only if it improves the
query-efficiency/accuracy Pareto frontier over a matched non-wavelet hierarchy,
greedy elimination, random search, group testing, and suffix-onset detectors.

## Immediate sequence

1. Finish evaluator-panel E1 component validation and external risk-coverage
   validation.
2. Conduct an E0 provenance and feasibility audit of candidate attack families
   without generating target-model outcomes.
3. Freeze the cross-regime attack matrix and intervention vocabularies.
4. Run a small development-only signal screen balanced across S, F, and U.
5. Apply predeclared GO/NARROW/STOP rules.
6. Open exact causal experiments only for stable successful pairs.
7. Freeze a fresh confirmatory contract for paper-valid evidence.

## Current sealed boundary

At this decision point:

- the earlier DAN/AIM-only Stage A is not opened;
- prior Gate 1 evaluation and Gate 2 held-out remain sealed;
- no cross-regime target-model outcomes have been generated;
- the causal oracle remains closed;
- wavelet remains closed;
- this document is a scope decision, not an empirical result.
