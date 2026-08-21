# Automated Gate 1 — Step 2 Materialization Report

Date: 2026-08-15 (Asia/Seoul)

Status: **PASS — immutable source, 60-payload split, and 250-record pre-inference denominator frozen; Gate 1 phenomenon is not yet evaluated**

## Scope completed

Step 2 resolved the real payload source and materialized the complete, machine-verifiable benchmark denominator before any target-model or evaluator result was observed.

- resolved the full immutable source revision;
- froze the source-file SHA-256;
- selected 50 Gate 1 development and 10 Gate 2 held-out payload IDs deterministically;
- created a safe payload registry without raw harmful requests;
- rendered 250 typed attack records from the 50 development payloads and five frozen composition families;
- validated payload character/byte invariance and full character/UTF-8 provenance;
- produced a complete pre-inference denominator and exclusion ledger;
- scanned every public output against all 100 raw source goals;
- persisted only safe hashes, metadata, offsets, program nodes, and provenance;
- reproduced all six safe files byte-for-byte on a later run.

No target-model generation, automated evaluator, eligibility decision, causal intervention, or localization result is part of this step.

## Immutable source identity

- repository: `JailbreakBench/JBB-Behaviors`
- source path: `data/harmful-behaviors.csv`
- requested prefix: `d8d87b8`
- resolved revision: `d8d87b8fdcb7806e3b4e45fffb2bc24aa6b17f32`
- source-file size: **23,116 bytes**
- source-file SHA-256: `4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1`
- validated rows: **100**
- validated categories: **10**

The source identity is stored in:

```text
data/gate1/materialized/source_identity.json
```

Future materialization runs must match the committed source SHA-256 and every committed safe output byte-for-byte. The workflow fails rather than silently replacing a frozen denominator.

## Deterministic payload split

The frozen category-stratified SHA-256 ranking selected:

- **5 development payloads per category = 50**;
- **1 held-out payload per category = 10**.

Each of the ten source categories therefore has exactly five Gate 1 development items and one Gate 2 held-out item.

Selection identity:

```text
selection SHA-256 = 3756b58c9f363ae7c9aeb21e91c74ce58b26b9fa245a26391ba9df51a8468a29
payload-registry canonical SHA-256 = 096cb8a4f0307c0b9f8604a714d39678f7de076acc91ecb9d8b33b4f051346ef
```

The public registry contains payload IDs, source indices, behavior/category labels, lengths, hashes, and split assignments. It does not contain the raw `Goal` field.

## Complete Gate 1 denominator

The materialized primary denominator is:

```text
50 Gate 1 development payloads × 5 primary composition families = 250 attacks
```

Family allocation is exactly balanced:

- `authority_directness`: 50
- `hypothetical_format`: 50
- `layered_fictional_persona`: 50
- `mixed_pressure`: 50
- `persona_justification`: 50

Every development payload appears in exactly five records. All 250 example IDs and all 250 rendered-prompt hashes are unique. Gate 2 held-out payloads do not appear in the Gate 1 attack records.

Pre-inference results:

- rendered attacks: **250**
- render failures: **0**
- pre-inference exclusions: **0**
- target-model inference: **false**
- tokenization status: `DEFERRED_UNTIL_TARGET_TOKENIZER_FREEZE`

## Invariant validation

Every materialized record passed:

- payload character-for-character equality;
- payload UTF-8 byte-for-byte equality;
- exactly one payload provenance segment;
- zero node/payload provenance overlap;
- gap-free character provenance;
- gap-free UTF-8 byte provenance;
- typed program compilation;
- registered parameter-domain validation;
- zero inserted forbidden safety/refusal cues;
- frozen contract identity.

Independent post-artifact structural checks confirmed:

- 60 unique payload entries;
- split counts 50/10;
- five development and one held-out item in every category;
- 250 records and 250 unique IDs;
- five records per development payload;
- 50 records per composition family;
- 250 unique rendered-prompt hashes;
- zero structural provenance errors;
- all committed file hashes match the materialization manifest.

## Safety and leakage controls

Raw payloads and rendered prompts were written only to an ephemeral workflow directory. After safe records were produced, both private JSONL files were shredded and the directory was removed.

The workflow concatenated all public output files and checked them against every raw source goal. Result:

```text
raw payload leak check = PASS
raw payloads committed = false
raw rendered prompts committed = false
```

The persistent safe files are:

```text
data/gate1/materialized/source_identity.json
data/gate1/materialized/payload_registry.safe.json
data/gate1/materialized/benchmark_records.safe.jsonl
data/gate1/materialized/denominator_manifest.json
data/gate1/materialized/exclusion_ledger.safe.json
data/gate1/materialized/materialization_manifest.json
```

## Frozen hashes

```text
contract SHA-256
035ed8ffba2914bb33af54474c47a379433d2d426f8974e70c6769be45439049

source file SHA-256
4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1

benchmark_records.safe.jsonl
7280eb5e92e1ccc179bc31da05e77f883226fe78856e7feda8fa186433844a0e

payload_registry.safe.json
c13a7f01775e32f18735441ff93415f7f94bb92807bc2b4e41c779356b02eac7

denominator_manifest.json
b56777d76b6b77a1360634f9c1067184c8214c8a6d5f9945a6942f9eafd486e9

exclusion_ledger.safe.json
961cbfaf21e9f05e18ea57792202b5def86c9d0918699d3d40a6e15488d72691

source_identity.json
7cd25d23f1b02138be5dcf9d0465d9b39c2df5b559c2ed82b5fb74fba366f849
```

## Execution and validation

Canonical successful materialization run:

```text
workflow run = 31884719455
artifact ID = 9246946837
artifact ZIP SHA-256 = 1d5060c9f8df230b512f4d33a01efa6d8bd235612adcd14e92cad19c9c6c98c1
```

The first implementation attempt stopped before source download because of one strict-mypy dictionary-invariance error. The private record was then explicitly typed, after which the complete workflow passed.

Final validation:

- `ruff`: PASS
- strict `mypy`: PASS
- tests: **37 passed**
- immutable source download: PASS
- source revision/prefix check: PASS
- source-file digest freeze: PASS
- typed render of 250 records: PASS
- raw-goal leakage scan: PASS
- private-file cleanup: PASS
- safe artifact upload: PASS
- persistent safe-output commit: PASS
- later expected-source-SHA check: PASS
- later byte-identical output diff: PASS
- Python 3.10 CI: PASS
- Python 3.11 CI: PASS

## Scientific interpretation

Step 2 establishes a reproducible generated denominator. It does **not** establish that any rendered attack succeeds, that 30 eligible attacks exist, or that any component is causal, compact, or minimal.

Program provenance remains distinct from causal evidence:

```text
program provenance != causal label
```

Causal labels will be assigned only after target-model eligibility and exhaustive intervention evaluation under frozen evaluators, neutralizers, and decoding seeds.

## Decision

```text
STEP2_PASS
GATE1_PHENOMENON_NOT_YET_EVALUATED
```

## Next step

Automated Gate 1 — Step 3 will freeze the primary target model, tokenizer/chat template, decoding seeds, token provenance, and automated evaluator consensus before running a small end-to-end eligibility smoke. It will not yet run the 250-item exact intervention oracle.
