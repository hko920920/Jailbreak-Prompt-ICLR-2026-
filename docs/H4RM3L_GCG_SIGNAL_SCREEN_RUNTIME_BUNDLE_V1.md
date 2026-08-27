# h4rm3l/GCG Signal-Screen Runtime Bundle V1

This gate freezes the identities required to execute the 36-generation development signal screen without opening target outcomes.

It verifies:

- the existing 4-payload, 2-family, 3-seed input manifest;
- the Qwen tokenizer/template compatibility preflight;
- the seven frozen h4rm3l programs and their balanced assignment contract;
- the pinned HarmBench behavior source and official per-behavior GCG optimizer targets;
- the pinned llm-attacks and HarmBench GCG implementations;
- the exact differentiable Qwen model revision and weight-file metadata;
- the exact Q4_K_M GGUF target-generation runtime;
- the WildGuard conservative-screen identity and the nonvoting HarmBench diagnostic identity;
- the private-work and safe-output boundary.

## Expected gate outcome

The bundle freeze is expected to pass while execution remains blocked. GCG requires autograd over unquantized or bfloat16 Qwen weights. The existing GGUF runtime is valid for target generation but cannot serve as the GCG optimizer runtime. No GPU runner, device-memory floor, wall-clock budget, or private model-cache contract is currently frozen.

The next authorized operation is therefore:

`FREEZE_GCG_QWEN_DIFFERENTIABLE_RUNTIME_AND_COMPUTE_CONTRACT`

The workflow must not substitute the initial GCG control for an optimized control, reduce the 500-step budget silently, or generate target outputs before that contract passes.

## Safe-output boundary

Raw payloads, optimizer targets, h4rm3l prompts, GCG controls, target responses, and evaluator outputs remain private. Repository records contain only hashes, lengths, source identities, parse statuses, and aggregate protocol state.
