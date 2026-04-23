# Lighthouse 모바일 스코어 기록

> **목적**: 모바일 반응형 개선(Phase B~D) 의 **Gate 3 증빙**. Performance/Accessibility/Best Practices/SEO 4 카테고리 전/후 비교로 회귀 감지.
> **관련 문서**: [`mobile-responsive-plan.md`](./mobile-responsive-plan.md) §10 (가이드), [`scripts/lighthouse-mobile.sh`](../scripts/lighthouse-mobile.sh) (자동화)

---

## 목표 스코어

| 카테고리 | 목표 | 근거 |
|---|---:|---|
| **Performance** | 85+ | aurora blur 경량화(D4) · 차트 aspect 축소(D3) 로 LCP/CLS 개선 기대. 실제 기기에서 체감 속도 확보 |
| **Accessibility** | 90+ | aria-label/aria-disabled/aria-pressed, min-h-[44px] 터치 타깃(D1), 뷰포트 메타(A1) 로 상향 |
| **Best Practices** | 90+ | HTTPS 로컬 제외 항목 감안. SSR-safe useMediaQuery(D3a) 로 콘솔 에러 0건 |
| **SEO** | 90+ | 뷰포트 메타 + 의미론적 태그 유지 |

---

## 측정 절차

### 자동 (권장) — 두 가지 모드 중 택일

**[A] dev 서버 (단순)**
```bash
# 1) backend + frontend 기동 (별도 터미널)
cd src/backend_py && uv run uvicorn src.app.main:app --port 8000
cd src/frontend && yarn build && yarn start

# 2) 전체 7 페이지 측정 (기본 BASE_URL=http://localhost:3000)
./scripts/lighthouse-mobile.sh
```

**[B] prod docker 스택 (caddy 경유, 실제 배포 구성과 동일)**
```bash
# 1) 재빌드 + 기동
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 2) self-signed HTTPS 로 측정 (스크립트가 --ignore-certificate-errors 내장)
LIGHTHOUSE_BASE_URL=https://localhost ./scripts/lighthouse-mobile.sh
```

**결과 확인 (공통)**
```bash
cat lighthouse-reports/summary.md     # paste-ready 요약
open lighthouse-reports/root.html     # 대시보드 상세
```

### 수동 (Chrome DevTools)
1. 위 1) 단계로 서버 기동
2. Chrome 에서 `http://localhost:3000` 접속 후 로그인 (seed: `e2e-manual`, `e2e-kis`)
3. DevTools → Lighthouse 탭 → Mode: Navigation / Device: **Mobile** / Categories 전체
4. 각 페이지에서 "Analyze page load" 실행 → 점수를 아래 §측정 결과에 기록

---

## 측정 결과

### Phase B~D 이후 — 2026-04-23 1차 측정 (비로그인 · prod docker 스택 · caddy 경유 HTTPS)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 비고 |
|---|---|---:|---:|---:|---:|---|
| `/` 대시보드 | 2026-04-23 | 99 | 96 | 100 | 100 | 목표 전부 통과 |
| `/portfolio` | 2026-04-23 | 94 | 97 | 100 | 100 | 비로그인 셸 측정 — 실데이터 재측정 필요(B 수동) |
| `/stocks/005930` | 2026-04-23 | ~~80~~ → **92** | 96 | 100 | 100 | CLS 0.362 → 0.123 수정 후 목표 통과 (footer 레이아웃 예약 + 차트 aspect CSS 이관) |
| `/reports/005930` | 2026-04-23 | 99 | 96 | 100 | 100 | 목표 전부 통과 |
| `/portfolio/1/alignment` | 2026-04-23 | 100 | 100 | 100 | 100 | 비로그인 셸 측정 — 실데이터 재측정 필요(B 수동) |
| `/backtest` | 2026-04-23 | 97 | 100 | 100 | 100 | 목표 전부 통과 |
| `/settings` | 2026-04-23 | 99 | 96 | 100 | 100 | 비로그인 셸 측정 — 실데이터 재측정 필요(B 수동) |

