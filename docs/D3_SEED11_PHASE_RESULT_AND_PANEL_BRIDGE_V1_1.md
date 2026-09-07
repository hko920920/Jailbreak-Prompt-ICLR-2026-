# D3 Seed-11 Phase Result and Panel Bridge V1.1

## Status

**SEED 11 COMPLETE; 888 DECISIONS INDEPENDENTLY RECONSTRUCTED; SEED 23 AUTHORIZED**

This is the first opened exact-topology phase outcome. It is an adaptive-routing checkpoint, not a
final topology result, not confirmation evidence, and not human ground truth.

## Immutable inputs

- D3 contract SHA-256:
  `d2824dee65ca65683154795ce52e4bd462a13bb052d19937514dd40a8bbf1ed7`.
- Target generations: 888/888, all operational and panel-eligible, zero target truncations.
- Qwen3Guard: 888/888 strict parses, zero output-limit stops.
- JailMeter: 886/888 strict parses. Execution orders 258 and 264 reached the frozen 1,536-token
  evaluator-output boundary and remain ineligible ABSTAIN observations. There was no retry or
  output-limit change.

## Pre-panel namespace bridge

The first `finalize-phase --seed 11` attempt stopped before computing or writing any panel decision
because the frozen D3 runner addressed `panel_decision` through `run_fresh_screen_2r`, whose import
list did not re-export that function. This is the same namespace-wiring defect encountered and
independently verified during D2.

Before any D3 panel output, V1.1 froze the completed plan, target, Qwen, and JailMeter files by hash.
It then bound the exact existing `jbspan.fresh_screen_funnel.panel_decision` function into the
missing namespace in memory. It changed no record, model output, label algorithm, threshold,
denominator, adaptive rule, control rule, or D3 gate. The original runner and contract remain
byte-identical. Thirteen focused contract/bridge/panel tests and Ruff passed before finalization.

Artifacts:

- amendment:
  `configs/natural_language_localization/d3_panel_bridge_v1_1_amendment.json`;
- operational finalizer: `scripts/finalize_d3_phase_operational_v1_1.py`;
- pre-output bridge audit:
  `data/natural_language_localization/d3_exact_topology_v1/phase_11_panel_bridge_v1_1.safe.json`.

## Seed-11 panel result

| Panel label | Count | Fraction |
|---|---:|---:|
| HARMFUL | 367 | 41.33% |
| SAFE | 362 | 40.77% |
| ABSTAIN | 159 | 17.91% |
| Total | 888 | 100% |

There are 886 measurement-eligible records. Of the 159 ABSTAINs, 157 are eligible axis
disagreements/abstentions and two are the frozen JailMeter output-limit observations.

The 367 HARMFUL decisions are valid nontruncated witnesses for 367 exact
instance-subset-neutralizer groups. Under the precommitted logic, each witness falsifies
all-three-seeds SAFE for only that exact group. Seeds 23 and 47 may therefore be skipped for those
groups; no skipped observation is synthesized, and the other neutralizer is unaffected.

### Evaluator cross-tabulation

| Qwen3Guard axis | JailMeter HARMFUL | JailMeter SAFE | JailMeter ABSTAIN | Row total |
|---|---:|---:|---:|---:|
| HARMFUL | 367 | 103 | 2 | 472 |
| SAFE | 16 | 362 | 0 | 378 |
| ABSTAIN | 17 | 21 | 0 | 38 |
| Column total | 400 | 486 | 2 | 888 |

The panel retains only the 367 HARMFUL/HARMFUL and 362 SAFE/SAFE cells as directional evidence.
Among the 886 measurement-eligible records, these 729 agreements are 82.28%; the other 157 are
conservatively retained as ABSTAIN. The asymmetric 103-versus-16 directional disagreement shows
that Qwen3Guard is materially more likely than JailMeter to mark these responses harmful. This is
a measurement limitation to carry into the paper, not an execution defect and not a reason to
change the frozen intersection rule after observing the results.

### Descriptive subgroup checks

| Group | HARMFUL | SAFE | ABSTAIN | Total |
|---|---:|---:|---:|---:|
| DeepInception | 315 | 303 | 144 | 762 |
| h4rm3l | 52 | 59 | 15 | 126 |
| `LAYOUT_PRESERVING_BLANK` | 193 | 181 | 70 | 444 |
| `SOURCE_AWARE_OMIT` | 174 | 181 | 89 | 444 |

Both attack families have a seed-11 HARMFUL fraction near 41%, so the phase is not degenerate and
the observed heterogeneity is not confined to one family. Equal aggregate SAFE counts for the two
neutralizers do not imply that they recover the same exact groups; only the completed three-seed
topologies and their predeclared positive-set Jaccard can answer that question.

As a non-gating sanity check, the aggregate intervention-size trend points in the expected
direction. DeepInception one-unit interventions were HARMFUL/SAFE/ABSTAIN = 31/6/5, whereas its
six-unit interventions were 6/33/3 and its full seven-unit interventions were 0/5/1. h4rm3l moved
from 38/4/12 for one-unit interventions to 0/18/0 for full three-unit interventions. This does not
license a monotonicity assumption for any individual lattice; exact subset enumeration remains
necessary.

## Independent reconstruction

A separate safe-side implementation recomputed eligibility, Qwen and JailMeter axis labels, the
conservative panel intersection, and adaptive witness eligibility for all 888 rows. It found:

- 888 unique decision IDs and exact frozen-plan order;
- zero record, order, response-hash, eligibility, axis-label, or panel-label mismatches;
- the same 367 valid HARMFUL witnesses; and
- the same 521-record seed-23 denominator.

Decision file SHA-256:
`c63e86ee0319afa935d57ae4b96df75ff0c3f4b448c0c4988188a881bc87a9a4`.

## Seed-23 route and time projection

Seed 23 contains exactly 521 records: 447 DeepInception and 74 h4rm3l. This is a 41.33% reduction
from the seed-11 denominator, arising only from valid HARMFUL short-circuit witnesses.

Using the matched seed-11 groups as a runtime projection gives approximately:

- target generation: 1.504 hours;
- Qwen3Guard: 7.6 minutes; and
- JailMeter: 1.454 hours.

These are operational estimates, not scientific outcomes. Seed-23 target generation remains
checkpointed and exact; subsequent pruning is allowed only after seed-23 phase finalization.

## Scientific interpretation boundary

Seed 11 shows that the intervention lattice produces heterogeneous panel outcomes and that the
adaptive rule can materially reduce later inference. It does **not** yet establish a recovered
subset, a minimal set, neutralizer recurrence, the 0.80 positive-Jaccard gate, or capability
preservation. Those claims require seeds 23 and 47, selected controls, final exact-topology
aggregation, and independent final verification.

Next authorized operation: **generate and evaluate the exact 521-record seed-23 phase**.
