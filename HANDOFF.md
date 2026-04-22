# Session Handoff

> Last updated: 2026-04-22 (KST, 당일 세션 — **CI lint 게이트 머지 + Hexagonal/Sync 분리 PR 준비**)
> Branch: `refactor/hexagonal-sync-split` (master 기반, uncommitted 변경 있음)
> Latest master HEAD: `3f0061e` — chore: CI 에 ruff + mypy strict 게이트 추가 (#22)

## Current Status (2026-04-22)

### 머지 완료 — PR #22 (CI lint/type 게이트)

`.github/workflows/ci.yml` 에 `backend-lint` job 신설 (ruff check + ruff format --check + mypy app strict). 전체 98 파일 ruff format 일괄 적용. signals.py union-attr 2건 해소. scripts/ SIM117 2건 autofix. **CI 5/5 PASS** (backend-lint 30s) 확인 후 squash merge, branch 삭제.

### 진행 중 — Hexagonal 리팩터 + SyncUseCase 분리 PR (커밋 대기)

PR 5 (#16) 이월 HIGH 2건 해소:

| 항목 | 내용 |
|---|---|
| DTO 이동 | `MaskedCredentialView` → **`app/application/dto/credential.py`** (신규). Hexagonal 경계 정합 — application layer 가 DTO 소유, infra(repository)가 import 해서 반환 |
| re-export 제거 | `portfolio_service.py` 의 `MaskedCredentialView as MaskedCredentialView` re-export 라인 제거 |
| UseCase 분할 | `SyncPortfolioFromKisUseCase` → **`SyncPortfolioFromKisMockUseCase`** + **`SyncPortfolioFromKisRealUseCase`** 두 클래스. 각자 필요한 DI 만 non-Optional 로 받음 — `RuntimeError` 런타임 검증 퇴화 제거 |
| 공통 헬퍼 | holding upsert 루프를 `_apply_kis_holdings()` 모듈 헬퍼로 추출. `connection_type: Literal["kis_rest_mock", "kis_rest_real"]` 로 좁혀 임의 문자열 오염 방지 |
| Router 디스패치 | `sync_from_kis` 가 `account.connection_type` 으로 분기 — 이중 account 로드는 동일 세션 내 캐시 히트 |
| 테스트 전환 | 3개 mock 케이스는 `SyncPortfolioFromKisMockUseCase`, 2개 real 케이스는 `SyncPortfolioFromKisRealUseCase`. `test_sync_kis_rest_real_requires_real_environment` 는 의미 복원 (이전 테스트는 mock UseCase 로 real 계좌 검증해 `UnsupportedConnectionError` 가 먼저 터져 environment 검증에 도달 못함). factory + `get_decrypted` 둘 다 AssertionError 스텁으로 순서 회귀 감지 |

### 리뷰 결과 (python-reviewer)

**HIGH 2건 반영 완료**:
- `_apply_kis_holdings(connection_type)` 파라미터에 Literal 적용 + UseCase 호출 시 리터럴 전달
- 테스트에 `credential_repo.get_decrypted` monkeypatch AssertionError 추가

**MEDIUM 기록만** (액션 불필요):
- Router 이중 account 로드 — 동일 세션 내 허용 범위
- Router `else` dead-path Literal exhaustive check 미적용 — DB 모델 `Mapped[str]` 변경 필요, 별도 PR

### 로컬 검증 결과
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 124 files already formatted
- `uv run mypy app` ✅ 81 source files (credential.py 신규), no issues
- `uv run pytest -q` ✅ **295 passed, 1 deselected** — 회귀 0건

### 미처리

- 커밋 + 푸시 + PR 생성 (**사용자 명시 요청 대기**)
- CI 5/5 PASS 확인 후 squash merge

### 차기 후보 (HANDOFF 백로그 갱신)

1. ~~#2 CI lint/type 게이트~~ ✅ 완료 (PR #22)
2. ~~#3 Hexagonal + #4 mock/real 분리~~ 🔄 이 PR 로 해소
3. **#1 모바일 반응형 착수** (3.5~4 man-day) — 최대 사용자 가치
4. **#5 KisAuthError 401/5xx 분리** (1h) — observability
5. **DB 모델 Mapped[str] → Literal 좁히기** (신규, 본 PR 리뷰에서 파생) — Router exhaustive check 가능
6. **#6 asyncio_mode=auto 마이그레이션** (소규모)
7. **#7 KIS sync 회고 문서** (선택적)

## Prior Session (2026-04-21, 마감)

**KIS sync 시리즈 6 PR 전원 머지 완료 + 4개 부수 문서/설정 PR 까지 깔끔히 종료**. 한 세션에 **6개 PR** 머지 (#16 → #20, 세션 시작 시점 `3db778f` 기준):

| PR | 제목 | 커밋 | 성격 |
|---|---|---|---|
| #16 | KIS sync PR 5: 연결 테스트 + 실 sync wire | `1461582` | 기능 (실 외부 호출 개시) |
| #17 | chore: `.claude/settings.local.json` gitignore | `2a97e27` | 설정 |
| #18 | docs: PIPELINE-GUIDE 현행화 + README 프로미넌트 링크 | `57dd562` | 문서 |
| #19 | docs: 모바일 반응형 계획서 현행화 | `7b11d88` | 문서 |
| #20 | **KIS sync PR 6: 로깅 마스킹 (시리즈 최종)** | `1483940` | 보안 (시리즈 완결) |

세션 시작 시점 머지 상태는 PR #14 (`3db778f`) 까지 — 본 세션에서 PR 5·6 구현 + 부수 PR 3건 + 1 PR 5 CI 확인 후 squash merge 로 시리즈 완결. 백엔드 테스트 **197 → 295** (+98 누적). CI **6회 연속 4/4 PASS**.

## Completed 2026-04-21 Session (6 PR 머지)

### PR #16 — KIS sync PR 5 (연결 테스트 + 실 sync wire)

| # | 작업 |
|---|------|
| 1 | `KisClient.test_connection()` — OAuth 토큰 dry-run, 재시도 없음 |
| 2 | `TestKisConnectionUseCase` (`__test__ = False`) + `KisRealClientFactory` 타입 별칭 + `_ensure_kis_real_account` 공통 헬퍼 |
| 3 | `SyncPortfolioFromKisUseCase` wire — credential_repo + real_client_factory 주입, `_fetch_balance_real` / `_fetch_balance_mock` 분리 |
| 4 | `KisCredentialsNotWiredError` 제거 (PR 2~4 개발 장벽 해제) |
| 5 | `POST /api/portfolio/accounts/{id}/test-connection` 엔드포인트 |
| 6 | `_credential_error_to_http` 공통 매퍼로 sync + test-connection + credential CRUD 예외 통합 |
| 7 | pytest marker `requires_kis_real_account` + pyproject `addopts` CI skip |
| 8 | FE Settings "연결 테스트" 버튼 + Portfolio 실계좌 sync 활성화 + 404 맥락 메시지 + 502 중립화 |
| 9 | `TestConnectionResponse.ok: true` 리터럴 타입으로 dead code 제거 |
| 10 | 테스트 12건 추가 (227 → 239) |

### PR #17 — `.claude/settings.local.json` gitignore

- 로컬 개인 설정 오버라이드 파일 추가 (includeCoAuthoredBy 등) + `.gitignore` 엔트리

### PR #18 — PIPELINE-GUIDE 현행화 + README 프로미넌트 링크

- README 상단 🚨 필독 call-out 박스 + PIPELINE-GUIDE 눈에 띄는 링크
- PIPELINE-GUIDE §2 스택 Java → Python 갱신, §8 Q3 언어별 reviewer 매핑 + 병렬 리뷰 패턴, §실전학습에 KIS sync 교훈 11건 + 공통 워크플로우 섹션

### PR #19 — 모바일 반응형 계획서 현행화

- Next.js 15 → 16.2.4 반영, PR #12·#15·#16 페이지 재진단
- P1 item 6·7 신규 (RealAccountSection 3-버튼 · sync 라벨 확장), D2 푸터 면책 스킵 판정
- 예상 작업량 3~3.5 → **3.5~4 man-day**, §9 변경 이력 섹션 신설

### PR #20 — KIS sync PR 6 (로깅 마스킹, 시리즈 최종)

| # | 작업 |
|---|------|
| 1 | `app/observability/` 신규 패키지 (선제 import 0) |
| 2 | `SENSITIVE_KEYS` frozenset + `SENSITIVE_KEY_SUFFIXES` tuple + `_is_sensitive_key` 헬퍼 + `_scan` 재귀 + JWT `eyJ` 접두 scrub + hex 40자+ scrub |
| 3 | `mask_sensitive` structlog processor + `setup_logging` `_configured` guard + `reset_logging_for_tests` 헬퍼 |
| 4 | `main.py` create_app() 앞단 setup_logging 호출 |
| 5 | `settings.py` `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` |
| 6 | README "KIS OpenAPI 토큰 revoke 한계" + "로깅 민감 데이터 보호" 섹션 |
| 7 | 설계서 § 5 PR 6 ✅ + § 8 완결 표시 |
| 8 | 테스트 56건 추가 (239 → 295) |

**CI 누적**: 본 세션 5회 (PR #16·#17·#18·#19·#20) 연속 4/4 PASS (PR #18·#19 는 e2e path filter 로 3/3 집계).

## In Progress / Pending

- 없음. 세션 깔끔히 종료, uncommitted 없음.
- `.claude/scheduled_tasks.lock` (untracked, 런타임 세션 잠금) 는 커밋 대상 아님.

## Key Decisions Made (본 세션)

### PR 5 (연결 테스트 + 실 sync)

- **요청 스코프 팩토리 DI**: `Callable[[KisCredentials], KisClient]` 팩토리로 계좌별 credential 다른 real client 를 요청마다 생성. `async with` 로 커넥션 풀 정리.
- **`_ensure_kis_real_account` 헬퍼 공유**: credential UseCase + TestConnection + Sync UseCase 세 곳의 계좌 검증을 1곳으로 집중.
- **`TestConnectionResponse.ok: true` 리터럴** (FE 리뷰 HIGH 반영): `adminCall` 이 !ok throw 하므로 성공 응답은 항상 `ok=true`. 리터럴로 좁혀 dead code 제거.
- **Portfolio sync 404 맥락 메시지** (FE 리뷰 HIGH 반영): `selected.connection_type === 'kis_rest_real'` + status 404 조합으로 credential 미등록 안내.
- **502 메시지 중립화** (FE 리뷰 MEDIUM 반영): "자격증명 거부 or 업스트림 장애" 재등록 오해 유도 방지.

### PR 6 (로깅 마스킹, 시리즈 최종)

- **JWT 패턴 `eyJ` 접두 제약** (리뷰 HIGH #1 반영): JOSE 표준 preserve — structlog `logger` 이름(`app.adapter.web.real_client`) false positive 차단.
- **`_configured` guard 실사용** (리뷰 HIGH #2 반영): dead code → early-return. pytest `caplog` 외부 핸들러 보존. `reset_logging_for_tests()` 명시 함수 노출.
- **`SENSITIVE_KEYS` + `SENSITIVE_KEY_SUFFIXES` 2층** (리뷰 HIGH #3 반영): 완전 일치(프로젝트 특이 필드 explicit) + 접미 일치(신규 env 자동 커버).
- **stdlib `extra` drop 이 안전장치**: structlog `ProcessorFormatter` 가 extra 를 event_dict 로 안 옮김 → 데이터 유출 없음. 테스트에서 명시 검증.
- **`assert` → 방어적 `if isinstance`** (리뷰 MEDIUM #1): `python -O` 안전 + mypy narrowing.
- **`log_level: Literal[...]`** (리뷰 MEDIUM #2): Pydantic enum 좁히기 — 오타 env var 즉시 실패.

### 공통 워크플로우 검증 (본 세션에서 반복됨)

1. 설계 승인 루프 → `/ted-run` → 병렬 리뷰 → HIGH 즉시 반영 → CI 4/4 → squash merge → branch 삭제
2. 문서·설정 chore 도 feature branch + PR 경유 (일관성)
3. `.gitignore` 추가 시 feature branch 경유 — direct-to-master 회피
4. Co-Authored-By 자동 부여: `.claude/settings.local.json` 은 Claude Code 내부 commit flow 전용. Bash `git commit` 은 명시 `--trailer` 또는 HEREDOC 필요 — 본 세션에서 실전 검증.

## Known Issues

### 본 세션 리뷰에서 의도적으로 스킵한 항목 (sequential carry-over)

**PR 5 이월 (구조적, 별도 PR 필요):**
- HIGH Hexagonal 레이어 위반 (`MaskedCredentialView` re-export, `app/application/service` → `app/adapter/out/persistence/repositories` DTO 참조). `app/application/dto/` 도입 후보.
- HIGH `SyncPortfolioFromKisUseCase.__init__` Optional 파라미터 RuntimeError 퇴화. mock/real UseCase 분리 필요.
- MEDIUM `KisAuthError` 4xx vs 5xx 분리 — credential 거부 vs 업스트림 장애. KIS 응답 status 검증 테스트 필요.

**PR 6 이월:**
- LOW hex 40자 임계값 → 56자 상향 논의 — git SHA/content hash 의도적 식별자 보존 필요 시. 현 KIS 도메인 실문제 없음.

**UX 폴리싱 (PR 4·5 이월):**
- FE MEDIUM `actionPending` 다른 계좌 disabled 이유 시각화 (tooltip/aria-description)
- FE MEDIUM Record 맵 라벨 (현재 삼항, 3+ 타입 확장 시)
- FE MEDIUM `title` vs `sr-only` 접근성
- FE LOW `window.prompt` → 인라인 모달 (credential 수정 플로우)

### 일반 부채
- **CI 가 ruff/mypy 안 돌림**: `.github/workflows/*.yml` 에 lint/type 단계 없음. 소규모 PR 후보 — 본 세션 전 진입 장벽 낮춤 (ruff clean, mypy 내 파일 0 err).
- **pre-existing signals.py mypy 2건**: `Stock | None` union-attr.
- **Python M2 중복 판단 N+1** (엑셀 import, PR #12 리뷰 이월): 메모리 집합 최적화, 1 commit 소형.
- **MEDIUM `setattr` mypy 우회** (`BacktestResult.hit_rate_{n}d`): 명시 setter 후보.
- **실 KIS 엑셀 샘플 부재**: PR #12 alias 보정.
- **로컬 백엔드 이미지 재빌드 루틴 미편입**.
- **carry-over 모니터링**: lending_balance T+1 지연, 218 stock_name 빈, TREND_REVERSAL Infinity (월요일 07:00 KST 스케줄 관찰).

## Context for Next Session

### 사용자의 원래 목표 (달성)

**KIS sync 시리즈 6/6 완결**. 엑셀 거래내역 import (낮은 위험부터) → 어댑터 분기 스캐폴딩 → credential 저장소 (Fernet 암호화) → 등록 API + Settings UI → 연결 테스트 + 실 sync wire (외부 호출 개시) → 로깅 마스킹 (민감 데이터 보호). 원자적 PR 6개가 서로 신뢰 빌드업으로 연결.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — 모든 PR 준수
- **push 는 명시 요청 시에만** — 본 세션 내 모든 PR 사용자 확인 후 실행
- **설계 승인 루프**: 복잡 과제는 `docs/*-plan.md` 선행 작성. 단일 PR 은 착수 여부 간단 확인만
- **리뷰 수용 원칙**: CRITICAL/HIGH 즉시 반영, MEDIUM 은 ROI 판단, 스킵 시 사유 기록
- **실측 마감 선호**: ruff + mypy + pytest + Next build 전부 통과 후 머지, CI 4/4 까지 polling
- **병렬 리뷰 활용**: python-reviewer + typescript-reviewer 동시 호출 — ~4분 내 양쪽 완료
- **trivial chore 도 feature branch**: 일관성 유지 (PR #17 gitignore 가 초기 master 직접 커밋 후 되감기하여 feature branch 로 이관된 사례)

### 차기 세션 후보 (우선순위 순)

1. **모바일 반응형 개선 착수** (PR #19 현행화 완료, 3.5~4 man-day)
   - Phase A (viewport meta · Playwright 모바일 프로필) → Gate 1 승인
   - Phase B (Portfolio 테이블→카드 + RealAccountSection 3-버튼) → Gate 2 스크린샷 승인
   - Phase C·D·E (나머지 가독성 · 터치 타깃 · Playwright 모바일 E2E) → Gate 3 Lighthouse 검증
2. **CI 에 ruff + mypy strict 추가** — 3~5분 PR. 본 세션 통과 상태라 진입 장벽 낮음.
3. **Hexagonal 리팩터** (PR 5 이월): `CredentialRepositoryPort` + `MaskedCredentialView` → `app/application/dto/`. 1~2h.
4. **`SyncPortfolioFromKisUseCase` mock/real UseCase 분리** (PR 5 이월): Optional 퇴화 제거 + 타입 안전성. 1~2h.
5. **`KisAuthError` 401 매핑** (PR 5 이월): 1h.
6. **`asyncio_mode=auto` 마이그레이션**: 프로젝트 전반 `@pytest.mark.asyncio` 제거. 소규모 PR.
7. **KIS sync 시리즈 회고 사례 연구 문서** (선택적): 6 PR 신뢰 빌드업 패턴을 `docs/research/` 에 독립 문서. PIPELINE-GUIDE 실전학습 항목이 이미 응축된 상태이므로 확장판 성격.

### 가치있는 발견 (본 세션 누적)

1. **JOSE 표준 활용으로 정확도 상승**: JWT header `eyJ` 접두 제약이 structlog logger 이름 오탐을 완전 차단. 일반성보다 표준 준수가 정확도에 유리한 사례.
2. **`_configured` guard + 외부 핸들러 보존**: setup 함수가 "과거 초기화" 를 하면 pytest caplog 를 silently 제거. Guard 로 "1회만 유효" 를 명시화하면 외부 핸들러 보존 + log_level 런타임 변경 불가 trade-off 가 명시적 계약이 됨.
3. **stdlib `extra` drop 이 안전장치**: structlog `ProcessorFormatter` 기본 동작 = extra 누락. "노출 안 됨" 자체가 마스킹보다 강한 방어. 테스트에서 명시 검증.
4. **예외 매퍼 네이밍 규칙**: `_raise_for_*` = 내부 raise, `_*_to_http` = return (caller raise). 이름과 동작 일치가 type hint 보다 강력.
5. **FE `ok: true` 리터럴 타입 narrowing**: `adminCall` 이 !ok throw 하는 계약이면 클라이언트 성공 응답 `ok` 는 항상 `true`. `boolean` 타입은 dead code 허용 — 리터럴로 좁혀 BE 계약 강제.
6. **`TestKisConnectionUseCase` pytest auto-collection 충돌**: "Test*" 접두 클래스가 pytest `PytestCollectionWarning` 유발. `__test__ = False` 클래스 속성으로 명시 제외.
7. **요청 스코프 팩토리 DI**: 계좌별 credential 이 다르면 프로세스 공유 불가. `Callable[[Creds], Client]` 팩토리 주입 + `async with` 로 요청 스코프.
8. **smoke 마커 + addopts 이중 방어**: `-m "not ..."` 기본 skip, 로컬은 `pytest -m ...` 으로 override. pytest 8.x 마지막 `-m` 승리 규칙에 의존.
9. **Co-Authored-By 는 Claude Code 내부 commit flow 전용**: `.claude/settings.local.json` `includeCoAuthoredBy: true` 는 Bash `git commit` 에 적용 안 됨 — HEREDOC 마지막에 명시 또는 `--trailer` 로 amend.
10. **trivial chore 도 feature branch 유지**: master 직접 커밋 → feature branch 로 되감기하는 패턴이 팀 일관성에 기여 (PR #17 실전 사례).
11. **6 PR 시리즈 성공 요인 회고**: ① `docs/*-plan.md` 선행 설계 ② 원자적 PR 단위로 신뢰 빌드업 (위험 낮은 것부터) ③ 병렬 리뷰 후 HIGH 즉시 반영 + MEDIUM ROI 판단 ④ HANDOFF 매 세션 마감 ⑤ CI 4/4 게이트 ⑥ feature branch + squash merge 일관성. 파이프라인 검증됨.

## Files Modified This Session (세션 누적)

**세션 시작(`3db778f`) → 세션 마감(`1483940`) 전체 diff**: 48 files, +5482 / −168

```
신규 파일 (13개):
  docs/kis-real-account-sync-plan.md                                (PR #13 부터 누적, 본 세션엔 § 5 PR 5·6 완결 표시)
  docs/mobile-responsive-plan.md                                    (PR #19 신규 커밋 — 작성 2026-04-20)
  src/backend_py/app/observability/__init__.py                      (PR #20)
  src/backend_py/app/observability/logging.py                       (PR #20 ~220 lines)
  src/backend_py/app/security/__init__.py                           (PR #14, 본 세션 직전)
  src/backend_py/app/security/credential_cipher.py                  (PR #14, 본 세션 직전)
  src/backend_py/app/adapter/out/persistence/repositories/brokerage_credential.py  (PR #14·#15·#16 누적)
  src/backend_py/migrations/versions/006_portfolio_excel_source.py  (PR #12)
  src/backend_py/migrations/versions/007_kis_real_connection.py     (PR #13)
  src/backend_py/migrations/versions/008_brokerage_credential.py    (PR #14)
  src/backend_py/tests/test_brokerage_credential.py                 (PR #14·#15 누적)
  src/backend_py/tests/test_excel_import.py                         (PR #12)
  src/backend_py/tests/test_kis_real_sync.py                        (PR #16 신규 ~473 lines)
  src/backend_py/tests/test_logging_masking.py                      (PR #20 신규 ~265 lines)
  src/frontend/src/components/features/ExcelImportPanel.tsx         (PR #12)
  src/frontend/src/components/features/RealAccountSection.tsx       (PR #15·#16 누적 ~484 lines)

수정 집중도 높은 파일:
  src/backend_py/app/adapter/web/routers/portfolio.py               (+309 / -? PR #13~#16 누적)
  src/backend_py/app/application/service/portfolio_service.py      (+297 / -? PR #13~#16 누적)
  src/backend_py/app/adapter/out/external/kis_client.py            (+116 / -? PR #13·#16 누적)
  src/frontend/src/lib/api/portfolio.ts                             (+90 / -? PR #15·#16 누적)

문서·설정:
  CHANGELOG.md, HANDOFF.md, README.md, .gitignore, pyproject.toml, docs/PIPELINE-GUIDE.md
```

세션 총 변경량이 크게 보이나, 실제로는 본 세션 이전 PR #12·#13·#14 의 산출물이 세션 직전 머지 상태에 이미 반영됐고 본 세션은 그 위에 PR #16·#20 을 올린 구조.

## 운영 배포 체크리스트 (누적)

- [ ] **`.env.prod`** 에 `KIS_CREDENTIAL_MASTER_KEY=<Fernet.generate_key()>` (PR 3/#14)
- [ ] 마스터키 secret manager 백업 — 분실 시 복구 불가
- [ ] 실 계좌 활성화 전 `POST /test-connection` 으로 credential 유효성 검증 (PR 5/#16)
- [ ] `LOG_LEVEL` env 는 `DEBUG|INFO|WARNING|ERROR|CRITICAL` 중 하나 (PR 6/#20, Pydantic Literal 검증)
- [ ] `APP_ENV=local` → ConsoleRenderer / 그 외 → JSONRenderer (PR 6/#20)
- [ ] 배포 직후 운영 로그 샘플 점검 — `[MASKED]` · `[MASKED_JWT]` · `[MASKED_HEX]` 가 실제 나타나는지, plaintext 누출 없는지 (PR 6/#20)
- [ ] KIS 자격증명 유출 의심 시 **즉시** KIS 웹사이트에서 `app_key` 재발급(roll) — 서버측 토큰 revoke 엔드포인트 없음 (24h TTL 대기, PR 6/#20 README 섹션)
- [ ] 로컬 실 KIS 검증: env 3개 주입 후 `pytest -m requires_kis_real_account -s` (PR 5/#16)
