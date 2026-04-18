# Session Handoff

> Last updated: 2026-04-19 (KST, 저녁 — E2/i 커밋 후 3년 백필 백그라운드 기동 직후)
> Branch: `master` (origin 대비 3 커밋 앞서 — 푸시 대기, 본 문서 커밋 포함 시 4)
> Latest commit: `c71a0fc` — 백필 스크립트: 3년 영업일 stock_price 순회 수집

## Current Status

**E2(DART 단축명 필터) + i(KRX market_type/stock_name 매핑 복구) 를 같은 세션에 해소하고, 3년(752영업일) 실데이터 백필을 백그라운드 기동.** 어댑터 수정으로 α 잔여 이슈(2,874건 market_type 단일·이름 공백) 구조적 원인을 제거했고, `StockRepository.upsert_by_code` 가 빈 이름은 덮어쓰지 않도록 방어해 β 시드 회귀도 차단. 테스트 146 → 158. 백필 실행(Bash id `bh6enx6xu`)은 약 2시간 예상이며 완료 보고는 차기 세션 인계.

## Completed This Session (전 세션에서 이어지는 단일 세션 스트림)

| # | Task | Commit | Files / 결과 |
|---|------|--------|--------------|
| 1 | P13-1 DART 벌크 sync 스크립트 | `43f07fd` | dart_client, scripts, tests |
| 2 | P13-2 운영 보안 M1~M4 | `1c27c65` | Caddyfile, Dockerfile, main.py |
| 3 | 운영 문서 현행화(1) | `99716af` | HANDOFF, CHANGELOG, runbook |
| 4 | P13-3 slowapi rate limiting | `3e44ab6` | _rate_limit, main.py, reports.py, settings |
| 5 | P13-4 KRX 교차 필터 | `e6d79e6` | sync_dart_corp_mapping |
| 6 | 운영 문서 현행화(2) | `85245c4` | HANDOFF, CHANGELOG |
| 7 | β UI 회귀 검증 시드 | `a494863` | seed_ui_demo.py, 테스트 10건 |
| 8 | 운영 문서 현행화(3) | `3c35295` | HANDOFF, CHANGELOG (β/Z 반영) |
| 9 | α KRX 어댑터 버그 2건 수정 | `bb8d2f2` | krx_client.py, test_krx_client.py |
| 10 | 운영 문서 현행화(4) | `6ec57d5` | HANDOFF, CHANGELOG (α/carry-over) |
| 11 | E2 + i carry-over 처리 | `93a88ec` | sync_dart, krx_client, stock repo, tests |
| 12 | 백필 스크립트 | `c71a0fc` | backfill_stock_prices + test |

**누적 규모(전체 세션)**: 12 커밋 / +2,000 라인 내외.
**테스트**: 백엔드 **158/158 PASS** (기존 98 + 본 세션 신규 60). mypy strict 0, ruff 0 (신규 파일).

### α 배치 실측 결과 (`POST /api/batch/collect?date=2026-04-17`)
| 지표 | 값 | 비고 |
|---|---|---|
| `stocks_upserted` | 2,879 | KOSPI+KOSDAQ 합집합 |
| `stock_prices_upserted` | 2,879 | 2026-04-17 종가 |
| `short_selling_upserted` | 949 | KOSPI 만 (pykrx 제약) |
| `lending_balance_upserted` | 0 | 기존 carry-over, fallback 동작 |
| `elapsed_ms` | 5,302 | |
| `stock_name` 채워진 건수 | 5 (β 복구) / 2,879 | **잔여 2,874건 공백 — carry-over i** |
| `market_type` 고유 값 | `{KOSPI}` | **KOSDAQ 미매핑 — carry-over i** |

### 실측 스냅샷

| 항목 | Before | After |
|---|---|---|
| DART → dart_corp_mapping | 수동 3건 | **3,654건** (벌크) |
| KRX 교차 필터 (Z) | — | **2,538건** (1,116 축소) |
| 외부 `/metrics` | 이론상 노출 | **HTTP 404** (Caddy 차단) |
| 외부 `/internal/info` | — | **HTTP 404** (Caddy 차단) |
| 내부 `/health` body | `{status,app,env}` | `{"status":"UP"}` |
| AI 리포트 엔드포인트 쿼터 | 무제한 | **30/min** (관리자 키 단위) |
| UI 수익률(3M)/MDD(3M) | `—` | **+5.31% / -10.23%** |
| UI stock_price 데이터 | 0 rows | **450 rows** (5종목×90일) |
| UI portfolio_snapshot | 0 rows | **90 rows** |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **원격 푸시** | pending | 본 문서 커밋 포함 4건 |
| 2 | **3년 백필 완료 확인** | 백그라운드 진행 중 | Bash id `bh6enx6xu`. 752영업일 × 약 10초/일 ≈ 125분. 로그 파일 `/private/tmp/.../bh6enx6xu.output`. 차기 세션에서 성공/실패 카운트 집계 후 마감 |
| 3 | **stock_name 실명 복구** | carry-over | 현재 α 재실행 시 market_type 은 정확하지만 stock_name 은 공백 유지. dart_corp_mapping 조인 또는 pykrx 티커별 이름 lookup(rate limit 2시간+) 필요 |
| 4 | **E2 블랙리스트 DB 반영** | 보류 | `sync_dart_corp_mapping` 재실행으로 088980/423310 삭제 확인. β 가 시드한 5 종목에 포함 안 되므로 UI 영향 없음 |
| 5 | **slowapi Redis 백엔드** | 보류 | multi-worker 확장 전까지 불필요 |
| 6 | **force_refresh 조건부 rate limiting** | 보류 | 현재 엔드포인트 전체 30/min 으로 충분 |
| 7 | **Frontend Playwright 회귀 테스트** | 보류 | UI 렌더링 실측은 했지만 자동화 없음. 0.5일 규모 |
| 8 | **`BrokerAdapter` Protocol 추출** | 보류 | 키움 합류 전까지 미필요 |
| 9 | **Caddy unhealthy** | 관찰 | localhost self-signed 한정 |

