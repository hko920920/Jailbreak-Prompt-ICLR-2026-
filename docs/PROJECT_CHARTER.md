# Project Charter

## Working title

**Causal Localization of Jailbreak-Enabling Semantic Spans in Large Language Model Prompts**

The title is provisional. The paper should not claim that wavelets explain safety; wavelet or tree-Haar structure is a candidate search mechanism whose value must be established empirically.

## Target

- Venue: ICLR 2027
- Official abstract deadline: September 11, 2026 AoE
- Official full-paper deadline: September 16, 2026 AoE
- Internal target: freeze the central claim and main tables before September 7, 2026 KST

## Central question

For a successful jailbreak prompt, which smallest human-editable semantic span set is causally necessary for bypassing refusal, while the underlying requested behavior remains present?

## Unit of explanation

The main explanatory object is **input text**, not an activation vector, attention head, or output token. Internal-model evidence may validate a text-level explanation but is not required for the method to operate.

## Core hypotheses

- **H1 — Localizability:** A meaningful fraction of successful jailbreaks contain a small span set whose neutralization restores refusal.
- **H2 — Scale heterogeneity:** The responsible spans occur at different semantic scales, from short suffixes to multi-clause framing.
- **H3 — Robust causality:** Valid spans remain effective across neutralization operators, decoding seeds, and judges.
- **H4 — Query efficiency:** Adaptive multiresolution search approximates exhaustive span search with substantially fewer target-model calls.
- **H5 — Heterogeneity is itself informative:** Some attack families will be distributed and should trigger calibrated abstention rather than forced localization.

## Main contribution hierarchy

1. A text-level, intent-preserving causal localization task and evaluation protocol.
2. A robust span criterion with explicit abstention for distributed or non-identifiable attacks.
3. A query-budgeted multiresolution search method, provisionally tree-Haar guided.
4. Empirical findings on localizability, scale, stability, and transfer across attack families and models.
5. Optional supporting analysis of known safety-critical internal components.

## Explicitly out of scope for the main paper

- discovering a new universal safety-head set;
- reconstructing a full causal circuit;
- proposing a new jailbreak attack;
- training a new safety-aligned model;
- all safety failure types beyond text-only single-turn jailbreaks;
- claiming a span is uniquely causal when multiple equivalent span sets exist.

## Success definition

The paper is viable only if the central behavioral phenomenon is strong before method optimization. A method-only gain on an unstable or weakly localizable target is not enough.
