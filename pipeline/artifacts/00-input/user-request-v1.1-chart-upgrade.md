---
created_at: "2026-04-23T15:00:00+09:00"
author: "user"
iteration: "v1.1"
parent_request: "pipeline/artifacts/00-input/user-request.md"
---

# v1.1 — `/stocks/[code]` 차트 고도화

## 원 요청 (2026-04-23)
> "트레이딩뷰 차트를 주식차트 처럼 (이동평균선, 거래량, 기타지표 등이 표시될 수 있게) 고도화 하자."

## 해석된 의도
v1.0 배포로 `/stocks/[code]` 상세 페이지에 TradingView Lightweight Charts v5 가 도입됐지만, 현재는 **AreaSeries 단일 + 시그널 마커** 수준. 업계 표준(증권사 앱, 트레이딩뷰 웹) 수준의 정보 밀도로 끌어올려 "시그널 해석"을 차트 한 화면에서 완결하려는 의도.

## 선택된 범위 — (C) 풀 스택
사용자와 대화를 통해 확정된 범위:

| 축 | MVP 포함 여부 |
|---|---|
| 가격 표시 방식 (Candlestick 전환) | **O** |
| 오버레이 지표 (MA 5/20/60/120) | **O** |
| 하단 페인 거래량 히스토그램 | **O** |
| RSI(14) 별도 페인 | **O** |
| MACD(12,26,9) 별도 페인 | **O** |
| Bollinger Bands | **deferred** |
| 지표 on/off 토글 UI | **O** |
| 지표 파라미터(기간 등) 사용자 편집 | **deferred** (기본값 고정) |
| 설정 영속화 (localStorage) | **O** |
| 설정 영속화 (DB) | **deferred** |
| 줌/팬 인터랙션 활성화 | **O** |
| OHLCV hover 툴팁 | **O** |

## 도메인 제약 (v1.0 상속)
- 개인 투자자(본인)의 참고용 내부 도구
- "투자 자문" 아님, "정보 제공 도구"임
- 모든 시그널/지표에 면책 고지 유지
- KRX 공개 데이터만 사용
- 추가 외부 의존성 최소화 (지표 계산은 FE 측에서 수행)

## 프로세스 결정 (옵션 β)
`/plan` 전체(biz/pm/marketing/crm)가 아닌 **biz-analyst + pm + judge 만** 실행. 내부 제품의 기술 고도화 성격상 GTM/고객여정 산출물은 이번 이터레이션에서 기여도 낮음.
