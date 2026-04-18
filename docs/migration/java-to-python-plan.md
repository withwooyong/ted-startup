# Java → Python 전환 작업계획서 (Draft)

- **문서 상태**: Decisions locked — 착수 대기
- **작성일**: 2026-04-18
- **대상 저장소**: `src/backend/` (Spring Boot 3.5.0 + Java 21)
- **결정 필요 시점**: 구현 착수 전, 인간 승인 #2(설계) 단계에서 재승인
- **운영 상태**: **사전-운영(pre-production)** — 실사용자 없음, 데이터 보존 의무 없음

---

## 1. 목표 및 전제

### 1.1 전환 목표
주식 시세 수집·시그널 탐지·백테스팅이 핵심 도메인인 본 서비스에서, 향후 기능 확장(수치연산·ML·다종 데이터소스) 시 **Python 데이터 생태계(pandas, numpy, pandas-ta, vectorbt, FastAPI)** 의 생산성을 전면 활용하기 위해 Java/Spring Boot 백엔드를 Python으로 전체 교체한다.

본 이전과 병행해 다음 **신규 도메인 2종**을 동일 Python 스택 위에 올린다 (상세는 §11):
- **계좌 포트폴리오 도메인** — 증권사 API 연동 또는 수동 등록으로 보유 종목·수량·평단가 관리 및 성과 검증
- **AI 종목 분석 리포트 도메인** — 외부 LLM(API) 기반 종목 분석·전망 리포트 생성

### 1.2 전제
- 아직 **운영 배포 전 단계** → 데이터 마이그레이션 부담 없음, 다운타임 개념 없음.
- DB 스키마(PostgreSQL 16)는 **그대로 유지**(파티셔닝 포함). 언어만 교체.
- 프론트엔드(Next.js), Caddy 역프록시, docker-compose 스택 구조는 유지. 변경 지점은 `backend` 서비스 이미지와 내부 포트 계약.
- 변경하지 않는 것: 도메인 명칭(stock/short_selling/lending_balance/signal/backtest_result/notification_preference), API 경로, 외부 연동 대상(KRX, Telegram).

### 1.3 성공 기준
- [ ] Spring Boot 스택을 제거해도 기존 기능 8개 API + 1개 배치 잡이 Python 스택에서 동일 계약(경로·요청·응답)으로 동작
- [ ] 통합 테스트가 Testcontainers-Python 기반으로 재작성되어 동일 도메인 시나리오 커버
- [ ] `docker compose -f docker-compose.prod.yml up` 한 번으로 전체 스택 기동
- [ ] 마스터 설계서(`docs/design/ai-agent-team-master.md`) 기술스택 항목이 Python으로 갱신 승인됨

---

## 2. 현 상태 인벤토리 요약

| 영역 | 현황 | 비고 |
|------|------|------|
| Java 소스 | 48개 (Hexagonal) | `src/backend/src/main/java/com/ted/signal/` |
| 컨트롤러 | 6개 | Signal, SignalDetection, Backtest, NotificationPreference, Batch, ApiKeyValidator |
| 외부 어댑터 | 2개 | `KrxClient`(java.net.http), `TelegramClient`(RestClient) |
| 서비스/유즈케이스 | 8개 | MarketData*, SignalDetection*, Backtest*, Notification*, TelegramNotification* |
| 도메인 엔티티 | 7개 | Stock, StockPrice, Signal, ShortSelling, LendingBalance, BacktestResult, NotificationPreference |
| 배치 잡 | 1개 Job / 3 Step | collect(KRX) → detect(시그널) → notify(텔레그램) |
| 테스트 | 8개 (Testcontainers PG16) | 통합 3 + 유닛 2 + 설정 1 + 부팅 1 |
| DB 마이그레이션 | 수동 SQL 2개 | `V1__init_schema.sql`, `V2__notification_preference.sql` (Flyway 미도입) |
| 컨테이너 | 멀티스테이지 Dockerfile(JDK21→JRE21) | Caddy가 /api 라우팅 |

---

## 3. Python 기술스택 제안