## Key Decisions Made (본 세션 전체 누적)

1. **필터 2단 + 교차 1단** — DART 보통주·이름 필터 → KRX 현재 상장 교차. pykrx 실패 시 fallback 설계.
2. **`.env.prod` KRX 크리덴셜 이미 설정됨** — Z 실측 과정에서 우연히 드러남. α 가 "크리덴셜 설정 필요" 가 아니라 "배치만 돌리면 됨" 상태.
3. **AI 리포트 rate limit 은 엔드포인트 전체** — slowapi 데코레이터 한계. 30/min 이 정상 사용엔 여유.
4. **rate limit key = API Key 우선, IP fallback** — 관리자 키 노출 시 IP 우회 무력화.
5. **시드 스크립트는 wipe 시 stock 보존** — `portfolio_holding.stock_id` FK 제약 때문. stock_price/portfolio_snapshot 만 기간 내 정리하고 stock 은 upsert 경로로 덮음.
6. **UI 파생 지표는 `portfolio_snapshot` 의존** — `stock_price` 만으론 부족. β 가 이를 반영해 activeaccount × 날짜별 snapshot 을 현재 holdings × 해당일 종가로 재구성.
7. **Caddyfile 수정 시 `docker compose restart caddy` 필수** — Docker Desktop bind mount 의 inode 추적 한계.
8. **실측 마무리 원칙** — 코드/테스트 PASS 에 그치지 않고 실 환경 검증까지.

## Known Issues

### 본 세션 수정·검증 완료
- `43f07fd` DART 벌크 sync + 어댑터
- `1c27c65` 운영 보안 4건
- `3e44ab6` AI 리포트 rate limiting
- `e6d79e6` KRX 교차 필터
- `a494863` UI 시드 (파생 지표 복구)
- `bb8d2f2` KRX 어댑터 버그 2건(시가총액 충돌·KOSDAQ 누락)
- `93a88ec` E2 DART 블랙리스트 + i KRX market_type/이름 보존
- `c71a0fc` 3년 백필 스크립트

### 본 세션 관찰(차후 개선)
- **DART 단축명 매칭 누락** — 맥쿼리인프라(088980) 가 `"인프라투융자회사"` 패턴과 매칭 실패해 통과. 패턴 보강 필요(E2 작업).
- **3M 기간의 기준 시점 불명확** — UI 가 `start=today-90일`로 호출하는지 확인 필요. β 시드 범위(2025-12-15~2026-04-17)가 UI 조회 범위와 일치해야 카드가 의미있는 값.
- **허구 스냅샷 vs 실제 거래 이력 불일치** — β 는 현재 holdings 를 과거에도 유지했다고 가정. 실제 거래 replay 는 하지 않음. UI 검증 용도로만 허용.
- **α 적재 이후 stock_name·market_type 대량 누락** — pykrx `get_market_ohlcv_by_ticker(market=ALL)` 반환 스키마 한계. 2,874건 공백. carry-over i 로 이관.
- **과거 N일 백필 미수행** — 2026-04-17 단일 날짜만 실데이터. 3M 범위 실데이터를 보려면 영업일별 반복 collect 필요. 우선순위 낮음(β 시드로 회귀 차단 가능).

### Carry-over (부분 해소 또는 미해소)
- **KRX 익명 차단** — α 가 즉시 가능함이 드러나 "실질 carry-over" 는 해소 임박. 실행 안 돼있을 뿐.
- **KRX 대차잔고 pykrx 스키마 불일치** — 어댑터 fallback 중.
- **Caddy unhealthy** — localhost self-signed 한정.
- **Docker Desktop bind mount 휘발성** — `docker compose restart caddy` 로 우회 가능.

## Context for Next Session

### 즉시 할 일

1. **원격 푸시** — `a494863` + 본 문서 업데이트 커밋.
2. **α 실행(선택)** — 이미 가능 상태. 배치 스케줄러를 prod 모드로 기동하거나, 관리자 run/collect 엔드포인트로 수동 trigger. 실 주가/시가총액 데이터로 stock_price 복구 + portfolio_snapshot 자연 축적.

