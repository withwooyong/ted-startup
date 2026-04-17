# Session Handoff

> Last updated: 2026-04-18 새벽 (로컬 Docker Desktop 스모크 테스트 완료, 커밋 완료, **로컬 푸시 대기**)
> Branch: `master` (origin/master 대비 **2 commits ahead**)
> Latest commit: `a89c6fe` — 세션 운영 문서·MCP 설정 현행화
> **Working tree**: clean
> **컨테이너 상태**: `ted-signal-db` / `ted-signal-backend` / `ted-signal-frontend` 모두 **healthy** (로컬 Docker Desktop 실행 중)

---

## Current Status

**v1.0이 로컬 Docker Desktop 환경에서 처음으로 E2E 동작 확인된 상태.** 이전 세션 HANDOFF의 "다음 세션 첫 액션"(로컬 스모크 테스트)을 실행해 3 컨테이너 모두 healthy + 5/5 스모크 테스트 HTTP 200 달성. 이 과정에서 runbook §2.5 test #4가 잘못된 HTTP method(GET 사용, 실제 Route Handler는 PUT 전용)를 명시하고 있음을 발견해 정정하고, 코드 리뷰 후 2 커밋으로 분리해 로컬 반영. 푸시는 사용자 명시 요청 전 대기. 다음 세션은 **push → Ship+48h P0(Reverse proxy+TLS)** 또는 **실제 VPS 이관**부터 착수 가능.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | `.env.prod` 실값 생성(`openssl rand`로 POSTGRES_PASSWORD/ADMIN_API_KEY 생성, 메모리 Telegram + 사용자 입력 KRX) + chmod 600 | *uncommitted (gitignored)* | .env.prod |
| 2 | 로컬 Docker Desktop 첫 배포 — 포트 3000 점유 중인 dev server(PID 76320) 종료 후 `docker compose up -d --build`로 3 컨테이너 기동 | (빌드만) | docker-compose.prod.yml |
| 3 | 스모크 테스트 5종 실행 (GET /, actuator/health, /api/signals, GET /api/notifications/preferences, PUT /api/admin/notifications/preferences) — 전부 HTTP 200. PUT 후 DB 원복 | (런타임 검증) | — |
| 4 | runbook §2.5 정정: GET→PUT + 유효 payload + test #0(ADMIN_API_KEY export) 추가 | `4a9d448` | runbook.md |
| 5 | 코드 리뷰(CRITICAL/HIGH 0건, MEDIUM 1건=M1 `ADMIN_API_KEY` export 안내 누락) → M1 반영 | `4a9d448` | runbook.md |
| 6 | 세션 운영 문서·MCP 설정 현행화 (settings.json MCP lockdown + .mcp.json 신규 + CHANGELOG/HANDOFF + context-budget-report) | `a89c6fe` | .claude/settings.json, .mcp.json, CHANGELOG.md, HANDOFF.md, docs/context-budget-report.md |

## In Progress / Pending

