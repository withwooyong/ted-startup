package com.ted.signal.application.service;

import com.ted.signal.application.port.in.GetSignalsUseCase;
import com.ted.signal.application.port.in.GetStockDetailUseCase;
import com.ted.signal.application.port.out.*;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class SignalQueryService implements GetSignalsUseCase, GetStockDetailUseCase {

    private final SignalRepository signalRepository;
    private final StockRepository stockRepository;
    private final StockPriceRepository stockPriceRepository;
    private final LendingBalanceRepository lendingBalanceRepository;

    @Override
    public List<SignalResult> getSignals(LocalDate date, SignalType type) {
        var signals = signalRepository.findByDateAndType(date, type);
        return signals.stream().map(s -> {
            var stock = s.getStock();
            var detail = s.getDetail() != null ? s.getDetail() : Map.<String, Object>of();
            return new SignalResult(
                    s.getId(),
                    stock.getStockCode(),
                    stock.getStockName(),
                    stock.getMarketType(),
                    s.getSignalType().name(),
                    s.getScore(),
                    s.getGrade().name(),
                    toDouble(detail.get("balanceChangeRate")),
                    toDouble(detail.get("volumeChangeRate")),
                    toInt(detail.get("consecutiveDecreaseDays")),
                    s.getSignalDate()
            );
        }).toList();
    }

    @Override
    public StockDetail getStockDetail(String stockCode, LocalDate from, LocalDate to) {
        var stock = stockRepository.findByStockCodeAndDeletedAtIsNull(stockCode)
                .orElseThrow(() -> new IllegalArgumentException("종목을 찾을 수 없어요: " + stockCode));

        var prices = stockPriceRepository.findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
                stock.getId(), from, to);
        var balances = lendingBalanceRepository.findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
                stock.getId(), from, to);
        var signals = signalRepository.findByStockIdAndSignalDateBetweenOrderBySignalDateDesc(
                stock.getId(), from, to);

        // Build balance lookup
        var balanceMap = balances.stream()
                .collect(Collectors.toMap(LendingBalance::getTradingDate, LendingBalance::getBalanceQuantity));

        var timeSeries = prices.stream()
                .map(p -> new TimeSeriesPoint(
                        p.getTradingDate(),
                        p.getClosePrice(),
                        balanceMap.getOrDefault(p.getTradingDate(), 0L)
                )).toList();

        var signalMarkers = signals.stream()
                .map(s -> new SignalMarker(
                        s.getSignalDate(),
                        s.getSignalType().name(),
                        s.getScore(),
                        s.getGrade().name(),
                        s.getDetail()
                )).toList();

        var latestPrice = prices.isEmpty() ? new LatestPrice(0, null, 0, 0)
                : new LatestPrice(
                prices.getLast().getClosePrice(),
                prices.getLast().getChangeRate(),
                prices.getLast().getVolume(),
                prices.getLast().getMarketCap() != null ? prices.getLast().getMarketCap() : 0
        );

        return new StockDetail(
                stock.getStockCode(),
                stock.getStockName(),
                stock.getMarketType(),
                latestPrice,
                timeSeries,
                signalMarkers
        );
    }

    private double toDouble(Object val) {
        if (val == null) return 0.0;
        if (val instanceof Number n) return n.doubleValue();
        try {
            return Double.parseDouble(val.toString());
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }

    private int toInt(Object val) {
        if (val == null) return 0;
        if (val instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(val.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
