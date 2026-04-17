---
agent: "07-db"
stage: "04-db-schema"
version: "1.0.0"
created_at: "2026-04-16T15:30:00+09:00"
quality_gate_passed: false
---

# 인덱스 전략 — 공매도 커버링 시그널 탐지 시스템

## 설계 원칙
- WHERE/JOIN/ORDER BY 패턴 기반 인덱스 설계
- 파티션 키(trading_date)는 파티션 pruning으로 자동 최적화
- 복합 인덱스 우선, 단일 인덱스는 선택도 높은 경우만

## 인덱스 목록

### stock

```sql
-- 종목코드 검색 (유니크 인덱스, 테이블 생성 시 자동)
-- CREATE UNIQUE INDEX idx_stock_code ON stock(stock_code);

-- 시장 + 활성 상태 필터
CREATE INDEX idx_stock_market_active ON stock(market_type, is_active)
    WHERE deleted_at IS NULL;

-- 종목명 검색 (한글 부분 검색)
CREATE INDEX idx_stock_name_trgm ON stock
    USING gin(stock_name gin_trgm_ops);
```

### stock_price (파티션 테이블)

```sql
-- 종목별 날짜순 조회 (차트 데이터)
-- UNIQUE (stock_id, trading_date) → 파티션 생성 시 자동
-- 파티션 pruning: WHERE trading_date BETWEEN ? AND ?

-- 시가총액 순위 조회
CREATE INDEX idx_stock_price_market_cap ON stock_price(trading_date, market_cap DESC);
```

### lending_balance (파티션 테이블)

```sql
-- 종목별 날짜순 조회 (추이 차트)
-- UNIQUE (stock_id, trading_date) → 자동

-- 대차잔고 급감 종목 탐지 (시그널 엔진 쿼리)
CREATE INDEX idx_lending_change_rate ON lending_balance(trading_date, change_rate)
    WHERE change_rate < 0;

-- 연속 감소 종목 필터
CREATE INDEX idx_lending_consecutive ON lending_balance(trading_date, consecutive_decrease_days DESC)
    WHERE consecutive_decrease_days > 0;
```

### short_selling (파티션 테이블)

```sql
-- 종목별 날짜순 조회
-- UNIQUE (stock_id, trading_date) → 자동

-- 공매도 비율 상위 종목
CREATE INDEX idx_short_ratio ON short_selling(trading_date, short_ratio DESC);
```

### signal

```sql
-- 날짜별 시그널 조회 (대시보드 메인 쿼리)
CREATE INDEX idx_signal_date_type ON signal(signal_date DESC, signal_type);

-- 날짜별 스코어 정렬 (대시보드 스코어순)
CREATE INDEX idx_signal_date_score ON signal(signal_date DESC, score DESC);

-- 종목별 시그널 이력 (종목 상세 페이지)
CREATE INDEX idx_signal_stock_date ON signal(stock_id, signal_date DESC);

-- 등급 필터 (긴급 알림: A등급만)
CREATE INDEX idx_signal_grade ON signal(signal_date, grade)
    WHERE grade = 'A';
```

### backtest_result

```sql
-- 시그널 타입별 최신 결과
CREATE INDEX idx_backtest_type ON backtest_result(signal_type, created_at DESC);
```

### batch_job_log

```sql
-- 최근 실행 이력 조회
CREATE INDEX idx_batch_status ON batch_job_log(job_name, started_at DESC);
```

## 예상 데이터 규모

| 테이블 | 1년 | 3년 | 비고 |
|--------|-----|-----|------|
| stock | ~2,500 | ~2,500 | 마스터, 거의 고정 |
| stock_price | ~625K | ~1.9M | 2,500종목 × 250거래일 |
| short_selling | ~625K | ~1.9M | 동일 |
| lending_balance | ~625K | ~1.9M | 동일 |
| signal | ~5K~15K | ~15K~45K | 종목당 연 2~6건 추정 |
| backtest_result | ~100 | ~100 | 소량 |

## 파티셔닝 판단

- `stock_price`, `short_selling`, `lending_balance`: **월별 파티셔닝 적용**
  - 3년 데이터 ~1.9M행, 파티션당 ~50K행으로 적절
  - 날짜 범위 쿼리에서 파티션 pruning으로 성능 확보
- `signal`: 3년 최대 45K행 → **파티셔닝 불필요** (단순 인덱스로 충분)
- `stock`: 2,500행 → **파티셔닝 불필요**

## pg_trgm 확장 (종목명 검색)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

종목명 부분 검색 (`LIKE '%삼성%'`)에 trigram 인덱스 사용.
