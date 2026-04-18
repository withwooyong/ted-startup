# 키움증권 REST API 가용성 조사 (P15 문서 스파이크)

- **조사일**: 2026-04-18
- **목적**: `docs/migration/java-to-python-plan.md` §11.1 의 증권사 API 연동 옵션 중 "키움 REST" 가 본 프로젝트의 포트폴리오 도메인(P10~P12) 에 실제 편입 가능한지 판단.
- **스코프**: 문서 스파이크만 — 본 조사는 **구현을 수반하지 않는다**. 결론은 "언제·어떤 조건이면 구현에 착수할지" 의 의사결정 가이드.
- **요약 결정**: **현 MVP 단계에서는 키움 REST 미구현.** KIS 모의(P11) 로 단독 운영. 재평가 시점은 아래 §7 "Go 조건" 3가지가 **모두** 충족되는 때.

---

## 1. TL;DR

| 항목 | 결론 |
|------|------|
| 키움 REST API 존재 여부 | ✅ 존재 (`openapi.kiwoom.com`) — 개인 계좌·모의 포함 |
| 본 프로젝트 착수 권고 | ❌ **보류** (Python SDK 성숙도·레퍼런스 부족) |
| 재평가 트리거 | §7 Go 조건 3/3 충족 시 |
| 대체 현황 | KIS 모의 REST 를 P11 에서 이미 구현·검증 완료 (72/72 PASS) |
| 조사 깊이 | 공식 사이트 2개 + Python SDK 1개 + 커뮤니티 라이브러리 2개 확인 |

---

## 2. 2026-04 공식 현황

### 2.1 공식 엔드포인트

| 환경 | Base URL | 비고 |
|------|----------|------|
| 프로덕션(실거래) | `https://api.kiwoom.com` | 본 MVP 는 **코드상 진입 차단** 필요 |
| 모의투자 | `https://mockapi.kiwoom.com` | 별도 앱키 발급 탭 제공 |

> 플랜 §11.1 은 `developers.kiwoom.com` 으로 기재했으나 실제 공식 도메인은 `openapi.kiwoom.com`. 후속 문서 수정 권장.

### 2.2 확인된 사실

- **가입 조건**: 키움증권 계좌 개설 필수 (개인 리테일 고객 지원 명시)
- **모의투자**: 별도 신청·무료. "모의투자 > 상시모의투자 > 주식/선물옵션 > 안내" 에서 가입. 로그인 시 "모의투자 접속" 체크
- **인증 방식**: OAuth 2.0 추정 (공식 페이지에 TokenManager 클래스 언급, 상세 토큰 엔드포인트 스펙은 로그인 후 가이드 페이지에서 확인 필요)
- **응답 포맷**: JSON
- **TR 네이밍**: `ka10001` (기본정보) 등 — 레거시 OCX `opt10001` 과 별도 체계
- **요금제**: 공식 페이지에 가격 기재 없음. 계좌 보유 조건만 명시

### 2.3 확인 실패 / 로그인 벽

다음 정보는 **공식 가이드가 로그인 뒤에 있어** 본 스파이크 범위(무로그인 웹 조사) 에서 확인 불가:

- 서비스 정식 런칭 일자 / 버전 이력
- 전체 TR 목록과 범위 (레거시 OCX 대비 커버리지)
- Rate limit 구체 수치
- OAuth 토큰 TTL·재발급 규칙
- 실거래 전환 시 실명확인·본인인증 절차
- 시간외 체결·해외주식·파생 커버 여부

→ **추가 조사가 필요하다면** 계정을 직접 생성한 담당자가 로그인 상태에서 가이드 캡처 후 본 문서 §2.3 을 채워 넣는 것이 가장 빠름.

---

## 3. Python 생태계 성숙도

