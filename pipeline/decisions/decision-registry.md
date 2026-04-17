---
last_updated: "2026-04-17"
total_decisions: 36
---

# Decision Registry — 핵심 의사결정 기록부

> Compaction이 발생해도 이 파일의 내용은 보존됩니다.
> 각 에이전트는 중요한 의사결정을 반드시 이 파일에 기록해야 합니다.

## Phase 1: Discovery (완료, 승인 #1 통과, Judge 8.1)

### D-1.1 MVP 범위 확정
- **결정**: KOSPI/KOSDAQ 2500종목, 시그널 3종 (급감/추세전환/숏스퀴즈), v1은 PWA (앱 없음)
- **근거**: 1인 운영, 6주 MVP 목표
- **에이전트**: 02-pm

### D-1.2 면책 고지 필수
- **결정**: 모든 시그널 표시 시 "투자자문 아님" 고지 의무
- **근거**: 자본시장법 리스크 회피
- **에이전트**: 13-security + 05-crm

### D-1.3 투자 등급 체계
- **결정**: 4단계 (A 80+ / B 60+ / C 40+ / D)
- **근거**: 사용자 인지 단순성 + 백테스팅 적중률 구분력
- **에이전트**: 02-pm

## Phase 2: Design (완료, 승인 #2 통과, Judge 8.3)

### D-2.1 Hexagonal Architecture 채택
- **결정**: domain / application(port) / adapter 3계층, QueryDSL 미사용
- **근거**: 1인 운영에서 QueryDSL 설정 복잡도 > 이점, JPA 3단계로 충분
- **에이전트**: 08-backend + 07-db

### D-2.2 PostgreSQL 월별 파티셔닝
- **결정**: `stock_price`, `signal` 테이블 월별 파티션 (LIST partition by month)
- **근거**: 3년 데이터 = 약 200만 행, 파티션 프루닝으로 쿼리 성능 확보
- **에이전트**: 07-db

### D-2.3 Dark Finance Terminal 디자인
- **결정**: 배경 #131720, 주 컬러 #6395FF, 등급별 색상 코드
- **근거**: 금융 도구 톤앤매너 + 장시간 사용 시 눈 피로 감소
- **에이전트**: 06-design

### D-2.4 시그널 스코어 공식 확정
- **결정**:
  - RAPID_DECLINE: `abs(changeRate)×3 + consecutiveDays×5 + 20`
  - TREND_REVERSAL: `divergence×10 + speed×15 + 30`
  - SHORT_SQUEEZE: 4팩터 가중합산 (30+25+25+20)
- **근거**: 급감 → 일회성 이벤트 가중, 추세 → 지속성 가중, 스퀴즈 → 복합 신호
- **에이전트**: 03-planning + 08-backend

## Phase 3: Build (진행 중)

### D-3.1 Spring Boot 3.4 → 3.5.0 (Sprint 1)
- **결정**: 버전 업그레이드
- **근거**: Spring Initializr 기본값 호환 + Java 21 최신 지원
- **커밋**: 33d7676

### D-3.2 JPA ddl-auto: none (Sprint 1)
- **결정**: `validate` → `none`
- **근거**: 파티션 테이블 메타데이터 검증이 Hibernate와 불일치
- **커밋**: 140694b

### D-3.3 HTTP 수집을 트랜잭션 밖으로 (Sprint 1)
- **결정**: `MarketDataCollectionService`에서 KRX HTTP 호출 후 별도 트랜잭션으로 저장
- **근거**: 네트워크 지연이 DB 트랜잭션을 잡고 있으면 커넥션 풀 고갈
- **커밋**: d710aa1

### D-3.4 대차잔고 벌크 조회 (Sprint 1)
- **결정**: 종목별 개별 쿼리 → `findAllByTradingDate` 1회 쿼리
- **근거**: N+1 최적화 (2500건 → 1건)
- **커밋**: d710aa1

### D-3.5 API Key 인증 (Sprint 2)
- **결정**: IP allowlist → `X-API-Key` 헤더 + `ADMIN_API_KEY` 환경변수
- **근거**: 로컬/스테이징/프로덕션 공통 적용 + IP 변경 대응
- **커밋**: e6754cb

### D-3.6 스코어 음수 방지 (Sprint 2)
- **결정**: `scoreVolumeChange`에 `Math.max(0, ...)` 가드
- **근거**: 거래량이 평균보다 낮을 때 음수 스코어가 합산되어 정확도 저하
- **커밋**: e6754cb

