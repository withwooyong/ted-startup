# phase-c-chart-alphanumeric-guard — 우선주/특수 종목 chart stk_cd 가드 완화 (옵션 c-A)

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | 신규 도메인 확장 (chart endpoint stk_cd 호환성). 외부 API 호출 범위 확장 + 내부 가드 분리 |
| 범위 | 영문 포함 6자리 (우선주/특수) — chart 계열 (ka10081/82/83/94 + ka10086) 가드 완화. lookup 계열 (ka10100/ka10001) 은 Excel R22 ASCII 제약 유지 |
| 출처 | STATUS § 5 #1 "ETF/ETN OHLCV 별도 endpoint (옵션 c)" / `phase-c-refactor-r2-defer-cleanup.md` § 6 #2. 사용자 분기 선택 — 옵션 A (가드 완화만, 2026-05-11) |
| 선행 chunk | R2 (`d43d956`) + follow-up 분석 (`e8d9d38`) 완료. Phase C 97% |
| 우선순위 | P1 — Phase C 종결 성격. Phase D 진입 전 마무리 |
| 분량 추정 | Chunk 1 (dry-run, 코드 0) = 임시 스크립트 1 + 문서 1 / Chunk 2 (가드 완화) ~ 코드 5 + 테스트 4 + 문서 4 |
| 진행 모드 | **Chunk 1 → 결과 확인 → Chunk 2** (사용자 결정, 2026-05-11). Chunk 1 실패 시 NO-FIX 결정 후 종결 |

## 1. 목적

ka10099 sync 가 stock 마스터에 영문 포함 6자리 코드(우선주/특수, 약 295종목 추정)를 적재하지만, chart 계열 UseCase 의 `_KA10081_COMPATIBLE_RE = ^[0-9]{6}$` 가드가 이를 skip — OHLCV/일별수급 누락.

가드는 `stkinfo.STK_CD_LOOKUP_PATTERN` 을 보수적으로 재사용한 결과이고, Excel docs 의 정의 근거는 **ka10100 R22 "Length=6 ASCII 0-9"** (lookup endpoint 제약). 차트 endpoint (ka10081/82/83/94/86) 가 영숫자 6자리 (`00088K`) 를 실제로 받는지는 docs 부재 → **운영 dry-run 선행 필수**.

본 chunk 는 두 단계:
1. **Chunk 1** — 운영 dry-run 1~3건 (코드 0). 키움 chart API 가 영숫자 코드를 받는지 확정
2. **Chunk 2** — Chunk 1 결과 SUCCESS 시 가드 분리 (`STK_CD_CHART_PATTERN` 신규) + chart 계열 라우터/어댑터/UseCase 적용. lookup 계열은 ASCII 제약 유지

## 2. 범위 외 (Out of Scope)

- ka10100 / ka10001 lookup 계열 stk_cd 가드 완화 (Excel R22 명시 ASCII 제약 유지)
- ETF 시장 (`market_code=8`) 신규 수집 — `master.md` § 0.3 결정 ("ETF/ELW/금현물 제외") 그대로
- NXT suffix (`_NX`/`_AL`) 처리 변경 — 기존 `build_stk_cd` 동작 유지
- 신규 ORM / 신규 Migration / 신규 Repository / 신규 백필 CLI
- 우선주 자동 백필 운영 — Chunk 2 머지 후 cron 자연 수집 또는 사용자 결정 별도 chunk
- ka10001 펀더멘털 영숫자 호출 — lookup 계열이라 본 chunk 범위 밖. 향후 운영 데이터 검증 후 별도 결정
- `stock.stock_code` 컬럼 길이 변경 — 현재 VARCHAR(20) 이고 6자리 영숫자는 그대로 적합

> **외부 동작 영향**: chart 계열 endpoint 의 호출 대상 stock 수가 ~3,800 → ~4,100 (+8%) 으로 증가. 운영 cron elapsed 비례 증가 (2초 rate limit 직렬화 — 300 종목 × 2초 = 10분 추가 추정). 사용자 사전 인지 필요.

## 3. Chunk 1 — 운영 dry-run (코드 0)

### 3.1 절차

