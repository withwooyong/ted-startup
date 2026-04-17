# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/).

## [Unreleased]

### Changed (uncommitted — /ted-run 코드 리뷰 반영)
- `next.config.ts` rewrites 제거 → `src/frontend/src/proxy.ts` 신규 (런타임 env 기반 프록시, Next.js 16 canonical)
- `src/frontend/src/lib/api/client.ts`: `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_API_BASE_URL` 정합, 기본값 `/api`
- `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: `BACKEND_API_URL` → `BACKEND_INTERNAL_URL` 정합, `/api` path prefix 추가, 16KB body 상한(M-4)
- `src/backend/Dockerfile`: `./gradlew dependencies || true` → `./gradlew dependencies` (M-1, 의존성 해석 실패 은폐 제거)

---

## [2026-04-17 — 오후] Phase 4 Verify + Phase 5 Ship + 프로토타입 효과 Next.js 이식 — v1.0 배포 준비 완료

### Added
- 프로토타입 효과 3종 Next.js 이식 (`871ff57`)
  - `src/frontend/src/components/ui/AuroraBackground.tsx`: 4-blob radial-gradient + drift keyframes, pure CSS, 서버 안전
  - `src/frontend/src/components/ui/CountUp.tsx`: rAF 기반 easeOutCubic 카운트업, `prefers-reduced-motion` 가드
  - `src/frontend/src/components/ui/Magnetic.tsx`: 커서 인력 버튼 래퍼, `coarse-pointer`/reduced-motion 가드
  - `src/frontend/src/app/globals.css`: `.aurora` + `@keyframes aurora-drift-1~4` + `.magnetic` 블록 추가
- Phase 4 Verify 산출물 3종 + Judge 평가 (`eb5fc15`)
  - `pipeline/artifacts/07-test-results/qa-report.md` (CONDITIONAL)
  - `pipeline/artifacts/08-review-report/review-report.md` (CONDITIONAL, CRITICAL 1 + HIGH 4)
  - `pipeline/artifacts/09-security-audit/audit-report.md` (CONDITIONAL, HIGH 1)
  - `pipeline/artifacts/07-test-results/verify-judge-evaluation.md` (7.6/10)
- Phase 5 Ship 인프라 (`764d6d3`)
  - `src/backend/Dockerfile` / `src/frontend/Dockerfile` (multi-stage, non-root, healthcheck)
  - `docker-compose.prod.yml` (3 서비스, 내부 네트워크, DB 미노출)
  - `.env.prod.example` + `.gitignore` 갱신
  - `.github/workflows/ci.yml` (backend-test + frontend-build + docker-build with GHA cache)
  - `pipeline/artifacts/10-deploy-log/runbook.md` (배포 / 롤백 / 백업 cron / AWS 5-step 이관)
  - `pipeline/artifacts/11-analytics/launch-report.md` (D+7 Top KPI 3종 + Week 1~4 모니터링)
  - `pipeline/artifacts/10-deploy-log/ship-judge-evaluation.md` (PASS 8.1/10)
- 백엔드 트랜잭션 리팩터
  - `src/backend/.../application/service/MarketDataPersistService.java`: `persistAll` 전담 빈 분리 — Spring AOP 자기호출 프록시 우회 문제 해결
- Admin API 서버 릴레이
  - `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: Next.js Route Handler — 서버 측 `ADMIN_API_KEY`로 backend 프록시

### Changed
- `src/frontend/src/app/layout.tsx`: `<AuroraBackground>` 주입 + 본문 z-index:1 레이어링 + footer backdrop-blur
- `src/frontend/src/app/page.tsx`: metric 카드 값에 `CountUp`, 필터 버튼에 `Magnetic` 래핑, 카드 배경 `bg-[#131720]/85 backdrop-blur`로 전환
- `src/backend/.../MarketDataCollectionService.java`: `persistAll` 로직 제거, `MarketDataPersistService`에 위임
- `src/frontend/src/app/settings/page.tsx`: `NEXT_PUBLIC_ADMIN_API_KEY` 의존 제거, `updateNotificationPreferences(form)`로 간소화
- `src/frontend/src/lib/api/client.ts`: `updateNotificationPreferences` apiKey 인자 제거, `/api/admin/notifications/preferences` Route Handler 호출로 전환
- `pipeline/state/current-state.json`: `status: "deployed"`, `human_approvals #3 passed 7.6`, `ship_artifacts` + `post_ship_recommendations` 추가
- `docs/sprint-4-plan.md`: Phase 4/5 통과 반영

