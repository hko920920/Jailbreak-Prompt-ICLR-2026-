# Current Research Scope and Contribution Freeze v3

Date: 2026-08-31 (Asia/Seoul)

Status: **TOPIC FIXED / METHOD CONTRACT FIXED IN PRINCIPLE / EMPIRICAL HYPOTHESIS OPEN / NO PAPER-VALID RESULT**

This document is the current authority for the paper question and claim boundary. It narrows the broader formulations in [PROJECT_CHARTER.md](PROJECT_CHARTER.md), [JAILBREAK_CAUSAL_TOPOLOGY_FORMALIZATION_V1.md](JAILBREAK_CAUSAL_TOPOLOGY_FORMALIZATION_V1.md), and [PAPER_SCOPE_DECISION_V2.md](PAPER_SCOPE_DECISION_V2.md). Those files remain useful protocol history; they are not evidence that the hypothesis is true.

## 1. 한 문장으로 설명한 연구

> 이미 실제로 뚫린 jailbreak prompt에서 해로운 요청 원문은 그대로 둔 채, 공격자가 덧붙인 편집 가능한 부분 중 어떤 **최소 조합**을 무력화해야 안전 행동이 돌아오는지를 하나만 찾지 않고 **전부** 찾는다.

조금 더 정확히 쓰면 다음과 같다.

> For a fixed successful jailbreak with an immutable explicit harmful payload, enumerate every strict-subset-minimal set of predeclared attack-added, human-editable units whose direct text neutralization robustly removes substantive harmful assistance while preserving the payload, input validity, and general response capability across neutralizers, sampling seeds, full-response judgments, and independent human audit.

## 2. 무엇을 찾는 연구인가

성공한 공격 prompt를 다음 두 부분으로 나눈다.

- **Immutable payload:** 모델에 시키려는 명시적 harmful request. 실험 중 삭제하거나 고치지 않는다.
- **Attack-added units:** role-play, 가상 상황, 비거절 지시, 출력 형식, distractor, 최적화 suffix block 등 공격자가 추가한 부분. 결과를 보기 전에 유한한 단위 목록을 고정한다.

공격 단위 집합을 U, 그중 중립화할 조합을 S라고 하자. S가 recovery set이 되려면 두 개 이상의 고정된 neutralizer와 여러 seed에서 다음 조건을 모두 만족해야 한다.

1. substantive harmful assistance가 사전 정의한 기준 아래로 내려간다.
2. refusal 또는 safe redirection이 회복된다.
3. immutable payload가 byte-identical하게 정확히 한 번 남는다.
4. prompt가 깨지거나 잘려서 생긴 가짜 회복이 아니다.
5. 모델의 일반 응답 능력이 무너지지 않는다.
6. 자동 판정의 불확실성과 의견 불일치는 숨기지 않고 인간 감사로 보낸다.

S가 **strict-subset-minimal**이라는 뜻은 S 자체는 회복시키지만 S의 모든 진부분집합은 회복시키지 못한다는 뜻이다. 단조성을 가정하지 않으므로 크기가 하나 작은 부분집합만 확인해서는 안 된다.

우리가 말하는 “전부”는 다음의 제한된 의미다.

> 결과를 보기 전에 선언한 유한한 attack-unit vocabulary와 neutralizer family 안에서 모든 subset을 검사해 모든 minimal recovery set을 열거한다.

모든 가능한 자연어 수정, 모든 tokenizer 표현, 모든 모델에서의 보편적 원인을 전부 찾는다는 뜻이 아니다.

## 3. 이 연구가 아닌 것

- 가장 위험해 보이는 token 하나를 ranking하는 연구가 아니다.
- harmful payload 자체를 지워서 거절을 만드는 연구가 아니다.
- “어떤 조합으로 계속 뚫리는가”를 공격 생성 목적으로 탐색하는 연구가 아니다.
- removal 결과만으로 minimal sufficient attack set을 주장하지 않는다.
- input intervention만으로 model-internal mechanism을 규명했다고 주장하지 않는다.
- 새로운 jailbreak generator, evaluator benchmark, 또는 defense product가 핵심 기여가 아니다.

Minimal recovery set의 여집합이나 실패 패턴은 대체 경로를 암시할 수 있지만, 특정 단위 조합만 남겨도 공격이 충분하다는 주장은 별도의 keep-only 실험 없이는 하지 않는다.

## 4. 최종 연구 질문

### Primary RQ

