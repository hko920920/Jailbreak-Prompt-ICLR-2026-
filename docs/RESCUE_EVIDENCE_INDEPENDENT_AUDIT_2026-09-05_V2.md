# Independent rescue evidence audit — 2026-09-05 V2

Snapshot: 2026-09-05T07:24:43Z (16:24:43 Asia/Seoul). Scope: read-only inspection of documentation and safe result/verification summaries. The repository was being updated concurrently; this report is an additive snapshot, not a replacement of the historical record. Only this new file was written by this audit.

No target or evaluator inference, private response inspection, Primary A / Reserve B raw-content access, historical verifier rerun, historical artifact edit, or deletion was performed. Reported prior test counts are documentary evidence; this audit did not rerun those tests.

## Findings supported by stored results

| Stage | Observed result | What failed and why | Evidence limit |
|---|---|---|---|
| D3 exact development topology | 12 instances; 11 reportable; 10 nontrivial; 1,807 target generations; 324 controls; independent verification 19/19 PASS | Frozen positive-neutralizer Jaccard was 64/141 = 0.4539, below 0.80. Seven other gates passed. | Completed development evidence; no cross-family confirmation. |
| Post-outcome family diagnosis | h4rm3l Jaccard 25/30 = 0.8333; DeepInception 39/111 = 0.3514 | DeepInception also produced 22 failed control records and 17 confounded subsets. h4rm3l's mandatory coarsening reduced all nine instances to the same singleton macro-group. | Legitimate explanation of the failure; not a substitute D3 PASS or evidence of granularity-invariant interactions. |
| C1N two-target screen | All 180 seed-11 target calls completed; Qwen 35 advancing pairs, Gemma 5; 40 pairs / 36 payloads / 15 topics pooled | Minimum six pairs per target became mathematically unreachable because later seeds could only remove candidates. | Valid negative population gate. Zero stored `STABLE_PAIR` statuses reflect unexecuted seeds 23/47; they are not a zero-prevalence estimate. |
| C1N measurement diagnosis | Gemma attacked: Qwen3Guard 41 harmful / 4 safe; JailMeter 5 harmful / 35 safe / 5 abstain; joint panel 5 harmful / 4 safe / 36 abstain | The frozen consensus panel certified few Gemma positives because of large evaluator disagreement. | Identifies certification coverage failure under this instrument. Does not establish which evaluator is correct or whether the attack itself failed. |
| Rescue resolution projection | 12 instances / nine unique payloads; 2,676 partitions and 228 contiguous partitions; 25/36 adjacent comparisons changed family, 6/36 reportability, 8/36 nontrivial classification | Feasibility signal exists, but fine/coarse differences can follow directly from changing admissible interventions. | Post-outcome exploratory evidence. Partitions are repeated views, not independent observations. |
| Rescue frame | Safe audit reports 120 unused identities; A 60 / B 60; zero overlap and prior-output collisions; A 13 topics / B 12 | No scientific failure at this stage. | Cohort seal and provenance evidence only; raw cohorts were not opened by this audit. |
| GuidedEval development preflight | 180 unique response hashes; four cells of 45; stored PASS identity `935670c6…` | Initial `prompt` metadata-key rejection was an artifact-field validation error; the stored final receipt uses `prompt_builder` and passes. | Completed content binding, zero new target/judge calls. No GuidedEval quality or rescue effect has yet been measured. |

Primary references:

- [D3 final result and decision](D3_EXACT_TOPOLOGY_FINAL_RESULT_AND_NARROW_DECISION_V1.md), [safe D3 result](../data/natural_language_localization/d3_exact_topology_v1/result.safe.json), [D3 independent verification](../data/natural_language_localization/d3_exact_topology_v1/independent_verification.safe.json).
- [C1N negative result](C1N_H4RM3L_FRESH_SCREEN_VALID_NEGATIVE_RESULT_V1.md), [safe C1N result](../data/natural_language_localization/c1n_h4rm3l_fresh_screen_v1/result.safe.json), [C1N independent verification](../data/natural_language_localization/c1n_h4rm3l_fresh_screen_v1/independent_verification.safe.json).
- [Resolution projection summary](../data/natural_language_localization/d3_exact_topology_v1/postoutcome_resolution_rescue_audit.safe.json), [unused-frame summary](../data/natural_language_localization/guidedbench_rescue_frame_r0_v1/audit.safe.json), [GuidedEval preflight](../data/natural_language_localization/rescue_guidedeval_development_v1/preflight.safe.json).

## Distinguish operational events from scientific failures

The C1N same-process transition stopped when the released Qwen judge left 1,344 MiB CUDA allocation, above its 1,000 MiB launch ceiling. A fresh JailMeter process started at 414 MiB and completed the already frozen plan. This is a completed operational recovery, not the reason the scientific gate failed.

The C1N record documents an obsolete historical test temporarily rewriting a Step 5N verifier receipt. It also documents exact byte/hash restoration and correction of the temporal test. This audit did not rerun that historical verifier or repeat the move/restore operation. The present C1N result and verification hashes match their documentation.

The GuidedEval `prompt` / `prompt_builder` event is separate from both of those events and from D3/C1N failure. A completed static preflight cannot demonstrate that the redesigned evaluator will work on model outputs.

## Handoff and provenance findings

