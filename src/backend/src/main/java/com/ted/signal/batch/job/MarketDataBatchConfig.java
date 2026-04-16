package com.ted.signal.batch.job;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import com.ted.signal.application.port.in.DetectSignalsUseCase;
import com.ted.signal.application.service.TelegramNotificationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.Step;
import org.springframework.batch.core.job.builder.JobBuilder;
import org.springframework.batch.core.repository.JobRepository;
import org.springframework.batch.core.step.builder.StepBuilder;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.PlatformTransactionManager;

import java.time.LocalDate;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class MarketDataBatchConfig {

    private final CollectMarketDataUseCase collectMarketDataUseCase;
    private final DetectSignalsUseCase detectSignalsUseCase;
    private final TelegramNotificationService notificationService;

    @Bean
    public Job marketDataCollectionJob(JobRepository jobRepository,
                                       Step collectStep, Step detectStep, Step notifyStep) {
        return new JobBuilder("marketDataCollectionJob", jobRepository)
                .start(collectStep)
                .next(detectStep)
                .next(notifyStep)
                .build();
    }

    @Bean
    public Step collectStep(JobRepository jobRepository, PlatformTransactionManager txManager) {
        return new StepBuilder("collectStep", jobRepository)
                .tasklet((contribution, chunkContext) -> {
                    var date = LocalDate.now();
                    log.info("Step 1: {} 데이터 수집 시작", date);

                    var result = collectMarketDataUseCase.collectAll(date);
                    log.info("Step 1 완료: 주가 {}건, 공매도 {}건, 대차잔고 {}건 ({}ms)",
                            result.stockPriceCount(), result.shortSellingCount(),
                            result.lendingBalanceCount(), result.elapsedMs());

                    return RepeatStatus.FINISHED;
                }, txManager)
                .build();
    }

    @Bean
    public Step detectStep(JobRepository jobRepository, PlatformTransactionManager txManager) {
        return new StepBuilder("detectStep", jobRepository)
                .tasklet((contribution, chunkContext) -> {
                    var date = LocalDate.now();
                    log.info("Step 2: {} 시그널 탐지 시작", date);

                    var result = detectSignalsUseCase.detectAll(date);
                    log.info("Step 2 완료: 급감 {}, 추세전환 {}, 숏스퀴즈 {} ({}ms)",
                            result.rapidDeclineCount(), result.trendReversalCount(),
                            result.shortSqueezeCount(), result.elapsedMs());

                    return RepeatStatus.FINISHED;
                }, txManager)
                .build();
    }

    @Bean
    public Step notifyStep(JobRepository jobRepository, PlatformTransactionManager txManager) {
        return new StepBuilder("notifyStep", jobRepository)
                .tasklet((contribution, chunkContext) -> {
                    var date = LocalDate.now();
                    log.info("Step 3: {} 알림 발송 시작", date);

                    int sent = notificationService.sendUrgentAlerts(date);
                    log.info("Step 3 완료: A등급 {}건 긴급 알림 발송", sent);

                    return RepeatStatus.FINISHED;
                }, txManager)
                .build();
    }
}