### Fixed
- **[CRITICAL B-C1]** `NEXT_PUBLIC_ADMIN_API_KEY` 브라우저 번들 노출 — Review+Security 공동 지목. Route Handler로 서버 전환, 관리자 API 4개(batch/collect, signals/detect, backtest/run, PUT preferences) 공개 상태 해소
- **[HIGH B-H1]** `MarketDataCollectionService.persistAll` 자기호출로 `@Transactional` 무효 — `MarketDataPersistService` 신규 빈으로 분리해 프록시 정상 적용
- **[HIGH B-H2]** `persistAll` 데드 코드 (`findByStockId(null, date, date)` 미사용 결과) 제거
- **[HIGH B-H3]** 배치 재실행 시 유니크 제약 충돌 — 일자별 기존 `stockId` 집합 1회 조회 후 INSERT skip, 건수 로깅으로 멱등성 확보

---

## [2026-04-17] Sprint 4 Task 4 — 알림 설정 페이지 (백엔드 + 프론트) + 프로토타입 합류본 확정 + 리뷰 반영

### Security / Review Fixes (HIGH 4 + MEDIUM 9)
- **HIGH-1**: `PUT /api/notifications/preferences`에 `X-API-Key` 인증 추가 — 공개 API에서 공격자의 알림 무력화 방지 (Security 리뷰)
- **HIGH-2**: `NotificationPreferenceService.loadOrCreate` race condition — `DataIntegrityViolationException` catch + 재조회 recover 패턴 적용 (Java 리뷰)
- **HIGH-3**: `GlobalExceptionHandler`에서 `IllegalArgumentException` 전역 캐치 제거 — JDK 내부 오류가 400으로 마스킹되던 문제 해소 (Java 리뷰)
- **HIGH-4**: Hexagonal 위반 수정 — `sanitizeSignalTypes` 검증 책임을 Controller에서 `UpdateCommand` compact constructor로 이동, `DomainException(DomainError.InvalidParameter)` 경로 사용 (Java 리뷰)
- **MEDIUM**: `@Size(min=1, max=3)` 제약 추가 (DoS 방지), 에러 메시지 사용자 입력 반사 제거(고정 문자열), `getPreferenceForFiltering`에 `@Transactional(readOnly=true)` 명시, 도메인 `update()` 자체 검증(minScore 범위, 빈 리스트), `sendBatchFailure` 로그에서 `errorMessage` 제거
- **MEDIUM (프론트)**: `aria-valuemin/max/now` 3줄 중복 제거(input[type=range] 자동 제공), `client.ts` `cache: 'no-store'` spread 후위 재명시(caller override 방어), 에러 메시지 직접 노출 → `friendlyError()` 매핑 함수로 status 기반 사용자 메시지 반환
- **테스트**: `NotificationApiIntegrationTest` 9개로 확장 (인증 2 + 업데이트 1 + 400 검증 5 + 기본값 1). 알 수 없는 타입이 응답에 반사되지 않는지 검증 포함
- **부수 개선**: `BacktestController`/`SignalDetectionController`/`BatchController`의 API Key 검증 로직 중복 제거 → 신규 `ApiKeyValidator` 컴포넌트로 추출

### Added
- `src/backend/.../domain/model/NotificationPreference.java`: 싱글 로우 엔티티(id=1 고정) — 4채널 플래그 + `minScore`(0-100) + `signalTypes` JSONB
- `src/backend/.../application/port/in/GetNotificationPreferenceUseCase`, `UpdateNotificationPreferenceUseCase`: 조회/업데이트 유스케이스 포트
- `src/backend/.../application/port/out/NotificationPreferenceRepository`: Spring Data JPA 리포지토리
- `src/backend/.../application/service/NotificationPreferenceService`: `loadOrCreate` 지연 생성 + `getPreferenceForFiltering` 기본값 fallback
- `src/backend/.../adapter/in/web/NotificationPreferenceController`: `GET/PUT /api/notifications/preferences` + Bean Validation(`@Min/@Max/@NotNull`)
- `src/backend/src/main/resources/db/migration/V2__notification_preference.sql`: 테이블 DDL + 기본 row INSERT (Flyway 도입 시 바로 적용 가능, 현재는 참고용)
- `src/backend/src/test/.../NotificationApiIntegrationTest`: 5개 통합 테스트 (기본값 생성 / 전체 업데이트 / minScore 범위 / 알 수 없는 타입 / 필수 필드 누락)
- `src/frontend/src/types/notification.ts`: `NotificationPreference` 타입 + 채널 라벨 상수
- `src/frontend/src/app/settings/page.tsx`: 4개 토글(switch role) + 3개 시그널타입 필터(aria-pressed) + minScore 슬라이더 + 저장 버튼 + 토스트

