# Evaluator Panel Calibration-only Redesign Plan v1

Date: 2026-09-02 (Asia/Seoul)

Decision: **PLAN READY / NO NEW INFERENCE / PRIMARY HELD-OUT CANDIDATE COMPARISON, P3, AND TOPOLOGY OUTCOMES REMAIN CLOSED**

Evidence class: **POST-FAILURE DEVELOPMENT PLAN; NOT PANEL QUALIFICATION AND NOT PAPER-VALID EVIDENCE**

## 1. 결론

E0D 실패는 evaluator를 다시 설계할 이유가 충분하지만, 임계값을 조금 낮추는 방식으로는 해결되지 않는다. 재설계의 1차 경로는 다음과 같다.

1. 기존 3,556개 Mistral/Phi axis 출력을 추가 추론 없이 재사용한다.
2. `harmful response`를 넓게 잡는 WildGuard를 주 신호 후보로 올린다.
3. Guided의 cross-family unanimity와 actionability의 dual hard veto를 제거한다.
4. Guided와 actionability는 behavior-specific 보조 신호 또는 soft feature로 사용한다.
5. safe와 harmful 결정을 별도 임계값으로 만들고 중간 구간은 `ABSTAIN`으로 둔다.
6. source를 가로지르는 behavior-group nested cross-validation으로 후보를 선택한다.
7. 새 추론은 약 20분, 누적 45분, 최종 약 2시간의 순차 futility gate로 끊는다.
8. calibration에서 충분한 margin을 가진 후보 하나만 고정한 뒤, 과거 결과에 노출되지 않은 held-out에서 한 번만 자격을 검증한다.

현재 가장 합리적인 가능성 평가는 다음과 같다.

- 단순 A 임계값 완화 또는 G unanimity 완화: 가능성 낮음;
- 기존 Mistral/Phi 출력을 이용한 저비용 재조합: 먼저 확인할 가치가 있으나 단독 성공 가능성은 높지 않음;
- WildGuard + behavior-specific G/A soft fusion: 중간 정도의 가능성이 있으며 현재의 우선 경로;
- 같은 3B judge에 여러 persona를 주는 방식: 독립 judge로 간주하지 않으며 우선 경로에서 제외;
- calibration 실패 후 계속 prompt/threshold를 탐색하는 방식: 금지.

## 2. E0D에서 정확히 무엇이 실패했는가

E0D는 실행 자체가 실패한 것이 아니다. 889개 calibration record에 대해 두 judge의 G/A 3,556개 측정이 모두 정상적으로 생성되었고, parse/canary/context/record-integrity failure는 0이었다.

실패는 측정 구조에 있었다.

| 신호 | Harmful precision | Harmful recall |
|---|---:|---:|
| Ministral Guided present | 0.6854 | 0.5034 |
| Phi Guided present | 0.5967 | 0.7552 |
| Guided unanimous present | 0.6872 | 0.4241 |
| Actionability alone, A1--A3 | 0.8784--0.8873 | 0.2172--0.2276 |
| Final G AND A | 0.9286--0.9500 | 0.1310--0.1345 |

즉, 각 축에는 일부 signal이 있지만 두 judge의 G와 A를 모두 hard conjunction으로 묶으면서 recall이 붕괴했다. 특히 A1/A2/A3가 거의 같은 결과를 냈기 때문에 현재 profile 중 하나를 고르는 것은 재설계가 아니다.

간단한 Guided OR도 해결책이 아니다. 두 Guided의 OR은 calibration harmful 290개 중 242개를 잡아 recall 약 0.8345에 그치고, precision은 약 0.6035다. frozen requirement인 recall 0.85와 precision 0.90을 모두 만족할 수 없다.

## 3. 왜 앞선 pilot이 이 실패를 일찍 잡지 못했는가

E0C와 이전의 작은 실행은 runtime/schema/canary pilot이었다. 다음은 확인했지만 인간 label 대비 scientific utility는 확인하지 않았다.

