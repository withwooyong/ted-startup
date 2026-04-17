---
agent: 11-qa
phase: Phase 4 Verify
sprint: Sprint 4 전체 완료 후 QA 검증
date: 2026-04-17
commit: 9436772 (master)
verdict: CONDITIONAL
---

# QA 테스트 리포트 — ted-startup (공매도 커버링 시그널 플랫폼)

## 1. Summary

| 지표 | 값 |
|---|---|
| **총 테스트 수** | 29 (백엔드) / 0 (프론트엔드) |
| **통과** | 29 / 29 |
| **실패/에러/스킵** | 0 / 0 / 0 |
| **Pass Rate** | 100% |
| **테스트 실행 시간** | 1.31s (JUnit 전체) + Testcontainers 부트 ~15s |
| **총 소요 (Gradle BUILD)** | 10s (warm JVM) |
| **라인 커버리지 추정** | 백엔드 50~60% (JaCoCo 미설정, 서비스 계층 중심) · 프론트엔드 0% |
| **프론트엔드 빌드** | PASS (Next.js 16, 6 routes, static/dynamic 분리 정상) |

### 실행 근거
- `./gradlew test --rerun-tasks`: `BUILD SUCCESSFUL in 10s`
- JUnit XML 7개 파일 합산: `tests="29" failures="0" errors="0" skipped="0"`
- `npm run build` (frontend): 빌드 성공, TypeScript 1.4s, 6개 라우트 생성

---

## 2. Test Pyramid 분석

### 현재 구성

| 레이어 | 테스트 수 | 비율 | 이상적 비율 | 판정 |
|---|---|---|---|---|
| Unit (순수 단위) | 9 | 31% | 70% | **부족** |
| Integration (Testcontainers + WebMvc) | 19 | 66% | 20% | **과다** |
| E2E (Playwright/Cypress) | 0 | 0% | 10% | **부재** |
| 컨텍스트 로드 sanity | 1 | 3% | - | OK |

**분류 근거**:
- Unit: `SignalDetectionServiceTest`(5) + `BacktestEngineServiceTest`(4) — Mockito 기반 순수 단위
- Integration: `SignalApiIntegrationTest`(3) + `BacktestApiIntegrationTest`(6) + `NotificationApiIntegrationTest`(9) + `CorsConfigTest`(1) — 실제 PostgreSQL 컨테이너 + MockMvc
- E2E: 없음

### 역피라미드 현상
- 통합이 단위의 2배 이상인 구조. 현재 프로젝트 규모(MVP)에서는 허용 가능하나, 향후 도메인 로직이 늘어나면 테스트 속도가 병목이 됨.
- 싱글톤 컨테이너 패턴(`IntegrationTestBase`)으로 부팅 1회만 발생하도록 최적화되어 있음 → 역피라미드의 성능 페널티는 현재 낮음.

---

## 3. Backend Test Inventory

### 3.1 `SignalDetectionServiceTest` (5 tests — 단위)
| # | DisplayName | 커버 영역 |
|---|---|---|
| 1 | 대차잔고 급감 시그널: changeRate -15%이면 RAPID_DECLINE 생성 | 급감 시그널 생성 정상 경로 |
| 2 | 대차잔고 급감: changeRate -5%이면 임계값 미달로 시그널 미생성 | 임계값 경계 (negative case) |
| 3 | 추세전환 시그널: 5일MA가 20일MA를 하향 돌파하면 TREND_REVERSAL 생성 | 이동평균 교차 로직 |
| 4 | 숏스퀴즈 종합 스코어: 4팩터 합산 40 이상이면 SHORT_SQUEEZE 생성 | 가중 합산 점수 계산 |
| 5 | 중복 탐지 방지: 같은 날짜+종목+타입 시그널은 재생성하지 않음 | 멱등성 보장 |

### 3.2 `BacktestEngineServiceTest` (4 tests — 단위)
| # | DisplayName | 커버 영역 |
|---|---|---|
| 1 | 수익률 계산: 시그널 발생일 대비 5/10/20일 후 주가 변동률 | 핵심 수익률 계산 |
| 2 | 적중률 집계: 양수 수익률 비율 계산 | 통계 집계 |
| 3 | 미래 주가 데이터 부족: 수익률을 null로 처리 | null-safe 경계 |
| 4 | 시그널 없는 기간: 빈 결과 반환 | empty 경계 |

### 3.3 `SignalApiIntegrationTest` (3 tests — 통합)
- `GET /api/signals`: 날짜별 조회
- `GET /api/signals`: 타입 필터링 (SignalType enum)
- `POST /api/signals/detect`: API Key 인증 검증

