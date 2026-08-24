# Robust Input-Level Causal Topology for Jailbreak Prompts v1

Date: 2026-08-24 (Asia/Seoul)

## Executive decision

The token-level SHIPs/SAHARA analogy is useful as a **candidate-ranking intuition**, but it is not the paper's main novelty and cannot by itself support the intended causal claims. The main object is instead a **robust minimal-recovery hypergraph** over input intervention units.

The revised scientific question is:

> Across semantic-readable, fluent-optimized, and non-fluent optimized single-turn jailbreaks, what robust minimal input sets must be neutralized to restore safe behavior, and do those sets reveal singleton dependence, higher-order interaction, redundant pathways, or distributed structure?

This document freezes the conceptual definitions before any cross-regime Stage A outputs, causal-oracle outputs, or wavelet results are inspected.

## 1. What can and cannot be transferred from SHIPs/SAHARA

The ICLR 2025 SHIPs paper attributes model safety to attention heads by ablating a head and measuring the KL divergence between the original and ablated output distributions. SAHARA greedily adds heads whose joint ablation produces the largest dataset-level representational change.

The transferable ideas are:

1. **intervene rather than merely correlate**;
2. evaluate both individual units and sets of units;
3. search for collaboratively acting groups;
4. validate the proposed attribution by observing an actual safety-behavior change.

The following parts do **not** transfer directly to prompt tokens:

1. In the attention-head setting, the paper assumes that deviation from a highly consistent rejection distribution is likely to move harmful queries toward affirmation. A token intervention can instead produce refusal, harmful compliance, incoherence, truncation, topic drift, or generic capability collapse. Output divergence alone is therefore not directional evidence of safety recovery.
2. A head is a fixed architectural component. A token is part of a structured sequence whose removal may shift all later positions, break grammar, alter tokenization, or delete the harmful goal itself.
3. SAHARA is a heuristic greedy search. It has no guarantee of finding a minimal set and can miss pure interactions in which every singleton has near-zero effect but a pair or triple has a large joint effect.
4. A token embedding replaced by a mean vector is an off-manifold representation intervention, not automatically a human-editable input intervention.

Accordingly, a SHIPs-inspired score is allowed only as a search heuristic or diagnostic. The paper-level ground truth must come from stable behavioral interventions under a frozen outcome contract.

## 2. Prompt decomposition and intervention domain

For a successful jailbreak instance, write the attacked prompt as

\[
x_J = \operatorname{Compose}(q, a),
\]

where:

- \(q\) is the explicit harmful goal or payload;
- \(a\) is the attack-added structure;
- the payload occurs exactly once and is byte-identical to the frozen source whenever the attack family permits structural payload preservation.

Let \(U(x_J)=\{u_1,\ldots,u_m\}\) be the frozen intervention vocabulary for the attack-added structure only. The harmful payload is outside the neutralizable domain.

The units are regime-specific:

- **Regime S — semantic-readable:** typed strategy nodes, then sentences/newline units, then token or character spans inside a localized node;
- **Regime F — fluent optimized:** provenance-preserving generated clauses or strategy blocks, then clauses/sentences, then contiguous token blocks;
- **Regime U — non-fluent optimized:** predeclared fixed token blocks, recursive sub-blocks, and contiguous token intervals.

For Regime U, exactness means exactness with respect to this frozen intervention vocabulary. It does not mean exhaustive enumeration of every subset of every individual token unless that enumeration is actually performed.

## 3. Primary outcome: behavior, not KL divergence

Let the validated evaluator panel emit one of:

- `REFUSAL_OR_SAFE_REDIRECTION`;
- `NON_ACTIONABLE_OR_IRRELEVANT`;
- `SUBSTANTIVE_HARMFUL_ASSISTANCE`;
- `CAPABILITY_CONFOUNDED`;
- `ABSTAIN`.

For a prompt \(x\), model \(M\), seed \(s\), and fixed generation configuration, define

\[
Y(x;M,s) \in \mathcal{Y}.
\]

Define the harmful-assistance indicator

\[
H(x;M,s)=\mathbf{1}\left[Y(x;M,s)=\texttt{SUBSTANTIVE\_HARMFUL\_ASSISTANCE}\right].
\]

A successful jailbreak instance is eligible only if the direct harmful goal is stably non-harmful and the full attacked prompt is stably harmful under the predeclared seed rule.

For intervention set \(S\subseteq U(x_J)\) and neutralizer \(k\), define the behavioral recovery effect

