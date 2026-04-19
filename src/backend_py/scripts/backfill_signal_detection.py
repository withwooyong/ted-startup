#!/usr/bin/env python3
"""과거 N 영업일 signal 탐지 백필.

POST /api/signals/detect?date=YYYY-MM-DD 를 영업일별로 반복 호출해
RAPID_DECLINE / TREND_REVERSAL / SHORT_SQUEEZE 를 일괄 탐지·적재한다.

stock_price 의 DISTINCT trading_date 를 기준 영업일로 사용 —
주말/공휴일을 자연 제외하므로 business_days_back 보다 정확.
SignalDetectionService.detect_all 은 existing_keys 로 중복 skip 하므로
재실행해도 안전(멱등).

사용:
  docker compose exec backend python -m scripts.backfill_signal_detection
  docker compose exec backend python -m scripts.backfill_signal_detection --since 2025-01-01
  docker compose exec backend python -m scripts.backfill_signal_detection --since 2026-04-17 --until 2026-04-17  # 1일만
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


async def _list_trading_dates(since: date | None, until: date | None) -> list[date]:
    """stock_price 에서 실제 거래가 있었던 trading_date 오름차순 반환."""
    from sqlalchemy import select

    from app.adapter.out.persistence.models import StockPrice
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stmt = select(StockPrice.trading_date).distinct().order_by(StockPrice.trading_date)
        if since is not None:
            stmt = stmt.where(StockPrice.trading_date >= since)
        if until is not None:
            stmt = stmt.where(StockPrice.trading_date <= until)
        rows = (await session.execute(stmt)).scalars().all()
    await get_engine().dispose()
    return list(rows)


def call_detect(api_key: str, target: date, timeout_s: float) -> tuple[int, str]:
    """단일 날짜 탐지 — (http_status, body_preview)."""
    url = f"http://localhost:8000/api/signals/detect?date={target.isoformat()}"
    req = urllib.request.Request(
        url, method="POST", headers={"X-API-Key": api_key}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_s)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def run(*, since: date | None, until: date | None, timeout_s: float) -> int:
    api_key = os.environ.get("ADMIN_API_KEY", "")
    if not api_key:
        print("[detect-backfill] ADMIN_API_KEY 미설정 — 중단", file=sys.stderr)
        return 2

    targets = asyncio.run(_list_trading_dates(since, until))
    if not targets:
        print("[detect-backfill] 대상 날짜 없음 — stock_price 에 데이터 부재", file=sys.stderr)
        return 0

    print(
        f"[detect-backfill] 대상 {len(targets)} 영업일 ({targets[0]} ~ {targets[-1]})",
        flush=True,
    )

    ok = 0
    fail = 0
    total_signals = {"rapid_decline": 0, "trend_reversal": 0, "short_squeeze": 0}
    started = time.monotonic()

    for i, d in enumerate(targets, start=1):
        t0 = time.monotonic()
        status, body = call_detect(api_key, d, timeout_s)
        elapsed = time.monotonic() - t0
        if status == 200:
            ok += 1
            # body 는 JSON: {"rapid_decline":N,"trend_reversal":N,"short_squeeze":N,"elapsed_ms":N}
            import json
            try:
                parsed = json.loads(body)
                for k in total_signals:
                    total_signals[k] += int(parsed.get(k, 0))
                summary = (
                    f"rapid={parsed.get('rapid_decline', 0)} "
                    f"trend={parsed.get('trend_reversal', 0)} "
                    f"squeeze={parsed.get('short_squeeze', 0)}"
                )
            except Exception:
                summary = body
            print(
                f"[detect-backfill] [{i:>3}/{len(targets)}] {d} OK ({elapsed:.1f}s) {summary}",
                flush=True,
            )
        else:
            fail += 1
            print(
                f"[detect-backfill] [{i:>3}/{len(targets)}] {d} FAIL({status}) "
                f"({elapsed:.1f}s) {body}",
                flush=True,
            )

    total_elapsed = time.monotonic() - started
    print(
        f"[detect-backfill] 완료 — 총 {len(targets)} 일 · 성공 {ok} · 실패 {fail} · "
        f"소요 {total_elapsed // 60:.0f}분 {total_elapsed % 60:.0f}초 · "
        f"누적 시그널 rapid={total_signals['rapid_decline']} "
        f"trend={total_signals['trend_reversal']} "
        f"squeeze={total_signals['short_squeeze']}",
        flush=True,
    )
    return 0 if fail == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="과거 영업일 signal 탐지 백필 (POST /api/signals/detect 반복)",
    )
    parser.add_argument(
        "--since", type=str, default=None,
        help="시작일 YYYY-MM-DD (기본: stock_price 최소 trading_date)",
    )
    parser.add_argument(
        "--until", type=str, default=None,
        help="종료일 YYYY-MM-DD (기본: stock_price 최대 trading_date)",
    )
    parser.add_argument(
        "--timeout", type=float, default=180.0,
        help="단일 호출 타임아웃 초 (기본 180s)",
    )
    args = parser.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    until = date.fromisoformat(args.until) if args.until else None
    rc = run(since=since, until=until, timeout_s=args.timeout)
    sys.exit(rc)


if __name__ == "__main__":
    main()