### D-3.7 BacktestResult Top20 제한 (Sprint 2)
- **결정**: `findTop20ByOrderByCreatedAtDesc`
- **근거**: unbounded 쿼리 방지
- **커밋**: 63407cd

### D-3.8 백테스팅 엔진 전략 (Sprint 3)
- **결정**: 시그널을 기준으로 역산 (시그널일 → +5/10/20 영업일 후 실제 주가)
- **근거**: 시그널 재탐지보다 단순하고 빠름, 정확도 차이 없음
- **커밋**: 022284e

### D-3.9 TreeMap 기반 영업일 탐색 (Sprint 3)
- **결정**: `priceMap.tailMap(signalDate, false)`로 N번째 영업일 O(log n) 조회
- **근거**: 한국 공휴일 캘린더 없이도 실제 거래일 기반 탐색 가능
- **커밋**: 022284e

### D-3.10 Testcontainers 싱글톤 패턴 (Sprint 3)
- **결정**: `@Container` 대신 `static {}` 블록으로 단일 컨테이너 공유
- **근거**: Spring Context 캐싱과 `@Container` 라이프사이클 충돌 해결
- **커밋**: 022284e

### D-3.11 API Key 상수 시간 비교 (Sprint 3)
- **결정**: `String.equals` → `MessageDigest.isEqual`
- **근거**: 타이밍 오라클 공격 방지 (CRIT-1 코드리뷰 반영)
- **커밋**: 022284e

### D-3.12 Hexagonal 경계 엄격 준수 (Sprint 3)
- **결정**: `MarketDataBatchConfig`에서 `SignalRepository` 직접 주입 제거 → `TelegramNotificationService.sendUrgentAlerts()` 위임
- **근거**: Config는 Infrastructure 레이어, Repository는 Output Port → Application 경유 필수
- **커밋**: 022284e

### D-3.13 401 Unauthorized 반환 (Sprint 3)
- **결정**: 관리자 API 인증 실패 시 `403 FORBIDDEN` → `401 UNAUTHORIZED`
- **근거**: 403은 엔드포인트 존재 사실을 유출, 401이 의미론적으로 정확
- **커밋**: 022284e

### D-3.14 텔레그램 비활성화 지원 (Sprint 3)
- **결정**: 환경변수 미설정 시 로그만 남기고 발송 스킵
- **근거**: 개발/테스트 환경에서 불필요한 발송 방지
- **커밋**: 022284e

### D-3.15 Sprint 4 범위 (계획)
- **결정**: N+1 최적화 → CORS → 알림 설정 페이지 → 모바일 반응형 순서
- **근거**: 성능/보안 우선 해소 후 사용자 체감 기능 확장
- **문서**: docs/sprint-4-plan.md

### D-4.1 N+1 해소 — 벌크 조회 + 메모리 루프 패턴 (Sprint 4 / 2026-04-17)
- **결정**: `SignalDetectionService.detectAll` 종목별 DB 조회 루프 → 활성 종목 1회 조회 후 벌크 쿼리 6건 + 메모리 루프
- **근거**: 17,500 쿼리 → 7 쿼리. Set dedup으로 `existsBy` 쿼리 제거. Map 구조로 O(1) 조회
- **커밋**: 33b6cf1

### D-4.2 Repository 벌크 메서드 네이밍 — `findAllByStockIdsAndTradingDateBetween` (Sprint 4 / 2026-04-17)
- **결정**: `findByStockIdInAndTradingDateBetween` → `findAllByStockIdsAndTradingDateBetween`로 통일
- **근거**: `findAll` prefix로 "대량 조회" 의도 표현 + stockIds IN 필터로 OOM 방지 (리뷰 HIGH-2 반영)
- **커밋**: 33b6cf1

### D-4.3 백테스팅 최대 기간 5년 → 3년 (Sprint 4 / 2026-04-17)
- **결정**: `BacktestController` 최대 기간 5년 → 3년, `to` 미래 날짜 차단 추가
- **근거**: 3년도 충분한 검증 기간 + 메모리/성능 여유. 미래 날짜는 데이터 부재로 무의미
- **커밋**: 33b6cf1

### D-4.4 CORS X-API-Key 허용 + OPTIONS + allowCredentials (Sprint 4 / 2026-04-17)
- **결정**: `WebConfig.addCorsMappings`에 `X-API-Key`, `OPTIONS`, `allowCredentials(true)`, `exposedHeaders` 추가
- **근거**: 브라우저 preflight 통과 + 프론트에서 관리자 API(`/backtest/run`, `/batch/collect`, `/signals/detect`) 호출 가능
- **커밋**: 33b6cf1