고정된 성공 jailbreak에서 payload를 보존한 직접 text intervention으로 얻은 complete minimal-recovery family는 singleton dependence, genuine non-singleton interaction, multiple alternative recovery pathways, 또는 capability-confounded apparent recovery 중 어떤 구조를 보이는가?

### Secondary RQs

1. 단일 단위 중요도나 leave-one-out 방법은 complete minimal-recovery family를 얼마나 놓치는가?
2. recovery topology는 neutralizer와 seed를 바꾸어도 얼마나 유지되는가?
3. 공격 family와 target model이 달라졌을 때 어떤 결과가 반복되고 어떤 결과가 family-specific인가?
4. 정확한 coarse oracle을 기준으로 greedy 또는 group-testing approximation은 얼마나 완전하고 효율적인가?

## 5. 논문의 기여 후보

### C1 — 새로운 측정 대상

단일 중요도 순위나 하나의 greedy explanation이 아니라, 고정된 성공 공격의 **모든 robust strict-subset-minimal recovery set**을 instance-level hypergraph로 측정한다.

주요 출력은 다음과 같다.

- minimum recovery order;
- distinct minimal-set multiplicity;
- non-singleton interaction incidence;
- multiple-pathway incidence와 overlap;
- singleton/greedy baseline miss rate;
- neutralizer agreement와 seed stability;
- capability-confound 및 abstention rate.

### C2 — artifact-resistant validity contract

설명처럼 보이는 단순 prompt 파괴를 safety recovery로 세지 않도록 다음을 하나의 계약으로 묶는다.

- explicit payload immutability;
- attack-added human-editable units only;
- direct text intervention;
- at least two meaningful neutralizers;
- multiple sampling seeds;
- full-response behavioral labeling;
- malformed, truncation, and capability controls;
- strict-subset verification without a monotonicity assumption;
- independent blinded human audit for reported baselines and minimal sets.

### C3 — 반드시 실험으로 얻어야 하는 empirical contribution

C1과 C2는 task/protocol 기여다. ICLR급 empirical paper가 되려면 fresh confirmation에서 다음 중 적어도 하나가 반복적으로 나타나야 한다.

- singleton attribution이 놓치는 robust non-singleton recovery sets;
- 여러 distinct minimal recovery pathways;
- attack surface가 달라도 반복되는 sparse recovery bottleneck;
- family-specific topology가 model 사이에서 재현됨;
- exact topology가 singleton/greedy baseline보다 완전성 또는 안정성에서 의미 있게 우수함.

개발 사례 한두 개의 흥미로운 그림은 C3가 아니다. 이 신호가 나오지 않으면 주제의 아이디어는 유효해도 현재 논문 기여는 성립하지 않는다.

## 6. 근접 연구와 남는 차이

아래 판정은 2026-08-31 검색 기준이며 priority 보장이 아니다.

