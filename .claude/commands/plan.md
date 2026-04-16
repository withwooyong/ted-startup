---
allowed-tools: Bash, Read, Write
description: Phase 1 Discovery 단계 실행 (요구사항 분석 → PRD → GTM → 고객여정)
argument-hint: [요구사항 텍스트]
---

# Phase 1: Discovery

사용자 요구사항: $ARGUMENTS

## Step 1: 요구사항 저장
$ARGUMENTS를 `pipeline/artifacts/00-input/user-request.md`에 저장

## Step 2: 에이전트 순차 실행
1. `agents/01-biz-analyst/AGENT.md` 로드 → 요구사항 분석서 생성
2. `agents/02-pm/AGENT.md` 로드 → PRD + 로드맵 + 스프린트 플랜
3. `agents/04-marketing/AGENT.md` 로드 → GTM 전략 + 경쟁사 분석
4. `agents/05-crm/AGENT.md` 로드 → 고객 여정 맵 + 알림 시나리오

## Step 3: Judge 평가
`agents/00-judge/AGENT.md` 로드 → Discovery 산출물 전체 품질 평가

## Step 4: 사용자 보고
Discovery 산출물 요약 + Judge 평가 결과를 사용자에게 보고
pipeline/state/current-state.json 업데이트
