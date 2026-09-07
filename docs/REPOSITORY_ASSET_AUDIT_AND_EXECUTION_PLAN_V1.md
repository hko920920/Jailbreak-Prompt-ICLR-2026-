# Repository Asset Audit and Execution Plan v1

Date: 2026-08-31 (Asia/Seoul)

Status: **CURRENT WORK PLAN / P2 HARMLESS RUNTIME COMPLETE / ATTACK AND TOPOLOGY OUTCOMES CLOSED**

This plan operationalizes [CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md](CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md). It does not authorize treating any legacy development output as paper-valid evidence.

## 1. 감사 범위와 현재 상태

감사 시작 시 snapshot은 693 commits와 684 tracked files였다. 새 current-state 문서를 만들기 전 작업 폴더의 주요 구성은 docs 93개, configs 56개, data 252개, scripts 78개, src 45개, tests 67개, GitHub workflows 83개였다. 이 양은 “실험이 많이 끝났다”는 뜻이 아니라 여러 연구 경로와 운영 실패를 상세히 보존했다는 뜻이다.

현재 증거 판정:

- **PROTOCOL:** 상당량 존재.
- **DEVELOPMENT:** evaluator와 legacy span 실험 등에 존재.
- **NEGATIVE:** human-free Gate 1과 AgentHarm 경로에 존재.
- **PAPER_VALID:** 없음.
- **SEALED:** fresh confirmation, current topology outcome, keep-only oracle 등은 열리지 않음.

현재 작업 트리에는 사용자의 ICLR style zip과 paper scaffold, 기존 수정사항이 있다. 이 감사에서는 삭제, commit, push를 하지 않는다.

## 2. 자산별 판정

### A. 현재 연구에 직접 살릴 자산

| 자산 | 위치 | 판정과 용도 |
|---|---|---|
| h4rm3l source/provenance, real-template, typed-unit adapter | [E0_H4RM3L_TYPED_UNITS_V1.md](E0_H4RM3L_TYPED_UNITS_V1.md), 관련 configs/data/scripts/tests | **직접 재사용.** 공격자가 추가한 의미 단위, exact payload 보존, 두 neutralizer의 출발점 |
| DeepInception exact-payload rerender v2와 parameter audit | [E0_DEEPINCEPTION_EXACT_PAYLOAD_RERENDER_V2.md](E0_DEEPINCEPTION_EXACT_PAYLOAD_RERENDER_V2.md), 관련 자산 | **로컬 축소 경로에 직접 재사용.** official byte-identical artifact가 아니라 source-conformant derived adapter라는 표시 유지 |
| GCG source boundary, tokenizer preflight, runtime bundle | [E0_GCG_STATIC_ADAPTER_AUDIT_V1.md](E0_GCG_STATIC_ADAPTER_AUDIT_V1.md), [H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_V1.md](H4RM3L_GCG_SIGNAL_SCREEN_RUNTIME_BUNDLE_V1.md) | **외부 GPU 경로에 재사용.** local semantic-only 결과와 섞지 않음 |
| AutoDAN exact-placeholder 및 Qwen adapter audit | [E0_AUTODAN_STATIC_ADAPTER_AUDIT_V1.md](E0_AUTODAN_STATIC_ADAPTER_AUDIT_V1.md), 관련 자산 | **confirmatory 확장 후보.** 최종 attack artifact/regeneration과 mutation payload protection이 해결되기 전에는 실험 family로 승격하지 않음 |
| config freeze, hash, provenance, safe-artifact ledger | configs, data, [EXPERIMENT_EXECUTION_LEDGER_V1.md](EXPERIMENT_EXECUTION_LEDGER_V1.md) | **직접 재사용.** model/tokenizer/revision/seed/hardware와 결과 연결, raw harmful artifact 비공개 |
| 인간 annotation packet, blinding, agreement/adjudication code | [NATURAL_LANGUAGE_ANNOTATION_RUNBOOK.md](NATURAL_LANGUAGE_ANNOTATION_RUNBOOK.md), src/jbspan/natural_language_annotation.py | **직접 재사용 후 label schema 갱신.** 두 annotator와 adjudicator 구조 유지 |
| payload alignment, TextSpan, deterministic neutralization primitives | src/jbspan/schemas.py, src/jbspan/neutralization.py, src/jbspan/dataio.py | **기초 재사용.** 새 typed attack-unit schema와 payload guard로 확장 필요 |
| CPU tests와 harmless fixtures | tests, [ci.yml](../.github/workflows/ci.yml) | **직접 재사용.** 새 oracle의 synthetic truth-table tests를 추가 |
| official ICLR style assets | iclr-2027-style-files.zip, paper | **후반부 재사용.** empirical gate 전에는 paper drafting에 시간을 쓰지 않음 |