| Step | 작업 | 산출물 |
|------|------|--------|
| 1 | DB 조회 — 영문 포함 6자리 active 종목 1~3건 식별 | `dry-run-results.md` § 1 |
| 2 | 임시 스크립트 `scripts/dry_run_chart_alphanumeric.py` 신규 — ka10081 (일봉) + ka10086 (일별수급) 단건 호출. **가드 일시 우회** (`_KA10081_COMPATIBLE_RE` 무시) | `scripts/dry_run_chart_alphanumeric.py` |
| 3 | 사용자 수동 실행 (`uv run python scripts/dry_run_chart_alphanumeric.py 00088K`) | stdout log + ADR 기록 |
| 4 | 응답 검증 — `return_code=0` + `items` 비어있지 않음 + price/volume 정상 | `dry-run-results.md` § 2 |
| 5 | 결과 분기 결정 | ADR § 32 |

### 3.2 결과 분기

| 결과 | 의미 | 다음 |
|------|------|------|
| **SUCCESS** (return_code=0 + items 있음) | 키움 chart API 가 영숫자 6자리 수용 | Chunk 2 진행 |
| **FAIL — return_code≠0** | 키움이 영숫자 stk_cd 거부 | NO-FIX 결정. ADR § 32 기록 후 chunk 종결. 295 종목 skip 정책 유지 |
| **FAIL — empty response** | 키움이 형식은 받지만 데이터 없음 (sentinel) | NO-FIX 또는 부분 적용 (Chunk 2 진행하되 빈 응답 처리 확인). 사용자 결정 필요 |
| **MIXED** (3건 중 일부만 SUCCESS) | 우선주 유형별로 다름 | Chunk 2 범위 재정의 (특정 prefix 만 허용 등). 사용자 결정 |

### 3.3 dry-run 스크립트 설계

```python
# scripts/dry_run_chart_alphanumeric.py (요지)
# - argv: stock_code (영숫자 6자리), 옵션 base_date (YYYYMMDD)
# - 가드 우회: KiwoomChartClient 직접 호출 — UseCase 거치지 않음
# - build_stk_cd 호출 우회: 직접 dict body 구성 + httpx 호출 또는 build_stk_cd 임시 패치
# - 출력: response status / return_code / items 개수 / 첫 row dict
# - 토큰: 기존 token_manager.get_or_issue() 재사용 (실 자격증명 사용)
```

> **운영 안전장치**: 단건 호출. 2초 rate limit 자연 준수. 응답은 stdout 만 — DB 적재 0. 실패 시 자연 종료. 비밀값 마스킹은 `KiwoomAuthClient` 기존 패턴 그대로.

### 3.4 산출물 (Chunk 1)

- `scripts/dry_run_chart_alphanumeric.py` — 임시 스크립트 (Chunk 2 머지 시 삭제 또는 유지 — 사용자 결정)
- `docs/operations/dry-run-chart-alphanumeric-results.md` — dry-run 결과 1~2 page (영업일 / 응답 / 결정)
- ADR § 32 — 결과 기록 + Chunk 2 진입 결정 또는 NO-FIX

## 4. Chunk 2 — 가드 완화 (Chunk 1 SUCCESS 시)

### 4.1 패턴 분리 — `stkinfo.py`

| 변경 | 내용 |
|------|------|
| `STK_CD_LOOKUP_PATTERN: Final[str] = r"^[0-9]{6}$"` (기존) | **그대로** — ka10100 / ka10001 lookup. Excel R22 ASCII 명시 |
| `STK_CD_CHART_PATTERN: Final[str] = r"^[0-9A-Z]{6}$"` (신규) | chart 계열 (ka10081/82/83/94 + ka10086). 영숫자 대문자 허용. lowercase / 특수문자 거부 유지 |
| `_STK_CD_CHART_RE = re.compile(STK_CD_CHART_PATTERN)` (신규) | adapter 사전 검증용 |

> **lowercase 거부 유지** 이유: 키움 응답 / 마스터 데이터 모두 uppercase 만 관찰됨. lowercase 입력은 mock/test 사고 또는 공격 패턴이라 거부 유지. dry-run 에서 lowercase 통과 여부도 부수 검증 가능.

