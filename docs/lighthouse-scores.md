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

### 자동 (권장)
```bash
# 1) backend + frontend 기동 (별도 터미널)
cd src/backend_py && uv run uvicorn src.app.main:app --port 8000
cd src/frontend && yarn build && yarn start

# 2) 전체 7 페이지 측정
./scripts/lighthouse-mobile.sh

# 3) 결과 확인
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

### Phase B~D 이후 (2026-04-23 이후 사용자 측정)

| 페이지 | 측정일 | Performance | Accessibility | Best Practices | SEO | 비고 |
|---|---|---:|---:|---:|---:|---|
| `/` 대시보드 | _TBD_ | — | — | — | — | |
| `/portfolio` | _TBD_ | — | — | — | — | |
| `/stocks/005930` | _TBD_ | — | — | — | — | |
| `/reports/005930` | _TBD_ | — | — | — | — | |
| `/portfolio/1/alignment` | _TBD_ | — | — | — | — | |
| `/backtest` | _TBD_ | — | — | — | — | |
| `/settings` | _TBD_ | — | — | — | — | |

### 측정 체크리스트
- [ ] Chrome 노트북 전원 연결 (배터리 절약 모드 영향 방지)
- [ ] 확장 프로그램 비활성화 (1Password, React DevTools 등)
- [ ] 로컬 backend 는 debug log OFF — 네트워크 throttle 정확도
- [ ] VPN/AdBlock 해제
- [ ] 각 페이지 3회 측정 후 중앙값 기록 (CPU 변동성 완화)

---

## 실패 항목 (각 카테고리별 상위 개선 여지)

_측정 후 90점 미만인 카테고리에 대해서만 기록_

### Performance 감점 요인 (예시)
- LCP: aurora 배경 최초 렌더링 - `.aurora .blob` blur(50px) 로도 합성 비용 있음
- TBT: recharts 초기 번들 크기
- CLS: `useMediaQuery` hydration 후 차트 aspect 재계산

### Accessibility 감점 요인 (예시)
- 색 대비: `#6B7A90` on `#131720` — WCAG AA 기준 확인 필요
- 포커스 링: `focus-visible:ring-*` 일부 버튼 누락 여부

### Best Practices 감점 요인 (예시)
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
