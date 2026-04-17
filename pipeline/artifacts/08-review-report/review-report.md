---
stage: 08-review-report
sprint: Sprint 4 전체 완료 시점 통합 리뷰
reviewer: 08-backend (review mode)
commit: 871ff57 (master)
date: 2026-04-17
---

# SIGNAL 통합 코드 리뷰 리포트

## Executive Summary

### Strengths
- Hexagonal Architecture 경계가 명확함. `adapter/in/web` → `application/port/in` → `application/service` → `application/port/out` 흐름이 일관되고, 도메인 모델이 기술 세부사항에 오염되지 않았다.
- Sprint 3까지 축적된 리뷰 피드백이 체계적으로 반영됨(N+1 제거, CORS, 3년 제한, ErrorBoundary, 반응형 등 9건). `current-state.json` → `resolved_issues`와 실제 소스가 일치.
- 전역 예외 처리(`GlobalExceptionHandler`)가 sealed `DomainError` 패턴 매칭 + Bean Validation + 메시지 파싱 오류까지 포괄.
- `ApiKeyValidator`는 `MessageDigest.isEqual`로 타이밍 공격 방어, 빈 키는 거부. 양호.
- Signal 탐지 로직이 메모리 벌크 처리로 전환되어 스케일링 여지가 확보됨(종목당 7쿼리 × 2500 → 전체 7쿼리).
- 프론트엔드 접근성(aria-pressed, aria-current, focus-visible, sr-only, ErrorBoundary resetKeys)이 고르게 적용됨.

### Concerns
- **관리자 API Key가 프론트엔드 번들에 노출된다(`NEXT_PUBLIC_ADMIN_API_KEY`).** 프로덕션 배포 시 관리자 권한이 사실상 공개됨. Phase 5 전 **반드시 차단**.
- `MarketDataCollectionService`에 **자기호출(Self-Invocation) 트랜잭션 누락**과 **데드 코드**가 존재. 배치 핵심 경로라 침묵 실패 위험.
- 데이터 수집 저장 시 **고유 제약 중복 체크가 빠져 있어** 재실행/수동 재수집 시 `DataIntegrityViolationException` 가능.
- 프론트엔드가 전체적으로 TanStack Query 컨벤션을 따르지 않고 `useEffect + fetch` 패턴 일색. Phase 5 블로커는 아니나 v1.1 기술부채로 등록 권장.

### Blocker-level
1. **CRITICAL (배포 블로커):** `NEXT_PUBLIC_ADMIN_API_KEY` 클라이언트 노출 — Phase 5 Ship 전 반드시 해결.
2. **HIGH (Phase 5 조건부 통과):** `MarketDataCollectionService.persistAll()` 트랜잭션 우회 + dead code + upsert 부재. 배포 후 첫 배치 재실행 시점에 재발성 결함으로 표출될 수 있음.

---

## Backend findings

### CRITICAL

#### [B-C1] 관리자 API Key 클라이언트 노출
- 위치: `src/frontend/src/app/settings/page.tsx:24`, `src/frontend/src/lib/api/client.ts:47-59`
- 내용: `NEXT_PUBLIC_ADMIN_API_KEY`로 읽는 모든 값은 Next.js 빌드 시 **자바스크립트 번들에 하드코딩**되어 브라우저로 전송된다. `PUT /api/notifications/preferences`, `POST /api/batch/collect`, `POST /api/signals/detect`, `POST /api/backtest/run`이 모두 이 키로 보호되므로, 배포 즉시 모든 관리자 기능이 익명 사용자에게 공개된다.
- 조치: 옵션 (택1)
  1. 관리자 기능을 **서버 컴포넌트 + Server Action**으로 이전하고 키는 서버 전용 env(`ADMIN_API_KEY`, 접두어 없음)로 보관.
  2. `/settings`를 별도 관리 도메인으로 분리하고 BFF 레이어에서 주입.
  3. v1에서는 `/settings` 쓰기 기능을 **직접 백엔드 CLI/cron으로 운용**하고 프론트는 읽기 전용으로 둔다(가장 단순).

