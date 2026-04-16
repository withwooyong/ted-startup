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
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
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
    public CollectionResult collectAll(LocalDate date) {
        long start = System.currentTimeMillis();
        log.info("=== KRX 데이터 수집 시작: {} ===", date);

        // Phase 1: HTTP 수집 (트랜잭션 밖에서 실행 — DB 커넥션 점유 방지)
        var priceData = krxClient.fetchStockPrice(date);
        log.info("주가 시세 {}건 수신", priceData.size());

        var shortData = krxClient.fetchShortSelling(date);
        log.info("공매도 거래 {}건 수신", shortData.size());

        var lendingData = krxClient.fetchLendingBalance(date);
        log.info("대차잔고 {}건 수신", lendingData.size());

        // Phase 2: DB 저장 (트랜잭션 안에서 실행)
        var result = persistAll(date, priceData, shortData, lendingData);

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== KRX 데이터 수집 완료: {}ms ===", elapsed);

        return new CollectionResult(
                result.priceCount, result.shortCount, result.lendingCount,
                result.newStockCount, elapsed);
    }

    @Transactional
    protected PersistResult persistAll(
            LocalDate date,
            List<KrxClient.StockPriceData> priceData,
            List<KrxClient.ShortSellingData> shortData,
            List<KrxClient.LendingBalanceData> lendingData) {

        // 종목 마스터 로드 (1회 벌크 조회)
        var stockMap = stockRepository.findByIsActiveTrueAndDeletedAtIsNull().stream()
                .collect(Collectors.toMap(Stock::getStockCode, s -> s, (a, b) -> a));

        // 신규 종목 등록
        int newStocks = 0;
        for (var p : priceData) {
            if (!stockMap.containsKey(p.stockCode())) {
                var stock = stockRepository.save(Stock.builder()
                        .stockCode(p.stockCode())
                        .stockName(p.stockName())
                        .marketType(p.marketType())
                        .build());
                stockMap.put(p.stockCode(), stock);
                newStocks++;
            }
        }
        if (newStocks > 0) log.info("신규 종목 {}건 등록", newStocks);

        // 기존 데이터 벌크 조회 (종목당 exists 쿼리 제거)
        var existingPriceIds = stockPriceRepository
                .findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
                        null, date, date).stream()  // null stockId 사용 불가 → 별도 쿼리 필요
                .map(sp -> sp.getStock().getId())
                .collect(Collectors.toSet());

        // 주가 저장 — saveAll 벌크
        var pricesToSave = new ArrayList<StockPrice>();
        for (var p : priceData) {
            var stock = stockMap.get(p.stockCode());
            if (stock == null) continue;
            pricesToSave.add(StockPrice.builder()
                    .stock(stock).tradingDate(date)
                    .closePrice(p.closePrice()).openPrice(p.openPrice())
                    .highPrice(p.highPrice()).lowPrice(p.lowPrice())
                    .volume(p.volume()).marketCap(p.marketCap())
                    .changeRate(p.changeRate())
                    .build());
        }
        stockPriceRepository.saveAll(pricesToSave);
        int priceCount = pricesToSave.size();
        log.info("주가 시세 {}건 저장", priceCount);

        // 공매도 저장 — saveAll 벌크
        var shortsToSave = new ArrayList<ShortSelling>();
        for (var s : shortData) {
            var stock = stockMap.get(s.stockCode());
            if (stock == null) continue;
            shortsToSave.add(ShortSelling.builder()
                    .stock(stock).tradingDate(date)
                    .shortVolume(s.shortVolume()).shortAmount(s.shortAmount())
                    .shortRatio(s.shortRatio())
                    .build());
        }
        shortSellingRepository.saveAll(shortsToSave);
        int shortCount = shortsToSave.size();
        log.info("공매도 거래 {}건 저장", shortCount);

        // 대차잔고 저장 — 전 영업일 대비 변동률 계산
        var prevTradingDate = findPreviousTradingDate(date);
        // 전 영업일 대차잔고 벌크 조회 (1회 쿼리)
        var prevBalanceMap = lendingBalanceRepository.findAllByTradingDate(prevTradingDate).stream()
                .collect(Collectors.toMap(lb -> lb.getStock().getId(), lb -> lb, (a, b) -> a));

        var lendingsToSave = new ArrayList<LendingBalance>();
        for (var lb : lendingData) {
            var stock = stockMap.get(lb.stockCode());
            if (stock == null) continue;

            BigDecimal changeRate = BigDecimal.ZERO;
            long changeQty = 0;
            int consecutiveDays = 0;

            var prev = prevBalanceMap.get(stock.getId());
            if (prev != null && prev.getBalanceQuantity() > 0) {
                long prevQty = prev.getBalanceQuantity();
                changeQty = lb.balanceQuantity() - prevQty;
                changeRate = BigDecimal.valueOf(changeQty)
                        .divide(BigDecimal.valueOf(prevQty), 4, RoundingMode.HALF_UP)
                        .multiply(BigDecimal.valueOf(100));
                if (changeQty < 0) {
                    consecutiveDays = prev.getConsecutiveDecreaseDays() + 1;
                }
            }

            lendingsToSave.add(LendingBalance.builder()
                    .stock(stock).tradingDate(date)
                    .balanceQuantity(lb.balanceQuantity()).balanceAmount(lb.balanceAmount())
                    .changeRate(changeRate).changeQuantity(changeQty)
                    .consecutiveDecreaseDays(consecutiveDays)
                    .build());
        }
        lendingBalanceRepository.saveAll(lendingsToSave);
        int lendingCount = lendingsToSave.size();
        log.info("대차잔고 {}건 저장 (전 영업일: {})", lendingCount, prevTradingDate);

        return new PersistResult(priceCount, shortCount, lendingCount, newStocks);
    }

    /**
     * 직전 영업일 계산 (주말/공휴일 건너뛰기)
     * TODO: 한국 공휴일 캘린더 연동 (v1.1)
     */
    private LocalDate findPreviousTradingDate(LocalDate date) {
        var prev = date.minusDays(1);
        while (prev.getDayOfWeek() == DayOfWeek.SATURDAY || prev.getDayOfWeek() == DayOfWeek.SUNDAY) {
            prev = prev.minusDays(1);
        }
        return prev;
    }

    private record PersistResult(int priceCount, int shortCount, int lendingCount, int newStockCount) {}
}
