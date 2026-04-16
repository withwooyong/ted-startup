---
allowed-tools: Bash, Read, Write
description: Phase 2 Design 단계 실행 (기획 → 디자인 → DB 설계)
---

# Phase 2: Design

## Step 1: 이전 단계 산출물 확인
- `pipeline/artifacts/01-requirements/requirements.md` 존재 확인
- `pipeline/artifacts/02-prd/prd.md` 존재 확인

## Step 2: 에이전트 순차 실행
1. `agents/03-planning/AGENT.md` 로드 → 기능명세 + 화면설계
2. `agents/06-design/AGENT.md` 로드 → 디자인시스템 (TDS 기반)
3. `agents/07-db/AGENT.md` 로드 → ERD + DDL + 인덱스 전략

## Step 3: Judge 평가
`agents/00-judge/AGENT.md` 로드 → Design 산출물 전체 품질 평가

## Step 4: 사용자 보고
Design 산출물 요약 + Judge 평가 결과를 사용자에게 보고
pipeline/state/current-state.json 업데이트
