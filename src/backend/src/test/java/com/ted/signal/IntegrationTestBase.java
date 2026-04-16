package com.ted.signal;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * 통합 테스트 기반 클래스 — 싱글톤 컨테이너 패턴
 * 모든 테스트 클래스가 동일한 PostgreSQL 컨테이너를 공유하여 컨텍스트 캐싱 문제 방지
 */
@SpringBootTest
public abstract class IntegrationTestBase {

    static final PostgreSQLContainer<?> POSTGRES;

    static {
        POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
                .withDatabaseName("signal_test")
                .withUsername("test")
                .withPassword("test");
        POSTGRES.start();
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
        registry.add("spring.batch.jdbc.initialize-schema", () -> "always");
        registry.add("signal.admin.api-key", () -> "test-key");
        registry.add("telegram.bot-token", () -> "");
        registry.add("telegram.chat-id", () -> "");
    }
}
