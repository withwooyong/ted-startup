---
allowed-tools: Bash, Read, Write
description: Phase 5 Ship 단계 실행 (DevOps 배포 + 성과분석)
---

# Phase 5: Ship

## Step 1: 이전 단계 산출물 확인
- Phase 4 Verify 통과 확인 (pipeline/state/current-state.json)
- 인간 승인 #3 완료 확인

## Step 2: 에이전트 순차 실행
1. `agents/12-devops/AGENT.md` → CI/CD + Docker + 배포
2. `agents/04-marketing/AGENT.md` (analytics mode) → 런칭 후 성과 분석

## Step 3: Judge 평가
`agents/00-judge/AGENT.md` 로드 → Ship 산출물 전체 품질 평가

## Step 4: 사용자 보고
배포 결과 + 성과 분석 요약
pipeline/state/current-state.json 업데이트 (status: "deployed")
