# Session Handoff

> Last updated: 2026-04-19 (KST, 새벽 — P13-1/P13-2 실측 검증 직후)
> Branch: `master` (origin 과 동기화 — 푸시 완료)
> Latest commit: `1c27c65` — P13-2: 운영 보안 carry-over M1~M4 일괄 처리

## Current Status

**P13-1 (DART 벌크 sync 스크립트) 와 P13-2 (운영 보안 M1~M4) 가 실 환경에서 실측 통과.** 이전 세션까지 carry-over 상태였던 4건의 운영 보안 개선과, 수동 시드 3건으로 한정됐던 `dart_corp_mapping` 의 bulk sync 경로를 같은 세션에 구현·검증·배포 완료. 실 DART API 호출까지 성공(전체 116,503 법인 → 필터 통과 3,654건). Caddy 외부 차단·내부 `/internal/info` 응답·appuser nologin 적용 모두 실측 확인.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | P13-1 DART corpCode 벌크 sync 스크립트 | `43f07fd` | `app/adapter/out/external/dart_client.py`, `scripts/__init__.py`, `scripts/sync_dart_corp_mapping.py`, `tests/test_sync_dart_corp_mapping.py` |
| 2 | P13-2 운영 보안 M1~M4 일괄 | `1c27c65` | `ops/caddy/Caddyfile`, `src/backend_py/Dockerfile`, `app/main.py`, `tests/test_health.py` |
| 3 | 세션 운영 문서 현행화 (이전 세션 마감) | `3dfaf7b` | `HANDOFF.md`, `CHANGELOG.md`, `runbook.md` |

**누적 규모(본 세션)**: 3 커밋 / 11 파일 / +613 / -114 라인.
**테스트**: 백엔드 **130/130 PASS** (기존 98 + /internal/info 1 + sync script 31). mypy strict 0, ruff 0 (신규 파일).

### 실측 검증 결과

| # | 단계 | 결과 |
|---|------|------|
| E | DART 벌크 sync `--dry-run` | PASS — ZIP 3,529,057 bytes · 전체 116,503 · stock_code 보유 3,959 · 필터 통과 **3,654건**. 샘플 10건 출력 정상(과거 폐지 종목 혼재 관찰) |
| F-1 | 외부 `/metrics` | PASS — HTTP 404 (Caddy `@blocked` matcher) |
| F-2 | 외부 `/internal/info` | PASS — HTTP 404 (Caddy `@blocked` matcher) |
| F-3 | 내부 `/health` | PASS — `{"status":"UP"}` 만 반환, app/env 미노출 |
| F-3 | 내부 `/internal/info` | PASS — `{"status":"UP","app":"ted-signal-backend","env":"prod"}` 상세 응답 |
| F-4 | appuser 로그인 셸 | PASS (범위 이해) — `/etc/passwd` 에 `/usr/sbin/nologin` 확인. `docker exec /bin/bash` 는 여전히 실행되지만 이는 설계 범위 밖(nologin 은 login/su/sshd 경로 차단 전용) |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **DART 벌크 sync 본실행 (DB upsert)** | pending | `--dry-run` 통과 확인. 실 upsert 는 사용자 지시 후 `docker compose exec backend python -m scripts.sync_dart_corp_mapping` |
| 2 | **brow UI 실측** | carry-over | P13a 프론트 렌더링 경로 미검증 (이전 세션 carry-over) |
| 3 | **force_refresh=true rate limiting** | 보류 (옵션 C) | slowapi/fastapi-limiter. 관리자 키 단위 쿼터 |
| 4 | **KRX 대차잔고 pykrx 스키마 복구** | 보류 (옵션 D) | 어댑터 fallback 중 |
| 5 | **`BrokerAdapter` Protocol 추출** | 보류 | 키움 합류 시점 전까지 미필요 |
| 6 | **Caddy unhealthy** | 관찰 | localhost self-signed 환경 한정. 실도메인 모드에선 자동 해소 |
| 7 | **KRX 익명 차단 (stock 마스터 0 rows)** | carry-over | P10~P13 검증은 수동 INSERT 로 우회 |

## Key Decisions Made

1. **필터 기준 확정** — 보통주(종목코드 6자리 + 끝자리 `0`) + 이름 기반 제외 8패턴(스팩·기업인수목적·리츠·부동산투자회사·인프라투융자회사·ETF·ETN·상장지수). ETF/ETN 은 법인 미등록이라 자연 제외되지만 방어 필터 유지. 리츠는 사용자 요청으로 명시 제외.
2. **XML 파싱은 stdlib ET 유지** — DART 는 Tier1 신뢰 출처. 범용 외부 XML 로 확장 시 `defusedxml` 도입. 현재는 코드 주석으로 신뢰 가정 명시.
3. **uv digest 는 multi-arch index digest 고정** — amd64/arm64 개별 digest 가 아닌 index digest(`sha256:240fb85a…516a`). 두 아키텍처 동시 고정. 업그레이드 절차(`docker buildx imagetools inspect`) 주석화.
4. **M2 `/health` 마스킹은 외부보다 내부 최소화가 본질** — Caddy 가 frontend 로만 프록시하므로 외부에서 `/health` 는 원래 미노출(→ Next.js 404). 그러나 Docker HEALTHCHECK 및 운영자 진단 경로에서의 정보 최소화 원칙은 유효하므로 마스킹 유지.
5. **M4 nologin 은 defense-in-depth 로 명시** — `docker exec /bin/bash` 는 여전히 실행됨. nologin 은 SSH/su/login 경로 차단 전용. 실질 방어는 `/bin/bash` 바이너리 제거까지 가야 하지만, 디버깅 편의성 트레이드오프로 MVP 단계에선 현 수준 유지.
6. **Caddyfile 수정 시 컨테이너 재시작 필요** — Docker Desktop bind mount 가 rename-on-save 로 바뀐 inode 를 따라오지 못함. `caddy reload` 전에 `docker compose restart caddy` 필수. 절차 문서화 필요.

