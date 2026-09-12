# 2026-09-10 구현 준비 상태 조사

> 사실과 제안의 작업 기록이다. 승인 요구/설계 및 테스트 기준을 변경하지 않는다.

## Request Context

사용자는 세부값을 모두 직접 정하기보다 기존 상태를 확인한 뒤 이야기하자고 요청했다.
현재 checkout의 코드/테스트/설정과 실제 로컬 실행을 확인했다. 원래 worktree는 조사하지 않았다.

## SSOT Impact

r1 및 d3, p2를 기준으로 읽었다. 새 승인/제품 구현은 없음.
현재 기반에 이미 있는 결정은 재사용하고, 조사로 정할 수 있는 내용은 에이전트가 정리한다.
아래 제안은 사용자에게 모든 항목을 새로 선택하라고 요구하는 목록이 아니다.

## 확인 결과

### 1. 파일/모듈 경계

| 실제 경로 | 확인 내용 | 구현 계획 반영 제안 |
|---|---|---|
| `harness_core/state/pipeline.py`, `harness_core/state/__init__.py`, `harness_core/cli.py` | phase enum·approval bool·고정 전이·state CLI 결합 | 새 실행 계약/state API로 교체; CLI의 비-SDD 기능 분리 보존 |
| `harness_core/state/storage.py` | atomic JSON/fsync/flock | 내구성 기법/검사 재사용; 다중 이벤트 transaction은 SQLite로 새 구현 |
| `skills/sdd/runtime/moondex-runtime.py` | state 이외 verify/mapper/PR/self-improve/result-action 공통 launcher | SDD 제거 전 공통 launcher를 새 경로로 옮기고 모든 소비자 갱신 |
| `skills/code-mapper/SKILL.md`, `skills/pr-converge/SKILL.md`, `skills/self-improve/SKILL.md` | 위 SDD runtime을 직접 참조 | 독립 skill은 유지하고 공통 runtime 포인터 변경 |
| `skills/sdd`, `skills/sdd-orchestrator`, `skills/sdd-taskrunner` | 구형 workflow 지침/형식 | 구형 실행 지침 교체, 유용한 작업 계약만 새 workflow에 반영 |
| `skills/sdd-orchestrator/scripts/result-action.py` | 구형 controller 의존 및 raw snapshot sync | 새 evidence 기반 result/sync로 교체; raw 읽기 전용 준수 |
| `scripts/adapter_render.py`, `harness_core/enforcement`, `harness_core/validation`, `harness_core/pr`, `harness_core/learning` | redaction·검증·독립 PR/학습 기반 | 무조건 삭제하지 않고 해당 계약의 유효한 회귀검사 유지 |
| `hooks/enforcement/stop-pipeline.py` | 구형 단계/role 호출 지침이 남아 있음 | 새 workflow를 옛 phase로 돌리지 않도록 optional hook 진입점도 점검 |
| `skills/ACTIVE_SURFACE.json`, runtime inventory, 설치 테스트, AGENTS/README | 경로와 포함 파일 목록이 서로 연결 | I6에서 함께 갱신; installed dependency closure 검증 |

이 목록은 소스 검색에 따른 직접 의존성 지도이며 전체 call graph 증명은 아니다.
구형 state 파일을 새 승인으로 읽지 않고 과거 기록은 보존한다.

### 2. 작업 순서

p2의 I1→I6 순차 기반은 유지 가능하다. 추가로 먼저 해결할 검증 준비 작업 I0가 드러났다.

- I0: fixture 준비 누락과 CI CLI 불일치를 재현 가능한 테스트로 정리·복구한다.
  입력은 아래 실제 실패 로그, 산출물은 clean checkout에서 재현되는 fixture setup과 CI 명령 검증이다.
  기대 assertion을 완화하지 않는다. 정확한 fixture 내용은 요구와 oracle을 읽고 복원해야 한다.
- I1: 기준/승인/DAG 계약.
- I2: 저장·이벤트·스케줄링·중단 후 재개.
- I3: 실제 command runner·증거·통합 gate.
- I4: Orca adapter와 실제 end-to-end 실행.
- I5: 결과와 Compound 기록.
- I6: 구형 실행 경로 교체·공통 launcher 이동·패키징·회귀/설치 검증.

공통 계약과 경로에 의존하므로 지금은 병렬 분할보다 순차 구현이 합리적이다.
상세 수정 파일/완료 증거는 이 지도와 기존 테스트를 기준으로 에이전트가 채울 수 있다.

