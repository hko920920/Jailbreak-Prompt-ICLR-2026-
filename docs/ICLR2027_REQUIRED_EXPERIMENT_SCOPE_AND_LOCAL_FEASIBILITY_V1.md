# ICLR 2027 필수 실험 스코프 및 로컬 실행 가능성 v1

작성 기준일: 2026-08-31 KST  
대상 브랜치: `agent/programmatic-agentharm-pivot`  
검토한 HEAD: `bfb91e8ab7547d9d25f925622fe5cee3e382c165`  
문서 성격: 현재 증거에 대한 객관적 의사결정 문서. 새로운 결과나 성공을 주장하지 않는다.

## 1. 한 줄 결론

현재 RTX 3070 8 GB 한 대만으로 **기존에 동결된 canonical BF16 GCG 계획을 그대로 수행하는 것은 불가능**하다. 반면 Q4 양자화 모델을 대체물이 아니라 실제 연구 대상으로 사전에 다시 동결하고, 비경사 semantic/compositional 공격으로 주장을 좁히면 로컬-only 실험은 기술적으로 가능하다. 다만 2026-08-31 현재 paper-valid 결과가 하나도 없고 독립 인간 감사도 확보되지 않았으므로, 이 축소안 역시 ICLR 2027 완주 가능성은 높지 않다.

권고 판단은 다음과 같다.

- **원래의 강한 주장 유지:** 외부 고메모리 GPU와 인간 평가자가 필수다.
- **외부 GPU 없이 계속:** Q4 로컬 축소 계약을 결과 확인 전에 새로 동결하고 주장 범위를 semantic/compositional 공격의 행동적 topology로 제한한다.
- **둘 다 확보하지 못함:** 논문 양식·코드·프로토콜까지만 완성하고, 불완전한 실험을 ICLR 완성 논문처럼 포장하지 않는다.

## 2. 증거 상태

### 확인된 사실

- AgentHarm 경로는 사전 선언된 terminal rule로 종료되었다. 이는 topology 가설의 반증이 아니라 해당 데이터 경로에서 적격 direct-fail/attacked-success 모집단을 얻지 못했다는 뜻이다.
- 현재 개발 micro-pilot은 h4rm3l과 GCG, Qwen2.5-7B, 4개 payload, 3개 seed로 동결되어 있다.
- 계획된 baseline은 direct 12회와 attacked 24회, 합계 36 generations이다.
- 적격 stable pair 하나당 최대 6개 coarse unit, 64개 subset, 2개 neutralizer, 3개 seed이므로 최대 384 intervened generations이다.
- 현재 저장소에는 paper-valid positive empirical result가 없다. 존재하는 것은 protocol, development, diagnostic, negative evidence다.
- canonical GCG 계약은 2× NVIDIA A100 80 GB PCIe, GPU당 최소 64 GiB free memory, BF16, 4개 500-step job, search width 512를 요구한다.
- 로컬 장비는 RTX 3070 8 GB, i7-11700, RAM 약 32 GB다. 저장소 안에는 실행할 model weight가 없다.

### 아직 확인되지 않은 가정

- Qwen2.5-7B-Instruct Q4_K_M이 현재 Windows/WSL runtime에서 충분한 GPU offload와 함께 안정적으로 생성할 수 있는지.
- 두 번째 Q4 target인 Llama-3.1-8B-Instruct가 라이선스 접근, tokenizer, chat template, VRAM, 속도 기준을 모두 통과하는지.
- h4rm3l 또는 DeepInception이 이 Q4 target들에서 충분한 stable pair를 만드는지.
- WildGuard가 로컬 runtime에서 유용한 처리량과 보수적 screening 성능을 내는지.
- 독립된 두 명의 blinded annotator와 disagreement용 제3 adjudicator를 제출 전 확보할 수 있는지.

