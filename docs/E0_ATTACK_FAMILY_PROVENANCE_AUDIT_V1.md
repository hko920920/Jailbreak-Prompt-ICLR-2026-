# E0 Attack-Family Provenance and Feasibility Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Status and boundary

This is a **pre-outcome provenance audit** for the cross-regime jailbreak causal-topology study. No target-model attack outputs, eligibility labels, causal interventions, held-out outputs, or wavelet results were generated or inspected while preparing this record.

The purpose of E0 is to determine whether each candidate attack family has a defensible and reproducible route before it is admitted to the balanced signal screen. Repository availability alone is insufficient. Every primary family must satisfy:

1. an official or author-maintained source repository;
2. an immutable source revision;
3. a usable research and redistribution route under its license;
4. a reproducible artifact-generation or frozen-artifact route;
5. explicit target-model and tokenizer compatibility;
6. a defensible rule for preserving the harmful goal exactly once;
7. an intervention vocabulary that can be frozen before outcomes;
8. a compute budget compatible with the staged feasibility study.

Raw jailbreak prompts and harmful outputs are not recorded in this public audit.

## Preliminary balanced matrix

The current **provisional main matrix** is:

| Regime | Primary candidate 1 | Primary candidate 2 | Status |
|---|---|---|---|
| S — semantic-readable | h4rm3l | DeepInception | both advance to static adapter audit |
| F — fluent optimized | AutoDAN | AdvPrompter | AutoDAN advances; AdvPrompter is conditional on artifact/payload checks |
| U — non-fluent optimized | GCG | AmpleGCG | both advance conditionally; AmpleGCG requires responsible-use and artifact checks |

The matrix is not yet authorized for target-model execution. A candidate becomes frozen only after its source, adapter, payload-preservation, tokenizer, artifact, and compute checks pass.

---

## Regime S — semantic-readable attacks

### S1. h4rm3l — primary candidate

- source: `mdoumbouya/h4rm3l`
- immutable revision: `e6f58a1a1e56c1a95b26b06aa4fe393ee2240dbd`
- repository license: MIT
- provenance role: official compositional jailbreak DSL and red-teaming toolkit
- expected attack object: typed, human-readable strategy composition
- expected intervention units: DSL strategy/decorator nodes, rendered clauses, sentences, and localized spans
- preliminary payload-preservation route: construct the attack scaffold around one frozen payload placeholder and verify exactly one byte-identical occurrence after rendering
- preliminary decision: `ADVANCE_TO_STATIC_ADAPTER_AUDIT`

Why it is useful: the DSL gives typed provenance for attack-added components, which supports exact node-subset intervention without inventing post-hoc semantic segments.

Remaining blockers:

- verify the exact renderer path used by the existing project adapter;
- test that every selected composition preserves one payload occurrence;
- freeze the set of allowed nodes and rule out payload-mutating decorators;
- confirm deterministic rendering under the pinned revision.

### S2. DeepInception — primary candidate

- source: `tmlr-group/DeepInception`
- immutable revision: `fc5689e76c4dd87a14babf1eadf890532f2b6880`
- repository license: MIT
- provenance role: author-maintained implementation of a nested fictional-scene jailbreak
- expected attack object: human-readable nested scenario and role structure
- expected intervention units: outer framing, scene nesting, character/role assignment, task embedding, and response-format clauses
- preliminary payload-preservation route: insert the frozen harmful goal once at the designated task slot and forbid rewriting during adaptation
- preliminary decision: `ADVANCE_TO_STATIC_ADAPTER_AUDIT`

Why it is useful: it is structurally distinct from h4rm3l's broad compositional DSL and provides a nested semantic attack whose interaction order may be nontrivial.

Remaining blockers:

- reproduce prompt construction from the pinned source;
- define typed units without using outcome-dependent segmentation;
- verify one-occurrence payload invariance;
- verify that the selected configuration is single-turn and does not rely on conversation history.

---

## Regime F — fluent optimized attacks

### F1. AutoDAN — primary candidate

