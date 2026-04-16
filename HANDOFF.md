# Session Handoff

> Last updated: 2026-04-16 21:00 (KST)
> Branch: `master`
> Latest commit: `63407cd` - Sprint 2 완료: 백테스팅 API + 페이지, 코드리뷰 반영

## Current Status

Sprint 1~2 완료. 백엔드(데이터 파이프라인 + 시그널 엔진 3종 + 백테스팅 API)와 프론트엔드(대시보드 + 종목상세 + 백테스팅 페이지) 모두 구현 완료. 코드리뷰 5회 누적, CRITICAL/HIGH 모두 해소. Sprint 3(백테스팅 엔진 로직 + 텔레그램 알림) 착수 예정.

## Completed This Session

| # | Task | Commit |
|---|------|--------|
| 1 | Scaffolding + Discovery/Design 산출물 (16 에이전트, 14 산출물) | `1908310` |
| 2 | Sprint 1: Spring Boot 프로젝트 + Entity 5개 + API 2개 | `33d7676` |
| 3 | Sprint 1: KRX 크롤러 + Spring Batch + Docker PostgreSQL | `620f2bf` |
| 4 | Sprint 1: 코드리뷰 반영 (sealed error, 벌크 조회, 트랜잭션 분리) | `d710aa1` |
| 5 | Sprint 2: 시그널 탐지 엔진 3종 (급감/추세전환/숏스퀴즈) | `7902cfd` |
| 6 | Sprint 2: 프론트엔드 대시보드 + 종목상세 (Recharts 듀얼 축 차트) | `7902cfd` |
| 7 | Sprint 2: 코드리뷰 반영 (API Key 인증, 타입 안전성, 스코어 음수 방지) | `e6754cb` |
| 8 | Sprint 2: 백테스팅 API + 페이지 (테이블 + Bar 차트) | `63407cd` |
| 9 | UI/UX 프로토타입 (Dark Finance Terminal, frontend-design 스킬) | `33d7676` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Sprint 3: 백테스팅 엔진 로직** | 미시작 | 과거 3년 시그널 재실행 + 수익률 계산 |
| 2 | **Sprint 3: 텔레그램 알림 연동** | 미시작 | Bot API + 08:30 일일 알림 |
| 3 | Sprint 3: 통합 테스트 (Testcontainers) | 미시작 | 커버리지 80% 목표 |
| 4 | 리팩토링: SignalDetection N+1 → 벌크 조회 | 이관 | 17,500쿼리 문제 |
| 5 | 리팩토링: ErrorBoundary 추가 | 이관 | |
| 6 | 리팩토링: Repository 헥사고날 경계 분리 | 이관 | |
| 7 | 리팩토링: API Pagination | 이관 | |

## Key Decisions Made

- **코드리뷰 → 커밋 순서** 확립 (사용자 피드백)
- **API Key 인증** (`X-API-Key` 헤더, `ADMIN_API_KEY` 환경변수) — 관리자 엔드포인트 보호
- **시그널 스코어 체계**: 급감(변동률×3+연속일×5), 추세전환(괴리율×10+전환속도×15), 숏스퀴즈(4팩터 가중합산 0~100)
- **BacktestResult 쿼리 Top20 제한** — unbounded 쿼리 방지
- Spring Boot **3.5.0**, JPA `ddl-auto: none`, KRX **HTTP 크롤링**, 트랜잭션 경계 분리

## Known Issues

- **N+1 쿼리**: SignalDetectionService 종목당 7쿼리 × 2500 = 17,500쿼리
- **한국 공휴일 미처리**: 주말만 건너뛰기 (v1.1)
- **saveAll 중복 INSERT**: 같은 날 재실행 시 unique constraint 에러
- **Testcontainers 미설정**: @SpringBootTest DB 필요
- **ErrorBoundary 없음**: Recharts 렌더링 에러 시 페이지 크래시

## Context for Next Session

- **사용자 목표**: 공매도 커버링 시그널 탐지 시스템 MVP 6주 내 완성
- **현재 단계**: Sprint 2 완료 → Sprint 3 (백테스팅 엔진 + 텔레그램 + 통합 테스트)
- **사용자 피드백**: 코드 작성 → 코드리뷰 → 수정 → 커밋 순서 준수
- **기술스택**: Spring Boot 3.5.0 + Java 21 / Next.js 15 / PostgreSQL 16 / Recharts
- **실행 명령어**:
  - DB: `docker compose up -d`
  - Backend: `DB_USERNAME=signal DB_PASSWORD=signal ADMIN_API_KEY=test ./gradlew bootRun --args='--spring.profiles.active=local'`
  - Frontend: `cd src/frontend && npm run dev`
  - 수동 배치: `curl -X POST -H "X-API-Key: test" http://localhost:8080/api/batch/collect`
  - 수동 탐지: `curl -X POST -H "X-API-Key: test" http://localhost:8080/api/signals/detect`
- **API 목록**:
  - `GET /api/signals` — 시그널 리스트
  - `GET /api/stocks/{code}` — 종목 상세
  - `GET /api/backtest` — 백테스팅 결과
  - `POST /api/batch/collect` — 수동 배치 (API Key)
  - `POST /api/signals/detect` — 수동 탐지 (API Key)
- **프론트엔드 라우트**:
  - `/` — 대시보드 (시그널 리스트)
  - `/stocks/[code]` — 종목 상세 (차트)
  - `/backtest` — 백테스팅 결과
