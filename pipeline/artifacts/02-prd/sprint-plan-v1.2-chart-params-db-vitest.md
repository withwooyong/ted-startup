---
agent: "02-pm"
stage: "02-prd"
version: "1.2.0"
iteration: "v1.2"
created_at: "2026-04-24T09:55:00+09:00"
depends_on:
  - "pipeline/artifacts/02-prd/prd-v1.2-chart-params-db-vitest.md"
  - "pipeline/artifacts/02-prd/roadmap-v1.2-chart-params-db-vitest.md"
quality_gate_passed: false
---

# Sprint Plan — v1.2 (1 스프린트 × 2 주 내 런칭)

## RICE 스코어링 (v1.2 MVP)

| 기능 | Reach | Impact | Confidence | Effort (days) | **RICE** | 우선순위 |
|---|---:|---:|---:|---:|---:|---|
| **Vitest 하네스 + indicators 단위 테스트** | 10 | 3 | 0.9 | 1.5 | **18.0** | P0 (Cp 0, 선행) |
| **Bollinger Bands 유틸 + overlay + 토글** | 10 | 2.5 | 0.9 | 1.25 | **18.0** | P0 (Cp 1) |
| **파라미터 편집 UI (drawer/sheet + 검증)** | 10 | 3 | 0.85 | 2.5 | **10.2** | P0 (Cp 2) |
| **useIndicatorPreferences v2 스키마 + v1→v2 마이그레이션** | 10 | 3 | 0.9 | 1 | **27.0** | P0 (Cp 2 동반) |
| **BE 엔드포인트 + Alembic 009 + Repository** | 10 | 2.5 | 0.9 | 1.5 | **15.0** | P0 (Cp 3) |
| **FE DB 동기화 어댑터 + Route Handler 릴레이** | 10 | 2.5 | 0.85 | 1 | **21.3** | P0 (Cp 3 동반) |
| **BB 툴팁 + sr-only 표 + 접근성 회귀** | 10 | 2 | 0.95 | 0.5 | **38.0** | P0 (Cp 4) |
| **CI FE vitest job** | 10 | 2 | 0.9 | 0.5 | **36.0** | P0 (Cp 4 동반) |
| **Lighthouse 재측정 + QA 체크리스트** | 10 | 2.5 | 0.95 | 0.75 | **31.7** | P0 (Cp 4 마감) |

**RICE 포뮬러**: `Reach × Impact × Confidence / Effort` (Reach 10 = 전 사용자, 즉 본인)

**합계 공수**: 10.5d. 2 주 (10 영업일) 예산 내 — 버퍼 없음. 버퍼 필요 시 파라미터 편집 UI 의 BB 섹션 or sr-only 업데이트를 v1.2.1 후속으로 조정 가능.

## 체크포인트 분해

### 체크포인트 0 — Vitest 하네스 선행 (2026-04-24 ~ 2026-04-25, 1.5d)

**목표**: 회귀 안전망을 먼저 세운다. 이후 체크포인트마다 테스트 동반.

| # | 태스크 | 산출 | 예상 공수 |
|---|---|---|---:|
| 0.1 | **PoC**: Vitest 2 + @vitejs/plugin-react 4 + jsdom 25 + React 19 호환 30 분 스파이크 | 동작 확인 로그 | 0.3d |
| 0.2 | devDep 설치 + `vitest.config.ts` + `src/test-setup.ts` + `package.json` scripts | 설정 파일 | 0.2d |
| 0.3 | MSW 2 + `src/test/msw/{server,handlers}.ts` — GET/PUT indicator-preferences mock 4 시나리오 | src + barrel | 0.3d |
| 0.4 | `src/lib/indicators/sma.test.ts` — happy/결측/경계/동일값/빈 배열 | 테스트 | 0.15d |
| 0.5 | `src/lib/indicators/rsi.test.ts` — Wilder 수식 검증 (known input → known output) + 결측 | 테스트 | 0.15d |
| 0.6 | `src/lib/indicators/macd.test.ts` — EMA + signal + histogram 경계 | 테스트 | 0.15d |
| 0.7 | `src/lib/indicators/aggregate.test.ts` — weekly/monthly 5일/20일 묶음 + 부분 주 처리 | 테스트 | 0.15d |
| 0.8 | `src/lib/indicators/index.test.ts` — barrel re-export sanity | 테스트 | 0.05d |
| **Gate 0** | ✅ 기존 indicators 5 개 단위 테스트 그린 + coverage 90%+ | 로컬 `npm test` 로그 | — |

