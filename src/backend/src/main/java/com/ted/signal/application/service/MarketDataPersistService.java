package com.ted.signal.application.service;

import com.ted.signal.adapter.out.external.KrxClient;
import com.ted.signal.application.port.out.LendingBalanceRepository;
import com.ted.signal.application.port.out.ShortSellingRepository;
import com.ted.signal.application.port.out.StockPriceRepository;
import com.ted.signal.application.port.out.StockRepository;
import com.ted.signal.domain.model.LendingBalance;
import com.ted.signal.domain.model.ShortSelling;
import com.ted.signal.domain.model.Stock;
import com.ted.signal.domain.model.StockPrice;
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
import java.util.Set;
import java.util.stream.Collectors;

/**
 * KRX 수집 데이터 영속화 전담 서비스.
 * MarketDataCollectionService에서 persistAll을 자기호출할 경우 Spring AOP 프록시가
 * @Transactional을 적용하지 않아 부분 커밋이 발생할 수 있다. 이를 방지하기 위해 별도 빈으로 분리했다.
 * <p>
 * 멱등성: 동일 (stock_id, trading_date) 레코드가 존재하면 INSERT를 스킵한다.
 * 운영자 수동 재수집 시 유니크 제약 충돌로 배치 전체가 실패하는 것을 방지.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MarketDataPersistService {

    private final StockRepository stockRepository;
    private final StockPriceRepository stockPriceRepository;
    private final ShortSellingRepository shortSellingRepository;
    private final LendingBalanceRepository lendingBalanceRepository;

    @Transactional
    public PersistResult persistAll(
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

        // 멱등성: 해당 일자의 기존 레코드 stockId 집합을 1회 조회해 중복 INSERT 스킵
        Set<Long> existingPriceStockIds = stockPriceRepository.findAllByTradingDate(date).stream()
                .map(sp -> sp.getStock().getId())
                .collect(Collectors.toSet());
        Set<Long> existingShortStockIds = shortSellingRepository.findAllByTradingDate(date).stream()
                .map(ss -> ss.getStock().getId())
                .collect(Collectors.toSet());
        Set<Long> existingLendingStockIds = lendingBalanceRepository.findAllByTradingDate(date).stream()
                .map(lb -> lb.getStock().getId())
                .collect(Collectors.toSet());

        // 주가 저장 — saveAll 벌크 (중복 skip)
        var pricesToSave = new ArrayList<StockPrice>();
        int skippedPrice = 0;
        for (var p : priceData) {
            var stock = stockMap.get(p.stockCode());
            if (stock == null) continue;
            if (existingPriceStockIds.contains(stock.getId())) {
                skippedPrice++;
                continue;
            }
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
        log.info("주가 시세 {}건 저장 (중복 스킵 {}건)", priceCount, skippedPrice);

        // 공매도 저장 — saveAll 벌크 (중복 skip)
        var shortsToSave = new ArrayList<ShortSelling>();
        int skippedShort = 0;
        for (var s : shortData) {
            var stock = stockMap.get(s.stockCode());
            if (stock == null) continue;
            if (existingShortStockIds.contains(stock.getId())) {
                skippedShort++;
                continue;
            }
            shortsToSave.add(ShortSelling.builder()
                    .stock(stock).tradingDate(date)
                    .shortVolume(s.shortVolume()).shortAmount(s.shortAmount())
                    .shortRatio(s.shortRatio())
                    .build());
        }
        shortSellingRepository.saveAll(shortsToSave);
        int shortCount = shortsToSave.size();
        log.info("공매도 거래 {}건 저장 (중복 스킵 {}건)", shortCount, skippedShort);

        // 대차잔고 저장 — 전 영업일 대비 변동률 계산 + 중복 skip
        var prevTradingDate = findPreviousTradingDate(date);
        var prevBalanceMap = lendingBalanceRepository.findAllByTradingDate(prevTradingDate).stream()
                .collect(Collectors.toMap(lb -> lb.getStock().getId(), lb -> lb, (a, b) -> a));

        var lendingsToSave = new ArrayList<LendingBalance>();
        int skippedLending = 0;
        for (var lb : lendingData) {
            var stock = stockMap.get(lb.stockCode());
            if (stock == null) continue;
            if (existingLendingStockIds.contains(stock.getId())) {
                skippedLending++;
                continue;
            }

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
        log.info("대차잔고 {}건 저장 (중복 스킵 {}건, 전 영업일: {})", lendingCount, skippedLending, prevTradingDate);

        return new PersistResult(priceCount, shortCount, lendingCount, newStocks);
    }

    /**
     * 직전 영업일 계산 (주말 건너뛰기)
     * TODO: 한국 공휴일 캘린더 연동 (v1.1)
     */
    private LocalDate findPreviousTradingDate(LocalDate date) {
        var prev = date.minusDays(1);
        while (prev.getDayOfWeek() == DayOfWeek.SATURDAY || prev.getDayOfWeek() == DayOfWeek.SUNDAY) {
            prev = prev.minusDays(1);
        }
        return prev;
    }

    public record PersistResult(int priceCount, int shortCount, int lendingCount, int newStockCount) {}
}
