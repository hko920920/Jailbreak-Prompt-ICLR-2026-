# E0 AutoDAN-to-Qwen Adapter Smoke v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This step tests whether a payload-preserving AutoDAN study adapter can be
rendered through the exact Qwen2.5-7B-Instruct tokenizer and chat template while
maintaining an unambiguous payload span and an attack-only intervention domain.

It is a synthetic, pre-outcome adapter test. It does not:

- use a real harmful payload;
- download target-model weights;
- call a target model;
- generate a response;
- estimate attack success;
- open Stage A or the causal oracle.

## Frozen inputs

### AutoDAN

- repository: `SheltonLiu-N/AutoDAN`;
- revision: `34062e964185693e81a6775b4f0d00bfd7507612`;
- tree: `39ceba6f45e5dec17db8d3099d7281f8673ceb14`;
- initial prompt blob: `b99248622923b631346bced8ebd38effc4a6b87b`.

### Qwen tokenizer

- repository: `Qwen/Qwen2.5-7B-Instruct`;
- revision: `a09a35458c702b33eeacc393d103063234e8bc28`;
- tokenizer-only files are downloaded;
- model weight files are excluded.

The model card's official usage route applies `tokenizer.apply_chat_template`
for Qwen chat inputs. This smoke follows that tokenizer/chat-template path but
performs no generation.

## Adapter under test

The official AutoDAN suffix manager inserts the instruction through
`self.instruction.lower()`, which violates this project's byte-identical payload
rule. The study adapter therefore performs only one controlled change:

`[REPLACE] -> exact synthetic payload`

No lowercasing or other payload transformation is allowed.

The materialized AutoDAN text is supplied as one Qwen user message. The Qwen
chat template is rendered deterministically with `add_generation_prompt=true`.
The rendered chat string is then tokenized with offset mappings.

## Required checks

The smoke passes only if all of the following hold:

1. the predecessor static audit is exactly identified and authorizes this step;
2. AutoDAN and Qwen revisions are pinned;
3. the initial prompt has exactly one placeholder;
4. the synthetic payload occurs exactly once, byte-identically, after
   materialization;
5. the payload also occurs exactly once in the rendered Qwen chat string;
6. both materialization and chat rendering are deterministic across three fresh
   repetitions;
7. the Qwen tokenizer is fast and returns a non-empty contiguous token interval
   covering the full payload character span;
8. the intervention-unit manifest marks only the AutoDAN prefix and suffix as
   neutralizable and excludes the immutable payload;
9. no model weight is downloaded and no generation is performed;
10. no raw attack or rendered chat text is committed.

## Interpretation

A pass means only that the project can preserve and locate the payload under a
Qwen tokenizer/chat-template adapter. It resolves two engineering blockers:

- exact-placeholder materialization;
- target tokenizer/chat-template compatibility.

It does not admit AutoDAN to the balanced signal screen. The following remain:

- choose and freeze regeneration versus frozen official artifact route;
- freeze compute and candidate-selection budgets;
- protect the payload placeholder in every enabled mutation route;
- run a harmless end-to-end candidate-materialization smoke without target
  generation.

## Decision

Pass status:

`E0_AUTODAN_QWEN_ADAPTER_SMOKE_PASS_REMAIN_CONDITIONAL`

Failure status:

`E0_AUTODAN_QWEN_ADAPTER_SMOKE_FAIL`

No threshold may be relaxed and no target outcome may be opened in response to
a failure.
