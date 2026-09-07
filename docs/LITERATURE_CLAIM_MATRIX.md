# Systematic Literature and Claim Matrix

Last audited: 2026-09-05 (Asia/Seoul)

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

**Verdict: CONDITIONAL PASS FOR AN h4rm3l-ONLY, VOCABULARY-RELATIVE CLAIM (narrow gap,
meaningful collision and significance risk).**

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

After the completed D3 development result, the project remains potentially distinct only if it
studies the **joint object and validity contract** below:

> Given a frozen successful h4rm3l jailbreak with an immutable explicit harmful payload and a
> source-native, predeclared three-unit vocabulary, enumerate every strict-subset-minimal unit set
> whose direct text neutralization restores safe non-assistance under multiple neutralizers,
> decoding seeds, a qualified abstaining evaluator panel, and matched capability controls.

The contribution is **not** that jailbreak components interact. It is the complete recovery family
for a fixed successful attack, the validity contract around that family, and a measured account of
what singleton and one-path procedures omit. Completeness is only over the declared finite unit
vocabulary, never over arbitrary natural-language edits.

The novelty cannot rest on any single phrase in that sentence. It must be established by the full conjunction and by experiments against the closest methods.

## Direct-overlap matrix

| Work | Status | Explanatory object | Intervention / objective | What it already occupies | Concrete remaining distinction |
|---|---|---|---|---|---|
| [LOCA: Minimal, Local, Causal Explanations for Jailbreak Success](https://arxiv.org/abs/2605.00123) | 2026 arXiv preprint | token-specific SAE concepts in intermediate representations | activation patching to induce refusal with a small number of representation changes | local, minimal, causal explanation of a specific jailbreak; token-specific localization inside the model | editable input-text spans; direct text intervention; full-response validation; intent preservation; neutralizer robustness; black/gray-box path |
| [DDOR: Delta Debugging for Explainable Overrefusal Testing and Repair](https://arxiv.org/abs/2606.03601) | 2026 arXiv preprint | phrase-level minimal refusal-triggering fragments in benign overrefusal cases | black-box delta debugging, multi-oracle validation, and prompt repair | minimal input-fragment localization and a one-path delta-debugging procedure | opposite starting population and outcome direction; immutable harmful payload; attack-added units only; every minimal recovery set rather than one path |
| [Jailbreak LEGO](https://openreview.net/pdf?id=Wc0VC0wUl6) | ICLR 2026 submission; no acceptance claim | atomic strategy components extracted from existing attacks | forward component composition and guided search for stronger attacks | atomic component interfaces, compositional jailbreak construction, and efficient guided search | reverse intervention on one fixed successful attack; recovery rather than attack generation; exact all-minimal family |
| [Compositional Jailbreaking](https://arxiv.org/abs/2605.15598) | 2026 arXiv preprint | ordered pairs from twelve attack mutators | forward measurement of persistence, destructive interference, and synergy | systematic component-interaction and synergy language across models | reverse payload-preserving recovery; all subsets of one declared prompt vocabulary; strict-subset minimality and controls |
| [The Anatomy of a Prompt Injection](https://arxiv.org/abs/2608.07808) | 2026 arXiv preprint | seven structural prompt-injection components | taxonomy and structured analysis record | component-level decomposition of prompt-injection artifacts | jailbreak behavior rather than taxonomy; outcome-linked neutralization; exact minimal recovery families and robustness |
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

The response judge must avoid equating any non-refusal or superficially unsafe text with a genuinely successful jailbreak. [How Real Is Your Jailbreak?](https://arxiv.org/abs/2601.03288) explicitly argues for fine-grained categories such as rejective, irrelevant, unhelpful, incorrect, and successful responses. This supports the already qualified, conservative full-response panel and explicit abstention. It does not make that automatic panel human-equivalent ground truth.

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

> We study vocabulary-relative recovery topologies of successful h4rm3l jailbreaks. For each fixed
> attack and immutable payload, we enumerate every strict-subset-minimal set of source-native
> attack units whose direct neutralization restores safe non-assistance under a predeclared
> neutralizer, seed, evaluator, and capability-control contract.

A stronger novelty sentence may be considered only after the weekly refresh:

> In a bounded search through 2026-09-05, we did not identify prior work that jointly preserves the
> harmful payload, intervenes only on source-native attack-added text units, and enumerates every
> robust strict-subset-minimal recovery set for a fixed successful jailbreak.

This is a literature-search statement, not proof of priority.

## Required closest baselines

The current exact-topology study must include, under the same frozen behavioral oracle:

- all declared singletons;
- leave-one-out ranking;
- DDMIN as the operational analogue of DDOR's one-path delta debugging;
- greedy forward and greedy backward one-path searches;
- the exact all-subset family as the oracle, with family precision, recall, Jaccard, query cost,
  and missed-path counts.

Token Highlighter and Erase-and-Check remain method-level comparisons and optional compatible
extensions; the present paper must not pretend that unit-level exact enumeration and gradient
token saliency share the same intervention vocabulary. PromptLocate, Jailbreak LEGO,
Compositional Jailbreaking, and Anatomy are threat-object comparisons rather than executable
recovery baselines. LOCA is a mechanistic comparison, not an input-text oracle.

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

## 2026-09-04 bounded refresh

Primary-source searches were rerun for jailbreak prompt ablation, minimal subsets, causal input
intervention, refusal recovery, token interaction, and all-minimal enumeration, including recent
2026 arXiv and ICLR/OpenReview records. No work was identified that occupies the complete joint
object of payload-preserving input-text intervention plus enumeration of every robust
strict-subset-minimal recovery set. This is a bounded search result, not proof of priority.

One additional relevant paper was added to the collision boundary:

- [Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak](https://arxiv.org/abs/2607.14147)
  studies a one-line prefill attack and localizes a response-site mechanism with causal probes. It
  does not enumerate input-side minimal recovery families, but it strengthens the simplest-cause
  objection: an attack can have an obvious local failure surface even when its internal mechanism
  is diffuse. The present project therefore cannot treat one obvious singleton as sufficient
  evidence for a topology paper.

The refresh also reconfirmed the active closest set: LOCA, Beyond "I'm Sorry, I Can't", Token
Highlighter, Mask-GCG, Causal Analyst, Adversarial Deja Vu, PromptLocate, TriageFuzz, GuidedBench,
and SAHARA. The current novelty status remains **conditional pass with meaningful collision and
significance risk**.

## 2026-09-05 D3-conditioned refresh

The search was repeated after the exact D3 outcome because that outcome changes which novelty
claim is still supportable. Exact-title and concept searches covered reverse jailbreak ablation,
all-minimal recovery, minimal cut sets, delta debugging, component interactions, and refusal
restoration. The bounded search did not surface a paper that already reports the same complete
payload-preserving recovery family. It did expose a tighter and less forgiving claim boundary:

- [LOCA](https://arxiv.org/abs/2605.00123), now listed as published at COLM 2026, already owns
  minimal local causal explanations of individual jailbreaks in internal representation space.
- [DDOR](https://arxiv.org/abs/2606.03601) already owns black-box phrase-level delta debugging and
  intent-preserving repair for overrefusal. DDMIN therefore cannot be presented as a new search
  idea; it is a required one-path baseline.
- [Jailbreak LEGO](https://openreview.net/pdf?id=Wc0VC0wUl6),
  [Compositional Jailbreaking](https://arxiv.org/abs/2605.15598), and
  [Concept2Scenario](https://arxiv.org/abs/2607.23496) already occupy atomic attack components,
  forward composition, interaction, and synergy language.
- [Adversarial Deja Vu](https://proceedings.iclr.cc/paper_files/paper/2026/hash/ab41709d06e9303c25ad6742ae661198-Abstract-Conference.html)
  is an ICLR 2026 paper that models unseen jailbreaks as sparse recombinations of previously seen
  adversarial skills. This blocks any broad claim that jailbreaks have reusable compositional
  primitives.
- [Robust Harmful Features](https://arxiv.org/abs/2606.28153), an ICML 2026 Oral, already links
  attack-template tokens to selective suppression of safety-relevant attention heads. Input-unit
  recovery cannot be marketed as the first token-to-mechanism account.
- [The Anatomy of a Prompt Injection](https://arxiv.org/abs/2608.07808) formalizes a seven-part
  component model for prompt-injection artifacts. A component taxonomy is not a contribution here.

The completed D3 coarsening result is now the dominant significance objection: all nine h4rm3l
instances become the same singleton macro-group when the first two adjacent source decorators are
merged. Consequently, even a successful confirmation may support only a
**source-native-vocabulary-relative complete-family** claim. It cannot support
granularity-invariant synergy, universal attack decomposition, or cross-attack-family generality.

The surviving empirical test is therefore narrow and falsifiable: on fresh payloads and two target
model families, does exact enumeration repeatedly recover more robust source-native minimal
families than every admitted singleton or one-path baseline, while passing the unchanged
neutralizer, fresh-seed, evaluator, and capability gates? A negative second-model or baseline-gap
result should stop the central paper claim rather than trigger another scope repair.

## 2026-09-05 STEP1 update -- latest independent-main claim decision

The immediately preceding exact-family continuation proposal is historical. The
author's latest priority and completed STEP1 decision are recorded in
[STEP1_ICLR_MAIN_CLAIM_AND_CLOSEST_WORK_AUDIT_2026-09-05.md](STEP1_ICLR_MAIN_CLAIM_AND_CLOSEST_WORK_AUDIT_2026-09-05.md).
No earlier conditional pass establishes the latest candidate's paper readiness.

Material claim-boundary corrections from the linked primary-source audits:

- DDOR explicitly recognizes nonmonotonicity, multiple triggers and the limits of
  1-minimality. A hypothetical consumer's global-necessity or upward-safety claim
  must not be attributed to DDOR/ddmin.
- FAME is verified in the official ICLR 2026 proceedings. Finite erasure observations
  must not be equated to its universal-completion sufficiency certificates.
- PromptLocate already measures post-removal attack outcomes AND legitimate task
  recovery, including AgentDojo; it is not merely a span-overlap baseline.
- AttnTrace v3 is a direct collision: observed-output attribution, post-removal
  attack success, agent settings, collaborating malicious texts, and existing
  PromptLocate overlocalization evidence. See the reviewer audit, Section 8,
  for the primary paper, official acceptance list and code boundaries.

The retained question is therefore conditional and narrower: isolate a published
learned-oracle search assumption from detector/length/renderer error, establish
material final security/utility consequences, and show value beyond simple
rechecking. Neither this gap nor a new corrective method is demonstrated yet.
GO is limited to bounded feasibility/falsification, not a paper-scale run.
