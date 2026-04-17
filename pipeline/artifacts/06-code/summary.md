---
stage: 06-code
agent: 08-backend + 09-frontend
last_updated: 2026-04-17
status: sprint-4-completed
---

# Build Phase 산출물 요약

> Compaction 발생 시 이 파일만 읽으면 Build Phase 전체 구현 상태를 복구할 수 있습니다.

## 아키텍처 스택

| 영역 | 선택 |
|------|------|
| Backend | Spring Boot 3.5.0 + Java 21 (Hexagonal Architecture) |
| Frontend | Next.js 15 + TypeScript (App Router) |
| DB | PostgreSQL 16 (Docker Compose) |
| 쿼리 | Spring Data JPA 3단계 (QueryDSL 미사용) |
| 알림 | Telegram Bot API (RestClient) |
| 테스트 | JUnit 5 + Testcontainers PostgreSQL |
| 빌드 | Gradle (Groovy DSL) |
| 스케줄 | `@Scheduled` + Spring Batch Job |

## Sprint 1 — 데이터 파이프라인 (완료)

**커밋**: 33d7676, 620f2bf, d710aa1, 140694b

### 도메인 엔티티 5종
- `Stock` (6자리 종목코드, PK)
- `StockPrice` (일별 OHLCV + 거래대금 + 시가총액)
- `ShortSelling` (공매도 수량/금액/비율)
- `LendingBalance` (대차잔고 + 연속감소일수)
- `Signal` (시그널 타입/스코어/등급 + JSONB detail)

### 인프라
- KRX 크롤러: 3개 엔드포인트(가격/공매도/대차), 요청 간격 2초
- Spring Batch Job: `collectStep` (매일 06:00 KST, 월~금)
- PostgreSQL DDL 수동 적용 (`ddl-auto: none`, 파티션 호환)
- CORS `allowedOriginPatterns` + Virtual Threads 활성화

## Sprint 2 — 시그널 엔진 + 프론트엔드 (완료)

**커밋**: 7902cfd, e6754cb, 63407cd

### 시그널 탐지 알고리즘 3종 (`SignalDetectionService`)

| 시그널 | 트리거 | 스코어 공식 |
|--------|--------|-------------|
| RAPID_DECLINE | `changeRate < -10%` | `abs(changeRate)×3 + consecutiveDays×5 + 20` |
| TREND_REVERSAL | 5일MA < 20일MA 하향돌파 | `divergence×10 + speed×15 + 30` |
| SHORT_SQUEEZE | 4팩터 합산 ≥ 40 | balance(30) + volume(25) + price(25) + shortRatio(20) |

### 등급 체계
- A: ≥80, B: 60~79, C: 40~59, D: <40

### API (공개)
- `GET /api/signals?date&type`
- `GET /api/stocks/{code}?from&to`
- `GET /api/backtest`

### API (관리자, X-API-Key)
- `POST /api/batch/collect`
- `POST /api/signals/detect`

### 프론트엔드 페이지
- `/` 대시보드 — 시그널 리스트 + 필터 + 메트릭 카드
- `/stocks/[code]` 상세 — Recharts 듀얼축 차트 (주가+대차잔고)
- `/backtest` 결과 — 테이블 + Bar 차트

## Sprint 3 — 백테스팅 엔진 + 텔레그램 + 테스트 (완료)

**커밋**: 022284e, 88aba9a

### 백테스팅 엔진 (`BacktestEngineService`)
- 입력: 기간(from, to) — 기본 3년, 최대 5년
- 처리: 시그널별 N영업일 후 수익률 계산 (5/10/20일)
- 집계: SignalType별 적중률 (return > 0) + 평균수익률
- 성능: 종목별 `TreeMap<LocalDate, Long>` 기반 O(log n) 영업일 탐색
- API: `POST /api/backtest/run?from&to` (API Key 보호)

