#!/usr/bin/env python3
"""DART corpCode.xml 전체 → dart_corp_mapping 벌크 동기화.

DART OpenAPI `/api/corpCode.xml` 에서 전체 기업 ZIP 을 내려받아
KOSPI+KOSDAQ 보통주만 필터한 뒤 `dart_corp_mapping` 테이블에 upsert.

필터 기준:
  1) stock_code 가 6자리 숫자이고 끝자리가 '0' → 보통주
     (우선주는 끝자리 5/7/9, KONEX 일부도 0 이 아님)
  2) corp_name 에 스팩/리츠/ETF/ETN/인프라투융자회사 키워드 없음
  3) KRX 현재 상장 종목과 교차 (옵션, 기본 ON) — 과거 상장폐지 종목 배제

ETF/ETN 은 펀드 상품이라 법인 등록이 없어 대부분 자연 제외되지만,
corpCode.xml 에 예외적으로 노출되는 경우를 대비해 방어 필터 유지.
리츠와 스팩은 법인으로 등록되므로 반드시 이름 기반 필터가 필요하다.

DART corpCode.xml 은 상장폐지 이력도 stock_code 를 유지하므로(최초 실측에서
전체 통과 3,654건 중 과거 폐지 종목 다수 관찰) pykrx 의 현재 상장 리스트와
교차 필터링해 실사용 가치가 있는 종목만 남긴다. KRX 익명 차단 상황에서는
경고 후 DART 필터 결과로 fallback.

사용 예:
  # 컨테이너 내부 (운영 환경과 동일) — 기본 교차 필터 ON
  docker compose exec backend python -m scripts.sync_dart_corp_mapping

  # dry-run 으로 필터 결과만 확인
  python -m scripts.sync_dart_corp_mapping --dry-run

  # KRX 교차 필터 없이 DART 기준으로만 upsert
  python -m scripts.sync_dart_corp_mapping --no-cross-filter-krx
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapter.out.external import DartClient
from app.adapter.out.persistence.repositories import DartCorpMappingRepository
from app.config.settings import get_settings

# ---------------------------------------------------------------------------
# 필터 (순수 함수 — 유닛 테스트 가능)
# ---------------------------------------------------------------------------

# 종목명에 포함되면 제외. 부분 일치 기준.
# - "스팩", "기업인수목적" → 스팩(SPAC). 분석 대상 아님.
# - "리츠", "부동산투자회사" → REITs. 사용자 요청으로 제외.
# - "인프라투융자회사" → 맥쿼리인프라 등 공모 인프라펀드.
# - "ETF", "ETN", "상장지수" → 펀드형 상품. 대부분 DART corpCode 에 없지만 방어용.
EXCLUDED_NAME_PATTERNS: tuple[str, ...] = (
    "스팩",
    "기업인수목적",
    "리츠",
    "부동산투자회사",
    "인프라투융자회사",
    "ETF",
    "ETN",
    "상장지수",
)

# DART 가 일부 공모 인프라펀드를 단축명으로 저장하는 케이스 대응.
# 예) 정식명 "맥쿼리한국인프라투융자회사" → DART corp_name = "맥쿼리인프라"
# 이름 기반 패턴만으론 매칭 실패 → 명시적 stock_code 블랙리스트로 보완.
# "인프라" 를 이름 패턴에 추가하면 "현대인프라코어" 등 일반 기업도 오탐되므로 지양.
EXCLUDED_STOCK_CODES: frozenset[str] = frozenset({
    "088980",  # 맥쿼리한국인프라투융자회사 (DART: "맥쿼리인프라")
    "423310",  # KB발해인프라투융자회사
})


def is_common_stock_code(stock_code: str) -> bool:
    """6자리 숫자이고 끝자리가 '0' 이면 보통주."""
    return (
        len(stock_code) == 6
        and stock_code.isdigit()
        and stock_code.endswith("0")
    )


def is_excluded_by_name(corp_name: str) -> bool:
    """스팩/리츠/ETF/ETN/인프라 펀드 여부."""
    name = corp_name.strip()
    if not name:
        return True
    return any(pat in name for pat in EXCLUDED_NAME_PATTERNS)


def is_excluded_by_code(stock_code: str) -> bool:
    """명시적 제외 종목 코드 (DART 단축명 매칭 실패 보완)."""
    return stock_code in EXCLUDED_STOCK_CODES


# ---------------------------------------------------------------------------
# XML 파싱
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class CorpRow:
    corp_code: str
    corp_name: str
    stock_code: str  # 비상장은 빈 문자열


def extract_xml_from_zip(zip_bytes: bytes) -> bytes:
    """ZIP 안의 첫 번째 XML 엔트리를 반환."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError("corpCode ZIP 에 XML 엔트리가 없음")
        with zf.open(xml_names[0]) as fp:
            return fp.read()