- 정확한 model file이 CPU에서 실행되는가;
- prompt와 JSON schema가 정상적으로 처리되는가;
- parser, nonce canary, determinism, context budget이 통과하는가.

따라서 `정상 실행`은 확인했지만 `human-harmful recall이 13%뿐`이라는 실패는 E0D 전체 실행 뒤에야 확인되었다. 재설계에서는 runtime pilot과 scientific futility pilot을 명시적으로 분리한다. 중간 단계는 PASS를 선언하는 데 사용하지 않고, 가망 없는 후보를 싸게 폐기하는 데만 사용한다.

## 4. 변하지 않는 과학적 경계

다음 조건은 재설계에서도 유지한다.

- explicit harmful payload는 evaluator 설계와 topology 실험 모두에서 별도 보존된다.
- human label이 있는 889개 calibration만 개발과 선택에 사용한다.
- P3 response, topology response, neutralizer outcome은 evaluator가 최종 자격을 통과하기 전까지 열지 않는다.
- source ID, stratum, annotation count, record hash는 classifier feature로 사용하지 않는다. 오직 split, audit, reporting에만 쓴다.
- target-response text를 기준으로 선택된 개별 예외 규칙을 만들지 않는다.
- calibration 결과를 본 뒤 final qualification gate를 낮추지 않는다.
- `CAPABILITY_CONFOUNDED`와 `ABSTAIN`은 recovery나 failure로 바꾸지 않는다.
- 새로 모집하는 human study는 이 경로의 critical path에 넣지 않는다. 기존 public human labels를 qualification ground truth로 사용한다.

## 5. Held-out exposure audit와 최종 시험 집합

과거 WildGuard judge-comparison 설계는 JailbreakBench 300개 전부의 label과 identity를 포함했다. 다만 completed component prediction은 old selection 200개에만 존재하고, old validation 100개는 label과 frozen design만 있으며 completed validation prediction은 없다. E0B split과 exact source locator를 대조하면 다음과 같다.

| Historical WildGuard subset | Exposure state | E0B calibration | E0B held-out | E0B excluded |
|---|---|---:|---:|---:|
| old selection 200 | label + completed component prediction | 101 | 98 | 1 |
| old validation 100 | label + frozen design only | 51 | 46 | 3 |
| total | mixed component-specific exposure | 152 | 144 | 4 |

따라서 WildGuard가 포함된 새 panel에서 JailbreakBench held-out 144개를 완전한 blinded qualification set이라고 부를 수 없다. 정확히는 98개가 label-plus-prediction exposed이고 46개가 label-plus-design exposed이다. 이 144개는 88 safe / 56 harmful이며, 보수적으로 모두 historically exposed stress test로만 보고한다.

재설계 v1은 후보 종류와 무관하게 primary final qualification set을 다음 803개로 미리 제한한다.

| Source | Records | Behavior groups | Safe | Harmful | Role |
|---|---:|---:|---:|---:|---|
| StrongREJECT | 514 | 19 | 406 | 108 | primary unexposed test |
| HarmBench | 289 | 142 | 160 | 129 | primary unexposed test |
| **Total** | **803** | **161** | **566** | **237** | **primary qualification** |
| JailbreakBench | 144 | 94 | 88 | 56 | exposed secondary stress test |

`unexposed`는 이 프로젝트가 exact candidate output과 human label을 이전에 비교하지 않았다는 뜻이다. foundation model의 사전학습 데이터에 대한 완전한 비오염을 주장하는 표현은 사용하지 않는다.

803개는 final harmful denominator 237개를 제공하므로 기존 최소 50개 조건을 충분히 만족한다. Primary test에서 JailbreakBench를 제외하는 결정은 새 candidate 결과를 보기 전에 고정한다.

## 6. 재설계하는 측정 구조

### 6.1 H: broad harmful-assistance evidence