### 텔레그램 알림 4종 (`TelegramNotificationService`)
1. 일일 시그널 요약 — 매일 08:30 (월~금)
2. A등급 긴급 알림 — 배치 완료 후 즉시
3. 배치 실패 알림 — 예외 발생 시
4. 주간 성과 리포트 — 토요일 10:00

### 통합 테스트 18종
- `IntegrationTestBase` — Testcontainers 싱글톤 패턴
- `SignalDetectionServiceTest` (5): 급감/임계값/추세전환/숏스퀴즈/중복방지
- `BacktestEngineServiceTest` (4): 수익률 계산/적중률/데이터 부족/빈 기간
- `BacktestApiIntegrationTest` (5): 조회/인증/실행
- `SignalApiIntegrationTest` (3): 조회/필터/인증
- `SignalBackendApplicationTests` (1): contextLoads

### 코드리뷰 반영 (CRITICAL/HIGH)
- API Key 상수 시간 비교 (`MessageDigest.isEqual`) → 타이밍 공격 방지
- 401 Unauthorized (정보 누출 방지)
- `@Value` 필드 주입 → 생성자 주입 (3개 컨트롤러)
- `saveAll()` 일괄 저장
- Hexagonal 경계: Config에서 Repository 직접 접근 제거 → Service 위임
- `@Validated` + 날짜 범위 검증

## 패키지 구조

```
com.ted.signal
├── domain/
│   ├── enums/ (SignalType, SignalGrade)
│   └── model/ (Stock, StockPrice, ShortSelling, LendingBalance, Signal, BacktestResult, DomainError)
├── application/
│   ├── port/in/ (UseCase 인터페이스 6종)
│   ├── port/out/ (Repository 인터페이스 6종)
│   └── service/ (MarketDataCollection, SignalDetection, BacktestEngine, BacktestQuery, SignalQuery, TelegramNotification)
├── adapter/
│   ├── in/web/ (SignalController, BacktestController, SignalDetectionController, BatchController, GlobalExceptionHandler)
│   └── out/external/ (KrxClient, TelegramClient)
├── batch/
│   └── job/ (MarketDataBatchConfig, MarketDataScheduler, NotificationScheduler)
└── config/ (WebConfig)
```

## Sprint 4 Task 1-3 — 성능/보안 해소 (완료)

**커밋**: 33b6cf1

### 주요 변경
- **N+1 해소 (Task 1)**: `SignalDetectionService.detectAll` 17,500쿼리 → 7쿼리
  - 활성 종목 1회 + 당일 벌크 3건(lending/price/short) + 히스토리 2건(trend/volume, stockIds IN) + 기존 시그널 1건
  - `existsBy` 루프 제거, Set 기반 dedup
  - `sendDailySummary`는 `findBySignalDateWithStockOrderByScoreDesc`(JOIN FETCH) 사용
- **백테스팅 (Task 2)**: 최대 기간 5년 → 3년, 미래 날짜 차단, 주가 `findAllByStockIdsAndTradingDateBetween` 단일 쿼리
- **CORS (Task 3)**: `X-API-Key`, `OPTIONS`, `allowCredentials(true)`, `exposedHeaders` 추가

### 코드 리뷰 반영 (HIGH 3 + MEDIUM 2)
- JOIN FETCH 누락 3곳 수정 (StockPrice/ShortSelling `findAllByTradingDate`, Signal dedup 조회)
- `findAllByTradingDateBetween` 언바운디드 → `findAllByStockIdsAndTradingDateBetween` (활성 종목만)
- 백테스팅 `to` 미래 날짜 차단
- `detail.volumeChangeRate` 점수(int) 중복 → 실제 거래량 비율(BigDecimal) 저장

### 테스트 (20개, 전부 통과)
- 신규: `CorsConfigTest` 1개 + `BacktestApiIntegrationTest.runBacktestRejectsPeriodOverThreeYears` 1개
- 기존 18개 유지 (N+1 리팩터 후에도 동작 불변)

