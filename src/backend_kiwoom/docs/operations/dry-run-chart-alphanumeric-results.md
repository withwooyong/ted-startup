# 운영 dry-run 결과 — chart 영숫자 stk_cd 가드 완화 (옵션 c-A Chunk 1)

> **상태**: ✅ **측정 완료** (2026-05-11)
> **측정자**: Ted (로컬 docker-compose + 운영 키움)
> **측정일**: 2026-05-11 (KST)
> **참조**: `docs/plans/phase-c-chart-alphanumeric-guard.md` (Chunk 1/2 plan) / `scripts/dry_run_chart_alphanumeric.py` (CLI)
> **결과 캡처**: `captures/dry-run-alphanumeric-20260511.json`

---

## 0. 요약 (TL;DR)

대형그룹사 우선주 3건 (`03473K` SK우 / `02826K` 삼성물산우B / `00499K` 롯데지주우) 대상 KRX + NXT × ka10081 + ka10086 dry-run.

- **KRX**: 6/6 호출 모두 `return_code=0` + 충분한 row (`ka10081` 600 / `ka10086` 20) 정상 응답 → **영숫자 stk_cd 수용 확정**
- **NXT**: 6/6 호출 모두 `return_code=0` 이지만 데이터 없음 (`ka10081` sentinel 빈 row 1 / `ka10086` row 0) → **NXT 우선주 거래 미지원** 확정
- **결정**: Chunk 2 진행 (KRX 가드만 완화 / NXT 는 기존 skip 동작 유지)

스크립트의 `verdict` 분류가 `KiwoomMaxPagesExceededError + rows>0` 를 `FAIL_EXCEPTION` 으로 잡았으나 (`--max-pages=1` cap 효과), 이는 wire-level 성공의 증거 — 키움이 영숫자 stk_cd 를 받아 600 row 응답을 보낸 후 cont-yn=Y 로 다음 page 를 요구한 케이스.

---

## 1. 운영 환경 정보

| 항목 | 값 |
|------|-----|
| 측정 시점 | 2026-05-11 KST |
| base_url | `https://api.kiwoom.com` (운영 도메인) |
| 자격증명 | `.env.prod` 의 `KIWOOM_API_KEY` / `KIWOOM_API_SECRET` (autoload) |
| 검증 종목 | `03473K` SK우 (2015-08-17 상장) / `02826K` 삼성물산우B (2015-09-15) / `00499K` 롯데지주우 (2017-10-30) |
| base-date | 2026-05-09 (직전 영업일) |
| exchanges | KRX, NXT |
| endpoints | ka10081 (일봉) + ka10086 (일별수급) |
| max-pages | 1 (dry-run 단건 검증) |
| 총 호출 | 3 stocks × 2 exchanges × 2 endpoints = **12 호출** |

---

## 2. 결과 표 (verdict 재해석)

| stock | exchange | api_id | return_code | rows | 스크립트 verdict | **실제 의미** |
|-------|----------|--------|-------------|------|-------------------|---------------|
| 03473K | KRX | ka10081 | 0 | **600** | FAIL_EXCEPTION | ✅ **SUCCESS** (max-pages=1 cap, cont-yn=Y) |
| 03473K | KRX | ka10086 | 0 | **20** | FAIL_EXCEPTION | ✅ **SUCCESS** (max-pages=1 cap) |
| 03473K | NXT | ka10081 | 0 | 1 (빈) | SUCCESS | ⚠️ EMPTY — sentinel row (`cur_prc=''`, `dt=''`) |
| 03473K | NXT | ka10086 | 0 | 0 | EMPTY | ⚠️ EMPTY — 정상 (NXT 우선주 미지원) |
| 02826K | KRX | ka10081 | 0 | **600** | FAIL_EXCEPTION | ✅ **SUCCESS** |
| 02826K | KRX | ka10086 | 0 | **20** | FAIL_EXCEPTION | ✅ **SUCCESS** |
| 02826K | NXT | ka10081 | 0 | 1 (빈) | SUCCESS | ⚠️ EMPTY — sentinel row |
| 02826K | NXT | ka10086 | 0 | 0 | EMPTY | ⚠️ EMPTY |
| 00499K | KRX | ka10081 | 0 | **600** | FAIL_EXCEPTION | ✅ **SUCCESS** |
| 00499K | KRX | ka10086 | 0 | **20** | FAIL_EXCEPTION | ✅ **SUCCESS** |
| 00499K | NXT | ka10081 | 0 | 1 (빈) | SUCCESS | ⚠️ EMPTY — sentinel row |
| 00499K | NXT | ka10086 | 0 | 0 | EMPTY | ⚠️ EMPTY |

**KRX 6/6 = 100% wire-level SUCCESS**. **NXT 6/6 = 100% empty** (예상된 결과).

---

## 3. 핵심 발견

### 3.1 KRX 영숫자 stk_cd 수용 ✅

