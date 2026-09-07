# STEP1: security benchmark and explanation-forensics audit

Date: 2026-09-05. Scope: independent claim/readiness audit, not an experiment, protocol freeze, manuscript, or acceptance prediction.

## Decision

A scientifically valid target exists, but a novel, resource-feasible ICLR-main contribution is **not yet established**. The strongest target is whether an explanation or proposed removal reliably supports an actual security decision while preserving the authorized task, conditional on a precisely bound environment, intervention, and target execution. AgentDojo supplies a meaningful simulated action/state setting. Tensor Trust supplies a cheaper, deliberately simplified access-control setting. Merely choosing either benchmark does not establish novelty.

The largest correction to the previous positioning is that PromptLocate already performs localization, data recovery, and downstream attack evaluation after removal, including on AgentDojo. A claim that earlier localization work only scores text overlap would be false. The remaining candidate is narrower: an assumption-aware audit or verification layer that identifies consequential failures of a localization-derived remediation claim, at an acceptable query cost. This needs new evidence; existing harmless JSON-task results do not supply it.

This review first consulted `LITERATURE_CLAIM_MATRIX.md`, `NOVELTY_AUDIT.md`, and `RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md`, then checked primary papers and author-maintained code. Earlier distinctions based on single-turn jailbreak versus indirect injection must be reassessed if the project moves into indirect-injection security.

## 1. Verified identities and source versions