### HIGH

#### [B-H1] `MarketDataCollectionService.persistAll` 자기호출 트랜잭션 무효화
- 위치: `src/backend/src/main/java/com/ted/signal/application/service/MarketDataCollectionService.java:32-55, 57-62`
- 내용: `collectAll()`이 같은 빈의 `persistAll()`을 직접 호출한다. Spring AOP 프록시는 **외부 호출에만 인터셉터가 적용**되므로 `persistAll`의 `@Transactional`은 **작동하지 않는다**. 또한 가시성이 `protected`라 프록시가 override하지도 못한다.
  실행 중 실패 시 **부분 커밋**이 발생해 주가는 저장되고 대차잔고는 실패하는 식의 일관성 깨짐이 가능.
- 조치:
  - `collectAll`에 `@Transactional`을 직접 붙이거나(다만 HTTP 호출이 트랜잭션 안으로 들어오므로 비권장),
  - `persistAll`을 **별도 `MarketDataPersistService`로 분리**하여 public `@Transactional` 메서드로 호출 (권장).

#### [B-H2] `MarketDataCollectionService.persistAll` 데드 코드 + 의미 불명 쿼리
- 위치: 동 파일 84–88행
```java
var existingPriceIds = stockPriceRepository
        .findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
                null, date, date).stream()
        .map(sp -> sp.getStock().getId())
        .collect(Collectors.toSet());
```
- 내용: `Long stockId`에 `null`을 넘겨 derived query가 `WHERE stock_id = null`로 번역되므로 항상 빈 리스트를 리턴한다. 게다가 `existingPriceIds` 변수는 **이후 어디에도 사용되지 않는다**. 주석 `// null stockId 사용 불가 → 별도 쿼리 필요`는 리팩터링 미완료 흔적.
- 조치: 해당 블록 삭제 후, 중복 방지가 필요하면 `findAllByTradingDate(date)` 결과로 set을 만들고 upsert 분기 처리.

#### [B-H3] 재실행 시 유니크 제약 충돌 가능
- 위치: `MarketDataCollectionService.persistAll` 전체 흐름
- 내용: `StockPrice`, `ShortSelling`, `LendingBalance`가 `(stock_id, trading_date)` 유일성 제약을 갖는다고 가정할 때(도메인 규칙상 자연스러움), 운영자가 수동 재수집(`POST /api/batch/collect`)을 동일 일자에 실행하면 `saveAll`이 INSERT만 수행해 제약 위반으로 전체 배치가 실패한다. `Sprint 4 task 1-3` 리뷰에서 "N+1 제거"에만 집중되어 이 경로는 수정되지 않음.
- 조치: 저장 전 `existsByStockIdAndTradingDate` 대신 `findAllByTradingDate(date)` 1회 조회로 key set을 만들고, 존재하는 레코드는 스킵 또는 업데이트. `LendingBalance`는 changeRate 계산이 전 영업일 기반이라 update 쪽이 자연스러움.

### MEDIUM

#### [B-M1] `BacktestController` 검증 실패 시 응답 형식 불일치
- 위치: `src/backend/src/main/java/com/ted/signal/adapter/in/web/BacktestController.java:54-62`
- 내용: `ResponseEntity.badRequest().build()`로 비어있는 400을 반환. `GlobalExceptionHandler`가 반환하는 `{status, message, timestamp}` 스키마와 **형식이 다르다**. 프론트 `fetchApi`가 `body.message`를 꺼낼 때 `undefined`가 되어 "API Error: 400"만 표시.
- 조치: `DomainException(new InvalidParameter("dateRange", "..."))`로 바꾸고 `GlobalExceptionHandler`가 처리하도록 위임.

#### [B-M2] `SignalDetectionService.detectAll` 트랜잭션 범위 과다
- 위치: `src/backend/.../application/service/SignalDetectionService.java:37-118`
- 내용: `@Transactional`(기본 readWrite)이 대규모 in-memory 계산 전체를 감싸 트랜잭션과 DB 커넥션을 오래 점유. 쓰기는 마지막 `saveAll` 한 번뿐이므로 조회 Phase와 쓰기 Phase를 분리 가능.
- 조치: 조회 섹션을 별도 `@Transactional(readOnly=true)` 메서드로 분리하고, 쓰기 섹션만 `@Transactional`.

