# Stage 1 dependency and resource audit

Recorded 2026-09-07. This is an independent audit of current explicit dependency pins and a machine snapshot, not execution authorization or scientific certification. No inference, model server, evaluator, registry change, deletion, or existing-file modification was performed. This new report is the sole file added by this audit.

## Dependency scope and method

Read only the two current configuration files below, recursively enumerated their explicit `path`/`size_bytes`/`sha256` descriptors, validated project containment, and compared each present file's size and SHA-256. Repeated paths were deduplicated before hashing; each distinct model path was hashed once. Each file's size and last-write timestamp were stable before and after its hash read. No referenced data contents were interpreted, and the prefix manifest was hashed without expanding its contents. Historical private C1N data, sealed cohorts, broad logs and the four previously removed obsolete model files were outside this audit.

Hash reads ran from `2026-09-07T03:23:39.5757876+00:00` to `2026-09-07T03:26:09.1358164+00:00`.

| Current configuration | Descriptor comparisons | Failures | Raw configuration SHA-256 |
| --- | ---: | ---: | --- |
| `configs/natural_language_localization/pa_llama_topology_execution_v1.json` | 122 | 0 | `d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0` |
| `configs/natural_language_localization/pa_llama_topology_target_continuation_v1.json` | 7 | 0 | `6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0` |

Result: **129/129 descriptor comparisons passed**, covering **98 distinct files** and **11,314,101,386 distinct bytes hashed**. There were no missing files, hash mismatches, size mismatches, or detected changes during individual reads. The scope includes all **37 required-code descriptors**, both pinned protocols, the preparation receipt, continuation prefix manifest, tokenizer/configuration/source dependencies, runtime binaries/archive, and all five active weight files below. Descriptor values are retained in the cited frozen configurations; they were not changed by this audit.

| Active weight | Bytes | Result |
| --- | ---: | --- |
| `artifacts/p2_runtime_qualification_v1/models/meta-llama-3.1-8b-instruct-q4-k-m/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | 4,920,739,232 | Size and SHA-256 match |
| `artifacts/evaluator_panel_v3/models/jailmeter-slm-6a492b5/jailmeter-slm-lora-f16.gguf` | 40,397,440 | Size and SHA-256 match |
| `artifacts/p2_runtime_qualification_v1/models/qwen2.5-7b-instruct-q4-k-m/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` | 3,993,201,344 | Size and SHA-256 match |
| `artifacts/p2_runtime_qualification_v1/models/qwen2.5-7b-instruct-q4-k-m/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf` | 689,872,288 | Size and SHA-256 match |
| `artifacts/evaluator_panel_v3/models/qwen3guard-gen-0.6b-fada3b2/model.safetensors` | 1,503,300,328 | Size and SHA-256 match |

## Machine snapshots

At `2026-09-07T03:22:38.0244292+00:00`, Windows CIM reported:

- C: capacity: **511,406,911,488 bytes**; free: **35,219,783,680 bytes (32.801 GiB)**.
- Physical memory: **33,255,656 KiB** total; **7,189,908 KiB** free.
- `C:\pagefile.sys`: **45,680 MiB** allocated; **8,890 MiB** current usage; **15,352 MiB** peak usage.
- `nvidia-smi`: NVIDIA GeForce RTX 3070, **8192 MiB** total, **378 MiB** used, **33 C**.

At `2026-09-07T03:24:20.8007348+00:00`, the Windows memory performance provider reported **6,971,002,880 bytes (6.492 GiB)** available RAM, **69,353,234,432 bytes** committed, and an **81,953,542,144-byte** commit limit. Commit headroom was **12,600,307,712 bytes (11.735 GiB)**, with **84.63%** of the limit committed. These are later measurements, so they need not equal the earlier CIM free-memory snapshot.

The target's configured TCP port **18087** had no listening connection. A process-name check for Python, llama, uvicorn, ollama and vllm executables found **zero** matching runtime processes. This is a scoped process check, not a claim that no other application consumes resources.

## Limits on interpretation

The observed disk space exceeds the frozen **20 GiB** prelaunch floor by **12.801 GiB**, and also exceeds the **15 GiB** per-dispatch floor. The sampled GPU usage and temperature are below the configured resource limits. These snapshots do not guarantee future admissibility, sustained RAM/commit/disk headroom, or successful model loading. The current disk/GPU guards do not themselves manage pagefile growth or reclaim storage.

Both current configurations still record the execution deadline as **`2026-09-05T22:55:47+00:00`**, which predates this audit; the continuation configuration records **`automatic_retry_allowed: false`**. Passing dependency comparisons and numeric snapshot thresholds does not override those restrictions, verify retained scientific receipts, establish uninterrupted-run equivalence, or authorize a second continuation. Reentry decisions remain separate from this dependency audit.
