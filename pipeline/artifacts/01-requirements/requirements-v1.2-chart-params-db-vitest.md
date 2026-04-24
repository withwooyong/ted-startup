---
agent: "01-biz-analyst"
stage: "01-requirements"
version: "1.2.0"
iteration: "v1.2"
created_at: "2026-04-24T09:15:00+09:00"
depends_on:
  - "pipeline/artifacts/00-input/user-request-v1.2-chart-params-db-vitest.md"
  - "pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md"
quality_gate_passed: false
changelog:
  - version: "1.2.0"
    changes: "v1.2 BB + 지표 파라미터 편집 UI + DB 영속화 + Vitest 하네스 요구사항 분석"
---

# Requirements — v1.2 차트 파라미터 편집 + DB 영속화 + Vitest 하네스

## 스키마 (YAML 본문)

```yaml
project_name: "Chart Personalization & Test Harness v1.2"

business_goals:
  - goal: "지표 파라미터를 사용자가 직접 튜닝해 자신의 매매 스타일에 맞춤"
    success_metric: "파라미터 편집 UI 노출 4 주 내 자기 프리셋 설정 ≥ 1 회 사용자 비율 100% (내부 사용자 1 명 기준)"
  - goal: "설정이 기기/브라우저 경계를 넘어 유지됨 — DB 영속화로 기기간 동기화"
    success_metric: "동일 ADMIN_API_KEY 를 공유하는 2 디바이스 이상에서 프리셋 일관성 100% (본 서비스는 내부 싱글 오퍼레이터 모델)"
  - goal: "FE 리그레션 안전망 확보 — 지표 계산 + 영속화 훅의 회귀를 CI 로 방지"
    success_metric: "Vitest 단위+컴포넌트 테스트 커버리지 src/lib/indicators/ 90% 이상, src/lib/hooks/useIndicatorPreferences.ts 100%"
  - goal: "Bollinger Bands 로 변동성 해석 수단 추가"
    success_metric: "`/stocks/[code]` 에서 BB 토글 ON 시 상/중/하 밴드 렌더 + 가격 band touch 감지 수동 검증"
  - goal: "번들 경량 정책 유지"
    success_metric: "first-load JS 순증 ≤ 15KB gzipped (BB 유틸 ~1KB + 편집 UI ~6KB + preferences v2 변환 ~0.5KB; Vitest 는 devDep 로 prod 미영향)"

user_stories:
  - id: US-D01
    as_a: "개인 투자자"
    i_want: "Bollinger Bands(20, 2σ) 를 가격 차트에 오버레이로 보기를"
    so_that: "변동성 밴드 폭/접촉으로 breakout 과 수축 시점을 포착"
    acceptance_criteria:
      - "상(upper) / 중(middle=SMA20) / 하(lower) 3 선 + 상-하 반투명 영역 채움"
      - "`(period, k)` 기본값 (20, 2). period 미만 구간은 자연 생략"
      - "토글 기본 OFF — 화면 복잡도 관리"
      - "색은 기존 MA 팔레트와 충돌하지 않는 청록 계열 (예: upper `#6FD4D4` / lower `#6FD4D4` / middle `#A8B2BF`)"
    priority: "Must"

  - id: US-D02
    as_a: "개인 투자자"
    i_want: "MA 4 개, RSI, MACD, BB 의 파라미터를 편집 UI 에서 직접 수정하기를"
    so_that: "트레이더 스타일별 튜닝(예: 단기 매매 MA 3/7/15, 스윙 RSI 9 등)이 가능"
    acceptance_criteria:
      - "편집 진입: 토글 패널의 설정 아이콘 클릭 또는 차트 상단 '지표 설정' 버튼"
      - "편집 범위: MA window (각 4 슬롯, 2-240), RSI period (2-60), MACD(fast 2-50 / slow 4-100 / signal 2-50, fast < slow 강제), BB(period 5-100, k 0.5-4.0)"
      - "검증 실패 시 입력 필드 aria-invalid + inline 에러 메시지 + 저장 버튼 비활성화"
      - "'기본값으로 되돌리기' 버튼 — 1 클릭 전체 초기화"
      - "편집 UI 는 모달 또는 우측 drawer — 키보드 접근 (focus trap + ESC 닫기)"
      - "값 변경은 '저장' 버튼 클릭 후에만 차트 반영 (프리뷰 방식 아님 — 연산 폭증 방지)"
    priority: "Must"

  - id: US-D03
    as_a: "개인 투자자"
    i_want: "편집한 프리셋이 재방문해도 유지되기를"
    so_that: "매번 다시 입력하지 않아도 됨"
    acceptance_criteria:
      - "로그아웃/익명 사용자: localStorage 키 `stock-chart-indicators:v2` (JSON) — v1 발견 시 v2 로 자동 마이그레이션 (토글만 있고 파라미터는 기본값)"
      - "로그인 사용자: DB 영속화 (아래 US-D04) — localStorage 는 캐시/fallback"
      - "SSR-safe — mount 전엔 DEFAULT_PREFS 렌더, mount 후 저장값 반영 (hydration shift 없음)"
      - "스키마 검증 실패 시 default 로 fallback — v1.1 패턴 유지 (zod 대신 수동 가드 우선 고려)"
    priority: "Must"

  - id: US-D04
    as_a: "(싱글 오퍼레이터) 개인 투자자"
    i_want: "내 프리셋이 DB 에 저장되어 다른 기기에서도 동일하게 보이기를"
    so_that: "PC/모바일/태블릿 간 설정 재입력 불필요"
    acceptance_criteria:
      - "본 서비스는 카카오 OAuth 미구현 상태 — 인증은 기존 `X-API-Key` (ADMIN_API_KEY) 어드민 키 단일 체계"
      - "따라서 **NotificationPreference 싱글톤 패턴 (id=1) 상속** — 테이블 `indicator_preferences` 단일 로우 운용"
      - "FE 는 Next.js Route Handler (`/api/admin/indicator-preferences`) 로 서버 릴레이 — ADMIN_API_KEY 는 서버 env 에서만 주입 (v1.0 `/api/admin/notifications/preferences` 패턴 재사용)"
      - "저장 트리거: 편집 UI '저장' 또는 토글 on/off 변경"
      - "낙관적 UI — 로컬 즉시 반영 + 백그라운드 PUT — 실패 시 토스트 + rollback"
      - "앱 진입 시 DB 값 pull → localStorage 동기화 — 서버가 source of truth (DB 값 부재 시 localStorage → DB 1 회 푸시 + 이후 서버 권위)"
    priority: "Must"

  - id: US-D05
    as_a: "개인 투자자"
    i_want: "서버 저장 실패나 응답 지연 시 명확한 피드백을 받기를"
    so_that: "내 변경이 반영됐는지 혼란 없음"
    acceptance_criteria:
      - "PUT 200: 토스트 생략 또는 '저장됨' 200ms 플래시 (과한 방해 금지)"
      - "PUT 4xx (검증 실패): '입력값이 유효하지 않습니다' + 편집 UI 재오픈"
      - "PUT 5xx / 네트워크: '서버에 저장하지 못했습니다. 다음 접속 때 다시 시도됩니다' + 로컬 dirty 플래그로 다음 기회에 재시도"
      - "요청 timeout 5 s"
    priority: "Should"

  - id: US-D06
    as_a: "개발자 (본인)"
    i_want: "FE 지표 유틸과 preferences 훅에 Vitest 단위/컴포넌트 테스트가 있기를"
    so_that: "리팩터링/스키마 변경 시 회귀를 CI 가 막아줌"
    acceptance_criteria:
      - "Vitest 설정: `vitest.config.ts` + jsdom 환경 + `src/test-setup.ts`"
      - "`src/lib/indicators/*.ts` 단위 테스트 — sma/rsi/macd/bb/aggregate 각 파일 + index barrel 포함"
      - "`src/lib/hooks/useIndicatorPreferences.ts` 테스트 — v1→v2 마이그레이션, SSR fallback, invalid schema fallback, multi-subscriber 동기화"
      - "`src/components/charts/IndicatorTogglePanel.tsx` + 파라미터 편집 컴포넌트 — 키보드/접근성/validation 시나리오"
      - "MSW 로 BE 프리셋 API mock — `GET/PUT /api/indicator-preferences` 성공/실패 시나리오"
      - "`package.json` scripts: `test`, `test:ci` (coverage 임계 설정)"
    priority: "Must"

  - id: US-D07
    as_a: "개발자 (본인)"
    i_want: "Vitest 가 CI 에서 자동 실행되기를"
    so_that: "PR 머지 전 테스트 실패가 차단됨"
    acceptance_criteria:
      - ".github/workflows/ci.yml 에 FE 테스트 job 추가 (backend job 이후 병렬 또는 후속)"
      - "coverage 리포트 artifact 업로드 (lcov)"
      - "커버리지 임계 미달 시 fail — `src/lib/indicators/` >=90%, `src/lib/hooks/useIndicatorPreferences.ts` 100%"
    priority: "Should"

  - id: US-D08
    as_a: "스크린리더 사용자"
    i_want: "편집 UI 와 BB 지표가 v1.1 의 접근성 수준을 유지하기를"
    so_that: "파라미터 편집과 BB 정보가 시각 의존 없이 이용 가능"
    acceptance_criteria:
      - "편집 UI 모달/drawer: 포커스 트랩 + aria-modal + role='dialog' + 제목 aria-labelledby"
      - "입력 필드: label 연결, 에러는 aria-describedby"
      - "BB 활성 시 sr-only 테이블 열에 BB upper/middle/lower 추가"
      - "A11y 100 유지 (Lighthouse `/stocks/005930`)"
    priority: "Must"

  - id: US-D09
    as_a: "개인 투자자"
    i_want: "v1.1 localStorage:v1 데이터가 v1.2 에서도 깨지지 않고 복원되기를"
    so_that: "업그레이드 체감 마찰이 없음"
    acceptance_criteria:
      - "`stock-chart-indicators:v1` 발견 시 v2 스키마로 합성 (토글값 + 기본 파라미터) — 1 회성"
      - "합성 후 v1 키 제거 (또는 유지하되 v2 가 우선 read)"
      - "v2 스키마 검증 실패 시 v1.1 과 동일하게 DEFAULT_PREFS fallback"
    priority: "Must"

  - id: US-D10
    as_a: "개인 투자자"
    i_want: "편집한 파라미터가 잘못된 값(예: MACD slow <= fast)이면 저장이 막히기를"
    so_that: "차트가 NaN 또는 빈 pane 으로 깨지지 않음"
    acceptance_criteria:
      - "프론트 검증 (서버 사전 차단)"
      - "BE 도 동일 검증 반복 (방어적) — 400 + 사유 반환"
      - "검증 룰: MA window >= 2, RSI period >= 2, MACD fast < slow, signal >= 2, BB period >= 2, BB k > 0"
    priority: "Must"

  - id: US-D11
    as_a: "개인 투자자"
    i_want: "파라미터 변경 시 차트 리렌더가 부드럽기를 (지표 페인 전부 재생성 금지)"
    so_that: "탐색 흐름이 끊기지 않음"
    acceptance_criteria:
      - "파라미터 변경 시 기존 LineSeries `.setData()` 로 재계산 값만 푸시 (series add/remove 지양)"
      - "토글 OFF → ON 전환은 pane + series add (기존 패턴 유지)"
      - "파라미터 변경 연산 < 16ms (60fps 1 frame) 기준 — 500 포인트 SMA window=240 기준"
    priority: "Should"

  - id: US-D12
    as_a: "개인 투자자"
    i_want: "Bollinger Bands 활성 시 OHLCV 툴팁에도 BB upper/middle/lower 가 노출되기를"
    so_that: "hover 한 시점의 BB 수치 정확 추출"
    acceptance_criteria:
      - "CrosshairMove 이벤트 시 BB 3 값 툴팁에 표시 (활성 상태만)"
      - "결측 구간(period 미만) 은 `-`"
    priority: "Should"

