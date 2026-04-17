---
agent: "04-marketing"
mode: "analytics"
stage: "11-analytics"
version: "1.0.0"
created_at: "2026-04-17T21:00:00+09:00"
depends_on:
  - "pipeline/artifacts/01-requirements/requirements.md"
  - "pipeline/artifacts/02-prd/prd.md"
  - "pipeline/artifacts/02-prd/gtm-strategy.md"
  - "pipeline/artifacts/02-prd/sprint-plan.md"
  - "pipeline/artifacts/08-review-report/review-report.md"
  - "pipeline/state/current-state.json"
quality_gate_passed: false
---

# 런칭 애널리틱스 리포트 & KPI 플랜 — v1.0

> 본 문서는 **v1.0 단일 운영자 내부 도구**의 런칭 이후 모니터링 체계를 정의한다. SaaS 전환 시 재활용 가능한 AARRR 지표는 섹션 C에 참고용으로만 수록한다.

---

## A. 런칭 개요

### v1.0 스코프 요약 (Sprint 1~4)

| 스프린트 | 기간 | 핵심 산출물 (1-line) | 상태 |
|---------|------|---------------------|------|
| Sprint 1 | Week 1~2 | Spring Boot Hexagonal 스캐폴딩 + KRX 공매도/시세 크롤러 + Spring Batch 일 1회 스케줄 + Docker PostgreSQL | completed (commit `140694b`) |
| Sprint 2 | Week 3~4 | 3대 시그널 엔진(급감/추세전환/숏스퀴즈) + Next.js 대시보드·상세·백테스트 페이지 + Recharts 듀얼 차트 | completed (commit `63407cd`) |
| Sprint 3 | Week 5~6 | 백테스팅 엔진(3년) + 텔레그램 4채널 알림 + Testcontainers 통합 테스트 18건 | completed (commit `88aba9a`) |
| Sprint 4 | Post-MVP 강화 | N+1 쿼리 제거 + 모바일 반응형 + ErrorBoundary(resetKeys) + `/settings` 알림 필터 + 프로토타입 Ambient UI 이식 | completed (commit `fa38b43`) |

### 배포 타깃

- **v1 대상**: 운영자 1인 (개발자 본인). 내부 Docker 환경에서 단일 인스턴스.
- **데이터 범위**: KOSPI + KOSDAQ 전 종목(~2,500개) × 시계열 3년.
- **채널**: 웹 대시보드(`http://localhost:3000`) + 텔레그램 Bot 알림(BEARWATCH 채널).
- **확장 가능성**: v2 이후 외부 사용자 개방 시 인증/멀티테넌시/SaaS 플랜 도입 예정(`docs/PIPELINE-GUIDE.md` 로드맵 참조). GTM 전략(`gtm-strategy.md`)과 AARRR 지표가 그 시점에 활성화된다.

---

## B. 성공 지표 (KPI) — 운영 관점

v1에서 운영자가 **주간 루틴으로 확인해야 할 4개 차원**이다.

### B-1. 시그널 품질

| 지표 | 목표 (Baseline) | 측정 방법 | 데이터 소스 |
|------|-----------------|-----------|-------------|
| 5거래일 적중률 | ≥ 60% (양수 수익률 비율) | 백테스팅 주간 실행 리포트 | `backtest_result` 테이블, `BacktestEngineService` 집계 |
| 10거래일 적중률 | ≥ 55% | 백테스팅 주간 실행 리포트 | 동일 |
| 20거래일 적중률 | ≥ 50% | 백테스팅 주간 실행 리포트 | 동일 |
| 시그널별 평균 수익률 | 5d: ≥ +2%, 10d: ≥ +3%, 20d: ≥ +4% | 시그널 타입별(RAPID_DECLINE / TREND_REVERSAL / SHORT_SQUEEZE) 분리 집계 | 동일 |
| 실적중률 vs 백테스팅 gap | abs(gap) ≤ 10%p | 실제 발령 시그널의 5일 후 수익률 → 백테스팅 예상치와 비교 | `signal` 테이블 + `stock_price` join |

> **Baseline 확정 절차**: 런칭 직후 D+1~D+3일 사이 최초 백테스팅 수행 → 해당 값을 공식 baseline으로 고정. 이후 주간 편차 모니터링.

### B-2. 시스템 안정성