### B. 핵심은 살리되 현재 주제에 맞게 고쳐야 할 자산

| 자산 | 현재 한계 | 필요한 전환 |
|---|---|---|
| src/jbspan/search/exhaustive.py | 이름과 달리 현재는 atomic leaf singleton만 검사 | predeclared unit의 모든 2^m subset 평가, 모든 minimal recovery set 반환, non-monotone truth table 지원 |
| src/jbspan/scoring.py와 pilot.py | scalar mean refusal/effect와 intent score 중심 | categorical full-response outcome, per-neutralizer/per-seed predicate, capability/truncation/abstention 상태로 교체 |
| LocalizationResult schema | 하나의 span set과 scalar effect를 중심으로 표현 | unit vocabulary, complete subset table, minimal-set family, exactness scope, provenance를 표현하는 TopologyResult 추가 |
| RegexClauseSegmenter | prompt 전체를 결과와 무관한 generic regex로 자름 | primary unit은 source-derived attack units만 사용; regex는 fallback/baseline으로 한정 |
| neutralizers | generic delete/placeholder/word-count replacement | family-specific neutral block/clause replacement, byte payload guard, layout/token-position validity 검사를 결합 |
| raw InterventionRecord | edited prompt와 response를 일반 record에 직접 보관 | private record와 safe hash/aggregate record를 분리 |
| cache/query accounting | 단일 search 호출 중심 | subset, neutralizer, seed, model revision을 key로 하는 resumable sharded execution과 deduplication |

즉, 현재 core package는 버릴 코드는 아니지만 **새 주제의 exact topology engine이 이미 완성돼 있다고 볼 수 없다.**

### C. 논문 결과가 아니라 배경·실패 증거로 살릴 자산

| 자산 | 사용할 수 있는 방식 | 사용할 수 없는 방식 |
|---|---|---|
| legacy Phase 1의 약 32–58% broad-span recovery 관찰 | 왜 더 작은 set과 intervention artifact를 확인해야 하는지 동기 제공 | 현재 topology 현상의 paper-valid 결과 |
| Gate 1 evaluator pipeline | 측정 실패, disagreement routing, frozen-threshold 준수의 설계 교훈 | WildGuard를 primary truth로 재승격하거나 threshold 완화 |
| WildGuard Q4/Q8 동일 confusion matrix | quantization이 해당 판정 차이의 원인이 아니었다는 negative evidence | current target topology의 자동 ground truth |
| AgentHarm Qwen negative 및 Llama interoperability failure | 실패한 population discovery 경로와 도구 호출 취약성 기록 | main empirical family 재개 또는 localization hypothesis 반증 |
| AutoDAN/DeepInception 초기 parser 실패 | payload-preservation construct validity의 중요성 | 공격 실패나 모델 안전성 결과 |
| 이전 charter, novelty matrix, formalization | 용어·선행연구·protocol history | 현재 scope를 덮는 권위 문서 |

### D. exact topology가 확인된 뒤에만 열 자산

