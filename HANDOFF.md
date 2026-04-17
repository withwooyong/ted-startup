# Session Handoff

> Last updated: 2026-04-17 10:30 (KST)
> Branch: `master`
> Latest commit: `33b6cf1` - Sprint 4 Task 1-3: N+1 쿼리 최적화 + 백테스팅 3년 제한 + CORS X-API-Key
> 커밋 상태: ✅ 전체 커밋 완료, 로컬 master가 origin/master보다 **5커밋 앞섬** (푸시 대기)

## Current Status

Sprint 4 Task 1-3 (성능/보안 해소) 전체 구현 + 리뷰 + 빌드 검증 + 커밋 완료. Task 4-5 (알림 설정 페이지 + 모바일 반응형)는 다음 세션 이관.

핵심 성과:
1. **N+1 완전 해소**: `SignalDetectionService` 17,500쿼리 → 7쿼리 (활성 종목 1 + 벌크 5 + 기존 시그널 1)
2. **sendDailySummary LAZY 로딩 제거**: JOIN FETCH 쿼리 전환
3. **백테스팅 3년 제한**: 메모리 안정성 + 미래 날짜 차단 + 주가 벌크 조회
4. **CORS X-API-Key 허용**: 프론트에서 관리자 API 직접 호출 가능
5. **모델 운용 전략 전환**: Max 구독자 Opus 4.7 단일 운영 (D-0.1 기록)
6. **리뷰 HIGH 3 + MEDIUM 2 전부 반영**: JOIN FETCH 누락 3곳, 언바운디드 쿼리 2곳, 미래 날짜 검증, detail 키 오류 수정

## Completed This Session

| # | Task | Commit |
|---|------|--------|
| 1 | 모델 운용 전략 문서 정합화 (PIPELINE-GUIDE, master, init-agent-team, decision-registry) | `d55738d` |
| 2 | Task 3 CORS X-API-Key 허용 + OPTIONS + allowCredentials | `33b6cf1` |
| 3 | Task 1 N+1 쿼리 최적화 (SignalDetectionService 전면 재작성) | `33b6cf1` |
| 4 | Task 1 sendDailySummary JOIN FETCH 적용 | `33b6cf1` |
| 5 | Task 2 백테스팅 5년 → 3년, 미래 날짜 차단 | `33b6cf1` |
| 6 | Task 2 주가 벌크 조회 (`findAllByStockIdsAndTradingDateBetween`) | `33b6cf1` |
| 7 | 코드리뷰 HIGH 3 + MEDIUM 2 반영 | `33b6cf1` |
| 8 | 테스트 2개 신규 + 전체 20개 통과 | `33b6cf1` |
| 9 | 문서 현행화: sprint-4-plan, current-state, summary, decision-registry, CHANGELOG | (handoff) |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **`git push origin master`** | 대기 | 로컬이 원격보다 5커밋 앞섬 (`da85ba2`, `eecdb7c`, `cdbacc5`, `d55738d`, `33b6cf1`) |
| 2 | Sprint 4 Task 4: 알림 설정 페이지 | 이관 | `NotificationPreference` 엔티티 + `/settings` 프론트 (1.5일) |
| 3 | Sprint 4 Task 5: 모바일 반응형 + ErrorBoundary | 이관 | grid-cols-1 sm:grid-cols-2, React ErrorBoundary (1일) |
| 4 | Sprint 4 Task 6: 접근성 감사 | 이관 | WCAG AA + 키보드 내비게이션 |
| 5 | CorsConfigTest 스코프 축소 | LOW | `@SpringBootTest` → `@WebMvcTest` (테스트 속도 향상) |
| 6 | 한국 공휴일 캘린더 (v1.1) | 이관 | 현재 주말만 스킵 |

## Key Decisions Made

- **N+1 해소 전략 = 벌크 조회 + 메모리 루프** (D-4.1): 종목별 DB 루프 대신 활성 종목 목록 → 일자별 벌크 쿼리 → Map O(1) 조회. Set 기반 dedup으로 `existsBy` 제거
- **Repository 벌크 메서드 네이밍 = `findAllByStockIdsAndTradingDateBetween`** (D-4.2): `findAll` prefix로 대량 조회 의도 명시. `findByTradingDateBetween` 언바운디드 형태는 OOM 리스크로 지양 (리뷰 HIGH-2 반영)
- **백테스팅 5년 → 3년 + 미래 날짜 차단** (D-4.3): 3년도 충분 + 메모리 여유. `to`가 미래면 400 반환
- **CORS 정책 = X-API-Key 허용 + allowCredentials** (D-4.4): 프론트에서 관리자 API 호출 가능. `exposedHeaders`로 응답 헤더 노출
- **모델 운용 전략 = Max 구독자 Opus 4.7 단일 운영** (D-0.1): Phase별 모델 분기 폐지. 실전 사례(Sprint 3 Opus HIGH 7건 포착) 근거
- **volumeChangeRate detail 키 의미 교정**: 점수(int) 중복 저장 → 실제 거래량 비율(BigDecimal) 저장 (리뷰 MEDIUM-4 반영)

