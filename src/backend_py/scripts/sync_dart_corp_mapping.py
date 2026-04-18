#!/usr/bin/env python3
"""DART corpCode.xml 전체 → dart_corp_mapping 벌크 동기화.

DART OpenAPI `/api/corpCode.xml` 에서 전체 기업 ZIP 을 내려받아
KOSPI+KOSDAQ 보통주만 필터한 뒤 `dart_corp_mapping` 테이블에 upsert.

필터 기준:
  1) stock_code 가 6자리 숫자이고 끝자리가 '0' → 보통주
     (우선주는 끝자리 5/7/9, KONEX 일부도 0 이 아님)
  2) corp_name 에 스팩/리츠/ETF/ETN/인프라투융자회사 키워드 없음

ETF/ETN 은 펀드 상품이라 법인 등록이 없어 대부분 자연 제외되지만,
corpCode.xml 에 예외적으로 노출되는 경우를 대비해 방어 필터 유지.
리츠와 스팩은 법인으로 등록되므로 반드시 이름 기반 필터가 필요하다.

사용 예:
  # 컨테이너 내부 (운영 환경과 동일)
  docker compose exec backend python -m scripts.sync_dart_corp_mapping

  # 로컬 (dry-run 으로 DB 변경 없이 결과만 확인)
  python -m scripts.sync_dart_corp_mapping --dry-run
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
        kept.append(r)
    return kept


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run(*, dry_run: bool = False, batch_size: int = 500) -> int:
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
    args = parser.parse_args()
    rc = asyncio.run(run(dry_run=args.dry_run, batch_size=args.batch_size))
    sys.exit(rc)


if __name__ == "__main__":
    main()