### Changed
- `src/backend/.../application/service/TelegramNotificationService`: 4개 시나리오 전부 preference 필터 반영
  - `sendDailySummary`: toggle + signalTypes + minScore 삼중 필터
  - `sendUrgentAlerts`: toggle + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: toggle
- `src/backend/.../adapter/in/web/GlobalExceptionHandler`: `@Valid @RequestBody` 검증 실패를 400으로 변환 — `MethodArgumentNotValidException` + `HttpMessageNotReadableException` + `IllegalArgumentException` 핸들러 신규
- `src/frontend/src/lib/api/client.ts`: `fetchApi`에 `RequestInit` 옵션 추가, `getNotificationPreferences` + `updateNotificationPreferences` 노출
- `src/frontend/src/components/NavHeader.tsx`: `/settings` 링크 추가

### Decision
- **D-4.11 알림 설정 = 싱글 로우 패턴**: id=1 고정, 4개 채널 플래그 + minScore + signalTypes JSONB. 사용자/인증 도입 시 user_id FK로 확장 가능
- **D-4.10 프로토타입 합류본 = ambient**: `prototype/index-ambient.html`(1332줄, aurora + skeleton + tilt + magnetic + count-up 누적)을 최종 합류본으로 확정 → `prototype/index.html`에 복사

### Testing
- 백엔드: JUnit 5 + Testcontainers 25개 전체 통과 (기존 20 + 신규 5)
- 프론트: `tsc --noEmit` + `eslint` + `next build` 전부 clean — `/settings` 라우트 정적 생성 확인

---

## [2026-04-17] Sprint 4 Task 5-6 — 프론트엔드 반응형 + ErrorBoundary + 글로벌 네비 + 접근성

### Added
- `src/frontend/src/components/NavHeader.tsx`: 글로벌 네비게이션 — sticky + 햄버거 + ESC + `aria-current` + render-time 리셋 패턴 (`9436772`)
- `src/frontend/src/components/ErrorBoundary.tsx`: class 컴포넌트 + `resetKeys` 자동 복구 + `role="alert"` (`9436772`)

### Changed
- `src/frontend/src/app/layout.tsx`: 글로벌 `<NavHeader />` 삽입 (`9436772`)
- `src/frontend/src/app/page.tsx`: 중복 헤더 제거(sr-only H1), 시그널 리스트 `grid-cols-1 lg:grid-cols-2`, `<ul>/<li>` 시맨틱, 필터 `role="group" + aria-pressed` (`9436772`)
- `src/frontend/src/app/stocks/[code]/page.tsx`: `ResponsiveContainer aspect={2}` 비율 기반 차트, ErrorBoundary 래핑, 기간 버튼 `role="group"`, render-time 상태 리셋 (`9436772`)
- `src/frontend/src/app/backtest/page.tsx`: 모바일 `<dl/dt/dd>` 카드 ↔ 데스크탑 `<table>` 이중 렌더, ErrorBoundary 래핑 (`9436772`)
- `src/frontend/src/components/features/SignalCard.tsx`: `<Link>`가 직접 그리드 컨테이너 (중첩 `<div role="article">` 제거), `aria-label` 상세화 (`9436772`)