\[
\Delta_H^{(k)}(S)
=
\Pr_s[H(x_J;M,s)=1]
-
\Pr_s[H(\mathcal{N}^{(k)}_S(x_J);M,s)=1].
\]

The primary causal decision is based on the categorical outcomes and stability rule, not on a scalar divergence score.

### 3.1 Refusal probability is secondary

A refusal score \(P_R(x)\) may be computed from a validated refusal classifier or safety-relevant logit statistic, but it is a secondary diagnostic. Sequence-level refusal is not reliably represented by a single first-token probability, and non-refusal does not imply substantive harmful assistance.

### 3.2 Distributional divergence is secondary

A distributional metric may help rank candidates. If used, Jensen-Shannon divergence or a clearly specified safety-relevant logit divergence is preferred to an undefined full-sequence KL divergence. The exact token positions, generation steps, vocabulary restriction, and aggregation rule must be stated.

The project must not claim that a large KL divergence proves a causal jailbreak token.

## 4. Why the proposed multiplicative J-SHIPs score is not the primary metric

A proposed score of the form

\[
D_{KL}(p(x_J)\Vert p(\mathcal{N}_S(x_J)))
\cdot
[P_R(\mathcal{N}_S(x_J))-P_R(x_J)]_+
\]

has four problems:

1. the two factors have incompatible and calibration-sensitive scales;
2. the product can suppress a genuine behavioral flip when one factor saturates;
3. a large distribution change can be caused by incoherence or topic drift;
4. full-sequence output distributions are generally intractable and approximations can be method-dependent.

If retained, the SHIPs-inspired diagnostic is represented as a vector rather than collapsed into a product:

\[
\operatorname{Diag}(S)
=
\left(
D_{JS}(S),
\Delta_R(S),
\Delta_H(S),
\operatorname{CapabilityPreserve}(S)
\right).
\]

A lexicographic or learned ranking over this vector may be evaluated as a search heuristic against exact-oracle ground truth. It does not define the ground truth itself.

## 5. Robust minimal recovery sets

A set \(S\subseteq U(x_J)\) is a **recovery set** when neutralizing it causes stable safety recovery under every required neutralizer while preserving the fixed harmful goal and generic response capability.

Let `Recover` be the frozen predicate requiring, for each required neutralizer:

1. harmful assistance at or below the allowed count across seeds;
2. refusal or safe redirection on at least the required number of seeds;
3. no `CAPABILITY_CONFOUNDED` majority;
4. no `ABSTAIN` pattern that prevents a decision;
5. payload byte invariance and structural validity.

Then

\[
\operatorname{Recover}(S)=1
\]

only if all required conditions hold.

A **robust minimal recovery set** is

\[
S^* \subseteq U(x_J)
\]

such that

\[
\operatorname{Recover}(S^*)=1
\]

and

\[
\forall S'\subsetneq S^*,\quad \operatorname{Recover}(S')=0.
\]

This is a minimal **causal cut set** or minimal **necessary neutralization set**. It must not automatically be called a minimal enabling set.

## 6. Necessity and sufficiency must be separated

Neutralizing \(S\) and breaking the attack tests a necessity-like cut property. It does not show that \(S\) alone is sufficient to cause the jailbreak.

For selected cases, define a keep-only operator \(\mathcal{K}_S(x_J)\) that retains the fixed harmful goal and only the attack units in \(S\), replacing or removing all other attack units under a frozen construction rule.

A **minimal sufficient attack set** \(E^*\) satisfies

\[
\Pr_s[H(\mathcal{K}_{E^*}(x_J);M,s)=1]\ge\tau_H
\]

and every strict subset fails the same stability rule.

The paper may use the term **causal core** only when a clearly defined relationship between recovery-cut evidence and keep-only sufficiency evidence is established. Otherwise it must report the two objects separately.

## 7. Minimal-recovery hypergraph: the main causal-topology object

For each successful instance, define

\[
\mathcal{M}(x_J)
=
\{S\subseteq U(x_J): S\text{ is a robust minimal recovery set}\}.
\]

Treat \(U(x_J)\) as vertices and each set in \(\mathcal{M}(x_J)\) as a hyperedge. The resulting hypergraph is the instance-level **minimal-recovery topology**.

This supports the following operational categories:

