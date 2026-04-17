package com.ted.signal.application.port.in;

import java.time.Instant;
import java.util.List;

public interface GetNotificationPreferenceUseCase {

    NotificationPreferenceView get();

    record NotificationPreferenceView(
            boolean dailySummaryEnabled,
            boolean urgentAlertEnabled,
            boolean batchFailureEnabled,
            boolean weeklyReportEnabled,
            int minScore,
            List<String> signalTypes,
            Instant updatedAt
    ) {}
}
