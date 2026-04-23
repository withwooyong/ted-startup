---
agent: "01-biz-analyst"
stage: "01-requirements"
version: "1.1.0"
iteration: "v1.1"
created_at: "2026-04-23T15:10:00+09:00"
depends_on:
  - "pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/01-requirements/requirements.md"  # v1.0 base
quality_gate_passed: false
changelog:
  - version: "1.1.0"
    changes: "v1.1 차트 고도화 요구사항 분석 — (C) 풀 스택 범위"
---

# Requirements — v1.1 `/stocks/[code]` 차트 고도화

## 스키마 (YAML 본문)

```yaml
project_name: "Chart UX 고도화 v1.1"

business_goals:
  - goal: "종목 상세 차트의 정보 밀도를 업계 표준(트레이딩뷰/증권사 앱) 수준으로 확장"
    success_metric: "/stocks/[code] 세션당 체류 시간 중앙값 현재 N 초 → +50% 이상"
  - goal: "시그널 해석 정확도 향상 — 지표 맥락과 함께 시그널 마커가 해석됨"
    success_metric: "/stocks/[code] 에서 백테스트/포트폴리오로 이동하는 전환율 +10pp"
  - goal: "기술 스택 의존성 0 증가로 번들 경량 유지"
    success_metric: "first-load JS 순증 < 80KB gzipped (lightweight-charts 50KB 이미 포함, 지표 계산은 FE 자체 구현)"

user_stories:
  - id: US-C01
    as_a: "개인 투자자"
    i_want: "가격 차트를 OHLC 캔들스틱으로 볼 수 있기를"
    so_that: "시가/고가/저가/종가의 상대 관계로 매매 강도를 직관적으로 판단"
    acceptance_criteria:
      - "Candlestick 시리즈에 상승일은 빨강, 하락일은 파랑 (한국 증시 관례)"
      - "open/high/low 결측일은 Area fallback 으로 표시하거나 캔들 생략"
      - "기존 시그널 마커는 캔들 시리즈에도 정상 적용"
    priority: "Must"

  - id: US-C02
    as_a: "개인 투자자"
    i_want: "이동평균선(MA5/20/60/120)을 가격 차트 위에 겹쳐 보기를"
    so_that: "단기/중기/장기 추세를 동시에 읽을 수 있다"
    acceptance_criteria:
      - "4개 기간 MA 라인이 서로 다른 색상으로 구분됨"
      - "각 라인의 범례가 우상단 또는 토글 패널에 표시"
      - "데이터 양 < MA 기간 구간은 자연히 생략 (NaN 영역)"
    priority: "Must"

  - id: US-C03
    as_a: "개인 투자자"
    i_want: "거래량 히스토그램을 가격 차트 아래 별도 페인에서 확인하기를"
    so_that: "가격 움직임과 거래량 변화를 동시 시각적으로 연관지을 수 있다"
    acceptance_criteria:
      - "페인 높이 비율 대략 70% 가격 / 30% 거래량"
      - "상승일 빨강 / 하락일 파랑 (캔들과 일관)"
      - "거래량 스케일은 독립 (가격과 분리)"
    priority: "Must"

  - id: US-C04
    as_a: "개인 투자자"
    i_want: "RSI(14) 를 별도 페인에서 70/30 과매수/과매도 선과 함께 확인하기를"
    so_that: "모멘텀 과열 여부를 빠르게 판단"
    acceptance_criteria:
      - "RSI 페인 높이 ~20%"
      - "70/30 가로 가이드 라인"
      - "14 미만 구간은 계산 불가이므로 비어있음"
    priority: "Must"

  - id: US-C05
    as_a: "개인 투자자"
    i_want: "MACD(12,26,9) 를 별도 페인에서 MACD 라인, Signal 라인, Histogram 함께 확인하기를"
    so_that: "추세 전환 타이밍 판단"
    acceptance_criteria:
      - "MACD 라인, Signal 라인, Histogram 모두 표시"
      - "Histogram 은 0 기준 상/하 색 구분"
      - "페인 높이 ~20%"
    priority: "Must"

  - id: US-C06
    as_a: "개인 투자자"
    i_want: "Bollinger Bands(20, 2σ) 를 가격 차트에 오버레이로 보기를"
    so_that: "변동성 밴드 폭으로 breakout/수축 시점 포착"
    acceptance_criteria:
      - "상/중/하 밴드 반투명 영역 채움"
      - "토글 기본 OFF (화면 복잡도 관리)"
    priority: "Could"  # v1.1 MVP deferred, v1.2 예정

  - id: US-C07
    as_a: "개인 투자자"
    i_want: "각 지표를 개별 on/off 토글로 제어하기를"
    so_that: "원하는 정보만 남기고 차트 밀도를 조절"
    acceptance_criteria:
      - "토글 UI 는 차트 상단 또는 사이드에 배치"
      - "각 지표별 색 칩 + 이름 + on/off 스위치"
      - "토글 애니메이션 <150ms, 레이아웃 shift 없음 (CLS<0.1)"
    priority: "Must"

  - id: US-C08
    as_a: "개인 투자자"
    i_want: "내가 선택한 지표 on/off 조합이 재방문해도 유지되기를"
    so_that: "매번 다시 설정하지 않아도 됨"
    acceptance_criteria:
      - "localStorage 키: `stock-chart-indicators:v1` (JSON)"
      - "SSR-safe (mount 전엔 default 상태, mount 후 localStorage 반영)"
      - "익명 사용자도 동작 (DB 영속화는 deferred)"
    priority: "Must"

  - id: US-C09
    as_a: "개인 투자자"
    i_want: "차트를 좌우로 드래그(팬) / 스크롤(줌) 해서 과거 구간을 탐색하기를"
    so_that: "기간 버튼(1M/3M/6M/1Y) 이상의 세밀한 탐색 가능"
    acceptance_criteria:
      - "lightweight-charts handleScroll/handleScale 활성화"
      - "모바일 터치 핀치 줌 지원 (추가 설정 불필요)"
      - "팬 한계는 데이터 범위 넘지 않도록"
    priority: "Must"

  - id: US-C10
    as_a: "개인 투자자"
    i_want: "특정 시점에 hover 하면 그 날의 OHLCV 값을 툴팁으로 보기를"
    so_that: "정확한 수치를 추출 가능"
    acceptance_criteria:
      - "hover 시 차트 좌상단 또는 crosshair 라벨에 O/H/L/C/V 표시"
      - "거래량은 천 단위 구분 또는 M/K 축약"
      - "결측값은 `-` 로 표기"
    priority: "Must"

  - id: US-C11
    as_a: "스크린리더 사용자"
    i_want: "차트 데이터를 sr-only 표로 대체 접근할 수 있기를"
    so_that: "시각 의존 없이 OHLCV 시계열 탐색 가능"
    acceptance_criteria:
      - "sr-only <table> 에 최근 30 거래일 OHLCV + MA + 시그널 열"
      - "aria-hidden 으로 SVG 는 AT 에서 숨김"
    priority: "Must"

  - id: US-C12
    as_a: "개인 투자자"
    i_want: "기존 시그널 마커(대차 급감/추세전환/숏스퀴즈)가 지표 페인과 공존해도 가독성 유지되기를"
    so_that: "v1.0 시그널 시스템의 핵심 가치가 훼손되지 않음"
    acceptance_criteria:
      - "마커는 가격 페인에만 표시 (지표 페인에는 영향 없음)"
      - "지표 OFF 상태에서도 마커는 독립 동작"
      - "시그널 hover 시 툴팁과 OHLCV 툴팁이 충돌하지 않음"
    priority: "Must"

functional_requirements:
  - id: FR-C01
    description: "Candlestick 시리즈 전환 — 기존 AreaSeries 를 CandlestickSeries 로 교체, OHLC 결측 방어"
    related_user_stories: [US-C01]
  - id: FR-C02
    description: "MA 계산 유틸 — 단순이동평균(SMA) 5/20/60/120 FE 계산. window < N 구간은 NaN"
    related_user_stories: [US-C02]
  - id: FR-C03
    description: "가격 페인 내 MA LineSeries 4개 오버레이 + 범례"
    related_user_stories: [US-C02]
  - id: FR-C04
    description: "거래량 HistogramSeries — 별도 price scale (상/하 페인 비율 70/30)"
    related_user_stories: [US-C03]
  - id: FR-C05
    description: "RSI(14) 계산 유틸 + 별도 pane + 70/30 가이드 라인"
    related_user_stories: [US-C04]
  - id: FR-C06
    description: "MACD(12,26,9) 계산 유틸 + 별도 pane + MACD/Signal 라인 + Histogram"
    related_user_stories: [US-C05]
  - id: FR-C07
    description: "지표 on/off 토글 패널 컴포넌트 (차트 상단 또는 사이드)"
    related_user_stories: [US-C07]
  - id: FR-C08
    description: "localStorage 기반 설정 영속화 — SSR-safe hook (`useIndicatorPreferences`)"
    related_user_stories: [US-C08]
  - id: FR-C09
    description: "handleScroll/handleScale 활성화 + 팬 경계 처리"
    related_user_stories: [US-C09]
  - id: FR-C10
    description: "CrosshairMove 이벤트 기반 OHLCV 툴팁 — 우상단 overlay 또는 네이티브 label"
    related_user_stories: [US-C10]
  - id: FR-C11
    description: "sr-only <table> — 최근 30 거래일 OHLCV + 활성 지표 값"
    related_user_stories: [US-C11]
  - id: FR-C12
    description: "기존 시그널 마커 플러그인 캔들 시리즈 호환성 검증 + 회귀 테스트"
    related_user_stories: [US-C12]

non_functional_requirements:
  - id: NFR-C01
    category: "Performance"
    target_metric: "`/stocks/005930` Lighthouse Perf 90 이상 유지 (현재 95)"
  - id: NFR-C02
    category: "Performance"
    target_metric: "LCP <= 2500ms 유지 (현재 1902ms), TBT <= 100ms 유지 (현재 44ms)"
  - id: NFR-C03
    category: "Performance"
    target_metric: "first-load JS 순증 <= 20KB gzipped (지표 FE 계산 경량 라이브러리 없이 자체 구현)"
  - id: NFR-C04
    category: "Performance"
    target_metric: "렌더 FPS >= 30 기준 (iOS Safari + Galaxy S8 4G throttle), 500 데이터포인트 × 지표 5개"
  - id: NFR-C05
    category: "Accessibility"
    target_metric: "Lighthouse A11y 100 유지 (현재 100). color-contrast WCAG AA 유지 (#131720 배경)"
  - id: NFR-C06
    category: "Accessibility"
    target_metric: "sr-only 표 존재 + aria-hidden 차트. 키보드로 토글 접근 가능 (focus-visible:ring)"
  - id: NFR-C07
    category: "Scalability"
    target_metric: "지표 모듈 추가 시 차트 컴포넌트 수정 최소 — 1개 추가 = <50줄 변경"
  - id: NFR-C08
    category: "Security"
    target_metric: "localStorage JSON 스키마 검증 (zod). 악성/변조값은 default로 fallback"

risks:
  - id: RISK-C01
    impact: "High"
    description: "**KRX 익명 차단 블로커** (프로젝트 메모리 기록) — OHLC 실데이터 부재 가능성. KRX 2026-04 전면 인증화로 KRX_ID/KRX_PW 없으면 데이터 0 rows."
    mitigation: "(1) seed_ui_demo.py 로 OHLCV 시드 데이터 보강 확인 (2) 실제 KRX 계정 확보 여부 확인 (3) 차트 컴포넌트는 결측 방어 로직 내장 (open/high/low null 시 Area fallback)"

  - id: RISK-C02
    impact: "Medium"
    description: "lightweight-charts v5 multi-pane API 제약 — pane 추가/크기 커스텀 제한 가능성"
    mitigation: "구현 착수 전 `addPane({ height })` / `createPane` API 공식 문서 확인. 제약 시 canvas 중첩 또는 multi-chart instance 대안."

  - id: RISK-C03
    impact: "Medium"
    description: "FE 지표 계산 성능 — 120 기간 SMA + RSI + MACD + 500 데이터포인트 실시간 재계산"
    mitigation: "useMemo 로 캐싱, 데이터 변경 시에만 재계산. 입력 배열 크기 따라 worker 분리 옵션 대기 (v1.2)."

  - id: RISK-C04
    impact: "Low"
    description: "설정 영속화 위치 — localStorage(익명 가능) vs DB(로그인 연동). 기기간 동기화 누락."
    mitigation: "v1.1 MVP 는 localStorage. 로그인 사용자 DB 영속화는 v1.2 별도 스프린트."

  - id: RISK-C05
    impact: "Low"
    description: "모바일 화면에서 다중 페인 시 정보 과밀"
    mitigation: "mobile breakpoint 시 기본 OFF 토글 집합 재정의 (MA/거래량만 기본 ON, RSI/MACD 기본 OFF). 사용자 토글로 추가 가능."

mvp_scope:
  included:
    - "Candlestick 시리즈 전환 (FR-C01)"
    - "MA 5/20/60/120 오버레이 (FR-C02, FR-C03)"
    - "거래량 histogram pane (FR-C04)"
    - "RSI(14) pane (FR-C05)"
    - "MACD(12,26,9) pane (FR-C06)"
    - "토글 UI (FR-C07)"
    - "localStorage 영속화 (FR-C08)"
    - "줌/팬 활성화 (FR-C09)"
    - "OHLCV hover 툴팁 (FR-C10)"
    - "sr-only 대체 테이블 (FR-C11)"
    - "시그널 마커 호환성 유지 (FR-C12)"
  deferred:
    - "Bollinger Bands (US-C06, v1.2)"
    - "지표 파라미터 사용자 편집 UI (v1.2)"
    - "DB 영속화 + 기기간 동기화 (v1.2)"
    - "지표 템플릿 프리셋 관리 (v1.3)"
    - "지표 기반 알림 확장 (v1.3)"
    - "Web Worker 지표 계산 오프로드 (v1.2 조건부)"

benchmarks:
  - name: "TradingView 웹"
    references: "multi-pane, 100+ indicator, 설정 저장"
  - name: "네이버 증권 모바일 차트"
    references: "한국 증시 관례 색상, 터치 UX"
  - name: "한국투자증권 MTS 차트"
    references: "지표 토글 패널 UX, MA 기본 프리셋(5/20/60/120)"
```

## 체크리스트 (biz-analyst self-audit)
- [x] 요구사항 모호 부분 가정 명시 (토글 배치, 색상 관례, 지표 기본값)
- [x] 경쟁 서비스 3개 이상 벤치마킹 (TradingView/네이버/한투)
- [x] NFR 측정 가능 수치 (Perf 90, LCP 2500ms, JS 20KB, FPS 30, A11y 100)
- [x] 사용자 스토리 10개 이상 (12개)
- [x] MVP 4-6주 내 런칭 가능 범위 (2스프린트 = 3주 예상)
- [x] v1.0 제약/도메인 상속 명시
