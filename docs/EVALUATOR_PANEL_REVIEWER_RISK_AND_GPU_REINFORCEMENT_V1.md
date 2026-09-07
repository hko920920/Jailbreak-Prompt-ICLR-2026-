# Evaluator Panel Reviewer-Risk and GPU-Reinforcement Plan v1

Date: 2026-09-03 (Asia/Seoul)

State: **CURRENT REVIEW-RISK ASSESSMENT; E0G-4 RULE UNCHANGED; HELD-OUT SEALED**

## Bottom line

The current E0G pipeline is methodologically valid as a qualification pipeline
for a selective automatic evaluator. E0G-4 alone is not sufficient to make the
panel a paper-grade oracle. A full-development pass must be followed by a
prospectively frozen one-shot held-out pass, explicit domain-shift safeguards,
and topology-level evaluator sensitivity.

The strongest honest description of the current pair is **heterogeneous by
evaluation objective and training procedure**. It is not independent by model
vendor or base-model lineage: Qwen3Guard-Gen-0.6B is based on Qwen3, while
JailMeter-SLM is a LoRA fine-tune of Qwen2.5-7B-Instruct.

## What the current design already handles well

- exact model, LoRA, tokenizer, prompt, parser, decoding, runtime, and device
  identities are recorded;
- operational qualification precedes scientific evaluation;
- the decision rule was fixed before the 889-record run;
- unsafe/non-refusal and request-completion constructs must agree;
- disagreements become `ABSTAIN`, not a forced majority label;
- 889 development records span three public human-labelled sources, 265
  behavior groups, and five behavior-disjoint folds;
- full gates include class precision, Wilson lower bounds, recall, coverage,
  decided error, source/fold stability, unanimity, behavior-group coverage, and
  10,000-replicate behavior-cluster bootstrap intervals;
- the primary 803-record held-out manifest is behavior-disjoint and its row
  labels remain sealed;
- historically exposed JailbreakBench rows cannot determine the primary
  held-out result;
- abstentions and capability-confounded cases cannot certify a recovery edge.

These controls make the pipeline substantially stronger than selecting one LLM
judge and quoting its raw accuracy.

## Reviewer objections that remain

| Risk | Severity | Honest response and required mitigation |
|---|---|---|
| External-benchmark to intervention-response distribution shift | High | A held-out benchmark pass does not prove validity on neutralized jailbreak responses. Preserve abstention, report all topology attrition, rerun pivotal edges, and require conclusion stability across admitted evaluator variants. |
| Shared Qwen lineage | Medium-high | Do not call the two axes model-family independent. Add a prospectively chosen non-Qwen evaluator as a sensitivity or stricter confirmation axis when compute permits. |
| Public benchmark exposure | Medium-high | “Held-out” means untouched by this project, not guaranteed absent from evaluator pretraining or model selection. Qwen3Guard reports HarmBench evaluation, and JailMeter-SLM was distilled on 10,400 responses derived from 520 AdvBench questions and nine attacks. Report source-specific results and add a fresh source or governed human audit if stronger independence is required. |
| Selective-label missingness | High | High precision obtained by abstaining can bias which attacks receive topology. Keep minimum coverage/recall gates, disclose selection rates by source/family/category/model, and treat unresolved cases as a primary outcome. |
| False-safe labels corrupt minimality | High | The held-out safe-precision gate must remain stricter than the harmful-precision gate. Every reported minimal edge and its strict-subset closure must be repeated across seeds and checked under a stricter evaluator sensitivity rule. |
| Heterogeneous public label definitions | Medium | Preserve the frozen ontology mapping, publish each source separately, report unanimous versus split-vote results, and avoid calling the aggregate universal ground truth. |
| Quantized development targets and one local GPU | Medium | Treat local Q4 topology as development. Use future compute for canonical or higher-precision target-model confirmation and a second model family before broad claims. |
| No newly recruited humans | Medium-high | State “no new human annotation in this study,” rely on pinned public human labels, and limit claims to the qualified automatic-panel domain. A fresh in-domain audit remains the cleanest optional response to construct-validity criticism, but is not silently simulated with personas. |

