# Session Handoff

> Last updated: 2026-04-20 (KST, 저녁)
> Branch: `feature/e2e-settings-save-toast` (master 기준 분기, uncommitted 0)
> Latest commit on master: `31d11ab` — 세션 마감 문서: 백테스트 Infinity 버그 수정 (#9)

## Current Status

직전 세션 HANDOFF 차기 1순위였던 **I6 (설정 저장 toast) E2E** 를 `/ted-run` 파이프라인으로 처리. Playwright `page.route` 로 PUT 만 인터셉트해 `notification_preference` 싱글톤 mutation 을 0건으로 격리한 뒤 성공/실패 toast 2건 추가. 리뷰 HIGH 1 + MEDIUM 3 모두 반영 후 로컬 settings.spec **7/7 PASS**, 전체 E2E 40/41 PASS (남은 1건 H5 는 로컬 백엔드 이미지의 seed 모듈 부재 — 내 변경과 무관, CI 는 매번 이미지 재빌드 + seed 실행이라 녹색). 본 브랜치 커밋만 남겨둔 상태, 푸시는 사용자 확인 후 진행.

## Completed This Session

| # | Task | 파일 | 비고 |
|---|------|-----|-----|
| 1 | I6-1 저장 성공 E2E (`waitForRequest` + `Promise.all` 로 race 제거, payload 캡처, toast filter) | `settings.spec.ts` | 리뷰 HIGH #1·MEDIUM #1·#2 반영 |
| 2 | I6-2 저장 실패 E2E (PUT 500 stub, `서버 오류가 발생했습니다` toast) | `settings.spec.ts` | `filter({ hasText })` 로 status 영역 정밀 매칭 |
| 3 | I6 격리 전략 문서화 + 표 갱신 (40→42 케이스, I6-1·I6-2 행 + 주석 갱신) | `docs/e2e-portfolio-test-plan.md` | 리뷰 MEDIUM #3 반영 |
| 4 | CHANGELOG Unreleased 블록 작성 | `CHANGELOG.md` | (본 커밋) |

## In Progress / Pending

- **푸시 + PR 생성** 사용자 요청 대기.
- 커밋 후 (선택) origin 푸시 + `gh pr create` → CI 확인 → 머지.

## Key Decisions Made

- **격리 전략: `page.route` 인터셉트 (PUT 한정)**: `afterEach` 로 DB 복원하는 대안 대비 외부 의존성 제로. PUT URL(`**/api/admin/notifications/preferences`) 과 GET URL(`/api/notifications/preferences`) 이 경로가 달라 glob 충돌 없음 → GET 은 자연스럽게 pass-through.
- **`waitForRequest` + `Promise.all` 패턴 채택 (리뷰 HIGH #1 반영)**: 기존안은 `let captured` 로 클로저에 캡처 후 assert 하는 방식이었으나 `route.fulfill()` 비동기 특성상 banner 가시성 타이밍과 race 가능. Playwright 공식 권장 패턴으로 교체.
- **updated_at 라벨 검증 제거 (리뷰 MEDIUM #2 반영)**: 초기 약한 검증(`/최근 업데이트:/` 정규식) 은 stub 반영 여부를 증명 못 함. 성공 toast + PUT payload 캡처만으로 "저장 경로가 진짜 trigger 됨 + 성공 경로 서사 완결" 이 입증되므로 라벨 체크는 과잉으로 판단해 drop.
- **H5 환경 실패는 스코프 밖**: 로컬 백엔드 이미지(4h 전 빌드)에 `app.batch.backtest_job` 모듈이 없어 `scripts.seed_backtest_e2e` 가 `ModuleNotFoundError` → `backtest_result` 0건 → `대차 급감` 라벨 부재. 내 변경은 `settings.spec.ts` + docs 만 touched. CI 는 매 실행마다 이미지 재빌드 + seed 실행이라 영향 없음.

## Known Issues

- **로컬 `scripts.seed_backtest_e2e` `ModuleNotFoundError`**: 현재 실행 중인 백엔드 이미지가 재빌드 전 snapshot. 로컬 H5 돌리려면 `docker compose -f docker-compose.prod.yml build backend && docker compose -f docker-compose.prod.yml up -d backend` → seed 재실행 필요. CI 영향 0.
- **`_dec(val) or Decimal("0")` 패턴** (`backtest_service.py:143`): 직전 세션 리뷰 MEDIUM #2 사전 부채. 차기 30분 규모 후보로 이월.
- **CI `Docker Build` 병목**: 여전히 2~3m. layer 캐시 개선 / conditional build 검토 여지.
- **carry-over 2026-04-16·17 `lending_balance` T+1 지연**: 해결 아님, `docs/data-state.md` 기록 유지.
- **218건 stock_name 빈 종목**: 현상 유지 결정 지속.
- **TREND_REVERSAL Infinity 재발 모니터링**: PR #9 로 소스 차단. 월요일 07:00 KST 첫 스케줄 실측 남음.

## Context for Next Session

### 사용자의 원래 목표 (달성)

직전 세션 HANDOFF "차기 세션 후보 1순위 — I6 (설정 저장 toast) E2E" 완결.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — 본 세션 준수
- **push 는 명시 요청 시에만** — 본 세션 커밋까지만 자동, 푸시 대기
- **설계 승인 루프**: 구현안 제안(표 + 격리 전략) → "진행하자" 확인 후 착수
- **리뷰 지적 즉시 반영**: HIGH 1 + MEDIUM 3 = 4건 모두 수용 → 재리뷰 생략하고 Step 3 진행 (ted-run 규칙)
- **체크리스트 + 한 줄 현황** — TaskCreate 6건 + 순차 체크 유지
- **실측 마감 선호** — 로컬 Playwright 전체 수트 실행 후 H5 환경 의존성 명확히 분리 보고

### 차기 세션 후보 (우선순위 순)

1. **`_dec(val) or Decimal("0")` 리팩터** (`backtest_service.py:143`): 직전 세션 리뷰 MEDIUM #2 사전 부채. `if _dec(x) is None` 명시 guard 로 교체. 30분 내.
2. **KIS 실계정 sync** — 현재 `kis_rest_mock` 만 지원. 실계좌·실잔고 동기화 미구현. 민감도 높아 보안 리뷰 필수. 엑셀·API 키·OAuth 순서 설계 필요. 수 시간 규모.
3. **CI `Docker Build` 최적화** — 3m 병목. `requirements.txt` layer 분리 or conditional build 검토.
4. **시드 시그널 실 탐지 경로 교체** — `seed_backtest_e2e.py` 의 score=80 고정 → `SignalDetectionService.detect_all` 호출로. 탐지 변경 시 CI 감지 가능하게.
5. **월요일 07:00 KST 스케줄러 실측** — PR #6·#9 적용 후 `backtest_result` 가 유한 값 + 축소된 신호 카운트로 정상 누적되는지 운영 로그로 확인. 관찰만.
6. **로컬 백엔드 이미지 재빌드 루틴화** — 이번처럼 H5 환경 오탐을 줄이도록 `docker compose build backend` 를 `/ted-run` Step 3-1 전 단계로 편입하는 안 검토.

### 가치있는 발견

1. **`waitForRequest` vs 클로저 캡처**: 비동기 `route.fulfill()` 타이밍을 믿고 `let captured` 로 스쿠프 공유하는 패턴은 CI 환경에서 race 가 실제로 현실화될 수 있음. Playwright 공식 `Promise.all([waitForRequest, click])` 이 유일하게 deterministic. "로컬에서 PASS = CI 에서도 PASS" 가 아님.
2. **`getByRole('status').first()` vs `filter({ hasText })`**: aria live region 이 여러 곳에 쓰이면 (예: aria-busy loading 스켈레톤) 첫 매치가 의도 밖 요소일 위험. 텍스트 기반 필터가 훨씬 안전.
3. **updated_at 라벨 검증의 함정**: 소스 코드에서 `toLocaleString('ko-KR')` 은 Node 버전·ICU 지원에 따라 출력이 미세하게 달라질 수 있음 (공백, 구분자). 약한 정규식은 stub 반영 증거가 못 됨. 강한 검증을 하려면 GET 도 stub 해서 before/after 값을 완전히 제어하거나, 아예 검증을 다른 지표(toast + payload) 로 옮기는 것이 실용적.
4. **URL 경로 설계가 격리 전략을 결정**: PUT (`/api/admin/...`) 과 GET (`/api/...`) 이 같은 리소스여도 경로가 달라 `page.route` glob 이 자연 분리. 만약 동일 경로였다면 method 기반 `route.fallback()` 처리가 필수였을 것. 이번엔 URL 설계가 선물.
5. **H5 로컬 실패 ≠ CI 실패**: 백엔드 이미지 재빌드 주기에 따라 로컬 H5 는 비결정적. 내 변경 여파 검증에는 "내 스펙 파일만 타깃 실행" + "전체 실행 후 실패 테스트의 원인 분리 확인" 두 단계 필요.

## Files Modified This Session

```
2 files changed

 src/frontend/tests/e2e/settings.spec.ts             | +73 / -1 (주석 + I6-1·I6-2 2건)
 docs/e2e-portfolio-test-plan.md                     | +3 / -2 (상태 + I6 행 2개 + 주석 갱신)
 CHANGELOG.md                                        | +9 (Unreleased 블록)
 HANDOFF.md                                          | (본 산출물)
```

본 세션은 **I6 설정 저장 toast E2E 단일 축** 에서 구현 → 리뷰 HIGH·MEDIUM 모두 반영 → 실행 검증 → 커밋 직전까지 완결. 차기 세션은 `_dec(val) or Decimal("0")` 30분 리팩터 (사전 부채 청산) 또는 KIS 실계정 sync 대형 과제 진입 중 택1.