| 지표 | 목표 | 측정 방법 | 데이터 소스 |
|------|------|-----------|-------------|
| 배치 정시 실행률 | ≥ 95% (PRD 정의), 실제 운영 목표 99% | 일 1회 배치 성공 건수 / 전체 영업일 | Spring Batch 메타데이터 (`BATCH_JOB_EXECUTION`) |
| KRX 데이터 수집 latency | < 10분 (NFR-001) | 수집 시작~완료 소요시간 | `MarketDataCollectionService` 로그 + Micrometer timer |
| API P95 | < 500ms (일반) / < 5s (`POST /api/backtest/run`) | Spring Actuator `/actuator/metrics/http.server.requests` | Micrometer |
| 에러율 | < 1% (5xx 기준) | 5xx 응답 수 / 전체 요청 수 | Spring Actuator |
| 대시보드 초기 로딩 | < 3초 (PRD KPI) | 브라우저 Performance API 또는 Lighthouse | 주간 수동 측정 |
| DB 디스크 사용량 | < 80% | `pg_database_size` + `df -h` | docker stats / cron 스크립트 |

### B-3. 알림 효용성

> v1에서는 운영자 본인이 유일한 사용자이므로 "응답성"은 정성 평가이다. 수치화 가능한 부분은 **발송 성공률**과 **발송 지연**에 집중한다.

| 지표 | 목표 | 측정 방법 | 데이터 소스 |
|------|------|-----------|-------------|
| Telegram 발송 성공률 | ≥ 99% | 200 응답 / 발송 시도 수 | `TelegramClient` 로그, `notification_log` 테이블(추가 권장) |
| 일일 시그널 알림 정시성 (08:30 KST) | 08:30 ± 2분 내 도달 | 텔레그램 수신 timestamp vs schedule | Telegram Bot API 응답 로그 |
| 4채널 필터 정확성 (daily / urgent / batch / weekly) | 수신자 설정과 100% 일치 | `NotificationPreference` 설정값 vs 실제 발송 로그 교차 검증 | `notification_preference` + `notification_log` |
| 운영자 주관적 유용성 | 주간 회고 점수 ≥ 4/5 | 주간 자가 평가 | 운영 로그 (`docs/` 아래 주간 노트) |

### B-4. 배포 운영

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 배포 빈도 | v1 안정화 기간 주 1회 이하 (핫픽스 제외) | Git tag / deploy log |
| 롤백 횟수 | 월 0~1회 | `pipeline/artifacts/10-deploy-log/` |
| MTTR (장애 평균 복구 시간) | < 30분 (배치 실패 기준) | 장애 발생~복구 timestamp |
| Docker 재시작 횟수 | 계획된 변경 외 0회 | `docker events` / `docker inspect` |

---

## C. SaaS 전환 대비 KPI (AARRR) — 참고용

> **v1 추적 대상 아님.** v2 이후 외부 사용자 개방 시점에 활성화하기 위한 참조 지표. GTM 전략 문서(`pipeline/artifacts/02-prd/gtm-strategy.md`)와 상호 참조.

| 단계 | 정의 | 측정 방법 | 제안 목표 (v2 런칭 후 3개월) |
|------|------|-----------|-------------------------------|
| **Acquisition** | SEO/커뮤니티를 통해 랜딩 페이지에 도달한 순 방문자 | GA4 또는 Plausible `users` 지표, UTM 분석 | MAU 1,000명 |
| **Activation** | 가입 후 첫 시그널 수신까지 완료 (텔레그램 연동 포함) | 이벤트 트래킹 (`signup_completed` → `first_signal_received`) | 전환율 ≥ 40%, 소요시간 < 3분 |
| **Retention** | 주간 활성 사용자 / 월간 활성 사용자 | DAU/MAU ratio, Telegram 알림 open 추정(링크 클릭) | DAU/MAU ≥ 20% |
| **Revenue** | 유료 전환(프리미엄 플랜, 예: 실시간 알림/고급 스코어링) | MRR, ARPU, 무료→유료 전환율 | 유료 전환율 ≥ 5%, MRR $500 |
| **Referral** | 시그널 적중 사례 공유 → 신규 가입 | K-factor, 추천 링크 파라미터 | K ≥ 0.2 |

**주의**: 위 목표치는 "공매도 분석" 관련 국내 투자자 커뮤니티 유입을 전제로 하며, 실제 런칭 시 baseline 수집 후 재조정 필요.

---

## D. 측정 도구 / 데이터 소스

| 데이터 출처 | 수집 대상 | 비고 |
|-------------|-----------|------|
| **DB 내부 테이블** | `signal`, `backtest_result`, `notification_preference`, (권장 추가) `notification_log` | 시그널 품질/알림 효용성의 근거. 주간 집계 쿼리로 대시보드 생성 가능 |
| **Spring Actuator `/actuator/metrics`** | `http.server.requests`, `jvm.memory.used`, `executor.active` | Micrometer 등록 필요 (현재 미적용 → 런칭 직후 추가 권장) |
| **Spring Batch 메타데이터** | `BATCH_JOB_EXECUTION`, `BATCH_STEP_EXECUTION` | 배치 성공률/duration 자동 저장 |
| **Telegram Bot API 응답** | `TelegramClient` 로그, HTTP 상태코드(200/401/429/5xx) | 스택트레이스 로깅은 B-M4에서 핫픽스 예정 |
| **Docker stats / logs** | 컨테이너 CPU/Memory, 로그 파일 | `docker stats`, `docker logs --since` 기반 크론 스크립트 |
| **Postgres 시스템 뷰** | `pg_stat_statements`, `pg_database_size`, 파티션별 행 수 | 느린 쿼리 조기 탐지 |
| **외부 트래킹 도구** | 적용 대상 아님 (Google Analytics 등) | v1은 단일 운영자 내부 도구 — 사용자 행동 분석 불필요 |

