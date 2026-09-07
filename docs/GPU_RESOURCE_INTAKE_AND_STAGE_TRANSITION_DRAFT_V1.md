# GPU Resource Intake and Stage-Transition Draft v1

Date: 2026-09-03 (Asia/Seoul)

State: **READINESS DRAFT; NO NEW SCIENTIFIC OUTCOME AUTHORIZED**

This document makes a future GPU immediately usable without changing a
scientific contract after seeing results. It does not authorize held-out labels,
P3 responses, topology outcomes, or canonical GCG execution.

## 1. Finish the current device-bound job first

E0G-4 JailMeter progress was generated on the local RTX 3070 under a frozen
one-slot runtime identity. Its remaining rows must finish on that device. Rows
from a future GPU must not be appended to the same axis file. Atomic progress
records make interruption recoverable, but not cross-device mixing valid.

If E0G-4 fails, a new GPU does not convert that scientific failure into a pass.
It can support a genuinely new evaluator or revised claim only under a fresh
development/test contract.

## 2. Information to capture when access arrives

Before downloading models or running prompts, record:

- GPU model, count, UUID, total/free VRAM, driver, CUDA runtime, and compute
  capability;
- CPU model, logical cores, RAM, free disk, operating system, and filesystem;
- whether the machine is persistent or preemptible and the maximum wall time;
- SSH, notebook, or batch-job access method;
- outbound Hugging Face and GitHub access;
- Docker/Conda availability and whether administrative access exists;
- expected availability window and any cost or quota ceiling.

The first evidence file should contain only hardware/runtime metadata and a
harmless diagnostic. No attack output is needed for resource admission.

## 3. Resource lanes

These are routing rules, not promises that a model will fit.

| Available GPU resource | Admissible first lane | Not yet justified |
|---|---|---|
| 8--12 GiB | Existing Q4 two-model target lane; small evaluator models | Canonical BF16 GCG |
| 16--24 GiB | Faster Q4 target experiments and separately tested small-model workloads | Existing canonical GCG contract without a new memory preflight |
| 40--48 GiB | Candidate canonical-development lane after a harmless peak-memory probe | Assuming the frozen 64-GiB-free GCG requirement passes |
| 1 x 80 GiB | Candidate sequential canonical GCG lane after a compute-only amendment | Mixing its rows with an already started job from another device |
| 2 x 80 GiB | Exact resource class anticipated by the existing canonical GCG contract | Scientific execution before source/runtime attestation passes |

The present canonical contract requests two A100 80-GB GPUs mainly to run jobs
in parallel. A one-GPU sequential variant may be scientifically equivalent, but
that substitution must be written as a compute-only amendment before attack
outcomes and must preserve the algorithm, search width, steps, seeds, and model
identity.

## 4. New-host admission sequence

1. Clone or transfer the repository at an identified commit/tree state.
2. Reconstruct dependencies in a clean environment and record exact versions.
3. Fetch model artifacts by pinned repository revision and verify every expected
   SHA-256; do not copy an undifferentiated local cache.
4. Run import-origin and safe-artifact checks.
5. Run harmless load, chat-template, context, deterministic replay, peak VRAM,
   throughput, and thermal checks.
6. For an evaluator stage, execute a prospectively frozen cross-device
   equivalence set before held-out inference.
7. For a target-model stage, freeze the exact attack/model/payload-hash/decoding
   contract before the first scientific call.
8. Enable atomic checkpoints and copy only finalized safe metadata artifacts
   back to the canonical repository.

Model weights should normally be downloaded directly on the GPU host. The local
machine currently has limited spare disk, so duplicate multi-gigabyte weights
should not be downloaded here merely in anticipation of remote access.

## 5. Cross-device evaluator rule to freeze if E0G-4 passes

The held-out contract must include a device-equivalence subprotocol before any
held-out row is called. A defensible candidate is the already published 60-case
E0G-2 sentinel, preserving exact inputs, one-slot execution, model revisions,
prompts, parsers, and generation settings.

Prospective acceptance should require:

- 60/60 reconstructed input hashes and token counts identical;
- 60/60 Qwen safety/refusal labels identical;
- 60/60 JailMeter binary labels identical;
- 60/60 final panel decisions identical;
- 60/60 eligible strict parses and zero decision-relevant output-limit stops;
- raw generated-byte identity reported descriptively rather than silently
  assumed.

If this exact rule is judged too strict or too weak, it must be revised before
the new-device outputs are generated. A failed equivalence test means the new
hardware cannot inherit the local qualification; it does not authorize
threshold adjustment.

## 6. Stage decision after E0G-4

If E0G-4 passes:

1. finalize the separate primary held-out contract;
2. admit the chosen execution device through the harmless equivalence gate;
3. run both held-out evaluator axes while row labels remain sealed;
4. apply the held-out gate once;
5. only after that pass, write a no-new-human topology-contract amendment;
6. choose the Q4 semantic/compositional route or canonical GCG route according
   to actual GPU capacity, not anticipated capacity.

If E0G-4 fails, keep held-out, P3, and topology sealed. Use the future GPU only
for a prospectively defined stronger evaluator or a separately justified model
route; do not rerun the same panel until it happens to pass.

## 7. What is already reusable

- P1 exact topology engine and its synthetic tests;
- P2 pinned Qwen2.5-7B and Llama-3.1-8B Q4 identities and runtime checks;
- typed h4rm3l units, DeepInception assets, and canonical GCG source audits;
- payload hashes, provenance rules, safe-artifact schema, resume logic, and
  execution ledger;
- E0G evaluator prompts, parsers, model identities, and development split;
- the official ICLR style archive, which is unrelated to compute admission and
  should remain untouched until empirical gates support drafting.

What is not reusable as positive evidence includes failed evaluator routes,
persona labels as human evidence, historically exposed JailbreakBench records
as primary held-out data, and any post-outcome threshold or family selection.