## Why the two axes are still useful

[Qwen3Guard](https://arxiv.org/abs/2510.14276) is a response safety and refusal
classifier. Its report explicitly notes annotation noise and evaluates response
classification on HarmBench, among other safety benchmarks. It does not by
itself establish that a response substantially completes a particular harmful
request.

[JailMeter](https://aclanthology.org/2026.findings-acl.786/) defines success in
terms of correctly understanding malicious intent and giving a complete,
on-topic answer. Its 330-example JailMeter-Eva benchmark is human labelled, and
the paper reports 97.27% accuracy for the full framework; its released SLM is a
distilled Qwen2.5-7B evaluator. This is relevant external support, not a
guarantee on the present intervention distribution.

The fixed intersection is therefore construct-motivated: one axis supplies
safety/refusal evidence and the other supplies request-completion evidence. The
E0G-2 complementary error pattern is an empirical reason to test the
intersection at full scale, not proof of independence.

[StrongREJECT](https://arxiv.org/abs/2402.10260) shows why completion and
capability matter: several common automatic evaluators overstate jailbreak
success relative to human judgments. [GuidedBench](https://arxiv.org/abs/2502.16903),
published at ICLR 2026, similarly reports large discrepancies from generic
evaluation and reduces inter-evaluator variance using question-specific
guidelines. These results support conservative multi-construct evaluation, but
also motivate the domain-shift objection above.

## Best use of a newly available GPU

### If it arrives before primary held-out execution

This is the best timing. After E0G-4 finishes:

1. do not open the 803 held-out row labels;
2. inventory the GPU and run harmless runtime/equivalence checks;
3. select a genuinely non-Qwen evaluator by provenance, task fit, license, and
   available exact implementation;
4. qualify and analyze that auxiliary axis only on the 889 development records;
5. freeze whether it is a non-gating sensitivity axis or a stricter triple
   intersection before any held-out model call;
6. freeze hardware, models, rules, and gates together;
7. run the primary held-out test once.

The existing Qwen-plus-JailMeter primary rule must not be retroactively changed
merely because a third axis gives a more favorable result. If a new primary
panel is proposed, it is a new version and must retain an untouched test source.

### If it arrives after primary held-out labels have been opened

Do not use the 803 labels to tune and then re-certify an expanded evaluator.
The GPU can still strengthen the paper through:

- a predeclared non-Qwen sensitivity analysis on topology responses;
- a new independently labelled benchmark or prospective human-audit set;
- canonical BF16 or otherwise higher-fidelity target-model confirmation;
- a second target-model family and additional attack families;
- more decoding seeds and repeated full-response validation;
- white-box baselines such as Token Highlighter or Mask-GCG-style scores where
  their exact assumptions apply;
- canonical GCG generation if the actual memory/runtime preflight passes.

These are confirmatory additions. They cannot turn a failed frozen evaluator
gate into a pass.

## Recommended stage decision

1. Finish E0G-4 unchanged on the RTX 3070.
2. If E0G-4 fails, keep held-out and topology sealed; use the new GPU only under
   a genuinely new evaluator contract.
3. If E0G-4 passes and GPU access is imminent, pause before held-out freeze.
4. Admit the new device and decide the non-Qwen auxiliary axis on development.
5. Execute the final frozen held-out contract once.
6. Only a held-out pass authorizes P3 rescoring and a no-new-human topology
   micro-pilot.
7. Use the larger GPU primarily to expand target-model fidelity, attack/model
   diversity, repetitions, and baselines—the empirical ingredients that decide
   whether the paper contribution is real.

## Current claim

The present pipeline is **defensible but not reviewer-proof**. Its prospective
controls are strong enough to justify continuing. Its residual weaknesses are
known and can be reduced substantially with a non-Qwen confirmation axis and
new-GPU target-model confirmation, but no amount of GPU compute alone proves
that automatic labels equal fresh in-domain human judgments.