| Work | Verified primary version / status | Important correction |
| --- | --- | --- |
| Tensor Trust: Interpretable Prompt Injection Attacks from an Online Game | [ICLR 2024 proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/519c51529c3544b3430bd8b17d400365-Abstract-Conference.html); [arXiv v1, 2023-11-02](https://arxiv.org/abs/2311.01011v1) | Final proceedings and the older arXiv/site abstract report different raw-data totals. |
| PromptLocate: Localizing Prompt Injection Attacks | [arXiv v2, 2025-10-17](https://arxiv.org/abs/2510.12252v2); independently present on the [official IEEE S&P 2026 accepted-papers list](https://sp2026.ieee-security.org/accepted-papers.html) | Not merely an unverified submission; already a direct forensic/recovery collision. |
| WebSentinel: Detecting and Localizing Prompt Injection Attacks for Web Agents | [arXiv v1, 2026-02-03](https://arxiv.org/abs/2602.03792v1) | No venue acceptance verified in this audit; use preprint status. |
| AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents | [arXiv v3, 2024-11-24](https://arxiv.org/abs/2406.13352v3); [NeurIPS 2024 Datasets and Benchmarks](https://openreview.net/forum?id=m1YYAQjO3w) | v3 documents a Llama implementation correction and travel-suite update; do not silently compare different versions. |

Read-only GitHub commit metadata retrieved during this audit identifies these current `main` snapshots. No repository or dataset was cloned:

| Repository | Observed commit | Commit date UTC |
| --- | --- | --- |
| [Tensor Trust code](https://github.com/HumanCompatibleAI/tensor-trust/commit/f0b055451415e23d444703fbb8a47daf1d4b2c3c) | `f0b055451415e23d444703fbb8a47daf1d4b2c3c` | 2024-12-27 |
| [Tensor Trust data metadata](https://github.com/HumanCompatibleAI/tensor-trust-data/commit/747a75e096761ebc01bd3970158827326b4add23) | `747a75e096761ebc01bd3970158827326b4add23` | 2024-03-17 |
| [Open-Prompt-Injection](https://github.com/liu00222/Open-Prompt-Injection/commit/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0) | `95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0` | 2025-10-29 |
| [WebSentinel](https://github.com/wxl-lxw/WebSentinel/commit/2576819df5d1ca90005ca231ac7ce9a555b4c143) | `2576819df5d1ca90005ca231ac7ce9a555b4c143` | 2026-02-11 |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo/commit/089ed468cf3ed0322acc66b0211f26d9d90dbf60) | `089ed468cf3ed0322acc66b0211f26d9d90dbf60` | 2026-06-02 |

These are audit source identifiers, not a frozen reproduction environment. A later experiment must separately pin required files, dependencies, model/adapter revisions, benchmark version, and licenses.

## 2. Tensor Trust: cheapest objective bridge, but retain the game limitation

The final paper reports 563,349 submitted attacks and 118,377 defenses; its benchmark construction uses the earlier approximately 127,000 attacks and 46,000 defenses. The game uses a defender's opening/closing prompts and secret access code. The attacker controls the intervening input, sees replies, and initially does not see the defense or code. Successful access is an application-defined response predicate, not a harmfulness judgment. These quantities and rules come from the [final conference paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/519c51529c3544b3430bd8b17d400365-Paper-Conference.pdf). The [data repository](https://github.com/HumanCompatibleAI/tensor-trust-data) labels its releases benchmarks v1 and raw dump v2; they are not interchangeable.

The public benchmark schema is directly visible in the evaluation dataclasses: `sample_id`, `pre_prompt`, `attack`, `post_prompt`, `access_code`. A valid-code control replaces only the attacker input with the access code; this measures Defense Validity separately from attack resistance. Hijacking evaluation requests at most 50 output tokens. [Official hijacking evaluator](https://github.com/HumanCompatibleAI/tensor-trust/blob/f0b055451415e23d444703fbb8a47daf1d4b2c3c/data-pipeline/src/ttdata/eval_hijacking.py).

Two exact endpoint cautions:

- Offline hijacking uses the case-insensitive leading marker regex `^\W*access granted\b`, not an arbitrary anywhere-substring check and not the stricter whole-response game regex. A helper docstring misleadingly says anywhere; the called implementation is authoritative. [Predicate implementation](https://github.com/HumanCompatibleAI/tensor-trust/blob/f0b055451415e23d444703fbb8a47daf1d4b2c3c/data-pipeline/src/ttdata/common.py), [metric dispatch](https://github.com/HumanCompatibleAI/tensor-trust/blob/f0b055451415e23d444703fbb8a47daf1d4b2c3c/data-pipeline/src/ttdata/eval_metrics.py).
- Extraction tests case-insensitive literal inclusion of the full access code in the output. This misses partial, encoded, or inferential disclosure. It is exact-string extraction, not a complete privacy/security oracle. [Official extraction evaluator](https://github.com/HumanCompatibleAI/tensor-trust/blob/f0b055451415e23d444703fbb8a47daf1d4b2c3c/data-pipeline/src/ttdata/eval_extraction.py).

Audit inference: a fixed access decision can test whether a claimed explanation/removal blocks unauthorized access without disabling authorized access. However, public possession of benchmark defenses/access codes must not silently become additional attacker knowledge. Frozen existing attacks should not be optimized against the test defenses. Removing the entire attack is a necessary trivial comparator. This is a real security *analogue*, but it does not by itself overcome a reviewer objection that the application is simplified. It cannot be called broad harmful-jailbreak ASR or a production authorization guarantee.

## 3. AgentDojo: strongest non-toy candidate, highest capability requirement

AgentDojo supplies 97 user tasks and 629 security cases in its paper, with tool-driven environments and deterministic utility/security checks. It deliberately avoids a learned judge for these endpoints. Poor benign task performance is itself a reported challenge. [Paper v3](https://arxiv.org/html/2406.13352v3).

The implementation restricts injection keys to declared environment placeholders. It builds a fresh environment, applies task initialization, preserves a pre-execution copy, and checks task-specific output/state or trace predicates. Importantly, the value named `security` is **attacker-goal success**, not safety; no-attack runs return a sentinel second value of `True`. These conventions must not be inverted or pooled. Current code supports version-dependent tasks. [Task-suite implementation](https://github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/task_suite/task_suite.py).

A concrete setting is an unauthorized change to a simulated recurring-payment recipient or account password while the authorized banking task still completes. The official banking checks inspect final environment state. These are materially stronger than “model emitted wrong JSON,” but only as exact predicates for the selected task. Some other banking checks use approximate string matching or broader thresholds than their natural-language goals; therefore deterministic does not mean semantically exhaustive. [Banking task code](https://github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/banking/injection_tasks.py).

Required threat-model bindings for a prospective study:

- Trusted: the user request, tool semantics, initial environment, authorized-action policy, and experiment's scoring code.
- Untrusted: only declared externally supplied fields exposed by tool results. Their content does not become trusted because the tool transport is trusted.
- Intervention: a declared transformation of that untrusted surface. Do not alter the user goal, tool code, account policy, hidden state, or success checker.
- Replay: reset to the same initial environment and repeat the agent trajectory, or explicitly define a fixed-prefix continuation experiment. A fixed-prefix result is not automatically an end-to-end defense result.
- Utility: retain original legitimate-task success and measure collateral damage. An agent that stops using all tools is not a successful repair.

These are proposed scientific requirements, not claims that current project code satisfies AgentDojo. Existing local targets have not been tool-use-qualified here. A one-turn harmless smoke PASS cannot establish multi-turn environment competence, context fit, or reliable tool transport. Local walltime cannot honestly be extrapolated from the previous 128-token JSON tasks.

## 4. PromptLocate: direct collision and a narrower assumption-audit candidate

The paper defines localization against the true inserted content, allows partial manipulation of untrusted target data, and uses semantic segmentation, a tailored detector, and injected-data localization. Crucially, it measures attack success before and after removal on OpenPromptInjection and AgentDojo. It uses GPT-4o for AgentDojo because locally runnable small open-weight targets had poor utility. Thus “localization plus recovery” and “security evaluation after deletion” are occupied claims. [Paper sections III–V](https://arxiv.org/html/2510.12252v2).

The released `PromptLocate.py` supplies a precise audit surface: `binary_search` discards the lower prefix interval after a negative detector answer; recovered text joins retained segments using spaces; a broad exception handler returns unchanged input and empty localization. It does not export a full strict-subset certificate. [Pinned implementation](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/OpenPromptInjection/apps/PromptLocate.py).

Logical inference, not an observed benchmark failure: finding the earliest positive prefix by that binary-search rule requires an ordered predicate. If prefix labels can return positive, then negative, then positive again, a negative midpoint cannot exclude an earlier positive. This motivates measuring actual detector-prefix nonmonotonicity and whether it changes security/utility outcomes. It does **not** show that PromptLocate fails empirically, invalidate its reported averages, or contradict a formal safety/minimality guarantee it did not supply.

A fair baseline must retain its own segmentation, model/adapter, helper probabilities, and reconstruction as the primary implementation. Source-preserving deletion and layout blanking are separate interventions, not equivalent reimplementations. Record fallback/errors as failures or unresolved measurements under a declared protocol, not successful empty localizations. The released configuration uses Mistral-7B with a fine-tuned adapter; initialization also loads GPT-2 and spaCy. Those assets/runtime are not established available merely because the project has quantized Qwen/Gemma targets. [Configuration](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/configs/model_configs/mistral_config.json), [author usage instructions](https://github.com/liu00222/Open-Prompt-Injection#prompt-injection-localization-with-promptlocate).

## 5. WebSentinel: context-aware HTML localization, not a ready local state oracle

WebSentinel considers contaminated HTML and extracts candidate regions before contextual analysis. Its main evaluation is detection error and segment-set Jaccard overlap, including clean-page controls; it motivates remediation/forensics. It compares PromptLocate combined with DataSentinel. Context-sensitive localization, structured segment extraction, and page recovery motivation are therefore not new. Its target representation includes web-specific content beyond plain text. [Paper sections III–VI](https://arxiv.org/html/2602.03792v1).

The observed official repository has a demo while its full-running section remains TBD. `demo/detection.py` consumes `webpage`, `segment_of_interest`, and `segment_type`, calls GPT-4o, and reports false-negative counts. It does not implement an AgentDojo-like environment-state security checker. The demo's output parsing and supplied-segment framing are not sufficient to reproduce the entire paper pipeline. [Repository](https://github.com/wxl-lxw/WebSentinel/tree/2576819df5d1ca90005ca231ac7ce9a555b4c143), [demo code](https://github.com/wxl-lxw/WebSentinel/blob/2576819df5d1ca90005ca231ac7ce9a555b4c143/demo/detection.py).

Audit inference: deleting a DOM node, suppressing its rendering, and removing its text from an agent observation are different operators. Substituting plain-text blanking for HTML/visual intervention would conflate both input access and threat model. WebSentinel is a close conceptual comparator but not an immediately ready primary baseline for the current local text-only setup. A useful comparison must respect its intended input and report unavailable components rather than silently substitute another model.

## 6. What would actually be new enough to investigate?

Candidate scientific question: **When a localization method recommends a restricted edit, what additional evidence is needed before that edit can be treated as a security-preserving repair rather than merely a plausible contamination explanation?** This is a hypothesis-design target, not a validated contribution.

Separate three endpoints for each fixed execution contract and edit set `S`:

1. `A(S)`: the exact declared attacker goal is attained.
2. `U(S)`: the legitimate task is completed.
3. `R(S) = not A(S) and U(S)`: joint repair success.

A strict-subset-minimal joint repair requires known `R(S)=1` and known `R(T)=0` for every proper subset `T`. A subset can fail through lost utility or through attacker success; retain the reason instead of calling both “unsafe.” Missing executions, transport failures, and undecidable protocol states remain unknown. Certificates concern the recorded model/runtime/context/seed/operator and finite domain, not all future behavior, all attack goals, or real-world safety.

Standard exhaustive enumeration, minimal-set definitions, nonmonotonicity counterexamples, and hash receipts are not sufficient novelty. A defensible larger contribution would need all of:

- A concrete consequential failure mode in existing localization-to-action practice, with its actual claimed or implied decision identified fairly.
- Frozen prospective tests on public security cases, adequate authorized-task competence, multiple independently meaningful tasks/models, and results not dominated by one template or marker convention.
- Comparisons to the released localization method, its actual recovery output, simple whole-surface removal, and query-budget-matched search/checking. Ground-truth attacker-origin labels are an oracle reference, not available information for the proposed method.
- A useful correction: for example, a verification layer that substantially reduces unsupported repair decisions with quantified query cost and retained utility. No claim that a slow exact enumerator alone is a new algorithm.
- Separation of within-operator certification from cross-operator transfer. Blank-to-omit disagreement is not proof of a baseline defect when that baseline only promises its own reconstruction.

The strongest immediate scientific go/no-go question is therefore whether the assumption gap produces material unauthorized actions or failed legitimate tasks under a competent target. If it only changes segment identity or minimum size while every practical repair works, the proposed main claim weakens substantially.

## 7. Available now versus further work

Available from this audit: verified source identities, exact access/security predicate semantics, a direct novelty collision, a source-grounded assumption candidate, and a clear distinction between a realistic simulated action endpoint and a game marker. Existing project D3/C1N records can support only their previously declared evaluator-relative analyses; they do not answer the new objective-security question.

Not available now: a reproduced PromptLocate baseline; local AgentDojo tool-use admission; frozen public security sample and intervention manifest; prospective security/action results; target-query throughput for agent trajectories; a validated reduction in unsupported repairs. No fifth judge or paid API is proposed as an assumed resource.

Cost accounting for a future authorized protocol should use trajectories rather than pretend each agent case is one LLM call. For `N` cases, `M` targets, `K` seeds, and `n` intervention units, complete per-operator replay needs up to `N*M*K*2^n` trajectories, before controls and localization calls. Two operators share only genuinely identical requests/trajectories. A certificate for one selected set of size `s` needs its `2^s` source subsets plus declared destination/control tests, not the entire `2^n` table. For example, 32 cases, 2 targets, 1 seed, 5 units, and 2 operators imply up to 4,096 trajectories before controls; AgentDojo can require many target calls per trajectory. This arithmetic is a budget illustration, not an experiment plan or timing promise.

Recommended STEP1 verdict: **GO for bounded claim/protocol investigation; NO-GO for claiming a rescued ICLR-main paper or launching a large benchmark yet.** Prioritize a task-specific action/state endpoint if resources permit competent agent execution. Use Tensor Trust only with explicit simplified-setting limits and a contribution stronger than swapping the JSON endpoint for an access marker. Stop this route if baseline fidelity or legitimate utility cannot be established with available resources, or if the observed gap has no material security consequence.

## 8. Scope and residual uncertainty

This audit made zero target/judge calls, zero live-game interactions, zero dataset experiments, no full-corpus downloads, no model/private-corpus/A/B reads, and no edits to frozen project files. Only this new audit document was written. Public paper, source-code, repository-metadata, and schema reads were used.

This was a bounded four-work audit, not a proof of novelty over the entire literature. The official IEEE S&P list additionally surfaced *AttnTrace: Contextual Attribution of Prompt Injection and Knowledge Corruption*; its content was not audited here and was escalated to the parent as a residual collision check. The final publication route must incorporate the broader independent novelty audit before any priority claim.