### 3.4 `BacktestApiIntegrationTest` (6 tests — 통합)
- `GET /api/backtest` 결과 조회
- `POST /api/backtest/run` API Key 누락 → 403
- `POST /api/backtest/run` 잘못된 API Key → 403
- `POST /api/backtest/run` 유효 키 → 실행 성공
- `POST /api/backtest/run` 파라미터 미지정 → 기본값 3년
- `POST /api/backtest/run` 3년 초과 → 400 Bad Request

### 3.5 `NotificationApiIntegrationTest` (9 tests — 통합, Sprint 4 Task 4)
- `GET /preferences`: 인증 없이 조회, 첫 호출 시 기본값 row 생성
- `PUT /preferences`: API Key 누락 → 401
- `PUT /preferences`: 잘못된 API Key → 401
- `PUT /preferences`: 전체 필드 업데이트 + 영속 확인
- `PUT /preferences`: minScore 범위 초과 → 400
- `PUT /preferences`: 알 수 없는 signalType → 400 (입력값 반사 없음, XSS 방지)
- `PUT /preferences`: signalTypes 빈 배열 → 400
- `PUT /preferences`: signalTypes 4개 이상 → 400 (DoS 방지)
- `PUT /preferences`: 필수 필드 누락 → 400

### 3.6 `CorsConfigTest` (1 test — 통합)
- CORS preflight에서 X-API-Key 헤더가 허용되는지 검증 (33b6cf1 이슈 회귀 방지)
- **기존 이슈**: 현재 전체 `@SpringBootTest` 컨텍스트를 로드 → `@WebMvcTest`로 분리 가능 (known_issues: LOW)

### 3.7 `SignalBackendApplicationTests` (1 test)
- `contextLoads()` — 스프링 컨텍스트 sanity check

---

## 4. Frontend Test Gap

### 현황
- `src/frontend/src/` 아래 `*.test.*` / `*.spec.*` 파일 **0개**
- Jest/Vitest/Playwright 설정 없음
- `package.json`에 test 스크립트 없음
- 빌드는 정상 (TypeScript strict, ESLint 0 error)

### 빠진 영역 (우선순위 순)
| 우선순위 | 테스트 | 대상 | 사유 |
|---|---|---|---|
| P1 | 대시보드 렌더링 | `app/page.tsx` (시그널 목록) | 메인 진입점, TanStack Query 연동 |
| P1 | 필터 상호작용 | 시그널 타입 버튼, 날짜 셀렉터 | `aria-pressed` 토글 회귀 방지 |
| P1 | ErrorBoundary 복구 | `components/ErrorBoundary.tsx` | `resetKeys` 동작 검증 (9436772) |
| P2 | 상세 페이지 라우팅 | `app/stocks/[code]/page.tsx` | 동적 라우트 + 서버 데이터 fetch |
| P2 | 백테스트 차트 렌더 | `app/backtest/page.tsx` | 숫자 포맷/NaN 방어 |
| P2 | 알림 설정 폼 | `app/settings/page.tsx` | react-hook-form + zod 유효성 |
| P3 | 접근성 스냅샷 | axe-core 전 페이지 통합 | WCAG AA 컴플라이언스 |
| P3 | E2E: 시그널 탐지→상세 이동 | Playwright | Happy path 사용자 여정 |

### 권장 스택
- **단위/컴포넌트**: Vitest + React Testing Library (Next.js 16 App Router 친화)
- **E2E**: Playwright (Next.js 공식 템플릿 지원)
- **MSW**: 백엔드 API 목업

---

## 5. Performance 검증

| 항목 | 상태 | 비고 |
|---|---|---|
| P95 응답시간 | **미측정 (GAP)** | `GET /api/signals` 기준 목표 < 500ms |
| P99 응답시간 | **미측정 (GAP)** | `POST /api/backtest/run` 기준 목표 < 5s |
| 부하 테스트 | **미실행 (GAP)** | k6/JMeter 스크립트 없음 |
| N+1 쿼리 회귀 테스트 | **부분 (GAP)** | 33b6cf1에서 17,500→7 쿼리로 최적화했으나 `@DataJpaTest` + Hibernate statistics 기반 회귀 테스트 없음 |
| 메모리/스레드 | Virtual Threads 활성화 | 실측치 없음 |

**권고**: Sprint 5에서 k6 부하 스크립트 + Hibernate statistics assertion 테스트 2종 추가.

---

## 6. Known Bugs / Issues

`pipeline/state/current-state.json` `known_issues` 기반:

