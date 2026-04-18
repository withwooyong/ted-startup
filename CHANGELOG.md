# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/).

## [Unreleased]

---

## [2026-04-18 — 새벽] P13-1 DART 벌크 sync 스크립트 + P13-2 운영 보안 M1~M4 + 실측 검증 (`43f07fd` … `1c27c65`)

수동 시드 3건에 머물던 `dart_corp_mapping` 을 전체 bulk sync 할 수 있는 CLI 스크립트를 구현하고, 이전 세션에서 carry-over 된 운영 보안 4건(M1 /metrics IP 게이팅 · M2 /health 마스킹 · M3 uv digest 고정 · M4 nologin 셸)을 일괄 처리. backend 재빌드 + Caddy reload 후 실 환경에서 **DART API 호출**과 **외부/내부 경로 차단 동작**을 실측 검증 완료.

### Added
- **`DartClient.fetch_corp_code_zip()`**(`43f07fd`): DART `/api/corpCode.xml` ZIP 바이너리 다운로드. `PK\x03\x04` 매직으로 성공 분기, JSON 바디는 `DartUpstreamError` 승격. 읽기 타임아웃 60초(수 MB 전송 고려), tenacity 3회 재시도.
- **`scripts/sync_dart_corp_mapping.py`**(`43f07fd`): CLI 진입점. `--dry-run` / `--batch-size` 옵션. 필터 2단: ① 종목코드 6자리 + 끝자리 `0` (보통주) ② 이름에 스팩·기업인수목적·리츠·부동산투자회사·인프라투융자회사·ETF·ETN·상장지수 미포함. 500건 배치 upsert.
- **`/internal/info` 엔드포인트**(`1c27c65`): app/env 상세 응답. Caddy 에서 `/internal/*` 차단하므로 Docker 네트워크 내부에서만 접근.
- **신규 테스트 31건**(`43f07fd`): 필터 파라미터라이즈 (보통주/우선주/스팩/리츠/ETF 경계값) + ZIP/XML 파싱 + `fetch_corp_code_zip` httpx.MockTransport 3종.

### Changed
- **`/health` 응답 본문 마스킹**(`1c27c65`): `{"status":"UP","app":...,"env":...}` → `{"status":"UP"}` 만. 운영 메타는 `/internal/info` 로 이동.
- **Caddy `/metrics`, `/internal/*` 외부 404**(`1c27c65`): `@blocked` matcher + `handle` 블록. frontend 프록시 경로와 무관하게 defense-in-depth.
- **uv 이미지 digest 고정**(`1c27c65`): `ghcr.io/astral-sh/uv:0.11` → `@sha256:240fb85a…516a` (multi-arch index). 공급망 공격 방어. 업그레이드 절차 주석 명시.
- **appuser 로그인 셸**(`1c27c65`): `/bin/bash` → `/usr/sbin/nologin`. login/su/sshd 경로 차단.

### Verified (실측)
- **E: DART 벌크 sync `--dry-run`** — 실 API 호출 성공. ZIP 3.5 MB · 전체 116,503 법인 → stock_code 보유 3,959건 → 필터 통과 **3,654건**. 샘플 10건 출력에서 과거 상장폐지 종목이 다수 혼재 확인(예상보다 많은 이유: corpCode.xml 이 폐지 이력도 유지).
- **F-1/F-2: 외부 차단** — `curl -k https://localhost/metrics` → HTTP 404 · `/internal/info` → HTTP 404. Caddy `@blocked` matcher 동작 확인.
- **F-3: 내부 응답 분리** — 컨테이너 내부에서 `/health` = `{"status":"UP"}`, `/internal/info` = `{"status":"UP","app":"ted-signal-backend","env":"prod"}` 정상.
- **F-4: nologin 적용 범위** — `/etc/passwd` 에 `/usr/sbin/nologin` 확인. `docker exec backend /bin/bash` 는 여전히 실행됨(설계 범위 밖 — nologin 은 login/su/sshd 경로 차단 전용). MVP 단계 적정.

### Observed (차후 개선)
- **Docker Desktop bind mount 휘발성** — 에디터의 rename-on-save 로 inode 가 바뀌면 컨테이너 mount 가 stale. Caddy reload 전에 **컨테이너 재시작 필수**(`docker compose restart caddy`). Caddyfile 수정 절차에 반영 필요.
- **상장폐지 종목 혼재** — `dart_corp_mapping` 에 과거 폐지 종목도 포함. AI 리포트 대상은 실제 호출자가 현재 상장 종목만 쿼리하므로 실사용 영향 없음. 필요 시 KRX 현재 상장 리스트와 교차 필터 추가 가능.

---

## [2026-04-18 — 심야] 실 E2E 검증 + 3건의 크리티컬/MEDIUM 버그 수정 (`2febdf2` … `510fa1c`)

`.env.prod` 의 실 DART/OpenAI/KIS 모의 키로 `docker compose --env-file .env.prod up -d --build` 풀 재빌드 후 엔드투엔드 검증. 포트폴리오 계좌 생성 → 수동 거래 → KIS 모의 동기화(OAuth+VTTC8434R) → **삼성전자 AI 리포트 실생성 (gpt-4o, 6.3초, 18524/530 토큰, DART 공시 5건 자동 소스 보강)** 까지 풀 체인 성공. 2차 호출 `cache_hit=true` 0.02초. 검증 과정에서 발견한 3건의 실버그를 같은 세션에 수정·검증 완료.

### Fixed
- **CRITICAL: entrypoint.py 레거시 경로가 003/004/005 누락**(`2febdf2`): `alembic_version` 없고 `stock` 있는 레거시 Java Flyway DB 에서 `stamp head` 만 실행 → P10~P13b 의 portfolio_* / dart_corp_mapping / analysis_report 5 테이블이 생성되지 않음. 수정: `stamp 002_notification_preference` (V1+V2 완료 마킹) → `upgrade head` (003/004/005 적용). Phase 7 E2E 테스트(testcontainers fresh DB) 가 stamp 경로를 타지 않아 놓친 사각지대. runbook §2.4 동시 갱신.
- **MEDIUM: `scripts/validate_env.py` KIS 계좌번호 기준 느슨**(`2febdf2`): `acct_digits >= 8` → 8자리도 PASS. 어댑터 실요구는 CANO(8) + ACNT_PRDT_CD(2) = `== 10`. 거짓 음성 버그. 수정: `== 10` 으로 정확히 + 미달/초과별 안내 메시지.
- **CRITICAL: REPORT_JSON_SCHEMA sources.items 의 required 에 `published_at` 누락**(`510fa1c`): OpenAI strict mode 는 `required` 배열에 **모든** properties 키가 포함되어야 함. `/chat/completions` 가 HTTP 400 "Missing 'published_at'" 으로 거부해 리포트 생성 실패. 수정: required 에 published_at 추가 (type: [string, null] 로 이미 nullable 선언).

