package com.ted.signal.application.port.in;

import com.ted.signal.domain.enums.SignalType;

import java.time.LocalDate;
import java.util.List;

public interface GetSignalsUseCase {

    List<SignalResult> getSignals(LocalDate date, SignalType type);

    record SignalResult(
            Long signalId,
            String stockCode,
            String stockName,
            String marketType,
            String signalType,
            int score,
            String grade,
            double balanceChangeRate,
            double volumeChangeRate,
            int consecutiveDecreaseDays,
            LocalDate signalDate
    ) {}
}
