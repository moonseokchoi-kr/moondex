---
name: handoff
description: Save project context and evidence pointers for another session when the user requests a handoff or progress preservation.
---

# Handoff

다음 세션이 승인 범위와 실제 상태를 확인하고 이어갈 수 있는 문서를 만든다.
`assets/HANDOFF_TEMPLATE.md`를 출발점으로 사용하되 불필요한 섹션은 생략한다.

AGENTS.md, Git 상태/현재 commit, 합의 문서와 대화의 사용자 결정을 확인한다.
실행 상태가 있으면 이 스킬 기준 `../../runtime/moondex-runtime.py`를 절대 경로로 해석해
`execute --root <project-root> status`로 조회한다. 문서 작성은 읽기 전용 상태 조회만 필요하며
`resume`이나 `advance`를 실행하지 않는다.

기록할 내용:
- 목표, 승인 기준 revision/digest, 실제 승인 출처, 제외 범위.
- 완료/진행/실패/미검증의 구분과 증거 위치. 오래된 PASS는 현재 완료로 간주하지 않는다.
- 현재 node/attempt, 진행 중 process 또는 Orca Task/Dispatch, 미해결 질문과 필요한 결정.
- 변경 파일, 작업 경로/브랜치, 실패한 접근법, 다음 세션의 구체적인 첫 행동.

문서는 보조 기록이다. `.moondex/STATE.json`과 revision/receipt를 덮어쓰거나 승인으로 대신하지 않는다.
실행을 이어달라는 요청이 있을 때 다음 세션이 `$moondex:execute`로 상태를 확인하고 재개한다.
파일만으로 다른 세션의 Orca 권한을 인수할 수 있다고 주장하지 않는다.

사용자 지정 위치를 우선한다. 별도 지식 DB 규칙이 있으면 따르고,
프로젝트 문서로 저장하는 경우 활성 기능의 `docs/execution/<feature>/HANDOFF.md` 또는 루트 `HANDOFF.md`를 사용한다.
작성 후 경로와 핵심 재개 지점을 보고한다. 문서 저장만을 위한 추가 승인 단계를 만들지 않는다.
