# Session Handoff

> Last updated: 2026-04-20 (KST)
> Branch: `master` (clean, origin 동기화 완료)
> Latest commit: `46f08bb` — Merge pull request #3 from withwooyong/chore/code-review-low-fixes

## Current Status

포트폴리오 E2E 스위트(30 케이스)가 CI 에서 3회 연속 녹색 상태. 3-PR 세션으로 E2E 도입 → 대차잔고·종목명 데이터 버그 체인 수정 → 코드 리뷰 MEDIUM 5 + LOW 4 정리까지 완료. 로컬·원격 master 동기화 완료, uncommitted 변경 없음. carry-over 없음.

## Completed This Session

| # | Task | PR | 주요 커밋 |
|---|------|-----|-----------|
| 1 | 포트폴리오 E2E 도입 (Phase 1 16 + Phase 2 4 케이스) | #1 | `99445b3` `eff2d65` |
| 2 | 대차잔고 pykrx 컬럼 오매핑 + change_rate 계산 로직 추가 | #1 | `9ed7d86` |
| 3 | `/signals/latest` 엔드포인트 + 대시보드 실제 날짜 표시 | #1 | `9523ee1` |
| 4 | 시그널 탐지 백필 스크립트 + 3년(752일) 탐지 실행 70,609건 적재 | #1 | `8712b3f` |
| 5 | stock_name 수집 누락 수정 + 2,880 건 복구 | #1 | `b5b5119` |
| 6 | `_compute_lending_deltas` 유닛 테스트 10건 | #1 | `177f014` |
| 7 | E2E D3/D4 실데이터 전제 반영 | #1 | `795f3b3` |
| 8 | CI seed 보강 (`seed_e2e_accounts.py`) | #1 | `977ce43` |
| 9 | E2E F/G/H 확장 (주식상세 4 + 리포트 2 + 백테스트 2) + C2 KIS stub | #1 | `eff2d65` |
| 10 | KIS 어댑터 in-memory mock 모드 | #1 | `59b2320` |
| 11 | E2E H3/H4 (backtest 데이터/에러 stub 케이스) | #1 | `c32def7` |
| 12 | CI `ci.yml` Java → Python 이전 반영 | #1 | `e7a39ae` `e69cfa3` |
| 13 | lending deltas 헬퍼 모듈 레벨 승격 + `LendingBalance` 타입 (M4+M5) | #2 | `235ab06` |
| 14 | `_IN_MEMORY_TOKEN` 문서화 주석 (M1) | #2 | `7e48e01` |
| 15 | `build_stock_name_map` public 승격 (M2) | #2 | `f651a8d` |
| 16 | `/signals` pagination `limit` 도입 (M3) | #2 | `b46371b` |
| 17 | 코드 리뷰 LOW 4건 정리 (L1~L4) | #3 | `ce1044c` |

**PR 3건 모두 머지** + `delete-branch` — CI 4/4 PASS × 3회 반복.

## In Progress / Pending

없음. 세션 깔끔히 종료.

## Key Decisions Made

- **3년 재수집 전 5일 dry-run**: pykrx 세션 만료/재로그인 동작이 불확실 → 5일 먼저 검증 후 전체 752일(125분 37초). 리스크 최소화.
- **KIS sync "mock" 네이밍이 외부 API 의존**: `connection_type="kis_rest_mock"` 이지만 실제 KIS sandbox 호출. 첫 대응은 E2E stub route(`page.route`), 이후 M2 PR 에서 `Settings.kis_use_in_memory_mock` 플래그로 `httpx.MockTransport` 자동 주입 → E2E·CI 양쪽 외부 의존 0.
- **218건 미매칭 `stock_name` 현상유지**: `is_active` 마이그레이션 ROI 낮음(UI 가 이미 null 대응). `docs/data-state.md` 에 결정 근거 기록.
- **코드 리뷰 MEDIUM/LOW 분리 PR**: 기능 변경 없는 리팩터와 hygiene 수정은 별도 PR 로 검토 이력 보존.
- **`list_by_date(signal_date, *, limit=None)` default None**: `SignalDetectionService` 가 중복 검사용으로 전량 조회 필요 → 내부 호출은 `limit=None`, 라우터만 명시 limit 주입.
- **13 커밋 PR 머지 전략 `--merge`**: squash 대신 개별 커밋 보존. 한글 커밋 메시지가 archeology 자산.

## Known Issues

- **2026-04-16·17 `lending_balance` 응답 0건**: KRX T+1 제공 지연 — 당일 대차잔고는 다음 영업일에야 집계. 해당 날짜 RAPID/SQUEEZE 시그널은 건너뛰고 TREND(과거 MA 기반)만 산출. `docs/data-state.md` 기록.
- **218건 stock_name 빈 종목**: 상폐/구코드 추정. `docs/data-state.md` 에 현상유지 결정. 추후 과거 KRX 데이터 확보 시 `fix_stock_names.py --date 2023-06-01` 재실행으로 부분 복구 가능.
- **`backtest_result` 0건**: 배치/사용자 트리거 의존. E2E H 시리즈는 stub route 로 우회. 실제 데이터 생성 경로는 별도 세션에서 다룰 것.

## Context for Next Session

### 사용자의 원래 목표 (달성)

