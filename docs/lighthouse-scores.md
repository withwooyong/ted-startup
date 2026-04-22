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
