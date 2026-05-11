#!/usr/bin/env python
"""chart 영숫자 stk_cd dry-run — `^[0-9]{6}$` 가드 완화 진입 전 검증 (옵션 c-A Chunk 1).

목적:
- 키움 chart 계열 (ka10081 일봉 + ka10086 일별수급) 이 영숫자 6자리 stk_cd (예: `00088K`,
  `0000D0` — 우선주/특수 종목) 를 wire-level 에서 수용하는지 단건 확인.
- 결과에 따라 `phase-c-chart-alphanumeric-guard.md` Chunk 2 진입 또는 NO-FIX 결정.

가드 우회 정책:
- `build_stk_cd` (`stkinfo.py:439`) 의 LOOKUP 정규식 (`^[0-9]{6}$`) 가 영숫자 거부 — 본
  스크립트는 stk_cd 를 **직접 구성** (build_stk_cd 미호출). KRX: `stock_code`, NXT:
  `f"{stock_code}_NX"`. KiwoomClient.call_paginated 직접 호출 — UseCase / Adapter
  high-level API 거치지 않음.
- 운영 본 코드 변경 0. 런타임 monkey-patch 없음.

안전 정책:
- DB write 0 (read-only). 응답을 stdout / 옵션 JSON 으로 dump 만.
- `--max-pages=1` 디폴트 — 단건 검증에 1 페이지면 충분 (수백 row).
- 자격증명 env 만 — 파일 / 인자 노출 금지.
- 출력에 토큰 미포함. 응답 비식별 메타 + raw items 만.

사용 예:
    KIWOOM_APPKEY=xxxx KIWOOM_SECRETKEY=yyyy \\
    uv run python scripts/dry_run_chart_alphanumeric.py \\
        --stocks 00088K \\
        --base-date 2026-05-09 \\
        --endpoints ka10081,ka10086 \\
        --exchanges KRX \\
        --output captures/dry-run-alphanumeric-20260511.json

결과 분기 (ADR § 32 기록):
- SUCCESS: 모든 (stock, exchange, endpoint) 가 return_code=0 + items 비어있지 않음 → Chunk 2 진행
- FAIL — return_code≠0: 키움이 영숫자 stk_cd 거부 → NO-FIX
- FAIL — empty: 형식은 받지만 데이터 없음 → 사용자 결정
- MIXED: 일부만 SUCCESS → Chunk 2 범위 재정의
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# scripts/ → backend_kiwoom/ 루트 import 보장
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

# .env autoload — backfill_ohlcv.py 와 동일 패턴
for candidate in (ROOT / ".env.prod", ROOT.parent.parent / ".env.prod", ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.application.constants import ExchangeType  # noqa: E402
from app.application.dto.kiwoom_auth import KiwoomCredentials  # noqa: E402

# chart 계열 endpoint 메타 — chart.py / mrkcond.py 의 PATH / API_ID 와 동일
_ENDPOINT_META: dict[str, dict[str, str]] = {
    "ka10081": {
        "path": "/api/dostk/chart",
        "body_date_key": "base_dt",
        "extra_body": '{"upd_stkpc_tp": "1"}',  # 수정주가 (운영 기본)
        "items_key": "stk_dt_pole_chart_qry",
    },
    "ka10086": {
        "path": "/api/dostk/mrkcond",
        "body_date_key": "qry_dt",
        "extra_body": '{"indc_tp": "0"}',  # QUANTITY (수량 모드)
        "items_key": "daly_stkpc",
    },
}


def _build_stk_cd_bypass(stock_code: str, exchange: ExchangeType) -> str:
    """build_stk_cd 의 가드 우회 — 직접 suffix 합성.

    실 코드의 `build_stk_cd` 와 동일 출력 형식 (KRX = base, NXT = base + `_NX`, SOR = base
    + `_AL`) 이지만 `_STK_CD_LOOKUP_RE.fullmatch` 검증을 건너뛴다. dry-run 전용.
    """
    if exchange is ExchangeType.KRX:
        return stock_code
    if exchange is ExchangeType.NXT:
        return f"{stock_code}_NX"
    if exchange is ExchangeType.SOR:
        return f"{stock_code}_AL"
    raise ValueError(f"unknown exchange: {exchange!r}")


async def _capture_one(
    kclient: KiwoomClient,
    *,
    stock_code: str,
    base_date: date,
    exchange: ExchangeType,
    api_id: str,
    max_pages: int,
) -> dict[str, Any]:
    """단일 (stock_code, exchange, api_id) 응답 캡처. raise 안 함 — error 메타만."""
    meta = _ENDPOINT_META[api_id]
    stk_cd = _build_stk_cd_bypass(stock_code, exchange)

    body: dict[str, Any] = {
        "stk_cd": stk_cd,
        meta["body_date_key"]: base_date.strftime("%Y%m%d"),
    }
    body.update(json.loads(meta["extra_body"]))

    capture: dict[str, Any] = {
        "stock_code": stock_code,
        "exchange": exchange.value,
        "api_id": api_id,
        "stk_cd_sent": stk_cd,
        "base_date": base_date.isoformat(),
        "pages_consumed": 0,
        "row_count": 0,
        "return_code": None,
        "return_msg": None,
        "first_row_sample": None,
        "error": None,
        "verdict": None,
    }

    all_rows: list[dict[str, Any]] = []
    try:
        async for page in kclient.call_paginated(
            api_id=api_id,
            endpoint=meta["path"],
            body=body,
            max_pages=max_pages,
        ):
            capture["pages_consumed"] += 1
            page_body = page.body
            capture["return_code"] = page_body.get("return_code")
            capture["return_msg"] = (page_body.get("return_msg") or "")[:200]

            if capture["return_code"] != 0:
                capture["error"] = f"business:return_code={capture['return_code']}"
                break

            items = page_body.get(meta["items_key"]) or []
            if isinstance(items, list):
                all_rows.extend(items)
    except Exception as exc:  # noqa: BLE001 — dry-run 분석은 정상 응답 + 실패 양쪽 모두 기록 대상
        capture["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"

    capture["row_count"] = len(all_rows)
    if all_rows:
        first = all_rows[0]
        capture["first_row_sample"] = {k: first[k] for k in list(first)[:8]} if isinstance(first, dict) else str(first)[:200]

    # verdict 산정
    if capture["error"] and capture["error"].startswith("business:"):
        capture["verdict"] = "FAIL_BUSINESS"
    elif capture["error"]:
        capture["verdict"] = "FAIL_EXCEPTION"
    elif capture["return_code"] == 0 and capture["row_count"] > 0:
        capture["verdict"] = "SUCCESS"
    elif capture["return_code"] == 0 and capture["row_count"] == 0:
        capture["verdict"] = "EMPTY"
    else:
        capture["verdict"] = "UNKNOWN"

    return capture


async def _build_clients(base_url: str) -> tuple[KiwoomClient, KiwoomAuthClient]:
    """env appkey/secretkey 로 토큰 발급 + 데이터 클라이언트 빌드.

    변수명 fallback (register_credential.py 와 일관 — 운영 표준 `.env.prod` 호환):
    - `KIWOOM_API_KEY` (운영 표준) → `KIWOOM_APPKEY` (legacy)
    - `KIWOOM_API_SECRET` (운영 표준) → `KIWOOM_SECRETKEY` (legacy)
    """
    appkey = (
        os.environ.get("KIWOOM_API_KEY")
        or os.environ.get("KIWOOM_APPKEY")
        or ""
    ).strip()
    secretkey = (
        os.environ.get("KIWOOM_API_SECRET")
        or os.environ.get("KIWOOM_SECRETKEY")
        or ""
    ).strip()
    if not appkey or not secretkey:
        raise SystemExit(
            "환경변수 KIWOOM_API_KEY / KIWOOM_API_SECRET (또는 legacy KIWOOM_APPKEY / "
            "KIWOOM_SECRETKEY) 미설정 — dry-run 중단",
        )

    auth = KiwoomAuthClient(base_url=base_url)
    issued = await auth.issue_token(KiwoomCredentials(appkey=appkey, secretkey=secretkey))
    token = issued.token

    async def _token_provider() -> str:
        return token

    kclient = KiwoomClient(
        base_url=base_url,
        token_provider=_token_provider,
        timeout_seconds=15.0,
        min_request_interval_seconds=2.0,  # 키움 2초 rate limit 직렬화
        concurrent_requests=1,  # dry-run 은 직렬
    )
    return kclient, auth


async def _close_all(kclient: KiwoomClient, auth: KiwoomAuthClient) -> None:
    with contextlib.suppress(Exception):
        await kclient.close()
    with contextlib.suppress(Exception):
        await auth.close()


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_exchanges(s: str) -> list[ExchangeType]:
    out: list[ExchangeType] = []
    for raw in s.split(","):
        v = raw.strip().upper()
        if v == "KRX":
            out.append(ExchangeType.KRX)
        elif v == "NXT":
            out.append(ExchangeType.NXT)
        else:
            raise SystemExit(f"--exchanges 는 KRX/NXT 만 지원: {v!r}")
    if not out:
        raise SystemExit("--exchanges 가 비어있음")
    return out


def _parse_endpoints(s: str) -> list[str]:
    out: list[str] = []
    for raw in s.split(","):
        v = raw.strip().lower()
        if v not in _ENDPOINT_META:
            raise SystemExit(f"--endpoints 는 {sorted(_ENDPOINT_META)} 만 지원: {v!r}")
        out.append(v)
    if not out:
        raise SystemExit("--endpoints 가 비어있음")
    return out


def _overall_verdict(captures: list[dict[str, Any]]) -> str:
    """전체 결과 종합 — ADR § 32 결정 분기 입력."""
    verdicts = {c["verdict"] for c in captures}
    if verdicts == {"SUCCESS"}:
        return "ALL_SUCCESS — Chunk 2 진행 가능"
    if "SUCCESS" not in verdicts:
        return f"ALL_FAIL — NO-FIX 권고 (verdicts={verdicts})"
    return f"MIXED — Chunk 2 범위 재정의 필요 (verdicts={verdicts})"


def _print_summary(captures: list[dict[str, Any]]) -> None:
    print("\n=== dry-run 결과 요약 ===", file=sys.stderr)
    header = f"{'stock':>8} {'exch':>4} {'api_id':>8} {'rc':>5} {'rows':>5} {'verdict':>16}  error/sample"
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)
    for c in captures:
        rc = c["return_code"] if c["return_code"] is not None else "-"
        detail = c["error"] or (str(c["first_row_sample"])[:80] if c["first_row_sample"] else "(empty)")
        print(
            f"{c['stock_code']:>8} {c['exchange']:>4} {c['api_id']:>8} "
            f"{str(rc):>5} {c['row_count']:>5} {c['verdict']:>16}  {detail}",
            file=sys.stderr,
        )
    print(f"\n[verdict] {_overall_verdict(captures)}", file=sys.stderr)


async def _run(args: argparse.Namespace) -> int:
    stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]
    if not stock_codes:
        raise SystemExit("--stocks 가 비어있음")
    base_date = _parse_date(args.base_date)
    exchanges = _parse_exchanges(args.exchanges)
    endpoints = _parse_endpoints(args.endpoints)

    print(
        f"[dry-run] base_url={args.base_url} stocks={stock_codes} date={base_date} "
        f"exchanges={[e.value for e in exchanges]} endpoints={endpoints}",
        file=sys.stderr,
    )

    kclient, auth = await _build_clients(args.base_url)
    captures: list[dict[str, Any]] = []
    try:
        for code in stock_codes:
            for exch in exchanges:
                for api_id in endpoints:
                    cap = await _capture_one(
                        kclient,
                        stock_code=code,
                        base_date=base_date,
                        exchange=exch,
                        api_id=api_id,
                        max_pages=args.max_pages,
                    )
                    short = (
                        f"verdict={cap['verdict']} rc={cap['return_code']} "
                        f"rows={cap['row_count']} pages={cap['pages_consumed']}"
                    )
                    if cap["error"]:
                        short += f" err={cap['error']}"
                    print(f"  [{code} {exch.value} {api_id}] {short}", file=sys.stderr)
                    captures.append(cap)
    finally:
        await _close_all(kclient, auth)

    _print_summary(captures)

    output_payload: dict[str, Any] = {
        "metadata": {
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "base_url": args.base_url,
            "stock_codes": stock_codes,
            "base_date": base_date.isoformat(),
            "exchanges": [e.value for e in exchanges],
            "endpoints": endpoints,
            "guard_bypass": "build_stk_cd 우회 (영숫자 6자리 dry-run)",
        },
        "captures": captures,
        "overall_verdict": _overall_verdict(captures),
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(output_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[dry-run] capture saved → {out_path}", file=sys.stderr)

    # exit code — CI/스크립트 연동 시 종합 verdict 로 분기
    verdicts = {c["verdict"] for c in captures}
    if verdicts == {"SUCCESS"}:
        return 0
    if "SUCCESS" in verdicts:
        return 2  # MIXED
    return 1  # ALL_FAIL


def main() -> int:
    p = argparse.ArgumentParser(
        description="chart 영숫자 stk_cd dry-run (옵션 c-A Chunk 1)",
    )
    p.add_argument(
        "--stocks",
        required=True,
        help="comma-separated 영숫자 6자리 종목코드 (예: 00088K,0000D0)",
    )
    p.add_argument(
        "--base-date",
        required=True,
        help="YYYY-MM-DD — ka10081 base_dt / ka10086 qry_dt 동일 적용 (가까운 평일 권장)",
    )
    p.add_argument(
        "--endpoints",
        default="ka10081,ka10086",
        help=f"comma-separated. 지원: {sorted(_ENDPOINT_META)}",
    )
    p.add_argument(
        "--exchanges",
        default="KRX",
        help="KRX | NXT | KRX,NXT (디폴트 KRX). NXT 는 우선주 거래 가능 여부 부수 검증",
    )
    p.add_argument(
        "--base-url",
        default="https://api.kiwoom.com",
        help="기본 운영 도메인. mockapi.kiwoom.com 은 NXT 미지원",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="(stock, exchange, endpoint) 별 최대 page (디폴트 1 — dry-run 단건 검증)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="JSON dump 경로 (옵션. 디렉토리 자동 생성)",
    )
    args = p.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