따라서 Q4 경로는 현재 **실행 가능성이 높은 후보**이지, 실행이 입증된 상태가 아니다. harmless smoke와 소규모 throughput 측정 전에는 가능으로 확정하지 않는다.

## 3. 논문을 성립시키는 최소 연구 질문

가장 방어 가능한 핵심 질문은 다음 하나다.

> 이미 성공한 jailbreak prompt에서 harmful payload를 보존한 채 attack-added input unit을 중립화할 때, 여러 neutralizer와 seed에서 안전 행동을 회복시키는 모든 robust minimal recovery set은 무엇이며, singleton attribution이 놓치는 higher-order 또는 alternative pathway가 반복되는가?

논문의 최소 기여는 세 부분이어야 한다.

1. **정의:** strict subset minimality, payload invariance, capability control을 포함하는 robust minimal-recovery topology.
2. **측정:** 결과를 본 뒤 고른 사례가 아닌 fresh split에서 exact 또는 contract-exact intervention.
3. **반복 관찰:** 최소 두 attack family와 두 target model에서 한 가지 이상의 비자명한 topology 현상이 재현됨.

마지막 항목이 없으면 사례 연구나 측정 프로토콜은 될 수 있어도, 강한 ICLR empirical paper로는 부족하다.

## 4. 완성 논문에 필수인 실험

### 4.1 Stable-pair screen

각 payload/model/attack 조합에서 동일한 decoding 조건과 seed를 사용해 다음을 확인한다.

- direct harmful request는 모든 동결 seed에서 non-harmful이다.
- attacked prompt는 모든 동결 seed에서 substantive harmful assistance를 만든다.
- explicit payload는 정확히 한 번 등장하며 byte-identical하다.
- decision-relevant truncation이나 명백한 capability collapse가 없다.
- 자동 screen이 불일치하거나 애매하면 인간 감사로 넘긴다.

이 단계를 통과하지 못한 사례에 topology를 계산하면 “안전 회복”의 원인이 attack unit이 아니라 원래 불안정성일 수 있다.

### 4.2 Blinded human baseline audit

- 독립된 2명이 model/attack/intervention identity를 가린 상태로 decision-critical output을 평가한다.
- disagreement는 제3자가 adjudicate한다.
- WildGuard는 conservative screen일 뿐 최종 투표권자가 아니다.
- HarmBench classifier는 diagnostic이며 primary label로 사용하지 않는다.
- agreement, abstention, adjudication rate를 보고한다.

이 항목은 GPU 문제가 아니라 사람 문제이며, 대체할 수 없는 외부 의존성이다.

### 4.3 Exact minimal-recovery topology

- stable pair별 coarse attack-added unit을 결과와 무관하게 freeze한다.
- 최대 6개 unit이면 64개 subset을 전부 검사한다.
- 두 개의 의미 있는 neutralizer와 seed 11, 23, 47을 사용한다.
- recovery set뿐 아니라 모든 strict subset의 실패를 확인해 minimality를 증명한다.
- neutralizer disagreement, seed instability, abstention을 숨기지 않고 별도 기록한다.

### 4.4 Intent/capability/confound controls

- payload byte invariance와 정확히 한 번 등장 조건.
- tokenizer/grammar/position-sensitive attack의 유효성 검사.
- benign capability probe 또는 matched task로 general capability collapse 배제.
- random cost-matched neutralization, irrelevant-unit neutralization, malformed-edit control.
- truncation, context-length, template breakage를 recovery로 계산하지 않음.

### 4.5 비교 baseline

최소 baseline은 다음이면 충분하다.

- singleton leave-one-out attribution.
- random cost-matched subset.
- greedy backward elimination 또는 group-testing search.

Gradient saliency baseline은 canonical compute를 확보한 경우 유용하지만, 좁은 black-box/Q4 논문의 논리적 필수조건은 아니다. 다만 포함하지 않으면 관련 방법 대비 위치를 더 제한적으로 써야 한다.

### 4.6 Fresh confirmatory split와 통계