functional_requirements:
  - id: FR-D01
    description: "`lib/indicators/bb.ts` — Bollinger Bands(period, k) SMA + 표본 표준편차 기반 O(n) 슬라이딩 윈도우 계산"
    related_user_stories: [US-D01]
  - id: FR-D02
    description: "`PriceAreaChart.tsx` BB 오버레이 3 LineSeries + 상-하 반투명 영역 (AreaSeries 또는 band 시리즈)"
    related_user_stories: [US-D01]
  - id: FR-D03
    description: "`IndicatorParametersDrawer.tsx` (또는 Modal) — MA/RSI/MACD/BB 파라미터 편집 폼 (검증 + 기본값 리셋)"
    related_user_stories: [US-D02, US-D10]
  - id: FR-D04
    description: "`useIndicatorPreferences` v2 스키마 확장 — 토글 + 파라미터. v1 → v2 자동 마이그레이션. localStorage 키 `stock-chart-indicators:v2`"
    related_user_stories: [US-D03, US-D09]
  - id: FR-D05
    description: "BE 엔드포인트: `GET /api/indicator-preferences` / `PUT /api/indicator-preferences` — `X-API-Key` (require_admin_key) 의존성 + Pydantic 검증. FE 는 Next.js Route Handler `/api/admin/indicator-preferences` 로 릴레이 (v1.0 notifications 패턴 재사용)"
    related_user_stories: [US-D04, US-D05, US-D10]
  - id: FR-D06
    description: "DB 테이블 `indicator_preferences` — **싱글톤 (id=1) 패턴** (NotificationPreference 상속). 컬럼: `id BIGINT PK`, `payload JSONB NOT NULL`, `updated_at TIMESTAMPTZ`. Alembic 009 마이그레이션에 `INSERT ... VALUES (1) ON CONFLICT DO NOTHING` 포함"
    related_user_stories: [US-D04]
  - id: FR-D07
    description: "`useIndicatorPreferences` DB 동기화 어댑터 — mount 시 pull, 변경 시 PUT (낙관적 + retry), 실패 시 dirty flag + localStorage 보존. DB 부재 시 localStorage → DB 1 회 bootstrap"
    related_user_stories: [US-D04, US-D05]
  - id: FR-D08
    description: "Vitest 하네스 — `vitest.config.ts` + jsdom + `src/test-setup.ts` + `@testing-library/*` + MSW 설치"
    related_user_stories: [US-D06]
  - id: FR-D09
    description: "Indicators 단위 테스트 — sma/rsi/macd/bb/aggregate 각 happy path + edge case(결측/경계값/길이 미달)"
    related_user_stories: [US-D06]
  - id: FR-D10
    description: "`useIndicatorPreferences` 테스트 — v1→v2 마이그레이션, SSR fallback, invalid JSON, 다중 subscriber"
    related_user_stories: [US-D06]
  - id: FR-D11
    description: "컴포넌트 테스트 — IndicatorTogglePanel + IndicatorParametersDrawer (폼 검증, 접근성, 키보드 네비)"
    related_user_stories: [US-D06, US-D08]
  - id: FR-D12
    description: "MSW mock — GET/PUT indicator-preferences (200/400/500/network-fail)"
    related_user_stories: [US-D06]
  - id: FR-D13
    description: "CI 통합 — `.github/workflows/ci.yml` FE vitest job + coverage lcov artifact"
    related_user_stories: [US-D07]
  - id: FR-D14
    description: "OHLCV 툴팁에 BB 값 추가 (활성 시)"
    related_user_stories: [US-D12]
  - id: FR-D15
    description: "sr-only 테이블에 BB 열 추가 (활성 시)"
    related_user_stories: [US-D08]
  - id: FR-D16
    description: "파라미터 변경 시 series `.setData()` 재계산만 수행 — series 재생성 최소화"
    related_user_stories: [US-D11]

