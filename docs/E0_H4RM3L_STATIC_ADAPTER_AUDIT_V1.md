# E0 h4rm3l Static Adapter Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This is the first executable attack-family admission experiment under the cross-regime causal-topology plan. It does **not** test attack success. It tests whether the pinned h4rm3l source can be integrated without compromising the payload-preservation and pre-outcome intervention requirements.

The audit uses only the synthetic placeholder:

`JBSPAN_E0_SAFE_PAYLOAD_7B3F_DO_NOT_TRANSFORM`

No real harmful request and no target model are used.

## Pinned source

- repository: `mdoumbouya/h4rm3l`
- revision: `e6f58a1a1e56c1a95b26b06aa4fe393ee2240dbd`
- package path: `h4rm3l`
- decorators source blob: `b60346ec12b9334e0818dabc59ba65af55c167aa`
- license: MIT

The workflow checks out this exact revision and executes its actual decorator implementation. The model-prompting interface is replaced with a fail-closed stub. Any decorator that attempts to call a synthesis model fails the audit.

## Admission questions

1. Can a fixed h4rm3l expression be parsed into a deterministic component manifest before target outcomes?
2. Does each admitted decorator preserve one exact, contiguous payload occurrence?
3. Does a fresh compilation of the same pinned expression produce byte-identical output?
4. Can payload-mutating, character-corrupting, encoding, and model-rewriting decorators be excluded before experiments?
5. Can the audit produce only hashes, lengths, component names, counts, and decisions without releasing rendered prompt text?

## Tested safe expressions

The test set exercises:

- identity;
- prefix/suffix role wrapping;
- a parameterized format-rule prefix;
- a parameterized affirmative suffix;
- JSON and encyclopedia-style wrappers;
- a one-slot distractor template;
- question-identification and chain-of-thought wrappers;
- a three-component `.then()` composition.

The strings supplied to parameterized decorators are deliberately harmless. This test evaluates adapter behavior, not jailbreak efficacy.

## Predeclared exclusion set

The initial h4rm3l Regime-S adapter forbids decorators that rewrite, split, encode, corrupt, translate, or model-reformulate the payload, including:

- reverse/base64/character corruption and dropout;
- word mix-in families;
- translation, synonym, persuasion, persona, PAP, and visual-obfuscation rewriting;
- payload splitting;
- arbitrary transform functions.

These decorators may be studied only under a separately frozen formulation. They cannot enter the payload-preserving Regime-S matrix by accident or after target outcomes are observed.

## Pass rule

The audit passes only when:

- every expression's AST-derived component manifest matches its frozen manifest;
- every component belongs to the allowlist and none belongs to the exclusion set;
- the synthetic payload occurs exactly once as the same UTF-8 byte sequence;
- all fresh compilations produce the same output hash;
- no null character appears;
- no model-prompting call occurs;
- all allowlisted and excluded class identities exist in the pinned source.

A pass authorizes only construction of the typed unit manifest and neutralizer contract for h4rm3l. It does not authorize target-model attack generation or causal intervention.

## Safe output

The result artifact contains only:

- source and contract hashes;
- component names and counts;
- expression and rendered-output hashes;
- output lengths;
- payload occurrence counts;
- pass/fail decisions;
- sealed-boundary status.

Rendered text is never written to the safe artifact.

## Current boundary

At contract freeze:

- real harmful payload: unused;
- target model: uncalled;
- semantic-only and cross-regime Stage A: closed;
- causal and keep-only oracles: closed;
- held-out data: sealed;
- wavelet: closed.