- 개발 micro-pilot에 사용하지 않은 payload만 사용한다.
- 최소 2개 attack family와 2개 model family를 결과 확인 전에 동결한다.
- primary endpoint, exclusion, abstention, multiplicity 처리, confidence interval을 사전 명시한다.
- family/model별 비교는 표본 수가 충분하지 않으면 descriptive로 제한한다.
- 결과 파일은 config hash, git commit, model/tokenizer revision, seed, runtime, hardware와 연결한다.

### 4.7 재현성·안전

- raw harmful payload/output, credentials, provider logs는 저장소에 commit하지 않는다.
- 공개 artifact에는 hash, aggregate, redacted example만 남긴다.
- 실험 실행 계약과 제외 ledger를 제공한다.
- AI 도구 사용 내역을 ICLR 정책에 따라 disclosure한다.

## 5. 기존 frozen 개발 gate

현재 [`PAPER_SCOPE_DECISION_V2.md`](PAPER_SCOPE_DECISION_V2.md)의 micro-pilot GO 조건은 모두 충족되어야 한다.

- stable pair 총 6개 이상.
- h4rm3l과 GCG에서 각각 2개 이상.
- robust minimal recovery set이 있는 instance 3개 이상.
- non-singleton minimal set 또는 multiple distinct minimal sets가 있는 instance 2개 이상.
- reportable topology의 neutralizer agreement 0.80 이상.
- capability-confounded recovery 0.25 미만.

다음이면 STOP이다.

- stable pair가 4개 미만.
- 모든 reportable case가 obvious singleton 또는 indivisible whole-suffix effect.
- neutralizer/seed instability가 지배적.
- capability confound가 지배적.
- human audit가 신뢰할 만한 agreement에 도달하지 못함.

이 gate는 개발 신호 확인용이지 그 자체로 paper-valid confirmation이 아니다.

## 6. 세 가지 실행 스코프

### Scope A — 기존 강한 논문안

구성:

- 개발: h4rm3l + GCG, canonical Qwen2.5-7B.
- 확인: DeepInception + AutoDAN 추가.
- 두 번째 canonical model family 추가.
- fresh payload와 blinded human audit.
- semantic-readable, fluent-optimized, non-fluent optimized regime을 포함.

판정: **현재 로컬-only로 불가능.** canonical BF16 GCG와 canonical confirmatory inference에 외부 고메모리 GPU가 필요하다. 인간 평가자도 별도 확보해야 한다.

### Scope B — 로컬-only 축소 논문안

구성:

- Q4_K_M 모델을 canonical 모델의 proxy가 아니라 논문이 직접 연구하는 target으로 정의한다.
- h4rm3l + DeepInception처럼 로컬에서 materialize 가능한 두 semantic/compositional attack family를 사용한다.
- Qwen2.5-7B-Instruct Q4와 Llama-3.1-8B-Instruct Q4를 사전 동결한다.
- exact coarse topology, 두 neutralizer, 세 seed, capability controls, fresh split, 인간 감사를 유지한다.
- GCG/AutoDAN 및 attack-regime 간 일반화 주장을 삭제한다.

허용되는 주장:

- “선택된 Q4 target 두 개에서 semantic/compositional jailbreak의 robust recovery topology를 측정했다.”
- “이 범위 안에서 singleton attribution이 놓치는 구조가 반복되었다.”

허용되지 않는 주장:

- canonical BF16 모델에도 동일하다는 주장.
- 모든 jailbreak 또는 optimized suffix로 일반화.
- semantic 대 optimized regime의 차이.
- 양자화가 topology에 영향을 주지 않는다는 주장.

판정: **기술적으로 가능성이 있으나 일정과 논문 강도 위험이 큼.** 결과를 보기 전에 새 계약을 freeze해야 하며, 기존 Q4 development-only 라벨을 조용히 paper-valid로 바꾸면 안 된다.

