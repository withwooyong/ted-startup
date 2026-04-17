package com.ted.signal.adapter.in.web;

import com.ted.signal.domain.model.DomainError;
import com.ted.signal.domain.model.DomainException;
import jakarta.validation.ConstraintViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
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
        return ResponseEntity.badRequest().body(errorBody(400, "잘못된 파라미터: " + e.getName()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleBodyValidation(MethodArgumentNotValidException e) {
        var first = e.getBindingResult().getFieldErrors().stream().findFirst();
        var msg = first.map(fe -> fe.getField() + ": 유효하지 않은 값입니다").orElse("요청 본문 검증 실패");
        return ResponseEntity.badRequest().body(errorBody(400, msg));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> handleUnreadable(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(errorBody(400, "요청 본문을 읽을 수 없습니다"));
    }

    private Map<String, Object> errorBody(int status, String message) {
        return Map.of(
                "status", status,
                "message", message,
                "timestamp", Instant.now().toString()
        );
    }
}
