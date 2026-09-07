# P1 Exact Topology Engine Gate Result v1

Date: 2026-08-31 (Asia/Seoul)

Decision: **PASS**

Evidence class: **PROTOCOL_IMPLEMENTATION**

Paper validity: **FALSE**

## 1. 이 단계가 확인한 것

P1은 harmful target output 없이 다음 질문만 검증했다.

> 결과를 보기 전에 고정한 attack-unit vocabulary에 대해 모든 subset을 완전하게 표현하고, payload·입력 유효성·capability 조건을 위반한 사례를 recovery에서 제외하면서 모든 strict-subset-minimal recovery set을 정확히 구할 수 있는가?

답은 synthetic oracle 범위에서 **예**다.

## 2. 구현된 기능

### Frozen input boundary

- immutable payload와 attack-added unit을 별도 schema로 표현;
- 한 unit이 prefix/suffix처럼 여러 disjoint span을 소유할 수 있음;
- unit 간 overlap과 payload overlap 차단;
- payload exactly-once와 byte identity 검사;
- unit order와 vocabulary version 고정.

### Complete exact oracle

- empty baseline을 포함한 모든 2^m subsets 열거;
- neutralizer × seed observation matrix 완전성 검사;
- duplicate, unknown unit, unexpected seed/neutralizer 차단;
- seed 사이에 edited-prompt hash가 달라지는 경우 차단;
- monotonicity를 가정하지 않음;
- 모든 recovered set과 모든 strict-subset-minimal set 열거;
- non-monotone witness 보존;
- singleton, pure pair, multiple minimal pathway 구분.

### Minimality validity

중요한 구현 보정이 추가되었다.

어떤 recovered candidate의 strict subset이 실제 NOT_RECOVERED가 아니라 다음 중 하나라면 candidate를 minimal로 확정하지 않는다.

- INVALID_INTERVENTION;
- TRUNCATED;
- CAPABILITY_CONFOUNDED;
- ABSTAINED;
- INCOMPLETE.

이런 candidate는 unresolved_minimal_candidates로 분리한다. 따라서 malformed subset을 실패로 간주해 더 큰 집합을 거짓 minimal set으로 보고하는 문제가 차단된다.

### Intervention validity

- deletion neutralizer;
- layout-preserving blank neutralizer;
- payload occurrence와 byte identity;
- prompt non-empty와 null-character 검사;
- optional same-length validator;
- invalid intervention, truncation, capability confound, abstention의 명시적 상태.

### Safe and resumable records

- execution identity는 instance, subset, neutralizer, seed, model identity, edited-prompt hash에 결합;
- 동일 execution key의 중복 generation 방지;
- atomic per-record write;
- interrupted write에서 private source로 safe hash record 복구;
- 같은 key의 conflicting response 차단;
- private artifact에는 raw prompt/response, safe artifact에는 hash·길이·label만 기록.

## 3. 검증 결과

| 검증 | 결과 |
|---|---:|
| P1 focused tests | 19 passed |
| 전체 repository CPU regression | **265 passed** |
| Ruff | **PASS** |
| mypy | **47 source files, no issues** |
| machine-readable safe self-checks | **10/10 PASS** |

검증된 synthetic 구조:

- singleton recovery;
- pure pair interaction;
- multiple minimal pathways;
- non-monotone recovery;
- immediate subset만이 아닌 모든 strict subset minimality;
- neutralizer disagreement;
- incomplete matrix;
- invalid payload/input;
- decision-relevant truncation;
- capability confound;
- abstention;
- recovered empty baseline rejection;
- private/safe separation;
- resume deduplication.

Machine-readable result:

- [p1_gate.safe.json](../data/natural_language_localization/topology_engine_p1_v1/p1_gate.safe.json)
- result identity: 360427235f8954723cb6de4d001f12d4fb541285301096d5b15dd220b5c6d2f4

Frozen implementation contract:

- [topology_engine_p1_v1.json](../configs/natural_language_localization/topology_engine_p1_v1.json)

## 4. 재사용과 교체

재사용:

- 기존 TextSpan;
- 기존 neutralizer protocol과 deterministic span replacement;
- canonical hash와 atomic file pattern;
- 과거 Gate 1 oracle의 subset/minimal-set 설계 교훈.

새로 교체·보강:

- singleton-only ExhaustiveAtomicSearch를 paper oracle로 사용하지 않음;
- 과거 script-local minimal_sets를 현재 scientific authority로 사용하지 않음;
- scalar refusal mean 대신 categorical recovery policy 사용;
- incomplete/confounded strict subset을 단순 실패로 처리하지 않음.

과거 코드는 삭제하지 않았으며 historical/legacy baseline으로 남아 있다.

## 5. 실행 중 발견한 operational issue

첫 validator 실행은 global Python이 과거 clone의 editable jbspan package를 먼저 import해 실패했다. 과학 코드나 gate failure는 아니었다.

수정:

- pytest가 현재 저장소의 src를 우선하도록 pyproject에 pythonpath 추가;
- P1 validator가 자신의 현재 repository src를 명시적으로 우선;
- plain python -m pytest가 현재 저장소에서 정상 동작함을 전체 regression으로 확인.

남은 조치:

- P2 전에 현재 저장소 전용 virtual environment를 동결;
- model/runtime script도 import origin을 assert;
- 과거 clone은 자동 삭제하지 않음.

## 6. 이 PASS의 의미

말할 수 있는 것:

> 현재 연구 질문을 측정하기 위한 exact finite-vocabulary topology engine이 harmless synthetic truth tables에서 정의대로 작동한다.

말할 수 없는 것:

- 실제 jailbreak에 non-singleton topology가 존재함;
- 특정 attack family가 성공함;
- local Q4 model이 실행 가능함;
- paper contribution이 실험적으로 확인됨;
- canonical BF16 또는 다른 모델로 일반화됨.

## 7. Sealed boundaries

- target model called: false;
- harmful payload used: false;
- attack success observed: false;
- topology outcome observed: false;
- held-out opened: false;
- paper-valid confirmation opened: false;
- keep-only oracle opened: false;
- wavelet used: false.

## 8. 다음 허용 단계

> **P2 — freeze and run local Q4 harmless runtime qualification.**

P2는 모델 load, identity, chat template, deterministic seed, VRAM/RAM, throughput, resume만 확인한다. 공격 성공이나 topology output은 아직 열지 않는다.

