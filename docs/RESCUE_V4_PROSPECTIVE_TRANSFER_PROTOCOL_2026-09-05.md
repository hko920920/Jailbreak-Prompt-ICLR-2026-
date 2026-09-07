# V4 prospective new-problem validation -- 2026-09-05

## Status and scope before outputs

The V3 discovery pilot found four blank-to-omit failures of strictly minimal repairs on two
underlying task problems. Its generation, selection and results remain immutable. V4 tests
these discovered repair locations on a separately generated fixed input panel; it does not
retroactively turn V3 into confirmation or rescue the old D3/C1N gates. The author authorized
continued rescue and careful ongoing records. Manuscript/PDF work and old A/B access remain
stopped. This protocol is written before any V4 target output.

The question is whether a repair verified under one input-edit operator can fail under a
different operator applied to the same declared spans. It concerns exact output-contract
compliance on harmless tasks, not harmfulness, natural jailbreak prevalence, causal model
internals, or a new optimal subset-search algorithm. Different operators are not asserted
to preserve meaning or model input representation.

## Fixed new input panel

Use 32 lookup problems and 32 sorting problems, shared across applicable model/mask views.
Lookup problems contain a new four-key dictionary and a query key. Four distinct values are
sampled from a fixed sixteen-word vocabulary; the queried key positions are balanced at
eight problems per position. The conflicting word `violet` is excluded from the valid answer
vocabulary. Some valid words occurred in V3; the claim is new dictionary/query problems,
not unseen vocabulary. The lookup dictionary is part of the problem identity.

Sorting problems use 32 distinct unordered triples from digits 1 through 9, excluding the
two V3 triples, with a fixed non-sorted presentation sampled for each. Sampling seeds and
algorithms are fixed in `src/jbspan/objective_transfer.py` before model outputs. Dictionary
mapping plus query identifies a lookup cluster; unordered numbers identify a sorting cluster.
Presentation bytes are hashed separately. Models, conflict styles and repair masks never
create independent task clusters. All 64 problem identities are disjoint from the V3 panel.

The five conflict note spans, aligned-control note spans, exact JSON scorer, editing
operators, target model artifacts, native chat framing, temperature 0, seed 11, maximum
128 output tokens and per-request limits retain their V3 definitions. Only task problems
change. This is single-run new-input replication under fixed templates and quantized models,
not stochastic-seed replication or new-template/new-model generalization.

## Disclosed discovery-derived strata

| Stratum | Target | Task / conflict style | Removal mask | Role |
|---|---|---|---:|---|
| qwen_lookup_18 | Qwen | lookup / format | 18 | Primary |
| qwen_sort_13 | Qwen | sorting / format | 13 | Primary |
| qwen_sort_24 | Qwen | sorting / format | 24 | Primary |
| gemma_lookup_2 | Gemma | lookup / value | 2 | Primary |
| gemma_sort_2 | Gemma | sorting / value | 2 | Preservation comparison |

The four primary masks were chosen because of the V3 failures. The comparison transferred
successfully in V3; it is not a proven population negative control. All five strata retain
all 32 applicable new problems, regardless of baseline/control failures or UNKNOWNs. No
screening selection, outcome-based replacement, template optimization or model substitution
is allowed within this protocol.

For each stratum/problem pair, measure BLANK at the witness mask S and every proper subset
of S; OMIT at S; and the CLEAN (all omitted), ALL_BLANK and ALIGNED controls. The unedited
condition is BLANK at mask 0 and is included among the proper-subset measurements. The two
Qwen sorting strata share several inputs; the exact request identity is reused, but every
logical stratum view remains present.

Total: 1,280 logical measurement views, 1,120 unique target requests, 160 stratum/problem
pairs, 128 model/problem pairs and **64 underlying problem clusters**. These denominators
must not be substituted for one another. Fresh V4 checkpoints never reuse V3 outputs as
validation evidence.

## Primary estimand and unresolved observations

For stratum j and problem i, the primary transfer-failure event is the conjunction:

