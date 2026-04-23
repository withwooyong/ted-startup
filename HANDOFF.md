# Session Handoff

> Last updated: 2026-04-23 18:15 KST (세션 최종 마감 — **v1.1 Sprint A + Sprint B 완주, A11y 100, hotfix 1 건 반영**)
> Branch: `master` (working tree **clean**, origin 과 동기화 완료)
> Latest commit: `669d9e8` — fix(chart): `useIndicatorPreferences` 무한 루프 해소 — snapshot 캐싱
> 세션 시작점: `4cf4937` 이후

## Current Status

하루 세션에 **3 대 영역을 한 싸이클로 완결**:
1. **A11y 회복**: `/stocks/005930` color-contrast 잔존 이슈 해결로 **A11y 95 → 100** 달성 (2 커밋)
2. **v1.1 Discovery + Sprint A**: `/plan` 스킬 옵션 β (biz+pm+judge) + γ (PoC 스파이크) 로 파이프라인 산출물 6 종 생성 후 Sprint A 8 태스크 (A1~A8) 완주 (2 커밋)
3. **v1.1 Sprint B**: 봉 주기(1D/1W/1M) + 시그널 마커 grade 색 + RSI + MACD + 지표 토글 UI + localStorage + sr-only 테이블까지 4 체크포인트로 완주 + React #185 런타임 버그픽스 (5 커밋)

총 **10 커밋 origin 반영**. Working tree clean.

## Completed This Session

| # | 커밋 | 제목 | 성격 |
|---|---|---|---|
| 1 | `4e660a9` | WCAG AA muted 토큰 `#3D4A5C → #7A8699` 전역 교체 (13 파일 41건) | fix(frontend) |
| 2 | `3f73f40` | `/stocks/005930` 색 대비 잔존 2건 수정 — A11y 100 달성 | fix(frontend) |
| 3 | `ccc7c51` | `docker-rebuild.sh` prod 모드 `--env-file` 자동 주입 | fix(scripts) |
| 4 | `fc1859e` | v1.1 Sprint A 완주 — 캔들 + MA + Volume + 줌/팬 + OHLCV 툴팁 | feat(chart) |
| 5 | `2b01258` | 세션 마감 핸드오프 (A11y + Sprint A 완주 반영) | docs |
| 6 | `473a9ad` | v1.1 Sprint B 체크포인트 1 — 봉 주기(1D/1W/1M) + 시그널 grade 색 구분 | feat(chart) |
| 7 | `a5beca7` | v1.1 Sprint B 체크포인트 2 — RSI(14) + MACD(12,26,9) 유틸 | feat(indicators) |
| 8 | `9c8f37d` | v1.1 Sprint B 체크포인트 3 — 토글 UI + RSI/MACD pane + localStorage | feat(chart) |
| 9 | `a68b8f6` | v1.1 Sprint B 체크포인트 4 — sr-only 테이블 + aria 정리 + Sprint B 완주 | feat(chart) |
| 10 | `669d9e8` | `useIndicatorPreferences` 무한 루프 해소 — snapshot 캐싱 | fix(chart) |

### v1.1 Sprint A 태스크 (A1~A8) — 전부 ✅
- A1 v5 multi-pane PoC → `typings.d.ts:1689,1932` 확인 흡수
- A2 AreaSeries → CandlestickSeries (한국 증시 색, OHLC 0값 필터, 마커 `aboveBar`)
- A3 `lib/indicators/sma.ts` O(n) 슬라이딩 윈도우
- A4 MA(5/20/60/120) overlay — 4 색 팔레트, window 별 Map 관리
- A5 Volume HistogramSeries pane — `chart.addPane()` + `setHeight(96px)`
- A6 `handleScroll/handleScale: true`
- A7 `subscribeCrosshairMove` + React state OHLCV 툴팁 overlay
- A8 Lighthouse 회귀 95/100/100/100 무회귀

