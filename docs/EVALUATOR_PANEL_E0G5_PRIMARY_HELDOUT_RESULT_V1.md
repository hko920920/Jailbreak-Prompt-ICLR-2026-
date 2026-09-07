# E0G-5 Primary Held-out Qualification Result V1

Date: 2026-09-04 (Asia/Seoul)  
Execution completed: 2026-09-03  
Evidence class: **ONE-SHOT BEHAVIOR-DISJOINT PUBLIC HELD-OUT EVALUATOR QUALIFICATION**  
Decision: **PRIMARY PASS; EXPOSED JAILBREAKBENCH STRESS WEAK; NO TOPOLOGY CLAIM**

## What this result decides

The unchanged Qwen3Guard-Gen-0.6B plus JailMeter-SLM conservative-intersection panel passed the
predeclared held-out qualification gate. It may therefore be used as the fixed selective automatic
outcome panel in the next topology experiment, subject to separately frozen capability-control,
abstention, seed-propagation, and topology rules.

This result does **not** show that the minimal-neutralizer topology hypothesis is true. It does not
open P3 responses or topology outcomes, does not establish human-equivalent judgment, and is not a
paper-valid topology result.

## Protocol integrity

- Both axes were completed and made immutable before the committed public labels were opened.
- The label opening reconstructed exactly 947 committed rows and 581,313 committed bytes with
  SHA-256 `bf339548e26e8dc919ee916dbd885c2c97c0dac12e18da416ae2b409e8e1932e`.
- Primary decision set: 803 previously untouched HarmBench/StrongREJECT records across 161
  behavior groups.
- Mandatory non-decisive stress set: 144 JailbreakBench records across 94 behavior groups. These
  records were excluded from primary pass/fail because of documented historical development
  exposure.
- Qwen3Guard parsed 947/947 outputs with zero output-limit stops.
- JailMeter parsed 943/947 outputs. The four unparsed outputs were all exactly at the frozen
  1,536-token boundary and were conservatively counted as effective output-limit stops; the
  all-record stop fraction was 4/947 = 0.004224, below the frozen 0.01 ceiling.
- No raw prompt, raw response, raw generated output, or per-record human label was written into
  the result or independent-verification artifact.
- P3 and topology outcomes remained unopened.

## Primary result

The panel made 534 decisions and abstained on 269 of 803 records. Of the 534 decisions, 515 were
correct and 19 were wrong.

| Metric | Observed | Frozen requirement | Result |
|---|---:|---:|---|
| Decided coverage | 0.6650 | at least 0.50 | pass |
| Decided error | 0.0356 | at most 0.075 | pass |
| Harmful precision | 0.9186 | at least 0.90 | pass |
| Harmful-precision Wilson lower | 0.8680 | at least 0.85 | pass |
| Harmful recall | 0.6667 | at least 0.40 | pass |
| Safe precision | 0.9862 | at least 0.95 | pass |
| Safe-precision Wilson lower | 0.9681 | at least 0.90 | pass |
| Safe recall | 0.6307 | at least 0.50 | pass |

The exact pooled confusion counts were 158 true-harmful, 14 false-harmful, 357 true-safe, and 5
false-safe decisions. All 27 frozen checks passed; no threshold, parser, prompt, or combination
rule was changed after labels were opened.

The 10,000-replicate behavior-cluster bootstrap also cleared every frozen lower-bound check:

- harmful-precision 95% interval: 0.8722--0.9583;
- safe-precision 95% interval: 0.9716--0.9971;
- decided-coverage 95% interval: 0.6250--0.7085;
- decided-error 95% interval: 0.0198--0.0563;
- harmful-recall 95% interval: 0.5853--0.7433;
- safe-recall 95% interval: 0.5819--0.6847.

## Source, fold, and agreement diagnostics

- HarmBench: 289 records, 0.7128 coverage, 0.0680 decided error, 0.8830 harmful precision,
  0.6434 harmful recall, 0.9732 safe precision, and 0.6813 safe recall.
- StrongREJECT: 514 records, 0.6381 coverage, 0.0152 decided error, 0.9615 harmful precision,
  0.6944 harmful recall, 0.9920 safe precision, and 0.6108 safe recall.
- All source-specific frozen gates passed. HarmBench harmful precision was below the pooled 0.90
  threshold, but no per-source precision gate had been predeclared; it must be reported as a
  limitation rather than converted post hoc into a new gate.
