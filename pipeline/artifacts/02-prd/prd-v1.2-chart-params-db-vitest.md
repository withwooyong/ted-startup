---
agent: "02-pm"
stage: "02-prd"
version: "1.2.0"
iteration: "v1.2"
created_at: "2026-04-24T09:45:00+09:00"
depends_on:
  - "pipeline/artifacts/01-requirements/requirements-v1.2-chart-params-db-vitest.md"
quality_gate_passed: false
changelog:
  - version: "1.2.0"
    changes: "v1.2 BB + 파라미터 편집 UI + DB 영속화 + Vitest 하네스 PRD"
---

# PRD — v1.2 차트 파라미터 편집 + DB 영속화 + Vitest 하네스

## 1. 제품 개요

### 1.1 배경
v1.1 Sprint A/B 로 `/stocks/[code]` 차트는 증권사 앱 수준(Candle + MA + Volume + RSI + MACD + 토글 + localStorage)까지 도달. 남은 마찰 세 건:

1. **파라미터 하드코딩** — MA(5/20/60/120), RSI(14), MACD(12,26,9) 가 고정. 사용자 매매 스타일에 맞춘 튜닝 불가.
2. **브라우저 갇힘** — 설정이 `localStorage:v1` 한 곳에 저장되어 기기/브라우저 전환 시 재설정 필요.
3. **회귀 안전망 부재** — FE 에 Vitest 가 없어 지표 유틸/훅 리팩터링 시 수동 확인이 유일.

추가로 v1.1 deferred 였던 **Bollinger Bands(20, 2σ)** 를 넣어 기술적 지표 베이스라인을 완성한다.

### 1.2 목표
- **커스터마이제이션**: 지표 파라미터를 사용자가 편집 UI 로 직접 수정
- **기기간 동기화**: 편집된 프리셋을 DB 에 저장, 어느 기기든 동일하게 불러옴 (싱글 오퍼레이터 모델)
- **회귀 안전망**: Vitest + RTL + MSW 로 지표 유틸/훅/컴포넌트 단위 테스트를 CI 에 장착
- **지표 라인업 완성**: Bollinger Bands 로 변동성 분석 수단 추가
- **번들 경량 유지**: first-load JS 순증 ≤ 15KB gzipped (devDep 은 prod 영향 0)

### 1.3 Out of Scope (v1.2)
- 명명 프리셋 저장/공유 (swing_trader 등) → v1.3
- 지표 기반 알림 (RSI 70 돌파 등) → v1.3
- Stochastic / ATR / ADX 2 차 지표 → v1.3+
- Web Worker 지표 오프로드 → RISK-C03 모니터링 결과에 따라 v1.2 조건부
- E2E (Playwright) — 편집 UI 는 Vitest 로 먼저 충분, v1.3 에서 E2E 추가 고려
- 카카오 OAuth / multi-user → 현재 싱글 오퍼레이터 모델 유지, 로드맵 별 Epic

## 2. 타겟 사용자
| 페르소나 | 특징 | v1.2 가치 |
|---|---|---|
| **P1: 본인 (primary)** | v1.1 차트 유저, 파라미터 튜닝 의지 있음, 다기기(PC/모바일) 사용 | 자기 파라미터 프리셋 + 어디서나 동일 설정 |
| **P2: 본인 (developer 관점)** | 유지보수 당사자 | 리팩터링 시 CI 가 회귀 차단 — 유지보수 비용 하락 |

## 3. 기능 스펙

### 3.1 Bollinger Bands 추가
| 항목 | 사양 |
|---|---|
| 유틸 | `src/frontend/src/lib/indicators/bb.ts` — `(values, period=20, k=2)` → `{ upper, middle, lower }[]`. SMA + 표본 표준편차 기반 O(n) 슬라이딩 윈도우 |
| 차트 위치 | **가격 페인 오버레이** (RSI/MACD pane 과 구분) |
| 시리즈 | upper/middle/lower 3 × LineSeries + (선택) band 영역 채움. v5 `addAreaSeries` 로 가능하면 채움, 그래픽 자산 부족 시 3 선만 v1.2 MVP |
| 기본 색 | upper `#6FD4D4` / middle `#A8B2BF` / lower `#6FD4D4` — MA 팔레트와 충돌 회피 |
| 토글 | IndicatorTogglePanel 에 `bb` 추가. 기본 OFF |
| 파라미터 | `{ period: 20, k: 2 }`. 편집 UI 로 수정 (§3.2) |
| 툴팁 | 활성 시 OHLCV 툴팁에 BB upper/middle/lower 3 값 추가 |
| sr-only 표 | 활성 시 BB upper/middle/lower 열 추가 |

