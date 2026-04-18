# Fixtures — Phase 3 외부 어댑터 회귀 기준 (초기본)

## 목적
Java 백엔드를 Python으로 이전(`docs/migration/java-to-python-plan.md`)할 때 외부 API 어댑터(`KrxClient`, `TelegramClient`) 포팅의 회귀 검증 기준점을 제공한다.

## 파일

- `krx/capture_krx.py` — 실캡처 시도 스크립트 (향후 KRX 세션 플로우 복구 시 재사용)
- `krx/*.synthetic.json` — 스키마 기반 합성 픽스처 (필드 이름·타입·구조만 보장, 값은 대표 예시)
- `telegram/send_message_response.mock.json` — Telegram `sendMessage` 성공 응답 모의본

## ⚠ KRX 실캡처 블로커 (2026-04-18)

`https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd`에 Java `KrxClient`와 동일한 요청 포맷(POST form-url-encoded, Referer·User-Agent 설정)을 보내면 **HTTP 400 + 본문 `LOGOUT`** 이 반환된다. JSESSIONID 쿠키를 워밍업 GET으로 확보해도 결과는 같다. AJAX 헤더(`X-Requested-With`, `Origin`, `Accept`) 추가도 무효.

**가설**
1. KRX가 JSON 엔드포인트에도 OTP 발급 플로우(`GenerateOTP/generate.cmd` → 토큰)를 요구하도록 정책을 강화했을 가능성
2. 봇 차단(Cloudflare 등) 레이어가 추가돼 JS 실행 기반 검증을 요구할 가능성
3. 요청 본문 키 순서·대소문자·서명 추가 등 미공개 변경

**프로덕션 영향**
현재 운영 중인 Java `MarketDataBatchConfig`의 `collectStep`이 **같은 엔드포인트를 같은 요청으로 호출**하므로 동일하게 실패할 가능성이 높다. Phase 3(외부 어댑터 이전) 착수 전에 별도 조사·복구 트랙이 필요하다.

**Phase 3 사전 조사 과제**
- [ ] Chrome DevTools로 KRX 공매도 페이지 실시간 XHR 캡처(필수 쿠키·헤더·OTP 확인)
- [ ] `GenerateOTP` 2단계 플로우 적용 여부 결정
- [ ] 복구되면 `capture_krx.py` 확장 후 실데이터 교체

## KRX Java 응답 스키마 (KrxClient.java 기반)

### Short Selling — `bld=dbms/MDC/STAT/srt/MDCSTAT1251&searchType=1`
```
OutBlock_1[] {
  ISU_SRT_CD      : string   # 종목코드
  ISU_ABBRV       : string   # 종목명
  MKT_NM          : string   # 시장구분 (유가증권/코스닥)
  CVSRTSELL_TRDVOL: string   # 공매도 거래량 (쉼표 포함)
  CVSRTSELL_TRDVAL: string   # 공매도 거래대금
  SRTSELL_RTO     : string   # 공매도 비중 (%)
}
```

### Lending Balance — `bld=dbms/MDC/STAT/srt/MDCSTAT1251&searchType=2`
```
OutBlock_1[] {
  ISU_SRT_CD: string
  ISU_ABBRV : string
  BAL_QTY   : string   # 대차 잔고 수량
  BAL_AMT   : string   # 대차 잔고 금액
}
```

### Stock Price — `bld=dbms/MDC/STAT/standard/MDCSTAT01501`
```
OutBlock_1[] {
  ISU_SRT_CD : string
  ISU_ABBRV  : string
  MKT_NM     : string
  TDD_CLSPRC : string   # 종가
  TDD_OPNPRC : string   # 시가
  TDD_HGPRC  : string   # 고가
  TDD_LWPRC  : string   # 저가
  ACC_TRDVOL : string   # 거래량
  MKTCAP     : string   # 시가총액
  FLUC_RT    : string   # 등락률 (%)
}
```

## Telegram 응답 스키마

Bot API `sendMessage` 성공 응답은 공식 문서상 안정적이며 `{ok: true, result: Message}` 구조. `send_message_response.mock.json`에 대표 payload 보관.
