package com.ted.signal.domain.model;

import com.ted.signal.domain.enums.SignalType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;

@Entity
@Table(name = "notification_preference")
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class NotificationPreference {

    public static final Long SINGLETON_ID = 1L;
    public static final int DEFAULT_MIN_SCORE = 60;

    @Id
    private Long id;

    @Column(name = "daily_summary_enabled", nullable = false)
    @Builder.Default
    private Boolean dailySummaryEnabled = true;

    @Column(name = "urgent_alert_enabled", nullable = false)
    @Builder.Default
    private Boolean urgentAlertEnabled = true;

    @Column(name = "batch_failure_enabled", nullable = false)
    @Builder.Default
    private Boolean batchFailureEnabled = true;

    @Column(name = "weekly_report_enabled", nullable = false)
    @Builder.Default
    private Boolean weeklyReportEnabled = true;

    @Column(name = "min_score", nullable = false)
    @Builder.Default
    private Integer minScore = DEFAULT_MIN_SCORE;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "signal_types", columnDefinition = "jsonb", nullable = false)
    @Builder.Default
    private List<String> signalTypes = List.of(
            SignalType.RAPID_DECLINE.name(),
            SignalType.TREND_REVERSAL.name(),
            SignalType.SHORT_SQUEEZE.name()
    );

    @Column(name = "updated_at", nullable = false)
    @Builder.Default
    private Instant updatedAt = Instant.now();

    public static NotificationPreference createDefault() {
        return NotificationPreference.builder()
                .id(SINGLETON_ID)
                .build();
    }

    /**
     * 도메인 방어 검증 — Controller 우회(배치/내부 호출)도 동일 규칙 강제.
     * 입력 값은 호출자가 신뢰 가능 범위에서 검증(UseCase compact constructor)했다고 가정하되,
     * 도메인 자체 불변식을 이중으로 보장한다.
     */
    public void update(
            boolean dailySummaryEnabled,
            boolean urgentAlertEnabled,
            boolean batchFailureEnabled,
            boolean weeklyReportEnabled,
            int minScore,
            List<String> signalTypes
    ) {
        if (minScore < 0 || minScore > 100) {
            throw new IllegalArgumentException("minScore must be 0-100");
        }
        if (signalTypes == null || signalTypes.isEmpty()) {
            throw new IllegalArgumentException("signalTypes must not be empty");
        }
        this.dailySummaryEnabled = dailySummaryEnabled;
        this.urgentAlertEnabled = urgentAlertEnabled;
        this.batchFailureEnabled = batchFailureEnabled;
        this.weeklyReportEnabled = weeklyReportEnabled;
        this.minScore = minScore;
        this.signalTypes = List.copyOf(signalTypes);
        this.updatedAt = Instant.now();
    }

    public Set<SignalType> enabledSignalTypes() {
        if (signalTypes == null || signalTypes.isEmpty()) {
            return EnumSet.noneOf(SignalType.class);
        }
        Set<SignalType> result = EnumSet.noneOf(SignalType.class);
        for (String raw : signalTypes) {
            try {
                result.add(SignalType.valueOf(raw));
            } catch (IllegalArgumentException ignored) {
                // skip unknown enum values (migration-safe)
            }
        }
        return result;
    }
}
