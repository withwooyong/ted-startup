package com.ted.signal.adapter.in.web;

import com.ted.signal.application.port.in.GetBacktestResultsUseCase;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/backtest")
@RequiredArgsConstructor
public class BacktestController {

    private final GetBacktestResultsUseCase getBacktestResultsUseCase;

    /**
     * 백테스팅 결과 조회
     * GET /api/backtest
     */
    @GetMapping
    public ResponseEntity<List<GetBacktestResultsUseCase.BacktestSummary>> getResults() {
        return ResponseEntity.ok(getBacktestResultsUseCase.getLatestResults());
    }
}
