# Session Handoff

> Last updated: 2026-04-23 16:30 KST (세션 마감 — **A11y 100 달성 + v1.1 Sprint A 완주**)
> Branch: `master` (local 1 commit ahead, **푸시 대기**)
> Latest commit: `fc1859e` — feat(chart): v1.1 Sprint A 완주 — 캔들 + MA + Volume pane + 줌/팬 + OHLCV 툴팁
> 직전 세션 mark: `4cf4937` (docker 자동 정리 스크립트)

## Current Status

3 개 독립 과제를 한 세션에 해소: **(1) v1.0 잔존 A11y 색대비 0→100, (2) docker-rebuild.sh `--env-file` 주입 버그, (3) v1.1 차트 고도화 Discovery + Sprint A 일괄 완주**. `/stocks/005930` Lighthouse 4 카테고리 전부 95+/100/100/100 — 색대비 통과 + Sprint A 대규모 차트 기능 추가에도 **완전 무회귀**. `fc1859e` 는 로컬만 있고 원격 미반영.

## Completed This Session

| # | 커밋 | 제목 | 성격 |
|---|---|---|---|
| 1 | `4e660a9` | WCAG AA muted 토큰 `#3D4A5C → #7A8699` 전역 교체 (13 파일 41건) | fix(frontend) |
| 2 | `3f73f40` | `/stocks/005930` 색 대비 잔존 2건 수정 — **A11y 100 달성** | fix(frontend) |
| 3 | `ccc7c51` | `docker-rebuild.sh` prod 모드 `--env-file` 자동 주입 | fix(scripts) |
| 4 | `fc1859e` | v1.1 Sprint A 완주 — 캔들 + MA + Volume pane + 줌/팬 + OHLCV 툴팁 | feat(chart) + docs |

### Lighthouse 추이 (`/stocks/005930`)

| 지표 | 세션 시작 | A11y 1차 수정 후 | A11y 2차 수정 후 | Sprint A 완주 후 |
|---|---:|---:|---:|---:|
| Performance | 95 | 94 | 95 | **95** |
| **Accessibility** | 95 | 95 | **100** | **100** |
| Best Practices | 100 | 100 | 100 | 100 |
| SEO | 100 | 100 | 100 | 100 |

### v1.1 차트 고도화 — 파이프라인 산출물 (신규 6 종)

- `pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md`
- `pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md` — US 12 + FR 12 + NFR 8 + Risk 5
- `pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md`
- `pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md` — 3/6/12 개월
- `pipeline/artifacts/02-prd/sprint-plan-v1.1-chart-upgrade.md` — RICE + A1~A8 all ✅
- `pipeline/decisions/discovery-v1.1-judge.md` — **PASS 9.20 / 10**

### Sprint A 태스크 완료 (A1~A8)

| # | 태스크 | 비고 |
|---|---|---|
| A1 | v5 multi-pane PoC | 30분 스파이크, `typings.d.ts:1689,1932` `addPane`/`setHeight` 확인 |
| A2 | AreaSeries → CandlestickSeries | 한국 증시 색(`#FF4D6A`/`#6395FF`), 0값 레코드 필터, 마커 `aboveBar` |
| A3 | `lib/indicators/sma.ts` | O(n) 슬라이딩 윈도우 |
| A4 | MA 5/20/60/120 오버레이 | 노랑/오렌지/녹색/보라, window 별 Map 관리 |
| A5 | Volume Histogram pane | `chart.addPane()` + `IPane.setHeight(96px)` |
| A6 | 줌/팬 활성화 | `handleScroll/handleScale: true` |
| A7 | OHLCV 툴팁 | `subscribeCrosshairMove` + React state 오버레이 (우상단, `aria-live`) |
| A8 | 회귀 검증 | Lighthouse 95/100/100/100 무회귀, Gate A 3/4 자동 통과 |

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | **`fc1859e` 푸시** | ⏳ 대기 | 전역 CLAUDE.md 규칙 — 명시 요청 시에만 push. 다음 세션 진입 시 최우선. |
| 2 | **Gate A 모바일 실기기 수동 확인** | ⏳ 대기 | iPhone SE / Galaxy S8 에서 핀치 줌 + 팬 + 캔들/MA/Volume 렌더 시각 확인 |
| 3 | **v1.1 Sprint B 착수** | 🟢 **즉시 가능** | 예산 6.3d. indicators/rsi.ts + indicators/macd.ts + IndicatorTogglePanel + useIndicatorPreferences(localStorage) + sr-only 테이블 + 모바일 breakpoint 기본 토글 차등 |
| 4 | **2026-04-20 OHLCV 전 0값 레코드** | 🟡 분석 | DB 에서 `stock_price` last row 전체 0. 차트 측에선 방어 필터 적용 완료. KRX 수집 배치 부분 실패 원인 별도 조사 필요 (공휴일? 부분 수집 실패?) |
| 5 | 이전 세션 이월: 다른 서비스 DIP 확장 (Telegram/Krx/Dart) | 백엔드 1~2h | PR #25 KIS leading example 복제 |
| 6 | 이전 세션 이월: DB 모델 `Mapped[str]` → `Literal` 좁히기 | 백엔드 1h | `connection_type` 등. Router exhaustive check. |
| 7 | 이전 세션 이월: R-04/R-05/R-06 소규모 이슈 | 각 30분 | MOCK 401 재분류 / `/sync` 400 테스트 / `.git-blame-ignore-revs` |
| 8 | 후속 A11y — 다른 페이지 `#6B7A90` / `#6395FF` 조합 전수 스캔 | 선택 | `/portfolio`, `/backtest`, `/settings` Lighthouse 재측정 필요 |

