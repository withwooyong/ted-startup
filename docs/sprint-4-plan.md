# Sprint 4 작업계획서 — 성능 최적화 + 보안 + 사용자 체감 기능

> 생성일: 2026-04-17
> 최종 업데이트: 2026-04-17 (Task 1-6 전체 완료)
> 이전 Sprint: Sprint 3 완료 (백테스팅 엔진 + 텔레그램 알림 + 통합 테스트)
> 기준 커밋: `88aba9a` → 현재 `8d003ba` (Task 4 + 리뷰 반영 커밋 완료)
> 진행 현황: **Sprint 4 전체 Task(1-6) 완료 + 3종 리뷰 반영(HIGH 4 + MEDIUM 9) 완료** — Human Approval #3 대기
> 목표 기간: 3~5일

---

## 1. 배경 및 목표

Sprint 3에서 핵심 기능(백테스팅 + 알림)과 테스트 인프라(Testcontainers 18개 테스트)를 완성했으나, 코드리뷰 잔여 이슈(성능/보안)와 Sprint 3 프론트 범위(알림 설정, 모바일 반응형)가 이관되었다. Sprint 4는 **성능/보안을 먼저 해소하고, 사용자 체감 기능으로 확장**한다.

### 완료 기준 (DoD)

- [ ] N+1 쿼리 17,500건 → 5건 이하로 감소 (SignalDetectionService)
- [ ] 백테스팅 3년 실행 시간 < 30초 (로컬 기준)
- [ ] CORS 환경에서 프론트엔드가 관리자 API 호출 가능
- [ ] 사용자가 프론트 UI에서 텔레그램 알림 설정 변경 가능
- [ ] 모든 페이지가 모바일(375px) 기준으로 정상 동작
- [ ] 기존 18개 테스트 + 추가 테스트 모두 통과
- [ ] WCAG AA 접근성 기준 통과 (주요 페이지)

---

## 2. 작업 범위 (우선순위 순)

### 완료 상태 (2026-04-17 세션)

| Task | 상태 | 커밋 |
|------|------|------|
| Task 1: N+1 쿼리 최적화 | ✅ 완료 (17,500쿼리 → 7쿼리) | `33b6cf1` |
| Task 2: 백테스팅 최적화 | ✅ 완료 (3년 제한 + 벌크 조회) | `33b6cf1` |
| Task 3: CORS X-API-Key | ✅ 완료 | `33b6cf1` |
| Task 4: 알림 설정 페이지 | ✅ 완료 (엔티티 + GET/PUT API + `/settings` 페이지 + Telegram 필터 + 3종 리뷰 반영) | `8d003ba` |
| Task 5: 모바일 반응형 + ErrorBoundary | ✅ 완료 (3개 페이지 + NavHeader + ErrorBoundary resetKeys) | `9436772` |
| Task 6: 접근성 감사 | ✅ 완료 (aria-pressed, focus-visible, Link 단순화) | `9436772` |

### Task 1: N+1 쿼리 최적화 🔴 HIGH

**현재 문제**:
- `SignalDetectionService.detectAll()`: 종목 2500개 × 7쿼리 = **17,500 쿼리**
  - `findByStockIdAndTradingDate()` (balance, price, short) 3회
  - `findByStockIdAndTradingDateBetween()` (trend MA 계산) 1회
  - `existsByStockIdAndSignalDateAndSignalType()` 3회
- `TelegramNotificationService.sendDailySummary()`: Signal 조회 후 `s.getStock().getStockName()` LAZY 로딩 N+1

**해결 방안**:

| 파일 | 변경 |
|------|------|
| `SignalDetectionService` | 일자별 벌크 조회로 전환: `LendingBalanceRepository.findAllByTradingDate`(이미 존재) 재활용 + `StockPriceRepository`, `ShortSellingRepository`에 `findAllByTradingDate` 메서드 추가 |
| `SignalDetectionService` | 기존 시그널 일괄 조회: `signalRepository.findBySignalDate(date)` → Set<Long> 캐싱으로 존재 체크 |
| `SignalRepository` | `findBySignalDateWithStockOrderByScoreDesc` 신규 (JOIN FETCH) |
| `TelegramNotificationService.sendDailySummary` | 신규 메서드 사용 |

