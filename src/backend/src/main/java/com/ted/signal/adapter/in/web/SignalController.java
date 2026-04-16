package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.GetSignalsUseCase;
import com.ted.signal.application.port.in.GetStockDetailUseCase;
import com.ted.signal.domain.enums.SignalType;
import jakarta.validation.constraints.Pattern;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Validated
public class SignalController {

    private final GetSignalsUseCase getSignalsUseCase;
    private final GetStockDetailUseCase getStockDetailUseCase;

    /**
     * 날짜별 시그널 리스트 조회
     * GET /api/signals?date=2026-04-16&type=SHORT_SQUEEZE
     */
    @GetMapping("/signals")
    public ResponseEntity<List<GetSignalsUseCase.SignalResult>> getSignals(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(required = false) SignalType type) {
        var targetDate = date != null ? date : LocalDate.now();
        return ResponseEntity.ok(getSignalsUseCase.getSignals(targetDate, type));
    }

    /**
     * 종목 상세 (시계열 + 시그널)
     * GET /api/stocks/005930?from=2026-01-01&to=2026-04-16
     */
    @GetMapping("/stocks/{stockCode}")
    public ResponseEntity<GetStockDetailUseCase.StockDetail> getStockDetail(
            @PathVariable @Pattern(regexp = "\\d{6}", message = "종목코드는 6자리 숫자여야 합니다") String stockCode,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        var toDate = to != null ? to : LocalDate.now();
        var fromDate = from != null ? from : toDate.minusMonths(3);
        return ResponseEntity.ok(getStockDetailUseCase.getStockDetail(stockCode, fromDate, toDate));
    }
}
