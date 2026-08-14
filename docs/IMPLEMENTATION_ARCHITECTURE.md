# Implementation Architecture

## Design principles

- Model access, judges, segmentation, neutralization, search, and metrics are separate interfaces.
- Unit tests never require a GPU or remote API.
- Every target-model call is counted and cacheable.
- Raw prompts and model outputs are kept out of git by default.
- Search methods cannot declare success without direct final intervention verification.

## Core objects

- `PromptPair`: original request and successful jailbreak prompt.
- `TextSpan`: immutable half-open character interval.
- `BehaviorScores`: refusal, harmful compliance, and optional intent score.
- `InterventionRecord`: one edited-prompt evaluation.
- `LocalizationResult`: final spans, status, cost, effects, and query count.

## Interfaces

- `TargetModel.generate`
- `ResponseJudge.score`
- `IntentJudge.score`
- `Neutralizer.apply`
- `CausalEvaluator.evaluate`
- search strategy `localize`

## Artifact layout

A future experiment run should write:

```text
artifacts/<run_id>/
  config.json
  environment.json
  data_manifest.json
  predictions.jsonl
  interventions.jsonl
  metrics.json
  audit_sample.jsonl
  stdout.log
```

## Near-term implementation sequence

1. CPU-only framework and toy smoke test.
2. JSONL loader, cache, and deterministic generation manifest.
3. Hugging Face model adapter with batched local inference.
4. Full-response refusal/harm judge adapter.
5. Phase 1 data normalization and frozen split.
6. Exhaustive oracle for short prompts.
7. Adaptive search methods and ablations.
8. Bootstrap analysis and publication plots.