**목표**: 17,500쿼리 → **5건 이하** (일자별 벌크 4회 + 시그널 일괄 조회 1회)

### Task 2: 백테스팅 페이징 + 실행 시간 최적화 🟡 MEDIUM

**현재 문제**:
- `findBySignalDateBetweenWithStock` 무제한 조회 → 3년 데이터 시 수만 건 메모리 로드
- 종목별 그룹핑 후 개별 주가 조회 → N번 쿼리

**해결 방안**:
- 최대 기간 3년 제한 (현재 5년 → 3년으로 축소, 백엔드/프론트 일관)
- 스트리밍 처리: `@QueryHints({@QueryHint(name = "org.hibernate.fetchSize", value = "1000")})` 적용
- 주가 벌크 조회 통합: 전체 종목 × 기간의 주가를 `findByTradingDateBetween` 1회로 로드 후 메모리 그룹핑 (메모리 오버헤드 검증 필요)
- 대안: 종목ID IN 절 벌크 조회 `findByStockIdInAndTradingDateBetween`

### Task 3: CORS X-API-Key 허용 🔴 HIGH (보안)

**현재 문제**:
- `WebConfig.java:15`에 `X-API-Key`가 `allowedHeaders`에 없음
- 프론트엔드에서 `POST /api/signals/detect`, `/api/batch/collect`, `/api/backtest/run` 호출 시 preflight 실패

**해결 방안**:
- `WebConfig`에 `X-API-Key` 추가
- Next.js 환경변수(`NEXT_PUBLIC_ADMIN_API_KEY`)로 프론트엔드에서 호출 가능하도록 (로컬/스테이징만, 프로덕션은 프록시 경유 권장 문서화)

### Task 4: 프론트엔드 알림 설정 페이지 🟡 MEDIUM

**요구사항**:
- `/settings` 라우트 신규
- 알림 종류별 on/off 토글 (일일 요약, 긴급 알림, 배치 실패, 주간 리포트)
- 시그널 타입별 필터 (RAPID_DECLINE, TREND_REVERSAL, SHORT_SQUEEZE)
- 최소 스코어 임계값 슬라이더 (0~100)
- 백테스팅 수동 실행 버튼 (API Key 헤더 포함)

**백엔드 변경**:
- `NotificationPreference` 엔티티 신규 (channel, enabled, minScore, signalTypes JSONB)
- `GET /api/notifications/preferences`, `PUT /api/notifications/preferences`
- `TelegramNotificationService` — 설정 반영하여 필터링

**프론트 변경**:
- `src/frontend/src/app/settings/page.tsx` 신규
- `src/frontend/src/lib/api/client.ts` — notification API 추가
- TanStack Query로 설정 fetch + mutation

### Task 5: 모바일 반응형 + ErrorBoundary 🟢 LOW

**반응형**:
- 대시보드: 시그널 카드 1열 (현재 3열) — `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`
- 종목 상세: 듀얼 축 차트 높이 축소 + 레이블 축약
- 백테스트: 테이블 → 카드 리스트로 전환 (모바일만)
- 헤더 네비: 햄버거 메뉴

**ErrorBoundary**:
- `src/frontend/src/components/ErrorBoundary.tsx` 신규 (React Error Boundary)
- 각 페이지의 Recharts 컴포넌트를 감싸기
- fallback UI: "차트를 렌더링할 수 없습니다. 새로고침하거나 기간을 변경해주세요."

### Task 6: 접근성 감사 🟢 LOW

- 키보드 내비게이션 (Tab 순서, 포커스 링)
- ARIA 레이블 (버튼, 차트, 필터)
- 컬러 대비 WCAG AA (Dark Finance Terminal 테마 검증)
- 스크린리더 테스트 (VoiceOver)

---

## 3. 파일별 변경 계획

