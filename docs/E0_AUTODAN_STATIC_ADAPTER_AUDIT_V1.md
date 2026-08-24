# E0 AutoDAN Static Adapter Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose and boundary

This is a pre-outcome source and adapter audit for the fluent-optimized
jailbreak regime. It does not run AutoDAN against a target model, generate a
real harmful attack, inspect attack success, open Stage A, or execute a causal
intervention.

The pinned source is:

- repository: `SheltonLiu-N/AutoDAN`;
- revision: `34062e964185693e81a6775b4f0d00bfd7507612`;
- source tree: `39ceba6f45e5dec17db8d3099d7281f8673ceb14`;
- license: MIT.

Only a synthetic harmless placeholder is used.

## Questions tested

The audit verifies:

1. exact upstream file identities and license;
2. the official prompt placeholder and construction path;
3. whether the official implementation preserves an instruction byte-for-byte;
4. whether a study-side exact-placeholder adapter can preserve the payload once;
5. GA/HGA entrypoint defaults and suffix-manager wiring;
6. official target-model keys;
7. placeholder-protection behavior in mutation routes;
8. safe handling of the released `prompt_group.pth` without deserializing it;
9. whether AutoDAN may enter the balanced signal screen at this stage.

## Expected and frozen finding

The official `autodan_SuffixManager` materializes a candidate by replacing
`[REPLACE]` with `self.instruction.lower()`. Therefore, the official route does
not satisfy this project's byte-identical payload rule when the source
instruction contains case-sensitive bytes.

The audit does not silently reinterpret this as success. It separately tests a
study adapter that replaces the same placeholder with the exact synthetic
payload without lowercasing. Passing that string-level test establishes only
that an exact-placeholder route is implementable; it does not establish attack
success or equivalence to the official runtime.

## Additional admission blockers

AutoDAN remains conditional after a successful static audit because:

- the current Qwen2.5 project target is absent from the official model map;
- an explicit chat-template and tokenizer adapter must be tested;
- local synonym/HGA replacement paths do not explicitly protect the token
  `REPLACE`;
- the released `prompt_group.pth` is an initial-population artifact, not a
  frozen final optimized-attack set;
- regeneration compute, candidate count, and selection rules are not frozen.

The binary `.pth` file is hashed but never deserialized in this audit because
`torch.load` of an untrusted pickle-capable artifact is outside the safe static
boundary.

## Decision

A successful audit yields:

`E0_AUTODAN_STATIC_AUDIT_CONDITIONAL_ADVANCE`

This means the source and a payload-preserving adapter route are sufficiently
understood to prepare the next synthetic-only adapter smoke. It does **not**
admit AutoDAN to the balanced target-model signal screen.

The only authorized follow-up is:

1. exact-placeholder adapter smoke with a synthetic harmless payload;
2. target chat-template/tokenizer adapter smoke without harmful outputs;
3. regeneration versus frozen-artifact route decision;
4. compute and candidate-selection budget freeze.

A failed static audit authorizes only repair or replacement without opening
target-model outcomes.

## Sealed boundaries

- real harmful payload: unused;
- target model: not called;
- cross-regime Stage A: closed;
- causal oracle: closed;
- wavelet: closed.