### Fixed
- `react-hooks/set-state-in-effect` ESLint 3건(Next 16 신규 룰): `NavHeader.pathname`, `StockDetail.code+period`, `Dashboard` 초기 `setLoading` 중복 → render-time 리셋 패턴 (`9436772`)
- `role="tablist"/"tab"` 스펙 위반 2건 → `role="group" + aria-pressed` (필터, 기간 버튼) (`9436772`)
- ErrorBoundary 재발 루프: `resetKeys` + `componentDidUpdate` 자동 리셋 (리뷰 MEDIUM-1) (`9436772`)
- `role="alert"` + `aria-live="assertive"` 중복 제거 (`9436772`)
- 백테스트 YAxis formatter 음수 처리 (`+-1.5%` → `-1.5%`) (`9436772`)
- `aria-current="page"`는 exact match만, 관련 경로는 시각 강조로 분리 (`9436772`)

### Committed
- Sprint 4 Task 5-6 (`9436772`): 7 files, +330/-73, `tsc + eslint + next build` 전부 ok

### Pending (Task 4 + 프로토타입 선정 다음 세션)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + `/settings` 프론트, 1.5일)
- 프로토타입 5종 중 합류본 선정 → `prototype/index.html`로 통합

---

## [2026-04-17] 프로토타입 UI 실험 5종 + 코드리뷰 보안 패치 전면 적용

### Added
- `prototype/index-before-skeleton.html`: 원본 스냅샷 (baseline, 보안 패치만) (`7a5b750`)
- `prototype/index-tilt-magnetic.html`: 3D 틸트 카드 + 마그네틱 버튼 — `prefers-reduced-motion` + 터치 자동 비활성 (`7a5b750`)
- `prototype/index-counter.html`: 카운트업 애니메이션 32개 카운터 (data 속성 선언형 엔진) (`7a5b750`)
- `prototype/index-ambient.html`: 배경 3층 — Aurora 메시 + 커서 스포트라이트 + 파티클 네트워크 캔버스 (`7a5b750`)

### Changed
- `prototype/index.html`: 스켈레톤 UI 적용 (시그널 리스트/상세 차트/백테스트 차트 로딩 + shimmer, 라이트/다크 대응) (`7a5b750`)

### Fixed
- **[CRITICAL] XSS 싱크 3종 차단**: `escapeHtml()` + `num()` 헬퍼, `onclick` 인라인 → `data-code` + `addEventListener` (`7a5b750`)
- **[HIGH] `showPage()` 허용목록**: `VALID_PAGES = Set` early return (`7a5b750`)
- **[HIGH] DOM 엘리먼트 캐싱**: `cacheEls()` INIT 1회 → `els[id]` 룩업 (`7a5b750`)
- **[MEDIUM] CDN SRI**: Chart.js 4.4.7 / Pretendard 1.3.9 `integrity="sha384-..."` + `crossorigin="anonymous"` (`7a5b750`)
- **[MEDIUM] 스켈레톤 접근성**: `role="list"` + `aria-busy` 토글 + `aria-live="polite"` + 카드 `role="button"` + 키보드 (`7a5b750`)
- **[LOW] matchMedia 동적 리스너**: `prefers-reduced-motion`/`pointer: coarse`에 `change` 리스너 (tilt/counter/ambient 3종) (`7a5b750`)

> 5종 HTML 모두 단독 실행 가능. 코드리뷰 재검증 CRITICAL/HIGH 0건 + 회귀 0건. 다음 세션에서 최종 합류본 결정 → `prototype/index.html` 통합 예정.

---

## [2026-04-17] Sprint 4 Task 1-3 — N+1 쿼리 최적화 + 백테스팅 3년 제한 + CORS X-API-Key

### Added
- `src/backend/src/test/java/com/ted/signal/config/CorsConfigTest.java`: CORS preflight 테스트 1개 신규 (`33b6cf1`)
- `BacktestApiIntegrationTest.runBacktestRejectsPeriodOverThreeYears`: 3년 초과 기간 rejection 테스트 추가 (`33b6cf1`)
- `StockPriceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 절 기반 벌크 주가 조회 (`33b6cf1`)
- `StockPriceRepository.findAllByTradingDate`: 일자별 주가 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `ShortSellingRepository.findAllByTradingDate`: 일자별 공매도 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `LendingBalanceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 기반 대차잔고 히스토리 (`33b6cf1`)
- `SignalRepository.findBySignalDateWithStockOrderByScoreDesc`: 일자별 시그널 JOIN FETCH 조회 (`33b6cf1`)

