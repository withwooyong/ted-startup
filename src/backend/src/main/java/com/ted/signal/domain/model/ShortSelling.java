package com.ted.signal.domain.model;

import jakarta.persistence.*;
import lombok.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "short_selling", uniqueConstraints = @UniqueConstraint(columnNames = {"stock_id", "trading_date"}))
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class ShortSelling {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "trading_date", nullable = false)
    private LocalDate tradingDate;

    @Column(name = "short_volume", nullable = false)
    @Builder.Default
    private Long shortVolume = 0L;

    @Column(name = "short_amount", nullable = false)
    @Builder.Default
    private Long shortAmount = 0L;

    @Column(name = "short_ratio", precision = 10, scale = 4)
    private BigDecimal shortRatio;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