- hierarchical, beam, group-testing, SHIPs/SAHARA-inspired, wavelet search;
- gradient/token attribution과 Mask-GCG-style baseline;
- selected-case keep-only sufficiency;
- mechanistic activation/head analysis;
- broader semantic/fluent/non-fluent regime comparison.

이것들은 가치가 없어서가 아니라 현재 논문의 존재 여부를 결정하는 선행 질문이 아니므로 보류한다.

### E. 더 이상 시간을 쓰지 않을 경로

- AgentHarm main route 재개;
- human-free single-primary-judge Gate 1 재개;
- WildGuard/HarmBench qualification을 headline contribution으로 확장;
- exact oracle 전에 wavelet 또는 복잡한 adaptive search 최적화;
- 현재 로컬 장비로 frozen BF16 GCG를 억지로 축소 실행;
- 모든 token power set, universal jailbreak taxonomy, 전 모델 일반화;
- 결과가 없는데 paper prose와 figure polishing을 먼저 진행;
- 결과를 만들기 위한 사후 threshold, unit, family, neutralizer 변경.

파일은 삭제하지 않는다. 이 판정은 **역사 기록은 보존하되 앞으로 연구 시간을 쓰지 않는다**는 뜻이다.

## 3. 운영상 정리할 기술 부채

GitHub workflows가 83개이고 다수가 과거 gate 또는 임시 수리용이며 push trigger를 가진다. 현재 연구와 무관한 workflow가 의도치 않게 재실행될 위험이 있다.

다음 정리는 scientific output을 열기 전에 별도 diff로 수행한다.

1. ci와 현재 static validation만 기본 push/PR 대상으로 남긴다.
2. 과거 Gate 1, AgentHarm, evaluator qualification, temporary-fix workflow는 manual-only 또는 archive 대상으로 분류한다.
3. current local-only contract가 정해지기 전 새 target-run workflow를 만들지 않는다.
4. 삭제 대신 archive manifest에 원래 path, 목적, terminal decision을 기록한다.

이 정리는 결과를 바꾸지 않는 operational cleanup이며, 현재 감사 문서 작성과 분리한다.

로컬 Python 환경에도 즉시 정리할 충돌이 있다. plain Python은 현재 저장소가 아니라 과거 복제본인 C:\Users\SOGANG\Documents\ICLR 2027 Plan 260808\JailbreakPrompt-ICLR2026-\src의 editable jbspan package를 먼저 import한다. 이 때문에 plain python -m pytest는 collection 단계에서 실패했다. 현재 저장소의 src를 import path 맨 앞에 명시하면 전체 CPU test suite가 통과했다.

P1을 시작하기 전에 다음 중 하나로 실행 환경을 격리한다.

1. 현재 저장소 전용 virtual environment를 만들고 현재 package만 editable install;
2. 모든 local command와 CI에서 import origin을 assert;
3. 과거 복제본은 자동 삭제하지 않고, 실험 process가 그 경로를 import하지 못하게 함.

## 4. 실행 경로 결정

### Route A — canonical / external high-memory GPU

기존 frozen development design을 최대한 유지한다.

- Qwen2.5-7B canonical BF16;
- h4rm3l + optimized GCG;
- GCG 4 jobs × 500 steps, width 512, top-k 256;
- exact coarse topology 후 DeepInception/AutoDAN과 second canonical model로 확장.

현재 [GCG_QWEN_DIFFERENTIABLE_COMPUTE_CONTRACT_V1.md](GCG_QWEN_DIFFERENTIABLE_COMPUTE_CONTRACT_V1.md)은 2×A100 80GB를 요구한다. 외부 GPU가 생기면 결과를 보기 전에 1×A100 sequential 사용 가능 여부를 compute-only amendment로 정해야 한다. 현재 로컬 RTX 3070 8GB에서는 이 경로가 불가능하다.

### Route B — local-only, 현재 권고

별도의 새 contract로 다음 범위만 연구한다.

