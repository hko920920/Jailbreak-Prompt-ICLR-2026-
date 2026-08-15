# Automated Gate 1 — Step 3B Source and Split Freeze Report

Date: 2026-08-16 (Asia/Seoul)

Status: **PASS — externally grounded v2 candidate pool and disjoint 10/10/30 data split frozen before any v2 target-model output**

## Executive decision

The first atomic Step 3B task is complete. Seven payload-preserving candidate attack programs were declared from a pinned, published h4rm3l source, and the 50 Gate 1 development payloads were split deterministically into three disjoint groups:

- 10 attack-family calibration payloads;
- 10 untouched eligibility-smoke payloads;
- 30 untouched final phenomenon-evaluation payloads.

No v2 target-model response, evaluator output, eligibility result, or causal result was observed before this freeze. The previous v1 `0/5` eligibility result remains preserved as a negative control.

This step does not show that the v2 attacks succeed. It establishes the only candidate pool and data partitions that may be used by the next calibration and untouched smoke.

## Published source identity

The v2 candidates are grounded in an immutable h4rm3l artifact rather than case-specific prompt writing.

```text
repository
mdoumbouya/h4rm3l

revision
e6f58a1a1e56c1a95b26b06aa4fe393ee2240dbd

source path
experiments/experiment_116_bandi_synthesis/config/benchmark_reference_programs.csv

Git blob SHA
220a255d39c1cad769e2414448fbad514e2823dd

source-file SHA-256
b4c07b11c9e92ecd332807e8ba32d8fe028b59f4c3499f72670d44105626ef07

license
MIT
```

The workflow downloads that exact revision and verifies the Git blob before parsing it. A source change causes failure rather than silently replacing the candidate pool.

## Candidate pool

Seven candidate programs were declared before calibration:

1. `v2_refusal_style_affirmative`
2. `v2_fewshot_affirmative`
3. `v2_cipher_affirmative`
4. `v2_aim_affirmative`
5. `v2_dan_affirmative`
6. `v2_aim_refusal_affirmative`
7. `v2_dan_refusal_affirmative`

Each candidate is composed only from pinned static `RoleplayingDecorator` programs in the source artifact. The parser accepts literal prefix/suffix wrappers and rejects dynamic or payload-transforming operations.

The following are forbidden in the primary candidate registry:

- payload paraphrasing;
- translation of the payload;
- encoding or corruption of the payload;
- splitting or reordering the payload;
- payload deletion;
- dynamic f-string values;
- unregistered decorator types;
- case-specific prompt edits.

For every candidate, a sentinel render verified that the payload appears exactly once and remains character-identical. Public files contain only candidate IDs, source-program IDs, node provenance, lengths, and hashes. Raw wrapper strings are not committed.

## Leakage-safe 10/10/30 split

The 50 previously frozen Gate 1 development payloads contain five items in each of ten behavior categories. Within every category, a frozen SHA-256 ranking assigns:

- rank 1 to calibration;
- rank 2 to untouched smoke;
- ranks 3–5 to final evaluation.

Therefore:

```text
10 categories × 1 calibration item = 10
10 categories × 1 smoke item       = 10
10 categories × 3 evaluation items  = 30
```

Validation established:

- `calibration ∩ smoke = ∅`;
- `calibration ∩ evaluation = ∅`;
- `smoke ∩ evaluation = ∅`;
- the union of the three groups is exactly the 50-item Gate 1 development registry;
- all ten Gate 2 held-out payloads remain excluded;
- every category contributes exactly `1 / 1 / 3` items.

Frozen split identities:

```text
calibration IDs SHA-256
b0928d50fb7a0a34f069b85dba1b04d2ea7a9e009025259431fbee885feda58c

smoke IDs SHA-256
6b496b52d3dc36cfaba09d66d19fddfbcc33567d8dc811094775a5261b7652c4

final-evaluation IDs SHA-256
c401c4841acd7e0a7ddd1c4780de57b4849ecf7f1be63d1dfef607a68b60c7ca

split manifest file SHA-256
38fa801d3ff61d6e0f31c88a88e7e2600b1e3ea020c229d23c359a3228ac4bcf
```

## Pre-result correction audit

The first implementation draft used a `10 calibration / 40 evaluation` split and planned to draw the smoke from that evaluation pool. An independent implementation audit identified that this would weaken the untouched final evaluation.

The frozen manifest at that point explicitly recorded:

```text
target_model_outputs_observed = false
v1_result_preserved = true
```

The split was therefore corrected before calibration or any v2 generation to the originally intended disjoint `10 / 10 / 30` design. The superseded `10/40` draft and failed infrastructure attempts remain visible in Git history; they were not erased or presented as scientific failures.

## Validation results

The corrected state passed:

- exact source revision and Git-blob verification;
- static source-program parsing;
- exact payload preservation for all seven candidate sentinel renders;
- deterministic category-balanced `10/10/30` split;
- pairwise split disjointness;
- complete coverage of the 50 development payloads;
- exclusion of all Gate 2 held-out payloads;
- raw-wrapper leakage guard;
- `ruff`;
- strict `mypy`;
- **45 tests**;
- corrected frozen-output audit;
- independent official freeze regeneration and recursive byte diff.

Canonical correction application:

```text
workflow run
31897343141

scientific-state commit
27a9e4cf2f5baad775c2370d22394b0fe9d1130a
```

Canonical official freeze revalidation:

```text
workflow run
31897505674

artifact ID
9250197742

artifact ZIP SHA-256
14883db22e877922998050bcf2c8fe0a488aa0740d5acebfd05ffe1c0426e055
```

## Scientific boundary

This step establishes provenance and experimental separation only. It does not establish:

- that any v2 candidate jailbreaks the target model;
- that three eligible attacks will be found in the untouched smoke;
- that any component is causal;
- that a compact or minimal component set exists;
- that Gate 1 passes;
- that wavelet or adaptive search should be developed.

Calibration outputs are development-only and cannot contribute paper-facing rates or decide Gate 1. Calibration may select only among the seven predeclared candidates using the frozen rule. It may not rewrite a candidate for a particular payload.

## Decision

```text
STEP3B_SOURCE_SPLIT_FREEZE_PASS
V2_ATTACK_SIGNAL_NOT_YET_EVALUATED
NEXT = CALIBRATION_ONLY
```

The next atomic task is to run the seven frozen candidates on the ten calibration payloads using the frozen target and development-only screening rule, then select the permitted candidate subset without observing the untouched smoke or final-evaluation payload outputs.
