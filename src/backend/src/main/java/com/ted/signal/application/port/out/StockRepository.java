package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.Stock;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface StockRepository extends JpaRepository<Stock, Long> {

    Optional<Stock> findByStockCodeAndDeletedAtIsNull(String stockCode);

    List<Stock> findByMarketTypeAndIsActiveTrueAndDeletedAtIsNull(String marketType);

    List<Stock> findByIsActiveTrueAndDeletedAtIsNull();

    List<Stock> findByStockNameContainingAndDeletedAtIsNull(String keyword);

    boolean existsByStockCode(String stockCode);
}