### Known Outcomes (E2E 검증 통과)
- 관리자 릴레이: `POST /api/admin/portfolio/accounts` 201 (Caddy HTTPS + Next.js Route Handler + backend 경로 전체 동작)
- 포트폴리오 거래 등록: 매수 10주@72000 → `GET /holdings` 200 (평단·수량 정확)
- KIS 모의 동기화: OAuth client_credentials 토큰 발급 → VTTC8434R 잔고 조회 rt_cd=0 → `fetched_count=0` (모의 잔고 없음, 정상 응답)
- AI 리포트 실생성: gpt-4o 모델 · 6.3초 · 토큰 18,524↓/530↑ · opinion=HOLD · sources 7건 전부 Tier1 (DART 공시 5 + 공식 홈페이지) · 자동 소스 보강 검증 · 24h 캐시 2차 호출 0.02s
- 레거시 DB 위에서 entrypoint 자동 마이그레이션 003/004/005 적용 확인

---

## [2026-04-18 — 저녁~밤] Phase 8/9 마무리 + §11 신규 도메인(P10~P15) + 프론트 UI + 리뷰 대응 (`24b43ba` … `7f4f3d1`)

이전 세션에서 Phase 1~7 으로 Java→Python 런타임 이전을 마친 데 이어, 본 세션은 **Phase 8/9 정리 + §11 (포트폴리오·AI 분석 리포트) 신규 도메인 전체 + 프론트 UI + 코드 리뷰 대응** 을 단일 세션에 완결. 커밋 12개 · 약 +7,120 / -5,141 라인 (Java 삭제 4,710 포함) · 백엔드 98/98 PASS · mypy strict 0 · ruff 0 · 프론트 build/tsc/lint clean.

### Removed
- **Phase 8 — Java 스택 물리 제거**(`24b43ba`): `src/backend/` 디렉토리 전량 삭제 (Spring Boot 3.5 + Java 21 + Gradle + 테스트 69개 포함 4,710 라인). 2026-04 Java→Python big-bang 이전 완결. Python 52/52 PASS 로 대체 검증 완료.

### Added
- **Phase 9 — 기술스택 문서/에이전트 Python 전환**(`005011e`): `CLAUDE.md` Tech Stack 표 + Backend Conventions(PEP 8·ruff·mypy strict·Pydantic v2·SQLAlchemy 2.0 async·APScheduler) + Key Design Decisions 전면 재작성. `docs/design/ai-agent-team-master.md` 기술 스택 확정 표 FastAPI/Python 전환 + Part V(부록 I~L, Java 21 Virtual Threads/JPA/QueryDSL) **역사적 기록·비활성** 배너 부착. `agents/08-backend/AGENT.md` 전면 재작성. `pipeline/artifacts/10-deploy-log/runbook.md` 내부 포트 8080→8000, /actuator/health→/health, Flyway→Alembic + entrypoint, KRX_AUTH_KEY→KRX_ID/KRX_PW 등 갱신.
- **P10 — 포트폴리오 도메인**(`97203c2`, +1,439): Alembic 003 (brokerage_account/portfolio_holding/portfolio_transaction/portfolio_snapshot 4 테이블 + UNIQUE/CHECK/인덱스). 모델 4종 + Repository 4종 + UseCase 4종 (RegisterAccount/RecordTransaction(가중평균 평단가)/ComputeSnapshot/ComputePerformance — pandas cummax/pct_change 벡터 연산으로 MDD·Sharpe). FastAPI 라우터 7 엔드포인트. 테스트 11 케이스.
- **P11 — KIS 모의투자 REST 연동**(`c003fc8`, +774): `KisClient` (httpx + OAuth2 `client_credentials` 토큰 캐시·300초 전 자동 재발급, TR_ID VTTC8434R 모의 전용, 실거래 URL 진입 차단, tenacity 재시도). `SyncPortfolioFromKisUseCase` — connection_type='kis_rest_mock' + environment='mock' 이중 검증, 잔고→holding 직접 upsert. Settings 에 KIS_APP_KEY_MOCK/SECRET/ACCOUNT + base_url 하드코드. 테스트 9 케이스.
- **P12 — 포트폴리오↔시그널 정합도 리포트**(`11e80c2`, +343): `SignalRepository.list_by_stocks_between` — IN + 기간 + min_score 복합 쿼리로 N+1 회피. `SignalAlignmentUseCase` — 종목별 max_score·hit_count 집계·정렬. `GET /api/portfolio/accounts/{id}/signal-alignment` 라우터. 테스트 5 케이스.
- **P13a — DART OpenAPI Tier1 어댑터**(`b2c20f4`, +711): Alembic 004 (`dart_corp_mapping` — KRX 6자리↔DART 8자리 매핑). `DartClient` — fetch_company/fetch_disclosures/fetch_financial_summary 3 엔드포인트, status='000'|'013' 만 통과 (그 외 `DartUpstreamError` 승격), 괄호 표기 음수·천단위 쉼표 Decimal 안전 변환, populate_existing upsert 패턴. 테스트 9 케이스.
- **P13b — AI 분석 리포트 파이프라인**(`caf8355`, +1,484): Alembic 005 (`analysis_report` JSONB content/sources, (stock_code, report_date) UNIQUE 로 24h 캐시). `LLMProvider` Protocol (`app/application/port/out/llm_provider.py`) + Tier1/Tier2 dataclass + REPORT_JSON_SCHEMA strict JSON. `OpenAIProvider` (Plan B, httpx `/v1/chat/completions` + `response_format=json_schema`, 역할 분리 시스템 프롬프트 "숫자는 Tier1 만, 정성은 Tier2 만 인용"). `AnalysisReportService` — 24h 캐시 조회 → dart_corp_mapping 해결 → DART 3종(company/disclosures 90d/financials 전년 CFS) + KRX 가격·시그널 Tier1 수집 → provider.analyze → 자동 소스 보강(공식 홈페이지 + 최근 공시 3건) → upsert. `POST /api/reports/{stock_code}` 라우터 (Admin Key 보호, force_refresh 쿼리, 404/400/502 매핑). 테스트 9 케이스.
- **P14 — 프론트 포트폴리오·AI 리포트 UI**(`3cd5c75`, +1,349): Next.js 16 + React 19. `/portfolio` (계좌 스위처 + 4 지표 카드 + 스냅샷/KIS 동기화 액션 + 보유 테이블 + AI 리포트 바로가기), `/portfolio/[accountId]/alignment` (시그널 정합도 상세, 스코어 슬라이더 필터), `/reports/[stockCode]` (AI 리포트 본문 — BUY/HOLD/SELL 컬러 뱃지, 강점/리스크 2열, 출처 Tier1/2 뱃지 + 외부 링크, 재생성 버튼). 제네릭 Route Handler `/api/admin/[...path]` (GET/POST/PUT/DELETE/PATCH, ADMIN_API_KEY 서버 측 부착, 64KB 본문 상한). API 클라이언트 2 (portfolio/reports) + 타입 2 (portfolio/report, snake_case 백엔드 정렬). NavHeader 에 '포트폴리오' 메뉴 추가.
- **P15 — 키움 REST 가용성 조사**(`7f4f3d1`, +177): `docs/research/kiwoom-rest-feasibility.md` — 문서 스파이크 전용 (구현 없음). 2026-04 공식 도메인 `openapi.kiwoom.com`, 모의 `mockapi.kiwoom.com`, Python SDK `kiwoom-rest-api` 0.1.12 미성숙 확인. KIS vs 키움 11항목 비교 매트릭스. **결론: No-Go**. Go 조건 3/3 (개인 키움 계좌 수요 + SDK 0.2+ 성숙 + KIS 어댑터 계약 고정) 충족 시 재평가. 플랜 §11.1 의 `developers.kiwoom.com` 오기 정정.

