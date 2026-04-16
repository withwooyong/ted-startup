package com.ted.signal.domain.model;

import lombok.Getter;

@Getter
public class DomainException extends RuntimeException {

    private final DomainError error;

    public DomainException(DomainError error) {
        super(formatMessage(error));
        this.error = error;
    }

    private static String formatMessage(DomainError error) {
        return switch (error) {
            case DomainError.StockNotFound e -> "종목을 찾을 수 없어요: " + e.stockCode();
            case DomainError.InvalidParameter e -> "잘못된 파라미터 (" + e.param() + "): " + e.reason();
            case DomainError.DataNotReady e -> e.message();
        };
    }
}