### 3. 실제 검증 기반

- Python 3.12.3, pytest 9.1.1, SQLite 3.51.0. Chrome executable 발견.
- `python3 -m pytest tests -q --durations=10`: **324 passed, 8 failed, 56.08s**, exit 1.
- 실패 4건은 `tests/e2e/test_codex_harness_acceptance.py`, 4건은 `tests/validation/test_preflight.py`.
- E2E config read/unlink 실패 및 preflight TDD/E2E evidence 누락이 직접 원인이다.
  fixture의 `.harness/state/` 입력 파일은 checkout과 tracked 목록에 없으며 `.gitignore`가 그 경로를 제외한다.
  과거 어떤 경로로 누락됐는지는 확인하지 않았다. 현재 fixture 준비가 불완전한 사실과 구분한다.
- `.github/workflows/moondex-verify.yml`은 `scripts/verify.py --source ci`와 원격 인자를 사용하지만
  현재 parser는 source를 explicit/worktree/hook만 허용한다. `--source ci`만으로 exit 2를 재현했다.
  hosted CI 전체를 실행한 것은 아니다.
- CI의 Python은 3.11이며 pytest 설치 단계가 명시돼 있지 않다. clean 환경 의존성 준비를 점검해야 한다.
- 독립 wheel/frontend build 설정은 조사한 pyproject/CI에 없었다. 이 plugin의 배포 검증은
  문법·manifest·inventory·opaque 설치 실행 검사를 중심으로 잡을 수 있다. 필수 gate를 N/A로 승인한 것은 아니다.
- `tests/test_installed_plugin_runtime.py`의 opaque-path/tamper 검사는 보존 가치가 있다.
  구형 phase 인접 전이 자체를 요구하는 `tests/state/test_pipeline.py` 일부와
  `_SoleWriterSimulation` 중심 구형 flow 검사는 새 사용자 결과 기준으로 교체해야 한다.

개발용 명령 후보(기존 제공 명령 기준): 전체 pytest, node별 해당 test 파일,
manifest JSON parse, 모든 hook의 개별 bash -n, Python compile, 설치 inventory/opaque-path 테스트.
기존 전체 테스트 56초는 미래 agent 작업이나 대형 E2E의 상한 근거가 아니다.

### 4. 복구/시간/사용량의 기존 상태

- 구형 state는 `MAX_RETRIES=3`이고 record_retry 호출마다 증가한다. 실제 작업 실행 전체를 감독하는 예산은 아니다.
- PR core에는 별도 `MAX_ITERATIONS=15`, `MAX_ATTEMPTS=3`가 있다. 실행 엔진 정책으로 자동 승계하지 않는다.
- 기본 config에는 knowledge_sync/ci/security만 있고 execution budget/time policy가 없다.
- PR adapter의 subprocess 실행 및 기존 consumer E2E 호출에는 호출 전체 timeout이 없다.
  browser 내부 poll/CDP timeout은 별도 목적이다.
- d1 추천 승인에 있는 기본 동시성 1과 자동 복구 2회는 유지할 근거가 있다.
- E1의 1 worker/0 retry/10분과 사용량 여유 답변은 그 실험 범위다. 제품 전체 상한으로 확대하지 않는다.

추천: 동시성 1과 복구 2회를 출발점으로 두고, 정상 장기 작업은 상태를 관찰한다.
정확한 token/금액 telemetry 없이 금액 상한을 보장하지 않는다. 계획을 막기 위해 모든 숫자를
지금 사용자에게 요구할 필요는 없다. 구현용 gate와 agent 작업이 구체화되면 근거 있는 한도안을 제시한다.
기준 충돌·권한 부족·재시도 소진 등 판단이 필요한 예외만 사용자에게 요청한다.

## Verification

원본 로그/receipt: `.harness/audit/implementation-readiness/`.
`pytest-receipt.json`의 exit_code가 실제 pytest 결과이며, 로그 보존 wrapper의 정상 종료와 구분한다.
Browser 독립 실행: 처음 repo root cwd로 실행해 404에 해당하는 DOM 미도달 실패가 났다.
runner가 cwd 기준 `/tests/panel_runner.html`을 제공하는 것을 확인하고 fixture root로 바로잡았다.
`cd tests/fixtures/e2e_sample_project && python3 tests/consumer_panel_e2e.py`는
Chrome/152.0.7977.83에서 PASS, 약 1.51초였다. 첫 실패는 조사 명령의 cwd 오류이며 제품 결함으로 분류하지 않는다.
이는 browser runner 자체의 실행 가능성만 확인하며 누락 config를 사용하는 전체 E2E 실패를 해소하지 않는다.
제품 파일/테스트 기대값은 변경하지 않았다. status/resume은 no project-local state이며 legacy start/transition은 하지 않았다.

