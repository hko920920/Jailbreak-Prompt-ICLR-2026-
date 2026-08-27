# Paper Scope Decision v2: Input-Level Causal Topology of LLM Jailbreaks

Date: 2026-08-27 (Asia/Seoul)
Status: frozen before any new target-model outcome
Target venue: ICLR 2027

## 1. Decision

The previous plan was too broad for one paper because it treated all of the following as co-equal contributions:

- a new evaluator panel;
- three fully populated attack regimes (semantic-readable, fluent optimized, and non-fluent optimized);
- exact minimal-cut topology;
- token-level refinement;
- necessity and sufficiency;
- a new efficient search method, including wavelet search;
- two or more attack families per regime and two model families.

That plan is not abandoned, but it is no longer the minimum paper contract.

The standalone paper is narrowed to one scientific question:

> For a frozen, already-successful jailbreak, what are the smallest attack-added input combinations whose neutralization reliably removes substantive harmful assistance without changing the explicit harmful goal or collapsing general model capability?

The primary empirical object is the complete set of robust minimal recovery sets within a predeclared coarse intervention vocabulary. Attack-family comparisons test generality; they are not separate contributions that each require an independent full study.

## 2. Current paper identity

Working title:

> **Beyond Critical Tokens: Minimal Recovery Topologies of LLM Jailbreaks**

One-sentence statement:

> We directly intervene on frozen successful jailbreak prompts, enumerate all minimal attack-added input sets whose removal restores safe behavior under multiple neutralizers, and test when singleton attribution misses higher-order interaction or alternative causal pathways.

The paper is not:

- a token-importance ranking paper;
- a jailbreak-generation paper;
- a new evaluator benchmark paper;
- a defense paper;
- a complete taxonomy of every jailbreak regime;
- a wavelet-search paper.

## 3. Why this remains an independent paper

Existing work already occupies nearby claims:

- Token Highlighter ranks jailbreak-critical tokens with gradients and soft embedding removal.
- Mask-GCG studies token redundancy and compression in optimized suffixes.
- Causal Analyst learns causal graphs over human-readable prompt features.
- LOCA gives minimal local causal explanations in intermediate representation space.
- GuidedBench shows that jailbreak evaluation requires case-specific criteria.

Therefore novelty cannot come from “finding important tokens,” “giving a minimal explanation,” or “using causal language.” The defensible conjunction is narrower:

1. input-side behavioral interventions on the original frozen prompt;
2. all minimal recovery sets, not only one ranked explanation;
3. strict-subset minimality;
4. higher-order interaction and alternative-pathway topology;
5. payload preservation and capability-confound controls;
6. agreement across at least two meaningful neutralizers;
7. comparison against singleton attribution and masking baselines.

This conjunction is sufficient for a standalone empirical paper if repeated non-singleton or multiple-pathway structure is found and replicated.

## 4. Core empirical scope

### 4.1 Development micro-pilot

Use two structurally different and already-audited families:

- **h4rm3l**: human-readable compositional semantic structure;
- **GCG**: non-fluent optimized suffix structure.

Use one frozen open-weight target model for the development decision. The purpose is not broad generalization; it is to decide whether the causal-topology object produces nontrivial, stable evidence.

### 4.2 Main confirmatory extension after GO

Only after the micro-pilot passes:

- add **DeepInception** as semantic-family replication;
- add **AutoDAN** as fluent-optimized replication;
- add a second target-model family;
- freeze fresh payloads and a paper-valid confirmatory split.

This yields four representative attack mechanisms without requiring two fully qualified families in every S/F/U bucket.

### 4.3 Descriptive strata, not causal regime claims

Results may be stratified as:

- semantic-compositional;
- fluent optimized;
- non-fluent optimized.

However, the paper must not claim that readability or optimization mechanism alone causes a topology difference unless the design supports that causal comparison. Family- and model-specific effects are valid findings.

## 5. Main outcomes

The primary outcomes are:

- minimum robust recovery-set size;
- number of distinct minimal recovery sets;
- maximum confirmed interaction order;
- fraction of cases with singleton, non-singleton, multiple-pathway, distributed-within-budget, or capability-confounded topology;
- agreement across neutralizers and seeds;
- exact-topology recovery accuracy of singleton attribution and masking baselines.