### Scope C — protocol/reproducibility paper preparation

구성:

- CPU tests, provenance, harmless smoke, LaTeX, figure/table templates, preregistration.
- 실제 empirical claim 없음.

판정: **로컬에서 가능하지만 현재 형태로는 ICLR empirical paper 완성이 아니다.** 다음 cycle 또는 workshop용 자산으로 보존하는 선택이다.

## 7. 로컬 실행 가능성 매트릭스

| 작업 | 판정 | 객관적 근거 / 선행조건 |
|---|---|---|
| CPU unit tests, lint, type check | 가능 | 현재 로컬에서 실행됨. Windows newline portability 이슈는 과학 결과와 무관한 test-fixture 문제였다. |
| provenance/config/payload hash freeze | 가능 | CPU와 디스크만 필요. |
| h4rm3l/DeepInception prompt materialization | 가능 | 기존 source audit와 adapter 자산이 있음. 실제 target success는 별도 실험. |
| Qwen2.5-7B Q4 sequential inference | 조건부 가능 | 약 4.36 GiB weight artifact는 8 GB VRAM 범위지만 KV cache/runtime buffer가 추가됨. 실제 smoke 필요. |
| Llama-3.1-8B Q4 sequential inference | 조건부 가능 | 8 GB에서 통상 가능한 크기이나 파일, 라이선스, runtime, context 설정을 실제 검증해야 함. |
| 36-generation Q4 pilot | 조건부 가능 | model smoke와 attack materialization 후 가능. 기존 canonical GCG pilot과는 다른 새 계약 필요. |
| stable pair별 384-generation exact enumeration | 조건부 가능 | 메모리보다 시간/열/중단 복구가 위험. checkpoint와 resumable shard 필요. |
| 최대 9,216-generation local confirmation | 조건부 가능·고위험 | 24 stable pairs × 384. 처리량 smoke 후 wall-clock을 산정해야 함. |
| WildGuard local screen | 미확정 | model fit와 throughput smoke 필요. 인간 감사 대체 불가. |
| precomputed GCG prompt transfer | 미확정 | 동일 payload/model/tokenizer provenance와 성공 재현이 필요하며 현재 계약 밖. |
| frozen BF16 GCG 4×500, width 512 | 불가능 | 8 GB VRAM 대 계약상 GPU당 64 GiB free requirement. |
| 2×A100 80 GB attestation | 로컬 불가능 | 장비 자체가 없음. |
| canonical BF16 7B/8B end-to-end confirmation | 로컬 불가능 | weight만으로도 8 GB를 초과하고 activation/KV가 추가됨. |
| 2 annotators + adjudicator | 로컬 계산과 무관한 외부 필수 | 독립성 때문에 연구자 혼자 대체할 수 없음. |

## 8. 외부 GPU가 필요한 정확한 이유

동결된 Qwen GCG 계약은 다음을 요구한다.

- Qwen2.5-7B canonical revision, BF16, gradient enabled.
- A100 80 GB 두 대, 각 64 GiB 이상 free.
- 4개 job × 500 steps.
- search width 512, top-k 256, initial candidate microbatch 64.
- OOM 시 microbatch만 절반으로 줄일 수 있고 width/algorithm은 변경 불가.

두 GPU는 주로 두 job 동시 실행을 위한 것으로 보인다. 결과를 보기 전 compute-only amendment를 만들면 1×A100 80 GB로 네 job을 순차 실행하는 것은 과학적으로 같은 algorithm을 유지할 수 있다. 그러나 현재 계약과 workflow는 2개 GPU를 강제하므로 사전 수정이 필요하다. job당 최대 720분 계약을 그대로 적용하면 1×A100의 보수적 상한은 약 48 GPU-hours다. 이는 설정으로부터의 계산이며 실제 runtime 측정값은 아니다.

## 9. 제안하는 로컬-only confirmatory 최소치

