# Session Handoff

> Last updated: 2026-04-17 09:10 (KST)
> Branch: `master`
> Latest commit: `cdbacc5` - 문서 업데이트: Opus 4.7 반영 + Spring Boot 3.5.0 + 사용설명서 신규
> 커밋 상태: ✅ 전체 커밋 완료, 로컬 master가 origin/master보다 3커밋 앞서 있음 (푸시 대기)

## Current Status

Sprint 3 전체 커밋 완료 + 파이프라인 플랫폼 정합화 완료. 핵심 전환:
1. **Sprint 3 구현물 커밋** (백테스팅 엔진 + 텔레그램 + 통합 테스트 18종)
2. **파이프라인 격차 해소** (state/artifacts/decisions 현행화)
3. **팀 공유 전환** (`.gitignore`에서 pipeline/ 제거 → 소규모 스타트업 공유 전제)
4. **문서 업데이트** (Opus 4.6 → 4.7, Spring Boot 3.5.0, 사용설명서 `PIPELINE-GUIDE.md` 신규)
5. **글로벌 statusline** 설정 (Opus↔Sonnet fallback 실시간 인지)

Sprint 4 착수 대기. 작업계획서: `docs/sprint-4-plan.md`.

## Completed This Session

| # | Task | Commit |
|---|------|--------|
| 1 | Sprint 3 구현: 백테스팅 엔진 + 텔레그램 4종 + Testcontainers 18개 | `022284e` |
| 2 | Sprint 3 핸드오프 문서 업데이트 | `88aba9a` |
| 3 | 텔레그램 봇 BEARWATCH 채널 연동 확인 (chat_id 메모리 저장) | (메모리) |
| 4 | `pipeline/state/current-state.json` Sprint 3 완료 상태 현행화 | `eecdb7c` |
| 5 | `pipeline/artifacts/06-code/summary.md` Sprint 1~3 요약 작성 | `eecdb7c` |
| 6 | `pipeline/decisions/decision-registry.md` 의사결정 23개 누적 | `da85ba2` |
| 7 | `docs/sprint-4-plan.md` Sprint 4 작업계획서 작성 | `da85ba2` |
| 8 | `.gitignore`에서 `pipeline/` 제거 → 팀 공유 전환 (21 파일 공유) | `eecdb7c` |
| 9 | `CLAUDE.md` 스타트업 팀 공유 전제 + Spring Boot 3.5.0 정합 | `eecdb7c`, `cdbacc5` |
| 10 | 마스터 설계서 Opus 4.6 → 4.7 치환 (14곳) | `cdbacc5` |
| 11 | `init-agent-team.md` 기본 스택 Spring Boot 3.5.0 반영 | `cdbacc5` |
| 12 | `docs/PIPELINE-GUIDE.md` 신규 (사용설명서, 9개 섹션) | `cdbacc5` |
| 13 | 글로벌 `~/.claude/settings.json`에 statusLine 추가 | (글로벌) |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **`git push origin master`** | 대기 | 로컬이 원격보다 3커밋 앞섬 (`da85ba2`, `eecdb7c`, `cdbacc5`) |
| 2 | Sprint 4 Phase A: CORS X-API-Key 허용 | 계획됨 | `WebConfig.allowedHeaders` 수정 (0.5일) |
| 3 | Sprint 4 Phase B-1: N+1 쿼리 최적화 | 계획됨 | SignalDetectionService 종목당 7쿼리 × 2500 → 5건 (1일) |
| 4 | Sprint 4 Phase B-2: 백테스팅 페이징 | 계획됨 | `findBySignalDateBetweenWithStock` 페이지 분할 (0.5일) |
| 5 | Sprint 4 Phase B-3: 알림 설정 페이지 | 계획됨 | `NotificationPreference` 엔티티 + 프론트 /settings (1.5일) |
| 6 | Sprint 4 Phase C: 모바일 반응형 + ErrorBoundary + 접근성 | 계획됨 | 1일 |
| 7 | `sendDailySummary` N+1 해소 | 이관 | `findBySignalDateOrderByScoreDesc` JOIN FETCH 추가 (리뷰 HIGH-7) |
| 8 | 한국 공휴일 캘린더 (v1.1) | 이관 | 현재 주말만 건너뛰기 |

## Key Decisions Made

