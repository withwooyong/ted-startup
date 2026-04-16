package com.ted.signal.batch.job;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.Step;
import org.springframework.batch.core.job.builder.JobBuilder;
import org.springframework.batch.core.launch.JobLauncher;
import org.springframework.batch.core.repository.JobRepository;
import org.springframework.batch.core.step.builder.StepBuilder;
import org.springframework.batch.core.step.tasklet.Tasklet;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.PlatformTransactionManager;

import java.time.LocalDate;

@Configuration
@EnableScheduling
@RequiredArgsConstructor
@Slf4j
public class MarketDataBatchConfig {

    private final CollectMarketDataUseCase collectMarketDataUseCase;
    private final JobLauncher jobLauncher;
    private final JobRepository jobRepository;

    @Bean
    public Job marketDataCollectionJob(Step collectStep) {
        return new JobBuilder("marketDataCollectionJob", jobRepository)
                .start(collectStep)
                .build();
    }

    @Bean
    public Step collectStep(PlatformTransactionManager txManager) {
        return new StepBuilder("collectStep", jobRepository)
                .tasklet(collectTasklet(), txManager)
                .build();
    }

    @Bean
    public Tasklet collectTasklet() {
        return (contribution, chunkContext) -> {
            var date = LocalDate.now();
            log.info("배치 실행: {} 데이터 수집 시작", date);

            var result = collectMarketDataUseCase.collectAll(date);
            log.info("배치 완료: 주가 {}건, 공매도 {}건, 대차잔고 {}건, 신규종목 {}건 ({}ms)",
                    result.stockPriceCount(), result.shortSellingCount(),
                    result.lendingBalanceCount(), result.newStockCount(), result.elapsedMs());

            return RepeatStatus.FINISHED;
        };
    }

    /**
     * 매일 06:00 배치 실행 (한국 시간)
     */
    @Scheduled(cron = "0 0 6 * * MON-FRI", zone = "Asia/Seoul")
    public void scheduledCollect() {
        try {
            var params = new org.springframework.batch.core.JobParametersBuilder()
                    .addString("date", LocalDate.now().toString())
                    .addLong("timestamp", System.currentTimeMillis())
                    .toJobParameters();
            jobLauncher.run(marketDataCollectionJob(null), params);
        } catch (Exception e) {
            log.error("스케줄 배치 실행 실패", e);
        }
    }
}
