package com.ted.signal.adapter.in.web;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 관리자 API Key 검증 — Timing-safe 비교.
 * 빈 키 설정(adminApiKey=="") 시 모든 요청을 거부한다.
 */
@Component
public class ApiKeyValidator {

    private final String adminApiKey;

    public ApiKeyValidator(@Value("${signal.admin.api-key:}") String adminApiKey) {
        this.adminApiKey = adminApiKey;
    }

    public boolean isValid(String apiKey) {
        if (adminApiKey == null || adminApiKey.isBlank()) return false;
        byte[] expected = adminApiKey.getBytes(StandardCharsets.UTF_8);
        byte[] actual = (apiKey != null ? apiKey : "").getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expected, actual);
    }
}
