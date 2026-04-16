package com.ted.signal.application.service;

import com.ted.signal.adapter.out.external.KrxClient;
import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import com.ted.signal.application.port.out.*;
import com.ted.signal.domain.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class MarketDataCollectionService implements CollectMarketDataUseCase {

    private final KrxClient krxClient;
    private final StockRepository stockRepository;
    private final StockPriceRepository stockPriceRepository;
    private final ShortSellingRepository shortSellingRepository;
    private final LendingBalanceRepository lendingBalanceRepository;

    @Override
    @Transactional
    public CollectionResult collectAll(LocalDate date) {
        long start = System.currentTimeMillis();
        log.info("=== KRX 데이터 수집 시작: {} ===", date);

        // 1. 주가 시세 수집
        var priceData = krxClient.fetchStockPrice(date);
        log.info("주가 시세 {}건 수신", priceData.size());

        // 종목 마스터 업데이트
        int newStocks = 0;
        var stockMap = stockRepository.findByIsActiveTrueAndDeletedAtIsNull().stream()
                .collect(Collectors.toMap(Stock::getStockCode, s -> s));

        for (var p : priceData) {
            if (!stockMap.containsKey(p.stockCode())) {
                var stock = Stock.builder()
                        .stockCode(p.stockCode())
                        .stockName(p.stockName())
                        .marketType(p.marketType())
                        .build();
                var saved = stockRepository.save(stock);
                stockMap.put(p.stockCode(), saved);
                newStocks++;
            }
        }
        if (newStocks > 0) log.info("신규 종목 {}건 등록", newStocks);

        // 주가 저장
        int priceCount = 0;
        for (var p : priceData) {
            var stock = stockMap.get(p.stockCode());
            if (stock == null || stockPriceRepository.existsByStockIdAndTradingDate(stock.getId(), date)) continue;
            stockPriceRepository.save(StockPrice.builder()
                    .stock(stock)
                    .tradingDate(date)
                    .closePrice(p.closePrice())
                    .openPrice(p.openPrice())
                    .highPrice(p.highPrice())
                    .lowPrice(p.lowPrice())
                    .volume(p.volume())
                    .marketCap(p.marketCap())
                    .changeRate(p.changeRate())
                    .build());
            priceCount++;
        }
        log.info("주가 시세 {}건 저장", priceCount);

        // 2. 공매도 거래 수집
        var shortData = krxClient.fetchShortSelling(date);
        int shortCount = 0;
        for (var s : shortData) {
            var stock = stockMap.get(s.stockCode());
            if (stock == null || shortSellingRepository.existsByStockIdAndTradingDate(stock.getId(), date)) continue;
            shortSellingRepository.save(ShortSelling.builder()
                    .stock(stock)
                    .tradingDate(date)
                    .shortVolume(s.shortVolume())
                    .shortAmount(s.shortAmount())
                    .shortRatio(s.shortRatio())
                    .build());
            shortCount++;
        }
        log.info("공매도 거래 {}건 저장", shortCount);

        // 3. 대차잔고 수집
        var lendingData = krxClient.fetchLendingBalance(date);
        int lendingCount = 0;
        for (var lb : lendingData) {
            var stock = stockMap.get(lb.stockCode());
            if (stock == null || lendingBalanceRepository.existsByStockIdAndTradingDate(stock.getId(), date)) continue;

            // 전일 대비 변동률 계산
            var prevDate = date.minusDays(1);
            var prevBalance = lendingBalanceRepository.findByStockIdAndTradingDate(stock.getId(), prevDate);
            BigDecimal changeRate = BigDecimal.ZERO;
            long changeQty = 0;
            int consecutiveDays = 0;

            if (prevBalance.isPresent() && prevBalance.get().getBalanceQuantity() > 0) {
                long prevQty = prevBalance.get().getBalanceQuantity();
                changeQty = lb.balanceQuantity() - prevQty;
                changeRate = BigDecimal.valueOf(changeQty)
                        .divide(BigDecimal.valueOf(prevQty), 4, RoundingMode.HALF_UP)
                        .multiply(BigDecimal.valueOf(100));
                if (changeQty < 0) {
                    consecutiveDays = prevBalance.get().getConsecutiveDecreaseDays() + 1;
                }
            }

            lendingBalanceRepository.save(LendingBalance.builder()
                    .stock(stock)
                    .tradingDate(date)
                    .balanceQuantity(lb.balanceQuantity())
                    .balanceAmount(lb.balanceAmount())
                    .changeRate(changeRate)
                    .changeQuantity(changeQty)
                    .consecutiveDecreaseDays(consecutiveDays)
                    .build());
            lendingCount++;
        }
        log.info("대차잔고 {}건 저장", lendingCount);

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== KRX 데이터 수집 완료: {}ms ===", elapsed);

        return new CollectionResult(priceCount, shortCount, lendingCount, newStocks, elapsed);
    }
}
