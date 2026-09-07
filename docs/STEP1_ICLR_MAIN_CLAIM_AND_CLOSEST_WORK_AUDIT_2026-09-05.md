# STEP1 decision: one independent ICLR-main research candidate

Date: 2026-09-05. Review began approximately 12:09 UTC / 21:09 KST.
This is a research decision record, not a manuscript, experiment, preregistration,
acceptance forecast, or reclassification of an earlier failure.

## 1. Outcome first

STEP1 is complete. The decision is GO for one bounded feasibility/falsification
package, but NO-GO for claiming that the existing results constitute an independent
ICLR-main paper or for launching a paper-scale experiment now.

The single retained question is:

> Can a learned-oracle localization procedure make consequentially wrong
> prompt-injection repair decisions because its search assumptions do not hold,
> and can those decisions be improved beyond simple rechecking at a comparable
> cost while retaining the authorized task?

The concrete first audit target is the ordered-prefix search in the published
PromptLocate workflow. The code/claim correspondence is verified; an actual
benchmark failure, its frequency, and a useful superior correction are NOT.
This is a testable candidate, not an already established new contribution.

Scope moves from characterizing minimal jailbreak-removal families to testing
the reliability of explanation-guided security repair. Prompt injection is within
LLM security but is not synonymous with harmful-content jailbreaks. The initial
objective endpoint would concern unauthorized actions or disclosure in an inert
benchmark environment. It must not be reported as general harmfulness ASR.
Security remains preferred; one independent ICLR MAIN paper remains the target.
A workshop, report, or collection of pilots is not substituted for that target.

## 2. What was actually done

The root began with existing literature and priority records, then checked
claim-specific primary papers and public source code. Three independent audits
covered formal explanations, security endpoints/forensics, and reviewer objections.
The root read their reports, checked the central search logic and prior evaluation
claims, and incorporated a newly surfaced direct competitor, AttnTrace.

- [Formal explanation/certificate collisions](STEP1_FORMAL_EXPLANATION_COLLISION_AUDIT_2026-09-05.md).
- [Security benchmarks and forensic methods](STEP1_SECURITY_BENCHMARK_AND_FORENSICS_AUDIT_2026-09-05.md).
- [Reviewer stress test, including AttnTrace](STEP1_REVIEWER_STRESS_TEST_2026-09-05.md).
- [Author priority and original work-package estimates](RESCUE_RESEARCH_PRIORITY_DECISION_2026-09-05.md).
- [Existing literature claim matrix](LITERATURE_CLAIM_MATRIX.md).

These are bounded primary-source checks, not proof that no relevant prior work
exists. An exact-title search miss is not evidence of novelty. Older conditional
passes in the project are historical, not current ICLR-main endorsements.

## 3. Claims rejected or demoted

| Proposed leading contribution | Closest-work/evidence obstacle | Decision |
| --- | --- | --- |
| Removal explanations depend on the chosen edit operator | Covert et al. explicitly organize removal methods by their specification | Validity condition, not standalone novelty |
| One reduction path misses alternatives or cannot establish global necessity | DDOR explicitly limits its guarantee and discusses nonmonotone interactions | Do not misrepresent this as a broken ddmin guarantee |
| Exact minimal families, conservative UNKNOWNs, or operator-bound certificates | Formal explanation work already distinguishes sufficiency, minimality and incomplete verification | Evaluation machinery, not a new theory claim |
| Localize an attack, delete it, and recover useful task performance | PromptLocate already evaluates this, including on AgentDojo | Broad candidate rejected |
| Condition attribution on the observed target output and test removal | AttnTrace already does output-conditioned attribution and post-removal attack evaluation | Broad candidate rejected |
| More fresh examples of BLANK-to-OMIT output-contract failure | V4 is real but predominantly formatting; destination rechecking catches the observed failures | Supporting pilot only |
| Full-family enumeration as a faster unrestricted oracle-search method | Inclusion-order search with positive-superset pruning is instance-optimal for terminal identification of all subset-minimal positives of an arbitrary Boolean oracle, with equal-cost exact binary queries and no extra structure | Do not promote this to runtime or UNKNOWN-handling optimality; see the reviewer audit's baseline proof |