#### [B-M3] `signal.detail` Map 생성 시 null 처리 일관성
- 위치: `SignalDetectionService.java:134-138, 175-179, 210-219`
- 내용: `Map.of`는 null 금지. `detectRapidDecline`은 `lb.getChangeRate()`가 null 아닐 때만 호출되므로 안전하나, 호출부에서의 nullability 계약이 주석으로만 명시되어 있어 향후 리팩터링 시 NPE 위험. Optional 래핑 또는 `Objects.requireNonNull` 가드를 추천.

#### [B-M4] `TelegramClient` 오류 로깅이 스택 없이 message만 기록
- 위치: `src/backend/.../adapter/out/external/TelegramClient.java:62-65`
- 내용: `log.error("텔레그램 발송 실패: {}", e.getMessage())`는 스택트레이스가 사라진다. 텔레그램 API가 429/401을 낼 때 원인 추적이 어렵다.
- 조치: `log.error("텔레그램 발송 실패", e)`로 변경. 또한 429/5xx 구분하여 재시도 정책 분기 고려(v1.1).

#### [B-M5] `KrxClient` 마지막 호출 이후에도 2초 sleep
- 위치: `src/backend/.../adapter/out/external/KrxClient.java:136`
- 내용: 매 요청 후 무조건 `Thread.sleep(2000)`. 3회 호출 시 최소 6초 누적 지연. 호출자가 순차 호출한다는 보장이 이미 있으므로 "호출 전 rate limit"로 전환하면 마지막 지연 제거 가능.
- 조치: `Instant lastCallAt` 필드 기반 토큰 버킷 스타일로 이관(사소함, v1.1).

### LOW

#### [B-L1] 기존 LOW 이슈 재확인
- `known_issues`의 세 항목(`korean-holidays`, `cors-test-scope`, `lockfile-duplicate`) 모두 동작/보안에 영향 없음. 현재 상태 그대로 v1.1 백로그 유지 적절.

#### [B-L2] `WebConfig` CORS — 로컬 개발 전용 설정
- 위치: `src/backend/.../config/WebConfig.java:13`
- 내용: `allowedOriginPatterns("http://localhost:3000")` 하드코딩. 프로덕션 도메인에 맞춰 환경변수화 필요. Phase 5 DevOps에서 처리하면 됨.

---

## Frontend findings

### HIGH

#### [F-H1] 관리자 API Key 클라이언트 번들 노출 (교차 참조: B-C1)
- 위치: `src/frontend/src/app/settings/page.tsx:24`
- 내용: 위 B-C1과 동일 이슈. 프론트 코드 관점에서 고치려면 저장 버튼 핸들러에서 직접 백엔드 호출을 하지 않고, 자체 API 라우트(Next Route Handler)를 통해 서버사이드 env로 릴레이하는 것이 최소 수정.

### MEDIUM

#### [F-M1] `useEffect + fetch` 패턴 — TanStack Query 컨벤션 위배
- 위치: `src/frontend/src/app/page.tsx:24-34`, `src/frontend/src/app/backtest/page.tsx:39-43`, `src/frontend/src/app/stocks/[code]/page.tsx:51-66`, `src/frontend/src/app/settings/page.tsx:52-70`
- 내용: `CLAUDE.md`에 "상태관리: TanStack Query (서버) + Zustand (클라이언트)" 명시. 현 구현은 4개 페이지 모두 수동 `useState + useEffect + fetch`로 처리되어
  - 캐시/재검증 없음 (새로고침마다 전량 재요청)
  - AbortController 없음 → 빠른 재네비게이션 시 stale state 경쟁
  - 에러/로딩 경계 중복 코드
- 조치: Phase 5 전 블로커는 아님. v1.1에 `@tanstack/react-query` 도입 태스크로 등록.

