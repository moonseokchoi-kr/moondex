# Team Spec Schema

`team-spec`은 stack profile을 바탕으로 Moondex가 어떤 팀원을 어떤 순서와 검증 책임으로 사용할지 정의하는 프로젝트별 계약이다.

기본 저장 위치:

```text
.moondex/team/team-spec.json
```

## Required Fields

```json
{
  "schema_version": "1",
  "team_id": "default",
  "generated_at": "2026-04-29T00:00:00Z",
  "stack_profile_ref": ".moondex/team/stack-profile.json",
  "members": [],
  "role_chain": [],
  "required_checks": [],
  "handoff_contracts": [],
  "escalation_rules": []
}
```

## Member Shape

```json
{
  "role_id": "code-reviewer",
  "description": "Reviews implementation correctness and regression risk.",
  "member_doc": ".moondex/team/members/code-reviewer.md",
  "specialist_lenses": ["rust_runtime", "cli_contract"],
  "required_for": ["implementation_change", "regression_risk"],
  "may_skip_when": ["docs_only_no_contract_change"]
}
```

## Role Chain

`role_chain`은 기본 실행 순서를 나타낸다.

기본값:

```json
["implementer", "code-reviewer"]
```

다음 조건에서는 role을 추가한다.

- `compliance-reviewer`: persisted state, schema, API, CLI contract, archive behavior, plugin manifest, policy-sensitive path, cross-role handoff contract.
- `tester`: UI, E2E, external IO, mobile/platform behavior, deployment, installation, user-critical workflow.

## Specialist Lenses

role 이름을 무한히 늘리지 않는다. 기술 스택별 전문성은 `specialist_lenses`로 표현한다.

권장 starter lenses:

- `rust_runtime`
- `cli_contract`
- `state_audit`
- `frontend_ui_accessibility`
- `browser_e2e`
- `flutter_widget_platform`
- `python_api_schema`
- `data_pipeline`
- `plugin_packaging`
- `skill_authoring`
- `mcp_server_contract`

## Required Checks

각 check는 실행 가능한 명령 또는 사람이 수행할 검토를 명확히 구분한다.

```json
{
  "check_id": "cargo-test",
  "kind": "command",
  "command": "cargo test -p moondex",
  "required_for": ["rust_runtime"],
  "owner_role": "tester"
}
```

`kind` 값:

- `command`
- `manual_review`
- `browser_evidence`
- `install_smoke`
- `contract_fixture`

## Handoff Contracts

handoff contract는 한 role의 출력이 다음 role이 바로 사용할 수 있는지를 정의한다.

필수 정보:

- `from_role`
- `to_role`
- `artifact`
- `required_fields`
- `failure_path`

## Escalation Rules

escalation rule은 자동 추측 대신 멈추거나 role을 추가해야 하는 조건이다.

예:

```json
{
  "when": "changed files include persisted state schema",
  "action": "add_role",
  "role_id": "compliance-reviewer",
  "reason": "state contract changed"
}
```

