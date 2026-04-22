# 모바일 반응형 개선 작업계획서

> **작성일**: 2026-04-20
> **최종 수정**: 2026-04-21 (Next.js 16 이전 · PR #12·#15·#16 이후 페이지 재진단 반영)
> **대상**: `src/frontend` (**Next.js 16.2.4** + React 19.2.4 + Tailwind v4)
> **브랜치**: `feature/mobile-responsive` (예정)
> **참고**: 토스 디자인 컨벤션, `docs/design/ai-agent-team-master.md`
> **상태**: 미착수 — Phase A 전

---

## 1. 결론: 가능한가?

**가능**하며, 대규모 리아키텍처 없이 증분 개선으로 끝낼 수 있다.
- 기반 스택이 이미 모바일-친화적: Tailwind v4 (mobile-first), Next.js App Router, `sm:/md:/lg:` 브레이크포인트가 전반적으로 일부 적용되어 있음
- 뷰포트 메타, 네비게이션 햄버거, 대시보드/백테스트/종목상세는 이미 일부 반응형 처리됨
- **2026-04-21 재진단**: 문서 작성 이후 머지된 PR (`#12` 엑셀 import · `#15` 실계정 등록 UI · `#16` 연결 테스트 버튼) 로 신규 UI 표면이 추가됨 → 수정 대상이 3 → **5군데**로 확장

---

## 2. 현황 진단 (What's responsive, what's broken)

### 이미 잘 되어 있는 부분
| 위치 | 상태 |
|---|---|
| `NavHeader.tsx` | 햄버거 드로어 + ESC 닫기 + route 변경 자동 닫기 완비 |
| `app/page.tsx` (대시보드) | `grid-cols-2 sm:grid-cols-4` 메트릭, 필터 `overflow-x-auto`, `SignalCard` `grid-cols-[40px_1fr_auto]` |
| `app/backtest/page.tsx` | 데스크톱 `<table>` + 모바일 `<ul>` 카드 이중 렌더링 (`hidden sm:block` / `sm:hidden`) — **참조 모델** |
| `app/stocks/[code]/page.tsx` | 헤더 카드 `grid-cols-1 sm:grid-cols-2`, 차트 ResponsiveContainer |
| `app/settings/page.tsx` | `max-w-3xl`, 스위치 UI가 세로 스택으로 자연스럽게 흐름 (알림 설정 본체) |
| `app/reports/[stockCode]/page.tsx` | `md:grid-cols-2` 강점/리스크 카드 |
| `ExcelImportPanel` (PR #12) | `max-w-xl` 폼 + 에러 리스트 세로 스택 — 모바일 충돌 없음 |

### 실제로 깨지는/가독성 떨어지는 부분

**🔴 P0 — 치명적**
1. **`app/portfolio/page.tsx` 보유 종목 테이블**
   - 5 컬럼(종목/수량/평단가/매입원가/리포트) HTML `<table>` 하나만 존재. 모바일 카드 대체가 **없음**.
   - `overflow-hidden` 래퍼 안에 고정 테이블 → 360~430px 화면에서 텍스트가 줄바꿈되며 종목명이 잘림
   - → 백테스트 페이지처럼 **테이블/카드 이중 렌더링**으로 전환 필요

2. **뷰포트 메타 누락**
   - `app/layout.tsx`에 `export const viewport` 없음 → iOS Safari에서 사용자 확대 허용·초기 스케일 미선언
   - → Next.js 15 권장 `export const viewport: Viewport = { width: 'device-width', initialScale: 1 }` 추가

**🟡 P1 — 중요**
3. **`app/stocks/[code]/page.tsx` 헤더 카드 내부 `grid-cols-3`**
   - 현재가/전일비/거래량 3열 고정 → 360px 이하에서 숫자 줄바꿈 발생 (`tracking-tighter` 부작용 포함, line 121·150)
   - → `grid-cols-3 gap-2` 유지하되 라벨 폰트 축소, 또는 모바일에서만 세로 스택

4. **`app/reports/[stockCode]/page.tsx` `SourceRow`**
   - `flex` + T1/T2 뱃지 + 고정폭 `w-12` 타입 + `truncate` 라벨 + 날짜 + 화살표 → 모바일에서 label이 10자 미만으로 잘림
   - → 모바일에서 메타 행(T1 · 타입 · 날짜)을 라벨 아래로 **2줄 레이아웃** 전환

5. **`app/portfolio/[accountId]/alignment/page.tsx` 시그널 chip wrap**
   - `flex-wrap gap-2`로 6개까지 표시 (line 189-190) → 모바일에서 카드 높이 폭발
   - → 모바일 최대 3개 + "+N개 더보기" 토글

**🆕 P1 (2026-04-21 추가) — 최근 PR 로 신규 유입된 UI**

6. **`components/features/RealAccountSection.tsx` 계좌 행 3-버튼 레이아웃** (PR #15·#16, 484줄)
   - 각 계좌 `<li>` 에 "연결 테스트(7자)" + "수정" + "삭제" 3 버튼이 `flex gap-2 shrink-0` 로 한 줄 배치
   - 계좌 별칭이 긴 경우 + actionPending 시 "연결중…(5자)" 표시 → 모바일 360px 에서 label 영역이 3~4자로 압축
   - → 모바일에서 버튼 행을 `flex-wrap` 또는 별칭 아래 2번째 줄로 이동. 또는 오버플로우 메뉴(`⋯`) 패턴
   - 추가 이슈: 폼 펼침(`showForm`) 시 `<input type="password">` 4개 세로 스택은 이미 반응형 OK

7. **`app/portfolio/page.tsx` KIS sync 버튼 라벨 확장** (PR #16)
   - connection_type 분기 라벨 "**KIS 실계좌 동기화**"(8자) / "**KIS 모의 동기화**"(7자) — 기존 "모의 동기화"(5자) 대비 길이 증가
   - 우측 "시그널 정합도" 링크와 "스냅샷 생성" 버튼 함께 있어 모바일 action 영역이 `flex-wrap` 으로 2줄 → 3줄로 늘어남 (line 247-283 주변)
   - → 모바일에서 라벨을 짧게 ("실계좌 sync" / "모의 sync"), 또는 아이콘(`⟳`) + 툴팁 패턴
   - 부가 검증: Portfolio 페이지 sync 404 분기 배너(PR #16) 가 모바일에서 1~2줄에 수납되는지

**🟢 P2 — 개선 여지**
8. **터치 타깃 크기**
   - Dashboard 필터 버튼 `py-1.5`(~30px), 정렬 select `py-1.5` → iOS HIG 44px, Material 48px 미달
   - 네비 링크도 `py-1.5` → 햄버거 드로어는 `py-3`로 OK
   - → 모바일에서만 `py-2.5`로 상향 또는 `min-h-[44px]`

9. **차트 `aspect={2.2}` / `aspect={2}`**
   - 모바일 375px 기준 높이 ~170px. XAxis 틱이 겹침.
   - → 모바일 `aspect={1.4}`로 분기 (recharts는 `aspect` prop 고정이라 wrapper 분기 필요)

10. **`globals.css` aurora blob `filter: blur(90px)`**
    - 저사양 모바일에서 프레임 드롭 — `prefers-reduced-motion` 외에 모바일 뷰포트 감지 후 blur 축소 검토

### ⚠️ 재평가 — 문서 claim 과 실제 코드 괴리
- **푸터 면책 고지** (원문 §2 item 7, P2): 실제 `app/layout.tsx` line 39-41 은 **3줄 짧은 문장**. "6~7줄로 늘어남" claim 은 과장. 모바일에서 경미한 래핑 수준이라 `<details>` 접기 필요성 낮음 → **D2 항목 스킵 또는 옵션화**.

### 사전 검증 안 된 부분
- **E2E 모바일 프로필 없음**: `playwright.config.ts`에 `Desktop Chrome` 하나만 (확인 완료). `devices['iPhone 13']` + `devices['Galaxy S8']` 추가해 회귀 방지 필요
- **RealAccountSection E2E 부재**: PR #15·#16 의 "연결 테스트" / "수정" / "삭제" 플로우가 모바일에서 어떻게 렌더되는지 회귀 테스트 미존재

---

## 3. 브레이크포인트 정책 (제안)

Tailwind v4 기본을 준수하되 프로젝트 컨벤션 명시화:

| 별칭 | 크기 | 대표 장치 | 용도 |
|---|---|---|---|
| (default) | ~639px | iPhone SE/13 | **모바일 우선** (기본 스타일) |
| `sm:` | ≥640px | 큰 폰/접이식 | 2열 그리드, 인라인 라벨 복원 |
| `md:` | ≥768px | 태블릿 세로 | 사이드 여백 확장, 2열 본문 |
| `lg:` | ≥1024px | 태블릿 가로/노트북 | 데스크톱 테이블, 대시보드 2열 카드 |

**주석 원칙**: 클래스는 모바일 → 큰 화면 순 (`px-4 sm:px-5`), 절대 역순 금지.

---

## 4. 작업 항목 (Work Breakdown)

### Phase A: 기반 (0.5일)
- [ ] **A1.** `app/layout.tsx`에 `export const viewport` 추가 (`width: 'device-width', initialScale: 1, maximumScale: 5`) — 접근성 위해 확대 허용 유지
- [ ] **A2.** `playwright.config.ts`에 `'Mobile Safari' (iPhone 13)` 프로젝트 추가
- [ ] **A3.** 기존 E2E 스모크를 모바일 프로필에서도 돌려 기준선 기록

### Phase B: P0 페이지 (1일 → 1.5일로 상향, B3 추가)
- [ ] **B1.** `app/portfolio/page.tsx`
  - 현재 `<table>` 유지하되 `hidden sm:block` 으로 감싸기 (line 329-394)
  - 모바일용 `<ul className="sm:hidden space-y-3">` 카드 리스트 추가 (백테스트 페이지 패턴 재사용)
  - 카드 항목: 종목명(+코드) · 수량/평단/매입원가 3×1 그리드 · AI 리포트 링크
  - `data-testid="holding-row"` 를 테이블 `<tr>` + 카드 `<li>` 양쪽에 부여 — E2E 셀렉터 공통화
- [ ] **B2.** NavHeader 로고 오른쪽의 버전 배지 `v1.0` 모바일 숨김 (`hidden sm:inline`) — 로고 스페이스 확보
- [ ] **B3. 🆕** `components/features/RealAccountSection.tsx` 계좌 행 3-버튼 모바일 레이아웃
  - 모바일 (`default`) 에서 버튼 행을 별칭·masked view 아래로 이동: `flex-col sm:flex-row sm:items-center`
  - 또는 "수정" + "삭제" 를 "⋯" 오버플로우 메뉴로 묶고 "연결 테스트" 만 primary action 노출
  - `actionPending === account.id` 시 "연결중…" 라벨이 다른 계좌 disabled 원인 표시로 보이도록 `aria-disabled` + 별칭 옆 스피너 뱃지 (선택)

### Phase C: P1 가독성 (1일 → 1.5일로 상향, C4 추가)
- [ ] **C1.** `app/stocks/[code]/page.tsx` 헤더 카드 `grid-cols-3` → 모바일 라벨 `text-[0.6rem]`, 숫자 `text-lg`로 다운사이즈. 현재 `tracking-tighter` 제거
- [ ] **C2.** `app/reports/[stockCode]/page.tsx` `SourceRow` 모바일에서 2줄 레이아웃 (`flex-col sm:flex-row`, 메타 행 분리)
- [ ] **C3.** `app/portfolio/[accountId]/alignment/page.tsx` 시그널 chip 모바일 3개 제한 + "+N" 배지
- [ ] **C4. 🆕** `app/portfolio/page.tsx` sync 버튼 모바일 라벨 단축
  - `sm:hidden` "실계좌 sync" / "모의 sync" + `hidden sm:inline` "KIS 실계좌 동기화" / "KIS 모의 동기화"
  - 또는 모바일에서 action 영역 자체를 세로 스택 (`flex-col gap-2 sm:flex-row`) — 스냅샷/sync/정합도 3개가 wrap 폭발하는 문제 근본 해결

### Phase D: P2 마감 (0.5일 → 0.3일로 하향, D2 스킵)
- [ ] **D1.** 필터/정렬 버튼 및 select `min-h-[44px]` (모바일만) 적용
- [x] ~~**D2.** `app/layout.tsx` 푸터 면책 고지를 `<details>`로 전환~~ **스킵**: 실제 3줄 짧은 문구 (§2 재평가 참조). 여유 생기면 재검토.
- [ ] **D3.** 차트 컴포넌트에 `useMediaQuery('(max-width: 639px)')` hook으로 `aspect` 분기 (신규 `src/lib/hooks/useMediaQuery.ts` 추가)
- [ ] **D4.** aurora blob `@media (max-width: 639px) { filter: blur(50px); }` — 가볍게

### Phase E: 검증 (0.5일 → 0.75일로 상향, 신규 페이지 대상 추가)
- [x] **E1.** Playwright 모바일 프로필로 각 페이지 스크린샷 회귀 — `src/frontend/tests/e2e/mobile.spec.ts` (2026-04-22)
  - 대시보드/포트폴리오/종목상세/AI 리포트/정합도/백테스트/설정 7페이지 스모크 + screenshot 수집
  - B1 카드 분기, B2 v1.0 배지, B3 RealAccountSection 세로 배치, C3 +N 배지, C4 sync 단축 라벨, D1 44px 터치 타깃, D3 차트 aspect 모두 assert
  - 기존 desktop-only 스펙 (`holdings.spec.ts`, `actions.spec.ts`) 는 `project.name !== 'chromium'` 조건으로 스킵
  - PortfolioPage.ts → `data-testid="holding-row"` + kisSyncButton regex 확장 (`/KIS 모의 동기화|모의 sync|KIS 실계좌 동기화|실계좌 sync/`)
- [ ] **E2.** Lighthouse 모바일 스코어 (Performance/Accessibility/Best Practices) 전/후 비교, 85 이상 목표 — **수동 검증 가이드** §10 참조. 자동화(lhci)는 별도 과제로 이관.
- [ ] **E3.** 실기기 점검 체크리스트: iPhone SE(375×667), iPhone 13(390×844), Galaxy S8(360×740), iPad mini(768×1024)

---

## 5. 수정 예정 파일 (상세)

| 파일 | Phase | 예상 diff |
|---|---|---|
| `src/frontend/src/app/layout.tsx` | A1 | +5 / -0 (viewport export 만. D2 스킵으로 푸터 손 안 댐) |
| `src/frontend/playwright.config.ts` | A2 | +12 (iPhone 13 + Galaxy S8 2개 프로필) |
| `src/frontend/src/app/portfolio/page.tsx` | B1, C4 | +65 / -5 (카드 리스트 추가 + sync 라벨 분기) |
| `src/frontend/src/components/NavHeader.tsx` | B2 | +1 / -1 |
| 🆕 `src/frontend/src/components/features/RealAccountSection.tsx` | B3 | +15 / -10 (버튼 행 레이아웃 + `aria-disabled`) |
| `src/frontend/src/app/stocks/[code]/page.tsx` | C1, D3 | +12 / -6 |
| `src/frontend/src/app/reports/[stockCode]/page.tsx` | C2 | +15 / -8 |
| `src/frontend/src/app/portfolio/[accountId]/alignment/page.tsx` | C3 | +10 / -2 |
| `src/frontend/src/app/page.tsx` | D1 | +3 / -3 |
| `src/frontend/src/app/backtest/page.tsx` | D3 | +5 / -2 |
| `src/frontend/src/app/globals.css` | D4 | +4 |
| 🆕 `src/frontend/src/lib/hooks/useMediaQuery.ts` | D3 | +20 (신규) |
| 🆕 `src/frontend/tests/e2e/mobile.spec.ts` | E1 | +120 (신규, RealAccountSection 시나리오 포함) |

**총 예상 작업량**: 3.5~4 man-day (개발 2.75~3일 + 검증 0.75~1일)
  - 원안 대비 +0.5일: B3 RealAccountSection + C4 sync 라벨 + E1 신규 페이지 스크린샷 분량

---

## 6. 위험 요소 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| recharts가 resize 시 react 재렌더 폭증 | 모바일에서 버벅임 | `ResponsiveContainer debounce` 옵션, `React.memo` 감싸기 |
| 뷰포트 메타 추가 후 시각적 줌이 깨짐 | iOS 기존 동작 변경 | `maximumScale: 5` 유지해 확대 접근성 확보 |
| 테이블 → 카드 전환 시 E2E 셀렉터 깨짐 | CI 실패 | `data-testid="holding-row"` 를 테이블/카드 양쪽에 공통 부여 |
| SSR 단계 `useMediaQuery`가 hydration mismatch 유발 | 콘솔 경고 | 초기값 `false` 고정 + `useEffect` 후 업데이트, 또는 CSS 분기로 대체 |

---

## 7. Out of Scope

- 다크모드/라이트모드 토글 (현재는 다크 전용 `<html className="dark">`)
- PWA 전환 (manifest/service worker) — 별도 스프린트
- 앱(React Native) 네이티브 트랜지션
- 관리자 API 전용 화면
- KIS 자격증명 등록 폼 UX 재설계 (`window.prompt` → 인라인 모달) — PR #15·#16 리뷰 이월 이슈, UX 폴리싱 스프린트로 분리

---

## 8. 체크포인트 & 승인

- **Gate 1**: Phase A 완료 후 뷰포트 메타 + 모바일 E2E 프로필 동작 확인 → 사용자 승인
- **Gate 2**: Phase B 완료 후 포트폴리오 페이지 + RealAccountSection 모바일 스크린샷 공유 → 사용자 승인
- **Gate 3**: Phase E 완료 후 Lighthouse 스코어 + 모든 페이지 스크린샷 → 최종 머지

---

## 9. 변경 이력

| 날짜 | 변경 | 이유 |
|---|---|---|
| 2026-04-20 | 최초 작성 (Phase A~E, 수정 파일 11개, 3~3.5 man-day) | — |
| 2026-04-21 | 현행화: Next.js 15 → 16.2.4, PR #12·#15·#16 페이지 재진단 | 문서 작성 후 3개 PR 머지로 신규 UI 표면 유입 |
| 2026-04-21 | P1 item 6·7 추가 (RealAccountSection 3-버튼 · sync 라벨 확장) | KIS sync PR 후유증 |
| 2026-04-21 | D2 (푸터 면책 `<details>`) 스킵 — 실제 3줄 짧은 문구 | 문서 claim vs 실제 코드 괴리 재평가 |
| 2026-04-21 | Phase B·C·E 각 0.5일 상향 → 총 3.5~4 man-day | B3 + C4 + E1 신규 시나리오 |
| 2026-04-22 | Phase B~D 구현 완료 (PR #29/#30/#31), Phase E1 mobile.spec.ts 작성 | ted-run 파이프라인 병행 |
| 2026-04-22 | §10 Lighthouse 수동 검증 가이드 추가, E2 자동화 이관 | lhci 세팅은 별도 CI 워크플로 추가 필요 |
| 2026-04-23 | `scripts/lighthouse-mobile.sh` + `docs/lighthouse-scores.md` 템플릿 추가, §10 단축 | Gate 3 증빙 인프라 완비. 실제 측정값은 사용자 로컬 기동 후 scores.md 채움 |

---

## 10. Lighthouse 모바일 검증 (E2)

**목적**: 모바일 Performance / Accessibility / Best Practices / SEO 스코어 회귀 감지. 자동화 전까지 수동 측정 + 기록.

### 결과 기록 위치
→ [`docs/lighthouse-scores.md`](./lighthouse-scores.md) (목표치, 측정 체크리스트, 결과 표 포함)

### 측정 방법 A — 자동 스크립트 (권장)
```bash
# 1) backend + frontend 기동 (별도 터미널)
cd src/backend_py && uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000
cd src/frontend && yarn build && yarn start

# 2) 7 페이지 자동 측정 (npx lighthouse, 첫 실행은 ~30s 패키지 다운로드)
./scripts/lighthouse-mobile.sh

# 3) 결과
cat lighthouse-reports/summary.md     # 4 카테고리 스코어 요약 (paste-ready)
open lighthouse-reports/root.html     # 각 페이지 상세 리포트
```

스크립트는 `lighthouse-reports/` 아래 페이지별 `.html` + `.report.json` 을 생성하고 `summary.md` 에 스코어 표를 누적한다. 로그인 세션이 필요한 페이지(portfolio/settings) 는 Chrome 쿠키 공유가 없으므로 비로그인 상태에서의 쉘 렌더만 측정됨 — 정확한 수치가 필요하면 방법 B.

### 측정 방법 B — Chrome DevTools (로그인 세션 보존)
1. Chrome 에서 `http://localhost:3000` 로그인 (seed: `e2e-manual`/`e2e-kis`)
2. DevTools → Lighthouse 탭 → Mode: Navigation / Device: **Mobile** / 4 카테고리 전체
3. 각 페이지에서 "Analyze page load"
4. 점수를 `docs/lighthouse-scores.md` 표에 기록

### 실기기 점검 (E3) 보조
DevTools Responsive 모드 외에 실기기 검증은 Chrome Remote Debugging (`chrome://inspect`) 으로 USB 연결된 Android 에서 Lighthouse 실행 가능. iOS 는 Xcode Instruments 활용.
