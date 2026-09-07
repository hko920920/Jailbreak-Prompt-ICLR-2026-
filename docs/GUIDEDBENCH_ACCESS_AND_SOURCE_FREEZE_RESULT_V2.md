# GuidedBench Access and Source Freeze Result V2

Date: 2026-09-01 (Asia/Seoul)

Status: **PASS**

This result supersedes the external-block status in [GUIDEDBENCH_ACCESS_GATE_RESULT_V1.md](GUIDEDBENCH_ACCESS_GATE_RESULT_V1.md) after the user completed the dataset access form. V1 remains unchanged as the provenance record of the earlier 403. No scientific target output was observed between V1 and this PASS.

## Pinned sources

- Dataset repository: `HRXUST/GuidedBench`
- Dataset revision: `10cc683c8df8c07139d3f900e381fb52738123c3`
- Dataset version: `1.0`
- Dataset license: CC BY 4.0
- Official evaluator repository: <https://github.com/SproutNan/GuidedBench>
- Official implementation `main` revision observed for this gate: `56214b9a24a193bbef8f9d28a3c276c4bdfd2844`
- Software license: Apache-2.0

Only the files needed to freeze the primary source were downloaded:

| File | Bytes | SHA-256 |
|---|---:|---|
| `core.jsonl` | 310,197 | `c9ee3d8b5e8e23b884f2e3a6ae7c276f21a2e4e94d2fb98b48a424418fa73fc9` |
| `README.md` | 3,171 | `163e7d45fcb724ebe7f4082a2701c0493bdfb84c367f29df1062b5b691c0f99e` |
| `LICENSE` | 881 | `5d0acf072aa60ad9313ae6dcf189f14d1f00839cbd3fd262442dccee5f90f9c4` |

The raw files remain only in the standard Hugging Face cache. They were not copied into the Git worktree, and no raw question, target, guideline description, or example was printed into the gate log.

## Core integrity result

- 180 JSON objects; no blank or malformed row
- benchmark version `1.0`; subset `core` for all rows
- 180 unique ids, indices, questions, and targets
- indices exactly contiguous from 0 through 179
- required top-level fields complete and non-null
- 15 core topics
- topic sizes, sorted without exposing topic labels: 4, 4, 5, 6, 6, 6, 9, 10, 10, 14, 16, 18, 20, 25, 27
- 802 case-specific guideline points
- 439 action points and 363 entity points
- 2–6 guideline points per case; mean 4.4556
- every guideline has nonempty `id`, `type`, `description`, and `examples`
- guideline ids are unique within each case

The dataset card resolves the earlier 20-topic ambiguity. The entire release has 20 topics, but the primary `core` split has 15. The remaining five topics occur in the 20-case `additional` split and are explicitly vendor-policy-dependent.

## Admission and sampling consequence

`additional.jsonl` is not admitted and was not downloaded. The primary study therefore concerns the 180-case, 15-topic core population.

Before any new target outputs are generated, the outcome-blind sampling contract should use a deterministic hash order within each core topic:

- development: one payload per topic, 15 total;
- confirmation: the next three payloads per topic, 45 total;
- no overlap between development and confirmation;
- the remaining 120 core records stay unopened for target generation under this contract.

This equal-topic design prevents the observed topic-size imbalance from allowing the largest categories to dominate the screen. The paper must report both topic-macro and instance-micro summaries and must not generalize to the five excluded policy-dependent topics.

## Machine-readable freeze

The non-content source manifest is:

[guidedbench_source_v1.json](../configs/evaluator_panel/guidedbench_source_v1.json)

It contains the exact revisions, hashes, schema summary, aggregate integrity counts, admission boundary, and content-handling rule without embedding raw harmful records.

## Scientific meaning

This PASS establishes only that the planned criterion source is accessible, licensed, pinned, structurally complete, and suitable for outcome-blind partitioning. It does **not** establish that GuidedEval or any automatic panel is valid for this project. The next stage is a versioned evaluator-panel amendment and external qualification gate (E0).

No target generation, evaluator label, stable pair, recovery subset, or topology result was opened in this step.
