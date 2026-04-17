package com.ted.signal.application.service;

import com.ted.signal.application.port.in.DetectSignalsUseCase;
import com.ted.signal.application.port.out.*;
import com.ted.signal.domain.enums.SignalGrade;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.*;
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
public class SignalDetectionService implements DetectSignalsUseCase {

    private static final BigDecimal RAPID_DECLINE_THRESHOLD = new BigDecimal("-10.0");
    private static final int TREND_MA_SHORT = 5;
    private static final int TREND_MA_LONG = 20;
    private static final int TREND_HISTORY_DAYS = TREND_MA_LONG + 10;
    private static final int VOLUME_HISTORY_DAYS = 30;

    private final StockRepository stockRepository;
    private final StockPriceRepository stockPriceRepository;
    private final LendingBalanceRepository lendingBalanceRepository;
    private final ShortSellingRepository shortSellingRepository;
    private final SignalRepository signalRepository;

    @Override
    @Transactional
    public DetectionResult detectAll(LocalDate date) {
        long start = System.currentTimeMillis();
        log.info("=== 시그널 탐지 시작: {} ===", date);

        // 1. 전체 데이터 벌크 로드 (N+1 제거: 종목당 7쿼리 → 전체 6쿼리)
        List<Stock> stocks = stockRepository.findByIsActiveTrueAndDeletedAtIsNull();
        Set<Long> activeStockIds = stocks.stream().map(Stock::getId).collect(Collectors.toSet());

        Map<Long, LendingBalance> balanceByStock = lendingBalanceRepository.findAllByTradingDate(date)
                .stream()
                .collect(Collectors.toMap(lb -> lb.getStock().getId(), lb -> lb, (a, b) -> a));

        Map<Long, StockPrice> priceByStock = stockPriceRepository.findAllByTradingDate(date)
                .stream()
                .collect(Collectors.toMap(sp -> sp.getStock().getId(), sp -> sp, (a, b) -> a));

        Map<Long, ShortSelling> shortByStock = shortSellingRepository.findAllByTradingDate(date)
                .stream()
                .collect(Collectors.toMap(ss -> ss.getStock().getId(), ss -> ss, (a, b) -> a));

        // 추세전환용 대차잔고 히스토리 (활성 종목만, 이후 메모리에서 정렬)
        LocalDate trendFrom = date.minusDays(TREND_HISTORY_DAYS);
        Map<Long, List<LendingBalance>> trendHistory = activeStockIds.isEmpty()
                ? Map.of()
                : lendingBalanceRepository
                        .findAllByStockIdsAndTradingDateBetween(activeStockIds, trendFrom, date)
                        .stream()
                        .collect(Collectors.groupingBy(lb -> lb.getStock().getId()));

        // 숏스퀴즈용 거래량 히스토리 (활성 종목, 당일 제외)
        LocalDate volumeFrom = date.minusDays(VOLUME_HISTORY_DAYS);
        Map<Long, List<StockPrice>> volumeHistory = activeStockIds.isEmpty()
                ? Map.of()
                : stockPriceRepository
                        .findAllByStockIdsAndTradingDateBetween(activeStockIds, volumeFrom, date.minusDays(1))
                        .stream()
                        .collect(Collectors.groupingBy(sp -> sp.getStock().getId()));

        // 기존 시그널 존재 여부 Set (JOIN FETCH로 N+1 방지)
        Set<String> existingKeys = signalRepository.findBySignalDateWithStockOrderByScoreDesc(date)
                .stream()
                .map(s -> signalKey(s.getStock().getId(), s.getSignalType()))
                .collect(Collectors.toCollection(HashSet::new));

        // 2. 메모리 기반 탐지 루프 (DB 히트 없음)
        List<Signal> toSave = new ArrayList<>();

        for (Stock stock : stocks) {
            Long stockId = stock.getId();

            detectRapidDecline(stock, date, balanceByStock.get(stockId), existingKeys)
                    .ifPresent(toSave::add);

            detectTrendReversal(stock, date, trendHistory.getOrDefault(stockId, List.of()), existingKeys)
                    .ifPresent(toSave::add);

            detectShortSqueeze(
                    stock, date,
                    balanceByStock.get(stockId),
                    priceByStock.get(stockId),
                    shortByStock.get(stockId),
                    volumeHistory.getOrDefault(stockId, List.of()),
                    existingKeys
            ).ifPresent(toSave::add);
        }

        // 3. 일괄 저장
        if (!toSave.isEmpty()) {
            signalRepository.saveAll(toSave);
        }

        long rapidCount = toSave.stream().filter(s -> s.getSignalType() == SignalType.RAPID_DECLINE).count();
        long trendCount = toSave.stream().filter(s -> s.getSignalType() == SignalType.TREND_REVERSAL).count();
        long squeezeCount = toSave.stream().filter(s -> s.getSignalType() == SignalType.SHORT_SQUEEZE).count();

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== 시그널 탐지 완료: 급감 {}, 추세전환 {}, 숏스퀴즈 {} ({}ms) ===",
                rapidCount, trendCount, squeezeCount, elapsed);

