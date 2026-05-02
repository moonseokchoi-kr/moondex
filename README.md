# Moondex

이 저장소는 Codex를 `상위 설계 수신형 multi-agent planner-executor`로 사용하기 위한 `moondex` runtime 작업 공간이다.

핵심은 상위 설계 자동화가 아니라 아래 세 가지다.

- planning 입력 계약 정의
- Codex가 생성해야 할 task/plan/wave 기준 정의
- planning 이후 실행을 안정화하는 규칙 정의

방향 기준 문서는 [docs/executor-direction.md](/Users/moon/Workspace/moondex/docs/executor-direction.md)다.

## 핵심 문서

- 방향 기준: [docs/executor-direction.md](/Users/moon/Workspace/moondex/docs/executor-direction.md)
- 저장소 감사: [docs/repository-audit-2026-04-21.md](/Users/moon/Workspace/moondex/docs/repository-audit-2026-04-21.md)
- 입력 문서 계약: [docs/contracts/input-document-contract.md](/Users/moon/Workspace/moondex/docs/contracts/input-document-contract.md)
- task 계약: [docs/contracts/task-schema.md](/Users/moon/Workspace/moondex/docs/contracts/task-schema.md)
- plan 계약: [docs/contracts/plan-schema.md](/Users/moon/Workspace/moondex/docs/contracts/plan-schema.md)
- wave 계약: [docs/contracts/wave-schema.md](/Users/moon/Workspace/moondex/docs/contracts/wave-schema.md)
- execution analysis report 계약: [docs/contracts/execution-analysis-report-schema.md](/Users/moon/Workspace/moondex/docs/contracts/execution-analysis-report-schema.md)
- harness change manifest 계약: [docs/contracts/harness-change-manifest-schema.md](/Users/moon/Workspace/moondex/docs/contracts/harness-change-manifest-schema.md)
- task set 템플릿: [docs/templates/task-set-template.md](/Users/moon/Workspace/moondex/docs/templates/task-set-template.md)
- task 템플릿: [docs/templates/task-template.md](/Users/moon/Workspace/moondex/docs/templates/task-template.md)
- plan 템플릿: [docs/templates/plan-template.md](/Users/moon/Workspace/moondex/docs/templates/plan-template.md)
- wave 템플릿: [docs/templates/wave-template.md](/Users/moon/Workspace/moondex/docs/templates/wave-template.md)
- implementation workflow 스킬: [skills/moondex-implementation-workflow/SKILL.md](/Users/moon/Workspace/moondex/skills/moondex-implementation-workflow/SKILL.md)
- task-creator 스킬: [skills/moondex-task-creator/SKILL.md](/Users/moon/Workspace/moondex/skills/moondex-task-creator/SKILL.md)
- task-planner 스킬: [skills/moondex-task-planner/SKILL.md](/Users/moon/Workspace/moondex/skills/moondex-task-planner/SKILL.md)
- wave-dispatcher 스킬: [skills/moondex-wave-dispatcher/SKILL.md](/Users/moon/Workspace/moondex/skills/moondex-wave-dispatcher/SKILL.md)
- handoff 스킬: [write-handoff](/Users/moon/.codex/skills/write-handoff/SKILL.md)
- cmux 스킬: [skills/moondex-cmux/SKILL.md](/Users/moon/Workspace/moondex/skills/moondex-cmux/SKILL.md)
- task-planner 에이전트: [.codex/agents/task-planner.toml](/Users/moon/Workspace/moondex/.codex/agents/task-planner.toml)
- role transfer hook: [.codex/hooks/validate-role-transfer.sh](/Users/moon/Workspace/moondex/.codex/hooks/validate-role-transfer.sh)
- readiness hook: [.codex/hooks/validate-readiness.sh](/Users/moon/Workspace/moondex/.codex/hooks/validate-readiness.sh)
- 실제 예시: [docs/examples/money-track-app-bootstrap-theme/README.md](/Users/moon/Workspace/moondex/docs/examples/money-track-app-bootstrap-theme/README.md)
- planning 절차: [docs/planning/planning-workflow.md](/Users/moon/Workspace/moondex/docs/planning/planning-workflow.md)
- task-planner agent 계약: [docs/planning/task-planner-subagent.md](/Users/moon/Workspace/moondex/docs/planning/task-planner-subagent.md)
- 멀티에이전트 운영 초안: [docs/execution/multi-agent-orchestration.md](/Users/moon/Workspace/moondex/docs/execution/multi-agent-orchestration.md)
- role transfer contracts: [docs/execution/role-transfer-contracts.md](/Users/moon/Workspace/moondex/docs/execution/role-transfer-contracts.md)
- work tracker: [docs/execution/WORK_TRACKER.md](/Users/moon/Workspace/moondex/docs/execution/WORK_TRACKER.md)
- cmux runtime alignment: [docs/execution/cmux-runtime-alignment.md](/Users/moon/Workspace/moondex/docs/execution/cmux-runtime-alignment.md)
- cmux operations playbook: [docs/execution/cmux-operations-playbook.md](/Users/moon/Workspace/moondex/docs/execution/cmux-operations-playbook.md)
- moondex CLI plan: [docs/execution/moondex-cli-plan.md](/Users/moon/Workspace/moondex/docs/execution/moondex-cli-plan.md)
- Codex hook auto-discovery: [docs/execution/codex-hook-auto-discovery.md](/Users/moon/Workspace/moondex/docs/execution/codex-hook-auto-discovery.md)
- moondex risk probes: [docs/execution/moondex-risk-probes.md](/Users/moon/Workspace/moondex/docs/execution/moondex-risk-probes.md)
- readiness 기준: [docs/execution/task-readiness-gate.md](/Users/moon/Workspace/moondex/docs/execution/task-readiness-gate.md)
- executor 체크리스트: [docs/execution/executor-checklist.md](/Users/moon/Workspace/moondex/docs/execution/executor-checklist.md)
- low-interruption 정책: [docs/execution/low-interruption-policy.md](/Users/moon/Workspace/moondex/docs/execution/low-interruption-policy.md)
- GPT-5.5 operating shape: [docs/execution/gpt-5.5-operating-shape.md](/Users/moon/Workspace/moondex/docs/execution/gpt-5.5-operating-shape.md)
- stack profile 계약: [docs/contracts/stack-profile-schema.md](/Users/moon/Workspace/moondex/docs/contracts/stack-profile-schema.md)
- team spec 계약: [docs/contracts/team-spec-schema.md](/Users/moon/Workspace/moondex/docs/contracts/team-spec-schema.md)
- stack-aware team composition: [docs/execution/stack-aware-team-composition.md](/Users/moon/Workspace/moondex/docs/execution/stack-aware-team-composition.md)
- research benchmarks: [docs/research/benchmarks/README.md](/Users/moon/Workspace/moondex/docs/research/benchmarks/README.md)

