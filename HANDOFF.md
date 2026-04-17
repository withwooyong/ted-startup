# Session Handoff

> Last updated: 2026-04-17 (세션 종료, v1.0 배포 준비 완료, 전부 커밋·푸시 완료)
> Branch: `master` (origin/master와 동기화)
> Latest commit: `08b1012` — 세션 핸드오프: v1.0 배포 준비 완료 + H-1 fix 컨텍스트
> **Working tree**: clean

---

## Current Status

**v1.0 배포 직전 상태, 모든 변경 푸시 완료.** Phase 1~5 전체 파이프라인 통과 (Discovery 8.1 · Design 8.3 · Build sprint 1-4 · Verify 7.6 · Ship 8.1). 코드 리뷰에서 발견한 HIGH H-1(프론트/백엔드 env 변수명 불일치) 블로커까지 수정·병합·푸시 완료. 다음 세션은 실제 VPS 배포 스모크 테스트 또는 Ship+48h P0 권고 작업(Reverse proxy + TLS)부터 착수 가능.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | 프로토타입 효과 3종 Next.js 이식 (Aurora/CountUp/Magnetic) | `871ff57` | layout.tsx, page.tsx, globals.css, ui/AuroraBackground.tsx, ui/CountUp.tsx, ui/Magnetic.tsx |
| 2 | Phase 4 Verify 3 에이전트 병렬 (QA/Review/Security) + Judge 7.6 + 블로커 4건(B-C1/H1/H2/H3) 수정 | `eb5fc15` | MarketDataPersistService.java (신규), MarketDataCollectionService.java, api/admin/notifications/preferences/route.ts (신규), settings/page.tsx, client.ts, 4 artifacts |
| 3 | Phase 5 Ship: DevOps + Analytics + Ship Judge 8.1 | `764d6d3` | Dockerfile x2, docker-compose.prod.yml, .env.prod.example, .github/workflows/ci.yml, runbook.md, launch-report.md, ship-judge-evaluation.md, next.config.ts, .gitignore |
| 4 | 코드 리뷰 재검증 HIGH H-1 수정 (env 정합 + Next.js 16 proxy.ts + body guard + Dockerfile M-1) | `ef8c267` | proxy.ts (신규), next.config.ts, route.ts, client.ts, backend Dockerfile |
| 5 | 세션 핸드오프 문서 현행화 | `08b1012` | CHANGELOG.md, HANDOFF.md, docs/sprint-4-plan.md |

## In Progress / Pending