        return new DetectionResult((int) rapidCount, (int) trendCount, (int) squeezeCount, elapsed);
    }

    /**
     * 시그널 1: 대차잔고 급감
     */
    private Optional<Signal> detectRapidDecline(Stock stock, LocalDate date,
                                                LendingBalance lb, Set<String> existingKeys) {
        if (lb == null || lb.getChangeRate() == null
                || lb.getChangeRate().compareTo(RAPID_DECLINE_THRESHOLD) > 0) {
            return Optional.empty();
        }

        String key = signalKey(stock.getId(), SignalType.RAPID_DECLINE);
        if (!existingKeys.add(key)) return Optional.empty();

        int score = calculateRapidDeclineScore(lb);
        var detail = Map.<String, Object>of(
                "balanceChangeRate", lb.getChangeRate(),
                "changeQuantity", lb.getChangeQuantity(),
                "consecutiveDecreaseDays", lb.getConsecutiveDecreaseDays()
        );

        return Optional.of(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.RAPID_DECLINE)
                .score(score).grade(SignalGrade.fromScore(score))
                .detail(detail)
                .build());
    }

    /**
     * 시그널 2: 추세전환 (골든크로스)
     */
    private Optional<Signal> detectTrendReversal(Stock stock, LocalDate date,
                                                 List<LendingBalance> history, Set<String> existingKeys) {
        if (history.size() < TREND_MA_LONG + 1) return Optional.empty();

        // tradingDate 오름차순 보장 (groupingBy는 순서 보장 안 됨)
        var sorted = history.stream()
                .sorted(Comparator.comparing(LendingBalance::getTradingDate))
                .toList();

        var quantities = sorted.stream().map(LendingBalance::getBalanceQuantity).toList();
        int size = quantities.size();

        double maShortToday = movingAverage(quantities, size - 1, TREND_MA_SHORT);
        double maLongToday = movingAverage(quantities, size - 1, TREND_MA_LONG);
        double maShortYesterday = movingAverage(quantities, size - 2, TREND_MA_SHORT);
        double maLongYesterday = movingAverage(quantities, size - 2, TREND_MA_LONG);

        boolean goldenCross = maShortYesterday >= maLongYesterday && maShortToday < maLongToday;
        if (!goldenCross) return Optional.empty();

        String key = signalKey(stock.getId(), SignalType.TREND_REVERSAL);
        if (!existingKeys.add(key)) return Optional.empty();

        int score = calculateTrendReversalScore(maShortToday, maLongToday, maShortYesterday, maLongYesterday);
        var detail = Map.<String, Object>of(
                "maShort", round(maShortToday),
                "maLong", round(maLongToday),
                "crossType", "GOLDEN_CROSS"
        );

        return Optional.of(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.TREND_REVERSAL)
                .score(score).grade(SignalGrade.fromScore(score))
                .detail(detail)
                .build());
    }

    /**
     * 시그널 3: 숏스퀴즈 종합 스코어
     */
    private Optional<Signal> detectShortSqueeze(Stock stock, LocalDate date,
                                                LendingBalance lb, StockPrice sp, ShortSelling ss,
                                                List<StockPrice> priceHistory,
                                                Set<String> existingKeys) {
        if (lb == null || sp == null) return Optional.empty();

        int balanceScore = scoreBalanceChange(lb.getChangeRate());
        BigDecimal volumeRatio = calcVolumeRatio(priceHistory, sp);
        int volumeScore = scoreVolumeChange(volumeRatio);
        int priceScore = scorePriceChange(sp.getChangeRate());
        int shortRatioScore = scoreShortRatio(ss);

        int totalScore = balanceScore + volumeScore + priceScore + shortRatioScore;
        if (totalScore < 40) return Optional.empty();

        String key = signalKey(stock.getId(), SignalType.SHORT_SQUEEZE);
        if (!existingKeys.add(key)) return Optional.empty();

        var detail = Map.<String, Object>of(
                "balanceChangeRate", lb.getChangeRate() != null ? lb.getChangeRate() : BigDecimal.ZERO,
                "balanceScore", balanceScore,
                "volumeChangeRate", volumeRatio,
                "volumeScore", volumeScore,
                "priceChangeRate", sp.getChangeRate() != null ? sp.getChangeRate() : BigDecimal.ZERO,
                "priceScore", priceScore,
                "shortRatioScore", shortRatioScore,
                "consecutiveDecreaseDays", lb.getConsecutiveDecreaseDays()
        );

        return Optional.of(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.SHORT_SQUEEZE)
                .score(totalScore).grade(SignalGrade.fromScore(totalScore))
                .detail(detail)
                .build());
    }

    // ========== Scoring Functions ==========

    private int calculateRapidDeclineScore(LendingBalance lb) {
        double absChange = Math.abs(lb.getChangeRate().doubleValue());
        int baseScore = (int) Math.min(60, absChange * 3);
        int consecutiveBonus = Math.min(20, lb.getConsecutiveDecreaseDays() * 5);
        return Math.min(100, baseScore + consecutiveBonus + 20);
    }

    private int calculateTrendReversalScore(double maShortToday, double maLongToday,
                                            double maShortYesterday, double maLongYesterday) {
        double divergence = Math.abs(maShortToday - maLongToday) / maLongToday * 100;
        int divergenceScore = (int) Math.min(40, divergence * 10);
        double speed = Math.abs((maShortToday - maShortYesterday) / maShortYesterday * 100);
        int speedScore = (int) Math.min(30, speed * 15);
        return Math.min(100, divergenceScore + speedScore + 30);
    }

    private int scoreBalanceChange(BigDecimal changeRate) {
        if (changeRate == null) return 0;
        double absChange = Math.abs(changeRate.doubleValue());
        return (int) Math.min(30, absChange * 1.5);
    }

    /** 오늘 거래량 / 20일 평균 거래량 비율 */
    private BigDecimal calcVolumeRatio(List<StockPrice> priceHistory, StockPrice today) {
        if (priceHistory.isEmpty() || today.getVolume() == 0) return BigDecimal.ZERO;
        double avgVolume = priceHistory.stream().mapToLong(StockPrice::getVolume).average().orElse(0);
        if (avgVolume == 0) return BigDecimal.ZERO;
        return BigDecimal.valueOf(today.getVolume() / avgVolume)
                .setScale(4, RoundingMode.HALF_UP);
    }

    /** 거래량 비율 → 스코어 (max 25) */
    private int scoreVolumeChange(BigDecimal ratio) {
        if (ratio == null || ratio.signum() == 0) return 0;
        double r = ratio.doubleValue();
        return (int) Math.max(0, Math.min(25, (r - 1) * 12.5));
    }

    private int scorePriceChange(BigDecimal changeRate) {
        if (changeRate == null) return 0;
        double change = changeRate.doubleValue();
        if (change <= 0) return 0;
        return (int) Math.min(25, change * 5);
    }

    private int scoreShortRatio(ShortSelling ss) {
        if (ss == null || ss.getShortRatio() == null) return 0;
        double ratio = ss.getShortRatio().doubleValue();
        return (int) Math.min(20, ratio * 2);
    }

    // ========== Helpers ==========

    private static String signalKey(Long stockId, SignalType type) {
        return stockId + ":" + type.name();
    }

    private double movingAverage(List<Long> values, int endIndex, int period) {
        int startIdx = Math.max(0, endIndex - period + 1);
        return values.subList(startIdx, endIndex + 1).stream()
                .mapToLong(Long::longValue).average().orElse(0);
    }

    private double round(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP).doubleValue();
    }
}
