#!/usr/bin/env python3
"""과거 N 영업일 stock_price 실데이터 백필.

POST /api/batch/collect?date=YYYY-MM-DD 를 영업일별로 반복 호출해
stock_price · short_selling 등을 실데이터로 채운다.

기본값은 3년(~752 영업일). pykrx rate limit(2초) 고려 시 약 2시간 소요.
중간 실패는 개별 날짜 단위로만 기록하고 다음 날짜로 계속 진행.
이미 적재된 날짜는 배치 내부에서 upsert 로 멱등 처리되므로 재실행 안전.

사용:
  docker compose exec backend python -m scripts.backfill_stock_prices
  docker compose exec backend python -m scripts.backfill_stock_prices --days 252
  docker compose exec backend python -m scripts.backfill_stock_prices --end 2026-04-17
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta


def business_days_back(end: date, count: int) -> list[date]:
    """end(포함) 에서 거꾸로 count 영업일을 오름차순으로 반환."""
    out: list[date] = []
    cur = end
    while len(out) < count:
        if cur.weekday() < 5:  # Mon..Fri
            out.append(cur)
        cur -= timedelta(days=1)
    return list(reversed(out))


def call_collect(api_key: str, target: date, timeout_s: float) -> tuple[int, str]:
    """단일 날짜 수집 — (http_status, body_preview) 반환."""
    req = urllib.request.Request(
        f"http://localhost:8000/api/batch/collect?date={target.isoformat()}",
        method="POST",
        headers={"X-API-Key": api_key},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_s)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:200]
    except Exception as e:  # noqa: BLE001 — 네트워크/파이프 오류 일반
        return -1, f"{type(e).__name__}: {e}"


def run(*, days: int, end: date, timeout_s: float) -> int:
    api_key = os.environ.get("ADMIN_API_KEY", "")
    if not api_key:
        print("[backfill] ADMIN_API_KEY 미설정 — 중단", file=sys.stderr)
        return 2

    targets = business_days_back(end, days)
    print(
        f"[backfill] 대상 {len(targets)} 영업일 ({targets[0]} ~ {targets[-1]}). "
        f"예상 소요 약 {len(targets) * 10 // 60}분",
        flush=True,
    )

    ok = 0
    fail = 0
    started = time.monotonic()
    for i, d in enumerate(targets, start=1):
        t0 = time.monotonic()
        status, body = call_collect(api_key, d, timeout_s)
        elapsed = time.monotonic() - t0
        if status == 200:
            ok += 1
            print(
                f"[backfill] [{i:>3}/{len(targets)}] {d} OK ({elapsed:.1f}s) {body}",
                flush=True,
            )
        else:
            fail += 1
            print(
                f"[backfill] [{i:>3}/{len(targets)}] {d} FAIL({status}) "
                f"({elapsed:.1f}s) {body}",
                flush=True,
            )

    total = time.monotonic() - started
    print(
        f"[backfill] 완료 — 총 {len(targets)} 일 · 성공 {ok} · 실패 {fail} · "
        f"소요 {total // 60:.0f}분 {total % 60:.0f}초",
        flush=True,
    )
    return 0 if fail == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="과거 N 영업일 stock_price 백필 (POST /api/batch/collect 반복)",
    )
    parser.add_argument(
        "--days", type=int, default=752,
        help="영업일 개수 (기본 752 ≈ 3년)",
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="기준 종료일 YYYY-MM-DD (기본: 오늘)",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="단일 호출 타임아웃 초 (기본 120s)",
    )
    args = parser.parse_args()
    end = date.fromisoformat(args.end) if args.end else date.today()
    rc = run(days=args.days, end=end, timeout_s=args.timeout)
    sys.exit(rc)


if __name__ == "__main__":
    main()
