# Session Handoff

> Last updated: 2026-04-18 (KST, 밤)
> Branch: `master` (origin 대비 1 커밋 ahead — `7f4f3d1` P15 푸시 대기)
> Latest commit: `7f4f3d1` — P15: 키움 REST 가용성 조사 (문서 스파이크)

## Current Status

**Java→Python 전면 이전 Phase 1~9 + §11 신규 도메인(P10~P15) 전체 완결.** 포트폴리오·KIS 모의 동기화·시그널 정합도·DART Tier1 어댑터·AI 분석 리포트 파이프라인·프론트 UI·키움 REST 조사까지 전부 완료. 백엔드 **98/98 PASS · mypy strict 0 · ruff 0**, 프론트 **build/tsc/lint clean**. 실 API 키 E2E 검증만 남음.

## Completed This Session

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Phase 8 Java 스택 물리 제거 | `24b43ba` | `src/backend/` 전량 삭제 (-4,710) |
| 2 | Phase 9 기술스택 문서/에이전트 Python 전환 | `005011e` | `CLAUDE.md`, `docs/design/ai-agent-team-master.md`, `agents/08-backend/AGENT.md`, `pipeline/artifacts/10-deploy-log/runbook.md`, `docs/migration/java-to-python-plan.md` |
| 3 | P10 포트폴리오 도메인 (스키마·CRUD·성과) | `97203c2` | Alembic 003, portfolio 모델/Repository/Service/Router, 테스트 11 (+1,439) |
| 4 | P11 KIS 모의투자 REST 연동 | `c003fc8` | `kis_client.py`, SyncPortfolioFromKisUseCase, /sync 라우터, 테스트 9 (+774) |
| 5 | P12 포트폴리오↔시그널 정합도 | `11e80c2` | SignalAlignmentUseCase, /signal-alignment 라우터, 테스트 5 (+343) |
| 6 | P13a DART OpenAPI Tier1 어댑터 | `b2c20f4` | Alembic 004, `dart_client.py`, dart_corp_mapping Repository, 테스트 9 (+711) |
| 7 | P13b AI 분석 리포트 파이프라인 | `caf8355` | Alembic 005, LLMProvider Protocol, OpenAIProvider(strict JSON + 역할 분리 프롬프트), AnalysisReportService(24h 캐시 + 자동 소스 보강), /api/reports/{stock_code}, 테스트 9 (+1,484) |
| 8 | 코드 리뷰 fix: P13b HIGH(mypy 5) + 보안 MEDIUM 4 | `185dfaf` | cast/list 제네릭/반환타입, `is_safe_public_url`, openai_base_url HTTPS 강제, `<tier1_data>` fence (+179/-43) |
| 9 | P14 프론트 포트폴리오·AI 리포트 UI | `3cd5c75` | Next.js 16 `/portfolio`·`/portfolio/[id]/alignment`·`/reports/[stockCode]`, 제네릭 `/api/admin/[...path]` 릴레이, types/portfolio·report, NavHeader 확장 (+1,349) |
| 10 | 코드 리뷰 fix: P14 HIGH 3 + MEDIUM 4 | `c008592` | path 세그먼트 allowlist(SSRF), reports cancellation race 해소, SourceRow safeHref(javascript: 차단), refreshCurrent 에러 전파, aria-label, ADMIN_BASE 공용화 (+153/-73) |
| 11 | cleanup: mypy strict 0 · ruff 0 · frontend 타입 스키마 정합 | `51bfe10` | pandas-stubs/types-python-dateutil, StrEnum 4, rowcount_of 헬퍼, UP037 forward-ref 제거, signal.ts snake_case 정렬 + SignalDetail 안전 접근, StockDetail 실제 구조 정정, CountUp queueMicrotask (+332/-232) |
| 12 | P15 키움 REST 가용성 조사 | `7f4f3d1` | `docs/research/kiwoom-rest-feasibility.md`, plan §11 도메인 정정 (+177) |