| 역할 | 제안 | 근거 / 대안 |
|------|------|------------|
| 런타임 | **Python 3.12 (확정)** | asyncio 성능 개선, 주요 데이터 라이브러리(pandas/numpy/vectorbt) 휠 안정 |
| 패키지 매니저 | **uv** | 설치·잠금·가상환경이 단일 도구. 대안: poetry |
| 웹 프레임워크 | **FastAPI** | Pydantic v2 타입 안전, 자동 OpenAPI, async 일급. Spring Web과 가장 유사한 DX |
| ORM | **SQLAlchemy 2.0 (async)** + Pydantic DTO | 대안: SQLModel(얇은 wrapper). 기존 JPA Entity 1:1 대응 용이 |
| DB 마이그레이션 | **Alembic** | Flyway 미도입이었던 점 해소. 기존 V1/V2 SQL을 Alembic 버전으로 포팅 |
| 배치/스케줄 | **APScheduler (확정)** + FastAPI `BackgroundTasks` | Spring Batch 3-Step 대응. 파이프라인 복잡도 증가 시 Prefect로 교체 여지 유지 |
| HTTP 클라이언트 | **httpx** (async) | `KrxClient`/`TelegramClient` 이전용 |
| 수치/분석 | pandas, numpy, pandas-ta | 현 자바 로직을 벡터 연산으로 치환해 성능·가독성 동시 향상 |
| 백테스트 | **vectorbt (확정)** | 벡터 연산 기반, pandas 생태계 통합, 현 `BacktestEngineService`를 라이브러리 호출로 대체해 코드량 감소 |
| 테스트 | pytest + pytest-asyncio + **testcontainers-python** | 기존 `IntegrationTestBase` 패턴 그대로 이전 가능 |
| 관측 | structlog + prometheus-fastapi-instrumentator | 기존 `/actuator/prometheus`를 `/metrics`로 치환 |
| 린트/타입 | **ruff** + **mypy**(strict) | Java 정적 타입에 가장 근접한 조합 |

---

## 4. 컴포넌트 매핑 테이블

| Java (현) | Python (제안) | 이전 난이도 |
|-----------|---------------|------------|
| `@RestController` | FastAPI `APIRouter` | 낮음 |
| `@Service` + UseCase 인터페이스 | 일반 class + Protocol (`typing.Protocol`) | 낮음 |
| `@Repository` (Spring Data JPA) | SQLAlchemy `Repository` 클래스 + async session | 중간 |
| Entity (`@Entity`) | SQLAlchemy `DeclarativeBase` 모델 | 중간 |
| DTO (`record`) | Pydantic `BaseModel` | 낮음 |
| `sealed interface` 에러 | `Exception` 계층 + pattern matching | 낮음 |
| `@Transactional(readOnly=true)` | `async with session.begin()` 컨텍스트 매니저 | 중간 |
| Spring Batch Job(3 Step) | APScheduler 작업 3개(함수) + 오케스트레이터 | 중간 |
| `java.net.http.HttpClient` (KRX) | httpx.AsyncClient + 재시도(tenacity) | 낮음 |
| `RestClient` (Telegram) | httpx.AsyncClient | 낮음 |
| Actuator `/health` `/prometheus` | `/health` 라우트 + prom exporter | 낮음 |
| Testcontainers PG16 | testcontainers-python PG16 | 낮음 |
| Virtual Thread + ReentrantLock | asyncio + `asyncio.Lock` | 중간 (동시성 모델이 다름) |
| `V1/V2__*.sql` | Alembic revisions (동일 SQL을 op.execute로 래핑) | 낮음 |

---

## 5. 이전 전략 (3안 비교)

### 안 A. Big-bang 일괄 재작성 (권장)
사전-운영 단계이고 사용자/데이터가 없으므로 가장 단순하고 빠름. Java 코드를 삭제하고 Python으로 새로 쓰되 DB 스키마는 유지.

- 장점: 이중 유지 비용 없음, 최종 구조가 깔끔
- 단점: 중간에 기능 검증 공백 구간 발생 → 테스트 먼저 포팅해서 방어

### 안 B. Strangler Fig (병행 운영)
Caddy에서 엔드포인트별로 라우팅을 Java→Python으로 하나씩 돌리는 방식.

- 장점: 각 단계마다 동작 검증 가능
- 단점: 운영 중이 아니므로 병행 가치가 낮음. 컨테이너 2개, 커넥션 풀 2개, 정책 충돌 가능

