# 통합테스트 계획서 — 포트폴리오 조회 플로우 (E2E Phase 1)

- **작성일**: 2026-04-19
- **대상 플로우**: 홈 → 포트폴리오 리스트 → 계좌 상세/얼라인먼트
- **도구**: Playwright (설치 전)
- **실행 환경**: 로컬 프로덕션 compose (`docker-compose.prod.yml`, Caddy 경유 `https://localhost`)
- **상태**: Phase 1+2 + F/G/H 확장 완료 (2026-04-20, 로컬 **31/31** 통과 ~6~10s, CI 5회 연속 녹색)
  - Phase 1 (읽기, A/B/D): 16 케이스 — PR #1
  - Phase 2 (쓰기·에러, C/E): 4 케이스 — PR #1 (C2 는 KIS in-memory mock 으로 독립화, PR #2)
  - 확장 (F 주식상세 4 + G AI 리포트 2 + H 백테스트 4 → **5**, H5 실데이터 케이스 PR #5) — PR #1·#2·#3·#5
  - CI 워크플로 `.github/workflows/e2e.yml` 활성: compose up → seed(ui_demo + e2e_accounts + **backtest_e2e**) → E2E → 아티팩트 업로드

---

## 1. 사전 확인된 제약

| # | 항목 | 영향 |
|---|---|---|
| 1 | `/api/portfolio/*` 엔드포인트는 `ADMIN_API_KEY` 필요 (`curl` 직접 호출 시 `{"detail":"Invalid API key"}`) | E2E는 **브라우저 세션 경로**만 사용. API 직접 호출 테스트는 별도 레이어 |
| 2 | `signal` 테이블 0건 | `/portfolio/[id]/alignment`는 "empty state" 검증만 가능 (`report.items.length === 0`) |
| 3 | 계좌 2개 존재: `e2e-manual`(id=1), `e2e-kis`(id=2) | 탭 전환·조건부 UI 테스트에 양쪽 사용 |
| 4 | 보유 종목: `e2e-manual`에 삼성전자(005930) 10주 @ 72,000원만 1건 | metric/테이블 기대값 고정 가능 |
| 5 | 프론트는 Caddy(80/443)로만 노출, 내부 포트(3000/8000)는 외부 차단 | baseURL은 `https://localhost` 고정 |
| 6 | Caddy는 internal CA 자체 서명 인증서 사용 | Playwright `ignoreHTTPSErrors: true` 필수 |

## 2. 현 시드 데이터 스냅샷 (2026-04-19 기준)

| 테이블 | 행 수 | 비고 |
|---|---:|---|
| `brokerage_account` | 2 | `e2e-manual`(manual/mock), `e2e-kis`(kis_rest_mock/mock) |
| `portfolio_holding` | 1 | 005930 삼성전자, 10주, 평단 72,000.00, account_id=1 |
| `portfolio_transaction` | 1 | 2026-04-01 BUY 10주 @ 72,000, memo "E2E" |
| `portfolio_snapshot` | 91 | 누적 스냅샷 존재 → 성과 지표 계산 가능 |
| `signal` | 0 | 얼라인먼트는 empty state만 |
| `analysis_report` | 1 | 005930, openai/gpt-4o, HOLD |
| `stock_price` | 2,130,316 | 2023-06-01 ~ 2026-04-17 (752 영업일) |

---

## 3. 테스트 케이스

### A. 내비게이션·접근성 (Smoke)

| # | 시나리오 | 기대 |
|---|---|---|
| A1 | 홈(`/`) 접근 | 200, 타이틀 `SIGNAL — 공매도 커버링 시그널`, `h1.sr-only` 존재 |
| A2 | NavHeader의 "포트폴리오" 클릭 | URL `/portfolio`, 해당 메뉴 `aria-current="page"` |
| A3 | 직접 `/portfolio` 진입 | 계좌 탭 2개(`e2e-manual`, `e2e-kis`) 렌더 |

### B. 포트폴리오 리스트 (핵심)

| # | 시나리오 | 기대 |
|---|---|---|
| B1 | 진입 시 첫 계좌(`e2e-manual`)가 기본 선택 | 첫 번째 탭 `aria-selected="true"` |
| B2 | Metric 4개 렌더 | 보유 종목 수 `1`, 매입 원가 `720,000`, 누적 수익률/MDD 값 또는 `-` |
| B3 | 보유 종목 테이블 | 행 1개, 종목명 `삼성전자`, 코드 `005930`, 수량 `10`, 평단 `72,000.00` |
| B4 | 종목명 링크 클릭 | `/stocks/005930`로 이동 |
| B5 | "AI 리포트 →" 버튼 클릭 | `/reports/005930`로 이동 |
| B6 | 계좌 탭 전환(`e2e-kis`) | 보유 테이블 빈 상태 "보유 종목이 없습니다." |
| B7 | 조건부 UI: "KIS 모의 동기화" 버튼 | `e2e-kis`(kis_rest_mock)에서만 노출, `manual` 계좌에선 비노출 |

### C. 포트폴리오 액션 (옵션 — 쓰기 경로, 파괴적)

| # | 시나리오 | 기대 | 부수효과 |
|---|---|---|---|
| C1 | "스냅샷 생성" 클릭 | 버튼 "처리 중…" → `role="status"` 배너 "스냅샷 저장 완료: 평가금액 …원 · 미실현 …원" | `portfolio_snapshot` +1 |
| C2 | "KIS 모의 동기화" 클릭 (`e2e-kis`) | 배너 "KIS 동기화 완료: 신규 X · 갱신 X · 그대로 X" | `portfolio_holding` 변동 가능 |

### D. 얼라인먼트 페이지

| # | 시나리오 | 기대 |
|---|---|---|
| D1 | 포트폴리오에서 "시그널 정합도" 링크 클릭 | URL `/portfolio/1/alignment` |
| D2 | 페이지 헤더 | "시그널 정합도 (계좌 #1)" + 서브카피 "최근 30일 · 스코어 60점 이상" |
| D3 | 빈 상태 (현 DB 상태) | "기간 내 해당 기준(스코어 ≥ 60) 의 시그널이 없습니다." |
| D4 | min_score 슬라이더 조작 (60→30) | 헤더 카피 숫자 갱신 + 재요청 발생 (network wait) |
| D5 | "← 포트폴리오" 링크 | `/portfolio`로 복귀 |
| D6 | 유효하지 않은 accountId (`/portfolio/abc/alignment`) | 에러 박스 "유효하지 않은 계좌 ID 입니다" |

### E. 에러/에지 (선택)

| # | 시나리오 | 기대 |
|---|---|---|
| E1 | 존재하지 않는 계좌 `/portfolio/999/alignment` | API 404 → 에러 배너 노출 |
| E2 | 네트워크 차단(route intercept) → accounts 호출 | "계좌 조회 실패: …" 에러 배너 |

---

## 4. 우선순위·단계 계획

| Phase | 범위 | 케이스 수 | 부수효과 | 비고 |
|---|---|---:|---|---|
| **Phase 1** (추천) | A1~A3 + B1~B7 + D1~D6 | 16 | 없음 | 현 시드로 100% 커버. 안정화 후 CI 적용 |
| **Phase 2** | C1, C2, E1, E2 | 4 | DB 쓰기 발생 | 격리 전략 확정 후 착수 |

---

## 5. 환경·설치 체크리스트

- [ ] `src/frontend/package.json`에 `@playwright/test` devDependency 추가
- [ ] `npx playwright install --with-deps chromium` (첫 실행만)
- [ ] `src/frontend/playwright.config.ts` 생성
  - `baseURL: 'https://localhost'`
  - `ignoreHTTPSErrors: true`
  - `use: { trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure' }`
- [ ] `src/frontend/tests/e2e/` 디렉토리 + POM
  - `pages/HomePage.ts`, `pages/PortfolioPage.ts`, `pages/AlignmentPage.ts`
  - `tests/portfolio/navigation.spec.ts`, `tests/portfolio/holdings.spec.ts`, `tests/portfolio/alignment.spec.ts`
- [ ] CI 실행 전 의존성 기동 스크립트 (`docker compose -f docker-compose.prod.yml up -d`)
- [ ] `.gitignore`에 `playwright-report/`, `test-results/` 추가

## 6. 리스크·선행 해결 항목

| 리스크 | 대응 |
|---|---|
| Caddy self-signed 인증서 | `ignoreHTTPSErrors: true` + CI에서 동일 설정 |
| 시드 데이터 의존 (삼성전자 10주 등) | 각 테스트 `beforeAll`에서 DB 상태 검증 or seed 스크립트 재실행 전제 |
| `signal` 0건 가정이 미래 깨질 수 있음 | D3는 "empty state **또는** 목록 렌더" 둘 다 허용하는 유연한 검증 고려 |
| Phase 2 쓰기 격리 | (a) 전용 테스트 계좌 추가, (b) count before/after 검증, (c) transaction rollback API 중 택일 |
| Metric 값 고정 (`720,000`) | `formatNumber` 로케일에 따른 구분자 차이 대응 — 정확 일치 대신 정규식 매칭 |

## 7. 결정 필요 항목 (승인 후 착수)

1. **Phase 1만 먼저, 아니면 Phase 1+2 동시?** (추천: Phase 1 먼저)
2. **baseURL 은 `https://localhost`(Caddy) vs `http://localhost:3000`(Next 직접)?** (추천: Caddy)
3. **C1/C2 격리 전략**:
   - (a) 전용 e2e 계좌 추가 생성 후 테스트 끝에 삭제
   - (b) 실행 전후 `portfolio_snapshot` count 비교만
   - (c) Phase 1에서 제외
4. **시그널 "데이터 있는" 케이스 포함 여부**: 현재 `signal` 0건 → 시드 스크립트를 추가할지, empty state만 검증할지

---

## 8. 진행 규칙 (세션 운영)

- 긴 작업은 TaskCreate 체크리스트로 단계 가시화
- 단계 진입 시 한 줄 현황 공유 ("지금 B1~B3 실행 중, 예상 30초")
- 오래 걸리는 명령(`playwright install`, `test` 러닝)은 `run_in_background`로 비동기 처리
- 완료 시 한 문장 결과 + 다음 단계 명시

---

## 9. 다음 액션

1. 위 "7. 결정 필요 항목" 4개 승인
2. 승인된 범위만 Playwright 스캐폴드 + Phase 1 스펙 17개 작성
3. 로컬 1회 전체 통과 확인
4. CI 워크플로(.github/workflows/e2e.yml) 추가 (별도 커밋)