### 권장 신규 구성요소 (D+7 이내)

1. **`notification_log` 테이블**: `id, channel, payload_hash, sent_at, http_status, error_message`. 현재 `TelegramClient` 로그만으로는 장기 통계 불가.
2. **Micrometer + Prometheus endpoint**: `management.endpoints.web.exposure.include=health,metrics,prometheus`.
3. **주간 KPI 집계 SQL 뷰** (`v_weekly_signal_quality`): 시그널 타입별 발령수/적중률/평균수익률 한 번에 조회.

---

## E. 첫 4주 모니터링 계획

### Week 1 — 안정화 확인 (Stability Gate)

| 체크포인트 | 목표 | 실패 시 대응 |
|-----------|------|-------------|
| 배치 성공률 | ≥ 99% (7 영업일) | 2회 이상 실패 시 KRX 스크레이퍼 점검 |
| 일일 시그널 탐지 정상 작동 | 매일 시그널 건수 > 0, 3종 시그널 타입 모두 발령 관찰 | 단일 타입만 발령 시 파라미터 재검토 |
| Telegram 발송 성공률 | ≥ 99%, 08:30 ±2분 도달 | 401(토큰) 또는 429(레이트) 발생 시 즉시 조치 |
| 수동 재수집 1회 시도 | 멱등성(`B-H3` 해소) 검증 | 유니크 제약 충돌 발생 시 롤백 |

### Week 2 — 백테스팅 vs 실적 비교 (Signal Quality Gate)

- 주간 백테스팅 자동 실행 → 5/10/20일 적중률 리포트 생성
- **실제 D-7 시그널의 5일 후 수익률**을 최신 `stock_price`로 재계산 → 백테스팅 예상치와 비교
- Gap이 15%p 초과 시 과적합(RISK-004) 의심 → Walk-forward 검증 강화 우선순위 상향

### Week 3 — 시그널 품질 튜닝 진단

- 시그널 타입별 false positive 집계 (5일 후 수익률 < -5%인 발령 수)
- 숏스퀴즈 스코어 구간(0~100)별 실제 적중률 분포 확인 → 임계값(기본 70) 재조정 판단
- 필요 시 FR-010(임계값 커스터마이징)을 v1.1 우선순위로 상향

### Week 4 — v1.1 우선순위 결정

- `known_issues` + review-report MEDIUM 9건을 **impact/effort 매트릭스**로 재평가 (G 섹션 참조)
- Top 3 핫픽스 픽업 → Sprint 5 킥오프
- 운영자 주간 회고: 실제 투자 판단에 기여도 ≥ 3/5인지 주관 평가

---

## F. 실패 조기 감지 시그널 (Red Flags)

| # | 시그널 | 탐지 방법 | 임계 | 대응 |
|---|--------|-----------|------|------|
| F1 | **KRX API/크롤링 차단** (RISK-003) | 수집 배치 HTTP 403/429 또는 HTML 포맷 변경 | 단일 발생 | 즉시 User-Agent / IP 확인, 공식 Open API 전환 준비 |
| F2 | **연속 3영업일 배치 실패** | Spring Batch `EXIT_STATUS=FAILED` 연속 카운트 | 3회 | 데이터 수집 레이어 전면 점검, Telegram batch failure 알림 확인 |
| F3 | **Telegram 401 / 429 지속** | `TelegramClient` 에러율 | 1시간 내 3회+ | 401: 봇 토큰 재발급. 429: exponential backoff 적용(B-M4 핫픽스) |
| F4 | **DB 디스크 사용량 80% 초과** | `df -h` / `pg_database_size` | ≥ 80% | 월별 파티션 아카이빙 실행, 3년 보관 정책(NFR-007) 확인 |
| F5 | **시그널 적중률 급락** | 주간 백테스팅 결과 | 연속 2주 50% 미만 | 시장 체제 변화(market regime shift) 가능성 — 임계값/가중치 재조정 |
| F6 | **실적중률 vs 백테스팅 gap 확대** | 주간 비교 | gap > 15%p | 과적합(RISK-004) 의심 → Walk-forward 검증 재실행 |
| F7 | **JVM Heap 사용량 > 85%** | Actuator `jvm.memory.used` | 5분 지속 | 배치 중 메모리 누수 의심 — heap dump 확보 |
| F8 | **운영자 미확인 알림 3일 연속** | Telegram 읽음 추정 (주관) | 3일 | 채널 과포화 여부 점검, `/settings` minScore 상향 조정 |