### 백엔드 (추가)
```
src/backend/src/main/java/com/ted/signal/
├── application/port/out/
│   ├── StockPriceRepository.java           (수정: findAllByTradingDate 추가)
│   ├── ShortSellingRepository.java         (수정: findAllByTradingDate 추가)
│   └── SignalRepository.java               (수정: findBySignalDateWithStock 추가)
├── application/service/
│   ├── SignalDetectionService.java         (수정: 벌크 조회로 전환)
│   ├── BacktestEngineService.java          (수정: 주가 벌크 조회 통합)
│   └── TelegramNotificationService.java    (수정: 설정 반영 + JOIN FETCH 쿼리 사용)
├── adapter/in/web/
│   └── NotificationPreferenceController.java (신규: GET/PUT)
├── domain/model/
│   └── NotificationPreference.java         (신규: 엔티티)
└── config/
    └── WebConfig.java                      (수정: X-API-Key 허용)
```

### 프론트엔드 (추가)
```
src/frontend/src/
├── app/
│   └── settings/page.tsx                   (신규: 알림 설정)
├── components/
│   ├── ErrorBoundary.tsx                   (신규)
│   └── features/
│       └── NotificationSettings.tsx        (신규: 토글/슬라이더 UI)
├── lib/api/
│   └── client.ts                           (수정: notification API 추가)
└── types/
    └── notification.ts                     (신규)
```

### 테스트 (추가)
```
src/backend/src/test/java/com/ted/signal/
├── application/service/
│   ├── SignalDetectionServicePerformanceTest.java (신규: 쿼리 수 검증)
│   └── NotificationPreferenceServiceTest.java     (신규)
└── adapter/in/web/
    └── NotificationApiIntegrationTest.java         (신규)
```

---

## 4. 구현 순서

```
1단계 (0.5일): Task 3 — CORS X-API-Key (빠른 보안 수정)
2단계 (1일):   Task 1 — N+1 쿼리 최적화 + 성능 테스트
3단계 (0.5일): Task 2 — 백테스팅 페이징
4단계 (1.5일): Task 4 — 알림 설정 페이지 (백엔드 + 프론트)
5단계 (1일):   Task 5 + 6 — 모바일 반응형 + ErrorBoundary + 접근성
```

**총 예상**: 4.5일

---

## 5. 검증 방법

| 항목 | 검증 |
|------|------|
| N+1 해소 | Hibernate statistics로 쿼리 수 로깅, 테스트에서 N < 10 검증 |
| 백테스팅 성능 | 로컬 3년 실행 시간 측정 (`BacktestExecutionResult.elapsedMs`) |
| CORS | 브라우저 DevTools Network 탭에서 preflight 200 확인 |
| 알림 설정 | 텔레그램 채널에서 설정 반영 확인 (on/off, 임계값) |
| 모바일 반응형 | Chrome DevTools 375px/768px/1024px 뷰포트 테스트 |
| 접근성 | axe DevTools + Lighthouse 접근성 스코어 90+ |

---

## 6. 리스크 및 의존성

- **주가 벌크 조회 메모리 오버헤드**: KOSPI+KOSDAQ 2500종목 × 750일 = 187만 행 — 메모리 측정 후 분할 전략 필요
- **NotificationPreference 스키마 변경**: 기존 DB에 테이블 추가 필요 → 마이그레이션 스크립트 작성
- **프론트엔드 API Key 노출**: `NEXT_PUBLIC_*`은 빌드에 포함됨 → 운영 환경은 서버사이드 프록시로 래핑 필요 (별도 Task로 분리 가능)

---

## 7. 완료 후 산출물

- 코드: 커밋 2~3개 (성능, 보안, 기능)
- 문서 업데이트:
  - `CHANGELOG.md`: Sprint 4 항목 추가
  - `HANDOFF.md`: 현재 상태 반영
  - `docs/design/ai-agent-team-master.md`: 필요 시 (성능 지표 등)
- 테스트: 기존 18개 + 성능 3~5개 + 통합 5~7개