non_functional_requirements:
  - id: NFR-D01
    category: "Performance"
    target_metric: "`/stocks/005930` Lighthouse Perf 80 이상 유지 (v1.1 마감 기준). BB/편집 UI 추가로 80 미만 하락 금지"
  - id: NFR-D02
    category: "Performance"
    target_metric: "first-load JS 순증 ≤ 15KB gzipped (BB 유틸 ~1KB + 편집 UI ~6KB + preferences v2 변환 ~0.5KB — 가량)"
  - id: NFR-D03
    category: "Performance"
    target_metric: "파라미터 변경 반영 <= 16ms (500 포인트 × 지표 재계산, window=240 기준 벤치마크)"
  - id: NFR-D04
    category: "Accessibility"
    target_metric: "Lighthouse A11y 100 유지. 편집 UI focus trap + ESC + aria-modal 구현"
  - id: NFR-D05
    category: "Reliability"
    target_metric: "BE 저장 실패 시 localStorage fallback + dirty flag 재시도 — 데이터 유실 0건"
  - id: NFR-D06
    category: "Security"
    target_metric: "GET/PUT indicator-preferences 비로그인 요청은 401. JSON 페이로드 Pydantic 검증, 악성 값 400"
  - id: NFR-D07
    category: "Security"
    target_metric: "localStorage JSON v2 스키마 수동 가드 — 악성/변조값은 DEFAULT_PREFS fallback (v1.1 패턴)"
  - id: NFR-D08
    category: "Testability"
    target_metric: "Vitest 커버리지 — `src/lib/indicators/` ≥ 90% lines/branches, `useIndicatorPreferences.ts` 100%"
  - id: NFR-D09
    category: "Scalability"
    target_metric: "파라미터 추가 시 스키마 변경 한 곳 (`indicator-preferences.schema.ts` or zod) + 편집 UI 필드 추가만 — 차트 컴포넌트 변경 최소 (<30 줄)"
  - id: NFR-D10
    category: "Observability"
    target_metric: "BE PUT indicator-preferences structlog JSON 로그 (user_id 마스킹) — 저장/실패 카운트 추적 가능"

