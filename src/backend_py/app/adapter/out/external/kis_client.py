"""한국투자증권(KIS) 모의투자 REST 어댑터.

- 모의 전용: base_url 은 `https://openapivts.koreainvestment.com:29443` 하드코드(Settings 기본값).
- OAuth2 access_token 은 24h TTL — 프로세스 인스턴스에 캐시, 만료 300초 전 자동 재발급.
- 실거래 진입 차단: TR_ID 는 `VTTC` 접두 모의 코드만 사용. prod URL로 교체 시도 시 RuntimeError.

지원 API(MVP):
- `fetch_balance(...)`: 잔고조회(`/uapi/domestic-stock/v1/trading/inquire-balance`, TR_ID=VTTC8434R)
  - output1: 보유 종목 리스트 → `KisHoldingRow`
  - output2: 평가/예수금 요약(본 MVP 에서는 미사용)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
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
        if (
            path == "/uapi/domestic-stock/v1/trading/inquire-balance"
            and request.method == "GET"
        ):
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


@dataclass(slots=True)
class KisHoldingRow:
    stock_code: str
    stock_name: str
    quantity: int
    avg_buy_price: Decimal


class KisClientError(Exception):
    """KIS API 호출 계층의 최상위 예외."""


class KisAuthError(KisClientError):
    pass


class KisNotConfiguredError(KisClientError):
    pass


def _account_parts(account_no: str) -> tuple[str, str]:
    digits = account_no.replace("-", "").strip()
    if len(digits) < 10:
        raise KisNotConfiguredError(
            f"KIS 계좌번호는 숫자 10자리여야 함 (현재 {len(digits)}자리)"
        )
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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self._settings = s
        if s.kis_base_url_mock != _MOCK_BASE_URL:
            # 안전장치: 모의 URL 외 진입 차단
            raise KisNotConfiguredError(
                f"모의 base_url 만 허용. 현재={s.kis_base_url_mock}"
            )
        self._base_url = s.kis_base_url_mock
        self._app_key = s.kis_app_key_mock
        self._app_secret = s.kis_app_secret_mock
        self._account_no = s.kis_account_no_mock
        timeout = httpx.Timeout(
            connect=5.0, read=s.kis_request_timeout_seconds,
            write=s.kis_request_timeout_seconds, pool=5.0,
        )
        # 명시적 transport 가 없을 때만 in-memory 모드 자동 주입.
        # 테스트에서 주입하는 MockTransport 는 우선 — 런타임 플래그에 영향 안 받음.
        if transport is None and s.kis_use_in_memory_mock:
            transport = _build_in_memory_transport()
            # in-memory 모드엔 configured 체크를 우회할 수 있도록 더미 자격증명 주입.
            self._app_key = self._app_key or "in-memory-app-key"
            self._app_secret = self._app_secret or "in-memory-app-secret"
            self._account_no = self._account_no or "0000000000-01"
            logger.info("KIS in-memory mock transport 활성화 — 외부 호출 없음")
        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout, transport=transport
        )
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
            raise KisAuthError(f"토큰 요청 네트워크 오류: {exc}") from exc
        if resp.status_code != 200:
            raise KisAuthError(
                f"토큰 요청 실패: HTTP {resp.status_code} body={resp.text[:200]}"
            )
        data = resp.json()
        raw_token = data.get("access_token")
        if not isinstance(raw_token, str) or not raw_token:
            raise KisAuthError(f"access_token 부재: {data}")
        expires_in = float(data.get("expires_in") or 86400)
        self._access_token = raw_token
        self._token_expires_at = now + max(expires_in - _TOKEN_RENEW_MARGIN_SECONDS, 60.0)
        logger.info("KIS 토큰 발급 성공 (expires_in=%ds)", int(expires_in))
        return raw_token

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
            "tr_id": "VTTC8434R",  # 모의 전용 TR_ID
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
        if resp.status_code != 200:
            raise KisClientError(
                f"잔고조회 실패: HTTP {resp.status_code} body={resp.text[:300]}"
            )
        body = resp.json()
        rt_cd = body.get("rt_cd")
        if rt_cd not in ("0", 0):
            raise KisClientError(
                f"잔고조회 응답 오류: rt_cd={rt_cd} msg={body.get('msg1')}"
            )
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
