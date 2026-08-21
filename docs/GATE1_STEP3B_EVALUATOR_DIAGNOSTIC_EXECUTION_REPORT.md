# Automated Gate 1 — Evaluator Diagnostic Execution Audit

Date: 2026-08-16 (Asia/Seoul)

## First complete execution

Workflow run `31941477931`, job `95151212278`, completed the entire frozen evaluator diagnostic before its result-persistence step:

- exact target response hash reproduction: `60/60` in that run;
- old StrongREJECT parse failures audited: `7`;
- JailMeter parsed: `60/60`;
- repaired evaluator abstention: `0/60`;
- original stable non-success: `10/10`;
- diagnostic stable eligible: `0/10`;
- diagnostic eligible candidates: `0`;
- final evaluation and Gate 2 held-out remained unopened.

The local result commit contained all eight safe output files, but the push was rejected as non-fast-forward because the branch changed while the long-running job was active. Private files were then destroyed by the mandatory cleanup step. The scientific output remains visible in the immutable workflow log, but the full safe bundle was not persisted.

## Controlled rerun

A rerun was launched only after partial result files were removed and branch writes were stopped. It used the same model GGUF hashes, llama.cpp commit, prompts, seeds, and generation parameters. The run stopped at the cross-run byte-identity guard because at least one stochastic response hash differed across hosted CPU runners.

This does not invalidate the first diagnostic or indicate model/evaluator drift. It demonstrates that byte-identical cross-run generation is an over-strong reproducibility requirement for temperature `0.6` on heterogeneous hosted CPUs.

## Frozen scientific interpretation

1. The Phi-based StrongREJECT surrogate is retired as a Gate decider because of parse failures and substantive disagreements.
2. Pinned JailMeter is operationally usable: complete parsing and zero repaired abstention were observed in the complete diagnostic execution.
3. The five candidates selected by HarmBench-only calibration did not yield a stable eligible case under the repaired evaluator on the old diagnostic smoke.
4. The old smoke is not relabelled or promoted to confirmatory evidence.
5. Before any fresh confirmatory smoke, all seven candidates must be reselected on the dedicated calibration split under the same JailMeter–HarmBench contract.
6. The final 30, causal oracle, adaptive search, and wavelet remain blocked.