**누적 규모**: 12 커밋 / 140 파일 / **+7,120 / -5,141 라인** (Java 삭제 -4,710 포함).
**테스트**: 백엔드 pytest **98/98 PASS** (이전 52 + 신규 46). 프론트 tsc + ESLint + Next.js build 모두 clean.

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **원격 푸시** | pending | `7f4f3d1` 1 커밋 ahead. 사용자 명시 지시 후 push |
| 2 | **실 E2E 검증** | pending | `.env.prod` 의 실 DART/OpenAI/KIS 모의 키로 `docker compose up` → 브라우저 `/portfolio` 계좌 등록 → KIS 동기화 → 특정 종목 AI 리포트 생성까지 1회 검증. `scripts/validate_env.py` 로 사전 키 확인 먼저 권고 |
| 3 | **`force_refresh=true` rate limiting** | pending (LOW) | P14 리뷰에서 식별. `slowapi` 또는 `fastapi-limiter` 도입해 관리자 키 보유자의 LLM 호출 폭주 방지. 인프라 수준 변경이라 별도 PR 권장 |
| 4 | **KRX 대차잔고 pykrx 스키마 불일치 복구** | pending (carry-over) | 어댑터에서 경고 로그 + 빈 리스트 fallback 중. 직접 KRX 호출 or pykrx 버전업으로 해결. 대차잔고 공백 기간 동안 `TREND_REVERSAL` 등 시그널 품질 저하 가능 |
| 5 | **`BrokerAdapter` Protocol 추출** | pending (P15 Go 조건 3) | 현 KIS 단일 구현을 Protocol 뒤로 분리해 계약 고정. 키움 합류 시점에 재작업 방지용. 범위: `fetch_balance() -> list[HoldingRow]` 등 |
| 6 | **M2 `/health` env 필드 노출** | pending (carry-over) | 외부 `/health` 는 `{"status":"UP"}` 만 노출하고 상세는 `/internal/info` 로 분리 권고 |
| 7 | **M1 `/metrics` 공개 노출** | pending (carry-over) | Caddyfile IP 게이팅 또는 `/internal/metrics` 경로 이동 권고 |

## Key Decisions Made

