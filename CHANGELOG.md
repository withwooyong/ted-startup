# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/).

## [Unreleased]

---

## [2026-04-17] 파이프라인 플랫폼 정합화 + 팀 공유 전환 + 문서 현행화

### Added
- `docs/PIPELINE-GUIDE.md`: 개발 플로우 사용설명서 신규 (9개 섹션, 다른 프로젝트 이식 체크리스트 포함) (`cdbacc5`)
- `docs/sprint-4-plan.md`: Sprint 4 작업계획서 (N+1 최적화 + CORS + 알림 설정 페이지 + 모바일 반응형, 4.5일 예상) (`da85ba2`)
- `pipeline/state/current-state.json`: Sprint 3 완료 상태 현행화 (진행 sprint 4종 + 테스트 커버리지 + 알려진 이슈) (`eecdb7c`)
- `pipeline/artifacts/06-code/summary.md`: Sprint 1~3 구현 요약 (Compaction 방어 영속화) (`eecdb7c`)
- `pipeline/decisions/decision-registry.md`: Phase 1~3 의사결정 23개 누적 (Discovery 3, Design 4, Build 15, Sprint 4 계획 1) (`da85ba2`)
- 글로벌 `~/.claude/settings.json` statusLine: 현재 모델 / 비용 / 200k 초과 / CWD 실시간 표시 (Opus→Sonnet fallback 즉시 인지)

### Changed
- `.gitignore`: `pipeline/state/`, `pipeline/artifacts/` 제외 규칙 제거 → 팀 공유 대상화 (`eecdb7c`)
- `CLAUDE.md`: 소규모 스타트업 팀 공유 전제 명시 + PIPELINE-GUIDE.md 참조 추가 + Spring Boot 3.4 → 3.5.0 일관성 (`eecdb7c`, `cdbacc5`)
- `docs/design/ai-agent-team-master.md`: `Opus 4.6` → `Opus 4.7` 14곳 치환 (1M 컨텍스트, 비용, MRCR 설명 전반) (`cdbacc5`)
- `.claude/commands/init-agent-team.md`: 기본 스택 `Spring Boot 3.4` → `3.5.0` (새 프로젝트 scaffolding 현행값) (`cdbacc5`)

### Committed
- Sprint 3 구현 (`022284e`): 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트 (19 files, +1346)
- Sprint 3 핸드오프 (`88aba9a`): CHANGELOG + HANDOFF
- 파이프라인 영속화 (`da85ba2`): decision-registry + sprint-4-plan
- 팀 공유 전환 (`eecdb7c`): pipeline/ 커밋 대상화 (22 files, +2369)
- 문서 업데이트 (`cdbacc5`): Opus 4.7 + Spring Boot 3.5.0 + PIPELINE-GUIDE

---

## [2026-04-17] Phase 3 Build Sprint 3 — 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트

### Added
- BacktestEngineService: 과거 3년 시그널 수익률 계산 + SignalType별 적중률/평균수익률 집계
- RunBacktestUseCase 포트 + POST /api/backtest/run API (API Key 보호, 기본 3년, 최대 5년)
- TelegramClient: RestClient 기반 Telegram Bot API 연동 (환경변수 비활성화 지원)
- TelegramNotificationService: 4가지 알림 시나리오 (일일 요약/A등급 긴급/배치 실패/주간 리포트)
- NotificationScheduler: 08:30 일일 요약 (월~금), 토요일 10:00 주간 리포트
- MarketDataBatchConfig notifyStep: 배치 완료 후 A등급 시그널 긴급 알림 자동 발송
- SignalRepository.findBySignalDateBetweenWithStock: JOIN FETCH 벌크 조회
- Testcontainers PostgreSQL 16 통합 테스트 인프라 (싱글톤 컨테이너 패턴)
- SignalDetectionServiceTest: 시그널 탐지 로직 5개 테스트 (급감/임계값/추세전환/숏스퀴즈/중복방지)
- BacktestEngineServiceTest: 수익률 계산 + 적중률 집계 + 데이터 부족 처리 4개 테스트
- BacktestApiIntegrationTest: API 인증/실행 5개 테스트
- SignalApiIntegrationTest: 시그널 조회/필터/인증 3개 테스트
- application.yml: telegram.bot-token, telegram.chat-id 환경변수 설정

### Changed
- API Key 비교: String.equals → MessageDigest.isEqual 상수 시간 비교 (타이밍 공격 방지, 3개 컨트롤러)
- API Key 미인증 시 403 → 401 UNAUTHORIZED 반환 (3개 컨트롤러)
- @Value 필드 주입 → 생성자 주입 전환 (BacktestController, BatchController, SignalDetectionController)
- BacktestEngineService: save() 루프 → saveAll() 일괄 저장
- MarketDataBatchConfig: SignalRepository 직접 주입 제거 → TelegramNotificationService.sendUrgentAlerts() 위임 (Hexagonal 경계 준수)
- MarketDataScheduler: 배치 실패 시 e.getMessage() 노출 → 클래스명만 텔레그램 발송
- BacktestController: @Validated 추가 + from/to 날짜 범위 검증 (최대 5년)
- TelegramNotificationService.sendBatchFailure: LocalDate → LocalDateTime (시간 정밀도)

