# E0G-0 CPU Learned Router Result V1

Date: 2026-09-03 (Asia/Seoul)  
Evidence class: **DEVELOPMENT-ONLY NESTED OOF ROUTER DIAGNOSTIC; NOT PANEL QUALIFICATION; NO TOPOLOGY EVIDENCE**

Decision: **FAIL AND DISCARD THE CLASSICAL LEARNED ROUTER**

## Bottom line

The frozen TF-IDF/logistic family is not reliable enough to reduce external-evaluator work under the predeclared selective-routing contract. The safe branch was precise, but harmful prediction had inadequate precision, confidence, recall, and source stability. One of five outer folds could not select any candidate that met even the inner development constraints.

The result does not test Qwen3Guard, JailMeter, P3, or the neutralizer-topology hypothesis. It only rejects this nine-candidate classical router family. The thresholds and role will not be weakened after observing the result, and the classifier will not be repurposed post hoc as a safe-only decider.

## Frozen design

- development records: 889;
- human harmful / safe: 290 / 599;
- behavior groups: 265, with no group crossing the five frozen outer folds;
- sources: HarmBench, JailbreakBench, StrongREJECT;
- candidates: word, character, and word+character TF-IDF crossed with logistic-regression C values 0.25, 1, and 4;
- selector: nested behavior-group OOF with a fixed selective threshold grid;
- output labels: `HARMFUL`, `SAFE`, or `ABSTAIN`;
- raw goal/response text: reconstructed from exact ignored sources, digest-checked, held in memory only, and never printed or written;
- held-out, P3, and topology: unopened.

## Primary nested-OOF result

| Metric | Observed | Gate | Result |
|---|---:|---:|---|
| Outer folds with a defined selector | 4/5 | 5/5 | FAIL |
| Decided coverage | 0.3588 | >= 0.35 | PASS |
| Harmful precision | 0.8889 | >= 0.90 | FAIL |
| Harmful precision Wilson 95% lower | 0.7781 | >= 0.85 | FAIL |
| Harmful recall | 0.1655 | >= 0.40 | FAIL |
| Safe precision | 0.9660 | >= 0.95 | PASS |
| Safe precision Wilson 95% lower | 0.9367 | >= 0.90 | PASS |
| Predicted harmful / safe | 54 / 265 | >= 40 / >= 80 | PASS |
| Decided error rate | 0.0470 | descriptive | — |

The pooled confusion counts were 48 harmful true positives, 6 harmful false positives, 256 safe true positives, and 9 harmful responses incorrectly predicted safe. The remaining 570 records abstained.

## Source and annotation-agreement audit

| Source | Coverage | Harmful precision | Harmful recall | Decided error |
|---|---:|---:|---:|---:|
| HarmBench | 0.3003 | 0.8621 | 0.1773 | 0.0769 |
| JailbreakBench | 0.3289 | 0.8889 | 0.2963 | 0.0400 |
| StrongREJECT | 0.4101 | 1.0000 | 0.0737 | 0.0337 |

On the 728 unanimous human-label records, decided error was 0.0208 and harmful precision was 0.9512, but harmful recall remained only 0.2031. On the 161 split-vote records, coverage fell to 0.1925 and decided error rose to 0.2903. This confirms that abstention helps on obvious examples but does not turn the model into a robust completion judge.

Leave-one-source-out transfer also failed as a general solution. When StrongREJECT was held out, the two-source training data could not select any admissible rule. On the other held-out sources, the harmful recall was 0.2482 for HarmBench and 0.0185 for JailbreakBench.

## Field ablations

- response-only: coverage 0.3993, harmful precision 0.8750, harmful recall 0.1690;
- goal-only negative control: coverage 0.1417, harmful precision 0.4444, harmful recall 0.0138;
- full goal+response: coverage 0.3588, harmful precision 0.8889, harmful recall 0.1655.

The goal-only collapse is expected. More importantly, adding the goal to the response did not materially improve harmful recall over response-only text. The model therefore supplies no convincing evidence that it learned request-conditioned substantive completion rather than response-surface cues.

## Integrity and verification

- preflight status: `E0G0_CPU_LEARNED_ROUTER_PREFLIGHT_PASS`;
- preflight identity: `f6fc039b294ef9f0fb58618f3c59ca8675e2e84e22017ca9b6ebbad9f8e9224c`;
- result status: `E0G0_CPU_LEARNED_ROUTER_DIAGNOSTIC_FAIL`;
- result identity: `aee2d6b5627d2c7f3a7abfad7cbcd1af5ab217466cdc985e3a78066b76aaae59`;
- focused tests: 4/4 passed before execution;
- Ruff: passed;
- mypy: passed for the new module and runner;
- new foundation-model inference: none;
- raw text or per-record prediction persisted: none;
- primary 803 held-out labels opened: false;
- P3 responses opened: false;
- topology outcomes opened: false.

## Authoritative artifacts

- validity review: `docs/EVALUATOR_ROUTE_E0G_CPU_LEARNED_CASCADE_VALIDITY_REVIEW_V1.md`;
- contract: `configs/evaluator_panel/cpu_learned_router_e0g0_v1.json`, SHA-256 `e9bdb77f3d39ae105ff054ce65ad5525f613bae7ec131e1d79a221825875dfd5`;
- runner: `scripts/audit_evaluator_cpu_learned_router_e0g0.py`, SHA-256 `a2925f2fb19768c60ee4417373dba094cec8e6a44df2da40eb4441b9f9abbdb9`;
- module: `src/jbspan/evaluator_cpu_router.py`, SHA-256 `806272344055f6db6abc95b7b28442d1eeb98fae1ad64eb885f047d971179637`;
- preflight: `data/evaluator_panel_v2/e0g0_cpu_learned_router_preflight.safe.json`, SHA-256 `07c5d1d3d04f9f4548ae936304b5668eec9bd45942fde3aa5a0e0347c02659f8`;
- result: `data/evaluator_panel_v2/e0g0_cpu_learned_router_result.safe.json`, SHA-256 `3047daded887c3572beedbf89a9396a6b166e65772d386ecea754e612b5791ec`.

## Next authorized decision

Do not tune or reuse this classical router. Decide whether the direct, heterogeneous `Qwen3Guard-Gen-0.6B + JailMeter-SLM` route is operationally affordable. The next result-bearing action, if pursued, must first freeze and pass a harmless runtime/parser/throughput qualification. It may not open the 803 held-out labels, P3 responses, or topology outcomes.