1. **Phase 8/9 정리 먼저, §11 신규는 그다음** — 플랜에 명시된 우선순위 준수. Java 제거와 문서 갱신이 끝난 후에만 신규 도메인 진입.
2. **포트폴리오 스키마: 4 테이블 분리** — `brokerage_account` / `portfolio_holding` (현재 잔고 스냅샷) / `portfolio_transaction` (매수/매도 원장) / `portfolio_snapshot` (일별 평가). holding 은 거래 이력 파생 캐시이되 가중평균 평단가는 `RecordTransactionUseCase` 에서 직접 갱신 — 매도 시에는 평단가 불변, 매수 시 가중평균 재계산.
3. **KIS 동기화는 snapshot-level upsert** — KIS `inquire-balance` 응답이 (수량, 평단가) 스냅샷이라 거래 이력 재구성 불가. `portfolio_transaction` 은 수동 입력용으로만 남기고 `portfolio_holding` 을 직접 upsert. 실거래 URL/TR_ID 진입은 생성자 assertion + TR_ID 하드코드 (`VTTC8434R`) 로 이중 차단.
4. **AI 리포트는 실시간 온디맨드 + 24h 캐시** (KST 00:00 기준). 일 1회 자동 배치는 비용 예측 가능해진 시점에 재논의. `force_refresh=true` 쿼리로 캐시 우회.
5. **LLMProvider 추상화 우선** — Plan B (OpenAI 단독) 로 착수하되 `LLMProvider` Protocol 뒤에 배치해 Plan A (Perplexity + Claude) 전환 시 `AI_PROVIDER` 환경변수만 변경하면 되게 설계. `collect_qualitative` / `analyze` / `repackage` 3 메서드. web_search (mini) 와 nano 리패키징은 MVP 에서 no-op/passthrough, Responses API 연동 후속.
6. **신뢰 출처 3-Tier 프롬프트 강제** — `<tier1_data>` / `<tier2_data>` XML-like fence 로 데이터와 지시문 분리. 시스템 프롬프트에 "숫자는 Tier1 만, 정성은 Tier2 만 인용, 일반지식으로 숫자 생성 금지" 역할 분리 규칙 + fence 내부 지시문 **무시** 명시. strict JSON schema 로 출력 블라스트 제한.
7. **프론트 admin 경로는 catch-all 릴레이** — `/api/admin/[...path]` 단일 Route Handler 가 ADMIN_API_KEY 서버 측 부착. 기존 `/api/admin/notifications/preferences` 는 static 경로라 우선순위 공존. path 세그먼트 `^[A-Za-z0-9_\-.]+$` allowlist + `..` 명시 거부로 SSRF 차단.
8. **프론트 타입 snake_case 로 전환** — 기존 `signal.ts` 가 camelCase (signalId, stockCode, balanceChangeRate) 로 백엔드 snake_case 와 불일치. 런타임 undefined 참조 다수 존재. P14 에서 portfolio/report 는 처음부터 snake_case 로 가고, cleanup 에서 signal.ts·StockDetail·BacktestSummary 도 snake_case 로 전환 + `SignalDetail` + `detailNumber()` 로 JSONB 안전 접근.
9. **키움 REST: 현 No-Go** — Python SDK (`kiwoom-rest-api` 0.1.12) 미성숙, 공식 가이드 로그인 벽, 커뮤니티 자료 부족. KIS 단독으로 포트폴리오 목표 달성 가능. Go 조건 3/3 (개인 키움 계좌 수요 + SDK 0.2+ 성숙 + KIS 어댑터 계약 고정) 충족 시 재평가.
10. **cleanup 에서 pandas-stubs 도입** — mypy strict 를 실제로 0 으로 만들기 위해 `pandas-stubs` + `types-python-dateutil` dev deps 추가. `pykrx` / `apscheduler` 는 스텁 없어 mypy override 로 무시. DataFrame 반환 곳의 `Hashable` 좁히기는 최소한의 `# type: ignore[arg-type]` 로 처리.

## Known Issues

### 보안·품질 이슈 (수정 완료)
- **P13b HIGH·MEDIUM**(`185dfaf`): mypy strict 5 해소, URL 스킴 검증, 에러 본문 누설 차단, openai_base_url HTTPS 강제, 프롬프트 인젝션 fence.
- **P14 HIGH·MEDIUM**(`c008592`): SSRF path allowlist, reports race 제거, SourceRow javascript: URI 차단, refreshCurrent 투명 실패 해소.
- **cleanup**(`51bfe10`): mypy strict 0 / ruff 0 달성.

### 이전 세션 carry-over (미처리)
- **M1 `/metrics` 공개 노출** — Caddyfile IP 게이팅 권고.
- **M2 `/health` env 필드 노출** — 외부용 `{"status":"UP"}` / 상세는 `/internal/info`.
- **M3 uv 컨테이너 이미지 digest 미고정** — 공급망 안정성.
- **M4 Dockerfile `useradd --shell /bin/bash`** — `/usr/sbin/nologin` 권장.
- **`force_refresh` rate limiting** — P14 리뷰에서 추가 식별.

### 도메인·운영 이슈
- **KRX 대차잔고**: pykrx 스키마 불일치로 0 rows fallback. 어댑터 경고 로그만. `TREND_REVERSAL` 등 일부 시그널 품질 영향.
- **실 E2E 검증 미완**: API 키 3종(DART/OpenAI/KIS 모의) 으로 풀 파이프라인 1회 생성 확인 필요.

## Context for Next Session

