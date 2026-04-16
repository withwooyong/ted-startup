package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.GetBacktestResultsUseCase;
import com.ted.signal.application.port.in.RunBacktestUseCase;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/backtest")
@Validated
public class BacktestController {

    private final String adminApiKey;
    private final GetBacktestResultsUseCase getBacktestResultsUseCase;
    private final RunBacktestUseCase runBacktestUseCase;

    public BacktestController(
            @Value("${signal.admin.api-key:}") String adminApiKey,
            GetBacktestResultsUseCase getBacktestResultsUseCase,
            RunBacktestUseCase runBacktestUseCase) {
        this.adminApiKey = adminApiKey;
        this.getBacktestResultsUseCase = getBacktestResultsUseCase;
        this.runBacktestUseCase = runBacktestUseCase;
    }

    /**
     * 백테스팅 결과 조회
     * GET /api/backtest
     */
    @GetMapping
    public ResponseEntity<List<GetBacktestResultsUseCase.BacktestSummary>> getResults() {
        return ResponseEntity.ok(getBacktestResultsUseCase.getLatestResults());
    }

    /**
     * 백테스팅 실행 (API Key 인증 필요)
     * POST /api/backtest/run?from=2023-04-17&to=2026-04-17
     * Header: X-API-Key: {admin-api-key}
     */
    @PostMapping("/run")
    public ResponseEntity<RunBacktestUseCase.BacktestExecutionResult> run(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @RequestHeader(value = "X-API-Key", required = false) String apiKey) {

        if (!isValidApiKey(apiKey)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        LocalDate end = to != null ? to : LocalDate.now();
        LocalDate start = from != null ? from : end.minusYears(3);

        if (start.isAfter(end)) {
            return ResponseEntity.badRequest().build();
        }
        if (start.isBefore(end.minusYears(5))) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(runBacktestUseCase.execute(start, end));
    }

    private boolean isValidApiKey(String apiKey) {
        if (adminApiKey.isBlank()) return false;
        byte[] expected = adminApiKey.getBytes(StandardCharsets.UTF_8);
        byte[] actual = (apiKey != null ? apiKey : "").getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expected, actual);
    }
}