### 4.2 adapter — chart.py / mrkcond.py

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/adapter/out/kiwoom/stkinfo.py` | `build_stk_cd:439` | 가드 정규식을 `_STK_CD_LOOKUP_RE` (lookup) 에서 `_STK_CD_CHART_RE` (chart) 로 교체. 함수 docstring 갱신 — "6자리 ASCII 숫자" → "6자리 영숫자 대문자" |
| `app/adapter/out/kiwoom/chart.py` | line 10 (module docstring) | "stock_code 6자리 ASCII 사전 검증" → "stock_code 6자리 영숫자 (build_stk_cd)" |
| `app/adapter/out/kiwoom/mrkcond.py` | line 10 | 동일 정정 |

> `build_stk_cd` 는 chart + mrkcond 양쪽 공유 — 단일 함수 가드 교체로 두 adapter 모두 일관 적용.

### 4.3 router Path pattern (chart 계열만)

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/adapter/web/routers/ohlcv.py` | line 239, 342 (ka10081 sync/refresh) | `pattern=STK_CD_LOOKUP_PATTERN` → `pattern=STK_CD_CHART_PATTERN` |
| `app/adapter/web/routers/ohlcv_periodic.py` | line 306, 358, 410 (ka10082/83/94) | 동일 |
| `app/adapter/web/routers/daily_flow.py` | line 211, 314 (ka10086) | 동일 |
| `app/adapter/web/routers/stocks.py` | line 265, 304 (ka10100) | **변경 없음** — lookup 그대로 |
| `app/adapter/web/routers/fundamentals.py` | line 232, 323 (ka10001) | **변경 없음** — lookup 그대로 |

