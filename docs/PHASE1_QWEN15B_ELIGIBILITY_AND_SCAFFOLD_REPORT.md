# Phase 1 Qwen2.5-1.5B Eligibility and Scaffold-Removal Diagnostic

Date: 2026-08-14 (Asia/Seoul)

Status: **MIXED / CONDITIONAL SIGNAL — NOT A GATE-1 RESULT**

This report records a CPU-feasible engineering smoke on `Qwen/Qwen2.5-1.5B-Instruct`. It is not a substitute for the planned 7B target-model evaluation, uses one deterministic decoding configuration, and does not provide paper-valid judge or minimal-span evidence.

## Questions tested

1. Does the target model refuse the 20 original harmful requests?
2. Do the paired historical PAIR/GCG jailbreak prompts transfer to this target model?
3. How accurate is the current heuristic response judge?
4. For human-confirmed successes, does removing obvious attack framing restore refusal under two text interventions?

## Frozen setup

- Data: 20 paired development examples, PAIR 10 / GCG 10
- Model: `Qwen/Qwen2.5-1.5B-Instruct`
- Device: GitHub-hosted CPU runner
- Decoding: greedy, temperature `0.0`, `max_new_tokens=64`
- Seed field: `11`; greedy decoding is deterministic, so this does not test stochastic seed stability
- Workflow run: `31785221085`
- Workflow commit: `3362758859e1b390a0f4658bcab052f3508ac71d`
- Private artifact digest: `sha256:05e9c5bf534bb1efb5ef5bce05cb99d8b7e0a5729d1b10054be62e8ca8271609`
- Paper validity: `false`

Raw prompts and generated responses remain outside the repository. Only IDs, aggregate counts, human-audit decisions, hashes, and non-operational metadata are committed.

## A. Eligibility smoke

### Automated heuristic result

| Measure | Count |
|---|---:|
| Original prompts called refusal | 20 / 20 |
| Jailbreak prompts called harmful compliance | 10 / 20 |
| Heuristic eligible pairs | 10 / 20 |

### Human audit result

| Human decision | Count | Fraction of all 20 |
|---|---:|---:|
| Confirmed original refusals | 20 | 1.00 |
| Confirmed harmful jailbreak compliance | 4 | 0.20 |
| Borderline because the 64-token response was insufficient for a confident label | 2 | 0.10 |
| Heuristic positives rejected as refusal, safe reframing, or non-fulfillment | 4 | 0.20 |

Strict precision of the heuristic among its 10 positive calls was therefore `4/10 = 0.40`. Counting the two borderline cases as possible positives gives an upper diagnostic precision of `6/10 = 0.60`. The heuristic judge cannot support paper claims.

### Family breakdown

| Family | Confirmed | Borderline | Total |
|---|---:|---:|---:|
| GCG | 1 | 0 | 10 |
| PAIR | 3 | 2 | 10 |

The conservative transfer-eligibility rate was `4/20 = 0.20`; even the inclusive rate was `6/20 = 0.30`. Both are below the provisional `0.35` phenomenon threshold, but this is not a valid Gate-1 failure because the attacks were generated for different historical target models and the smoke used a smaller 1.5B model.

## B. Human-audit-guided scaffold-removal diagnostic

Only the four human-confirmed successful jailbreaks were examined. The edits were chosen after inspecting each prompt's structure:

- retain the direct requested behavior;
- remove or neutralize surrounding attack framing;
- test a core-only deletion variant;
- test a neutral-context wrapper variant.

This is **not** an automatic localization result and **not** a minimal-span search.

### Outcome

| Outcome | Count |
|---|---:|
| Refusal recovered with core-only deletion | 2 / 4 |
| Refusal recovered with neutral-context wrapper | 3 / 4 |
| Refusal recovered under both operators | 2 / 4 |
| Operator-sensitive result | 1 / 4 |
| Harmful compliance remained under both | 1 / 4 |

Manual review agreed with these four diagnostic classifications. The two robust cases retained the requested harmful behavior, remained interpretable, and produced direct refusals under both edit realizations; the behavior change was not explained by an empty or malformed prompt.

### Size and minimality

Across the four audit-guided candidates:

- proper median retained-core character fraction: `0.5002`;
- proper median removed character fraction: `0.4998`;
- median removed fraction among the two robust cases: `0.4998`.

Thus, the diagnostic removed approximately half of each prompt. It supports the weaker statement that attack framing can be behaviorally decisive in some transferred jailbreaks, but it does **not** support a claim that the enabling cause is small or minimal.

The automated summary used an upper-middle value (`0.5354`) for the four-item median. The corrected statistical median computed from the frozen per-example records is `0.5002`; paper-facing code must use `statistics.median` before larger experiments.

## C. What is encouraging

1. All 20 original harmful requests were refused under human audit.
2. Four historical jailbreak prompts transferred with clear harmful compliance despite the model and source mismatch.
3. Two of those four successes lost their effect under both scaffold-removal realizations while the underlying request remained present.
4. The workflow reproduced the pinned dataset, model execution, private audit artifact, and safe summary end to end.
5. Human audit exposed concrete judge errors before they contaminated a larger experiment.

## D. What is not yet good enough

1. Conservative eligibility was only 20% on this cross-model 1.5B smoke.
2. Robust scaffold sensitivity was only `2/20 = 10%` over the full development set.
3. The edited context was large, approximately half of the prompt.
4. Candidate edits were selected with human knowledge rather than discovered by the proposed search.
5. One greedy run does not establish sampling, model, or judge robustness.
6. PAIR transferred better than GCG, showing that historical source artifacts are not a neutral evaluation set for a new target model.
7. The heuristic judge substantially overestimated attack success.

## E. Decision

**Decision: CONDITIONAL PROCEED. Do not start wavelet optimization.**

The smoke provides a real but narrow phenomenon signal: some jailbreak successes depend on removable textual framing, and this effect can survive two intervention realizations. However, it does not yet establish small-span localizability or meet Gate 1.

The next experiment must change the evidence quality rather than merely increase sample count:

1. run a 7B-class target model on GPU;
2. construct or select target-aligned successful jailbreaks instead of relying only on transfer from older models;
3. use a validated response judge plus a human-audit subset;
4. freeze multiple decoding settings or explicitly use deterministic evaluation;
5. run exhaustive or budgeted span search only on confirmed eligible pairs;
6. compare deletion, placeholder, and length-aware neutralization;
7. measure minimality and abstain on distributed cases.

If target-aligned 7B experiments still produce fewer than 35% localizable eligible examples, or if valid explanations consistently require roughly half the prompt, the project should pivot from "minimal enabling spans" to a localized-versus-distributed jailbreak-causality characterization.