### 다음 우선 후보

- **α.** KRX 실데이터 배치 실행. `scheduler_enabled=True` 로 재기동하거나 `/api/admin/batch/run` 수동 트리거. ~30분.
- **E2.** DART 단축명 필터 보강. 맥쿼리인프라류 수동 블랙리스트 또는 "맥쿼리" 접두 대응. ~15분.
- **I.** Frontend Playwright 회귀 테스트 최소 세트 — 포트폴리오 페이지 · AI 리포트 페이지 렌더링. ~0.5일.
- **γ.** KIS REST 주가 조회 전환 — 근본 해결, 구조 변경 동반. ~1일.
- **H.** force_refresh 조건부 rate limiting — 엔드포인트 분리 리팩터. 우선순위 낮음.

### 사용자의 원래 목표 (carry-over)
주식 시그널 탐지·백테스팅 서비스 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) MVP. **본 세션 누적으로 기능 완성 → 운영 준비 → 방어선 → 데이터 복구까지 달성**. 남은 건 실 주가 데이터 경로(α)와 UI 자동 회귀(I) 두 가지 정도.

### 사용자 선호·제약 (재확인)
- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단** — 컨테이너 내부 env 접근이 유효한 우회
- **작업 단위 커밋 분리 선호**
- **리뷰 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호**
- **실측 마무리 선호**
- **병렬 작업 가능 시 병렬** — 본 세션은 A+B+D, Z+β 두 병렬 트랙으로 진행

### 사용자에게 공유할 가치있는 발견

1. **α 는 사실상 환경 기준 준비 완료** — `.env.prod` 에 `KRX_ID` 가 이미 있고 pykrx 로그인 성공도 확인됨. "크리덴셜이 없어서 못한다" 가 아니라 "배치만 돌리면 된다" 상태. 차기 세션에서 30분 이내 해결 가능.
2. **UI 파생 지표의 의존 체인** — `stock` → `stock_price` → `portfolio_snapshot` (최소 2건) → Metric 카드. 어느 하나만 있어도 렌더링 실패. β 가 체인을 완전체로 시드하면서 UI 회귀 검증의 데이터 블로커가 처음으로 해소됨.
3. **DART 단축명 매칭 누락** — 필터 패턴을 정식명 기준으로 작성했지만 실제 DART 가 일부 법인을 단축명으로 저장. 향후 블랙리스트형 패턴 또는 KRX 종목명과 교차 필터링으로 보완.
4. **병렬 워크플로의 이득 관찰** — A(백그라운드 실행) + B(코드 작업) + D(브라우저 실측) 3트랙, Z(컨테이너 재빌드 대기) + β(스크립트 작성) 2트랙. 세션 효율 상승 체감.

## Files Modified This Session (누적)

```
 CHANGELOG.md                                          | 대폭 갱신(3개 섹션 추가)
 HANDOFF.md                                            | (본 산출물)
 pipeline/artifacts/10-deploy-log/runbook.md           | §2.4 stamp 002 정정
 ops/caddy/Caddyfile                                   | +14 / -3 (M1/M2)
 src/backend_py/Dockerfile                             | +9 / -2 (M3/M4)
 src/backend_py/app/main.py                            | +25 / -2 (slowapi·/internal/info)
 src/backend_py/app/config/settings.py                 | +8 (rate limit)
 src/backend_py/app/adapter/web/_rate_limit.py         | +30 (신규)
 src/backend_py/app/adapter/web/routers/reports.py     | +11 / -1 (rate limit)
 src/backend_py/app/adapter/out/external/dart_client.py| +47 / -1 (corpCode ZIP)
 src/backend_py/scripts/__init__.py                    | +1 (신규)
 src/backend_py/scripts/entrypoint.py                  | +8 / -3 (stamp 002)
 src/backend_py/scripts/sync_dart_corp_mapping.py      | +245 (신규 + KRX 교차)
 src/backend_py/scripts/seed_ui_demo.py                | +235 (신규)
 src/backend_py/scripts/validate_env.py                | +3 / -2 (KIS 자리수)
 src/backend_py/app/application/port/out/llm_provider.py | +1 (schema)
 src/backend_py/pyproject.toml                         | +1 (slowapi)
 src/backend_py/uv.lock                                | +28 (lock)
 src/backend_py/tests/test_health.py                   | +14 / -1
 src/backend_py/tests/test_analysis_report.py          | +56
 src/backend_py/tests/test_sync_dart_corp_mapping.py   | +265 (신규)
 src/backend_py/tests/test_seed_ui_demo.py             | +112 (신규)
```

본 세션은 **기능 완성 + 운영 준비 + 방어선 + 데이터 복구** 의 연쇄 작업을 단일 스트림으로 처리. 매 단계에서 **실측 마무리** 원칙을 지켜 차기 세션 인수 비용 최소화.