## 현재 결론

- 외부는 `spec`, `design set`, `implementation design set`를 제공한다.
- Codex 메인 에이전트는 이를 바탕으로 `task`를 만든다.
- `task-planner` planning layer가 각 task의 `plan`을 만든다.
- `wave-planner` planning layer가 plan 기준으로 `wave`를 확정한다.
- Codex는 생성한 task/plan/wave를 기준으로 구현, 테스트, 검증, 리스크 보고를 수행한다.
- 멀티 에이전트 실행이 기본 운영 모델이다.
- 멀티 에이전트의 성패는 task/plan/wave 품질에 달린다.

운영 레이어 메모:

- planning agent와 execution agent는 분리된 레이어로 본다.
- implementer는 `validated ready` 상태의 task만 받는다.
- 여러 planner/implementer/reviewer agent를 병렬로 띄울 수 있다.
- 터미널 세션 분리와 화면 모니터링은 `cmux` 같은 멀티플렉서로 수행한다.
- `cmux send`는 role worker를 깨우는 trigger일 뿐, dispatch 성공이나 상태 변경의 source of truth가 아니다.
- 핵심 계약은 task/plan/wave 문서와 role transfer/state artifact다.
- `validate-role-transfer`, `validate-readiness`, lifecycle hook warnings, `next-action`, `orchestrator-step/loop`, `archive-state`, `list-events`, and `inspect-hooks` now cover W-01 through W-16 in the work tracker.
- 같은 logical task는 `phase`를 통해 implementer에서 code-reviewer/compliance/tester로 넘어간다. review만을 위한 별도 task를 만드는 것은 더 이상 기본 runtime path가 아니다.
- `cmux` 화면은 source of truth가 아니다. `.moondex/state`와 `events.jsonl`이 runtime truth다.
- 플러그인이 설치된 대상 프로젝트의 팀 설정은 `.moondex/team/`에 두고, runtime state인 `.moondex/state/`와 분리한다.
- AHE-lite는 execution analysis report, harness change manifest, research benchmark run으로 제한한다. 자동 하네스 수정, 자동 rollback, 반복 rollout aggregation은 아직 범위가 아니다.
- GPT-5.5용 Moondex 스킬은 outcome-first 실행을 선호하되, task/plan/wave/readiness/runtime source-of-truth invariant는 줄이지 않는다.

