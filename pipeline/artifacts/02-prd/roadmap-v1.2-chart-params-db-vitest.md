---
agent: "02-pm"
stage: "02-prd"
version: "1.2.0"
iteration: "v1.2"
created_at: "2026-04-24T09:50:00+09:00"
depends_on:
  - "pipeline/artifacts/02-prd/prd-v1.2-chart-params-db-vitest.md"
  - "pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md"
quality_gate_passed: false
---

# Roadmap — 차트 고도화 시리즈 (v1.1 → v1.4+) — 2026-04-24 재정비

v1.1 로드맵을 상속하되 2026-04-24 v1.2 Discovery 에서 확인된 실스택(카카오 OAuth 미구현, 싱글 오퍼레이터 모델) 에 맞춰 multi-user 언급을 별 Epic 으로 분리.

## 3개월 로드맵 (2026-04 ~ 2026-07)

### v1.1 — 핵심 지표 + 토글 UX ✅ 완료 (2026-04-23)
2 스프린트 (A+B) 로 Candlestick + MA + Volume + RSI + MACD + 토글 + localStorage + 줌/팬 + OHLCV 툴팁 + sr-only 완주. 상세: `pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md`.

### v1.2 — 파라미터 편집 + DB 영속화 + Vitest 하네스 (2026-04-24 ~ 2026-05-08, 2 주)
**목표**: 파워유저 튜닝 + 기기간 동기화 + 회귀 안전망
- Bollinger Bands(20, 2σ) 추가 (US-C06 v1.1 deferred 소화)
- 지표 파라미터 편집 UI — MA(4 window) / RSI(period) / MACD(f/s/sig) / BB(period, k)
- DB 기반 설정 영속화 — **싱글톤 id=1 패턴** (NotificationPreference 상속, 멀티 유저 아님)
- Vitest + RTL + MSW 테스트 하네스 도입 + CI 통합
- 체크포인트 0 (Vitest 하네스) 선행 → 체크포인트 1~4 (BB / 파라미터 UI / DB / 회귀)

### v1.3 — 프리셋 + 알림 + 2 차 지표 (2026-05 하순 ~ 2026-06, 4 주)
**목표**: 명명 프리셋 저장/공유 + 지표 기반 자동 알림
- 지표 프리셋 템플릿 저장/로드 (swing/day/long) — indicator_preferences 스키마 확장 (payload.presets array)
- 지표 조건 기반 알림 (RSI 70/30 돌파, MACD 골든크로스, BB band touch) — NotificationPreference 확장
- Stochastic(%K, %D), ATR, ADX 2 차 지표 (요청 시)
- Playwright E2E — 편집 UI + 프리셋 시나리오
- Web Worker 지표 계산 오프로드 (조건부, v1.1 RISK-C03 모니터링 결과에 따라)

## 6개월 로드맵 (2026-04 ~ 2026-10)

### v1.4 — Drawing Tools (2026-07)
- 추세선, 피보나치, 수평/수직선
- 사용자 annotation DB 저장 (v1.2 영속화 인프라 재사용)
- lightweight-charts v5 는 drawing 공식 지원 미흡 — 착수 전 PoC 필수 (v1.1 roadmap 의 동일 주의)

### v1.5 — Multi-symbol Overlay (2026-08)
- 동일 차트에 다른 종목 상대 비교 (코스피/코스닥 지수 등)
- 상대 수익률 시리즈
- 지표 유틸 재사용

### v1.6 — 실시간 (WebSocket) (2026-09 ~ 2026-10)
- KRX 지연 시세 분봉 업데이트
- KRX 계정/인증 상태가 선결 조건 (프로젝트 메모리 `project_krx_auth_blocker`)

## 12개월 로드맵 (2026-04 ~ 2027-04)

### Q3 2026 (v1.3 ~ v1.5)
위 완료

### Q4 2026
- v1.7 포트폴리오 통합 — 보유 종목 thumbnail 차트
- v1.8 모바일 앱 WebView 최적화
- **Epic: 카카오 OAuth 2.0 도입** (multi-user 기반) — indicator_preferences 싱글톤 → user_id 연동 (대규모 마이그레이션, 별 Sprint)

### Q1 2027
- v2.0 전략 백테스트 ↔ 차트 연동 — 백테스트 시그널을 차트 마커로 주입
- v2.x AI 기반 패턴 자동 주석 (experimental)

## 의존성 맵 (v1.2 재정비)

```
v1.1 (차트 기반) ✅
  ↓
v1.2 (파라미터 + DB 영속화 + Vitest) ◀─ 현재
  │    ├─ indicator_preferences 테이블 (싱글톤)
  │    ├─ Vitest 하네스 + MSW
  │    └─ Bollinger Bands
  ↓
v1.3 (프리셋 + 알림 + 2차 지표) ←── DB 스키마 확장 (payload.presets)
  ↓
v1.4 (drawing) ←── annotation 저장 (indicator_preferences 인프라 재사용 or 별 테이블)
  ↓
v1.5 (multi-symbol) ←── 지표 유틸 재사용
  ↓
v1.6 (실시간) ←── KRX 인증 선결
  ↓
[Epic] 카카오 OAuth 2.0 ←── indicator_preferences 싱글톤 → user_id 마이그레이션 (별 Sprint)
```

## 병목/리스크 (v1.2 업데이트)

- **카카오 OAuth 미도입**: 현재 싱글 오퍼레이터 모델이라 v1.6 이후까지 영향 없음. 멀티 유저 요구 발생 시점에 Epic 으로 격상.
- **KRX 인증 블로커** (기존): v1.6 실시간 착수 조건. v1.1~v1.5 는 일봉으로 커버.
- **lightweight-charts v5 drawing 제약**: v1.4 착수 전 PoC 필수.
- **Vitest/Next 16/React 19 호환성**: v1.2 체크포인트 0 에서 해결. 미해결 시 Sprint 일정 영향.
- **모바일 앱 Phase**: v1.0 결정 "v1 은 PWA 로 대체" 유지. 네이티브 이전은 v2.x.

## v1.1 → v1.2 delta

| 항목 | v1.1 계획 (기존) | v1.2 Discovery 결과 |
|---|---|---|
| 멀티 유저 | "로그인 사용자 DB 영속화" 언급 | **싱글 오퍼레이터 + 싱글톤 id=1 패턴으로 축소** (카카오 OAuth 미도입 확인) |
| Bollinger Bands | v1.2 예정 | v1.2 MVP 포함 ✅ |
| 파라미터 편집 UI | v1.2 예정 | v1.2 MVP 포함 ✅ |
| DB 영속화 | v1.2 예정 | v1.2 MVP 포함 ✅ (싱글톤 패턴) |
| Vitest 하네스 | v1.1 post-ship 권장 → v1.2 이월 | v1.2 MVP 포함 + **체크포인트 0 선행** ✅ |
| Web Worker 오프로드 | v1.2 조건부 | v1.2 조건부 유지 (RISK-C03 모니터링 결과) |
| Stochastic/ATR | v1.2 요청 시 | **v1.3 이월** (v1.2 범위 집중) |
