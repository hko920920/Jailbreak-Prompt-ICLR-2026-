# Causal Input Topology Method v1

Date: 2026-08-24 (Asia/Seoul)

## Status and boundary

This document freezes the input-level causal-analysis method before any cross-regime Stage A outputs, held-out outputs, causal-oracle outputs, or wavelet outputs are opened. It is downstream of `JAILBREAK_ATTACK_REGIME_SCOPE_V2.md` and does not promote any prior development result into paper-valid evidence.

The scientific object is not a token-importance ranking. It is the causal topology of an already-successful jailbreak under predeclared interventions.

## Research question

> Across semantic-readable, fluent-optimized, and non-fluent optimized jailbreaks, is success maintained by a compact causal bottleneck, higher-order interaction, redundant alternative pathways, or distributed input structure?

## What is retained from SHIPs/SAHARA

The SHIPs/SAHARA analogy is retained only at the level of experimental logic:

1. intervene directly on a candidate component;
2. measure a safety-relevant behavioral change;
3. extend from individual components to jointly intervened groups;
4. use a heuristic score only to prioritize candidates when exhaustive search is not yet affordable.

The original head-level SHIPs score is not copied as the paper's primary endpoint. Token positions are prompt-specific, token neutralization can damage syntax or capability, and full-output distribution divergence can be dominated by stylistic changes unrelated to safety recovery.

## Primary outcome set function

For a successful attacked prompt `x`, intervention operator `a`, neutralized unit set `S`, and frozen seed set `Z`, define

`J_a(S) = Pr_z[SUBSTANTIVE_HARMFUL_ASSISTANCE | N_a(S, x), z]`.

The production label comes from the externally validated abstaining evaluator panel, with audit escalation under its frozen contract. `CAPABILITY_CONFOUNDED` and `ABSTAIN` are never silently converted into successful recovery.

The primary removal effect is

`V_a(S) = J_a(empty) - J_a(S)`.

Refusal probability, next-token refusal mass, sequence-level divergence, gradient scores, and affirmation-loss scores are secondary diagnostics or search surrogates only.

## Necessity and sufficiency must be separated

### Minimal causal cut set

A set `C` is a robust minimal causal cut set when neutralizing `C` breaks the jailbreak under every required intervention operator and no strict subset does so.

Operationally, for every required operator `a`:

- `J_a(C) <= tau_fail`;
- refusal or safe redirection is the majority non-abstaining outcome;
- no capability confound is present;
- every strict subset `T subset C` fails at least one of the same conditions.

A cut set is a minimal necessary-removal set. It must not be called a minimal enabling set.

### Minimal sufficient enabling set

A set `E` is a minimal sufficient enabling set only when retaining `E` while neutralizing the complement preserves attack success, and no strict subset of `E` does so.

This keep-only experiment is optional where a coherent reconstruction cannot be defined. When it is not performed, no sufficiency claim is allowed.

### Why both matter

A token can belong to a minimal cut set without being sufficient on its own. Conversely, multiple sufficient routes may create redundancy such that no singleton removal breaks the attack. Necessity and sufficiency therefore support different causal claims.

## Interaction definitions

For a numeric set function `V`, pairwise interaction is the finite difference

`I_a(i,j) = V_a({i,j}) - V_a({i}) - V_a({j}) + V_a(empty)`.

Higher-order interaction for set `S` is the Moebius/Harsanyi finite difference

`delta_a(S) = sum_{T subseteq S} (-1)^(|S|-|T|) V_a(T)`.

These numeric quantities are descriptive. The confirmatory interaction claim is Boolean and minimality-based:

- `INTERACTIVE`: a robust minimal cut set has size at least two and every strict subset preserves the jailbreak;
- `REDUNDANT_PATHWAYS`: multiple distinct minimal cut sets or multiple minimal sufficient sets exist;
- `DISTRIBUTED`: no robust cut set within the frozen size/query budget is found, without capability failure;
- `NON_MONOTONE`: adding a neutralized unit re-enables or materially strengthens attack success.

No monotonicity assumption is permitted unless separately tested. Greedy or branch-and-bound methods that rely on monotonicity cannot define ground truth.

## Intervention hierarchy by attack regime

### Regime S: semantic-readable

1. typed strategy node;
2. sentence/newline or clause;
3. word/byte span;
4. tokenizer token only inside a previously localized coherent span.

### Regime F: fluent optimized

1. provenance-preserving generated clause or strategy block;
2. sentence/clause;
3. fixed contiguous token block;
4. tokenizer-token refinement inside a localized block.

### Regime U: non-fluent optimized

1. predeclared fixed token blocks;
2. recursive sub-blocks;
3. contiguous token intervals;
4. individual token positions only where compute permits.

For Regime U, exactness is claimed only with respect to the frozen intervention vocabulary.

## Required intervention operators