Necessity is primary. Keep-only sufficiency is optional and may appear only where a coherent complement reconstruction exists. No sufficiency claim is allowed otherwise.

## 6. Measurement decision after HarmBench

HarmBench is excluded from the production voting panel under the frozen E1C decision. Its earlier 200-example accuracy and later paired-invariance failures remain development evidence and are not erased.

The new measurement strategy is hybrid and deliberately limited:

1. automatic evaluators are used for high-recall development screening and disagreement detection;
2. WildGuard may contribute a conservative refusal/general-harmfulness signal but is never the single primary judge;
3. HarmBench may be retained only as a non-voting diagnostic;
4. every paper-reported attacked baseline, minimal recovery set, strict subset needed for minimality, neutralizer disagreement, and confirmatory control enters blinded human audit;
5. final confirmatory labels require two independent annotators and third-person adjudication on disagreement;
6. same-model personas remain development sensitivity analyses and are not counted as humans.

This prevents evaluator engineering from becoming the paper while preserving defensible behavioral claims.

## 7. Explicitly removed from the core paper

The following are moved to appendix, exploratory analysis, or future work:

- a fully autonomous production evaluator panel;
- a six-family, three-regime minimum requirement;
- wavelet search as a contribution;
- a new attack generator;
- universal claims over all jailbreak types;
- exact all-token power-set enumeration for long optimized suffixes;
- mandatory keep-only sufficiency for every instance;
- AgentHarm as a main empirical route;
- evaluator qualification results as a headline contribution.

## 8. Development micro-pilot gate

The development micro-pilot uses h4rm3l and GCG on one target model.

A stable pair requires:

- direct harmful request is non-harmful under the frozen seeds;
- attacked prompt yields substantive harmful assistance under the frozen seeds;
- explicit harmful payload occurs exactly once and is byte-identical;
- no decision-relevant truncation or capability collapse;
- automatic screen is either unanimous or escalated to audit.

For each stable pair, freeze at most six coarse attack-added units and enumerate every subset under two neutralizers and three seeds.

### GO

Proceed to the four-family, two-model confirmation only if all hold:

- at least six stable pairs total;
- at least two stable pairs from each development family;
- at least three instances have a robust minimal recovery set;
- at least two instances exhibit either a non-singleton minimal set or multiple distinct minimal sets;
- neutralizer agreement is at least 0.80 on reportable topology;
- capability-confounded recovery is below 0.25.

### NARROW

Narrow honestly to one attack family or one structural class if only that class yields stable, nontrivial topology.

### STOP

Stop the main-paper route if:

- fewer than four stable pairs exist;
- all reportable cases are obvious singletons or indivisible whole-suffix effects;
- topology is unstable across neutralizers or seeds;
- capability confounds dominate;
- the human audit cannot reach acceptable agreement.

## 9. Paper-strength threshold

A strong paper requires more than examples. At least one repeated empirical finding must hold, such as:

- singleton attribution misses a meaningful fraction of robust non-singleton recovery sets;
- multiple minimal pathways recur across families or models;
- optimized and semantic attacks exhibit systematically different topology distributions;
- diverse surface attacks share an unexpectedly sparse recovery bottleneck;
- intervention topology is family-specific but reproducible and more informative than saliency.

If none appears in the development micro-pilot, additional evaluator or search engineering is not justified.

## 10. Immediate execution order

1. freeze this narrowed scope and the micro-pilot contract;
2. freeze the hybrid outcome/audit protocol;
3. run the h4rm3l/GCG stable-pair signal screen;
4. audit screen-positive pairs without opening held-out data;
5. enumerate coarse subsets for qualified pairs;
6. apply GO/NARROW/STOP;
7. only after GO, add DeepInception, AutoDAN, a second model family, and fresh paper-valid payloads;
8. add token refinement and search baselines only after exact coarse topology exists.

## 11. Current objective judgment

The project is worth continuing, but only under this narrowed gate.

- The formal research question is independently publishable.
- The current full S/F/U-plus-evaluator-plus-search plan is too broad.
- The paper has no core empirical result yet.
- One small, decisive topology micro-pilot should now determine whether further investment is rational.
