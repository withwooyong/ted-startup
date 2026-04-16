package com.ted.signal.application.port.in;

import java.time.LocalDate;

public interface RunBacktestUseCase {

    BacktestExecutionResult execute(LocalDate from, LocalDate to);

    record BacktestExecutionResult(
            int totalSignalsProcessed,
            int returnsCalculated,
            int backtestResultsSaved,
            long elapsedMs
    ) {}
}