## 저장소 원칙

- 방향이 바뀌면 먼저 `docs/executor-direction.md`를 갱신한다.
- 새 파일은 planning 입력 계약, planning 산출물 기준, 전용 planner 역할, gate, 실행 안정성 중 하나에 기여해야 한다.
- 상위 설계 생성 흐름은 이 저장소의 우선순위가 아니다.

## Codex Plugin

이 저장소는 repo root 자체가 Codex plugin root가 되도록 구성되어 있다.

- manifest: [.codex-plugin/plugin.json](/Users/moon/Workspace/moondex/.codex-plugin/plugin.json)
- bundled skills: [skills/](/Users/moon/Workspace/moondex/skills)

이 repo는 plugin package이며 marketplace repo가 아니다. 설치 테스트는 이 repo 안에 marketplace 파일을 두지 않고, 외부 marketplace에서 이 Git repo 또는 로컬 checkout을 plugin source로 가리키는 방식으로 수행한다. 로컬에서 빠르게 확인할 때는 임시 marketplace root를 만들고 그 root를 Codex에 추가한다.

```bash
codex plugin marketplace add <marketplace-root-or-git-url>
```

플러그인 설치는 Codex skill discovery만 보장한다. `moondex` CLI 빌드와 대상 repo의 runtime state 초기화는 별도 bootstrap 단계다. `codex plugin list`는 현재 Codex CLI에서 지원되는 확인 명령이 아니므로 사용하지 않는다.

설치 후 사용할 수 있는 주요 skill:

- `moondex-implementation-workflow`
- `moondex-runtime`
- `moondex-cmux`
- `moondex-task-creator`
- `moondex-task-planner`
- `moondex-wave-dispatcher`
- `moondex-diagnostics`
- `moondex-team-designer`

`moondex-team-designer`는 대상 프로젝트의 기술 스택을 읽고 `.moondex/team/` 아래에 stack profile, team spec, 팀원 설명, 검증 계획을 생성한다.

## Runtime Bootstrap

최초 runtime 사용 전에는 대상 repo에서 doctor를 먼저 실행한다. Moondex checkout 자체를 대상 repo로 쓸 때는 아래처럼 실행한다.

```bash
./scripts/doctor.sh
./scripts/doctor.sh --json
```