WildGuard의 response harmfulness/refusal output을 broad harmfulness anchor 후보로 사용한다. 기존처럼 safe 후보의 보조 R axis에만 두지 않고 harmful classification에도 사용할 수 있게 한다. 단, WildGuard 단독을 ground truth로 승격하지 않는다.

### 6.2 G: behavior-specific relevance

Mistral/Phi Guided output은 exact forbidden behavior와의 관련성을 나타내는 feature로 유지한다. 다음 hard rule은 제거한다.

- 두 judge가 같은 criterion을 반드시 동시에 present라고 해야 harmful이라는 규칙;
- 한 judge의 disagreement를 자동으로 무정보로 만드는 규칙.

각 judge의 G output은 별도 binary feature로 남고, source-blind calibrator가 그 유용성을 평가한다.

### 6.3 A: soft substantive-utility evidence

specificity, actionability, harmful utility, task alignment의 여덟 ordinal score는 유지하되, 두 judge가 모두 임계값을 넘어야 한다는 hard veto는 제거한다. A는 false positive를 줄이는 soft evidence가 될 수 있지만, A가 낮다는 이유만으로 broad harmful evidence를 자동 삭제하지 않는다.

### 6.4 S: conservative safe decision

한 binary complement로 harmful이 아니면 safe라고 하지 않는다. Calibrated harmful probability 또는 score가 낮고, selected safe guard가 통과하고, topology 실행에서는 matched benign capability control K까지 통과한 경우에만 `SAFE_NONASSISTANCE`를 낸다.

### 6.5 Abstention

높은 harmful threshold와 낮은 safe threshold 사이를 `ABSTAIN`으로 둔다. 이 간격은 precision을 지키기 위한 selective classification이며, coverage gate를 별도로 통과해야 한다.

## 7. 고정할 candidate family

실제 WildGuard output을 보기 전에 exact feature bundles, regularization grid, thresholds search, tie-break를 JSON contract로 고정한다. 계획 단계의 권장 bundle은 다음과 같다.

| Bundle | Features | 추가 calibration 추론 | 관측 CPU 시간/response | 의미 |
|---|---|---:|---:|---|
| B0 | existing M/P G+A only | 0 | 0 now | zero-cost feasibility baseline |
| B1 | WildGuard only | 1 call | 약 8 s | broad classifier baseline |
| B2 | WildGuard + Phi G | 1 new call | 약 19 s total at deployment | cheapest behavior-specific fusion |
| B3 | WildGuard + both G | 1 new call | 약 27 s total | cross-family G fusion |
| B4 | WildGuard + Phi G+A | 1 new call | 약 31 s total | soft utility fusion |
| B5 | WildGuard + both G+A | 1 new call | 약 48 s total | full feature ceiling |

M/P calibration outputs은 이미 존재하므로 B0--B5 비교에서 새로 필요한 calibration inference는 WildGuard 한 번뿐이다. M/P를 다시 돌리지 않는다.

두 종류의 source-blind mapping만 허용한다.

1. 소수의 명시적 deterministic score/rule candidate;
2. 낮은 차원의 L2-regularized logistic selective classifier.

Nested CV의 inner split 안에서만 regularization, feature bundle, safe/harmful threshold를 고른다. Source-balanced 또는 empirical weighting 여부도 사전 grid에 포함하고 outcome을 본 뒤 추가하지 않는다. source/stratum/record identity는 feature가 아니다.

## 8. Behavior-group nested cross-validation

최종 개발 평가는 response-random split이 아니라 behavior group 단위로 한다.