### v1.1 Sprint B 태스크 — 전부 ✅
- **B0** (신규 추가) 기간 버튼 재정의 1D/1W/1M + OHLC 주봉/월봉 재집계 (`aggregate.ts`)
- **B1 + B2** RSI(14) Wilder + MACD(12,26,9) EMA/Signal/Histogram 유틸
- **B3 + B4** RSI pane + MACD pane (pane 동적 생성/제거, `chart.removePane(paneIndex())`)
- **B5** `IndicatorTogglePanel` 7 토글 (MA4 + 거래량 + RSI + MACD)
- **B6** `useIndicatorPreferences` (useSyncExternalStore + localStorage + 인메모리 subscribers)
- **B7** `StockChartAccessibilityTable` (sr-only 최근 30일 OHLCV + 지표)
- **B8** 모바일 breakpoint 기본값 — `DEFAULT_PREFS` 자체가 "MA5/MA20/Volume ON" 이라 별도 로직 불요
- **B9 + B10** 회귀 + QA + 런타임 hotfix (`669d9e8`)
- 사용자 요청: 시그널 마커 grade 색 구분 (A 노랑 / B 녹색 / C 오렌지 / D 회색)

### Lighthouse 추이 (`/stocks/005930`)
| 지표 | 세션 시작 | A11y 1차 | A11y 2차 | Sprint A 완주 | Sprint B 완주 |
|---|---:|---:|---:|---:|---:|
| Performance | 95 | 94 | 95 | 95 | **80** ↓ (aurora CLS Known Issue) |
| **Accessibility** | 95 | 95 | **100** | 100 | **100** |
| Best Practices | 100 | 100 | 100 | 100 | 100 |
| SEO | 100 | 100 | 100 | 100 | 100 |

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | ~~세션 작업 커밋 + 푸시~~ | ✅ **완료** | 10 커밋 `4e660a9..669d9e8` 전부 origin 반영 |
| 2 | **브라우저 시각 검증** | ⏳ 사용자 대기 | `/stocks/012450` 캔들 + MA + Volume + OHLCV 툴팁 + 토글 7종 + grade 색 + 봉 주기 3 가지 동작 확인 |
| 3 | **모바일 실기기 Gate A 확인** | ⏳ 사용자 대기 | iPhone SE / Galaxy S8 핀치 줌/팬 UX |
| 4 | **Aurora CLS 개선** | 🟡 분리 | `div.aurora > div.blob-4` transform 애니메이션이 Lighthouse 에서 CLS culprit. 완화 시도 3회 효과 미미. 실기기 체감 확인 후 애니메이션 정적화 or keyframe 범위 축소 별도 디자인 PR |
| 5 | **v1.2 착수 결정** | 🟢 가능 | Bollinger Bands / 지표 파라미터 편집 UI / DB 기반 영속화 / Vitest FE 테스트 하네스. roadmap 상 5월. |
| 6 | **2026-04-20 OHLCV 전 0값 레코드** | 🟡 분석 | KRX 수집 배치 부분 실패 원인 추적 |
| 7 | 이전 세션 이월 — 다른 서비스 DIP 확장 (Telegram/Krx/Dart) | 백엔드 1~2h | |
| 8 | 이전 세션 이월 — DB 모델 `Mapped[str]` → `Literal` | 백엔드 1h | |
| 9 | 이전 세션 이월 — R-04/R-05/R-06 소규모 이슈 | 각 30분 | |
| 10 | 후속 A11y — 다른 페이지 `#6B7A90` / `#6395FF` 조합 전수 스캔 | 선택 | |

**미커밋 변경**: **없음** (HANDOFF.md 본 문서 수정은 이 커밋에서 반영)

## Key Decisions Made

### A11y 색 대비
1. **스팟 수정 우선, 글로벌 토큰 후순위**: accent `#6395FF` / secondary `#6B7A90` 미변경, 계층 역전 수용 + 스팟 처리.
2. **인버트 active 버튼**: 기간 버튼 active 상태 `text-white` → `text-[#0B0E11] font-semibold` 로 2.88:1 → 7.27:1.

### `/plan` 프로세스 축소 + PoC 선행
3. **옵션 β** (biz+pm+judge, marketing/crm 생략) — 내부 제품 기술 고도화 성격.
4. **옵션 γ** (A1 PoC 스파이크 선행) — 30분 안에 KRX 실데이터 + v5 multi-pane API 두 리스크 해소.

