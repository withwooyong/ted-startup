# Session Handoff

> Last updated: 2026-04-18 (KST, 저녁)
> Branch: `master` (origin/master 대비 **15 commits ahead + 본 세션 Phase 8/9 커밋 대기** — 푸시 대기)
> Latest commit: `610918a` — 코드 리뷰 fix: M1·M2·M3

## Current Status

Java → Python 전면 이전 프로젝트가 **Phase 1~9 완료** 상태. 전체 테스트 **52/52 PASS**, 로컬 Docker 스모크 검증 완료(alembic migrate + /health + /api 응답 정상). **Spring Boot 스택 물리 제거 + 문서 4종(CLAUDE.md, 마스터 설계서, 08-backend AGENT.md, runbook) 갱신 완료**. 다음 단계는 **§11 신규 도메인(P10 포트폴리오 → P13 AI 리포트)** 착수. 아직 원격에 푸시하지 않았음.

## Completed This Session

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | 운영 설정 소소한 정리(이전 세션 M-1~M-4) | `c417977` | Caddyfile, docker-compose.prod.yml, application.yml |
| 2 | Java→Python 전환 작업계획서 + .env.prod.example 확장 | `f66cfdd` | `docs/migration/java-to-python-plan.md`, `.env.prod.example` |
| 3 | 환경변수 검증 스크립트 + KRX/Telegram 픽스처(블로커 문서 포함) | `cb5bd24` | `scripts/validate_env.py`, `pipeline/artifacts/fixtures/**` |
| 4 | Phase 1 스캐폴딩(FastAPI + uv + Dockerfile) | `e669fed` | `src/backend_py/**` (21 파일) |
| 5 | KRX 계정 유효성 검증 스크립트 | `127625d` | `scripts/validate_krx.py` |
| 6 | Phase 2 DB 계층(SQLAlchemy async + Alembic + Repository) | `f00b2cf` | `app/adapter/out/persistence/**`, `migrations/versions/**` |
| 7 | Phase 3 외부 어댑터(KrxClient + TelegramClient) | `e9f3c75` | `app/adapter/out/external/**` |
| 8 | Phase 4 UseCase·서비스(vectorbt 리라이트) | `3724d1e` | `app/application/**` |
| 9 | 코드 리뷰 fix H1/M1/M4 | `bda6e42` | NotificationService, SignalDetectionService |
| 10 | Phase 5 API 계층(FastAPI 라우터 8종) | `31ea518` | `app/adapter/web/**` |
| 11 | Phase 6 APScheduler 배치 파이프라인 | `65b4bb6` | `app/batch/**` |
| 12 | Phase 7 컨테이너 전환 + E2E | `b5e3cc8` | `scripts/entrypoint.py`, `docker-compose.prod.yml` |
| 13 | 코드 리뷰 fix M1/M2/M3 | `610918a` | entrypoint·scheduler·market_data_job |
| 14 | **Phase 8 — Java 스택 물리 제거** | _본 세션 커밋 대기_ | `src/backend/` 전체(69 tracked + .gradle/build 언트랙) |
| 15 | **Phase 9 — 문서·에이전트 갱신** | _본 세션 커밋 대기_ | `CLAUDE.md`, `docs/design/ai-agent-team-master.md`, `agents/08-backend/AGENT.md`, `pipeline/artifacts/10-deploy-log/runbook.md`, `docs/migration/java-to-python-plan.md` |

