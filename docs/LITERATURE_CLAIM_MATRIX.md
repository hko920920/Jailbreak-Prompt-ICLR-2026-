# Systematic Literature and Claim Matrix

Last audited: 2026-08-14 (Asia/Seoul)

## Audit protocol

This audit is designed to test the paper's novelty boundary, not to collect a long generic jailbreak bibliography.

Sources searched:

- SciSpace semantic paper search using multiple independently phrased questions;
- arXiv and arXiv HTML full text;
- OpenReview / official conference pages;
- AAAI OJS, PMLR, and ACL Anthology;
- backward and forward terminology expansion from the closest papers.

Search axes:

1. jailbreak-critical input tokens, phrases, and spans;
2. text deletion, masking, neutralization, and refusal recovery;
3. minimal, necessary, sufficient, or causal input explanations;
4. prompt-injection and adversarial-segment localization;
5. safety heads, refusal features, and token-to-circuit attribution;
6. wavelet, tree-Haar, hierarchical, and multiresolution attribution;
7. jailbreak-success evaluation and intent-preservation validity.

Inclusion rule: a paper is retained below if it overlaps the explanatory object, intervention, validity criterion, search problem, mechanism claim, or core evaluation protocol. Generic attacks and defenses without localization or causal relevance are excluded from the main matrix.

No literature search can prove mathematical exhaustiveness. Therefore this document records the search boundary and must be refreshed weekly until the evidence freeze.

## Decision summary

**Verdict: CONDITIONAL PASS (narrow gap, meaningful collision risk).**

The broad topic is occupied. The following are already established in prior work:

- local, minimal, causal explanations of jailbreak success in internal representation space;
- jailbreak-critical token localization;
- token-level adversarial-span localization;
- token erasure or attribution-guided excision for jailbreak defense;
- semantic-segment localization for prompt injection;
- token-sensitive query-efficient jailbreak search;
- token-to-safety-head mechanistic attribution;
- wavelet-domain feature attribution;
- minimal sufficient input subsets and compact rationales in general NLP/XAI.

The project remains potentially distinct only if it studies the **joint object and validity contract** below:

> Given an original harmful request that is refused and a successful jailbreak prompt that preserves the same requested behavior, identify a minimal human-editable input-text span set whose direct text-level neutralization restores refusal, while preserving the underlying harmful intent, remaining robust across multiple neutralizers / decoding seeds / judges, and abstaining when the cause is distributed.

The novelty cannot rest on any single phrase in that sentence. It must be established by the full conjunction and by experiments against the closest methods.

## Direct-overlap matrix

