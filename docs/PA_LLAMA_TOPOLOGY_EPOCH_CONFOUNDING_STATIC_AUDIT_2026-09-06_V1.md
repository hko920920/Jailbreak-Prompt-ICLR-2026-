# Static execution-epoch confounding audit -- 2026-09-06 KST

Recorded 2026-09-05 21:18 UTC, after the resource failure/technical amendment and
before topology judge outcomes. This is an outcome-blinded static sensitivity
proposal, not original preregistration, a changed C3 gate, or an executed analysis.
No original90 private response, actual topology response, judge label or model
was accessed for this audit. Original scientific selection remains DEVELOPMENT.

## Authority and scope

The independent reviewer read the pinned SAFE bound plan and independently
reconstructed all1470 ordinal keys from the pure schedule. Bound-plan file SHA:
`3a8bc4391f2ba6d02f2de446bd8b4ff61d1c1ac121fb3c57044bee379df1615b`;
plan identity `8b3b702ab5ea256699b9c3a92b148f05feb0523bd903724dd7ae91dfa9c789f9`.
Original contract `d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0`;
continuation `6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0`.
Root checked the reported combinatorial arithmetic and interpretation against the
frozen continuation protocol. No source, protocol or contract was modified.

ALL21 P, masks1..7, operators OMIT/BLANK and seeds11/23/47 are retained. Mask0
is excluded here because it is the shared prior-screen reference, not another
new target epoch. Epoch labels below are the fixed original/continuation mapping;
they do not attest that prospective suffix processes or responses completed.

## Exact static mapping

| Outer epoch | Target calls | Science | Controls |
| --- | ---: | ---: | ---: |
| 002, retained original | 872 | 536 | 336 |
| 003, continuation | 210 | 126 | 84 |
| 004, continuation | 210 | 126 | 84 |
| 005, continuation | 178 | 94 | 84 |
| Total planned | 1470 | 882 | 588 |

Masks1..4 have all science and controls in002. For mask5, OMIT/11 has all21 P
in002; BLANK/11 has11 in002 and10 in003. Both operators at23/47 and controls
are in003. For mask6, BLANK/11 has all21 in003; OMIT/11 has11 in003 and10
in004; later seeds/controls are in004. For mask7, OMIT/11 has all21 in004;
BLANK/11 has11 in004 and10 in005; later seeds/controls are in005.

There are choose(21,2) x choose(7,2) =210 x21 =4410 unordered P-pair/mask-pair
rectangles. Each six-slice rectangle uses24 science calls and16 distinct matched
control calls, because controls are reused across the three science seeds.

Exactly1260/4410 (28.571%) have all24 science calls in one epoch: every P-pair
and the six mask-pairs drawn from{1,2,3,4}, all in002. Requiring one common epoch
within each of all six slices gives the same1260, not additional rectangles.
Requiring all16 matched controls to share that epoch also gives1260.

| Slice | Science-only same-epoch rectangles | Including that slice's 8 controls |
| --- | ---: | ---: |
| OMIT /11 | 2145 | 1260 |
| BLANK /11 | 1525 | 1260 |
| OMIT /23 | 1260 | 1260 |
| BLANK /23 | 1260 | 1260 |
| OMIT /47 | 1260 | 1260 |
| BLANK /47 | 1260 | 1260 |

Science-only additions: each mask-pair(i,5), i in1..4, contributes210 OMIT/11
and55 BLANK/11 rectangles; pair(5,6) contributes45 BLANK/11, and pair(6,7)
contributes45 OMIT/11. No other additions. Thus the six-/two-/one-/zero-slice
eligibility histogram is1260/220/710/2220; any-slice2190 and total eligible
rectangle-slices8710/26460. Requiring matched controls removes every addition.
These are structural counts, NOT observed reversals. Directed orientations
double the candidate counts, but do not create independent comparisons.

## Proposed diagnostic after full unchanged evaluation

Keep the original full4410 primary candidate accounting and unchanged C3.
Separately describe the same-oriented, fully control-qualified six-slice
witnesses whose two masks both lie in{1,2,3,4}. Keep denominator1260 and ALL21 P,
including UNKNOWN/unassessable counts; never select only favorable P or treat
UNKNOWN as negative. No new pass flag, subset finalizer or shorter experiment
is authorized. This proposal has not been applied to actual scientific outcomes.

A positive witness in this diagnostic would show that this observed ordering
contradiction does not REQUIRE a target-process restart between its constituent
calls. It would NOT eliminate within-epoch time/cache/RNG drift: masks remain
contiguous time blocks, and P/operator rotation is deterministic rather than
randomized or balanced. It would not prove judge invariance, causal security
mechanisms, independence, significance, epoch invariance or fresh confirmation.
No witness with UNKNOWN cannot validate the shared-order null. The four-mask
subset cannot replace exhaustive seven-mask recovery/minimality or original C3.

This audit adds interpretive preparation only. It makes0 model calls, changes0
scientific criteria, and does not establish that the paper contribution exists.
