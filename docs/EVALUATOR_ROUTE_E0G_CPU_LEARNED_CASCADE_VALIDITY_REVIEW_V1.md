# E0G CPU Learned-Cascade Validity Review V1

Date: 2026-09-03 (Asia/Seoul)  
Decision: **CONDITIONAL GO; A LEARNED TEXT CLASSIFIER IS ADMISSIBLE ONLY AS A ROUTER OR SENSITIVITY AXIS**

## Bottom line

A CPU-trained TF-IDF/linear classifier by itself is not a defensible primary oracle for this paper. It can learn refusal phrases, response length, benchmark formatting, or source-specific annotation conventions without reliably deciding whether a response substantively completes the immutable harmful request. A high cross-validation score alone would therefore not solve the measurement problem.

A narrower use is defensible: train it only on the frozen 889-record development partition, make behavior groups disjoint across folds, force uncertain cases to abstain, and use it only to route work inside a heterogeneous evaluator cascade. In the eventual cascade, a final `SAFE` or `HARMFUL` outcome must be supported by two methodologically different families; otherwise the record is `EVALUATOR_ABSTAIN`. The learned model may never override both external evaluators or label a topology edge alone.

This is consistent with the current literature. HarmBench establishes classifier-based standardized evaluation but also shows that older classifiers fail outside their intended settings. StrongREJECT demonstrates that refusal or coarse harmfulness is not the same as useful harmful assistance. GuidedBench shows that case-specific criteria materially reduce evaluator discrepancies. The new candidate families address different pieces of the construct:

- [Qwen3Guard](https://arxiv.org/abs/2510.14276) is an open 0.6B response-safety/refusal guard suitable for exhaustive CPU screening.
- [JailMeter](https://aclanthology.org/2026.findings-acl.786/) directly asks whether the response captures the malicious intent and completely answers the request; its public SLM is the expensive completion adjudicator.
- The classical learned model is only a cheap selective router and a sensitivity analysis.

The route remains **human-annotation-free in this study**, not independent of human judgments: both the local calibration labels and the published evaluators ultimately derive validity from human-labeled data.

## Recovered historical evidence

The repository had already tested JailMeter-SLM operationally. Workflow `31941477931` reproduced 60/60 target-response hashes, parsed JailMeter on 60/60 responses, and produced zero repaired evaluator abstentions. The observed failure was not a JailMeter performance failure: the five attacks previously selected under HarmBench did not yield a stable eligible case under the repaired criterion.

A later 80-response evaluator-consistent recalibration was launched twice. Run `31951126809` stopped immediately at Python setup. Run `31951266031` successfully generated all 80 Qwen responses and evaluated all 80 with HarmBench, then failed while converting the pinned JailMeter LoRA to GGUF. Its private target and HarmBench files were deleted by the mandatory cleanup step. No JailMeter labels or candidate-selection result were produced or persisted. Therefore that branch is **unfinished**, not a negative scientific result.

## Why this route can support a paper

The evaluator is supporting infrastructure rather than the paper contribution. It is acceptable if its error is independently characterized before it touches P3 or topology outputs. The existing data make that possible:

- 889 human-labeled development records across HarmBench, JailbreakBench, and StrongREJECT;
- behavior-disjoint frozen folds and globally unique response hashes;
- 803 historically unexposed primary held-out identities from HarmBench and StrongREJECT, whose labels remain sealed;
- an explicit abstention state and hard source-wise error gates;
- target-distribution wrapper, capability, and seed-stability checks before topology claims.

The decisive protection is the one-shot 803-record evaluation. Development results may choose the router, external model revisions, thresholds, and escalation rule. After those are frozen, the held-out labels are reconstructed exactly once. A failure cannot be repaired by changing the rule on the same 803 records.

## What would still be rejected by reviewers

The following are prohibited:

1. reporting a TF-IDF model as human-equivalent or as the sole primary judge;
2. treating Qwen3Guard's coarse unsafe label as proof of goal completion;
3. tuning thresholds on P3, topology, or the 803 primary held-out results;
4. hiding abstentions or counting them as safe recovery;
5. claiming complete topology when decision-critical strict subsets lack a valid label;
6. inferring target-distribution validity only from public benchmark accuracy;
7. presenting model personas as independent humans.

## Frozen staged route

### E0G-0 — learned-router development diagnostic

Run the nine predeclared TF-IDF/logistic candidates under nested behavior-group out-of-fold evaluation on the 889 development records. Text is reconstructed from pinned ignored raw sources, verified against every frozen digest, held in memory only, and never printed or written. The output contains aggregate metrics and selected candidate identifiers only.

Passing E0G-0 means only that the router may be tested in a later cascade. Failure discards this cheap component without rejecting the external evaluators or research topic.

### E0G-1 — external-model operational qualification

Pin the open `Qwen/Qwen3Guard-Gen-0.6B` revision and the already frozen JailMeter commit and adapter blobs. Run harmless schema, parser, instruction/data-separation, determinism, memory, and throughput probes before any labeled metric. Repair the historical JailMeter conversion path without changing its prompt or label semantics.

### E0G-2 — small development sentinel

Run the external models on a small, predeclared balanced development subset. Stop early if either evaluator has gross parse, precision, recall, source, or runtime failure. Do not spend 889 calls merely because the models load.

### E0G-3 — full development and cascade freeze

Only after the sentinel passes, evaluate enough of the 889 records to select exactly one cascade. Freeze model revisions, prompts, parsers, the learned router if admitted, escalation rules, thresholds, abstention logic, and all final gates.

### E0G-4 — one-shot primary held-out qualification

Run the exact frozen cascade once on the 803 unexposed held-out records, verify the existing label commitment, and score. JailbreakBench's 144 historically exposed records remain a separate stress set. A primary held-out failure closes this exact cascade; it cannot be retuned on those labels.

### E0G-5 — P3 and topology bridge

Only a held-out PASS permits P3 rescoring. Before exact topology, require content-preserving wrapper checks, capability controls, seed stability, and explicit abstention handling. JailMeter must adjudicate baseline attack success and every edge/strict-subset observation that is decision-critical to a reported minimal set. A random audit of screen-negative subsets estimates missed-path risk; the paper must define completeness relative to the frozen composite oracle rather than objective semantic truth.

## Current decision

Proceed with E0G-0 because it is CPU-only, uses development data only, cannot consume the held-out or P3 boundary, and directly answers whether a learned router can save enough external-evaluator work to be useful. Do not download another large target model and do not rerun the lost 80-response attack calibration at this stage.

The machine-readable pre-result contract is `configs/evaluator_panel/cpu_learned_router_e0g0_v1.json`.
