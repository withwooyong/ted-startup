package com.ted.signal.application.port.in;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

public interface GetBacktestResultsUseCase {

    List<BacktestSummary> getLatestResults();

    record BacktestSummary(
            String signalType,
            LocalDate periodStart,
            LocalDate periodEnd,
            int totalSignals,
            int hitCount5d,
            BigDecimal hitRate5d,
            BigDecimal avgReturn5d,
            int hitCount10d,
            BigDecimal hitRate10d,
            BigDecimal avgReturn10d,
            int hitCount20d,
            BigDecimal hitRate20d,
            BigDecimal avgReturn20d
    ) {}
}