### D-4.5 글로벌 NavHeader 단일 네비게이션 전환 (Sprint 4 Task 5 / 2026-04-17)
- **결정**: 페이지별 헤더(SIGNAL 로고/백테스트 링크/대시보드 링크)를 글로벌 `NavHeader` 하나로 통합. sticky + 햄버거 + `pathname` 기반 active state
- **근거**: 페이지 추가 시마다 중복 작성 제거 + 모바일 네비 일관성 + `aria-current` 정확도
- **커밋**: 9436772

### D-4.6 ErrorBoundary는 resetKeys 기반 자동 복구 (Sprint 4 Task 5 / 2026-04-17)
- **결정**: class 컴포넌트 + `resetKeys: ReadonlyArray<unknown>` 지원. `componentDidUpdate`에서 Object.is 비교로 자동 리셋
- **근거**: "다시 시도" 버튼만으로는 재발 루프 → 상위 상태 변경(period, chartData.length)에 반응해 자동 재마운트 필요 (리뷰 MEDIUM-1)
- **커밋**: 9436772

### D-4.7 Render-time 상태 리셋 패턴 적용 (Sprint 4 Task 5 / 2026-04-17)
- **결정**: Next 16 신규 ESLint `react-hooks/set-state-in-effect` 3건 해소 — `useEffect(() => setState)` → `if (prev !== current) setPrev + setState` 패턴
- **근거**: React 19 공식 권장 "resetting state when a prop changes" 패턴. effect는 외부 시스템 동기화 전용
- **커밋**: 9436772
- **적용 파일**: `NavHeader.tsx`(pathname), `stocks/[code]/page.tsx`(code+period), `page.tsx`(초기 setLoading 제거)

### D-4.8 role="tablist" → role="group" + aria-pressed (Sprint 4 Task 6 / 2026-04-17)
- **결정**: 필터/기간 버튼 그룹에서 `role="tablist"`/`role="tab"` 제거 → `role="group"` + `aria-pressed`
- **근거**: ARIA 스펙상 `role="tab"`은 대응되는 `role="tabpanel"` 필수. 현재 버튼들은 필터 토글이므로 `aria-pressed`가 정확 (리뷰 HIGH-2)
- **커밋**: 9436772

### D-4.9 프로토타입 UI 실험 5종 누적 비교본 + 보안 패치 (2026-04-17)
- **결정**: skeleton / tilt-magnetic / counter / ambient 4개 파일 + `index-before-skeleton.html` baseline → 기능 누적형 비교 구조. XSS/SRI/키보드/모션 접근성 패치를 5파일 전부에 선제 반영
- **근거**: 사용자가 "API 연동 시점까지 기다리지 않고 프로토타입 단계에서 보안 선제 적용"을 선택 → 이후 실제 프론트 이식 시 추가 점검 불필요
- **커밋**: 7a5b750
- **후속**: D-4.10에서 `index-ambient.html`을 최종 합류본으로 확정

### D-4.12 Task 4 리뷰 반영 — HIGH 4 + MEDIUM 9 전량 수정 (2026-04-17)
- **배경**: Task 4 구현 후 java-reviewer / typescript-reviewer / security-reviewer 3개 리뷰어 병렬 실행 → BLOCK(HIGH 4) 판정
- **핵심 수정**:
  1. `PUT /api/notifications/preferences` 인증 추가 — 기존 관리자 API 패턴(X-API-Key) 재사용. `ApiKeyValidator` 컴포넌트로 추출해 3개 컨트롤러 중복 제거
  2. `loadOrCreate` race condition — `DataIntegrityViolationException` catch + 재조회. 싱글톤 row 지연 생성의 동시 최초 요청 경합을 멱등 처리
  3. `IllegalArgumentException` 전역 캐치 제거 — JDK 내부 오류가 400으로 마스킹되는 위험 해소. 검증은 `DomainException(DomainError.InvalidParameter)` 경로로 이동
  4. Hexagonal 경계 교정 — `sanitizeSignalTypes` 검증을 Controller에서 `UpdateCommand` compact constructor로 이동. record 생성 자체가 검증 계기 → 어떤 경로로 생성해도 도메인 규칙 강제
