---
agent: "02-pm"
stage: "02-prd"
version: "1.1.0"
iteration: "v1.1"
created_at: "2026-04-23T15:25:00+09:00"
depends_on:
  - "pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md"
quality_gate_passed: false
changelog:
  - version: "1.1.0"
    changes: "v1.1 차트 고도화 PRD"
---

# PRD — v1.1 `/stocks/[code]` 차트 고도화

## 1. 제품 개요

### 1.1 배경
v1.0 배포로 `/stocks/005930` 상세 페이지에 TradingView Lightweight Charts v5 가 도입됨. 하지만 현재는 가격 AreaSeries 1개 + 시그널 마커 뿐이라 **종목의 기술적 상태(모멘텀/거래량/추세)** 해석은 여전히 외부 도구(증권사 앱) 에서 수행해야 함. v1.1 은 이 단절을 봉합해 **시그널→지표→의사결정** 이 한 페이지에서 완결되도록 한다.

### 1.2 목표
- **정보 통합**: OHLC + 거래량 + MA + RSI + MACD 를 한 화면에 배치
- **사용자 주도권**: 지표 on/off 토글 + 설정 영속화
- **번들 경량 유지**: 지표 계산 FE 자체 구현, JS 순증 ≤ 20KB gzipped
- **v1.0 자산 보호**: 기존 시그널 마커와 성능 점수(Perf 95, A11y 100) 유지

### 1.3 Out of Scope (v1.1)
- Bollinger Bands (v1.2)
- 지표 파라미터 커스터마이징 UI (v1.2)
- DB 기반 설정 동기화 (v1.2)
- 지표 템플릿 저장/공유 (v1.3)

## 2. 타겟 사용자
| 페르소나 | 특징 | v1.1 가치 |
|---|---|---|
| **P1: 본인 (primary)** | v1.0 주 사용자, 시그널 검증 목적 | 시그널 트리거 시점의 기술 맥락을 한 눈에 검토 |
| **P2: 향후 소수 공유 대상** | v1.1 이후 클로즈드 베타 가능성 | 친숙한 증권사 앱 스타일 차트로 학습 곡선 낮춤 |

## 3. 기능 스펙

### 3.1 차트 기본 변환
| 기능 | 현재 | v1.1 |
|---|---|---|
| 가격 시리즈 | AreaSeries (close 1개) | **CandlestickSeries** (OHLC) + 결측 fallback |
| 상승/하락 색 | (없음, Area 단일색) | **빨강 상승 / 파랑 하락** (한국 증시 관례) |
| 인터랙션 | `handleScroll: false`, `handleScale: false` | **활성화** (팬/핀치줌) |
| 크로스헤어 | 기본값 | **OHLCV 툴팁 overlay** |

### 3.2 지표 (Indicator)
| 지표 | 타입 | 위치 | 파라미터 | 기본 ON |
|---|---|---|---|---|
| MA5 | SMA | 가격 페인 오버레이 | window=5 | ✓ |
| MA20 | SMA | 가격 페인 오버레이 | window=20 | ✓ |
| MA60 | SMA | 가격 페인 오버레이 | window=60 | ✗ |
| MA120 | SMA | 가격 페인 오버레이 | window=120 | ✗ |
| Volume | Histogram | 별도 페인 (~30%) | — | ✓ |
| RSI(14) | Line | 별도 페인 (~20%) | period=14, OB=70, OS=30 | ✗ |
| MACD(12,26,9) | Line + Hist | 별도 페인 (~20%) | fast=12, slow=26, signal=9 | ✗ |

**모바일 breakpoint (<640px)**: 기본 ON 집합 축소 — MA5, MA20, Volume 만. RSI/MACD 는 토글로 추가.

### 3.3 설정 영속화
- **스토어**: `localStorage` (key: `stock-chart-indicators:v1`)
- **SSR-safe**: 초기 렌더 default → mount 후 localStorage 반영 (hydration shift 없도록 `useEffect` 내부에서 적용)
- **스키마**: zod 검증. 악성/변조값은 default fallback.
- **스키마 예시**:
  ```json
  {
    "ma5": true, "ma20": true, "ma60": false, "ma120": false,
    "volume": true, "rsi": false, "macd": false
  }
  ```

### 3.4 접근성
- **sr-only 테이블**: 최근 30 거래일 OHLCV + 활성 지표 값을 `<table>` 로 제공
- **차트 SVG/canvas**: `aria-hidden="true"` (AT 숨김)
- **토글**: 키보드 접근 (`focus-visible:ring`) + `aria-pressed` 상태

## 4. UX 개략 (와이어프레임 설명)

