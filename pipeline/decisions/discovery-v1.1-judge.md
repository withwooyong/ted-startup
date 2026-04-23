---
agent: "00-judge"
stage: "discovery-evaluation"
iteration: "v1.1"
version: "1.0.0"
created_at: "2026-04-23T15:45:00+09:00"
evaluated_artifacts:
  - "pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md"
  - "pipeline/artifacts/02-prd/sprint-plan-v1.1-chart-upgrade.md"
rubric: "ISO 25010 / CMMI 5차원"
verdict: "PASS"
score: 9.10
---

# Judge Report — v1.1 Discovery 평가

## 종합 판정

| 차원 | 가중치 | 점수 (초기) | PoC 후 점수 | 가중점수 |
|---|---:|---:|---:|---:|
| 완전성 (Completeness) | 25% | 9.0 | 9.0 | 2.25 |
| 일관성 (Consistency) | 25% | 9.5 | 9.5 | 2.375 |
| 정확성 (Accuracy) | 20% | 8.5 | **9.0** | **1.80** |
| 명확성 (Clarity) | 15% | 9.0 | 9.0 | 1.35 |
| 실행가능성 (Actionability) | 15% | 9.5 | 9.5 | 1.425 |
| **합계** | **100%** | **9.10** | **9.20** | **9.20 / 10** |

**판정: PASS** (기준 ≥ 8.0)

### 2026-04-23 PoC 스파이크 결과 반영
- **RISK-C01** (KRX 실데이터) → ✅ **해소**: DB 쿼리로 005930 753 거래일 100% OHLC + 최근 90일 62/62 확인. 마지막 1건 0값 방어 로직 A2 에 반영 (+0.25d).
- **RISK-C02** (lightweight-charts v5 multi-pane) → ✅ **완전 해소**: node_modules `typings.d.ts:1689,1932` 에서 `addPane` / `IPane.setHeight` 확인 + JSDoc 3-pane 예시 (`typings.d.ts:2002-2004`). A1 공수(0.5d) 흡수.
- **RISK-C03** (FE 지표 성능) → ⏳ 미검증 (Sprint B 자연 모니터링 유지).
- 정확성 8.5 → **9.0** (2 개 핵심 가정 실데이터/실라이브러리로 검증됨).

## 차원별 평가

### 1. 완전성 — 9.0 / 10
**강점**
- Requirements: user_stories 12 개, FR 12 개, NFR 8 개, Risk 5 개, MVP scope included/deferred 명확. biz-analyst 스키마 모든 필드 충족.
- PRD: 8 섹션 (개요/타겟/기능/UX/기술/KPI/Risk/의존성) + Out of Scope 명시.
- Sprint Plan: RICE 스코어링 표, 2 스프린트 태스크 분해, Gate A/B 체크리스트, 크리티컬 패스, 승인 게이트.

**감점 요인**
- Marketing/CRM 산출물 생략 (옵션 β 선택). 이번 이터레이션 성격(내부 제품 기술 고도화)상 타당한 생략이지만, `/plan` 스킬의 **형식적 완전성** 에서는 −1.0.

### 2. 일관성 — 9.5 / 10
**강점**
- 12 × US-C → 12 × FR-C 전부 1:1 매핑.
- FR-C → Sprint task 매핑 (FR-C01→A2, FR-C02/03→A3/A4, FR-C04→A5, FR-C05→B1/B3, FR-C06→B2/B4, FR-C07→B5, FR-C08→B6, FR-C09→A6, FR-C10→A7, FR-C11→B7, FR-C12→A8) 확인.
- MVP scope (included/deferred) 가 3 문서에서 동일. RSI/MACD 포함 + Bollinger 배제 일관.
- v1.0 시각 언어 (한국 증시 색 관례, `#131720` 배경, lightweight-charts v5) 상속 일관.

**감점 요인**
- Roadmap v1.4 drawing tools 에서 "lightweight-charts 는 공식 지원하지 않음" 언급 — 사실 여부 재확인 필요 (−0.5).

### 3. 정확성 — 8.5 / 10
**검증됨**
- `src/backend_py/app/adapter/web/_schemas.py:55-62` `StockPricePoint` 의 open/high/low/volume 필드 존재 확인.
- `src/backend_py/app/adapter/out/external/krx_client.py:229-231` 시가/고가/저가 파싱 확인.
- NFR 기준값 (Perf 95, A11y 100, LCP 1902ms) 은 `docs/lighthouse-scores.md` 최신 측정과 일치.
- SMA/RSI/MACD 계산 복잡도 O(n) 기술적으로 정확.

