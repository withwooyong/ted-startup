"""한국투자증권(KIS) REST 어댑터 — 모의·실거래 2환경 지원.

- 환경별 base_url + TR_ID:
  * MOCK: `https://openapivts.koreainvestment.com:29443` / 잔고 TR_ID `VTTC8434R`
  * REAL: `https://openapi.koreainvestment.com:9443` / 잔고 TR_ID `TTTC8434R`
- OAuth2 access_token 은 24h TTL — 클라이언트 인스턴스에 캐시, 만료 300초 전 자동 재발급.
- 실거래는 반드시 `credentials` 주입 필수 (PR 3 이후 DB 저장소와 연결). 미주입 시 즉시 예외.

지원 API(MVP):
- `fetch_balance(...)`: 잔고조회(`/uapi/domestic-stock/v1/trading/inquire-balance`)
  - output1: 보유 종목 리스트 → `KisHoldingRow`
  - output2: 평가/예수금 요약(본 MVP 에서는 미사용)
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.dto.kis import KisCredentials, KisEnvironment, KisHoldingRow
from app.application.port.out.kis_port import (
    KisCredentialRejectedError,
    KisUpstreamError,
)
from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
_TR_ID_BALANCE: dict[KisEnvironment, str] = {
    KisEnvironment.MOCK: "VTTC8434R",
    KisEnvironment.REAL: "TTTC8434R",
}
_TOKEN_RENEW_MARGIN_SECONDS = 300.0  # 만료 5분 전에 재발급

# Test-only constant. Returned only from the internal httpx.MockTransport when
# settings.kis_use_in_memory_mock=True — never transmitted to any external host.
_IN_MEMORY_TOKEN = "in-memory-e2e-token"  # noqa: S105 — fake token, not a secret
_IN_MEMORY_BALANCE: list[dict[str, Any]] = [
    # 결정론적 보유 종목 3건 — 실제 KIS sandbox 가 아닌 로컬 mock 용.
    {
        "pdno": "005930",
        "prdt_name": "삼성전자",
        "hldg_qty": "10",
        "pchs_avg_pric": "72000.00",
    },
    {
        "pdno": "000660",
        "prdt_name": "SK하이닉스",
        "hldg_qty": "5",
        "pchs_avg_pric": "150000.00",
    },
    {
        "pdno": "035420",
        "prdt_name": "NAVER",
        "hldg_qty": "3",
        "pchs_avg_pric": "205000.00",
    },
]


def _build_in_memory_transport() -> httpx.MockTransport:
    """KIS 모의 sandbox 를 완전히 대체하는 로컬 MockTransport.

    토큰 발급·잔고조회 두 엔드포인트만 구현. 결정론적 응답 — 동일 입력엔 동일 출력.
    외부 네트워크 일체 호출하지 않으므로 CI/E2E 안정성 확보.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/oauth2/tokenP" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "access_token": _IN_MEMORY_TOKEN,
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        if path == "/uapi/domestic-stock/v1/trading/inquire-balance" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg_cd": "MCA00000",
                    "msg1": "정상처리",
                    "output1": _IN_MEMORY_BALANCE,
                    "output2": [],
                    "ctx_area_fk100": "",
                    "ctx_area_nk100": "",
                },
            )
        return httpx.Response(
            404,
            json={
                "rt_cd": "1",
                "msg1": f"in-memory mock: 미구현 경로 {request.method} {path}",
            },
        )

    return httpx.MockTransport(handler)


class KisNotConfiguredError(Exception):
    """adapter-internal — Settings 에 KIS 자격증명이 누락됐거나 잘못된 형식.

    **의도적으로 `KisUpstreamError` 를 상속하지 않음**. 서버 측 설정 오류는 KIS
    업스트림 장애(5xx/네트워크) 와 성격이 다르며, UseCase 의 `except KisUpstreamError`
    가 설정 오류를 함께 삼켜 `SyncError` → 502 로 오진단하는 것을 방지.

    라우터는 이 예외를 잡지 않고 FastAPI 기본 500 으로 전파해 운영팀이 설정을
    점검하도록 유도. 필요 시 `main.py` startup 훅에서 선제 검증 권장.
    """


