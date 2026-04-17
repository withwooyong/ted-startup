---
agent: "07-db"
stage: "04-db-schema"
version: "1.0.0"
created_at: "2026-04-16T15:30:00+09:00"
quality_gate_passed: false
---

# 쿼리 전략 자동 추천 — Spring Data JPA 3단계

## 전략 평가 기준

| Entity 그룹 | 동적조건 | JOIN깊이 | DB전용 | 집계 | → 추천 전략 |
|-------------|---------|---------|--------|------|------------|
| Stock | 0~2개 | 0 | X | 없음 | **Level 1** |
| Signal | 2~3개 | 1 (→Stock) | JSONB | 낮음 | **Level 2+3** |
| StockPrice | 1개 | 1 (→Stock) | X | 없음 | **Level 1** |
| LendingBalance | 2~3개 | 1 (→Stock) | X | 중간 | **Level 2** |
| ShortSelling | 1~2개 | 1 (→Stock) | X | 낮음 | **Level 1** |
| BacktestResult | 1개 | 0 | X | 없음 | **Level 1** |
| BatchJobLog | 1~2개 | 0 | X | 없음 | **Level 1** |

---

## Entity별 쿼리 전략

### Stock — Level 1 (JPA 메서드 이름 쿼리)

```java
public interface StockRepository extends JpaRepository<Stock, Long> {
    Optional<Stock> findByStockCodeAndDeletedAtIsNull(String stockCode);
    List<Stock> findByMarketTypeAndIsActiveTrueAndDeletedAtIsNull(String marketType);
    List<Stock> findByStockNameContainingAndDeletedAtIsNull(String keyword);
}
```

### StockPrice — Level 1

```java
public interface StockPriceRepository extends JpaRepository<StockPrice, Long> {
    List<StockPrice> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
        Long stockId, LocalDate from, LocalDate to);
    Optional<StockPrice> findByStockIdAndTradingDate(Long stockId, LocalDate date);
}
```

### LendingBalance — Level 2 (@Query JPQL)

```java
public interface LendingBalanceRepository extends JpaRepository<LendingBalance, Long> {
    // Level 1: 기본 조회
    List<LendingBalance> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
        Long stockId, LocalDate from, LocalDate to);

    // Level 2: 급감 종목 탐지 (동적 임계값)
    @Query("""
        SELECT lb FROM LendingBalance lb
        JOIN FETCH lb.stock s
        WHERE lb.tradingDate = :date
          AND lb.changeRate < :threshold
          AND s.isActive = true
          AND s.deletedAt IS NULL
        ORDER BY lb.changeRate ASC
        """)
    List<LendingBalance> findRapidDecline(
        @Param("date") LocalDate date,
        @Param("threshold") BigDecimal threshold);

    // Level 2: 연속 감소 종목
    @Query("""
        SELECT lb FROM LendingBalance lb
        JOIN FETCH lb.stock s
        WHERE lb.tradingDate = :date
          AND lb.consecutiveDecreaseDays >= :minDays
          AND s.isActive = true
        ORDER BY lb.consecutiveDecreaseDays DESC
        """)
    List<LendingBalance> findConsecutiveDecrease(
        @Param("date") LocalDate date,
        @Param("minDays") int minDays);
}
```

### ShortSelling — Level 1

```java
public interface ShortSellingRepository extends JpaRepository<ShortSelling, Long> {
    List<ShortSelling> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
        Long stockId, LocalDate from, LocalDate to);
    Optional<ShortSelling> findByStockIdAndTradingDate(Long stockId, LocalDate date);
}
```

### Signal — Level 2 + Level 3 (JSONB)

```java
public interface SignalRepository extends JpaRepository<Signal, Long> {
    // Level 1: 날짜별 시그널
    List<Signal> findBySignalDateOrderByScoreDesc(LocalDate date);

    // Level 2: 타입 필터 + 날짜
    @Query("""
        SELECT s FROM Signal s
        JOIN FETCH s.stock st
        WHERE s.signalDate = :date
          AND (:type IS NULL OR s.signalType = :type)
        ORDER BY s.score DESC
        """)
    List<Signal> findByDateAndType(
        @Param("date") LocalDate date,
        @Param("type") String type);

    // Level 2: 종목별 시그널 이력
    List<Signal> findByStockIdAndSignalDateBetweenOrderBySignalDateDesc(
        Long stockId, LocalDate from, LocalDate to);

    // Level 3: JSONB 검색 (스코어 근거 상세)
    @Query(value = """
        SELECT * FROM signal
        WHERE signal_date = :date
          AND detail->>'balanceChangeRate' IS NOT NULL
          AND CAST(detail->>'balanceChangeRate' AS NUMERIC) < :threshold
        ORDER BY score DESC
        """, nativeQuery = true)
    List<Signal> findByDetailThreshold(
        @Param("date") LocalDate date,
        @Param("threshold") BigDecimal threshold);
}
```

### BacktestResult — Level 1

```java
public interface BacktestResultRepository extends JpaRepository<BacktestResult, Long> {
    List<BacktestResult> findBySignalTypeOrderByCreatedAtDesc(String signalType);
    Optional<BacktestResult> findFirstBySignalTypeOrderByCreatedAtDesc(String signalType);
}
```

### BatchJobLog — Level 1

```java
public interface BatchJobLogRepository extends JpaRepository<BatchJobLog, Long> {
    Optional<BatchJobLog> findFirstByJobNameOrderByStartedAtDesc(String jobName);
    List<BatchJobLog> findByJobNameAndStatusOrderByStartedAtDesc(String jobName, String status);
}
```

---

## 요약

| 전략 | 사용 Entity | 비율 |
|------|------------|------|
| Level 1 (메서드 이름) | Stock, StockPrice, ShortSelling, BacktestResult, BatchJobLog | 71% |
| Level 2 (@Query JPQL) | LendingBalance, Signal | 26% |
| Level 3 (Native Query) | Signal (JSONB 검색) | 3% |

**QueryDSL 미사용** — 동적 조건이 2~3개 수준이므로 JPQL + `@Param`으로 충분.
