---
name: adversarial-review
description: Diagnose repeated review failures or challenge an implementation approach when ordinary fixes have not resolved the underlying problem.
---

# Adversarial Review

승인 기준, 실제 코드와 재현 증거, 이전 실패/수정 이력을 읽고 접근법을 검토한다.
기본은 현재 세션의 단일 분석이다. 특정 모델·별도 에이전트·반복 디스패치를 강제하지 않는다.

관찰 가능한 실패를 설명하고, 원인을 요구/설계 변경·구현 결함·검증 결함으로 구분한다.
근거가 부족하면 미확인으로 남긴다. 각 제안에는 해당 파일/동작, 영향 범위, 구체적인 대안,
대안을 확인할 테스트를 포함한다. 사소한 취향 차이를 재작업 이유로 만들지 않는다.

리뷰 결과는 실행 완료 판정이 아니다. `$moondex:execute` 실행 중이면 분석 결과를
해당 feedback 경로에 제출하고 영향 DAG와 증거 무효화를 스크립트에 맡긴다.
기준 변경은 새 합의/revision이 필요하며, 수정 반복으로 복구 한도를 초기화하지 않는다.
실제 구현 요청이 없으면 진단 결과를 보고한다. 구현까지 승인된 경우 해당 범위의 수정·검증을 계속한다.