| # | Task | Priority / Deadline | Notes |
|---|------|--------|-------|
| 1 | 로컬 2 커밋 푸시 (`git push origin master`) | 사용자 결정 | `4a9d448` + `a89c6fe`, origin 대비 2 ahead. 커밋·푸시 분리 규칙 |
| 2 | Reverse proxy + TLS (Caddy/Nginx + Let's Encrypt) 구축 | P0 / Ship+48h | Judge Ship 리포트 권고 → 필수 격상. `ADMIN_API_KEY` 평문 전송 회피 |
| 3 | Spring Actuator metrics/prometheus exposure 활성화 | P0 / Ship+7d | `management.endpoints.web.exposure.include=health,metrics,prometheus` 1줄 수정. Week 1 P95/에러율 베이스라인 수집 |
| 4 | 실제 VPS 이관 (로컬 스모크 완료 → 동일 절차 반복) | 사용자 결정 | `.env.prod`를 VPS에 `scp` 또는 새로 생성 후 동일 명령 실행. VPS 스펙 권장: 2 vCPU / 4GB / 40GB SSD, Ubuntu 22.04 LTS |
| 5 | Flyway 도입 (V3+ 자동 마이그레이션) | P1 / v1.1 | 현재 V1/V2 SQL은 compose initdb로 최초 부팅 시 1회만 실행 |
| 6 | 프론트엔드 테스트 하네스 (Vitest + RTL + MSW) | P1 / v1.1 | QA 리포트 Top 권고 — 회귀 보호 부재 |
| 7 | TanStack Query 도입 (4개 페이지 리팩터) | P2 / v1.1 | `useEffect + fetch` 패턴 일소, F-M1 |
| 8 | 한국 공휴일 캘린더 연동 | P2 / v1.1 | `MarketDataPersistService.findPreviousTradingDate` TODO |
| 9 | 로컬 Docker 컨테이너 정리 (`docker compose down`) | 선택 | 볼륨 `ted-signal-prod-data`는 `down -v` 쓸 때만 삭제 — 유지 권장 |

## Key Decisions Made

- **옵션 B 채택 (dev server 종료 후 3000 유지)** — 로컬에서 이미 Next.js dev server(PID 76320)가 3000을 점유 중이었음. 포트 이동 대신 사용자가 dev 중단을 허가해 `FRONTEND_PORT=3000` 유지로 실배포 환경 1:1 시뮬레이션.
- **`.env.prod` 실값 생성 절차 표준화** — POSTGRES_PASSWORD는 `openssl rand -base64 24` (특수문자 가능 → 큰따옴표), ADMIN_API_KEY는 `openssl rand -hex 32` (64자 hex), Telegram은 메모리의 BEARWATCH 값 재사용, KRX는 사용자가 data.krx.co.kr에서 발급한 실키 입력. 파일 권한 600 강제.
- **커밋 분리 기준** — 본 세션 변경을 2 커밋으로 나눔. (A) runbook §2.5 문서 정정 = 배포 절차 영향이 있는 사실 수정. (B) 운영 메타(MCP lockdown + 세션 핸드오프 + 컨텍스트 예산 리포트) = 저장소 운영 관련 정리. "내용 성격이 다르면 커밋도 분리"가 리버트/체리픽 관리에 유리.
- **M1(ADMIN_API_KEY export 누락) 선반영 후 커밋** — 코드 리뷰에서 발견한 문서 결함을 **별도 후속 커밋**이 아니라 커밋 A에 같이 담아 runbook이 한 번에 완결되도록.
- **405 정상 동작 판정 근거** — `src/frontend/src/app/api/admin/notifications/preferences/route.ts`는 `PUT`만 export. 브라우저에서 읽기는 공개 `GET /api/notifications/preferences`(proxy.ts 경유)로 별도 라우팅. 2 경로 병기가 admin API의 의도된 구조.

## Known Issues

### MEDIUM (배포 후 개선)
- runbook §2.5 예시의 `curl -fsS -X PUT`은 400 응답(유효하지 않은 enum 등) 시 종료 코드 22로 실패. 스모크 테스트 스크립트화 시 `-f` 대신 HTTP 코드 체크 로직 추가 필요
- `docker-compose.prod.yml` backend healthcheck `start_period: 60s` — Spring Boot + initdb 동시 부팅 시 빠듯. 이번 로컬 기동은 통과했으나 저사양 VPS에서는 90~120s 권장
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

### 이번 세션 해결된 사항
- ✅ runbook §2.5 test #4 HTTP method 오류 (GET → PUT 정정)
- ✅ runbook §2.5 `ADMIN_API_KEY` export 안내 누락 (M1)
- ✅ 프로젝트 레벨 MCP 자동활성화 차단 (`enabledMcpjsonServers: []` + `.mcp.json` 빈 mcpServers)
- ✅ 로컬 Docker Desktop에서 v1.0 E2E 첫 배포 검증

## Context for Next Session

### 사용자 의도
- 이번 세션: 이전 HANDOFF의 "실제 VPS 배포 스모크 테스트" 권고를 **로컬 Docker Desktop에서 먼저** 수행. 시크릿 키 생성법부터 학습 — (1) 생성 → (2) 파일 작성 → (3) 기동 → (4) 스모크 → (5) 발견 이슈 수정 → (6) 리뷰 → (7) 커밋. 한 번에 풀 사이클을 직접 체험하려는 의도.
- **세션 말미에 `/handoff` 실행** — push 여부는 명시 안 함. 기본적으로 푸시는 별도 요청 규칙(~/.claude/CLAUDE.md).
- 문서 수정이 **배포 절차 정확성 향상에 기여**한다는 점을 명확히 인지. 스모크 테스트가 단순히 pass/fail이 아니라 runbook의 품질 지표로 돌아옴.

### 선택된 접근 방식
- **로컬 선행 → VPS 추후** — VPS 프로비저닝 없이도 동일 compose로 로컬 검증 가능하다는 점을 활용.
- **포트 충돌 회피보다 dev server kill** — 실배포와 동일한 3000 포트를 쓰는 게 장기적으로 더 정확하다는 판단. 사용자가 dev 중단을 명시 허가.
- **코드 리뷰를 문서 변경에도 적용** — 소스코드가 아니어도 리뷰 프로세스로 M1 결함 발견. `/everything-claude-code:code-review` 활용.

### 배포 동작 시뮬레이션 (현재 커밋 기준, 로컬 검증 완료)
- Browser → `GET /` → Next.js SSR 페이지 (16KB HTML) ✓
- Browser → `GET /api/signals` → `proxy.ts` → `http://backend:8080/api/signals` → `[]` ✓
- Browser → `GET /api/notifications/preferences` → `proxy.ts` → backend public ✓
- Browser → `PUT /api/admin/notifications/preferences` → Route Handler(X-API-Key 서버 부착) → backend 인증 경로 ✓
- backend actuator/health → `{"status":"UP"}` (컨테이너 내부) ✓

### 다음 세션 첫 액션 권고
1. **(선택) 2 커밋 푸시**: `git push origin master` — 사용자 명시 요청 시
2. **컨테이너 유지 상태 확인**: `docker compose --env-file .env.prod -f docker-compose.prod.yml ps` — 장기 구동 중이면 Telegram 알림 수신 확인 후 필요 시 `docker compose down`
3. **Ship+48h P0: Reverse proxy + TLS 구축** — `runbook.md §11 v1.1 로드맵` 중 Caddy 또는 Nginx + Let's Encrypt 추가. `ADMIN_API_KEY`가 평문 HTTP로 노출되지 않도록
4. **Ship+7d P0: Actuator 활성화** — backend `application-prod.yml`에 `management.endpoints.web.exposure.include=health,metrics,prometheus` 1줄 추가. 재배포
5. **(선택) 실제 VPS 이관** — 이번 세션과 동일 절차로 Ubuntu 22.04 VPS에 반복. `.env.prod`는 VPS에서 새로 생성 권장

### 제약/선호
- **Claude 모델**: Opus 4.7 (1M context) 단일 운영. Max 구독자.
- **Git 규칙**: 한글 커밋 메시지 / 커밋·푸시 분리 / `git push` 명시 요청 전 실행 금지.
- **커밋 메시지 스타일**: 한 줄 제목 + 빈 줄 + 여러 줄 본문 (bullet 또는 서술). 2 커밋으로 분리할 때는 내용 성격별.
- **Next.js**: v16.2.4 — training data와 다름. `node_modules/next/dist/docs/`로 확인. `middleware` → `proxy.ts` 파일 컨벤션.
- **프론트엔드 상태관리 컨벤션**: TanStack Query (서버) + Zustand (클라이언트) — 현재 미준수, v1.1 부채.
- **시크릿 처리**: `.env.prod`는 절대 커밋 금지 (gitignore:17). 생성 시 항상 `chmod 600`. 특수문자 포함 시 큰따옴표.
- **로컬 Docker Desktop**: v28.4.0, 정상 동작. Docker Compose v2 CLI 사용.

## Files Modified This Session

### 커밋 2건, 6 files, +348/-51
```
4a9d448  runbook §2.5 스모크 테스트 정정                      (1 file, +21/-2)
a89c6fe  세션 운영 문서·MCP 설정 현행화                       (5 files, +327/-49)
```

### 추가로 생성된 로컬 파일 (커밋 제외)
```
.env.prod                       (chmod 600, gitignore:17 — 실값 주입 완료)
Docker 이미지 2종:
  ted-signal-backend:latest     (Spring Boot 3.5.0 + Java 21, multi-stage)
  ted-signal-frontend:latest    (Next.js 16 standalone)
Docker 볼륨:
  ted-signal-prod-data          (Postgres 16 데이터, V1/V2 스키마 자동 적용)
```

### 빌드/런타임 검증 상태
- `docker compose build`: backend(48s Gradle resolve + 12s bootJar) + frontend 전부 성공
- `docker compose ps`: 3 컨테이너 모두 **(healthy)** — db 5432, backend 8080 (내부), frontend 3000 (호스트)
- 스모크 테스트: 5/5 HTTP 200
- 현재 DB 알림 설정: `dailySummaryEnabled=true, urgentAlertEnabled=true, batchFailureEnabled=true, weeklyReportEnabled=true, minScore=60, signalTypes=[RAPID_DECLINE, TREND_REVERSAL, SHORT_SQUEEZE]` (초기 상태 원복됨)

### 원격 동기화
- `origin/master` HEAD: `08b1012`
- 로컬 `master` HEAD: `a89c6fe`
- **2 commits ahead of origin** — 푸시 대기