```
┌─────────────────────────────────────────┐
│  [←대시보드]                              │
│  ┌──────────┐  ┌──────────┐              │
│  │ 종목 헤더 │  │ 시그널 스코어 │          │
│  └──────────┘  └──────────┘              │
│  [1M][3M][6M][1Y]                        │
│                                          │
│  ┌───────── 지표 토글 ──────────┐         │
│  │ ● MA5  ● MA20  ○ MA60  ○ MA120 │     │
│  │ ● Volume  ○ RSI  ○ MACD  │         │
│  └────────────────────────────┘         │
│                                          │
│  ┌───── 가격 페인 (~50%) ──────┐          │
│  │  Candlestick + MA overlay + │          │
│  │  시그널 마커                │          │
│  │  [OHLCV 툴팁 ↖ 우상단]      │          │
│  └────────────────────────────┘          │
│  ┌─── 거래량 페인 (~30%) ──────┐          │
│  │  Histogram (상승/하락 색)   │          │
│  └────────────────────────────┘          │
│  ┌─── RSI 페인 (~20%) ─────────┐ (옵션)   │
│  │  Line + 70/30 가이드        │          │
│  └────────────────────────────┘          │
│  ┌─── MACD 페인 (~20%) ────────┐ (옵션)   │
│  │  MACD/Signal + Histogram    │          │
│  └────────────────────────────┘          │
│                                          │
│  (sr-only table: 30일 OHLCV + 지표값)     │
└─────────────────────────────────────────┘
```

## 5. 기술 결정

### 5.1 지표 계산 위치 — **FE**
- BE 왕복 없이 기존 `/api/stocks/{code}` 응답의 `prices` 배열로 계산
- SMA: `O(n)` 슬라이딩 윈도우
- RSI: Wilder's smoothing, `O(n)`
- MACD: 두 EMA + 그 차이의 EMA, `O(n)`
- 외부 의존성 0, 자체 유틸 함수 (`src/lib/indicators/*.ts`)

### 5.2 Multi-pane 구현 — **lightweight-charts v5 `addPane`**
- v5 에서 `chart.addPane({ height })` API 공식 지원
- 착수 시 실제 API 버전 확인 필수 (package.json `^5.1.0`)
- 제약 발견 시 대안: `chart.addSeries(SeriesType, { priceScaleId: 'volume' })` + `priceScale` 영역 분리

### 5.3 Candlestick 색 관례 — 한국 증시 기준
- 상승: `#FF4D6A` (기존 변화율 상승 색)
- 하락: `#6395FF` (기존 변화율 하락 색, accent)
- v1.0 의 시각 언어 일관성 유지

### 5.4 상태 관리
- 지표 토글 상태: React `useState` + `useEffect` localStorage 동기화
- Zustand 등 별도 스토어 도입 불필요 (페이지 로컬 상태)

### 5.5 성능 전략
- `useMemo` 로 지표 계산 캐싱 — deps 는 `prices` 참조
- 데이터 변경 시에만 재계산, 토글 on/off 는 series 표시/숨김 토글로 처리
- 시리즈 동적 add/remove 보다 `series.applyOptions({ visible: false })` 권장

## 6. 성공 지표 (KPI)

### 6.1 정량 (Launch criteria)
| 지표 | 기준값 | 측정 방법 |
|---|---|---|
| `/stocks/005930` Lighthouse Perf | ≥ 90 | `./scripts/lighthouse-mobile.sh` |
| `/stocks/005930` Lighthouse A11y | ≥ 100 | 동상 |
| LCP (모바일 4G throttle) | ≤ 2500ms | 동상 |
| TBT | ≤ 100ms | 동상 |
| first-load JS 순증 | ≤ 20KB gzipped | `yarn build` 후 `.next/static/chunks` 비교 |
| 렌더 FPS (500 포인트 × 지표 5개) | ≥ 30 | DevTools Performance 탭 |

### 6.2 정성
- 본인 시그널 해석 세션에서 외부 증권사 앱 의존 횟수 ↓
- 시그널 마커 hover 시 "왜 이 시점에 시그널?" 을 MA/RSI/MACD 맥락으로 즉답 가능

## 7. 리스크 & 완화 (requirements.md 에서 상속)
- RISK-C01 (High) KRX 익명 차단 — 시드 데이터 + 실계정 확보 옵션
- RISK-C02 (Medium) multi-pane API 제약 — PoC 선행
- RISK-C03 (Medium) FE 지표 성능 — useMemo + 500포인트 상한
- RISK-C04 (Low) 설정 동기화 누락 — v1.2 이월
- RISK-C05 (Low) 모바일 페인 밀도 — breakpoint 기본값 차등

## 8. 의존성 & 가정
- **의존성**: `lightweight-charts@^5.1.0` 이미 설치됨. 추가 패키지 **0**.
- **가정**: `/api/stocks/{code}` 응답의 `prices[].open_price/high_price/low_price/volume` 이 채워져 있음 (KRX 크롤러 확인됨, 익명 차단 해제 시 유효).
- **영향 범위**: `src/frontend/src/components/charts/PriceAreaChart.tsx`, `src/frontend/src/app/stocks/[code]/page.tsx`, 신규 `src/frontend/src/lib/indicators/*.ts`.