**누적 규모**: 13 커밋 + 본 세션 Phase 8/9 / 84+ 파일 변경 / **+7,483+ / -17+ 라인**.
**테스트**: Phase 1~7 전부 포함 **52/52 PASS**. Phase 8/9 는 문서/삭제 작업이라 테스트 영향 없음.

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **§11 신규 스코프 — 포트폴리오** | **다음 착수 대상** | P10 (Alembic 4테이블 + 수동 등록 CRUD + 성과 계산기, 1.5일) → P11 (KIS 모의 REST, 2일) → P12 (시그널 정합도, 0.5일) |
| 2 | **§11 신규 스코프 — AI 분석 리포트** | pending | P13a (DART/ECOS 어댑터, 1일) → P13b (LLMProvider + OpenAI GPT-5.4 3단 + Tier 병합기 + 24h 캐시, 2일) → P14 프론트 뷰(1.5일) |
| 3 | **키움 REST API 가용성 조사** | pending | P15 (0.5일 문서 스파이크) |
| 4 | **KRX 대차잔고 pykrx 스키마 불일치 복구** | pending | 현재 fallback 로 0 rows 반환 — 직접 KRX 호출 또는 pykrx 버전업으로 해결 |
| 5 | **원격 푸시** | pending | 사용자 명시 지시 후에만 — 17+ 커밋 누적 (Phase 8/9 포함) |

## Key Decisions Made

1. **Big-bang 재작성 채택** — 사전-운영 단계라는 결정적 이점. Strangler Fig / 도메인 분할 경로는 과투자로 판단.
2. **Python 3.12 + FastAPI + SQLAlchemy 2.0 (async, asyncpg) + Alembic** 스택 확정.
3. **vectorbt + pandas 벡터화 전면 리라이트** — BacktestEngineService 의 Java TreeMap 순회를 피벗 테이블 + shift(-N) 행렬 연산으로 대체. SignalDetectionService 는 Java 로직 1:1 포팅(scoring 상수·cap 유지)하되 rolling MA는 pandas.
4. **Alembic 마이그레이션은 동기 psycopg2**, 앱 런타임은 asyncpg — asyncpg 의 다중 statement 제약 회피를 위한 표준 분리 패턴.
5. **디렉토리 전략**: `src/backend_py/` 신규 생성(기존 `src/backend/` 는 Phase 9에서 일괄 삭제). `app/adapter/in/web/` 은 Python `in` 예약어 파싱 문제로 `app/adapter/web/` 로 평탄화.
6. **KIS 모의투자 단독 착수** — 실거래 URL·키 코드상 진입 차단. 키움은 P15에서 조사만.
7. **AI 스택 Plan B (OpenAI GPT-5.4 단독)** 착수 — 현재 사용자가 즉시 제공 가능한 키 제약에 맞춤. 수집 mini + 분석 flagship(1M ctx) + 리패키징 nano 의 3단 구성. 공급자 추상화 `LLMProvider` 로 Plan A(Perplexity+Claude) 로 코드 수정 없이 교체 가능하게 설계.
8. **신뢰 출처 3-Tier** — DART/KRX/ECOS 공식 API(Tier1, 숫자·공시 원문) / web_search 도메인 화이트리스트(Tier2, 정성) / 블로그·커뮤니티(Tier3, 차단). 분석 프롬프트에 "숫자는 Tier1만, 정성은 Tier2만 인용" 역할 분리 제약 강제.
9. **batch_job_log 테이블 기록은 Phase 6 에서 생략** — Java 원본도 기록 로직 부재. 로거 출력만 사용. 향후 관측성 필요 시 도입.

## Known Issues

### 보안·품질 이슈 (수정 완료)
- H1 NotificationService N+1 쿼리 → `list_by_ids` 벌크 조회로 교체(`bda6e42`)
- M4 Telegram HTML escape + 한글 라벨 매핑(`bda6e42`)
- M1 uvicorn `--forwarded-allow-ips "*"` → Docker 사설 대역 제한(`610918a`)
- M2 스케줄러 `date.today()` → `datetime.now(KST).date()` 타임존 명시(`610918a`)

### 후속 처리 대상 (Phase 8 이후)
- **M2 /health env 필드 노출** (정보 누설) — 외부 `/health` 는 `{"status":"UP"}` 만, 상세는 `/internal/info` 로 분리 권고
- **M1 /metrics 공개 노출** — Caddyfile IP 게이팅 또는 `/internal/metrics` 경로 이동 권고(Phase 8 배포 강화 시)
- **M3 uv 컨테이너 이미지 digest 미고정** (`ghcr.io/astral-sh/uv:0.11`) — 공급망 안정성 강화용
- **M4 Dockerfile `useradd --shell /bin/bash`** — 서비스 계정엔 `/usr/sbin/nologin` 권장
- **settings.py 테스트 미흡** — 환경변수 오버라이드·기본값·`.env` 우선순위 커버 부족

