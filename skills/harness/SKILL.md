---
name: harness
description: Audit or improve a project's agent-facing instructions, verification commands, architecture checks, and evidence access when environment work is requested.
---

# Harness

프로젝트의 에이전트 작업 환경을 점검하거나 요청한 범위에서 개선한다.
일반 기능 구현에 별도의 환경 구축 단계를 강제하지 않는다.

## Audit

AGENTS.md, 실제 실행 명령, 코드 구조와 최근 검증 증거를 읽는다. 파일이 존재하는 것과
명령이 실제로 성공하거나 의도한 결함을 검출하는 것을 구분한다.

점검 대상은 작업에 맞게 선택한다:
- 지침과 승인 기준을 쉽게 찾을 수 있는가? 상충하거나 낡은 포인터가 있는가?
- 필수 build/unit/integration/E2E 명령이 실제 환경에서 실행되는가?
- 아키텍처 경계를 검사하는 도구가 관련 위반을 검출하는가?
- 로그와 재현 자료에 접근할 수 있고, 출력에서 민감 정보가 제거되는가?
- 중단 시 진행 중 process, 실패, 사용자 결정 대기를 구분할 수 있는가?

상세 관점은 `references/harness-principles.md`, 보안 관련 점검은
`references/security-baseline.md`를 읽는다. 사용자가 점수를 요청한 경우에만
`references/scoring-guide.md`를 참고하며 점수를 완료 판정으로 사용하지 않는다.
관찰 결과마다 근거·영향·개선안을 적는다. 실행하지 못한 검사는 미검증으로 기록한다.

## Setup 또는 수정

사용자가 요청한 문제를 해결할 최소한의 지침·명령·검증을 추가한다. 기존 문서 체계를 존중하고
폴더나 정해진 문서 개수를 채우기 위한 scaffolding은 하지 않는다.
자동 hook 설치, 세션 종료 시 학습 추출, 정책 승격은 이 스킬의 기본 동작이 아니다.
Hook을 별도로 요청한 경우에만 현재 환경의 공식 지원 계약과 기존 설정을 확인한 뒤 해당 범위를 다룬다.

승인된 검증 조건은 `$moondex:execute`의 gate에 연결한다. `.moondex/STATE.json`을 직접 편집하거나
audit 결과로 실행을 완료 처리하지 않는다. 필수 테스트를 시간 때문에 생략하지 않는다.
개선 중 수집한 실패/재시도 증거는 기록하되, 정책 개선은 사용자가 명시적으로 요청하는
`$moondex:self-improve`로 분리한다.
