package com.ted.signal.domain.model;

import com.ted.signal.domain.enums.SignalGrade;
import com.ted.signal.domain.enums.SignalType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Map;

@Entity
@Table(name = "signal", uniqueConstraints = @UniqueConstraint(columnNames = {"stock_id", "signal_date", "signal_type"}))
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class Signal {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "stock_id", nullable = false)
    private Stock stock;

    @Column(name = "signal_date", nullable = false)
    private LocalDate signalDate;

    @Enumerated(EnumType.STRING)
    @Column(name = "signal_type", nullable = false, length = 30)
    private SignalType signalType;

    @Column(nullable = false)
    private Integer score;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 1)
    private SignalGrade grade;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> detail;

    @Column(name = "return_5d", precision = 10, scale = 4)
    private BigDecimal return5d;

    @Column(name = "return_10d", precision = 10, scale = 4)
    private BigDecimal return10d;

    @Column(name = "return_20d", precision = 10, scale = 4)
    private BigDecimal return20d;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    public void updateReturns(BigDecimal r5d, BigDecimal r10d, BigDecimal r20d) {
        this.return5d = r5d;
        this.return10d = r10d;
        this.return20d = r20d;
    }
}
