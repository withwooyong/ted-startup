---
agent: 00-judge
phase: Phase 4 Verify
date: 2026-04-17
last_commit: 9436772
inputs:
  - pipeline/artifacts/07-test-results/qa-report.md
  - pipeline/artifacts/08-review-report/review-report.md
  - pipeline/artifacts/09-security-audit/audit-report.md
verdict: CONDITIONAL
final_score: 7.6
---

# Phase 4 Verify 통합 판정 — ted-startup (BEARWATCH)

## 1. 종합 판정 — **CONDITIONAL**

세 에이전트 리포트(QA / Review / Security) 모두 독립적으로 CONDITIONAL을 부여했고, 조건부 사유 또한 **동일한 블로커(`NEXT_PUBLIC_ADMIN_API_KEY` 번들 노출)에 수렴**함. 통합 판정 역시 **CONDITIONAL PASS**. Phase 5 Ship 진입은 아래 차단 조건 4건 해소를 전제로 가결을 권고한다. 차단 이슈가 해소되면 무조건 PASS 전환 가능.

## 2. 5차원 평가 점수

| 차원 | 가중치 | 점수 | 가중 점수 | 근거 |
|---|---|---|---|---|
| 완전성(Completeness) | 25% | 7.0 | 1.75 | 백엔드 29/29 통과, MVP 기능 커버. 단 프론트 테스트 0건·P95/P99 미측정·JaCoCo 미설정으로 품질 증거 불완전. |
| 일관성(Consistency) | 25% | 8.5 | 2.125 | 3개 리포트 상호 모순 없음. 같은 블로커를 세 에이전트가 동일 방향으로 지적 — 내부 신호 강함. |
| 정확성(Accuracy) | 20% | 8.0 | 1.60 | 각 지적 이슈가 실제 파일/라인 인용 포함, 재현 가능. B-H1 자기호출 트랜잭션 지적은 Spring AOP 프록시 동작과 일치. |
| 명확성(Clarity) | 15% | 8.0 | 1.20 | 심각도 라벨(CRITICAL/HIGH/MEDIUM/LOW) + 조치 옵션 명시. OWASP Top 10 맵핑 수행. |
| 실행가능성(Actionability) | 15% | 6.0 | 0.90 | 블로커 3건 수정안에 복수 옵션 제시되나 택일 가이던스가 약함(B-C1은 3가지 대안). Ship+1/+7 타임라인은 명확. |
| **합계** |  |  | **7.575 (반올림 7.6)** | → 판정 구간 6.0~7.9 → **CONDITIONAL** |

## 3. Phase 5 진입 가능 여부 — **N (조건부)**

**Blockers (진입 전 필수 해결):**

1. **[B-C1 / F-H1 / HIGH-1] `NEXT_PUBLIC_ADMIN_API_KEY` 클라이언트 번들 노출** — 세 리포트 공통 지목. Next Route Handler/Server Action으로 이전해 서버 전용 `ADMIN_API_KEY`만 사용하거나, v1은 `/settings` 쓰기를 백엔드 CLI로 임시 운용. **단독 최중대 이슈.**
2. **[B-H1] `MarketDataCollectionService.collectAll` → `persistAll` 자기호출 트랜잭션 무효** — `MarketDataPersistService`로 분리하여 public `@Transactional` 메서드로 외부 호출.
3. **[B-H2] `persistAll` 데드 코드 블록 삭제** — `findByStockIdAndTradingDateBetween(null, ...)` 블록은 항상 빈 리스트 반환하고 이후 미사용. 단순 삭제.
4. **[B-H3] 배치 재실행 시 유니크 제약 충돌 방지** — `findAllByTradingDate(date)` 1회 조회 + exists 체크 후 skip/update, 또는 Native upsert(`ON CONFLICT DO UPDATE`).

