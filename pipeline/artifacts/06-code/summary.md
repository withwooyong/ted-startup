---
stage: 06-code
agent: 08-backend + 09-frontend
last_updated: 2026-04-17
status: sprint-4-task-1-3-completed
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

## 알려진 이슈 (Sprint 4 Task 4-5 이관)

| 심각도 | 이슈 | 비고 |
|--------|------|------|
| MEDIUM | 알림 설정 페이지 미구현 | NotificationPreference 엔티티 + /settings 신규 필요 |
| LOW | 모바일 반응형 미적용 | `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` 등 |
| LOW | ErrorBoundary 없음 | Recharts 렌더링 에러 크래시 가능 |
| LOW | 접근성 감사 | WCAG AA + 키보드 내비게이션 |
| LOW | 한국 공휴일 미처리 | 현재 주말만 스킵 (v1.1) |
| LOW | CorsConfigTest 스코프 | `@SpringBootTest` → `@WebMvcTest` 분리 가능 |
