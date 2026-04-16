package com.ted.signal.adapter.out.external;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/**
 * KRX 공개 데이터 크롤러
 * - 공매도 거래 현황
 * - 대차잔고 현황
 * - 주가 시세
 *
 * 요청 간격: 2초 이상 (IP 차단 방지)
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class KrxClient {

    private static final String KRX_BASE_URL = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd";
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);
    private static final long REQUEST_INTERVAL_MS = 2000;

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    /**
     * 공매도 거래 현황 조회 (전 종목)
     */
    public List<ShortSellingData> fetchShortSelling(LocalDate date) {
        var formData = buildFormData(
                "bld", "dbms/MDC/STAT/srt/MDCSTAT1251",
                "searchType", "1",
                "mktId", "ALL",
                "trdDd", date.format(DATE_FMT)
        );
        return requestAndParse(formData, this::parseShortSelling);
    }

    /**
     * 대차잔고 현황 조회 (전 종목)
     */
    public List<LendingBalanceData> fetchLendingBalance(LocalDate date) {
        var formData = buildFormData(
                "bld", "dbms/MDC/STAT/srt/MDCSTAT1251",
                "searchType", "2",
                "mktId", "ALL",
                "trdDd", date.format(DATE_FMT)
        );
        return requestAndParse(formData, this::parseLendingBalance);
    }

    /**
     * 주가 시세 조회 (전 종목)
     */
    public List<StockPriceData> fetchStockPrice(LocalDate date) {
        var formData = buildFormData(
                "bld", "dbms/MDC/STAT/standard/MDCSTAT01501",
                "mktId", "ALL",
                "trdDd", date.format(DATE_FMT)
        );
        return requestAndParse(formData, this::parseStockPrice);
    }

    // ========== Data Records ==========

    public record ShortSellingData(
            String stockCode,
            String stockName,
            String marketType,
            long shortVolume,
            long shortAmount,
            BigDecimal shortRatio
    ) {}

    public record LendingBalanceData(
            String stockCode,
            String stockName,
            long balanceQuantity,
            long balanceAmount
    ) {}

    public record StockPriceData(
            String stockCode,
            String stockName,
            String marketType,
            long closePrice,
            long openPrice,
            long highPrice,
            long lowPrice,
            long volume,
            long marketCap,
            BigDecimal changeRate
    ) {}

    // ========== Internal ==========

    private <T> List<T> requestAndParse(String formData, ThrowingFunction<JsonNode, List<T>> parser) {
        try {
            var request = HttpRequest.newBuilder()
                    .uri(URI.create(KRX_BASE_URL))
                    .header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                    .header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
                    .header("Referer", "http://data.krx.co.kr/contents/MDC/MDI/mdiStat/")
                    .timeout(REQUEST_TIMEOUT)
                    .POST(HttpRequest.BodyPublishers.ofString(formData))
                    .build();

            var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                log.error("KRX 요청 실패: status={}, body={}", response.statusCode(), response.body().substring(0, Math.min(200, response.body().length())));
                return List.of();
            }

            var root = objectMapper.readTree(response.body());
            var result = parser.apply(root);

            // IP 차단 방지 — 요청 간격 준수
            Thread.sleep(REQUEST_INTERVAL_MS);

            return result;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.warn("KRX 요청 중 인터럽트 발생");
            return List.of();
        } catch (Exception e) {
            log.error("KRX 데이터 수집 실패: {}", e.getMessage(), e);
            return List.of();
        }
    }

    private List<ShortSellingData> parseShortSelling(JsonNode root) {
        var items = root.path("OutBlock_1");
        var result = new ArrayList<ShortSellingData>();
        for (var item : items) {
            result.add(new ShortSellingData(
                    item.path("ISU_SRT_CD").asText(),
                    item.path("ISU_ABBRV").asText(),
                    item.path("MKT_NM").asText(),
                    parseLong(item.path("CVSRTSELL_TRDVOL").asText()),
                    parseLong(item.path("CVSRTSELL_TRDVAL").asText()),
                    parseBigDecimal(item.path("SRTSELL_RTO").asText())
            ));
        }
        return result;
    }

    private List<LendingBalanceData> parseLendingBalance(JsonNode root) {
        var items = root.path("OutBlock_1");
        var result = new ArrayList<LendingBalanceData>();
        for (var item : items) {
            result.add(new LendingBalanceData(
                    item.path("ISU_SRT_CD").asText(),
                    item.path("ISU_ABBRV").asText(),
                    parseLong(item.path("BAL_QTY").asText()),
                    parseLong(item.path("BAL_AMT").asText())
            ));
        }
        return result;
    }

    private List<StockPriceData> parseStockPrice(JsonNode root) {
        var items = root.path("OutBlock_1");
        var result = new ArrayList<StockPriceData>();
        for (var item : items) {
            result.add(new StockPriceData(
                    item.path("ISU_SRT_CD").asText(),
                    item.path("ISU_ABBRV").asText(),
                    item.path("MKT_NM").asText(),
                    parseLong(item.path("TDD_CLSPRC").asText()),
                    parseLong(item.path("TDD_OPNPRC").asText()),
                    parseLong(item.path("TDD_HGPRC").asText()),
                    parseLong(item.path("TDD_LWPRC").asText()),
                    parseLong(item.path("ACC_TRDVOL").asText()),
                    parseLong(item.path("MKTCAP").asText()),
                    parseBigDecimal(item.path("FLUC_RT").asText())
            ));
        }
        return result;
    }

    private String buildFormData(String... pairs) {
        var sb = new StringBuilder();
        for (int i = 0; i < pairs.length; i += 2) {
            if (!sb.isEmpty()) sb.append('&');
            sb.append(pairs[i]).append('=').append(pairs[i + 1]);
        }
        return sb.toString();
    }

    private long parseLong(String val) {
        try {
            return Long.parseLong(val.replace(",", "").replace("-", "0").trim());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private BigDecimal parseBigDecimal(String val) {
        try {
            return new BigDecimal(val.replace(",", "").trim());
        } catch (NumberFormatException e) {
            return BigDecimal.ZERO;
        }
    }

    @FunctionalInterface
    private interface ThrowingFunction<T, R> {
        R apply(T t) throws Exception;
    }
}
