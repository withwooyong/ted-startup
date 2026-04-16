package com.ted.signal.adapter.out.external;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
@Slf4j
public class TelegramClient {

    private static final String TELEGRAM_API = "https://api.telegram.org/bot";

    private final RestClient restClient;
    private final String botToken;
    private final String chatId;
    private final boolean enabled;

    public TelegramClient(
            @Value("${telegram.bot-token:}") String botToken,
            @Value("${telegram.chat-id:}") String chatId) {
        this.botToken = botToken;
        this.chatId = chatId;
        this.enabled = !botToken.isBlank() && !chatId.isBlank();
        this.restClient = RestClient.builder()
                .baseUrl(TELEGRAM_API)
                .build();

        if (enabled) {
            log.info("텔레그램 알림 활성화 (chatId: {})", chatId);
        } else {
            log.warn("텔레그램 알림 비활성화 — bot-token 또는 chat-id 미설정");
        }
    }

    /**
     * 텔레그램 메시지 발송
     * @param text HTML 파싱 모드 메시지
     * @return 발송 성공 여부
     */
    public boolean sendMessage(String text) {
        if (!enabled) {
            log.debug("텔레그램 비활성 상태 — 메시지 스킵");
            return false;
        }

        try {
            restClient.post()
                    .uri("/{token}/sendMessage", botToken)
                    .body(Map.of(
                            "chat_id", chatId,
                            "text", text,
                            "parse_mode", "HTML"
                    ))
                    .retrieve()
                    .toBodilessEntity();

            log.info("텔레그램 발송 성공 (길이: {})", text.length());
            return true;
        } catch (Exception e) {
            log.error("텔레그램 발송 실패: {}", e.getMessage());
            return false;
        }
    }

    public boolean isEnabled() {
        return enabled;
    }
}