> **1순위 red flag**: **F2 (연속 3영업일 배치 실패)**. 배치가 실패하면 시그널 생성 자체가 멈추고 downstream(알림/백테스팅) 전체가 무력화되므로 가장 높은 블라스트 반경을 갖는다. B-H3 해소로 1차 방어선은 확보했지만, 대응 플레이북이 필수.

---

## G. v1.1 기능 우선순위 제안 (Impact × Effort Matrix)

`current-state.json`의 `known_issues` 3건 + review-report의 MEDIUM 9건(Backend 5 + Frontend 4)을 impact(운영/사용자 영향)와 effort(구현 공수)로 2차원 분류했다.

### 매트릭스

| Impact \ Effort | **Low (≤ 0.5d)** | **Mid (1~2d)** | **High (> 2d)** |
|----------------|------------------|-----------------|------------------|
| **High** | **[Q1] B-M4** 텔레그램 스택트레이스 로깅<br>**[Q2] F-M2** 한국 타임존 표시 수정 | **[Q3] B-M1** Backtest 400 응답 스키마 통일<br>**[Q4] korean-holidays** 공휴일 캘린더 도입 | **[Q5] F-M1** TanStack Query 도입 (4페이지 리팩터) |
| **Mid** | **[Q6] B-M3** `Map.of` null 가드 | **[Q7] B-M2** SignalDetection 트랜잭션 범위 분리 | **[Q8] F-L1** 프론트 컴포넌트/E2E 테스트 스위트 |
| **Low** | **[Q9] lockfile-duplicate** 제거<br>**[Q10] B-L2** CORS 환경변수화 | **[Q11] B-M5** KrxClient rate-limit 리팩터<br>**[Q12] cors-test-scope** `@WebMvcTest` 분리 | — |

### v1.1 Top 5 (권장 작업 순서)

1. **Q1 (B-M4) 텔레그램 스택트레이스 로깅** — 0.5d, 운영 관측성 즉시 향상. F3 red flag 진단 속도 단축.
2. **Q2 (F-M2) 타임존 표시 수정** — 0.5d, 사용자(운영자) 혼란 제거. 매일 아침 00:00~09:00 KST 윈도우 버그.
3. **Q3 (B-M1) Backtest 400 응답 통일** — 1d, 프론트 에러 UX 정상화.
4. **Q4 (korean-holidays) 공휴일 캘린더** — 1~2d, 설날/추석 이후 `changeRate=0` 버그 원천 차단. **D+60 전후 연휴 도래 시점 역산**해서 최우선 적용.
5. **Q5 (F-M1) TanStack Query 도입** — 3d, 프론트 재검증/캐시/AbortController 일괄 해결. Sprint 5 킥오프의 핵심 기반 작업.

### v1.2 이후 (Deferred)

- Q7, Q8, Q11, Q12는 기능/보안 영향이 낮아 v1.2 백로그에 보관.
- FR-009 (시장 전체 동향), FR-010 (임계값 커스터마이징), FR-011 (워치리스트) 등 PRD 상 deferred 기능은 v1.1~v2 분리 판단 (G 섹션 실적 기반 재평가).

---

## 부록. 주간 KPI 리포트 템플릿

매주 금요일 18:00 KST에 운영자가 수동 확인하거나 크론으로 자동 집계:

```sql
-- 주간 시그널 발령수 + 5d 적중률
SELECT
  signal_type,
  COUNT(*) AS signal_count,
  ROUND(100.0 * SUM(CASE WHEN return_5d > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(return_5d), 0), 2) AS hit_rate_5d,
  ROUND(AVG(return_5d)::numeric, 4) AS avg_return_5d
FROM v_weekly_signal_quality
WHERE signal_date BETWEEN CURRENT_DATE - INTERVAL '7 days' AND CURRENT_DATE
GROUP BY signal_type;
```

```sql
-- 주간 배치 성공률
SELECT
  DATE(start_time) AS run_date,
  job_name,
  exit_status,
  end_time - start_time AS duration
FROM batch_job_execution
WHERE start_time >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY start_time DESC;
```

---

## 면책 고지

본 시스템은 투자 자문이 아닌 정보 제공 목적의 참고 도구이다. 모든 투자 판단과 그에 따른 결과의 책임은 투자자 본인에게 있으며, 과거 성과(백테스팅 수치 포함)가 미래 수익을 보장하지 않는다.