**Gate 0 통과 조건**:
- [ ] `npm test` 로컬 그린, `npm run test:ci` 그린
- [ ] `src/lib/indicators/` coverage ≥ 90% lines/branches
- [ ] MSW 서버 setup/teardown 정상 (샘플 fetch 테스트 1 개 포함)
- [ ] 빌드 (`npm run build`) + 타입체크 (`npm run type-check`) 무회귀

### 체크포인트 1 — Bollinger Bands 추가 (2026-04-28, 1.25d)

**목표**: BB 지표 라인업 완성.

| # | 태스크 | 산출 | 예상 공수 |
|---|---|---|---:|
| 1.1 | `src/lib/indicators/bb.ts` — `(values, period, k)` → `{ upper, middle, lower }[]` O(n) 슬라이딩 | src | 0.4d |
| 1.2 | `src/lib/indicators/bb.test.ts` — period=20, k=2 known sample + 결측/경계/k 극단값 | 테스트 | 0.25d |
| 1.3 | `indicators/index.ts` barrel 에 bb 추가 | diff | 0.05d |
| 1.4 | `PriceAreaChart.tsx` BB overlay (3 LineSeries + 가능 시 band 채움) + 파라미터 연결 | diff | 0.3d |
| 1.5 | `IndicatorTogglePanel.tsx` 에 `bb` 토글 + 기본 OFF | diff | 0.1d |
| 1.6 | `useIndicatorPreferences` DEFAULT_PREFS 에 `bb: false` + `params.bb = { period: 20, k: 2 }` 임시 주입 (스키마 v2 완전 전환은 Cp 2) | diff | 0.1d |
| 1.7 | 수동 시각 검증 — `/stocks/005930` BB on/off | 스크린샷 | 0.05d |
| **Gate 1** | ✅ BB 토글 동작 + Vitest 그린 + 시각 OK | — | — |

### 체크포인트 2 — 파라미터 편집 UI + v2 스키마 마이그레이션 (2026-04-29 ~ 2026-05-01, 3.5d)

**목표**: 파라미터를 사용자가 직접 편집. localStorage v2 로 전환, v1 마이그레이션.

| # | 태스크 | 산출 | 예상 공수 |
|---|---|---|---:|
| 2.1 | `useIndicatorPreferences.ts` **v2 스키마 확장** + TypeScript 타입 (`IndicatorPreferences` + `Params`) | diff | 0.3d |
| 2.2 | v1 → v2 마이그레이션 함수 `migrateV1ToV2(raw)` + invalid schema fallback 확장 | diff | 0.3d |
| 2.3 | `src/lib/hooks/useIndicatorPreferences.test.ts` — migration / SSR fallback / multi-subscriber / invalid JSON / empty localStorage | 테스트 | 0.5d |
| 2.4 | `IndicatorParametersDrawer.tsx` — MA/RSI/MACD/BB 섹션 collapsible, 검증 (inline error + aria-invalid), '기본값 복원', '저장/취소' | 신규 | 1.0d |
| 2.5 | `IndicatorParametersDrawer.test.tsx` — 유효 입력 submit / 유효성 실패 시 저장 disabled / ESC close / focus trap / 기본값 복원 | 테스트 | 0.6d |
| 2.6 | `IndicatorTogglePanel.tsx` 에 '⚙ 지표 설정' 버튼 + Drawer open state 연결 | diff | 0.15d |
| 2.7 | `PriceAreaChart.tsx` 에 파라미터 반영 — 지표 재계산 로직이 params 의존 (기존 hardcode 제거), `setData()` 재계산 경로 확인 | diff | 0.4d |
| 2.8 | `stocks/[code]/page.tsx` params 전달 연결 | diff | 0.15d |
| 2.9 | 수동 검증: 파라미터 변경 → 저장 → 차트 반영 → 새로고침 후 유지 (localStorage only) | 체크리스트 | 0.1d |
| **Gate 2** | ✅ 편집 UI 동작 + v2 마이그레이션 테스트 그린 + 접근성 (focus trap/ESC/aria-modal) 수동 OK | — | — |

### 체크포인트 3 — DB 영속화 (2026-05-04 ~ 2026-05-06, 3d)

