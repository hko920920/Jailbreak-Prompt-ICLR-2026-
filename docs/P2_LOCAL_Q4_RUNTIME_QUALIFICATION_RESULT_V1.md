# P2 Local Q4 Runtime Qualification Result v1

Date: 2026-08-31 (Asia/Seoul)

Decision: **P2_LOCAL_Q4_RUNTIME_QUALIFICATION_PASS**

Evidence class: **DEVELOPMENT**

Paper validity: **false**

This gate qualifies a local two-model Q4 inference lane. It does not test a
jailbreak, a safety hypothesis, a recovery set, or a paper claim.

## 1. Authorized scope

P2 was frozen before any P2 model generation in
[`local_q4_runtime_qualification_p2_v1.json`](../configs/natural_language_localization/local_q4_runtime_qualification_p2_v1.json).
Only ten harmless capability prompts and one independent-process determinism
replay per model were permitted. Harmful prompts, attack templates,
attack-success judgments, topology outcomes, causal oracles, and keep-only
oracles remained closed.

The predecessor was the P1 result identity
`360427235f8954723cb6de4d001f12d4fb541285301096d5b15dd220b5c6d2f4`.

## 2. Exact runtime and model identities

Runtime:

- `ggml-org/llama.cpp` release `b10441`;
- commit `0177dcc7300bad8914bb838baabce87899812491`;
- official Windows Vulkan asset
  `llama-b10441-bin-win-vulkan-x64.zip`;
- archive SHA-256
  `7fdbac5860ad1c64bf1e5703e4491612562e953a709a9f190affd6141147c6aa`;
- extracted `llama-cli.exe` SHA-256
  `4baa37f8ac762388eabba68f9a2dfcd555250e4462c798119f6f5de20bd46f1c`.

Vulkan was selected before model output because the installed NVIDIA driver
advertises CUDA 12.2 while the pinned release's official Windows CUDA asset
starts at CUDA 12.4. The runtime enumerated the RTX 3070 separately as
`Vulkan1`; every invocation selected that exact device.

Models:

| Model | Runtime repository and revision | Frozen Q4_K_M files | License boundary |
|---|---|---|---|
| Qwen2.5-7B-Instruct | `Qwen/Qwen2.5-7B-Instruct-GGUF@bb5d59e06d9551d752d08b292a50eb208b07ab1f` | 2 shards, 4,683,073,632 bytes total; LFS SHA-256 values `dfce12e3…80db` and `539cf93f…d72a` | Apache-2.0; official Qwen GGUF repository |
| Meta-Llama-3.1-8B-Instruct | `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF@bf5b95e96dac0462e2a09145ec66cae9a3f12067` | 1 file, 4,920,739,232 bytes; LFS SHA-256 `7b064f58…557c` | Llama 3.1; pinned community quantization, not represented as an official Meta artifact |

Remote immutable revisions, file sizes, and LFS digests were checked before
download. All three downloaded files then passed full local SHA-256 checks.
The approximately 9.60 GB of weights and raw harmless outputs live under the
gitignored `artifacts/p2_runtime_qualification_v1/` directory.

## 3. Machine and frozen gate

Observed machine baseline:

- NVIDIA GeForce RTX 3070, 8,192 MiB;
- driver `536.67`;
- 31.715 GiB system RAM;
- 96.547 GiB free disk after artifact preparation;
- 8 physical / 16 logical CPU cores.

For each model the gate required:

- exact artifact and runtime identities;
- 11/11 successful processes: ten distinct harmless prompts plus one replay;
- at least 9/10 capability checks;
- byte-identical normalized replay at seed 17 and temperature 0;
- active embedded Jinja chat template and actual GPU offload;
- median decode throughput at least 8 tokens/s;
- peak VRAM at most 8,064 MiB and GPU temperature at most 85 °C;
- atomic per-invocation records and a cache-only resume replay.

## 4. Result

| Metric | Qwen2.5-7B Q4_K_M | Llama-3.1-8B Q4_K_M |
|---|---:|---:|
| successful processes | 11/11 | 11/11 |
| harmless capability checks | 10/10 | 10/10 |
| deterministic replay | pass | pass |
| decode tokens/s, min / median / max | 48.78 / 62.87 / 66.64 | 48.17 / 55.99 / 66.58 |
| cold one-shot process, median | 4.297 s | 4.750 s |
| peak VRAM used | 4,687 MiB | 5,041 MiB |
| maximum measured GPU-memory increase | 4,420 MiB | 4,774 MiB |
| maximum GPU temperature | 43 °C | 47 °C |
| embedded chat template | pass | pass |
| GPU offload | pass | pass |
| atomic resume replay | pass | pass |

The determinism response hash was identical across the two independent
processes for both models:
`fca142e5f3b67b5ba2d094bdf4fe089d8df85b17cd4b9b38db7ce3c0a7b9aaa3`.

As a conservative planning calculation, adding 512 divided by median decode
throughput to the observed median cold one-shot wall time gives 12.441 seconds
for Qwen and 13.894 seconds for Llama. This is not a measured 512-token run and
must not be used as a final confirmation budget. P3 must measure realistic
response lengths and persistent-server overhead before a P5-scale estimate is
accepted.

## 5. Preserved instrumentation failure

The first execution produced safe result identity
`ea248ce1ba3e812ab035ffe129f1a630aea292911e7d22cc0fc7c9c495001637`
and was classified as an instrumentation failure, not a model failure.

Evidence supporting that classification was available without changing any
scientific threshold:

- both models completed 11/11 processes with return code 0;
- GPU memory increased by 4.4–4.8 GB;
- the stdout wrapper visibly contained correct harmless answers and the
  runtime's `[ Prompt: … | Generation: … ]` summary;
- the adapter had incorrectly treated the entire simple-IO banner, echoed user
  turn, answer, timing line, and exit message as the assistant response;
- consequently capability, determinism, chat-template, and throughput parsers
  returned false or null together.

The remediation changed only the measurement adapter: it extracts assistant
text between the exact simple-IO user marker and timing boundary, parses the
official summary, enables verbose provenance logging, and verifies offload with
the independently sampled VRAM increase. The frozen contract hash, prompts,
expected answers, model files, seed, decoding parameters, and gate thresholds
were unchanged. The failed runner SHA-256 was `ec8594bf…963`; the passing runner
SHA-256 is `b5e8d3d8…fa3`. Both sets of 22 private records remain in the
gitignored record store.

## 6. Machine-readable artifact and decision boundary

Canonical safe result:

- [`p2_result.safe.json`](../data/natural_language_localization/local_q4_runtime_qualification_p2_v1/p2_result.safe.json)
- contract SHA-256:
  `bc9e05aa6e1447917ca07c0fc8198dcdfb32e891d3879be28c9f1968a87cbe34`
- passing runner SHA-256:
  `b5e8d3d8a5d4ebbd29edb090f598bf0236ee318d174aa4c763181cb404c8ffa3`
- result identity:
  `63254f2d0ba160b5f07a5bcb0d1d314b1011774da2efe8851a5deaeddb97178f`

P2 authorizes only:

> **Freeze P3 local development signal-screen inputs, exact prompts, private
> output boundary, evaluators, seeds, budgets, and GO/NARROW/STOP rules in a
> separate pre-outcome contract.**

P2 does not establish that either attack family succeeds, that a stable pair
exists, that a nontrivial minimal recovery topology exists, or that an ICLR
paper is empirically viable. Those hypotheses remain open.
