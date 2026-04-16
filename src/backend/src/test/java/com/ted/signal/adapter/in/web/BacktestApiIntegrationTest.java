package com.ted.signal.adapter.in.web;

import com.ted.signal.IntegrationTestBase;
import com.ted.signal.application.port.out.*;
import com.ted.signal.domain.model.BacktestResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class BacktestApiIntegrationTest extends IntegrationTestBase {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private BacktestResultRepository backtestResultRepository;

    @Autowired
    private SignalRepository signalRepository;

    @Autowired
    private ShortSellingRepository shortSellingRepository;

    @Autowired
    private LendingBalanceRepository lendingBalanceRepository;

    @Autowired
    private StockPriceRepository stockPriceRepository;

    @Autowired
    private StockRepository stockRepository;

    @BeforeEach
    void setUp() {
        backtestResultRepository.deleteAll();
        signalRepository.deleteAll();
        shortSellingRepository.deleteAll();
        lendingBalanceRepository.deleteAll();
        stockPriceRepository.deleteAll();
        stockRepository.deleteAll();
    }

    @Test
    @DisplayName("GET /api/backtest: 백테스팅 결과 조회")
    void getBacktestResults() throws Exception {
        // given
        backtestResultRepository.save(BacktestResult.builder()
                .signalType("RAPID_DECLINE")
                .periodStart(LocalDate.of(2023, 1, 1))
                .periodEnd(LocalDate.of(2026, 1, 1))
                .totalSignals(100)
                .hitCount5d(65)
                .hitRate5d(new BigDecimal("65.0000"))
                .avgReturn5d(new BigDecimal("3.2500"))
                .hitCount10d(60)
                .hitRate10d(new BigDecimal("60.0000"))
                .avgReturn10d(new BigDecimal("5.1000"))
                .hitCount20d(55)
                .hitRate20d(new BigDecimal("55.0000"))
                .avgReturn20d(new BigDecimal("7.8000"))
                .build());

        // when & then
        mockMvc.perform(get("/api/backtest"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].signalType", is("RAPID_DECLINE")))
                .andExpect(jsonPath("$[0].totalSignals", is(100)))
                .andExpect(jsonPath("$[0].hitRate5d", is(65.0)));
    }

    @Test
    @DisplayName("POST /api/backtest/run: API Key 없으면 403")
    void runBacktestForbiddenWithoutApiKey() throws Exception {
        mockMvc.perform(post("/api/backtest/run"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("POST /api/backtest/run: 잘못된 API Key이면 403")
    void runBacktestForbiddenWithWrongKey() throws Exception {
        mockMvc.perform(post("/api/backtest/run")
                        .header("X-API-Key", "wrong-key"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("POST /api/backtest/run: 유효한 API Key로 실행 성공")
    void runBacktestSuccess() throws Exception {
        mockMvc.perform(post("/api/backtest/run")
                        .header("X-API-Key", "test-key")
                        .param("from", "2026-01-01")
                        .param("to", "2026-04-01"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalSignalsProcessed").isNumber())
                .andExpect(jsonPath("$.elapsedMs").isNumber());
    }

    @Test
    @DisplayName("POST /api/backtest/run: 파라미터 없으면 기본값 3년 적용")
    void runBacktestWithDefaults() throws Exception {
        mockMvc.perform(post("/api/backtest/run")
                        .header("X-API-Key", "test-key"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalSignalsProcessed", is(0)));
    }
}
