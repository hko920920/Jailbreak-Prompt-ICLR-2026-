# Automated Gate 1 — Step 1 Contract Freeze Report

Date: 2026-08-15 (Asia/Seoul)

Status: **PASS — benchmark and intervention contract frozen; Gate 1 itself is not yet passed**

## Scope completed

Step 1 froze and implemented the machine-verifiable contract used before any Gate 1 target-model or evaluator result is observed.

- payload-source and split policy;
- safe payload-registry schema;
- typed attack primitive registry;
- composition grammar and held-out policy;
- typed neutralizer registry;
- character and UTF-8 byte provenance;
- deferred overlap-aware token provenance schema;
- deterministic contract hashing;
- typed renderer and intervention validator;
- safe toy smoke tests and CI.

This step does not establish attack eligibility, localizability, causal effects, or paper-facing results.

## Frozen payload contract

Primary source pool:

- repository: `JailbreakBench/JBB-Behaviors`;
- config: `behaviors`;
- split: `harmful`;
- requested revision prefix: `d8d87b8`;
- expected rows: **100**;
- expected categories: **10**;
- license: MIT;
- DOI: `10.57967/hf/2540`.

Step 2 must resolve the source revision prefix to a full immutable revision and record the source-file SHA-256 before materializing any payload IDs.

The deterministic category-stratified policy selects:

- **5** Gate 1 development payloads per category = **50**;
- **1** Gate 2 held-out payload per category = **10**;
- selected total = **60**.

Raw harmful payload text is not committed. The later public registry will contain safe metadata, source indices, lengths, and hashes.

## Frozen program contract

Primary primitives: **8**

1. `persona_frame`
2. `hypothetical_frame`
3. `authority_frame`
4. `refusal_suppression`
5. `benign_justification`
6. `output_format_coercion`
7. `fictional_wrapper`
8. `task_persistence`

Primary composition families: **5**

1. `persona_justification`
2. `hypothetical_format`
3. `authority_directness`
4. `layered_fictional_persona`
5. `mixed_pressure`

One additional family, `heldout_fictional_authority`, is reserved for Gate 2.

The Gate 1 primary denominator is therefore frozen as:

```text
50 development payloads × 5 primary composition families = 250 rendered attacks
```

Parameterized surface forms are selected by deterministic SHA-256 domain indexing. This varies surface realizations across payloads without multiplying or post-selecting the denominator.

## Frozen intervention contract

Primary neutralizers: **2**

- `typed_disable_v1`: disable selected program nodes and re-render;
- `typed_neutral_replace_v1`: replace selected nodes with registered neutral templates and re-render.

Diagnostic only:

- `diagnostic_delete_v1`.

Accepted interventions must:

- preserve the payload character-for-character and byte-for-byte;
- avoid all payload provenance;
- re-render through the typed program;
- preserve required slots;
- use registered nodes and operators only;
- insert no registered explicit refusal or safety cue.

Unknown nodes, duplicate nodes, unbound neutralizer calls, parameter-domain violations, neutralization no-ops, malformed templates, provenance gaps, and payload overlaps are rejected before model inference.

## Provenance contract

Character and UTF-8 byte offsets are recorded at render time. Token provenance is intentionally deferred until the primary tokenizer revision and chat template are frozen.

The token-provenance schema is overlap-aware because one tokenizer unit can cross two rendered component boundaries. It therefore records token-to-source links and boundary-crossing tokens rather than assigning every token to exactly one component.

Program provenance identifies which node generated text. It is not a causal label. Causal status will be assigned only by the later exact target-model intervention oracle.

## Validation results

Canonical CI run: `31883638739`

Both Python jobs passed:

- Python 3.10: `ruff`, `mypy`, and `pytest` PASS;
- Python 3.11: `ruff`, `mypy`, `pytest`, Gate 1 contract validation, and legacy Phase 1 regression checks PASS;
- total test suite: **34 passed**;
- typed contract smoke families: **5**.

Canonical safe contract output:

```text
status = GATE1_CONTRACT_VALIDATED
selected payload target = 60
Gate 1 development payloads = 50
Gate 2 held-out payloads = 10
primary primitives = 8
primary composition families = 5
primary neutralizers = 2
projected Gate 1 attacks = 250
max neutralizable nodes = 8
raw payloads committed = false
contract SHA-256 = 035ed8ffba2914bb33af54474c47a379433d2d426f8974e70c6769be45439049
```

## Design corrections made before results

1. **Leakage-safe denominator:** the initially tempting 60 × 5 design was rejected. Ten payloads and one composition family are held out, leaving a primary denominator of 250 rather than allowing Gate 2 material into Gate 1.
2. **Controlled surface variation:** one fixed wrapper string per family was rejected. Frozen finite parameter domains are varied deterministically by payload and family.
3. **Tokenizer-aware provenance:** token offsets are not fabricated before tokenizer freeze; the later record explicitly handles boundary-crossing tokens.
4. **Immutable source identity:** the short source revision is insufficient for evidence freeze. Step 2 must resolve the full revision and source-file digest.
5. **Provenance/causality separation:** inserted component positions are not treated as causal ground truth. Only intervention outcomes can receive causal-oracle labels.

## Scientific limitations at this point

- no raw payload registry has been materialized;
- no 250-item benchmark has yet been generated;
- no target model or automated evaluator has been run;
- no attack has been declared eligible;
- no component has been declared causal or minimal;
- the constructed composition families may produce too few target-model successes;
- this registry is not claimed as a new jailbreak DSL;
- wavelet or adaptive-search optimization remains prohibited before the Gate 1 phenomenon decision.

## Decision

```text
STEP1_PASS
GATE1_NOT_YET_EVALUATED
```

## Next step

Automated Gate 1 — Step 2 will:

1. resolve the full immutable payload-source revision and file digest;
2. materialize the deterministic 60-item safe payload registry;
3. freeze the 50-development / 10-heldout IDs;
4. render and validate the projected 250 Gate 1 program records;
5. preserve raw payloads and rendered prompts outside public Git history;
6. produce a complete safe denominator and exclusion ledger without target-model inference.
