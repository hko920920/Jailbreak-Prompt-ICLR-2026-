# Novelty Audit and Claim Boundary

Last reviewed: 2026-08-14.

## Closest work

### LOCA — Minimal, Local, Causal Explanations for Jailbreak Success

LOCA identifies a minimal set of interpretable **intermediate-representation changes** that induce refusal on an otherwise successful jailbreak. It uses white-box activation patching and sparse-autoencoder directions. It is the closest conceptual overlap and invalidates any broad claim that local, minimal, causal explanations of jailbreak success are unexplored.

Our intended distinction must remain concrete:

- output object: editable input-text span set rather than token-concept activation patches;
- access: behavioral black-box/gray-box path rather than mandatory SAEs and residual-stream patching;
- validation: prompt counterfactuals, full generated behavior, intent preservation, neutralizer robustness;
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

### PromptLocate

PromptLocate localizes injected instructions and data inside contaminated external content. It establishes semantic-segment localization for prompt injection, but not causal refusal recovery for jailbreak prompts.

### SAHARA and later attention-head work

SAHARA identifies safety-critical attention heads; later work links attack-template tokens to compromised and robust safety heads. This area is crowded. Attention heads should be supporting evidence only unless a separate paper is pursued.

### Wavelet attribution

Wavelet-domain attribution already exists in other modalities. The project cannot claim novelty from using wavelets alone. Tree-Haar structure must earn its place through query efficiency, scale robustness, or stability.

## Safe claim language

Potentially supportable:

> We formulate text-level counterfactual localization of jailbreak-enabling semantic spans under refusal-recovery and intent-preservation constraints.

Not supportable:

> We are the first to provide local, causal explanations of jailbreak success.

Not supportable:

> We are the first to locate jailbreak-critical input tokens.

## Novelty gate

Before paper-scale experiments, complete the following:

1. Re-read LOCA, Token Highlighter, PromptLocate, WhatFeatures, and current 2026 jailbreak-localization work.
2. Build a claim-by-claim comparison table using exact method inputs, outputs, access assumptions, interventions, and metrics.
3. Search new papers weekly until submission freeze.
4. Reject the project or pivot if a paper already performs robust, intent-preserving, text-level minimal span-set localization on successful jailbreaks.

## Planned pivot options

- **Pivot A:** If text-level localization is already occupied, study calibrated localizable-versus-distributed jailbreak structure.
- **Pivot B:** If wavelet search has no advantage, retain the task and use a simpler adaptive group-testing method.
- **Pivot C:** If small spans rarely restore refusal, characterize distributed causal mass and develop a non-localizability certificate.
