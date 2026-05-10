# phase-c-backfill-daily-flow.md — Phase C-backfill-daily-flow (ka10086 백필 CLI)

## 0. 메타

| 항목 | 값 |
|------|-----|
| chunk 명 | **C-backfill-daily-flow** (ka10086 일별 수급 백필) |
| 범위 | `scripts/backfill_daily_flow.py` 신규 CLI + `mrkcond.py` since_date + `daily_flow_service.py` ETF 가드 + since_date 전파 |
| 분할 | **단일 chunk** — CLI 1개 + 어댑터/UseCase 확장 + 테스트 |
| 선행 chunk | C-2β (`e442416`) IngestDailyFlowUseCase 완료 / C-backfill (OHLCV) 운영 실측 완료 (`12f0daf`) |
| 우선순위 | **P1** — daily_flow 운영 진입 전 3년 백필 + NUMERIC magnitude 측정 |
| 분류 | **일반 기능 (general)** — scripts 신규, 보안/계약/Migration 변경 없음 (UseCase 시그니처 in-process 확장) |
| 운영 실측 | **본 chunk 범위 외** — CLI 코드 + 단위 테스트만. 실측은 사용자 수동 실행 후 별도 결과 정리 (OHLCV 백필 패턴 동일) |
| 관련 plan doc | [`endpoint-10-ka10086.md`](./endpoint-10-ka10086.md) / [`phase-c-backfill-ohlcv.md`](./phase-c-backfill-ohlcv.md) |

> **본 doc 의 역할**: chunk 단위 응집 정보 (영향 범위 / self-check / DoD). CLI 인자 명세 / 알고리즘은 § 3 에 직접 명시.

---

## 1. 목적

**3년 daily_flow (ka10086) 백필 스크립트** — `IngestDailyFlowUseCase` 의 1년 cap 을 우회해 과거 시계열 일괄 적재. OHLCV 백필 (`backfill_ohlcv.py`) 의 발견된 운영 차단 fix 3건 (since_date guard / `--max-stocks` 정상 적용 / ETF 호환 가드) 을 처음부터 동일 패턴으로 내장.

**측정 도구로서의 역할** (사용자 수동 실행):

1. **페이지네이션 빈도** — ka10086 1 페이지 ~300 거래일 추정 (계획서 § 12.7) vs 실측 (3년 = 750 거래일 → 2~3 페이지)
2. **3년 백필 시간** — active 4078 종목 × KRX 2초 rate-limit 직렬화. OHLCV 34분 대비 페이지네이션 추가로 +α 추정
3. **NUMERIC magnitude 분포** — `change_rate` / `foreign_holding_ratio` / `credit_ratio` 실제 값 분포. 한도 초과 시 컬럼 확장 결정 (별도 Migration chunk)
4. **빈 응답 / ETF skip 비율** — OHLCV 4078 fetch 시도 / DISTINCT 4077 적재 (1 종목 빈 응답) 와 일치하는지 cross-check

**본 chunk 의 산출물**: CLI 그 자체 + dry-run mode + 단위 테스트. 실제 운영 실측은 사용자 환경에서 추후 수동 실행.

---

## 2. 범위 외 (Out of Scope)

