# Local Storage Cleanup Candidates — 2026-09-03

State: **AUDITED; DELETION NOT EXECUTED**

The workspace had approximately 37.29 GiB free before cleanup. A read-only
inventory identified four model-cache files from stopped predecessor evaluator
routes. They total 14,833,346,048 bytes (approximately 13.81 GiB).

| Exact file | Bytes | Why disposable |
|---|---:|---|
| `artifacts/p3_signal_screen_v1/wildguard_runtime/wildguard-q8_0.gguf` | 7,702,573,664 | E0F/WildGuard route is scientifically stopped; model provenance remains recorded |
| `artifacts/evaluator_panel_v2/runtime_qualification_e0c/models/ministral_3_3b_instruct_2512_q4_k_m/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` | 2,147,023,008 | superseded failed E0D evaluator axis |
| `artifacts/evaluator_panel_v2/runtime_qualification_e0c/models/phi_4_mini_instruct_q4_k_m/microsoft-Phi-4-mini-instruct-Q4_K_M.gguf` | 2,491,874,688 | superseded failed E0D evaluator axis |
| `artifacts/evaluator_panel_v2/runtime_qualification_e0c/models/phi_4_mini_instruct_q4_k_m/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf` | 2,491,874,688 | duplicate spelling of the superseded Phi artifact |

Before the attempted cleanup, the resolved absolute paths were verified to be
inside this workspace and no active process command line referenced any of the
four files. The active E0G-4 JailMeter process instead references:

- the P2 Qwen2.5-7B Q4 shards;
- the P2 llama.cpp b10441 Vulkan runtime;
- the E0G JailMeter LoRA under `artifacts/evaluator_panel_v3/`.

Those active/current assets were excluded from cleanup, as were the P2 Llama
Q4 model, Qwen3Guard weights, source repositories, private P3 records, configs,
and all safe evidence files.

The automated deletion command was blocked by the execution environment's
safety policy before any file was removed. All four candidates still exist.
They are recoverable by downloading the pinned model revisions and verifying
the recorded SHA-256 values, but deletion would remove the local cached copies.

Do not remove these candidates while rerunning any historical E0C/E0D/E0F job.
For the current E0G route and future topology route they are not required.

## 2026-09-07 — authorized cleanup completed

This entry supersedes the historical "DELETION NOT EXECUTED" state above.
Following the user's explicit authorization, exactly the four listed GGUF files
were permanently deleted at 03:05:43–03:05:44 UTC (12:05 KST). All four matched
their recorded SHA-256 immediately before deletion. Absolute paths and ancestor
directories were checked; no reparse points or running Python/llama runtimes
were found. No directories, experiment responses, evaluation results, source
repositories, or active model files were deleted.

Removed logical file sizes total 14,833,346,048 bytes (13.815 GiB). Actual C: free
space increased from 22,913,880,064 to 35,255,361,536 bytes: **11.494 GiB reclaimed,
32.834 GiB free**. The difference from logical sizes is not attributed to a
confirmed cause; the two identical Phi files were not proven to be hard links.
Use measured free-space growth, not summed logical sizes, as reclaimed capacity.

Post-deletion verification confirmed all four targets absent, all five protected
current model files present with unchanged sizes, both active topology contract
hashes unchanged, and all recovery provenance hashes unchanged. The protected
models were not rehashed in full. No model calls, experiment restart, raw-response
reads, OS/pagefile changes, or automatic cleanup installation occurred.

Recovery correction: **WildGuard is not a directly downloadable GGUF**. It needs
the pinned official source and Q8_0_DIRECT conversion, including the recorded
snapshot metadata and exact revision-named input directory. Ministral and Phi
can be restored from their pinned GGUF repositories, subject to access and
availability. Downloads/reconstruction were not retested. The files are not in
the Recycle Bin; prior configurations may require restoration before reuse.

Exact paths, hashes, source revisions, reconstruction conditions, protected
assets, authorization scope, and measurements are preserved in the
[execution record](LOCAL_STORAGE_CLEANUP_EXECUTION_2026-09-07.json).
