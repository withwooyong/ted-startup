package com.ted.signal.adapter.in.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ted.signal.IntegrationTestBase;
import com.ted.signal.application.port.out.NotificationPreferenceRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class NotificationApiIntegrationTest extends IntegrationTestBase {

    private static final String API_KEY_HEADER = "X-API-Key";
    private static final String VALID_KEY = "test-key";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private NotificationPreferenceRepository repository;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        repository.deleteAll();
    }

    @Test
    @DisplayName("GET /api/notifications/preferences: 인증 없이 조회 가능, 기존 row 없으면 기본값 생성")
    void getCreatesDefaultWhenMissing() throws Exception {
        mockMvc.perform(get("/api/notifications/preferences"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.dailySummaryEnabled", is(true)))
                .andExpect(jsonPath("$.urgentAlertEnabled", is(true)))
                .andExpect(jsonPath("$.batchFailureEnabled", is(true)))
                .andExpect(jsonPath("$.weeklyReportEnabled", is(true)))
                .andExpect(jsonPath("$.minScore", is(60)))
                .andExpect(jsonPath("$.signalTypes", hasSize(3)));
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: API Key 없으면 401")
    void updateUnauthorizedWithoutApiKey() throws Exception {
        mockMvc.perform(put("/api/notifications/preferences")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validBody()))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: 잘못된 API Key면 401")
    void updateUnauthorizedWithWrongApiKey() throws Exception {
        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, "wrong-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validBody()))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: 모든 필드 업데이트 + 영속 확인")
    void updateAllFields() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", false,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", false,
                "weeklyReportEnabled", true,
                "minScore", 75,
                "signalTypes", List.of("RAPID_DECLINE", "SHORT_SQUEEZE")
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.dailySummaryEnabled", is(false)))
                .andExpect(jsonPath("$.minScore", is(75)))
                .andExpect(jsonPath("$.signalTypes", containsInAnyOrder("RAPID_DECLINE", "SHORT_SQUEEZE")));

        mockMvc.perform(get("/api/notifications/preferences"))
                .andExpect(jsonPath("$.minScore", is(75)))
                .andExpect(jsonPath("$.dailySummaryEnabled", is(false)));
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: minScore 범위 벗어나면 400")
    void updateRejectsOutOfRangeScore() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", true,
                "weeklyReportEnabled", true,
                "minScore", 150,
                "signalTypes", List.of("RAPID_DECLINE")
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: 알 수 없는 signalType이면 400 — 입력 값 반사 없음")
    void updateRejectsUnknownSignalType() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", true,
                "weeklyReportEnabled", true,
                "minScore", 60,
                "signalTypes", List.of("RAPID_DECLINE", "UNKNOWN_TYPE")
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                // 공격자가 보낸 "UNKNOWN_TYPE" 문자열이 에러 응답에 반사되지 않음
                .andExpect(jsonPath("$.message", not(containsString("UNKNOWN_TYPE"))));
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: signalTypes 빈 배열이면 400")
    void updateRejectsEmptySignalTypes() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", true,
                "weeklyReportEnabled", true,
                "minScore", 60,
                "signalTypes", List.of()
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: signalTypes 4개 이상이면 400 (DoS 방지)")
    void updateRejectsOversizedSignalTypes() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", true,
                "weeklyReportEnabled", true,
                "minScore", 60,
                "signalTypes", List.of("RAPID_DECLINE", "TREND_REVERSAL", "SHORT_SQUEEZE", "EXTRA_TYPE")
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("PUT /api/notifications/preferences: 필수 필드 누락이면 400")
    void updateRejectsMissingField() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true
        ));

        mockMvc.perform(put("/api/notifications/preferences")
                        .header(API_KEY_HEADER, VALID_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    private String validBody() throws Exception {
        return objectMapper.writeValueAsString(Map.of(
                "dailySummaryEnabled", true,
                "urgentAlertEnabled", true,
                "batchFailureEnabled", true,
                "weeklyReportEnabled", true,
                "minScore", 60,
                "signalTypes", List.of("RAPID_DECLINE")
        ));
    }
}
