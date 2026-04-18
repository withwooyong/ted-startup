# Session Handoff

> Last updated: 2026-04-19 (KST, 밤 — 3년 백필 완료 · 본 세션 모든 작업 마감)
> Branch: `master` (origin 과 동기화 — 본 문서 커밋만 대기)
> Latest commit: `ecdabb5` — 세션 운영 문서 현행화: E2 + i + 3년 백필 착수 반영

## Current Status

**세션 목표 전 범위 완결.** §11 도메인(포트폴리오·AI 리포트) 의 운영 준비도 4축(기능 · 방어선 · 관측 · 데이터)을 모두 끌어올렸고, 마지막 남은 데이터 블로커였던 3년치 stock_price 실데이터까지 백그라운드 백필로 적재 완료(**752/752 성공, 실패 0**). E2(DART 단축명 필터 블랙리스트) · i(KRX market_type/stock_name 매핑 복구)까지 carry-over 청소. 남은 개선 후보는 전부 "선택적 고도화" 범주로, 차기 세션에서 곧바로 신규 기능 개발로 진입 가능.

### 운영 준비도 전후 비교

| 축 | Before (세션 진입) | After (세션 종료) |
|---|---|---|
| **기능** | P10~P15 코드 완료, 수동 시드 3건 한정 | 전체 상장사 실데이터 DB 보유 |
| **방어선** | AI 리포트 무제한 호출 가능 | 관리자 키 단위 30/min 쿼터 |
| **관측** | `/metrics` 외부 노출 가능성 | Caddy 404 차단 + 보안 헤더 |
| **데이터** | 주가 0 rows → UI 지표 `—` | 2.13M rows × 752 days 실데이터 |

## Completed This Session (13 커밋)

| # | Task | Commit | 비고 |
|---|------|--------|-----|
| 1 | P13-1 DART 벌크 sync 스크립트 | `43f07fd` | corpCode ZIP · 필터 2단 |
| 2 | P13-2 운영 보안 M1~M4 일괄 | `1c27c65` | /metrics IP 게이팅 · /health 마스킹 · uv digest · nologin |
| 3 | 문서 현행화 (1) | `99716af` | P13-1/P13-2 실측 |
| 4 | P13-3 slowapi rate limiting | `3e44ab6` | 관리자 키 단위 30/min |
| 5 | P13-4 KRX 교차 필터 | `e6d79e6` | 폐지 종목 제거 |
| 6 | 문서 현행화 (2) | `85245c4` | P13-3/P13-4 |
| 7 | β UI 시드 스크립트 | `a494863` | 데모 데이터 + 스냅샷 |
| 8 | 문서 현행화 (3) | `3c35295` | Z/β 실측 |
| 9 | KRX 어댑터 버그 2건 수정 | `bb8d2f2` | 시가총액 충돌 · KOSDAQ 누락 |
| 10 | 문서 현행화 (4) | `6ec57d5` | α 부분 성공 |
| 11 | E2 + i carry-over 처리 | `93a88ec` | DART 블랙리스트 + KRX market_type |
| 12 | 3년 백필 스크립트 | `c71a0fc` | 영업일 순회 CLI |
| 13 | 문서 현행화 (5) | `ecdabb5` | E2/i/백필 착수 |

**누적 규모**: 13 커밋 / 19 파일 / +1,287 / -95 라인.
**테스트**: 백엔드 **158/158 PASS** (기존 98 + 본 세션 신규 60). mypy strict 0 · ruff 0 (신규 파일).

## 실측 결과 스냅샷

### 3년 백필 (Bash id `bh6enx6xu`)

```
[backfill] 완료 — 총 752 일 · 성공 752 · 실패 0 · 소요 125분 38초
```

| 테이블 | Rows | Days | 범위 |
|---|---|---|---|
| `stock_price` | **2,130,316** | 752 | 2023-06-01 ~ 2026-04-17 |
| `short_selling` | **718,997** | 752 | 전 영업일 커버 |
| `lending_balance` | **668,322** | 699 | 53일 공백(공휴일·스키마 drift) |
| `stock` (distinct) | **3,098** | — | 현재 2,879 + 과거 상장폐지 219 |

### E2 실측 (블랙리스트 반영 후 dry-run)

| 지표 | 이전 | 현재 |
|---|---|---|
| DART 기본 필터 | 3,654 | **3,653** (-1, 088980 제거) |
| KRX 교차 후 | 2,538 | **2,537** (-1) |

