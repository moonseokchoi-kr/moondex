# 2026-09-10 Codex 훅 초기화

> 작업 사실 기록이며 SSOT가 아니다.

## 요청과 범위

훅 제거를 우선하고 이후 새 구조를 진행한다는 사용자 요청으로 수행했다.
기본 ~/.codex와 현재 Orca CODEX_HOME만 조사·수정했다.

## 변경

- 두 home의 hooks.json에서 cmux 감지와 dangerous_command_guard 등록 제거.
- 두 home의 설치 Moondex 0.4.0 hooks/hooks.json을 빈 hooks로 교체.
- config.toml의 과거 Moondex 및 제거된 사용자 훅 신뢰 기록 제거: 기본 18개, 현재 계정 29개.
- 현재 계정 Orca 연동 command 8개 유지. features.hooks 및 notify 설정은 유지.
- 스크립트 원본·repo hooks·다른 계정·원래 worktree는 수정하지 않았다.

## 백업 및 복원

백업: /Users/moon/.codex/backups/hook-reset-20260910-005354/
receipt.json에 각 원본 경로, 백업 파일, 전후 SHA256이 있다. 원본 설정 백업은 0600, 디렉터리는 0700이다.
복원 시 receipt의 backup을 해당 path에 복사하면 된다. 설정 변경이 더 발생했다면 전체 덮어쓰기보다 필요한 항목만 복원한다.

## 검증

JSON/TOML 재파싱 성공. config는 의도한 trust key 제거 외 의미적 변경 없음 비교 통과.
기본 command 0개, 현재 계정 command 8개 모두 Orca 경로임을 확인했다.
설치 Moondex hooks는 두 경로 모두 비어 있으며 Moondex trust key는 없다.
현재 세션의 hook 재로딩과 새 세션 runtime 무호출은 아직 관찰하지 않았다.
캐시 재설치나 외부 관리 도구가 설정을 다시 생성할 가능성은 이번 파일 검사로 판정하지 않는다.

## 설계 기록

d4에 파일 기반 상태·AI의 advance 호출·script의 완료 판정, 스킬 정리 후순위와 기존 baseline 복구 비선행 결정을 기록했다.
새 제품 구현 완료를 주장하지 않는다.