---

## [2026-04-16] Phase 3 Build Sprint 2 — 시그널 엔진 + 대시보드

### Added
- SignalDetectionService: 3대 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) (`7902cfd`)
- POST /api/signals/detect 수동 시그널 탐지 API (`7902cfd`)
- Spring Batch detectStep 추가 (collectStep → detectStep 순차) (`7902cfd`)
- 프론트엔드 대시보드: 메트릭 카드 + 필터 탭 + 시그널 리스트 (`7902cfd`)
- 프론트엔드 종목 상세: 주가/대차잔고 듀얼 축 차트 (Recharts) (`7902cfd`)
- SignalCard 컴포넌트, TypeScript 타입 정의, API 클라이언트 (`7902cfd`)
- BacktestResult Entity + Repository + BacktestQueryService (`63407cd`)
- GET /api/backtest 백테스팅 결과 조회 API (`63407cd`)
- 프론트엔드 /backtest 페이지: 성과 테이블 + 보유기간별 수익률 Bar 차트 (`63407cd`)

### Changed
- 관리자 API 인증: IP allowlist → API Key 헤더(X-API-Key) 전환 (`e6754cb`)
- detail.volumeChangeRate 매핑 오류 수정 (`e6754cb`)
- scoreVolumeChange 음수 방지 Math.max(0, ...) 추가 (`e6754cb`)
- params.code 안전한 타입 처리 (Array.isArray 체크) (`e6754cb`)
- 프론트엔드 API 클라이언트 단일화 (중복 fetch 제거) (`e6754cb`)
- 미사용 변수 signalDates 제거 (`e6754cb`)

---

## [2026-04-16] Phase 3 Build Sprint 1 — 데이터 파이프라인 구축

### Added
- 16개 에이전트 AGENT.md + 공유 프로토콜 + 7개 슬래시 커맨드 scaffolding (`1908310`)
- Phase 1 Discovery 산출물 8건: 요구사항, PRD, 로드맵, 스프린트 플랜, GTM, 경쟁사 분석, 고객여정, 알림 시나리오 (`1908310`)
- Phase 2 Design 산출물 6건: 기능명세, 디자인 토큰, 컴포넌트 명세, ERD, DDL, 쿼리 전략 (`1908310`)
- Spring Boot 3.5.0 + Java 21 백엔드 프로젝트 (Hexagonal Architecture) (`33d7676`)
- Domain Entity 5개: Stock, StockPrice, LendingBalance, ShortSelling, Signal (`33d7676`)
- Repository 5개 (JPA 3단계 쿼리 전략), UseCase 2개, SignalQueryService (`33d7676`)
- REST API: GET /api/signals, GET /api/stocks/{code} (`33d7676`)
- GlobalExceptionHandler + sealed interface DomainError (`33d7676`)
- KRX 크롤러: 공매도/대차잔고/시세 수집 (요청 간격 2초) (`620f2bf`)
- Spring Batch Job + MarketDataScheduler (매일 06:00 스케줄) (`620f2bf`)
- 수동 배치 API: POST /api/batch/collect (localhost 제한) (`620f2bf`)
- docker-compose.yml: PostgreSQL 16 + DDL 자동 적용 (`620f2bf`)
- Next.js 15 + TypeScript 프론트엔드 프로젝트 초기화 (`33d7676`)
- UI/UX 프로토타입: Dark Finance Terminal 디자인 (prototype/index.html) (`33d7676`)
- .env.example (`620f2bf`)

### Changed
- Spring Boot 버전 3.4 → 3.5.0 (Spring Initializr 호환) (`33d7676`)
- JPA ddl-auto: validate → none (파티션 테이블 호환) (`140694b`)
- CORS allowedOrigins → allowedOriginPatterns + 헤더 제한 (`620f2bf`)
- MarketDataCollectionService: HTTP 수집을 트랜잭션 밖으로 분리 (`d710aa1`)
- 대차잔고 전 영업일 계산: minusDays(1) → 주말 건너뛰기 (`d710aa1`)
- 대차잔고 벌크 조회: 종목별 개별 쿼리 → findAllByTradingDate 1회 쿼리 (`d710aa1`)
- saveAll 벌크 저장으로 개별 exists/save 쿼리 제거 (`d710aa1`)
- BatchConfig → BatchConfig + Scheduler 분리 (Job Bean 직접 주입) (`d710aa1`)

---

## [2026-04-16] 프로젝트 초기 설정

### Added
- CLAUDE.md 생성 — 프로젝트 개요, 기술스택, 파이프라인, 에이전트 구조 가이드 (`fd26e75`)
- .gitignore 생성 — 빌드/IDE/환경파일 제외 설정 (`fd26e75`)
- GitHub 저장소 생성 (withwooyong/ted-startup, private) (`fd26e75`)
- AI Agent Team Platform 설계서 및 scaffolding 생성기 커밋 (`fd26e75`)