## Residual Gaps

fixture 복구와 CI 수정은 아직 수행하지 않았다. 이번 요청은 기존 상태 조사다.
전체 테스트가 현재 green이라고 주장하지 않는다. 사용자에게 필요한 것은 전체 세부 설계 작성이 아니라
조사 결과를 바탕으로 정리된 수정안의 핵심 판단이다.

## 후속 조사: 스킬 전체 정리와 재작성 대안

사용자가 스킬 의존성 개선·불필요 스킬 제거도 범위에 포함하자고 요청했고,
수정이 너무 크면 전체 삭제 후 제로베이스 시작도 가능하다는 선택지를 제시했다.
이것은 구체 삭제 목록 확정이나 파일 삭제 실행으로 해석하지 않았다.

현재 `skills/*/SKILL.md`는 13개다. 직접 공통 launcher를 사용하는 비-SDD 스킬은
code-mapper, pr-converge, self-improve다. 세 adapter의 core import는 각각
harness_core.code_mapper, harness_core.pr, harness_core.learning이며 SDD phase controller를 직접 import하지 않는다.
따라서 세 기능이 SDD phase 실행을 필수로 요구하는 것과 launcher가 SDD 폴더에 있는 문제는 구분한다.
다만 pr-converge의 입력 의미에는 spec/design alignment가 있어 새 승인 revision 계약으로 수정이 필요하다.

| 스킬 | 현재 역할/연결 | 추천 검토 방향 (미확정) |
|---|---|---|
| sdd, sdd-orchestrator, sdd-taskrunner | 고정 단계·AI 실행 루프·구형 task template | 새 실행 workflow로 교체 |
| code-mapper | graph probe/근사 검색, SDD launcher 경로 참조 | 분석 capability 재사용; 독립 공개 skill 필요성 재평가 |
| pr-converge | 리뷰 처분/수렴/실제 검증 command; SDD launcher+spec/design alignment | 유효한 evidence/수렴 기법 재사용; 실행 feedback loop와 책임 통합 검토 |
| self-improve | 명시 호출 learning policy, SDD launcher 참조 | 합의 R11에 따라 별도 skill 유지, launcher 분리 |
| idea-workshop | 아이디어 준비, 마지막에 SDD 진입, role profiles 참조 | 선택형 준비 skill로 재설계; 고정 SDD 전환 제거 |
| handoff | 문맥 기록, docs/sdd로 Phase 추정 | 새 runtime 상태 기반 재개/보고에 통합 검토 |
| git-worktree | raw git worktree 생성, SDD phase/호출자 정리 가정 | Orca adapter에 작업공간 책임 통합; 중복 공개 skill 제거 후보 |
| harness | 프로젝트 환경/문서/hooks 구성 | 실행 전 점검과 선택형 setup 분리; 본체 필수 제공 여부 재평가 |
| adversarial-review | 별도 역할·모델 지정·AI 재검토 루프 | 필요할 때의 원인분석/재계획 역할로 흡수 검토 |
| design-md, enhance-prompt | Stitch 전용 design system/프롬프트 | 위임 실행 본체 밖의 선택형 별도 도구로 분리 후보 |

추천은 새 사용자 흐름·공개 skill·실행 core를 제로베이스로 구성하고,
기존의 유효한 검증/보안/내구성 코드와 회귀 테스트를 선별 재사용하는 방식이다.
기존 구조의 호환성을 유지하는 비용은 이미 사용자 결정으로 제거됐다.
전부 재작성하면 redaction/path containment/설치 무결성까지 재구현·재검증해야 한다.
현재 조사만으로 모든 기존 코드가 불필요하다거나 전체 재작성 비용이 더 작다고 판단할 근거는 없다.

최소 공개 표면 후보는 새 실행 skill과 별도 self-improve이며, idea-workshop과 harness 등은
별도 사용 목적에 따라 선택한다. 이는 추천 후보로 남기고 확정된 삭제 목록으로 기록하지 않는다.
스킬 정리 감사는 구현 계획 I6뿐 아니라 core 책임을 정하는 I1/I4에도 영향을 준다.
제품 파일 삭제·manifest 변경은 수행하지 않았다.
