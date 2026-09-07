# Step 1: formal-explanation and certificate collision audit

Status: independent claim audit, not experimental authorization or paper readiness.
Source checks: 2026-09-05 UTC. Local snapshot hashes collected at approximately 12:22 UTC.
Authoring boundary: this new document only; no historical records, research code, frozen
configurations, results, manuscripts, or PDFs were edited. No model/judge calls, private
harmful-content reads, or Primary A / Reserve B accesses were made in this audit.

## Decision

The existing D3/V4 evidence does not presently support an independent ICLR-main contribution
based on the general claims that removal explanations depend on the removal rule, that one
minimal explanation is not all explanations, that nonmonotonicity invalidates upward
propagation, or that incomplete evidence should not be treated as a certificate.

The strongest direct collision is DDOR: its formal discussion already distinguishes a
selected 1-minimal refusal trigger from global minimality, all triggers, and a unique root
cause, and explicitly warns about nonmonotone interactions. Covert et al. defeat the broad
operator-dependence novelty claim; FAME and earlier formal explanation work defeat the broad
certification/minimality novelty claim. These are different collisions, not one universal
prior method solving our exact finite-table problem.

One candidate remains conditional: establish a practically consequential failure of an
actual explanation-to-security-decision workflow, and show a useful correction at matched
cost and utility against direct testing of the deployed intervention. A conjunction of
known ideas, without this demonstrated consequence and advantage, is insufficient.

## Starting records and evidence boundary

The following records were read before targeted primary-source checks. Their older
CONDITIONAL PASS language is historical and is not a current ICLR-main endorsement.

| Local record | SHA256 at this snapshot |
|---|---|
| `docs/RESCUE_RESEARCH_PRIORITY_DECISION_2026-09-05.md` | `3e941d89f38b54103fca0c8281861d3fc79e47487bf793040f10652a9e9c431b` |
| `docs/CLOSEST_WORK_AND_CONTRIBUTION_MATRIX_V2.md` | `42149490177848fc30aec750041306e3039b76dbef5f2b03c748b12880db06b7` |
| `docs/LITERATURE_CLAIM_MATRIX.md` | `df216d7aabcba87e69cce56c2d3d0a3f9a3ec0d05b00cc091136e2b601c259c0` |
| `docs/RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md` | `b79b2583e2c382cd89f24ae24dd236d5cfd42824cbaeba79c67929eebfe71447` |

The priority document is concurrently maintained; its hash identifies this audit's snapshot,
not a demand to revert subsequent changes.

## Distinguish the objects before comparing guarantees

Let U be a fixed atom set. For our finite intervention table, R_o(S) is the specified recovery
predicate after removing S with operator o, holding the task, model, decoding, finite seed
panel, scorer, and controls fixed. This is not a universal assertion over future responses.

| Object | Actual quantifier | What does not follow |
|---|---|---|
| 1-minimal positive set | R(S)=1 and every immediate proper subset is negative | Every proper subset is negative; S has minimum cardinality; every positive set contains each member of S |
| Strict subset-minimal positive set | R(S)=1 and every proper subset T of S is negative | All other minima have been found; positivity is upward closed; another operator agrees |
| All-minimum-family identification | Every subset-minimal positive set of the specified R is determined | Generalization to unseen tasks, seeds, renderers, or a different measurement oracle |
| Formal sufficient explanation | Fix selected feature values; every admissible completion of the other features satisfies the target property | Empirical erasure with one baseline has this universal-completion guarantee |

