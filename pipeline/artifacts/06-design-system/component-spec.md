---
agent: "06-design"
stage: "06-design-system"
version: "1.0.0"
created_at: "2026-04-16T15:30:00+09:00"
depends_on:
  - "pipeline/artifacts/03-design-spec/feature-spec.md"
  - "pipeline/artifacts/06-design-system/design-tokens.json"
quality_gate_passed: false
---

# 컴포넌트 명세서 — 공매도 커버링 시그널 탐지 시스템

## 적용 컨벤션
- 토스 디자인 시스템(TDS) 기반
- 에러/빈 상태 메시지: 해요체 ("시그널이 없어요")
- 다크모드 자동 대응
- 접근성 5대 규칙 적용

---

## 1. SignalCard

시그널 리스트의 개별 항목 카드.

| 속성 | 타입 | 설명 |
|------|------|------|
| stockCode | string | 종목코드 (6자리) |
| stockName | string | 종목명 |
| signalType | 'rapid_decline' \| 'trend_reversal' \| 'short_squeeze' | 시그널 타입 |
| score | number (0~100) | 숏스퀴즈 스코어 |
| grade | 'A' \| 'B' \| 'C' \| 'D' | 등급 |
| balanceChangeRate | number | 대차잔고 변동률 (%) |
| volumeChangeRate | number | 거래량 변동률 (%) |
| consecutiveDays | number | 연속 감소일수 |

### 스타일
- 배경: `neutral.0` (light) / `dark.surface` (dark)
- 테두리: `neutral.200` / `dark.border`
- 등급 배지 색상: `signal.gradeA~D`
- 호버: `shadow.md` + 미세한 translateY(-2px)
- 클릭: 종목 상세 페이지 이동
- border-radius: `lg` (12px)

### 접근성
- role="article", aria-label="[종목명] [시그널타입] 스코어 [점수]점"
- 키보드 Enter/Space로 클릭 가능

---

## 2. SignalFilterTabs

시그널 타입별 필터 탭.

| 속성 | 타입 | 설명 |
|------|------|------|
| activeFilter | string | 현재 활성 필터 |
| counts | Record<string, number> | 타입별 건수 |
| onChange | (filter: string) => void | 필터 변경 콜백 |

### 탭 목록
- 전체 (ALL) | 급감 (RAPID_DECLINE) | 추세전환 (TREND_REVERSAL) | 숏스퀴즈 (SHORT_SQUEEZE)

### 스타일
- 활성 탭: `primary.500` 텍스트 + 밑줄
- 비활성: `neutral.500` 텍스트
- 건수 배지: `neutral.100` 배경 + `neutral.700` 텍스트

### 접근성
- role="tablist", 각 탭은 role="tab"
- aria-selected로 활성 상태 표시

---

## 3. DualAxisChart

대차잔고 + 주가 듀얼 축 차트 (Recharts ComposedChart 기반).

| 속성 | 타입 | 설명 |
|------|------|------|
| data | Array<{date, price, balance}> | 시계열 데이터 |
| signals | Array<{date, type, score}> | 시그널 마커 |
| period | '1M' \| '3M' \| '6M' \| '1Y' | 조회 기간 |

### 스타일
- 주가 라인: `chart.priceLineColor` (#3182F6), 실선
- 대차잔고 라인: `chart.balanceLineColor` (#FF6D1A), 점선
- 시그널 마커: `chart.signalMarkerColor` (#F04452), 원형 점
- 그리드: `chart.gridColor`
- 툴팁: `chart.tooltipBg` + `chart.tooltipText`

### 접근성
- aria-label="[종목명] 주가 및 대차잔고 추이 차트"
- 차트 하단에 "데이터 테이블 보기" 토글 (시각 장애인 대응)

---

## 4. ScoreBreakdown

숏스퀴즈 스코어 산출 근거 표시.

| 속성 | 타입 | 설명 |
|------|------|------|
| factors | Array<{name, value, maxScore, score}> | 점수 항목 |
| totalScore | number | 총점 |
| grade | string | 등급 |

### 스타일
- 프로그레스 바: 각 항목별 `primary.500` 게이지
- 총점: `2xl` bold, 등급 색상 적용
- 카드 형태: `shadow.sm`, `borderRadius.lg`

---

## 5. BacktestTable

백테스팅 결과 요약 테이블.

| 속성 | 타입 | 설명 |
|------|------|------|
| results | Array<{signalType, count, hitRate, avgReturn5d, avgReturn10d, avgReturn20d}> | 결과 |

### 스타일
- 적중률 60%+: `semantic.success` 텍스트
- 적중률 50~60%: `semantic.warning` 텍스트
- 적중률 <50%: `semantic.error` 텍스트
- 양의 수익률: `stock.up`, 음의 수익률: `stock.down`
- 헤더: `neutral.50` 배경, `fontWeight.semibold`

### 접근성
- caption="시그널 타입별 백테스팅 결과"
- scope="col" / scope="row" 적용

---

## 6. DisclaimerFooter

면책 고지 고정 표시 컴포넌트.

### 내용
```
⚠️ 본 시스템은 투자 자문이 아닌 정보 제공 목적의 참고 도구입니다.
모든 투자 판단과 그에 따른 결과의 책임은 투자자 본인에게 있습니다.
과거 성과가 미래 수익을 보장하지 않습니다.
```

### 스타일
- 배경: `neutral.50` / `dark.bg`
- 텍스트: `neutral.600`, `fontSize.sm`
- padding: `md` (16px)
- 전체 너비 고정, 항상 페이지 하단
- 비활성화 불가 (props 없음)

---

## 7. EmptyState

빈 상태 표시 컴포넌트.

| 속성 | 타입 | 설명 |
|------|------|------|
| title | string | 제목 (해요체) |
| description | string | 부가 설명 |
| action | { label: string, onClick: () => void } | 선택적 액션 버튼 |

### 스타일
- 아이콘: `neutral.300`, 48px
- 제목: `neutral.800`, `fontSize.lg`, `fontWeight.medium`
- 설명: `neutral.500`, `fontSize.sm`
- 수직 중앙 정렬, `spacing.xl` 간격