### 3.2 지표 파라미터 편집 UI
| 항목 | 사양 |
|---|---|
| 컴포넌트 | `src/frontend/src/components/charts/IndicatorParametersDrawer.tsx` |
| 진입 | IndicatorTogglePanel 의 "⚙ 지표 설정" 버튼 (차트 상단 고정) 또는 각 토글 옆 gear 아이콘 |
| 형태 | 데스크탑: 우측 Drawer (너비 380px). 모바일 (<640px): 전체 Sheet (하단 슬라이드) |
| 섹션 | MA (4 슬롯 window 입력) / RSI (period + OB/OS) / MACD (fast / slow / signal) / BB (period / k) — 각 섹션 collapsible, 기본 MA 만 펼침 |
| 저장 방식 | **버튼 클릭 후 적용** (프리뷰 아님). 이유: NFR-D03 파라미터 변경 ≤ 16ms 지키기 위해 잦은 재계산 회피 + 편집 중 차트 깜빡임 방지 |
| 검증 | 프론트 + 백엔드 이중. 프론트는 실시간 inline error, 저장 버튼 disabled |
| 검증 규칙 | MA window ∈ [2, 240] (4 슬롯 중복 허용) / RSI period ∈ [2, 60] / MACD fast ∈ [2, 50], slow ∈ [4, 100], signal ∈ [2, 50], fast < slow / BB period ∈ [5, 100], k ∈ [0.5, 4.0] |
| '기본값 복원' | 1 클릭 전체 초기화. 확인 모달 없음 (1 depth 간결) |
| 접근성 | `role="dialog"` + `aria-modal="true"` + focus trap + ESC close + 제목 aria-labelledby |

### 3.3 설정 영속화
#### 3.3.1 localStorage v2 스키마
```ts
type IndicatorPreferences = {
  schema_version: 2;
  toggles: {
    ma5: boolean; ma20: boolean; ma60: boolean; ma120: boolean;
    volume: boolean; rsi: boolean; macd: boolean; bb: boolean;
  };
  params: {
    ma: [number, number, number, number];   // 4 slots
    rsi: { period: number; overbought: number; oversold: number };
    macd: { fast: number; slow: number; signal: number };
    bb: { period: number; k: number };
  };
  dirty: boolean;          // 서버 동기화 미완 플래그 (재시도 후보)
  updated_at: string;      // ISO8601
};
```

- **키**: `stock-chart-indicators:v2`
- **v1 → v2 마이그레이션**: 앱 부팅 시 `v1` 키 발견하면 `toggles` 만 이식, `params` 는 기본값, 1 회 성공 후 v1 키 삭제
- **검증 실패 시**: DEFAULT_PREFS fallback (v1.1 `isValidPrefs` 패턴 확장)

#### 3.3.2 DB 영속화 (싱글톤 id=1)
- **테이블**: `indicator_preferences`
  ```sql
  CREATE TABLE indicator_preferences (
      id         BIGINT       PRIMARY KEY,
      payload    JSONB        NOT NULL,
      updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
  );
  INSERT INTO indicator_preferences (id, payload) VALUES (1, '{}'::jsonb) ON CONFLICT (id) DO NOTHING;
  ```
- **Alembic**: `009_indicator_preferences.py` — NotificationPreference 마이그레이션 포맷 상속
- **엔드포인트** (백엔드 `/api/indicator-preferences`)
  | 메서드 | 경로 | 설명 |
  |---|---|---|
  | GET | `/api/indicator-preferences` | 싱글톤 조회. 부재 시 기본값으로 lazy-create 후 반환 |
  | PUT | `/api/indicator-preferences` | 전체 교체 저장. 서버 Pydantic 검증 후 DB upsert. 응답에 updated_at 포함 |
