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
- task 템플릿: [docs/templates/task-template.md](/Users/moon/Workspace/moondex/docs/templates/task-template.md)
- plan 템플릿: [docs/templates/plan-template.md](/Users/moon/Workspace/moondex/docs/templates/plan-template.md)
- wave 템플릿: [docs/templates/wave-template.md](/Users/moon/Workspace/moondex/docs/templates/wave-template.md)
- task-planner 스킬: [.agents/skills/task-planner/SKILL.md](/Users/moon/Workspace/moondex/.agents/skills/task-planner/SKILL.md)
- handoff 스킬: [write-handoff](/Users/moon/.codex/skills/write-handoff/SKILL.md)
- cmux 스킬: [.agents/skills/cmux/SKILL.md](/Users/moon/Workspace/moondex/.agents/skills/cmux/SKILL.md)
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
- stack profile 계약: [docs/contracts/stack-profile-schema.md](/Users/moon/Workspace/moondex/docs/contracts/stack-profile-schema.md)
- team spec 계약: [docs/contracts/team-spec-schema.md](/Users/moon/Workspace/moondex/docs/contracts/team-spec-schema.md)
- stack-aware team composition: [docs/execution/stack-aware-team-composition.md](/Users/moon/Workspace/moondex/docs/execution/stack-aware-team-composition.md)

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

## 저장소 원칙

- 방향이 바뀌면 먼저 `docs/executor-direction.md`를 갱신한다.
- 새 파일은 planning 입력 계약, planning 산출물 기준, 전용 planner 역할, gate, 실행 안정성 중 하나에 기여해야 한다.
- 상위 설계 생성 흐름은 이 저장소의 우선순위가 아니다.

## Codex Plugin

이 저장소는 repo root 자체가 Codex plugin root가 되도록 구성되어 있다.

- manifest: [.codex-plugin/plugin.json](/Users/moon/Workspace/moondex/.codex-plugin/plugin.json)
- marketplace: [.agents/plugins/marketplace.json](/Users/moon/Workspace/moondex/.agents/plugins/marketplace.json)
- bundled skills: [skills/](/Users/moon/Workspace/moondex/skills)

로컬에서 테스트하려면 Codex plugin directory에서 repo marketplace를 선택하거나 CLI로 marketplace root를 추가한다.

```bash
codex plugin marketplace add ./ 
```

설치 후 사용할 수 있는 주요 skill:

- `moondex-runtime`
- `moondex-cmux`
- `moondex-task-planner`
- `moondex-diagnostics`
- `moondex-team-designer`

`moondex-team-designer`는 대상 프로젝트의 기술 스택을 읽고 `.moondex/team/` 아래에 stack profile, team spec, 팀원 설명, 검증 계획을 생성한다.

## 다음 우선순위

- [docs/execution/WORK_TRACKER.md](/Users/moon/Workspace/moondex/docs/execution/WORK_TRACKER.md)의 W-01부터 W-16까지 완료됐다.
- 다음 후보는 target product repo와 연결한 장기 E2E 검증, native Codex lifecycle hook manifest 검증, 또는 archive/evidence retention 정책 심화다.
