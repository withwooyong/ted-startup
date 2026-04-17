package com.ted.signal.application.service;

import com.ted.signal.adapter.out.external.TelegramClient;
import com.ted.signal.application.port.out.BacktestResultRepository;
import com.ted.signal.application.port.out.SignalRepository;
import com.ted.signal.domain.enums.SignalGrade;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.BacktestResult;
import com.ted.signal.domain.model.NotificationPreference;
import com.ted.signal.domain.model.Signal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional(readOnly = true)
public class TelegramNotificationService {

    private final TelegramClient telegramClient;
    private final SignalRepository signalRepository;
    private final BacktestResultRepository backtestResultRepository;
    private final NotificationPreferenceService notificationPreferenceService;

    /**
     * 시나리오 1: 일일 시그널 요약 (08:30 발송)
     * 사용자 preference 반영: dailySummaryEnabled 토글, minScore 하한, signalTypes 필터.
     */
    public boolean sendDailySummary(LocalDate date) {
        NotificationPreference pref = notificationPreferenceService.getPreferenceForFiltering();
        if (!pref.getDailySummaryEnabled()) {
            log.info("{}일자 일일 요약 스킵 — 사용자 설정 off", date);
            return false;
        }

        var allSignals = signalRepository.findBySignalDateWithStockOrderByScoreDesc(date);
        Set<SignalType> enabledTypes = pref.enabledSignalTypes();
        int minScore = pref.getMinScore();
        var signals = allSignals.stream()
                .filter(s -> enabledTypes.contains(s.getSignalType()))
                .filter(s -> s.getScore() != null && s.getScore() >= minScore)
                .toList();

        if (signals.isEmpty()) {
            log.info("{}일자 시그널 없음(필터 적용 후) — 일일 요약 스킵", date);
            return false;
        }

        Map<SignalType, List<Signal>> byType = signals.stream()
                .collect(Collectors.groupingBy(Signal::getSignalType));

        var sb = new StringBuilder();
        sb.append(String.format("<b>📊 일일 시그널 리포트 (%s)</b>\n\n", date));
        sb.append(String.format("총 <b>%d</b>개 시그널 탐지\n\n", signals.size()));

        for (SignalType type : SignalType.values()) {
            var typed = byType.getOrDefault(type, List.of());
            if (typed.isEmpty()) continue;

            String emoji = typeEmoji(type);
            sb.append(String.format("%s <b>%s</b> — %d건\n", emoji, typeLabel(type), typed.size()));

            // 상위 3개 시그널
            typed.stream().limit(3).forEach(s -> sb.append(String.format(
                    "  • %s(%s) — 스코어 %d (%s등급)\n",
                    s.getStock().getStockName(), s.getStock().getStockCode(),
                    s.getScore(), s.getGrade())));

            if (typed.size() > 3) {
                sb.append(String.format("  ... 외 %d건\n", typed.size() - 3));
            }
            sb.append("\n");
        }

        return telegramClient.sendMessage(sb.toString());
    }

    /**
     * 시나리오 1.5: A등급 긴급 알림 일괄 발송 (배치 3단계에서 호출)
     * 사용자 preference 반영: urgentAlertEnabled 토글, signalTypes 필터.
     * minScore는 A등급 자체 기준(80+) > 사용자 임계값일 가능성이 높아 중복 적용 불필요.
     */
    public int sendUrgentAlerts(LocalDate date) {
        NotificationPreference pref = notificationPreferenceService.getPreferenceForFiltering();
        if (!pref.getUrgentAlertEnabled()) {
            log.info("{}일자 긴급 알림 스킵 — 사용자 설정 off", date);
            return 0;
        }

        Set<SignalType> enabledTypes = pref.enabledSignalTypes();
        var signals = signalRepository.findByDateAndType(date, null);
        var urgentSignals = signals.stream()
                .filter(s -> s.getGrade() == SignalGrade.A)
                .filter(s -> enabledTypes.contains(s.getSignalType()))
                .toList();

        int sent = 0;
        for (var signal : urgentSignals) {
            if (sendUrgentAlert(signal)) sent++;
        }
        log.info("A등급 긴급 알림 {}건 발송 (필터 후 {}건 중)", sent, urgentSignals.size());
        return sent;
    }