- **원칙**: 사용자 입력을 에러 메시지에 반사하지 않음(정보 노출 방지). `@Size(min=1, max=3)`으로 DoS 벡터 차단. 도메인 `update()` 자체도 방어 검증(이중 안전망)
- **프론트**: `aria-*` 중복 제거, `cache: 'no-store'` spread 순서 교정, 백엔드 에러 메시지 직접 노출 → status 기반 `friendlyError()` 매핑
- **테스트**: 5개 → 9개 확장 (인증 2, 업데이트 1, 검증 5, 기본값 1). 에러 응답 입력 반사 없음 검증 포함
- **전체 테스트**: 20 → 29개 통과 (기존 20 + Task 4 신규 9)
- **리뷰 판정 변화**: BLOCK(HIGH 4) → PASS (HIGH 0, MEDIUM 0 남음, LOW 5 v1.1 이관)

### D-4.11 알림 설정 = 싱글 로우 패턴 (Sprint 4 Task 4 / 2026-04-17)
- **결정**: `NotificationPreference` 엔티티를 **싱글 로우(id=1 고정)** 로 운영. 4개 채널 플래그(daily/urgent/batch/weekly) + `minScore`(0-100) + `signalTypes`(JSONB 배열)
- **근거**:
  - MVP 1인 운영 → 사용자/인증 개념이 아직 없음 (카카오 OAuth는 추후)
  - Sprint 4 plan의 `channel`(TELEGRAM/EMAIL/WEB) 구분보다 **시나리오별 on/off**가 실제 UX에 더 정확 (일일 요약/긴급/배치/주간)
  - 첫 GET 호출 시 기본값 row 자동 생성 (`loadOrCreate`) → 별도 초기화 스크립트 불필요
- **필터 적용 범위**:
  - `sendDailySummary`: toggle + signalTypes + minScore 삼중 필터
  - `sendUrgentAlerts`: toggle + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: toggle만
  - `sendUrgentAlert(single)`: 필터 미적용 — 호출자 책임 원칙
- **확장 경로**: user 테이블 도입 시 `user_id FK` + unique constraint로 다중 사용자 전환 가능
- **파일**: `domain/model/NotificationPreference`, `application/service/NotificationPreferenceService`, `adapter/in/web/NotificationPreferenceController`, `db/migration/V2__notification_preference.sql`
- **테스트**: 5개 신규 통합 테스트 (기본값 생성 / 전체 업데이트 / minScore 범위 / 알 수 없는 타입 / 필수 필드 누락)

### D-4.10 프로토타입 합류본 = ambient 확정 (2026-04-17)
- **결정**: `index-ambient.html`(1332줄, 61KB)을 최종 합류본으로 채택하고 `prototype/index.html`을 동일 내용으로 덮어써 캐노니컬 엔트리 통일
- **근거**: skeleton(로딩) + tilt/tilt-shine(3D 카드) + magnetic(버튼 인력) + data-count(카운트업) + aurora(4 blob 배경) 5종 효과가 누적 탑재된 유일한 파일. UI/UX 화려도 극대화가 프로토타입 목적에 부합
- **잔여 파일**: `index-{before-skeleton,tilt-magnetic,counter,ambient}.html` 4종은 단계별 비교 레퍼런스로 보존 (삭제 보류)
- **다음 단계**: Next.js 프론트 이식 시 효과별 컴포넌트 분해 — aurora → fixed layer, tilt → hook(useTilt), counter → hook(useCountUp), magnetic → 버튼 래퍼
- **사용자 승인**: 2026-04-17 대화 내

## Phase 0: Meta / 운영 전략

### D-0.1 모델 운용 전략 — Opus 4.7 단일 운영 (2026-04-17)
- **결정**: 이전 "Phase 1~3 Sonnet 4.6 / Phase 4 Opus 4.7" 분기 전략 → **모든 Phase Opus 4.7 단일 운영**으로 전환
- **근거**:
  - Claude Code Max $200 구독 → 모델 분기로 얻는 비용 이득 없음
  - Sprint 3 코드리뷰에서 Opus 4.7이 N+1 17,500건 등 HIGH 이슈 7건 포착 (Sonnet 대비 우위 확인)
  - Phase 1~3에서도 엣지 케이스/복합 제약 판단은 Opus가 유리
  - 리밋 도달 시 Sonnet 4.6 자동 fallback — statusline으로 실시간 인지 가능
- **적용 범위**: 이 프로젝트(ted-startup) 기본값. 타 프로젝트 이식 시 구독 유형에 따라 Option A/B 선택
- **문서**:
  - docs/PIPELINE-GUIDE.md (모델 운용 전략 섹션)
  - docs/design/ai-agent-team-master.md (§11 모델 전략)
  - .claude/commands/init-agent-team.md (CLAUDE.md 템플릿)
