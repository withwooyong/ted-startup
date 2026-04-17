# Session Handoff

> Last updated: 2026-04-17 (세션 종료, Sprint 4 완결)
> Branch: `master`
> Latest commit: `8d003ba` - Sprint 4 Task 4: 알림 설정 페이지 + 리뷰 반영(HIGH 4 + MEDIUM 9)
> 원격 동기화: ⏳ `origin/master`보다 1커밋 앞섬 (푸시 대기)
> 커밋 상태: ✅ 전체 커밋 완료, 작업 트리 clean

## Current Status

**Sprint 4 전체 완료 → Human Approval #3 대기**. 이번 세션에서 Task 4(알림 설정 페이지)와 프로토타입 합류본 결정까지 마무리했고, 3종 병렬 코드리뷰(java/typescript/security)의 HIGH 4 + MEDIUM 9 이슈를 전량 반영했다. Phase 5 Ship 단계 진입 가능.

## Completed This Session

| # | Task | Commit | 주요 변경 |
|---|------|--------|-----------|
| 1 | 프로토타입 합류본 결정 (D-4.10) | `8d003ba` | `index-ambient.html`(1332줄, aurora/skeleton/tilt/magnetic/count 5종 누적) → `prototype/index.html`로 복사 |
| 2 | Sprint 4 Task 4: 알림 설정 (D-4.11) | `8d003ba` | 백엔드 9파일 신규 + 2파일 변경, 프론트 3파일 신규/변경. `NotificationPreference` 싱글 로우 엔티티 + `GET/PUT /api/notifications/preferences` + Telegram 4채널 필터 + `/settings` 페이지 |
| 3 | 3종 리뷰 반영 (D-4.12) | `8d003ba` | java-reviewer/typescript-reviewer/security-reviewer 병렬 → BLOCK(HIGH 4). 전량 수정 후 PASS. `ApiKeyValidator` 추출로 3개 컨트롤러 중복 제거 포함 |
| 4 | 문서 현행화 | `8d003ba` | CHANGELOG prepend, decision-registry D-4.10/11/12 추가(33→36건), summary/state/HANDOFF/sprint-4-plan 갱신 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | `origin/master` 푸시 | 대기 | 사용자 명시 요청 시 실행 (글로벌 규칙) |
| 2 | Human Approval #3 | 대기 | Sprint 4 전체 완료, Phase 5 Ship 진입 승인 |
| 3 | 프로토타입 효과 → Next.js 이식 | 대기 | ambient 5종 효과 → `AuroraBackground` / `useTilt` / `useCountUp` / `MagneticButton` 컴포넌트 분해 (반나절~1일) |
| 4 | Phase 5 Ship (devops + analytics) | 대기 | `/deploy` 슬래시 커맨드로 진입 가능 |
| 5 | CorsConfigTest 스코프 축소 | LOW | `@SpringBootTest` → `@WebMvcTest` 분리 가능 |
| 6 | `turbopack.root` 설정 | LOW | lockfile 중복 경고 제거 |
| 7 | Flyway 도입 | v1.1 | 현재 `ddl-auto: create-drop` 의존, 프로덕션 전환 시 필수 |
| 8 | 한국 공휴일 캘린더 | v1.1 | 현재 주말만 스킵 |
| 9 | `NOTIFICATION_CHANNEL_LABELS` Exclude 패턴 | LOW | 채널 추가 시 컴파일 에러 강제 가능 (TS 리뷰 LOW) |
| 10 | `catch (err: unknown)` narrowing 통일 | LOW | Promise rejection 기본 타입 (TS 리뷰 LOW) |

## Key Decisions Made

