package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.ShortSelling;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface ShortSellingRepository extends JpaRepository<ShortSelling, Long> {

    List<ShortSelling> findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
            Long stockId, LocalDate from, LocalDate to);

    Optional<ShortSelling> findByStockIdAndTradingDate(Long stockId, LocalDate date);

    boolean existsByStockIdAndTradingDate(Long stockId, LocalDate date);

    @Query("SELECT ss FROM ShortSelling ss JOIN FETCH ss.stock WHERE ss.tradingDate = :date")
    List<ShortSelling> findAllByTradingDate(@Param("date") LocalDate date);
}