- Across the five behavior-disjoint reporting folds, coverage ranged from 0.6026 to 0.7833 and
  decided error ranged from 0.0227 to 0.0909. Every frozen fold gate passed.
- At least one decision was produced for 148/161 behavior groups. The source-specific rates were
  129/142 for HarmBench and 19/19 for StrongREJECT.
- On 664 unanimous-reference records, coverage was 0.7033 and decided error was 0.0086. On 139
  split-vote records, coverage fell to 0.4820 and decided error rose to 0.2239. This is the clearest
  observed weakness and prevents treating the panel as a general human-equivalent oracle.

## Exposed JailbreakBench stress result

The mandatory but non-decisive JailbreakBench stress set was materially weaker: 68 decisions from
144 records, 0.4722 coverage, 0.1029 decided error, 0.8077 harmful precision, 0.3750 harmful recall,
0.9524 safe precision, and 0.4545 safe recall. Its behavior-cluster bootstrap lower endpoints were
0.6250 for harmful precision, 0.8864 for safe precision, and 0.3983 for coverage.

This stress result would not support claiming uniformly strong performance across all public
jailbreak distributions. It does not reverse the primary outcome because its non-decisive status
was frozen before inference and follows from historical exposure, not from the observed score.

## Independent reconstruction

An independently implemented metric verifier reconstructed the source commitment, exact ID/order
of both 947-row axes, every panel decision, primary and stress aggregates, both 10,000-replicate
behavior-cluster bootstraps, all 27 gates, and canonical artifact identities. It reproduced the
authoritative PASS exactly. The verifier deliberately reuses the already frozen E0B source loader
for source normalization, so this is independent metric/gate reconstruction rather than a second
independent dataset-ingestion implementation. The pre-existing byte commitment guards the loaded
label payload. A second verifier invocation produced the same verification file byte-for-byte.

Verification results:

- status: `E0G5_INDEPENDENT_RECONSTRUCTION_PASS`;
- gate failures: zero;
- focused tests: 12/12 pass;
- complete test suite: 413/413 pass;
- Ruff over `src`, `tests`, and `scripts`: pass;
- mypy over the four E0G-5 production files: pass.

Repository-wide mypy is not clean: 373 existing errors remain across 57 mostly historical scripts.
This does not change the reproduced E0G-5 metrics, but it is recorded rather than misrepresented as
a repository-wide static-type pass.

## Frozen identities

- contract SHA-256: `a38884ba38484b492417bf00ecbb31ec6cf16e46c715c2157b8938ea3c43218b`;
- execution runner SHA-256: `935c53a42ce8895a26960a1f850fb48df657ec7983dfd27932d7f6418bb64473`;
- independent verifier SHA-256: `f49af3f16f9768c11cb774f8cca5843fa39b9878435433fb9da4a526574ac5cf`;
- selection file SHA-256: `8a08ff438ffaeaa936e336faebcef6e6a0c5f224127096b881437973767de6a6`;
- Qwen axis SHA-256: `26ad660f021e7810a67cceaee80514b1c990a74d44ccfbe98588bdabf0ba71b8`;
- JailMeter axis SHA-256: `e3fcbd91b909eeb7cb59ee19e47b0a597a458ba1d8af0601518df148d59feb6c`;
- label-opening receipt SHA-256:
  `74c4db782c6237d1aaa7b5973284af44fe3ac3e5c91680f2de92328e002d64b7`;
- result file SHA-256: `5862f07fd8f38f4e413d98ca11a92eb55885cd318efd15aa59d2dd15f410d1f3`;
- result identity: `f0c5aed5199baa7a014644d3a925ed8883487e5be8bd2c0a12105306f25949c9`;
- independent-verification file SHA-256:
  `50d8c7856274b6cf3cf98a6f79b035d6bc1fad10337a994b7c3b67bd03a1ac7e`;
- independent-verification identity:
  `a0d2f10d1ec290e236359965d20ed4cf7f3c5b37ace87fd5444007c24eeb377a`.

## Decision and next operation

The evaluator qualification stage is complete. The result is strong enough to proceed, but only
as a precision-oriented selective automatic panel with explicit abstention and uncertainty. It is
not evidence that the paper's central topology contribution works.

Before any P3 response or topology outcome is opened, freeze the capability-control outcome,
abstention treatment, seed aggregation/propagation, unit vocabulary, neutralizers, exact-minimality
search, and stopping rules. Then execute a small nontrivial topology pilot. Only that pilot can
begin answering whether multiple robust strict-subset-minimal recovery sets actually exist and can
be recovered reliably.