**D-4.10 프로토타입 합류본 = ambient (2026-04-17)**
- `index-ambient.html`(1332줄, 61KB)을 최종 합류본으로 채택, `prototype/index.html`을 동일 내용으로 덮어써 캐노니컬 엔트리 통일
- 근거: skeleton/tilt/tilt-shine/magnetic/data-count/aurora 5종 효과가 누적 탑재된 유일한 파일. UI/UX 화려도 극대화가 프로토타입 목적에 부합
- 4종 비교본(before-skeleton/tilt-magnetic/counter/ambient)은 단계별 레퍼런스로 보존

**D-4.11 알림 설정 = 싱글 로우(id=1) 패턴**
- `NotificationPreference`는 id=1 고정 싱글 로우. 4채널 플래그(daily/urgent/batch/weekly) + `minScore`(0-100) + `signalTypes` JSONB
- 근거: MVP 1인 운영, 사용자/인증 개념 없음. Sprint 4 plan의 `channel` 구분보다 시나리오별 on/off가 UX에 더 정확
- 확장 경로: user 테이블 도입 시 `user_id FK` + unique constraint로 다중 사용자 전환 가능
- 첫 GET 호출 시 기본값 row 자동 생성 (`loadOrCreate`) → 초기화 스크립트 불필요

**D-4.12 Task 4 리뷰 반영 (HIGH 4 + MEDIUM 9)**
- HIGH-1 **PUT 인증 추가**: 기존 `X-API-Key` 패턴 재사용. `ApiKeyValidator` 컴포넌트로 추출해 Backtest/SignalDetection/Batch 3개 컨트롤러 중복 제거
- HIGH-2 **`loadOrCreate` race condition**: `DataIntegrityViolationException` catch + 재조회. 싱글톤 row 지연 생성의 동시 최초 요청 경합을 멱등 처리
- HIGH-3 **`IllegalArgumentException` 전역 캐치 제거**: JDK 내부 오류가 400으로 마스킹되는 위험 해소. 검증은 `DomainException(DomainError.InvalidParameter)` 경로로 통일
- HIGH-4 **Hexagonal 경계 교정**: `sanitizeSignalTypes` 검증을 Controller → `UpdateCommand` compact constructor로 이동. record 생성 자체가 검증 계기 → 어떤 경로로 생성해도 도메인 규칙 강제
- MEDIUM: `@Size(min=1, max=3)` DoS 방지, 에러 메시지 사용자 입력 반사 제거(고정 문자열), `getPreferenceForFiltering` 트랜잭션 명시, 도메인 `update()` 자체 검증(이중 안전망), `sendBatchFailure` 로그 `errorMessage` 제거
- 프론트 MEDIUM: `aria-valuemin/max/now` 중복 제거, `cache: 'no-store'` spread 후위 재명시(caller override 방어), `friendlyError()` 매핑 함수로 에러 직접 노출 제거
- 테스트: 5개 → 9개 확장. 알 수 없는 타입이 응답에 반사되지 않는지 검증 포함

**기존 유지**: D-0.1 Opus 4.7 단일 운영, D-4.1~D-4.9 (Sprint 4 Task 1-3 + Task 5-6 + 프로토타입 보안 패치)

## Known Issues

**해소됨 (이번 세션)**
- ~~알림 설정 페이지 없음~~ → Task 4 전체 구현 (`8d003ba`)
- ~~프로토타입 5종 합류본 미결정~~ → D-4.10 ambient 확정 (`8d003ba`)
- ~~PUT 엔드포인트 인증 부재~~ → `X-API-Key` 적용 (`8d003ba`)
- ~~`loadOrCreate` race condition~~ → `DataIntegrityViolationException` recover (`8d003ba`)
- ~~`IllegalArgumentException` 전역 캐치 남용~~ → 제거, `DomainException` 경로로 통일 (`8d003ba`)
- ~~Controller의 Hexagonal 경계 위반~~ → 검증을 `UpdateCommand` compact constructor로 이동 (`8d003ba`)

