package com.ted.signal.application.service;

import com.ted.signal.application.port.in.RunBacktestUseCase;
import com.ted.signal.application.port.out.BacktestResultRepository;
import com.ted.signal.application.port.out.SignalRepository;
import com.ted.signal.application.port.out.StockPriceRepository;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.BacktestResult;
import com.ted.signal.domain.model.Signal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class BacktestEngineService implements RunBacktestUseCase {

    private static final int FUTURE_BUFFER_DAYS = 40; // 영업일 20일 = 달력일 ~30일 + 여유

    private final SignalRepository signalRepository;
    private final StockPriceRepository stockPriceRepository;
    private final BacktestResultRepository backtestResultRepository;

    @Override
    @Transactional
    public BacktestExecutionResult execute(LocalDate from, LocalDate to) {
        long start = System.currentTimeMillis();
        log.info("=== 백테스팅 시작: {} ~ {} ===", from, to);

        // 1. 기간 내 전체 시그널 조회 (Stock JOIN FETCH)
        List<Signal> signals = signalRepository.findBySignalDateBetweenWithStock(from, to);
        log.info("대상 시그널 수: {}", signals.size());

        if (signals.isEmpty()) {
            return new BacktestExecutionResult(0, 0, 0, System.currentTimeMillis() - start);
        }

        // 2. 종목별로 그룹핑 → 주가 벌크 로드 → 수익률 계산
        Map<Long, List<Signal>> byStock = signals.stream()
                .collect(Collectors.groupingBy(s -> s.getStock().getId()));

        int returnsCalculated = 0;

        for (var entry : byStock.entrySet()) {
            Long stockId = entry.getKey();
            List<Signal> stockSignals = entry.getValue();

            // 주가 벌크 로드: 시그널 최소일 ~ 최대일 + 버퍼
            LocalDate minDate = stockSignals.stream()
                    .map(Signal::getSignalDate).min(LocalDate::compareTo).orElse(from);
            LocalDate maxDate = stockSignals.stream()
                    .map(Signal::getSignalDate).max(LocalDate::compareTo).orElse(to)
                    .plusDays(FUTURE_BUFFER_DAYS);

            var prices = stockPriceRepository
                    .findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(stockId, minDate, maxDate);

            // TreeMap으로 거래일 기반 O(1) 조회 + tailMap으로 N영업일 후 탐색
            TreeMap<LocalDate, Long> priceMap = new TreeMap<>();
            for (var p : prices) {
                priceMap.put(p.getTradingDate(), p.getClosePrice());
            }

            for (Signal signal : stockSignals) {
                BigDecimal r5d = calculateReturn(priceMap, signal.getSignalDate(), 5);
                BigDecimal r10d = calculateReturn(priceMap, signal.getSignalDate(), 10);
                BigDecimal r20d = calculateReturn(priceMap, signal.getSignalDate(), 20);

                signal.updateReturns(r5d, r10d, r20d);
                if (r5d != null || r10d != null || r20d != null) {
                    returnsCalculated++;
                }
            }
        }

        // 3. 시그널 일괄 저장 (dirty checking으로 UPDATE)
        signalRepository.saveAll(signals);

        // 4. SignalType별 집계 → BacktestResult 일괄 저장
        List<BacktestResult> results = new ArrayList<>();
        for (SignalType type : SignalType.values()) {
            List<Signal> typed = signals.stream()
                    .filter(s -> s.getSignalType() == type)
                    .toList();

            if (typed.isEmpty()) continue;

            BacktestResult result = aggregateResult(type, typed, from, to);
            results.add(result);

            log.info("  {} → 시그널 {}, 5일 적중률 {}, 10일 적중률 {}, 20일 적중률 {}",
                    type, result.getTotalSignals(),
                    result.getHitRate5d(), result.getHitRate10d(), result.getHitRate20d());
        }
        backtestResultRepository.saveAll(results);

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== 백테스팅 완료: 시그널 {}, 수익률 계산 {}, 결과 {} ({}ms) ===",
                signals.size(), returnsCalculated, results.size(), elapsed);

        return new BacktestExecutionResult(signals.size(), returnsCalculated, results.size(), elapsed);
    }

    /**
     * 시그널 발생일 기준 N영업일 후 수익률 계산
     * return = (futurePrice - basePrice) / basePrice * 100
     */
    private BigDecimal calculateReturn(TreeMap<LocalDate, Long> priceMap, LocalDate signalDate, int tradingDays) {
        Long basePrice = priceMap.get(signalDate);
        if (basePrice == null || basePrice == 0) return null;

        // signalDate 이후 거래일만 추출
        var futureDates = new ArrayList<>(priceMap.tailMap(signalDate, false).keySet());
        if (futureDates.size() < tradingDays) return null;

        LocalDate targetDate = futureDates.get(tradingDays - 1);
        Long targetPrice = priceMap.get(targetDate);
        if (targetPrice == null) return null;

        return BigDecimal.valueOf(targetPrice - basePrice)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(basePrice), 4, RoundingMode.HALF_UP);
    }

    /**
     * SignalType별 적중률/평균수익률 집계
     */
    private BacktestResult aggregateResult(SignalType type, List<Signal> signals,
                                           LocalDate from, LocalDate to) {
        int total = signals.size();

        // 수익률이 null이 아닌 시그널만 집계 대상
        List<Signal> with5d = signals.stream().filter(s -> s.getReturn5d() != null).toList();
        List<Signal> with10d = signals.stream().filter(s -> s.getReturn10d() != null).toList();
        List<Signal> with20d = signals.stream().filter(s -> s.getReturn20d() != null).toList();

        int hit5d = (int) with5d.stream().filter(s -> s.getReturn5d().compareTo(BigDecimal.ZERO) > 0).count();
        int hit10d = (int) with10d.stream().filter(s -> s.getReturn10d().compareTo(BigDecimal.ZERO) > 0).count();
        int hit20d = (int) with20d.stream().filter(s -> s.getReturn20d().compareTo(BigDecimal.ZERO) > 0).count();

        return BacktestResult.builder()
                .signalType(type.name())
                .periodStart(from)
                .periodEnd(to)
                .totalSignals(total)
                .hitCount5d(hit5d)
                .hitRate5d(rate(hit5d, with5d.size()))
                .avgReturn5d(avgReturn(with5d.stream().map(Signal::getReturn5d).toList()))
                .hitCount10d(hit10d)
                .hitRate10d(rate(hit10d, with10d.size()))
                .avgReturn10d(avgReturn(with10d.stream().map(Signal::getReturn10d).toList()))
                .hitCount20d(hit20d)
                .hitRate20d(rate(hit20d, with20d.size()))
                .avgReturn20d(avgReturn(with20d.stream().map(Signal::getReturn20d).toList()))
                .build();
    }

    private BigDecimal rate(int hits, int total) {
        if (total == 0) return BigDecimal.ZERO;
        return BigDecimal.valueOf(hits)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(total), 4, RoundingMode.HALF_UP);
    }

    private BigDecimal avgReturn(List<BigDecimal> returns) {
        if (returns.isEmpty()) return BigDecimal.ZERO;
        BigDecimal sum = returns.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.divide(BigDecimal.valueOf(returns.size()), 4, RoundingMode.HALF_UP);
    }
}
