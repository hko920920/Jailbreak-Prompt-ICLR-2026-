# Automated Gate 1 — Step 2 Materialization Protocol

Date: 2026-08-15 (Asia/Seoul)

Status: **frozen before target-model inference**

## Objective

Resolve the immutable payload source, select the frozen 50-development / 10-heldout payload split, and materialize the complete 250-record Gate 1 denominator without target-model or evaluator calls.

## Immutable source

- repository: `JailbreakBench/JBB-Behaviors`
- full revision: `d8d87b8fdcb7806e3b4e45fffb2bc24aa6b17f32`
- source file: `data/harmful-behaviors.csv`
- rows: 100
- categories: 10
- source file SHA-256: computed during materialization and frozen in the safe source identity

## Selection

Within each category, rank rows by:

```text
SHA256(
  selection_seed || NUL || category || NUL || source_index || NUL ||
  SHA256(goal) || NUL || SHA256(behavior)
)
```

The first five rows are assigned to `gate1_development`; the sixth is assigned to `gate2_heldout`. The raw goal text is never written to a public registry.

## Materialized denominator

- 50 development payloads × 5 primary composition families = 250 records
- 10 heldout payloads are registered but not rendered into the Gate 1 primary denominator
- every record is typed-rendered and carries character and UTF-8 byte provenance
- token provenance remains deferred until the target tokenizer and chat template are frozen

## Public outputs

- immutable source identity;
- safe 60-item payload registry;
- safe 250-record benchmark JSONL;
- complete denominator manifest;
- pre-inference exclusion ledger;
- safe materialization manifest.

Public outputs contain hashes, offsets, lengths, categories, behavior labels, program nodes, and provenance, but no raw harmful payload or rendered prompt.

## Private outputs

Raw payloads and rendered prompts exist only in the ephemeral workflow directory. They are deleted after the safe outputs are produced and are not uploaded as artifacts.

## Interpretation boundary

This step establishes a reproducible denominator only. It does not establish attack success, eligibility, localizability, causal effects, or Gate 1 passage.
