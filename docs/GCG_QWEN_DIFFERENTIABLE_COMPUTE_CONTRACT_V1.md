# GCG–Qwen Differentiable Compute Contract V1

## Decision

The static runtime bundle is valid, but the signal screen remains blocked until a private self-hosted GPU runner is live-attested. This contract targets two `NVIDIA A100 80GB PCIe` devices and preserves the already frozen Qwen2.5-7B, GCG, payload, optimizer-target, and evaluator identities.

## Frozen environment

- Linux x86-64 self-hosted runner with labels `gpu`, `a100-80gb`, and `private-research`.
- Two A100 80GB devices, at least 64 GiB free memory per device, BF16 enabled, MIG disabled.
- NVIDIA driver in the CUDA 12.x minor-compatibility range `[525.60.13, 580.0.0)`.
- Python 3.11, PyTorch 2.6.0 from the official CUDA 12.4 wheel index, Transformers 4.48.3, and a pinned supporting package set.
- Four 500-step GCG jobs, search width 512, top-k 256, initial candidate-evaluation microbatch 64, at most two concurrent jobs.
- OOM recovery may halve only the candidate-evaluation microbatch. It may not reduce the 512-candidate search width or alter the frozen algorithm.

## Privacy boundary

Model weights may enter only a private cache outside `GITHUB_WORKSPACE`. Raw payloads, targets, prompts, optimized controls, target responses, evaluator outputs, hostnames, and private filesystem paths may not enter Git commits or public artifacts. Safe records contain hashes, lengths, package/runtime versions, GPU counts, memory values, and coded statuses only.

## Gate sequence

1. Static compute-contract freeze on a hosted CPU runner.
2. Self-hosted runner registration and hardware/storage attestation. No model download.
3. Private environment materialization and a one-step synthetic, non-harmful gradient smoke test.
4. Four full GCG optimizations.
5. The already frozen 36-generation h4rm3l/GCG signal screen.

The current step establishes protocol readiness only. It does not produce jailbreak outcomes or paper evidence.