### Changed
- `SignalDetectionService.detectAll`: 종목당 7쿼리 × 2500 = 17,500쿼리 → 전체 7쿼리 (활성 종목 1 + 벌크 5 + 기존 시그널 1). 메모리 루프 기반 재작성 (`33b6cf1`)
- `TelegramNotificationService.sendDailySummary`: `findBySignalDateOrderByScoreDesc` → `findBySignalDateWithStockOrderByScoreDesc` (stock LAZY 로딩 N+1 해소) (`33b6cf1`)
- `BacktestController`: 최대 기간 5년 → **3년**, `to` 미래 날짜 차단 검증 추가 (`33b6cf1`)
- `BacktestEngineService`: 종목별 주가 조회 N쿼리 → `findAllByStockIdsAndTradingDateBetween` 단일 쿼리 (`33b6cf1`)
- `WebConfig`: CORS `allowedHeaders`에 `X-API-Key` 추가, `OPTIONS` 메서드, `allowCredentials(true)`, `exposedHeaders` 명시 (`33b6cf1`)
- `SignalDetectionService` detail의 `volumeChangeRate`: 점수(int) 중복 저장 → 실제 거래량 비율(BigDecimal) 저장 (`33b6cf1`)

### Committed
- Sprint 4 Task 1-3 (`33b6cf1`): 성능/보안 HIGH 3건 해소 (11 files, +245/-114, 테스트 20개 전부 통과)

### Pending (Task 4-5 다음 세션 이관)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + 프론트 `/settings`)
- Task 5: 모바일 반응형 + ErrorBoundary + 접근성 감사

---

## [2026-04-17] 모델 운용 전략 전환 — Max 구독자 Opus 4.7 단일 운영

### Changed
- `docs/PIPELINE-GUIDE.md`: "Phase 1~3 Sonnet, Phase 4 Opus" 분기 전략 → **Max 구독자 Opus 4.7 단일 운영**으로 전환. API 종량제 사용자용 Option B 병기 (`d55738d`)
- `docs/design/ai-agent-team-master.md`: §11 "비용 최적화" 섹션을 **Option A (Max 구독) / Option B (API 종량제)** 이원화. Judge 비용 설명 보강 (`d55738d`)
- `.claude/commands/init-agent-team.md`: CLAUDE.md 템플릿에 "모델 운용 전략" 섹션 추가 + 최종 안내 메시지에 구독 유형별 가이드 포함 (`d55738d`)
- `pipeline/decisions/decision-registry.md`: D-0.1 "모델 운용 전략" 의사결정 추가 (23 → 24건) (`d55738d`)

> 근거: Claude Code Max $200 구독 활용 시 모델 분기로 얻는 비용 이득 없음. Sprint 3에서 Opus 4.7이 N+1 쿼리 17,500건 등 HIGH 이슈 7건 포착 → Phase 1~3에서도 Opus 사용 시 품질 우위 확인.

---

## [2026-04-17] 파이프라인 플랫폼 정합화 + 팀 공유 전환 + 문서 현행화

### Added
- `docs/PIPELINE-GUIDE.md`: 개발 플로우 사용설명서 신규 (9개 섹션, 다른 프로젝트 이식 체크리스트 포함) (`cdbacc5`)
- `docs/sprint-4-plan.md`: Sprint 4 작업계획서 (N+1 최적화 + CORS + 알림 설정 페이지 + 모바일 반응형, 4.5일 예상) (`da85ba2`)
- `pipeline/state/current-state.json`: Sprint 3 완료 상태 현행화 (진행 sprint 4종 + 테스트 커버리지 + 알려진 이슈) (`eecdb7c`)
- `pipeline/artifacts/06-code/summary.md`: Sprint 1~3 구현 요약 (Compaction 방어 영속화) (`eecdb7c`)
- `pipeline/decisions/decision-registry.md`: Phase 1~3 의사결정 23개 누적 (Discovery 3, Design 4, Build 15, Sprint 4 계획 1) (`da85ba2`)
- 글로벌 `~/.claude/settings.json` statusLine: 현재 모델 / 비용 / 200k 초과 / CWD 실시간 표시 (Opus→Sonnet fallback 즉시 인지)