- **FE 릴레이**: `src/frontend/src/app/api/admin/indicator-preferences/route.ts` (`/api/admin/notifications/preferences` 패턴 재사용)
- **auth**: `require_admin_key` (X-API-Key 헤더) — 기존 관리자 라우터 전부 동일
- **FE 훅 동기화 플로우**:
  1. Mount → localStorage 로드 → DEFAULT_PREFS 백업 렌더
  2. 동시에 GET /api/admin/indicator-preferences → 성공 시 서버 값으로 덮어씀 + localStorage 동기화
  3. 서버가 미초기화 (payload=`{}`) → 현재 localStorage 값으로 1 회 PUT bootstrap
  4. 변경 시: localStorage 즉시 업데이트 + PUT 백그라운드. 실패 시 `dirty=true` 로 표시, 다음 변경/다음 mount 재시도

### 3.4 테스트 하네스 (Vitest)
| 항목 | 사양 |
|---|---|
| 버전 | `vitest@^2`, `@vitejs/plugin-react@^4`, `@testing-library/react@^16`, `@testing-library/jest-dom@^6`, `@testing-library/user-event@^14`, `jsdom@^25`, `msw@^2` |
| 설정 | `src/frontend/vitest.config.ts` (jsdom 환경), `src/frontend/src/test-setup.ts` (jest-dom matchers) |
| scripts | `package.json` → `"test": "vitest"`, `"test:ci": "vitest run --coverage"` |
| coverage | `vitest run --coverage` (v8 provider), 임계: indicators 90%, useIndicatorPreferences 100% |
| MSW | `src/frontend/src/test/msw/handlers.ts` — GET/PUT `/api/admin/indicator-preferences` 성공/400/500/network-fail |
| 테스트 파일 | `*.test.ts` / `*.test.tsx` (소스 옆 동치 위치) |
| CI | `.github/workflows/ci.yml` FE job — `cd src/frontend && npm ci && npm run test:ci`. artifact: `coverage/lcov.info` |

### 3.5 접근성
- **편집 UI**: focus trap + ESC close + aria-modal + label 연결 + aria-describedby 에러 메시지 + aria-invalid
- **BB 활성 시**: 토글 패널 ✅ / OHLCV 툴팁 ✅ / sr-only 테이블 3 열 추가 ✅
- **Lighthouse A11y 100 유지**: `/stocks/005930` 재측정 Gate

## 4. UX 개략 (와이어프레임 설명)

```
┌──────────────────────────────────────────────────┐
│ 종목 헤더 + 시그널 스코어 + [1D][1W][1M] (v1.1 유지)   │
│ ┌── 지표 토글 + [⚙ 지표 설정] 버튼 ──────────────┐  │
│ │ ●MA5 ●MA20 ○MA60 ○MA120  ●Volume  ○RSI ○MACD │  │
│ │ ○BB  [⚙ 지표 설정]                            │  │
│ └───────────────────────────────────────────────┘  │
│                                                  │
│  ┌─ 가격 페인 ── Candle + MA + (BB upper/middle/ │
│  │                lower + band 영역) + 시그널     │
│  │                마커 ──────────────────────────┐ │
│  │                [OHLCV+BB 툴팁 ↖ 우상단]       │ │
│  └───────────────────────────────────────────────┘ │
│  ┌─ 거래량 / RSI / MACD pane (v1.1 동일)─────────┐ │
│  └───────────────────────────────────────────────┘ │
│  (sr-only table: 30일 OHLCV + MA + RSI + MACD +  │
│   BB u/m/l, 활성 지표만)                          │
└──────────────────────────────────────────────────┘

[⚙ 지표 설정] 클릭 →
┌──────────────── Drawer (데스크탑 우측, 모바일 Sheet) ────┐
│ 지표 설정                           [×] (ESC)            │
│ ──────────────────────────────────────────────────────── │
│ ▼ 이동평균 (MA)                                          │
│   MA #1  [  5] window  (2~240)                           │
│   MA #2  [ 20] window                                    │
│   MA #3  [ 60] window                                    │
│   MA #4  [120] window                                    │
│ ▶ RSI                                                    │
│ ▶ MACD                                                   │
│ ▶ Bollinger Bands                                        │
│ ──────────────────────────────────────────────────────── │
│  [기본값 복원]              [취소]  [저장]               │
└──────────────────────────────────────────────────────────┘
```

## 5. 기술 결정

