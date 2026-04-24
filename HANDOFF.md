# Session Handoff

> Last updated: 2026-04-24 16:30 KST (세션 최종 마감 — **v1.2 착수: Discovery + Cp 0/1/2α 3 체크포인트 완주**)
> Branch: `master` (working tree **clean**, origin 과 **미동기화** — 3 커밋 대기)
> Latest commit: `45837fd` — feat(v1.2): Cp 2α — useIndicatorPreferences v2 스키마 + 파라미터 end-to-end 배선
> 세션 시작점: `e110b30` (v1.1 마감 핸드오프 커밋) 이후

## Current Status

한 세션에 **v1.2 iteration 의 5 개 체크포인트 중 3 개(60%)를 완주**:

1. **Discovery**: 옵션 β (biz+pm+judge) 로 6 산출물 생성, Judge PASS **9.05 / 10**. 사전 스파이크로 실스택 교정 (카카오 OAuth 미구현 → X-API-Key + NotificationPreference 싱글톤 패턴 상속)
2. **Cp 0 — Vitest + RTL + MSW 하네스**: 기존 indicators 5 유틸에 39 테스트 장착 (coverage 99.25%)
3. **Cp 1 — Bollinger Bands**: BB 유틸 + 차트 overlay + 토글 (12 테스트 추가)
4. **Cp 2α — 훅 v2 스키마 + 파라미터 배선**: 훅 전면 재작성 + v1→v2 마이그레이션 + 페이지/차트/테이블/토글 end-to-end 배선 (35 훅 테스트, coverage 100%)

총 **3 커밋** (working tree clean, origin 반영 대기). 테스트 **94 건** 그린, useIndicatorPreferences.ts 100% 커버.

## Completed This Session

| # | 커밋 | 제목 | 성격 |
|---|---|---|---|
| 1 | `e13e0e2` | Discovery + Cp 0 Vitest 하네스 — 테스트 기반 선행 (19 files, +3939/−38) | feat(v1.2) |
| 2 | `8ece65c` | Cp 1 — Bollinger Bands 유틸 + 차트 overlay + 토글 통합 (8 files, +293/−5) | feat(v1.2) |
| 3 | `45837fd` | Cp 2α — useIndicatorPreferences v2 스키마 + 파라미터 end-to-end 배선 (7 files, +658/−119) | feat(v1.2) |

## v1.2 Sprint 진행 현황

| Cp | 내용 | 공수 | 상태 | 커밋 |
|---|---|---:|---|---|
| **0** | Vitest + RTL + MSW 하네스 + indicators 테스트 | 1.5d | ✅ 완료 | `e13e0e2` |
| **1** | Bollinger Bands 유틸 + overlay + 토글 | 1.25d | ✅ 완료 | `8ece65c` |
| **2α** | 훅 v2 스키마 + v1→v2 마이그레이션 + params 배선 + 훅 테스트 35 건 | (2 split 채택) | ✅ 완료 | `45837fd` |
| **2β** | `IndicatorParametersDrawer` 편집 UI + 컴포넌트 테스트 + Drawer 오픈 버튼 연결 | — | ⬜ 대기 | — |
| **3** | Alembic 009 + BE 엔드포인트 + FE DB 어댑터 + Route Handler 릴레이 + 테스트 | 3.0d | ⬜ 대기 | — |
| **4** | BB 툴팁/sr-only 업데이트 + CI FE job + Lighthouse + 번들 diff + QA | 1.25d | ⬜ 대기 | — |

## 테스트 상태

