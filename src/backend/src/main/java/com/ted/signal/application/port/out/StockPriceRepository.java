package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.StockPrice;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface StockPriceRepository extends JpaRepository<StockPrice, Long> {

    List<StockPrice> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
            Long stockId, LocalDate from, LocalDate to);

    Optional<StockPrice> findByStockIdAndTradingDate(Long stockId, LocalDate date);

    boolean existsByStockIdAndTradingDate(Long stockId, LocalDate date);
}
