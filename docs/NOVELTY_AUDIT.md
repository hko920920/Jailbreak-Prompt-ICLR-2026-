# Novelty Audit and Claim Boundary

Last reviewed: 2026-08-14.

Full claim-by-claim evidence matrix: [`LITERATURE_CLAIM_MATRIX.md`](LITERATURE_CLAIM_MATRIX.md).

## Current verdict

**CONDITIONAL PASS.** The broad topic is crowded, but the following joint research object was not identified in the completed search:

> A minimal human-editable input-text span set whose direct text neutralization restores refusal on a successful jailbreak while preserving the underlying harmful intent, remaining robust across neutralizers / seeds / judges, passing subset-minimality checks, and abstaining when the causal structure is distributed.

This is a search result, not proof of priority. Weekly refresh is mandatory through submission.

## Closest work

### LOCA — Minimal, Local, Causal Explanations for Jailbreak Success

LOCA identifies a minimal set of interpretable **intermediate-representation changes** that induce refusal on an otherwise successful jailbreak. It uses white-box activation patching and sparse-autoencoder directions. It is the closest conceptual overlap and invalidates any broad claim that local, minimal, causal explanations of jailbreak success are unexplored.

Our intended distinction must remain concrete:

- output object: editable input-text span set rather than token-concept activation patches;
- access: behavioral black-box/gray-box path rather than mandatory SAEs and residual-stream patching;
- validation: direct prompt counterfactuals, full generated behavior, intent preservation, and neutralizer robustness;
- application: prompt forensics and targeted remediation;
- failure handling: explicit non-localizable/distributed abstention.

### Token Highlighter

Token Highlighter uses gradients of an affirmation loss to identify jailbreak-critical tokens and softly suppress their embeddings. It occupies white-box token-level importance and mitigation. We must not claim first jailbreak-token localization.

Required differentiation:

- semantic spans and span sets rather than independent token saliency;
- causal text edits rather than embedding shrinkage;
- minimality and intent-preservation constraints;
- robustness across intervention realizations;
- query-budgeted search and calibrated abstention.

### GuardNet

GuardNet uses supervised graph-attention models to detect jailbreak prompts and label fine-grained adversarial spans. It invalidates a broad claim that jailbreak span localization itself is new.

Required differentiation:

- explanation of a target model's observed refusal failure rather than prediction of changed/adversarial tokens;
- direct behavioral intervention rather than supervised token labels;
- minimality, harmful-intent preservation, and distributed-case abstention.

### Erase-and-Check and attribution-guided excision

Erase-and-Check systematically removes tokens and checks subsequences with a safety filter, including greedy and gradient variants. Explain–Delete–Defend uses SHAP or feature ablation to excise influential tokens and regenerate. These works invalidate any claim that token removal or attribution-guided deletion is new.

Required differentiation:

- target-model refusal recovery rather than safety-filter certification or fixed-percentage excision;
- human-readable semantic span sets;
- explicit preservation of the original harmful goal;
- robust subset minimality and intervention-artifact controls.

### PromptLocate and WebSentinel

PromptLocate localizes injected instructions and data inside contaminated external content; WebSentinel localizes prompt injection in webpages. They establish semantic-segment localization for prompt injection, but not intent-preserving refusal recovery for single-turn jailbreak prompts.

### TriageFuzz and ALERT

TriageFuzz estimates refusal-sensitive token regions to prioritize query-efficient jailbreak mutation. ALERT localizes informative safety tokens for zero-shot detection. Token-aware sensitive-region search and token-wise safety localization therefore cannot be claimed as new.

### SAHARA and later attention-head work

SAHARA identifies safety-critical attention heads. Robust Harmful Features links attack-template tokens to adversarially compromised and safety-aligned heads, and Attention Slipping studies reduced attention to unsafe request tokens. This area is crowded. Attention heads should be supporting evidence only unless a separate paper is pursued.

### Wavelet attribution

Wavelet-domain attribution already exists in WAM and related work. The project cannot claim novelty from using wavelets alone. Tree-Haar structure must earn its place through query efficiency, heterogeneous-scale recovery, interaction discovery, or stability relative to the identical hierarchy without wavelets.

### General minimal-rationale literature

Sufficient Input Subsets, sequential rationalization, and input-mask optimization already establish minimal subsets, sufficiency, comprehensiveness, and compactness. These concepts are foundations and evaluation tools, not standalone novelty.

## Safe claim language

Potentially supportable:

> We study intent-preserving interventional localization of human-editable jailbreak-enabling span sets under refusal-recovery, intervention-robustness, and subset-minimality constraints, with explicit abstention for distributed cases.

Not supportable:

> We are the first to provide local, causal explanations of jailbreak success.

Not supportable:

> We are the first to locate jailbreak-critical input tokens or adversarial spans.

Not supportable:

> We are the first to remove important jailbreak tokens to restore safety.

Not supportable:

> We are the first to use wavelets for attribution.

## Novelty gate

Before paper-scale experiments, complete the following:

1. Keep the claim-by-claim matrix current using exact method inputs, outputs, access assumptions, interventions, validity conditions, and metrics.
2. Treat GuardNet, Erase-and-Check, Explain–Delete–Defend, TriageFuzz, and ALERT as direct or near-direct collision checks in addition to LOCA, Token Highlighter, and PromptLocate.
3. Search new papers weekly until submission freeze.
4. Reject or pivot if a paper already performs robust, intent-preserving, text-level minimal span-set localization on successful jailbreaks.
5. Require direct empirical superiority over token saliency/excision baselines on validity, minimality, stability, or query cost.

## Planned pivot options

- **Pivot A:** If the full text-level localization contract is already occupied, study calibrated localizable-versus-distributed jailbreak structure.
- **Pivot B:** If wavelet search has no advantage, retain the task and use a simpler adaptive group-testing method.
- **Pivot C:** If small spans rarely restore refusal, characterize distributed causal mass and develop a non-localizability certificate.
- **Pivot D:** If intent-preserving neutralization is the dominant difficulty, make intervention validity and artifact-resistant counterfactual construction the central method.