risks:
  - id: RISK-D01
    impact: "Low"
    description: "(당초 '카카오 OAuth 세션 의존' 리스크로 분석되었으나 2026-04-24 실스택 점검으로 **기각됨** — 본 서비스는 싱글 오퍼레이터 + X-API-Key 어드민 인증 모델, NotificationPreference id=1 싱글톤 패턴이 이미 정립됨) 잔여 리스크: 여러 오퍼레이터가 동일 키로 동시 저장 시 last-writer-wins 혼동"
    mitigation: "(1) 싱글 오퍼레이터 전제를 README/HANDOFF 에 명시 (2) updated_at 응답에 포함 → FE 가 로컬 stale 감지 시 경고 (v1.3 선택)"

  - id: RISK-D02
    impact: "Medium"
    description: "localStorage v1 → v2 스키마 마이그레이션 실패로 기존 사용자 토글 상태 유실"
    mitigation: "(1) 마이그레이션 함수 Vitest 로 v1 샘플 10+ 케이스 검증 (2) v1 키는 마이그레이션 1 주 후 삭제 — 중간 기간 v1 존속"

  - id: RISK-D03
    impact: "Medium"
    description: "파라미터 조합 매트릭스 폭증 — MA 4 × window × RSI × MACD(f,s,sig) × BB(p,k) = 수많은 NaN 유발 경계 케이스"
    mitigation: "(1) BE + FE 이중 검증 (US-D10) (2) Vitest 에 경계값 케이스 (window=2, window=데이터길이, fast=slow-1 등) 추가 (3) 지표 유틸이 NaN 을 invalidTime 으로 매핑하는 로직 유지"

  - id: RISK-D04
    impact: "Low"
    description: "Vitest 도입 시 Next 16 / React 19 호환성 — 최신 버전 호환 이슈 가능"
    mitigation: "(1) `vitest@^2` + `@vitejs/plugin-react@^4` + `jsdom@^25` 공식 추천 버전 사용 (2) `@testing-library/react@^16` (React 19 대응 릴리스 확인)"

  - id: RISK-D05
    impact: "Low"
    description: "파라미터 편집 UI 의 UX 복잡성 — 밀집 폼으로 모바일 사용성 하락"
    mitigation: "(1) drawer 형 (모바일) + modal (데스크탑) 반응형 (2) 각 지표 섹션 collapsible — 한 번에 한 섹션만 편집 (3) 기본값 복원 1 클릭 항상 제공"

  - id: RISK-D06
    impact: "-"
    description: "(사전 점검으로 **기각됨** — 2026-04-24 실스택 조사 결과 users/kakao_users 테이블 부재, 인증은 X-API-Key 어드민 키 단일 체계. NotificationPreference(id=1) 싱글톤 패턴이 정립된 선례. indicator_preferences 도 동일 패턴 채택으로 FK 불요)"
    mitigation: "이행 — FR-D06 에 싱글톤 (id=1) 패턴 명시."

  - id: RISK-D07
    impact: "Low"
    description: "CI 에 Vitest 추가 시 빌드 시간 증가 (초기 설치 + 런타임)"
    mitigation: "(1) FE 테스트 job 을 백엔드 job 과 병렬 (2) coverage 는 PR 머지 전에만 실행 (dev branch 는 스킵 옵션)"

