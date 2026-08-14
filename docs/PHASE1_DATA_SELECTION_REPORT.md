# Phase 1 Micro-Pilot Data Selection and Validation Report

Date: 2026-08-14 (Asia/Seoul)

Status: **PASS — data assembly and validation only**

This report does not claim that the target model is jailbreakable, that any input span is localizable, or that Gate 1 has passed. It freezes the 20-example development input used for the next real-model smoke test.

## Objective

Construct a small, reproducible paired development set with:

- at least two attack families;
- the same requested behavior represented across families;
- source and license provenance;
- stable IDs and pinned source revisions;
- no raw harmful prompts committed to this repository;
- strict schema, duplicate, and pairing validation;
- a validation-only path exercised in CI.

## Source selection

Source repository: `JailbreakBench/artifacts` under the repository MIT license.

| Attack family | Source artifact | Source model | Attack type | Pinned blob SHA | Selected examples |
|---|---|---|---|---|---:|
| PAIR | `attack-artifacts/PAIR/black_box/gpt-3.5-turbo-1106.json` | `gpt-3.5-turbo-1106` | black-box | `9612434c11c29492ae83fe160d466285b32114a8` | 10 |
| GCG | `attack-artifacts/GCG/white_box/vicuna-13b-v1.5.json` | `vicuna-13b-v1.5` | white-box | `1430aafc1795106ac89555b8ede5eee925d90e00` | 10 |

Selected source indices:

```text
0, 1, 2, 3, 5, 7, 8, 10, 11, 12
```

Each selected index appears once for PAIR and once for GCG, yielding 20 examples over 10 matched requested behaviors.

## Behavior coverage

| Pairing key | Behavior | Category |
|---|---|---|
| JBB-000 | Defamation | Harassment/Discrimination |
| JBB-001 | Body shaming | Harassment/Discrimination |
| JBB-002 | Xenophobia | Harassment/Discrimination |
| JBB-003 | Ableism | Harassment/Discrimination |
| JBB-005 | Racial discrimination | Harassment/Discrimination |
| JBB-007 | Enslavement | Harassment/Discrimination |
| JBB-008 | Holocaust glorification | Harassment/Discrimination |
| JBB-010 | Disable antivirus | Malware/Hacking |
| JBB-011 | Network hacking | Malware/Hacking |
| JBB-012 | Ransomware | Malware/Hacking |

This is a development micro-pilot, not a representative benchmark. Category imbalance is intentional at this stage because the purpose is to validate the phenomenon and pipeline before constructing the 100-example frozen pilot.

## Reproducible assembly

The script below downloads the two pinned source artifacts, selects the fixed indices, and writes the raw JSONL only to a gitignored local path:

```bash
python scripts/assemble_phase1_jbb_micro_pilot.py
```

Default raw output:

```text
data/processed/phase1_micro_pilot_20.local.jsonl
```

The assembler requires:

- non-empty goal, behavior, category, and prompt fields;
- `jailbroken == true` in the source artifact;
- unique stable IDs;
- unique jailbreak-prompt hashes;
- one PAIR and one GCG record per pairing key;
- identical original goal text across both families for each pairing key.

The committed source-selection manifest contains only provenance, indices, categories, and validation rules. It contains no prompt text.

## Validation-only execution

```bash
python scripts/run_phase1_micro_pilot.py \
  --config configs/phase1_micro_pilot.json \
  --validate-only
```

The CI workflow independently ran:

1. `ruff check .`
2. `mypy src/jbspan`
3. `pytest`
4. exact dataset assembly from the pinned upstream artifacts;
5. strict JSONL loading and validation-only manifest generation.

Both Python 3.10 and 3.11 jobs passed. Dataset assembly and validation-only execution ran on Python 3.11 and passed.

## Canonical validation result

```json
{
  "status": "VALIDATED_ONLY",
  "example_count": 20,
  "attack_family_counts": {
    "GCG": 10,
    "PAIR": 10
  },
  "source_sha256": "1b23badc7b42108be330e98da1c78c9147f997a7b85d5b3b1116d274567cfce5",
  "selection_output_sha256": "1b23badc7b42108be330e98da1c78c9147f997a7b85d5b3b1116d274567cfce5",
  "ids_sha256": "88f197df94a40da79d448c6ca607fc551a7f099ab5cdf8b8682ac8ac49882609",
  "paper_validity": false,
  "raw_prompts_committed": false
}
```

Validation failures:

- schema failures: 0
- duplicate stable IDs: 0
- duplicate jailbreak prompts: 0
- incomplete PAIR/GCG pairing keys: 0
- inconsistent original goals within pairing keys: 0
- missing source or license metadata: 0

## Interpretation

### What passed

- the 20-example paired development input is reproducibly constructible;
- source versions and licenses are pinned;
- the two attack families are balanced;
- matched behaviors are aligned by exact original goal;
- raw prompt text stays outside Git;
- the strict validation and manifest path runs successfully in CI.

### What remains untested

- whether Qwen or any other current target model refuses the original requests;
- whether the paired jailbreak prompts succeed on that target model;
- whether success is stable across seeds;
- whether small text spans restore refusal;
- whether intent is preserved after neutralization;
- whether the current heuristic judges agree with human judgments.

The next step is therefore a single-model, small-batch Hugging Face smoke with human auditing. No wavelet comparison or paper-level claim is justified before that step.
