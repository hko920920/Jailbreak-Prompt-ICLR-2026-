# Automated Gate 1 — Step 3B.5 Decision

Date: 2026-08-16 (Asia/Seoul)

Status: **NO_REPRODUCIBLE_CANDIDATE_PASSES_SELECTION**

## Decision

The frozen JBB judge-comparison experiment used 200 examples for candidate selection and 100 disjoint examples for untouched validation against the existing public `human_majority` label. No new human annotation was collected, and the earlier ten-case smoke was not used to choose an evaluator.

Neither selectable and reproducible candidate passed the predeclared selection thresholds:

- official precomputed HarmBench: selection accuracy `0.785`, macro-F1 `0.779`, FNR `0.151`, FPR `0.252`;
- official precomputed LlamaGuard2: selection accuracy `0.875`, macro-F1 `0.868`, FNR `0.110`, FPR `0.134`.

The two reference-only candidates passed selection but failed the untouched validation thresholds:

- JailbreakBench Llama-3 70B: validation accuracy `0.870`, macro-F1 `0.865`, FNR `0.081`, FPR `0.159`;
- JailbreakBench GPT-4: validation accuracy `0.880`, macro-F1 `0.874`, FNR `0.108`, FPR `0.127`.

Accordingly:

```text
selected_primary_evaluator = none
confirmatory_smoke_allowed = false
final_evaluation_30_observed = false
gate2_heldout_10_used = false
Gate 1 = NOT_EVALUATED
```

Thresholds are not lowered after observing the result, and no runner-up is promoted. The next admissible evaluator attempt is a separately frozen, official WildGuard validation on the same external selection/validation split. If that attempt also fails the unchanged measurement-validity gate, the human-free free-form-response path must stop or pivot to a programmatically verifiable output task.

## Execution identity

- canonical workflow: `31954421564` — PASS
- result commit: `411ad17dd4e68b92f723c373eee7e0149675be14`
- safe artifact: `9265547576`
- artifact SHA-256: `23866b7c776d2dd689cb701f3a209600194a0f760cd7e97a37d2b2d73bedceac`
- source CSV SHA-256: `dacaf76a1057785f11b0fc6aa07b9a73cdab588319ddfc5e8cef2909e5b112a5`