### v1.1 차트 기술
5. **lightweight-charts v5 `addPane()` 네이티브 채택**: `typings.d.ts:1689,1932`, JSDoc 3-pane 예시 (`:2002-2004`) 검증.
6. **pane 동적 생성/제거 `chart.removePane(paneIndex())`**: 토글 OFF 시 pane 완전 제거로 공간 낭비 없음.
7. **FE 자체 지표 계산**: SMA/RSI/MACD/aggregate 자체 구현 (~0.4~1KB 각), 외부 라이브러리 없음. 번들 순증 ≤ 5KB.
8. **한국 증시 색 관례 일관성**: 상승 `#FF4D6A` / 하락 `#6395FF` 로 candle + volume histogram 통일.
9. **시그널 마커 grade 색 구분** (사용자 요청): A 노랑 / B 녹색 / C 오렌지 / D 회색 — `enums.py SignalGrade.from_score` 기준 동기.

### 기간 버튼 의미 재정의
10. **봉 주기 해석 (A)**: 1D 일봉 / 1W 주봉(5일 집계) / 1M 월봉(20일 집계). 표시 기간 방식(B)는 1D 캔들 1개라 의미 낮음 → 배제. 분봉 방식(C)는 데이터 없음 → 별도 Epic.
11. **fetch monthsFetch**: 1D 3 / 1W 12 / 1M 36 — 집계 후 대략 62 / 52 / 36 캔들.

