"""DART corpCode 벌크 sync — 필터 로직 + ZIP/XML 파싱 단위 테스트."""

from __future__ import annotations

import io
import zipfile

import httpx
import pytest

from app.adapter.out.external import DartClient, DartUpstreamError
from app.config.settings import Settings
from scripts.sync_dart_corp_mapping import (
    CorpRow,
    extract_xml_from_zip,
    fetch_krx_listed_codes,
    filter_by_krx_listing,
    filter_listed_common_stocks,
    is_common_stock_code,
    is_excluded_by_code,
    is_excluded_by_name,
    parse_corp_code_xml,
)

# ---------------------------------------------------------------------------
# is_common_stock_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stock_code,expected",
    [
        ("005930", True),  # 삼성전자 보통주
        ("000660", True),  # SK하이닉스
        ("035420", True),  # NAVER
        ("005935", False),  # 삼성전자우 — 끝자리 5 우선주
        ("005937", False),  # 삼성전자 2우B — 끝자리 7
        ("005939", False),  # 끝자리 9
        ("", False),
        ("00593", False),  # 자리수 부족
        ("A05930", False),  # 문자 포함 (KOSPI200 ETF 심볼 가짜 케이스)
        ("0059300", False),  # 7자리
    ],
)
def test_is_common_stock_code(stock_code: str, expected: bool) -> None:
    assert is_common_stock_code(stock_code) is expected


# ---------------------------------------------------------------------------
# is_excluded_by_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "corp_name,excluded",
    [
        ("삼성전자", False),
        ("SK하이닉스", False),
        ("네이버", False),
        # 스팩
        ("미래에셋비전스팩1호", True),
        ("NH기업인수목적12호", True),
        # 리츠
        ("SK리츠", True),
        ("KB스타리츠", True),
        ("맥쿼리부동산투자회사", True),
        # 인프라 펀드
        ("맥쿼리한국인프라투융자회사", True),
        # ETF/ETN
        ("KODEX 200 ETF", True),
        ("삼성 WTI원유 ETN", True),
        ("TIGER 상장지수", True),
        # 경계 — 빈 문자열은 안전하게 제외
        ("", True),
        ("   ", True),
    ],
)
def test_is_excluded_by_name(corp_name: str, excluded: bool) -> None:
    assert is_excluded_by_name(corp_name) is excluded


# ---------------------------------------------------------------------------
# filter_listed_common_stocks
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# is_excluded_by_code (stock_code 블랙리스트)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stock_code,excluded",
    [
        ("088980", True),  # 맥쿼리한국인프라투융자회사 (DART 단축명 "맥쿼리인프라")
        ("423310", True),  # KB발해인프라투융자회사
        ("005930", False),  # 삼성전자
        ("000660", False),  # SK하이닉스
        ("", False),
    ],
)
def test_is_excluded_by_code(stock_code: str, excluded: bool) -> None:
    assert is_excluded_by_code(stock_code) is excluded


def test_filter_applies_stock_code_blacklist() -> None:
    """이름으론 안 잡히지만 명시 블랙리스트로 제외되는 케이스."""
    rows = [
        CorpRow(corp_code="00126380", corp_name="삼성전자", stock_code="005930"),
        # DART 가 단축명으로 저장한 맥쿼리인프라 — 이름 필터 통과하지만 코드 블랙리스트에 있음
        CorpRow(corp_code="00335812", corp_name="맥쿼리인프라", stock_code="088980"),
        CorpRow(corp_code="00999999", corp_name="KB발해인프라", stock_code="423310"),
    ]
    kept = filter_listed_common_stocks(rows)
    assert [r.stock_code for r in kept] == ["005930"]


def test_filter_by_krx_listing_keeps_intersection() -> None:
    rows = [
        CorpRow(corp_code="00126380", corp_name="삼성전자", stock_code="005930"),
        CorpRow(corp_code="00164779", corp_name="SK하이닉스", stock_code="000660"),
        CorpRow(corp_code="99999999", corp_name="상폐기업", stock_code="111110"),
    ]
    # 상폐기업은 KRX 현재 상장 리스트에 없음
    krx_codes = {"005930", "000660", "035420"}
    kept = filter_by_krx_listing(rows, krx_codes)
    assert [r.stock_code for r in kept] == ["005930", "000660"]


def test_filter_by_krx_listing_passes_through_on_empty_set() -> None:
    """KRX 조회 실패(=빈 집합) 시 원본 그대로 fallback."""
    rows = [
        CorpRow(corp_code="00126380", corp_name="삼성전자", stock_code="005930"),
        CorpRow(corp_code="99999999", corp_name="상폐기업", stock_code="111110"),
    ]
    kept = filter_by_krx_listing(rows, set())
    assert len(kept) == 2


