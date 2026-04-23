---
agent: "02-pm"
stage: "02-prd"
version: "1.1.0"
iteration: "v1.1"
created_at: "2026-04-23T15:30:00+09:00"
depends_on:
  - "pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md"
quality_gate_passed: false
---

# Roadmap — 차트 고도화 시리즈 (v1.1 → v1.3)

## 3개월 로드맵 (2026-04 ~ 2026-07)

### v1.1 — 핵심 지표 + 토글 UX (2026-04, 3주)
**목표**: 증권사 앱 수준의 기술적 지표 기반 분석 가능
- Candlestick 전환
- MA(5/20/60/120) 오버레이
- 거래량 / RSI / MACD 페인
- 지표 on/off 토글 + localStorage 영속화
- OHLCV hover 툴팁, 줌/팬

### v1.2 — 확장 지표 + 커스터마이즈 (2026-05, 3주)
**목표**: 파워유저 니즈 커버
- Bollinger Bands(20, 2σ) 추가 (US-C06)
- 지표 파라미터 편집 UI (MA 기간, RSI 기간, MACD (fast,slow,signal))
- DB 기반 설정 영속화 + 기기간 동기화 (로그인 사용자)
- Stochastic, ATR 등 2차 지표 옵션 (요청 시)
- Web Worker 지표 계산 오프로드 (렌더 성능 이슈 발생 시)

### v1.3 — 알림 + 템플릿 (2026-06 ~ 2026-07, 4주)
**목표**: 차트 기반 자동 발견 → 알림
- 지표 조건 기반 알림 (예: RSI 70 돌파, MACD 골든크로스)
- 지표 프리셋 템플릿 저장/공유 (`swing_trader_v1`, `day_trader_v1`)
- 기존 텔레그램 알림 채널 연동
- 포트폴리오 보유 종목에 대한 자동 watchlist 지표 추적

## 6개월 로드맵 (2026-04 ~ 2026-10)

### v1.4 — Drawing Tools (2026-08)
- 추세선, 피보나치, 수평/수직선
- 사용자 annotation localStorage 저장

### v1.5 — Multi-symbol Overlay (2026-09)
- 동일 차트에 다른 종목 상대 비교 (코스피 지수 등)
- 상대 수익률 시리즈

### v1.6 — 실시간 (WebSocket) (2026-10)
- KRX 지연 시세 5분봉 업데이트
- 장중 라이브 차트 (v1.0 ~ v1.5 는 일봉 기준)
- 실시간 조건은 KRX 계정/인증 상태 선결

## 12개월 로드맵 (2026-04 ~ 2027-04)

### Q3 2026 (v1.3 ~ v1.5)
위 v1.3~v1.5 완료

### Q4 2026
- v1.7 포트폴리오 통합 — 보유 종목 thumbnail 차트
- v1.8 모바일 앱 WebView 최적화

### Q1 2027
- v2.0 전략 백테스트 ↔ 차트 연동 — 백테스트 시그널을 차트 마커로 주입
- v2.x AI 기반 패턴 자동 주석 (experimental)

## 의존성 맵

```
v1.1 (차트 기반)
  ↓ 지표 계산 유틸
v1.2 (파라미터 + DB 영속화) ────┐
  ↓                         │
v1.3 (알림 + 템플릿) ←───── DB 영속화 필요
  ↓
v1.4 (drawing) ←── annotation 저장 필요 (localStorage 시작, DB 확장)
  ↓
v1.5 (multi-symbol) ←── 지표 유틸 재사용
  ↓
v1.6 (실시간) ←── KRX 계정 + WebSocket 인프라
```

## 병목/리스크
- **KRX 인증 블로커** (프로젝트 메모리): v1.6 실시간 착수 조건. v1.1~v1.5 는 일봉으로 커버.
- **lightweight-charts v5 제약**: v1.4 drawing tools 는 lightweight-charts 가 공식 지원하지 않음. 대안으로 canvas overlay 직접 구현 또는 다른 라이브러리 평가 (v1.4 착수 전 PoC 필수).
- **모바일 앱 Phase**: v1.0 HANDOFF 에서 "v1 은 PWA 로 대체" 결정. 네이티브 앱 이전 시점은 사용자 기반 확보 후 (v2.x).