    /**
     * 시나리오 2: 긴급 알림 — A등급 시그널 즉시 발송
     * 개별 발송은 필터링 없이 항상 전송 (호출자가 filter 책임).
     */
    public boolean sendUrgentAlert(Signal signal) {

        String msg = String.format(
                "🚨 <b>긴급 시그널 발생!</b>\n\n"
                        + "<b>%s</b> (%s)\n"
                        + "유형: %s %s\n"
                        + "스코어: <b>%d</b> (A등급)\n"
                        + "날짜: %s\n\n"
                        + "즉시 확인이 필요합니다.",
                signal.getStock().getStockName(), signal.getStock().getStockCode(),
                typeEmoji(signal.getSignalType()), typeLabel(signal.getSignalType()),
                signal.getScore(), signal.getSignalDate());

        return telegramClient.sendMessage(msg);
    }

    /**
     * 시나리오 3: 배치 실패 알림 — batchFailureEnabled 토글 반영.
     */
    public boolean sendBatchFailure(String jobName, String errorMessage) {
        NotificationPreference pref = notificationPreferenceService.getPreferenceForFiltering();
        if (!pref.getBatchFailureEnabled()) {
            log.warn("배치 실패 알림 스킵(설정 off) — job={}", jobName);
            return false;
        }
        String msg = String.format(
                "⚠️ <b>배치 실행 실패</b>\n\n"
                        + "작업: %s\n"
                        + "시간: %s\n"
                        + "오류: <code>%s</code>\n\n"
                        + "수동 확인이 필요합니다.",
                jobName, java.time.LocalDateTime.now(java.time.ZoneId.of("Asia/Seoul")), errorMessage);

        return telegramClient.sendMessage(msg);
    }

    /**
     * 시나리오 4: 주간 성과 리포트 (토요일 10:00 발송) — weeklyReportEnabled 토글 반영.
     */
    public boolean sendWeeklyReport() {
        NotificationPreference pref = notificationPreferenceService.getPreferenceForFiltering();
        if (!pref.getWeeklyReportEnabled()) {
            log.info("주간 리포트 스킵 — 사용자 설정 off");
            return false;
        }
        var results = backtestResultRepository.findTop20ByOrderByCreatedAtDesc();
        if (results.isEmpty()) {
            return telegramClient.sendMessage("📈 <b>주간 리포트</b>\n\n백테스팅 결과가 아직 없습니다.");
        }

        // SignalType별 최신 결과 1건씩
        Map<String, BacktestResult> latest = results.stream()
                .collect(Collectors.toMap(
                        BacktestResult::getSignalType,
                        r -> r,
                        (a, b) -> a));

        var sb = new StringBuilder();
        sb.append("<b>📈 주간 성과 리포트</b>\n\n");

        for (SignalType type : SignalType.values()) {
            var r = latest.get(type.name());
            if (r == null) continue;

            sb.append(String.format("<b>%s %s</b>\n", typeEmoji(type), typeLabel(type)));
            sb.append(String.format("  시그널 %d건 | 기간 %s~%s\n",
                    r.getTotalSignals(), r.getPeriodStart(), r.getPeriodEnd()));
            sb.append(String.format("  5일: 적중 %s%% / 수익 %s%%\n",
                    formatRate(r.getHitRate5d()), formatRate(r.getAvgReturn5d())));
            sb.append(String.format("  10일: 적중 %s%% / 수익 %s%%\n",
                    formatRate(r.getHitRate10d()), formatRate(r.getAvgReturn10d())));
            sb.append(String.format("  20일: 적중 %s%% / 수익 %s%%\n\n",
                    formatRate(r.getHitRate20d()), formatRate(r.getAvgReturn20d())));
        }

        return telegramClient.sendMessage(sb.toString());
    }

    // ========== Helpers ==========

    private String typeEmoji(SignalType type) {
        return switch (type) {
            case RAPID_DECLINE -> "📉";
            case TREND_REVERSAL -> "🔄";
            case SHORT_SQUEEZE -> "🔥";
        };
    }

    private String typeLabel(SignalType type) {
        return switch (type) {
            case RAPID_DECLINE -> "대차잔고 급감";
            case TREND_REVERSAL -> "추세전환";
            case SHORT_SQUEEZE -> "숏스퀴즈";
        };
    }

    private String formatRate(BigDecimal rate) {
        return rate != null ? rate.setScale(2, java.math.RoundingMode.HALF_UP).toPlainString() : "-";
    }
}
