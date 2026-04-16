package com.ted.signal.domain.model;

import jakarta.persistence.*;
import lombok.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "lending_balance", uniqueConstraints = @UniqueConstraint(columnNames = {"stock_id", "trading_date"}))
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class LendingBalance {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "trading_date", nullable = false)
    private LocalDate tradingDate;

    @Column(name = "balance_quantity", nullable = false)
    @Builder.Default
    private Long balanceQuantity = 0L;

    @Column(name = "balance_amount", nullable = false)
    @Builder.Default
    private Long balanceAmount = 0L;

    @Column(name = "change_rate", precision = 10, scale = 4)
    private BigDecimal changeRate;

    @Column(name = "change_quantity")
    @Builder.Default
    private Long changeQuantity = 0L;

    @Column(name = "consecutive_decrease_days")
    @Builder.Default
    private Integer consecutiveDecreaseDays = 0;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
