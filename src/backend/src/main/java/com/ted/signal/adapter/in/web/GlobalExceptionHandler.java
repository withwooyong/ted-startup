package com.ted.signal.adapter.in.web;

import com.ted.signal.domain.model.DomainError;
import com.ted.signal.domain.model.DomainException;
import jakarta.validation.ConstraintViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.time.Instant;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(DomainException.class)
    public ResponseEntity<Map<String, Object>> handleDomain(DomainException e) {
        var status = switch (e.getError()) {
            case DomainError.StockNotFound ignored -> HttpStatus.NOT_FOUND;
            case DomainError.InvalidParameter ignored -> HttpStatus.BAD_REQUEST;
            case DomainError.DataNotReady ignored -> HttpStatus.SERVICE_UNAVAILABLE;
        };
        return ResponseEntity.status(status).body(errorBody(status.value(), e.getMessage()));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(ConstraintViolationException e) {
        return ResponseEntity.badRequest().body(errorBody(400, e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Map<String, Object>> handleTypeMismatch(MethodArgumentTypeMismatchException e) {
        var msg = "잘못된 파라미터: " + e.getName() + " = " + e.getValue();
        return ResponseEntity.badRequest().body(errorBody(400, msg));
    }

    private Map<String, Object> errorBody(int status, String message) {
        return Map.of(
                "status", status,
                "message", message,
                "timestamp", Instant.now().toString()
        );
    }
}