1. Rescue links in README, `CURRENT_PROJECT_INDEX.md`, and the execution ledger appeared during this audit as the other recording session appended them. At the checked snapshot, all local Markdown link targets in those four files and the rescue record resolved. Earlier missing rescue links were a concurrent-write state, not a final defect.
2. The index and README retain earlier next-operation prose followed by a rescue addendum. Read the dated addendum and rescue record together with the immutable negative results. Historical statements that a future action needed a new instruction describe that earlier session's boundary; new user instructions must be evaluated separately.
3. The C1N safe final result intentionally retains `C1N_H4RM3L_FAIL_PROVISIONAL_PENDING_INDEPENDENT_RECONSTRUCTION`. The separate independent verification receipt is PASS and binds that exact immutable result. A status consumer must join the result and verification receipts; it must not infer that verification remains unperformed from the result's status string alone.
4. D3 result-document section 9 calls `3038276ed076c39da108d3fde4a29da48d16e39731f8210e8632c45529507f0b` an independent-verifier identity. The actual safe receipts identify it as the **result** identity; the **verification** identity is `f302f0f16ff1a171bd54fb3d8770be37fe66f220ab7886ec670960561939bb32`. This is a provenance-label error, not a discrepancy in the scientific result. Historical files were preserved; this note supplies the clarification.
5. The rescue record section 8.2 says payload identities are never written to tracked safe artifacts, while the safe manifests and input plan deliberately contain IDs and hashes. The operative privacy boundary should be described as no **raw payload/prompt/response text** in safe artifacts. IDs/hashes are the stated reproducibility mechanism. No content exposure was found in the inspected safe summaries.
6. The rescue record calls some assets "tracked," but `git status --short` reports the new rescue source, configs, documents, and data directories as untracked. They exist locally but are not yet protected by a committed repository snapshot. This audit did not stage or commit user work.

## Legitimate paper route

The defensible route is a new, prospectively evaluated measurement-method paper about complete recovery families and their sensitivity to an explicitly declared observation/intervention contract. Its contribution must exceed the elementary fact that merging available interventions changes a minimum's representation.

The existing assets support an exact oracle and a useful pilot: h4rm3l has 12 certified minima, while the best single-path baseline finds eight, a 4/12 family-recall deficit. The same data also contain the strongest counterexample to a broad interaction claim: coarse h4rm3l minima collapse. Both observations belong in the main motivation and limitations.

Before A outcomes are available, specify which qualitative conclusions have practical meaning, compare them in a common atomic-unit space, fix all admissible coarsenings independently of outcomes, and freeze each target/evaluator/neutralizer/capability and missing-data rule. Report whether differences arise from unavailable interventions, evaluator abstention, capability confounding, or changes among certifiable alternatives. Report all judges separately as well as any consensus certificate; agreement is not ground truth.

The next informative empirical action is development-only GuidedEval qualification on the already generated 180 C1N responses, under an exact runtime and analysis contract. It can assess whether the new instrument has enough valid coverage and whether judge disagreement remains. It cannot repair C1N or count as confirmation. A primary unanimous-zero endpoint may have especially low coverage, so its viability must be measured before using any A outcome to select the instrument.

Prospective A and sealed B must then support the promised generality, including both attack families and distinct target families if those remain in the claim. Treat unique payloads as clusters, with target/attack/seed/partition observations repeated within them. Freeze replication contrasts after A and before B, and disclose which A conclusions were selected. Predefine a publication-worthy negative outcome as an informative, reproducible instrument/representation audit only if its rigor and scope are sufficient; do not require a positive instability result by construction.

At this snapshot, a paper-ready empirical conclusion and acceptance guarantee are both unavailable. The old route is closed, while the new route has reusable infrastructure, fresh evidence capacity, and a testable question. Its unresolved obstacles are measurement validity, nontrivial contribution, fresh cross-target replication, and resource/runtime specification.

This audit did not independently refresh the literature claims in the rescue record; priority and closest-work conclusions still require external source verification.

## Snapshot identities

These hashes record sources at the timestamp above; later concurrent documentation edits may legitimately differ.

| Source | SHA-256 |
|---|---|
| Rescue pivot record | `3a1a441a8ecfccabff4a3153ac844f2f79352e88092927caf0f3335205545ff1` |
| D3 result document | `34d9d9c70cfcbdc4743ab35d10f299b0dec41dec6fe433fc8af4c74d3be266b1` |
| C1N result document | `e5bc57ed9a575e0207503c638664d152f8cd11a27d975d42d868b3a6f5d40fa7` |
| Current project index | `33857023474896fa3333912ca69eeea86d5e1198663b8f4cc31c2a48cba3c36a` |
| Execution ledger | `bbfbab87315dd6a0a95b8bf62ec551ebe53ba138d5cd9b03fa4d0eb0929e649d` |
| README | `760637242c8ffb9cd9d5c6982609648b86356bfe43ec2c8c22b79aa3d80b80e6` |
| D3 result safe JSON | `12e9289370c3db20423736103c5ca4f12666e4faf77c8a5b3eeeffdb0ce7e59b` |
| D3 verifier safe JSON | `12f65afb42862fc6d21766872f25086beeb8bcb1094244712099fe837bc8a171` |
| Resolution projection safe JSON | `63eda0a5f50a79811a57939d85929ccd3bf0a190f886c7920e6055e1803ce50d` |
| C1N result safe JSON | `acd2467e4c805fe6c3fe0b5f2ba7d416fe08a00760032166051430253c02b948` |
| C1N verifier safe JSON | `72d9c56841b8aaff07d069bba6c8e73a3335d0a0cd3b4d3c95573903e6fa4556` |
| GuidedEval preflight safe JSON | `dd5c6133f3fa501cfa029c531d2d90c09dee65d0f78b449c7fe0067f230197a3` |
| Unused-frame audit safe JSON | `8e12f7f52e9731b0f73f28487e28da4d45220638fbb8a77af41965acf6c7fa02` |