| 영역 | 파일 | 케이스 | Coverage |
|---|---:|---:|---|
| indicators (sma/rsi/macd/aggregate/bb/index) | 6 | 51 | 99.37%/97.56%/100%/100% |
| useIndicatorPreferences | 1 | 35 | **100%/100%/100%/100%** |
| MSW 하네스 sanity | 1 | 3 | — |
| **합계** | **8** | **94** | — |

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | **커밋 푸시** | ⏳ 사용자 대기 | `e13e0e2 + 8ece65c + 45837fd` 3 커밋 origin 반영 필요 (전역 규칙상 명시 요청 시에만) |
| 2 | **브라우저 시각 검증** | ⏳ 사용자 대기 | `/stocks/005930` 에서 기존 토글 + BB on/off 동작 회귀 없는지 확인. 파라미터 UI 는 Cp 2β 이후 |
| 3 | **Cp 2β 착수** | 🟢 가능 | `IndicatorParametersDrawer` 편집 UI — Drawer/Sheet 반응형, 폼 검증, focus trap, 컴포넌트 테스트 |
| 4 | **Cp 3 착수** (2β 이후) | 🟢 가능 | Alembic 009 + BE 라우터 + FE 어댑터 + Route Handler 릴레이 |
| 5 | **Cp 4 착수** (3 이후) | 🟢 가능 | BB 툴팁/sr-only + CI FE job + Lighthouse + 번들 diff |
| 6 | **Aurora CLS 개선** | 🟡 분리 | v1.1 이월. 실기기 체감 확인 후 디자인 PR |
| 7 | **2026-04-20 OHLCV 전 0값 레코드** | 🟡 분석 | v1.1 이월. KRX 수집 배치 부분 실패 원인 추적 |
| 8 | 이전 세션 이월 — 다른 서비스 DIP 확장 (Telegram/Krx/Dart) | 백엔드 1~2h | |
| 9 | 이전 세션 이월 — DB 모델 `Mapped[str]` → `Literal` | 백엔드 1h | |
| 10 | 이전 세션 이월 — R-04/R-05/R-06 소규모 이슈 | 각 30분 | |

**미커밋 변경**: **없음** (working tree clean). 본 HANDOFF.md 수정은 이 마감 커밋에 포함.

## Key Decisions Made

### v1.2 스코프 / 프로세스
1. **옵션 β + 사전 스파이크 2 건**: v1.1 과 동일하게 biz+pm+judge 로 축소. 스파이크 2 건으로 실스택(카카오 OAuth 미구현 + NotificationPreference 싱글톤 선례) 을 검증 후 PRD 교정 — 정확성 9.0 달성
2. **Judge 권고 #1 (Cp 2 분리)**: 원안 3-split (2a/2b/2c) 대신 **2-split** 채택. 2a 단독은 dead code 가 되는 구조적 문제 회피 — 2α = 훅 v2 + 배선, 2β = 편집 UI

### 기술 결정
3. **카카오 OAuth 미구현 확인 → 싱글톤 id=1 패턴 상속**: CLAUDE.md 의 "카카오 OAuth 2.0" 언급은 로드맵 레벨. 실구현은 `require_admin_key` (X-API-Key) 단일 인증. `indicator_preferences` 테이블은 `NotificationPreference` 선례(`migrations/versions/002`) 를 그대로 복제
4. **lightweight-charts v5 band 채움 미지원**: typings.d.ts PoC 로 확인 (AreaSeries/BaselineSeries 는 baseline-relative 단일 그라데이션만). v1.2 MVP 는 3 LineSeries only, 채움은 v1.3 custom primitive 로 이월
5. **BB 표본 표준편차 one-pass 공식**: sumSq / sum² 차분. KRW 대형 스케일 (예: 200,000 원) 에서는 정밀도 손실 가능하나 MVP 허용 범위. 필요 시 Welford online 으로 교체 — 주석 명시
6. **v1 localStorage 무손실 마이그레이션**: v1 키 → v2 자동 합성(`migrateV1ToV2`), 토글 전부 이식, 파라미터는 DEFAULT_PARAMS. v2 저장 시점에 v1 키 1 회성 삭제
7. **setPrefs API 선행 확보**: Cp 3 DB 어댑터가 서버 페이로드 일괄 주입할 통로로 `useIndicatorPreferences` 의 공개 API 에 setPrefs 포함. 훅 재작성 시 한 번에 반영
8. **snapshot 캐시 키 확장**: `${source}:${raw}` 조합으로 v1/v2 전환 invalidate 동시에 v1.1 의 React #185 방어 패턴 유지

### 코드 품질
9. **v8 ignore 로 SSR 분기 가드**: jsdom 도달 불가한 `typeof window === 'undefined'` 분기 + `getServerSnapshot` 을 ignore. 향후 SSR 확장 시 ignore 제거 + SSR 테스트 추가 경로 명시
10. **useIndicatorPreferences 100% 커버 임계 활성화**: Cp 0 에서는 indicators 90% 만 걸고 hooks 임계는 Cp 2 예정 주석 → Cp 2α 에서 약속대로 복원 (100% lines/branches/functions/statements)
11. **모듈 스코프 상수화**: 페이지의 `MA_COLORS` / `MA_TOGGLE_KEYS` 를 리뷰 지적 후 파일 상단으로 승격 — eslint-disable 제거