### 도메인·운영 이슈
- **KRX 익명 차단**(2026-04 확인): `data.krx.co.kr` 가 익명 요청을 `HTTP 400 LOGOUT` 으로 거부. 프로덕션 Java 배치가 수개월간 데이터를 못 받고 있었음(DB 3개 테이블 0 rows 로 확증). pykrx 도 `KRX_ID/KRX_PW` 세션 기반 접근으로 전환. `scripts/validate_krx.py` 로 복구 확인 완료. **대차잔고**는 pykrx 스키마 불일치로 여전히 0 rows → 어댑터 fallback 로 격리 처리, 후속 복구 필요.
- **batch_job_log 미기록**: 운영 관측성 한계. 추후 도입 권고.

## Context for Next Session

### 사용자의 원래 목표
주식 시그널 탐지·백테스팅 서비스의 향후 확장(수치 연산·ML·다종 데이터소스) 을 위해 Java/Spring Boot 백엔드를 **Python 전면 이전**. 동시에 §11 신규 스코프(포트폴리오 현황 + AI 종목 분석 리포트) 도입.

### 선택된 경로와 이유
- **Big-bang**: 실사용자·영구 데이터 없는 사전-운영 단계라 병행/점진 교체가 과투자. `docs/migration/java-to-python-plan.md` 가 확정 계획서.
- **KIS 모의 + OpenAI 단독**: 사용자가 즉시 제공 가능한 키 제약 + 실거래 리스크 회피. 공급자 추상화로 이후 Plan A(Perplexity+Claude)·실거래 전환 가능.
- **신뢰 출처 3-Tier**: "LLM 이 어디서 주워 온 숫자를 리포트에 박을 수 있는가" 질문에 **절대 불가** 로 못 박음. Tier1(공식 API 원문)만 숫자 근거 인정.

### 사용자 선호·제약
- **커밋 메시지는 반드시 한글** (글로벌 CLAUDE.md).
- **푸시는 사용자 명시 지시 후에만** — 15 커밋이 로컬에 쌓여 있으나 푸시 대기.
- **값이 민감한 명령 차단**: `.env.prod` cat / env 값 로깅 등은 사용자가 즉시 차단. 모든 검증 스크립트는 값 비노출 원칙 준수(`_key_structure` 같은 구조 진단만).
- **작업 단위 커밋 분리 선호**: 논리 묶음별로 Phase/리뷰 fix 를 별도 커밋.

### 다음 세션 선택지
- **A.** Phase 8/9 정리 (Java 스택 제거 + 문서 갱신, 약 0.5~1일) — 이전 과제를 깔끔히 마무리
- **B.** §11 진입 (포트폴리오 + DART + OpenAI, P10~P13 ~7일) — 신규 도메인 앞당김
- **C.** 남은 M 이슈(우선순위 M2 `/health` env 누설, M1 `/metrics` 게이팅) 보강 후 A/B

A → B 순이 계획서 권장. C 는 A 안에 묶어 처리 가능.

## Files Modified This Session

```
 84 files changed, 7,483 insertions(+), 17 deletions(-)
```

주요 디렉토리 분포:
- `src/backend_py/app/` 신규 (어댑터 out/in + application + batch + config) — 약 2,000 라인
- `src/backend_py/tests/` 신규 — 약 1,600 라인 (52 테스트)
- `src/backend_py/migrations/` + Alembic 설정 — 약 340 라인
- `src/backend_py/pyproject.toml` + `uv.lock` — 의존성 13종 추가
- `scripts/validate_env.py` + `scripts/validate_krx.py` + `src/backend_py/scripts/entrypoint.py` — 운영 스크립트 3종
- `docker-compose.prod.yml`, `ops/caddy/Caddyfile`, `src/backend_py/Dockerfile` — 배포 전환
- `docs/migration/java-to-python-plan.md`, `pipeline/artifacts/fixtures/**`, `.env.prod.example` — 설계·참조 문서
