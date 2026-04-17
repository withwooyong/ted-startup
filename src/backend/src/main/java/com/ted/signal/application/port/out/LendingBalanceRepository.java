package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.LendingBalance;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface LendingBalanceRepository extends JpaRepository<LendingBalance, Long> {

    List<LendingBalance> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
            Long stockId, LocalDate from, LocalDate to);

    Optional<LendingBalance> findByStockIdAndTradingDate(Long stockId, LocalDate date);

    @Query("SELECT lb FROM LendingBalance lb JOIN FETCH lb.stock WHERE lb.tradingDate = :date")
    List<LendingBalance> findAllByTradingDate(@Param("date") LocalDate date);

    @Query("""
            SELECT lb FROM LendingBalance lb
            WHERE lb.stock.id IN :stockIds
              AND lb.tradingDate BETWEEN :from AND :to
            """)
    List<LendingBalance> findAllByStockIdsAndTradingDateBetween(
            @Param("stockIds") Collection<Long> stockIds,
            @Param("from") LocalDate from,
            @Param("to") LocalDate to);

    boolean existsByStockIdAndTradingDate(Long stockId, LocalDate date);

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