**해결 요건 체크리스트:**
- [ ] 프론트엔드에서 `NEXT_PUBLIC_ADMIN_API_KEY` 참조 0건 재빌드 확인 (`grep -r NEXT_PUBLIC_ADMIN src/frontend` → 결과 없음)
- [ ] `collectAll` 재실행 통합 테스트 추가 (멱등성 + 트랜잭션 경계 회귀 방지 2종)
- [ ] 기존 29개 테스트 회귀 통과
- [ ] 차단 4건 수정 커밋 후 본 판정 재실행

## 4. 크로스 체크 결과 (requirements → PRD → code)

MVP 범위 9개 FR 기준. 누락/불일치만 기재.

| FR | requirements | PRD 우선순위 | 구현 상태 | 비고 |
|---|---|---|---|---|
| FR-001 KRX 공매도 수집 | US-001/002/003 | P0 | 구현(`MarketDataCollectionService`) | **B-H1/H2/H3 결함 — 블로커** |
| FR-007 백테스팅 엔진 | US-005 | P0 | 구현 + 통합 테스트 6건 | **B-M1 응답 스키마 불일치 — 배포 후 핫픽스 허용** |
| FR-008 텔레그램 알림 | US-006 | P0 | 구현(`TelegramNotificationService`) | **MED-4 HTML escape 누락 / B-M4 스택트레이스 소실** |
| FR-010 임계값 커스터마이징 | US-008 | **P1 (deferred v1.1)** | **선제 구현(`/settings`)** | 요구사항 범위 초과 구현. 이는 B-C1 블로커의 진원지. |

**핵심 불일치**: FR-010은 MVP deferred인데 Sprint 4 Task 4에서 **계획 외 구현**되어 블로커를 만들어냈다. 관리자 쓰기 경로가 인증 구조 없이 추가된 결과. v1 범위를 지키는 "읽기 전용 `/settings`"로 축소하거나 서버 라우팅으로 이전해야 정합성 회복.

**나머지 매핑은 양호**: US-001~006/012, FR-001~008/012 모두 DB 스키마·엔드포인트·프론트 화면까지 추적 가능. 모든 테이블(`stock`, `stock_price`, `short_selling`, `lending_balance`, `signal`, `backtest_result`, `notification_preference`)이 최소 1개 API로 접근된다.

## 5. 3 에이전트 리포트 합치성

| 이슈 | QA | Review | Security | 합치 |
|---|---|---|---|---|
| `NEXT_PUBLIC_ADMIN_API_KEY` | 언급 없음 (QA 스코프 밖) | CRITICAL (B-C1/F-H1) | HIGH (HIGH-1) | **완전 일치** — 2개 리포트가 동일 파일·라인 인용, 조치안 동일 방향 |
| 프론트엔드 테스트 0건 | 조건부 사유 #1 | F-L1 언급 | 언급 없음 | 일치(QA 주도) |
| 성능 기준선 미수립 | 조건부 사유 #2 | B-M2 트랜잭션 범위 | MED-1 rate limit | 보완 관계 — 충돌 없음 |
| Rate limiting 부재 | 언급 없음 | 언급 없음 | MED-1 | Security 단독 |
| 자기호출 트랜잭션(B-H1) | 언급 없음 | HIGH 단독 발견 | 언급 없음 | **Review 단독 심층 발견 — 유의미 신호** |
| Actuator info 노출 | 언급 없음 | 언급 없음 | MED-2 | Security 단독 |
| CORS 하드코딩 | 언급 없음 | B-L2 | 설정 범위 밖 | 일치 |

**충돌 0건, 중복 보강 3건, 단독 발견 상호 보완**. 세 에이전트가 각자 전문 영역을 책임지며 횡단 이슈(B-C1)에서만 수렴 — 이상적인 다중 시각 검증 형태.

## 6. 공통 발견 이슈 Top 3 (중복 발견 = 강한 신호)

