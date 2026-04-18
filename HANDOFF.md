# Session Handoff

> Last updated: 2026-04-19 (KST, 오전 — P13-3/P13-4 구현·실측·커밋 직후)
> Branch: `master` (origin 과 2 커밋 앞서 — 푸시 대기)
> Latest commit: `e6d79e6` — P13-4: DART 벌크 sync 에 KRX 현재 상장 교차 필터 추가

## Current Status

**DART 벌크 sync 실 DB 적재(3,654건) + AI 리포트 rate limiting + KRX 교차 필터 + 포트폴리오 UI 실측까지 한 세션에 완료.** 전 세션에서 마련한 스크립트/보안 기반 위에 **운영 데이터**가 처음으로 적재되었고, OpenAI/DART 호출 루프 공격에 대한 관리자 키 단위 쿼터 방어선이 확보됨. UI 실측은 라우팅/컴포넌트 층 PASS, 데이터 파생 지표는 KRX carry-over 파급으로 `—` 상태 유지 중 — 차후 과제로 명확히 분리.

## Completed This Session

| # | Task | Commit | Files / 결과 |
|---|------|--------|--------------|
| 1 | A: DART 벌크 sync 본실행 | (스크립트 실행만) | DB 에 3,654건 upsert. 삼성전자/SK하이닉스/NAVER 매핑 확인 |
| 2 | B: AI 리포트 slowapi rate limiting | `3e44ab6` | `_rate_limit.py`, `main.py`, `reports.py`, `settings.py`, `pyproject.toml`, `uv.lock`, `tests/test_analysis_report.py` |
| 3 | D: 포트폴리오 UI 실측 | (실측만) | 라우팅·보유 테이블·AI 리포트 페이지 렌더링 PASS. 파생 지표는 데이터 부재로 `—` |
| 4 | E: KRX 현재 상장 교차 필터 | `e6d79e6` | `scripts/sync_dart_corp_mapping.py`, `tests/test_sync_dart_corp_mapping.py` |

**누적 규모(본 세션)**: 2 커밋 / 9 파일 / +289 / -6 라인.
**테스트**: 백엔드 **135/135 PASS** (전 세션 131 + rate limit 1 + KRX 교차 4). mypy strict 0, ruff 0 (신규 파일).

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **원격 푸시** | pending | `3e44ab6`, `e6d79e6` 2 커밋 origin 앞서 있음 |
| 2 | **Z: E 실측** | pending | 컨테이너 재빌드 후 `docker compose exec backend python -m scripts.sync_dart_corp_mapping --dry-run` 로 KRX 교차 필터 결과 확인. 3,654 → ~2,500 수준 축소 예상 |
| 3 | **데이터 부재 해소(α/β/γ)** | 결정 필요 | KRX 익명 차단 carry-over 의 실제 파급. UI 파생 지표·시그널·백테스트 기능 전체 블로커 |
| 4 | **`force_refresh=true` 조건부 rate limiting** | 보류 | 현재는 엔드포인트 전체에 30/min. 조건부 분리 원하면 엔드포인트 분리 리팩터 필요 |
| 5 | **slowapi Redis 백엔드** | 보류 | 단일 uvicorn 프로세스 동안 불필요 |
| 6 | **`BrokerAdapter` Protocol 추출** | 보류 | 키움 합류 전까지 미필요 |
| 7 | **Caddy unhealthy** | 관찰 | localhost self-signed 한정 |

## Key Decisions Made

1. **AI 리포트 rate limit 은 엔드포인트 전체에 적용** — slowapi 데코레이터 기반이라 런타임 조건부(`force_refresh=true` 만)는 hack 필요. 30/min 쿼터는 정상 사용(캐시 히트 포함)에 여유, 루프 공격에는 충분. 필요 시 엔드포인트 분리 리팩터.
2. **Rate limit key 는 API Key 우선, IP fallback** — 관리자 키가 노출된 경우 공격자가 IP 우회해도 같은 키로 묶이도록. 정상 요청은 항상 키 보유하므로 IP fallback 경로는 도달 불가.
3. **Limit 값은 런타임 조회 (`_ai_report_limit()` 함수)** — 테스트가 `monkeypatch.setenv` + `get_settings.cache_clear()` 로 override 할 수 있음. import-time 평가는 테스트 불가능.
4. **KRX 교차 필터는 기본 ON, 실패 시 fallback** — 운영 연속성 우선. DART 결과만으로도 upsert 는 가능하므로 KRX 조회 실패를 블로커로 삼지 않음. stderr 경고로 운영자가 인지 가능.
5. **KONEX 는 교차 필터 대상 제외** — 유동성 낮아 AI 리포트 대상 외. 실제 수요 발생 시 `market="ALL"` 로 확장.
6. **UI 데이터 부재 문제를 Rate limit/KRX 필터와 분리** — UI 의 파생 지표(수익률·MDD)가 비어있는 것은 stock 마스터·stock_price 시계열 미집계가 원인이며, 본 세션 작업과 독립. 차후 작업(α/β/γ)으로 이관.

## Known Issues

### 본 세션 구현·검증 완료
- `3e44ab6` AI 리포트 엔드포인트 slowapi rate limiting
- `e6d79e6` DART 벌크 sync 에 KRX 현재 상장 교차 필터

