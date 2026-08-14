# Jailbreak Prompt Localization

Research codebase for **causal localization of minimal jailbreak-enabling semantic spans** in LLM prompts.

> Target cycle: **ICLR 2027**. The repository slug is retained for continuity. The official abstract and paper deadlines are September 11 and September 16, 2026 (AoE), respectively.

## Research question

Given an original harmful request that a target model refuses and a successful jailbreak prompt derived from it, identify the smallest human-editable span set whose neutralization restores refusal **without removing the underlying requested behavior**.

This repository deliberately separates three layers:

1. **Behavioral localization**: prompt-text interventions and response-level causal validation.
2. **Search**: exhaustive, hierarchical, and tree-Haar/wavelet-guided candidate discovery.
3. **Optional mechanistic validation**: internal-model analysis is supporting evidence, not a prerequisite for the main method.

## Why this scope

Recent work already studies minimal causal **internal-representation** changes (LOCA), gradient-based jailbreak-critical tokens (Token Highlighter), prompt-injection segment localization (PromptLocate), and safety-critical attention heads (SAHARA). The intended contribution here is narrower and operationally different: a target-model-facing, text-level, intent-preserving, robust causal localization task that can support black-box or gray-box evaluation.

See [`docs/NOVELTY_AUDIT.md`](docs/NOVELTY_AUDIT.md) for the current boundary and pivot rules.

## Current stage

**Phase 0 — phenomenon and infrastructure validation.** No paper claim is considered locked until the following gate passes:

- successful jailbreak pairs can be reproduced;
- small span interventions restore refusal on a meaningful fraction of cases;
- the effect survives more than one neutralization operator;
- the original requested behavior remains present;
- adaptive search reduces target-model queries relative to exhaustive contiguous-span search.

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

The codebase currently provides framework-level implementations and a toy end-to-end path. Hugging Face and judge adapters are intentionally isolated behind protocols and are the next implementation milestone after the Phase 0 research gate is reviewed.
