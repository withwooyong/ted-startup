---
allowed-tools: Bash, Read, Write
description: Phase 4 Verify 단계 실행 (QA + 코드리뷰 + 보안검증)
---

# Phase 4: Verify (Agent Teams 병렬)

## Step 1: 이전 단계 산출물 확인
- `src/backend/` 소스코드 존재 확인
- `src/frontend/` 소스코드 존재 확인

## Step 2: 에이전트 병렬 실행 (Agent Teams)
1. `agents/11-qa/AGENT.md` → 단위/통합/E2E/성능 테스트
2. `agents/08-backend/AGENT.md` (review mode) → 코드 리뷰
3. `agents/13-security/AGENT.md` → OWASP 체크 + 의존성 스캔

## Step 3: Judge 평가
`agents/00-judge/AGENT.md` 로드 → Verify 산출물 전체 품질 평가

## Step 4: 사용자 보고
테스트 결과 + 코드 리뷰 + 보안 리포트 요약
pipeline/state/current-state.json 업데이트