The relevant primary boundaries are specific:

- Covert, Lundberg and Lee, JMLR 22(209), 2021: removal implementation is part of
  the explanation question. [Publisher record](https://www.jmlr.org/papers/v22/20-1316.html).
- DDOR, arXiv:2606.03601v1, Section 3.1: chosen-granularity 1-minimality is not a
  global minimum, all triggers, or a unique cause; nonmonotonicity is explicitly
  discussed. [Primary text](https://arxiv.org/html/2606.03601v1).
- FAME is verified in ICLR 2026 proceedings. Its universal-completion sufficiency
  and abstract/exact minimality distinctions are not the same as a finite observed
  erasure table. [Official proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/313c5f89162aeee02ea3b8e3cfdd0c6d-Abstract-Conference.html).
- Token Highlighter already combines gradient localization, embedding attenuation
  and benign-task evaluation. It is a white-box intervention, not literal text
  omission. [AAAI 2025](https://ojs.aaai.org/index.php/AAAI/article/view/34943).
- Mask-GCG studies learned masking and suffix compression for attack optimization,
  not certified useful repair. Its v2 record identifies ICASSP 2026.
  [Versioned record](https://arxiv.org/abs/2509.06350v2).
- LOCA v3, revised 2026-08-07, already studies local causal jailbreak explanations
  through representation edits. Its first-token proxy has acknowledged limitations
  and supplementary full-response evaluation; do not claim it never checks them.
  [Primary text](https://arxiv.org/html/2605.00123v3).
- Causal Analyst learns relationships among interpretable prompt features and uses
  them for attack and defense. Merely using the phrase causal jailbreak analysis
  is not a new scope. [NDSS publication](https://www.ndss-symposium.org/ndss-paper/a-causal-perspective-for-enhancing-jailbreak-attack-and-defense/).
- Erase-and-Check's guarantee concerns bounded threat transformations and a
  specified harmfulness filter. Our arbitrary response-table reversals do not
  refute that guarantee. [Primary paper](https://arxiv.org/html/2309.02705).

The older Explain-Delete-Defend publisher entry was retried but returned an error
on the final fetch. Its earlier matrix entry is retained as history; this review
does not claim a new full-text verification or rely on it for the decision.

## 4. Strongest direct competition and actual audit surface

PromptLocate v2 states that its binary search finds the earliest contaminated
segment prefix. It also uses multiple rounds, evaluates recovery and post-removal
attacks on AgentDojo, and tests adaptive attacks against its detector. These are
already occupied contributions, not omissions to allege.
[Paper, Sections IV-B, V-C and VI-B](https://arxiv.org/html/2510.12252v2).

The pinned implementation discards the earlier prefix interval after a negative
midpoint. With arbitrary prefix labels, that exclusion does not establish absence
of an earlier positive. This is our logical inference about a required search
condition, not measured failure of the learned detector.
[Code, lines 10-32](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/OpenPromptInjection/apps/PromptLocate.py#L10).

A mathematical illustration, NOT a generated attack or empirical result: let a
fixed eight-segment prefix oracle label lengths 1 and 5 through 8 positive, but
lengths 2 through 4 negative. Starting with interval [0,8], midpoint checks 4,
6 and 5 return negative, positive and positive, so the code returns 5 although
the earliest positive is 1. This establishes only that unrestricted prefix
predictions do not justify earliest-positive correctness.

Important limits: binary search can still return the earliest positive on many
nonmonotone vectors; a nonmonotonicity count is not a search-error count. Moreover,
later rounds and the helper stage may compensate. A wrong intermediate boundary
does not prove a wrong final localization or an unsafe final repair.

AttnTrace v3, revised 2026-04-17 and listed at IEEE S&P 2026, already attributes
given outputs, evaluates removal and collaborating malicious texts, and reports
PromptLocate clean-token overlocalization with a possible long-context detector
explanation. Therefore a new generic false-positive result is insufficient.
[AttnTrace, Sections IV-VI](https://arxiv.org/html/2508.03793v3).

The residual hypothesis must isolate search-rule effects from detector error,
length/context limitations and reconstruction effects, then show consequences
for both security and authorized-task completion. Absence of an identical
analysis in these checked works is not a priority claim.

## 5. Baseline fidelity is part of the scientific test

The public implementation snapshot is Open-Prompt-Injection commit
95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0, not a reproduced environment.
Its recovery path normalizes segmentation and joins retained text with spaces;
exceptions can return unchanged input and empty localization. A BLANK operator
or source-preserving deletion is a separate treatment, not the native baseline.
Separately, the Step III helper retains the last 1,024 input tokens, while its
condition length was computed before that truncation; long-context helper-score
validity is an additional confound to check, not a measured failure here.
[Recovery code](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/OpenPromptInjection/apps/PromptLocate.py#L265).

The detector preprocesses text, including lowercasing, and uses its localization
query path. Source-native behavior must be recorded before proposing any fix.
[Detector implementation](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/OpenPromptInjection/apps/DataSentinelDetector.py).

That localization path uses its own instruction/text formatting, greedy generation
with a 10-new-token cap and repetition penalty 1.2. It does not use the generic
configuration's 128-token output setting. It returns only decoded text, without
finish metadata; no explicit input truncation is requested there. The loader uses
4-bit NF4 with a fine-tuned adapter. The native path must not silently be replaced
by our Qwen/Gemma chat servers. Greedy decoding is not hardware-independent
determinism, and the actual loaded context limit is not established by the source
alone. [Pinned model implementation](https://github.com/liu00222/Open-Prompt-Injection/blob/95290f7ce3794c4c52ad3fe8113db2bfcdfe89e0/OpenPromptInjection/models/QLoraModel.py#L85).

Additional fidelity requirements: pin weights/adapter/tokenizer/dependencies,
record effective seed after initialization, include helper and detector costs,
retain fallback/length failures, and separate a faithful reproduction from any
instrumented variant. None of those runtime admissions has happened in STEP1.

## 6. What would make this ONE paper rather than a code bug report?

The proposed contribution has one causal chain, not three disconnected pilots:

1. A reproducible, materially consequential mismatch between a published search
   decision and the information supplied by its learned oracle.
2. A controlled explanation of when that mismatch changes the final repair,
   separating security-policy violation from loss of the authorized task.
3. A useful correction or audit strategy that earns its cost against strong simple
   baselines on untouched cases and independently meaningful conditions.

Only the source-level candidate in item 1 exists today. No new method is claimed.
Changing binary search to a linear scan is an obvious diagnostic/control, not a
novel algorithm. A single isolated bug, a synthetic Boolean example, or one
favorable template would not presently justify the ICLR-main claim.

For a fixed execution and intervention S, record V(S), the declared prohibited
action/disclosure, and U(S), the authorized task result. Joint useful repair
requires V=0 and U=1. V=0/U=0 is suppression without demonstrated useful repair;
it is not automatically proof that deletion caused capability damage.
Matched clean edit controls are needed for that stronger attribution.
Unknown components remain explicit; a known violation rejects repair regardless
of uncertainty about U.

AgentDojo offers simulated action/state endpoints and legitimate-task checks,
but its utility requirements are real. Our local targets are not yet admitted
for these trajectories. [Benchmark paper](https://arxiv.org/html/2406.13352v3).
Tensor Trust offers cheaper access-marker/exact-secret endpoints with narrower,
game-specific coverage; substituting its marker for JSON is not itself progress
on novelty. [ICLR 2024 record](https://proceedings.iclr.cc/paper_files/paper/2024/hash/519c51529c3544b3430bd8b17d400365-Abstract-Conference.html).
Neither benchmark solves measurement merely by existing; task-specific scorer
semantics and authorized-task competence must pass first.

## 7. Smallest discriminating next package -- not executed here

First do a resource/faithfulness and decision-audit preflight, estimated 2-4 hours
of focused work, then report the exact proposed pilot and call ceiling BEFORE
any inference. This estimate is for preparation and a viability decision, not
for proving a paper or reproducing a multi-turn benchmark.

The next package should produce:

- A pinned native-baseline dependency/asset inventory and read-only admission
  report. No unannounced model download, provider spend or target replacement.
- A safe decision-replay specification distinguishing oracle labels, search
  decisions, provenance labels and final V/U outcomes.
- Source-level synthetic tests of the search implementation and failure handling.
  Such tests establish code behavior only and never count as security evidence.
- One exact, executable security endpoint and a clean-task admission protocol.
  If existing local resources cannot faithfully run both method and target,
  report that limitation before choosing resources or a different setting.
- A pre-output pilot manifest with outcome-independent cases, complete accounting,
  budgets, controls, untouched validation and continuation thresholds.

The decisive later comparison uses identical cached prefix-label vectors and
segmentation to contrast native search with a literal earliest-positive scan.
Every subsequent exclusion round changes the input and needs its own labels.
Then run the FULL native recovery and controlled variant to determine whether
the search difference matters; do not stop at an intermediate index mismatch.
Oracle-table acquisition is charged even when replay itself is cheap.

Necessary baselines include native PromptLocate, native output plus destination
V/U rechecking, whole-source removal, and budget-matched simple joint-endpoint
search/rechecking. AttnTrace is a close comparator where its target/surrogate
access can be reproduced fairly. A gold injected-span oracle is an evaluation
reference, never free information for the proposed method.

For decision reporting, count useful nonviolating releases, violating releases,
withheld/unresolved cases, legitimate utility, edited information and all calls
over the entire frozen case frame. Conditional rates need their denominators;
always withholding cannot win merely by having zero released violations.
Evaluation-oracle access to exact V/U must not silently be given to a deployed
method unless that access is expressly part of the operational setting.

Stop or change direction if any of the following occurs:

1. Only artificial Boolean vectors show the search gap; real eligible traces do
   not show material final-decision consequences.
2. A detector/length/renderer mismatch, not the search assumption, explains the
   result, and the claimed contribution is already covered by existing work.
3. Correcting the intermediate boundary does not improve the final security/utility
   decision, or makes it worse.
4. Direct rechecking or a simple matched-budget search provides equivalent value
   more cheaply; exhaustive certificates add no required decision information.
5. Whole-source removal already solves the chosen task without utility loss.
6. Faithful baselines or adequate clean-task competence are unavailable locally.

These are scientific decision conditions, not post-hoc numeric acceptance gates.
Effect margins and actual resource ceilings must be set before new pilot outputs.
The broader 24-48-hour direction decision and conditional multi-day study estimate
remain planning ranges, subject to the resource admission result.

## 8. Existing evidence is retained, not promoted

| Evidence | What remains useful | What it does not establish |
| --- | --- | --- |
| D3 | Fixed finite intervention observations and a panel-relative safety-propagation counterexample | A failure of ddmin's actual guarantee, fresh human truth, or this new search mechanism |
| C1N / V2 measurement | Records of response diversity, disagreement and the failed replacement-judge control | A qualified new harmfulness endpoint or an intervention lattice |
| V3/V4 | Tested infrastructure and prospective operator-transfer evidence on harmless tasks | Prompt-injection repair prevalence or a useful correction beyond direct checking |

The D3 neutralizer agreement gate remains failed. Its hypothetical upward-closure
replay has one contradiction among 17 decisions, including one among six unqueried
supersets; that consumer assumption is not a published ddmin guarantee. The 44
cross-operator disagreements have no actually required source capability controls
and must not be promoted to 44 qualified repairs.

V4 completed 1,120 target calls before this review: 65/128 primary joint events
over 64 problems, with 60 formatting failures and five wrong values. These
facts remain unchanged. [Completed result](RESCUE_V4_PROSPECTIVE_TRANSFER_RESULT_2026-09-05.md).
No current-step count is added to those experiment totals.

## 9. Execution and authorization boundary

This review made zero target-model/judge inference calls, zero paid model calls,
zero original private-prompt/response or A/B accesses, zero dataset experiments,
and zero manuscript/PDF edits. Public literature, code and metadata reads are
not model experiments. No attack was optimized or deployed.

Only new STEP1 audit documents and append-only navigation, literature and ledger
updates were written. Frozen research code, protocols, configurations and results were not
changed. No old test/verifier was rerun, no commit/push was made, and no model
experiment was started. The current action is to report STEP1, not silently
advance to the next package.