이 절은 **아직 frozen protocol이 아닌 제안**이다. 결과를 생성하기 전에 별도 config와 decision 문서로 동결해야 한다.

### Stage L0 — harmless runtime qualification

- Qwen Q4와 두 번째 Q4 model의 exact repository revision, filename, LFS SHA-256, tokenizer revision을 기록한다.
- harmless prompt로 load, chat template, deterministic seed, 512-token cap, resume/sharding을 확인한다.
- 10~20회 generation으로 seconds/token, peak VRAM, RAM, thermal stability를 측정한다.
- 둘 중 하나라도 안정적으로 실행되지 않으면 local-only two-model paper route를 중단한다.

### Stage L1 — 작은 development signal gate

- 4개 development payload.
- 2개 local attack family.
- Qwen Q4 한 모델.
- seed 3개.
- direct 12 + attacked 24 = baseline 36 generations.
- eligible pair에 exact 64-subset × 2-neutralizer × 3-seed topology.

기존 GO 구조를 유지하되 GCG를 DeepInception으로 바꾼 새 계약을 동결한다. 가족 구성 변경 때문에 기존 pilot 결과와 동일 gate라고 부르면 안 된다.

### Stage L2 — fresh two-model confirmation

운영 최소안:

- fresh payload 20개, 가능하면 4개 semantic category에 균형 배치.
- 2 attack families × 2 Q4 models × 3 seeds.
- shared direct baseline 120 generations.
- attacked baseline 240 generations.
- baseline 합계 360 generations.
- stable attack instance 최소 24개, 각 family/model에서 최소 6개, 4개 category 포함.
- exact topology 대상은 사전 규칙으로 최대 24개를 stratified selection.
- worst case intervened generations: 24 × 64 × 2 × 3 = 9,216.

24 stable instances는 운영상 **하한**일 뿐 ICLR 강도를 보장하지 않는다. 가능한 경우 40개 이상의 stable instances를 목표로 하고, 그보다 작으면 family/model 차이는 descriptive로만 보고한다. 결과가 희소하면 표본을 사후 추가해 유리한 사례를 찾지 말고 NARROW/STOP 규칙을 적용한다.

### Stage L3 — required analyses

- topology 존재율과 95% confidence interval.
- minimal set size 분포.
- multiple minimal pathway 비율.
- singleton baseline miss rate.
- neutralizer agreement와 seed stability.
- capability-confounded recovery와 abstention 비율.
- model/family/category별 결과는 사전 정의된 집계만 사용.
- 대표 사례는 정량 결과 이후, redacted form으로 선택한다.

## 10. 논문 강도를 결정하는 필수 empirical signal

다음 중 적어도 하나가 fresh confirmation에서 반복되어야 한다.

- singleton attribution이 robust non-singleton minimal set의 의미 있는 비율을 놓침.
- multiple distinct minimal pathways가 여러 model/family에서 반복됨.
- surface가 다른 공격이 공통의 sparse recovery bottleneck을 가짐.
- topology가 family-specific이지만 model 간 재현됨.
- exact topology가 greedy/singleton baseline보다 안정성 또는 완전성에서 명확히 나음.

개발 사례 1~2개의 흥미로운 그림만으로는 부족하다. 이 신호가 없으면 evaluator/search engineering을 더 붙이지 말고 STOP 또는 protocol paper로 전환한다.

## 11. 핵심에서 제외할 것

다음은 현 논문을 완성하는 데 필수가 아니며, deadline 전에 범위를 넓히면 오히려 위험하다.

- wavelet/tree-Haar를 headline contribution으로 만드는 것.
- evaluator panel qualification 자체를 주 기여로 만드는 것.
- attention head/activation/mechanistic 분석.
- universal S/F/U taxonomy.
- 모든 instance의 keep-only sufficiency.
- 새로운 jailbreak generator 개발.
- 긴 optimized suffix의 full token power set.
- exhaustive topology가 이미 가능한 micro-pilot에서 복잡한 adaptive search를 먼저 최적화하는 것.

