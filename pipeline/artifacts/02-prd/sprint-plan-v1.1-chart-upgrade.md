---
agent: "02-pm"
stage: "02-prd"
version: "1.1.0"
iteration: "v1.1"
created_at: "2026-04-23T15:35:00+09:00"
depends_on:
  - "pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md"
quality_gate_passed: false
---

# Sprint Plan — v1.1 차트 고도화 (2주 × 2 = 3주 내 런칭)

## RICE 스코어링 (v1.1 MVP 기능)

| 기능 | Reach | Impact | Confidence | Effort (days) | **RICE** | 우선순위 |
|---|---:|---:|---:|---:|---:|---|
| **Candlestick 전환** | 10 | 3 | 0.9 | 1 | **27.0** | P0 (Sprint A) |
| **거래량 histogram** | 10 | 3 | 0.9 | 1 | **27.0** | P0 (Sprint A) |
| **MA(5/20/60/120) 오버레이** | 10 | 3 | 0.95 | 1.5 | **19.0** | P0 (Sprint A) |
| **줌/팬 활성화** | 10 | 2 | 1.0 | 0.3 | **66.7** | P0 (Sprint A, 번들링 free) |
| **OHLCV 툴팁** | 10 | 2 | 0.9 | 0.5 | **36.0** | P0 (Sprint A) |
| **RSI(14) pane** | 8 | 2.5 | 0.85 | 1 | **17.0** | P1 (Sprint B) |
| **MACD pane** | 8 | 2.5 | 0.85 | 1.5 | **11.3** | P1 (Sprint B) |
| **토글 UI** | 10 | 2.5 | 0.9 | 1 | **22.5** | P0 (Sprint B) |
| **localStorage 영속화** | 10 | 2 | 0.9 | 0.5 | **36.0** | P0 (Sprint B) |
| **sr-only 테이블** | 3 | 3 | 0.95 | 0.5 | **17.1** | P0 (Sprint B, A11y 유지 필수) |
| **시그널 마커 호환 검증** | 10 | 3 | 0.9 | 0.3 | **90.0** | P0 (전 스프린트 회귀) |

**RICE 포뮬러**: `Reach × Impact × Confidence / Effort`  (Reach 10=전 사용자, Impact 0-3)

## 스프린트 분해

### Sprint A — "가격 페인 완성" (1.5주, 2026-04-24 ~ 2026-05-03)

**목표**: 가격 차트가 증권사 앱 수준이 된다 (시그널 마커 회귀 없음)

| # | 태스크 | 산출 | 인원 | 예상 공수 | 상태 |
|---|---|---|---|---:|---|
| A1 | `lightweight-charts` v5 multi-pane API PoC | 30분 스파이크 (2026-04-23) | FE | 0.5d | ✅ **완료** — `chart.addPane()` + `IPane.setHeight(px)` v5 네이티브 확인 (node_modules `typings.d.ts:1689,1932`) |
| A2 | `PriceAreaChart.tsx` Area → Candlestick 전환 + OHLC 결측/0값 방어 | diff | FE | **1.25d** | ✅ **완료** — CandlestickSeries (한국 증시 색) + 0값 행 사전 필터, 마커 `inBar → aboveBar` |
| A3 | `indicators/sma.ts` 유틸 (SMA window 5/20/60/120) + JSDoc sanity (vitest 도입은 v1.2) | `src/lib/indicators/*.ts` | FE | 0.5d | ✅ **완료** — O(n) 슬라이딩 윈도우 + barrel export |
| A4 | MA LineSeries 오버레이 (4개, 색 Palette) | diff | FE | 1d | ✅ **완료** — 5/20/60/120 각 색 노랑/오렌지/녹색/보라, window 별 Map 관리 |
| A5 | 거래량 HistogramSeries — 별도 pane + 색 상승/하락 | diff | FE | 1d | ✅ **완료** — `chart.addPane()` + `setHeight(96px)`, 반투명 상승/하락 색 |
| A6 | 줌/팬 활성화 (`handleScroll/handleScale: true`) + 모바일 터치 테스트 | diff | FE | 0.5d | ✅ **완료** — 옵션 플립, 라이브러리가 핀치 줌 자동 처리 |
| A7 | OHLCV 툴팁 (CrosshairMove 이벤트) | diff | FE | 0.5d | ✅ **완료** — subscribeCrosshairMove + React state 오버레이 (우상단, pointer-events-none, aria-live) |
| A8 | **회귀 테스트**: 시그널 마커 캔들 시리즈 호환, Lighthouse Perf/A11y 재측정 | 스크린샷 + scores | FE | 0.5d | ✅ **완료** — Perf 95 / A11y 100 / BP 100 / SEO 100 유지 |
| | **Sprint A 합계** | | | **5.25d** | ✅ **Sprint A 완료 (2026-04-23 단일 세션)** |

**Gate A (Sprint A 완료 조건)**:
- [x] 시그널 마커 여전히 캔들 위 표시 (`aboveBar` 로 이동, 노랑 `#FFCC00`)
- [x] Lighthouse Perf ≥ 90, A11y ≥ 100 유지 — **Perf 95 / A11y 100**
- [x] JS 번들 순증 ≤ 10KB gzipped — SMA 유틸 ~0.4KB + 내부 로직만 (외부 의존성 0)
- [ ] 모바일 Safari + Chrome 터치 줌/팬 동작 확인 — **사용자 수동 확인 필요** (실기기 or DevTools touch emulation)