> **판정**: 7 페이지 중 **6 통과** (1차) → 후속 개선 PR 로 `/stocks/005930` Perf 92 달성, **7/7 통과**.
> **측정 환경**: macOS · `docker compose -f docker-compose.prod.yml` 재빌드 직후 · caddy self-signed HTTPS · Chrome headless · 모바일 4G throttle 기본값 · 각 페이지 1회 측정(중앙값 아님).
> **비로그인 주의**: `/portfolio`, `/settings`, `/portfolio/1/alignment` 는 로그인 미들웨어에서 로그인 리다이렉트 셸이 반환됐을 가능성. 실데이터 상태 스코어는 수동 절차(§측정 절차 B) 로 보완 필요.

### v1.1 Sprint B 완료 후 — 2026-04-23 최종 측정 (`/stocks/005930` 단일 집중)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 변화 |
|---|---|---:|---:|---:|---:|---|
| `/stocks/005930` | 2026-04-23 18:08 | 95 → **80** ↓15 | 100 → **100** | 100 | 100 | Sprint B 전체 (B0~B10 + 마커 grade 색) 투입. **A11y/BP/SEO 는 완전 무회귀**, Perf 는 aurora blob CLS 오검출로 회귀. |

> **⚠️ Perf 회귀 원인**: `div.aurora > div.blob-4` transform 애니메이션이 Chrome Lighthouse 에서 CLS culprit 으로 계상되어 CLS **0.393** (단일 소스). Sprint B 기능과 직접 관련 없음 (체크포인트 1~3 단계에서는 Perf 95→96 유지).
> **완화 시도 3 회 효과 미미**: (1) `.aurora .blob { contain: layout paint }`, (2) `.aurora { contain: layout paint }`, (3) keyframes 에서 `scale()` 제거 → 결과: 80 → 81.
> **후속 계획**: 실기기 체감 확인 후 aurora 애니메이션 정적화 여부 **별도 디자인 PR** 로 추적.
> **추가 버그픽스**: `669d9e8` — `useIndicatorPreferences.getSnapshot` 이 매 호출마다 새 객체를 반환해 React #185 무한 루프. snapshot 캐싱으로 해소 (성능 측정 이후 반영).

---

### v1.1 Sprint A 완료 후 — 2026-04-23 재측정 (`/stocks/005930` 단일 집중)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 변화 |
|---|---|---:|---:|---:|---:|---|
| `/stocks/005930` | 2026-04-23 15:58 | 95 → **95** | 100 → **100** | 100 | 100 | v1.1 Sprint A 전체 투입 (캔들 + MA 4개 + Volume pane + 줌/팬 + OHLCV 툴팁) 후에도 **완전 무회귀**. canvas 기반 lightweight-charts + FE 자체 지표 계산(O(n) 슬라이딩)의 경량성 입증. |

> **A8 회귀 검증 결과**: Sprint A 의 모든 기능 추가(차트 기능 +6, 시리즈 +5개, pane +1)가 스코어에 영향 0. first-load JS 순증 추정 <5KB (SMA 유틸 ~0.4KB + 내부 로직만, 외부 의존성 0).
> **Gate A 판정**: 3/4 자동 통과. 모바일 실기기 터치 핀치 줌/팬만 수동 확인 대기.

---

### A11y 색 대비 수정 후 — 2026-04-23 재측정 (`/stocks/005930` 단일 집중)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 변화 |
|---|---|---:|---:|---:|---:|---|
| `/stocks/005930` | 2026-04-23 14:43 | 95 → **95** | 95 → **100** | 100 | 100 | 헤더 카드 `#3D4A5C → #7A8699` 전역 교체 + 잔존 2건(중립 `#6B7A90`, active 버튼 `#FFF on #6395FF`) 스팟 수정. **color-contrast 감사 PASS**. Perf 동률, A11y +5. |