- source: `SheltonLiu-N/AutoDAN`
- immutable revision: `34062e964185693e81a6775b4f0d00bfd7507612`
- repository license: MIT
- provenance role: official ICLR 2024 implementation of a stealthy, readable optimized jailbreak
- expected attack object: automatically optimized but fluent adversarial prompt/scaffold
- expected intervention units: provenance-preserving generated clauses, sentences, and fixed token blocks inside the generated attack portion
- preliminary payload-preservation route: preserve the frozen harmful goal in the source instruction field and distinguish it from the optimized attack-added text
- preliminary decision: `ADVANCE_TO_STATIC_ADAPTER_AUDIT`

Remaining blockers:

- determine whether the official route rewrites or semantically transforms the harmful goal;
- select only configurations where the goal can be recovered and verified byte-identically, or define a separate non-byte-preserving formulation before outcomes;
- freeze initialization, population, mutation, model, tokenizer, and compute budget;
- determine whether official frozen artifacts can replace expensive regeneration without selection bias.

### F2. AdvPrompter — conditional primary candidate

- source: `facebookresearch/advprompter`
- immutable revision: `802a500c91f1dcd7c8b76869d3e39bf8e40ed7d7`
- repository state: archived/read-only
- repository license: Creative Commons Attribution-NonCommercial 4.0
- provenance role: official implementation of a learned generator for human-readable adversarial suffixes
- expected attack object: fluent generated suffix appended to an explicit harmful instruction
- expected intervention units: generated sentence/clause segments and fixed contiguous token blocks
- preliminary payload-preservation route: keep the frozen instruction untouched and intervene only on the generated suffix
- preliminary decision: `CONDITIONAL_ADVANCE`

Conditions for admission:

- confirm that academic noncommercial use and any released adapter code/artifacts comply with attribution and noncommercial restrictions;
- confirm model/checkpoint/data availability at the pinned revision or define a reproducible frozen-output route;
- verify that suffix generation leaves the harmful instruction byte-identical;
- freeze the generator checkpoint, sampling configuration, tokenizer, and candidate-selection rule before outputs.

Fallback rule: if any condition fails, replace AdvPrompter before the balanced screen. It cannot be retained merely because it is scientifically convenient.

---

## Regime U — non-fluent optimized attacks

### U1. GCG — primary candidate

- source: `llm-attacks/llm-attacks`
- immutable revision: `098262edf85f807224e70ecd87b9d83716bf6b73`
- repository license: MIT
- provenance role: canonical implementation of universal and transferable adversarial suffix optimization
- expected attack object: discrete non-fluent optimized suffix attached to one explicit harmful goal
- expected intervention units: predeclared equal-token blocks, recursive sub-blocks, and contiguous token intervals
- preliminary payload-preservation route: freeze the harmful request and optimize/intervene only on the appended suffix
- preliminary decision: `ADVANCE_TO_STATIC_ADAPTER_AUDIT`

Remaining blockers:

- freeze exact model/tokenizer compatibility and chat template;
- choose regeneration versus frozen suffix artifacts before outcome inspection;
- freeze optimization budget and candidate-selection rule;
- require a position-preserving neutralizer in addition to deletion;
- define contract-exactness only over the frozen block/interval vocabulary.

### U2. AmpleGCG — conditional primary candidate

- source: `OSU-NLP-Group/AmpleGCG`
- immutable revision: `92fbc9a14d40dfaaf5f7f479ef0d56f32c2f93a3`
- repository license: AI Pubs OpenRAIL-S 0.1 with responsible-use restrictions
- provenance role: learned generator of multiple transferable adversarial suffixes rather than per-instance coordinate optimization
- expected attack object: generated discrete adversarial suffix attached to one explicit harmful goal
- expected intervention units: generated suffix blocks, recursive sub-blocks, and contiguous token intervals
- preliminary payload-preservation route: freeze the harmful request and intervene only on the generated suffix
- preliminary decision: `CONDITIONAL_ADVANCE`

Why it is provisionally preferred over a second GCG optimization variant: it changes the attack-generation mechanism from iterative per-instance optimization to a learned suffix generator, improving family diversity within Regime U.

