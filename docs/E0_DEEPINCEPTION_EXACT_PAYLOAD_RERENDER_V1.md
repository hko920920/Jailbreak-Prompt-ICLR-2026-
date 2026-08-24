# E0 DeepInception Exact-Payload Rerender v1

Date: 2026-08-24 (Asia/Seoul)

## Decision prompted by the strict official-artifact failure

The immutable official-artifact audit rejected DeepInception because at least one official rendered prompt changed internal acronym casing in the embedded goal (`IoT` to `iot`). That exceeded the predeclared initial-character-only normalization. The failure remains valid and is not overwritten.

This follow-up evaluates a narrower, explicitly derived route:

> retain every non-payload character of the pinned official DeepInception template, remove the source-rendered payload slot, and insert the experiment's canonical goal once as a contiguous, byte-identical string.

The resulting prompt is called **source-conformant derived DeepInception**, not an official artifact.

## Why this route is scientifically defensible

The project requires the same explicit goal in direct and attacked conditions. Allowing an attack implementation to lowercase internal acronyms, rephrase, translate, duplicate, or otherwise rewrite that goal creates a causal confound: a later intervention could appear to alter jailbreak success because the task itself changed.

The derived route preserves the attack strategy while eliminating that confound:

- source repository and revision remain fixed;
- payload-slot boundaries are located from frozen official anchors;
- prefix, antagonist suffix, final-layer text, and all other source characters remain unchanged;
- the canonical goal used by the direct condition is inserted into the slot exactly once;
- the source's rewritten embedded text is retained only as provenance evidence and is never used as the experimental goal.

## Canonical goal

Before any target output, the experimental goal is frozen as:

1. the official `plain_attack` value;
2. leading and trailing ASCII whitespace removed;
3. at most one terminal ASCII period removed;
4. no internal case, token, character, byte, or ordering change permitted.

The same canonical goal must be used by direct and attacked conditions.

## Source-template admission

The official embedded slot must still correspond to the plain goal. To prevent arbitrary template extraction, admission requires:

- equal character length;
- equal UTF-8 byte length;
- equality after Unicode case folding;
- no token addition, deletion, or reordering.

This admits the observed case-only discrepancy while rejecting paraphrase or structural payload changes.

## Static audit

For every official main-data row, the audit must:

1. verify pinned source, data, and license identities;
2. locate the source payload slot from frozen anchors;
3. verify case-only source-slot correspondence;
4. construct the derived prompt with the canonical goal inserted exactly once;
5. prove that every non-payload source character is unchanged;
6. replace the goal with a harmless sentinel for intervention testing;
7. partition the synthetic prompt into seven typed attack units plus one immutable payload fragment;
8. enumerate all 127 non-empty unit subsets;
9. apply deletion and layout-preserving blanking, yielding 254 variants per row;
10. verify exact sentinel preservation and neutralizer length rules for every variant.

No target model is called, no attack success is scored, and no raw source goal, rendered prompt, derived prompt, or synthetic prompt is written to the safe artifact.

## Interpretation

A pass establishes only that the pinned DeepInception source can support a payload-invariant, seven-unit intervention adapter. It does not establish attack effectiveness or causal topology.

A later paper must identify this family accurately, for example:

> source-conformant DeepInception templates with exact payload rerendering

It must not claim that the modified prompts are byte-identical official artifacts.

## Decision boundary

- The official-artifact route remains failed.
- The derived route is admitted only if every official row and every synthetic neutralization variant passes.
- A failure permits implementation repair under the same rule or replacement of DeepInception by another independent semantic family.
- Target outputs, Stage A, held-out data, causal oracle, keep-only oracle, and wavelet remain sealed.
