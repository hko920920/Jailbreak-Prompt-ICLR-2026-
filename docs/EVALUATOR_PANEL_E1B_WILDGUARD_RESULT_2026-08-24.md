# Evaluator Panel E1B — WildGuard Result

Date: 2026-08-24 (Asia/Seoul)

## Decision

The hardened E1B execution completed successfully.

- workflow run: `32704859942`
- job: `97372967617`
- source commit: `bdf26570ff835498cb9dc85b40eaf379a1080a12`
- safe artifact: `9517659337`
- artifact digest: `sha256:2c22f6d09848df37861eda2f275b813738060cd655b0d1d76073519a6f8534a0`
- final E1B status: `EVALUATOR_PANEL_E1B_WILDGUARD_PASS`
- next authorized operation: `E1C_HARMBENCH_COMPONENT_REPRODUCTION_AND_CANARIES`

This is `DEVELOPMENT` measurement evidence, not paper-valid causal-topology evidence.

## Runtime result

The runtime-only startup hardening resolved the prior ambiguous cancellation/startup state without changing the scientific contract.

- server ready: `true`
- startup time: `5 seconds`
- health status: `200`
- `--no-warmup`: supported and used
- context: `4096`
- CPU threads: `4`
- parallel slots: `1`
- scientific contract changed: `false`

## Exact 200-example reproduction

The live Q8_0 WildGuard run exactly reproduced the predecessor predictions and confusion matrix.

| Metric | Result |
|---|---:|
| Examples | 200 |
| Parse coverage | 1.000 |
| Accuracy | 0.885 |
| Macro-F1 | 0.879426 |
| Balanced accuracy | 0.891975 |
| True positive | 67 |
| True negative | 110 |
| False positive | 17 |
| False negative | 6 |
| False-positive rate | 0.133858 |
| False-negative rate | 0.082192 |

Additional identity checks:

- safe predictions byte-identical to predecessor: `true`
- strict parser predictions match legacy predictions: `true`
- metrics match: `true`
- confusion matrix matches: `true`
- GGUF identity matches: `true`

The prior all-or-nothing single-primary-judge status remains `WILDGUARD_SELECTION_FAIL`. In particular, observed macro-F1 (`0.879426`) remains slightly below the old `0.88` threshold. E1B therefore does **not** promote WildGuard to a standalone ground-truth judge.

## Injection canaries

Twenty-four live requests evaluated 12 cases under the raw official template and the hardened template.

| Mode | Auto decisions | Coverage | Correct | Incorrect | Abstain | Canary leaks |
|---|---:|---:|---:|---:|---:|---:|
| Raw official template | 9 | 0.750 | 8 | 1 | 3 | 0 |
| Hardened template | 7 | 0.583 | 7 | 0 | 5 | 0 |

The hardened path traded coverage for reliability: it abstained more often but made zero incorrect automatic decisions in this canary set. No parse errors, truncations, or canary leaks occurred.

## Scientific interpretation

E1B supports only the following claim:

> At the pinned model, data, parser, and runtime identities, WildGuard is reproducible and can be retained as one hardened, abstaining component for refusal/response-harmfulness measurement.

E1B does not support any of the following:

- WildGuard is a universal or standalone ground-truth evaluator;
- the complete evaluator panel is externally valid;
- any S/F/U attack has succeeded;
- any jailbreak-critical input combination has been identified;
- any causal-topology or paper-level conclusion is established.

## Frozen boundary after E1B

The following remain closed:

- semantic-only Stage A;
- cross-regime Stage A;
- prior evaluation and held-out partitions;
- causal cut-set oracle;
- keep-only sufficiency oracle;
- wavelet.

The next operation is the independent HarmBench behavior-compliance component qualification. The full evaluator panel must still qualify its actionability, capability-confound, and external selective-risk/coverage axes before any attack outcome screen is opened.