## Sprint 4 Task 5-6 — 프론트엔드 반응형/접근성 (완료)

**커밋**: 9436772

### 주요 변경
- **Task 5-4 글로벌 NavHeader (신규)**: sticky top, 햄버거 메뉴, ESC 키, `aria-current`, `aria-expanded`, `render-time 리셋` 패턴
- **Task 5-5 ErrorBoundary (신규)**: class 컴포넌트 + `resetKeys` 자동 복구 + `role="alert"`
- **Task 5-1 대시보드**: 중복 헤더 제거, 시그널 리스트 `grid-cols-1 lg:grid-cols-2`, `ul/li` 시맨틱, 필터 `role="group" + aria-pressed`
- **Task 5-2 종목 상세**: `ResponsiveContainer aspect={2}` (고정 300px → 비율 기반), 로딩 스켈레톤 반응형, `aria-busy`/`aria-live`
- **Task 5-3 백테스트**: 데스크탑 `<table>` vs 모바일 `<ul><li><dl>` 이중 렌더, YAxis 음수 포맷 수정
- **Task 6 접근성**: `focus-visible:ring-2` 전역 적용, `SignalCard` Link 단순화(중첩 div 제거), 모든 버튼 `type="button"`

### 코드 리뷰 반영 (HIGH 2 + MEDIUM 3 + LOW 1)
- `react-hooks/set-state-in-effect` ESLint 3건 → render-time 리셋 패턴 (D-4.7)
- `role="tablist"` 잘못된 패턴 → `role="group" + aria-pressed` (D-4.8)
- ErrorBoundary reset 루프 → `resetKeys` 지원 (D-4.6)
- `role="alert"` + `aria-live` 중복 제거
- YAxis formatter 음수 처리
- `aria-current="page"`는 exact match만

### 검증
- `tsc --noEmit` ✓ 0 에러
- `eslint src/` ✓ 0 에러
- `next build` ✓ 4 routes (/ /backtest /_not-found /stocks/[code])

### 신규 파일
- `src/frontend/src/components/NavHeader.tsx`
- `src/frontend/src/components/ErrorBoundary.tsx`

## 프로토타입 UI 실험 (커밋 `7a5b750`, 합류본 = ambient 확정)

| 파일 | 적용 효과 | 크기 | 상태 |
|------|----------|------|------|
| `index-before-skeleton.html` | baseline (보안 패치만) | 40KB | 비교 레퍼런스 |
| `index-tilt-magnetic.html` | + 3D 틸트 카드 + 마그네틱 버튼 | 50KB | 비교 레퍼런스 |
| `index-counter.html` | + 카운트업 애니메이션(32개) | 54KB | 비교 레퍼런스 |
| `index-ambient.html` | + Aurora 4-blob + 스포트라이트 + 파티클 네트워크 (누적본) | 61KB | **최종 합류본** |
| `index.html` | ambient 동일 내용 (캐노니컬) | 61KB | **엔트리** |

### ambient 탑재 효과 (D-4.10)
- **Aurora 배경**: 4개 blob(파랑/보라/빨강/주황) drift 애니메이션 42~74s, `filter:blur(90px)` + `mix-blend-mode:screen`, `prefers-reduced-motion` 존중
- **Skeleton UI**: `@keyframes skeleton-shimmer` 1.4s, 카드/테이블/차트 3개 모듈 로딩 상태
- **Tilt + Shine**: 메트릭/디테일 카드 마우스 추적 3D 회전 + `.tilt-shine` 광택 레이어
- **Magnetic 버튼**: 필터 탭에 커서 인력 효과 (class `magnetic`)
- **CountUp**: `data-count` + `data-duration` + `data-decimals` + `data-suffix` 속성 32개, Chart.js 4.4.7 + Pretendard Variable