1. **관리자 API Key 클라이언트 노출 (B-C1 / F-H1 / HIGH-1)** — Review CRITICAL + Security HIGH. 배포 시 관리자 엔드포인트 4개(batch/collect, signals/detect, backtest/run, notifications/preferences PUT) 전부 익명 공개. **최중대 블로커.**
2. **프론트엔드 자동화 테스트 부재 (QA §4 / F-L1)** — QA가 CONDITIONAL 핵심 사유로 지목, Review도 인지. Sprint 4 Task 5/6(ErrorBoundary, 반응형, 접근성)의 회귀 보호 수단 없음. Phase 5 블로커는 아니나 Sprint 5 필수.
3. **배치 운영 안정성 (B-H1/H2/H3 + MED-1 rate limit)** — Review HIGH 3건 + Security MED 1건이 `POST /api/batch/collect` 경로에 집중. 수동 재수집 1회만 실행해도 배치 전체 실패 가능.

## 7. 에이전트별 리포트 자체 품질

| 에이전트 | 점수 | 근거 |
|---|---|---|
| 11-qa | **8.5 / 10** | 테스트 피라미드 분석, 커버리지 공백 P1~P3 분류, 차기 Sprint 액션 공수(인일) 산정까지 포함. Phase 5 판정과 Sprint 5 로드맵 연결이 명확. 감점: JaCoCo 미설정이라 커버리지 수치가 "추정" 수준. |
| 08-backend(review) | **9.0 / 10** | 17개 이슈를 CRITICAL/HIGH/MEDIUM/LOW 일관 분류. B-H1 자기호출 트랜잭션·B-H2 데드 코드는 QA/Security가 놓친 **심층 단독 발견**. Resolved 9건을 소스 라인까지 재확인한 것은 모범. 감점: 프론트 TanStack Query 미도입을 F-M1으로 다뤘으나 v1.1 이관 결정의 근거가 약함. |
| 13-security | **8.5 / 10** | OWASP Top 10 전 항목 walkthrough + `npm audit`·grep 증거 제시. Pre-ship/Ship+1/Ship+7 3단계 로드맵 구조화 양호. 감점: `pom.xml 언급은 리포 구조와 불일치(Gradle 사용)` 자체 지적은 정직하나, 해당 오탐이 존재했다는 점에서 교정. Backend 자동 의존성 스캔 결과 부재. |

## 8. 최종 권고

**인간 승인 #3 — 조건부 가결 (Conditional Approve) 권고.**

### 가결 조건 (Phase 5 진입 직전 확인)
1. B-C1/F-H1/HIGH-1 `NEXT_PUBLIC_ADMIN_API_KEY` 번들 제거 — Next Route Handler 또는 v1 한정 읽기 전용 `/settings` 다운그레이드.
2. B-H1 `MarketDataPersistService` 분리 + public `@Transactional`.
3. B-H2 `persistAll` 데드 코드 삭제.
4. B-H3 배치 멱등성(`existsByStockIdAndTradingDate` 기반 skip 또는 upsert).
5. 차단 4건 수정 후 29개 기존 테스트 회귀 통과 확인 + 재수집 멱등성 통합 테스트 1종 추가.

### Ship+48h 내 핫픽스 허용
- MED-1 Rate limiting (Bucket4j)
- MED-2 Actuator `info/metrics` 노출 축소 (prod `health`만)
- MED-3 보안 응답 헤더 3종
- B-M1 BacktestController 검증 응답 표준화
- LOW-2 관리자 401 WARN 로깅

### Sprint 5 첫 번째 태스크(배포 직후)
- 프론트엔드 Vitest + RTL + MSW 하네스 + P1 스모크 3종 (QA §8.1)
- JaCoCo 플러그인 + CI 커버리지 리포트 아카이브
- Hibernate statistics 기반 N+1 회귀 테스트 2종

### 반려 사유가 있다면
차단 4건 중 B-C1을 제외한 3건(B-H1/H2/H3)은 "수동 재수집이 없으면 당장 표출되지 않음"이므로 운영 초기 엄격 금지만으로 단기 회피 가능하다. 그러나 **B-C1은 배포 순간 즉시 실재 리스크로 전환**되므로 단독으로도 반려 사유에 해당한다. B-C1이 해소되지 않은 상태에서는 절대 가결하지 말 것.

---

**최종 점수 7.6 / 10 · 판정 CONDITIONAL · 인간 승인 #3 조건부 가결 권고.**