### 안 C. 도메인 단위 재작성 후 커트오버
도메인(시그널/백테스트/알림)별로 Python 모듈을 완성한 뒤 마지막에 커트오버.

- 장점: 안 A보다 리스크 분산
- 단점: 인터페이스 어댑터를 두 번 짜게 됨

> **권장: 안 A(Big-bang) + 테스트 퍼스트**. 운영 전이라는 결정적 이점을 살린다.

---

## 6. 단계별 작업 (안 A 기준)

### Phase 0. 사전 합의 (0.5일)
- [ ] 본 작업계획서 승인
- [ ] `docs/design/ai-agent-team-master.md` 기술스택 항목 업데이트안 선승인
- [ ] Python 3.12 + uv + FastAPI + SQLAlchemy 2.0 조합 최종 확정

### Phase 1. 스캐폴딩 (1일)
- [ ] `src/backend_py/` 신규 디렉토리 생성 (기존 `src/backend/`는 삭제 직전까지 보존)
- [ ] uv 초기화, `pyproject.toml`(ruff, mypy strict, pytest 설정 포함)
- [ ] 디렉토리: `app/{api,domain,application,adapter,config,batch}` + `tests/`
- [ ] Dockerfile(python:3.12-slim 멀티스테이지) + compose 서비스 교체 브랜치
- [ ] `/health`, `/metrics` 최소 엔드포인트 기동 확인

### Phase 2. DB 계층 (1일)
- [ ] Alembic 초기화, `V1`/`V2` SQL을 revision으로 이식(그대로 `op.execute`)
- [ ] SQLAlchemy 모델 7개(Stock/StockPrice/Signal/ShortSelling/LendingBalance/BacktestResult/NotificationPreference)
- [ ] 파티셔닝은 DB 레벨에서 이미 처리되므로 ORM은 부모 테이블만 매핑
- [ ] Repository 클래스 + async session factory

### Phase 3. 외부 어댑터 (1일)
- [ ] `KrxClient` 이전: httpx + 2초 간격 rate limiter + 재시도(tenacity)
- [ ] `TelegramClient` 이전: httpx, HTML parse 모드
- [ ] 각 어댑터 단위 테스트(httpx MockTransport)

### Phase 4. 도메인/유즈케이스 (2~3일)
- [ ] 시그널 탐지 로직 포팅 — **여기서 pandas 벡터 연산으로 리팩터할지 결정 포인트**
- [ ] 백테스팅 엔진 — vectorbt 도입 여부 결정. 도입 시 코드량 유의미 감소 기대
- [ ] 알림 설정 CRUD
- [ ] 도메인 단위 테스트(pytest, 픽스처)

### Phase 5. API 계층 (1일)
- [ ] FastAPI 라우터 6개(Signal/SignalDetection/Backtest/NotificationPreference/Batch/AdminAuth)
- [ ] Pydantic 스키마(요청/응답) — 기존 DTO와 필드 동일성 보장
- [ ] 어드민 API Key 검증 의존성(Depends) — 기존 `ApiKeyValidator`와 동등

### Phase 6. 배치 (1일)
- [ ] APScheduler 기반 `marketDataCollectionJob` 구현 (collect → detect → notify)
- [ ] 거래일 필터링, 실행시간 기록, 실패 격리(한 Step 실패가 다음 Step 차단)

### Phase 7. 통합 테스트 (1일)
- [ ] testcontainers-python PG16 베이스 픽스처
- [ ] 기존 3개 API 통합 테스트 시나리오 포팅
- [ ] 배치 End-to-End 1개(KRX는 httpx mock)

### Phase 8. 컨테이너/오케스트레이션 (0.5일)
- [ ] `docker-compose.prod.yml`의 `backend` 서비스 이미지·포트·헬스체크 업데이트
- [ ] Caddy `/api` 업스트림은 포트 유지(8080 → 8000으로 바꿀지 결정)
- [ ] `.env.prod` 키 유지(ADMIN_API_KEY / TELEGRAM_* / KRX_AUTH_KEY / POSTGRES_*)