1. calibration의 265 behavior group을 source와 label count가 가능한 한 균형을 이루도록 deterministic five-fold로 배치한다.
2. greedy allocation과 hash tie-break를 한 번 고정하고 seed search를 하지 않는다.
3. 각 outer fold에서 나머지 네 fold만 사용해 bundle, regularization, 두 abstention threshold를 선택한다.
4. outer fold prediction을 합쳐 889개 전체 out-of-fold metric을 만든다.
5. confidence interval은 record-level Wilson과 behavior-group cluster bootstrap을 모두 보고한다.
6. pooled metric, source metric, HarmBench의 frozen semantic/functional strata, unanimous/non-unanimous human-label strata를 모두 보고한다.
7. candidate 선택에는 source별 다른 threshold를 허용하지 않는다.

이 절차의 목적은 calibration 전체에 맞춘 score가 얼마나 낙관적인지 분리하는 것이다. 최종 paper qualification은 여전히 803개 primary held-out에서 한 번만 결정한다.

## 9. 비용을 제한하는 순차 실행

WildGuard의 실제 local CPU 관측치는 response당 대략 8초였다. 각 단계는 이전 출력을 재사용하며 처음부터 다시 시작하지 않는다.

### E0F-0: zero-inference audit

추가 추론: **0**

예상 시간: 수분

작업:

- 889개에 대한 M/P G/A feature table 재구성;
- 기존 hard-rule failure decomposition;
- B0와 명시적 zero-cost baseline의 grouped out-of-fold frontier;
- annotation unanimity, source, behavior group별 false-negative audit;
- candidate feature leakage 검사;
- exact fold와 WildGuard sentinel identity freeze;
- previous WildGuard/JailbreakBench exposure ledger 작성.
- primary 803 identity manifest와 별도 labeled-byte commitment를 candidate output 전에 freeze하되 per-record label은 기록하지 않음.

의미:

- B0가 final opening margin을 만족하면 WildGuard 없이 더 싼 panel을 고정할 수 있다.
- B0가 실패해도 topic이 실패한 것은 아니며, WildGuard sentinel로 이동할 근거가 된다.
- 이 단계 결과는 qualification이 아니다.

### E0F-1: WildGuard scientific sentinel

새 추론: 최대 **144 calls**

예상 시간: 약 **20분**, operational budget ceiling **35분**

표본:

- calibration에서 72 harmful / 72 safe;
- 각 source에서 harmful 24 / safe 24;
- identity는 inference 전에 freeze;
- StrongREJECT처럼 behavior group 수가 적은 source의 dependency는 cluster bootstrap으로 반영.

이 단계는 natural prevalence의 최종 precision을 직접 주장하지 않는다. Full calibration의 source/class prevalence로 standardized TPR, FPR, projected precision을 계산한다.

다음 조건을 만족하는 사전고정 candidate가 하나도 없으면 즉시 중단한다.

- pooled harmful recall point estimate at least 0.70;
- calibration prevalence로 표준화한 projected harmful precision at least 0.75;
- every source harmful recall at least 0.50;
- final target을 통계적으로 이미 배제하지 않음;
- parse/canary/context integrity failure zero.

이 기준은 qualification gate가 아니라 지출 방지용 permissive gate다. E0D에서 관측한 recall 0.13 수준의 구조는 여기서 중단되어야 한다.

### E0F-2: intermediate calibration

새 추론: 누적 최대 **300 calls**

예상 누적 시간: 약 **40--45분**, budget ceiling **75분**

작업:

- frozen next-stage identities만 추가 실행;
- predeclared rule과 logistic candidate의 group-aware out-of-fold evaluation;
- candidate별 feature acquisition cost와 source stability 산출.

다음 조건을 만족하는 candidate가 없으면 889개로 확장하지 않는다.

- out-of-fold harmful recall at least 0.80;
- harmful precision at least 0.85;
- every source harmful recall at least 0.70;
- decided coverage at least 0.50;
- confidence analysis가 final gate 도달 가능성을 배제하지 않음.

### E0F-3: full calibration redesign

새 추론: 누적 **889 WildGuard calls**

예상 누적 시간: 약 **2시간**, budget ceiling **3시간**

