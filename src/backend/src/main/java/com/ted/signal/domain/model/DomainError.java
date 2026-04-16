package com.ted.signal.domain.model;

/**
 * 도메인 에러 sealed interface (컨벤션: 에러 타입은 sealed interface)
 */
public sealed interface DomainError {

    record StockNotFound(String stockCode) implements DomainError {}

    record InvalidParameter(String param, String reason) implements DomainError {}

    record DataNotReady(String message) implements DomainError {}
}