**목표**: 기기간 동기화. 싱글톤 id=1 패턴. 실패 시 localStorage fallback.

| # | 태스크 | 산출 | 예상 공수 |
|---|---|---|---:|
| 3.1 | Alembic `009_indicator_preferences.py` — NotificationPreference 포맷 상속, INSERT (1, '{}') ON CONFLICT | 마이그레이션 | 0.15d |
| 3.2 | `app/adapter/out/persistence/models/indicator_preferences.py` — SQLAlchemy 모델 (SINGLETON_ID=1, payload JSONB) | src | 0.15d |
| 3.3 | `app/adapter/out/persistence/repositories/indicator_preferences.py` — `get_or_create()`, `save()` (notification 선례) | src | 0.2d |
| 3.4 | `app/adapter/web/_schemas.py` — Pydantic `IndicatorPreferencesPayload` (toggles + params + 이중 검증) | diff | 0.3d |
| 3.5 | `app/adapter/web/routers/indicator_preferences.py` — GET/PUT + `require_admin_key` + rate limit | src | 0.3d |
| 3.6 | `app/main.py` 에 라우터 등록 | diff | 0.05d |
| 3.7 | `tests/test_indicator_preferences.py` — GET 기본/저장 후 조회/검증 실패/미인증 401 (testcontainers PG) | 테스트 | 0.5d |
| 3.8 | FE `src/app/api/admin/indicator-preferences/route.ts` — GET + PUT 릴레이 (notifications 선례 복사 + 수정) | src | 0.25d |
| 3.9 | FE `src/lib/preferences-sync.ts` — GET/PUT 래퍼 + timeout 5s + 실패 표준화 | src | 0.3d |
| 3.10 | `useIndicatorPreferences` DB 어댑터 통합 — mount pull / 변경 시 PUT / dirty flag / retry 로직 | diff | 0.5d |
| 3.11 | `useIndicatorPreferences.test.ts` 확장 — MSW 로 GET/PUT 200/400/500/네트워크 실패 시나리오 | 테스트 | 0.4d |
| 3.12 | 수동 검증: 2 기기 (MacBook Chrome + iPhone Safari) 저장/로드 일관성 | 시나리오 | 0.2d |
| **Gate 3** | ✅ BE 테스트 그린 + FE 테스트 그린 + 2 기기 시나리오 OK + `docker compose` 기동 실패 없음 | — | — |

### 체크포인트 4 — 접근성 회귀 + CI + 런칭 (2026-05-07 ~ 2026-05-08, 1.25d)

**목표**: A11y 유지, CI 동작, Lighthouse 증빙, v1.2 태그.

| # | 태스크 | 산출 | 예상 공수 |
|---|---|---|---:|
| 4.1 | `StockChartAccessibilityTable.tsx` BB 열(upper/middle/lower) 추가 (활성 시) | diff | 0.15d |
| 4.2 | OHLCV 툴팁에 BB 3 값 추가 (활성 시) | diff | 0.15d |
| 4.3 | `.github/workflows/ci.yml` FE vitest job 추가 (backend 와 병렬) + lcov artifact | diff | 0.2d |
| 4.4 | Lighthouse 재측정 — `/stocks/005930` Perf ≥ 80, A11y = 100 | scores doc prepend | 0.15d |
| 4.5 | 번들 diff 측정 — first-load JS 순증 ≤ 15KB gzipped | 측정 log | 0.1d |
| 4.6 | QA 체크리스트 — 토글 × 파라미터 조합 × 브라우저 3 × 디바이스 2 | `pipeline/artifacts/07-test-results/v1.2-qa.md` | 0.3d |
| 4.7 | 파라미터 변경 반영 <= 16ms 벤치마크 (performance.now() 500 포인트) | log | 0.1d |
| 4.8 | 문서 현행화 — README + HANDOFF 준비 | diff | 0.1d |
| **Gate 4 (v1.2 런칭)** | ✅ 모든 체크리스트 통과 + PR 생성 + v1.2 태그 | — | — |