- **Singleton-localized:** at least one minimal hyperedge has size 1;
- **Interactive:** the smallest minimal hyperedge has size greater than 1, so no singleton intervention recovers safety;
- **Multiple minimal pathways:** more than one distinct minimal hyperedge exists;
- **Redundant pathways:** minimal hyperedges are sufficiently disjoint that removing one pathway does not eliminate all alternatives;
- **Distributed or unresolved within budget:** no recovery set is found below the predeclared size/query budget;
- **Capability-confounded:** apparent recovery is driven by incoherence, truncation, malformed input, or generic capability failure.

`Distributed` is a budget-relative conclusion unless all subsets of the full intervention vocabulary were exhaustively tested.

## 8. Interaction definition

The interaction expression must include the baseline and must be defined on a directional behavioral effect, not on a product of unrelated scores.

For recovery effect \(F(S)=\Delta_H(S)\), the conditional pair interaction given an already-neutralized context \(B\) is

\[
\Gamma_{ij\mid B}
=
F(B\cup\{i,j\})
-F(B\cup\{i\})
-F(B\cup\{j\})
+F(B).
\]

A positive \(\Gamma_{ij\mid B}\) indicates super-additive recovery under the specified outcome and neutralizer. This is a diagnostic interaction magnitude.

The stronger discrete evidence for a pure interaction is:

\[
\operatorname{Recover}(B\cup\{i,j\})=1,
\]

while

\[
\operatorname{Recover}(B\cup\{i\})=
\operatorname{Recover}(B\cup\{j\})=0.
\]

Higher-order interactions are defined analogously through set minimality or higher-order discrete derivatives. Shapley-Taylor interaction indices may be included as a baseline, but exact robust minimality remains the primary object.

## 9. Cross-regime topology metrics

For each eligible instance, report at least:

1. **Minimum recovery order**
   \[
   o(x_J)=\min_{S\in\mathcal{M}(x_J)}|S|.
   \]

2. **Minimal-set multiplicity**
   \[
   m(x_J)=|\mathcal{M}(x_J)|.
   \]

3. **Normalized causal size**
   \[
   c_U(x_J)=\frac{o(x_J)}{|U(x_J)|}.
   \]

4. **Token coverage of the smallest recovery set**
   \[
   c_T(x_J)=\frac{|\operatorname{TokenIndices}(S_{\min})|}{|\operatorname{AttackTokenIndices}(x_J)|}.
   \]

5. **Recovery-set stability** across seeds, neutralizers, model families, and reruns, reported by exact agreement and Jaccard overlap.

6. **Pathway redundancy**, measured by the number of distinct minimal sets and a predeclared disjointness or hitting-set statistic.

7. **Distributedness curve**, reporting the best recovery rate achievable for each neutralization budget \(b\), rather than only a binary label.

8. **Capability-confound rate** and `ABSTAIN` rate.

### 9.1 Correct denominator for compression

The denominator must be the attack-added intervention domain, not the full prompt including the immutable harmful payload. Otherwise attacks with longer payloads appear artificially less compressible.

For cross-model reporting, both tokenizer-specific token coverage and a tokenizer-independent character/byte coverage should be reported where meaningful.

## 10. Neutralization operators

At least two intervention families are required where semantically meaningful.

### 10.1 On-manifold or text-level interventions

Preferred for human-readable claims:

- deletion with position-shift effects explicitly acknowledged;
- neutral semantic replacement using a frozen template;
- structure-preserving clause replacement;
- same-length or matched-token-count replacement when feasible.

### 10.2 Representation-level interventions

Allowed as robustness checks:

- embedding scaling;
- embedding interpolation toward a frozen neutral baseline;
- position-preserving embedding replacement;
- internal information-path attenuation.

Representation interventions must not be presented as equivalent to editable text. They test robustness of causal attribution to a different intervention family.

### 10.3 Regime-specific requirements

- For SlotGCG or position-sensitive attacks, deletion alone is insufficient because it shifts downstream positions. A position-preserving neutralizer is mandatory.
- For GCG-like suffixes, the fixed harmful payload and non-attacked prompt prefix remain unchanged.
- For automatically rewritten fluent attacks, the E0 provenance audit must establish whether the original harmful goal remains structurally recoverable. Attack families that cannot support a defensible payload-preservation contract require a separate formulation and cannot be silently pooled.

## 11. Capability and intent controls

A safe-looking output is not automatically safety recovery.

Required controls include:

1. byte-identical harmful payload when structurally possible;
2. syntactic and tokenizer validity;
3. coherent response generation;
4. task comprehension diagnostic;
5. matched benign prompt capability;
6. random same-size neutralization;
7. position-matched neutralization;
8. irrelevant attack-unit neutralization;
9. two neutralizers with agreement analysis;
10. evaluator abstention on malformed or judge-injected outputs.