def parse_corp_code_xml(xml_bytes: bytes) -> Iterator[CorpRow]:
    """corpCode.xml 을 <list> 단위로 yield.

    보안 주의:
      - 입력은 DART OpenAPI (`https://opendart.fss.or.kr/api/corpCode.xml`) 전용.
        §11.2 신뢰 출처 설계의 Tier1 공식 API 이므로 임의 XML 은 받지 않는다.
      - Python 3.7.1+ 의 stdlib ET 는 외부 엔티티(XXE) 를 기본 차단한다.
      - 범용 XML(외부 소스) 로 확장되면 `defusedxml` 도입 필요.
    """
    root = ET.fromstring(xml_bytes)
    for item in root.findall("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        if not corp_code or not corp_name:
            continue
        yield CorpRow(corp_code=corp_code, corp_name=corp_name, stock_code=stock_code)


def filter_listed_common_stocks(rows: Iterable[CorpRow]) -> list[CorpRow]:
    """상장 보통주 + 비펀드만 통과."""
    kept: list[CorpRow] = []
    for r in rows:
        if not is_common_stock_code(r.stock_code):
            continue
        if is_excluded_by_name(r.corp_name):
            continue
        if is_excluded_by_code(r.stock_code):
            continue
        kept.append(r)
    return kept


def fetch_krx_listed_codes() -> set[str]:
    """KOSPI + KOSDAQ 현재 상장 종목코드 집합.

    pykrx 가 KRX 익명 차단(carry-over) 등으로 실패하면 빈 집합 반환.
    호출부는 빈 집합이면 교차 필터 생략하고 DART 결과로 fallback 한다.
    KONEX 는 거래량/유동성이 낮아 AI 리포트 대상에서 제외.
    """
    try:
        from pykrx import stock as pykrx_stock
        kospi = set(pykrx_stock.get_market_ticker_list(market="KOSPI"))
        kosdaq = set(pykrx_stock.get_market_ticker_list(market="KOSDAQ"))
        return kospi | kosdaq
    except Exception as exc:  # pykrx 네트워크/인증 실패 전반
        print(
            f"[sync] WARN: KRX 상장 리스트 조회 실패 "
            f"({exc.__class__.__name__}: {exc})",
            file=sys.stderr,
        )
        print(
            "[sync]        → KRX 교차 필터 생략, DART 필터 결과로 fallback",
            file=sys.stderr,
        )
        return set()


def filter_by_krx_listing(
    rows: Iterable[CorpRow], krx_codes: set[str]
) -> list[CorpRow]:
    """KRX 현재 상장 리스트에 존재하는 종목만 통과. 빈 집합이면 전체 통과."""
    if not krx_codes:
        return list(rows)
    return [r for r in rows if r.stock_code in krx_codes]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run(
    *,
    dry_run: bool = False,
    batch_size: int = 500,
    cross_filter_krx: bool = True,
) -> int:
    settings = get_settings()
    if not settings.dart_api_key:
        print("[sync] DART_API_KEY 미설정 — 중단", file=sys.stderr)
        return 2

    async with DartClient(settings) as client:
        print("[sync] corpCode.xml ZIP 다운로드 시작", flush=True)
        zip_bytes = await client.fetch_corp_code_zip()
        print(f"[sync] ZIP 수신: {len(zip_bytes):,} bytes", flush=True)

    xml_bytes = extract_xml_from_zip(zip_bytes)
    all_rows = list(parse_corp_code_xml(xml_bytes))
    with_stock = [r for r in all_rows if r.stock_code]
    kept = filter_listed_common_stocks(all_rows)

    print(f"[sync] 전체 corpCode 항목    : {len(all_rows):,}", flush=True)
    print(f"[sync]   stock_code 보유    : {len(with_stock):,}", flush=True)
    print(f"[sync]   → 보통주·비펀드 통과: {len(kept):,}", flush=True)

    if cross_filter_krx:
        print("[sync] KRX 현재 상장 리스트 조회 중 (pykrx)...", flush=True)
        krx_codes = fetch_krx_listed_codes()
        if krx_codes:
            print(
                f"[sync]   KRX 상장 종목 수(KOSPI+KOSDAQ): {len(krx_codes):,}",
                flush=True,
            )
            before = len(kept)
            kept = filter_by_krx_listing(kept, krx_codes)
            print(
                f"[sync]   → KRX 교차 필터: {before:,} → {len(kept):,} 건",
                flush=True,
            )
        else:
            print(
                "[sync]   (KRX 조회 실패 — 교차 필터 생략, DART 필터 결과 유지)",
                flush=True,
            )

    if dry_run:
        print("[sync] --dry-run 모드 — DB upsert 생략. 샘플 10건:", flush=True)
        for r in kept[:10]:
            print(f"  {r.stock_code} {r.corp_code} {r.corp_name}", flush=True)
        return 0

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    total_upserted = 0
    try:
        async with session_factory() as session, session.begin():
            repo = DartCorpMappingRepository(session)
            for i in range(0, len(kept), batch_size):
                batch = kept[i:i + batch_size]
                payload = [(r.stock_code, r.corp_code, r.corp_name) for r in batch]
                total_upserted += await repo.upsert_many(payload)
                print(
                    f"[sync]   upsert {i + len(batch):,}/{len(kept):,}",
                    flush=True,
                )
    finally:
        await engine.dispose()

    print(f"[sync] 완료 — upsert rowcount={total_upserted:,}", flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DART corpCode.xml 전체 → dart_corp_mapping 벌크 upsert",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="DB 변경 없이 필터 결과와 샘플만 출력",
    )
    parser.add_argument(
        "--batch-size", type=int, default=500,
        help="upsert 배치 크기 (기본 500)",
    )
    parser.add_argument(
        "--no-cross-filter-krx",
        dest="cross_filter_krx", action="store_false",
        help="KRX 현재 상장 리스트와의 교차 필터 비활성 (DART 기준만 사용)",
    )
    parser.set_defaults(cross_filter_krx=True)
    args = parser.parse_args()
    rc = asyncio.run(run(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        cross_filter_krx=args.cross_filter_krx,
    ))
    sys.exit(rc)


if __name__ == "__main__":
    main()