doctor는 plugin manifest, bundled skills, Rust/Cargo, PATH의 `moondex`, repo-local `.moondex/bin/moondex`, `.moondex/state`, `status`, `audit-state`를 확인한다. `.moondex/state`가 없으면 `status`를 실행하지 않는다. `status` 명령은 state를 초기화할 수 있으므로 doctor는 진단 중 runtime state를 몰래 만들지 않는다.

문제가 있으면 setup을 실행한다.

```bash
./scripts/setup-moondex.sh
```

기본 setup은 전역 PATH를 건드리지 않는다.

- `cargo build --release -p moondex`
- release binary를 `.moondex/bin/moondex`로 복사
- `.moondex/bin/moondex init`
- `.moondex/bin/moondex status --json`
- `.moondex/bin/moondex api audit-state --json`

다른 대상 repo를 초기화할 때는 `--target-root`를 사용한다.

```bash
./scripts/setup-moondex.sh --target-root /path/to/target-repo
```

또는 대상 repo를 cwd로 둔 상태에서 Moondex checkout의 script 경로를 직접 실행해도 된다.

전역 `moondex` 명령이 필요한 경우에만 선택적으로 설치한다.

```bash
./scripts/setup-moondex.sh --install-cli
```

실행 우선순위는 PATH의 `moondex`, `.moondex/bin/moondex` 순서다. `target/debug/moondex`는 개발 중 임시 산출물이며 runtime 기본 경로로 사용하지 않는다.

## Implementation Workflow

Bootstrap 이후 실제 구현은 전체 task set을 만든 뒤 plan set과 wave decision을 확정하는 흐름으로 시작한다.

SDD/Moondex형 repo에서 `진행해줘`, `계속해줘`, `다음 단계 진행`, `implement`, `proceed`, `continue` 같은 짧은 요청은 `moondex-implementation-workflow`를 기본 진입점으로 사용한다.

1. `moondex-implementation-workflow`가 repo marker와 현재 산출물 상태를 확인한다.
2. `moondex-task-creator`로 `spec`, `design set`, `implementation design set`, codebase scan을 읽고 task set을 만든다.
3. 모든 task를 `moondex-task-planner`에 넘겨 executor-ready plan set을 만든다. 서로 독립적인 task의 planner 요청은 병렬로 실행할 수 있다.
4. `moondex-wave-dispatcher`가 plan set 전체를 보고 dependency, ownership, shared contract를 기준으로 wave와 병렬 실행 가능 여부를 결정한다.
5. task, plan, wave payload를 `validate-readiness`로 검증한다.
6. READY wave task만 `<command_prefix> api create-task --input '<json>' --json`로 runtime에 등록한다.
7. 등록된 task만 `moondex-runtime`으로 dispatch, claim, review, test phase에 넘긴다.

`create-task` payload는 task creation 단계에서 만들 수 있지만, 실제 runtime 등록은 wave approval 이후에만 한다. 병렬 처리 여부는 task가 아니라 plan set 기준으로 판단한다.

승인된 wave 안에서는 high-impact blocker가 없는 한 사용자에게 묻지 않고 진행한다. 진행 상황은 mailbox/state/checkpoint로 보고하고, 사용자 개입은 wave approval, high-impact blocker, final integration summary에 집중한다.

## 다음 우선순위

- [docs/execution/WORK_TRACKER.md](/Users/moon/Workspace/moondex/docs/execution/WORK_TRACKER.md)의 W-01부터 W-16까지 완료됐다.
- [docs/execution/WORK_TRACKER.md](/Users/moon/Workspace/moondex/docs/execution/WORK_TRACKER.md)의 W-17 AHE-lite baseline도 완료됐다.
- [docs/execution/WORK_TRACKER.md](/Users/moon/Workspace/moondex/docs/execution/WORK_TRACKER.md)의 W-18 GPT-5.5 operating shape도 완료됐다.
- 다음 후보는 첫 benchmark run 작성, target product repo와 연결한 장기 E2E 검증, native Codex lifecycle hook manifest 검증, 또는 archive/evidence retention 정책 심화다.