### 4.4 UseCase active_stocks filter

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/application/service/ohlcv_daily_service.py` | line 51-54 | `_KA10081_COMPATIBLE_RE = re.compile(STK_CD_LOOKUP_PATTERN)` → `STK_CD_CHART_PATTERN`. 변수명 `_KA10081_COMPATIBLE_RE` 유지 (의미 동일 — endpoint 호환 패턴) |
| `app/application/service/ohlcv_periodic_service.py` | line 51 | 동일 |
| `app/application/service/daily_flow_service.py` | line 163 부근 | 동일 |

> 변수명 변경 (`_KA10081_..._RE` → `_CHART_COMPATIBLE_RE`) 옵션도 있으나 본 chunk 는 가드 분리에 집중 — 변수명은 그대로 유지 (변경 시 import / docstring 누적). 추후 별도 cleanup chunk 가능.

### 4.5 영향 받는 로깅

`%s 호환 가드 — active %d 중 %d 종목 skip (ETF/ETN/우선주 추정)` 로그 메시지 갱신:
- skip 카운트가 크게 줄어듦 (~295 → ~0) — 정상 동작
- 로그 메시지의 "ETF/ETN/우선주 추정" 표현 갱신 — "non-ASCII 6자리" 또는 단순 "패턴 불일치" 로 일반화. 295 → 0 으로 줄어도 잔여는 여전히 비정상 (예: 5자리 입력) 이라 메시지 유지가 적합

### 4.6 테스트 (Chunk 2)

| 파일 | 변경 |
|------|------|
| `tests/test_stkinfo.py` (또는 build_stk_cd 테스트 파일) | (1) `build_stk_cd("00088K", KRX)` SUCCESS / (2) `build_stk_cd("00088k", KRX)` 거부 (lowercase) / (3) `build_stk_cd("00088!", KRX)` 거부 (특수문자) / (4) `STK_CD_LOOKUP_PATTERN` 영숫자 거부 단언 (lookup 계열 보호) |
| `tests/test_ohlcv_router.py` 또는 `test_ohlcv_periodic_router.py` 또는 `test_daily_flow_router.py` | chart 계열 라우터 path 가 영숫자 통과 + lookup 계열 (stocks/fundamentals) 라우터 path 가 영숫자 거부 (422) 단언 — 각 1~2 case |
| `tests/test_ohlcv_daily_service.py` (또는 동등) | UseCase active_stocks filter 가 영숫자 종목을 keep + skip 카운트 감소 단언 |
| 회귀 — 기존 `^[0-9]{6}$` 단언 테스트 | 모든 기존 단언이 lookup 계열 또는 거부 케이스인지 검토. chart 계열 거부 단언이 있다면 영숫자 허용으로 갱신 필요 (testcontainers 자동 발견 가능성) |

> **예상 신규 cases 4~8 — 1037 → ~1045**. 정확한 수는 기존 테스트 거부 단언 수에 따라 가감.

### 4.7 문서 (Chunk 2)

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 32 (Chunk 1 결과) + § 33 (Chunk 2 결과) 신규
- `src/backend_kiwoom/STATUS.md` 갱신 — § 6 chunk 누적 + § 5 #1 해소 + § 0 한눈에 보기 갱신
- `HANDOFF.md` 전체 갱신
- `CHANGELOG.md` prepend — `feat(kiwoom): chart stk_cd 영숫자 가드 완화 — STK_CD_CHART_PATTERN 신규 (옵션 c-A)`

## 5. 적대적 사전 self-check (H-1 ~ H-10)

| # | 위험 | 완화 |
|---|------|------|
| **H-1** | chart adapter 가 영숫자 받는다는 가정 검증 부재 | **Chunk 1 dry-run 절대 선행** — 1~3건 운영 호출 후 응답으로 확정. dry-run 실패 시 Chunk 2 진입 차단 |
| **H-2** | lookup endpoint (ka10100/ka10001) 가 영숫자로 호출되면 wire-level 거부 또는 KiwoomBusinessError | 라우터 Path 가드 LOOKUP 유지로 422 사전 차단. adapter `_validate_stk_cd_for_lookup` 도 LOOKUP 패턴 그대로 — 이중 가드 |
| **H-3** | 기존 테스트의 `^[0-9]{6}$` 단언이 chart 계열에 잔존 | grep `"\\^\\[0-9\\]\\{6\\}\\$"` + `"6자리 ASCII"` 로 전체 testcase 검사 — chart 계열 거부 케이스가 있으면 영숫자 허용 단언으로 갱신 (testcontainers 가 자동 fail) |
| **H-4** | NXT suffix 종목 `00088K_NX` 가 키움에 존재 가능 | dry-run 시 ka10081 KRX + NXT 양쪽 호출. NXT 응답 형식 확인. 받지 않으면 `_NX` suffix 영숫자는 NXT skip (`yearly_nxt_disabled` 패턴 응용) |
| **H-5** | `build_stk_cd` 가 영숫자 lowercase / unicode digit 거부 유지 검증 | `STK_CD_CHART_PATTERN = ^[0-9A-Z]{6}$` 가 `re.fullmatch` 로 매칭 — lowercase / unicode 자동 거부. 단위 테스트로 명시 단언 |
| **H-6** | 295 종목 중 일부만 chart 가능 (mixed) — Chunk 1 단일 종목으로 부족 | Chunk 1 dry-run 을 1건 → 3건 (다양한 prefix `0000xx` / `00088x` / `0098xx`) 으로 샘플링. MIXED 결과 시 Chunk 2 범위 재정의 후 사용자 결정 분기 |
| **H-7** | `stock.stock_code` 컬럼 길이 / Repository INSERT 제약 | 현재 `VARCHAR(20)` (master.md § 0.4 ETF/ELW 여유). 6자리 영숫자는 그대로 fit — 변경 0 |
| **H-8** | 운영 cron elapsed 증가 (300 종목 × 2초 = 10분 추가) | OHLCV daily cron 현재 34분 → ~44분 추정. 사용자 사전 인지 + STATUS § 5 일정 영향. 부분 적용 옵션 (e.g., 100건 제한) 도 가능하나 본 chunk 는 전체 허용 권장 |
| **H-9** | Chunk 2 후 첫 cron 실행에서 KiwoomBusinessError 누적 (Chunk 1 검증 종목 외 다수가 fail) | Chunk 1 dry-run 으로 SUCCESS 확정한 종목 외 운영 실측 후 follow-up chunk 검토. Chunk 2 의 router 가 KiwoomError 5종 핸들러 보유 (R2 E-1 완료) — 500 누설 차단됨 |
| **H-10** | `STK_CD_CHART_PATTERN` 도 ka10100 lookup 에 잘못 사용되면 wire-level fail | LOOKUP 계열 라우터/어댑터/Pydantic Request 5곳 모두 LOOKUP 그대로 — code review + grep `STK_CD_CHART_PATTERN` 사용처가 chart 계열만인지 명시 검증 |

## 6. DoD

### 6.1 Chunk 1 DoD (dry-run)

- [ ] DB 조회로 영숫자 active 종목 1~3건 식별 (예: `00088K`, `0000D0`, `00098N`)
- [ ] `scripts/dry_run_chart_alphanumeric.py` 작성 (가드 우회 + 단건 ka10081 + ka10086 호출)
- [ ] 사용자 수동 실행 + stdout 로그 캡처
- [ ] `docs/operations/dry-run-chart-alphanumeric-results.md` 결과 기록
- [ ] ADR § 32 — 결정 (Chunk 2 진행 / NO-FIX / 범위 재정의)
- [ ] STATUS § 5 #1 — Chunk 1 결과 한 줄 갱신
- [ ] CHANGELOG prepend (`docs(kiwoom): chart 영숫자 stk_cd dry-run 결과 (옵션 c-A Chunk 1)`)

### 6.2 Chunk 2 DoD (Chunk 1 SUCCESS 시)

**코드** (ruff/mypy strict PASS / 외부 contract 영향: chart 계열 호출 범위 확장만):

- [ ] `stkinfo.py` — `STK_CD_CHART_PATTERN` 상수 신규 + `_STK_CD_CHART_RE` 컴파일
- [ ] `build_stk_cd` — chart adapter 가드 교체 (LOOKUP → CHART)
- [ ] 5 chart 계열 router (ohlcv 2 / ohlcv_periodic 3 / daily_flow 2) 의 Path pattern 교체 (총 7 path)
- [ ] 3 UseCase 의 `_KA*_COMPATIBLE_RE` 교체 (ohlcv_daily / ohlcv_periodic / daily_flow service)
- [ ] lookup 계열 5곳 (stocks router 2 / fundamentals router 2 / stkinfo `_validate_stk_cd_for_lookup`) **무변** 검증 (grep)

**테스트** (목표: 1037 → ~1045 / coverage 유지 ≥ 80%):

- [ ] `build_stk_cd` 영숫자 4 cases — 통과 (`00088K`), 거부 (lowercase / 특수문자 / 5자리)
- [ ] chart 계열 라우터 path 영숫자 통과 + lookup 계열 라우터 path 영숫자 거부 (422) 단언
- [ ] UseCase active_stocks filter — 영숫자 keep + skip 카운트 변화 단언
- [ ] 회귀 0 — 기존 1037 그대로 PASS (chart 계열 거부 단언이 있다면 갱신 — testcontainers 자동 발견)

**Verification**:

- [ ] mypy --strict 0 errors
- [ ] ruff check + format All passed
- [ ] pytest 전체 PASS
- [ ] coverage 유지

**리뷰**:

- [ ] 1R 리뷰 PASS (신규 도메인 — sub-agent 1회 라운드)
- [ ] Verification Loop — lookup/chart 분리 정확성 + 회귀 검사

**문서**:

- [ ] ADR § 33 추가 (Chunk 2 결과)
- [ ] CHANGELOG prepend (`feat(kiwoom): chart stk_cd 영숫자 가드 완화 — STK_CD_CHART_PATTERN 신규 (옵션 c-A Chunk 2)`)
- [ ] STATUS § 6 chunk 누적 / § 5 #1 해소 / § 0 endpoint 진행률 갱신 (영숫자 종목 적재 가능 명시)
- [ ] HANDOFF.md 전체 갱신

## 7. 다음 chunk (본 chunk 종결 후)

1. **영숫자 종목 백필** — Chunk 2 후 cron 자연 수집 또는 별도 backfill_ohlcv resume — 사용자 결정. ~295 종목 × 3년 = 추가 ~200K rows 추정
2. **운영 cron 활성 + 1주 모니터** (STATUS § 5 최종) — scheduler_enabled=true. 측정 #13 일간 cron elapsed 해소
3. **Phase D** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. **Phase E/F/G** — 공매도/대차/순위/투자자별 wave

---

_옵션 c-A. STATUS § 5 #1 / phase-c-refactor-r2-defer-cleanup.md § 6 #2 출처. 사용자 결정 — Chunk 1 dry-run 선행 (2026-05-11)._
