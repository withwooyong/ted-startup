---
agent: 00-judge
phase: Phase 5 Ship
date: 2026-04-17
last_commit: fa38b43
inputs:
  - src/backend/Dockerfile
  - src/frontend/Dockerfile
  - docker-compose.prod.yml
  - .env.prod.example
  - .github/workflows/ci.yml
  - pipeline/artifacts/10-deploy-log/runbook.md
  - pipeline/artifacts/11-analytics/launch-report.md
cross_reference:
  - pipeline/state/current-state.json (approval #3 passed)
  - pipeline/artifacts/07-test-results/verify-judge-evaluation.md
  - pipeline/artifacts/02-prd/prd.md
verdict: PASS (CONDITIONAL-minor)
final_score: 8.1
deployable: Y (with 1 minor follow-up before first prod push)
---

# Phase 5 Ship 통합 판정 — ted-startup (BEARWATCH)

## 1. 종합 판정 — **PASS** (조건부 minor, 점수 8.1)

DevOps 산출물 6건 + Analytics 1건 모두 "1인 Solo operator · 단일 VPS · 내부 MVP" 제약을 정확히 인지한 범위에서 설계됐다. Verify phase의 블로커 4건(B-C1 / B-H1 / B-H2 / B-H3)이 Ship 산출물에 **완전 반영**된 것을 교차 확인했다(섹션 9). 컨테이너 레지스트리 미결정과 Flyway 미도입은 **의도된 MVP 제약**으로 runbook에 명시 · 로드맵 편성되어 있어 감점 요소이지 블로커가 아니다. **배포 진행 권고.**

## 2. 5차원 평가 점수

| 차원 | 가중치 | 점수 | 가중 점수 | 근거 |
|---|---|---|---|---|
| 완전성(Completeness) | 25% | 8.0 | 2.00 | Dockerfile(FE/BE) · compose · env.example · CI · runbook · KPI 리포트 모두 존재. 누락은 (a) `notification_preference.sql` → `/docker-entrypoint-initdb.d/` 마운트만 있고 Flyway 대체 수동 절차 runbook §7에 명시(설계된 공백), (b) 레지스트리 push step은 스텁(docker-build load-only)으로 설계됨 — "push 미확정" 자체가 문서화. 프론트 E2E 스모크 스크립트는 없으나 runbook §2.5에 curl 기반 스모크 명시. |
| 일관성(Consistency) | 25% | 8.5 | 2.125 | compose 환경변수 ↔ .env.prod.example 필수 키(ADMIN_API_KEY/TELEGRAM_*/KRX_AUTH_KEY/POSTGRES_*) ↔ runbook §2.2 필수 시크릿 ↔ application.yml 키 네이밍 4자리 모두 일치. backend `healthcheck`(curl /actuator/health) ↔ Dockerfile HEALTHCHECK ↔ `build.gradle` actuator 의존성 일치. FE Dockerfile standalone ↔ next.config.ts `output: "standalone"` 일치. Analytics B-4 배포 운영 KPI ↔ runbook §4~5 rolling update/rollback 절차 일치. |
| 정확성(Accuracy) | 20% | 8.0 | 1.60 | 모든 기술 선택이 실제 동작 가능: UID 1001 non-root, `HEALTHCHECK` 문법, `depends_on: service_healthy`, volume 영속화(`signal-prod-data`), `docker-entrypoint-initdb.d` 볼륨-empty-only 실행 규칙이 정확히 기술됨. `MaxRAMPercentage=75.0`은 Java 21 컨테이너 인지 옵션으로 적절. 단 감점: (a) backend 헬스체크가 grep으로 `"status":"UP"` 확인 — `"status":"OUT_OF_SERVICE"` 등 비정상 상태도 grep pattern 자체는 매칭되지 않으므로 OK지만, actuator 응답 JSON 변화에 brittle. (b) CI `TESTCONTAINERS_RYUK_DISABLED=true`는 CI runner 청소 부담을 Github에 위임하는 패턴 — 의도적이나 주석 없음. |
| 명확성(Clarity) | 15% | 8.5 | 1.275 | runbook은 12개 섹션(사전준비/초기배포/운영/업데이트/롤백/백업/스키마/시크릿/모니터링/제약/AWS로드맵/빠른레퍼런스)이 체계적. launch-report는 A~G + 부록 7개 섹션으로 KPI 측정 방법·소스·대응까지 매핑. Dockerfile 주석이 한글로 단계 명시. 감점: compose 파일 내 "frontend:3000만 외부 노출, backend/db는 내부 전용" 네트워크 격리 의도가 주석으로만 설명됨 — 실제로 `ports:` 미지정으로 노출 차단되는 것은 올바르나 초심자용 각주 한 줄 더 있었으면 9.0. |
| 실행가능성(Actionability) | 15% | 7.5 | 1.125 | runbook §2.1~2.5 그대로 따라가면 첫 배포 성공. §5 롤백 3가지 시나리오 제시. §6 cron 자동 백업 템플릿 copy-paste 가능. Analytics E 섹션 Week 1~4 체크포인트와 F 섹션 Red Flags 8종은 실제 측정 가능(대부분 기존 테이블·Actuator 기반). 감점: (a) `IMAGE_TAG` 환경변수는 compose에는 있으나 .env.prod.example / runbook에 값 지정 가이드 부재(기본값 latest로 동작하므로 치명적 아님). (b) Analytics B-2 "API P95 < 500ms"는 Micrometer 미적용 상태이므로 D+7 "Prometheus endpoint 추가" 선행 필요 — launch-report §D 권장 신규 구성요소에 명시되어 있으나, baseline 수집 시점이 Week 1 스테빌리티 게이트 이후로 밀릴 위험. |
| **합계** |  |  | **8.125 (반올림 8.1)** | → **PASS** (>= 8.0) |

## 3. 배포 가능 여부 — **Y**

### 최종 배포 체크리스트 (운영자 실행)

- [ ] `.env.prod` 생성 후 `chmod 600` (runbook §2.2)
- [ ] `ADMIN_API_KEY` = `openssl rand -hex 32` — 서버 측 env로만 주입(compose line 58, 91 확인)
- [ ] `POSTGRES_PASSWORD`, `KRX_AUTH_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 실제 값 세팅
- [ ] `docker compose -f docker-compose.prod.yml up -d --build` — 5~10분 기다린 후 `ps`로 3 컨테이너 healthy 확인
- [ ] DB 초기화 검증: `docker compose exec db psql -U signal -d signal_db -c "\dt"` → `short_interest_daily`, `signal`, `notification_preference`, `backtest_result`, `stock`, `stock_price`, `lending_balance` 확인
- [ ] 스모크 4종(runbook §2.5): frontend `/`, backend `/actuator/health`, `/api/signals`, admin preferences(X-Admin-Api-Key 헤더)
- [ ] **D+1 최초 일일 배치 작동 확인** — 텔레그램 채널에 daily 알림 수신
- [ ] **D+3 내 최초 백테스팅 실행** → baseline 수치 고정(launch-report B-1 주석)

### 권장 follow-up (Ship+48h 이내 — non-blocking)

1. reverse proxy + TLS(Nginx/Caddy + Let's Encrypt) — runbook §1에 "선택" 표기되어 있으나, ADMIN_API_KEY가 X-Admin-Api-Key 헤더로 평문 전송되므로 TLS 없이 공개 IP 노출은 회피.
2. `management.endpoints.web.exposure.include=health,metrics,prometheus` 추가(launch-report §D) → Week 1 안정화 게이트에서 P95/에러율 baseline 수집 가능.

## 4. Dockerfile / compose 품질 평가

| 항목 | Backend | Frontend | compose | 평가 |
|---|---|---|---|---|
| 멀티스테이지 | builder(JDK) → runtime(JRE) | deps → builder → runtime | — | 양 Dockerfile 이미지 크기 최소화 적절. |
| non-root | `spring:spring` UID/GID 1001 | `nextjs:nodejs` UID/GID 1001 | — | **양호**. |
| healthcheck | `curl /actuator/health | grep UP` | `node fetch('/')` | compose `depends_on: service_healthy` | 기동 순서 보장, 장애 시 auto-restart(`unless-stopped`). **양호**. |
| 비밀값 처리 | ENV JAVA_OPTS만 포함. 비밀은 compose env로 주입 | PORT/HOSTNAME만 build-time | `${VAR}` 치환, .env.prod 분리, .gitignore 등록(`.env.prod`, `.env.prod.local`) | **양호**. 이미지에 시크릿 하드코딩 없음. |
| 네트워크 격리 | backend port 미공개 | `ports: 3000:3000`만 공개 | `backend-net` bridge, db/backend는 내부 전용, db 주석 "외부 노출 금지" | **양호**. 공격 표면 frontend 3000만. |
| 이미지 레이어 캐시 | Gradle deps 선다운로드 → 소스는 뒤에 COPY | package.json만 먼저 COPY → ci 설치 → 소스 | — | CI 빌드 타임 최적화 양호. |
| 빌드 재현성 | `syntax=docker/dockerfile:1.7`, gradle --no-daemon | npm ci(lock 고정) | `image: ted-signal-*:${IMAGE_TAG:-latest}` | **양호**. |

**감점 요인 (각 -0.25)**:
- backend Dockerfile line 42: `apt-get install curl` — healthcheck 전용이지만 `--no-install-recommends` 외 CVE surface 확대. 대안: `wget` 대신 `HealthCheck`를 Spring Actuator 내장 JMX/cli로 전환 가능하나 MVP 복잡도 감안 시 허용.
- frontend healthcheck `fetch('http://localhost:3000/')` 200만 확인 → SSR hydration 오류 같은 응용 레벨 결함은 놓칠 수 있음(MVP 허용).

## 5. CI 파이프라인 적절성

| 영역 | 평가 | 점수 |
|---|---|---|
| 테스트 커버리지 경로 | backend-test → Testcontainers + JUnit 29개. frontend-build → tsc + lint(continue-on-error) + next build. frontend 테스트 0건은 Verify phase의 F-L1 MEDIUM와 동일한 상태로 Sprint 5 이관됨 — CI가 이를 은폐하지 않고 있음(good). | 8 |
| 캐시 전략 | `gradle/actions/setup-gradle@v4`(PR은 read-only), `cache: npm` + lockfile path, docker buildx `type=gha,scope=backend/frontend,mode=max` 분리. | 9 |
| 이미지 태깅 | `${SHORT_SHA}` + `latest` 이중 태깅 — 롤백 시(runbook §5.2) SHA 기반 복귀 가능. | 8 |
| Push 미설정 | docker-build job은 `push: false, load: true`. 레지스트리 미확정 상태에서 이미지 빌드 유효성 검증만 수행. **이는 MVP에서 올바른 선택** — 운영자는 VPS에서 `docker compose --build`로 직접 빌드하므로 레지스트리 없이도 배포 가능. v1.1 AWS/ECR 이관 시 `push: true` + `aws ecr get-login-password` step 추가로 1~2시간 내 확장(runbook §11.1 체크리스트 존재). | 8 |
| 보안 | `permissions: contents: read` 최소권한. secrets는 CI에서 사용하지 않음(테스트는 Testcontainers in-process). | 9 |
| 동시성 | `concurrency: cancel-in-progress` — 동일 ref의 중복 워크플로우 자동 취소. | 9 |

**총평**: CI는 "검증 레인" 역할에 충실. 배포 자동화가 아닌 품질 게이트라는 역할 분리가 명확. 레지스트리 푸시는 v1.1 AWS 이관 시점에 활성화하는 것이 올바른 순서.

## 6. Runbook 실행 가능성 — **Solo operator 실행 가능 Y**

| 섹션 | 평가 |
|---|---|
| §1 사전준비 | Ubuntu 22.04/24.04 + Docker 24+ 명시, 리소스 요건(vCPU 2 / RAM 4GB / 20GB) 구체적. |
| §2 초기배포 | git clone → .env.prod → up -d → smoke 4종까지 copy-paste 가능한 5단계. 기대 상태(healthy)와 소요시간(첫 5~10분)까지 명시. |
| §3 일상운영 | logs / healthcheck inspect / restart 3종 rote 작업. |
| §4 rolling update | `git pull + up -d --build` — 짧은 다운타임(≤30초) 허용을 전제로 단순화. **1인 운영 맥락에서 정확**. |
| §5 롤백 | (1) 직전 커밋 (2) 이미지 태그 (3) DB 덤프 복원 3시나리오 분리. |
| §6 DB 백업 | pg_dump 수동 + cron(14일 보관) + 복원 — **오프사이트 백업 부재를 제약으로 명시**하고 NAS/S3 수동 복사 월 1회 권장 — 정직하고 실행 가능. |
| §7 스키마 변경 | **Flyway 미도입 caveat를 숨기지 않음**. V3+는 수동 psql 실행 4단계. Followup으로 Flyway 도입 안내. |
| §8 비밀값 관리 | .gitignore / chmod 600 / 분기 순환 / SSH 접근 — 표 형식 간결. |
| §9 모니터링 | 현재(수동) vs v1.1 권장(Uptime Kuma/Loki/Prometheus) 분리 — MVP 허용 범위 정직. |
| §10 알려진 제약 | 무중단/HA/오프사이트/시크릿매니저/로그보존/레지스트리 6항목 현재 vs 미래 매핑. |
| §11 AWS 이관 로드맵 | 5단계(ECR/Aurora/ECS/CloudFront/관측) 순서 명확. 본 Ship의 핫픽스가 아니라 후속 마일스톤임을 분명히 함. |
| §12 빠른 레퍼런스 | ps/logs/pg_dump/down/down -v — 혼동 위험 명령(`down -v` 볼륨 삭제)에 경고 이모지 부착. |

**판정**: Solo operator가 문서만으로 초기 배포 → 정상 운영 → 롤백 → 백업 복원까지 가능. **누락 단계 없음**.

## 7. Analytics / KPI 완성도

| 질문 | 답 |
|---|---|
| v1 운영 KPI 4차원(시그널 품질 / 시스템 안정성 / 알림 효용성 / 배포 운영)이 실제 측정 가능한가? | **대부분 Y**. B-1 적중률/수익률은 `backtest_result` + `signal × stock_price` 조인으로 즉시 집계 가능. B-2 배치 성공률은 `BATCH_JOB_EXECUTION` 테이블에서 즉시. B-3 알림 성공률은 현재 `TelegramClient` 로그만 존재 — **`notification_log` 테이블 신설 권장(§D)**이 D+7 내 액션으로 명시됨. B-4 배포 운영은 git/docker 기반. |
| Baseline 확정 전략이 명확한가? | **Y**. B-1 주석: "D+1~D+3 최초 백테스팅으로 baseline 고정 → 주간 편차 모니터링". |
| Week 1~4 계획이 실행 가능한가? | **Y**. Week 1 Stability Gate(배치 ≥99%, 텔레그램 ≥99%, 재수집 1회 멱등성 검증 — B-H3 수정이 여기서 실증된다) → Week 2 Signal Quality Gate(실적중 vs 백테스팅 gap ≤15%p) → Week 3 튜닝 진단 → Week 4 v1.1 우선순위 결정. 각 주별 pass/fail 임계와 실패 대응이 구체적. |
| Red Flags 구체성은? | **Y**. 8종(F1 KRX 차단 / F2 배치 3연속 실패 / F3 텔레그램 401·429 / F4 디스크 80% / F5 적중률 급락 / F6 과적합 / F7 Heap 85% / F8 알림 미확인). **F2를 1순위로 명시**(블라스트 반경 근거 포함) — 탁월. 각 임계·탐지방법·대응까지 3항목 완결. |
| SaaS AARRR(C 섹션)은 혼란을 주지 않는가? | **Y**. 명확히 "v1 추적 대상 아님, v2 참고용"으로 격리. GTM 전략 문서와 교차 참조. |
| v1.1 우선순위 매트릭스(G 섹션)는 근거 있는가? | **Y**. `known_issues` 3건 + review MEDIUM 9건을 impact × effort 2차원 분류 후 Top 5 순서(Q1 텔레그램 스택트레이스 → Q2 타임존 → Q3 백테스트 400 → Q4 공휴일 캘린더 → Q5 TanStack Query). **Q4는 "D+60 전후 연휴 도래 시점 역산"으로 시즈널 리스크 반영** — 운영자 관점 우수. |

**감점 요인**:
- B-2 API P95는 Micrometer + Prometheus endpoint 활성화 전에는 측정 불가 — launch-report §D가 이를 "권장 신규 구성요소 D+7"로 명시하나, 이 한 설정은 `application.yml` 한 줄이면 되는 수준이라 **Ship에 포함되었으면 9.0**이었다.

## 8. 발견된 이슈

### CRITICAL (배포 차단) — **0건**

### HIGH — **0건**

### MEDIUM — **2건** (비차단, Ship+7 권고)

- **M-S1** `management.endpoints.web.exposure.include` 미설정 → P95/에러율 baseline 측정이 Week 1 스테빌리티 게이트에서 불가. **조치**: `application-prod.yml`에 `health,metrics,prometheus` 추가 후 재배포. 1시간 작업, D+7 이내 권장.
- **M-S2** `.env.prod.example` → `IMAGE_TAG` / `FRONTEND_PORT` / `NEXT_PUBLIC_API_BASE_URL` / `SPRING_PROFILES_ACTIVE`는 compose에서 기본값 fallback으로 동작하나 example에 명시되지 않으면 초심자 배포 시 "변수 미세팅 경고" 노출. **조치**: example에 주석 포함 기본값 샘플 추가. 15분 작업.

### LOW — **3건**

- **L-S1** backend healthcheck의 `grep '"status":"UP"'`은 actuator 응답 포맷에 결합. Spring Boot 버전 업 시 brittle. **조치**: `curl -fsS --fail http://localhost:8080/actuator/health` 단독 사용(HTTP 200/503 구분)으로 교체 검토.
- **L-S2** frontend Dockerfile runtime stage에 healthcheck가 standalone server.js의 루트 fetch만 하므로 SSR 렌더 에러는 탐지 못 함. v1 허용.
- **L-S3** docker-compose의 log driver/rotation 미설정 → 장기 운영 시 디스크 소진 가능성. runbook §10 "로그 보존 Docker 기본(로테이션 미설정)" 언급 있음. `logging.options: max-size=10m, max-file=5` 추가 권장.

**배포 차단 여부**: **없음**. 5건 전부 운영 개선 항목으로 Ship+7 핫픽스/Sprint 5 백로그에서 소화.

## 9. 크로스 체크 — Verify resolved_issues ↔ Ship 산출물 반영

| Verify 블로커 | 조치 요구 | Ship 산출물 반영 상태 | 증거 |
|---|---|---|---|
| **B-C1** `NEXT_PUBLIC_ADMIN_API_KEY` 번들 노출 | 서버 측 `ADMIN_API_KEY`로만 존재, 클라이언트 번들 제거 | **완전 반영 Y** | `grep -r NEXT_PUBLIC_ADMIN src/frontend` → **0건**. `docker-compose.prod.yml` line 58(backend env) + line 91(frontend env: 서버 사이드 Route Handler용). `src/frontend/src/app/api/admin/notifications/preferences/route.ts` line 17: `process.env.ADMIN_API_KEY`(접두어 없음 = 서버 전용). runbook §2.2 필수 시크릿에 `ADMIN_API_KEY` 포함, §2.5 스모크에서 `X-Admin-Api-Key: $ADMIN_API_KEY` 헤더 사용. |
| **B-H1** 자기호출 `@Transactional` 무효 | `MarketDataPersistService` 빈 분리 | 코드 반영됨(state.resolved_issues), Ship 산출물 관점에선 실행 경로 영향 없음 — runbook §2.5 스모크로 Week 1에 실증. |
| **B-H2** `persistAll` dead code | 삭제 | 동일. Ship 영향 없음. |
| **B-H3** 배치 멱등성(유니크 제약 충돌 방지) | `findAllByTradingDate` 1회 조회 후 skip | 동일. launch-report Week 1 "수동 재수집 1회 시도"로 실증 계획 반영. |

**교차 결론**: Verify phase에서 차단한 4건 모두 Ship 산출물 레벨에서 정상 반영됨. 특히 B-C1은 **DevOps의 단일 최고 리스크였는데 .env.prod.example · compose · Route Handler 3곳에서 일관되게 처리**되어 있다(누수 경로 0).

**추가 추적성 확인**:
- PRD KPI 5개(적중률/배치정시/로딩/알림도달/커버리지) → launch-report B-1~B-4 전부 매핑.
- PRD FR-001~008, FR-012 → runbook §2.5 스모크 4종 + launch-report 데이터 소스 테이블이 각각 API/테이블로 접근 가능함을 재확인.

## 10. 최종 권고 — **배포 진행 (Approve with minor follow-up)**

### 권고 결정
**Phase 5 Ship → PASS. 배포 시작해도 좋다.** 운영자는 runbook §2.1~2.5를 그대로 실행하면 된다.

### 조건 (배포 절차에 포함)
1. **(first-push 전)** `.env.prod` 생성 시 `ADMIN_API_KEY`를 `openssl rand -hex 32`로 생성하고 `chmod 600` 적용. 서버 외부에 노출 금지.
2. **(Ship+48h)** reverse proxy + TLS 구축(Nginx/Caddy + Let's Encrypt) — ADMIN_API_KEY 평문 전송 회피. runbook §1 "선택" → "필수"로 격상 권장.
3. **(Ship+7)** `management.endpoints.web.exposure.include=health,metrics,prometheus` 활성화 → Week 1 스테빌리티 게이트에서 API P95 baseline 수집.
4. **(Ship+14)** `notification_log` 테이블 신설 + `logging.options max-size=10m/max-file=5` compose 반영.

### Sprint 5 킥오프 입력
launch-report G 섹션 v1.1 Top 5(Q1 텔레그램 스택트레이스 → Q2 타임존 → Q3 백테스트 400 → Q4 korean-holidays → Q5 TanStack Query)를 그대로 승계. 총 공수 약 5.5 인일.

### 반려 사유가 있다면
없음. 모든 블로커는 Verify 단계에서 이미 해소되었고, Ship 산출물의 감점은 전부 "측정·관측 공백"이지 "배포 안정성 결함"이 아니다.

---

**최종 점수 8.1 / 10 · 판정 PASS · 배포 가능 Y · 권고: 진행.**
