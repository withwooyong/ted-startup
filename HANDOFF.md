# Session Handoff

> Last updated: 2026-04-18 (KST, 밤 — E2E 검증 진입 직후)
> Branch: `master` (origin 과 동일, 0 ahead / 0 behind)
> Latest commit: `243826e` — 세션 운영 문서 현행화: CHANGELOG · HANDOFF
> **작업 트리 clean. 신규 커밋 없음.** 본 핸드오프는 **진행 중 E2E 검증 일시 정지 상태** 를 기록.

## Current Status

Phase 1~9 + §11 P10~P15 전체 완결 상태(이전 핸드오프 참조). **실 API 키 E2E 검증 단계 진입** 후 외부 상태 파악 결과 2가지 블로커가 나와 사용자 결정 대기 중. 신규 코드 변경은 없고 **진행 상태만 본 문서로 인계**.

## In-Flight: 실 E2E 검증 (A 경로)

### 이번 턴 완료

| # | 단계 | 결과 |
|---|------|------|
| E2E-1 | 사전 상태 점검 | `.env.prod` 존재·읽기 가능 ✅. 기존 Docker 스택이 **구 Java 이미지로 기동 중** (backend command `exec java ...`, 포트 8080 노출, Phase 7/8 이전 빌드) — 재빌드 필요 |
| E2E-2 | `scripts/validate_env.py` | **3종 모두 PASS**: DART `status=000`, OpenAI `HTTP 200 (sk-proj-)`, KIS 모의 OAuth `access_token 발급`. 추가로 "KIS 계좌번호 형식: 숫자 8자리 (OK)" — 하지만 스크립트의 PASS 기준(`>=8`)과 어댑터 요구(`>=10`)가 불일치 → §블로커 #1 참조 |

### 블로커 (사용자 결정 대기)

#### #1. KIS 계좌번호 자리수 불일치
- `scripts/validate_env.py` 의 기준: `acct_digits >= 8` → 현재 8자리 PASS 로 찍음
- `app/adapter/out/external/kis_client.py::_account_parts()` 의 기준:
  ```python
  digits = account_no.replace("-", "").strip()
  if len(digits) < 10:
      raise KisNotConfiguredError(f"KIS 계좌번호는 숫자 10자리여야 함 (현재 {len(digits)}자리)")
  ```
- **질의**: `.env.prod` 의 `KIS_ACCOUNT_NO_MOCK` 값이 **하이픈 제거 후 몇자리인가**? (값 자체는 공유 불필요)
- **후속 수정 방향**:
  - 8자리라면 → KIS 모의 HTS "계좌정보" 에서 정식 10자리(`CANO(8) + ACNT_PRDT_CD(2)`) 재확인 후 `.env.prod` 갱신
  - 동시에 `validate_env.py` 의 `acct_ok` 기준도 `>=10` 으로 정정 권고 (검증 스크립트가 어댑터보다 관대해서 문제를 늦게 잡음 — **참 양성/거짓 음성** 문제)

#### #2. E2E 기동 방식 선택
- **(A) 풀 재빌드** — `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`. pandas/vectorbt/numpy 포함 5~10분. entrypoint.py 가 기존 DB 볼륨에 `alembic stamp head` → `upgrade head` 로 003/004/005 자동 적용. **가장 정확한 실환경 검증**
- **(B) 로컬 uv 기동** — 기존 DB 컨테이너 재활용. backend 만 호스트에서 `uv run uvicorn` 구동. 빠르지만 Caddy·프론트 릴레이 경로 미검증
- **(C) pytest 수준 어댑터 실호출 시뮬레이션** — MockTransport 대신 실 httpx. 인프라 스택 미기동

### 추가 발견 (E2E-1 사이드)
- `docker compose ps` 출력에서 `POSTGRES_DB/USER/PASSWORD` env 빈 값 경고 — **`--env-file .env.prod` 플래그 누락** 때문. runbook §2.3 에 이미 명시돼 있으나 실수로 빠지기 쉬운 지점
- `ted-signal-caddy` **unhealthy** 상태 — TLS 발급 이슈 가능성(로컬 `DOMAIN=localhost` + self-signed). 기능 영향은 제한적이나 §2.5 스모크 테스트 시 `-k` 필수
- 기존 `ted-signal-backend` (Java) 가 11시간 전 빌드로 살아 있음 — **KRX 익명 차단으로 데이터 0 rows** 상태라 기능적으로 무력화. 재빌드 시 Python 이미지로 교체되므로 문제 없음

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **E2E-3 스택 기동** | 🔴 블로커 #2 결정 대기 | A/B/C 중 선택 |
| 2 | **E2E-4 포트폴리오 API 체인** | 대기 | 관리자 키로 POST /api/portfolio/accounts → 수동 보유 등록 → holdings 조회 |
| 3 | **E2E-5 KIS 모의 /sync** | 블로커 #1 결정 필요 | 계좌번호 10자리 확정 후만 시도 가능 |
| 4 | **E2E-6 AI 리포트 실생성** | 선행 작업 있음 | `dart_corp_mapping` 테이블 수동 시드 필요 (최소 005930=00126380). bulk sync 미구현 |
| 5 | **E2E-7 결과 정리** | 대기 | 이슈 발견 시 보정 커밋 |
| 6 | `force_refresh=true` rate limiting | 보류 | P14 리뷰 LOW 이슈 |
| 7 | KRX 대차잔고 pykrx 스키마 불일치 복구 | carry-over | 어댑터 fallback 중 |
| 8 | `BrokerAdapter` Protocol 추출 | 보류 | 키움 합류 전제 시 |
| 9 | M1 `/metrics` 게이팅 · M2 `/health` env 분리 · M3 uv digest · M4 useradd shell | carry-over | 보안·운영 잔여 |