- **운영 실측 자체** — 사용자 수동 실행. 본 chunk 는 CLI + 가드 패턴까지 (OHLCV 일관)
- **NUMERIC 컬럼 magnitude 확장** — 실측 후 필요 시 별도 Migration chunk
- **scheduler_enabled 운영 cron 활성** — 별도 follow-up chunk (HANDOFF Pending #2)
- **ETF/ETN OHLCV 별도 endpoint** — 옵션 (c) 별도 chunk
- **resume 의 분산 lock** — 단일 프로세스 가정 (OHLCV 백필 일관)

---

## 3. CLI 명세

### 3.1 인자

```bash
python scripts/backfill_daily_flow.py \
    --alias <kiwoom_credential_alias>     # 필수
    [--years N]                            # 디폴트 3
    [--start-date YYYY-MM-DD]              # 명시 시 --years 무시
    [--end-date YYYY-MM-DD]                # 디폴트 today
    [--indc-mode {quantity,amount}]        # 디폴트 quantity (백테스팅 시그널 단위 일관)
    [--only-market-codes 0,10,...]         # 디폴트 전체 5 시장
    [--only-stock-codes 005930,000660]     # 디폴트 active 전체. 디버그 용
    [--dry-run]                            # 종목 수 + 페이지 + 시간 추정만, DB 미적재
    [--resume]                             # 이미 적재된 종목 (max(trading_date) >= end_date) skip
    [--max-stocks N]                       # 처음 N 종목만 (디버그)
    [--log-level {DEBUG,INFO,WARNING}]     # 디폴트 INFO
```

### 3.2 동작 흐름

```
1. 인자 검증 (resolve_date_range / market_codes 화이트리스트 / alias 등록 여부 — UseCase 위임)
2. settings + DB 연결 + KiwoomMarketCondClient 빌드 (lifespan 외부, OHLCV 백필 패턴 동일)
3. _count_active_stocks (only_market_codes / only_stock_codes / max_stocks 반영)
4. resume / max_stocks 시 explicit_stock_codes 산출 (compute_resume_remaining_codes — table=stock_daily_flow)
5. dry-run mode 면 추정값 출력 + return 0
6. UseCase.execute(base_date=end_date, since_date=start_date, only_market_codes=..., only_stock_codes=effective_codes, _skip_base_date_validation=True, indc_mode=...)
7. format_summary + exit code (failed > 0 면 1, 0 이면 0)
```

### 3.3 종료 코드

- `0`: 모든 종목 success (failed = 0)
- `1`: 부분 실패 (failed > 0)
- `2`: 인자 검증 실패 / alias 미등록
- `3`: 시스템 오류 (DB / settings)

---

## 4. 어댑터/서비스 변경

### 4.1 `mrkcond.py` — `fetch_daily_market` since_date 추가

`chart.py` 의 `fetch_daily` since_date 패턴 그대로 응용:

- `since_date: date | None = None` 파라미터 신규 (디폴트 None — 운영 cron 기존 동작 유지)
- 페이지의 가장 오래된 row date 가 `since_date <=` 면 다음 페이지 stop
- 마지막 페이지 fragment (since_date 보다 과거 row) 는 응답에서 제거
- ka10086 응답 정렬 신→구 가정 (계획서 § 6.1 — ka10081 와 같은 의미)
- 헬퍼: `_page_reached_since_market` / `_row_on_or_after_market` (DailyMarketRow 의 `date` 필드는 8자리 `YYYYMMDD` string — `_parse_yyyymmdd` 적용)

### 4.2 `daily_flow_service.py` — `IngestDailyFlowUseCase` 확장

OHLCV daily_service 패턴 그대로 응용:

- `execute(*, only_stock_codes=None, _skip_base_date_validation=False, since_date=None)` 파라미터 추가
- `refresh_one(*, _skip_base_date_validation=False)` 파라미터 추가
- `_KA10086_COMPATIBLE_RE = re.compile(STK_CD_LOOKUP_PATTERN)` 모듈 상수 신규
- raw_stocks 조회 후 `fullmatch` 사전 필터 + skip 로깅 (sample 5)
- `_ingest_one` 에 `since_date` 전달 (mrkcond.fetch_daily_market 까지 propagate)
- `_validate_base_date(skip_past_cap=True)` 분기 (OHLCV 백필 H-1 일관)

---

## 5. 영향 범위 / 위험 self-check

| # | 영향 / 위험 | 완화 |
|---|------------|------|
| H-1 | UseCase 시그니처 확장으로 router 호환성 깨질 가능성 | 모든 신규 파라미터 디폴트값 — 운영 라우터 / cron 호환 (OHLCV 일관) |
| H-2 | mrkcond.py since_date 마지막 페이지 fragment 제거 시 빈 응답 | `_row_on_or_after_market` 가 빈 dt (`date.min`) keep — Repository 가 skip 안전망 (OHLCV 일관) |
| H-3 | dry-run 시간 추정의 ±50% margin | OHLCV 와 동일 — log message 명시. 실측 후 results.md 보강 |
| H-4 | `--resume` 시 `stock_daily_flow.trading_date` max 기준 — 부분 적재 (일부 일자만) gap 미감지 | OHLCV 와 동일 한계 — gap detection 별도 chunk |
| H-5 | exit code 정책 — failed > 0 시 1 | OHLCV 와 동일 (CLI 운영 자동화 호환) |
| H-6 | `_build_use_case` 의 graceful close (try/finally) | OHLCV 백필 동일 — `kiwoom_client.close()` + `engine.dispose()` 보장 |

---

## 6. DoD 체크리스트

- [ ] **단위** — `tests/test_kiwoom_mrkcond_client.py` since_date 페이지네이션 종료 + fragment 제거 (+2 cases)
- [ ] **단위** — `tests/test_ingest_daily_flow_service.py` ETF/ETN skip + since_date 전파 (+3 cases)
- [ ] **단위** — `tests/test_backfill_daily_flow_cli.py` 신규 — argparse / resolve_date_range / dry-run / max-stocks / resume / format_summary / exit_code (~+10 cases)
- [ ] **정적 분석** — `ruff check` + `mypy --strict` PASS
- [ ] **테스트 + 커버리지** — `pytest --cov` 80%+ 유지 (현재 993 → ~1003 cases)
- [ ] **STATUS.md / HANDOFF.md / CHANGELOG.md / ADR § 26.6** 동시 갱신
- [ ] **plan doc 본 § 7 운영 미해결** 채울 자리 신설 (운영 실측 결과 별도 chunk)

---

## 7. 운영 미해결 (실측 후 채움)

| # | 항목 | 결과 | 결정 |
|---|------|------|------|
| 1 | 페이지네이션 빈도 | TBD | TBD |
| 2 | 3년 백필 elapsed | TBD | TBD |
| 3 | NUMERIC change_rate / foreign_holding_ratio / credit_ratio | TBD | TBD |
| 4 | 빈 응답 / ETF skip 비율 | TBD | TBD |