def test_fetch_krx_listed_codes_returns_union_of_kospi_kosdaq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pykrx import stock as pykrx_stock

    def fake_list(market: str) -> list[str]:
        if market == "KOSPI":
            return ["005930", "000660"]
        if market == "KOSDAQ":
            return ["035420", "251270"]
        return []

    monkeypatch.setattr(pykrx_stock, "get_market_ticker_list", fake_list)
    codes = fetch_krx_listed_codes()
    assert codes == {"005930", "000660", "035420", "251270"}


def test_fetch_krx_listed_codes_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pykrx 가 KRX 익명 차단 등으로 실패하면 빈 집합 + 경고 메시지."""
    from pykrx import stock as pykrx_stock

    def broken(*_args: object, **_kwargs: object) -> list[str]:
        raise RuntimeError("KRX anonymous access blocked")

    monkeypatch.setattr(pykrx_stock, "get_market_ticker_list", broken)
    codes = fetch_krx_listed_codes()
    assert codes == set()
    captured = capsys.readouterr()
    assert "KRX 상장 리스트 조회 실패" in captured.err
    assert "fallback" in captured.err


def test_filter_listed_common_stocks_applies_both_rules() -> None:
    rows = [
        CorpRow(corp_code="00126380", corp_name="삼성전자", stock_code="005930"),
        CorpRow(corp_code="00126381", corp_name="삼성전자우", stock_code="005935"),
        CorpRow(corp_code="00126382", corp_name="SK리츠", stock_code="395400"),
        CorpRow(corp_code="00126383", corp_name="미래에셋비전스팩1호", stock_code="437760"),
        CorpRow(corp_code="00126384", corp_name="NAVER", stock_code="035420"),
        # 비상장 — stock_code 빈 값
        CorpRow(corp_code="00126385", corp_name="비상장법인", stock_code=""),
        # 코드에 문자 포함 (정상적으로 제외되는지)
        CorpRow(corp_code="00126386", corp_name="수상한기업", stock_code="A00001"),
        CorpRow(corp_code="00126387", corp_name="KODEX 200 ETF", stock_code="069500"),
    ]
    kept = filter_listed_common_stocks(rows)
    assert [r.stock_code for r in kept] == ["005930", "035420"]


# ---------------------------------------------------------------------------
# XML / ZIP parsing
# ---------------------------------------------------------------------------


_SAMPLE_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
    <stock_code>005930</stock_code>
    <modify_date>20250101</modify_date>
  </list>
  <list>
    <corp_code>99999999</corp_code>
    <corp_name>\xec\x9d\xb4\xec\x83\x81\xed\x95\x9c\xec\xa0\x84\xec\x9e\x90</corp_name>
    <stock_code></stock_code>
    <modify_date>20250101</modify_date>
  </list>
  <list>
    <corp_code></corp_code>
    <corp_name>\xeb\xa7\x89</corp_name>
    <stock_code>999990</stock_code>
    <modify_date>20250101</modify_date>
  </list>
</result>
"""


def test_parse_corp_code_xml_skips_incomplete_rows() -> None:
    rows = list(parse_corp_code_xml(_SAMPLE_XML))
    assert len(rows) == 2
    assert rows[0].corp_code == "00126380"
    assert rows[0].corp_name == "삼성전자"
    assert rows[0].stock_code == "005930"
    assert rows[1].stock_code == ""  # 비상장도 유지, 필터는 상위에서


def test_extract_xml_from_zip_returns_first_xml_entry() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CORPCODE.xml", _SAMPLE_XML)
    xml_bytes = extract_xml_from_zip(buf.getvalue())
    assert b"<corp_code>00126380</corp_code>" in xml_bytes


def test_extract_xml_from_zip_raises_when_no_xml() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", b"no xml here")
    with pytest.raises(ValueError, match="XML 엔트리"):
        extract_xml_from_zip(buf.getvalue())


# ---------------------------------------------------------------------------
# DartClient.fetch_corp_code_zip
# ---------------------------------------------------------------------------


def _settings() -> Settings:
    return Settings(dart_api_key="FAKE-DART-KEY")


@pytest.mark.asyncio
async def test_fetch_corp_code_zip_returns_binary_when_zip_magic() -> None:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CORPCODE.xml", _SAMPLE_XML)
    zip_payload = zip_buf.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/corpCode.xml")
        assert request.url.params.get("crtfc_key") == "FAKE-DART-KEY"
        return httpx.Response(
            200,
            content=zip_payload,
            headers={"content-type": "application/x-msdownload"},
        )

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        data = await client.fetch_corp_code_zip()
    assert data.startswith(b"PK\x03\x04")
    assert data == zip_payload


@pytest.mark.asyncio
async def test_fetch_corp_code_zip_raises_on_json_error_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "010", "message": "미등록된 키"},
        )

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        with pytest.raises(DartUpstreamError, match="status=010"):
            await client.fetch_corp_code_zip()


@pytest.mark.asyncio
async def test_fetch_corp_code_zip_raises_on_http_500() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="DART down")

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        with pytest.raises(DartUpstreamError):
            await client.fetch_corp_code_zip()