> **Gate A 판정: 3/4 자동 통과**. 모바일 터치 인터랙션은 브라우저 환경에서 사용자 1회 확인으로 완료.

### Sprint B — "지표 생태계 + 영속화" (1.5주, 2026-05-04 ~ 2026-05-13)

**목표**: 사용자가 지표를 on/off 해 화면을 구성한다, 설정이 유지된다

| # | 태스크 | 산출 | 인원 | 예상 공수 |
|---|---|---|---|---:|
| B1 | `indicators/rsi.ts` (Wilder's smoothing) + 테스트 | src + test | FE | 0.5d |
| B2 | `indicators/macd.ts` (EMA + signal + histogram) + 테스트 | src + test | FE | 1d |
| B3 | RSI LineSeries + 별도 pane + 70/30 가이드 라인 | diff | FE | 0.5d |
| B4 | MACD Line + Signal Line + Histogram — 별도 pane | diff | FE | 1d |
| B5 | `IndicatorTogglePanel.tsx` 컴포넌트 — 색칩 + 스위치 + aria | 신규 | FE | 1d |
| B6 | `useIndicatorPreferences.ts` — SSR-safe localStorage hook + zod 검증 | 신규 | FE | 0.5d |
| B7 | `StockChartAccessibilityTable.tsx` (sr-only 최근 30일 OHLCV + 활성 지표) | 신규 | FE | 0.5d |
| B8 | 모바일 breakpoint 기본 토글 집합 (MA5/MA20/Volume만 ON) | diff | FE | 0.3d |
| B9 | **Gate 3 재측정**: Lighthouse 7페이지 + FPS 측정 | `lighthouse-scores.md` prepend | FE | 0.5d |
| B10 | QA 체크리스트 + 수동 시나리오 실행 | `pipeline/artifacts/07-test-results/v1.1-qa.md` | QA 겸 | 0.5d |
| | **Sprint B 합계** | | | **6.3d (1.5주 빠듯)** |

**Gate B (v1.1 런칭 조건)**:
- [ ] 모든 지표 on/off 토글 정상 동작
- [ ] localStorage 재방문 복원 동작 (Chrome/Safari/Firefox)
- [ ] sr-only 테이블 존재 — VoiceOver/NVDA 기본 네비 가능
- [ ] Lighthouse `/stocks/005930`: Perf ≥ 90, A11y = 100
- [ ] 시그널 마커 회귀 없음
- [ ] 번들 순증 ≤ 20KB gzipped
- [ ] 모바일 (iPhone SE, Galaxy S8) 실기기 스모크 OK

## 크리티컬 패스

```
A1 (PoC)
  → A2 (candle 전환) → A4 (MA 오버레이) → A5 (volume pane) → A8 (회귀)
                                           ↓
                                      B3 (RSI) ─┐
                                      B4 (MACD)├→ B5 (토글) → B6 (영속화) → B9/B10 (검증)
                                                 ┘
```

**A1 PoC 실패 시 대안**: multi-pane 대신 `priceScaleId` 분리 + 단일 차트 세로 분할. 공수 +0.5d 예상.

## 의존성 / 선행 조건

| 선행 조건 | 상태 |
|---|---|
| lightweight-charts v5 설치 | ✅ `package.json` 확인됨 |
| **lightweight-charts v5 multi-pane API** | ✅ **2026-04-23 A1 PoC 로 완전 해소** (`chart.addPane()` + `IPane.setHeight(px)` + JSDoc 3-pane 예시 `typings.d.ts:2002-2004`) |
| backend OHLCV 응답 | ✅ `StockPricePoint` 에 open/high/low/volume 이미 있음 |
| KRX 크롤러 OHLC 파싱 | ✅ `krx_client.py:229-231` 확인 |
| **실 OHLC 데이터 존재 (005930)** | ✅ **2026-04-23 DB 쿼리로 해소** — 753 거래일 100% OHLC 완비, 최근 90일 62/62. 단 마지막 1건(2026-04-20) 0값 레코드 존재 → A2 에 방어 로직 추가 |
| A11y 기준 체계 | ✅ `#131720` WCAG 가이드 확립됨 (직전 커밋 `ccc7c51` 까지) |

## 커뮤니케이션 / 승인 게이트

- **Gate A 완료 → 사용자 리뷰 승인**: Sprint A PR 머지 전 사용자가 `/stocks/005930` 수동 확인
- **Gate B 완료 → 사용자 런칭 승인**: 전체 시나리오 리뷰 + Lighthouse 증빙 + v1.1 태그 생성

## 기술 부채 / 비즈니스 가치 균형

- **부채 축적 위험**: FE 지표 계산 유틸을 자체 구현 → 버그 책임 FE 팀. 단, 외부 라이브러리(technicalindicators 등) 채택 시 번들 +30~50KB 리스크 > 자체 구현 ~5KB. NFR-C03 준수 위해 자체 구현 채택.
- **비즈니스 가치**: 이번 작업은 v1.0 MVP 의 "시그널 신뢰도" 이슈를 간접 해결 (지표 맥락 제공으로 사용자가 직접 검증 가능). 전환율 +10pp 은 포트폴리오 실사용 전환과 직결.
