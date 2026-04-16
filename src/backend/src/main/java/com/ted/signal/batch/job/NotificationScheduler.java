package com.ted.signal.batch.job;

import com.ted.signal.application.service.TelegramNotificationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

@Component
@RequiredArgsConstructor
@Slf4j
public class NotificationScheduler {

    private final TelegramNotificationService notificationService;

    /**
     * 일일 시그널 요약: 매일 08:30 (월~금, 장 개시 30분 전)
     */
    @Scheduled(cron = "0 30 8 * * MON-FRI", zone = "Asia/Seoul")
    public void dailySummary() {
        log.info("일일 시그널 요약 발송 시작");
        try {
            notificationService.sendDailySummary(LocalDate.now());
        } catch (Exception e) {
            log.error("일일 요약 발송 실패", e);
        }
    }

    /**
     * 주간 성과 리포트: 토요일 10:00
     */
    @Scheduled(cron = "0 0 10 * * SAT", zone = "Asia/Seoul")
    public void weeklyReport() {
        log.info("주간 성과 리포트 발송 시작");
        try {
            notificationService.sendWeeklyReport();
        } catch (Exception e) {
            log.error("주간 리포트 발송 실패", e);
        }
    }
}