## Key Decisions This Turn

1. **E2E 진입 시 민감 명령 차단 원칙 재확인** — `cat .env.prod`, `ls -la .env.prod`, `awk` 로 키 나열 등 값에 접근 가능한 명령은 모두 **차단됨**. 대체 경로로 `test -f`/`test -r` (exit code 만) + `scripts/validate_env.py` (값 마스킹 내장) 사용. 다음 세션에서도 동일 원칙 유지.
2. **validate_env.py 의 느슨한 기준이 실제 어댑터 요구와 불일치** 하는 버그 발견 — 8자리 PASS 를 내지만 KIS 어댑터는 10자리를 요구. E2E 시도 전에 스크립트·어댑터 기준 통일 필요.
3. **기존 Docker 스택은 Phase 7/8 이전 빌드 상태** — 재빌드 없이 E2E 의미 없음. `--env-file .env.prod` 플래그 누락 경고까지 감안하면 옵션 A 풀 재빌드가 가장 깨끗.

## Context for Next Session

### 즉시 할 일 (블로커 해소 순서)

1. **사용자에게 KIS 계좌번호 자리수 확인받기** (블로커 #1)
   - 8자리면 모의 HTS 에서 10자리 재발급 → `.env.prod` 갱신
   - `scripts/validate_env.py` 의 `acct_ok` 기준도 `>=10` 으로 정정 (작은 follow-up 커밋)

2. **기동 방식 선택받기** (블로커 #2) — A 권장

3. **E2E-3 기동**:
   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
   # 기동 확인
   docker compose -f docker-compose.prod.yml ps
   # alembic 리비전 확인
   docker compose -f docker-compose.prod.yml exec backend alembic current
   # /health 내부
   docker compose -f docker-compose.prod.yml exec backend \
     python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
   ```

4. **E2E-4 포트폴리오 체인** (Admin Key 는 현재 셸로 export — runbook §2.5 test #0):
   ```bash
   export ADMIN_API_KEY=$(grep '^ADMIN_API_KEY=' .env.prod | cut -d= -f2-)
   # 수동 계좌 생성
   curl -fsSk -X POST https://localhost/api/admin/portfolio/accounts \
     -H "Content-Type: application/json" \
     -H "X-API-Key: $ADMIN_API_KEY" \
     -d '{"account_alias":"e2e-manual","broker_code":"manual","connection_type":"manual","environment":"mock"}'
   ```

5. **E2E-5 KIS 동기화** — 계좌 alias=e2e-kis, connection_type=kis_rest_mock 으로 별도 생성 후 `/sync`.

6. **E2E-6 AI 리포트 실생성** — 선행 작업: `dart_corp_mapping` 시드. 예시:
   ```sql
   INSERT INTO dart_corp_mapping (stock_code, corp_code, corp_name) VALUES
     ('005930', '00126380', '삼성전자'),
     ('000660', '00164779', 'SK하이닉스')
   ON CONFLICT (stock_code) DO UPDATE SET corp_code=EXCLUDED.corp_code, corp_name=EXCLUDED.corp_name;
   ```
   그 후 `POST /api/admin/reports/005930` 호출. OpenAI 비용 소모 주의 — 1건만.

7. **브라우저 E2E**: `https://localhost/portfolio` 접속 → 계정 탭 → 보유 등록 → `/reports/005930` 링크.

### 사용자의 원래 목표 (carry-over)
주식 시그널 탐지·백테스팅 서비스의 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) 풀 MVP. 본 E2E 가 실 환경에서 동작하는지 마지막 검증.

### 사용자 선호·제약 (carry-over)
- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단** — 심지어 `awk` 로 키 나열도 거부됨. `test -f`/`test -r` exit code 또는 값 마스킹 스크립트 경유가 유일 경로
- 작업 단위 커밋 분리 선호

### 다음 세션 선택지

- **A.** 블로커 2건 해소 후 E2E 풀 검증 (A 경로 풀 재빌드)
- **B.** `validate_env.py` 의 acct_ok 기준 `>=10` 정정 + 작은 follow-up 커밋만 먼저 (블로커 #1 영구 해소)
- **C.** `dart_corp_mapping` bulk sync 스크립트 + `BrokerAdapter` Protocol 추출 등 carry-over 처리로 우회
- **D.** M1/M2/M3/M4 보안 carry-over 정리

A 는 사용자 응답 대기, B 는 즉시 가능한 정리. A 가 먼저 풀려야 진짜 E2E 결론 나옴.

## Files Modified This Turn

```
(none — working tree clean, no new commits since 243826e)
```

본 턴 변경은 실행(`docker compose ps`, `validate_env.py`)과 파일 존재 확인뿐이며 코드·문서 수정 없음.