| 심각도 | ID | 설명 | QA 코멘트 |
|---|---|---|---|
| LOW | `korean-holidays` | 한국 공휴일 캘린더 미적용 | v1.1 연기 — 주말만 처리하고 있어 실서비스 시 신호일 오탐 가능 |
| LOW | `cors-test-scope` | `CorsConfigTest`가 전체 SpringBootTest 컨텍스트 로드 | `@WebMvcTest` 분리 시 CI 속도 개선 (~5s 단축) |
| LOW | `lockfile-duplicate` | `~/package-lock.json`과 `src/frontend/package-lock.json` 공존 | Next.js 16 turbopack 경고 — `turbopack.root` 설정 필요 |

### 회귀 검증 확인
- `N+1-signal-detection` (33b6cf1): 쿼리 감소 회귀 테스트 **부재** → 재발 가능
- `N+1-daily-summary`: 회귀 테스트 **부재**
- `backtest-unbounded` (3년 제한): `BacktestApiIntegrationTest` 6번째 테스트로 회귀 보호 **확인**
- `cors-api-key`: `CorsConfigTest`로 회귀 보호 **확인**
- `mobile-responsive` / `error-boundary`: 프론트엔드 테스트 부재로 회귀 보호 **없음**

---

## 7. Verdict: **CONDITIONAL**

### PASS 요소
- 백엔드 29개 테스트 100% 통과, 실패 0건
- 도메인 핵심 로직(시그널 탐지 3종 + 백테스팅) 단위 테스트 커버
- 보안 회귀(CORS, API Key, DoS, XSS) 통합 테스트로 보호
- 프론트엔드 빌드 성공 (타입 체크 + 린트 0 error)

### 조건부 사유
1. **프론트엔드 자동화 테스트 전무** — 수동 검증 의존, Sprint 4 Task 5/6의 접근성/ErrorBoundary 회귀 위험
2. **성능 기준선 미수립** — P95/P99 미측정, N+1 회귀 테스트 없음
3. **E2E 부재** — 사용자 여정 전체 경로 검증 수단 없음
4. **커버리지 측정 도구 미통합** — JaCoCo가 `build.gradle`에 미설정, 정량 커버리지 수치를 클레임 불가

### Human Approval #3 권고
- **조건부 통과 권고**: 백엔드 품질은 MVP 릴리즈에 부족하지 않음
- **차기 Sprint 5 진입 전 필수 보완 1건**: 프론트엔드 최소 smoke 테스트 3종 (P1 항목)
- **배포 전 권장 1건**: 핵심 API 5종의 수동 부하 테스트(k6 최소) 1회 실시

---

## 8. Recommendations (차기 Sprint 액션)

### 8.1 Sprint 5 필수 (배포 차단 요소)
- [ ] **프론트엔드 테스트 하네스 구성**: Vitest + RTL + MSW (1인일)
- [ ] **P1 스모크 테스트 3종 작성**: 대시보드 렌더, 필터 aria-pressed, ErrorBoundary resetKeys (0.5인일)
- [ ] **JaCoCo 플러그인 추가**: `build.gradle`에 coverage 측정, CI 리포트 아카이브 (0.3인일)

### 8.2 Sprint 5 권장 (품질 향상)
- [ ] **Playwright E2E 1종**: 시그널 탐지 → 상세 진입 happy path (0.5인일)
- [ ] **N+1 회귀 테스트**: Hibernate `Statistics.getQueryExecutionCount()` 기반 assertion 2종 추가 (0.3인일)
- [ ] **k6 부하 스크립트**: `GET /api/signals` 기준 P95 < 500ms 검증 (0.3인일)

### 8.3 Sprint 6+ (장기 개선)
- [ ] `CorsConfigTest`를 `@WebMvcTest`로 리팩터 (CI 속도 5s 단축)
- [ ] 한국 공휴일 캘린더 적용 (`workalendar-kr` 등) — 신호일 정확도 개선
- [ ] 접근성 CI 게이트 (axe-playwright + 0 violation threshold)
- [ ] Mutation testing (PIT) 도입 — 테스트 품질 정량화

---

## 9. 부록: 실행 환경

- **JVM**: Java 21 (Virtual Threads 활성화)
- **테스트 프레임워크**: JUnit 5 + Mockito + Testcontainers
- **컨테이너**: `postgres:16-alpine` (싱글톤 패턴, 모든 통합 테스트 공유)
- **빌드 툴**: Gradle 8.x (`./gradlew test --rerun-tasks`)
- **프론트엔드**: Next.js 16 + React 19 + TypeScript strict + ESLint
- **CI 통합**: 아직 없음 (로컬 수동 실행)

---

_검증 완료: 2026-04-17 by 11-qa agent_
