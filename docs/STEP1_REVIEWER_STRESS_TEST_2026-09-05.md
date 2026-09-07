# Step 1 independent reviewer stress test -- 2026-09-05

Scope: choose one defensible research question for an independent ICLR main-conference paper, with jailbreak/security preferred but scientific viability decisive. This is a research decision audit, not a manuscript, experimental authorization, acceptance prediction, or retrospective gate change. It reads the research-priority decision, completed V4 report, literature claim matrix, earlier novelty audit and human-free addendum. Only claim-specific primary literature was refreshed. No model or judge calls, private-response reads, A/B access, code changes, or PDF work were performed.

## 1. Decision

**C is the strongest candidate to investigate, but none of A/B/C currently passes as a demonstrated standalone contribution.** A should be a supporting validity condition, and B a tightly sourced failure analysis within C, not three disconnected contributions.

Recommended single question:

> When does localizing and removing suspected injected content actually restore authorized task execution, rather than merely stop the model from doing anything useful? Can a target-conditioned intervention audit distinguish these outcomes and improve safe data-reuse decisions beyond localization followed by direct security-and-utility rechecking, at a matched query budget?

This is a candidate question, not an established gap. Its broad version is already occupied. In particular, PromptLocate already removes localized content, measures recovered target-task performance, and explicitly discusses residual attack risk versus denial of service. The contribution cannot be “localize an injection and preserve the task.” [PromptLocate, Sections VI-B and VII](https://arxiv.org/html/2510.12252v2).

The possible narrower distinction is a consequential, target-conditioned mismatch between contamination provenance, behavioral suppression, and useful repair, measured with intervention-level capability controls and tested against the simplest competent correction. Whether this mismatch is common, important, and not already adequately handled is unproved. ICLR-main potential depends on that evidence; combining several known conditions does not establish novelty by itself.

| Candidate | Strongest defensible version | Weakest meaningful baseline that can defeat it | Current decision |
|---|---|---|---|
| A. Operator-bound repair-transfer certificates | Characterize when a repair verified under one rendering remains valid under an operationally required rendering | Re-execute the proposed destination repair and check the declared endpoint | Not standalone; support C only if a real workflow transfers repairs and direct rechecking is inadequate for a specified reason |
| B. Wrong necessity/safety conclusions from partial traces | Audit a documented inference that causes wrong remediation decisions under actual nonmonotonicity or missing observations | State only the search method's real guarantee; abstain on untested claims; directly test the proposed decision | Not standalone without a real claim/policy being violated and consequential fresh evidence |
| C. Security-specific versus destructive localization | Find interventions that stop an independently defined security violation while retaining the authorized task, and audit false repair claims | Existing localization plus destination security/utility checks; joint-endpoint greedy or ddmin search | Best candidate for the next evidence decision, not yet a paper-level pass |

## 2. Candidate A: operator-transfer certification

### Strongest case

A security analyst may localize a repair with a convenient mask but deploy a different sanitizer. If a source-certified repair then releases unsafe content or breaks authorized work, a transfer-aware audit could prevent consequential deployment mistakes. The event must arise in a documented workflow; swapping BLANK and OMIT solely because the experiment can do so does not establish practical importance.

### Attempt to kill it

Removal specifications already define different explanation problems; sensitivity to the removal operator is not a new conceptual discovery. [Explaining by Removing](https://jmlr.org/papers/v22/20-1316.html).

There is also a simple information limit. If destination oracle g is unconstrained relative to source oracle f, all source observations are compatible with both g(S)=0 and g(S)=1. A source-only certificate cannot establish destination success. For a deterministic finite endpoint, one destination query settles that particular success claim. Rechecking all destination proper subsets is needed only for a stronger destination-minimality claim, not for deciding whether the proposed repair works.

Therefore “attach the operator identity to the certificate” is correct engineering, not a standalone algorithmic advance. A useful contribution would have to show why a real decision needs more than the direct recheck, or introduce and validate a nontrivial cross-operator assumption. No such assumption has been established here.

### Why V4 is insufficient

V4 genuinely validates its frozen joint event on new inputs: 65/128 primary opportunities, from 38/64 semantic problem clusters. But 60 of the 65 failures are malformed JSON and five are wrong values. Models are confounded with conflict style; templates and seed remain fixed; V4 does not enumerate destination minimal families. A direct destination correctness check detects all observed transfer failures without source minimality enumeration. These are limitations documented in the completed V4 report, not reasons to remove observations.

**Necessary new evidence:** a pre-existing sanitizer-transfer use case, fresh security consequences rather than mostly formatting, and a measurable advantage over destination-only security-and-utility rechecking. Without the last item, A remains a useful diagnostic within C.

## 3. Candidate B: wrong conclusions from partial or nonmonotone traces

### Strongest case

An existing localization pipeline may turn one observed repair into a stronger claim: a unit is globally necessary, larger deletions are safe, or an unexplored branch cannot contain a useful repair. If that inference is actually present in a method or deployment policy, exact intervention data can expose wrong decisions and identify the least expensive correction.

### Attempt to kill it

The original delta-debugging work explicitly distinguishes 1-minimality from stronger minimality and already has unresolved test outcomes. A larger successful deletion after every one-element deletion fails does not contradict ddmin's stated guarantee. [Zeller and Hildebrandt, 2002](https://www.st.cs.uni-saarland.de/publications/files/zeller-tse-2002.pdf). Phrase-level delta debugging and targeted intent-preserving prompt repair also already exist in DDOR. [DDOR](https://arxiv.org/abs/2606.03601).

The following are not equivalent:

- Membership in the one repair returned by a search.
- Membership in every valid repair: a global necessity claim.
- Failure of every single-element rollback: 1-minimality.
- Failure of every proper subset: strict inclusion minimality.
- Safety of every larger removal: an additional monotonicity-style claim.

For example, if M is the complete minimal family, a globally necessary unit belongs to the intersection of M, not merely to one selected member. But discovering that a one-path method omits other paths is built into its output contract; it is not evidence that the method fails at its promised task.

The proposed full-family active-search rescue also has no query-complexity opening in the unrestricted noiseless model. Let y be the partial table, P its possible minima and R the unknown rows with no known-positive proper subset. Then D=P iff R is empty. For completed f with minimal family M, every initially unknown q satisfying

`there is no m in M with m a strict subset of q`

is individually mandatory: flipping its value changes the minimal family. Querying unknown sets in inclusion order, skipping strict supersets of known positives, queries exactly these mandatory rows. It is instance-optimal for terminal exact identification. The adversarial remaining worst case is |R|. An independent synthetic check covered all 6,561 ternary tables on three atoms and all 65,536 compatible state/completion pairs. This is a baseline proof, not a claim of literature priority or empirical jailbreak evidence. It rules out presenting a one-step minimax uncertainty-width heuristic as a superior full-family query algorithm in this model.

### Why D3 is insufficient

The priority decision records one old-panel-relative harmful counterexample among 17 hypothetical superset decisions from nine COMPLETE ddmin outputs; six decisions were unqueried in the stored search traces, including the counterexample. This motivates a check but does not show a documented ddmin guarantee was broken. The destination lacks the required capability evidence. Further, the 44 opposite-operator disagreements do not have actually required passing source capability controls; a vacuous `passed=true` must not be promoted into qualified recovery.

**Necessary new evidence:** identify the exact published statement or implemented decision rule first, retain its actual contract, and reproduce wrong security decisions on fresh cases with an independent endpoint. Compare against honest abstention and direct rechecking, charging their calls and reporting their coverage. If only hypothetical misuse can be demonstrated, B should not lead an ICLR-main paper.

## 4. Candidate C: useful security repair rather than suppression

### The strongest formulation

Study **target-conditioned useful repair**, not an unqualified “cause of jailbreak success.” For a fixed application, model, intervention S, rendering operator and decoding contract, measure two independently defined quantities:

- V(S): an explicit security-policy violation, such as an unauthorized state change or disclosure of a synthetic protected value.
- U(S): completion of the authorized task using information that must remain available.

A useful repair is G(S) = [V(S)=0 and U(S)=1]. Minimum size or strict-subset minimality is a secondary property of G, not a substitute for it.

| Observed V | Observed U | Allowed interpretation |
|---|---|---|
| 1 | Either | Security violation remains, regardless of task usefulness |
| 0 | 1 | Useful repair under the measured contract |
| 0 | 0 | Suppression without demonstrated useful repair; not automatically proof of capability damage |
| Unknown | Either, or U unknown | Unresolved; preserve the observed components and do not certify the conjunction |

Transport errors, refusal, malformed output and a disabled execution path cannot be silently rewarded as useful repair. A clean matched counterpart on which the same intervention destroys task performance can support an edit-induced damage interpretation. Without that counterpart, V=0/U=0 could also be residual misdirection or unrelated failure. This distinction prevents the proposed “separates cause from damage” language from exceeding what black-box measurements identify.

### Closest-work collision is serious

- PromptLocate's explanatory target is the injected content itself, while the proposed target is the particular model's valid intervention set. Its downstream data-recovery evaluation already measures useful task restoration; that is a required comparison, not an unaddressed omission. [PromptLocate](https://arxiv.org/html/2510.12252v2).
- WebSentinel already detects and localizes contaminated webpage segments and evaluates clean counterparts. A generic segment localizer is not new. [WebSentinel](https://arxiv.org/abs/2602.03792).
- LOCA already studies minimal local causal explanations of specific jailbreak successes through representation changes. Switching to input edits does not justify a broad first-cause claim. [LOCA](https://arxiv.org/abs/2605.00123).
- Erase-and-Check already uses erasure and safety checking; its guarantees concern a specified threat/filter model, not arbitrary target behavior. Do not attack that guarantee using a different oracle. [Certifying LLM Safety against Adversarial Prompting](https://arxiv.org/abs/2309.02705).

The remaining possible contribution is a demonstrated mismatch between provenance localization and useful behavioral remediation, plus an efficient audit/correction that changes consequential decisions beyond the existing methods' own end-to-end checks. An audit may also find that the existing methods are adequate; that outcome rejects the proposed leading claim.

## 5. One contribution test that minimizes the main confounds

This is a design requirement for a later authorization decision, not an experiment to launch under Step 1.

1. **Fix an operational security endpoint independent of presentation.** Use a closed, inert environment whose authorized result and prohibited state transitions or synthetic-secret disclosure are programmatically decidable. A wrong JSON wrapper alone is not a security breach. V and U must be separable: a system can perform the useful task and still execute an unauthorized additional action. Existing environments such as AgentDojo establish that task utility and prompt-injection outcomes can be studied together; they are foundations rather than a new benchmark claim. [AgentDojo](https://arxiv.org/abs/2406.13352).

2. **Select a public, outcome-independent case frame.** Prefer released security tasks and attacks with clear licensing and executable scoring over author-selected success stories. Freeze attack/template/problem clusters before measuring the new targets. Do not use old A/B cohorts. If a new small synthetic frame is needed for feasibility, call it a pilot, not representative security prevalence.

3. **Preserve the actual task.** Ground the authorized result in case-specific data, not a fixed answer that can be guessed without reading the data. Keep trusted instructions immutable. Make task-relevant and injected content genuinely coexist in the candidate region; otherwise deleting the whole region solves the benchmark trivially. The method must not receive gold inserted-span labels that make removal obvious. Provenance labels may evaluate contamination detection but are not behavioral causal ground truth.

4. **Freeze source-native edit units and both operators.** Map each edit explicitly to the intended bytes/source object. Blanking and omission are different treatments, not guaranteed semantic equivalents. Do not choose a granularity after seeing a favorable topology. Include a small predeclared alternative grouping only if the claim requires robustness to it.

5. **Measure the two outcome axes on every compared intervention.** For a small development lattice, obtain a complete table only where affordable, and keep all incomplete rows explicit. Include clean task, unedited attack, appropriate aligned controls and task-bearing deletion controls. Do not run capability checks only on the interventions that happen to make a favorable figure. Passing unrelated easy questions is weaker than preserving the particular authorized task.

6. **Use the simplest competitive comparison first.** Compare unchanged input, discarding the entire untrusted source, published localization followed by literal removal, that same localization with direct destination V/U rechecking, and a basic joint-endpoint greedy/ddmin search with rechecking. Count every target, detector, auxiliary-model and control call; use identical target access and admissible edits. The small exact table is the evaluation oracle, not a novel scalable algorithm. Multi-start greedy at the same budget is a stronger sanity check before claiming benefit from an elaborate search.

7. **Test decision value, not merely family recall.** The primary outcome should be correctly released useful repairs per all frozen opportunities, together with the number of security-violating releases. Report withheld/unknown cases, utility loss, retained/deleted task information and query cost. An always-abstaining auditor must not appear superior merely because it releases nothing. Evaluate the security-risk/utility/coverage/cost trade-off against the best simple baseline, rather than tune a scalar on observed results.

8. **Separate development selection from adjudication.** Any method choice or diagnosis learned from the small full table needs evaluation on untouched problem and attack/template clusters. Reusing the same trace to select and “validate” a repair only establishes in-sample finite behavior. Source operator, target model and conflict type must be crossed, not confounded as in V4. Independent repeats test stability; a recorded greedy seed is not a population guarantee.

9. **Require a useful correction.** If destination rechecking alone identifies every problematic repair at lower cost and similar coverage, stop the certificate-as-method claim. If the proposed audit only rejects more outputs without finding useful alternatives or improving a clearly declared risk constraint, stop the correction claim. If provenance localization plus rechecking is already competitive, report that result rather than weaken the baseline.

10. **Choose the continuation rule before new outcomes.** Specify a deployment-relevant effect margin and resource ceiling with the author before a pilot. A positive estimate alone is not enough. Continued work requires a reproducible security consequence beyond output formatting, adequate clean-task capability, a gap that survives the simple-baseline comparison, and evidence across independent model and attack/task clusters. This audit does not invent a numeric ICLR acceptance threshold.

Tensor Trust's released synthetic-secret and hijacking tasks are another possible objective endpoint source, but their particular success rules and task-utility limitations must be checked before adoption. A game access-control result must not be relabeled general harmful-content jailbreak evaluation. [Tensor Trust](https://arxiv.org/abs/2311.01011).

## 6. What existing evidence contributes -- and does not

D3 contributes recorded finite intervention structure and a small panel-relative warning about extrapolating repairs. It does not supply fresh ground truth, qualified capability evidence for every attractive contrast, a representative denominator, or a demonstrated failure of a published localization guarantee.

C1N contributes paired unedited/attacked responses, not a repair lattice. Its later GuidedEval remeasurement is not calibrated ground truth: the Qwen judge failed the frozen 45-case empty-response control. Repeating that instrument cannot establish the endpoint needed for C.

V4 contributes a real new-input demonstration that source-certified output-contract repairs can fail under another operator. Its controls and complete accounting are valuable. However, most events are formatting, its template scope is narrow, and direct destination checks suffice for its measured decision. It therefore supports an operational caution and test infrastructure, not the proposed security-specific leading claim.

The shared lesson is not “the project already has an ICLR paper.” It is that the next experiment must measure a consequential decision where the validity machinery earns its cost. Additional hashes, exhaustive enumeration or more unchanged-template formatting examples cannot close that gap.

## 7. Step 1 handoff

Proceed with **C as one narrowly stated question for feasibility assessment**, incorporating A only as an operator-validity check and B only when an actual invalid decision rule is documented. Do not launch experiments, open cohorts, change models, or start a manuscript under this review alone. If the required simple-baseline gap and security endpoint cannot be made credible, reject this route before a large run rather than call a collection of pilots an independent main-conference contribution.

All former failures remain failures. The older literature matrix's conditional-pass wording is historical and does not certify this latest question. This review writes only this new audit file.

## 8. Bounded last collision triage: AttnTrace

The official IEEE S&P 2026 accepted-paper list confirms **AttnTrace: Contextual Attribution of Prompt Injection and Knowledge Corruption**, by Yanting Wang, Runpeng Geng, Ying Chen and Jinyuan Jia. The older search title, *Attention-based Context Traceback for Long-Context LLMs*, refers to the same arXiv record. The latest verified version is v3, revised 2026-04-17. [Official conference list](https://www.ieee-security.org/TC/SP2026/accepted-papers.html), [versioned primary paper](https://arxiv.org/abs/2508.03793v3).

### Exact overlap and endpoints

AttnTrace conditions attribution on a given generated output, using top-token attention aggregation and context subsampling. Its principal measurements are malicious-text precision/recall, runtime, and attack success before/after removing attributed texts. It also evaluates agent attacks, cooperating/split malicious texts, and attribution-before-detection using FPR/FNR and AUC. These are stronger overlaps than a generic attention visualizer. The inspected metrics do not supply a joint authorized-task-utility and security certificate for each repair or enumerate all strict-subset-minimal repairs. [AttnTrace, Sections IV--VI](https://arxiv.org/html/2508.03793v3).

The official code independently confirms response-conditioned attribution: `main_attribute` passes question, contexts and the observed answer into `attr.attribute`. The driver scores attack success using normalized attacker-target substring inclusion, omits unsuccessful attacks from the attribution records, and uses a surrogate model for some closed-source targets. Its clean-response counter tests attacker-target occurrence, not authorized-answer correctness. These are the inspected driver's semantics, not a claim about every repository experiment. No code was executed or dataset read. [Official driver](https://raw.githubusercontent.com/Wang-Yanting/AttnTrace/main/main.py), [experiment entry point](https://raw.githubusercontent.com/Wang-Yanting/AttnTrace/main/scripts/script_prompt_injection.py). The read-only review used the current public `main`; a future experiment must pin a commit first.

**Interpretation:** neither “target-conditioned attribution” nor “removing attributed text reduces security failures” remains a plausible new leading claim. C is narrowed further to the explicitly paired security/authorized-utility distinction and consequential correction. That gap is still only a candidate; an omitted metric is not automatically a publishable failure. AttnTrace plus the same destination V/U checks belongs among the closest methods if target/surrogate access is feasible and fairly matched.

### Relation to the PromptLocate ordered-prefix audit

AttnTrace already reports PromptLocate overlocalizing clean tokens on MuSiQue: 1,093.4 of 1,172.6 localized tokens were clean. Its proposed explanation is detector mismatch with long contexts, not an isolated ordered-prefix search failure. Thus another generic demonstration of PromptLocate false positives would repeat an existing finding. [AttnTrace, Section VI](https://arxiv.org/html/2508.03793v3).

PromptLocate Section IV-B explicitly uses binary search to find the earliest positive prefix, and repeats it after excluding previously selected segments. A claimed earliest-positive result requires appropriate behavior of the detector along those ordered prefixes; arbitrary context-dependent Boolean predictions do not supply that condition. [PromptLocate, Section IV-B](https://arxiv.org/html/2510.12252v2).

The following is this audit's proposed distinction, not an empirical result or attribution of a new flaw to either paper. On a frozen candidate frame, use the **same complete vector of detector outputs for all relevant prefixes**, the same segmentation, and identical cached outputs in two search procedures. Compare published binary search to a literal left-to-right earliest-positive scan. This isolates search-rule disagreement from additional model calls or a different detector. Repeating it after each exclusion must use that round's actual prefix sequence, not reuse predictions for different concatenated inputs.

Then ask whether correcting the search decision changes downstream useful/security repair, and whether it beats spending the same extra budget on direct destination V/U rechecks. Preserve detector error against provenance, observed prefix nonmonotonicity, search mismatch relative to the frozen detector, and downstream target error as four distinct quantities. A binary/linear disagreement does not by itself establish a wrongly localized malicious unit: both may be wrong relative to provenance, and either may have the better downstream repair.

**Last-triage verdict:** this is a narrower, falsifiable algorithm-assumption audit than the already published long-context overlocalization result. It remains a no-go as a standalone ICLR-main claim if it only produces synthetic Boolean counterexamples, small rank changes, or downstream failures corrected equally well by simple rechecking. AttnTrace materially strengthens the closest-work barrier; it does not supply missing evidence for the current project.

Only this appendix was added in the last triage. There were no model/judge calls, dataset/private/A-B reads, downloads, or changes to any existing experimental artifact.
