# Gate 1 External Stage-Transition Protocol

Date: 2026-08-20 (Asia/Seoul)

## Purpose

GitHub suppresses new workflow triggers for pushes performed by another workflow's default `GITHUB_TOKEN`. Gate 1 therefore uses an external repository write between completed scientific stages. This transition mechanism changes no model output, label, split, threshold, prompt, seed, or scientific decision.

## Frozen transition sequence

1. Official WildGuard `Q8_0_DIRECT` selection and conditional validation.
2. WildGuard wrapper-stability audit.
3. Fresh 10-case confirmatory smoke.
4. Sealed 30-payload × 5-candidate final eligibility evaluation.
5. Exact typed-component causal oracle and Gate 1 decision.

## Transition rule

After a stage commits its immutable safe decision:

- the decision is read exactly as committed;
- an external connector either creates the next stage's compatibility decision alias or appends an operational transition field that is ignored by all scientific code;
- the external commit triggers the already-frozen next-stage workflow;
- the scientific decision fields are not changed;
- raw prompts, responses, model weights, and judge outputs are never committed.

## Stop rules

- Q8 selection failure closes the automatic-evaluator path; no additional runtime candidate or threshold relaxation is allowed.
- Q8 validation failure blocks wrapper and all response-facing Gate 1 experiments.
- Wrapper-stability failure blocks confirmatory smoke.
- Confirmatory failure keeps the final 30-payload split sealed.
- Final-eligibility failure blocks causal intervention and yields `GATE1_STOP_OR_NARROW` through the frozen exact-oracle gate.
- Wavelet, adaptive search, and Gate 2 remain disabled until the exact Gate 1 decision is committed.

## Audit boundary

External stage transitions are operational control-plane events, not scientific observations. Every transition commit records only safe metadata and remains independently inspectable in Git history.
