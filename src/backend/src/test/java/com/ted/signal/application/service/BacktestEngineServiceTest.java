package com.ted.signal.application.service;

import com.ted.signal.IntegrationTestBase;
import com.ted.signal.application.port.out.*;
import com.ted.signal.domain.enums.SignalGrade;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class BacktestEngineServiceTest extends IntegrationTestBase {

    @Autowired
    private BacktestEngineService backtestEngineService;

    @Autowired
    private StockRepository stockRepository;

    @Autowired
    private StockPriceRepository stockPriceRepository;

    @Autowired
    private SignalRepository signalRepository;

    @Autowired
    private BacktestResultRepository backtestResultRepository;

    @Autowired
    private LendingBalanceRepository lendingBalanceRepository;

    @Autowired
    private ShortSellingRepository shortSellingRepository;

    private Stock testStock;
    private static final LocalDate SIGNAL_DATE = LocalDate.of(2026, 1, 5); // 월요일

    @BeforeEach
    void setUp() {
        backtestResultRepository.deleteAll();
        signalRepository.deleteAll();
        shortSellingRepository.deleteAll();
        lendingBalanceRepository.deleteAll();
        stockPriceRepository.deleteAll();
        stockRepository.deleteAll();

        testStock = stockRepository.save(Stock.builder()
                .stockCode("005930")
                .stockName("삼성전자")
                .marketType("KOSPI")
                .sector("반도체")
                .build());
    }

    @Test
    @DisplayName("수익률 계산: 시그널 발생일 대비 5/10/20일 후 주가 변동률")
    void calculateReturns() {
        // given: 시그널 1건 + 30영업일 주가 데이터
        signalRepository.save(Signal.builder()
                .stock(testStock)
                .signalDate(SIGNAL_DATE)
                .signalType(SignalType.RAPID_DECLINE)
                .score(80)
                .grade(SignalGrade.A)
                .build());

        // 시그널일 기준가: 50,000원
        // 5영업일 후: 52,000원 (+4%)
        // 10영업일 후: 53,000원 (+6%)
        // 20영업일 후: 55,000원 (+10%)
        insertPriceData(SIGNAL_DATE, 50_000L, 30, new long[]{
                50_000, 50_500, 51_000, 51_200, 51_500,  // day 0-4
                52_000, 52_200, 52_500, 52_800, 53_000,  // day 5-9 (5일후=52000)
                53_000, 53_200, 53_500, 53_200, 53_800,  // day 10-14 (10일후=53000)
                54_000, 54_200, 54_500, 54_800, 55_000,  // day 15-19
                55_000, 55_200, 55_500, 55_800, 56_000,  // day 20-24 (20일후=55000)
                56_200, 56_500, 56_800, 57_000, 57_200   // day 25-29
        });

        // when
        var result = backtestEngineService.execute(
                SIGNAL_DATE.minusDays(1), SIGNAL_DATE.plusDays(1));

        // then
        assertThat(result.totalSignalsProcessed()).isEqualTo(1);
        assertThat(result.returnsCalculated()).isEqualTo(1);
        assertThat(result.backtestResultsSaved()).isEqualTo(1);

        // 시그널의 수익률 검증
        var signal = signalRepository.findBySignalDateOrderByScoreDesc(SIGNAL_DATE).get(0);
        assertThat(signal.getReturn5d()).isNotNull();
        assertThat(signal.getReturn5d().doubleValue()).isCloseTo(4.0, org.assertj.core.data.Offset.offset(0.5));
        assertThat(signal.getReturn10d()).isNotNull();
        assertThat(signal.getReturn10d().doubleValue()).isCloseTo(6.0, org.assertj.core.data.Offset.offset(0.5));
        assertThat(signal.getReturn20d()).isNotNull();
        assertThat(signal.getReturn20d().doubleValue()).isCloseTo(10.0, org.assertj.core.data.Offset.offset(0.5));
    }

    @Test
    @DisplayName("적중률 집계: 양수 수익률 비율 계산")
    void aggregateHitRate() {
        // given: RAPID_DECLINE 시그널 3건 (2건 양수 수익, 1건 음수 수익)
        createSignalWithPrices(SIGNAL_DATE, SignalType.RAPID_DECLINE, 50_000, 52_000);       // +4% hit
        createSignalWithPrices(SIGNAL_DATE.plusDays(7), SignalType.RAPID_DECLINE, 50_000, 48_000); // -4% miss
        createSignalWithPrices(SIGNAL_DATE.plusDays(14), SignalType.RAPID_DECLINE, 50_000, 51_000); // +2% hit

        // when
        var result = backtestEngineService.execute(
                SIGNAL_DATE.minusDays(1), SIGNAL_DATE.plusDays(30));

        // then
        assertThat(result.backtestResultsSaved()).isEqualTo(1);

        var backtestResult = backtestResultRepository.findFirstBySignalTypeOrderByCreatedAtDesc("RAPID_DECLINE");
        assertThat(backtestResult).isPresent();
        assertThat(backtestResult.get().getTotalSignals()).isEqualTo(3);
        // 5일 적중률: 2/3 = 66.67%
        assertThat(backtestResult.get().getHitRate5d().doubleValue()).isCloseTo(66.67, org.assertj.core.data.Offset.offset(1.0));
    }

    @Test
    @DisplayName("미래 주가 데이터 부족: 수익률을 null로 처리")
    void insufficientFutureData() {
        // given: 시그널은 있지만 이후 주가가 3일치밖에 없음
        signalRepository.save(Signal.builder()
                .stock(testStock)
                .signalDate(SIGNAL_DATE)
                .signalType(SignalType.RAPID_DECLINE)
                .score(70)
                .grade(SignalGrade.B)
                .build());

        // 시그널일 + 3영업일만
        insertPriceData(SIGNAL_DATE, 50_000L, 4, new long[]{50_000, 50_500, 51_000, 51_500});

        // when
        var result = backtestEngineService.execute(
                SIGNAL_DATE.minusDays(1), SIGNAL_DATE.plusDays(1));

        // then
        assertThat(result.totalSignalsProcessed()).isEqualTo(1);
        var signal = signalRepository.findBySignalDateOrderByScoreDesc(SIGNAL_DATE).get(0);
        assertThat(signal.getReturn5d()).isNull();  // 5영업일 후 데이터 없음
        assertThat(signal.getReturn10d()).isNull();
        assertThat(signal.getReturn20d()).isNull();
    }

    @Test
    @DisplayName("시그널 없는 기간: 빈 결과 반환")
    void noSignalsInPeriod() {
        // when
        var result = backtestEngineService.execute(
                LocalDate.of(2020, 1, 1), LocalDate.of(2020, 12, 31));

        // then
        assertThat(result.totalSignalsProcessed()).isZero();
        assertThat(result.returnsCalculated()).isZero();
        assertThat(result.backtestResultsSaved()).isZero();
    }

    // ========== Test Helpers ==========

    private void insertPriceData(LocalDate startDate, long basePrice, int days, long[] prices) {
        int priceIdx = 0;
        for (int i = 0; i < days && priceIdx < prices.length; i++) {
            LocalDate date = startDate.plusDays(i);
            // 주말 스킵
            if (date.getDayOfWeek().getValue() > 5) {
                days++; // 주말분 보정
                continue;
            }
            stockPriceRepository.save(StockPrice.builder()
                    .stock(testStock)
                    .tradingDate(date)
                    .closePrice(prices[priceIdx])
                    .openPrice(prices[priceIdx])
                    .highPrice(prices[priceIdx] + 500)
                    .lowPrice(prices[priceIdx] - 500)
                    .volume(100_000L)
                    .changeRate(priceIdx > 0
                            ? BigDecimal.valueOf((prices[priceIdx] - prices[priceIdx - 1]) * 100.0 / prices[priceIdx - 1])
                            : BigDecimal.ZERO)
                    .build());
            priceIdx++;
        }
    }

    private void createSignalWithPrices(LocalDate signalDate, SignalType type, long basePrice, long futurePrice) {
        // 각 시그널마다 별도 종목 생성 (unique constraint 방지)
        String code = String.format("%06d", (int) (Math.random() * 999999));
        Stock stock = stockRepository.save(Stock.builder()
                .stockCode(code)
                .stockName("테스트종목_" + code)
                .marketType("KOSPI")
                .build());

        signalRepository.save(Signal.builder()
                .stock(stock)
                .signalDate(signalDate)
                .signalType(type)
                .score(70)
                .grade(SignalGrade.B)
                .build());

        // 시그널일 주가
        stockPriceRepository.save(StockPrice.builder()
                .stock(stock)
                .tradingDate(signalDate)
                .closePrice(basePrice)
                .openPrice(basePrice).highPrice(basePrice).lowPrice(basePrice)
                .volume(100_000L)
                .changeRate(BigDecimal.ZERO)
                .build());

        // 5~25영업일 후 주가 (선형 보간)
        for (int i = 1; i <= 35; i++) {
            LocalDate date = signalDate.plusDays(i);
            if (date.getDayOfWeek().getValue() > 5) continue;
            long price = basePrice + (futurePrice - basePrice) * i / 35;
            stockPriceRepository.save(StockPrice.builder()
                    .stock(stock)
                    .tradingDate(date)
                    .closePrice(price)
                    .openPrice(price).highPrice(price).lowPrice(price)
                    .volume(100_000L)
                    .changeRate(BigDecimal.ZERO)
                    .build());
        }
    }
}
