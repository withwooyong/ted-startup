---
allowed-tools: Bash, Read, Write
description: 전체 파이프라인 실행 (Discovery→Design→Build→Verify→Ship)
argument-hint: [요구사항 텍스트]
---

# Kickoff Full Pipeline

사용자 요구사항: $ARGUMENTS

## Step 1: 요구사항 저장
$ARGUMENTS를 `pipeline/artifacts/00-input/user-request.md`에 저장

## Step 2: Phase 1 — Discovery
순차 실행:
1. agents/01-biz-analyst/AGENT.md 로드 → 요구사항 분석
2. agents/02-pm/AGENT.md 로드 → PRD + 로드맵
3. agents/04-marketing/AGENT.md 로드 → GTM + 경쟁사
4. agents/05-crm/AGENT.md 로드 → 고객 여정

각 단계 후 agents/00-judge/AGENT.md로 품질 평가.

## Step 3: 인간 승인 #1
agents/00-advisor/AGENT.md 로드 → Decision Brief + Tradeoff Matrix 생성
사용자에게 진행 여부 확인.

## Step 4: Phase 2 — Design
순차 실행: 03-planning → 06-design → 07-db

## Step 5: 인간 승인 #2
Advisor가 설계 요약 + 기술 판단 근거 제공

## Step 6: Phase 3 — Build (Agent Teams 병렬)
Team Lead + Backend/Frontend/QA 3 Teammates 구성
계약 기반 병렬 구현

## Step 7: Phase 4 — Verify (Agent Teams 병렬)
QA + Backend(review) + Security 3 Teammates 병렬 검증

## Step 8: 인간 승인 #3
배포 준비도 종합 평가

## Step 9: Phase 5 — Ship
DevOps 배포 + Marketing 성과 분석
