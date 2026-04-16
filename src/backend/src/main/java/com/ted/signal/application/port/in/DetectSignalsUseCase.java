package com.ted.signal.application.port.in;

import java.time.LocalDate;

public interface DetectSignalsUseCase {

    DetectionResult detectAll(LocalDate date);

    record DetectionResult(
            int rapidDeclineCount,
            int trendReversalCount,
            int shortSqueezeCount,
            long elapsedMs
    ) {}
}
