---
created_at: "2026-04-24T09:00:00+09:00"
author: "user"
iteration: "v1.2"
parent_request: "pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md"
---

# v1.2 — 차트 파라미터 편집 + DB 영속화 + Vitest 하네스

## 원 요청 (2026-04-24)
> "v1.2 착수 (Bollinger Bands + 지표 파라미터 편집 UI + DB 영속화 + Vitest 하네스)"

v1.1 Discovery 의 `roadmap-v1.1-chart-upgrade.md` § "v1.2 — 확장 지표 + 커스터마이즈" 에서 사전 계획된 네 축을 한 이터레이션으로 묶어 실행.

## 해석된 의도
v1.1 에서 `/stocks/[code]` 차트가 증권사 앱 수준 정보 밀도를 달성했지만, (a) 지표 **파라미터**(MA window, RSI period, MACD(f/s/sig), BB(period/k)) 는 여전히 하드코딩이고, (b) 설정 영속화는 `localStorage:v1` 단일 브라우저에 갇혀 있으며, (c) FE 지표 계산/차트 훅에 **테스트 회귀 안전망이 없다**. v1.2 는 이 세 축을 한 세션으로 해결하고, Bollinger Bands 를 추가해 기술적 지표 라인업을 완성한다.

## 선택된 범위 — (A) 네 축 모두 포함
사용자가 명시적으로 네 축을 함께 요청. 내부 제품이므로 축소하지 않는다.

| 축 | MVP 포함 여부 | 근거 |
|---|---|---|
| Bollinger Bands(20, 2σ) FE 유틸 + 가격 페인 overlay | **O** | US-C06 (v1.1 에서 deferred) |
| 지표 파라미터 편집 UI (MA/RSI/MACD/BB) | **O** | 로드맵 v1.2 Must |
| 편집된 프리셋 localStorage:v2 스키마 마이그레이션 | **O** | v1.1 `localStorage:v1` 호환 경로 필수 |
| 편집된 프리셋 DB 영속화 (로그인 사용자) | **O** | 로드맵 v1.2 Must, 기기간 동기화 |
| Vitest + RTL + MSW 테스트 하네스 도입 | **O** | v1.1 HANDOFF "FE 테스트 하네스 미도입 → v1.2 스프린트" |
| 기존 indicators 유틸 단위 테스트 (sma/rsi/macd/aggregate/bb) | **O** | 하네스 도입 가치 입증 |
| useIndicatorPreferences 훅 테스트 + 스키마 v2 마이그레이션 회귀 | **O** | React #185 재발 방지 |
| IndicatorTogglePanel + 파라미터 편집 UI 컴포넌트 테스트 | **O** | 신규 컴포넌트 회귀 보호 |
| 지표 프리셋 템플릿 저장/공유 (swing_trader 등 명명 프리셋) | **deferred** | v1.3 (범위 안정화 후) |
| 지표 기반 알림 확장 (RSI 70 돌파 등) | **deferred** | v1.3 |
| Stochastic / ATR 등 2 차 지표 | **deferred** | v1.3+, 사용자 요청 시 |
| Web Worker 지표 계산 오프로드 | **deferred** (조건부) | v1.1 RISK-C03 모니터링 결과 따라 |

## 도메인 제약 (v1.0/v1.1 상속)
- 개인 투자자(본인)의 참고용 내부 도구, "투자 자문" 아님
- 모든 시그널/지표에 면책 고지 유지
- KRX 공개 데이터만 사용
- 번들 경량 유지 정책 (FE 지표 자체 구현 원칙 계속 — BB 포함)
- 카카오 OAuth 인증 기반 사용자 식별

## 프로세스 결정 (옵션 β + 체크포인트 0 선행)
- **옵션 β**: `/plan` 전체(biz/pm/marketing/crm) 가 아닌 **biz-analyst + pm + judge 만** 실행. 내부 제품 기술 고도화 성격 유지 (v1.1 과 동일).
- **체크포인트 0 Vitest 선행**: Bollinger / 파라미터 UI / DB 영속화 구현은 회귀 리스크가 v1.1 보다 크다 (스키마 마이그레이션, BE 왕복, 파라미터 매트릭스 조합 폭증). 따라서 **체크포인트 0 에 Vitest+RTL+MSW 하네스를 세우고 기존 indicators 유틸 단위 테스트부터 작성** 한 뒤 이후 기능 구현 체크포인트마다 테스트 동반 진행.

## 사전 확인된 기술 전제 (2026-04-24)
- 백엔드 스택: FastAPI + SQLAlchemy 2.0 async + Alembic (현재 `008_brokerage_credential` 까지, v1.2 는 `009_indicator_preferences` 신규)
- 프론트엔드: Next.js 16 + React 19, Vitest **미설치** — 도입 시 vitest / @testing-library/react / @testing-library/jest-dom / @testing-library/user-event / msw / jsdom 신규
- 인증: **카카오 OAuth 는 현재 미구현**, 백엔드는 `X-API-Key` (ADMIN_API_KEY) 어드민 단일 인증. FE 는 Next.js Route Handler 가 서버 측에서 키 주입(`/api/admin/notifications/preferences` 선례). DB 프리셋은 NotificationPreference(id=1) 싱글톤 패턴 상속 예정 (CLAUDE.md 의 "카카오 OAuth 2.0" 언급은 로드맵 레벨 — 실구현은 미완)
- 기존 자산: `src/frontend/src/lib/indicators/{sma,rsi,macd,aggregate,index}.ts`, `useIndicatorPreferences.ts` (`localStorage:v1`), `IndicatorTogglePanel.tsx`