## Known Issues

**해소됨 (Sprint 4 Task 1-3)**:
- ~~N+1 17,500쿼리 (SignalDetectionService)~~ → 해소 (`33b6cf1`)
- ~~sendDailySummary LAZY 로딩 N+1~~ → 해소 (`33b6cf1`)
- ~~백테스팅 무제한 조회~~ → 해소 (3년 제한 + IN 절 벌크) (`33b6cf1`)
- ~~CORS X-API-Key 미허용~~ → 해소 (`33b6cf1`)

**이관됨 (Task 4-5 또는 v1.1)**:
- 알림 설정 페이지 없음 (엔티티 신규 필요)
- ErrorBoundary 없음 (Recharts 렌더링 에러 시 페이지 크래시)
- 모바일 반응형 미적용 (현재 PC 그리드만)
- 한국 공휴일 미처리 (v1.1)
- CorsConfigTest 전체 컨텍스트 로드 (LOW — 테스트 속도)

## Context for Next Session

- **사용자 목표**: 공매도 커버링 시그널 탐지 시스템 MVP 6주 내 완성, 동시에 AI Agent Team 플랫폼 학습
- **현재 단계**: Sprint 4 Task 1-3 완료 → 원격 푸시 대기 → Task 4-5 착수 또는 푸시 후 세션 종료 선택
- **다음 세션 착수 순서 권장**:
  1. `git push origin master` (5커밋 반영)
  2. Task 4 (알림 설정): 백엔드 `NotificationPreference` 엔티티 + `GET/PUT /api/notifications/preferences` + 프론트 `/settings` 페이지
  3. Task 5 (모바일 + ErrorBoundary): 대시보드/상세/백테스트 반응형 + Recharts ErrorBoundary
  4. Task 6 (접근성): axe DevTools + Lighthouse 90+
- **모델 운용**: Opus 4.7 단일 운영 — 리밋 도달 시 Sonnet 4.6 자동 fallback (statusline으로 확인)
- **텔레그램 봇**: @bearchwatch_alarm_bot, BEARWATCH 채널 (chat_id: -1003817432997)
- **기술 스택**: Spring Boot 3.5.0 + Java 21 / Next.js 15 / PostgreSQL 16 / Recharts / Testcontainers
- **실행 명령어**:
  - DB: `docker compose up -d`
  - Backend: `DB_USERNAME=signal DB_PASSWORD=signal ADMIN_API_KEY=test TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./gradlew bootRun --args='--spring.profiles.active=local'`
  - Frontend: `cd src/frontend && npm run dev`
  - 테스트: `cd src/backend && ./gradlew test`
- **주요 Repository 벌크 메서드** (Sprint 4에서 신규):
  - `StockPriceRepository.findAllByTradingDate(date)` (JOIN FETCH)
  - `StockPriceRepository.findAllByStockIdsAndTradingDateBetween(stockIds, from, to)`
  - `ShortSellingRepository.findAllByTradingDate(date)` (JOIN FETCH)
  - `LendingBalanceRepository.findAllByStockIdsAndTradingDateBetween(stockIds, from, to)`
  - `SignalRepository.findBySignalDateWithStockOrderByScoreDesc(date)` (JOIN FETCH)

## 핵심 참조 경로

- 사용설명서: `docs/PIPELINE-GUIDE.md` (개발 플로우 + 이식 체크리스트, 모델 운용 Option A/B)
- Sprint 4 계획: `docs/sprint-4-plan.md` (Task 1-3 완료 표시됨)
- 마스터 설계서: `docs/design/ai-agent-team-master.md`
- 파이프라인 상태: `pipeline/state/current-state.json`
- 의사결정 레지스트리: `pipeline/decisions/decision-registry.md` (28건 누적)
- Build 요약: `pipeline/artifacts/06-code/summary.md`

## Files Modified This Session (커밋 완료)

```
커밋 2개 통계
 d55738d  모델 운용 전략 전환           5 files, +107/-11
 33b6cf1  Sprint 4 Task 1-3            11 files, +245/-114

핸드오프 문서 업데이트 (이 커밋 예정):
 docs/sprint-4-plan.md                 Task 1-3 완료 표시
 pipeline/state/current-state.json     sprint_4 partial, 해소 이슈 이관
 pipeline/artifacts/06-code/summary.md Sprint 4 섹션 추가
 pipeline/decisions/decision-registry.md D-4.1~D-4.4 추가 (24 → 28)
 CHANGELOG.md                          Sprint 4 Task 1-3 엔트리
 HANDOFF.md                            전체 재작성
```