### Fixed
- **P13b 리뷰 fix**(`185dfaf`): mypy strict HIGH 5 (cast dict[str, Any], list[ReportSource] 제네릭, -> ReportSource 반환 타입) + 보안 MEDIUM 4 (`is_safe_public_url` 유틸로 javascript:/ftp:/file: 스킴 차단, OpenAI 에러 본문 외부 누설 제거 — body 는 logger.warning 만, `openai_base_url` HTTPS 스킴 강제로 SSRF 차단, `<tier1_data>`/`<tier2_data>` XML-like fence 로 프롬프트 인젝션 완화). 테스트 3 케이스 추가.
- **P14 리뷰 fix**(`c008592`): HIGH 3 (릴레이 path 세그먼트 `^[A-Za-z0-9_\-.]+$` allowlist + `.`/`..` 명시 거부 — undici collapse 로 /api/ 스코프 탈출 SSRF 차단, reports 페이지 `cancelled` 플래그 + `refreshTick` idempotent 재생성 패턴으로 race 제거, `SourceRow` `safeHref` 로 javascript: URI 브라우저 실행 차단) + MEDIUM 4 (refreshCurrent 에러 투명 전파, `aria-label` 새 탭 안내, `ADMIN_BASE`/adminCall 공용 헬퍼 추출, accountId NaN 가드).

### Changed
- **cleanup: mypy strict 0 · ruff 0 · frontend 타입 스키마 정합**(`51bfe10`, +332/-232): 백엔드 mypy 23→0, ruff 17→0. `pandas-stubs`/`types-python-dateutil` dev deps. StrEnum 4종 전환. Repository 공용 `rowcount_of()` 헬퍼. 외부 클라이언트 forward-ref 따옴표 제거(UP037). KIS/DART Any 반환 isinstance/cast 좁히기. market_data_job 파라미터 full 타입 힌트. 프론트 `signal.ts`/`SignalCard`/`page.tsx`/`stocks/[code]/page.tsx`/`backtest/page.tsx` snake_case 백엔드 응답과 정렬, `SignalDetail` + `detailNumber()` JSONB 안전 접근, `StockDetail` 가짜 `latestPrice/timeSeries` 구조 → 실제 `stock{}/prices[]` 로 정정, CountUp `queueMicrotask` 로 React 19 린트 해소.

### Known Issues / Follow-up
- `POST /api/reports/{stock_code}?force_refresh=true` 에 rate limiting 없음 — 관리자 키만으로 LLM 호출 폭주 가능. `slowapi` 도입 권고 (리뷰 LOW).
- 실 E2E 검증 미완: `.env.prod` 의 실 DART/OpenAI/KIS 키로 브라우저에서 `/portfolio` → AI 리포트 생성까지 1회 검증 필요.

---

## [2026-04-18 — 오후~저녁] Java→Python 전면 이전 Phase 1~7 일괄 완료 (`c417977` … `610918a`)

본 세션의 주제: **Spring Boot 3.5 + Java 21** 백엔드를 **FastAPI + Python 3.12** 로 전면 이전.
사전-운영 단계라는 결정적 이점으로 big-bang 재작성 경로를 선택. 18 영업일 추정 중 ~7일 분량을 진행.
전체 52/52 PASS · 로컬 Docker 스모크 확인 · 커밋 13회 · 약 7,400+ 라인 신규.

### Added
- **작업계획서 확정**(`f66cfdd`): `docs/migration/java-to-python-plan.md` — 9 결정 잠금, §11 포트폴리오 + AI 분석 스코프, Perplexity+Claude Plan A / OpenAI GPT-5.4 단독 Plan B 구분, DART+KRX+ECOS Tier1 / web_search 화이트리스트 Tier2 신뢰 출처 3-Tier 설계. 루트 `.env.prod.example` DOMAIN/ACME_EMAIL/DART/OPENAI/KIS 변수 확장.
- **환경변수 검증 스크립트**(`cb5bd24`): `scripts/validate_env.py` — `.env.prod` 의 DART/OpenAI/KIS 키를 API 실호출로 검증. 키 값 절대 로그에 노출되지 않도록 pykrx 내부 print 까지 `contextlib.redirect` 로 차폐.
- **KRX 계정 유효성 검증 스크립트**(`127625d`): `scripts/validate_krx.py` — pykrx 로그인 + OHLCV·공매도·대차잔고 수신 실측.
- **픽스처 베이스**(`cb5bd24`): `pipeline/artifacts/fixtures/` — `capture_krx.py` + 합성 JSON 3종 + Telegram 모의본 + KRX 익명 차단 블로커 문서.
- **Phase 1 Python 백엔드 스캐폴딩**(`e669fed`): `src/backend_py/` Hexagonal 구조, uv + FastAPI + pydantic-settings + prometheus-fastapi-instrumentator + structlog + pytest + ruff + mypy strict, Dockerfile (python:3.12-slim 멀티스테이지 + 비루트 uid 1001). Health/CORS 테스트 6종.
- **Phase 2 DB 계층**(`f00b2cf`): SQLAlchemy 2.0 async + asyncpg(런타임) + psycopg2(마이그레이션), Alembic V1/V2 리비전 이식, 모델 7종(Stock/StockPrice/ShortSelling/LendingBalance/Signal/BacktestResult/NotificationPreference) + Repository 7종, testcontainers PG16 통합 테스트 7종, macOS Docker Desktop 소켓 자동 감지.
- **Phase 3 외부 어댑터**(`e9f3c75`): `KrxClient` (pykrx async 래퍼 + asyncio.Lock + 2초 rate limit + stdout 차폐 + tenacity 재시도), `TelegramClient` (httpx AsyncClient + HTML parse_mode + no-op fallback). 어댑터 테스트 8종.
- **Phase 4 UseCase/서비스**(`3724d1e`): `MarketDataCollectionService`, `SignalDetectionService` (pandas rolling MA 벡터화), `BacktestEngineService` (피벗 테이블 + shift(-N) 벡터 리라이트 — Java TreeMap 순회를 행렬 1회 연산으로 대체), `NotificationService`. Port Protocol 정의. pandas/numpy/vectorbt 의존성 추가. 서비스 통합 테스트 5종.
- **Phase 5 API 계층**(`31ea518`): `app/adapter/web/` — FastAPI 라우터 8개(GET `/api/signals`, GET `/api/stocks/{code}`, POST `/api/signals/detect`, GET·POST `/api/backtest`, GET·PUT `/api/notifications/preferences`, POST `/api/batch/collect`), Admin API Key `hmac.compare_digest` timing-safe 검증, RequestValidationError → 400 통일 응답. 라우터 통합 테스트 14종.
- **Phase 6 배치**(`65b4bb6`): `app/batch/trading_day.py` (주말 제외), `market_data_job.py` (3-Step 오케스트레이션 — collect → detect → notify, 각 Step 독립 세션·트랜잭션), `scheduler.py` (AsyncIOScheduler CronTrigger mon-fri KST 06:00, max_instances=1, coalesce=True), FastAPI lifespan 연동. 배치 테스트 7종.
- **Phase 7 컨테이너 전환**(`b5e3cc8`): `scripts/entrypoint.py` — alembic_version/stock 테이블 존재 여부로 `stamp head` vs `upgrade head` 분기 후 `os.execvp` 로 uvicorn 전환(PID 1 유지). E2E 플로우 테스트 2종(`/api/batch/collect` → `/api/signals/detect` → GET `/api/signals` 체인).

