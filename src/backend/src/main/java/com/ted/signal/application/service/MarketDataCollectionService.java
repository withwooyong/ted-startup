package com.ted.signal.application.service;

import com.ted.signal.adapter.out.external.KrxClient;
import com.ted.signal.application.port.in.CollectMarketDataUseCase;
import com.ted.signal.application.port.in.CollectMarketDataUseCase.CollectionResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;

/**
 * KRX 데이터 수집 오케스트레이터.
 * HTTP 수집 Phase는 트랜잭션 밖에서 실행하고, DB 영속화는 별도 빈(MarketDataPersistService)에 위임해
 * Spring AOP 프록시가 @Transactional을 정상 적용하도록 한다.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MarketDataCollectionService implements CollectMarketDataUseCase {

    private final KrxClient krxClient;
    private final MarketDataPersistService persistService;

    @Override
    public CollectionResult collectAll(LocalDate date) {
        long start = System.currentTimeMillis();
        log.info("=== KRX 데이터 수집 시작: {} ===", date);

        // Phase 1: HTTP 수집 (트랜잭션 밖에서 실행 — DB 커넥션 점유 방지)
        var priceData = krxClient.fetchStockPrice(date);
        log.info("주가 시세 {}건 수신", priceData.size());

        var shortData = krxClient.fetchShortSelling(date);
        log.info("공매도 거래 {}건 수신", shortData.size());

        var lendingData = krxClient.fetchLendingBalance(date);
        log.info("대차잔고 {}건 수신", lendingData.size());

        // Phase 2: DB 저장 (별도 빈 경유 → 프록시 @Transactional 정상 동작)
        var result = persistService.persistAll(date, priceData, shortData, lendingData);

        long elapsed = System.currentTimeMillis() - start;
        log.info("=== KRX 데이터 수집 완료: {}ms ===", elapsed);

        return new CollectionResult(
                result.priceCount(), result.shortCount(), result.lendingCount(),
                result.newStockCount(), elapsed);
    }
}
