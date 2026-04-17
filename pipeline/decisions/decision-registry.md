---
last_updated: "2026-04-17"
total_decisions: 24
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