Here the first row assumes known binary negatives. A tri-state reducer's own treatment of
UNRESOLVED must be checked separately; the original ddmin guarantee must not silently be
rewritten as strict minimality. The foundational source is Zeller and Hildebrandt,
[*Simplifying and Isolating Failure-Inducing Input*, IEEE TSE 28(2), 2002](https://www.st.cs.uni-saarland.de/publications/files/zeller-tse-2002.pdf).

For arbitrary binary completions of a partial table, a set is necessarily minimal when it is
known positive and all its proper subsets are known negative. It is possibly minimal when
it is not known negative and no proper subset is known positive. These are sharp marginal
membership statements, not a claim that every individually possible minimum can occur
jointly in one completed family. Their use here is transparent bookkeeping; no priority or
ICLR-level theoretical novelty is asserted.

## Primary-source collisions

### 1. Removal specification: Covert, Lundberg, and Lee

Verified identity: *Explaining by Removing: A Unified Framework for Model Explanation*,
JMLR 22(209):1-90, 2021. The publisher explicitly organizes 26 methods by the removal
implementation, the model behavior being explained, and the influence summary. The latest
listed arXiv revision is v2, dated 2022-05-13; the journal publication remains 2021.
[Official JMLR record](https://www.jmlr.org/papers/v22/20-1316.html),
[author preprint record](https://arxiv.org/abs/2011.14878).

Collision: BLANK and OMIT define different intervention questions. Observing their disagreement
cannot itself establish a new general principle of explanation. Binding an artifact to the
operator is good engineering, but not a newly discovered conceptual requirement. Our exact
finite-cell audit could add application evidence; its significance must come from the
decisions affected and the correction's measured value.

### 2. DDOR: direct LLM localization, uncertainty of interpretation, and repair

Verified identity: *DDOR: Delta Debugging for Explainable Overrefusal Testing and Repair*,
Qinyan Zhou et al., arXiv:2606.03601v1, submitted 2026-06-02. No accepted venue was verified.
Section 3.1 defines a retained fragment S whose concatenation triggers refusal, while deleting
each individual member makes the binary refusal test pass. It explicitly limits the guarantee
to 1-minimality under its chosen granularity and reduction strategy. It does not promise all
triggers, global minimum size, or a unique root cause; it explicitly recognizes nonmonotone
interactions. Returning one trigger is intentional. Refusal detection is operationalized with
Qwen3Guard-Gen-0.6B and separately checked against human ratings. The method evaluates
trigger-guided repair, not only localization.
[Primary full text, especially Section 3.1](https://arxiv.org/html/2606.03601v1).

Collision: reversing the desired outcome from refusal to recovery does not by itself create a
new method. Our one-path/global-necessity counterexamples do not refute this paper's guarantee.
A useful challenge would have to concern its measured downstream use or a separately documented
consumer assumption, rather than substituting a stronger guarantee for the one it states.

### 3. DD-CAM: local necessity and 1-minimal explanations are explicit prior work

Verified identity: *DD-CAM: Minimal Sufficient Explanations for Vision Models Using Delta
Debugging*, Krishna Khadka et al., arXiv:2602.19274v1, submitted 2026-02-22; no accepted venue
was verified. It zero-masks representation units outside a selected set and preserves the
top-1 prediction. The formal discussion distinguishes 1-minimality from cardinality minimum,
defines necessity relative to the selected set, and allows multiple such explanations. Its
search configuration accounts for whether representation units interact.
[Primary full text, Sections 1, 4, and 5.2](https://arxiv.org/html/2602.19274v1).

Collision: black-box reduction, sparse explanations, and selected-set necessity are occupied
ideas. Our finite renderer domain differs from internal vision representations, but this
domain change alone does not establish substantial methodological novelty. Do not criticize
informal wording about small explanations while ignoring the explicit formal qualification.

### 4. FAME: sound sufficiency, incomplete abstraction, and exact refinement

Verified identity: *FAME: Formal Abstract Minimal Explanation for Neural Networks*, Ryma
Boumazouza et al. The official ICLR 2026 proceedings confirms publication; arXiv:2603.10661v1
was submitted 2026-03-11. Its sufficient explanations fix selected coordinates and quantify
over every remaining admissible input. Sound abstract interpretation certifies the target
property, while abstract minimality is weaker than exact minimality; exact refinement is
available. The arXiv discussion distinguishes soundness from completeness: failure to certify
need not establish a real counterexample. This latter detail is attributed to the arXiv
discussion/appendix, not assumed to appear identically in the shorter proceedings version.
[Official ICLR record](https://proceedings.iclr.cc/paper_files/paper/2026/hash/313c5f89162aeee02ea3b8e3cfdd0c6d-Abstract-Conference.html),
[primary arXiv text, Sections 2, 4, 6 and Appendix A.3](https://arxiv.org/html/2603.10661v1).

Collision: conservative certification, minimality qualification, and unresolved evidence are
not new. Conversely, FAME is not a turnkey algorithm for our arbitrary erasure table: fixing
more coordinates shrinks its quantified domain, whereas removing more text need not preserve
our response predicate. A receipt hash authenticates a finite observation; it does not confer
FAME's universal guarantee.

### 5. Earlier formal explanations and sufficient input subsets

Ignatiev, Narodytska, and Marques-Silva's *Abduction-Based Explanations for Machine Learning
Models*, AAAI 2019, already computes formally justified subset- and cardinality-minimal
explanations using decision oracles for model constraints.
[Official AAAI publication](https://ojs.aaai.org/index.php/AAAI/article/view/3964).
The later *On Relating 'Why?' and 'Why Not?' Explanations*, arXiv:2012.11067v1, establishes
minimal-hitting-set duality and algorithms for extracting and enumerating both explanation
families. The checked arXiv record dates to 2020-12-21; no venue inference is needed.
[Primary record](https://arxiv.org/abs/2012.11067).

Carter et al.'s *What made you do this? Understanding black-box decisions with sufficient
input subsets*, AISTATS 2019, obtains compact decision-preserving subsets by backward
selection with other inputs missing. This occupies model-agnostic minimal input-subset
explanations, without making its selected subsets a universal-completion proof.
[Official PMLR publication](https://proceedings.mlr.press/v89/carter19a.html).

Collision: neither formal minimality nor family enumeration can be introduced as new.
The standard formal-explanation duality should not be transferred without proof to an
arbitrary, potentially nonmonotone fixed-renderer recovery predicate. A different mathematical
object is a necessary clarification, not automatically a sufficiently important contribution.

### 6. Faithfulness and validity: erasure artifacts are not a fresh discovery

Feng et al., *Pathologies of Neural Models Make Interpretations Difficult*, EMNLP 2018,
show that iterative input reduction can leave nonsensical fragments on which models remain
confident; their human experiments establish that these remnants need not retain information
needed by people. Thus outcome-preserving deletion is not itself evidence of a meaningful
human explanation. [Primary ACL publication](https://aclanthology.org/D18-1407/).

Jacovi and Goldberg, *Towards Faithfully Interpretable NLP Systems: How Should We Define and
Evaluate Faithfulness?*, ACL 2020, explicitly separates evaluation criteria and assumptions
for faithfulness. It is an opinion/analysis paper, not a universal empirical impossibility
theorem. [Primary ACL publication](https://aclanthology.org/2020.acl-main.386/).

Collision: a generic warning about malformed remnants, human plausibility, or faithfulness
does not establish novelty. Our study has no new human explanation-validity experiment.
V4's strict output contract measures a different endpoint and cannot fill that gap.

### 7. Existing jailbreak-localization boundary: LOCA

Identity rechecked, without duplicating the parallel full-method audit: *Minimal, Local,
Causal Explanations for Jailbreak Success in Large Language Models*, Shubham Kumar and
Narendra Ahuja, arXiv:2605.00123v3, revised 2026-08-07. The author-maintained record states
COLM 2026 publication. It identifies small sets of interpretable internal representation
changes inducing refusal on successful jailbreaks, across Gemma, Llama, and Qwen.
[Primary versioned record](https://arxiv.org/abs/2605.00123v3).

Consequently, neither local causal jailbreak explanation nor minimal refusal-inducing
intervention is an unoccupied broad title. Input-level, operator-bound evidence remains a
different object; its advantage must be demonstrated rather than inferred from that difference.

## What D3 and V4 actually add

The source for the following established facts is the safe-record reconstruction summarized
in the [priority decision](RESCUE_RESEARCH_PRIORITY_DECISION_2026-09-05.md), the
[theory audit](RESCUE_THEORY_AND_NOVELTY_AUDIT_2026-09-05_V2.md), and the
[completed V4 report](RESCUE_V4_PROSPECTIVE_TRANSFER_RESULT_2026-09-05.md).
This literature pass does not pretend to execute a second fresh numerical reconstruction.

| Existing evidence | Supported addition | Unsupported promotion |
|---|---|---|
| D3: 12 instances / 9 payloads; 456 cells; 46 unresolved; 16 necessary versus 45 possible minima; 7 identified families | Exact, finite-panel-relative description of this intervention frame | General attack prevalence; universal model safety; new minimality theory |
| D3 adjacent merges: 4 contrasts, deduplicated to 3 atomic reversals across 2 payloads; all BLANK-only | Specific response-panel failures of a closure implication | Operator-invariant phenomenon; 4 independent replications; harmfulness stable across seeds |
| D3 stored ddmin: 9 COMPLETE, 2 UNCERTIFIED, 1 UNAVAILABLE | All 9 COMPLETE selected sets are strict minima in the current table | Failed ddmin minimality guarantees |
| Hypothetical upward propagation: 1 contradiction / 17 superset decisions; 1 / 6 unqueried in their stored traces | A concrete way an additional, unjustified consumer assumption can be wrong | Proof that an existing method actually makes that assumption |
| Hypothetical global necessity: 7 / 19 selected units have known contrary alternatives across 4 / 9 COMPLETE instances | Refutation of global-necessity overinterpretation | Refutation of selected-set necessity; dropping 3 non-COMPLETE instances from the fixed frame |
| V4: 65 / 128 primary opportunities, 64 fresh underlying problems, 38 / 64 affected clusters | Prospective recurrence of a source-certificate / target-correctness transfer error for the frozen harmless templates | 128 independent problems; actual harmful-jailbreak incidence |

The D3 source mask 77 -> destination 95 is the most concrete safety-propagation witness.
Source 77 has genuinely required passing capability controls and three safe observations per
operator. Destination 95 has one OMIT harmful observation at seed 47 and three BLANK safe
observations. Destination capability preservation was not tested. This is enough to contradict
the finite automatic-panel safety implication, not enough to claim a controlled useful repair
at the destination or human-validated harmfulness. It is an already observed reversal with a
new decision-replay interpretation, not newly collected security evidence.

The 44 opposite-operator response disagreements are not 44 controlled repairs: all 44 lack
actually required source capability controls. A stored `passed=true` with `required=false`
is vacuous. In V4, by contrast, all 480 logical controls pass, and no outcome is UNKNOWN.
However, 60 of the 65 primary failures are MALFORMED_JSON and only 5 are WRONG_VALUE.
V4 does not measure target proper subsets, hence does not certify target minimality. The
comparison stratum is a preservation comparison, not a known-negative control.

The original D3 neutralizer-Jaccard gate remains failed at 64/141, approximately 0.454,
below 0.80. These audits neither reinterpret that as a pass nor validate the replacement
harmfulness judge, whose local null controls failed.

## Explicitly blocked claims

- First minimal, local, causal jailbreak explanation: contradicted by the verified LOCA scope.
- First removal-dependent explanation framework: contradicted by the Covert framework.
- First certified/minimal explanations or family enumeration: contradicted by formal work.
- DDOR/ddmin falsely certifies unique/global necessity: not its stated guarantee; our nine
  COMPLETE D3 outputs are not counterexamples to their selected-set guarantee.
- New evidence that nonmonotonicity or erasure artifacts exist: known conceptually and
  empirically, including warnings in the closest LLM reduction paper.
- Hashes, mandatory operator metadata, exhaustive enumeration, or UNKNOWN bookkeeping alone
  establish a substantive theory contribution: not demonstrated.
- V4 proves security impact, 44 D3 mismatches are control-qualified, or incomplete cells are
  negative truth: contradicted by the measurement and control boundaries above.
- No exact matching title was found, therefore novelty is established: invalid inference.

## One residual candidate and its falsifiable qualification

Candidate question: In a documented explanation-guided security repair workflow, when do
finite local certificates lead to wrong deployment decisions, and can a decision-specific
audit reduce those errors at matched test cost, retained task utility, and decision coverage?

The proposed contribution would be measured decision reliability, not the observation that
different edited prompts differ. It requires an actual consumer or implemented published
workflow, its precise acceptance decision, and evidence that the disputed inference occurs.
If no such consumer uses a source certificate beyond its domain, a hypothetical upward-closure
policy is only a cautionary example, not a consequential baseline to defeat.

Required comparisons are source-only explanation use, direct testing of the exact deployed
intervention, a matched-budget audit, and conservative abstention. The crucial negative
control is operational: if direct destination rechecking gives the same decision quality
and utility for less cost, a full minimal-family certificate has not earned practical value.
Coverage must be reported so abstaining on every case cannot masquerade as a successful fix.

The endpoint must be security-relevant and independently defensible: locally validated
harmfulness, or an explicitly scoped unauthorized-action/disclosure observable. Harmless
JSON compliance is not a substitute. Preserve the real task and count every preselected
problem; match capability controls to every source certificate being called a repair.
Use genuinely fresh problem/attack clusters and distinguish repeated models/operators from
independent samples. The exact small-domain table can validate certificate classification,
but cannot by itself supply external validity or an unbounded safety guarantee.

Continuation requires both a meaningful decision error in the specified workflow and a
nontrivial advantage over direct rechecking under an appropriate cost/coverage comparison.
Failure of either condition rejects this candidate's current main-paper claim. Favorable
pilot data would justify a larger study, not automatic ICLR-main readiness. This audit
authorizes no new experiment and substitutes no workshop or preprint for the user's target.
