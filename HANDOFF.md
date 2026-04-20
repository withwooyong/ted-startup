# Session Handoff

> Last updated: 2026-04-20 (KST)
> Branch: `master` (clean, origin 동기화 완료)
> Latest commit: `0ff25a9` — Merge pull request #9 from withwooyong/feature/backtest-infinity-fix

## Current Status

직전 세션(3 PR 완결) 에서 HANDOFF 1순위 차기 후보로 남겨둔 **백테스트 `Infinity` INSERT 실패** 를 `/ted-run` 파이프라인으로 처리. 1 PR 추가 머지, CI 4/4 PASS. 리뷰 단계에서 HIGH 2건 지적받아 "분자·분모 동시 마스킹 → 분모만 마스킹" 으로 설계 재수정 + 추가 회귀 테스트 1건 보강. 로컬·원격 master 동기화, uncommitted 변경 없음.

## Completed This Session

| # | Task | PR | 주요 커밋 |
|---|------|-----|-----------|
| 1 | `backtest_service.py` 2-layer guard: 분모 `where(>0)` NaN 마스킹 + returns `where(isfinite)` | #9 | `74938cf` |
| 2 | 회귀 테스트 `test_backtest_handles_zero_close_price_without_infinity` (base=0 → return_Nd=None, INSERT 성공) | #9 | `74938cf` |
| 3 | 회귀 테스트 `test_backtest_preserves_minus_hundred_when_future_close_zero` (base=10000, future=0 → -100% 보존) | #9 | `74938cf` |
| 4 | `docs/data-state.md` 에 close_price=0 처리 + 기존 70k 시그널 vs 신규 임계값 관측 패턴 추가 | — | (본 산출물) |

**PR #9 머지** + `delete-branch` — CI 4/4 PASS × 1회.

## In Progress / Pending

없음. 세션 깔끔히 종료.

## Key Decisions Made