### Phase 9. 정리 (0.5일)
- [ ] `src/backend/` 삭제 (Java)
- [ ] `build.gradle`, `gradlew*`, `gradle/` 삭제
- [ ] `docs/design/ai-agent-team-master.md` 기술스택/부록 K 갱신
- [ ] 에이전트 정의(`agents/08-backend/`)에 Python 컨벤션 반영
- [ ] `CLAUDE.md` Backend Conventions 섹션 Python(PEP 8 + ruff) 기준으로 교체
- [ ] `runbook.md` 프로덕션 기동 절차 갱신

**총 추정: 8.5~9.5 영업일 (1인 기준)**

---

## 7. 리스크와 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Spring Batch 트랜잭션/재시작 의미론을 APScheduler에서 1:1 재현 불가 | 중 | 각 Step을 DB 트랜잭션으로 감싸고, 실패 Step은 멱등 재실행 가능하게 설계. 본격 파이프라인 필요 시 Prefect로 교체 여지 명시 |
| Virtual Thread→asyncio 전환 시 CPU 바운드 작업(백테스트) 병목 | 중 | CPU 바운드는 `run_in_executor` 또는 `concurrent.futures.ProcessPoolExecutor`로 분리 |
| Pydantic/SQLAlchemy 타입 정의량이 예상보다 큼 | 저 | 엔티티 7개/DTO 수십 개 수준 — 1~1.5일 안에 처리 가능 |
| KRX 응답 포맷 변경 회귀 | 중 | 기존 Java 구현을 **삭제 전에 통합 테스트 픽스처(응답 JSON)로 캡처** 해두고 Python 테스트에 재사용 |
| 기존 `decision-registry.md`에 "Java 선정" 의사결정 기록이 남아 있음 | 저 | 새 의사결정 레코드 추가(덮어쓰지 않음) — 감사 이력 보존 |
| 작업 중간 중단 시 Java/Python 동시 존재 기간 | 저 | 안 A라도 `src/backend_py/`로 병행 저장 후 Phase 9에서 일괄 제거 |

---

## 8. 문서 갱신 대상

**수정**
- `docs/design/ai-agent-team-master.md` — 기술스택 표(L58), 부록 K(Java 21 패턴), Teammate 정의(L2367, L2618)
- `CLAUDE.md` — Tech Stack 표, Backend Conventions
- `agents/08-backend/AGENT.md` — 시스템 프롬프트
- `pipeline/artifacts/10-deploy-log/runbook.md` — 기동/배포 절차
- `README` 류(있다면)

**신규**
- `docs/migration/java-to-python-plan.md` (본 문서)
- `pipeline/decisions/` 에 전환 결정 레코드 추가

**그대로 유지**
- `pipeline/artifacts/04-db-schema/ddl.sql`, `query-strategy.md`
- `pipeline/artifacts/03-design-spec/feature-spec.md`
- `ops/caddy/Caddyfile` (업스트림 포트만 선택적으로 변경)

---

## 9. Go / No-Go 체크리스트 (착수 직전)

- [x] Python 3.12 + FastAPI + SQLAlchemy 2.0 조합 확정
- [x] 백테스트 라이브러리: vectorbt 확정
- [x] 배치 오케스트레이션: APScheduler 확정
- [x] `src/backend/` 삭제는 Phase 9 일괄
- [x] 디렉토리 전략: `src/backend_py/` 신규
- [ ] **남은 착수 전 작업**: 기존 Java 통합 테스트에서 KRX/Telegram 응답을 고정 픽스처(JSON)로 캡처 → Python 테스트 재사용 (Phase 1 직전에 수행)

---

## 11. 추가 스코프 — 포트폴리오 + AI 분석 리포트 (신규 도메인)

### 11.1 포트폴리오 도메인

**목적**: 내 실계좌 보유 종목을 앱에 등록(또는 자동 수집) 후, 기존 시그널/백테스트 엔진과 연계해 **실현/미실현 손익, 시그널 정합도, 가상 백테스트 성과 vs 실거래 성과 비교**를 제공한다.

#### 증권사 API 연동 현실 (2026-04 기준)