**Gate 4 (v1.2 런칭 조건)**:
- [ ] Bollinger Bands 토글 on/off 정상, 파라미터 편집 반영
- [ ] 파라미터 편집 UI 모든 지표 (MA4/RSI/MACD/BB) 검증 동작
- [ ] localStorage v1 → v2 자동 마이그레이션 — 기존 사용자 토글 유지
- [ ] DB 저장 — 2 기기 시나리오 일관성 OK
- [ ] BE 테스트 그린 (pytest + testcontainers) + FE 테스트 그린 (vitest)
- [ ] CI FE job 그린 (PR 머지 차단 활성)
- [ ] Vitest coverage — indicators ≥ 90%, useIndicatorPreferences = 100%
- [ ] Lighthouse `/stocks/005930`: Perf ≥ 80, A11y = 100
- [ ] first-load JS 순증 ≤ 15KB gzipped
- [ ] A11y 회귀 없음 — 편집 UI focus trap + ESC + aria-modal 동작
- [ ] 시그널 마커 회귀 없음

## 크리티컬 패스

```
Cp 0 (Vitest 하네스)
  ↓
Cp 1 (BB 유틸 + overlay) ─┐
                          ↓
Cp 2 (편집 UI + v2 스키마 + v1→v2 마이그레이션)
                          ↓
Cp 3 (DB 영속화 BE + FE 어댑터)
                          ↓
Cp 4 (접근성 + CI + Lighthouse + 런칭)
```

**Cp 0 PoC 실패 시 대안**:
- Vitest 호환 이슈 확인 → Jest 로 백업? — 비추천 (Next 16/React 19 는 Vitest 가 더 잘 맞고 MSW/ESM 호환 좋음)
- jsdom 대신 happy-dom 시도 (Vitest 2 기본 옵션) — 0.1d 추가

## 의존성 / 선행 조건

| 선행 조건 | 상태 |
|---|---|
| v1.1 차트 기반 (Candle + MA + Volume + RSI + MACD + 토글 + localStorage) | ✅ 완료 (2026-04-23) |
| lightweight-charts v5 `addPane` / `setHeight` | ✅ 검증됨 |
| `require_admin_key` 어드민 인증 체계 | ✅ `_deps.py:113-124` |
| NotificationPreference 싱글톤 패턴 선례 | ✅ `migrations/versions/002` |
| Next.js Route Handler 서버 릴레이 패턴 | ✅ `src/frontend/src/app/api/admin/notifications/preferences/route.ts` |
| `useIndicatorPreferences` snapshot 캐싱 | ✅ v1.1 hotfix `669d9e8` |
| Vitest 2.x / @testing-library/react 16 / jsdom 25 React 19 호환 | ⏳ Cp 0 PoC (30 분) 에서 확정 |

## 커뮤니케이션 / 승인 게이트

- **Gate 0 완료 → 진행 자동** (하네스 동작 확인만)
- **Gate 1 완료 → 시각 확인 승인**: `/stocks/005930` BB 토글 스크린샷
- **Gate 2 완료 → 편집 UX 승인**: 파라미터 편집 → 저장 → 차트 반영 데모 (스크린레코딩 or 시연)
- **Gate 3 완료 → 동기화 시연 승인**: 2 기기 시나리오 스크린샷 2 장
- **Gate 4 완료 → v1.2 런칭 승인**: 전체 시나리오 + Lighthouse 증빙 + 커버리지 리포트 + v1.2 태그 생성

## 기술 부채 / 비즈니스 가치 균형

- **Vitest 도입의 장기 가치**: v1.2 이후 모든 FE 변경의 회귀 비용을 수동 확인 → CI 자동으로 이전. v1.3 알림 확장 + v1.4 drawing 에서 누적 가치 발현.
- **싱글톤 id=1 vs user_id**: 현재 싱글 오퍼레이터 모델에서는 싱글톤이 정합. 멀티 유저 요구 발생 시 `ALTER TABLE ADD COLUMN user_id` + 데이터 마이그레이션으로 확장 가능. 기술 부채라기보다 **상황에 맞는 설계**.
- **저장 버튼 방식 편집 UX**: 프리뷰 방식 포기로 발생하는 UX 마찰 — v1.3 에서 "미리보기 토글" 옵션 검토.

## v1.1 패턴 상속 (확정)

- 한국어 커밋 메시지 + Co-Authored-By
- `git push` 는 명시 요청 시에만
- 체크포인트 단위 커밋 (4 체크포인트)
- 매 체크포인트 Lighthouse 재측정은 Cp 1 / Cp 4 에서만 (시간 예산)
- pre-commit hook `--no-verify` 금지, heredoc 오탐 시 `-F <file>` 우회
- 코드 주석 최소 (Why 가 중요한 부분만)