Conditions for admission:

- verify source, model, checkpoint, and dataset access under all applicable licenses;
- verify that the intended safety-research use and redistribution route respect the OpenRAIL restrictions;
- freeze generator checkpoint, sampling, candidate count, and selection rule;
- confirm exact suffix/payload separation and tokenizer compatibility;
- confirm a feasible compute path without selecting examples after target outcomes.

---

## Secondary, sensitivity, and blocked candidates

### BEAST — scientifically valuable but license-blocked backup

- source: `vinusankars/BEAST`
- immutable revision: `a3448da673f6527a523668bd40554301eee69e67`
- official role: ICML 2024 gradient-free beam-search adversarial attack
- detected repository license: none
- decision: `BLOCKED_PENDING_LICENSE_OR_PERMISSION_ROUTE`

BEAST is attractive because it is more independent from GCG than another coordinate-gradient variant. It must not become a main family unless a defensible use and redistribution route is documented. Scientific diversity does not override provenance requirements.

### AttnGCG — licensed U-regime backup and attention-sensitive extension

- source: `UCSC-VLAA/AttnGCG-attack`
- immutable revision: `201aee0167c4e7ea2ad5601829dc7fe6afe880cc`
- repository license: MIT
- decision: `LICENSED_BACKUP_OR_SENSITIVITY_ONLY`

It is reproducible and licensed, but it remains in the GCG lineage. It does not automatically count as an independent second family in the main cross-regime claim.

### I-GCG — optimization-strength sensitivity candidate

- source: `jiaxiaojunQAQ/I-GCG`
- immutable revision: `8820ec669cee41d6cd0162d84dfa6e4379fc697d`
- official role: ICLR 2025 improved GCG optimization
- detected repository license: none
- decision: `SENSITIVITY_ONLY_PENDING_LICENSE`

It is useful for testing whether topology changes with a stronger optimizer, but it should not be counted as a distinct main family from GCG.

### SlotGCG — position-sensitivity candidate

- source: `youai058/SlotGCG`
- immutable revision: `d76c3c9b6bc1c2cfffd2906301d3945c9f9d4b56`
- official role: ICLR 2026 position-aware GCG variant
- detected repository license: none
- decision: `POSITION_SENSITIVITY_ONLY_PENDING_LICENSE`

Its main methodological value is to test whether causal conclusions survive position-preserving neutralization. It should not be pooled with ordinary suffix attacks without explicit insertion-position controls.

---

## Admission tests to execute next

The next E0 step is a **static source and adapter audit**, not target-model attack execution.

For each provisional main family, the audit will produce only safe metadata:

1. checkout/download success at the exact revision;
2. license file identity and redistribution notes;
3. entrypoint and dependency resolution;
4. supported target models and tokenizers;
5. prompt-construction path and insertion position;
6. proof that the frozen payload occurs exactly once and remains unchanged;
7. deterministic unit manifest for the attack-added region;
8. availability of official artifacts or reproducible generation route;
9. estimated compute and storage budget;
10. adapter test status on synthetic non-harmful placeholder inputs.

No real harmful attack output is required for these checks.

## E0 decision rule

A balanced signal-screen contract may be frozen only if:

- exactly two main families in each of S, F, and U pass all mandatory admission tests;
- no family is selected using target-model outcomes;
- intervention units and position rules are frozen;
- generation/frozen-artifact routes are declared;
- payload invariance is machine-checked;
- the compute budget is feasible;
- the evaluator panel has independently passed its required validation gate.

If a candidate fails, its replacement must be chosen and audited before any cross-regime target output is inspected.

## Current sealed boundary

At this E0 freeze point:

- no cross-regime target outputs have been generated;
- the legacy semantic-only Stage A remains closed;
- cross-regime Stage A remains closed;
- prior evaluation and held-out partitions remain sealed;
- the causal oracle and keep-only oracle remain closed;
- wavelet remains closed;
- this document is provenance and feasibility evidence, not a scientific result.