| # | Task | Priority / Deadline | Notes |
|---|------|--------|-------|
| 1 | Reverse proxy + TLS (Caddy/Nginx + Let's Encrypt) 구축 | P0 / Ship+48h | Judge Ship 리포트 권고 → 필수 격상. `ADMIN_API_KEY` 평문 전송 회피 |
| 2 | Spring Actuator metrics/prometheus exposure 활성화 | P0 / Ship+7d | `management.endpoints.web.exposure.include=health,metrics,prometheus` 1줄 수정. Week 1 P95/에러율 베이스라인 수집 |
| 3 | 실제 VPS 배포 스모크 테스트 | 사용자 결정 | `.env.prod` 실값 입력 → `docker compose -f docker-compose.prod.yml up -d --build` → runbook.md §5 테스트 |
| 4 | Flyway 도입 (V3+ 자동 마이그레이션) | P1 / v1.1 | 현재 V1/V2 SQL은 compose initdb로 최초 부팅 시 1회만 실행 |
| 5 | 프론트엔드 테스트 하네스 (Vitest + RTL + MSW) | P1 / v1.1 | QA 리포트 Top 권고 — 회귀 보호 부재 |
| 6 | TanStack Query 도입 (4개 페이지 리팩터) | P2 / v1.1 | `useEffect + fetch` 패턴 일소, F-M1 |
| 7 | 한국 공휴일 캘린더 연동 | P2 / v1.1 | `MarketDataPersistService.findPreviousTradingDate` TODO |

## Key Decisions Made

- **블로커 4건 즉시 수정 경로 선택 (Judge 권고 C-1)** — CRITICAL B-C1(`NEXT_PUBLIC_ADMIN_API_KEY` 번들 노출)이 관리자 API 4개를 공개 상태로 만들어서, 배포 후 수정보다 사전 수정이 리스크 낮음. 3 HIGH 포함 총 4건 해결 후 Approval #3 가결.
- **Admin API 서버 릴레이 방식 채택** — Next.js Route Handler (`/api/admin/notifications/preferences/route.ts`)가 서버 측 `ADMIN_API_KEY`로 backend에 프록시. `NEXT_PUBLIC_` 제거. MVP에서 user login 없이 서버 사이드로 키 보관.
- **Backend 트랜잭션 분리 패턴** — `persistAll`을 `MarketDataPersistService` 별도 빈으로 분리해 Spring AOP 자기호출 프록시 우회 문제 해결. SRP 원칙 준수와 병행.
- **배치 멱등성: skip 전략** — `(stock_id, trading_date)` 기존 레코드를 1회 조회하여 중복 INSERT 스킵. `upsert`는 `LendingBalance` `changeRate` 재계산 로직 때문에 복잡하므로 skip이 단순/안전.
- **프로토타입 이식 범위 축소 (Aurora/CountUp/Magnetic 3종만)** — prototype/index.html에 있는 Tilt/Spotlight/Particle은 복잡도 대비 체감 효과 애매. 3종만 이식하고 Tilt/Particle은 v1.1 백로그로 연기.
- **내부 MVP 전제 배포 인프라** — AWS Terraform 대신 단일 VPS용 Docker Compose. Ship Judge가 v1.1 AWS 이관 5-step 체크리스트만 runbook에 문서화.
- **`rewrites` 대신 `proxy.ts`** — Next.js `next.config.ts` rewrites는 build time에 routes-manifest.json으로 고정되어 런타임 env 반영 불가. Next.js 16 canonical `proxy.ts` 파일 컨벤션 사용(구 middleware 대체). 매 요청 `process.env.BACKEND_INTERNAL_URL` 평가.

## Known Issues

### MEDIUM (배포 후 개선)
- `docker-compose.prod.yml` backend healthcheck `start_period: 60s` — Spring Boot + initdb 동시 부팅 시 빠듯. 90~120s 권장
- CI `lint continue-on-error: true` — 장기적으로 false 전환
- Route Handler upstream이 non-JSON일 때 client.ts가 `res.json()` 실패 가능성
- 배치 `findAllByTradingDate` 3회 JOIN FETCH로 7,500 엔티티 로드 (존재 확인만 필요) — exists / id-only projection로 전환 가능

### LOW (v1.1 백로그)
- 프론트 `client.ts` AbortSignal 미전파 — 빠른 네비게이션 시 좀비 요청
- `CountUp.tsx` prop 1개 변경만으로 애니메이션 전체 재시작 — `value` 외 prop memo 분리 가능
- `Magnetic.tsx` reducedMotion 미디어쿼리 변경 이벤트 미구독 (페이지 진입 시 1회만)
- CI `docker-build` registry push 없음 — GHCR/ECR 결정 후 활성화
- Flyway 미설치 (v1.1 P1)
- Docker registry 미확정
- 한국 공휴일 캘린더 미적용
- lockfile 중복 경고 (`~/package-lock.json`)

### 이번 세션 해결된 블로커
- ✅ CRITICAL B-C1: `NEXT_PUBLIC_ADMIN_API_KEY` 번들 노출
- ✅ HIGH B-H1: `MarketDataCollectionService` 자기호출 트랜잭션 무효
- ✅ HIGH B-H2: `persistAll` 데드 코드
- ✅ HIGH B-H3: 배치 재실행 유니크 제약 충돌
- ✅ HIGH H-1: env 변수명 3중 불일치 — `NEXT_PUBLIC_API_BASE_URL` + `BACKEND_INTERNAL_URL` 단일화

## Context for Next Session

### 사용자 의도
- 이번 세션: 이전 세션 핸드오프의 "다음 할일"(B → A 순서) 실행 — (B) 프로토타입 효과 Next.js 이식 + (A) Phase 5 Ship.
- 최종적으로 v1.0 배포 직전 상태를 원함. **Judge PASS 후 코드 리뷰 재검증까지 요청한 건, 배포 전 마지막 검증을 원한다는 신호.**
- 사용자 커밋 철학: 한글 메시지 + 푸시는 명시 요청 시에만. 커밋과 푸시를 분리. 이번 세션 말미에 "커밋/푸시하자" 명시 후 push 완료.

### 선택된 접근 방식
- **3-에이전트 병렬 Verify** (QA + Code Review + Security) → Judge 종합 평가 → 블로커 수정 → 재검증 → 승인 #3
- **2-에이전트 Ship** (DevOps + Analytics) 병렬 → Ship Judge → `status: deployed`
- **코드 리뷰 후 /ted-run 파이프라인**으로 H-1 수정. Next.js 16 canonical `proxy.ts` 채택(build-time baking 이슈 회피).

### 배포 동작 시뮬레이션 (현재 커밋 기준)
- Browser → `GET /api/signals` → Next.js `proxy.ts` → rewrite `http://backend:8080/api/signals` ✓
- Browser → `PUT /api/admin/notifications/preferences` → Route Handler(X-API-Key 추가) → `http://backend:8080/api/notifications/preferences` ✓
- Dev(env 미설정) → `http://localhost:8080` fallback ✓

### 다음 세션 첫 액션 권고
1. **실제 VPS에서 첫 배포 스모크 테스트**
   - `cp .env.prod.example .env.prod` → 실값(`POSTGRES_PASSWORD`, `ADMIN_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `KRX_AUTH_KEY`) 입력
   - `chmod 600 .env.prod`
   - `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`
   - runbook.md §5 스모크 테스트 — `curl http://localhost:3000/`, `/api/signals`, `/api/admin/notifications/preferences` 등
2. **Ship+48h P0 작업**: Reverse proxy + TLS 구축. `runbook.md §1` 선택 → 필수 격상.
3. **Ship+7d P0 작업**: Spring Actuator `management.endpoints.web.exposure.include=health,metrics,prometheus` 1줄 수정 → Week 1 베이스라인 수집.
4. **(선택) v1.1 시작**: Flyway / 프론트 테스트 / TanStack Query 중 우선순위 결정.

### 제약/선호
- **Claude 모델**: Opus 4.7 (1M context) 단일 운영. Max 구독자.
- **Git 규칙**: 한글 커밋 메시지 / 커밋·푸시 분리 / `git push` 명시 요청 전 실행 금지.
- **Next.js**: v16.2.4 — training data와 다름. `node_modules/next/dist/docs/`로 확인 후 작업 (AGENTS.md 지시). `middleware` 파일 컨벤션은 `proxy.ts`로 개명됨.
- **프론트엔드 상태관리 컨벤션**: TanStack Query (서버) + Zustand (클라이언트) — 현재 미준수, v1.1 부채.
- **Reduced motion / Coarse pointer**: 애니메이션 훅들(`Magnetic`, `CountUp`)에 모두 media query guard 적용 완료.

## Files Modified This Session

### 커밋 5건, 31 files, +2,548 / -197
```
871ff57  프로토타입 효과 3종 Next.js 이식                       (6 files, +271/-30)
eb5fc15  Phase 4 Verify + 블로커 4건 수정                       (10 files, +1013/-158)
764d6d3  Phase 5 Ship 완료 (Judge 8.1)                          (11 files, +1210/-8)
ef8c267  코드 리뷰 H-1 fix + proxy.ts 도입                       (5 files, +60/-7)
08b1012  세션 핸드오프 문서 현행화                              (3 files, +143/-150)
```

### 빌드 검증 상태
- `next build`: 6 pages + Proxy + Route Handler `/api/admin/notifications/preferences` 모두 성공
- `./gradlew test`: 29/29 통과

### 원격 동기화
- `origin/master` HEAD: `08b1012` (push 완료)
- Working tree: clean