## Known Issues

### 이번 세션 중 발견 → 해결
- 타입 가드 이중 cast (IndicatorPrefs → Record<string, unknown>) → `v is Record<string, unknown>` 으로 narrow target 완화로 해소 (1차 타입체크 에러)
- Cp 2α 커버리지 위반 (useIndicatorPreferences.ts < 100%) → v8 ignore + 누락 검증 분기 테스트 추가로 임계 통과
- 스켈레톤 placeholder 토글 수 7 → 8 (BB 추가로 CLS 플리커) → INFO 반영

### Known Issue (v1.1 이월)
- **Perf 95 → 80 회귀** (`/stocks/005930`): aurora blob-4 transform 애니메이션 CLS 0.393. v1.2 에서 Lighthouse 재측정 Cp 4 예정
- **2026-04-20 stock_price OHLCV 전 0값**: KRX 수집 배치 부분 실패 가능성. 차트 측 방어는 v1.1 에서 완료

### 미해결 (v1.2 후속)
- **Cp 2β 편집 UI 이월**: 데이터 흐름은 완비 (prefs.params 사용자 편집값이 차트에 반영) 되지만 사용자가 직접 편집하는 UI 는 아직 없음 → DEFAULT_PARAMS 고정 상태
- **Cp 3 DB 영속화**: 기기간 동기화 아직 없음, localStorage only
- **Cp 4 CI FE job + Lighthouse**: CI 에 Vitest job 추가 + Lighthouse 재측정 대기
- **BB 툴팁 + sr-only 표**: BB 활성 시 OHLCV 툴팁에 upper/middle/lower 3 값 추가 + sr-only 표에 BB 열 — Cp 4 예정
- 이전 세션 이월 — 다른 서비스 DIP 확장, `Mapped[str]` → `Literal`, R-04~06

## Context for Next Session

### 사용자의 원 목적 (본 세션 전체 흐름)

세션 진입 시 사용자 요청은 "v1.2 착수 (Bollinger Bands + 지표 파라미터 편집 UI + DB 영속화 + Vitest 하네스)". 수행 과정:

1. 사용자에게 **진행 옵션 4 안 (α/β/γ/δ/β+γ) 제시** → α (완전 Discovery + 순차 Sprint) 선택
2. `/plan` 스킬로 **Discovery 6 산출물 생성**. 사전 스파이크로 실스택 교정 (카카오 OAuth 미구현 확인 → 싱글톤 패턴 결정). Judge PASS 9.05
3. **Cp 0 착수** — Vitest + RTL + MSW 설치 + 설정 + MSW mock + indicators 테스트 5 종 (39 케이스). typescript-reviewer APPROVE 후 커밋
4. **Cp 1 착수** — Bollinger Bands 유틸 + 차트 overlay + 토글. lightweight-charts v5 의 band 채움 미지원 확인 (PoC 15 분). typescript-reviewer APPROVE (INFO/MEDIUM 3 건 반영) 후 커밋
5. **Cp 2 분리 판단** — Judge 권고 3-split 보다 **2-split (2α + 2β)** 이 dead-code 구조 회피 측면에서 더 자연스러움을 제시 → 사용자 승인
6. **Cp 2α 착수** — 훅 전면 재작성 (v2 스키마 + 마이그레이션), 35 훅 테스트, 페이지/차트/테이블/토글 end-to-end 배선. typescript-reviewer APPROVE (MEDIUM 2 건 반영: overbought>oversold 교차검증 + 모듈 스코프 상수화) 후 커밋
7. **/handoff 로 세션 마감**

### 선택한 접근과 이유

