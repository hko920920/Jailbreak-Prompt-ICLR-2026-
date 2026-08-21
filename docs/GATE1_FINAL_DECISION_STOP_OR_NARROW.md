# Gate 1 Final Decision — STOP OR NARROW

Date: 2026-08-20 (Asia/Seoul)

Status: **GATE1_STOP_OR_NARROW**

## Executive decision

The current Gate 1 formulation is stopped before confirmatory smoke, final eligibility, and the causal oracle.

This decision applies specifically to the current formulation:

> free-form jailbreak responses, no new human annotations, and a single externally validated automatic primary judge.

The operational pipeline succeeded. The measurement gate did not.

The causal-localization hypothesis itself was **not** tested by the exact oracle and therefore is neither confirmed nor falsified by this decision.

## Completed work

- exact-payload-preserving attack programs and typed provenance were frozen;
- calibration selected five published-source attack candidates without case-specific rewriting;
- the original untouched smoke exposed substantive evaluator disagreement;
- public human-majority data were used to screen automatic evaluator candidates;
- official WildGuard was run at Q4_K_M and, under a predeclared fidelity contingency, at Q8_0_DIRECT;
- both WildGuard runs completed operationally and produced complete 200-example selection matrices;
- final evaluation 30, Gate 2 held-out 10, wrapper stability, fresh confirmatory smoke, causal oracle, adaptive search, and wavelet remained sealed.

## Frozen WildGuard results

| Metric | Required | Q4_K_M | Q8_0_DIRECT | Decision |
|---|---:|---:|---:|---|
| Parse coverage | >= 0.98 | 1.000000 | 1.000000 | PASS |
| Accuracy | >= 0.88 | 0.885000 | 0.885000 | PASS |
| Macro-F1 | >= 0.88 | 0.879426 | 0.879426 | **FAIL** |
| False-negative rate | <= 0.12 | 0.082192 | 0.082192 | PASS |
| False-positive rate | <= 0.15 | 0.133858 | 0.133858 | PASS |

Both runs produced the same confusion matrix:

```text
TP = 67
TN = 110
FP = 17
FN = 6
```

The frozen threshold is not rounded down or relaxed after observing the result.

## Q4–Q8 fidelity audit

The Q8 check was declared before the Q4 selection result was observed. It was the only permitted higher-fidelity runtime confirmation.

Across the same 200 selection examples:

```text
binary prediction changes        0 / 200
binary prediction agreement      1.000
parsed-status changes            0 / 200
response-harmfulness changes     0 / 200
response-refusal changes         0 / 200
```

Therefore the failed Macro-F1 threshold cannot reasonably be attributed to Q4 quantization. Another runtime, quantization level, evaluator substitution, or threshold relaxation is not permitted in the current Gate 1 contract.

## Why downstream stages remain sealed

The predeclared continuation rule requires WildGuard Q8 to pass both the 200-example selection set and the untouched 100-example validation set before it can become the primary judge.

Because selection failed:

- validation 100 was not opened;
- wrapper stability is not authorized;
- the fresh unused ten-case confirmatory split is not executed;
- the final 30-payload split is not opened;
- the exact typed-component oracle is not executed;
- adaptive search and wavelet analysis are not executed;
- Gate 2 held-out examples remain unused.

Opening those stages would require changing the measurement contract after observing results.

## Scientific interpretation

### What failed

The current study did not secure an automatic evaluator that satisfies every predeclared external measurement threshold for free-form harmful-compliance responses without new human annotation.

### What did not fail

The following scientific question remains open:

> Do successful compositional jailbreaks have compact, interactive, or distributed causal input structure?

That question was not reached because the study could not establish a sufficiently qualified primary response judge under the frozen contract.

### Reviewer-safe conclusion

The defensible conclusion is not that causal jailbreak localization is impossible. It is:

> Under the frozen human-free free-form-response protocol, evaluator choice remains decision-critical, and the final official evaluator missed the qualification gate even at higher runtime fidelity.

This is a real measurement result, not a code failure.

## Permitted next operation

The next study must be designed before observing new target outputs and must narrow the response-success criterion to something independently and programmatically verifiable. Suitable directions include:

- structured outputs with exact required fields and forbidden-field checks;
- executable code tasks with sandboxed behavioral tests;
- deterministic target-string or state-transition objectives;
- tool-use environments with verifiable side effects;
- a separately preregistered study that explicitly permits a small external human adjudication set.

The present final 30 and Gate 2 held-out partitions must not be recycled into development data for that redesign.

## Immutable decision

```text
OPERATIONAL_PIPELINE = PASS
AUTOMATIC_MEASUREMENT_GATE = FAIL
PRIMARY_EVALUATOR = NONE
Q4_Q8_BINARY_AGREEMENT = 1.000
FURTHER_RUNTIME_CANDIDATES = FORBIDDEN
THRESHOLD_RELAXATION = FORBIDDEN
FRESH_CONFIRMATORY = SEALED
FINAL_30 = SEALED
CAUSAL_ORACLE = SEALED
GATE2_HELDOUT = UNUSED
GATE1 = STOP_OR_NARROW
```