### 상태 저장
12. **useSyncExternalStore 채택**: Next 16 `react-hooks/set-state-in-effect` 규칙 회피 + SSR-safe. snapshot 캐싱 필수 (미적용 시 React #185 무한 루프).
13. **zod 미설치 환경**: 수동 타입 가드 (`isValidPrefs`) — 필드 7 개라 수동으로 충분.

### 인프라
14. **docker-rebuild.sh `--env-file` 자동 주입**: prod 기본 `.env.prod`, dev 기본 `.env`, `ENV_FILE` override. `.env.prod` 없는 prod 는 fail-loud.

### 운영 프로세스
15. **pre-commit hook `block-no-verify@1.1.2` heredoc 오탐 → `-F` 파일 우회**: 프로젝트 메모리에 저장됨 (`memory/project_block_no_verify_heredoc_pitfall.md`).
16. **`/handoff` 스킬**: CHANGELOG prepend, HANDOFF overwrite, docs 현행화 3 축 실행.

## Known Issues

### 이번 세션 해결
- ~~A11y `/stocks/005930` 색 대비~~ → **100 달성** (`4e660a9` + `3f73f40`)
- ~~docker-rebuild.sh env-file 미주입~~ → `ccc7c51`
- ~~useIndicatorPreferences 무한 루프 (React #185)~~ → `669d9e8`

### Known Issue (후속 추적)
- **Perf 95 → 80 회귀** (`/stocks/005930`): aurora blob-4 transform 애니메이션이 Chrome Lighthouse 에서 CLS 0.393 으로 계상. 완화 시도 3 회 미미. A11y/BP/SEO 무회귀라 기능 품질은 정상. 실기기 체감 확인 후 디자인 PR 분리 결정.
- **2026-04-20 stock_price OHLCV 전 0값**: KRX 수집 배치 부분 실패 가능성. 차트 측 방어 완료. 원인 추적 별도.

### 미해결 (다음 세션 이후)
- HIGH fetch race — `/portfolio`, `/backtest` 에서 동일 패턴 전수 점검 (`/stocks/[code]` 는 `277bb46` 이전 세션에서 해결됨)
- 다른 서비스 DIP 확장 (Telegram/Krx/Dart)
- DB 모델 `Mapped[str]` → `Literal`
- R-03 이름 중복 / R-04~06 소규모 이슈
- Python M2 중복 판단 N+1
- FE 테스트 하네스 (Vitest + RTL + MSW) 미도입 → v1.2 스프린트

## Context for Next Session

### 사용자의 원 목적 (본 세션 전체 흐름)

세션 진입 시 숙제는 "A11y color-contrast 1.99 → AA 기준 4.5 이상" 단일 건이었음. 수행 과정에서:
1. **Lighthouse 재측정 루프**로 잔존 이슈 2건을 추가 발견 → A11y 100 까지 끌어올림 (목표 96 초과).
2. 중간에 `docker-rebuild.sh` 가 `--env-file .env.prod` 를 주입하지 않는 버그가 실전 블로커로 노출 → 즉시 수정.
3. 사용자가 `/plan <트레이딩뷰 차트 고도화>` 를 트리거해 **v1.1 iteration** 전체 (Discovery + Sprint A + Sprint B) 를 한 세션에 완주.
4. 사용자 추가 요청 (동그라미/알파벳 의미 설명 + 기간 버튼을 1D/1W/1M 로 + 시그널 마커 grade 색 구분) 전부 반영.
5. 체크포인트 단위 커밋 (4 체크포인트 + hotfix) + 매 체크포인트 Lighthouse 재측정 + code-review 최종 통과.

### 선택한 접근과 이유

- **Discovery 프로세스 축소 (β + γ)**: marketing/crm 산출물은 내부 제품 기술 고도화에 기여도 낮음. PoC 스파이크로 리스크 가정을 실데이터 기반으로 전환.
- **체크포인트 단위 커밋**: Sprint B 6.3d 분량을 4 체크포인트로 쪼개 매 커밋마다 시각 검증 + 롤백 가능 단위 유지.
- **FE 자체 지표 계산**: 외부 라이브러리(technicalindicators 등 ~30~50KB) 대신 자체 구현 (~5KB). NFR-C03 번들 순증 ≤ 20KB gzipped 충족.
- **pane 동적 생성/제거**: `chart.removePane()` v5 API 활용. 토글 OFF 시 공간 낭비 없음.

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 는 명시 요청 시에만** — 이번 세션 매 체크포인트마다 커밋만 만들고 푸시는 세션 마감 시 한 번에
- **npm 기반** — yarn 사용 금지
- **Gate 승인 루프** — 매 의사결정 지점에서 옵션 제시 후 사용자 선택 (α/β/γ 패턴 재사용)
- **리뷰 후 CRITICAL/HIGH 즉시 반영**
- **pre-commit hook `--no-verify` 금지** — 훅 오탐 시 `-F` 파일 우회
- **코드 주석 최소 (CLAUDE.md)** — Why 가 중요한 부분만 간결히
- **실측 기반 검증** — 가정 대신 DB 쿼리 / `typings.d.ts` grep / Lighthouse JSON audit 으로 곧바로 확인

### 다음 세션에서 먼저 확인할 것

1. **브라우저 시각 검증** — `/stocks/012450` 캔들 + MA + Volume pane + OHLCV 툴팁 + 토글 7종 + grade 마커 색 + 1D/1W/1M 봉 주기 전환 정상 동작
2. **모바일 실기기 Gate A** — 핀치 줌/팬 UX
3. **Aurora CLS 개선** 여부 결정 — 실기기 체감 정상이면 Known Issue 유지, 체감 나쁘면 디자인 PR
4. **v1.2 착수 결정** — Bollinger / 파라미터 편집 UI / DB 영속화 / Vitest / Aurora 정리 중 우선순위
5. **이월 과제** (HIGH fetch race 전수, DIP 확장, `Mapped[Literal]`, R-04~06) 우선순위 결정

### 가치 있는 발견 (본 세션)

1. **Lighthouse color-contrast 감사 특성**: 한 노드 수정하면 가려졌던 다른 노드가 드러남 → 재측정 + 2차 수정 루프 필수. A11y 95→95→95→100 로 2 단계 필요했음.
2. **`#131720` dark surface 수학적 제약**: 어떤 fg 도 AA 통과하려면 L≥~0.21 필요 → "dim 하면서 legible" 은 동시 만족 불가. 계층은 크기/두께/위치로 표현.
3. **PoC 스파이크 ROI**: 30 분 타이핑으로 2 리스크 해소, Sprint 공수 추정 신뢰도 상승.
4. **`typings.d.ts` 직접 확인 > 훈련 데이터**: Context7 MCP 미등록 환경에서 에이전트 답변은 훈련 데이터 기반. `node_modules/*/dist/typings.d.ts` grep 이 빠르고 정확.
5. **`useSyncExternalStore` 의 snapshot 캐싱 함정**: 초보 패턴에서 getSnapshot 이 매번 새 객체 반환 → Object.is 비교 실패 → React #185 무한 루프. 모듈 스코프 캐시 필수.
6. **pre-commit hook heredoc 오탐 (프로젝트 메모리)**: `block-no-verify@1.1.2` 가 `git commit -m "$(cat <<EOF ... EOF)"` 를 `--no-verify` 로 오검출. `-F <file>` 즉시 우회책.
7. **lightweight-charts v5 `addPane` + `setHeight` + `removePane` 완비**: multi-pane 동적 관리가 공식 지원. v4 대비 강력한 확장성.
8. **aurora 애니메이션의 Chrome CLS 오검출**: `transform: translate3d + scale` 애니메이션이 CLS 로 계상되는 특이 케이스. `contain: layout paint` 도 효과 미미 — 애니메이션 정적화가 근본 해결.
9. **FE 자체 지표 구현의 번들 효율성**: technicalindicators ~40KB vs 자체 ~3KB. NFR 달성.

## Files Modified This Session

```
 .gitignore — 미변경
 CHANGELOG.md — ~200 ++ (10 커밋 분량 엔트리 prepend)
 HANDOFF.md — overwrite (본 문서)
 docs/lighthouse-scores.md — ~60 ++ (A11y 1차/2차 + Sprint A + Sprint B 측정 4개 섹션 prepend)
 pipeline/state/current-state.json — ~50 ++ (iterations.v1.1 블록)
 pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md — 신규
 pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md — 신규
 pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md — 신규
 pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md — 신규
 pipeline/artifacts/02-prd/sprint-plan-v1.1-chart-upgrade.md — 신규 (A1~A8, B0~B10 전부 ✅)
 pipeline/decisions/discovery-v1.1-judge.md — 신규 (Judge PASS 9.20)
 scripts/docker-rebuild.sh — ~30 ++ (env-file 자동 주입)
 src/frontend/src/app/globals.css — ~15 ++ (muted 토큰 + aurora contain + keyframes scale 제거)
 src/frontend/src/app/layout.tsx — 2 +- (muted)
 src/frontend/src/app/page.tsx — 6 +- (muted)
 src/frontend/src/app/stocks/[code]/page.tsx — ~200 ++ (봉 주기 + chartData/maLines/rsi/macd/토글/sr-only + 색대비 2건 + skeleton 정합)
 src/frontend/src/app/backtest/page.tsx — 16 +- (muted)
 src/frontend/src/app/portfolio/page.tsx — 16 +- (muted)
 src/frontend/src/app/portfolio/[accountId]/alignment/page.tsx — 6 +- (muted)
 src/frontend/src/app/reports/[stockCode]/page.tsx — 6 +- (muted)
 src/frontend/src/app/settings/page.tsx — 2 +- (muted)
 src/frontend/src/components/NavHeader.tsx — 2 +- (muted)
 src/frontend/src/components/features/SignalCard.tsx — 2 +- (muted)
 src/frontend/src/components/features/ExcelImportPanel.tsx — 2 +- (muted)
 src/frontend/src/components/features/RealAccountSection.tsx — 10 +- (muted + placeholder)
 src/frontend/src/components/charts/PriceAreaChart.tsx — 거의 재작성 (Candle + MA + Volume + RSI + MACD + 줌/팬 + OHLCV 툴팁 + grade 색)
 src/frontend/src/components/charts/IndicatorTogglePanel.tsx — 신규 (7 토글)
 src/frontend/src/components/charts/StockChartAccessibilityTable.tsx — 신규 (sr-only 30일 OHLCV)
 src/frontend/src/lib/hooks/useIndicatorPreferences.ts — 신규 (useSyncExternalStore + snapshot 캐싱)
 src/frontend/src/lib/indicators/sma.ts — 신규 (O(n))
 src/frontend/src/lib/indicators/rsi.ts — 신규 (Wilder)
 src/frontend/src/lib/indicators/macd.ts — 신규 (EMA + Signal + Histogram)
 src/frontend/src/lib/indicators/aggregate.ts — 신규 (weekly/monthly)
 src/frontend/src/lib/indicators/index.ts — barrel
```

**10 commits total. A11y 2 + scripts 1 + Sprint A 1 + handoff 1 + Sprint B 4 + hotfix 1.**