#### [F-M2] 오늘 날짜 렌더 — 타임존 불일치
- 위치: `src/frontend/src/app/page.tsx:60`
- 내용: `new Date().toISOString().split('T')[0]`은 UTC 기준이라 한국 자정~09:00 사이 전일 날짜가 표시된다. 백엔드는 `Asia/Seoul`로 고정(`application.yml:33`).
- 조치: `Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())` 또는 dayjs/date-fns-tz로 고정.

### LOW

#### [F-L1] 프론트엔드 테스트 0건
- `current-state.json` → `test_coverage.frontend.total_tests: 0`, 자체 E2E/컴포넌트 테스트 부재. Phase 4 QA 스프린트 또는 Phase 5 이후 추가 권장. 빌드/lint/tsc 세 가지는 통과 상태.

#### [F-L2] `signalId`가 `signalId` 하나로 key 사용되지만 타입이 `number` — 서버 응답 직렬화에 따른 overflow 확인 필요
- 위치: `src/frontend/src/types/signal.ts:5`
- 내용: Long id가 2^53을 넘으면 JS number 정밀도 손실. 현재 PK `BIGSERIAL`이라 수십만 건 범위에서는 무해. 장기 위험 항목.

#### [F-L3] `AuroraBackground`가 `'use client'` 없이 default export
- 위치: `src/frontend/src/components/ui/AuroraBackground.tsx`
- 내용: 순수 JSX라 서버 컴포넌트로 처리된다. 문제는 없으나, 자매 컴포넌트(`Magnetic`, `CountUp`)와 네이밍 일관성 차원에서 의도 명시하면 유지보수 편함. (선택)

---

## Resolved since last sprint

Sprint 3 → Sprint 4 전체 완료 시점까지 해결된 9건을 소스에서 재확인함:

| ID | 커밋 | 검증 방식 | 상태 |
|---|---|---|---|
| `N+1-signal-detection` | 33b6cf1 | `SignalDetectionService:43-80` 벌크 로드 확인 | 해결 |
| `N+1-daily-summary` | 33b6cf1 | `SignalRepository.findBySignalDateWithStockOrderByScoreDesc` JOIN FETCH | 해결 |
| `backtest-unbounded` | 33b6cf1 | `BacktestController:60`, `BacktestEngineService:59` IN 쿼리 | 해결 |
| `cors-api-key` | 33b6cf1 | `WebConfig:15` X-API-Key 추가 | 해결 |
| `mobile-responsive` | 9436772 | `page.tsx:52, 65`, `backtest/page.tsx:101-135`(desktop)/138-175(mobile) | 해결 |
| `error-boundary` | 9436772 | `ErrorBoundary.tsx` resetKeys + componentDidUpdate | 해결 |
| `react-hooks-set-state-in-effect` | 9436772 | `stocks/[code]/page.tsx:45-49`, `NavHeader:19-22` render-time 리셋 | 해결 |
| `notification-settings-missing` | task 4 | `NotificationPreferenceController`, `NotificationPreferenceService`, `/settings` 페이지, Telegram 4채널 필터 | 해결 |
| `prototype-canonical-decision` | D-4.10 | `AuroraBackground`, `Magnetic`, `CountUp` 컴포넌트 분해 완료 | 해결 |

---

## Remaining LOW from current-state

| ID | 현재 평가 | 권고 |
|---|---|---|
| `korean-holidays` | `MarketDataCollectionService.findPreviousTradingDate` 주석으로 TODO 명시됨. 주말만 스킵. 설날/추석 연휴 이후 첫 영업일 `changeRate` 계산이 빈 값 → 전 영업일이 공휴일일 때 `prevBalanceMap`이 비어 `changeRate=0`이 됨 | v1.1에 공휴일 캘린더 추가. 현재는 관측 가능한 버그이므로 운영 FAQ에 명시 권장 |
| `cors-test-scope` | `CorsConfigTest`가 전체 SpringBootTest 컨텍스트 로드 — CI 시간 +3~5s. 기능 영향 없음 | v1.1에 `@WebMvcTest(controllers=...)` 분리 |
| `lockfile-duplicate` | Next.js 경고만 출력, 빌드/런타임 영향 없음 | 루트의 `~/package-lock.json` 삭제 또는 `turbopack.root` 명시 |

