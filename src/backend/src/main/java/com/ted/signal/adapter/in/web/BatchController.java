package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.PastOrPresent;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.Set;

@RestController
@RequestMapping("/api/batch")
@RequiredArgsConstructor
@Validated
public class BatchController {

    private static final Set<String> ALLOWED_IPS = Set.of(
            "127.0.0.1", "0:0:0:0:0:0:0:1", "::1"
    );

    private final CollectMarketDataUseCase collectMarketDataUseCase;

    /**
     * 수동 배치 실행 (localhost에서만 허용)
     * POST /api/batch/collect?date=2026-04-16
     */
    @PostMapping("/collect")
    public ResponseEntity<CollectMarketDataUseCase.CollectionResult> collect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date,
            HttpServletRequest request) {
        if (!ALLOWED_IPS.contains(request.getRemoteAddr())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        var targetDate = date != null ? date : LocalDate.now();
        var result = collectMarketDataUseCase.collectAll(targetDate);
        return ResponseEntity.ok(result);
    }
}