| 옵션 | 제약 | 권장도 |
|------|------|--------|
| **키움 OpenAPI+ (OCX/COM)** | **Windows + 32bit Python 전용** — 리눅스/Docker 불가. 별도 Windows 워커 VM 필요 | ▲ 낮음 (단독 서버 운영 구조와 충돌) |
| **키움 REST API** | 2024년 공개됐으나 OCX 대비 제공 TR 범위 제한. 실거래 주문 가능 여부·실명 계좌 연결 정책 재확인 필요 | ◎ 확인 필요 (가장 먼저 조사) |
| **한국투자증권(KIS) OpenAPI** | **완전 REST·크로스플랫폼**, 파이썬 레퍼런스 풍부(`pykis`, 공식 샘플), 모의·실거래 모두 지원 | ★ **실질 1순위** |
| **LS증권 REST API** | REST, 국내 개인 투자자 활용 사례 존재 | ☆ 2순위 대안 |
| **수동 등록 (Fallback)** | 사용자가 종목/수량/평단가 직접 입력. 시세는 기존 KRX 수집 데이터로 계산 | ○ **무조건 병행 구현** (API 불가 시 단독, 가능 시 자동 동기화의 휴먼 오버라이드) |

**확정 경로 (2026-04-18)**:
1. **KIS REST API 단독 착수** (모의투자 전용)
   - 베이스 URL: `https://openapivts.koreainvestment.com:29443` (모의)
   - APP Key/Secret은 모의투자용으로 별도 발급 → `.env.prod`에 `KIS_APP_KEY_MOCK`, `KIS_APP_SECRET_MOCK`, `KIS_ACCOUNT_NO_MOCK`
   - 실거래 계좌 연동은 **본 단계에서 차단** (코드상 모의 URL 하드코드 + 환경변수명에 `_MOCK` 접미사로 오사용 방지)
2. **수동 등록 기능을 우선 완성** 후 KIS 동기화를 덧붙이는 순서 유지 (Fallback 보장)
3. **키움 REST API는 조사만 수행** — 별도 스파이크 문서(`docs/research/kiwoom-rest-feasibility.md`)로 분리, 본 마이그레이션 일정에서 제외

#### 데이터 모델 (추가 테이블 초안)

| 테이블 | 역할 |
|--------|------|
| `brokerage_account` | 증권사/계좌별칭/연결방식(manual/kis_rest_mock) · 환경(mock/real — MVP는 mock 고정) |
| `portfolio_holding` | 계좌별 보유종목·수량·평단가·매수일 |
| `portfolio_transaction` | 매수/매도 거래 이력 (수동 입력 또는 API 동기화) |
| `portfolio_snapshot` | 일별 평가금액·손익 스냅샷 (성과 그래프·드로다운 계산) |

#### 신규 API (FastAPI 라우터)
- `POST /api/portfolio/accounts` — 계좌 등록
- `POST /api/portfolio/holdings` — 보유 종목 수동 등록
- `POST /api/portfolio/holdings/sync` — 증권사 API 동기화(가능한 연결만)
- `GET  /api/portfolio/performance` — 기간별 성과(수익률/샤프/MDD)
- `GET  /api/portfolio/signal-alignment` — 보유 종목과 탐지 시그널 정합도

### 11.2 AI 종목 분석 리포트 도메인

#### LLM 공급자 비교 (본 프로젝트 관점)

| 공급자 | 대표 모델/엔드포인트 | 핵심 강점 | 약점 | 본 프로젝트 적합 역할 |
|--------|---------------------|----------|------|---------------------|
| **Perplexity** | `sonar-pro`, `sonar-reasoning` | **API 자체가 웹 검색 + 출처 인용 내장**. 공시/뉴스/이슈를 당일 반영 | 장문 추론·일관성은 Claude/GPT 대비 약간 낮음 | **실시간 공시/뉴스/이슈 수집 레이어** |
| **Anthropic Claude** | Sonnet 4.6, Opus 4.7 (1M ctx) | 장문 한글 리포트 품질·뉘앙스 최상, 긴 컨텍스트에서 재무제표/공시 다수 문서 동시 분석, extended thinking으로 단계적 논증 | 내장 웹 검색 없음(도구 연결 필요) | **종합 분석 리포트 본문 생성** |
| **OpenAI** | GPT-4.1, GPT-4o | 구조화 출력(strict JSON schema), 툴 콜링·Assistants API 성숙, 코드 인터프리터로 수치 분석 | 한글 장문 톤은 Claude가 일부 우위 | **정형 파이프라인 단계**(지표 요약·태깅·JSON 스키마 반환) |
| **Google Gemini** | Gemini 2.5 Pro | **Google Search Grounding 네이티브**, 멀티모달(차트 이미지 해석), 긴 컨텍스트 | 한국 시장 특화 프롬프트 튜닝 노하우는 상대적 부족 | 보조/대체재(시각 자료 해석·검색 보강) |

