package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import jakarta.validation.constraints.PastOrPresent;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

@RestController
@RequestMapping("/api/batch")
@RequiredArgsConstructor
@Validated
public class BatchController {

    private final CollectMarketDataUseCase collectMarketDataUseCase;

    /**
     * 수동 배치 실행
     * POST /api/batch/collect?date=2026-04-16
     */
    @PostMapping("/collect")
    public ResponseEntity<CollectMarketDataUseCase.CollectionResult> collect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date) {
        var targetDate = date != null ? date : LocalDate.now();
        var result = collectMarketDataUseCase.collectAll(targetDate);
        return ResponseEntity.ok(result);
    }
}