> **측정 방법**: 앞선 수정 커밋(`4e660a9`) + 잔존 2건 추가 수정 후 `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build frontend` 으로 프론트엔드 이미지만 재빌드 후 caddy self-signed HTTPS 경유 측정.
> **잔존 2건 근본 원인**: `#3D4A5C` 위반이 color-contrast 감사를 실패시키면서 같은 감사에 포함된 다른 노드(`#6B7A90` 중립값, `text-white on #6395FF`)가 감사 스코어에 이미 반영되어 있었음. `#3D4A5C` 해소 후 노출.
> **디자인 트레이드오프**: active 기간 버튼을 `text-white` → `text-[#0B0E11]` 로 invert + `font-semibold`. 7.27:1 대비 확보 + "눌린" 상태 시각 강화.

---

### TradingView 차트 전환 완료 후 — 2026-04-23 최종 측정 (recharts 완전 제거 직후)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 차트 전환 효과 |
|---|---|---:|---:|---:|---:|---|
| `/` 대시보드 | 2026-04-23 | 99 | 96 | 100 | 100 | 변화 없음 (차트 없음) |
| `/portfolio` | 2026-04-23 | 94 | 97 | 100 | 100 | 변화 없음 (차트 없음) |
| `/stocks/005930` | 2026-04-23 | 92 → **95** | 96 → 95 | 100 | 100 | TradingView Lightweight Charts (PR #39) — LCP 2557→1902ms (−25%), TBT 119→44ms (−63%). A11y −1 은 기존 헤더 색대비 |
| `/reports/005930` | 2026-04-23 | 99 | 96 | 100 | 100 | 변화 없음 (차트 없음) |
| `/portfolio/1/alignment` | 2026-04-23 | 100 | 100 | 100 | 100 | 변화 없음 (차트 없음) |
| `/backtest` | 2026-04-23 | 97 → **99** | 100 | 100 | 100 | pure SVG GroupedBarChart (PR #40) — 의존성 순증 0, 번들 경량화 |
| `/settings` | 2026-04-23 | 99 | 96 | 100 | 100 | 변화 없음 (차트 없음) |

> **Gate 3 최종 판정**: **7/7 전 페이지 통과**. `/stocks/005930` 과 `/backtest` 가 차트 교체로 추가 개선.
> **번들 효과**: `recharts@^3.8.1` 제거(~200KB gzipped) + `lightweight-charts@^5.1.0` 추가(~50KB gzipped) → **순수 감소 ~150KB gzipped 추정**. `/backtest` 는 pure SVG 라 의존성 순증 0.
> **측정 환경**: 1차와 동일 — prod docker 스택 재빌드 직후, caddy self-signed HTTPS, Chrome headless, 모바일 4G throttle.

### 측정 체크리스트
- [ ] Chrome 노트북 전원 연결 (배터리 절약 모드 영향 방지)
- [ ] 확장 프로그램 비활성화 (1Password, React DevTools 등)
- [ ] 로컬 backend 는 debug log OFF — 네트워크 throttle 정확도
- [ ] VPN/AdBlock 해제
- [ ] 각 페이지 3회 측정 후 중앙값 기록 (CPU 변동성 완화)

---

## 해결 이력 (1차 측정 미달 → 후속 개선)

### `/stocks/005930` Performance 80 → 92 (2026-04-23, 후속 PR)

**실제 원인**: TBT 가 아니라 **CLS = 0.362** (2건 shift, 모두 `footer.border-t`). 스켈레톤 높이(~448px) 가 실제 콘텐츠 높이(~550px+) 보다 작아 로드 직후 footer 가 아래로 밀림 + `useMediaQuery` 기반 차트 aspect 가 hydration 시점 재배치.

**초기 가설 반증**: recharts TBT 는 48ms 로 이미 충분히 낮았음 → dynamic import 불필요.

**수행한 변경**:
1. `useMediaQuery` 제거, 차트 aspect 를 Tailwind CSS (`aspect-[1.4/1] sm:aspect-[2/1]`) 로 이관 → hydration shift 소거
2. 세 상태(loading/error/loaded) 의 `<main>` 에 `min-h-[calc(100dvh-8rem)]` → footer 를 뷰포트 하단에 고정 → footer shift 원천 봉쇄
3. 스켈레톤을 실제 구조(back 버튼 + 2 카드 + 기간 선택기 + 차트) 에 맞춰 세분화 → 스켈레톤 ↔ 실콘텐츠 전환 시 세로 높이 변화 최소화

**측정 결과**: CLS 0.362 → 0.123 (남은 shift 1건은 헤더 카드 내부), Perf **80 → 92**.

### `/stocks/005930` Performance 92 → 95 (2026-04-23, TradingView 전환 PR #39)

recharts (`ComposedChart` + `Area` + `ReferenceDot`) → TradingView Lightweight Charts v5 (`AreaSeries` + `createSeriesMarkers` plugin) 로 교체. canvas 기반 차트라 recharts 의 SVG + React 재조정 오버헤드 제거.

- **LCP**: 2557ms → **1902ms** (Good 구간 진입)
- **TBT**: 119ms → **44ms** (−63%)
- **Speed Index**: 1128ms → **964ms**
- **A11y**: 96 → 95 (−1) — 헤더 카드 `#3d4a5c` on `#131720` 색대비 1.99 (기존 디자인 이슈, 별도 PR 추적)

### `/backtest` Performance 97 → 99 (2026-04-23, SVG 자작 PR #40)

recharts `BarChart` (시계열 전용 lightweight-charts 로 매핑 불가) → pure SVG + Tailwind 자작 `GroupedBarChart`. 의존성 순증 0.

- ResizeObserver 로 부모 픽셀 측정, niceStep y축 자동 눈금, hover 시 값 라벨 표시
- sr-only `<table>` 백업으로 SR 접근성 보장

### recharts 의존성 완전 제거 (2026-04-23, PR #41)

`npm uninstall recharts` + `src/lib/hooks/useMediaQuery.ts` dead code 제거. 번들 ~150KB gzipped 감소 추정.

### (향후) Accessibility / Best Practices 감점 발생 시 기록용 (예시)
- 색 대비: `#6B7A90` on `#131720` — WCAG AA 기준 확인 필요
- 포커스 링: `focus-visible:ring-*` 일부 버튼 누락 여부
- HTTPS: 로컬 측정시 자동 감점 (staging/prod 에서 재측정 권장)
- 콘솔 에러: backend down 상태 측정시 API 404/500 에러 누적

---

## 자동화 이관 계획 (별도 스프린트)

현 문서는 수동 측정. PR 마다 자동 측정하려면:

1. `@lhci/cli` 의존성 추가 (`yarn add -D @lhci/cli`)
2. `.lighthouserc.json` 생성 — `assertions` 로 목표치 강제:
   ```json
   {
     "ci": {
       "collect": { "url": ["http://localhost:3000/", "..."] },
       "assert": {
         "assertions": {
           "categories:performance": ["warn", { "minScore": 0.85 }],
           "categories:accessibility": ["error", { "minScore": 0.9 }],
           "categories:best-practices": ["warn", { "minScore": 0.9 }]
         }
       }
     }
   }
   ```
3. `.github/workflows/lighthouse.yml` 에서 staging 환경 대상으로 `lhci autorun` 실행
4. PR 코멘트로 회귀 리포트 자동 작성

staging 환경 (로그인 세션 시드) 이 선행 전제라 현재 scope 에서 제외.

---

## 변경 이력

| 날짜 | 변경 | 측정자 |
|---|---|---|
| 2026-04-23 | 템플릿 생성 (측정 대기) | — |
| 2026-04-23 | 1차 측정 기록 — 7페이지 중 6통과 · `/stocks/005930` Perf 80 미달 | Ted (prod docker 스택) |
| 2026-04-23 | `/stocks/005930` CLS 수정 후 Perf 92 달성 — 7/7 통과 | Ted (prod docker 스택) |
| 2026-04-23 | TradingView Lightweight Charts 전환 완료 — `/stocks/005930` 92→95, `/backtest` 97→99, recharts 의존성 제거 | Ted (prod docker 스택) |