#### 권장 구성 — Plan A (이상적, 이후 확장용)

```
[수집] Perplexity Sonar-Pro  →  [분석] Claude Sonnet 4.6
```

- 공시/뉴스 신선도 최상 + 한글 장문 리포트 품질 최상의 조합
- API Key 추가 발급이 가능해지는 시점(§12 #9 변경)에 이 구성으로 전환

#### **착수 구성 — Plan B (OpenAI GPT-5.4 계열 + DART 공식 API, 2026-04-18 확정)**

출처: OpenAI 공식 모델 페이지(2026-04 확인). GPT-5.4 계열은 3종 모두 **reasoning + web_search + file_search + functions** 내장. 지식 컷오프 2025-08-31, 최대 출력 128K.

##### 신뢰 출처 설계 (3-Tier) — **web_search 단독 금지**

리포트 신뢰도 확보를 위해 LLM 웹 검색을 Tier 2로 강등하고, 숫자와 공시 원문은 공식 API로 직접 수집한다.

| Tier | 출처 | 파이프라인에서 역할 | 본문 인용 허용 범위 |
|------|------|-------------------|-------------------|
| **1 (공식 API)** | DART OpenAPI (opendart.fss.or.kr), KRX, 한국은행 ECOS | **재무 숫자·공시 원문의 유일한 원천** | 숫자·공시 사실 전량 |
| **2 (도메인 허용 web_search)** | dart.fss.or.kr, kind.krx.co.kr, krx.co.kr, bok.or.kr, yna.co.kr, yonhapnews.co.kr, mk.co.kr, hankyung.com, edaily.co.kr, newsis.com, finance.naver.com | **정성 이슈·시장반응·업황 컨텍스트** 수집 | 정성 정보만. 숫자는 Tier 1과 교차검증 후에만 사용 |
| **3 (차단)** | 블로그·커뮤니티·재가공 매체·개인 매체 | 파이프라인 미진입 | 금지 |

- `web_search` 도구 호출 시 `filters.allowed_domains`에 Tier 2 리스트 하드 바인딩
- 수집 결과 각 항목에 `source_tier`, `source_url`, `published_at` 메타를 반드시 부여
- 분석 모델 프롬프트에 **역할 분리 제약** 명시: "숫자 인용은 Tier 1 payload에서만, 정성 서술은 Tier 2 payload에서만 — 그 외 추론/일반지식으로 숫자 생성 금지"
- 리포트 말미에 **출처 리스트 + Tier 뱃지** 자동 삽입

##### DART OpenAPI 연동 요건 (신규 외부 어댑터)
- 무료 인증키 발급(사용자 수행), `.env.prod`에 `DART_API_KEY`
- 호출 지점: 기업개황, 사업보고서 단일회사 주요계정, 주요사항보고 목록/본문, 임원·주요주주 소유보고
- Rate limit: 일 10,000건 수준 → DB에 원문 캐시(24h~30일, 공시 종류별 TTL 차등)
- `src/backend_py/app/adapter/out/external/dart_client.py` 신설


| 계층 | 모델 ID | 컨텍스트 | 본 프로젝트 단계 |
|------|---------|---------|-----------------|
| Flagship | **gpt-5.4** | 1M | **분석 레이어** — 재무/기술/시그널/뉴스 종합 리포트 생성 |
| Mid | **gpt-5.4-mini** | 400K | **수집 레이어** — web_search 로 당일 공시·뉴스 수집·요약 |
| Nano | **gpt-5.4-nano** | 400K | **리패키징** — 프론트 카드 UI용 strict JSON 변환 |

```
[수집 Tier1]  DART OpenAPI + KRX + ECOS  (HTTP 직접)
                 ↓ 재무·공시·거시 원문(정규화 JSON)
[수집 Tier2]  gpt-5.4-mini + web_search  (allowed_domains 하드 바인딩)
                 ↓ 정성 이슈·뉴스 요약 + 출처 URL + tier 메타
[병합]        Tier1 payload + Tier2 payload → 단일 컨텍스트
                 ↓
[분석]        gpt-5.4  (1M 컨텍스트, 역할 분리 프롬프트)
                 → 숫자는 Tier1만, 정성은 Tier2만 인용하도록 강제
                 ↓ strict JSON (요약/강점/리스크/전망/의견 + 섹션별 근거 URL)
[리패키징]    gpt-5.4-nano → 프론트 카드 스키마
```

- **장점**: 단일 공급자·키 1개·빌링 1개, 전 계층 reasoning 내장, web_search 네이티브, strict JSON 안정, 1M 컨텍스트로 재무제표·과거 뉴스 다량 동시 주입 가능
- **타협점**: 공시·뉴스 신선도는 Perplexity 전용 엔진 대비 약간 낮을 수 있음. 한글 장문 톤은 Claude 대비 약간 딱딱할 수 있음 — 프롬프트 튜닝과 reasoning effort 파라미터로 커버
- **지식 컷오프 주의**: 2025-08-31. **그 이후의 시장 사건·공시는 반드시 web_search 툴 경로로** 확보. 분석 모델이 자체 지식으로 최신 사건을 답하지 못하도록 프롬프트에서 명시 제약
- **교체 경로 설계**: AI 공급자 추상화 레이어(`app/adapter/out/ai/`)에 `LLMProvider` 프로토콜을 두고 `OpenAIProvider`만 우선 구현 → 추후 `PerplexityProvider`/`ClaudeProvider`를 같은 포트 뒤에 꽂아 `AI_PROVIDER` 환경변수로 Plan A 전환
- **비용 절감 라우팅**: 단순 수집/리패키징을 mini/nano로 분리해 **flagship 호출을 분석 단계 1회로 한정** → 리포트당 토큰 비용 대폭 절감

#### 운영 고려
- API 키는 `.env.prod`에 `OPENAI_API_KEY` **필수** (Plan A 전환 시 `PPLX_API_KEY`, `ANTHROPIC_API_KEY` 추가), Caddy를 통해 외부로 절대 노출하지 않음
- 캐시 전략: 동일 종목·동일 날짜 리포트는 Postgres에 저장해 **24h TTL** 재사용 (LLM 비용 방어)
- 컴플라이언스: 리포트 말미에 "투자 참고용·투자 책임은 본인" 고지 고정 삽입
- Rate limit: 지수 백오프 + web_search 실패 시 뉴스 공백으로 폴백하고 리포트에 명시
- **공급자 추상화**: `app/adapter/out/ai/` 밑에 `LLMProvider` 프로토콜과 `OpenAIProvider` 구현 1개만 우선 작성. 환경변수 `AI_PROVIDER=openai|perplexity+claude`로 런타임 전환 가능하도록 설계

### 11.3 AI 리포트 발행 모드

**확정: 실시간 온디맨드** — 사용자가 종목 상세/포트폴리오 항목에서 "분석 리포트 요청" 클릭 시 파이프라인 실행.

- **1차 호출 경로 (Plan B)**: DART/KRX/ECOS(Tier1 숫자·공시) + gpt-5.4-mini web_search(Tier2 정성, 도메인 화이트리스트) → gpt-5.4(분석, 역할 분리 프롬프트) → gpt-5.4-nano(프론트 JSON) → DB 저장
- **캐시 규칙**: `(종목코드, 발행일(KST 00:00 기준))` 복합키로 **24h TTL** — 같은 날 동일 종목 재요청은 DB 캐시 반환 (비용 방어의 핵심)
- **강제 재생성**: `force_refresh=true` 쿼리 파라미터로 캐시 우회 (일 N회 제한 필요 시 어드민 API Key 보호)
- **실패 격리**: web_search 실패 시 뉴스 공백으로 진행하고 리포트 말미에 "뉴스 데이터 일시 부재" 표기. 분석 단계 실패 시 전체 요청 500
- **일 1회 자동 배치**는 본 단계에서 **미도입** — 보유 종목 수 증가 시 비용 예측 가능한 시점에 재논의

### 11.4 신규 Phase (마이그레이션 Phase 이후 연속)

| Phase | 작업 | 추정 |
|-------|------|------|
| **P10. 포트폴리오 스키마·수동 등록** | Alembic revision, 4개 테이블, CRUD API, 성과 계산기 | 1.5일 |
| **P11. KIS REST(모의) 연동** | 모의 APP Key 발급·토큰 관리(OAuth 만료 6h)·`httpx` 클라이언트·잔고/체결 동기화 잡 | 2일 |
| **P12. 포트폴리오 ↔ 시그널 정합도** | 기존 Signal 테이블과 조인, "보유 종목에 뜬 시그널" 리포트 | 0.5일 |
| **P13a. 신뢰 출처 어댑터** | DART OpenAPI 클라이언트(`dart_client.py`), ECOS 클라이언트, 응답 정규화·캐시 | 1일 |
| **P13b. AI 분석 파이프라인** | `LLMProvider` 추상 + `OpenAIProvider`(web_search + `allowed_domains` 화이트리스트 + strict JSON) + Tier 병합기 + 역할 분리 프롬프트 + 24h 캐시 + 온디맨드 라우트 | 2일 |
| **P14. 프론트 리포트 뷰** | 포트폴리오 대시보드 + AI 리포트 상세 페이지 + 재생성 버튼 | 1.5일 |
| **P15. 키움 REST 가용성 조사 (별도 트랙)** | 문서 스파이크만. 제공 TR 범위·제약·KIS 대비 차별점 정리. 구현 없음 | 0.5일 |

**추가 소계: 9일** → 마이그레이션 9일 + 추가 9일 = **약 18 영업일(1인)**

---

## 12. 확정 결정 사항 (2026-04-18)

| # | 항목 | 확정 |
|---|------|------|
| 1 | Python 버전 | **3.12** |
| 2 | 백테스팅 라이브러리 | **vectorbt** |
| 3 | 배치 오케스트레이션 | **APScheduler로 출발**, 복잡도 상승 시 Prefect 검토 |
| 4 | 커트오버 시점 | **Phase 9 일괄** (Java 스택은 마지막에 한 번에 제거) |
| 5 | 디렉토리 전략 | **`src/backend_py/` 신규 생성**, Phase 9에서 `src/backend/` 삭제 (Phase 9 종료 후 rename은 선택) |
| 6 | 증권사 API | **KIS 단독 착수**. 키움 REST는 P15 조사 트랙으로 분리(구현 없음) |
| 7 | 연동 계좌 범위 | **모의투자 전용** (MVP). 실거래 URL·키는 코드 진입 차단 |
| 8 | AI 리포트 모드 | **실시간 온디맨드** + 24h DB 캐시. 일 1회 배치는 미도입 |
| 9 | AI 스택 (착수) | **OpenAI GPT-5.4 계열 단독** — 수집: `gpt-5.4-mini` + web_search / 분석: `gpt-5.4` (1M ctx, reasoning 내장) / 리패키징: `gpt-5.4-nano`. 공급자 추상화 레이어(`LLMProvider`)로 구현해 추후 Plan A(Perplexity+Claude)로 환경변수 전환만으로 교체 |

### 12.1 남은 착수 전 작업
- [ ] 사용자가 KIS 모의투자 APP Key/Secret 발급 및 `.env.prod`에 주입 (`KIS_APP_KEY_MOCK` / `KIS_APP_SECRET_MOCK` / `KIS_ACCOUNT_NO_MOCK`)
- [ ] `OPENAI_API_KEY` 주입 (사용자 제공 예정)
- [ ] `DART_API_KEY` 발급(무료, opendart.fss.or.kr) 및 주입 — **신뢰 출처 1티어의 핵심**
- [ ] Java 통합 테스트의 KRX/Telegram 응답 JSON 픽스처 캡처 (Phase 1 직전)
- [ ] (선택/후속) Plan A 전환용 `ANTHROPIC_API_KEY`, `PPLX_API_KEY`는 예산/필요 확정 후 추가
