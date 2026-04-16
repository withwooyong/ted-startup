package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.DetectSignalsUseCase;
import jakarta.validation.constraints.PastOrPresent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;

@RestController
@RequestMapping("/api/signals")
@Validated
public class SignalDetectionController {

    private final String adminApiKey;
    private final DetectSignalsUseCase detectSignalsUseCase;

    public SignalDetectionController(
            @Value("${signal.admin.api-key:}") String adminApiKey,
            DetectSignalsUseCase detectSignalsUseCase) {
        this.adminApiKey = adminApiKey;
        this.detectSignalsUseCase = detectSignalsUseCase;
    }

    /**
     * 시그널 탐지 실행 (API Key 인증 필요)
     * POST /api/signals/detect?date=2026-04-16
     * Header: X-API-Key: {admin-api-key}
     */
    @PostMapping("/detect")
    public ResponseEntity<DetectSignalsUseCase.DetectionResult> detect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date,
            @RequestHeader(value = "X-API-Key", required = false) String apiKey) {
        if (!isValidApiKey(apiKey)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        var targetDate = date != null ? date : LocalDate.now();
        return ResponseEntity.ok(detectSignalsUseCase.detectAll(targetDate));
    }

    private boolean isValidApiKey(String apiKey) {
        if (adminApiKey.isBlank()) return false;
        byte[] expected = adminApiKey.getBytes(StandardCharsets.UTF_8);
        byte[] actual = (apiKey != null ? apiKey : "").getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expected, actual);
    }
}