**v1.1 / LOW 이관**
- 한국 공휴일 미처리 (현재 주말만 스킵)
- Flyway 미도입 (현재 `ddl-auto: create-drop` 의존 — 프로덕션 전환 시 V1/V2 수동 적용 필요)
- CorsConfigTest 전체 컨텍스트 로드 (`@WebMvcTest` 분리 가능)
- lockfile 중복 경고 (`turbopack.root` 설정 권장)
- `NOTIFICATION_CHANNEL_LABELS` `Exclude` 패턴 (새 채널 추가 시 자동 감지)
- `catch (err: unknown)` narrowing (현재 `Error` 단언 위치 2곳)

## Context for Next Session

- **사용자 원래 의도**: Sprint 4에서 N+1/CORS/알림 설정/모바일 반응형 4.5일 예정 → **Task 1-6 전체 + 리뷰 반영까지 완료**. 실제 총 분량은 3~4일 × 여러 세션.
- **이번 세션 흐름**:
  1. 시작 시점: Task 4만 남음 + 프로토타입 5종 합류본 미결정
  2. 프로토타입 선정 → ambient 채택 (D-4.10)
  3. Task 4 구현 (백엔드 9신규 + 프론트 3신규/변경, 5개 테스트)
  4. `/ted-run` 순서대로 진행 요청 → 3종 리뷰어 병렬 실행
  5. BLOCK 판정 (HIGH 4) → 전량 수정 + 테스트 확장 (5 → 9개)
  6. 재검증: 백엔드 29/29 통과, 프론트 clean
  7. 커밋 (`8d003ba`) + 핸드오프
- **다음 세션 착수 순서 권장**:
  1. **푸시** (명시 요청 필요): `git push origin master` (사용자 글로벌 규칙)
  2. **Human Approval #3**: Sprint 4 완료 검토 후 Phase 5 진입 승인
  3. **Phase 5 Ship**: `/deploy` — 12-devops(배포 파이프라인) + 13-analytics(성과 분석)
  4. 또는 **ambient 효과 Next.js 이식** (프로토타입 → 실 프론트 반영, 반나절~1일)
- **모델 운용**: Opus 4.7 단일 운영 — 리밋 시 Sonnet 4.6 자동 fallback (statusline 확인)
- **텔레그램 봇**: @bearchwatch_alarm_bot, BEARWATCH (`chat_id: -1003817432997`)
- **기술 스택**: Spring Boot 3.5.0 / Java 21 / Next.js 16.2.4 / React 19.2.4 / Tailwind 4 / Recharts 3.8.1 / PostgreSQL 16
- **⚠ 프론트엔드 주의**: `src/frontend/AGENTS.md` — "This is NOT the Next.js you know". Next 16 신규 ESLint 룰 `react-hooks/set-state-in-effect` 준수
- **실행 명령어**:
  - 프로토타입: `open prototype/index.html` (ambient 합류본)
  - DB: `docker compose up -d`
  - Backend: `DB_USERNAME=signal DB_PASSWORD=signal ADMIN_API_KEY=test TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./gradlew bootRun --args='--spring.profiles.active=local'`
  - Frontend: `NEXT_PUBLIC_ADMIN_API_KEY=test cd src/frontend && npm run dev`
    - ⚠ Task 4 이후 `/settings` 저장에 `NEXT_PUBLIC_ADMIN_API_KEY` 필수
  - 백엔드 테스트: `cd src/backend && ./gradlew test` (29개)
  - 프론트 검증: `cd src/frontend && npx tsc --noEmit && npx eslint src/ && npm run build`

## Task 4 주요 신규 파일 (8d003ba)