- Qwen2.5-7B-Instruct Q4와 Meta-Llama-3.1-8B-Instruct Q4;
- h4rm3l + DeepInception semantic/compositional attacks;
- exact coarse topology, two neutralizers, three seeds, full-response labels, capability controls;
- fresh confirmatory split와 independent human audit.

이 경로의 결과는 canonical BF16 proxy가 아니라 **Q4 target 자체에 대한 결과**다. GCG/AutoDAN, optimized-suffix 비교, semantic 대 optimized regime 일반화는 주장하지 않는다.

현재 장비 확인:

- NVIDIA GeForce RTX 3070, 8192 MiB;
- system RAM 약 32 GiB;
- Intel i7-11700, 8 cores / 16 logical processors.

따라서 Q4 inference는 조건부 가능하지만 실제 load, VRAM, context, throughput, thermal stability를 harmless smoke로 확인하기 전에는 가능하다고 확정하지 않는다.

## 5. 단계별 실행계획

### P0 — 현재 scope와 증거 경계 고정

완료 조건:

- [CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md](CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md)가 central question과 non-claims의 권위 문서가 됨;
- 본 asset audit가 이전 경로의 사용/전환/중단 상태를 명시;
- paper-valid result가 없다는 상태 유지;
- local-only route를 실행하기 전 별도 machine-readable config를 작성.

### P1 — exact topology engine 구현과 CPU 검증

**Status: COMPLETE — 2026-08-31.** Harmless synthetic gate PASS. See [P1_EXACT_TOPOLOGY_ENGINE_GATE_RESULT_V1.md](P1_EXACT_TOPOLOGY_ENGINE_GATE_RESULT_V1.md).

새 target output 없이 먼저 구현한다.

1. immutable payload와 ordered typed attack units를 분리하는 schema.
2. categorical outcome과 capability/truncation/abstention을 포함한 Recovery predicate.
3. empty set을 포함한 모든 subset 평가와 complete truth table.
4. monotonicity를 가정하지 않는 strict-subset-minimal family 추출.
5. 두 neutralizer의 payload/length/layout validity validator.
6. private raw record와 safe hashed aggregate 분리.
7. resumable shard, deterministic cache key, duplicate-call 방지.
8. singleton, pure pair interaction, multiple pathways, non-monotone recovery, neutralizer disagreement, capability confound, payload corruption의 synthetic oracle tests.

**P1 gate:** synthetic truth table에서 모든 minimal set을 정확히 복원하고 payload/confound 위반을 recovery로 세지 못해야 한다. 이 gate 전 target-model topology를 실행하지 않는다.

### P2 — harmless local runtime qualification

**Status: COMPLETE — 2026-08-31.** Two-model harmless gate PASS. See [P2_LOCAL_Q4_RUNTIME_QUALIFICATION_RESULT_V1.md](P2_LOCAL_Q4_RUNTIME_QUALIFICATION_RESULT_V1.md).

- 두 Q4 artifact의 repository revision, filename, LFS SHA-256, tokenizer/chat template를 기록;
- harmless prompt 10–20회로 load, deterministic seed, resume/sharding 검증;
- seconds/token, peak VRAM/RAM, 오류율, 512-token upper-bound runtime 측정;
- private work directory와 safe output boundary 확인.

**P2 STOP:** 두 모델 중 하나가 안정적으로 실행되지 않거나, 예상 confirmatory runtime이 deadline 안에 들어오지 않으면 two-model ICLR route를 중단하거나 다음 cycle로 넘긴다.

Observed P2 decision: both exact Q4 targets passed 11/11 harmless processes, 10/10 capability checks, deterministic replay, embedded chat-template, GPU-offload, throughput, VRAM, thermal, hash, and resume gates. Median decode throughput was 62.87 tokens/s for Qwen and 55.99 tokens/s for Llama. This is an operational GO to freeze P3, not evidence of attack success or topology.