---

## Verdict

**CONDITIONAL PASS** — Phase 5 Ship 진행 가능하되 아래 조건 충족을 전제로 한다.

### 차단 조건 (Phase 5 진입 전 필수)
1. **[B-C1 / F-H1]** `NEXT_PUBLIC_ADMIN_API_KEY` 제거. 관리자 API 호출을 Next Route Handler 또는 Server Action으로 릴레이하거나, v1에서 `/settings` 쓰기 기능을 백엔드 CLI로 임시 운용.
2. **[B-H1]** `MarketDataCollectionService.persistAll` 트랜잭션 경계 수정(별도 서비스 분리).
3. **[B-H2]** `persistAll` 데드 코드 블록 삭제.
4. **[B-H3]** 재실행 시 중복 방지 로직 추가 또는 `ON CONFLICT DO UPDATE` 적용(Native Query로).

### 허용 조건 (Phase 5 이후 7일 내 핫픽스 가능)
- [B-M1] BacktestController 검증 응답 표준화
- [B-M2] 트랜잭션 범위 축소
- [B-M4] Telegram 스택트레이스 로깅
- [F-M2] 타임존 표시 수정

### Rationale
차단 이슈 4건은 모두 배포 직후 첫 번째 운영 주기에서 표출되는 결함이다. 특히 B-C1은 **보안 사고 수준**이며, B-H1~H3은 운영자가 **수동 재수집을 시도하는 순간 배치가 전부 실패**하는 잠재적 장애. 반대로 MEDIUM/LOW는 UX/관측성 개선 수준이라 Sprint 5에서 다뤄도 무방.

---

## Recommendations (ordered)

1. **관리자 API Key를 서버 전용으로 이전** — Server Action or Next Route Handler. 블로커 해제의 가장 작은 변경.
2. **`MarketDataPersistService`를 새 빈으로 분리** — `collectAll`은 HTTP 수집만, `persistAll`은 public `@Transactional` 메서드로. 자기호출 문제 해결 + SRP 준수.
3. **`persistAll` dead block 제거** — 단순 삭제로 가독성/오판 위험 둘 다 해소.
4. **배치 멱등성 확보** — 날짜별 기존 레코드 셋을 1회 조회 → exists check → insert skip 또는 update. 공휴일 버그도 부분 완화.
5. **BacktestController/BatchController 검증 로직을 `DomainException`으로 일관화** — GlobalExceptionHandler 응답 스키마 통일.
6. **TanStack Query 도입을 v1.1 첫 번째 태스크로 등록** — 4개 페이지 리팩터. 현 프론트는 복구/재시도 UX가 단조롭다.
7. **Telegram 재시도 정책** — 429 exponential backoff, 5xx 3회 재시도 후 포기. `sendBatchFailure` 호출 시점까지의 silence 기간 단축.
8. **한국 공휴일 캘린더** — `Holidays` 도메인 모듈 분리 가능성 있음. KRX 영업일 API 또는 로컬 yaml 두 옵션.
9. **프론트 컴포넌트 테스트 도입** — `/settings`와 `SignalCard`부터. Playwright E2E는 Phase 5 Ship 후로 미뤄도 됨.
10. **CorsConfigTest를 `@WebMvcTest`로 전환** — CI 시간 단축.

---

## Appendix: Severity Count

| Severity | Backend | Frontend | Total |
|---|---:|---:|---:|
| CRITICAL | 1 | 0 | **1** |
| HIGH | 3 | 1 | **4** (공유 1건 포함) |
| MEDIUM | 5 | 2 | **7** |
| LOW | 2 | 3 | **5** |
| 합계 | **11** | **6** | **17** |

※ B-C1과 F-H1은 동일 이슈로 각 프론트/백엔드 관점에서 별도 기술됨. 실제 고유 이슈 수 16건.