**감점 요인 (−1.5)**
- **lightweight-charts v5 `addPane` API 미검증** — PRD §5.2, Sprint A1 PoC 로 리스크 관리되고 있으나, 전제 자체가 미검증 상태로 Sprint 공수 추정에 반영됨. PoC 실패 시 대안(priceScaleId 분리) 공수 +0.5d 명시로 완화됨.
- KRX 익명 차단 블로커로 실 OHLCV 데이터 비어있을 가능성 — Risk C-01 로 명시되어 있으나, **실제 DB 쿼리 결과**(005930 최근 30일 open_price IS NOT NULL count)를 선행 점검 권장. 현재는 가정 단계.

### 4. 명확성 — 9.0 / 10
**강점**
- YAML 스키마 + 표 + ASCII 와이어프레임 혼합 포맷 — 독자 그룹별(엔지니어/PM) 접근성 모두 양호.
- 각 Task 에 파일 경로 + 예상 공수 명시.
- Gate 체크리스트 체크박스 형태로 구조화.
- 용어 통일 (페인, 오버레이, 토글, 영속화).

**감점 요인**
- PRD §4 ASCII 와이어프레임은 GitHub 웹 렌더링 시 등폭 폰트 가정 — 편집 툴 따라 깨질 수 있음. Figma/Excalidraw 이미지 병행 권장 (−1.0).

### 5. 실행가능성 — 9.5 / 10
**강점**
- Sprint A 5.5d / Sprint B 6.3d — 합 11.8d, 3주 예산 내 정합.
- 신규 파일 경로 구체적: `src/lib/indicators/{sma,rsi,macd}.ts`, `src/frontend/src/components/IndicatorTogglePanel.tsx`, `src/lib/hooks/useIndicatorPreferences.ts`, `src/components/charts/StockChartAccessibilityTable.tsx`.
- 의존성 선행 검증 상태 표 포함.
- RISK 완화 전략이 Sprint task 에 반영 (A1 PoC, A8 회귀 테스트, B6 zod 검증).
- 바로 `/design` (Phase 2) 또는 `/develop` (Phase 3) 진입 가능.

**감점 요인**
- QA 공수(B10 0.5d) 가 회귀 시나리오 범위 대비 타이트해 보임 — A/B 2 스프린트 모두 영향 받는 통합 QA 는 하루 이상 권장 (−0.5).

## 크로스 체크

| 항목 | 결과 |
|---|---|
| 모든 US → FR 매핑 | ✅ 12/12 |
| 모든 FR → Sprint Task 매핑 | ✅ 12/12 |
| PRD 기능 → 화면 설계 | ⚠️ ASCII 와이어프레임만 — 본격 Design Spec 은 Phase 2 (03-design-spec) 에서 작성 |
| 데이터 요구사항 → DB 스키마 | ✅ 기존 `stock_price` 테이블 OHLCV 충족, 추가 마이그레이션 없음 |
| 모든 테이블 → API | ✅ 기존 `/api/stocks/{code}` 재사용 (확장 불필요) |
| v1.0 아키텍처 원칙과 정합 | ✅ Hexagonal / FE 계산 / 번들 경량 |

## 개선 권고 (Conditional 이 아닌 PASS 이후 선택)

1. **PoC A1 선행 이관**: Sprint A 시작 전 별도 30 분 스파이크로 lightweight-charts v5 multi-pane 가능 여부 확인. 실패 시 Sprint A 공수 +0.5d 로 조정.
2. **실 OHLCV 데이터 샘플 쿼리**: Sprint 착수 전 `SELECT COUNT(*) FROM stock_price WHERE stock_id=(005930 id) AND open_price IS NOT NULL AND trading_date >= now()-interval '90 days';` 확인. 0 rows 면 seed 재생성 결정.
3. **B10 QA 공수 상향**: 0.5d → 1.0d. 시그널 마커 회귀 + 지표 on/off 조합 × 3 브라우저 × 모바일 실기기 2 종은 최소 1 일.
4. **Figma 와이어프레임**: v1.2 PRD 부터는 이미지 링크 병행 권장.

## 다음 단계 결정

**Phase 2 Design** 으로 진입 가능. 다만 이번 이터레이션은 FE 전용 고도화라 `06-design` 은 경량 (UX 와이어프레임 1 장) 으로 처리하고 바로 `/develop` 병행 고려. `07-db` 는 생략 (스키마 변경 없음).

권장 순서:
```
현재 → /design (경량, 06-design-system wireframe 1 장)
     → /develop (Sprint A 착수)
     → /test (회귀 + Lighthouse)
     → /deploy (v1.1 태그)
```

또는 사용자가 `/ted-run` 파이프라인으로 Sprint A 의 첫 태스크부터 즉시 구현 착수하는 것도 가능 (요구사항이 충분히 잘게 분해되어 있음).
