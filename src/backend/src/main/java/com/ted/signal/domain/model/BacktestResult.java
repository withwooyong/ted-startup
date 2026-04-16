package com.ted.signal.domain.model;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "backtest_result")
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class BacktestResult {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "signal_type", nullable = false, length = 30)
    private String signalType;

    @Column(name = "period_start", nullable = false)
    private LocalDate periodStart;

    @Column(name = "period_end", nullable = false)
    private LocalDate periodEnd;

    @Column(name = "total_signals", nullable = false)
    @Builder.Default
    private Integer totalSignals = 0;

    @Column(name = "hit_count_5d")
    @Builder.Default
    private Integer hitCount5d = 0;

    @Column(name = "hit_rate_5d", precision = 10, scale = 4)
    private BigDecimal hitRate5d;

    @Column(name = "avg_return_5d", precision = 10, scale = 4)
    private BigDecimal avgReturn5d;

    @Column(name = "hit_count_10d")
    @Builder.Default
    private Integer hitCount10d = 0;

    @Column(name = "hit_rate_10d", precision = 10, scale = 4)
    private BigDecimal hitRate10d;

    @Column(name = "avg_return_10d", precision = 10, scale = 4)
    private BigDecimal avgReturn10d;

    @Column(name = "hit_count_20d")
    @Builder.Default
    private Integer hitCount20d = 0;

    @Column(name = "hit_rate_20d", precision = 10, scale = 4)
    private BigDecimal hitRate20d;

    @Column(name = "avg_return_20d", precision = 10, scale = 4)
    private BigDecimal avgReturn20d;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