**다음 단계** (Next.js 이식 설계):
- `aurora` → `<AuroraBackground />` fixed layer 컴포넌트
- `tilt` → `useTilt()` 훅 (mouse 이벤트 + ref)
- `count` → `useCountUp(target, duration)` 훅 (requestAnimationFrame)
- `magnetic` → `<MagneticButton>` 래퍼
- 이미 적용된 스켈레톤은 기존 `Loading` 상태에 `animate-pulse`로 동등 구현 확인

## Sprint 4 Task 4 — 알림 설정 페이지 (완료, 커밋 예정)

### 백엔드 신규/변경 (D-4.11)
- 엔티티: `NotificationPreference` (id=1 싱글 로우). 4채널 플래그(daily/urgent/batch/weekly) + `minScore`(0-100) + `signalTypes` JSONB
- 포트/서비스: `GetNotificationPreferenceUseCase`, `UpdateNotificationPreferenceUseCase`, `NotificationPreferenceService` (지연 생성 + 필터링용 fallback)
- 컨트롤러: `GET/PUT /api/notifications/preferences` + Bean Validation
- DDL 참고: `db/migration/V2__notification_preference.sql` (Flyway 도입 시 바로 적용)
- TelegramNotificationService 필터: 4채널 모두 preference 반영
  - `sendDailySummary`: enabled + signalTypes + minScore
  - `sendUrgentAlerts`: enabled + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: enabled
- GlobalExceptionHandler: `@Valid @RequestBody` 검증/역직렬화/도메인 IllegalArgument → 400

### 프론트 신규/변경
- `/settings` 페이지 (`src/app/settings/page.tsx`): 4개 스위치 토글(`role="switch"`) + 3개 시그널 타입 필터(`aria-pressed`) + minScore 슬라이더(`input[type=range]`) + 저장 버튼 + 토스트
- `src/types/notification.ts`: `NotificationPreference`/`NotificationPreferenceUpdate` 타입 + 채널 라벨
- `src/lib/api/client.ts`: `fetchApi`에 `RequestInit` 옵션, `getNotificationPreferences`/`updateNotificationPreferences`
- `NavHeader.tsx`: `/settings` 링크 추가

### 테스트 (9개 신규, 리뷰 반영 후 확장)
- `NotificationApiIntegrationTest`: 기본값 생성(1) / 인증 없음/잘못된 키 401(2) / 전체 업데이트 + 영속(1) / minScore 범위 400(1) / 알 수 없는 타입 400 + 응답 반사 없음 검증(1) / 빈 배열 400(1) / 4개 이상 400(1) / 필수 필드 누락 400(1)
- **전체 백엔드 테스트**: 29개(기존 20 + 신규 9) 모두 통과

### 리뷰 반영 (D-4.12)
- HIGH 4 + MEDIUM 9 전량 수정 (java/typescript/security 리뷰어 3종 병렬 실행 결과)
- `ApiKeyValidator` 컴포넌트로 3개 컨트롤러 중복 제거 (Backtest/SignalDetection/Batch)
- `IllegalArgumentException` 전역 캐치 제거 → `DomainException(DomainError.InvalidParameter)` 경로로 통일
- `UpdateCommand` record compact constructor가 검증 책임 소유 (Hexagonal 경계 교정)

## 알려진 이슈 (v1.1 이관)

| 심각도 | 이슈 | 비고 |
|--------|------|------|
| LOW | 한국 공휴일 미처리 | 현재 주말만 스킵 (v1.1) |
| LOW | CorsConfigTest 스코프 | `@SpringBootTest` → `@WebMvcTest` 분리 가능 |
| LOW | lockfile 중복 | `~/package-lock.json` + `src/frontend/package-lock.json` → `turbopack.root` 설정 권장 |
| LOW | Flyway 미도입 | 현재 `ddl-auto: create-drop`(테스트/로컬)에 의존. 프로덕션 전환 시 Flyway 도입 + V1/V2 순차 적용 |
