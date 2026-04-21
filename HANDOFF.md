# Session Handoff

> Last updated: 2026-04-21 (KST, PR 4 구현·검증 완료)
> Branch: `master` 기준 feature branch 커밋 예정 (본 핸드오프 직후)
> Latest commit on master: `3db778f` — KIS sync PR 3: `brokerage_account_credential` + Fernet 암호화 (#14)

## Current Status

**KIS sync 시리즈 PR 4 (실계정 등록 API + Settings UI) 구현·리뷰·검증 완료, 커밋/푸시 대기**. 외부 호출 0 유지 — credential 등록·마스킹·삭제 CRUD 만 제공, 실 KIS 호출은 PR 5 에서 credential 저장소와 `SyncPortfolioFromKisUseCase` 를 wire 할 때 개시. 백엔드 **226 → 227** (+14, PR 3 후속 `test_create_account_blocks_real_environment` 1건을 PR 4 시맨틱에 맞춰 3건으로 분리 재작성), Next.js build PASS, mypy strict 0 (내 파일 4), ruff 0 (내 파일 6). 리뷰 HIGH 6건(BE 2 + FE 4) 전부 반영.

**KIS sync 진행률:** 4/6 PR 구현 완료 (엑셀 → 어댑터 → credential 저장소 → 등록 API/UI). 다음은 **PR 5 (연결 테스트 + 실 sync)**.

## Completed This Session (2026-04-21, PR 4)

| # | 작업 | 파일 |
|---|------|------|
| 1 | `RegisterAccountUseCase` 완화 — `kis_rest_real + environment='real'` 조합 허용, 불일치는 `InvalidRealEnvironmentError`로 라우터에서 403 | `app/application/service/portfolio_service.py` |
| 2 | `BrokerageCredentialUseCase` — `create`/`replace`/`get_masked`/`delete` + `_ensure_real_account` + `_require_view` (`assert` → `RuntimeError`) | `portfolio_service.py` |
| 3 | `CredentialAlreadyExistsError` / `CredentialNotFoundError` 예외 추가 | `portfolio_service.py` |
| 4 | Repository 확장 — `find_row` (복호화 X), `get_masked_view` (필요 필드만 복호화) + `_mask_tail` **비례 길이 마스킹** + `MaskedCredentialView` DTO | `repositories/brokerage_credential.py` |
| 5 | Pydantic 스키마 — `BrokerageCredentialRequest/Response` (후자는 `_Base` 상속), `AccountCreateRequest` 패턴 확장 | `_schemas.py` |
| 6 | 4개 HTTP 엔드포인트 `POST/PUT/GET/DELETE /api/portfolio/accounts/{id}/credentials` + `_cipher_failure_as_http` (CredentialCipherError → 500, 내부 미노출) | `routers/portfolio.py` |
| 7 | FE `RealAccountSection` 신규 (~380 lines) — 목록/등록/수정/삭제, 비례 마스킹, `actionPending` 중복 클릭 차단, PUT→POST 폴백 + 409 재시도 | `components/features/RealAccountSection.tsx` |
| 8 | FE types/API/Settings 배선 — `ConnectionType` 에 `kis_rest_real`, credential CRUD 함수 4개 | `types/portfolio.ts`, `lib/api/portfolio.ts`, `app/settings/page.tsx` |
| 9 | 백엔드 테스트 14건 추가 (HTTP 엔드포인트 9 + cipher/repo 2 + 조합 검증 3) | `tests/test_brokerage_credential.py`, `tests/test_portfolio.py` |

## In Progress / Pending

- **커밋/푸시/PR 생성 대기** — 사용자 확인 후 feature branch 로 분기해 커밋 · push · PR #15 생성.
- PR 3 직전 세션의 `CHANGELOG.md` / `HANDOFF.md` / `docs/kis-real-account-sync-plan.md` 미커밋 문서 3건도 이 커밋에 함께 반영 (PR 3 블록 + PR 4 블록 연속 기록).

## Key Decisions Made (PR 4)

- **`CredentialCipherError` 별도 catch → HTTP 500 변환** (리뷰 HIGH 반영): `DecryptionFailedError` / `UnknownKeyVersionError` 는 `PortfolioError` 와 무관한 계층. router 의 `except PortfolioError` 에 걸리지 않아 FastAPI 기본 500 으로 누출되면 스택트레이스가 노출된다. `_cipher_failure_as_http` 로 예외 타입만 로그에 남기고 응답 본문은 "자격증명 복호화 실패 — 운영자에게 문의" 로 sanitize. 테스트에서 응답에 `DecryptionFailedError`/`InvalidToken` 문자열이 없음을 명시 검증.
- **`_require_view()` 로 `assert` 대체** (리뷰 HIGH 반영): `upsert` 직후 `get_masked_view` 가 `None` 이면 DB flush 타이밍 이상 또는 동시 DELETE 레이스. `assert view is not None` 은 `python -O` 에서 제거돼 프로덕션에 silent `None` 이 흘러들어갈 수 있음. 명시적 `RuntimeError` 로 대체.
- **`_mask_tail` 비례 길이 마스킹** (리뷰 MEDIUM 반영): 기존 고정 4개 불릿(`"••••1234"`) 은 짧은 값에서 노출 비율이 과도해질 수 있음. `(len - keep)` 개 불릿으로 실제 가려진 문자 수와 일치시켜 "얼마나 가렸는지" 가 시각적으로 드러나게 함. 24자 app_key 는 `"••••••••••••••••••••1234"` (20 bullets + 4 tail).
- **`handleCreate` 흐름 재구성** (FE 리뷰 HIGH 반영): API 호출 성공 직후 `setShowForm(false)+resetForm()` 을 즉시 실행하고 `await reload()` 는 별도 try/catch 로 감싸 분리. 이전 구현은 reload 예외 시 폼이 닫히지 않은 채 pending 만 해제되는 불일치가 있었음. secret state 는 가능한 빨리 clear.
- **`showForm` 토글의 stale closure 제거** (FE 리뷰 HIGH 반영): `setShowForm(prev => !prev); if (showForm) resetForm();` 패턴은 batching 에서 `showForm` 이 stale. 함수형 업데이터 내부로 `resetForm()` 호출을 이동해 snapshot 시점 일관성 보장.
- **`actionPending` 단일 state 로 수정/삭제 버튼 중복 클릭 차단** (FE 리뷰 MEDIUM 반영): `number | null` — 처리 중인 account_id 를 담고, null 이면 idle. 모든 수정/삭제 버튼이 `disabled={actionPending !== null}` 로 잠김. 처리 중 해당 행은 "처리중…" 표시.
- **PUT→POST 폴백에서 409 race 자동 재시도** (FE 리뷰 HIGH 반영): 두 탭 동시 수정 시 PUT 404 → POST → 409 경로에서 혼란스러운 "이미 등록됨" 메시지가 노출되는 케이스. 폴백 POST 가 409 면 즉시 PUT 한 번 더 시도해 최종 상태를 수렴.
- **라우터에서만 조합 검증, Pydantic 은 enum 범위만** (설계 유지): `AccountCreateRequest` 의 `connection_type` + `environment` 패턴은 enum 범위(`^(manual|kis_rest_mock|kis_rest_real)$` / `^(mock|real)$`)만 강제. 조합 검증(`kis_rest_real ⇔ real`)은 `RegisterAccountUseCase` 에서 `InvalidRealEnvironmentError` → 403. 에러 메시지를 한글로 구체적으로 전달 가능.
- **`BrokerageCredentialResponse` 는 `_Base` 상속** (리뷰 LOW 반영): 프로젝트 응답 스키마 컨벤션 유지. `from_attributes=True` 를 `model_validate` 호출마다 지정하는 중복 제거.
- **DELETE 의 `cipher: CredentialCipher = Depends(...)` 유지** (의도적): repository 생성자가 cipher 를 필수 인자로 받으므로 DELETE 경로에서도 주입 필요. 마스터키 미설정 환경에서 DELETE 도 실패하는 부수효과가 있으나, PR 5 때 repository 재조직 시 함께 정리.

## Known Issues

### PR 5+ 로 이월된 항목
- **실 sync 봉쇄 여전**: `SyncPortfolioFromKisUseCase.execute` 의 `kis_rest_real` 분기는 여전히 `KisCredentialsNotWiredError` → HTTP 501. **PR 5** 에서 credential repo 주입 → `KisClient(REAL, credentials)` 조립.
- **"연결 테스트" 엔드포인트 없음**: OAuth 토큰 발급만 시도하는 dry-run — **PR 5** 소관.
- **로깅 마스킹 미적용**: structlog processor 로 `app_key`/`app_secret`/`access_token` 자동 치환 — **PR 6** 소관.

### PR 4 리뷰에서 의도적으로 스킵한 항목 (심각도·ROI 판단)
- **MEDIUM `MaskedCredentialView` layer re-export**: `app/application/service/portfolio_service.py` 가 persistence DTO 를 re-export 하는 구조. Hexagonal Architecture 상 어색. PR 5 때 `app/application/dto/credential.py` 로 분리 후보.
- **MEDIUM TOCTOU POST race**: `find_row → upsert` 사이 잠금 없음. Admin 전용 + DB `UNIQUE(account_id)` 로 데이터 무결성 보장. `SELECT FOR UPDATE` / `INSERT ... ON CONFLICT DO NOTHING` 는 향후 멀티유저 확장 때 검토.
- **LOW DELETE 의 cipher 주입 불필요**: 위 Decisions 참조. Repository 재조직 필요 — 단독 리팩터 PR 가치 낮음.
- **TS MEDIUM `adminCall` void 지원**: 204 No Content 응답 파싱 분기 부재. 현재 `deleteCredential` 이 직접 fetch 로 우회 (엑셀 업로드도 동일 패턴). 별도 리팩터 PR 분리.
- **TS MEDIUM toast 중복**: `RealAccountSection` 과 `SettingsPage` 가 각자 fixed toast 렌더. 공용 Context 로 승격 시 해결 — MVP 허용.
- **TS MEDIUM `window.prompt` UX**: 수정 흐름이 prompt × 3. 일부 모바일 브라우저에서 두 번째부터 차단 가능. 커스텀 모달로 교체 시점은 PR 5 이후 UX 폴리싱 단계.

### 일반 부채 (PR 3 이월)
- **CI 가 ruff/mypy 안 돌림**: `.github/workflows/*.yml` 에 lint/type 단계 없음. 소규모 PR 후보.
- **pre-existing F401 3건** (`tests/test_services.py`): CI 미통합 탓에 누적.
- **pre-existing signals.py mypy 2건**: `Stock | None` union-attr. 리팩터 PR 분리.
- **Python M2 중복 판단 N+1** (엑셀 import): 1 commit 소형.
- **MEDIUM #4 `setattr` mypy 우회** (`BacktestResult`): 30min~1h.
- **실 KIS 엑셀 샘플 부재**: PR #12 alias 보정 필요.
- **로컬 백엔드 이미지 재빌드 루틴 미편입**.
- **carry-over**: lending_balance T+1 지연, 218 stock_name 빈, TREND_REVERSAL Infinity 모니터링.

## Context for Next Session

### 사용자의 원래 목표 (진행 중)

KIS sync 시리즈 6 PR 중 4개 구현 완료. PR 4 머지 후 **PR 5 (연결 테스트 + 실 sync, 3단계 온보딩)** 로 진입. 여기서 드디어 외부 KIS API 호출이 시작됨 — `@pytest.mark.requires_kis_real_account` 로 CI 에서는 skip, 로컬에서만 실행되는 smoke 테스트 도입.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — 모든 PR 준수
- **push 는 명시 요청 시에만** — 본 세션에서는 `/ted-run` Step 4 진입 시 명시 요청 받음
- **설계 승인 루프**: 복잡 과제는 `docs/*-plan.md` 로 선행 설계 후 착수. PR 4 는 PR 1~3 때 확정된 설계 § 5 그대로 구현이라 별도 승인 없이 진행.
- **리뷰 수용 원칙**: CRITICAL/HIGH 즉시 반영, MEDIUM 은 ROI 판단. PR 4 는 HIGH 6건 전부 수용, MEDIUM 6건 중 3건 수용 · 3건 사유 기록 후 defer.
- **실측 마감 선호**: ruff + mypy + pytest + Next build 전부 통과 후 머지.
- **병렬 리뷰 활용**: python-reviewer + typescript-reviewer 동시 호출 — 본 PR 에서도 ~4분 내 양쪽 리뷰 완료.

### 차기 세션 후보 (우선순위 순)

1. **PR 5: 연결 테스트 + 실 sync** (`docs/kis-real-account-sync-plan.md` § 5 PR 5) — 2~3h. 외부 KIS API 호출 개시.
   - **BE**: `POST /api/portfolio/accounts/{id}/test-connection` (OAuth 토큰 발급만 dry-run), `SyncPortfolioFromKisUseCase` 에 `BrokerageAccountCredentialRepository` 주입 → credential decrypt → `KisClient(credentials, environment=REAL)` 조립. `KisCredentialsNotWiredError` 제거.
   - **FE**: Settings 섹션에 "연결 테스트" 버튼 + 포트폴리오 페이지에 실 계좌용 "잔고 동기화" 버튼 활성화.
   - **테스트**: 단위/통합은 MockTransport 유지. `@pytest.mark.requires_kis_real_account` smoke 1~2건 추가 — CI skip 마커 확인.
2. **CI 에 ruff + mypy strict 추가** — 3~5분 PR. F401 정돈 동반.
3. **PR 6: 로깅 마스킹** — structlog processor + token revoke 한계 README 명시.
4. **`MaskedCredentialView` → `app/application/dto/`** 분리 (레이어 정합) — PR 5 때 묶어서 처리.
5. **Python M2 중복 판단 N+1 최적화** (엑셀 import).
6. **`BacktestResult` setattr → 명시 setter**.

### 가치있는 발견 (PR 4 세션)

1. **`CredentialCipherError` vs `PortfolioError` 계층 분리의 실전 가치**: 두 예외 계층이 독립적이면 router 에서 개별 catch 가 필수. `except Exception:` 같은 포괄 catch 는 의미론적 sanitize 기회를 놓침. 계층 교차 예외는 명시적 매핑 테이블(`_cipher_failure_as_http`) 로 분리하면 응답 본문 위생이 팀 규칙화됨.
2. **`python -O` 대응으로 `assert` 전면 금지 규칙 재확인**: 프로젝트에 이미 실전 Docker 이미지가 있다면 `-O` 유무를 알 수 없음. 불변 조건 문서화용 `assert` 는 모두 `if not X: raise RuntimeError` 로 전환하는 것이 안전. 리뷰 에이전트가 먼저 발견한 규칙.
3. **마스킹 불릿 수 = 실제 가려진 문자 수**: 고정 4개 불릿은 짧은 값 노출 비율이 과도. 사용자 피드백 없이도 리뷰 에이전트가 "min_length=16 가드는 보안, 함수 자체는 재사용 열려있음" 으로 방어적 설계를 제안 — 규칙으로 고정.
4. **FE batching stale closure 패턴**: `setX(prev => !prev); if (x) ...` 형태는 React 18+ batching 에서 `x` 가 snapshot 이전 값을 가리킴. 함수형 업데이터 내부로 조건부 액션을 모두 이동하는 것이 안전.
5. **PUT→POST 폴백의 race 자연 해소**: 409 를 "이미 등록됨" 메시지로 소비하지 말고, 폴백 경로에서 발생한 409 는 "선행 등록이 있었다" 로 해석해 PUT 한 번 더 시도 → 최종 상태 수렴. UX 에러 메시지 혼란 원천 차단.
6. **Pydantic pattern 완화 후 조합 검증을 UseCase 로 이관**: 이전 PR 의 400 (pattern) 응답이 403 (UseCase) 로 바뀌면서 테스트 1건이 3건으로 분리돼 오히려 의미론이 명확해짐. 패턴 · 조합 · 비즈니스 규칙을 layer 별로 분리해두면 에러 메시지 일관성 유지 가능.

## Files Modified This Session (PR 4)

```
백엔드
  src/backend_py/app/adapter/out/persistence/repositories/brokerage_credential.py  (+MaskedCredentialView DTO +_mask_tail +find_row +get_masked_view)
  src/backend_py/app/application/service/portfolio_service.py                      (+BrokerageCredentialUseCase +예외 2종 +_require_view, RegisterAccountUseCase 완화)
  src/backend_py/app/adapter/web/_schemas.py                                       (+BrokerageCredentialRequest/Response, AccountCreateRequest 패턴 확장)
  src/backend_py/app/adapter/web/routers/portfolio.py                              (+4 엔드포인트 +_cipher_failure_as_http +_raise_for_credential_error)
  src/backend_py/tests/test_brokerage_credential.py                                (+11 테스트: repo 2 + HTTP 9)
  src/backend_py/tests/test_portfolio.py                                           (기존 1건 수정 → 3건 분리 +1)

프런트엔드
  src/frontend/src/components/features/RealAccountSection.tsx                      (신규 ~380 lines)
  src/frontend/src/app/settings/page.tsx                                           (<RealAccountSection/> 삽입)
  src/frontend/src/types/portfolio.ts                                              (+BrokerageCredential Request/Response, ConnectionType 확장)
  src/frontend/src/lib/api/portfolio.ts                                            (+4 credential 함수)

문서 (커밋 시 함께 반영)
  docs/kis-real-account-sync-plan.md                                               (§ 5 PR 4 → ✅, § 8 PR 4 완료 표시)
  CHANGELOG.md                                                                     (2026-04-21 PR 4 블록 추가)
  HANDOFF.md                                                                       (본 산출물)
```

본 세션 4번째 KIS sync PR 완료 (#15 예정). 다음 세션은 **PR 5 (연결 테스트 + 실 sync)** 진입 권장 — 이 PR 부터 실제 외부 호출 시작. credential 저장소 맥락 계속 따끈.

## 운영 배포 체크리스트 (PR 3 + PR 4)

- [ ] **`.env.prod`** 에 `KIS_CREDENTIAL_MASTER_KEY=<Fernet.generate_key() 출력>` 주입 필수 (PR 3).
- [ ] 마스터키 백업 (분실 시 복구 불가).
- [ ] PR 4 추가: 실계정 등록은 관리자만 가능 — `ADMIN_API_KEY` 부재 시 모든 credential 엔드포인트 401.
- [ ] PR 4 추가: Settings 페이지 "실계좌 연동" 섹션은 PR 5 전까지 "자격증명 저장" 만 가능하고 "연결 테스트"·"잔고 동기화" 는 PR 5 배포 후 활성화.