### UI 실측 (D)

- 포트폴리오 페이지 · 계좌 탭 · 보유 테이블 · AI 리포트 버튼 정상
- 누적 수익률(3M) **+5.31%** (빨강 / 한국 관습) · MDD(3M) **-10.23%** (파랑)
- AI 리포트 페이지 캐시된 005930 리포트 렌더링 확인

### 보안 검증 (M1~M4)

- 외부 `https://localhost/metrics` → **HTTP 404**
- 외부 `https://localhost/internal/info` → **HTTP 404**
- 내부 `/health` → `{"status":"UP"}` (app/env 비공개)
- 내부 `/internal/info` → `{"status":"UP","app":"ted-signal-backend","env":"prod"}`
- `appuser` 로그인 셸 `/usr/sbin/nologin` 확인

## Known Issues

### 수정·검증 완료
전 13 커밋 참조. 운영 보안 · 벌크 동기화 · AI 리포트 쿼터 · KRX 어댑터 드리프트 2건 · DART 단축명 블랙리스트 · UI 시드 · 실데이터 3년 백필.

### 관찰(차후 개선)

- **`stock_name` 대량 누락(~2,874건)** — pykrx `get_market_ohlcv_by_ticker(market=ALL)` 이 종목명을 반환하지 않음. 현재 α 재실행 경로는 `upsert_by_code` 보호 규칙(`93a88ec`)으로 β 시드 이름은 보존되지만, 2,874건은 여전히 공백. `dart_corp_mapping` 조인(빠름) 또는 `get_market_ticker_name` 루프(느림) 선택.
- **`seed_ui_demo.py:run()` 90라인** — 코드 리뷰 M1 지적. 기능 중립 리팩터 권장. 차기 세션에서 선택적으로 수행.
- **`backfill` 공휴일 호출 최적화** — `is_trading_day` 를 import 해서 스킵하면 약 2-3분 단축. 일회성 실행이었으므로 우선순위 낮음.
- **3M UI 지표 기간 불확실** — 프론트가 `start=today-90일` 로 조회하는지 확인 필요. 현재는 실데이터 커버 범위(~2026-04-17) 가 넓어 정상 동작 예상.

### Carry-over (부분 해소 또는 미해소)

- **KRX 대차잔고 pykrx 스키마 불일치** — 과거 날짜에선 성공(952 rows/day), 최근 날짜에서만 실패. 이전에 "전면 fallback" 으로 판단했던 carry-over 의 실제 범위 대폭 축소.
- **Caddy unhealthy** — localhost self-signed 한정. 실도메인 모드에선 자동 해소.
- **Docker Desktop bind mount 휘발성** — Caddyfile 수정 시 `docker compose restart caddy` 필수. 절차 문서화 완료.

## Context for Next Session

### 즉시 할 일

1. **본 문서 커밋 + 원격 푸시** — `CHANGELOG.md` / `HANDOFF.md` 변경분.

### 다음 우선 후보 (모두 선택적)

- **stock_name 실명 복구** — `dart_corp_mapping` 조인 또는 pykrx 이름 lookup. 2,874건 공백 해소. ~30분(조인 방식) ~ ~2시간(lookup 방식).
- **I. Frontend Playwright 회귀 테스트** — UI 렌더링 자동화. 0.5일 규모. 본 세션에서 수동 실측 PASS 했으므로 차기 보강 차원.
- **M1 리팩터 (`seed_ui_demo.py:run()` 분할)** — 리뷰 지적. 기능 중립. 15분.
- **백필 공휴일 스킵** — `is_trading_day` import. 10분.
- **γ. KIS REST 주가 조회 전환** — 근본 해결이지만 pykrx 만으로 현재 운영 가능한 상태라 우선순위 하향. ~1일.
- **H. force_refresh 조건부 rate limiting** — 현재 엔드포인트 전체 30/min 으로 충분. 우선순위 낮음.
- **`BrokerAdapter` Protocol 추출** — 키움 합류 시점 전까지 미필요.

### 사용자의 원래 목표 (달성)

