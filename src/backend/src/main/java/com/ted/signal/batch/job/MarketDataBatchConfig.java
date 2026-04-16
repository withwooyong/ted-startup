package com.ted.signal.batch.job;

import com.ted.signal.application.port.in.CollectMarketDataUseCase;
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

    @Bean
    public Job marketDataCollectionJob(JobRepository jobRepository, Step collectStep) {
        return new JobBuilder("marketDataCollectionJob", jobRepository)
                .start(collectStep)
                .build();
    }

    @Bean
    public Step collectStep(JobRepository jobRepository, PlatformTransactionManager txManager) {
        return new StepBuilder("collectStep", jobRepository)
                .tasklet((contribution, chunkContext) -> {
                    var date = LocalDate.now();
                    log.info("배치 실행: {} 데이터 수집 시작", date);

                    var result = collectMarketDataUseCase.collectAll(date);
                    log.info("배치 완료: 주가 {}건, 공매도 {}건, 대차잔고 {}건, 신규종목 {}건 ({}ms)",
                            result.stockPriceCount(), result.shortSellingCount(),
                            result.lendingBalanceCount(), result.newStockCount(), result.elapsedMs());

                    return RepeatStatus.FINISHED;
                }, txManager)
                .build();
    }
}