| 라이브러리 | 유형 | 최신 릴리스 | 평가 |
|------------|------|-------------|------|
| [`kiwoom-rest-api`](https://pypi.org/project/kiwoom-rest-api/) | REST 공식 래퍼(추정) | **2025-06 (0.1.12)** | **0.1.x 단계**. 현 PyPI 노출 기능은 `StockInfo.basic_stock_information_request_ka10001()` 1개만 확인. 잔고·주문 메서드 부재 또는 미노출 |
| [`kiwoom-restful`](https://pypi.org/project/kiwoom-restful/) | OCX → REST 브리지 | 커뮤니티 유지 | Windows OCX 를 서버로 노출하는 브리지. **리눅스/Docker 불가** 한 OCX 의존을 근본 해소하지 않음 |
| [`koapy`](https://pypi.org/project/koapy/) | OCX 래퍼 (Python 전용) | 활발 | OCX 의존 → 리눅스 불가 |
| [`breadum/kiwoom`](https://github.com/breadum/kiwoom) | OCX 간소 래퍼 | 유지 | 동일 제약 |

**KIS 측 대비**: `pykis` 등 비공식 래퍼가 잔고·주문·시세 전범위를 잘 커버하고 있고, 공식 샘플 코드가 GitHub 에 광범위. 커뮤니티 블로그·질의응답 밀도가 키움 REST 대비 현저히 큼 (2026-04 기준 체감).

---

## 4. KIS vs 키움 비교 매트릭스

| 항목 | KIS (구현됨) | 키움 REST |
|------|---------------|-----------|
| 본 프로젝트 구현 | ✅ P11 완료, 테스트 72/72 PASS | ❌ 미구현 |
| 프로덕션 URL | `openapi.koreainvestment.com:9443` | `api.kiwoom.com` |
| 모의 URL | `openapivts.koreainvestment.com:29443` | `mockapi.kiwoom.com` |
| 플랫폼 독립성 | ✅ 순수 REST | ✅ 순수 REST (OCX 레거시는 별개) |
| 인증 흐름 | OAuth2 `client_credentials`, 24h 토큰 | OAuth 추정 (확정 미확인) |
| TR 체계 | `VTTC...` (모의) / `TTTC...` (실거래) 접두로 명확 분리 | `ka...` (신규 체계, 실거래/모의 구분 규약 미확인) |
| Python 공식 샘플 | 레퍼런스 풍부 | 초기 단계 (0.1.x) |
| 커뮤니티 라이브러리 | `pykis` 등 성숙 | 미성숙 |
| 공식 가이드 접근 | 비로그인 상당 부분 공개 | 주요 가이드 로그인 필요 |
| 모의 신청 난이도 | 낮음 (발급 수 분) | 낮음 (이미 무료 가입) |
| 본 프로젝트 편익 | **즉시 사용 가능** (P11 어댑터 + 테스트) | 미지(조사·구현 2일+ 필요) |

---

## 5. 구현 시 필요 작업 (if go)

만약 §7 Go 조건이 만족되어 착수한다면, 다음 골격이 예상된다. **KIS 구현(P11)을 템플릿으로 그대로 이식 가능** — `LLMProvider` 처럼 Broker 추상을 굳이 도입할 필요 없이 `KiwoomClient` 독립 어댑터로 시작이 간단.

### 5.1 설정 (Settings)

```python
kiwoom_base_url_mock: str = "https://mockapi.kiwoom.com"  # 하드코드, 변경 시 에러
kiwoom_app_key_mock: str = ""
kiwoom_app_secret_mock: str = ""
kiwoom_account_no_mock: str = ""
kiwoom_request_timeout_seconds: float = 15.0
```

### 5.2 어댑터 (`app/adapter/out/external/kiwoom_client.py`)

- `httpx.AsyncClient` + `MockTransport` 테스트 주입 (KIS 와 동일 패턴)
- `_get_access_token()` — OAuth 토큰 캐시 + 만료 5분 전 재발급
- `fetch_balance()` — 잔고 TR 호출 → `KiwoomHoldingRow` 리스트
- TR 헤더·파라미터는 **실제 가이드 로그인 후 재확인 필수** (§2.3)
- 실거래 URL 진입 차단: 생성자에서 `base_url != mock` 이면 `KiwoomNotConfiguredError`

### 5.3 UseCase 편입

- `SyncPortfolioFromKisUseCase` 와 **별도 UseCase** 로 `SyncPortfolioFromKiwoomUseCase` 신설
- 또는 `BrokerAdapter` Protocol (`fetch_balance() -> list[HoldingRow]`) 를 선 추출 후 KIS/키움 양쪽을 단일 `SyncPortfolioUseCase` 뒤에 꽂는 방식 — Broker 추가가 2개 이상 될 때 도입 권고
- `brokerage_account.connection_type` 에 `kiwoom_rest_mock` 값 추가 + CHECK 제약 업데이트 (Alembic revision)

### 5.4 테스트

- `tests/test_kiwoom_client.py` — httpx MockTransport 로 토큰·잔고 응답 스텁
- `tests/test_portfolio.py` 에 키움 동기화 E2E 케이스 추가

**추정 공수**: 1.5~2 일 (KIS 템플릿 재사용 포함). 단, §7 Go 조건 중 (b) Python SDK 안정화가 없으면 응답 스키마·에러 케이스를 **우리가 직접 검증** 해야 해서 +1일 위험.

---

## 6. 리스크·제약

| # | 리스크 | 영향 | 완화 |
|---|-------|------|------|
| 1 | 공식 Python SDK 미성숙 (0.1.12, 잔고·주문 메서드 미노출) | 중 | 우리가 직접 httpx 로 REST 구현 (KIS 방식과 동일) |
| 2 | 공식 가이드 로그인 필요 → 스펙 사전 확인 불가 | 중 | 착수 전 계정 생성 후 가이드 캡처 스파이크 0.25일 추가 |
| 3 | TR 범위가 레거시 OCX 대비 제한적일 가능성 | 중 | MVP 는 잔고·체결 조회만 필요 — 이 범위는 대부분 커버될 것으로 추정, but 확인 필요 |
| 4 | 실거래 URL 오염 시 실제 자산에 영향 | 높음 | KIS 어댑터처럼 base URL 하드코드 + 생성자 assertion |
| 5 | 커뮤니티 자료 적음 — 트러블슈팅 시 Stack Overflow 등 의존 어려움 | 낮음 | 공식 문의창구 사전 확보 |
| 6 | 응답 포맷이 KIS 와 다른 필드명 — 어댑터 레벨에서 정규화 필요 | 낮음 | `KiwoomHoldingRow → HoldingRow` 매핑 |

---

## 7. Go / No-Go 결정 트리

**현재 상태: No-Go.** 다음 3가지 조건이 **모두** 만족되면 재평가.

### 7.1 Go 조건

1. **사용자가 키움증권 계좌를 실제 보유**하고 있고, 그쪽 포트폴리오도 본 서비스로 동기화할 필요가 생김 (KIS 만으로 커버되지 않는 외부 수요).
2. **`kiwoom-rest-api` 파이썬 SDK 가 0.2 이상** 으로 올라가 잔고·주문 메서드를 안정적으로 제공하거나, **공식 가이드가 로그인 없이도 전체 TR 스펙을 공개** 함.
3. **KIS 쪽 MVP 검증이 완전히 끝나** 현 어댑터 계약(HoldingRow, transaction_type, source) 이 안정화됨 — Broker 추가 전에 계약을 먼저 고정해야 중복 리팩터 방지.

### 7.2 No-Go 유지 근거

- KIS 모의 REST 단독으로 §11 P10~P12 의 원래 목표(수동 등록 + 1개 증권사 자동 동기화) 달성 가능
- 키움 추가는 편익(커버리지) 대비 비용(2일 + 트러블슈팅 리스크) 이 크고, **AI 리포트 파이프라인(P13b)** 이나 **프론트 리포트 뷰(P14)** 보다 우선순위가 낮음
- P15 자체가 "구현 없음, 조사만" 으로 작업계획서(§11.4 P15 0.5일) 에 명시됨 — 범위 준수

---

## 8. 후속 작업 (권고)

| 작업 | 소요 | 트리거 |
|------|------|--------|
| 플랜 §11.1 의 `developers.kiwoom.com` 기재를 `openapi.kiwoom.com` 으로 정정 | 0.1일 | 즉시 |
| 로그인 후 가이드 캡처 — TR 목록·OAuth 상세·Rate limit 를 본 문서 §2.3 에 채움 | 0.25일 | Go 조건 검토 시작 시 |
| `BrokerAdapter` Protocol 추출 (현 KIS 를 단일 구현으로) — 키움 합류 전 계약 안정화 | 0.5일 | Go 조건 (3) 충족 시 |
| `KiwoomClient` + UseCase + 테스트 | 1.5~2일 | Go 조건 3/3 충족 시 |

---

## 9. 레퍼런스

- 공식 안내: [키움 REST API 서비스 이용안내](https://openapi.kiwoom.com/m/intro/serviceInfo)
- 공식 가이드 (로그인 필요): [KIWOOM REST API 가이드](https://openapi.kiwoom.com/guide/index)
- 이벤트 공지: [REST API 거래 이벤트](https://www1.kiwoom.com/e/m/home/event/VEvent20250074View)
- 레거시 OCX 가이드: [키움 OpenAPI+ 개발가이드 v1.1 (PDF)](https://download.kiwoom.com/web/openapi/kiwoom_openapi_plus_devguide_ver_1.1.pdf)
- 공식 Python SDK (미성숙): [`kiwoom-rest-api` on PyPI](https://pypi.org/project/kiwoom-rest-api/)
- 대안 라이브러리: [`kiwoom-restful`](https://pypi.org/project/kiwoom-restful/), [`koapy`](https://pypi.org/project/koapy/), [`breadum/kiwoom`](https://github.com/breadum/kiwoom)
- KIS 비교 기준: [한국투자증권 오픈API 개발자센터](https://apiportal.koreainvestment.com/intro)