주식 시그널 탐지·백테스팅 서비스 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) MVP. **본 세션으로 기능 → 운영 준비 → 방어선 → 데이터 복구까지 4축 전부 도달**. 차기 세션은 신규 기능 개발(시그널 탐지 개선, 알림 고도화 등) 또는 UI 자동화 테스트 등 다음 단계로 전환 가능.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단** — 컨테이너 내부 env 접근으로 우회
- **작업 단위 커밋 분리 선호**
- **리뷰 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호**
- **실측 마무리 선호** — 코드/테스트 PASS 만으로 종결하지 않고 실 환경 검증까지
- **병렬 작업 가능 시 병렬** — 본 세션은 최대 3트랙 (A+B+D) 동시 진행

### 가치있는 발견

1. **백필 대량 실행 패턴** — urllib + admin key + 배치 endpoint 반복의 간단 패턴으로 752영업일을 실패 0건 + 125분 안에 완료. 재사용 가능한 백필 템플릿 확보.
2. **pykrx schema drift 의 시간 의존성** — `lending_balance` 가 2026-04-17 에선 실패(`0`)하지만 2023-11 부터는 정상(`952`). 즉 carry-over "pykrx 스키마 불일치" 는 범주로 단순화하면 안 되고 날짜별 동작 차이로 기록해야 함.
3. **`upsert_by_code` 의 빈 이름 보호** — pykrx 가 종목명을 안 주는 경로를 명시적으로 방어. 한 줄 로직이지만 β 시드 회귀를 원천 차단.
4. **테스트 병렬 확장** — 본 세션 신규 테스트 60건 중 대부분이 `@pytest.mark.parametrize` 기반 경계값 표. 유지보수 비용 대비 회귀 방지 효과 우수.
5. **병렬 워크플로 3트랙** — A(DB 배치 백그라운드) + B(코드 작성) + D(사용자 브라우저 실측). 각 트랙이 서로 간섭하지 않도록 분리 설계.

## Files Modified This Session (누적)

```
 CHANGELOG.md                                       |  +90 / -11 (6개 섹션 prepend)
 HANDOFF.md                                         |  (본 산출물)
 pipeline/artifacts/10-deploy-log/runbook.md        |  §2.4 stamp 002 정정
 ops/caddy/Caddyfile                                |  +14 / -3 (M1/M2)
 src/backend_py/Dockerfile                          |  +9 / -2 (M3/M4)
 src/backend_py/app/main.py                         |  +25 / -2 (slowapi + /internal/info)
 src/backend_py/app/config/settings.py              |  +8 (rate limit)
 src/backend_py/app/adapter/web/_rate_limit.py      |  +28 (신규)
 src/backend_py/app/adapter/web/routers/reports.py  |  +11 / -1 (rate limit)
 src/backend_py/app/adapter/out/external/dart_client.py | +47 / -1 (corpCode ZIP)
 src/backend_py/app/adapter/out/external/krx_client.py  | +73 / -17 (i 매핑 + 버그 2건)
 src/backend_py/app/adapter/out/persistence/repositories/stock.py | +13 / -2 (이름 보호)
 src/backend_py/scripts/__init__.py                 |  +1 (신규)
 src/backend_py/scripts/entrypoint.py               |  +8 / -3 (stamp 002)
 src/backend_py/scripts/sync_dart_corp_mapping.py   | +245 (신규 + KRX 교차 + E2)
 src/backend_py/scripts/seed_ui_demo.py             | +294 (신규)
 src/backend_py/scripts/backfill_stock_prices.py    | +121 (신규)
 src/backend_py/scripts/validate_env.py             | +3 / -2 (KIS 자리수)
 src/backend_py/app/application/port/out/llm_provider.py | +1 (schema)
 src/backend_py/pyproject.toml                      |  +1 (slowapi)
 src/backend_py/uv.lock                             |  +28
 src/backend_py/tests/test_health.py                |  +14 / -1
 src/backend_py/tests/test_analysis_report.py       |  +56 (rate limit)
 src/backend_py/tests/test_sync_dart_corp_mapping.py|  +355 (신규 + E2)
 src/backend_py/tests/test_seed_ui_demo.py          | +112 (신규)
 src/backend_py/tests/test_backfill_stock_prices.py |  +37 (신규)
 src/backend_py/tests/test_krx_client.py            |  +85 (i + 버그 수정)
 src/backend_py/tests/test_repositories.py          |  +29 (이름 보호)
```

본 세션은 **작업 완성 + 실측 마감 + 문서 동기화** 3박자를 13 커밋에 걸쳐 반복. 차기 세션은 신규 기능 또는 선택적 고도화로 자연스럽게 전환 가능.
