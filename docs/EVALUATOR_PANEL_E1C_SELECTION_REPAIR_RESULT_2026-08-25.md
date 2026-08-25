# Evaluator Panel E1C Selection Repair Result

Date: 2026-08-25 (Asia/Seoul)

## Decision

The static E1C selection-repair step completed successfully.

- workflow: `temporary-e1c-selection-repair-pr`
- run: `32749293206`
- job: `97502158461`
- source commit: `65eb932a90591489c9774c56b704f2dec2492ff0`
- safe artifact: `9528332306`
- artifact digest: `sha256:babf38c782d8b7a6a20b015a352bde35aac11ab682b245bc2b78aade7a9d0c9d`
- status: `E1C_SELECTION_REPAIR_PASS`
- next authorized operation: `FREEZE_E1C_PROMPT_SOURCE_V3_WITH_REPAIRED_SELECTION`

This is `DEVELOPMENT` measurement evidence. It is not a HarmBench classifier result and not paper-valid jailbreak-topology evidence.

## What stopped E1C v2

The pinned official validation set contained selected records whose behavior IDs did not resolve in the pinned text-plus-multimodal behavior registry. The v2 prompt-source freeze correctly stopped before model inference:

- old selection rows: 200;
- human-majority labels: 100 negative / 100 positive;
- unresolved selected rows: 3;
- unresolved behavior hashes: 2;
- HarmBench model inference: not performed;
- live predictions: not generated.

## Frozen repair

No rows were chosen manually. The original label-balanced behavior round-robin selection was rerun after filtering official validation records to behavior IDs that resolve in the pinned registry and contain the notebook-required source fields.

| Check | Result |
|---|---:|
| New selection rows | 200 |
| Negative / positive | 100 / 100 |
| Unique behavior hashes | 166 |
| Dropped records | 3 |
| Deterministically added records | 3 |
| Unresolved registry rows | 0 |
| Repeated selection identical | true |

Identities:

- old record-ID identity: `8839e523fe353861a5ca69f7230f539e026044966867c8284251f750361b9356`
- new record-ID identity: `c02d697f27c6507691f55d2eaff63b760da0b6bce33f5756279b53d2a433979b`
- new safe-row canonical identity: `84acea4be52616456427fb92607322f074a9e3dc89cd4829b9037f2a846c3e7b`
- committed selection file SHA-256: `8e897219ce0fa12cd10a95091275f4f22c4528748f15ef1f601ceef4fd834510`

## Source integrity

The repair used the immutable HarmBench source:

- repository: `centerforaisafety/HarmBench`
- revision: `8e1604d1171fe8a48d8febecd22f600e462bdcdd`
- tree: `e28303aa064b3a4fdbe5698bc323e43306b7ab74`

The validation JSON and both behavior-registry CSV blobs matched their frozen Git identities. The resolved registry contained 400 text behaviors and 110 multimodal rows; 400 behavior IDs satisfied the source-field requirements used by the text-classifier notebook route.

## Scientific and safety boundary

This repair:

- downloaded no classifier weights;
- performed no model inference;
- generated no HarmBench predictions;
- generated no new jailbreak outputs;
- did not open semantic-only or cross-regime Stage A;
- did not open the causal cut-set or keep-only oracle;
- did not inspect held-out results;
- did not use wavelet search.

The only authorized next step is a prompt-source freeze v3 that reconstructs all 200 repaired rows from the pinned official registry and freezes their prompt/source identities before any live classifier output is generated.

## Committed safe records

- `data/natural_language_localization/evaluator_panel_v1/e1c_selection_repair.safe.json`
- `data/natural_language_localization/evaluator_panel_v1/e1c_harmbench_selection_v2.safe.jsonl`
