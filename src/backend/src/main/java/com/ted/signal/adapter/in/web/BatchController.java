package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
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
@RequestMapping("/api/batch")
@Validated
public class BatchController {

    private final String adminApiKey;
    private final CollectMarketDataUseCase collectMarketDataUseCase;

    public BatchController(
            @Value("${signal.admin.api-key:}") String adminApiKey,
            CollectMarketDataUseCase collectMarketDataUseCase) {
        this.adminApiKey = adminApiKey;
        this.collectMarketDataUseCase = collectMarketDataUseCase;
    }

    /**
     * 수동 배치 실행 (API Key 인증 필요)
     * POST /api/batch/collect?date=2026-04-16
     * Header: X-API-Key: {admin-api-key}
     */
    @PostMapping("/collect")
    public ResponseEntity<CollectMarketDataUseCase.CollectionResult> collect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date,
            @RequestHeader(value = "X-API-Key", required = false) String apiKey) {
        if (!isValidApiKey(apiKey)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        var targetDate = date != null ? date : LocalDate.now();
        var result = collectMarketDataUseCase.collectAll(targetDate);
        return ResponseEntity.ok(result);
    }

    private boolean isValidApiKey(String apiKey) {
        if (adminApiKey.isBlank()) return false;
        byte[] expected = adminApiKey.getBytes(StandardCharsets.UTF_8);
        byte[] actual = (apiKey != null ? apiKey : "").getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expected, actual);
    }
}
