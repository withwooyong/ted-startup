package com.ted.signal.domain.model;

import jakarta.persistence.*;
import lombok.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "stock_price", uniqueConstraints = @UniqueConstraint(columnNames = {"stock_id", "trading_date"}))
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class StockPrice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "trading_date", nullable = false)
    private LocalDate tradingDate;

    @Column(name = "close_price", nullable = false)
    private Long closePrice;

    @Column(name = "open_price")
    private Long openPrice;

    @Column(name = "high_price")
    private Long highPrice;

    @Column(name = "low_price")
    private Long lowPrice;

    @Column(nullable = false)
    @Builder.Default
    private Long volume = 0L;

    @Column(name = "market_cap")
    private Long marketCap;

    @Column(name = "change_rate", precision = 10, scale = 4)
    private BigDecimal changeRate;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