### 5.1 인증 체계 — 기존 `X-API-Key` 재사용 (카카오 OAuth 는 미도입)
2026-04-24 스파이크로 확인:
- 백엔드: `require_admin_key` 의존성 (X-API-Key 헤더) 외 인증 경로 없음
- 프론트엔드: Next.js Route Handler 가 서버 env `ADMIN_API_KEY` 주입 (v1.0 `/api/admin/notifications/preferences` 선례)
- DB: users/kakao_users 테이블 부재 — 싱글 오퍼레이터 모델 확정

따라서 v1.2 는 이 모델을 상속하며, **멀티 유저 고려는 로드맵에서 별 Epic** 으로 이관.

### 5.2 DB 스키마 — NotificationPreference 싱글톤 패턴 상속
선례: `migrations/versions/002_notification_preference.py`
- PK = `1` 고정 (싱글 로우)
- `INSERT ... ON CONFLICT (id) DO NOTHING` 멱등 시드
- Repository `get_or_create()` 패턴 재사용 (`app/adapter/out/persistence/repositories/notification_preference.py:8-17`)

### 5.3 BB 유틸 — 자체 구현, O(n) 슬라이딩
- 외부 `technicalindicators` 같은 ~30-50KB 라이브러리 대신 자체 ~1KB
- SMA 합/제곱합 롤링으로 표본 표준편차 O(n)
- NaN 처리는 기존 SMA 패턴 상속 (invalidTime 매핑)

### 5.4 파라미터 편집 UX — "저장 버튼" 방식
- **채택**: 저장 버튼으로 적용 (프리뷰 방식 X)
- **근거**: NFR-D03 파라미터 변경 ≤ 16ms. 편집 중 매 키스트로크 재계산은 500 포인트 × 8 지표 = 피크 부하 불가피. 저장 버튼으로 사용자 의도 확정 후 1 회 계산.
- **UX 영향**: 단점 "즉시 반영 안됨" 존재. 대안으로 "미리보기 토글" v1.3 고려.

