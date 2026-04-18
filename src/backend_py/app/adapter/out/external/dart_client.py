"""DART OpenAPI (금융감독원 공시시스템) 어댑터.

§11.2 의 3-Tier 신뢰 출처 설계에서 **Tier 1 (공식 API)** 에 해당. 재무 숫자와 공시
원문의 유일한 원천으로 사용하며, LLM web_search 로는 대체하지 않는다.

지원 엔드포인트(MVP 3종):
- `fetch_company(corp_code)` — 기업개황 (`/api/company.json`)
- `fetch_disclosures(...)` — 공시검색 (`/api/list.json`)
- `fetch_financial_summary(...)` — 단일회사 전체 재무제표 주요계정
  (`/api/fnlttSinglAcntAll.json`)

응답 규약:
- DART 는 HTTP 200 + `{"status": "000"}` 이 정상. 그 외 상태 코드는 모두 예외.
- `013` = 조회된 데이타가 없음 → 빈 리스트 반환(호출부 무조건 처리).
- 나머지 오류는 `DartClientError` 로 승격.

Rate limit:
- 무료 키 일 10,000 호출 — 본 어댑터는 단건 호출만 수행. 캐시는 상위 UseCase 책임.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# 정상 처리 상태 코드
_OK = "000"
# 데이터 없음 — 공시·재무가 전무한 신규 상장 등에서 정상 발생
_NO_DATA = "013"


class DartClientError(Exception):
    """DART API 호출 계층 상위 예외."""


class DartNotConfiguredError(DartClientError):
    pass


class DartUpstreamError(DartClientError):
    """상태코드·HTTP 오류 등 업스트림 응답 이상."""


# ---------- Response DTOs ----------


@dataclass(slots=True)
class DartCompanyInfo:
    corp_code: str
    corp_name: str
    corp_name_eng: str | None
    stock_code: str | None
    ceo_nm: str | None
    corp_cls: str | None  # Y=유가, K=코스닥, N=코넥스, E=기타
    induty_code: str | None
    est_dt: str | None  # YYYYMMDD
    adres: str | None
    hm_url: str | None
    phn_no: str | None


@dataclass(slots=True)
class DartDisclosure:
    corp_code: str
    corp_name: str
    stock_code: str | None
    report_nm: str
    rcept_no: str  # 접수번호 (보고서 PK)
    rcept_dt: str  # YYYYMMDD
    flr_nm: str | None  # 제출인
    rm: str | None  # 비고

    @property
    def dart_viewer_url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.rcept_no}"


@dataclass(slots=True)
class DartFinancialRow:
    account_nm: str           # 계정명 (예: '매출액')
    account_id: str | None    # XBRL 태그
    fs_div: str               # CFS(연결) / OFS(개별)
    fs_nm: str                # 재무제표명
    sj_div: str               # BS / IS / CIS / CF 등
    sj_nm: str
    thstrm_nm: str            # 당기 (예: '제 54 기')
    thstrm_amount: Decimal    # 당기 금액
    frmtrm_nm: str | None
    frmtrm_amount: Decimal | None
    bfefrmtrm_nm: str | None
    bfefrmtrm_amount: Decimal | None
    currency: str | None


@dataclass(slots=True)
class DartFinancialStatement:
    corp_code: str
    bsns_year: int
    reprt_code: str
    fs_div: str
    rows: list[DartFinancialRow] = field(default_factory=list)


# ---------- Helpers ----------


def _to_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "--"):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        d = Decimal(s)
    except Exception:
        return None
    return -d if neg else d


def _str_or_none(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


# ---------- Client ----------


class DartClient:
    """DART OpenAPI async 어댑터. 프로세스당 1 인스턴스 권장."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self._api_key = s.dart_api_key
        timeout = httpx.Timeout(
            connect=5.0, read=s.dart_request_timeout_seconds,
            write=s.dart_request_timeout_seconds, pool=5.0,
        )
        self._client = httpx.AsyncClient(
            base_url=s.dart_base_url, timeout=timeout, transport=transport
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> DartClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        if not self.configured:
            raise DartNotConfiguredError("DART_API_KEY 누락")
        merged = {"crtfc_key": self._api_key, **params}
        resp = await self._client.get(path, params=merged)
        if resp.status_code != 200:
            raise DartUpstreamError(
                f"DART HTTP {resp.status_code} path={path} body={resp.text[:200]}"
            )
        try:
            body = cast(dict[str, Any], resp.json())
        except ValueError as exc:
            raise DartUpstreamError(f"DART 응답 JSON 파싱 실패: {resp.text[:200]}") from exc
        status_code = str(body.get("status", ""))
        if status_code in (_OK, _NO_DATA):
            return body
        raise DartUpstreamError(
            f"DART status={status_code} message={body.get('message', '')}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_company(self, corp_code: str) -> DartCompanyInfo | None:
        """기업개황. corp_code 미등록 시 None."""
        body = await self._get("/company.json", {"corp_code": corp_code})
        if str(body.get("status")) == _NO_DATA:
            return None
        return DartCompanyInfo(
            corp_code=str(body.get("corp_code", corp_code)),
            corp_name=str(body.get("corp_name", "")),
            corp_name_eng=_str_or_none(body.get("corp_name_eng")),
            stock_code=_str_or_none(body.get("stock_code")),
            ceo_nm=_str_or_none(body.get("ceo_nm")),
            corp_cls=_str_or_none(body.get("corp_cls")),
            induty_code=_str_or_none(body.get("induty_code")),
            est_dt=_str_or_none(body.get("est_dt")),
            adres=_str_or_none(body.get("adres")),
            hm_url=_str_or_none(body.get("hm_url")),
            phn_no=_str_or_none(body.get("phn_no")),
        )

    async def fetch_disclosures(
        self,
        corp_code: str,
        *,
        bgn_de: str,   # YYYYMMDD
        end_de: str,   # YYYYMMDD
        page_no: int = 1,
        page_count: int = 20,
    ) -> list[DartDisclosure]:
        """기간 내 공시목록. 최신순."""
        params = {
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": str(max(1, page_no)),
            "page_count": str(max(1, min(page_count, 100))),
        }
        body = await self._get("/list.json", params)
        if str(body.get("status")) == _NO_DATA:
            return []
        raw = body.get("list") or []
        rows: list[DartDisclosure] = []
        for r in raw:
            rows.append(DartDisclosure(
                corp_code=str(r.get("corp_code", corp_code)),
                corp_name=str(r.get("corp_name", "")),
                stock_code=_str_or_none(r.get("stock_code")),
                report_nm=str(r.get("report_nm", "")),
                rcept_no=str(r.get("rcept_no", "")),
                rcept_dt=str(r.get("rcept_dt", "")),
                flr_nm=_str_or_none(r.get("flr_nm")),
                rm=_str_or_none(r.get("rm")),
            ))
        return rows

    async def fetch_financial_summary(
        self,
        corp_code: str,
        *,
        bsns_year: int,
        reprt_code: str = "11011",  # 기본: 사업보고서(연간). 분기: 11013(1Q), 11012(반기), 11014(3Q)
        fs_div: str = "CFS",        # CFS 연결 / OFS 별도
    ) -> DartFinancialStatement:
        """단일회사 재무제표 주요계정 (전체 계정)."""
        params = {
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        }
        body = await self._get("/fnlttSinglAcntAll.json", params)
        rows: list[DartFinancialRow] = []
        if str(body.get("status")) == _OK:
            for r in body.get("list") or []:
                rows.append(DartFinancialRow(
                    account_nm=str(r.get("account_nm", "")),
                    account_id=_str_or_none(r.get("account_id")),
                    fs_div=str(r.get("fs_div", fs_div)),
                    fs_nm=str(r.get("fs_nm", "")),
                    sj_div=str(r.get("sj_div", "")),
                    sj_nm=str(r.get("sj_nm", "")),
                    thstrm_nm=str(r.get("thstrm_nm", "")),
                    thstrm_amount=_to_decimal(r.get("thstrm_amount")) or Decimal("0"),
                    frmtrm_nm=_str_or_none(r.get("frmtrm_nm")),
                    frmtrm_amount=_to_decimal(r.get("frmtrm_amount")),
                    bfefrmtrm_nm=_str_or_none(r.get("bfefrmtrm_nm")),
                    bfefrmtrm_amount=_to_decimal(r.get("bfefrmtrm_amount")),
                    currency=_str_or_none(r.get("currency")),
                ))
        return DartFinancialStatement(
            corp_code=corp_code,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
            fs_div=fs_div,
            rows=rows,
        )
