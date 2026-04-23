# Session Handoff

> Last updated: 2026-04-23 12:40 KST (세션 최종 마감 — **Gate 3 7/7 통과 + TradingView 전환 시리즈 완결 + docker 자동 정리 스크립트 + 로컬 핸드오프 2커밋 origin push 완료**)
> Current branch: `master` (working tree **clean**, origin 과 동기화 완료)
> Latest commit: `4cf4937` — chore(scripts): docker 빌드/정리 자동화 스크립트 추가 + 세션 마감 핸드오프
> 직전 커밋: `d6d7012` — docs: 세션 마감 핸드오프 — 2026-04-23 TradingView 전환 시리즈 완결

## Current Status

하루 세션에 **8 PR 무회귀 연속 머지** (#34~#41, 중간 #36 재생성으로 실제 넘버는 #34/#35/#37/#38/#39/#40/#41). Gate 3 증빙 인프라 → 실제 측정 → 미달 수정 → TradingView 전환 3-PR 시리즈까지 **한 사이클 완결**. 백엔드 변경 無, 프론트엔드는 recharts 의존성 완전 소멸 + 차트 2곳 교체. CI 각 PR 6/6 green.

## Completed This Session (2026-04-23 연속)

| 순서 | PR | 커밋 | 제목 | 성격 |
|---|---|---|---|---|
| 1 | #34 | `62a7361` | Gate 3 Lighthouse 증빙 인프라 | docs (scripts + 템플릿) |
| 2 | #35 | `b9a8ec7` | Gate 3 1차 측정 — 7페이지 중 6통과 | docs (측정 결과) |
| 3 | #37 | `238153f` | 세션 마감 핸드오프 1차 (Gate 3 측정/수정 완결) | docs |
| 4 | #38 | `037f675` | /stocks/005930 CLS 0.36→0.12 · Perf 80→92 (원 PR #36 재생성) | fix |
| 5 | #39 | `6957e00` | TradingView PR 1/3 — /stocks/[code] 차트 전환 | feature |
| 6 | #40 | `0ff61f7` | TradingView PR 2/3 — /backtest pure SVG 자작 | feature |
| 7 | #41 | `507bd54` | TradingView PR 3/3 — recharts 제거 + Gate 3 최종 | chore |
| 8 | (master) | `d6d7012` | 세션 마감 핸드오프 — TradingView 시리즈 완결 (CHANGELOG + HANDOFF) | docs |
| 9 | (master) | `4cf4937` | docker 빌드/정리 자동화 스크립트 2종 + 핸드오프 보강 | chore |

### 누적 성과 지표

| 지표 | 시작 (세션 진입) | 최종 (현재 master) |
|---|---|---|
| Gate 3 판정 | 미측정 | **7/7 통과** |
| `/stocks/005930` Perf | 80 (미달) | **95** |
| `/stocks/005930` CLS | 0.362 (Poor) | 0.123 (Needs Improvement) |
| `/stocks/005930` LCP | 2557ms (경계) | **1902ms (Good)** |
| `/stocks/005930` TBT | 119ms | **44ms (Good)** |
| `/backtest` Perf | 97 | **99** |
| 차트 라이브러리 | recharts@^3.8.1 | **lightweight-charts@^5.1.0** + pure SVG |
| 번들 감소 (추정) | — | **~150KB gzipped** (first-load JS) |

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | ~~본 세션 마감 핸드오프 커밋~~ | ✅ **완료 + push** | `d6d7012` (handoff) + `4cf4937` (docker scripts) 2커밋 origin 반영. |
| 2 | **HIGH / fetch race condition** | 기술 부채 | `getStockDetail` 호출 시 `AbortController` 없음 → 기간 버튼 빠른 전환 시 stale response. `/stocks/[code]` 외 다른 페이지도 동일 패턴일 가능성. 독립 PR 1~2h. |
| 3 | **A11y / header card color-contrast** | 디자인 부채 | `#3d4a5c` on `#131720` 대비 **1.99 < WCAG AA 4.5**. `/stocks/005930` 에서 A11y 96→95 감점 원인. 디자인 토큰 재검토 (30m~1h). |
| 4 | **로그인 세션 기반 실데이터 재측정** | 선택 | `/portfolio`, `/settings`, `/portfolio/1/alignment` 는 현재 비로그인 셸 기준 점수. 실데이터 측정은 DevTools 수동 절차 (scores.md §B). |
| 5 | **실기기 점검 (Phase E3)** | 선택 | iPhone SE/13, Galaxy S8, iPad mini. |
| 6 | **lhci 자동화** | 별도 스프린트 | staging 환경 + 로그인 세션 시드 준비 후. |
| 7 | 이전 세션 이월: 다른 서비스 DIP 확장 (Telegram/Krx/Dart) | 백엔드, 1~2h | PR #25 KIS leading example 복제. |
| 8 | 이전 세션 이월: DB 모델 `Mapped[str]` → `Literal` 좁히기 | 백엔드, 1h | `connection_type` 등. Router exhaustive check. |
| 9 | 이전 세션 이월: R-04/R-05/R-06 소규모 이슈 | 각 30분 | MOCK 401 재분류 / `/sync` 400 테스트 / `.git-blame-ignore-revs`. |

미커밋 변경: **없음** — working tree clean, `origin/master` 와 로컬 HEAD `4cf4937` 동기화 완료.

### 복구 노트 (2026-04-23 12:30~12:40)

PC 멈춤으로 리부팅 후 두 개 세션이 동시 복구 작업을 진행:
- **세션 A (이 문서 작성 세션)**: `/handoff` 스킬로 CHANGELOG/HANDOFF 편집 후 `d6d7012` 커밋.
- **세션 B**: docker 자동화 스크립트 작성·테스트 후 HANDOFF 보강하여 `4cf4937` 커밋.
- 사용자 검토 후 `git push origin master` 로 2커밋 일괄 반영. 충돌 없음.

## Key Decisions Made

### Lighthouse 측정 방법론

1. **prod docker 스택 경유 측정 표준화**: caddy self-signed HTTPS + `--ignore-certificate-errors` chrome-flag. dev 서버(uvicorn + yarn) 대비 실제 배포 구성이 반영돼 점수 신뢰도 ↑.
2. **"JSON audit 먼저 읽고 수정 방향 결정"**: `/stocks/005930` Perf 80 미달 초기 가설(recharts dynamic import for TBT) 은 TBT 48ms("Good") 로 반증 → 실제 병목은 CLS 0.362 (footer shift). 세션 최대 교훈.

### 차트 라이브러리 전환 전략

3. **TradingView Lightweight Charts v5 (Apache-2.0) 채택**: canvas 기반 금융 시계열 차트. `/stocks/[code]` 의 라인+마커 조합에 최적. 상표 로고 자동 표시는 허용.
4. **/backtest 만 pure SVG 자작 (B3)**: lightweight-charts 는 시계열 전용이라 카테고리형 그룹 막대 지원 불가. chart.js (~230KB) 도입 대신 ~180줄 SVG 자작으로 의존성 순증 0.
5. **3-PR 분할**: 범위·리뷰 부담·롤백 단위 최소화. (1) /stocks 전환 → (2) /backtest 자작 → (3) recharts 제거 + 최종 재측정.

### PR 체인 관리

6. **`--delete-branch` base 소실 복구 패턴 재적용**: PR #36 이 base 브랜치 삭제로 자동 closed → 로컬 rebase master + `git push --force-with-lease` + 새 PR 생성 (#38). 이전 세션 Phase C 때와 동일 우회.

### React 19 + Next 16 패턴

7. **`next/dynamic({ ssr: false })` 는 Client Component 내부에서만 합법**: 대상 페이지들이 이미 `'use client'` 라 호환. `node_modules/next/dist/docs/` 확인 후 적용.
8. **Setup + update useEffect 분리 (lightweight-charts)**: Strict Mode remount 시 update effect 가 deps 보존으로 재실행돼 새 chart 에 데이터 재주입. 별도 ref 동기화 불필요.
9. **SVG 차트 접근성: sr-only `<table>` 백업**: `<title>` 요소는 VoiceOver/NVDA 호환성 불일치 → SVG 는 `aria-hidden`, 테이블로 SR 데이터 전달.

### 패키지 매니저

10. **npm 표준 준수 (yarn 사용 금지)**: CI 가 `npm ci` + `package-lock.json` 을 쓰므로 `yarn add` 는 `yarn.lock` 을 생성해 lock 분기 유발. 본 세션에서 한 번 실수 → `yarn.lock` 삭제 + `npm install` 로 복구. **규칙**: 이 저장소 프론트엔드는 **npm 만 사용**.

## Known Issues

### 이번 세션 중 발견 (기존 코드 이슈)

- **HIGH / `getStockDetail` fetch race**: `/stocks/[code]/page.tsx` 의 useEffect fetch 가 `AbortController` 미사용. 기간 버튼(1M/3M/6M/1Y) 빠른 전환 시 stale response 가능. 이번 PR 범위 외로 독립 PR 예정. 동일 패턴이 다른 페이지(`/backtest`, `/portfolio`) 에도 있을 가능성 → 전수 점검 권장.
- **A11y / 헤더 카드 color-contrast**: `#3d4a5c` on `#131720` 조합 대비 1.99 (WCAG AA 4.5 미달). `/stocks/005930` A11y 95 의 유일한 감점 원인. Phase C 에서 의도적으로 `text-[#3D4A5C]` 로 라벨 폰트 darken 한 결정이 결과적으로 대비 부족. 디자인 토큰 재검토 필요.

### 당일 이전 세션 이월 (미해소)

- **다른 서비스 DIP 확장 미완**: Telegram/Krx/Dart 는 여전히 `from app.adapter.out.external import ...` (1~2h)
- **DB 모델 `Mapped[str]` → `Literal`**: Router exhaustive check 불가 (1h)
- **R-04** MOCK 401 경로 재분류 / **R-05** `/sync` endpoint 400 직접 테스트 부재 / **R-06** `.git-blame-ignore-revs` 미생성 (각 30분)
- **R-03 이름 중복 완화**: port `KisCredentialRejectedError` vs domain `CredentialRejectedError` (30분)

### 일반 부채 (세션 이전 잔존)

- Python M2 중복 판단 N+1 (엑셀 import, PR #12 리뷰 이월)
- MEDIUM `setattr` mypy 우회 (`BacktestResult.hit_rate_{n}d`)
- 실 KIS 엑셀 샘플 부재
- carry-over 모니터링: lending_balance T+1 지연, 218 stock_name 빈, TREND_REVERSAL Infinity

## Context for Next Session

### 사용자의 원 목적 (본 세션 전체 흐름)

Gate 3 증빙 마무리 → 결과 기반 즉시 개선 → 사용자가 추가로 제안한 TradingView Lightweight Charts 전환까지 **파이프라인 하나로 통합**. 각 단계마다 `/ted-run` 스킬로 구현→리뷰→빌드→커밋/푸시 1사이클 + PR 오픈 + CI 대기 + 머지 승인 요청을 반복.

### 선택한 접근과 이유

- **"JSON 먼저 읽고 가설 검증"**: /stocks Perf 80 미달 원인이 recharts TBT 라는 초기 가설을 JSON audit 으로 즉시 반증 (TBT 48ms 이미 Good). 진범 CLS 0.362 (footer shift) 를 CSS-only 수정으로 해결. 가설만 좇았으면 시간 허비였음.
- **TradingView 로 "진짜 차트" 이관**: CLS 수정은 증상 수정이었고, 근본적으로 recharts 의 SVG + React 재조정이 모바일 저사양에 무거웠음. canvas 기반 lightweight-charts 로 LCP/TBT 가 대폭 개선 (−25%/−63%).
- **3-PR 분할로 리뷰/롤백 단위 최소화**: ted-run 파이프라인이 PR 단위로 녹아 들어가서 리뷰 부담 경감 + 문제 발생 시 특정 PR 만 revert 가능.

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** 유지 (글로벌 CLAUDE.md).
- **`git push` 는 명시 요청 시에만** — 본 세션도 매 PR 머지 승인을 명시적으로 받음.
- **npm 기반 프로젝트** — yarn 사용 금지 (본 세션에서 yarn.lock 생성 실수 → 즉시 복구).
- **Gate 승인 원칙** 유지 — 각 PR 머지 전 CI 전체 green 확인.
- **설계 승인 루프** — TradingView 전환 전 4가지 (범위/라이선스/SSR/recharts 거취) 파라미터 사용자 합의 후 착수.
- **리뷰 후 HIGH/MED 즉시 반영** — ted-run 파이프라인 Step 2 규칙 준수 (HIGH-2 fetch race 는 기존 코드라 분리).

### 다음 세션에서 먼저 확인할 것

1. **핸드오프 커밋** (`CHANGELOG.md` prepend + `HANDOFF.md` overwrite) 머지.
2. **HIGH / fetch race AbortController** — 소규모 PR 로 시작해 워밍업 가능. `/stocks/[code]`, `/backtest`, `/portfolio` 에서 동일 패턴 있는지 전수 점검 후 일괄 수정.
3. **A11y / color-contrast** — 디자인 토큰(`#3D4A5C` → 더 밝은 회색으로 조정) 검토 후 `/stocks` A11y 96 복귀.
4. **이월 과제** 중 백엔드 (DIP 확장, `Mapped[Literal]`) vs 프론트 소규모 (R-04~06) 우선순위 결정.

### 가치 있는 발견 (본 세션)

1. **Lighthouse 최적화는 JSON audit 이 먼저**: 가설은 쉽게 틀림. 측정 데이터(specifically `metrics` audit + `layout-shifts`/`bootup-time`) 가 병목을 곧바로 가리킴. 세션 내 반복된 원칙.
2. **TradingView Lightweight Charts v5 는 Apache-2.0 + canvas**: 금융 시계열에서 recharts 대비 TBT 절반 이하. API 는 `addSeries(AreaSeries, ...)` + `createSeriesMarkers` plugin 분리 (v4 deprecated).
3. **pure SVG 가 "적당한" 차트의 최적 선택일 수 있다**: backtest 처럼 입력 규모 작으면 150~200줄 SVG 자작이 외부 의존성 도입보다 싸다. 단, 접근성 책임도 떠안으므로 sr-only 테이블 백업이 필수.
4. **`--delete-branch` 체인 끊김은 반복 발생**: squash merge 기본 컨벤션 + 체인 PR 조합에서 base 소실 → 자동 close. 로컬 rebase + 새 PR 로 복구 패턴 확립. 이전 세션 Phase C 에 이어 본 세션 PR #36 에서도 재발.
5. **Next 16 `react-hooks/refs` 규칙**: 렌더 중 ref 쓰기 금지 (`refMyRef.current = value`). 해결책은 setup effect 내부에서 모든 ref 초기화 + update effect 는 React Strict Mode 재실행에 의존.
6. **yarn vs npm lock 파일 혼용 위험**: `yarn add` 가 `yarn.lock` 생성 → CI `npm ci` 실패 가능성. 이 저장소는 npm 전용이므로 `.gitignore` 에 `yarn.lock` 추가 검토 가치 있음 (이번 세션은 삭제로 대응).

## Files Modified This Session (master 기준 누적, 세션 시작점 `be6a5f8` 기준)

```
 .gitignore                                                  |   3 +
 CHANGELOG.md                                                | (prepend 이번 세션 엔트리 다수)
 HANDOFF.md                                                  | (overwrite)
 docs/lighthouse-scores.md                                   | 176 ++++++ (신규+갱신)
 docs/mobile-responsive-plan.md                              |  51 ++-
 scripts/lighthouse-mobile.sh                                | 105 ++++ (신규, 0755)
 scripts/docker-rebuild.sh                                   |  82 ++++ (신규, 0755, compose up 자동 정리 래퍼)
 scripts/docker-clean.sh                                     |  41 ++++ (신규, 0755, 주기적 수동 정리)
 src/frontend/package.json                                   |   4 +-  (−recharts, +lightweight-charts)
 src/frontend/package-lock.json                              | 419 +--  (−recharts deps, +lightweight-charts + fancy-canvas)
 src/frontend/src/app/backtest/page.tsx                      |  83 ++-
 src/frontend/src/app/stocks/[code]/page.tsx                 | 133 ++-
 src/frontend/src/components/charts/GroupedBarChart.tsx      | 276 ++++ (신규, pure SVG)
 src/frontend/src/components/charts/PriceAreaChart.tsx       | 140 ++++ (신규, lightweight-charts)
 src/frontend/src/lib/hooks/useMediaQuery.ts                 |  23 -- (삭제, 사용처 0)
 src/frontend/tests/e2e/actions.spec.ts                      |  10 +
 src/frontend/tests/e2e/holdings.spec.ts                     |  10 +-
 src/frontend/tests/e2e/mobile.spec.ts                       | 171 ++++ (신규, Phase E1)
 src/frontend/tests/e2e/pages/PortfolioPage.ts               |  17 +-
 + Phase B~D 에서 수정된 9 파일 (NavHeader, alignment, globals.css, portfolio 등)
```
