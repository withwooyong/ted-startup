package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.DetectSignalsUseCase;
import jakarta.validation.constraints.PastOrPresent;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

@RestController
@RequestMapping("/api/signals")
@RequiredArgsConstructor
@Validated
public class SignalDetectionController {

    private final ApiKeyValidator apiKeyValidator;
    private final DetectSignalsUseCase detectSignalsUseCase;

    /**
     * 시그널 탐지 실행 (API Key 인증 필요)
     * POST /api/signals/detect?date=2026-04-16
     * Header: X-API-Key: {admin-api-key}
     */
    @PostMapping("/detect")
    public ResponseEntity<DetectSignalsUseCase.DetectionResult> detect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date,
            @RequestHeader(value = "X-API-Key", required = false) String apiKey) {
        if (!apiKeyValidator.isValid(apiKey)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        var targetDate = date != null ? date : LocalDate.now();
        return ResponseEntity.ok(detectSignalsUseCase.detectAll(targetDate));
    }
}