mvp_scope:
  included:
    - "Bollinger Bands 유틸 + 가격 페인 overlay + 토글 (FR-D01, FR-D02)"
    - "지표 파라미터 편집 UI (FR-D03)"
    - "useIndicatorPreferences v2 스키마 + v1→v2 마이그레이션 (FR-D04)"
    - "DB 영속화 엔드포인트 + 테이블 + 마이그레이션 009 (FR-D05, FR-D06)"
    - "DB 동기화 훅 어댑터 (낙관적 + 실패 rollback) (FR-D07)"
    - "Vitest + RTL + MSW 하네스 (FR-D08)"
    - "Indicators 유틸 단위 테스트 (FR-D09)"
    - "useIndicatorPreferences 훅 테스트 (FR-D10)"
    - "컴포넌트 테스트 (FR-D11)"
    - "MSW mock (FR-D12)"
    - "CI FE 테스트 job (FR-D13)"
    - "BB 툴팁 + sr-only 테이블 반영 (FR-D14, FR-D15)"
    - "series.setData() 최적화 (FR-D16)"
  deferred:
    - "명명 프리셋 저장/공유 (swing_trader/day_trader 템플릿, v1.3)"
    - "지표 기반 알림 확장 (RSI 70 돌파, MACD 골든크로스) (v1.3)"
    - "Stochastic / ATR / ADX 등 2 차 지표 (v1.3+)"
    - "Web Worker 지표 계산 오프로드 (v1.2 조건부 — RISK-C03 모니터링 결과)"
    - "Playwright E2E for 편집 UI (v1.3, Vitest 로 먼저 충분)"

