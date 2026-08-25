# Natural-language rubric-calibration packet protocol

## Purpose

This workflow creates only the 30-item rubric-calibration packet authorized by
`feasibility_v1.json`. It does not generate or open the 60-item feasibility
decision packet, the prior 30-item evaluation split, Gate 2 held-out data, the
causal oracle, or wavelet analysis.

## Frozen denominator

The packet contains ten direct responses and twenty attacked responses: each of
the ten rubric-calibration payloads receives its direct condition and two
preassigned cyclic attack candidates at seed 17. The target, attacks, payload
hashes, generation settings, and item IDs are validated against the committed
contract and safe plan before model execution.

## Blinding

The private annotation packet shows only:

- an HMAC-derived annotation ID;
- the original harmful goal;
- the target-model response;
- empty label, confidence, and notes fields.

It hides condition, attack candidate, full wrapper text, seed, and original item
ordering. A separate private key file maps annotation IDs back to experimental
conditions. A fresh 256-bit randomization seed determines both annotation IDs
and packet order; only its SHA-256 commitment is released in the safe summary.

## Storage boundary

Raw prompts, responses, annotation packet, key, schema, and randomization seed
exist only in the runner's private temporary directory. After generation they
are archived and encrypted with the existing project recipient certificate
using OpenSSL CMS AES-256. The plaintext files and archive are then removed.

The uploaded artifact contains:

- the encrypted CMS bundle;
- preparation counts and source identities;
- packet counts, commitments, and response-set hashes.

It does not contain raw prompts, raw responses, attack text, or annotation-key
mappings in plaintext.

## Human gate

Two independent annotators complete separate copies of the same blinded packet.
A third adjudicator resolves every disagreement or `UNCERTAIN` label. Calibration
must reach raw agreement of at least 0.80 and Cohen's kappa of at least 0.60.
Rubric revision is allowed only before any decision-packet labels are opened.

A successful packet-generation workflow therefore establishes only that the
frozen calibration denominator and blinding/encryption pipeline are complete.
It does not establish jailbreak success, measurement reliability, eligibility,
or causal localization.
