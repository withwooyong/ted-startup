package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.StockPrice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface StockPriceRepository extends JpaRepository<StockPrice, Long> {

    List<StockPrice> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
            Long stockId, LocalDate from, LocalDate to);

    Optional<StockPrice> findByStockIdAndTradingDate(Long stockId, LocalDate date);

    boolean existsByStockIdAndTradingDate(Long stockId, LocalDate date);

    @Query("SELECT sp FROM StockPrice sp JOIN FETCH sp.stock WHERE sp.tradingDate = :date")
    List<StockPrice> findAllByTradingDate(@Param("date") LocalDate date);

    @Query("""
            SELECT sp FROM StockPrice sp
            WHERE sp.stock.id IN :stockIds
              AND sp.tradingDate BETWEEN :from AND :to
            """)
    List<StockPrice> findAllByStockIdsAndTradingDateBetween(
            @Param("stockIds") Collection<Long> stockIds,
            @Param("from") LocalDate from,
            @Param("to") LocalDate to);
}
