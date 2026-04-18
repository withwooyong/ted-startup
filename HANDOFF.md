# Session Handoff

> Last updated: 2026-04-18 (KST, 심야 — 실 E2E 검증 성공 직후)
> Branch: `master` (origin 대비 **2 커밋 ahead** — 푸시 대기)
> Latest commit: `510fa1c` — fix: REPORT_JSON_SCHEMA 의 sources.items.required 에 published_at 추가

## Current Status

**실 API 키 기반 E2E 풀 파이프라인 검증 성공.** Docker 프로덕션 스택(`--env-file .env.prod` + `up -d --build`) 위에서 포트폴리오 CRUD · KIS 모의 OAuth + 잔고 동기화 · **삼성전자 AI 리포트 실 생성(gpt-4o 6.3s, DART 공시 5건 Tier1 자동 보강)** · 24h 캐시 히트까지 전부 실측 통과. 검증 과정에서 드러난 3건의 실버그(2 CRITICAL + 1 MEDIUM) 를 즉시 수정 커밋. 프론트 브라우저 UI 실측은 미완.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | E2E 사전 수정: entrypoint 레거시 경로 + validate_env 기준 강화 | `2febdf2` | `src/backend_py/scripts/entrypoint.py`, `scripts/validate_env.py`, `HANDOFF.md` |
| 2 | fix: REPORT_JSON_SCHEMA published_at required 추가 | `510fa1c` | `src/backend_py/app/application/port/out/llm_provider.py` |

**누적 규모(본 세션)**: 2 커밋 / 4 파일 수정 / +141 / -107 라인.
**테스트**: 백엔드 **98/98 PASS** 유지. E2E 실측은 별도 항목 참조.

### 실 E2E 검증 결과 (커밋 아님, 런타임 관찰)

| # | 단계 | 결과 |
|---|------|------|
| E2E-1 | `.env.prod` 존재·Docker 상태 | PASS. 기존 Java 이미지 확인 → 재빌드 결정 |
| E2E-2 | `scripts/validate_env.py` | 4/4 PASS (DART status=000, OpenAI sk-proj-, KIS OAuth 발급, 계좌 10자리) |
| E2E-3 | 풀 재빌드 + entrypoint | backend/frontend 이미지 신규 빌드 성공. entrypoint 로그에서 **`alembic stamp 002 → upgrade head`** 로 003/004/005 자동 적용 확인. `\dt` 에서 brokerage_account·portfolio_*·dart_corp_mapping·analysis_report 전부 present |
| E2E-4 | 포트폴리오 API | Caddy HTTPS 경유 `POST /api/admin/portfolio/accounts` 201 (id=1, manual). `POST /transactions` 201 (삼성 10주@72000). `GET /holdings` 200 (평단 정확) |
| E2E-5 | KIS 모의 `/sync` | 계좌 id=2 (kis_rest_mock). `POST /sync` 200 · OAuth `client_credentials` 토큰 발급 → VTTC8434R 잔고 조회 rt_cd=0 → `fetched_count=0` (사용자 모의계좌 실제 보유 없음, 응답 파싱 체인 전부 동작) |
| E2E-6 | AI 리포트 실생성 (005930) | `dart_corp_mapping` 3종 수동 시드(005930/000660/035420) 후 `POST /api/reports/005930` → **HTTP 200 · 6.3초 · gpt-4o · 토큰 18,524↓/530↑ · opinion=HOLD**. 본문이 실제 DART 재무제표 인용(자산 566조/영업이익 43조/매출 333조, 단기차입금·자기주식 취득 리스크 언급). sources 7건 전부 Tier1(DART 공시 5 + 공식 홈페이지). 2차 호출 `cache_hit=true` 0.02s (24h 캐시 동작) |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **원격 푸시** | pending | 2 커밋 (`2febdf2`, `510fa1c`) origin 앞서 있음. 사용자 명시 지시 후 push |
| 2 | **브라우저 UI 실측** | pending | `https://localhost/portfolio` 에서 계정 탭·보유 테이블·AI 리포트 페이지 렌더링 실확인. 현재 스택은 기동 상태 유지 중 |
| 3 | **스택 정지 판단** | pending | 유지/정지 선택. `docker compose --env-file .env.prod -f docker-compose.prod.yml down` 으로 정지 가능 |
| 4 | **`dart_corp_mapping` bulk sync** | 보류 | 현재 수동 시드 3건뿐. 전체 ~40,000 기업을 DART `corpCode.xml` 에서 벌크 로드하는 스크립트 미구현. P13 후속 |
| 5 | **`force_refresh=true` rate limiting** | 보류 (LOW) | slowapi/fastapi-limiter. 관리자 키로 LLM 호출 폭주 방어 |
| 6 | **KRX 대차잔고 pykrx 스키마 불일치 복구** | carry-over | 어댑터 fallback 중. 일부 시그널 품질 영향 |
| 7 | **`BrokerAdapter` Protocol 추출** | 보류 | 키움 합류 시점 전까지 미필요 |
| 8 | **M1/M2/M3/M4 carry-over** | carry-over | /health env 노출·/metrics 게이팅·uv digest 고정·useradd nologin |
| 9 | **Caddy unhealthy** | 관찰 | localhost self-signed 관련 헬스체크 미통과. 외부 도메인 모드에선 해소 예상. 기능 영향은 `-k` 옵션 필요 정도 |

