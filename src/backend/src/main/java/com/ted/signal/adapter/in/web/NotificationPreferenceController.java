package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.GetNotificationPreferenceUseCase;
import com.ted.signal.application.port.in.GetNotificationPreferenceUseCase.NotificationPreferenceView;
import com.ted.signal.application.port.in.UpdateNotificationPreferenceUseCase;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/notifications")
@RequiredArgsConstructor
@Validated
public class NotificationPreferenceController {

    private final GetNotificationPreferenceUseCase getUseCase;
    private final UpdateNotificationPreferenceUseCase updateUseCase;
    private final ApiKeyValidator apiKeyValidator;

    /**
     * 현재 알림 설정 조회 (공개)
     * GET /api/notifications/preferences
     */
    @GetMapping("/preferences")
    public ResponseEntity<NotificationPreferenceView> get() {
        return ResponseEntity.ok(getUseCase.get());
    }

    /**
     * 알림 설정 업데이트 (API Key 인증 필요)
     * PUT /api/notifications/preferences
     * Header: X-API-Key: {admin-api-key}
     */
    @PutMapping("/preferences")
    public ResponseEntity<NotificationPreferenceView> update(
            @Valid @RequestBody UpdateRequest request,
            @RequestHeader(value = "X-API-Key", required = false) String apiKey) {
        if (!apiKeyValidator.isValid(apiKey)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        var command = new UpdateNotificationPreferenceUseCase.UpdateCommand(
                request.dailySummaryEnabled(),
                request.urgentAlertEnabled(),
                request.batchFailureEnabled(),
                request.weeklyReportEnabled(),
                request.minScore(),
                request.signalTypes()
        );
        return ResponseEntity.ok(updateUseCase.update(command));
    }

    public record UpdateRequest(
            @NotNull Boolean dailySummaryEnabled,
            @NotNull Boolean urgentAlertEnabled,
            @NotNull Boolean batchFailureEnabled,
            @NotNull Boolean weeklyReportEnabled,
            @NotNull @Min(0) @Max(100) Integer minScore,
            @NotNull @Size(min = 1, max = 3) List<String> signalTypes
    ) {}
}
