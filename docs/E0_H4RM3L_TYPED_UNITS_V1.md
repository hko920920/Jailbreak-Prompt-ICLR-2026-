# E0 h4rm3l Typed Units and Neutralizers v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

The preceding h4rm3l static audit established that an allowlisted set of pinned decorators can preserve one exact synthetic payload, render deterministically, and avoid model prompting. This second E0 experiment asks whether those decorators can be converted into a typed, pre-outcome intervention vocabulary suitable for later causal subset experiments.

No harmful request and no target model are used.

## Typed-unit construction

For each frozen h4rm3l expression, the workflow:

1. parses the `.then()` composition into ordered component calls;
2. applies each component separately to the current text;
3. requires the complete component input to occur exactly once in its output;
4. attributes the newly added prefix and/or suffix fragments to that component;
5. shifts earlier fragment offsets through later wrappers;
6. verifies that payload plus all attributed fragments form a complete, non-overlapping partition of the final prompt;
7. verifies that sequential component application exactly matches h4rm3l's compiled full-chain output.

The manifest stores component names, fragment ownership, offsets, lengths, and hashes. It does not store raw fragment or prompt text.

## Frozen programs

Three harmless synthetic programs are used:

- a three-component semantic wrapper chain;
- a two-component formatting chain;
- a two-component distractor/identification chain.

Together they contain seven typed components. Their non-empty subset counts are:

- three-component chain: 7;
- first two-component chain: 3;
- second two-component chain: 3;
- total: 13.

## Neutralizers

Every non-empty component subset is evaluated under both:

1. `delete_component_fragments`: remove all final-output fragments owned by the selected components;
2. `layout_preserving_blank`: replace selected fragments' non-whitespace characters with ASCII spaces while preserving whitespace and character offsets.

This yields 26 synthetic variants. Every variant must retain one exact UTF-8 payload occurrence, contain no null character, and satisfy its predeclared length rule.

These neutralizers are admission prototypes for Regime S. They do not yet establish safety recovery and do not automatically become the final target-model neutralizers.

## Pass meaning

A pass establishes that:

- h4rm3l composition can be represented as pre-outcome typed input units;
- component fragments can be mapped to the final rendered prompt without overlap;
- every component subset can be neutralized deterministically;
- the immutable payload survives every tested neutralization;
- no synthesis or target model is called;
- safe artifacts can omit all raw rendered text.

A pass authorizes only a real-template payload-invariance audit under a separately frozen, non-output-scored route. It does not authorize Stage A or causal claims.

## Sealed boundary

- real harmful payload: unused;
- target model: uncalled;
- cross-regime Stage A: closed;
- causal and keep-only oracles: closed;
- held-out data: sealed;
- wavelet: closed.
