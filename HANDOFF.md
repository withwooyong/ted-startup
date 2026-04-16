# Session Handoff

> Last updated: 2026-04-16 19:00 (KST)
> Branch: `master`
> Latest commit: `d710aa1` - 코드리뷰 반영: Batch Job 주입, 벌크 조회, 트랜잭션 분리, 접근 제한

## Current Status

Phase 3 Build Sprint 1 완료. 백엔드 데이터 파이프라인(KRX 크롤러 → Spring Batch → PostgreSQL) 구축 완료, API 동작 검증 완료. 코드리뷰 2회 실시 후 모든 HIGH 이슈 해소. 프론트엔드는 Next.js 초기화만 완료.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | `/init-agent-team` 실행 — 16개 에이전트 + 파이프라인 scaffolding | `1908310` | agents/*, pipeline/*, .claude/commands/* |
| 2 | Phase 1 Discovery — 요구사항, PRD, 로드맵, 스프린트 플랜 등 8건 | `1908310` | pipeline/artifacts/01~02/* |
| 3 | Phase 2 Design — 기능명세, 디자인토큰, ERD, DDL, 쿼리전략 등 6건 | `1908310` | pipeline/artifacts/03~06/* |
| 4 | UI/UX 프로토타입 (Dark Finance Terminal) | `33d7676` | prototype/index.html |
| 5 | Spring Boot 3.5.0 백엔드 프로젝트 + Hexagonal Architecture | `33d7676` | src/backend/* |
| 6 | Domain Entity 5개 + Repository 5개 + UseCase 2개 + REST API | `33d7676` | 18 Java files |
| 7 | KRX 크롤러 (공매도/대차잔고/시세) + Spring Batch Job | `620f2bf` | KrxClient, BatchConfig |
| 8 | Docker Compose (PostgreSQL 16) + DDL 자동 적용 | `620f2bf` | docker-compose.yml |
| 9 | 코드리뷰 #1 반영 — sealed error, 입력검증, 예외처리 | `620f2bf` | DomainError, GlobalExceptionHandler |
| 10 | 코드리뷰 #2 반영 — 벌크 조회, 트랜잭션 분리, 스케줄러 분리 | `d710aa1` | MarketDataCollectionService, Scheduler |
| 11 | Next.js 15 프론트엔드 프로젝트 초기화 | `33d7676` | src/frontend/* |
| 12 | GitHub push 완료 | — | — |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Sprint 2: 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) | 미시작 | 로직 설계는 plan.md에 완료 |
| 2 | Sprint 2: 프론트엔드 대시보드 + API 연동 | 미시작 | 프로토타입(prototype/index.html) 참고 |
| 3 | Sprint 3: 백테스팅 엔진 | 미시작 | |
| 4 | Sprint 3: 텔레그램 알림 연동 | 미시작 | |
| 5 | 리팩토링: Repository 헥사고날 경계 분리 | 이관 | port/out에 JpaRepository 직접 extends 중 |
| 6 | 리팩토링: API Pagination 적용 | 이관 | 현재 List 반환, Page로 변경 필요 |
| 7 | 리팩토링: SignalQueryService → 2개 서비스 분리 | 이관 | 1 Service에 2 UseCase 구현 중 |
| 8 | 리팩토링: @CreatedDate Spring Data Auditing 전환 | 이관 | 현재 @Builder.Default Instant.now() |

## Key Decisions Made

- Spring Boot 버전 **3.4 → 3.5.0** 변경 (Spring Initializr가 3.4 미지원)
- JPA `ddl-auto: none` — PostgreSQL 파티션 테이블과 Hibernate validate 충돌 방지, DDL은 마이그레이션 스크립트로 관리
- KRX 데이터 수집은 **HTTP 크롤링** (Open API 아님) — 요청 간격 2초 준수
- 트랜잭션 경계: HTTP 수집은 트랜잭션 밖, DB 저장만 트랜잭션 안
- sealed interface `DomainError`로 에러 타입 관리 (컨벤션 준수)
- 배치 API는 **localhost IP 제한** (Spring Security 미적용 상태)
- 프로토타입 디자인: "Dark Finance Terminal" 컨셉 — Outfit + DM Mono 폰트

## Known Issues

- KRX 크롤링 시 **한국 공휴일 미처리** — 주말만 건너뛰고 공휴일은 무시 (TODO: v1.1에서 공휴일 캘린더 연동)
- `findAllByTradingDate` 쿼리가 파티션 테이블에서 전체 스캔 가능성 — 실제 데이터 적재 후 EXPLAIN 확인 필요
- 주가/공매도 saveAll 시 중복 데이터 INSERT 시 unique constraint 에러 가능 — ON CONFLICT 미적용 (같은 날 재실행 시 에러)
- `@SpringBootTest` 테스트가 DB 없이 실행 불가 — Testcontainers 설정 필요

## Context for Next Session

- **사용자 목표**: 공매도 커버링 시그널 탐지 시스템 MVP 6주 내 완성
- **현재 단계**: Sprint 1 완료, Sprint 2(시그널 엔진 + 대시보드) 착수 예정
- **기술스택**: Spring Boot 3.5.0 + Java 21 / Next.js 15 / PostgreSQL 16 / Spring Batch
- **컨벤션**: 네이버(백엔드) + 토스(디자인) + 카카오(인증)
- **Docker**: `docker compose up -d`로 PostgreSQL 기동 (signal-db 컨테이너)
- **백엔드 실행**: `DB_USERNAME=signal DB_PASSWORD=signal ./gradlew bootRun --args='--spring.profiles.active=local'`
- **프론트엔드**: `cd src/frontend && npm run dev`
- **프로토타입**: `prototype/index.html` (브라우저에서 직접 열기)
- **다음 작업**: Sprint 2 시그널 탐지 로직 구현 → 프론트엔드 대시보드 → API 연동

## Files Modified This Session

```
 .claude/commands/ (7 files)           | 7 slash commands
 .claude/settings.json                 | 프로젝트 설정
 agents/ (18 files)                    | 16 AGENT.md + 2 shared protocols
 pipeline/artifacts/ (14 files)        | Discovery + Design 산출물
 pipeline/state/current-state.json     | 파이프라인 상태
 pipeline/decisions/decision-registry.md
 prototype/index.html                  | UI/UX 프로토타입
 src/backend/ (22 Java files)          | Spring Boot 백엔드
 src/frontend/ (초기화)                | Next.js 프론트엔드
 docker-compose.yml                    | PostgreSQL 16
 .env.example                          | 환경변수 템플릿
 CLAUDE.md                             | 프로젝트 가이드 업데이트
 CHANGELOG.md                          | 변경이력
 scaffolding_check.sh                  | Scaffolding 검증 스크립트
```
