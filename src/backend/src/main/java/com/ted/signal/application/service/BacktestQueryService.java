package com.ted.signal.application.service;

import com.ted.signal.application.port.in.GetBacktestResultsUseCase;
import com.ted.signal.application.port.out.BacktestResultRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class BacktestQueryService implements GetBacktestResultsUseCase {

    private final BacktestResultRepository backtestResultRepository;

    @Override
    public List<BacktestSummary> getLatestResults() {
        return backtestResultRepository.findTop20ByOrderByCreatedAtDesc().stream()
                .map(r -> new BacktestSummary(
                        r.getSignalType(),
                        r.getPeriodStart(),
                        r.getPeriodEnd(),
                        r.getTotalSignals(),
                        r.getHitCount5d(),
                        r.getHitRate5d(),
                        r.getAvgReturn5d(),
                        r.getHitCount10d(),
                        r.getHitRate10d(),
                        r.getAvgReturn10d(),
                        r.getHitCount20d(),
                        r.getHitRate20d(),
                        r.getAvgReturn20d()
                ))
                .toList();
    }
}