**미커밋 변경: 없음** — working tree clean. 로컬 HEAD `fc1859e` 가 `origin/master` 보다 1 커밋 앞섬.

## Key Decisions Made

### A11y 색 대비 전략
1. **스팟 수정 우선, 글로벌 토큰 후순위**: 2차 수정 시 `#6395FF` accent / `#6B7A90` secondary 는 미변경. 글로벌 변경은 다른 페이지 시각 영향이 크므로 계층 역전 수용 + 스팟 처리.
2. **계층 역전 감수**: `#131720` 배경에서 WCAG AA 통과하려면 L≥~0.21 필요 → 새 muted `#7A8699` (4.86:1) 가 기존 secondary `#6B7A90` (4.11:1) 보다 밝아짐. 이는 수학적 필연이고 문서화해 수용.
3. **인버트 버튼 색**: active 기간 버튼은 `text-white` → `text-[#0B0E11] font-semibold` 로 전환해 2.88:1 → 7.27:1. 디자인은 "눌린" 상태가 오히려 강조되는 효과.

### /plan 프로세스 축소
4. **옵션 β 채택 (biz-analyst + pm + judge; marketing/crm 생략)**: 이 iteration 이 내부 제품의 기술 고도화 성격이라 GTM/고객여정 산출물 기여도 낮음. 명시적 결정으로 과잉 프로세스 회피.
5. **γ PoC 스파이크 선행**: Sprint A1 공수(0.5d) 를 30분 스파이크로 앞당겨 2대 핵심 리스크(KRX 실데이터, v5 multi-pane API) 를 실데이터 + 실라이브러리 타입으로 해소. 가정 → 검증의 ROI 가 매우 높음.

### v1.1 차트 기술 결정
6. **lightweight-charts v5 `addPane()` 네이티브 채택**: `node_modules/lightweight-charts/dist/typings.d.ts:1689,1932` 교차 확인. `chart.addPane()` + `IPane.setHeight(px)` + `pane.addSeries(...)` 로 3-pane+ 확장 가능. Plan B (priceScaleId overlay) 대비 시각 분리 품질 우월.
7. **FE 자체 지표 계산 (외부 의존성 0)**: `technicalindicators` 등 라이브러리 (~30~50KB gzipped) 대신 `sma.ts` 자체 구현 (~0.4KB). 번들 순증 ≤ 5KB 달성. Sprint B 의 RSI/MACD 도 동일 전략.
8. **한국 증시 색 관례 일관성**: 상승 빨강 `#FF4D6A` / 하락 파랑 `#6395FF` — 헤더 카드 `changeColor`, 캔들, 거래량 히스토그램 모두 동일. 시각 언어 단일화.
9. **MA 4개 기본 visible**: 토글 UI 는 Sprint B 까지 없으므로 기본 전부 ON. 토글 UI 구현 후 모바일 breakpoint 기본값 차등 (MA5/20 + Volume만) 적용 예정.
10. **시그널 마커 `aboveBar` 이동**: 캔들 바디와 겹치는 `inBar` 대신 바 위로 배치, 색 `#FFCC00` 노랑. 기존 Area 차트 시각 언어에서 변경.

### 운영 프로세스
11. **pre-commit hook `block-no-verify@1.1.2` heredoc 오탐 → `-F` 파일 우회**: 프로젝트 메모리에 저장 (`memory/project_block_no_verify_heredoc_pitfall.md`). 재발 시 즉시 우회 가능.
12. **docker-rebuild.sh 가 `--env-file` 자동 주입하도록 수정**: prod 기본 `.env.prod`, dev 기본 `.env`, 환경변수 `ENV_FILE` override 지원. `.env.prod` 없는 prod 는 fail-loud.