### 본 세션 관찰(차후 개선)
- **UI 파생 지표 전체 블로커** — 수익률·MDD·시그널 정합도·백테스트 모두 `stock_price` 시계열 의존. KRX 익명 차단 carry-over 가 실사용 기능 전체의 실질 블로커임이 D 실측에서 명확해짐.
- **상장폐지 종목 혼재 → 축소 예상** — E 구현으로 다음 sync 실행 시 ~2,500건 수준으로 수렴 예상. 실측은 차기 과제(Z).

### Carry-over (이전 세션에서 식별, 본 세션에서 미처리)
- KRX 익명 차단 (stock 마스터 0 rows → 파생 지표 전반 `—`)
- KRX 대차잔고 pykrx 스키마 불일치 (fallback 동작 중)
- Caddy unhealthy (localhost self-signed 한정, 실도메인 모드에선 자동 해소)
- Docker Desktop bind mount 휘발성 (Caddyfile 수정 시 `docker compose restart caddy` 필수)

## Context for Next Session

### 즉시 할 일

1. **원격 푸시** — 2 커밋 (`3e44ab6`, `e6d79e6`) + 본 문서 업데이트 커밋.
2. **Z: E 실측** — backend 재빌드 후 dry-run 으로 KRX 교차 필터 결과 확인. DART 3,654 → KRX 교집합 ~2,500건 수준으로 수렴하는지. 실측 통과 시 본실행(`--dry-run` 제거)로 DB 재적재.

### 다음 우선 후보

- **α.** KRX 회원 크리덴셜 설정 (`.env.prod` KRX_ID/KRX_PW) + 배치 재실행 → stock 마스터 + 60일 주가 복구. 파생 지표 전체 복구 가능. ~30분(계정 보유 시)
- **β.** UI 검증 전용 수동 시드 (stock + stock_price CSV) — 운영용 아님, UI 회귀 테스트용. ~1시간
- **γ.** KIS REST 주가 조회 전환 — KIS 어댑터에 OHLCV 조회 추가, 배치에서 KRX 대신 사용. 근본 해결이지만 구조 변경. ~1일
- **H.** `force_refresh=true` 조건부 rate limiting (엔드포인트 분리) — 현재 30/min 전체 제한으로 충분. 우선순위 낮음.
- **I.** Frontend UI 리그레션 테스트(Playwright) — UI 렌더링은 PASS 확인했지만 자동화된 회귀 없음. ~0.5일.

### 사용자의 원래 목표 (carry-over)
주식 시그널 탐지·백테스팅 서비스 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) MVP. **본 세션에서 기능 완성도 → 운영 준비도 → 보안/방어선 → UI 검증까지 한 번에 진행**. 남은 블로커는 주가 데이터 부재 한 가지로 수렴.

### 사용자 선호·제약 (carry-over + 본 세션 재확인)
- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단** — 대안: 컨테이너 내부 env 접근
- **작업 단위 커밋 분리 선호**
- **리뷰 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호**
- **실측 마무리 선호** — 코드/테스트 PASS 에 그치지 않고 실 환경 검증까지
- **병렬 작업 가능 시 병렬** — 본 세션에서 A(백그라운드 DB 작업) + B(코드) + D(사용자 브라우저) 세 트랙 동시 진행

### 사용자에게 공유할 가치있는 발견

1. **UI 실측의 레이어 구분** — 라우팅/컴포넌트/상태 관리는 데이터 없이도 검증 가능. 파생 지표는 데이터 의존. 데이터 부재를 UI 버그로 오인하지 않는 판단 중요. 본 세션 스크린샷에서 명확히 드러남.
2. **slowapi 런타임 limit 값 조회 패턴** — 데코레이터에 callable 넘기면 매 요청마다 evaluated. 이것 덕에 테스트가 `monkeypatch.setenv` + `get_settings.cache_clear()` + `limiter.reset()` 3스텝으로 쿼터 override 가능.
3. **E 는 구현만으로는 축소 효과 미실측** — DART 3,654 → ? 건으로 실제로 몇 건 걸러지는지는 `pykrx.get_market_ticker_list` 성공 여부에 달림. KRX 익명 차단 carry-over 가 pykrx 에도 영향을 주면 fallback 동작해 교차 필터가 사실상 skip. Z 실측이 이걸 판별.

## Files Modified This Session

```
 CHANGELOG.md                                          | (본 산출물)
 HANDOFF.md                                            | (본 산출물)
 src/backend_py/pyproject.toml                         | +1 (slowapi)
 src/backend_py/uv.lock                                | +28 (lock sync)
 src/backend_py/app/main.py                            | +18 / -1
 src/backend_py/app/config/settings.py                 | +8
 src/backend_py/app/adapter/web/_rate_limit.py         | +30 (신규)
 src/backend_py/app/adapter/web/routers/reports.py     | +10 / -1
 src/backend_py/scripts/sync_dart_corp_mapping.py      | +81 / -5
 src/backend_py/tests/test_analysis_report.py          | +56
 src/backend_py/tests/test_sync_dart_corp_mapping.py   | +58 / -0
```

본 세션은 **한 트랙으로 머물지 않고 A→B→D→E 멀티 트랙** 진행. 매 단계에서 검증/커밋을 분리해 HANDOFF 전달성 극대화.