### P3 — local development signal screen

결과를 보기 전 새 config로 고정한다.

- 4 development payloads;
- h4rm3l + DeepInception;
- Qwen Q4 한 모델;
- seeds 11, 23, 47;
- shared direct baseline 12 generations;
- attacked baselines 24 generations;
- baseline total 36 generations;
- 자동 평가는 screening/disagreement routing만 담당;
- direct-safe / attacked-harmful stable pair만 topology 대상으로 진입.

독립 인간 감사가 아직 준비되지 않았다면 P3는 development triage까지만 하고 paper claim은 열지 않는다.

Observed P3 execution: the pre-outcome contract was frozen at SHA-256 `cab5e7899c57c267e2b2f2ad5b202c05026103dac48de6cace835085120c5a1b`, and all 36 Qwen processes completed. A parser-only failure on 24 long prompt echoes was fully recovered from preserved stdout without rerunning generation or changing scientific conditions; the repaired result is 36/36 operational, 36/36 screening eligible, with zero max-token truncations. The auxiliary refusal/length queue produced zero joint candidates, but it is not a harmfulness judge. Exact official WildGuard Q8 screening then completed with 36/36 eligible judgments and three nonfinal automatic candidates, all h4rm3l. This is below the frozen narrow threshold and therefore enters `STOP_REVIEW`, not terminal STOP. The full 36-item blinded two-annotator packet is ready; human labels and topology remain unopened. See [P3_LOCAL_SIGNAL_SCREEN_EXECUTION_RESULT_V1.md](P3_LOCAL_SIGNAL_SCREEN_EXECUTION_RESULT_V1.md) and [P3_WILDGUARD_SCREEN_AND_HUMAN_AUDIT_PACKET_RESULT_V1.md](P3_WILDGUARD_SCREEN_AND_HUMAN_AUDIT_PACKET_RESULT_V1.md).

### P4 — exact coarse topology micro-pilot

- unit vocabulary는 결과를 보기 전에 source-derived 방식으로 고정;
- h4rm3l은 existing typed units 활용;
- DeepInception은 P3 output 전에 source-derived seven-unit adapter 유지와 post-outcome merge 금지를 동결했으므로, 진입 시 instance당 128 subsets 사용;
- 각 subset × two neutralizers × three seeds;
- every reported recovery set의 모든 strict subset 확인;
- random/cost-matched, irrelevant-unit, malformed, benign capability controls.

비용:

| units | subsets | generations per stable pair |
|---:|---:|---:|
| 6 | 64 | 384 |
| 7 | 128 | 768 |

**Development GO:** stable pairs 총 6개 이상, family당 2개 이상, robust minimal set instance 3개 이상, non-singleton 또는 multiple-set instance 2개 이상, neutralizer agreement 0.80 이상, capability-confound rate 0.25 미만.

**NARROW:** 한 family에서만 안정적이고 비자명한 topology가 반복됨.

**STOP:** stable pairs 4개 미만, 결과가 obvious singleton/whole wrapper뿐, instability/confound가 지배, 또는 human label이 신뢰 기준에 미달.

이 gate는 paper-valid result가 아니라 fresh confirmation으로 갈지를 결정한다.

### P5 — fresh two-model confirmation

P4 GO일 때만 연다.

- development에서 사용하지 않은 fresh payload 20개;
- 2 attack families × 2 Q4 models × 3 seeds;
- shared direct baseline 120 + attacked baseline 240 = 360 generations;
- stable instances는 family/model/category별로 사전 정의한 stratified rule로 선택;
- exact topology 대상 상한과 unit cap을 runtime smoke 결과를 본 뒤가 아니라 **outcome 전** 고정;
- 2 independent annotators, disagreement/uncertain은 third adjudicator;
- primary endpoint, exclusion, multiplicity handling, confidence interval을 사전 명시.