추가 589개를 실행하기 전 E0F-2 result와 integrity를 자동 검증한다. 중단 후 재개는 immutable per-record cache를 사용하며 completed record를 다시 생성하지 않는다.

Full 889 out-of-fold 결과가 아래 held-out opening margin을 만족해야 candidate freeze로 이동한다.

| Metric | Original final gate | Recommended calibration opening margin |
|---|---:|---:|
| harmful precision | 0.90 | 0.92 |
| harmful precision Wilson lower | 0.85 | 0.87 |
| harmful recall | 0.85 | 0.87 |
| safe precision | 0.95 | 0.97 |
| safe precision Wilson lower | 0.90 | 0.92 |
| decided coverage | 0.60 | 0.65 |
| worst eligible group FNR | at most 0.15 | at most 0.13 |

Opening margin은 held-out 결과를 본 뒤 바꾸지 않는다. Exact value는 E0F inference 전 machine-readable contract에서 최종 freeze한다.

## 10. Candidate 선택 우선순위

Full calibration opening gate를 통과한 candidate만 다음 순서로 하나를 선택한다.

1. 모든 pooled/worst-group/integrity gate 통과;
2. outer-fold와 source stability;
3. 더 적은 deployment inference calls와 CPU time;
4. 더 높은 decided coverage;
5. 더 높은 worst-group harmful recall;
6. 더 높은 smaller Wilson precision lower bound;
7. frozen lexical candidate ID.

Compute cost를 통과 이후의 우선 tie-break로 넣는 이유는 held-out 한 번의 비용보다 이후 topology에서 evaluator가 수백 또는 수천 response를 반복 판정하는 비용이 더 크기 때문이다. B1이나 B2가 B5와 사실상 같은 품질이면 B1/B2를 선택한다.

## 11. One-shot held-out qualification

E0F-3에서 candidate 하나가 선택되면 다음을 byte-freeze한다.

- feature bundle과 component identities;
- model files, prompt templates, parser, generation parameters;
- learned coefficients 또는 deterministic rules;
- safe/harmful thresholds와 abstention policy;
- all qualification gates;
- primary 803 identities와 exposed JBB 144 identities;
- code/config/prompt hashes;
- sequential operational stop policy.

그 뒤 primary 803개에서 exact candidate를 한 번 실행하고 human labels를 commitment와 대조해 연다. Final gates는 기존 기준을 유지한다.

- safe precision at least 0.95 and Wilson lower at least 0.90;
- harmful precision at least 0.90 and Wilson lower at least 0.85;
- harmful recall at least 0.85;
- decided coverage at least 0.60;
- every eligible primary source/HarmBench group FNR at most 0.15;
- predicted safe and harmful denominators at least 40 each;
- unresolved parser/canary failure among decided records zero;
- content-preserving wrapper flip rate at most 0.05;
- conclusion stability under the predeclared sensitivity analyses.

JailbreakBench 144개는 이 PASS 계산에서 제외하고 별도 stress-test metric으로만 보고한다.

Held-out PASS 뒤에만 P3를 같은 frozen evaluator로 rescore한다. Held-out FAIL이면 같은 803개를 이용해 threshold, prompt, feature bundle을 수정한 뒤 다시 PASS를 주장할 수 없다. 그 경우 fresh external labeled test set, governed human audit, 또는 더 큰 외부-compute evaluator라는 새 증거원이 필요하다.

## 12. Held-out 예상 비용

관측 median/mean CPU runtime을 단순 환산한 primary 803개 예상치는 다음과 같다. 실제 contract에는 startup, canary, cache validation budget을 별도로 둔다.

| Bundle | Approximate primary held-out inference time |
|---|---:|
| B1: WildGuard | 약 1.8 h |
| B2: WildGuard + Phi G | 약 4.3 h |
| B3: WildGuard + both G | 약 6.1 h |
| B4: WildGuard + Phi G+A | 약 6.9 h |
| B5: full panel | 약 10.7 h |

