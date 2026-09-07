# Jailbreak Minimal-Recovery Topology

Research codebase for enumerating **all robust strict-subset-minimal recovery sets** in already-successful jailbreak prompts while preserving the explicit harmful payload.

> Target cycle: **ICLR 2027**. The repository slug is retained for continuity. The official abstract and paper deadlines are September 18 and September 25, 2026 (AoE), respectively.

## Research question

Given an original harmful request that a target model refuses and a fixed successful jailbreak prompt derived from it, which predeclared combinations of attack-added, human-editable input units must be neutralized to robustly remove substantive harmful assistance **without changing the explicit harmful payload or collapsing general response capability**?

The primary object is the complete family of strict-subset-minimal recovery sets within a frozen finite intervention vocabulary, not a token-importance ranking or one greedy explanation.

This repository deliberately separates three layers:

1. **Behavioral localization**: prompt-text interventions and response-level causal validation.
2. **Search**: exhaustive, hierarchical, and tree-Haar/wavelet-guided candidate discovery.
3. **Optional mechanistic validation**: internal-model analysis is supporting evidence, not a prerequisite for the main method.

## Why this scope

Recent work already studies minimal causal **internal-representation** changes (LOCA), gradient-based jailbreak-critical tokens (Token Highlighter), prompt-injection segment localization (PromptLocate), and safety-critical attention heads (SAHARA). The intended contribution here is narrower and operationally different: a target-model-facing, text-level, intent-preserving, robust causal localization task that can support black-box or gray-box evaluation.

Start with [`docs/CURRENT_PROJECT_INDEX.md`](docs/CURRENT_PROJECT_INDEX.md). The current contribution and non-claim boundary is frozen in [`docs/CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md`](docs/CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md), with its human-evidence clauses superseded by the [`v3.1 no-new-human amendment`](docs/CURRENT_RESEARCH_SCOPE_V3_1_NO_NEW_HUMAN_AMENDMENT.md).

## Current stage

**Steps 1, 2R, 3, 4, Step 5N, and the h4rm3l-only C1N screen are complete, but the frozen C1N gate is a valid negative and no paper-valid confirmatory topology result exists.** The official two-family D3 gate failed only its pooled neutralizer-agreement threshold: positive-decision Jaccard was 64/141 = 0.4539 against the frozen 0.80 gate. It is not relabeled. The permitted project route was narrowed to h4rm3l, where the development diagnostics were stronger: 8/9 reportable, 7/9 nontrivial, Jaccard 25/30 = 0.8333, zero capability-control failures, and a 0.3333 complete-family recall loss for the best one-path baseline. The mandatory coarsening collapsed every h4rm3l development topology to the same singleton macro-group, so granularity-invariant synergy and broad mechanism claims are prohibited.

After explicit author acceptance, Step 5N froze and ran a harmless-only admission for the preferred pair: the existing official Qwen2.5 target and Google's official Gemma 4 E4B Q4 artifact. Both passed 11/11 independent-process generations, 10/10 capabilities, deterministic replay, template/GPU, speed, VRAM, temperature, echo, and truncation gates. An independent reconstruction passed 18/18 checks. No harmful payload, evaluator, attack-success label, topology, or C1N output was opened, and Llama3.1 fallback was not activated. See [`docs/STEP5N_TARGET_ADMISSION_RESULT_V1.md`](docs/STEP5N_TARGET_ADMISSION_RESULT_V1.md).

The subsequently frozen C1N completed every seed-11 call: 180/180 target generations, 180/180
Qwen3Guard evaluations, and 180/180 JailMeter evaluations. Forty pairs from 36 unique payloads
could advance, but the per-target split was Qwen 35 and Gemma 5 against a frozen minimum of six
each. Because later seeds can only remove pairs, the gate became mathematically unreachable and
the exact rule stopped before the remaining 360 target calls. Independent reconstruction passed.
The negative result is driven mainly by severe evaluator disagreement on Gemma attacked responses
and does not authorize C2N or establish that no three-seed-stable pairs exist. See
[`docs/C1N_H4RM3L_FRESH_SCREEN_VALID_NEGATIVE_RESULT_V1.md`](docs/C1N_H4RM3L_FRESH_SCREEN_VALID_NEGATIVE_RESULT_V1.md).

## Repository layout

```text
configs/                 Frozen experiment configurations
data/                    Data placement and licensing notes; no raw harmful data committed
docs/                    Research charter, novelty audit, experiment plan, decisions
scripts/                 Reproducible entry points
src/jbspan/              Core package
tests/                   CPU-only unit and smoke tests
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python -m jbspan.cli smoke
```

The smoke test uses a harmless deterministic toy model. It verifies segmentation, intervention, causal scoring, search, result serialization, and query accounting without downloading a model or dataset.

## Initial commands

```bash
make test
make lint
python scripts/run_smoke.py
```

## Data contract

Each paired example uses JSONL with at least:

```json
{
  "id": "example-id",
  "behavior": "abstract behavior identifier or description",
  "original_prompt": "request refused by the target model",
  "jailbreak_prompt": "successful adversarially framed request",
  "attack_family": "attack-family",
  "metadata": {}
}
```

Do not commit restricted benchmark data, raw model outputs containing operational harmful instructions, credentials, or provider logs. Store only hashes, aggregate metrics, and redacted examples when licensing or safety requires it.

## Reproducibility rules

- Freeze evaluation IDs before tuning.
- Record model revision, tokenizer revision, generation parameters, judge revision, hardware, runtime, and random seeds.
- Use matched random-span controls and multiple neutralization operators.
- Report paired confidence intervals and abstention rates.
- Keep every result linked to a config hash and git commit.
- Inspect diffs before committing generated datasets or model outputs.

## Status

Protocol, provenance, exact-topology tests, target-generation infrastructure, public-label splits, one-shot held-out heterogeneous-evaluator qualification, the T0 transition contract, D2/D3 development topology, Step 5N preferred-target admission, and the target-scoped C1N are implemented. C1N is independently verified as a valid negative gate and C2N is closed under that contract. The next operation is a reviewer-calibrated paper-scope and measurement-validity decision; it is not automatic topology execution or a post-outcome threshold repair. The repository deliberately labels protocol, evaluator qualification, negative evidence, and paper-valid topology evidence separately.

The 2026-09-05 rescue-pivot record is
[`docs/ICLR2027_RESCUE_PIVOT_RECORD_2026-09-05_V1.md`](docs/ICLR2027_RESCUE_PIVOT_RECORD_2026-09-05_V1.md).
It preserves the D3/C1N failures, records the post-outcome resolution-sensitivity signal, seals a
fresh 60/60 GuidedBench primary/replication frame, and documents the no-inference GuidedEval
development preflight. No new paper-valid claim has yet been established.
