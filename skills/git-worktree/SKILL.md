---
name: git-worktree
description: Create an isolated Git worktree for requested feature work while preserving existing changes and the selected base revision.
---

# Git Worktree

격리된 작업공간이 요청되었거나 실제로 필요한 경우에 사용한다. 단계 이름을 이유로 새 worktree를 만들지 않는다.

현재 Git 상태, 기존 worktree/브랜치, 요청된 기준 ref와 실제 commit을 먼저 확인한다.
사용자가 최신 remote 기준을 요청했다면 fetch 후 그 commit을 기록한다.
기존 경로나 브랜치를 덮어쓰지 않고, 현재 미커밋 파일을 임의로 새 작업공간에 복사하지 않는다.

Orca가 관리하는 작업공간이면 사용 가능한 `orca-cli` 스킬과 설치 CLI 가이드를 확인해 그 관리 경로로 생성한다.
필요한 기능을 사용할 수 없으면 제약을 보고하고 관리 상태를 raw Git으로 몰래 대체하지 않는다.
일반 Git 저장소에서는 충돌 없는 경로와 branch를 정한 뒤 다음 형태로 만든다:

```sh
git worktree add -b <new-branch> <new-path> <base-commit>
```

저장소 안에 만들 경우 해당 경로의 ignore 여부를 먼저 확인한다. 생성 후 작업 경로·브랜치·HEAD를
조회해 선택한 base와 일치하는지 검증하고 사용자에게 보고한다.
자동 snapshot commit, 다른 작업공간의 정리, merge/push는 생성 작업에 포함되지 않는다.
작업공간 제거가 요청되면 미커밋 변경과 실행 중인 소유 작업이 없는지 먼저 확인한다.
