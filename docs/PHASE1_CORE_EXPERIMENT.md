# Phase 1 Core Experiment Readiness Protocol

## Purpose

The first real experiment answers only one question:

> Among paired examples where the original request is refused and the jailbreak prompt succeeds, does a small human-editable input span exist whose neutralization restores refusal while retaining the requested behavior?

It does **not** test wavelet superiority, attention-head mechanisms, or paper-scale generalization.

## Stage A — Validation-only run

Prepare a local JSONL file following `data/examples/phase1_pair_template.jsonl`. Raw prompts and unrestricted responses remain outside git.

```bash
python scripts/run_phase1_micro_pilot.py \
  --config configs/phase1_micro_pilot.json \
  --validate-only
```

This freezes:

- dataset SHA-256;
- stable ID hash;
- attack-family counts;
- complete configuration hash;
- Python and platform metadata.

## Stage B — Infrastructure micro-pilot

Install the local-model extra and run on at most 20 development examples:

```bash
python -m pip install -e '.[dev,hf]'
python scripts/run_phase1_micro_pilot.py \
  --config configs/phase1_micro_pilot.json
```

The default judges are explicitly named `NOT-FOR-PAPER`. Their only purpose is to exercise the full pipeline and identify cases for human audit.

## Stage C — Human audit before Gate 1

For every apparently localized example, inspect:

1. original prompt was genuinely refused;
2. jailbreak response genuinely complied;
3. edited prompt still contains the same requested behavior;
4. refusal recovery is not caused by malformed grammar;
5. both deterministic neutralizers support the same span;
6. the selected span is not merely the harmful payload itself.

No central claim is unlocked until validated response and intent judges replace the heuristic adapters.

## Core outputs

```text
artifacts/phase1-micro-pilot-v1/
  data_manifest.json
  run_manifest.json
  records.jsonl
  summary.json
```

`records.jsonl` contains IDs, offsets, scores, statuses, and query counts. It does not intentionally copy prompt text into the result artifact. Model responses remain in the local response cache and must not be committed.

## Gate interpretation

- `GO`: enough eligible cases are localized with short spans and cross-neutralizer agreement.
- `CONDITIONAL_GO`: evidence is concentrated in particular attack families or spans are somewhat larger than planned.
- `NO_GO`: localizable cases are rare, unstable, payload-confounded, or intervention-artifact driven.

The micro-pilot output is diagnostic. The formal Phase 1 Gate requires validated judges, an exclusion ledger, and human-audited examples.