### 사용자의 원래 목표
주식 시그널 탐지·백테스팅 서비스의 Java→Python 전면 이전 + §11 (계좌 포트폴리오 + AI 종목 분석 리포트) 신규 도메인 합류. MVP 4~6주 내 런칭 범위.

### 선택된 경로와 이유
- **Big-bang 재작성 + 완료 후 §11 진입**: 사전-운영 단계 이점 활용. Strangler Fig 보다 최종 구조 깔끔.
- **Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic + APScheduler + pandas/vectorbt** 스택.
- **KIS 모의 단독 착수, 키움은 조사만**: KIS REST 성숙도·레퍼런스·크로스플랫폼 모두 우위. 키움은 Python SDK 안정화 후 재평가.
- **AI: OpenAI GPT-5.4 단독 (Plan B) 로 출발** + `LLMProvider` 추상화로 Plan A (Perplexity+Claude) 런타임 전환 가능.
- **신뢰 출처 3-Tier**: Tier1(공식 API 원문) 이 숫자·공시의 유일한 근거. Tier2(web_search) 는 정성만. Tier3(블로그·커뮤니티) 는 파이프라인 미진입.

### 사용자 선호·제약
- **커밋 메시지는 반드시 한글** (글로벌 CLAUDE.md).
- **푸시는 사용자 명시 지시 후에만** — 현재 1 커밋 로컬 대기.
- **값이 민감한 명령 차단**: `.env.prod` cat / env 값 로깅 등은 차단. 검증 스크립트는 값 비노출 (`_key_structure` 같은 구조 진단만).
- **작업 단위 커밋 분리 선호**: Phase/P단위/리뷰 fix/cleanup 을 별도 커밋.
- **리뷰 요청 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호** (자동수정 포함).

### 다음 세션 선택지
- **A.** 원격 푸시 → 실 E2E 검증 → `force_refresh` rate limiting — 현 MVP 를 실가동 검증으로 넘기는 자연스러운 흐름
- **B.** M1/M2 carry-over (관측성 경로 분리) + Dockerfile 하드닝 (M3/M4) — 보안·운영 잔여 과제 처리
- **C.** P14 프론트 보강: ErrorBoundary 공용화, `portfolio/page.tsx` 리팩터(Metric/ActionButton 추출), /stocks 페이지 대차잔고 라인 재도입(별도 API 필요)
- **D.** AI 리포트 고도화: Responses API + web_search_preview 로 Tier2 활성화, nano 리패키징 실구현

A → B 순이 우선도 높음. D 는 비용·검증 가시화 후 재논의.

## Files Modified This Session

```
 140 files changed, 7,120 insertions(+), 5,141 deletions(-)
```

주요 디렉토리 분포:
- `src/backend_py/app/adapter/out/ai/` (신규) — OpenAI provider + LLMProvider 추상 (~400 라인)
- `src/backend_py/app/adapter/out/external/` — KIS·DART 신규 + 기존 KRX/Telegram 타입 정리 (~900 라인)
- `src/backend_py/app/adapter/out/persistence/` — portfolio/analysis_report/dart 모델·Repository + `_helpers.rowcount_of` (~600 라인)
- `src/backend_py/app/adapter/web/` — portfolio/reports 라우터, 스키마 확장 (~600 라인)
- `src/backend_py/app/application/` — portfolio/analysis_report 서비스, LLMProvider Port (~1,300 라인)
- `src/backend_py/migrations/versions/` — 003 portfolio / 004 dart / 005 analysis_report (~200 라인)
- `src/backend_py/tests/` — test_portfolio/test_kis_client/test_dart_client/test_analysis_report (46 테스트, ~1,560 라인)
- `src/frontend/src/app/` — portfolio/reports/admin catch-all 라우트 (~1,000 라인)
- `src/frontend/src/lib/api/` + `src/frontend/src/types/` — API 클라이언트·타입 (~350 라인)
- `src/backend/` (삭제) — Java 스택 4,710 라인 제거
- `docs/research/kiwoom-rest-feasibility.md` (신규, 177 라인)
