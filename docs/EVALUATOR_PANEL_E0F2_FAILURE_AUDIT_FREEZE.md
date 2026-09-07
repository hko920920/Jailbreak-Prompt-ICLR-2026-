# E0F-2 Failure Audit Freeze (V1.1)

Date: 2026-09-03 (Asia/Seoul)  
Evidence class: post-outcome development diagnostic; **not** evaluator qualification, held-out evidence, or paper evidence.

## Question fixed before metric expansion

After the locked E0F-2 panel failed prospectively, does a broad but interpretable, source-blind monotone Boolean fusion of the already available local signals show enough stable signal to justify a separately frozen replacement-design review?

This audit cannot rescue E0F-2. It performs no new model inference, does not open held-out/P3/topology data, and cannot automatically freeze a replacement evaluator.

## Version history

- V1 contract is preserved at `configs/evaluator_panel/e0f2_failure_audit_v1.json` (8,300 bytes; SHA-256 `3d0bf64154ec0ce2334cd0bccc37f83c7f411b58b2aa7aaaf860e9b839d0f2ba`).
- Its first CLI attempt failed while resolving an argparse `Path`, before contract validation, data loading, metric computation, or output creation.
- V1.1 changes only CLI path resolution, the default contract path, and version-specific output paths. Candidate definitions, inputs, gates, folds, selection rules, and the stop/continue rule are unchanged.
- V1.1 contract: 9,332 bytes; SHA-256 `7bbd69b1357977f1aec5648d3e6cb2e89474e51219ea0e464686a52c3ad1a262`.
- V1.1 runner: 42,991 bytes; SHA-256 `941253caab4fee07df2db7e4da903c77afe8f69bfb5e2bbf334793a43e170c36`.

## Frozen candidate universe

The successful preflight used exactly 300 development records in 166 behavior groups and the five pre-WildGuard frozen behavior-group folds (55/61/56/61/67 records).

- Numeric atoms: 278
- All atoms, including three WildGuard atoms: 281
- Raw monotone expressions: 155,967
- Unique 300-record prediction vectors after label- and source-blind deduplication: 15,048
- Candidate specification SHA-256: `762644cdc82b85b3cb983c5ef30934628955f98741cf2c9c82565fd022879421`
- Prediction commitment SHA-256: `df73e741f1fca14b956f93f9c191620095e7c44b2e1e7efafcba908608b9db46`

The preflight explicitly reports that expanded candidate metrics were not computed and human labels were not used for candidate generation or deduplication.

## Frozen decision rule

Continuation requires all three conditions:

1. At least one fixed candidate passes every exact E0F-2 gate on the post-outcome full 300.
2. At least one of the two frozen nested-selection schemes passes every gate after concatenating its five out-of-fold predictions.
3. At least one full-300 passing candidate also passes all harmful/safe point gates on each of the five frozen folds.

If any condition fails, this local monotone Boolean fusion family stops. Such a stop is not a claim that every learned classifier or stronger external evaluator is impossible.

## Preflight identity

- Output: `data/evaluator_panel_v2/e0f2_failure_audit_v1_1_preflight.safe.json`
- Bytes: 1,338
- File SHA-256: `8dc214b919860e2c6e77040e5f9b1b17c6e36e62403dec6cd77c6303bc8497fd`
- Result identity SHA-256: `63ed99f1137588d372a650a715a89eeba4bf3846c9de5d50ca470376b4cd07a9`
- Repeated preflight: byte-identical
- New model inference: false
- Held-out opened: false
- P3 opened: false
- Topology opened: false