### Changed
- `.gitignore`: `pipeline/state/`, `pipeline/artifacts/` 제외 규칙 제거 → 팀 공유 대상화 (`eecdb7c`)
- `CLAUDE.md`: 소규모 스타트업 팀 공유 전제 명시 + PIPELINE-GUIDE.md 참조 추가 + Spring Boot 3.4 → 3.5.0 일관성 (`eecdb7c`, `cdbacc5`)
- `docs/design/ai-agent-team-master.md`: `Opus 4.6` → `Opus 4.7` 14곳 치환 (1M 컨텍스트, 비용, MRCR 설명 전반) (`cdbacc5`)
- `.claude/commands/init-agent-team.md`: 기본 스택 `Spring Boot 3.4` → `3.5.0` (새 프로젝트 scaffolding 현행값) (`cdbacc5`)

### Committed
- Sprint 3 구현 (`022284e`): 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트 (19 files, +1346)
- Sprint 3 핸드오프 (`88aba9a`): CHANGELOG + HANDOFF
- 파이프라인 영속화 (`da85ba2`): decision-registry + sprint-4-plan
- 팀 공유 전환 (`eecdb7c`): pipeline/ 커밋 대상화 (22 files, +2369)
- 문서 업데이트 (`cdbacc5`): Opus 4.7 + Spring Boot 3.5.0 + PIPELINE-GUIDE

---

## [2026-04-17] Phase 3 Build Sprint 3 — 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트

### Added
- BacktestEngineService: 과거 3년 시그널 수익률 계산 + SignalType별 적중률/평균수익률 집계
- RunBacktestUseCase 포트 + POST /api/backtest/run API (API Key 보호, 기본 3년, 최대 5년)
- TelegramClient: RestClient 기반 Telegram Bot API 연동 (환경변수 비활성화 지원)
- TelegramNotificationService: 4가지 알림 시나리오 (일일 요약/A등급 긴급/배치 실패/주간 리포트)
- NotificationScheduler: 08:30 일일 요약 (월~금), 토요일 10:00 주간 리포트
- MarketDataBatchConfig notifyStep: 배치 완료 후 A등급 시그널 긴급 알림 자동 발송
- SignalRepository.findBySignalDateBetweenWithStock: JOIN FETCH 벌크 조회
- Testcontainers PostgreSQL 16 통합 테스트 인프라 (싱글톤 컨테이너 패턴)
- SignalDetectionServiceTest: 시그널 탐지 로직 5개 테스트 (급감/임계값/추세전환/숏스퀴즈/중복방지)
- BacktestEngineServiceTest: 수익률 계산 + 적중률 집계 + 데이터 부족 처리 4개 테스트
- BacktestApiIntegrationTest: API 인증/실행 5개 테스트
- SignalApiIntegrationTest: 시그널 조회/필터/인증 3개 테스트
- application.yml: telegram.bot-token, telegram.chat-id 환경변수 설정

### Changed
- API Key 비교: String.equals → MessageDigest.isEqual 상수 시간 비교 (타이밍 공격 방지, 3개 컨트롤러)
- API Key 미인증 시 403 → 401 UNAUTHORIZED 반환 (3개 컨트롤러)
- @Value 필드 주입 → 생성자 주입 전환 (BacktestController, BatchController, SignalDetectionController)
- BacktestEngineService: save() 루프 → saveAll() 일괄 저장
- MarketDataBatchConfig: SignalRepository 직접 주입 제거 → TelegramNotificationService.sendUrgentAlerts() 위임 (Hexagonal 경계 준수)
- MarketDataScheduler: 배치 실패 시 e.getMessage() 노출 → 클래스명만 텔레그램 발송
- BacktestController: @Validated 추가 + from/to 날짜 범위 검증 (최대 5년)
- TelegramNotificationService.sendBatchFailure: LocalDate → LocalDateTime (시간 정밀도)

---

## [2026-04-16] Phase 3 Build Sprint 2 — 시그널 엔진 + 대시보드

### Added
- SignalDetectionService: 3대 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) (`7902cfd`)
- POST /api/signals/detect 수동 시그널 탐지 API (`7902cfd`)
- Spring Batch detectStep 추가 (collectStep → detectStep 순차) (`7902cfd`)
- 프론트엔드 대시보드: 메트릭 카드 + 필터 탭 + 시그널 리스트 (`7902cfd`)
- 프론트엔드 종목 상세: 주가/대차잔고 듀얼 축 차트 (Recharts) (`7902cfd`)
- SignalCard 컴포넌트, TypeScript 타입 정의, API 클라이언트 (`7902cfd`)
- BacktestResult Entity + Repository + BacktestQueryService (`63407cd`)
- GET /api/backtest 백테스팅 결과 조회 API (`63407cd`)
- 프론트엔드 /backtest 페이지: 성과 테이블 + 보유기간별 수익률 Bar 차트 (`63407cd`)