benchmarks:
  - name: "TradingView 웹 지표 설정"
    references: "지표별 gear 아이콘 → 모달. period/length 입력. 변경 시 즉시 적용(v1.2는 저장 버튼 방식 선택)"
  - name: "네이버 증권 모바일 차트"
    references: "지표 on/off + 일부 period 편집. 본인 프리셋은 로그인 시 유지"
  - name: "Webull 차트"
    references: "Bollinger Bands 기본값 (20, 2). 상하 반투명 영역 채움 관례"
  - name: "Vitest + React Testing Library 공식 예제"
    references: "https://vitest.dev/guide/ — jsdom + @vitejs/plugin-react + coverage v8"
  - name: "MSW 공식 가이드"
    references: "https://mswjs.io/docs/ — Node (test) + Browser(dev) 이원. test 에서는 setupServer"
```

## 체크리스트 (biz-analyst self-audit)
- [x] 요구사항 모호 부분 가정 명시 (편집 UX 방식 저장 버튼, BB 색 팔레트, v1→v2 마이그레이션 1 주 유지)
- [x] 경쟁 서비스 3+ 벤치마킹 (TradingView/네이버/Webull) + 테스트 참조 (Vitest/MSW)
- [x] NFR 측정 가능 수치 (Perf 80, JS 15KB, 커버리지 90/100%, 파라미터 변경 16ms)
- [x] 사용자 스토리 10+ (12 개)
- [x] FR-US 매핑 (16 × FR 모두 연결)
- [x] MVP 4-6 주 내 런칭 가능 범위 (Sprint 1 스프린트, 5 체크포인트 ≈ 2 주 예상)
- [x] v1.0/v1.1 제약/도메인 상속 명시
- [x] **체크포인트 0 Vitest 선행** 명시 — 후속 구현의 회귀 안전망
- [x] v1.2 스코프가 v1.1 deferred 및 로드맵과 1:1 정합