## Known Issues

### 이번 세션 해결
- ~~**A11y / 헤더 카드 color-contrast**~~ ✅ 완전 해결 (A11y **100**). `4e660a9` + `3f73f40`.
- ~~**docker-rebuild.sh 누락**~~ ✅ 해결. `ccc7c51`.

### 수동 확인 대기
- **모바일 실기기 터치 UX**: Sprint A 핀치 줌/팬 + 다중 pane 터치 스크롤. Gate A 3/4 자동 통과, 1/4 수동.
- **시각 검증**: `/stocks/005930` 에서 캔들 + MA 4색 + 거래량 pane + OHLCV 툴팁 의도대로 렌더되는지 사용자 브라우저 확인 필요.

### 미해결 (다음 세션 이후)
- **2026-04-20 stock_price OHLCV 전체 0값**: KRX 수집 배치 부분 실패 가능성. 차트 측 방어는 완료, 원인 추적 별도.
- **RISK-C03** FE 지표 계산 성능 (500 포인트 × 지표 5개): Sprint B RSI/MACD 투입 후 자연 모니터링.

### 일반 부채 (이전 세션 이월)
- 다른 서비스 DIP 확장 (Telegram/Krx/Dart)
- DB 모델 `Mapped[str]` → `Literal` 좁히기
- R-03 이름 중복 / R-04~06 소규모 이슈
- Python M2 중복 판단 N+1 (PR #12 이월), carry-over 모니터링 (lending_balance T+1, 218 stock_name 빈, TREND_REVERSAL Infinity)

## Context for Next Session

### 사용자의 원 목적

세션 진입 시 숙제: "A11y / header card color-contrast (#3d4a5c on #131720 대비 1.99)" → 직접적 목표는 `/stocks/005930` A11y 96 복귀. 수행 과정에서 Lighthouse 재측정으로 잔존 이슈 2건을 드러내 A11y **100** 까지 올림 (목표 초과). 중간에 docker-rebuild.sh 버그가 실전 블로커로 노출돼 즉시 수정. 이후 사용자가 `/plan <트레이딩뷰 차트 고도화>` 를 트리거해 v1.1 iteration Discovery + Sprint A 를 한 세션에 완주.

### 선택한 접근과 이유

- **측정 기반 반복 (Lighthouse 수시 재측정)**: 색상 변경이 A11y 감사의 통합 이슈를 점진적으로 드러내는 특성상, 재측정 → 다음 수정 → 재측정 루프가 효과적.
- **`/plan` 프로세스 축소 (β + γ)**: 모든 에이전트를 기계적으로 돌리지 않고 이번 성격에 맞는 부분만. γ 로 PoC 선행해서 공수 추정/리스크 가정을 실데이터 기반으로 전환.
- **스프린트 통합 커밋 선택**: 사용자가 "Sprint A 완주 후 일괄 커밋" 을 선택 — 커밋 단위 = 완결 기능 단위. 리뷰 부담 대신 맥락 완결 우선.
- **팀 공유 전제 파이프라인 유지**: `pipeline/artifacts/*-v1.1-chart-upgrade.md` 6 종 신규 생성, v1.0 산출물 보존. Iteration 분리 관례 확립.

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 는 명시 요청 시에만** — 이번 세션 3 커밋 푸시, `fc1859e` 1 커밋 미푸시 상태로 마감
- **npm 기반** — yarn 사용 금지
- **Gate 승인 루프** — 매 의사결정 지점에서 옵션 제시 후 사용자 선택
- **리뷰 후 CRITICAL/HIGH 즉시 반영** — MEDIUM 은 기록 후 진행
- **pre-commit hook `--no-verify` 금지** — 훅 오탐 시 `-F` 파일 우회
- **코드 주석 최소 (CLAUDE.md)** — 이번 세션 코드도 자명한 부분은 주석 없이, Why 가 중요한 부분만 간결히

### 다음 세션에서 먼저 확인할 것

1. **`fc1859e` 푸시** — 사용자 확인 즉시 `git push origin master`
2. **브라우저 시각 확인** — `/stocks/005930` 캔들 + MA + Volume + OHLCV 툴팁 렌더 정상 여부
3. **모바일 실기기 핀치 줌/팬** — Gate A 최종 통과
4. **Sprint B 착수 여부 결정** — indicators/rsi.ts + indicators/macd.ts + IndicatorTogglePanel + useIndicatorPreferences + sr-only 테이블 (예산 6.3d)
5. **2026-04-20 OHLCV 0값 원인 분석** (옵션) — KRX 수집 배치 로그 확인
6. **이월 과제 우선순위 결정** — 백엔드 DIP 확장 vs FE 소규모 (R-04~06)

### 가치 있는 발견 (본 세션)

1. **Lighthouse color-contrast 감사는 통합 pass/fail**: 한 노드 수정하면 가려졌던 다른 노드가 드러남. 1차 수정 + 재측정 + 2차 수정 루프가 필요.
2. **`#131720` dark surface 의 수학적 제약**: 어떤 fg 도 AA 통과하려면 L≥~0.21 (밝은 회색) 필요. "dim 하면서 legible" 은 동시 만족 불가. 계층은 크기/두께/위치로 표현해야.
3. **PoC 스파이크 ROI**: 30 분 타이핑으로 2 리스크 해소, Sprint 공수 추정 신뢰도 상승. 추후 모든 다중 의존성 Sprint 에 선행 권장.
4. **`typings.d.ts` 직접 확인 > 훈련 데이터**: Context7 MCP 미등록 환경에서 에이전트 답변은 훈련 데이터 기반. `node_modules/*/dist/typings.d.ts` 를 grep 하는 게 빠르고 정확.
5. **v5 `addPane()` + `IPane.setHeight()` API 는 JSDoc 예시까지 있음**: `typings.d.ts:2002-2004` 에 3-pane 예시. API 탐색 시 코드 주변 JSDoc 스캔이 문서보다 빠를 때 있음.
6. **pre-commit hook heredoc 오탐**: `block-no-verify@1.1.2` 가 `git commit -m "$(cat <<EOF ... EOF)"` 를 `--no-verify` 로 잘못 매칭. `-F` 파일 방식이 즉시 우회책 — 프로젝트 메모리 저장됨.
7. **옵션 β + γ 조합으로 `/plan` 유연화**: 스킬 지시문을 기계적으로 따르지 않고 작업 성격에 맞게 축소/선행하는 것이 시간/품질 모두 이득.

## Files Modified This Session

```
 CHANGELOG.md                                               |  ~80 ++ (4 엔트리 prepend)
 HANDOFF.md                                                 | overwrite (본 문서)
 docs/lighthouse-scores.md                                  |  ~30 ++ (2 회차 prepend)
 pipeline/state/current-state.json                          |  ~50 ++ (iterations.v1.1 블록)
 pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md      | 신규
 pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md | 신규
 pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md                 | 신규
 pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md             | 신규
 pipeline/artifacts/02-prd/sprint-plan-v1.1-chart-upgrade.md         | 신규
 pipeline/decisions/discovery-v1.1-judge.md                          | 신규
 scripts/docker-rebuild.sh                                           |  ~30 ++ (env-file 주입 로직)
 src/frontend/src/app/globals.css                                    |    2 +- (muted 토큰)
 src/frontend/src/app/layout.tsx                                     |    2 +- (muted)
 src/frontend/src/app/page.tsx                                       |    6 +- (muted)
 src/frontend/src/app/stocks/[code]/page.tsx                         |  ~50 ++ (chartData/volume/MA, 색대비 2건)
 src/frontend/src/app/backtest/page.tsx                              |   16 +- (muted)
 src/frontend/src/app/portfolio/page.tsx                             |   16 +- (muted)
 src/frontend/src/app/portfolio/[accountId]/alignment/page.tsx       |    6 +- (muted)
 src/frontend/src/app/reports/[stockCode]/page.tsx                   |    6 +- (muted)
 src/frontend/src/app/settings/page.tsx                              |    2 +- (muted)
 src/frontend/src/components/NavHeader.tsx                           |    2 +- (muted)
 src/frontend/src/components/features/SignalCard.tsx                 |    2 +- (muted)
 src/frontend/src/components/features/ExcelImportPanel.tsx           |    2 +- (muted)
 src/frontend/src/components/features/RealAccountSection.tsx         |   10 +- (muted + placeholder)
 src/frontend/src/components/charts/PriceAreaChart.tsx               | 거의 재작성 (Candle + MA + Volume + 줌팬 + 툴팁)
 src/frontend/src/lib/indicators/sma.ts                              | 신규 (O(n) SMA)
 src/frontend/src/lib/indicators/index.ts                            | 신규 (barrel)
```

**4 commits total, 14 files + 6 신규 파이프라인 산출물 + 2 신규 indicator 파일.**
