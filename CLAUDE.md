# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Agent Team Platform — Claude Code 기반 멀티에이전트 SDLC 자동화 플랫폼.
요구사항 한 줄 입력으로 기획→설계→개발→테스트→배포까지 16개 AI 전문가 에이전트가 순차/병렬로 처리하는 구조.

- **Repository**: github.com/withwooyong/ted-startup
- **기본 브랜치**: master
- **현재 상태**: Phase 3 Build Sprint 2 진행 중 (시그널 엔진 + 대시보드)

## 핵심 참조 문서

- 마스터 설계서: `docs/design/ai-agent-team-master.md` — 모든 아키텍처/기술 판단의 권위 있는 출처
- Scaffolding 생성기: `.claude/commands/init-agent-team.md` — 에이전트/파이프라인 구조 자동 생성

## Getting Started

**초기 프로젝트 구조 생성** (아직 안 했다면):
```
/init-agent-team
```
이 명령이 16개 에이전트 AGENT.md, 파이프라인 디렉토리, 7개 슬래시 커맨드, 공유 프로토콜을 일괄 생성한다.

**파이프라인 실행** (scaffolding 생성 후):
```
/kickoff [요구사항 텍스트]     # 전체 파이프라인
/plan [요구사항]               # Phase 1: Discovery만
/design                        # Phase 2: Design만
/develop                       # Phase 3: Build만
/test                          # Phase 4: Verify만
/review                        # 코드 리뷰 + 보안 검증
/deploy                        # Phase 5: Ship만
```

## Tech Stack

| 영역 | 선택 |
|------|------|
| Backend | Spring Boot 3.4 + Java 21 (Hexagonal Architecture) |
| Frontend | Next.js 15 + TypeScript (App Router) |
| DB | PostgreSQL 16 |
| 쿼리 전략 | Spring Data JPA 3단계 (QueryDSL 미사용) |
| 인증 | 카카오 OAuth 2.0 |
| 컨벤션 | 네이버(백엔드) + 토스(디자인) + 카카오(인증) |

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

- 산출물: `pipeline/artifacts/XX-stage/`
- 파이프라인 상태: `pipeline/state/current-state.json`
- 의사결정 기록: `pipeline/decisions/decision-registry.md`

## Agent Architecture (16 agents)

- **메타 (3)**: 00-distiller(요약), 00-judge(품질평가), 00-advisor(의사결정 지원)
- **비즈니스 (5)**: 01-biz-analyst, 02-pm, 03-planning, 04-marketing, 05-crm
- **설계/개발 (5)**: 06-design, 07-db, 08-backend, 09-frontend, 10-app
- **품질/운영 (3)**: 11-qa, 12-devops, 13-security

에이전트 간 통신은 `agents/_shared/context-protocol.md` 규격 (마크다운 + YAML 프론트매터).

### 에이전트 호출 규칙
1. 각 에이전트는 `agents/XX-name/AGENT.md`를 시스템 프롬프트로 로드
2. 산출물은 `pipeline/artifacts/XX-stage/`에 저장
3. 각 에이전트는 자신의 전문 영역만 처리하고 경계를 넘지 않음

### 컨텍스트 관리 (1M Token)
- Phase 1~3: 산출물 요약본(summary.md) 사용 (Selective Loading)
- Phase 4: 소스코드 전체 원본 로드 (Full Context Mode)

### 코드 생성 전략 (128K Output)
1. **Scaffolding Pass** (1회) — Entity, Repository, UseCase, DTO, Controller 스켈레톤 일괄 생성
2. **Domain Pass** (도메인당 1회) — 비즈니스 로직 개별 구현
3. **Integration Pass** (1회) — Security, 예외 핸들러, 통합 테스트, Docker

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

## Backend Conventions (네이버 캠퍼스 핵데이)

- 하드탭 4스페이스, 줄 너비 120자
- null 반환 지양, Optional 활용
- `@Transactional(readOnly = true)` 읽기 기본
- Lombok: `@Getter`, `@Builder`, `@RequiredArgsConstructor` (Entity에 `@Setter` 금지)
- JPA 쿼리 3단계: 메서드 이름 쿼리 → `@Query` JPQL → Native Query

## Frontend Conventions (토스 + NHN)

- 공백 2개 들여쓰기
- Server Component 기본, `'use client'`는 필요 시만
- Suspense + ErrorBoundary 선언적 비동기
- 상태관리: TanStack Query (서버) + Zustand (클라이언트)
- 폼: react-hook-form + zod
- `any` 타입 사용 금지

## Compaction Recovery

Compaction 발생 시 복구 순서:
1. `pipeline/state/current-state.json` 읽기
2. `pipeline/decisions/decision-registry.md` 읽기
3. 현재 단계에 필요한 산출물 로드
