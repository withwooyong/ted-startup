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
import java.time.DayOfWeek;
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

        var stocks = stockRepository.findByIsActiveTrueAndDeletedAtIsNull();
        int rapidCount = 0, trendCount = 0, squeezeCount = 0;

        for (var stock : stocks) {
            // 대차잔고 급감 시그널
            if (detectRapidDecline(stock, date)) rapidCount++;

            // 추세전환 시그널
            if (detectTrendReversal(stock, date)) trendCount++;

            // 숏스퀴즈 종합 스코어
            if (detectShortSqueeze(stock, date)) squeezeCount++;
        }

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== 시그널 탐지 완료: 급감 {}, 추세전환 {}, 숏스퀴즈 {} ({}ms) ===",
                rapidCount, trendCount, squeezeCount, elapsed);

        return new DetectionResult(rapidCount, trendCount, squeezeCount, elapsed);
    }

    /**
     * 시그널 1: 대차잔고 급감
     * 전일 대비 대차잔고 감소율이 임계값(-10%) 이하인 종목
     */
    private boolean detectRapidDecline(Stock stock, LocalDate date) {
        var balance = lendingBalanceRepository.findByStockIdAndTradingDate(stock.getId(), date);
        if (balance.isEmpty()) return false;

        var lb = balance.get();
        if (lb.getChangeRate() == null || lb.getChangeRate().compareTo(RAPID_DECLINE_THRESHOLD) > 0) return false;

        // 이미 탐지된 시그널이면 스킵
        if (signalRepository.existsByStockIdAndSignalDateAndSignalType(
                stock.getId(), date, SignalType.RAPID_DECLINE)) return false;

        int score = calculateRapidDeclineScore(lb);
        var detail = Map.<String, Object>of(
                "balanceChangeRate", lb.getChangeRate(),
                "changeQuantity", lb.getChangeQuantity(),
                "consecutiveDecreaseDays", lb.getConsecutiveDecreaseDays()
        );

        signalRepository.save(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.RAPID_DECLINE)
                .score(score).grade(SignalGrade.fromScore(score))
                .detail(detail)
                .build());
        return true;
    }

    /**
     * 시그널 2: 추세전환
     * 대차잔고 5일/20일 이동평균 골든크로스 감지
     */
    private boolean detectTrendReversal(Stock stock, LocalDate date) {
        var from = date.minusDays(TREND_MA_LONG + 10); // 영업일 여유분
        var balances = lendingBalanceRepository
                .findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(stock.getId(), from, date);

        if (balances.size() < TREND_MA_LONG + 1) return false;

        // 이동평균 계산
        var quantities = balances.stream().map(LendingBalance::getBalanceQuantity).toList();
        int size = quantities.size();

        double maShortToday = movingAverage(quantities, size - 1, TREND_MA_SHORT);
        double maLongToday = movingAverage(quantities, size - 1, TREND_MA_LONG);
        double maShortYesterday = movingAverage(quantities, size - 2, TREND_MA_SHORT);
        double maLongYesterday = movingAverage(quantities, size - 2, TREND_MA_LONG);

        // 골든크로스: 단기MA가 장기MA를 하향 돌파 (대차잔고 감소 = 숏커버링 신호)
        boolean goldenCross = maShortYesterday >= maLongYesterday && maShortToday < maLongToday;
        if (!goldenCross) return false;

        if (signalRepository.existsByStockIdAndSignalDateAndSignalType(
                stock.getId(), date, SignalType.TREND_REVERSAL)) return false;

        int score = calculateTrendReversalScore(maShortToday, maLongToday, maShortYesterday, maLongYesterday);
        var detail = Map.<String, Object>of(
                "maShort", round(maShortToday),
                "maLong", round(maLongToday),
                "crossType", "GOLDEN_CROSS"
        );

        signalRepository.save(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.TREND_REVERSAL)
                .score(score).grade(SignalGrade.fromScore(score))
                .detail(detail)
                .build());
        return true;
    }

    /**
     * 시그널 3: 숏스퀴즈 종합 스코어
     * 대차잔고 감소율(30%) + 거래량 급증(25%) + 주가 상승(25%) + 공매도 비율(20%)
     */
    private boolean detectShortSqueeze(Stock stock, LocalDate date) {
        var balance = lendingBalanceRepository.findByStockIdAndTradingDate(stock.getId(), date);
        var price = stockPriceRepository.findByStockIdAndTradingDate(stock.getId(), date);
        var shortSell = shortSellingRepository.findByStockIdAndTradingDate(stock.getId(), date);

        if (balance.isEmpty() || price.isEmpty()) return false;

        var lb = balance.get();
        var sp = price.get();

        // 각 팩터 스코어 계산 (0~max)
        int balanceScore = scoreBalanceChange(lb.getChangeRate());           // max 30
        int volumeScore = scoreVolumeChange(stock.getId(), date, sp);       // max 25
        int priceScore = scorePriceChange(sp.getChangeRate());              // max 25
        int shortRatioScore = scoreShortRatio(shortSell.orElse(null));      // max 20

        int totalScore = balanceScore + volumeScore + priceScore + shortRatioScore;

        // 스코어 40 미만이면 시그널 생성하지 않음
        if (totalScore < 40) return false;

        if (signalRepository.existsByStockIdAndSignalDateAndSignalType(
                stock.getId(), date, SignalType.SHORT_SQUEEZE)) return false;

        var detail = Map.<String, Object>of(
                "balanceChangeRate", lb.getChangeRate() != null ? lb.getChangeRate() : BigDecimal.ZERO,
                "balanceScore", balanceScore,
                "volumeChangeRate", volumeScore, // 거래량 스코어 (별도 변동률 계산은 scoreVolumeChange 내부)
                "volumeScore", volumeScore,
                "priceChangeRate", sp.getChangeRate() != null ? sp.getChangeRate() : BigDecimal.ZERO,
                "priceScore", priceScore,
                "shortRatioScore", shortRatioScore,
                "consecutiveDecreaseDays", lb.getConsecutiveDecreaseDays()
        );

        signalRepository.save(Signal.builder()
                .stock(stock).signalDate(date)
                .signalType(SignalType.SHORT_SQUEEZE)
                .score(totalScore).grade(SignalGrade.fromScore(totalScore))
                .detail(detail)
                .build());
        return true;
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
        // 교차 강도: 단기MA와 장기MA의 괴리율
        double divergence = Math.abs(maShortToday - maLongToday) / maLongToday * 100;
        int divergenceScore = (int) Math.min(40, divergence * 10);
        // 추세 방향 전환 속도
        double speed = Math.abs((maShortToday - maShortYesterday) / maShortYesterday * 100);
        int speedScore = (int) Math.min(30, speed * 15);
        return Math.min(100, divergenceScore + speedScore + 30);
    }

    /** 대차잔고 변동률 → 스코어 (max 30) */
    private int scoreBalanceChange(BigDecimal changeRate) {
        if (changeRate == null) return 0;
        double absChange = Math.abs(changeRate.doubleValue());
        return (int) Math.min(30, absChange * 1.5);
    }

    /** 거래량 급증 → 스코어 (max 25): 20일 평균 대비 */
    private int scoreVolumeChange(Long stockId, LocalDate date, StockPrice today) {
        var from = date.minusDays(30);
        var prices = stockPriceRepository.findByStockIdAndTradingDateBetweenOrderByTradingDateAsc(
                stockId, from, date.minusDays(1));

        if (prices.isEmpty() || today.getVolume() == 0) return 0;

        double avgVolume = prices.stream().mapToLong(StockPrice::getVolume).average().orElse(0);
        if (avgVolume == 0) return 0;

        double ratio = today.getVolume() / avgVolume;
        return (int) Math.max(0, Math.min(25, (ratio - 1) * 12.5));
    }

    /** 주가 상승률 → 스코어 (max 25) */
    private int scorePriceChange(BigDecimal changeRate) {
        if (changeRate == null) return 0;
        double change = changeRate.doubleValue();
        if (change <= 0) return 0;
        return (int) Math.min(25, change * 5);
    }

    /** 공매도 비율 → 스코어 (max 20): 비율이 높을수록 숏스퀴즈 가능성 */
    private int scoreShortRatio(ShortSelling ss) {
        if (ss == null || ss.getShortRatio() == null) return 0;
        double ratio = ss.getShortRatio().doubleValue();
        return (int) Math.min(20, ratio * 2);
    }

    // ========== Helpers ==========

    private double movingAverage(List<Long> values, int endIndex, int period) {
        int start = Math.max(0, endIndex - period + 1);
        return values.subList(start, endIndex + 1).stream()
                .mapToLong(Long::longValue).average().orElse(0);
    }

    private double round(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP).doubleValue();
    }
}
