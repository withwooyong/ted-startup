package com.ted.signal.application.port.in;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

public interface GetStockDetailUseCase {

    StockDetail getStockDetail(String stockCode, LocalDate from, LocalDate to);

    record StockDetail(
            String stockCode,
            String stockName,
            String marketType,
            LatestPrice latestPrice,
            List<TimeSeriesPoint> timeSeries,
            List<SignalMarker> signals
    ) {}

    record LatestPrice(
            long closePrice,
            BigDecimal changeRate,
            long volume,
            long marketCap
    ) {}

    record TimeSeriesPoint(
            LocalDate date,
            long price,
            long lendingBalance
    ) {}

    record SignalMarker(
            LocalDate date,
            String signalType,
            int score,
            String grade,
            Map<String, Object> detail
    ) {}
}
