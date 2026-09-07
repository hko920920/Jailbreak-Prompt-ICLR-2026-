# Evaluator Panel Calibration Redesign E0F-0 Result

Date: 2026-09-02 (Asia/Seoul)

Decision: **ZERO-INFERENCE AUDIT PASS / EXISTING-SIGNAL B0 FAIL / AUTHORIZE AT MOST THE 144-CALL WILDGUARD SENTINEL**

Evidence class: **CALIBRATION-ONLY POST-FAILURE DEVELOPMENT; NOT PANEL QUALIFICATION AND NOT PAPER-VALID EVIDENCE**

## Meaning of the result

The E0F-0 audit completed normally and protected every sealed outcome. It reconstructed the 889-record external calibration table from the already completed Mistral/Phi measurements, evaluated the frozen source-blind B0 candidate family, froze behavior-group folds and staged WildGuard identities, and committed the revised held-out boundary without running a model.

No tested recombination of the existing Mistral/Phi Guided and actionability signals met the harmful-class final gate or the stricter calibration opening margin. B0 therefore cannot be frozen as the evaluator panel. This is positive evidence for running the small WildGuard scientific sentinel, not evidence for running all 889 WildGuard calls.

The result does not reject the jailbreak-neutralizer topology topic. It says that the current local G/A signals alone are not an adequate primary measurement instrument under the frozen gates.

## Protected execution boundary

- new model inference: **none**;
- held-out candidate output or candidate metric generated: **false**;
- primary held-out labels compared with a candidate: **false**;
- P3 responses opened or rescored: **false**;
- topology outcomes opened: **false**;
- raw prompts or responses written by E0F-0: **false**;
- panel qualified: **false**;
- paper-valid result: **false**.

The 947-record original held-out labeled-byte commitment was reconstructed exactly in memory. Per-record held-out labels were not written to the new safe manifests.

## Input and implementation integrity

| Item | Result |
|---|---:|
| Calibration records | 889 |
| Behavior groups | 265 |
| Human-harmful / human-safe | 290 / 599 |
| Existing Mistral/Phi axis rows | 3,556 |
| Missing or invalid axis cells | 0 |
| Source-blind score formulas | 17 |
| Enumerated formula/threshold candidates | 254 |

Source composition was 303 HarmBench records (141 harmful), 152 JailbreakBench records (54 harmful), and 434 StrongREJECT records (95 harmful).

Frozen implementation identities:

- contract: `configs/evaluator_panel/calibration_redesign_e0f_v1.json`, SHA-256 `32cdf72c6d6c98f0a1039dbc2a659711c005a932bb41335fa441b98c23bc10ce`;
- audit library: `src/jbspan/evaluator_panel_redesign.py`, SHA-256 `2a505c1622a1f0bf7ef3ec71601c0d7278f118741fa791bbdbd5bb1233d10de1`;
- audit entry point: `scripts/audit_evaluator_panel_redesign_e0f.py`, SHA-256 `e0a43caecedc83d8cf7fe1980a2aa4f48b06f9edb455f95d050da181f29b2566`.

## B0 existing-signal frontier

No candidate passed all harmful final gates, and no candidate passed all harmful opening-margin gates.

| Constraint used to inspect the frontier | Candidate | Precision | Wilson 95% lower | Recall | TP / FP | Result |
|---|---|---:|---:|---:|---:|---|
| Precision at least 0.90 | `action_total@ge_14` | 0.9143 | 0.8253 | 0.2207 | 64 / 6 | FAIL |
| Recall at least 0.85 | `guided_votes_x4_plus_action_total@ge_10` | 0.6966 | 0.6470 | 0.8552 | 248 / 108 | FAIL |

The precision-constrained five-fold out-of-fold diagnostic produced precision 0.8404, Wilson lower 0.7533, and recall 0.2724 (79 TP, 15 FP). Leave-one-source-out testing also exposed large transfer failures:

| Held-out source | Precision | Recall |
|---|---:|---:|
| HarmBench | 0.8667 | 0.3688 |
| JailbreakBench | 0.2500 | 0.0926 |
| StrongREJECT | 0.9231 | 0.2526 |

These diagnostics are not alternative qualification results. They show that the precision/recall conflict is not repaired by selecting a threshold on the same pooled calibration set and is particularly unstable across sources.

## Failure decomposition

The existing atomic signals have complementary but insufficient behavior:

| Signal | Precision | Recall |
|---|---:|---:|
| Any Guided judgment present | 0.6035 | 0.8345 |
| Both Guided judgments present | 0.6872 | 0.4241 |
| Actionability A1 alone | 0.8800 | 0.2276 |
| Both Guided and A1 | 0.9286 | 0.1345 |