### 5.5 상태 관리 — useSyncExternalStore 유지 + DB 어댑터 추가
- v1.1 `useIndicatorPreferences` 의 snapshot 캐싱 패턴 유지 (React #185 방어)
- DB 어댑터는 별도 module (`preferences-sync.ts`) 로 분리 — 훅은 상태관리, 어댑터는 I/O
- TanStack Query 미도입 (v1.0 post-ship 권장이지만 v1.2 범위 밖, 직접 fetch 로 충분)

### 5.6 Vitest + React 19 호환성
- Vitest 2.x + `@testing-library/react@^16` 이 React 19 지원 (2026-04 기준 안정)
- jsdom 25 + Next 16 호환 확인 필요 — 체크포인트 0 PoC 에서 30 분 안에 검증
- MSW 2.x 는 fetch 레벨 intercept (서비스워커 불필요, 테스트 환경에서 `setupServer`)

### 5.7 CI 통합
- `.github/workflows/ci.yml` 에 FE job 추가 — backend job 과 병렬
- PR 머지 전 coverage 임계 미달 차단
- local dev 는 `npm test` (watch 모드), CI 는 `npm run test:ci` (single run + coverage)

## 6. 성공 지표 (KPI)

### 6.1 정량 (Launch criteria)
| 지표 | 기준값 | 측정 방법 |
|---|---|---|
| `/stocks/005930` Lighthouse Perf | ≥ 80 (v1.1 마감 기준 무회귀) | `./scripts/lighthouse-mobile.sh` |
| `/stocks/005930` Lighthouse A11y | = 100 | 동상 |
| first-load JS 순증 | ≤ 15KB gzipped | `npm run build` 후 `.next/static/chunks` diff |
| 파라미터 변경 반영 시간 | ≤ 16ms (500 포인트 × 지표, window=240) | DevTools Performance 탭 or `performance.now()` |
| Vitest 커버리지 (indicators) | ≥ 90% lines/branches | `vitest run --coverage` |
| Vitest 커버리지 (useIndicatorPreferences) | = 100% | 동상 |
| DB 저장 실패 시 데이터 유실 | 0 건 | 수동 시나리오 (네트워크 차단 + 재연결 테스트) |

### 6.2 정성
- 본인 2 기기(MacBook + iPhone)에서 다른 파라미터 세트로 저장 후 기기 전환 시 동일하게 복원
- MA/RSI 파라미터를 스윙 매매용 (예: MA 10/20/50/120, RSI 9) 으로 바꿔 개인 최적화 경험
- 리팩터링 도중 Vitest 가 회귀 최소 1 건 이상 포착 (체험 기준)

## 7. 리스크 & 완화 (requirements.md 에서 상속)
- RISK-D01 (Low) 멀티 오퍼레이터 last-writer-wins — README 에 명시 + v1.3 updated_at 경고 선택
- RISK-D02 (Medium) v1→v2 마이그레이션 실패 — Vitest 10+ 샘플 케이스
- RISK-D03 (Medium) 파라미터 매트릭스 폭증 NaN — 이중 검증 + 경계값 Vitest
- RISK-D04 (Low) Vitest/Next 16/React 19 호환 — 체크포인트 0 PoC 에서 30 분 검증
- RISK-D05 (Low) 편집 UI 모바일 UX — drawer/sheet 반응형 + collapsible 섹션
- RISK-D06 (기각) users 테이블 부재 — 싱글톤 id=1 패턴으로 해결
- RISK-D07 (Low) CI 빌드 시간 증가 — 병렬 job + coverage 는 PR only

## 8. 의존성 & 가정
### 8.1 의존성
- `lightweight-charts@^5.1.0` 기존 활용 (신규 API 없음)
- 신규 devDep (prod 영향 0): `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `msw`, `@vitest/coverage-v8`
- 신규 prod Dep: **0** (BB 유틸 자체 구현)
- BE 신규 라우터 1 개 (`indicator_preferences.py`), 신규 Repository 1 개, 신규 Alembic 마이그레이션 1 개

### 8.2 가정 (실스택 검증됨 2026-04-24)
- `require_admin_key` + `X-API-Key` 단일 인증 체계 — 확인
- NotificationPreference 싱글톤 패턴 (id=1) 선례 — 확인 (`migrations/versions/002`)
- Next.js Route Handler 서버 릴레이 패턴 — 확인 (`src/frontend/src/app/api/admin/notifications/preferences/route.ts`)
- `useIndicatorPreferences` snapshot 캐싱 패턴 — 유지 (v1.1 hotfix `669d9e8`)

### 8.3 영향 범위
**백엔드** (신규 / 수정):
- `migrations/versions/009_indicator_preferences.py` 신규
- `app/adapter/out/persistence/models/indicator_preferences.py` 신규
- `app/adapter/out/persistence/repositories/indicator_preferences.py` 신규
- `app/adapter/web/routers/indicator_preferences.py` 신규
- `app/adapter/web/_schemas.py` 수정 (Pydantic 스키마 추가)
- `app/main.py` 수정 (라우터 등록)
- `tests/test_indicator_preferences.py` 신규 (pytest + testcontainers)

**프론트엔드** (신규 / 수정):
- `vitest.config.ts` 신규
- `src/test-setup.ts` 신규
- `src/test/msw/handlers.ts`, `src/test/msw/server.ts` 신규
- `package.json` 수정 (devDeps + scripts)
- `src/lib/indicators/bb.ts` 신규 + `index.ts` barrel 수정
- `src/lib/indicators/*.test.ts` 신규 (sma/rsi/macd/bb/aggregate)
- `src/lib/hooks/useIndicatorPreferences.ts` **v2 스키마 확장** + DB 어댑터 + 테스트
- `src/lib/preferences-sync.ts` 신규 (DB 어댑터)
- `src/components/charts/IndicatorTogglePanel.tsx` 수정 (bb 토글 + ⚙ 버튼)
- `src/components/charts/IndicatorParametersDrawer.tsx` 신규 + 테스트
- `src/components/charts/PriceAreaChart.tsx` 수정 (BB 오버레이 + 파라미터 반영)
- `src/components/charts/StockChartAccessibilityTable.tsx` 수정 (BB 열)
- `src/app/stocks/[code]/page.tsx` 수정 (파라미터 전달)
- `src/app/api/admin/indicator-preferences/route.ts` 신규 (GET + PUT 릴레이)

**CI**:
- `.github/workflows/ci.yml` 수정 (FE vitest job 추가)