- **파이프라인 팀 공유 전환**: 1인 프로젝트 가정 → 소규모 스타트업 팀 전원이 기획/디자인/개발/보안/DevOps 겸무하는 구조로 선회. `pipeline/` 디렉토리 커밋 대상화
- **모델 운용 전략**: Claude Code Max $200 구독 활용 → Opus 4.7 단일 운영, 리밋 도달 시 자동 Sonnet fallback
- **Statusline 영속 표시**: `~/.claude/settings.json`에 모델/비용/200k/CWD 커스텀 포맷 추가 → fallback 즉시 인지 가능
- **문서 계층화**: 마스터 설계서(4112줄) + 사용설명서(실전 요약) + 작업계획서(스프린트별) 3계층 구조 확립
- **의사결정 누적**: `decision-registry.md`에 23개 결정 기록 완료 → Compaction 방어 + 세션 복구용

## Known Issues

- **N+1 쿼리**: SignalDetectionService 종목당 7쿼리 × 2500 = 17,500쿼리 (Sprint 4 Task 1)
- **sendDailySummary LAZY 로딩**: stock 엔티티 N+1 조회 — JOIN FETCH 쿼리 추가 필요
- **백테스팅 대량 데이터**: findBySignalDateBetweenWithStock 무제한 조회 — Pageable 또는 Stream 적용 필요
- **CORS X-API-Key 누락**: `WebConfig.allowedHeaders`에 미포함 — 브라우저 직접 호출 시 차단 (Sprint 4 Task 3)
- **ErrorBoundary 없음**: Recharts 렌더링 에러 시 페이지 크래시
- **한국 공휴일 미처리**: 주말만 건너뛰기 (v1.1)

## Context for Next Session

- **사용자 목표**: 공매도 커버링 시그널 탐지 시스템 MVP 6주 내 완성, 동시에 AI Agent Team 플랫폼 학습
- **현재 단계**: Sprint 3 완료 → 원격 푸시 후 Sprint 4 착수
- **Sprint 4 실행 방식 후보**:
  - 방식 A: Phase A(CORS) 순차 → Phase B(3 Task) 병렬 (안전, 권장)
  - 방식 B: Phase A + Phase B 동시 착수 (최대 속도, worktree 격리 기반)
- **모델 운용**: Opus 4.7 단일 사용 — 리밋 시 Sonnet 자동 fallback (statusline으로 확인)
- **텔레그램 봇**: @bearchwatch_alarm_bot, BEARWATCH 채널 (chat_id: -1003817432997)
- **기술스택**: Spring Boot 3.5.0 + Java 21 / Next.js 15 / PostgreSQL 16 / Recharts / Testcontainers
- **실행 명령어**:
  - DB: `docker compose up -d`
  - Backend: `DB_USERNAME=signal DB_PASSWORD=signal ADMIN_API_KEY=test TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./gradlew bootRun --args='--spring.profiles.active=local'`
  - Frontend: `cd src/frontend && npm run dev`
  - 테스트: `cd src/backend && ./gradlew test`
- **API 목록**:
  - `GET /api/signals?date&type` — 시그널 리스트
  - `GET /api/stocks/{code}?from&to` — 종목 상세
  - `GET /api/backtest` — 백테스팅 결과 조회
  - `POST /api/backtest/run?from&to` — 백테스팅 실행 (API Key, 최대 5년)
  - `POST /api/batch/collect` — 수동 배치 (API Key)
  - `POST /api/signals/detect` — 수동 탐지 (API Key)

## 핵심 참조 경로

- 사용설명서: `docs/PIPELINE-GUIDE.md` (개발 플로우 + 이식 체크리스트)
- Sprint 4 계획: `docs/sprint-4-plan.md`
- 마스터 설계서: `docs/design/ai-agent-team-master.md`
- 파이프라인 상태: `pipeline/state/current-state.json`
- 의사결정 레지스트리: `pipeline/decisions/decision-registry.md`
- Build 요약: `pipeline/artifacts/06-code/summary.md`

## Files Modified This Session (커밋 완료)

```
커밋 4개 (022284e → cdbacc5) 통계
 pipeline/artifacts/* (21 파일 신규)          팀 공유 전환
 pipeline/state/current-state.json            Sprint 3 완료 반영
 pipeline/decisions/decision-registry.md      의사결정 23개 누적
 docs/PIPELINE-GUIDE.md (신규)                사용설명서
 docs/sprint-4-plan.md (신규)                 Sprint 4 작업계획
 docs/design/ai-agent-team-master.md          Opus 4.7 (14곳)
 .claude/commands/init-agent-team.md          Spring Boot 3.5.0
 CLAUDE.md                                    스타트업 팀 공유 명시
 .gitignore                                   pipeline/ 제외 규칙 제거
 src/backend/src/main/**/*.java (19 파일)     Sprint 3 구현
 src/backend/src/test/java/**/*.java (6 파일) Testcontainers 18개
 ~/.claude/settings.json (글로벌)             statusLine 설정 추가
```
