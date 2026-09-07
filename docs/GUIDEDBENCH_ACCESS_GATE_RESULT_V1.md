# GuidedBench Access Gate Result V1

Date: 2026-09-01 (Asia/Seoul)

Status: **BLOCKED_EXTERNAL**

This gate checks whether the project can obtain the case-specific, pre-existing evaluation criteria required by the no-new-human-study measurement route. It does not generate any target-model response and does not expose or reproduce any harmful benchmark record.

## Exact access check

- Authenticated Hugging Face account: `Kohankyeong`
- Token authentication: valid
- Dataset repository: `HRXUST/GuidedBench`
- Dataset revision reported by the Hub: `10cc683c8df8c07139d3f900e381fb52738123c3`
- Gating mode reported by the Hub: `auto`
- Requested object: `core.jsonl` at the exact revision above
- Result: HTTP 403 `GatedRepoError`
- Server meaning: the authenticated account is not in the dataset's authorized list

Metadata was visible, but file bytes were not accessible. Visible repository objects were:

| Object | Reported bytes | Hub blob identifier |
|---|---:|---|
| `.gitattributes` | 2,504 | `bed0738c7eeb449bca98b5d2f33c89a1ee56349a` |
| `LICENSE` | 881 | `b99e525ac961913bdba6b5ab4e4375ecf5271224` |
| `README.md` | 3,171 | `b0892808b223f71a6f6e4fdcb4e973d8a233df99` |
| `additional.jsonl` | 19,390 | `8eae49f308cee4433f3f6edc44c208ef1315ae3a` |
| `core.jsonl` | 310,197 | `41d5feaca9b7b98c46362f5f737f52bebde41c26` |

## Official-source cross-check

- Official implementation: <https://github.com/SproutNan/GuidedBench>
- Public `main` HEAD observed at this gate: `56214b9a24a193bbef8f9d28a3c276c4bdfd2844`
- The official README states that the GitHub repository and Python wheel do not contain benchmark records; they download a pinned Hugging Face release.
- The README describes 200 English cases across 20 topics: a 180-case core set and a 20-case policy-dependent additional set.
- The software license is Apache-2.0, while the separately distributed dataset is described as CC BY 4.0. The exact dataset license file must still be downloaded and hashed after authorization.

There is therefore no official public-GitHub fallback for `core.jsonl`. Scraping, unofficial mirrors, or reconstruction from paper examples is not admissible because it would break provenance, licensing, and sampling integrity.

## Local side effects

- No GuidedBench package was installed.
- No dataset record was downloaded into the repository.
- No partial `HRXUST/GuidedBench` cache directory remained after the failed request.
- No target generation, evaluator run, scientific label, or topology result was opened.
- Existing frozen P1–P3 artifacts were not modified.

## User action required

While signed into Hugging Face as `Kohankyeong`, visit:

<https://huggingface.co/datasets/HRXUST/GuidedBench>

Complete the displayed `Agree and access repository` or `Request access` flow. Creating or refreshing another access token does not solve this specific error; authorization must be granted to the account at the dataset level.

## Re-entry acceptance criterion

After the account is authorized, rerun the exact revision request. This gate passes only when:

1. `core.jsonl` downloads successfully at revision `10cc683c8df8c07139d3f900e381fb52738123c3`;
2. the downloaded byte count is 310,197 unless the pinned Hub metadata itself is shown to have changed;
3. local SHA-256 values are recorded for `core.jsonl`, `LICENSE`, and `README.md`;
4. the JSONL schema, row count, unique identifiers, topic counts, and entity/action guideline fields are validated without printing harmful record contents;
5. only the core split required by the study is admitted; `additional.jsonl` is not downloaded unless a later pre-outcome amendment justifies it.

Only after this PASS may the evaluator-panel amendment be frozen and Stage E0 continue.
