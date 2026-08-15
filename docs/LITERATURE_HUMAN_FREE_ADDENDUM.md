# Literature Addendum — Human-Free Programmatic Design

Last audited: 2026-08-15 (Asia/Seoul)

This addendum supplements `docs/LITERATURE_CLAIM_MATRIX.md` after changing the primary paper design from free-form paired jailbreaks plus human semantic audit to programmatically grounded compositional jailbreaks plus automated evaluator consensus.

## New closest collision: h4rm3l

[h4rm3l: A Dynamic Benchmark of Composable Jailbreak Attacks for LLM Safety Assessment](https://arxiv.org/abs/2408.04811) already contributes:

- a domain-specific language for composable jailbreak attacks;
- parameterized string-transformation primitives;
- program synthesis for high-ASR attack discovery;
- an automated human-aligned harmful-behavior classifier;
- a large dataset and benchmark across multiple target models.

Blocked claims:

- first formal/composable jailbreak language;
- first programmatic jailbreak benchmark;
- first interpretable composition of attack primitives;
- first automated synthesis over jailbreak programs.

Remaining defensible gap:

> Given a successful formally represented jailbreak program, identify the smallest robust set of program components or rendered spans whose typed neutralization restores safety while preserving the payload exactly, or abstain when the causal structure is distributed.

h4rm3l optimizes attack programs for success. The proposed paper analyzes successful programs through exhaustive interventions and develops a query-efficient causal localization method.

## Program provenance versus causal ground truth

A generated program supplies exact component provenance, but this is not itself causal ground truth. The paper must distinguish:

- **provenance ground truth:** which program node rendered which characters/tokens;
- **interventional oracle:** which node/span sets actually change target-model behavior under the frozen intervention family;
- **algorithm prediction:** which sets are found under a limited target-query budget.

Calling the inserted scaffold or DSL node `the causal ground truth` without an intervention oracle would be vulnerable to immediate reviewer rejection.

## Evaluator literature and the no-new-human-annotation design

### HarmBench

[HarmBench](https://arxiv.org/abs/2402.04249) provides a standardized framework for automated red teaming and robust refusal across many methods and models. It supports the use of a frozen automated classifier in a reproducible safety pipeline.

### JailbreakBench

[JailbreakBench](https://arxiv.org/abs/2404.01318) standardizes threat models, behaviors, chat templates, scoring, attack costs, and reproducible artifacts. It supports complete-denominator and target-specific eligibility reporting.

### StrongREJECT

[StrongREJECT](https://arxiv.org/abs/2402.10260) shows that many existing evaluation methods substantially overestimate jailbreak success and proposes an evaluator that measures useful harmful information and aligns more closely with human judgments.

Consequence: refusal-marker heuristics and single binary guard labels cannot serve as the primary oracle.

### FJAR

[How Real is Your Jailbreak? / FJAR](https://arxiv.org/abs/2601.03288) separates rejective, irrelevant, unhelpful, incorrect, and successful outputs using anchored references and reports improved alignment with human judgment.

Consequence: evaluator consensus should distinguish failure modes rather than treating every non-refusal as successful harmful compliance.

### Correct interpretation of `human-free`

The project may contain no new human annotations while using public evaluators that were themselves developed or validated using human judgments. The supportable wording is:

> No new human annotations are used in our benchmark construction, primary evaluation, or gate decisions.

The unsupported wording is:

> The evaluation is independent of all human-labeled data or human normative choices.

## Closest localization and intervention work remains binding

The human-free reformulation does not erase existing overlap with:

- [LOCA](https://arxiv.org/abs/2605.00123): local/minimal/causal jailbreak explanations in representation space;
- [Token Highlighter](https://ojs.aaai.org/index.php/AAAI/article/view/34943): gradient-based critical-token localization and soft removal;
- [GuardNet](https://arxiv.org/abs/2509.23037): supervised token-level adversarial-span localization;
- [Erase-and-Check](https://arxiv.org/abs/2309.02705): systematic token erasure, safety checking, greedy and gradient variants;
- [PromptLocate](https://arxiv.org/abs/2510.12252): semantic-segment localization for prompt injection;
- [Sufficient Input Subsets](https://proceedings.mlr.press/v89/carter19a.html): minimal black-box feature subsets;
- [WAM](https://proceedings.mlr.press/v267/kasmi25a.html): wavelet-domain feature attribution.

Therefore novelty must come from the joint object and validity contract plus the efficient algorithm—not from tokens, spans, minimality, composability, causal language, or wavelets individually.

## Required literature-facing positioning

Recommended positioning paragraph:

> Prior work separately formalizes compositional jailbreak programs, localizes critical input tokens or supervised adversarial spans, certifies safety through token erasure, and produces local causal explanations in internal representation space. We instead study interventional localization within successful compositional attack programs. Exact payload provenance and typed rendering make intervention validity machine-checkable, while an exhaustive oracle identifies minimal robust enabling component sets within a declared candidate lattice. The learning problem is to approach this oracle under a limited target-model query budget and to abstain when the causal structure is distributed or evaluator-ambiguous.

## Weekly refresh targets

Re-run title and citation-neighbor searches for:

- h4rm3l and papers citing it;
- LOCA;
- Token Highlighter;
- GuardNet;
- Erase-and-Check;
- PromptLocate and WebSentinel;
- StrongREJECT, HarmBench, FJAR, and new jailbreak evaluators;
- compositional prompt attribution, program slicing, and causal subprogram localization;
- query-efficient black-box explanation and group testing;
- wavelet/hierarchical attribution if tree-Haar remains under consideration.

Any paper that jointly provides typed payload-preserving attack programs, exhaustive minimal causal component oracles, and query-efficient localization would require immediate scope reassessment.