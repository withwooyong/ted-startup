# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Agent Team Platform — Claude Code 기반 멀티에이전트 SDLC 자동화 플랫폼.
요구사항 한 줄 입력으로 기획→설계→개발→테스트→배포까지 16개 AI 전문가 에이전트가 순차/병렬로 처리하는 구조.

**현재 상태**: 설계 완료, 구현 전 (설계서 + scaffolding 생성기만 존재)

## Tech Stack

| 영역 | 선택 |
|------|------|
| Backend | Spring Boot 3.4 + Java 21 (Hexagonal Architecture) |
| Frontend | Next.js 15 + TypeScript (App Router) |
| DB | PostgreSQL 16 |
| 쿼리 전략 | Spring Data JPA 3단계 (QueryDSL 미사용) |
| 인증 | 카카오 OAuth 2.0 |
| 컨벤션 | 네이버(백엔드) + 토스(디자인) + 카카오(인증) |

## Scaffolding

프로젝트 초기화는 `/init-agent-team` 슬래시 커맨드로 수행:
- 16개 에이전트 AGENT.md 생성 (agents/XX-name/)
- 파이프라인 디렉토리 (pipeline/artifacts, state, decisions, contracts)
- 7개 슬래시 커맨드 (kickoff, plan, design, develop, test, review, deploy)
- 공유 프로토콜 (agents/_shared/)

## Pipeline (5 Phases)

```
Phase 1: Discovery — biz-analyst → pm → marketing → crm
   🔴 인간 승인 #1
Phase 2: Design — planning → design → db
   🔴 인간 승인 #2
Phase 3: Build — backend + frontend + app (Agent Teams 병렬)
Phase 4: Verify — qa + code-review + security (Agent Teams 병렬)
   🔴 인간 승인 #3
Phase 5: Ship — devops → analytics
```

- 산출물은 `pipeline/artifacts/XX-stage/`에 저장
- 파이프라인 상태는 `pipeline/state/current-state.json`으로 추적
- 의사결정 기록은 `pipeline/decisions/decision-registry.md`에 영속화

## Agent Architecture (16 agents)

- **메타 에이전트 (3)**: 00-distiller(요약), 00-judge(품질평가), 00-advisor(의사결정 지원)
- **비즈니스 (5)**: 01-biz-analyst, 02-pm, 03-planning, 04-marketing, 05-crm
- **설계/개발 (5)**: 06-design, 07-db, 08-backend, 09-frontend, 10-app
- **품질/운영 (3)**: 11-qa, 12-devops, 13-security

에이전트 간 통신은 `agents/_shared/context-protocol.md` 규격으로 마크다운 + YAML 프론트매터 사용.

## Quality Gates

00-judge가 각 Phase 완료 시 5차원 평가 (완전성/일관성/정확성/명확성/실행가능성):
- Score >= 8.0 → PASS
- Score 6.0~7.9 → CONDITIONAL
- Score < 6.0 → RETRY 또는 FAIL

## Key Design Decisions

- QueryDSL 미사용: 1인 운영에서 설정 복잡도 > 이점
- Virtual Threads 활성화 (`spring.threads.virtual.enabled: true`)
- synchronized 대신 ReentrantLock (Virtual Thread pinning 방지)
- DTO는 Java record 클래스
- 에러 타입은 sealed interface
- MVP는 4~6주 내 런칭 가능한 범위로 제한
- 앱은 v1에서 PWA로 대체 권장

## Compaction Recovery

Compaction 발생 시 복구 순서:
1. `pipeline/state/current-state.json` 읽기
2. `pipeline/decisions/decision-registry.md` 읽기
3. 현재 단계에 필요한 산출물 로드