## Known Issues

### 본 세션 수정·검증 완료
- `43f07fd` DART 벌크 sync 스크립트 + 어댑터 확장 + 테스트 31건
- `1c27c65` M1 `/metrics` 외부 차단 · M2 `/health` 마스킹 + `/internal/info` 분리 · M3 uv digest 고정 · M4 appuser nologin

### 본 세션 관찰(차후 개선)
- **상장폐지 종목 혼재** — `dart_corp_mapping` 필터 통과 3,654건 중 상당수가 과거 폐지 종목. AI 리포트 대상이 현재 상장 종목에 한정되므로 실사용 영향은 없으나, KRX 현재 상장 리스트와 교차 필터하면 더 깔끔해짐. 우선순위 낮음.
- **Docker Desktop bind mount 휘발성** — Caddyfile 수정 시 inode 변경으로 mount stale. 운영 절차에 반영 필요.

### Carry-over (이전 세션에서 식별, 본 세션에서 미처리)
- `force_refresh=true` rate limiting (slowapi/fastapi-limiter)
- KRX 대차잔고 pykrx 스키마 불일치 (fallback 동작 중)
- KRX 익명 차단 (stock 마스터 0 rows, MVP 는 수동 INSERT 로 우회)
- Caddy unhealthy (localhost self-signed 한정, 실도메인 모드에선 자동 해소)

## Context for Next Session

### 즉시 할 일

1. **DART 벌크 sync 본실행** — `docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend python -m scripts.sync_dart_corp_mapping` 로 `dart_corp_mapping` 에 3,654건 upsert. 완료 후 `psql \dt` 로 count 확인.
2. **세션 종료 판단** — 스택 유지/정지. `down -v` 는 DB 파괴하므로 금지.

### 다음 우선 후보

- **A.** 실 DB 벌크 upsert 실행 (스크립트 완성 후 최종 단계) — ~5분
- **B.** `force_refresh=true` rate limiting (slowapi) — ~0.3일
- **C.** KRX 대차잔고 복구 — ~1일
- **D.** 브라우저 UI 실측 (P13a 프론트 렌더링 경로) — ~0.3일
- **E.** KRX 현재 상장 리스트 교차 필터(폐지 종목 제외) — ~0.2일

### 사용자의 원래 목표 (carry-over)
주식 시그널 탐지·백테스팅 서비스 Java→Python 이전 완결 + §11 (포트폴리오 + AI 리포트) MVP. 전 세션에서 실 E2E 검증 완료 → 본 세션에서 **수동 시드 한계 해소 + 운영 보안 강화** 로 운영 준비도 한 단계 상승.

### 사용자 선호·제약 (carry-over + 본 세션 재확인)
- **커밋 메시지 한글 필수**
- **푸시는 명시 지시 후에만**
- **시크릿 값 노출 명령 차단** — `grep '^KEY=' .env.prod` 차단. 대안은 컨테이너 내부 env 접근 또는 `scripts/validate_env.py` 마스킹 출력
- **작업 단위 커밋 분리 선호**
- **리뷰 시 HIGH + 보안 MEDIUM + Python/Frontend MEDIUM 일괄 수정 선호**
- **실측 마무리 선호** — 코드/테스트 PASS 만으로 종결하지 않고 실 환경 검증까지 (본 세션 명시 확인)

### 사용자에게 공유할 가치있는 발견

1. **DART corpCode 규모는 "상장사 ~2,500건" 이 아님** — 전체 116,503 법인 중 stock_code 를 가진 것만 3,959건, 필터 후 3,654건. 과거 상장폐지 종목이 대거 포함되기 때문. 실사용(현재 상장 종목만 조회) 관점에선 영향 없지만 수치 기대값은 정정.
2. **Caddy bind mount 의 stale 패턴** — Docker Desktop 환경에서 Caddyfile 을 수정한 직후 `caddy reload` 하면 이전 버전 config 로 파싱되어 syntax error 가 날 수 있음. **증상은 "unexpected token" 에 가까운 파서 에러** 이고 실제로는 파일이 잘려서 보이는 것. `docker compose restart caddy` 한 번이면 해소.
3. **M4 nologin 은 명확한 범위 제한이 있음** — 컨테이너 내부에서 `docker exec` 로 `/bin/bash` 바이너리 직접 호출은 여전히 실행됨. 이는 nologin 의 설계 의도 밖(SSH/su/login 경로 차단 전용). 실제 셸 탈출을 막으려면 `/bin/bash` 바이너리 제거 또는 read-only rootfs 등 추가 layer 필요.

## Files Modified This Session

```
 CHANGELOG.md                                          | (본 산출물)
 HANDOFF.md                                            | (본 산출물)
 ops/caddy/Caddyfile                                   | +14 / -3
 src/backend_py/Dockerfile                             | +9  / -2
 src/backend_py/app/main.py                            | +7  / -1
 src/backend_py/app/adapter/out/external/dart_client.py| +47 / -1
 src/backend_py/scripts/__init__.py                    | +1  (신규)
 src/backend_py/scripts/sync_dart_corp_mapping.py      | +185 (신규)
 src/backend_py/tests/test_health.py                   | +14 / -1
 src/backend_py/tests/test_sync_dart_corp_mapping.py   | +207 (신규)
```

본 세션은 **코드 + 실측 병행** 기조. 3 커밋으로 수동 시드 한계 해소와 운영 보안 4건을 동시 처리하고, 모든 변경을 실 환경에서 실측 검증으로 마감.
