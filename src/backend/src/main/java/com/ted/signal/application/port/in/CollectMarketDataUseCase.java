package com.ted.signal.application.port.in;

import java.time.LocalDate;

public interface CollectMarketDataUseCase {

    CollectionResult collectAll(LocalDate date);

    record CollectionResult(
            int stockPriceCount,
            int shortSellingCount,
            int lendingBalanceCount,
            int newStockCount,
            long elapsedMs
    ) {}
}
