# E0G-1 Heterogeneous Runtime Qualification Result V1

Date: 2026-09-03 (Asia/Seoul)  
Evidence class: **HARMLESS OPERATIONAL QUALIFICATION; NOT SCIENTIFIC CALIBRATION**

Decision: **PASS BOTH AXES**

## Bottom line

The exact local Qwen3Guard-Gen-0.6B response-safety/refusal axis and the exact released
JailMeter-SLM purpose-completion axis both passed harmless parser, determinism, resource,
and runtime gates. This admits a small public-development sentinel. It does not qualify the
combined panel, score jailbreaks, or provide topology evidence.

## Qwen3Guard E0G-1A

- exact model: `Qwen/Qwen3Guard-Gen-0.6B` at revision
  `fada3b2d...`, 1,519,203,341 local bytes;
- device: RTX 3070, CUDA, float16, greedy decoding;
- four harmless cases, two repetitions each: 8/8 strict parses;
- expected safety and refusal labels: 8/8 each;
- byte-identical output within every repeated case: 100%;
- output-limit stops: zero;
- mean inference: 0.647 seconds; total qualification: 7.99 seconds;
- peak CUDA allocation: 1,297,318,400 bytes.

Result identity:
`1042f10ea89bebbb19249908ee836bece6062c634aae7bd045451b0e0781550d`.

## JailMeter E0G-1B

- exact source: `Magi2B0y/JailMeter` commit
  `6a492b5a547497d1aa852849025edf2cc7bfd632`;
- exact released LoRA converted to F16 GGUF; converted file SHA-256
  `335a66a0...`;
- existing Qwen2.5-7B-Instruct Q4_K_M base and llama.cpp b10441 reused;
- five harmless cases, two repetitions each: 10/10 strict parses;
- expected purpose-completion labels: 10/10;
- byte-identical output within every repeated case: 100%;
- output-limit stops: zero;
- 29/29 layers offloaded; controlled baseline 358 MiB and peak 5,000 MiB;
- mean inference: 4.607 seconds; total qualification: 50.39 seconds.

Result identity:
`41139327f083eeb2fdb6fef6940d26c3b4d068fc5908e3f20d278787768a895b`.

## Validity boundary

All prompts were harmless synthetic cases. No public human-labelled calibration record,
held-out record, P3 response, or topology outcome was opened by these qualifications. The
tests establish that the exact implementations run and parse deterministically under the
qualified conditions; they do not establish construct validity on jailbreak responses.

## Authoritative artifacts

- Qwen contract/result SHA-256:
  `42cf0d9422431d5769cbb95bed0be4c0858f96b51e25671f16a8f73dccf90c9e` /
  `c1e2bf92d68fd99fe8e99c27d27998f58dcdca36705dc91221e0f08e9a0b43b8`;
- JailMeter contract/result SHA-256:
  `29eaa72ee336f7ec24a256e26e2c01d5ba0d3226b20bc279ead7033c30c4f0ef` /
  `581e06f83a66bad4dc7adff8e5303bb1246a61265317d252e798bfbea868a0ce`;
- runners:
  `scripts/qualify_qwen3guard_runtime_e0g1a.py` and
  `scripts/qualify_jailmeter_runtime_e0g1b.py`.

Next authorized operation: freeze a small, label-balanced, public-development sentinel for
the unchanged two-axis abstaining rule.