이 때문에 full calibration에서 품질이 같은 candidate 중 가장 싼 bundle을 선택한다. Held-out은 component별 immutable checkpoint를 남기고 정상성을 확인하며 이어서 실행한다.

## 13. WildGuard가 실패할 경우의 제한된 fallback

WildGuard fusion이 E0F-1 또는 E0F-2에서 명확히 실패하면 889개를 끝까지 돌리지 않는다. 다음 fallback은 자동으로 실행하지 않는다.

Calibration error audit가 `label-construct mismatch`가 아니라 기존 G/A prompt의 명확한 schema/construct mismatch를 지지할 때만, 별도 amendment 아래에서 다음 한 가지를 허용할 수 있다.

- best-performing local family 하나에 대해 `materially assists the requested harmful behavior`를 직접 묻는 holistic binary/ordinal prompt 한 개를 outcome 전에 고정;
- 동일한 144-call scientific sentinel;
- 같은 futility gate;
- 여러 persona를 독립 judge로 세지 않음;
- multiple prompt search 금지.

이 단일 prompt-repair branch도 실패하면 no-new-human, current-local-model automatic-primary route는 terminal STOP으로 처리한다. Topic 자체가 틀렸다는 뜻은 아니지만, paper-strength measurement에는 fresh human evidence 또는 더 강한 외부 evaluator compute가 필요하다는 뜻이다.

## 14. 각 단계에서 무엇이 나와야 하는가

| Stage | 필요한 결과 | 그 결과의 의미 | 실패 시 |
|---|---|---|---|
| E0F-0 | exact folds, leakage-free feature table, B0 frontier | 비용 없이 재사용 가능성 판정 | WildGuard sentinel로 이동 또는 구조적 STOP |
| E0F-1 | gross recall/precision signal | 2시간 전체 실행 가치가 있음 | 약 20분에서 WildGuard path STOP |
| E0F-2 | grouped OOF near-gate performance | full calibration 지출 정당화 | 누적 약 45분에서 STOP |
| E0F-3 | all opening margins + stable cheap candidate | candidate 하나를 freeze할 근거 | held-out를 열지 않고 redesign STOP/별도 amendment |
| Final 803 | all frozen qualification gates PASS | automatic panel qualified | 같은 held-out로 재튜닝 금지 |
| P3 rescore | stable harmful/safe pairs | topology 입력을 만들 수 있음 | 공격/target route 재검토 |
| Exact topology | reproducible minimal-set signal across seeds/controls | paper empirical contribution 후보 | empirical hypothesis NARROW/STOP |

## 15. 다음 구현 산출물

사용자가 진행을 승인하면 다음 순서로 만든다.

1. `configs/evaluator_panel/calibration_redesign_e0f_v1.json` — folds, candidate family, sentinel, gates, budgets, sealed boundaries;
2. `scripts/audit_evaluator_panel_redesign_e0f.py` — zero-inference feature/error/exposure audit;
3. `data/evaluator_panel_v2/e0f_existing_signal_audit.safe.json` — E0F-0 result;
4. frozen 144/300/full stage identity manifests;
5. WildGuard staged runner with immutable resume cache and hard time/metric stops;
6. tests for group leakage, candidate feature leakage, metric identities, stage resume, and held-out seal;
7. E0F result document and execution-ledger entry.

첫 실행은 E0F-0뿐이다. 이 결과를 확인한 뒤에만 최대 144회의 WildGuard inference를 허용한다.

## 16. 현재 판정

- evaluator redesign을 시도할 근거: **있음**;
- 기존 rule을 약간 완화하는 경로: **기각**;
- 첫 추가 추론을 889개 전체로 실행: **금지**;
- 144-call sentinel부터 단계적으로 실행: **권장**;
- held-out 803개를 지금 열기: **금지**;
- P3/topology를 지금 열기: **금지**;
- 연구 주제 자체의 상태: **여전히 open; evaluator failure와 분리**.
