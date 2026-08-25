# E0 DeepInception Static Template Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This is the static admission audit for the second provisional Regime-S family. It uses the author-maintained DeepInception repository at an immutable revision and inspects the official `res/data_main.json` artifacts without calling any target model or scoring attack success.

The audit asks whether the official attacks expose a stable payload slot and a pre-outcome seven-unit semantic structure that can later support direct subset interventions.

## Pinned source

- repository: `tmlr-group/DeepInception`
- revision: `fc5689e76c4dd87a14babf1eadf890532f2b6880`
- license: MIT
- main code blob: `aa47305f5e709e103570ccb9b4beddbda68c877a`
- official main-data blob: `16b4082922e8d8986cb1345e9c6556c6f82da0a9`

The repository's `main.py` reads each `inception_attack` from the official data file and sends it to the target model. E0 stops before that model call.

## Payload-slot rule

The official source contains both a plain request and a rendered inception attack. The source sometimes embeds the request after a grammatical prefix with its initial character lowercased and without one terminal period.

Before execution, the audit therefore freezes the only allowed source-comparison normalization:

1. strip leading and trailing ASCII whitespace;
2. remove at most one terminal ASCII period;
3. optionally lowercase only the first character;
4. permit no other rewriting.

The rendered payload slot is extracted between the fixed per-layer proposal prefix and one of two declared antagonist suffixes. Every official row must match its plain request under the narrow rule above.

For intervention testing, the extracted source payload is replaced by the harmless sentinel:

`JBSPAN_E0_SAFE_PAYLOAD_7B3F_DO_NOT_TRANSFORM`

The sentinel must occur exactly once as the same UTF-8 byte sequence.

## Seven typed units

Every synthetic reconstruction must be partitioned into:

1. scene and character setup;
2. recursive layer rule;
3. target-depth instruction;
4. per-layer proposal scaffold;
5. antagonist or justification frame;
6. final practicality requirement;
7. summary instruction.

The sentinel payload is an eighth immutable fragment outside the neutralizable unit set.

## Exhaustive static neutralization

For every official main-data row:

- all 127 non-empty subsets of the seven attack units are enumerated;
- each subset is processed by deletion and layout-preserving blanking;
- 254 variants per row must retain one exact sentinel occurrence;
- deletion may only shorten the prompt;
- blanking must preserve prompt length and offsets;
- no null character may be introduced.

Only hashes, lengths, counts, normalization modes, and pass/fail decisions are written to the safe artifact. No raw source request, rendered attack, synthetic prompt, or fragment text is committed.

## Interpretation

A pass establishes that DeepInception's official main attack artifacts support:

- a stable and narrowly normalized payload slot;
- a deterministic seven-unit semantic intervention vocabulary;
- exhaustive component-subset neutralization under two operators;
- safe metadata-only recording.

It does not establish that DeepInception succeeds on the project's target models and does not establish causal topology. A pass authorizes only a later parameter and balanced-template audit before any target-model signal screen.

## Sealed boundary

- target model: uncalled;
- attack success: unscored;
- real harmful output: not generated;
- cross-regime Stage A: closed;
- causal and keep-only oracles: closed;
- held-out data: sealed;
- wavelet: closed.
