package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.DetectSignalsUseCase;
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
@RequestMapping("/api/signals")
@RequiredArgsConstructor
@Validated
public class SignalDetectionController {

    private static final Set<String> ALLOWED_IPS = Set.of(
            "127.0.0.1", "0:0:0:0:0:0:0:1", "::1"
    );

    private final DetectSignalsUseCase detectSignalsUseCase;

    /**
     * 시그널 탐지 실행 (localhost 전용)
     * POST /api/signals/detect?date=2026-04-16
     */
    @PostMapping("/detect")
    public ResponseEntity<DetectSignalsUseCase.DetectionResult> detect(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) @PastOrPresent LocalDate date,
            HttpServletRequest request) {
        if (!ALLOWED_IPS.contains(request.getRemoteAddr())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        var targetDate = date != null ? date : LocalDate.now();
        return ResponseEntity.ok(detectSignalsUseCase.detectAll(targetDate));
    }
}