- **체크포인트 단위 커밋**: 각 체크포인트 하나가 "유효한 중간 상태" — 롤백 단위 명확 + 시각 검증 사이클 짧음 (v1.1 에서 검증된 리듬 재사용)
- **테스트 선행 (Cp 0)**: 이후 체크포인트가 기존 indicators 를 수정/확장하는 위험 도장. 실제로 Cp 1/2α 에서 훅 재작성 시 기존 테스트가 회귀 조기 발견에 기여
- **사전 스파이크로 PRD 교정**: 카카오 OAuth 가정을 실스택 조사로 뒤집음 → Cp 3 공수 추정 신뢰도 상승
- **2-split 제안**: Judge 의 3-split 권고를 맹목 수용하지 않고 dead-code 문제를 언어화해 사용자 결정권 유지

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 는 명시 요청 시에만** — 이번 세션도 3 커밋 origin 반영 대기
- **npm 기반** — yarn 사용 금지
- **Gate 승인 루프** — 매 의사결정 지점에서 옵션 제시 후 사용자 선택 (α/β/γ 패턴 재사용)
- **리뷰 후 CRITICAL/HIGH 즉시 반영, MEDIUM 도 trivial 하면 반영**
- **pre-commit hook `--no-verify` 금지** — 훅 오탐 시 `-F` 파일 우회
- **코드 주석 최소 (CLAUDE.md)** — Why 가 중요한 부분만 간결히
- **실측 기반 검증** — typings.d.ts PoC, alembic 선례 파일, `require_admin_key` 실제 호출 지점 등 실코드로 가정 교정

### 다음 세션에서 먼저 확인할 것

1. **3 커밋 푸시 여부** — `e13e0e2 + 8ece65c + 45837fd`
2. **브라우저 시각 검증** — `/stocks/005930` 에서 기존 토글 + BB on/off 동작 회귀 없는지. 파라미터 변경 체험은 Cp 2β 이후
3. **Cp 2β 착수 판단** — `IndicatorParametersDrawer` (Drawer + Sheet 반응형, 폼 검증, focus trap, 컴포넌트 테스트). 예상 공수 ~2d
4. **또는 Cp 2β 건너뛰고 Cp 3 착수** — 편집 UI 없이 DB 영속화만 먼저? (옵션이긴 하지만 UI 없이 DB 만 있으면 테스트 시나리오 제한적)
5. **이월 과제 우선순위** — v1.1 known issue (Aurora CLS, OHLCV 0값 추적), 이전 세션 이월 (DIP 확장, Mapped Literal)

### 가치 있는 발견 (본 세션)

1. **2-split vs 3-split 의 구조적 차이**: 3-split 의 중간 커밋이 dead code 로 남을 수 있는 문제 → end-to-end 데이터 흐름 단위로 묶는 2-split 이 "유효한 중간 상태" 제공. 범용 원칙으로 재사용 가능
2. **실스택 조사 ROI**: CLAUDE.md 의 "카카오 OAuth 2.0" 문구가 실제 구현 유무와 불일치 → 5 분 `grep kakao` 으로 전면 PRD 교정. 의존성 테이블도 동시에 검증 (`_deps.py:113`, `migrations/002`, `route.ts:17` 각각 실존 확인)
3. **lightweight-charts v5 band 제약**: 두 선 사이 채움은 custom primitive 필요. v1.3 과제로 명확히 분리한 덕에 Cp 1 범위 고정
4. **Vitest 4 + Next 16 + React 19 호환성**: 공식 Next vitest 가이드 그대로 따라 30 분 내 하네스 구동. `@testing-library/react@^16` 이 React 19 지원, `msw@2` + `setupServer` 는 jsdom 에서 무난
5. **v8 ignore 의 합리적 사용**: SSR 분기처럼 jsdom 도달 불가 경로는 테스트 강제보다 ignore 가 정직. 향후 SSR 확장 시 ignore 제거 + 테스트 추가 경로 주석으로 명시 → 미래 자신/리뷰어에게 친절
6. **스냅샷 캐시 키 확장**: `${source}:${raw}` 조합으로 v1/v2 전환 invalidate 동시에 React #185 방어 유지. 캐시 키를 단순 문자열이 아닌 "데이터 출처 + 값" 으로 둔 덕에 상태 전환이 자연스러움
7. **훅 재작성 시 테스트 먼저 짜면 API 설계 질 상승**: setToggle/setParams/setPrefs 3 분할 API 를 테스트 관점에서 검토 → Cp 3 DB 어댑터용 setPrefs 가 자연스럽게 도출
8. **리뷰 MEDIUM 중 trivial 건 즉시 반영의 가치**: overbought>oversold 교차검증은 한 줄. 모듈 스코프 상수화는 두 줄. 누적하면 코드 신뢰도 상승, 누적 부담 없음

