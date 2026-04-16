---
allowed-tools: Bash, Read, Write
description: Phase 3 Build 단계 실행 (백엔드 + 프론트엔드 + 앱 구현)
---

# Phase 3: Build (Agent Teams 병렬)

## Step 1: 이전 단계 산출물 확인
- `pipeline/artifacts/03-design-spec/feature-spec.md` 존재 확인
- `pipeline/artifacts/04-db-schema/ddl.sql` 존재 확인
- `pipeline/artifacts/05-api-spec/openapi.yaml` 존재 확인 (없으면 08-backend가 생성)

## Step 2: 에이전트 병렬 실행 (Agent Teams)
Team Lead + 3 Teammates 구성:
1. `agents/08-backend/AGENT.md` → Spring Boot + Java 21 구현
2. `agents/09-frontend/AGENT.md` → Next.js 구현
3. `agents/10-app/AGENT.md` → 모바일 앱 (선택, v1은 PWA 권장)

## Step 3: Judge 평가
`agents/00-judge/AGENT.md` 로드 → Build 산출물 전체 품질 평가

## Step 4: 사용자 보고
Build 산출물 요약 + Judge 평가 결과를 사용자에게 보고
pipeline/state/current-state.json 업데이트