### Changed
- 관리자 API 인증: IP allowlist → API Key 헤더(X-API-Key) 전환 (`e6754cb`)
- detail.volumeChangeRate 매핑 오류 수정 (`e6754cb`)
- scoreVolumeChange 음수 방지 Math.max(0, ...) 추가 (`e6754cb`)
- params.code 안전한 타입 처리 (Array.isArray 체크) (`e6754cb`)
- 프론트엔드 API 클라이언트 단일화 (중복 fetch 제거) (`e6754cb`)
- 미사용 변수 signalDates 제거 (`e6754cb`)

---

## [2026-04-16] Phase 3 Build Sprint 1 — 데이터 파이프라인 구축

### Added
- 16개 에이전트 AGENT.md + 공유 프로토콜 + 7개 슬래시 커맨드 scaffolding (`1908310`)
- Phase 1 Discovery 산출물 8건: 요구사항, PRD, 로드맵, 스프린트 플랜, GTM, 경쟁사 분석, 고객여정, 알림 시나리오 (`1908310`)
- Phase 2 Design 산출물 6건: 기능명세, 디자인 토큰, 컴포넌트 명세, ERD, DDL, 쿼리 전략 (`1908310`)
- Spring Boot 3.5.0 + Java 21 백엔드 프로젝트 (Hexagonal Architecture) (`33d7676`)
- Domain Entity 5개: Stock, StockPrice, LendingBalance, ShortSelling, Signal (`33d7676`)
- Repository 5개 (JPA 3단계 쿼리 전략), UseCase 2개, SignalQueryService (`33d7676`)
- REST API: GET /api/signals, GET /api/stocks/{code} (`33d7676`)
- GlobalExceptionHandler + sealed interface DomainError (`33d7676`)
- KRX 크롤러: 공매도/대차잔고/시세 수집 (요청 간격 2초) (`620f2bf`)
- Spring Batch Job + MarketDataScheduler (매일 06:00 스케줄) (`620f2bf`)
- 수동 배치 API: POST /api/batch/collect (localhost 제한) (`620f2bf`)
- docker-compose.yml: PostgreSQL 16 + DDL 자동 적용 (`620f2bf`)
- Next.js 15 + TypeScript 프론트엔드 프로젝트 초기화 (`33d7676`)
- UI/UX 프로토타입: Dark Finance Terminal 디자인 (prototype/index.html) (`33d7676`)
- .env.example (`620f2bf`)

### Changed
- Spring Boot 버전 3.4 → 3.5.0 (Spring Initializr 호환) (`33d7676`)
- JPA ddl-auto: validate → none (파티션 테이블 호환) (`140694b`)
- CORS allowedOrigins → allowedOriginPatterns + 헤더 제한 (`620f2bf`)
- MarketDataCollectionService: HTTP 수집을 트랜잭션 밖으로 분리 (`d710aa1`)
- 대차잔고 전 영업일 계산: minusDays(1) → 주말 건너뛰기 (`d710aa1`)
- 대차잔고 벌크 조회: 종목별 개별 쿼리 → findAllByTradingDate 1회 쿼리 (`d710aa1`)
- saveAll 벌크 저장으로 개별 exists/save 쿼리 제거 (`d710aa1`)
- BatchConfig → BatchConfig + Scheduler 분리 (Job Bean 직접 주입) (`d710aa1`)

---

## [2026-04-16] 프로젝트 초기 설정

### Added
- CLAUDE.md 생성 — 프로젝트 개요, 기술스택, 파이프라인, 에이전트 구조 가이드 (`fd26e75`)
- .gitignore 생성 — 빌드/IDE/환경파일 제외 설정 (`fd26e75`)
- GitHub 저장소 생성 (withwooyong/ted-startup, private) (`fd26e75`)
- AI Agent Team Platform 설계서 및 scaffolding 생성기 커밋 (`fd26e75`)