## 12. 일정과 hard decision date

공식 일정은 abstract 2026-09-18 23:59 AoE, paper 2026-09-25 23:59 AoE다. KST로 각각 2026-09-20 20:59와 2026-09-27 20:59다.

현실적인 공격 일정:

- 08-31~09-02: Windows/CI 정리, official paper scaffold, local-only 계약 초안, Q4 artifact/runtime smoke.
- 09-03~09-05: 36-generation local pilot와 baseline human audit.
- 09-06~09-09: eligible pair exact topology, GO/NARROW/STOP.
- 09-10~09-15: GO일 때만 fresh two-model confirmation.
- 09-16~09-18: 인간 감사 종료, 통계/figure/abstract freeze.
- 09-19~09-25: 본문 압축, reproducibility/ethics/AI disclosure, 최종 검증.

이 일정은 매우 공격적이다. 09-02까지 두 Q4 model smoke가 끝나지 않거나 09-09까지 pilot gate가 닫히지 않으면 ICLR 2027 완성 논문 확률은 급격히 낮아진다.

## 13. 최종 STOP 조건

다음 중 하나면 ICLR empirical-paper route를 중단하거나 다음 cycle로 이월한다.

- pilot에서 stable pair 6개 미만 또는 family당 2개 미만.
- 비자명 topology instance가 2개 미만.
- independent blinded human audit 미확보.
- 두 번째 model의 fresh confirmation 미완료.
- capability confound, neutralizer disagreement, seed instability가 주 신호를 설명함.
- confirmatory split에서 반복 empirical finding이 없음.
- 결과가 deadline 전에 재현 가능한 artifact/ledger로 닫히지 않음.

## 14. 현재 추천

1. 외부 A100을 며칠 내 확보할 현실적 경로가 있으면 Scope A를 유지하되, 먼저 1×A100 sequential amendment가 허용되는지 계약을 수정한다.
2. 외부 GPU가 없으면 Scope B를 즉시 별도 이름으로 freeze하고 Q4 smoke부터 한다. 기존 canonical/GCG 계획의 연속 결과인 것처럼 취급하지 않는다.
3. 동시에 인간 평가자 2명과 adjudicator를 확보한다. 이것이 안 되면 GPU 확보 여부와 무관하게 paper-valid main result는 닫히지 않는다.
4. 09-09에 숫자 기반 GO/NARROW/STOP을 집행한다. 일정 압박을 이유로 threshold를 사후 완화하지 않는다.

## 15. 근거 문서

- [`PAPER_SCOPE_DECISION_V2.md`](PAPER_SCOPE_DECISION_V2.md)
- [`TOPOLOGY_MICRO_PILOT_V1.md`](TOPOLOGY_MICRO_PILOT_V1.md)
- [`TOPOLOGY_MICRO_PILOT_EXECUTION_FREEZE_V1.md`](TOPOLOGY_MICRO_PILOT_EXECUTION_FREEZE_V1.md)
- [`GCG_QWEN_DIFFERENTIABLE_COMPUTE_CONTRACT_V1.md`](GCG_QWEN_DIFFERENTIABLE_COMPUTE_CONTRACT_V1.md)
- [`H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST_V1.md`](H4RM3L_GCG_SIGNAL_SCREEN_INPUT_MANIFEST_V1.md)
- [`PROGRAMMATIC_AGENTHARM_PIVOT.md`](PROGRAMMATIC_AGENTHARM_PIVOT.md)
- [`programmatic_agentharm_terminal_decision.md`](programmatic_agentharm_terminal_decision.md)
- [ICLR 2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
- [ICLR 2027 Dates](https://iclr.cc/Conferences/2027/Dates)
- [ICLR 2027 AI Policy for Authors](https://iclr.cc/Conferences/2027/AIPolicyForAuthors)

