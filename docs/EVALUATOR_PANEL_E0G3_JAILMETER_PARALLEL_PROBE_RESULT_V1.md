# E0G-3 JailMeter Parallel Probe Result V1

Date: 2026-09-03 (Asia/Seoul)  
Evidence class: **OPERATIONAL EQUIVALENCE AND THROUGHPUT PROBE ONLY**

Decision: **DO NOT ADOPT TWO-SLOT EXECUTION**

## Design

Before the 889-record run, 12 completed E0G-2 JailMeter records were frozen: the four largest
observed input-plus-output cases and eight deterministic hash-ranked remainder cases. The
candidate runtime used two concurrent requests, two llama.cpp slots, continuous batching, and
8,192 total context tokens. Each slot had 4,096 tokens; the worst frozen request required at
most 3,038 including the full 1,536-token generation allowance.

Adoption required all 12 inputs, outputs, parser results, and labels to match the prior
sequential run exactly, remain inside time/GPU limits, and achieve at least 1.25x request-wall
speedup. This rule was frozen before parallel inference.

## Result

- input SHA/token identity: 12/12;
- strict label and label-match-count identity: 12/12;
- output SHA/length/token identity: 7/12;
- parse coverage: 12/12; output-limit stops: zero;
- sequential reference inference sum: 133.29 seconds;
- parallel request wall time: 86.69 seconds;
- observed speedup: 1.538x;
- controlled baseline / peak GPU memory: 361 / 5,210 MiB;
- total probe time: 91.25 seconds.

Continuous batching changed five generated reasoning traces even though their final labels were
unchanged. Because the prospective contract required byte-level equivalence, the faster route
failed and was not redefined post hoc around label-only equivalence. E0G-4 therefore retains
the exact one-slot sequential runtime and uses per-record checkpoints instead of concurrency.

## Identity

- contract SHA-256:
  `5138c7c225f8f0c0acfcb3d36c248ed19a5406a36f4a32ef8a62d61463ae0d1d`;
- selection identity:
  `f2a2bc5a9bb6fab9f72e6e407c3cccea656c889bb3b72e8d00b6d4f391a29fe9`;
- result SHA-256:
  `a2d558fba8faae263bf5395e47f8ba1733d946121df80a4359c9b7fdd03863ab`;
- result identity:
  `3922e91a79e4b4a1f35c016e33da9551f60fc7d965ed97a28dfe84d15d6ce666`.

No new scientific metric was computed and no held-out, P3, or topology outcome was opened.