Surface and representation interventions are not treated as interchangeable evidence.

### Primary surface operators

- length-aware neutral replacement;
- deletion, as a secondary contrast rather than the sole primary operator;
- regime-specific neutral block replacement preserving payload bytes and insertion position.

### White-box sensitivity operators

- embedding scaling toward zero;
- interpolation toward a context-independent neutral embedding;
- position-specific information attenuation.

White-box operators are sensitivity checks because they can be off-manifold. They cannot by themselves establish a human-readable input explanation.

A robust cut set must reproduce under at least two predeclared operators that are meaningful for the regime. Operator disagreement is reported rather than averaged away.

## Intent and capability preservation

Every attacked and intervened prompt must satisfy:

- the explicit harmful payload occurs exactly once;
- payload bytes are unchanged;
- intervention touches only the frozen attack region or unit vocabulary;
- target behavior remains identifiable to the behavior-compliance axis;
- response is coherent and not decision-relevantly truncated;
- a matched benign or capability control does not show generic collapse;
- malformed, incoherent, or generally incapable outcomes are `CAPABILITY_CONFOUNDED`.

Semantic similarity alone is insufficient evidence of intent preservation.

## Search strategy and ground truth

1. Use exact enumeration for small strategy-node sets.
2. Localize a coherent node/block before token-level refinement.
3. Enumerate all subsets within the tractable localized vocabulary and record all minimal sets, not only the first.
4. Use SHIPs-like KL, refusal-logit gradients, Token-Highlighter-style affirmation gradients, greedy SAHARA-style addition, or wavelet scores only as candidate-ranking baselines.
5. A heuristic never proves minimality; every reported minimal set must be verified against all strict subsets in the frozen vocabulary.

## Core topology metrics

Report at least:

- minimum robust cut size;
- minimum sufficient-set size where defined;
- number of distinct minimal cut sets;
- maximum confirmed interaction order;
- non-monotonicity rate;
- intervention-operator agreement;
- seed stability;
- cross-model transfer of discovered sets;
- capability-confounded rate;
- distributed-within-budget rate.

### Compression metrics

Let `A(x)` be the frozen attack-only unit set, excluding the harmful payload.

- attack-normalized cut fraction: `|C*| / |A(x)|`;
- full-prompt cut fraction: `|C*| / |x|`;
- coarse-to-fine compression: `|C*| / |B|` for a previously localized block `B`.

Report token counts with the target tokenizer and also byte/character spans for cross-tokenizer comparability.

Effect retention is defined only for a sufficient enabling set `E*`, not for a cut set:

`EffectRetention(E*) = ASR(keep_only(E*)) / ASR(full_attack)`.

## Topology labels

Each stable successful jailbreak receives one primary label:

- `LOCALIZED_SINGLE`;
- `LOCALIZED_SMALL_SET`;
- `LOCALIZED_INTERACTIVE`;
- `MULTIPLE_MINIMAL_CUT_SETS`;
- `MULTIPLE_SUFFICIENT_PATHWAYS`;
- `DISTRIBUTED_WITHIN_BUDGET`;
- `NON_MONOTONE`;
- `CAPABILITY_CONFOUNDED`;
- `UNRESOLVED_ABSTENTION`.

Labels are assigned under frozen priority and tie-breaking rules in the executable contract.

## Closest-work boundary

The paper must not claim first token localization or first token suppression. Prior work already ranks or suppresses jailbreak-critical tokens, prunes optimized suffixes, uses deletion for certified defense, detects suffix onset, and gives local causal explanations in internal representation space.

The intended contribution is the conjunction of:

1. input-level behavioral interventions rather than attribution alone;
2. necessity and sufficiency separated explicitly;
3. exact or contract-exact enumeration of all minimal sets;
4. higher-order interaction, redundant pathways, non-monotonicity, and distributed cases;
5. multi-operator robustness and capability controls;
6. comparison across semantic-readable, fluent-optimized, and non-fluent optimized regimes.

## Immediate authorized sequence

1. finish evaluator-panel component and external validation;
2. complete attack-family E0 provenance audit without target outcomes;
3. freeze the cross-regime unit vocabularies and topology-label rules;
4. run a balanced signal screen;
5. open exact/contract-exact topology analysis only for stable direct-safe/attacked-harmful pairs;
6. compare exact topology with Token Highlighter, Mask-GCG-style masking, leave-one-out, random same-size removal, greedy SAHARA-style search, CPD onset localization, and LOCA-style internal explanations where implementation permits;
7. consider wavelet only after exact ground truth exists.

## Sealed boundary

At this freeze point:

- semantic-only Stage A remains unopened;
- cross-regime Stage A remains unopened;
- prior evaluation and held-out partitions remain sealed;
- no causal topology result has been observed;
- no wavelet result has been observed;
- this is a method decision, not empirical evidence.
