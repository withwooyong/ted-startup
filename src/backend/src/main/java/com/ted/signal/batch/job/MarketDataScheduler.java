package com.ted.signal.batch.job;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.JobParametersBuilder;
import org.springframework.batch.core.launch.JobLauncher;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

@Component
@EnableScheduling
@RequiredArgsConstructor
@Slf4j
public class MarketDataScheduler {

    private final JobLauncher jobLauncher;
    private final Job marketDataCollectionJob;

    /**
     * 매일 06:00 배치 실행 (한국 시간, 월~금)
     */
    @Scheduled(cron = "0 0 6 * * MON-FRI", zone = "Asia/Seoul")
    public void scheduledCollect() {
        try {
            var params = new JobParametersBuilder()
                    .addString("date", LocalDate.now().toString())
                    .addLong("timestamp", System.currentTimeMillis())
                    .toJobParameters();
            jobLauncher.run(marketDataCollectionJob, params);
        } catch (Exception e) {
            log.error("스케줄 배치 실행 실패", e);
        }
    }
}
