# Session Handoff

> Last updated: 2026-04-22 (KST, 세션 마감 — **5 PR 무회귀 연속 머지 + CI 게이트 완비**)
> Branch: `master` (origin 동기화 완료, working tree clean)
> Latest commit: `5c0b305` — chore: CI 에 frontend-lint 게이트 추가 — eslint + tsc --noEmit (#26)

## Current Status

하루 세션에 **5개 PR 무회귀 연속 머지**. PR 5 이월 HIGH 2·MEDIUM 1 + /review 세션 감사 HIGH 2 + frontend CI 게이트 신설. 백엔드 **303 passed** (+8), CI 체크 **6/6** (backend-lint → **frontend-lint 신규** 포함). 모바일 반응형 refactor 진입 직전 상태.

## Completed This Session (2026-04-22, 5 PR 머지)

| PR | 제목 | 커밋 | 성격 |
|----|------|------|------|
| #22 | chore: CI 에 ruff + mypy strict 게이트 추가 + 전체 ruff format 적용 | `3f0061e` | 인프라 (98 파일 format + `backend-lint` 신설) |
| #23 | refactor: Hexagonal 경계 정돈 + SyncPortfolioFromKis mock/real UseCase 분리 | `576e9f2` | 아키텍처 (PR 5 이월 HIGH 2) |
| #24 | refactor: KisAuthError 4xx/5xx 분리 — credential 거부 vs 업스트림 장애 | `77903d9` | 도메인 (PR 5 이월 MEDIUM) |
| #25 | refactor: KIS Hexagonal DIP 완성 + Router account 단일 로드 + 세션 감사 리포트 | `597d5e8` | 아키텍처 (/review HIGH 2) |
| #26 | **chore: CI 에 frontend-lint 게이트 추가 — eslint + tsc --noEmit** | **`5c0b305`** | 인프라 (`frontend-lint` 신설, 6/6 체크) |

### 세션 시작점과의 비교

- 세션 시작 HEAD: `ddfa461` (KIS sync 시리즈 완결 핸드오프)
- 세션 마감 HEAD: `5c0b305`
- 누적 diff: `.github/ci.yml` +87 / `CHANGELOG.md` +260 / `HANDOFF.md` +376 / `docs/*` 현행화 + 신규 리포트 2종 + `src/backend_py/*` 다수 / `src/frontend/package.json` type-check script
- 백엔드 테스트: **295 → 303** (+8)
- CI 체크: backend(lint/test/docker/e2e) 4→5 → 프론트 포함 **6/6**

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 모바일 반응형 Phase A | 착수 대기 | `docs/mobile-responsive-plan.md` 5단계 (A→E) 구조 완비, CI 안전망(frontend-lint) 준비됨 |

미커밋 변경: **없음**. 브랜치: master clean.

## Key Decisions Made

### 세션 전략

1. **CI 게이트 우선**: 백엔드(`backend-lint` PR #22) → 프론트(`frontend-lint` PR #26) 순으로 대칭 게이트 구축. 이후 refactor(#23·#24·#25) 는 backend-lint 안전망 위에서 안전하게 쌓임. 모바일 refactor 진입 전에도 동일 패턴으로 frontend-lint 선행.
2. **PR 단위 원자성**: 한 세션에 5 PR, 각 PR 은 단일 관심사(게이트·DTO 이동·예외 분리·DIP 완성·frontend 게이트). 리뷰 병렬 실행 + HIGH 즉시 반영 + CI 5~6/6 확인 후 squash merge.
3. **/review 세션 감사**: 3 PR(#22·#23·#24) 머지 후 통합 감사 실시. 산출 리포트 2종(`review-2026-04-22-session.md`, `audit-2026-04-22-session.md`) 커밋. 발견된 HIGH 2건을 PR #25 로 즉시 해소.

### 아키텍처 결정

1. **Hexagonal DIP 완성 (KIS 영역)**:
   - `app/application/dto/kis.py` — `KisCredentials`/`KisHoldingRow`/`KisEnvironment` 이동
   - `app/application/port/out/kis_port.py` — `KisHoldingsFetcher` Protocol(structural) + `KisUpstreamError`/`KisCredentialRejectedError` port 예외 + `KisRealFetcherFactory` 타입 별칭
   - `portfolio_service.py` 에서 `from app.adapter.out.external import ...` **완전 제거**
   - Adapter `__init__.py` 는 re-export 로 backward-compat 유지 (테스트·배선 편의)
2. **KisNotConfiguredError 독립**: 서버 설정 오류(500) 를 업스트림 장애(`KisUpstreamError` 502) 계층에서 분리해 오진단 차단.
3. **Protocol structural typing**: `KisClient` 가 명시 상속 없이 `KisHoldingsFetcher` 를 자동 만족. mypy strict 가 factory 반환 경로에서 검증.
4. **Optional account 파라미터**: UseCase `execute(*, account_id, account=None)` 으로 Router 선로드 결과 명시 전달 — identity map 캐시 히트 의존 제거.
5. **예외 4xx/5xx 분리**: credential 거부(`CredentialRejectedError` → HTTP 400) vs 업스트림 장애(`SyncError` → HTTP 502) 타입 레벨 구분.

### CI 설계

1. **lint job 을 test/build 앞에**: `needs: [X-lint]` 로 풀 빌드 스킵해 1~2분 내 빠른 실패. backend-test(~50s) / frontend-build(~30s) 자원 절감.
2. **eslint + tsc 별도 스텝**: CI 로그에서 lint vs type 에러 즉시 구분. `next build` 가 타입 체크 포함하지만 `// @ts-ignore` 우회 가능 → 독립 `tsc --noEmit` 이 더 엄격.
3. **기존 코드 clean 전제**: backend PR #22 는 98 파일 format fix 동반 / frontend PR #26 은 순수 게이트 추가 (로컬 `npm run lint` + `tsc --noEmit` 이미 clean).

## Known Issues

### 남은 부채 (발견됨, 미해소)

- **R-03 이름 중복 완화**: port `KisCredentialRejectedError` vs domain `CredentialRejectedError`. `Kis` prefix 로 구분되지만 가독성 부담. ruff N818(Error suffix) 때문에 suffix 유지 필요 → 리네이밍은 별도 PR 후보 (30분).
- **다른 서비스 DIP 확장 미완**: Telegram/Krx/Dart 는 여전히 `from app.adapter.out.external import ...` 사용. 본 세션 PR #25 는 KIS leading example, 추후 PR 로 확장 (1~2h).
- **DB 모델 `Mapped[str]` → `Literal`**: Router `else` dead-path exhaustive check 불가. `connection_type` 등 CHECK CONSTRAINT 와 매칭되는 Literal 좁히기 (1h).
- **R-04 MOCK 401 경로 재분류**: MOCK 환경 401 이 `CredentialRejectedError` → 400 으로 사용자 응답되지만 실제로는 운영자 오류. 500/502 재분류 검토 필요.
- **R-05 `/sync` endpoint 400 응답 직접 테스트 부재**: `test-connection` 만 400 커버. `/sync` 에 대응 테스트 추가.
- **R-06 `.git-blame-ignore-revs` 미생성**: PR #22 format 커밋(`3f0061e`) 이 blame 단일화. `.git-blame-ignore-revs` 파일로 투명화 (1파일 추가).

### 일반 부채 (세션 이전 잔존)

- CI 가 ruff/mypy 는 신설됐으나 **다른 서비스 DIP 미확장** (본 세션 범위 아님)
- pre-existing `signals.py` mypy 2건은 PR #22 에서 해소됨
- Python M2 중복 판단 N+1(엑셀 import, PR #12 리뷰 이월)
- MEDIUM `setattr` mypy 우회(`BacktestResult.hit_rate_{n}d`)
- 실 KIS 엑셀 샘플 부재
- 로컬 백엔드 이미지 재빌드 루틴 미편입
- carry-over 모니터링: lending_balance T+1 지연, 218 stock_name 빈, TREND_REVERSAL Infinity (월요일 07:00 KST 스케줄 관찰)

## Context for Next Session

### 사용자의 원래 목표

**모바일 반응형 개선 착수** (`docs/mobile-responsive-plan.md`, 3.5~4 man-day). 본 세션의 PR 5건은 **모바일 작업 착수 전 안전망·부채 청소** 목적:

1. 백엔드 정돈 (HIGH 부채 5건 해소) — PR #22·#23·#24·#25
2. 프론트 CI 게이트 신설 (refactor 안전망) — PR #26

이제 모바일 작업에 진입할 수 있는 깨끗한 상태.

### 차기 세션 진입 순서 (우선순위)

1. **모바일 반응형 Phase A 착수** ⭐ (사용자 목표)
   - `docs/mobile-responsive-plan.md` 재확인 → `/ted-run docs/plan/mobile-responsive-plan.md` 또는 "Phase A 진행"
   - Phase A: viewport meta + Playwright 모바일 프로필 → Gate 1 승인
   - Phase B: Portfolio 테이블→카드 + RealAccountSection 3-버튼 → Gate 2 스크린샷 승인
   - Phase C·D·E: 가독성 + 터치 타깃 + Playwright 모바일 E2E → Gate 3 Lighthouse 검증
2. **다른 서비스 DIP 확장** (1~2h) — 본 세션 PR #25 의 leading example 활용해 Telegram/Krx/Dart 동일 패턴 적용. 모바일과 병렬 가능.
3. **DB 모델 Literal 좁히기** (1h) — `connection_type` 등. Router exhaustive check 가능.
4. **R-04/R-05/R-06** — 각 30분 내 소규모 독립 PR.
5. **Exception 이름 중복 완화 (R-03)** — 30분.
6. **asyncio_mode=auto 마이그레이션** — 소규모.
7. **KIS sync 시리즈 회고 문서** — 선택적, PIPELINE-GUIDE 확장판.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — 5 PR 모두 준수
- **push 는 명시 요청 시에만** — 본 세션 모든 PR 사용자 확인 후 실행
- **설계 승인 루프**: 복잡 과제는 `docs/*-plan.md` 선행. 단일 PR 은 착수 여부 확인만
- **CI 게이트 우선**: backend-lint → frontend-lint 대칭 패턴. lint job 을 build/test 앞에 두어 빠른 실패.
- **리뷰 수용 원칙**: CRITICAL/HIGH 즉시 반영, MEDIUM 은 ROI 판단, 스킵 시 사유 기록. 본 세션 모두 준수.
- **Monitor + squash merge 파이프라인**: `gh pr create` → CI poll → `gh pr merge --squash --delete-branch` 흐름. 5회 반복 검증됨.

### 가치 있는 발견 (본 세션)

1. **세션 누적 /review 감사의 레버리지**: 3 PR 머지 후 통합 리뷰 → HIGH 2 발견 → 1 PR 로 통합 해소. 개별 PR 리뷰가 놓칠 수 있는 부채를 포착.
2. **ruff format + git blame 오염**: 98 파일 일괄 format 이 blame 을 단일 커밋으로 소멸 → `.git-blame-ignore-revs` 필요 (R-06 후보).
3. **Structural typing 활용**: `KisClient` 가 Protocol 명시 상속 없이 자동 만족 — mypy strict 가 할당 경로에서 검증. Protocol 에 `__aenter__`/`__aexit__` 포함이 `typing.AsyncContextManager` 상속보다 explicit 해 가독성 우수.
4. **포트 예외 계층 설계 함정**: `KisNotConfiguredError` 를 `KisUpstreamError` 서브로 두면 UseCase `except KisUpstreamError` 가 설정 오류까지 삼켜 502 오진단. 독립 계층이 안전.
5. **lint 게이트 대칭 패턴**: backend-lint (PR #22) 도입 직후 3 PR 이 안전하게 쌓임 → frontend-lint (PR #26) 도 동일 레버리지 기대. "refactor 착수 전 30분 게이트 PR" 이 공통 레시피로 검증됨.
6. **Optional 파라미터 하위 호환**: UseCase `execute(*, account_id, account=None)` — 기존 호출부 0 변경, Router 만 명시 전달. 대규모 API 변경을 피하면서 R-02 해결.
7. **CHANGELOG `PR #(예정)` 마커**: 커밋 시점엔 PR 번호 미정 → `PR #(예정)` 로 두고 머지 후 다음 PR 에서 해시+번호로 업데이트하는 관행. 본 세션 3회 실행.

## Files Modified This Session

세션 시작 `ddfa461` → 마감 `5c0b305`, **5 PR** 누적:

```
주요 변경 카테고리:

CI/인프라 (+87, .github/workflows/ci.yml):
  - backend-lint job 신설 (ruff check + format + mypy strict)
  - frontend-lint job 신설 (eslint + tsc --noEmit)
  - backend-test / frontend-build 에 needs 의존 설정

신규 파일 (7개):
  - docs/mobile-responsive-plan.md (PR #19 부터, 세션 직전 현행화)
  - pipeline/artifacts/08-review-report/review-2026-04-22-session.md (PR #25)
  - pipeline/artifacts/09-security-audit/audit-2026-04-22-session.md (PR #25)
  - src/backend_py/app/application/dto/credential.py (PR #23)
  - src/backend_py/app/application/dto/kis.py (PR #25)
  - src/backend_py/app/application/port/out/kis_port.py (PR #25)

수정 집중도 높은 파일:
  - src/backend_py/app/application/service/portfolio_service.py (SyncPortfolioFromKis 분리 + DIP)
  - src/backend_py/app/adapter/web/routers/portfolio.py (디스패치 + account 전달)
  - src/backend_py/app/adapter/out/external/kis_client.py (DTO 제거 + port 예외)
  - src/backend_py/app/adapter/out/external/__init__.py (re-export 조정)
  - src/backend_py/app/adapter/web/_deps.py (DTO import 경로 + factory 타입)
  - src/backend_py/tests/test_portfolio.py (UseCase 이름 교체 + 환경 검증 의미 복원)
  - src/backend_py/tests/test_kis_real_sync.py (401/403 vs 5xx 분리 + Literal factory)
  - src/backend_py/tests/test_kis_client.py (예외 이름 + 5xx → base 단언)

Frontend:
  - src/frontend/package.json (type-check script 추가)

문서·설정 (세션 누적):
  CHANGELOG.md (+260), HANDOFF.md (+376), docs/PIPELINE-GUIDE.md (+99)
```

### 백엔드 테스트 증분

- 세션 시작: 295 passed
- 세션 마감: **303 passed** (+8)
  - PR #24 신규: 토큰 401/403 파라메트라이즈(2), 토큰 500 base 단언(1), 잔고 401/403 파라메트라이즈(2), endpoint 400/502 분리(2), UseCase 레벨 credential reject(1) = +8

### CI 체크 증분

- 세션 시작: 4 checks (backend-test / frontend-build / docker-build / e2e)
- 세션 마감: **6 checks** (+ backend-lint / frontend-lint)

## 운영 배포 체크리스트 (누적)

이전 세션 항목 유지 (`.env.prod` KIS_CREDENTIAL_MASTER_KEY, 마스터키 secret manager 백업, `/test-connection` 사전 검증, `LOG_LEVEL` env, `APP_ENV`, 로그 마스킹 점검, KIS 토큰 revoke 한계, 로컬 smoke 테스트).

신규 추가 없음 — 본 세션은 내부 아키텍처 정돈 + CI 게이트 중심.