전 세션 carry-over였던 **3년 백필 후 대시보드 검증**에서 시작 → 대시보드 빈 화면 원인 추적 → 대차잔고·종목명 데이터 체인 버그 발견·복구 → E2E 도입으로 회귀 방어선 구축 → CI 첫 실행 녹색화 → 코드 리뷰 정리까지. **"작업 완결 + 실측 + 방어선 + 정리" 4단계 모두 완료**.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — 본 세션 21건 전부 준수
- **push 는 명시 요청 시에만** — PR 만들 때마다 사용자 확인 후 실행
- **병렬 작업 선호** — A/B/C/D 그룹 동시 진행, 4개 파일 한 번에 편집
- **체크리스트 + 한 줄 현황** — `feedback_progress_visibility.md` memory 적용 유지
- **실측 마감 선호** — 단순 PASS 가 아닌 로컬 3회 연속 + CI 실행까지 확인
- **PR 패턴**: feature 브랜치 → push → `gh pr create` → CI 4/4 PASS 대기 → `gh pr merge --merge --delete-branch` → 로컬 master 동기화

### 차기 세션 후보 (우선순위 순)

1. **`backtest_result` 생성 경로 구현** — 현재 0건으로 H 시리즈는 stub 의존. 배치/트리거 설계 + DB 시드 + E2E "실데이터" 케이스 추가.
2. **signal 탐지 로직 개선** — 3년 백필에서 TREND_REVERSAL 6,242건 · SHORT_SQUEEZE 43,311건인데 경계값 조정으로 신호 품질 재검토.
3. **알림(Telegram) 플로우 E2E·통합 테스트** — BEARWATCH 채널 연동 검증.
4. **다른 UI 플로우 E2E 확장** — settings 페이지, stocks 심화 (기간별 차트 상호작용).
5. **KIS sync 개선** — 현재 `kis_rest_mock` 만 지원. 실계정·실잔고 동기화는 아직 미구현.

### 가치있는 발견

1. **CI 워크플로가 silent 하게 깨져 있었음**: `ci.yml` 이 Phase 9 에서 삭제된 `src/backend/`(Gradle)를 참조 중. PR #1 첫 실행으로 발견. CI 를 실제로 돌리지 않으면 설정 drift 가 누적된다.
2. **"mock" 네이밍은 검증 대상**: KIS `kis_rest_mock` connection_type 이 실 sandbox 호출이라는 점. E2E 에서 `page.route` stub 으로 우회했고, 이후 `Settings` 플래그로 진짜 로컬 mock 구현까지 진행.
3. **`_IN_MEMORY_TOKEN` 같은 테스트 상수**: grep 기반 보안 스캐너 false-positive 위험. 주석 한 줄로 계약 명시.
4. **`getByRole('alert')` Next.js 충돌**: `__next-route-announcer__` 와 strict violation. 본 세션에서 E2/F4/C2 세 번 반복 발생. **패턴 인지 후 텍스트 기반 매칭 또는 버튼 기반 assertion 으로 전환**.
5. **13개 커밋 PR 머지 전략**: squash 대신 `--merge` 로 개별 커밋 보존. 한글 커밋 메시지가 archeology 자산이라는 판단.

## Files Modified This Session

```
21 commits (99445b3 → 46f08bb, 3 merge commits 포함)

 .github/workflows/ci.yml                               |  +27 / -27
 .github/workflows/e2e.yml                              | +135 (신규)
 CHANGELOG.md                                           |  (본 산출물)
 HANDOFF.md                                             |  (본 산출물)
 README.md                                              |  +77 (신규)
 docker-compose.prod.yml                                |   +1
 docs/data-state.md                                     |  +52 (신규)
 docs/e2e-portfolio-test-plan.md                        | +147 (신규, 본 세션 상태 갱신)
 src/backend_py/app/adapter/out/external/kis_client.py  | +100 / -1
 src/backend_py/app/adapter/out/external/krx_client.py  |  +43 / -5
 src/backend_py/app/adapter/out/persistence/repositories/signal.py | +20 / -2
 src/backend_py/app/adapter/web/_schemas.py             |  +11
 src/backend_py/app/adapter/web/routers/signals.py      |  +44 / -2
 src/backend_py/app/application/service/market_data_service.py | +60 / -7
 src/backend_py/app/config/settings.py                  |   +8
 src/backend_py/scripts/backfill_signal_detection.py    | +134 (신규)
 src/backend_py/scripts/fix_stock_names.py              |  +86 (신규)
 src/backend_py/scripts/seed_e2e_accounts.py            | +125 (신규)
 src/backend_py/tests/test_kis_client.py                |  +49
 src/backend_py/tests/test_market_data_lending_deltas.py|  +83 (신규)
 src/frontend/.gitignore                                |   +5
 src/frontend/package.json / lock                       |  @playwright/test 추가
 src/frontend/playwright.config.ts                      |  +27 (신규)
 src/frontend/src/app/page.tsx                          |  +8 / -4
 src/frontend/src/lib/api/client.ts                     |  +10 / -1
 src/frontend/src/types/signal.ts                       |   +5
 src/frontend/tests/e2e/*.spec.ts                       | +350 (6 spec + 3 POM, 신규)
```

본 세션은 **E2E 기반 구축 + 데이터 체인 버그 복구 + CI 녹색화 + 코드 리뷰 정리** 를 3-PR 에 나누어 완결. 차기 세션은 신규 기능(backtest 데이터, 알림 E2E 등)으로 자연 전환.