| Work | Status | Explanatory object | Intervention / objective | What it already occupies | Concrete remaining distinction |
|---|---|---|---|---|---|
| [LOCA: Minimal, Local, Causal Explanations for Jailbreak Success](https://arxiv.org/abs/2605.00123) | 2026 arXiv preprint | token-specific SAE concepts in intermediate representations | activation patching to induce refusal with a small number of representation changes | local, minimal, causal explanation of a specific jailbreak; token-specific localization inside the model | editable input-text spans; direct text intervention; full-response validation; intent preservation; neutralizer robustness; black/gray-box path |
| [Token Highlighter](https://ojs.aaai.org/index.php/AAAI/article/view/34943) | AAAI 2025 | individual input tokens | gradient of Affirmation Loss; soft embedding removal | jailbreak-critical token localization and mitigation | semantic span sets rather than independent saliency; text edits rather than embedding shrinkage; minimality and intent-preservation constraints |
| [GuardNet](https://arxiv.org/abs/2509.23037) | 2025 arXiv preprint | token-level adversarial spans | supervised graph-attention filtering before inference | fine-grained adversarial-span localization with token labels and IoU/F1 evaluation | behavioral/interventional rather than supervised change-label detection; minimal cause of observed refusal failure; intent preservation and abstention |
| [Certifying LLM Safety against Adversarial Prompting](https://arxiv.org/abs/2309.02705) | 2023 arXiv preprint | erased token subsequences | erase-and-check safety filtering; certified defense against bounded inserted tokens | systematic token erasure, greedy/gradient erasure, and safety checking | explanation rather than certification; target-model refusal recovery; human-readable minimal spans; preservation of original harmful goal |
| [Explain–Delete–Defend](https://www.csitcp.net/abstract/15/1513csit01) | SPM 2025 proceedings; lower evidentiary weight but direct overlap | high-attribution tokens | SHAP / feature-ablation ranking followed by token excision and regeneration | attribution-guided token deletion as a low-latency jailbreak defense | robust minimal semantic span-set localization; no fixed deletion percentage; intent preservation; distributed-case abstention; stronger venues/models/evaluation |
| [PromptLocate](https://arxiv.org/abs/2510.12252) | to appear IEEE S&P 2026 | semantically coherent segments containing injected instructions/data | prompt-injection localization for forensics and data recovery | semantic-segment localization of malicious prompt content | jailbreak rather than indirect prompt injection; paired original/jailbreak behavior; intervention-induced refusal recovery and intent preservation |
| [WebSentinel](https://arxiv.org/abs/2602.03792) | 2026 arXiv preprint | suspicious webpage segments | segment extraction and context-consistency checking | segment-level localization in web-agent prompt injection | same distinction as PromptLocate; not the primary closest baseline for single-turn jailbreaks |
| [TriageFuzz: Not All Tokens Are Created Equal](https://arxiv.org/abs/2603.23269) | 2026 arXiv preprint | refusal-sensitive prompt regions estimated by a surrogate | token-aware mutation for query-efficient attack generation | skewed token contributions and query-efficient sensitive-region search | explanatory/remedial localization rather than attack optimization; robust minimal text intervention and intent preservation |
| [ALERT](https://arxiv.org/abs/2601.03600) | 2026 arXiv preprint | informative safety tokens and internal discrepancies | zero-shot jailbreak detection | token-wise localization of safety-relevant signals | detection is not a minimal behavioral explanation; no direct text neutralization contract |

## Mechanistic-overlap matrix

| Work | Status | Main result relevant to this project | Claim blocked here |
|---|---|---|---|
| [What Features in Prompts Jailbreak LLMs?](https://arxiv.org/abs/2411.03343) | 2024 arXiv preprint | different attacks rely on different nonlinear prompt-representation features and transfer poorly to held-out attack methods | universal or linear jailbreak-feature explanations |
| [On the Role of Attention Heads in LLM Safety / SAHARA](https://arxiv.org/abs/2410.13708) | ICLR 2025 Oral | identifies safety-critical heads and studies their causal safety contribution | first safety-head discovery or a broad head-level safety explanation |
| [Attention Slipping](https://arxiv.org/abs/2507.04365) | 2025 arXiv preprint | successful attacks reduce attention allocated to unsafe requests across several attack classes | first attention-routing account of jailbreak success |
| [Robust Harmful Features Under Jailbreak Attacks](https://arxiv.org/abs/2606.28153) | ICML 2026 Oral | attack-template tokens selectively drive suppression of adversarially compromised heads while other safety heads retain harmful features | first token-to-safety-head linkage; first template-token mechanistic attribution |
| [Do LLMs Know Their Vulnerable Scenarios? / Concept2Scenario](https://arxiv.org/abs/2607.23496) | 2026 arXiv preprint | attributes refusal suppression to SAE concepts, translates them to scenarios, and studies synergistic combinations | first interpretable scenario-level refusal-vulnerability discovery or interaction attribution |
| [Where Did It Go Wrong?](https://arxiv.org/abs/2510.02334) | 2025 arXiv preprint | representation-gradient tracing provides sample- and phrase-level causal attribution for undesirable behavior | broad first fine-grained causal phrase attribution in LLM safety |

Mechanistic analysis in this project is therefore supporting evidence only. It may test whether behaviorally localized spans perturb previously identified safety mechanisms more than matched controls, but it must not become a second safety-head-discovery contribution.

## General explanation and multiresolution foundations

| Work | Established result | Consequence for claims |
|---|---|---|
| [Sufficient Input Subsets](https://proceedings.mlr.press/v89/carter19a.html), AISTATS 2019 | minimal observed feature subsets sufficient for the same black-box decision | cannot claim first minimal input subset or model-agnostic subset explanation |
| [Rationales for Sequential Predictions](https://arxiv.org/abs/2109.06387), EMNLP 2021 | combinatorial smallest context subsets and greedy rationalization for sequential outputs | minimal token subset search is an established explanation paradigm |
| [Input Mask Optimization](https://aclanthology.org/2023.findings-acl.867/), ACL Findings 2023 | extractive masks optimized for sufficiency, comprehensiveness, and compactness | these validity terms and mask objectives are not novel by themselves |
| [Towards Faithful Model Explanation in NLP](https://doi.org/10.1162/coli_a_00511), Computational Linguistics 2024 | systematic faithfulness taxonomy including counterfactual intervention | deletion-based faithfulness must address intervention artifacts and construct validity |
| [One Wave To Explain Them All / WAM](https://proceedings.mlr.press/v267/kasmi25a.html), ICML 2025 | wavelet-domain, scale-localized feature attribution across multiple modalities | cannot claim first wavelet attribution; wavelet must earn value through query efficiency, scale recovery, or stability |

## Evaluation-adjacent work

The response judge must avoid equating any non-refusal or superficially unsafe text with a genuinely successful jailbreak. [How Real Is Your Jailbreak?](https://arxiv.org/abs/2601.03288) explicitly argues for fine-grained categories such as rejective, irrelevant, unhelpful, incorrect, and successful responses. This supports the planned human audit and multi-class response-judge design.

## Forbidden claims

The paper must not state or strongly imply any of the following:

1. "We are the first to provide a local, minimal, causal explanation of jailbreak success."
2. "Jailbreak-critical input tokens have not been localized before."
3. "Fine-grained adversarial spans in jailbreak prompts have not been identified before."
4. "Removing important jailbreak tokens is a new defense principle."
5. "Semantic segmentation for malicious-prompt localization is new."
6. "Token-aware query-efficient search of jailbreak prompts is new."
7. "Attack-template tokens have not been connected to safety-critical heads."
8. "Wavelets have not previously been used for feature attribution."
9. "Minimal sufficient input subsets or compact rationales are new."
10. Any unqualified "first" claim before the final pre-submission refresh.

## Provisional supportable claim

Use conservative wording until the phenomenon and algorithm gates pass:

> We study intent-preserving interventional localization of human-editable jailbreak-enabling span sets. An explanation is accepted only when direct text neutralization restores the target model's refusal while retaining the underlying requested behavior, remains stable across intervention realizations, and passes subset-minimality checks; the method may abstain when no localized explanation is supported.

A stronger novelty sentence may be considered only after the weekly refresh:

> We did not identify prior work that jointly enforces text-level editability, target-model refusal recovery, harmful-intent preservation, multi-neutralizer robustness, subset minimality, and explicit distributed-case abstention for successful jailbreak prompts.

This is a literature-search statement, not proof of priority.

## Required closest baselines

At minimum, the empirical comparison must include or faithfully adapt:

- Token Highlighter;
- Erase-and-Check, GreedyEC, or GradEC as appropriate;
- SHAP / feature-ablation token excision;
- GuardNet when compatible token labels and code are available;
- random length- and position-matched spans;
- leave-one-out and a wavelet-free hierarchical search;
- exhaustive contiguous-span search on tractable prompts.

PromptLocate is primarily a threat-model comparison rather than necessarily an executable baseline. LOCA is a mechanistic comparison and may be evaluated on a smaller open-weight subset rather than across the full black/gray-box benchmark.

## Project gates created by this audit

1. **Phenomenon gate:** intent-preserving text neutralization must recover refusal on a meaningful fraction of eligible jailbreaks.
2. **Artifact gate:** recovery must survive at least two neutralizers and manual coherence review.
3. **Minimality gate:** selected span sets must pass direct subset tests against an exhaustive or near-exhaustive oracle where tractable.
4. **Comparison gate:** the method must improve on token saliency/excision baselines in explanation validity, minimality, stability, or query cost.
5. **Wavelet gate:** tree-Haar remains only if it materially improves the quality-query Pareto frontier, heterogeneous-scale recovery, boundary stability, or interaction discovery.
6. **Scope gate:** if single-span explanations are uncommon, pivot to localized-versus-distributed causal structure rather than forcing localization.

## Refresh rule

- Run the same SciSpace and primary-source searches once per week through paper submission.
- Add newly surfaced works to this matrix with venue/status and the exact claim collision.
- Re-run exact-title and citation-neighbor searches for LOCA, Token Highlighter, GuardNet, PromptLocate, TriageFuzz, and Robust Harmful Features.
- Record the refresh date even when no new direct competitor is found.
- Immediately narrow or pivot the claim if a work satisfies the full joint validity contract above.