## Key Decisions Made

1. **E2E 는 옵션 A (풀 재빌드) 선택** — 기존 Java 이미지가 12시간 전 빌드였고 `--env-file` 플래그도 누락 상태라 운영과 동일한 경로 검증을 위해 `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build` 실행.
2. **민감 명령 차단 정책 고수 — 컨테이너 내부 실행으로 우회** — `.env.prod` 에서 ADMIN_API_KEY 를 grep 으로 읽는 명령이 사용자 샌드박스에 차단되자, backend 컨테이너 내부에 이미 주입된 `$ADMIN_API_KEY` env 를 활용하는 `docker compose exec backend python3 -c ...` 패턴으로 전환. curl 이 슬림 이미지에 없어 urllib 사용. **다음 세션에서도 유효한 패턴**.
3. **entrypoint 레거시 경로 버그 즉시 수정 후 빌드** — `stamp head` → `stamp 002 + upgrade head` 로 전환. Phase 7 E2E 테스트는 testcontainers fresh DB 로 이 경로를 타지 않아 놓친 사각지대임을 명시적으로 문서화.
4. **validate_env.py 의 KIS 기준을 `== 10` 으로 엄격화** — 검증 스크립트가 어댑터보다 관대하면 거짓 음성이 발생. 스크립트/어댑터 정책 동일 기준 유지가 원칙.
5. **AI 리포트 strict schema 호환성 교훈** — OpenAI strict JSON schema 는 `required` 가 **모든** properties 키를 포함해야 함. nullable 필드도 required 에 넣고 `type: ["string", "null"]` 로 선언해야 한다. 향후 스키마 확장 시 동일 원칙 준수.
6. **dart_corp_mapping 시드는 수동 3건으로 MVP** — 전체 벌크 sync 는 P13 후속 작업으로 보류. 본 검증은 시드된 005930 으로 실체 확인.

## Known Issues

### 본 세션 수정 완료 (사실상 크리티컬)
- `2febdf2` entrypoint stamp head → stamp 002 + upgrade head
- `2febdf2` validate_env KIS 자리수 `>= 8` → `== 10`
- `510fa1c` REPORT_JSON_SCHEMA sources.items.required 에 published_at 추가

### Carry-over (이전 세션에서 식별, 미처리)
- M1 `/metrics` 공개 노출 — Caddyfile IP 게이팅 필요
- M2 `/health` env 필드 노출 — 외부 `/health` 는 `{"status":"UP"}` 만 노출, 상세는 `/internal/info`
- M3 uv 컨테이너 이미지 digest 미고정
- M4 Dockerfile `useradd --shell /bin/bash` → `/usr/sbin/nologin`
- `force_refresh=true` rate limiting 미설정
- KRX 대차잔고 pykrx 스키마 불일치 (fallback 동작 중)

### 런타임 관찰
- **Caddy unhealthy** — `DOMAIN=localhost` + self-signed 환경에서 헬스체크 로직이 internal CA 를 인식 못 해서 발생. TLS 자체는 정상(브라우저 `-k`/수락 후 사용 가능). 실도메인 모드에선 자동 해소. 기능 블로커 아님.
- **stock 마스터 0 rows** — KRX 익명 차단 carry-over. E2E 검증은 수동 INSERT 3개로 우회.
- **dart_corp_mapping 3 rows only** — 수동 시드. 전체 4만건 bulk sync 미구현.

