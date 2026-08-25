# Evaluator Panel E1C Prompt-Source Freeze v3

Date: 2026-08-25 (Asia/Seoul)

## Purpose

This stage binds the repaired 200-record HarmBench validation selection to the exact
behavior, context, generation, prompt family, and runtime-artifact identities that a
future live classifier reproduction will use. It remains a static source operation.

It does not download classifier weights, perform model inference, generate HarmBench
predictions, or open any jailbreak-output or causal-topology experiment.

## Predecessor

The frozen selection repair passed with:

- 200 selected records;
- 100 human-majority negative and 100 human-majority positive labels;
- 166 distinct behavior hashes;
- three unresolved records deterministically replaced;
- zero unresolved records in the repaired selection;
- selection-file SHA-256
  `8e897219ce0fa12cd10a95091275f4f22c4528748f15ef1f601ceef4fd834510`.

## Primary execution identity

The production live route is frozen as:

- source model: `cais/HarmBench-Llama-2-13b-cls` at immutable revision
  `bda705349d1144fa618770bea64d99ce54e3835b`;
- CPU runtime artifact:
  `HarmBench-Llama-2-13b-cls.Q4_K_M.gguf` with SHA-256
  `45f6c4dc9e86d540a2e153f57852673f54732704a3039b1426ce46b1e436f578`;
- prompt source: pinned HarmBench `eval_utils.py`;
- prompt family: `LLAMA2_CLS_PROMPT`;
- decoding contract: temperature `0.0`, maximum output tokens `1`.

The official validation notebook's text section is retained as a provenance diagnostic,
not silently treated as the production route. That notebook loads the Llama classifier
while selecting `MISTRAL_CLS_PROMPT` through its `classifier_path` state. Cached `cls`
values therefore are not the primary reference labels. The primary labels remain the
majority of the three public human annotations.

## Static reconstruction

For each repaired safe selection row, v3:

1. recomputes the private canonical record ID from the pinned validation JSON;
2. verifies its safe record ID, behavior hash, human-majority label, and position;
3. resolves the behavior and context from the pinned behavior registry;
4. chooses `prompt` or `prompt_contextual` according to the official context rule;
5. renders the production Llama classifier prompt in memory;
6. writes only hashes, lengths, labels, positions, and template-key identities.

The committed safe manifest contains no raw behavior, context, generation, test case, or
rendered prompt text.

## Decision gate

Pass requires all 200 rows to reconstruct exactly, all frozen source and selection
identities to match, the production prompt family to match the pinned `eval_utils.py`,
and the safe prompt manifest to be deterministic.

On pass, the only authorized next operation is:

`FREEZE_E1C_HARMBENCH_LIVE_REPRODUCTION_AND_INJECTION_CANARY_CONTRACT_FROM_PROMPT_SOURCE_V3`

No live classifier output is authorized by v3 itself.
