# HANDOFF: Codex Harness Parity

> 이 문서는 새 세션이 컨텍스트 없이 `codex-harness-parity` 작업을 재개하기 위한 기록이다.

## 프로젝트 한줄 요약

Claude 전용 lifecycle hook 의존을 Codex에서 실제 실행 가능한 상태 preflight, git hook/CI, 결정적 Python 코어로 대체해 Moondex를 회사 환경에서도 안전하게 운영할 수 있게 하는 작업이다.

## 현재 상태

| 항목 | 상태 |
|---|---|
| SDD Phase 1 (Spec) | **완료** — `docs/sdd/spec/`에 F1~F10 수용 기준 정의 |
| SDD Phase 2 (Design) | **완료** — Codex adapter, 상태·enforcement 설계 확정 |
| SDD Phase 3 (Task) | **실행 중** — 11개 태스크 중 T-1~T-5 완료, T-6/T-7/T-9 진행 중 |
| Wave 1 | **완료** — config/CLI/오프라인 테스트 기반 |
| Wave 2 | **완료** — state, learning, PR, code-mapper 결정적 코어 |
| Wave 3 | **진행 중** — skill adapter, enforcement/CI, benchmark substrate |
| Worktree | `/Users/moon/Workspace/moondex-codex-harness-parity`, 브랜치 `feat/codex-harness-parity` |

## 핵심 문서 위치

| 문서 | 경로 | 용도 |
|---|---|---|
| 실행 상태 | `docs/sdd/ORCHESTRATOR_STATE.md` | 태스크 상태·소유권·의존성의 기준 |
| 명세 | `docs/sdd/spec/2026-07-14-codex-harness-parity.md` | F1~F10 수용 기준 |
| 설계 | `docs/sdd/design/arch/2026-07-14-codex-harness-parity.md` | runtime 구조와 Codex enforcement 경계 |
| 태스크 | `docs/sdd/task/codex-harness-parity/` | T-1~T-11의 소유 파일·검증 명령 |

상태 판정은 `ORCHESTRATOR_STATE.md`를 우선한다. 루트 `HANDOFF.md`는 이 기능 이전의 일반 프로젝트 기록이므로, 이 작업의 재개 기준으로 쓰지 않는다.

## 완료된 작업

### 1. 계획과 격리 작업공간

- Spec, architecture, 11개 태스크와 Wave DAG를 작성하고 사용자 승인을 받았다.
- 별도 worktree와 feature 브랜치를 생성했다. `main`에는 이 기능 변경이 병합되지 않았다.
- 관련 커밋: `5ccc750`, `47bb6df`, `16ee366`, `d983914`, `7b01798`.

### 2. Wave 1 — 런타임 구성 기반

- `harness_core` CLI와 `.harness/config.json` 파서를 추가했다.
- knowledge sync는 기본 비활성이고, 설정이 없으면 외부 대상에 쓰지 않는 계약이다.
- 관련 파일: `harness_core/{__init__,__main__,cli,config}.py`, `tests/test_config.py`, `pyproject.toml`.

### 3. Wave 2 — 결정적 코어

- 상태 전이·재시도·소유권·원자적 저장·preflight: `harness_core/state/`.
- learning provenance/tier/proposal/sync-skip: `harness_core/learning/`.
- PR comment dedup·수렴·에스컬레이션: `harness_core/pr/`.
- graph 상태와 명시적 approximate fallback: `harness_core/code_mapper/`.
- 대응 테스트: `tests/state/test_pipeline.py`, `tests/test_portable_cores.py`.

### 4. 착수된 Wave 3

- portable skill 표면: `skills/self-improve/`, `skills/pr-converge/`, `skills/code-mapper/`.
- verifier baseline: `scripts/verify.py`.
- train/held-out 디렉터리 및 live eval 분리: `benchmarks/`, `evals/`, `tests/test_test_collection.py`.
- T-6, T-7, T-9은 **완료로 전이하지 않았다**. 남은 수용 기준과 검증 증거를 채운 뒤 review/test 순서를 거쳐야 한다.

## 미완료 작업

### 즉시 필요

1. **T-6 완료** — 세 skill이 실질적인 Codex adapter 계약과 테스트를 갖추도록 보완한다.
2. **T-7 완료** — `harness_core/validation/`, git hook wrapper, CI 및 실패 시나리오 검증을 구현한다.
3. **T-9 완료** — benchmark score 기록·held-out 회귀 gate를 구현한다.
4. 위 세 태스크가 완료된 뒤 **T-8**(role contract/SDD resume)를 진행한다.

### 후속 작업

5. **T-10** — manifest, AGENTS.md, README portability audit (T-6~T-9 후).
6. **T-11** — F1~F10 end-to-end acceptance 및 `docs/sdd/result/` 증거 작성 (T-10 후).
7. 결과 검증 뒤 feature 브랜치를 검토·병합한다. `main`은 현재 이 변경을 포함하지 않는다.

## 실패하거나 주의가 필요한 점

### pytest 미설치

- **문제**: 현재 macOS Python 3.9.6에서 `python3 -m pytest -q`는 `No module named pytest`로 실패했다.
- **의미**: 상태 문서에는 과거 통과 기록이 있으나, 이 세션에서 전체 pytest 결과를 재현하지 못했다.
- **대응**: 프로젝트에 적절한 개발 의존성을 설치한 뒤 전체 테스트를 재실행하고 출력/결과 문서에 기록한다. 테스트 실패를 무시하고 태스크를 완료 처리하지 않는다.

### 검증된 범위와 미검증 범위

- `python3 -m harness_core doctor --help`와 `python3 scripts/verify.py`는 이 세션에서 통과했다 (`VERIFY_OK`).
- 실제 git hook 설치, CI required check, 기본 브랜치 보호, UI E2E 실패 경로는 T-7/T-11 전까지 미검증이다.

### 개인 경로 정책

- F8은 개인 Compound 경로를 기본 실행 경로에서 제거하고 조직 설정 opt-in만 허용한다.
- 기존 `main` worktree의 `hooks/hooks.json` 절대경로 수정은 이 feature worktree의 커밋에 포함되지 않는다. T-10 portability audit에서 이와 같은 경로 의존을 반드시 점검한다.

## 환경 정보

```
OS: macOS (Darwin 25.3.0)
Runtime: Python 3.9.6
프로젝트 worktree: /Users/moon/Workspace/moondex-codex-harness-parity
브랜치: feat/codex-harness-parity
현재 HEAD: 7b01798 feat: add portable skill adapter baseline
```

## 다음 에이전트가 해야 할 일

1. 이 파일과 `docs/sdd/ORCHESTRATOR_STATE.md`를 읽는다.
2. feature worktree에서 `git status --short`와 `git log --oneline -6`로 시작 상태를 확인한다.
3. pytest 개발 의존성을 준비한 뒤 `python3 -m pytest -q`를 실행해 이전 결과를 재현한다.
4. T-6/T-7/T-9의 각 태스크 문서에 따라 남은 구현·review·test와 증거 기록을 완료한다.
5. 오케스트레이터만 상태 파일을 갱신하고, Wave 의존성과 완료 순서를 지킨다.