def _account_parts(account_no: str) -> tuple[str, str]:
    digits = account_no.replace("-", "").strip()
    if len(digits) < 10:
        raise KisNotConfiguredError(f"KIS 계좌번호는 숫자 10자리여야 함 (현재 {len(digits)}자리)")
    return digits[:8], digits[8:10]


def _to_int(val: Any) -> int:
    if val is None:
        return 0
    s = str(val).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(Decimal(s))
    except Exception:
        return 0


def _to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    s = str(val).strip().replace(",", "")
    if not s:
        return Decimal("0")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0")


class KisClient:
    """KIS REST 클라이언트. 프로세스당 1 인스턴스 권장 (토큰 캐시 공유).

    테스트에서는 `transport=httpx.MockTransport(...)` 를 주입해 외부 호출 없이 검증.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        environment: KisEnvironment = KisEnvironment.MOCK,
        credentials: KisCredentials | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self._settings = s
        self._environment = environment

        if environment is KisEnvironment.MOCK:
            # base_url 은 환경 상수로 직접 고정 — Settings 커스터마이징이 실 URL 을
            # "mock" 으로 위장해 주입하는 경로를 원천 차단.
            self._base_url = _MOCK_BASE_URL
            if credentials is None:
                self._app_key = s.kis_app_key_mock
                self._app_secret = s.kis_app_secret_mock
                self._account_no = s.kis_account_no_mock
            else:
                self._app_key = credentials.app_key
                self._app_secret = credentials.app_secret
                self._account_no = credentials.account_no
        else:  # KisEnvironment.REAL
            # 실거래는 credentials 주입 필수 — Settings 에는 실 자격증명을 두지 않는다.
            # PR 3 에서 `brokerage_account_credential` 저장소가 Fernet 복호화 후 주입.
            if credentials is None:
                raise KisNotConfiguredError(
                    "실 환경(KisEnvironment.REAL)은 credentials 주입 필수 — PR 3 이후 credential 저장소 연동 필요"
                )
            self._base_url = _REAL_BASE_URL
            self._app_key = credentials.app_key
            self._app_secret = credentials.app_secret
            self._account_no = credentials.account_no

        timeout = httpx.Timeout(
            connect=5.0,
            read=s.kis_request_timeout_seconds,
            write=s.kis_request_timeout_seconds,
            pool=5.0,
        )
        # In-memory MockTransport 는 MOCK 환경에서만 자동 주입. REAL 환경에서 사용하려면
        # 테스트가 명시적으로 `transport=...` 를 건네야 함 (실 URL 호출 안전장치).
        if transport is None and environment is KisEnvironment.MOCK and s.kis_use_in_memory_mock:
            transport = _build_in_memory_transport()
            self._app_key = self._app_key or "in-memory-app-key"
            self._app_secret = self._app_secret or "in-memory-app-secret"
            self._account_no = self._account_no or "0000000000-01"
            logger.info("KIS in-memory mock transport 활성화 — 외부 호출 없음")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout, transport=transport)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._app_key and self._app_secret and self._account_no)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KisClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str:
        now = time.monotonic()
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        if not self.configured:
            raise KisNotConfiguredError("KIS_APP_KEY_MOCK / SECRET / ACCOUNT 누락")

        payload = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }
        try:
            resp = await self._client.post(
                "/oauth2/tokenP",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise KisUpstreamError(f"토큰 요청 네트워크 오류: {exc}") from exc
        if resp.status_code in (401, 403):
            # KIS 가 자격증명을 명시적 거부 — 사용자 재등록 필요. 업스트림 장애와 분리.
            # 원 응답 body 는 DEBUG 로그로만 분리 — PR #20 로깅 마스킹 파이프라인을 거쳐
            # JWT/hex 패턴이 자동 스크럽 되도록 함. 예외 메시지에 담으면 HTTP response
            # detail 로 사용자 노출될 수 있어 body 는 절대 메시지에 포함 안 함.
            logger.debug("KIS token %s body: %s", resp.status_code, resp.text[:200])
            raise KisCredentialRejectedError(f"KIS 자격증명 거부 (토큰 발급): HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.debug("KIS token %s body: %s", resp.status_code, resp.text[:200])
            raise KisUpstreamError(f"토큰 요청 실패: HTTP {resp.status_code}")
        data = resp.json()
        raw_token = data.get("access_token")
        if not isinstance(raw_token, str) or not raw_token:
            raise KisUpstreamError(f"access_token 부재: {data}")
        expires_in = float(data.get("expires_in") or 86400)
        self._access_token = raw_token
        self._token_expires_at = now + max(expires_in - _TOKEN_RENEW_MARGIN_SECONDS, 60.0)
        logger.info("KIS 토큰 발급 성공 (expires_in=%ds)", int(expires_in))
        return raw_token

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def test_connection(self) -> None:
        """OAuth 토큰 발급만 시도하는 dry-run. 자격증명 유효성 검증용.

        실패 시 HTTP 401/403 → `KisCredentialRejectedError`, 그 외 → `KisUpstreamError`.
        잔고 조회 API 는
        호출하지 않아 KIS 서비스에 부하 최소 + 계좌 상태 변경 0.

        **부수 효과**: 성공 시 인스턴스에 `access_token` 이 캐시된다 — 이후 동일 인스턴스로
        `fetch_balance()` 를 호출하면 토큰 재발급이 생략된다. 본 프로젝트의 REAL 클라이언트는
        요청 스코프(use case `async with`) 라 영향 범위가 1회 요청 내로 한정.

        **재시도 없음**: `fetch_balance()` 와 달리 tenacity `@retry` 데코레이터를 두지 않아
        일시 네트워크 오류도 즉시 실패. 연결 테스트는 "빠른 1회 검증" 의미 — 재시도로
        위장된 성공을 만들지 않도록 의도된 설계.
        """
        await self._get_access_token()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        reraise=True,
    )
    async def fetch_balance(self) -> list[KisHoldingRow]:
        """모의계좌 보유 종목 전량 조회. 페이징은 MVP 에서 생략(보유 종목 ≤ 50 가정)."""
        token = await self._get_access_token()
        cano, prdt = _account_parts(self._account_no)
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            # 환경별 TR_ID 분기: MOCK→VTTC8434R, REAL→TTTC8434R
            "tr_id": _TR_ID_BALANCE[self._environment],
            "custtype": "P",  # 개인
        }
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=headers,
            params=params,
        )
        if resp.status_code in (401, 403):
            # 토큰은 발급됐지만 잔고조회 시점에 자격증명이 거부되는 경우 (권한 회수 등).
            # 사용자 조치 가능하므로 credential reject 로 승격. body 는 DEBUG 로그로 분리.
            logger.debug("KIS balance %s body: %s", resp.status_code, resp.text[:300])
            raise KisCredentialRejectedError(f"KIS 자격증명 거부 (잔고조회): HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.debug("KIS balance %s body: %s", resp.status_code, resp.text[:300])
            raise KisUpstreamError(f"잔고조회 실패: HTTP {resp.status_code}")
        body = resp.json()
        rt_cd = body.get("rt_cd")
        if rt_cd not in ("0", 0):
            raise KisUpstreamError(f"잔고조회 응답 오류: rt_cd={rt_cd} msg={body.get('msg1')}")
        output1 = body.get("output1") or []
        rows: list[KisHoldingRow] = []
        for row in output1:
            qty = _to_int(row.get("hldg_qty"))
            if qty <= 0:
                continue
            rows.append(
                KisHoldingRow(
                    stock_code=str(row.get("pdno") or "").strip(),
                    stock_name=str(row.get("prdt_name") or "").strip(),
                    quantity=qty,
                    avg_buy_price=_to_decimal(row.get("pchs_avg_pric")),
                )
            )
        return rows