1. CLEAN, ALL_BLANK and ALIGNED are all correct.
2. BLANK(S) is correct.
3. BLANK(T) is incorrect for every proper subset T of S, including mask 0.
4. OMIT(S) is incorrect.

This verifies a control-qualified strictly minimal blank repair and a failed response after
switching to omission. It is not merely a change in minimal-family membership.

Let K=1 when every required literal is observed true. Let P=1 when no required literal is
observed false. UNKNOWN is unresolved, but one known false literal makes the conjunction
false even if another literal is UNKNOWN. Report the fixed-panel rate bounds
`[sum(K)/32, sum(P)/32]` separately for each primary stratum.

The primary aggregate is the equal-weight mean of the four primary stratum rates: bounds
`[sum(K)/128, sum(P)/128]`. Each of the 64 problem clusters contributes the mean of its two
primary views. The Gemma sorting comparison is excluded from this aggregate. Shared-row
requirements in the two Qwen sorting strata do not conflict: shared proper subsets must be
incorrect, and shared controls correct. Code tests check this compatibility rather than
silently interpreting a sum of incompatible marginal upper bounds as jointly attainable.

These are identification bounds for the measured panel, **not confidence intervals**.
No eligible-only denominator is used. A missing measurement is never favorably imputed.

Secondary reports include individual control failure/UNKNOWN rates; source minimal-certificate
availability; paired BLANK(S)-versus-OMIT(S) correctness differences with unknown bounds;
raw response correctness versus source strict-minimal certification; and the separately
labelled preservation comparison. Target-operator proper subsets are not measured in V4,
so a correct OMIT(S) response does not certify its target-operator minimality. Conditions
forced true by the event definition are not independent discoveries. All null, reversed
and heterogeneous outcomes remain visible.

## Sampling sensitivity, not a population guarantee

If reported, use exactly 10,000 paired problem-cluster bootstrap draws with fixed seed
2026090511. Resample lookup problems within their four balanced query-key-position groups
(eight draws each), and resample the 32 sorting clusters together. Carry both primary
views and all lower/upper indicators for a problem through the same draw. Do not resample
model/mask/stratum rows independently.

Label these summaries APPROXIMATE_GENERATOR_SENSITIVITY, not exact confidence intervals or
evidence of external validity. The original design is balanced and without replacement;
ordinary bootstrap approximations do not reproduce it exactly. Do not output a purported
zero-width inferential interval when all observed primary events are known and constant.
Finite-panel identification bounds are still reported in that case. No p-value, acceptance
guarantee or automatically favorable paper-quality gate is attached to this validation.

## Execution limits and records

The request ceiling is 1,120, the validation walltime ceiling is 3,600 seconds, and each
request retains the V3 90-second transport limit and byte/output limits. All planned cases
are measured unless a declared operational stop occurs. There is no success-driven early
stop. Exact model alias mismatches stop after recording the receipt. Uncertain dispatches
cannot be automatically resent. Completed transport failures remain UNKNOWN and retained.

The new configuration will pin this protocol, generator, analyzer, tests, runner, inherited
runtime/parser code, model artifacts and the full runtime dependencies. A safe plan is
written before dispatch; replies are recorded privately and projected to content-free safe
results. Both owned servers are cleaned up; no unrelated process is reused or stopped.
No paid service, new model download, original private response corpus, Primary A or Reserve B
is used. The final config hash and start/completion states will be recorded in a separate
`RESCUE_V4_LIVE_EXECUTION_LOG_2026-09-05.md`, preserving this protocol snapshot unchanged.

## Interpretation after completion

Report whether each discovery-derived stratum reproduced, the fixed-panel proportions and
bounds, all comparison outcomes and the limits of the new-input scope. A reproducible result
would strengthen the evidence for specification-bound repair certification. It would still
require a clear useful contribution beyond established removal explanations and instruction
hierarchy benchmarks, and broader task/template validation, before claiming a strong paper.
Failure to reproduce must remain a failed prospective test of these fixed witnesses; no
new witness may be chosen from V4 and described as prospectively confirmed in V4.
