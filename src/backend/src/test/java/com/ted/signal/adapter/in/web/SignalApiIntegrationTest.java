package com.ted.signal.adapter.in.web;

import com.ted.signal.IntegrationTestBase;
import com.ted.signal.application.port.out.SignalRepository;
import com.ted.signal.application.port.out.StockRepository;
import com.ted.signal.domain.enums.SignalGrade;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.Signal;
import com.ted.signal.domain.model.Stock;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.util.Map;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class SignalApiIntegrationTest extends IntegrationTestBase {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private SignalRepository signalRepository;

    @Autowired
    private StockRepository stockRepository;

    private Stock testStock;
    private static final LocalDate TARGET_DATE = LocalDate.of(2026, 4, 15);

    @BeforeEach
    void setUp() {
        signalRepository.deleteAll();
        stockRepository.deleteAll();

        testStock = stockRepository.save(Stock.builder()
                .stockCode("005930")
                .stockName("삼성전자")
                .marketType("KOSPI")
                .sector("반도체")
                .build());
    }

    @Test
    @DisplayName("GET /api/signals: 날짜별 시그널 조회")
    void getSignalsByDate() throws Exception {
        // given
        signalRepository.save(Signal.builder()
                .stock(testStock)
                .signalDate(TARGET_DATE)
                .signalType(SignalType.RAPID_DECLINE)
                .score(85)
                .grade(SignalGrade.A)
                .detail(Map.of("balanceChangeRate", -15.0))
                .build());

        // when & then
        mockMvc.perform(get("/api/signals")
                        .param("date", TARGET_DATE.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].stockCode", is("005930")))
                .andExpect(jsonPath("$[0].stockName", is("삼성전자")))
                .andExpect(jsonPath("$[0].signalType", is("RAPID_DECLINE")))
                .andExpect(jsonPath("$[0].score", is(85)));
    }

    @Test
    @DisplayName("GET /api/signals: 타입 필터링")
    void getSignalsFilteredByType() throws Exception {
        // given
        signalRepository.save(Signal.builder()
                .stock(testStock)
                .signalDate(TARGET_DATE)
                .signalType(SignalType.RAPID_DECLINE)
                .score(85).grade(SignalGrade.A)
                .build());
        // SHORT_SQUEEZE는 같은 종목+날짜에 다른 타입으로 추가 가능
        signalRepository.save(Signal.builder()
                .stock(testStock)
                .signalDate(TARGET_DATE)
                .signalType(SignalType.SHORT_SQUEEZE)
                .score(70).grade(SignalGrade.B)
                .build());

        // when & then: SHORT_SQUEEZE만 필터
        mockMvc.perform(get("/api/signals")
                        .param("date", TARGET_DATE.toString())
                        .param("type", "SHORT_SQUEEZE"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].signalType", is("SHORT_SQUEEZE")));
    }

    @Test
    @DisplayName("POST /api/signals/detect: API Key 인증 검증")
    void detectRequiresApiKey() throws Exception {
        mockMvc.perform(post("/api/signals/detect"))
                .andExpect(status().isUnauthorized());
    }
}