### Changed
- **운영 설정 소소한 정리**(`c417977`): `ops/caddy/Caddyfile` X-Forwarded-* header_up 중복 제거, `docker-compose.prod.yml` Caddy 헬스체크 `localhost:2019/config/` 로 단순화, `src/backend/src/main/resources/application.yml` management.endpoint.health.show-details 및 management.prometheus.* 중복 설정 제거.
- **docker-compose.prod.yml Python 전환**(`b5e3cc8`): backend 서비스 build context `./src/backend` → `./src/backend_py`, 환경변수 Spring 계열 제거 + DATABASE_URL(asyncpg DSN) / KRX_ID/KRX_PW / DART/OPENAI/KIS / SCHEDULER_ENABLED=true 추가, healthcheck `/actuator/health` → `/health` 전환(curl 대신 python urllib), frontend BACKEND_INTERNAL_URL 포트 8080→8000, db initdb Java migration mount 제거(Alembic 전담), Caddyfile 주석 포트 8080→8000.
- **CORS 보안 설계**(`e669fed` 이후 유지): 빈 화이트리스트면 미들웨어 미탑재, `"*"` + credentials 조합 코드상 차단.
- **NotificationPreferenceRepository**(`31ea518`): `save()` 이후 `session.refresh()` 로 server_default `updated_at` 동기화 — Pydantic model_validate 중 MissingGreenlet 회피.
- **app/adapter/in/web/** → **app/adapter/web/**(`31ea518`): Python 예약어 `in` 때문에 `from app.adapter.in.web...` 파싱 실패 → 경로 평탄화.

### Fixed
- **코드 리뷰 H1·M1·M4 (Phase 4 후)**(`bda6e42`): NotificationService N+1 쿼리 제거(`StockRepository.list_by_ids` IN 쿼리 1회), SignalDetectionService `_trend_reversal` 의 `is None` 죽은 조건 제거(pd.isna 일원화), Telegram 메시지에 `html.escape` 적용 + 영문 enum → 한글 라벨("대차잔고 급감"/"추세전환"/"숏스퀴즈"). 회귀 테스트 3종 추가.
- **코드 리뷰 M1·M2·M3 (Phase 7 후)**(`610918a`): entrypoint uvicorn `--forwarded-allow-ips "*"` → Docker 사설 대역(127.0.0.1,10/8,172.16/12,192.168/16), `FORWARDED_ALLOW_IPS` env 로 오버라이드 가능. 스케줄러 `date.today()` → `datetime.now(KST).date()` 로 TZ 명시화. market_data_job 의 죽은 코드 `detected_signal_ids` 블록 삭제(DB 쿼리 1회 절감).

### Known Issues (Carry-over)
- **KRX 익명 접근 차단(2026-04 확인)**: `data.krx.co.kr` 가 익명 요청을 `HTTP 400 LOGOUT` 으로 거부. pykrx 도 `KRX_ID/KRX_PW` 요구로 전환 완료. 프로덕션 Java 배치가 수개월간 실제 데이터를 못 가져오고 있었음(DB 3개 테이블 0 rows 로 확인). 사용자가 회원가입 후 `.env.prod` 에 `KRX_ID/KRX_PW` 주입, `scripts/validate_krx.py` 로 OHLCV 2879종목 + 공매도 949종목 수신 확인. 대차잔고는 pykrx 스키마 불일치로 0 rows → Phase 3 어댑터에서 예외 격리 + fallback 경고 로그, 본격 복구는 후속 작업.
- **Phase 8/9 미완**: `src/backend/` Java 스택 물리 제거, `docs/design/ai-agent-team-master.md` 기술스택 표, `CLAUDE.md` Backend Conventions, `agents/08-backend/AGENT.md`, `pipeline/artifacts/10-deploy-log/runbook.md` 갱신이 남아 있음.

---

## [2026-04-18 — 새벽] 로컬 Docker Desktop 첫 배포 스모크 테스트 + runbook 정정 + MCP lockdown (`4a9d448`, `a89c6fe`)

### Added
- `.mcp.json` (신규): 빈 `mcpServers`로 프로젝트 스코프 MCP 기본값 잠금 — 외부 MCP 서버 주입 차단
- `docs/context-budget-report.md` (신규): `/context-budget --verbose` 산출물. 세션 오버헤드 ~24.4K tokens / 1M의 2.4% 집계, Top 1~5 절감안(~4.1K tokens / 17%) 제시

### Changed
- `.claude/settings.json`: `enabledMcpjsonServers: []` + `enableAllProjectMcpServers: false` — 프로젝트 레벨 MCP 자동활성화 차단 (보안 순기능)
- `pipeline/artifacts/10-deploy-log/runbook.md` §2.5 스모크 테스트:
  - test #0 신설: `.env.prod`에서 `ADMIN_API_KEY`를 현재 셸로 `export`하는 절차
  - test #4 GET 공개 읽기(`/api/notifications/preferences`, proxy.ts 경유)로 분리
  - test #5 PUT 쓰기(`/api/admin/notifications/preferences`, Route Handler)로 유효 payload 예시 명시
  - signalTypes 열거값(RAPID_DECLINE/TREND_REVERSAL/SHORT_SQUEEZE), minScore 범위(0~100) 힌트 추가
- `CHANGELOG.md` / `HANDOFF.md`: 세션 운영 현행화

### Fixed
- runbook §2.5 test #4: GET은 Route Handler에서 405 반환 — HTTP method 정정(GET → PUT). 로컬 Docker Desktop 스모크 테스트로 5/5 경로 HTTP 200 확인 후 반영

### Verified (not committed)
- 로컬 Docker Desktop 첫 배포 성공 — 3 컨테이너(db/backend/frontend) 전부 `healthy`
- 스모크 테스트 5종 전부 2xx
  - `GET /` → 200 (16KB SSR HTML)
  - backend `/actuator/health` → `{"status":"UP"}`
  - `GET /api/signals` → 200 (빈 배열, DB 초기 상태)
  - `GET /api/notifications/preferences` → 200 (공개, proxy.ts 경유)
  - `PUT /api/admin/notifications/preferences` → 200 (ADMIN_API_KEY 인증 통과, 값 수정→원복 확인)
- `.env.prod` 로컬 생성 (chmod 600, gitignore 확인) — POSTGRES_PASSWORD/ADMIN_API_KEY 랜덤 생성, Telegram/KRX 실값 주입

---

## [2026-04-17 — 저녁] 코드 리뷰 블로커(H-1) 수정 + Next.js 16 canonical proxy 적용 (`ef8c267`)

### Added
- `src/frontend/src/proxy.ts`: 런타임 `/api/*` → `BACKEND_INTERNAL_URL` 프록시 (Next.js 16 canonical, 구 middleware 대체). `/api/admin/*`는 Route Handler 우선 통과

### Changed
- `src/frontend/next.config.ts`: `rewrites()` 제거 — build time에 routes-manifest.json으로 고정되어 런타임 env 반영 불가. 주석으로 proxy.ts 선택 이유 명시
- `src/frontend/src/lib/api/client.ts`: `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_API_BASE_URL` 정합, 기본값 `/api`
- `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: `BACKEND_API_URL` → `BACKEND_INTERNAL_URL` 정합, `/api` path prefix 추가, 16KB body 상한(M-4)
- `src/backend/Dockerfile`: `./gradlew dependencies || true` → `./gradlew dependencies` (M-1, 의존성 해석 실패 은폐 제거)

### Fixed
- **[HIGH H-1]** compose / client.ts / route.ts 간 env 변수명 3중 불일치 — 프로덕션에서 브라우저→proxy→backend 경로가 끊어지는 블로커. `NEXT_PUBLIC_API_BASE_URL` + `BACKEND_INTERNAL_URL` 단일 네임스페이스로 통일

---

## [2026-04-17 — 오후] Phase 4 Verify + Phase 5 Ship + 프로토타입 효과 Next.js 이식 — v1.0 배포 준비 완료

### Added
- 프로토타입 효과 3종 Next.js 이식 (`871ff57`)
  - `src/frontend/src/components/ui/AuroraBackground.tsx`: 4-blob radial-gradient + drift keyframes, pure CSS, 서버 안전
  - `src/frontend/src/components/ui/CountUp.tsx`: rAF 기반 easeOutCubic 카운트업, `prefers-reduced-motion` 가드
  - `src/frontend/src/components/ui/Magnetic.tsx`: 커서 인력 버튼 래퍼, `coarse-pointer`/reduced-motion 가드
  - `src/frontend/src/app/globals.css`: `.aurora` + `@keyframes aurora-drift-1~4` + `.magnetic` 블록 추가
- Phase 4 Verify 산출물 3종 + Judge 평가 (`eb5fc15`)
  - `pipeline/artifacts/07-test-results/qa-report.md` (CONDITIONAL)
  - `pipeline/artifacts/08-review-report/review-report.md` (CONDITIONAL, CRITICAL 1 + HIGH 4)
  - `pipeline/artifacts/09-security-audit/audit-report.md` (CONDITIONAL, HIGH 1)
  - `pipeline/artifacts/07-test-results/verify-judge-evaluation.md` (7.6/10)
- Phase 5 Ship 인프라 (`764d6d3`)
  - `src/backend/Dockerfile` / `src/frontend/Dockerfile` (multi-stage, non-root, healthcheck)
  - `docker-compose.prod.yml` (3 서비스, 내부 네트워크, DB 미노출)
  - `.env.prod.example` + `.gitignore` 갱신
  - `.github/workflows/ci.yml` (backend-test + frontend-build + docker-build with GHA cache)
  - `pipeline/artifacts/10-deploy-log/runbook.md` (배포 / 롤백 / 백업 cron / AWS 5-step 이관)
  - `pipeline/artifacts/11-analytics/launch-report.md` (D+7 Top KPI 3종 + Week 1~4 모니터링)
  - `pipeline/artifacts/10-deploy-log/ship-judge-evaluation.md` (PASS 8.1/10)
- 백엔드 트랜잭션 리팩터
  - `src/backend/.../application/service/MarketDataPersistService.java`: `persistAll` 전담 빈 분리 — Spring AOP 자기호출 프록시 우회 문제 해결
- Admin API 서버 릴레이
  - `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: Next.js Route Handler — 서버 측 `ADMIN_API_KEY`로 backend 프록시

### Changed
- `src/frontend/src/app/layout.tsx`: `<AuroraBackground>` 주입 + 본문 z-index:1 레이어링 + footer backdrop-blur
- `src/frontend/src/app/page.tsx`: metric 카드 값에 `CountUp`, 필터 버튼에 `Magnetic` 래핑, 카드 배경 `bg-[#131720]/85 backdrop-blur`로 전환
- `src/backend/.../MarketDataCollectionService.java`: `persistAll` 로직 제거, `MarketDataPersistService`에 위임
- `src/frontend/src/app/settings/page.tsx`: `NEXT_PUBLIC_ADMIN_API_KEY` 의존 제거, `updateNotificationPreferences(form)`로 간소화
- `src/frontend/src/lib/api/client.ts`: `updateNotificationPreferences` apiKey 인자 제거, `/api/admin/notifications/preferences` Route Handler 호출로 전환
- `pipeline/state/current-state.json`: `status: "deployed"`, `human_approvals #3 passed 7.6`, `ship_artifacts` + `post_ship_recommendations` 추가
- `docs/sprint-4-plan.md`: Phase 4/5 통과 반영

### Fixed
- **[CRITICAL B-C1]** `NEXT_PUBLIC_ADMIN_API_KEY` 브라우저 번들 노출 — Review+Security 공동 지목. Route Handler로 서버 전환, 관리자 API 4개(batch/collect, signals/detect, backtest/run, PUT preferences) 공개 상태 해소
- **[HIGH B-H1]** `MarketDataCollectionService.persistAll` 자기호출로 `@Transactional` 무효 — `MarketDataPersistService` 신규 빈으로 분리해 프록시 정상 적용
- **[HIGH B-H2]** `persistAll` 데드 코드 (`findByStockId(null, date, date)` 미사용 결과) 제거
- **[HIGH B-H3]** 배치 재실행 시 유니크 제약 충돌 — 일자별 기존 `stockId` 집합 1회 조회 후 INSERT skip, 건수 로깅으로 멱등성 확보

---

## [2026-04-17] Sprint 4 Task 4 — 알림 설정 페이지 (백엔드 + 프론트) + 프로토타입 합류본 확정 + 리뷰 반영

### Security / Review Fixes (HIGH 4 + MEDIUM 9)
- **HIGH-1**: `PUT /api/notifications/preferences`에 `X-API-Key` 인증 추가 — 공개 API에서 공격자의 알림 무력화 방지 (Security 리뷰)
- **HIGH-2**: `NotificationPreferenceService.loadOrCreate` race condition — `DataIntegrityViolationException` catch + 재조회 recover 패턴 적용 (Java 리뷰)
- **HIGH-3**: `GlobalExceptionHandler`에서 `IllegalArgumentException` 전역 캐치 제거 — JDK 내부 오류가 400으로 마스킹되던 문제 해소 (Java 리뷰)
- **HIGH-4**: Hexagonal 위반 수정 — `sanitizeSignalTypes` 검증 책임을 Controller에서 `UpdateCommand` compact constructor로 이동, `DomainException(DomainError.InvalidParameter)` 경로 사용 (Java 리뷰)
- **MEDIUM**: `@Size(min=1, max=3)` 제약 추가 (DoS 방지), 에러 메시지 사용자 입력 반사 제거(고정 문자열), `getPreferenceForFiltering`에 `@Transactional(readOnly=true)` 명시, 도메인 `update()` 자체 검증(minScore 범위, 빈 리스트), `sendBatchFailure` 로그에서 `errorMessage` 제거
- **MEDIUM (프론트)**: `aria-valuemin/max/now` 3줄 중복 제거(input[type=range] 자동 제공), `client.ts` `cache: 'no-store'` spread 후위 재명시(caller override 방어), 에러 메시지 직접 노출 → `friendlyError()` 매핑 함수로 status 기반 사용자 메시지 반환
- **테스트**: `NotificationApiIntegrationTest` 9개로 확장 (인증 2 + 업데이트 1 + 400 검증 5 + 기본값 1). 알 수 없는 타입이 응답에 반사되지 않는지 검증 포함
- **부수 개선**: `BacktestController`/`SignalDetectionController`/`BatchController`의 API Key 검증 로직 중복 제거 → 신규 `ApiKeyValidator` 컴포넌트로 추출

### Added
- `src/backend/.../domain/model/NotificationPreference.java`: 싱글 로우 엔티티(id=1 고정) — 4채널 플래그 + `minScore`(0-100) + `signalTypes` JSONB
- `src/backend/.../application/port/in/GetNotificationPreferenceUseCase`, `UpdateNotificationPreferenceUseCase`: 조회/업데이트 유스케이스 포트
- `src/backend/.../application/port/out/NotificationPreferenceRepository`: Spring Data JPA 리포지토리
- `src/backend/.../application/service/NotificationPreferenceService`: `loadOrCreate` 지연 생성 + `getPreferenceForFiltering` 기본값 fallback
- `src/backend/.../adapter/in/web/NotificationPreferenceController`: `GET/PUT /api/notifications/preferences` + Bean Validation(`@Min/@Max/@NotNull`)
- `src/backend/src/main/resources/db/migration/V2__notification_preference.sql`: 테이블 DDL + 기본 row INSERT (Flyway 도입 시 바로 적용 가능, 현재는 참고용)
- `src/backend/src/test/.../NotificationApiIntegrationTest`: 5개 통합 테스트 (기본값 생성 / 전체 업데이트 / minScore 범위 / 알 수 없는 타입 / 필수 필드 누락)
- `src/frontend/src/types/notification.ts`: `NotificationPreference` 타입 + 채널 라벨 상수
- `src/frontend/src/app/settings/page.tsx`: 4개 토글(switch role) + 3개 시그널타입 필터(aria-pressed) + minScore 슬라이더 + 저장 버튼 + 토스트

### Changed
- `src/backend/.../application/service/TelegramNotificationService`: 4개 시나리오 전부 preference 필터 반영
  - `sendDailySummary`: toggle + signalTypes + minScore 삼중 필터
  - `sendUrgentAlerts`: toggle + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: toggle
- `src/backend/.../adapter/in/web/GlobalExceptionHandler`: `@Valid @RequestBody` 검증 실패를 400으로 변환 — `MethodArgumentNotValidException` + `HttpMessageNotReadableException` + `IllegalArgumentException` 핸들러 신규
- `src/frontend/src/lib/api/client.ts`: `fetchApi`에 `RequestInit` 옵션 추가, `getNotificationPreferences` + `updateNotificationPreferences` 노출
- `src/frontend/src/components/NavHeader.tsx`: `/settings` 링크 추가

### Decision
- **D-4.11 알림 설정 = 싱글 로우 패턴**: id=1 고정, 4개 채널 플래그 + minScore + signalTypes JSONB. 사용자/인증 도입 시 user_id FK로 확장 가능
- **D-4.10 프로토타입 합류본 = ambient**: `prototype/index-ambient.html`(1332줄, aurora + skeleton + tilt + magnetic + count-up 누적)을 최종 합류본으로 확정 → `prototype/index.html`에 복사

### Testing
- 백엔드: JUnit 5 + Testcontainers 25개 전체 통과 (기존 20 + 신규 5)
- 프론트: `tsc --noEmit` + `eslint` + `next build` 전부 clean — `/settings` 라우트 정적 생성 확인

---

## [2026-04-17] Sprint 4 Task 5-6 — 프론트엔드 반응형 + ErrorBoundary + 글로벌 네비 + 접근성

### Added
- `src/frontend/src/components/NavHeader.tsx`: 글로벌 네비게이션 — sticky + 햄버거 + ESC + `aria-current` + render-time 리셋 패턴 (`9436772`)
- `src/frontend/src/components/ErrorBoundary.tsx`: class 컴포넌트 + `resetKeys` 자동 복구 + `role="alert"` (`9436772`)

### Changed
- `src/frontend/src/app/layout.tsx`: 글로벌 `<NavHeader />` 삽입 (`9436772`)
- `src/frontend/src/app/page.tsx`: 중복 헤더 제거(sr-only H1), 시그널 리스트 `grid-cols-1 lg:grid-cols-2`, `<ul>/<li>` 시맨틱, 필터 `role="group" + aria-pressed` (`9436772`)
- `src/frontend/src/app/stocks/[code]/page.tsx`: `ResponsiveContainer aspect={2}` 비율 기반 차트, ErrorBoundary 래핑, 기간 버튼 `role="group"`, render-time 상태 리셋 (`9436772`)
- `src/frontend/src/app/backtest/page.tsx`: 모바일 `<dl/dt/dd>` 카드 ↔ 데스크탑 `<table>` 이중 렌더, ErrorBoundary 래핑 (`9436772`)
- `src/frontend/src/components/features/SignalCard.tsx`: `<Link>`가 직접 그리드 컨테이너 (중첩 `<div role="article">` 제거), `aria-label` 상세화 (`9436772`)

### Fixed
- `react-hooks/set-state-in-effect` ESLint 3건(Next 16 신규 룰): `NavHeader.pathname`, `StockDetail.code+period`, `Dashboard` 초기 `setLoading` 중복 → render-time 리셋 패턴 (`9436772`)
- `role="tablist"/"tab"` 스펙 위반 2건 → `role="group" + aria-pressed` (필터, 기간 버튼) (`9436772`)
- ErrorBoundary 재발 루프: `resetKeys` + `componentDidUpdate` 자동 리셋 (리뷰 MEDIUM-1) (`9436772`)
- `role="alert"` + `aria-live="assertive"` 중복 제거 (`9436772`)
- 백테스트 YAxis formatter 음수 처리 (`+-1.5%` → `-1.5%`) (`9436772`)
- `aria-current="page"`는 exact match만, 관련 경로는 시각 강조로 분리 (`9436772`)

### Committed
- Sprint 4 Task 5-6 (`9436772`): 7 files, +330/-73, `tsc + eslint + next build` 전부 ok

### Pending (Task 4 + 프로토타입 선정 다음 세션)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + `/settings` 프론트, 1.5일)
- 프로토타입 5종 중 합류본 선정 → `prototype/index.html`로 통합

---

## [2026-04-17] 프로토타입 UI 실험 5종 + 코드리뷰 보안 패치 전면 적용

### Added
- `prototype/index-before-skeleton.html`: 원본 스냅샷 (baseline, 보안 패치만) (`7a5b750`)
- `prototype/index-tilt-magnetic.html`: 3D 틸트 카드 + 마그네틱 버튼 — `prefers-reduced-motion` + 터치 자동 비활성 (`7a5b750`)
- `prototype/index-counter.html`: 카운트업 애니메이션 32개 카운터 (data 속성 선언형 엔진) (`7a5b750`)
- `prototype/index-ambient.html`: 배경 3층 — Aurora 메시 + 커서 스포트라이트 + 파티클 네트워크 캔버스 (`7a5b750`)

### Changed
- `prototype/index.html`: 스켈레톤 UI 적용 (시그널 리스트/상세 차트/백테스트 차트 로딩 + shimmer, 라이트/다크 대응) (`7a5b750`)

### Fixed
- **[CRITICAL] XSS 싱크 3종 차단**: `escapeHtml()` + `num()` 헬퍼, `onclick` 인라인 → `data-code` + `addEventListener` (`7a5b750`)
- **[HIGH] `showPage()` 허용목록**: `VALID_PAGES = Set` early return (`7a5b750`)
- **[HIGH] DOM 엘리먼트 캐싱**: `cacheEls()` INIT 1회 → `els[id]` 룩업 (`7a5b750`)
- **[MEDIUM] CDN SRI**: Chart.js 4.4.7 / Pretendard 1.3.9 `integrity="sha384-..."` + `crossorigin="anonymous"` (`7a5b750`)
- **[MEDIUM] 스켈레톤 접근성**: `role="list"` + `aria-busy` 토글 + `aria-live="polite"` + 카드 `role="button"` + 키보드 (`7a5b750`)
- **[LOW] matchMedia 동적 리스너**: `prefers-reduced-motion`/`pointer: coarse`에 `change` 리스너 (tilt/counter/ambient 3종) (`7a5b750`)

> 5종 HTML 모두 단독 실행 가능. 코드리뷰 재검증 CRITICAL/HIGH 0건 + 회귀 0건. 다음 세션에서 최종 합류본 결정 → `prototype/index.html` 통합 예정.

---

## [2026-04-17] Sprint 4 Task 1-3 — N+1 쿼리 최적화 + 백테스팅 3년 제한 + CORS X-API-Key

### Added
- `src/backend/src/test/java/com/ted/signal/config/CorsConfigTest.java`: CORS preflight 테스트 1개 신규 (`33b6cf1`)
- `BacktestApiIntegrationTest.runBacktestRejectsPeriodOverThreeYears`: 3년 초과 기간 rejection 테스트 추가 (`33b6cf1`)
- `StockPriceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 절 기반 벌크 주가 조회 (`33b6cf1`)
- `StockPriceRepository.findAllByTradingDate`: 일자별 주가 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `ShortSellingRepository.findAllByTradingDate`: 일자별 공매도 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `LendingBalanceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 기반 대차잔고 히스토리 (`33b6cf1`)
- `SignalRepository.findBySignalDateWithStockOrderByScoreDesc`: 일자별 시그널 JOIN FETCH 조회 (`33b6cf1`)

### Changed
- `SignalDetectionService.detectAll`: 종목당 7쿼리 × 2500 = 17,500쿼리 → 전체 7쿼리 (활성 종목 1 + 벌크 5 + 기존 시그널 1). 메모리 루프 기반 재작성 (`33b6cf1`)
- `TelegramNotificationService.sendDailySummary`: `findBySignalDateOrderByScoreDesc` → `findBySignalDateWithStockOrderByScoreDesc` (stock LAZY 로딩 N+1 해소) (`33b6cf1`)
- `BacktestController`: 최대 기간 5년 → **3년**, `to` 미래 날짜 차단 검증 추가 (`33b6cf1`)
- `BacktestEngineService`: 종목별 주가 조회 N쿼리 → `findAllByStockIdsAndTradingDateBetween` 단일 쿼리 (`33b6cf1`)
- `WebConfig`: CORS `allowedHeaders`에 `X-API-Key` 추가, `OPTIONS` 메서드, `allowCredentials(true)`, `exposedHeaders` 명시 (`33b6cf1`)
- `SignalDetectionService` detail의 `volumeChangeRate`: 점수(int) 중복 저장 → 실제 거래량 비율(BigDecimal) 저장 (`33b6cf1`)

### Committed
- Sprint 4 Task 1-3 (`33b6cf1`): 성능/보안 HIGH 3건 해소 (11 files, +245/-114, 테스트 20개 전부 통과)

### Pending (Task 4-5 다음 세션 이관)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + 프론트 `/settings`)
- Task 5: 모바일 반응형 + ErrorBoundary + 접근성 감사

---

## [2026-04-17] 모델 운용 전략 전환 — Max 구독자 Opus 4.7 단일 운영

### Changed
- `docs/PIPELINE-GUIDE.md`: "Phase 1~3 Sonnet, Phase 4 Opus" 분기 전략 → **Max 구독자 Opus 4.7 단일 운영**으로 전환. API 종량제 사용자용 Option B 병기 (`d55738d`)
- `docs/design/ai-agent-team-master.md`: §11 "비용 최적화" 섹션을 **Option A (Max 구독) / Option B (API 종량제)** 이원화. Judge 비용 설명 보강 (`d55738d`)
- `.claude/commands/init-agent-team.md`: CLAUDE.md 템플릿에 "모델 운용 전략" 섹션 추가 + 최종 안내 메시지에 구독 유형별 가이드 포함 (`d55738d`)
- `pipeline/decisions/decision-registry.md`: D-0.1 "모델 운용 전략" 의사결정 추가 (23 → 24건) (`d55738d`)

> 근거: Claude Code Max $200 구독 활용 시 모델 분기로 얻는 비용 이득 없음. Sprint 3에서 Opus 4.7이 N+1 쿼리 17,500건 등 HIGH 이슈 7건 포착 → Phase 1~3에서도 Opus 사용 시 품질 우위 확인.

---

## [2026-04-17] 파이프라인 플랫폼 정합화 + 팀 공유 전환 + 문서 현행화

### Added
- `docs/PIPELINE-GUIDE.md`: 개발 플로우 사용설명서 신규 (9개 섹션, 다른 프로젝트 이식 체크리스트 포함) (`cdbacc5`)
- `docs/sprint-4-plan.md`: Sprint 4 작업계획서 (N+1 최적화 + CORS + 알림 설정 페이지 + 모바일 반응형, 4.5일 예상) (`da85ba2`)
- `pipeline/state/current-state.json`: Sprint 3 완료 상태 현행화 (진행 sprint 4종 + 테스트 커버리지 + 알려진 이슈) (`eecdb7c`)
- `pipeline/artifacts/06-code/summary.md`: Sprint 1~3 구현 요약 (Compaction 방어 영속화) (`eecdb7c`)
- `pipeline/decisions/decision-registry.md`: Phase 1~3 의사결정 23개 누적 (Discovery 3, Design 4, Build 15, Sprint 4 계획 1) (`da85ba2`)
- 글로벌 `~/.claude/settings.json` statusLine: 현재 모델 / 비용 / 200k 초과 / CWD 실시간 표시 (Opus→Sonnet fallback 즉시 인지)

### Changed
- `.gitignore`: `pipeline/state/`, `pipeline/artifacts/` 제외 규칙 제거 → 팀 공유 대상화 (`eecdb7c`)
- `CLAUDE.md`: 소규모 스타트업 팀 공유 전제 명시 + PIPELINE-GUIDE.md 참조 추가 + Spring Boot 3.4 → 3.5.0 일관성 (`eecdb7c`, `cdbacc5`)
- `docs/design/ai-agent-team-master.md`: `Opus 4.6` → `Opus 4.7` 14곳 치환 (1M 컨텍스트, 비용, MRCR 설명 전반) (`cdbacc5`)
- `.claude/commands/init-agent-team.md`: 기본 스택 `Spring Boot 3.4` → `3.5.0` (새 프로젝트 scaffolding 현행값) (`cdbacc5`)

### Committed
- Sprint 3 구현 (`022284e`): 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트 (19 files, +1346)
- Sprint 3 핸드오프 (`88aba9a`): CHANGELOG + HANDOFF
- 파이프라인 영속화 (`da85ba2`): decision-registry + sprint-4-plan
- 팀 공유 전환 (`eecdb7c`): pipeline/ 커밋 대상화 (22 files, +2369)
- 문서 업데이트 (`cdbacc5`): Opus 4.7 + Spring Boot 3.5.0 + PIPELINE-GUIDE

---

## [2026-04-17] Phase 3 Build Sprint 3 — 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트

### Added
- BacktestEngineService: 과거 3년 시그널 수익률 계산 + SignalType별 적중률/평균수익률 집계
- RunBacktestUseCase 포트 + POST /api/backtest/run API (API Key 보호, 기본 3년, 최대 5년)
- TelegramClient: RestClient 기반 Telegram Bot API 연동 (환경변수 비활성화 지원)
- TelegramNotificationService: 4가지 알림 시나리오 (일일 요약/A등급 긴급/배치 실패/주간 리포트)
- NotificationScheduler: 08:30 일일 요약 (월~금), 토요일 10:00 주간 리포트
- MarketDataBatchConfig notifyStep: 배치 완료 후 A등급 시그널 긴급 알림 자동 발송
- SignalRepository.findBySignalDateBetweenWithStock: JOIN FETCH 벌크 조회
- Testcontainers PostgreSQL 16 통합 테스트 인프라 (싱글톤 컨테이너 패턴)
- SignalDetectionServiceTest: 시그널 탐지 로직 5개 테스트 (급감/임계값/추세전환/숏스퀴즈/중복방지)
- BacktestEngineServiceTest: 수익률 계산 + 적중률 집계 + 데이터 부족 처리 4개 테스트
- BacktestApiIntegrationTest: API 인증/실행 5개 테스트
- SignalApiIntegrationTest: 시그널 조회/필터/인증 3개 테스트
- application.yml: telegram.bot-token, telegram.chat-id 환경변수 설정

### Changed
- API Key 비교: String.equals → MessageDigest.isEqual 상수 시간 비교 (타이밍 공격 방지, 3개 컨트롤러)
- API Key 미인증 시 403 → 401 UNAUTHORIZED 반환 (3개 컨트롤러)
- @Value 필드 주입 → 생성자 주입 전환 (BacktestController, BatchController, SignalDetectionController)
- BacktestEngineService: save() 루프 → saveAll() 일괄 저장
- MarketDataBatchConfig: SignalRepository 직접 주입 제거 → TelegramNotificationService.sendUrgentAlerts() 위임 (Hexagonal 경계 준수)
- MarketDataScheduler: 배치 실패 시 e.getMessage() 노출 → 클래스명만 텔레그램 발송
- BacktestController: @Validated 추가 + from/to 날짜 범위 검증 (최대 5년)
- TelegramNotificationService.sendBatchFailure: LocalDate → LocalDateTime (시간 정밀도)

---

## [2026-04-16] Phase 3 Build Sprint 2 — 시그널 엔진 + 대시보드

### Added
- SignalDetectionService: 3대 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) (`7902cfd`)
- POST /api/signals/detect 수동 시그널 탐지 API (`7902cfd`)
- Spring Batch detectStep 추가 (collectStep → detectStep 순차) (`7902cfd`)
- 프론트엔드 대시보드: 메트릭 카드 + 필터 탭 + 시그널 리스트 (`7902cfd`)
- 프론트엔드 종목 상세: 주가/대차잔고 듀얼 축 차트 (Recharts) (`7902cfd`)
- SignalCard 컴포넌트, TypeScript 타입 정의, API 클라이언트 (`7902cfd`)
- BacktestResult Entity + Repository + BacktestQueryService (`63407cd`)
- GET /api/backtest 백테스팅 결과 조회 API (`63407cd`)
- 프론트엔드 /backtest 페이지: 성과 테이블 + 보유기간별 수익률 Bar 차트 (`63407cd`)

### Changed
- 관리자 API 인증: IP allowlist → API Key 헤더(X-API-Key) 전환 (`e6754cb`)
- detail.volumeChangeRate 매핑 오류 수정 (`e6754cb`)
- scoreVolumeChange 음수 방지 Math.max(0, ...) 추가 (`e6754cb`)
- params.code 안전한 타입 처리 (Array.isArray 체크) (`e6754cb`)
- 프론트엔드 API 클라이언트 단일화 (중복 fetch 제거) (`e6754cb`)
- 미사용 변수 signalDates 제거 (`e6754cb`)

---

## [2026-04-16] Phase 3 Build Sprint 1 — 데이터 파이프라인 구축

### Added
- 16개 에이전트 AGENT.md + 공유 프로토콜 + 7개 슬래시 커맨드 scaffolding (`1908310`)
- Phase 1 Discovery 산출물 8건: 요구사항, PRD, 로드맵, 스프린트 플랜, GTM, 경쟁사 분석, 고객여정, 알림 시나리오 (`1908310`)
- Phase 2 Design 산출물 6건: 기능명세, 디자인 토큰, 컴포넌트 명세, ERD, DDL, 쿼리 전략 (`1908310`)
- Spring Boot 3.5.0 + Java 21 백엔드 프로젝트 (Hexagonal Architecture) (`33d7676`)
- Domain Entity 5개: Stock, StockPrice, LendingBalance, ShortSelling, Signal (`33d7676`)
- Repository 5개 (JPA 3단계 쿼리 전략), UseCase 2개, SignalQueryService (`33d7676`)
- REST API: GET /api/signals, GET /api/stocks/{code} (`33d7676`)
- GlobalExceptionHandler + sealed interface DomainError (`33d7676`)
- KRX 크롤러: 공매도/대차잔고/시세 수집 (요청 간격 2초) (`620f2bf`)
- Spring Batch Job + MarketDataScheduler (매일 06:00 스케줄) (`620f2bf`)
- 수동 배치 API: POST /api/batch/collect (localhost 제한) (`620f2bf`)
- docker-compose.yml: PostgreSQL 16 + DDL 자동 적용 (`620f2bf`)
- Next.js 15 + TypeScript 프론트엔드 프로젝트 초기화 (`33d7676`)
- UI/UX 프로토타입: Dark Finance Terminal 디자인 (prototype/index.html) (`33d7676`)
- .env.example (`620f2bf`)

### Changed
- Spring Boot 버전 3.4 → 3.5.0 (Spring Initializr 호환) (`33d7676`)
- JPA ddl-auto: validate → none (파티션 테이블 호환) (`140694b`)
- CORS allowedOrigins → allowedOriginPatterns + 헤더 제한 (`620f2bf`)
- MarketDataCollectionService: HTTP 수집을 트랜잭션 밖으로 분리 (`d710aa1`)
- 대차잔고 전 영업일 계산: minusDays(1) → 주말 건너뛰기 (`d710aa1`)
- 대차잔고 벌크 조회: 종목별 개별 쿼리 → findAllByTradingDate 1회 쿼리 (`d710aa1`)
- saveAll 벌크 저장으로 개별 exists/save 쿼리 제거 (`d710aa1`)
- BatchConfig → BatchConfig + Scheduler 분리 (Job Bean 직접 주입) (`d710aa1`)

---

## [2026-04-16] 프로젝트 초기 설정

### Added
- CLAUDE.md 생성 — 프로젝트 개요, 기술스택, 파이프라인, 에이전트 구조 가이드 (`fd26e75`)
- .gitignore 생성 — 빌드/IDE/환경파일 제외 설정 (`fd26e75`)
- GitHub 저장소 생성 (withwooyong/ted-startup, private) (`fd26e75`)
- AI Agent Team Platform 설계서 및 scaffolding 생성기 커밋 (`fd26e75`)
