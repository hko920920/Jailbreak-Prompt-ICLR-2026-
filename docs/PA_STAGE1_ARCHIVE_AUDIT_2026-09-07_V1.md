# Stage 1 archived continuation audit — 2026-09-07

Read-only independent SAFE audit of the first target continuation. No worker,
model call, private request/reply content read, artifact relocation, or historical
receipt edit occurred. This note is not raw-response certification or execution
authority; the main Stage 1 audit supplies pinned raw verification separately.

## Current evidence

Original contract: `d05f91c14625217e191837c0abbef0bc2e78eebaa7cecec18c97ce30b0cf19f0`.
First continuation: `6ac6b915bfebc3f2e7351a1533af78a9aafd2fdb041e12ffc37cecd67ff677f0`.
The SAFE and private continuation trees both retain this continuation in the
`_run1_archived` directory; both corresponding unarchived directories are empty.

All 210 archived target IDs are exactly original ordinals 873–1082: 126 science
and 84 controls. Each has one SAFE dispatch, row, template and cooldown file,
plus one private request and reply filename. Private contents were not read.
No extra or missing target filename, duplicate ID, or SAFE ordering gap was found.

Across 858 SAFE/config/preparation files, the independent audit found no
inconsistency in plan fields, SAFE native-census hashes, journal/row equality,
resource-receipt hashes, template pins, ownership, timestamps, epoch bindings,
or start/abort/reservation bindings. This checks internal SAFE consistency;
response-content and request-payload verification remain separate.

All 1,065 cooldown samples satisfy the existing resource and time rules.
Maximum sampled temperature was 69 C; every accepted final sample was at most
60 C. Minimum sampled disk space was 18,851,717,120 bytes, above the 15 GiB
per-dispatch floor. Maximum recorded wait was approximately 7.906 seconds.

Epoch 003 has its complete SAFE lifecycle and private log filename. PID 1344
started at `2026-09-05T21:19:37.977073+00:00` and stopped at
`2026-09-05T21:37:02.500757+00:00`. Its stop return code is 1; the existing
lifecycle verifier accepts any integer return code, so this is not independently
classified as a crash. First dispatch was `21:19:46.430071+00:00`; last target
receipt was `21:37:01.928756+00:00`, on the same UTC date.

Epoch 004 contains only amendment and rejected prelaunch-resource evidence.
Its latest event timestamp is `2026-09-05T21:37:02.613757+00:00`, recording
18,858,278,912 free bytes, below 20 GiB. No epoch-004 server lifecycle/private
directory or target dispatch exists. Epoch 005 is absent. The immutable abort
is `CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB`, with scientific gate unevaluated.

## Exact remainder and hashes

Missing ordinals are exactly 1083–1470: 388 requests, comprising 220 science
and 168 controls. The full original plan remains 1,470 targets.

| Object | SHA-256 |
| --- | --- |
| Ordered archived SAFE rows, canonical JSON | `fe4640066a4c6ac29ef0fec3afdf515fca00423b8dec62f9521ac6c7b1ff9280` |
| Ordered missing request-ID list, canonical JSON | `7d7ddd7ff5bf8ef532db2c09e0e2ca6a9988a90495cf0a757d4fa283e63ece5a` |
| Ordered missing plan-request list, canonical JSON | `ead9c678e451700ab9d82a2286cfcd0d98a6a977ba3fa0fbdf1a6d5d36222369` |
| Archived abort file bytes | `fae2d8030f4f4d09792de8be25fccee07bc85895539bfdd059f284e210398648` |
| Archived generate-started file bytes | `f1d1768104c703408fa42c82bc93a502527a679ee5c25053212141e75c2743fc` |
| Epoch-004 rejected resource file bytes | `cd226b21b7fda7f40cf4dc99d76404dd9d5f64d966f80401fdf00c6c5261a94a` |

Canonical JSON uses sorted keys, compact separators, UTF-8, no ASCII escaping,
and no trailing newline. File hashes include original file bytes.

## Reentry implications

The existing continuation constructor resolves `{continuation_sha}`, not
`{continuation_sha}_run1_archived`. Receipt authority fields still bind the
original contract and first amendment correctly, but no archive mapping or
relocation-provenance descriptor exists within the inspected continuation roots.
The original prefix manifest covers the original failure, not these 210 later
responses. Directory naming alone does not establish a historical relocation chain.

A future separately authorized continuation therefore requires explicit pinned
archive paths and complete file sets, verified reuse of all 1,082 retained first
responses, preservation of both failures, and an exact 388-request remainder.
It also requires a new execution window: the existing deadline was
`2026-09-05T22:55:47+00:00`. Do not infer retry authority from the empty active
directory. No archive mapping, new continuation, or replacement receipt was
implemented by this audit.