`KiwoomMaxPagesExceededError` 에도 불구하고 **호출 자체는 정상**:
- `return_code=0` (키움 비즈니스 layer 성공)
- `rows=600` (ka10081) — 일봉 약 2~3년치, `chart.py` 의 `DAILY_MAX_PAGES=10` 주석 ("1 페이지 ~600 거래일") 과 일치
- `rows=20` (ka10086) — 일별수급 1 페이지 ~20 거래일 (page size 동일)
- `KiwoomMaxPagesExceededError` 는 `max-pages=1` cap 효과 — `cont-yn=Y` 다음 페이지 요청을 받자 cap 도달로 raise

→ 키움 chart endpoint (ka10081/ka10086) 가 영숫자 6자리 stk_cd (`03473K`) 를 **wire-level 정상 수용** 확정.

### 3.2 NXT 우선주 미지원 확정

3종 모두 NXT 양쪽 endpoint 가 데이터 없음:
- `ka10081 NXT`: rows=1 이지만 모든 필드 빈 문자열 (`cur_prc=''`, `trde_qty=''`, `dt=''`) — sentinel marker row
- `ka10086 NXT`: rows=0 — 정상 empty 응답

이는 **우선주가 NXT 에 상장되지 않음**을 의미. 기존 `stock.nxt_enable=False` 정책이 자연스럽게 적용되어 운영 cron 에서 NXT 호출이 차단됨 → Chunk 2 의 NXT 처리 변경 0.

부수 확인: `72dbe69` 의 sentinel 가드 (`if not <list>: break` for mrkcond + chart 4곳) 가 정상 동작 — NXT 의 empty/sentinel 응답이 무한 루프로 빠지지 않음.

### 3.3 stock_name 분류 — 우선주 dominant

식별된 영숫자 active 종목 10건 (listed_date 보유) 모두 우선주 (`*우`, `*우B`):
- `00781K` 코리아써키트2우B (2013-06-17)
- `18064K` 한진칼우 (2013-09-16)
- `03473K` SK우 (2015-08-17)
- `02826K` 삼성물산우B (2015-09-15)
- `00088K` 한화3우B (2016-10-19)
- ... (모두 같은 패턴)

전형적인 KOSPI 우선주 표기 — `*K` suffix 가 우선주 식별자. ETF 신규 상장 (`0000D0` TIGER 등, listed_date NULL/최근) 와는 분리된 패턴.

### 3.4 first_row_sample 누락 정밀화

stdout `first_row_sample` 이 NXT ka10081 에서 모든 필드 빈 문자열로 관측 (`{'cur_prc': '', 'trde_qty': '', 'trde_prica': '', 'dt': '', 'open_pric': '', 'hi…`). 키움이 NXT 미상장 종목에 대해 1개의 빈 row 를 반환하는 **새로운 sentinel 패턴**. mrkcond + chart sentinel 가드 (`72dbe69`) 가 list 길이 0 만 검사하므로, 1 빈 row 는 통과한다.

→ **Chunk 2 범위 외 미해결 위험**: 우선주 NXT 호출 시 sentinel 빈 row 1개가 UseCase 까지 도달 → Repository INSERT 시 모든 NULL 컬럼으로 적재 가능. 현재는 `nxt_enable=False` 가드로 우선주 NXT 호출 자체가 차단되므로 운영 영향 0. Chunk 2 후 follow-up 로 sentinel 빈 row detection 보강 검토 (`if not <list> or all(not row.<key> for row in <list>): break` 패턴).

---

## 4. 결정 (Chunk 1 → Chunk 2)

| 항목 | 결정 |
|------|------|
| **Chunk 2 진행 여부** | ✅ **진행** — KRX 영숫자 stk_cd 수용 확정 |
| Chunk 2 범위 변경 | ❌ 없음 — plan doc `phase-c-chart-alphanumeric-guard.md` § 4 그대로. NXT 미지원은 기존 `nxt_enable=False` 가 자연 처리 |
| 신규 follow-up (Chunk 2 외) | NXT sentinel 빈 row detection (low priority — 운영 영향 0, 우선주 한정) |
| 스크립트 verdict 로직 보정 | 옵션 — 단발성 dry-run 도구이므로 미수정 가능. 보정 시 `SUCCESS_PAGINATED` (rows>0 + MaxPagesExceeded) 분류 추가 |

---

## 5. 다음 단계

1. **Chunk 1 commit** — 본 결과 doc + ADR § 32 + STATUS § 5 #1 갱신 + plan doc + dry-run 스크립트 + JSON 캡처
2. **Chunk 2 진행** — `STK_CD_CHART_PATTERN` 신규 + chart 계열 11곳 가드 교체 (plan doc § 4)
3. **Chunk 2 commit + 운영 cron 자연 수집** — scheduler_enabled 활성 시 다음 영업일 cron 부터 영숫자 종목 (~195~295) 자동 수집

---

_Chunk 1 dry-run 결과 doc. plan doc `phase-c-chart-alphanumeric-guard.md` § 3 / DoD § 6.1 산출물._
