# Session Handoff

> Last updated: 2026-05-10 (KST) — ka10099 운영 검증 + 2 차단 버그 fix
> Branch: `master`
> Latest commit (커밋 대기): `fix(kiwoom): 운영 검증 도구 보강 + 실 호출에서 발견된 2 차단 버그 fix`
> 직전 푸시: `e9ab050` — DATABASE_URL → KIWOOM_DATABASE_URL rename

## Current Status

**ka10099 첫 실 호출 성공** — `register_credential.py` (alias=prod 등록) → `sync_stock_master.py` 실행 흐름 완성. **5 시장 / 4373 active stock / 630 NXT / 1.7초 elapsed**. 동시에 **2 운영 차단 버그 발견·수정**. 테스트 985 → 988. 운영 미해결 #1 (페이지네이션 빈도) 부분 검증: ka10099 는 단일 호출 (cont-yn=N).

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | 마스터키 운영 가이드 | `docs/operations/credential-master-key-guide.md` (신규) | 왜 필요 / 무엇이 아닌가 / 생성·보관·회전·분실 시 절차 |
| 2 | 2 admin 스크립트 dotenv autoload | `scripts/register_credential.py` / `sync_stock_master.py` | backend_kiwoom/.env.prod → ../../env.prod 순서로 autoload. KIWOOM_API_KEY/SECRET fallback (키움 공식 명명) |
| 3 | **next-key 빈값 fix** (운영 차단) | `app/adapter/out/kiwoom/_client.py:216, 299` | `next-key=""` 응답을 형식 오류로 reject 하던 정규식 검증 → 빈값 정상 처리. **모든 키움 API + cron 차단 해소** |
| 4 | **upsert_many chunk 분할 fix** (운영 차단) | `app/adapter/out/persistence/repositories/stock.py` | asyncpg bind parameter 32767 한도 초과 (KOSPI 2440 × 14 = 34160). 1000/batch chunk 분할 |
| 5 | 단위 테스트 +5 cases | `test_kiwoom_client.py` 2 / `test_stock_repository.py` 1 / `test_register_credential_cli.py` 2 | 빈 next-key / 2500 row chunking / API_KEY fallback / precedence |
| 6 | STATUS / HANDOFF / CHANGELOG 갱신 | 3 문서 동시 갱신 | backend_kiwoom CLAUDE.md § 1 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit 통합 |
| 2 | **backfill_ohlcv.py 실측** | not started | 다음 단계. smoke 10 → mid 100 → full 3000 |
| 3 | gap detection / daily_flow 백필 / refactor R2 / ka10094 | pending | 실측 결과 후 우선순위 결정 |
| 4 | ADR § 26.5 채움 | pending | results.md 채운 후 |

## Key Decisions Made (운영 검증)

### 발견된 운영 차단 버그 2건

| # | 버그 | 발견 시점 | mock 테스트가 못 잡은 이유 |
|---|------|----------|-------------------------|
| next-key 빈값 reject | `_client.py` 정규식 `^[...]+$` | sync_stock_master.py 첫 실 호출 | mock 응답이 항상 `next-key="page-2"` 같은 non-empty 값 사용 |
| upsert_many bind 한도 초과 | `stock.py` 의 PG insert | 같은 호출, KOSPI 적재 시점 | 단위 테스트가 2~10 row 만 사용 (실 운영 2440) |

→ **운영 실측의 가치 입증**. 모든 endpoint 가 `_client.py` 사용 → 자동 cron (daily_flow / weekly / monthly OHLCV 등) 도 모두 차단 상태였을 것

### admin 도구 사용성 보강

- **dotenv autoload** — symlink/cp 없이도 `.env.prod` 가 backend_kiwoom 또는 루트에 있으면 자동 로드
- **KIWOOM_API_KEY/SECRET fallback** — 사용자 .env.prod 명명 (키움 공식) 호환. 둘 다 있으면 KIWOOM_APPKEY 우선
- **마스터키 가이드 문서** — 향후 운영자 / 신규 입문자 학습 자료

### 단일 commit 결정

- 운영 차단 버그 fix + admin 도구 보강 + 마스터키 가이드를 **한 commit 으로 통합** (사용자 결정 1번)
- 맥락 일관: 첫 실 호출 → 버그 발견 → 즉시 fix 라는 흐름이 자연스러움

## Known Issues

- **다른 endpoint 도 동일 next-key 패턴 사용** — `_client.py` 의 두 위치 모두 fix 됨. 회귀 테스트 988 cases 통과
- **upsert_many chunk 분할은 stock.py 만 적용** — 다른 Repository (stock_price_krx 등) 도 같은 패턴이면 같은 한도 영향. 운영 실측에서 발견 시 동일 fix 적용
- **운영 미해결 #1 ka10099 페이지네이션** — 단일 호출 (4782 종목 1회). 다른 endpoint (ka10081 일봉 3년) 는 페이지네이션 발생 가능 — backfill_ohlcv 실측에서 검증
- **sync_stock_master 의 KOSPI 2440 → DB 2031** — §11.2 정책 (cross-market conflict 시 market_code 덮어씀) 적용. ETF/REIT 등이 KOSPI stock_code 와 겹쳐 재배정. 정상 동작

## Context for Next Session

### 사용자의 원래 의도

ka10099 종목 마스터 sync 진행 → 운영 데이터 적재 시작. 본 chunk 가 그 첫 실 호출 + 도구 보강.

### 선택된 접근 + 이유

- **dotenv autoload** — 사용자가 symlink 안 만들어도 동작
- **KIWOOM_API_KEY fallback** — 사용자 환경의 명명을 코드가 따라감 (사용자 강제 변경 회피)
- **2 차단 버그 즉시 fix** — admin 도구 첫 실행에서 발견됨, 동일 commit 으로 묶어 맥락 일관

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- 큰 chunk 도 통합 가능 (옵션 1 commit 통합 선택)

### 다음 세션 진입 시 결정 필요

본 chunk commit + push 후:

1. **backfill_ohlcv.py 실측 진입** (권장 1순위)
   - smoke: `--max-stocks 10 --only-market-codes 0 --years 1`
   - mid: `--max-stocks 100 --only-market-codes 0 --years 3`
   - full: `--years 3` (active 4373 KRX+NXT)
2. **다른 Repository 의 chunk 분할 일괄 점검** — stock_price_krx / stock_price_nxt / stock_price_periodic / stock_daily_flow 의 upsert_many. backfill 실측 중 발견 시 별도 chunk
3. **운영 cron 활성화** — `scheduler_enabled=True` + alias env 채움 → daily/weekly/monthly OHLCV + daily_flow 자동 실행

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/docs/operations/credential-master-key-guide.md   (신규, ~250줄)
src/backend_kiwoom/scripts/register_credential.py                   (수정 — dotenv + fallback)
src/backend_kiwoom/scripts/sync_stock_master.py                     (수정 — dotenv)
src/backend_kiwoom/app/adapter/out/kiwoom/_client.py                (수정 — fix 1)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock.py (수정 — fix 2)
src/backend_kiwoom/tests/test_kiwoom_client.py                       (수정 — +2 cases)
src/backend_kiwoom/tests/test_stock_repository.py                    (수정 — +1 case)
src/backend_kiwoom/tests/test_register_credential_cli.py             (수정 — +2 cases / 격리 보강)
src/backend_kiwoom/STATUS.md                                         (수정)
CHANGELOG.md                                                         (수정 — prepend)
HANDOFF.md                                                           (본 파일)
```

총 11 파일 / 신규 1 + 수정 10 / +500 줄