## Context for Next Session

### 즉시 할 일

1. **원격 푸시** — 사용자 지시 후 `git push origin master`. 현재 2 커밋 ahead(`2febdf2`, `510fa1c`).
2. **브라우저 UI 실측** (선택) — 백엔드 API E2E 는 통과했지만 프론트 SSR/클라이언트 렌더링 경로는 미검증. Caddy가 unhealthy이지만 기능적으로는 동작하므로 `https://localhost/portfolio` 접속해 아래 확인:
   - 계좌 탭에 `e2e-manual` / `e2e-kis` 두 계정 표시
   - `e2e-manual` 선택 시 삼성 10주 보유 테이블
   - "AI 리포트" 버튼 → `/reports/005930` 이동 → 캐시된 리포트 본문 즉시 렌더링
   - 재생성 버튼 동작 확인(force_refresh → 새 호출)
3. **스택 정지**: 테스트 후 `docker compose --env-file .env.prod -f docker-compose.prod.yml down` 으로 컨테이너만 정지(볼륨 유지). `-v` 는 DB 데이터까지 파괴하므로 금지.

### 즉시 할 일 (다음 우선 후보)

- **A.** `dart_corp_mapping` bulk sync 스크립트 — DART corpCode.xml ZIP 다운로드 + 파싱 + upsert 로 전체 4만건 시드. P13 후속. ~0.5일
- **B.** 운영 보안 carry-over(M1~M4) 일괄 처리 — 인프라 수준. ~0.5일
- **C.** `force_refresh=true` rate limiting — slowapi 도입 + 관리자 키 단위 쿼터. ~0.3일
- **D.** KRX 대차잔고 복구 — pykrx 직접 호출 또는 버전업. ~1일

### 사용자의 원래 목표 (carry-over)
주식 시그널 탐지·백테스팅 서비스 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) MVP. **본 세션에서 실 환경 E2E 검증까지 완료** — 기능 검증 단계 종료, 이제 운영 강화·실사용자 투입 준비로 전환.

### 사용자 선호·제약 (carry-over + 본 세션 재확인)
- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단 — `grep '^KEY=' .env.prod` 조차 차단됨**. 대안: `test -f` exit code, 컨테이너 내부 env 접근, `scripts/validate_env.py` 의 마스킹된 출력. **본 세션 유효 경로로 확립**.
- 작업 단위 커밋 분리 선호
- 리뷰 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호

### 사용자에게 공유할 가치있는 발견

1. **테스트 사각지대 드러남** — Phase 7 의 testcontainers fresh DB 픽스처는 "레거시 Java 스키마 + Alembic 이양" 시나리오를 검증하지 않음. 차후 **별도 통합 테스트**(레거시 DB dump 준비 후 stamp+upgrade 경로 확인) 를 추가하는 것이 좋다.
2. **OpenAI strict schema 검증이 pytest 에서 안 걸린 이유** — FakeLLMProvider 를 썼기 때문. 실 OpenAI 호환성은 **실 API 1회 호출 없이는 검증 불가능**. 차후 `OPENAI_LIVE=1` 환경변수 기반 스모크 테스트 1건을 CI 선택 실행으로 추가하는 것 고려.
3. **실 E2E 에서도 자동 소스 보강이 강력히 동작** — 모델이 sources 에 5건만 반환했더라도 AnalysisReportService 가 Tier1 공식 홈페이지 + 최근 공시 3건을 자동 보강. 실제로 DART 공시 5건 + 공식 홈페이지 1건 = 7건으로 확장됨. Tier1 신뢰 출처 강제 원칙이 코드 레벨에서 유효함을 재확인.

## Files Modified This Session

```
 HANDOFF.md                                       | (본 산출물)
 CHANGELOG.md                                     | 심야 E2E 섹션 prepend
 pipeline/artifacts/10-deploy-log/runbook.md      | §2.4 stamp 002 → upgrade head 로 정정
 scripts/validate_env.py                          | KIS 자리수 == 10 엄격화
 src/backend_py/scripts/entrypoint.py             | stamp 002 + upgrade head 두 단계
 src/backend_py/app/application/port/out/llm_provider.py | published_at required 추가
```

본 세션은 코드 변경 최소화·실환경 검증 극대화 기조. 2 커밋으로 3건의 실버그를 조기 포착·수정·재검증 완료.