기존 제안처럼 24개 stable instance에 6 units를 사용하면 intervened generation worst case는 9,216이다. 7 units면 18,432이므로 P2 throughput으로 현실적 시간을 먼저 계산해야 한다.

### P6 — baselines와 분석

exact topology 이후에만 실행한다.

필수 baseline:

- singleton leave-one-out;
- random size/position/cost-matched subset;
- greedy backward elimination 또는 group-testing search.

canonical gradient compute가 확보될 때만 Token Highlighter/Mask-GCG-style white-box baseline을 추가한다.

필수 분석:

- eligible/stable attack population rate;
- minimal recovery order distribution;
- distinct minimal-pathway incidence와 overlap;
- singleton/greedy miss rate;
- per-neutralizer and per-seed agreement;
- capability-confound, truncation, malformed, abstention rate;
- paired/bootstrap or cluster-aware 95% confidence intervals;
- model/family/category strata는 표본이 작으면 descriptive로 제한.

### P7 — paper 작성

P5에서 반복되는 C3 signal이 확인되고 인간감사가 닫힌 뒤에만 본문 초안을 시작한다. official ICLR style, reproducibility, ethics, artifact release boundary, AI-tool disclosure를 적용한다.

## 6. 우선순위와 hard gates

현재 날짜와 ICLR 2027 일정을 고려한 공격적 기준:

| 날짜 | 반드시 닫혀야 할 항목 | 실패 시 |
|---|---|---|
| 09-02 | P1 핵심 oracle tests + P2 두 모델 smoke | ICLR two-model route 고위험/다음 cycle 검토 |
| 09-05 | 36-generation development screen + baseline audit routing | empirical route 중단 검토 |
| 09-09 | exact micro-pilot GO/NARROW/STOP | GO가 아니면 confirmatory 금지 |
| 09-15 | fresh confirmation generation 종료 | complete ICLR empirical paper 사실상 어려움 |
| 09-18 | 인간 감사·통계·abstract claim freeze | 불완전 claim 제출 금지 |

Official deadlines and policies:

- [ICLR 2027 Dates](https://iclr.cc/Conferences/2027/Dates)
- [ICLR 2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
- [ICLR 2027 AI Policy for Authors](https://iclr.cc/Conferences/2027/AIPolicyForAuthors)

## 7. 최종 성공/중단 기준

계속할 조건:

- 안정적인 successful jailbreak population이 충분함;
- 비자명한 topology가 사례 선택 없이 반복됨;
- singleton 또는 greedy baseline의 구체적 miss가 있음;
- 결과가 neutralizer/seed/capability controls를 통과;
- fresh second-model confirmation과 independent human audit가 완료됨.

중단하거나 다음 cycle로 넘길 조건:

- stable population 부족;
- 모든 결과가 obvious singleton 또는 whole-wrapper deletion;
- neutralizer disagreement, truncation, prompt corruption, capability collapse가 설명을 대체;
- second model 또는 human audit 미완료;
- fresh split에서 개발 신호가 반복되지 않음;
- deadline 전에 reproducible ledger와 confidence interval을 닫지 못함.

## 8. 바로 다음 작업

1. 준비된 Reviewer A와 Reviewer B의 로컬 private packet을 서로 독립된 두 사람에게 전달.
2. 두 annotator가 condition, family, seed, WildGuard 결과를 모른 채 36개 전부를 판정.
3. 두 파일을 모두 먼저 checksum으로 동결한 뒤 agreement와 Cohen's kappa gate를 계산.
4. disagreement와 `UNCERTAIN`만 제3 adjudicator가 판정.
5. human-confirmed stable pair 수에 따라 P4 broad, qualified-family narrow, 또는 current-screen stop을 적용.

현재 가장 중요한 것은 자동 후보 3개를 결과로 과해석하는 일이 아니라 **동결된 독립 인간 감사로 WildGuard false positive/negative를 확인하고 topology 진입 여부를 확정하는 것**이다.