## Files Modified This Session

```
 CHANGELOG.md                                                   — ~120 prepend (3 커밋 섹션)
 HANDOFF.md                                                     — overwrite (본 문서)
 pipeline/state/current-state.json                              — ~65 (iterations.v1.2 블록 신설)
 pipeline/artifacts/00-input/user-request-v1.2-chart-params-db-vitest.md   — 신규
 pipeline/artifacts/01-requirements/requirements-v1.2-chart-params-db-vitest.md — 신규 (US 12 / FR 16 / NFR 10)
 pipeline/artifacts/02-prd/prd-v1.2-chart-params-db-vitest.md   — 신규 (8 섹션)
 pipeline/artifacts/02-prd/roadmap-v1.2-chart-params-db-vitest.md — 신규 (v1.1 delta 포함)
 pipeline/artifacts/02-prd/sprint-plan-v1.2-chart-params-db-vitest.md — 신규 (체크포인트 5 개)
 pipeline/decisions/discovery-v1.2-judge.md                     — 신규 (PASS 9.05)

 src/frontend/package.json                                      — scripts + devDeps 10
 src/frontend/package-lock.json                                 — +2394
 src/frontend/vitest.config.ts                                  — 신규 (jsdom + coverage v8)
 src/frontend/src/test-setup.ts                                 — 신규 (jest-dom + MSW lifecycle)
 src/frontend/src/test/msw/handlers.ts                          — 신규 (GET/PUT + errorHandlers)
 src/frontend/src/test/msw/server.ts                            — 신규 (setupServer)
 src/frontend/src/test/msw/msw-smoke.test.ts                    — 신규 (3 sanity)

 src/frontend/src/lib/indicators/sma.test.ts                    — 신규 (9)
 src/frontend/src/lib/indicators/rsi.test.ts                    — 신규 (9)
 src/frontend/src/lib/indicators/macd.test.ts                   — 신규 (9)
 src/frontend/src/lib/indicators/aggregate.test.ts              — 신규 (weekly/monthly)
 src/frontend/src/lib/indicators/index.test.ts                  — 신규 (barrel sanity)
 src/frontend/src/lib/indicators/bb.ts                          — 신규 (O(n) 슬라이딩)
 src/frontend/src/lib/indicators/bb.test.ts                     — 신규 (12)
 src/frontend/src/lib/indicators/index.ts                       — bb/BBResult barrel

 src/frontend/src/lib/hooks/useIndicatorPreferences.ts          — 전면 재작성 (v2 스키마)
 src/frontend/src/lib/hooks/useIndicatorPreferences.test.ts     — 신규 (35 케이스, 100% coverage)

 src/frontend/src/components/charts/PriceAreaChart.tsx          — BBSeriesProp + BB useEffect + RSI 가이드 props
 src/frontend/src/components/charts/IndicatorTogglePanel.tsx    — bb 토글 + props { toggles, onToggle }
 src/frontend/src/components/charts/StockChartAccessibilityTable.tsx — { ma1, ma2 } + rsiPeriod 동적 레이블

 src/frontend/src/app/stocks/[code]/page.tsx                    — params 배선 + MA_COLORS/MA_TOGGLE_KEYS 모듈 스코프 + setToggle
```

**3 commits total. Discovery + Cp 0 (1) + Cp 1 (1) + Cp 2α (1).**

### Context to Load (다음 세션)

Cp 2β 또는 Cp 3 착수 시 먼저 로드할 파일:

```
pipeline/artifacts/02-prd/sprint-plan-v1.2-chart-params-db-vitest.md  # 체크포인트 상세
pipeline/artifacts/02-prd/prd-v1.2-chart-params-db-vitest.md          # 기능 스펙 (3.2 편집 UI, 3.3.2 DB 영속화)
src/frontend/src/lib/hooks/useIndicatorPreferences.ts                 # 훅 v2 API 확인
src/frontend/src/lib/hooks/useIndicatorPreferences.test.ts            # 기존 테스트 패턴
src/backend_py/migrations/versions/002_notification_preference.py     # Cp 3 Alembic 선례
src/backend_py/app/adapter/out/persistence/repositories/notification_preference.py  # Cp 3 Repository 선례
src/frontend/src/app/api/admin/notifications/preferences/route.ts     # Cp 3 Route Handler 릴레이 선례
```