- **2-layer guard 채택 (#9)**: Layer 1 (분모 NaN 마스킹) 은 근본 원인 차단. Layer 2 (isfinite) 는 집계 경로의 `series.dropna()` 가 inf 를 제거하지 못한다는 특성 때문에 필수. 초기 주석에는 "방어선" 으로 표현했다가 리뷰 지적 후 "필수" 로 재프레이밍.
- **분자·분모 분리 (리뷰 HIGH #1 반영)**: `price_wide.where(>0)` 를 그대로 분자·분모에 동시 적용하면 `future=0 & base>0` 케이스가 `NaN/base = NaN` 이 되어 **유효한 -100% 전손 수익률이 집계에서 사라짐**. 승률·평균수익을 부풀리는 silent 회귀. `price_base` 를 별도 변수로 분리해 분모에만 적용.
- **MEDIUM #2 (`_dec(val) or Decimal("0")`)는 사전 부채로 분리**: `Decimal('0.0000')` falsy 이슈 + `observed==0` 분기에서만 None 가능한 불필요한 guard. 이번 PR 스코프 밖이라 건드리지 않음. 별도 PR 후보로 남김.
- **`/ted-run` 파이프라인 활용**: 구현 → 리뷰 → 빌드 → 커밋 4단계 연결. 리뷰어의 uncommitted 변경 미인식은 툴링 제약이지만 "지적 구체성 + 회귀 테스트 통과" 로 효력 검증 가능.

## Known Issues

- **MEDIUM #2 `_dec(val) or Decimal("0")` 패턴** (`backtest_service.py:143`): `Decimal('0.0000')` 이 Python 에서 falsy 라 `_dec(0.0) or Decimal('0')` 은 실질 동일값이지만 의도 불투명. `observed==0` 분기에서만 None 가능하므로 guard 자체가 과잉. 명시적 `if _dec(x) is None` 으로 리팩터 후보. 기능적 영향은 없음.
- **기존 70k 시그널 vs 신규 임계값**: PR #6 로 임계 상향했지만 signal 테이블의 기존 70,609건은 옛 기준. append 모델이라 자연 보존. 월요일 07:00 KST cron 실행 후부터 새 기준 집계가 `backtest_result` 에 누적.
- **CI `Docker Build` 병목**: PR #9 에서 2m28s. 백엔드 변경 PR 에서 여전히 2~3m 수준. layer 캐시 개선 / conditional build 검토 여지.
- **carry-over 2026-04-16·17 `lending_balance` T+1 지연**: 해결 아님, `docs/data-state.md` 기록 유지.
- **218건 stock_name 빈 종목**: 현상 유지 결정 지속.
- **I6 (저장 성공 toast) 미커버**: `notification_preference` 싱글톤 mutation 격리 전략 확정 후 별도 PR 로 추가.
- **TREND_REVERSAL Infinity 재발 모니터링**: PR #9 로 소스는 차단했지만 월요일 첫 스케줄 실행 후 실제 집계 결과를 한 번 확인해 `backtest_result` 에 유한 값이 정상 적재되는지 검증 필요. (관찰만, 코드 변경 없음)

## Context for Next Session

### 사용자의 원래 목표 (달성)

직전 세션 HANDOFF "차기 세션 후보 1순위 — TREND_REVERSAL Infinity 버그" 완결.

### 사용자 선호·제약 (재확인)

- **커밋 메시지 한글 필수** — PR #9 준수
- **push 는 명시 요청 시에만** — "1. 푸시 + PR 생성" 확인 후 실행
- **설계 승인 루프**: 구현안 제안 → 사용자 확인 → 착수. 본 세션 리뷰 HIGH 지적 반영 시에도 "HIGH 수정 후 Step 3 계속" 자동 진행 규칙 준수.
- **체크리스트 + 한 줄 현황** — `feedback_progress_visibility.md` memory 적용 유지. 본 세션 TaskCreate 5건 + 완료 체크.
- **실측 마감 선호** — ruff + mypy + pytest 전체 실행, CI 4/4 PASS 까지 대기 후 머지.
- **`/ted-run` 파이프라인** — 구현/리뷰/빌드/커밋 자동 연결. 사용자가 명시적으로 invoke.
- **버그 발견 시 원인 규명 우선** — 리뷰 HIGH #1 (분자·분모 동시 마스킹) 처럼 의미 회귀까지 파고드는 리뷰 수용.

### 차기 세션 후보 (우선순위 순)

1. **I6 (설정 저장 toast) E2E** — `page.route('/api/admin/notifications/preferences')` 로 PUT 인터셉트 → 싱글톤 mutation 보호 + 성공/실패 toast 검증. 30분 내.
2. **`_dec(val) or Decimal("0")` 리팩터** (`backtest_service.py:143`): 리뷰 MEDIUM #2 사전 부채. `if _dec(x) is None` 명시 guard 로 교체. 30분 내.
3. **KIS 실계정 sync** — 현재 `kis_rest_mock` 만 지원. 실계좌·실잔고 동기화 미구현. 민감도 높아 보안 리뷰 필수. 엑셀·API 키·OAuth 순서 설계 필요. 수 시간 규모.
4. **CI `Docker Build` 최적화** — 3m 병목. `requirements.txt` layer 분리 or conditional build 검토.
5. **시드 시그널 실 탐지 경로 교체** — `seed_backtest_e2e.py` 의 score=80 고정 → `SignalDetectionService.detect_all` 호출로. 탐지 변경 시 CI 감지 가능하게.
6. **월요일 07:00 KST 스케줄러 실측** — PR #6·#9 적용 후 `backtest_result` 가 유한 값 + 축소된 신호 카운트로 정상 누적되는지 운영 로그로 확인. 관찰만.

### 가치있는 발견

1. **분모/분자 마스킹의 의미 차이**: 금융 수익률 계산에서 `NaN/value` 와 `value/NaN` 은 모두 NaN 이지만, **`0/value=0` 이 되면 -100% 라는 유효값** 이 나와야 한다. 전역 마스킹은 silent 의미 회귀를 만들어 "일부 종목이 -100% 기록 안 됨" 이라는 탐지 어려운 버그로 이어짐. 리뷰어의 초기 HIGH #1 지적이 없었다면 1차 fix 로 배포됐을 가능성 큼. **belt-and-suspenders 접근도 의미 보존을 우선 고려해야 함**.
2. **`dropna()` 는 inf 를 남긴다**: pandas 직관과 달리 `series.dropna()` 는 NaN 만 제거하고 `np.inf`·`-np.inf` 는 보존. aggregation 파이프라인에서 단일 inf 도 `mean()` 을 `inf` 로 만들어 downstream 전파. Numeric guard 는 `where(isfinite)` 가 정답.
3. **리뷰 에이전트 툴링 제약**: `everything-claude-code:python-reviewer` 는 git tree 읽기 기반이라 uncommitted 변경을 감지 못 함. 1차 리뷰 후 수정 → 재리뷰 요청 시 "push 전" 상태에서는 커밋 SHA 가 동일해 "변경 없음" 응답. 회피책: (a) 수정 후 커밋 → 재리뷰, (b) 지적 구체성 + 회귀 테스트 통과로 실효 검증. 본 세션은 (b) 경로.
4. **한 번의 fix 로 가장 심각한 tech debt 해소**: Baseline 측정에서 관측된 `Infinity` 가 유일하게 남은 백테스트 적재 실패 원인이었음. 70k 시그널 + 3년 구간 재집계가 PR #9 머지 후 다음 월요일부터 정상 수행될 전망.
5. **`docs/data-state.md` 의 역할**: "정상이지만 이상해 보이는 패턴" 저장소. 이번 세션에서 close_price=0 처리 + 70k 레거시 시그널 주석을 추가. UI/E2E 설계 시 이 파일 먼저 보고 들어가면 불필요한 방어 코드 줄일 수 있음.

## Files Modified This Session

```
1 code commit (74938cf — 머지 커밋 포함하면 +1) + docs 업데이트

 CHANGELOG.md                                                         | (+30)
 HANDOFF.md                                                           | (본 산출물)
 docs/data-state.md                                                   | (+3 새 관측 패턴)
 src/backend_py/app/application/service/backtest_service.py           | +10 / -1
 src/backend_py/tests/test_services.py                                | +89 / 0 (회귀 2건)
```

본 세션은 **백테스트 Infinity 버그 단일 축** 에서 리뷰 루프까지 완결. 백엔드 테스트 181 → 183, E2E 변화 없음. 차기 세션은 I6 (설정 저장 toast) 또는 `_dec or Decimal("0")` 리팩터 중 30분 규모 소형 과제부터 + KIS 실계정 sync 같은 대형 과제 전에 준비 작업(보안 리뷰 세팅) 분리 검토.