| 근접 연구 | 이미 차지한 영역 | 현재 주제에 남는 구체적 차이 |
|---|---|---|
| [LOCA](https://arxiv.org/abs/2605.00123) | 특정 jailbreak의 minimal, local, causal explanation과 interaction-aware internal activation patching | 입력 텍스트의 attack-added unit에 직접 개입하고, 하나의 greedy path가 아닌 모든 robust minimal recovery set을 열거 |
| [Beyond “I’m Sorry, I Can’t”](https://arxiv.org/abs/2509.09708) | SAE feature 최소 집합, nonlinear interaction, dormant/redundant features | internal-feature ablation이 아닌 payload-preserving text counterfactual과 complete recovery family |
| [Token Highlighter](https://ojs.aaai.org/index.php/AAAI/article/view/34943) | jailbreak-critical token gradient ranking과 embedding soft removal | 독립 token saliency가 아닌 typed unit 조합, full-response recovery, strict-subset completeness |
| [Mask-GCG](https://arxiv.org/abs/2509.06350) | GCG suffix token의 필요성·중복성과 learnable masking | 공격 효율화가 아닌 이미 성공한 prompt의 reverse intervention; 모든 minimal cut set과 neutralizer/capability contract |
| [Erase-and-Check](https://arxiv.org/abs/2309.02705) | systematic token erasure와 safety certification/defense | safety-filter certificate가 아닌 target-model behavioral recovery topology와 immutable payload |
| [Causal Analyst](https://www.ndss-symposium.org/ndss-paper/a-causal-perspective-for-enhancing-jailbreak-attack-and-defense/) | 37개 human-readable feature에 대한 population-level learned causal graph, attack/defense 응용 | 한 성공 instance의 predeclared units를 직접 개입해 완전한 minimal recovery family를 구함 |
| [Don’t Listen To Me](https://www.usenix.org/conference/usenixsecurity24/presentation/yu-zhiyuan) | universal jailbreak 구성요소의 ablation과 persona/non-refusal/detail 요소 분석 | one-at-a-time component importance가 아닌 모든 조합의 minimality, multiple pathways, robustness |
| [Compositional Jailbreaking](https://arxiv.org/abs/2605.15598) | 12개 mutator의 ordered-pair persistence, synergy, destructive interaction | 약한 공격 transformation의 조합 생성이 아니라 고정된 성공 prompt를 역방향 개입해 모든 recovery cut set을 찾음 |
| [CMOOF](https://www.techscience.com/cmc/v88n3/68066/html) | role/content/context/communication component space와 component ablation, 공격 성공·query 효율 최적화 | strategy template 공격 최적화가 아닌 instance-level complete robust recovery topology |
| [The Anatomy of a Prompt Injection](https://arxiv.org/abs/2608.07808) | carrier, delivery, concealment, context-break, privilege escalation, payload, return channel의 구조적 taxonomy | component labeling 자체가 아니라 outcome-linked intervention, minimality, robustness 실험 |
| [What Features in Prompts Jailbreak LLMs?](https://arxiv.org/abs/2411.03343) | 35개 공격법의 nonlinear, attack-specific latent prompt features | universal feature 주장이 아닌 fixed-instance editable-text recovery structure |
| [Concept-Based Abductive and Contrastive Explanations](https://arxiv.org/abs/2605.06640) 및 [Sufficient Input Subsets](https://proceedings.mlr.press/v89/carter19a.html) | 일반 XAI에서 minimal feature/concept explanations와 all-minimal enumeration | all-minimal enumeration 자체가 아니라 jailbreak-specific recovery object와 전체 validity contract의 결합 |

따라서 “구성요소를 나눈다”, “중요 token을 찾는다”, “interaction이나 redundancy가 있다”, “causal graph를 만든다” 중 어느 하나도 독립적인 novelty가 아니다. 현재 살아남는 후보는 다음의 **결합**이다.

> complete robust minimal-recovery hypergraph of a fixed successful jailbreak under direct, payload-preserving text interventions, within a predeclared finite intervention vocabulary, validated across neutralizers, seeds, full responses, capability controls, and human audit.

## 7. 금지 주장

현재 논문은 다음을 말하지 않는다.

1. 최초의 causal/minimal/local jailbreak explanation.
2. 최초의 jailbreak-critical token 또는 component 발견.
3. 최초의 compositional interaction/redundancy 발견.
4. 유일하고 참된 jailbreak 원인 규명.
5. 모든 자연어 edit에 대한 complete topology.
6. 한 quantized model 결과의 canonical BF16 또는 closed model 일반화.
7. removal-only evidence를 이용한 attack sufficiency.
8. distributed 구조를 full declared subset enumeration 없이 단정.
9. 자동 judge를 인간-equivalent ground truth로 취급.
10. 결과가 나오기 전의 무조건적인 “first” 또는 “state of the art”.

## 8. 무엇이 고정되고 무엇이 열려 있는가

| 항목 | 상태 |
|---|---|
| 연구 주제 | 고정 |
| primary object: all robust strict-subset-minimal recovery sets | 고정 |
| immutable payload와 attack-added-unit 경계 | 고정 |
| multi-neutralizer, multi-seed, full-response, capability, human-audit 원칙 | 고정 |
| exactness가 predeclared finite vocabulary에 상대적이라는 표현 | 고정 |
| non-singleton/multiple-pathway 현상이 실제로 존재함 | **열려 있음** |
| 어떤 attack family/model에서 반복되는지 | **열려 있음** |
| ICLR 기여가 충분한지 | **실험 gate에 조건부** |
| paper-valid empirical result | 없음 |

## 9. 프로젝트 판정

주제로서는 더 진행할 의미가 있다. 다만 현재 결정은 “논문 결론이 맞다”가 아니라 다음과 같다.

> **Topic fixed, protocol direction fixed, hypothesis open, contribution conditional.**

저장소의 다음 작업은 아이디어를 더 넓히는 일이 아니라, 정확한 recovery predicate와 all-subset oracle을 구현하고 작은 개발 실험에서 C3가 존재하는지 빠르게 판정하는 일이다.