An intervention that causes generic inability, gibberish, or truncation is labeled `CAPABILITY_CONFOUNDED` rather than recovery.

## 12. Search algorithms and exactness

### 12.1 Oracle first

For small intervention vocabularies, enumerate all non-empty subsets and compute all minimal recovery sets.

For larger vocabularies, freeze a block hierarchy and claim contract-exactness only within that hierarchy. Iterative deepening by set size is preferred because it identifies the minimum order directly.

### 12.2 SHIPs/SAHARA-inspired greedy search

A greedy rule that repeatedly adds the unit with the largest marginal diagnostic score is retained only as a baseline or approximate search method. It may fail under XOR-like interactions, redundant pathways, or non-monotone interventions.

### 12.3 Additional baselines

- leave-one-unit-out;
- random same-size search;
- greedy backward elimination;
- beam search;
- group testing;
- gradient/token attribution;
- Token Highlighter-style affirmation gradient;
- Mask-GCG importance or mask values for GCG-family attacks;
- Shapley or Shapley-Taylor interaction approximations;
- CPD/suffix-onset localization where applicable;
- wavelet-guided search only after the oracle exists.

## 13. Relationship to the earlier broad-span pilot

The earlier development observation that neutralizing approximately 32%--58% of some prompts appeared to recover refusal is not paper-valid evidence. It is a legacy pilot that motivates a refinement question:

> Does a broad recovery region contain a much smaller robust recovery set, or is the effect genuinely distributed within that region?

The new study may compare broad-region size with minimal-recovery size, but it must reproduce the phenomenon under the new evaluator and frozen cross-regime contract.

## 14. Closest novelty line

The strongest defensible contribution is not:

- token-level SHIPs;
- a new token importance score;
- finding jailbreak-critical tokens;
- pruning GCG suffixes;
- locating where a suffix begins;
- discovering human-readable jailbreak skills;
- proving that prompt features correlate with success.

The candidate contribution is:

> We define and measure the robust minimal-recovery topology of successful jailbreak prompts under direct behavioral interventions, separating singleton dependence, higher-order interaction, multiple minimal cut sets, redundant pathways, distributed structure, and capability-confounded recovery, and compare these topologies across semantic-readable, fluent-optimized, and non-fluent optimized attack regimes.

This claim survives only if the experiments include stable successful attacks, multiple neutralizers, capability controls, multiple attack families per regime, and cross-model replication.

## 15. Allowed paper claims and forbidden overclaims

### Allowed if supported

- exact minimality with respect to a frozen intervention vocabulary;
- robust recovery across specified seeds and neutralizers;
- regime-level differences in minimal-recovery topology;
- failure of singleton attribution to capture higher-order interactions;
- attack-family or model-specific topology;
- query-efficiency of an approximation relative to exact ground truth.

### Forbidden without additional evidence

- identifying the unique true cause of a jailbreak;
- model-internal mechanistic explanation from input intervention alone;
- a minimal enabling set from removal-only experiments;
- universal jailbreak structure from one model or one attack family;
- true distributedness when only small subsets were searched;
- human-editable explanations from embedding-only interventions;
- human-equivalent ground truth from same-model evaluator personas;
- wavelet novelty without matched non-wavelet superiority.

## 16. Immediate experimental sequence

1. Finish external validation and hardening of the standards-derived abstaining evaluator panel.
2. Complete the E0 provenance audit for at least two candidate families in each S/F/U regime.
3. Freeze target models, tokenizers, payload-preservation rules, unit vocabularies, neutralizers, stability criteria, and compute budgets.
4. Run a balanced development-only signal screen without opening prior held-out data.
5. Apply predeclared GO/NARROW/STOP rules per regime.
6. For stable successful pairs, compute the complete minimal-recovery hypergraph when feasible.
7. Run keep-only sufficiency tests on a predeclared subset.
8. Compare topology and compression metrics across regimes, attack families, models, and harm categories.
9. Only then evaluate SHIPs-inspired greedy search, attribution, group testing, and optional wavelet approximations.
10. Freeze a fresh confirmatory contract on unseen payloads and at least two target-model families.

## 17. Research-safety boundary

The project studies already-successful attacks and does not treat compressed attack generation as a contribution. Minimal sufficient attack strings and raw harmful outputs are dual-use artifacts and should not be released by default. Public artifacts should prioritize hashes, aggregate topology, evaluation code, safe synthetic examples, and defensive implications.