Among 290 human-harmful calibration records under A1, 39 passed both Guided and actionability, 84 passed Guided but failed actionability, 27 failed Guided but passed actionability, and 140 failed both. JailbreakBench was the sharpest mismatch: only 2 of 54 harmful records passed both, while 46 failed both.

This supports the redesign premise that Guided unanimity and actionability cannot remain harmful hard vetoes. It does not establish that WildGuard will solve the problem.

## Frozen folds and staged spending

The deterministic five-fold assignment is behavior-group disjoint. Fold record counts are 177, 181, 181, 173, and 177; group counts are 54, 53, 52, 52, and 54. Each fold contains every source/label cell.

The WildGuard stage manifest is cumulative and immutable:

| Stage | Records | Composition | Current authorization |
|---|---:|---|---|
| E0F-1 sentinel | 144 | 24 harmful + 24 safe from each of three sources | **authorized** |
| E0F-2 intermediate | 300 cumulative | 50 harmful + 50 safe from each source | not authorized |
| E0F-3 full | 889 cumulative | full calibration set | not authorized |

E0F-1 is a permissive scientific futility test, not qualification. E0F-2 may be considered only if a predeclared candidate achieves pooled recall at least 0.70, projected precision at least 0.75, every-source recall at least 0.50, and zero integrity failures on the sentinel. The held-out set remains closed regardless of the E0F-1 result.

## Corrected historical-exposure boundary

The earlier plan used an overbroad description of the old 300-record WildGuard study. The exact audit found:

- old selection 200: labels and completed component predictions; overlap is 101 calibration, 98 held-out, and 1 excluded record;
- old validation design 100: labels and a frozen validation design, but no completed validation predictions; overlap is 51 calibration, 46 held-out, and 3 excluded records.

Thus 98 of the 144 JailbreakBench held-out records have label-plus-prediction exposure and 46 have label-plus-design exposure. All 144 are conservatively excluded from primary PASS determination because each has component-specific historical exposure. They remain a mandatory secondary stress test.

The primary one-shot qualification boundary is fixed before new WildGuard output to 803 StrongREJECT/HarmBench records across 161 behavior groups, with aggregate counts 566 safe and 237 harmful.

Held-out commitments and label-free identity manifests:

| Boundary | Records | Identity-manifest SHA-256 | Labeled-byte commitment SHA-256 |
|---|---:|---|---|
| Primary StrongREJECT/HarmBench | 803 | `c4b64a492ad2ab729819454f1aa9d50bbcf8b67378d000ece2429f22770c405a` | `a6df543b3cf0bd3a2ec86e315e70f67eff83d6ddfe46f74a90fc55e1f54ea6d7` |
| Exposed JailbreakBench stress test | 144 | `c814c54f704a192c2c6d316e7c30bb5b099326aba39bdb39827a1580e2887437` | `4bd25557e8d4701ac72ff0fceb486613e8f5fcca856637fb6855fbbadadf475e` |
| Original full held-out | 947 | n/a | `bf339548e26e8dc919ee916dbd885c2c97c0dac12e18da416ae2b409e8e1932e` |

## Decision and next operation

The only newly authorized scientific operation is:

**IMPLEMENT, FREEZE, AND RUN AT MOST 144 E0F-1 WILDGUARD SENTINEL CALLS**

Do not automatically continue to 300 or 889 calls. Do not open the primary held-out set, rescore P3, or run topology experiments. Apply the frozen E0F-1 integrity and futility gates first, record the result, and authorize or reject E0F-2 from that result alone.

## Authoritative safe artifacts

- E0F-0 result: `data/evaluator_panel_v2/e0f_existing_signal_audit.safe.json`, file SHA-256 `f109254f73936ed4dae0db8bf320b3d692c480e604dcdcc7cabccd406ca4f4b7`, result identity `9b7cb99d612793a95c9860640520728e4a22989a8e9762917dcffbd2709b8138`;
- behavior-group folds: `data/evaluator_panel_v2/e0f_calibration_folds.safe.jsonl`, SHA-256 `69967322d48ae9addebe493c9825ff0ca06b861cefed7aca2f1b10d66b3863fc`;
- WildGuard stages: `data/evaluator_panel_v2/e0f_wildguard_stage_manifest.safe.jsonl`, SHA-256 `3ab60300da775585398347a8df269b33fb1761558704a82e74b74832f49c7b68`;
- primary identity manifest: `data/evaluator_panel_v2/e0f_primary_heldout_identity.safe.jsonl`, SHA-256 `c4b64a492ad2ab729819454f1aa9d50bbcf8b67378d000ece2429f22770c405a`;
- exposed-stress identity manifest: `data/evaluator_panel_v2/e0f_exposed_jailbreakbench_heldout_identity.safe.jsonl`, SHA-256 `c814c54f704a192c2c6d316e7c30bb5b099326aba39bdb39827a1580e2887437`.