**백엔드 신규 9개**
- `adapter/in/web/ApiKeyValidator.java` — 관리자 API Key 검증 컴포넌트 (3개 컨트롤러 공유)
- `adapter/in/web/NotificationPreferenceController.java` — GET(공개) / PUT(X-API-Key)
- `application/port/in/GetNotificationPreferenceUseCase.java` + `NotificationPreferenceView` record
- `application/port/in/UpdateNotificationPreferenceUseCase.java` + `UpdateCommand` (compact constructor 검증)
- `application/port/out/NotificationPreferenceRepository.java`
- `application/service/NotificationPreferenceService.java` — `loadOrCreate`(race handling), `getPreferenceForFiltering`(읽기 전용)
- `domain/model/NotificationPreference.java` — 싱글 로우(id=1) 엔티티, 도메인 `update()` 자체 검증
- `db/migration/V2__notification_preference.sql` — 참고용 DDL
- `test/.../NotificationApiIntegrationTest.java` — 9개 통합 테스트

**백엔드 변경 5개**
- `BacktestController`/`SignalDetectionController`/`BatchController` — `ApiKeyValidator` 주입으로 `@Value` 중복 제거
- `TelegramNotificationService` — 4채널 preference 필터
- `GlobalExceptionHandler` — `@Valid @RequestBody` 400 매핑, `IllegalArgumentException` 핸들러 제거

**프론트 신규 2 + 변경 2**
- `types/notification.ts` — `NotificationPreference` 타입 + 채널 라벨
- `app/settings/page.tsx` — 스위치 토글(aria-checked) + aria-pressed 필터 + range 슬라이더 + `friendlyError()`
- `lib/api/client.ts` — `RequestInit` 옵션 + `X-API-Key` 헤더 + status 보존 Error
- `NavHeader.tsx` — `/settings` 링크 추가

## 핵심 참조 경로

- 사용설명서: `docs/PIPELINE-GUIDE.md`
- Sprint 4 계획: `docs/sprint-4-plan.md` (Task 1-6 전체 완료)
- 마스터 설계서: `docs/design/ai-agent-team-master.md`
- 파이프라인 상태: `pipeline/state/current-state.json` (Sprint 4 completed)
- 의사결정: `pipeline/decisions/decision-registry.md` (36건 누적, D-4.10~12 신규)
- Build 요약: `pipeline/artifacts/06-code/summary.md` (Task 4 섹션 + 리뷰 반영)
- 프로토타입: `prototype/index.html` (ambient 합류본, 1332줄)

## Files Modified This Session

```
커밋 통계 (8d003ba: 25 files, +1620/-184)

신규 11개:
 src/backend/.../ApiKeyValidator.java                            28 lines
 src/backend/.../NotificationPreferenceController.java           69 lines
 src/backend/.../GetNotificationPreferenceUseCase.java           19 lines
 src/backend/.../UpdateNotificationPreferenceUseCase.java        57 lines
 src/backend/.../NotificationPreferenceRepository.java            7 lines
 src/backend/.../NotificationPreferenceService.java              78 lines
 src/backend/.../NotificationPreference.java (domain)           109 lines
 src/backend/src/main/resources/db/migration/V2__notification_preference.sql  26 lines
 src/backend/src/test/.../NotificationApiIntegrationTest.java   202 lines
 src/frontend/src/app/settings/page.tsx                         278 lines
 src/frontend/src/types/notification.ts                          38 lines

변경 14개:
 CHANGELOG.md                                    +42
 HANDOFF.md                                      (이 파일, 재작성)
 docs/sprint-4-plan.md                            +8/-4
 pipeline/artifacts/06-code/summary.md            +52/-19
 pipeline/decisions/decision-registry.md          +34/-5
 pipeline/state/current-state.json                +17/-6
 prototype/index.html                            +506/-144 (ambient 복사)
 src/backend/.../BacktestController.java          -11
 src/backend/.../BatchController.java             -14
 src/backend/.../GlobalExceptionHandler.java      +13/-4
 src/backend/.../SignalDetectionController.java   -14
 src/backend/.../TelegramNotificationService.java +42/-6
 src/frontend/src/components/NavHeader.tsx         +1
 src/frontend/src/lib/api/client.ts               +20/-9
```
