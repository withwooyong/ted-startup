# Session Handoff

> Last updated: 2026-04-16 20:00 (KST)
> Branch: `master`
> Latest commit: `e6754cb` - 코드리뷰 반영: API Key 인증, 스코어 음수 방지, 프론트엔드 타입 안전성

## Current Status

Sprint 2 진행 중. 시그널 탐지 엔진 3종(급감/추세전환/숏스퀴즈)과 프론트엔드 대시보드+종목상세 페이지 구현 완료. 코드리뷰 4회 누적 실시, CRITICAL/HIGH 이슈 모두 해소. 백테스팅 페이지와 텔레그램 알림은 Sprint 3에서 구현 예정.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Scaffolding + Discovery + Design 산출물 | `1908310` | 32 files |
| 2 | Sprint 1: 백엔드 프로젝트 + Entity + API | `33d7676` | 18 Java files |
| 3 | Sprint 1: KRX 크롤러 + Spring Batch | `620f2bf` | KrxClient, BatchConfig |
| 4 | Sprint 1: Docker Compose + DDL | `620f2bf`, `140694b` | docker-compose.yml |
| 5 | 코드리뷰 #1~2 반영 (sealed error, 벌크, 트랜잭션) | `620f2bf`, `d710aa1` | 5 files |
| 6 | Sprint 2: 시그널 탐지 엔진 3종 | `7902cfd` | SignalDetectionService |
| 7 | Sprint 2: 프론트엔드 대시보드 + 종목상세 | `7902cfd` | page.tsx, stocks/[code] |
| 8 | 코드리뷰 #3~4 반영 (API Key, 타입 안전성) | `e6754cb` | 7 files |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Sprint 2 잔여: 백테스팅 결과 페이지 (프론트엔드) | 미시작 | |
| 2 | Sprint 3: 백테스팅 엔진 + API | 미시작 | |
| 3 | Sprint 3: 텔레그램 알림 연동 | 미시작 | |
| 4 | 리팩토링: SignalDetection N+1 벌크 조회 전환 | 이관 | 종목당 7쿼리 × 2500 = 17,500쿼리 |
| 5 | 리팩토링: ErrorBoundary 추가 | 이관 | Recharts 렌더링 에러 대응 |
| 6 | 리팩토링: Repository 헥사고날 경계 분리 | 이관 | port/out에 JpaRepository 직접 extends |
| 7 | 리팩토링: API Pagination 적용 | 이관 | |
| 8 | 리팩토링: Testcontainers 테스트 환경 | 이관 | |

## Key Decisions Made

- **API Key 인증**: IP allowlist가 프록시 환경에서 우회 가능하므로 `X-API-Key` 헤더 방식으로 전환. 환경변수 `ADMIN_API_KEY`로 관리
- **코드리뷰 → 커밋 순서**: 코드 작성 후 반드시 코드리뷰를 거친 뒤 커밋하는 플로우 확립
- **시그널 스코어 체계**: 급감(변동률×3 + 연속일×5), 추세전환(괴리율×10 + 전환속도×15), 숏스퀴즈(4팩터 가중합산 0~100)
- Spring Boot **3.5.0**, JPA `ddl-auto: none`, KRX **HTTP 크롤링**, 트랜잭션 경계 분리 (이전 세션 결정 유지)

## Known Issues

- **N+1 쿼리**: SignalDetectionService가 종목당 최대 7쿼리 실행 (2500종목 × 7 = 17,500쿼리). 벌크 조회 리팩토링 필요
- **한국 공휴일 미처리**: 주말만 건너뛰고 공휴일 무시 (v1.1 대응)
- **saveAll 중복**: 같은 날 재실행 시 unique constraint 에러 (ON CONFLICT 미적용)
- **@SpringBootTest**: DB 없이 실행 불가 (Testcontainers 미설정)
- **ErrorBoundary 없음**: Recharts 렌더링 에러 시 전체 페이지 크래시

## Context for Next Session

- **사용자 목표**: 공매도 커버링 시그널 탐지 시스템 MVP 6주 내 완성
- **현재 단계**: Sprint 2 진행 중 → 백테스팅 페이지 → Sprint 3 (백테스팅 엔진 + 텔레그램)
- **사용자 피드백**: 코드리뷰를 커밋 전에 실행할 것 (코드 작성 → 리뷰 → 수정 → 커밋)
- **기술스택**: Spring Boot 3.5.0 + Java 21 / Next.js 15 / PostgreSQL 16 / Recharts
- **Docker**: `docker compose up -d` (signal-db 컨테이너)
- **백엔드**: `DB_USERNAME=signal DB_PASSWORD=signal ADMIN_API_KEY=test ./gradlew bootRun --args='--spring.profiles.active=local'`
- **프론트엔드**: `cd src/frontend && npm run dev`
- **수동 배치**: `curl -X POST -H "X-API-Key: test" http://localhost:8080/api/batch/collect`
- **수동 탐지**: `curl -X POST -H "X-API-Key: test" http://localhost:8080/api/signals/detect`

## Files Modified This Session

```
 CLAUDE.md, CHANGELOG.md, HANDOFF.md     | 문서
 .env.example                             | API Key 추가
 src/backend/ (25 Java files)             | Spring Boot 백엔드
 src/frontend/src/ (7 files)              | Next.js 프론트엔드
 prototype/index.html                     | UI/UX 프로토타입
 docker-compose.yml                       | PostgreSQL 16
 agents/ (18 files)                       | 에이전트 AGENT.md
 pipeline/ (14 files)                     | 파이프라인 산출물
 .claude/ (8 files)                       | 설정 + 슬래시 커맨드
 scaffolding_check.sh                     | 검증 스크립트
```
