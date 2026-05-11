#!/usr/bin/env python
"""ka10086 dry-run capture — 가설 B (이중 부호) + NXT mirror 검증.

목적:
- 운영 첫 호출에서 raw 응답을 수집 + 이중 부호 빈도 측정 + KRX vs NXT diff 분석
- DB / TokenManager 우회 (env appkey/secretkey 직접 사용) — 최소 setup 으로 실행

사용 예:
    KIWOOM_APPKEY=xxxx KIWOOM_SECRETKEY=yyyy \\
    uv run python scripts/dry_run_ka10086_capture.py \\
        --stocks 005930,000660,035720 \\
        --query-date 2026-05-08 \\
        --exchanges KRX,NXT \\
        --output captures/ka10086-dryrun-20260508.json

분석 출력:
- 22 필드 fill rate
- 이중 부호 (`--XXX` / `++XXX`) 발생 컬럼 + 빈도
- 신규 부호 패턴 (가설 외) 검출
- KRX vs NXT diff (mirror 여부 판단 — 같은 종목·같은 일자 투자자별 net 비교)
- for_qty >= |for_netprps| 합리성

안전 정책:
- DB write 0 (read-only). 본 스크립트는 키움 호출 + JSON dump 만.
- 앱키/시크릿키는 env 만 — 파일 / 인자에 절대 노출 금지.
- 출력 JSON 에 토큰 미포함. raw 응답 본문만.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# app/ 루트 import 보장
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom._records import (  # noqa: E402
    DailyMarketResponse,
    DailyMarketRow,
    NormalizedDailyFlow,
)
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.adapter.out.kiwoom.stkinfo import build_stk_cd  # noqa: E402
from app.application.constants import DailyMarketDisplayMode, ExchangeType  # noqa: E402
from app.application.dto.kiwoom_auth import KiwoomCredentials  # noqa: E402

# DailyMarketRow 의 22 필드 — fill rate / 부호 패턴 측정 대상
_DATA_FIELDS = (
    "open_pric", "high_pric", "low_pric", "close_pric",
    "pred_rt", "flu_rt", "trde_qty", "amt_mn",
    "crd_rt", "crd_remn_rt",
    "ind", "orgn", "frgn", "prm",
    "for_qty", "for_rt", "for_poss", "for_wght",
    "for_netprps", "orgn_netprps", "ind_netprps",
)
# NXT mirror 판단의 핵심 — 투자자별 net + 외인 거래량
_INVESTOR_FIELDS = (
    "ind", "orgn", "frgn", "prm",
    "for_qty", "for_netprps", "orgn_netprps", "ind_netprps",
)
# 부호 prefix 검출 정규식
_DOUBLE_NEG = re.compile(r"^-{2,}")
_DOUBLE_POS = re.compile(r"^\+{2,}")
_MIXED_SIGN = re.compile(r"^[+\-]{2,}")


# ============================================================================
# 캡처 — KRX/NXT 양쪽 호출 + raw + normalized
# ============================================================================


async def _capture_one(
    kclient: KiwoomClient,
    stock_code: str,
    *,
    query_date: date,
    exchange: ExchangeType,
    indc_mode: DailyMarketDisplayMode,
    max_rows: int,
    max_pages: int,
) -> dict[str, Any]:
    """단일 (stock_code, exchange) 캡처. raw rows + normalized + 페이지 메타.

    `KiwoomClient.call_paginated` 직접 사용 — `fetch_daily_market` 의 cap (10) 우회.
    `max_rows` 또는 `max_pages` 도달 시 페이지네이션 조기 중단 (가설 B / NXT mirror 분석엔
    수백 row 면 충분). 운영 raw 응답 빈도 측정에 적합.

    실패해도 raise 안 함 — error 필드에 type 만 기록.
    """
    capture: dict[str, Any] = {
        "stock_code": stock_code,
        "exchange": exchange.value,
        "indc_mode": indc_mode.value,
        "query_date": query_date.isoformat(),
        "rows_raw": [],
        "rows_normalized": [],
        "row_count": 0,
        "pages_consumed": 0,
        "stopped_reason": None,
        "error": None,
    }

    try:
        expected_stk_cd = build_stk_cd(stock_code, exchange)
    except Exception as exc:  # noqa: BLE001
        capture["error"] = f"build_stk_cd:{type(exc).__name__}"
        return capture

    body: dict[str, Any] = {
        "stk_cd": expected_stk_cd,
        "qry_dt": query_date.strftime("%Y%m%d"),
        "indc_tp": indc_mode.value,
    }

    all_raw: list[dict[str, Any]] = []
    pages_consumed = 0
    stopped = "completed"
    try:
        async for page in kclient.call_paginated(
            api_id="ka10086",
            endpoint="/api/dostk/mrkcond",
            body=body,
            max_pages=max_pages,
        ):
            pages_consumed += 1
            try:
                parsed = DailyMarketResponse.model_validate(page.body)
            except Exception as exc:  # noqa: BLE001 — Pydantic ValidationError 등
                capture["error"] = f"validation:{type(exc).__name__}"
                stopped = "validation_error"
                break

            if parsed.return_code != 0:
                capture["error"] = f"business:return_code={parsed.return_code}"
                stopped = "business_error"
                break

            for row in parsed.daly_stkpc:
                all_raw.append(row.model_dump())
                if len(all_raw) >= max_rows:
                    break

            if len(all_raw) >= max_rows:
                stopped = "max_rows_reached"
                break
    except Exception as exc:  # noqa: BLE001 — KiwoomMaxPagesExceededError 포함
        capture["error"] = type(exc).__name__
        stopped = "exception_partial"

    capture["row_count"] = len(all_raw)
    capture["pages_consumed"] = pages_consumed
    capture["stopped_reason"] = stopped
    capture["rows_raw"] = all_raw

    # raw → DailyMarketRow → NormalizedDailyFlow (정규화 검증 + 부호 처리 가설 적용)
    normalized: list[NormalizedDailyFlow] = []
    for raw in all_raw:
        try:
            row = DailyMarketRow.model_validate(raw)
        except Exception:  # noqa: BLE001 — 분석은 raw 가 우선, normalized 는 best-effort
            continue
        normalized.append(
            row.to_normalized(stock_id=0, exchange=exchange, indc_mode=indc_mode)
        )

    capture["rows_normalized"] = [
        {
            "trading_date": n.trading_date.isoformat() if n.trading_date != date.min else None,
            "exchange": n.exchange.value,
            "indc_mode": n.indc_mode.value,
            "credit_rate": str(n.credit_rate) if n.credit_rate is not None else None,
            "individual_net": n.individual_net,
            "institutional_net": n.institutional_net,
            "foreign_brokerage_net": n.foreign_brokerage_net,
            "program_net": n.program_net,
            "foreign_volume": n.foreign_volume,
            "foreign_rate": str(n.foreign_rate) if n.foreign_rate is not None else None,
            "foreign_holdings": n.foreign_holdings,
            # C-2γ Migration 008 — D-E 중복 3 컬럼 (foreign/institutional/individual_net_purchase)
            # 은 NormalizedDailyFlow 에서 제거. C-2δ Migration 013 — C/E 중복 2 컬럼
            # (credit_balance_rate / foreign_weight) 도 동일하게 제거 (2.88M rows IS DISTINCT FROM=0).
        }
        for n in normalized
    ]
    return capture


# ============================================================================
# 분석 — 가설 B 정확성 + NXT mirror + fill rate
# ============================================================================


def _analyze_signs(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """22 필드 부호 prefix 패턴 카운트.

    측정:
    - double_neg_count[col] — `--XXX` 발생 횟수
    - double_pos_count[col] — `++XXX` 발생 횟수
    - mixed_sign_count[col] — 그 외 부호 prefix 2개 이상 (`+-` `-+` 등)
    - sample[col] — 발견된 raw 값 sample (max 5개)
    """
    double_neg: Counter[str] = Counter()
    double_pos: Counter[str] = Counter()
    mixed: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    total_rows = 0

    for cap in captures:
        for row in cap["rows_raw"]:
            total_rows += 1
            for col in _DATA_FIELDS:
                val = str(row.get(col, "") or "").strip()
                if not val:
                    continue
                if _DOUBLE_NEG.match(val):
                    double_neg[col] += 1
                    if len(samples[col]) < 5:
                        samples[col].append(val)
                elif _DOUBLE_POS.match(val):
                    double_pos[col] += 1
                    if len(samples[col]) < 5:
                        samples[col].append(val)
                elif _MIXED_SIGN.match(val):
                    mixed[col] += 1
                    if len(samples[col]) < 5:
                        samples[col].append(val)

    return {
        "total_rows_scanned": total_rows,
        "double_neg_count": dict(double_neg),
        "double_pos_count": dict(double_pos),
        "mixed_sign_count": dict(mixed),
        "samples_by_column": dict(samples),
    }


def _analyze_fill_rate(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """22 필드 비어있지 않은 row 수 / 전체 row 수."""
    counters: Counter[str] = Counter()
    total = 0
    for cap in captures:
        for row in cap["rows_raw"]:
            total += 1
            for col in _DATA_FIELDS:
                val = str(row.get(col, "") or "").strip()
                if val:
                    counters[col] += 1
    return {
        "total_rows": total,
        "fill_rate": {
            col: f"{counters[col]}/{total} ({100 * counters[col] / total:.1f}%)" if total else "0/0"
            for col in _DATA_FIELDS
        },
    }


def _analyze_nxt_mirror(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """KRX vs NXT 같은 (stock_code, trading_date) row 의 투자자별 net 비교.

    mirror 판단 휴리스틱:
    - 모든 _INVESTOR_FIELDS 값이 동일 → mirror 강력 의심 (NXT 컬럼 의미 약함)
    - 일부 필드만 동일 → partial mirror
    - 모두 다르면 NXT 가 독립 집계 (KRX/NXT 분리 row 의미 명확)
    """
    by_pair: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for cap in captures:
        if cap["error"]:
            continue
        for row in cap["rows_raw"]:
            dt = str(row.get("date", "") or "").strip()
            if not dt:
                continue
            key = (cap["stock_code"], dt)
            by_pair[key][cap["exchange"]] = row

    comparisons: list[dict[str, Any]] = []
    for (stock_code, dt), exchanges in by_pair.items():
        if "KRX" not in exchanges or "NXT" not in exchanges:
            continue
        krx_row = exchanges["KRX"]
        nxt_row = exchanges["NXT"]
        diffs: dict[str, dict[str, Any]] = {}
        identical_cols: list[str] = []
        for col in _INVESTOR_FIELDS:
            krx_v = str(krx_row.get(col, "") or "").strip()
            nxt_v = str(nxt_row.get(col, "") or "").strip()
            if krx_v == nxt_v:
                identical_cols.append(col)
            else:
                diffs[col] = {"krx": krx_v, "nxt": nxt_v}
        comparisons.append({
            "stock_code": stock_code,
            "trading_date": dt,
            "identical_columns": identical_cols,
            "differing_columns": diffs,
            "mirror_verdict": (
                "FULL_MIRROR" if len(identical_cols) == len(_INVESTOR_FIELDS)
                else "PARTIAL_MIRROR" if identical_cols
                else "INDEPENDENT"
            ),
        })

    verdict_counter: Counter[str] = Counter(c["mirror_verdict"] for c in comparisons)
    return {
        "pairs_compared": len(comparisons),
        "verdict_summary": dict(verdict_counter),
        "comparisons": comparisons,
    }


def _analyze_partial_mirror_breakdown(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """PARTIAL_MIRROR 케이스 컬럼별 KRX vs NXT 동일/상이 빈도.

    `_analyze_nxt_mirror` 가 페어 단위 verdict 만 산출 — 본 함수는 컬럼 단위로 풀어
    어떤 필드가 KRX 와 NXT 사이 항상 동일하고 (= mirror), 어떤 필드가 항상 다른지 (= 분리
    집계) 식별.
    """
    by_pair: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for cap in captures:
        if cap["error"]:
            continue
        for row in cap["rows_raw"]:
            dt = str(row.get("date", "") or "").strip()
            if dt:
                by_pair[(cap["stock_code"], dt)][cap["exchange"]] = row

    identical: Counter[str] = Counter()
    differing: Counter[str] = Counter()
    pairs = 0
    for exchanges in by_pair.values():
        if "KRX" not in exchanges or "NXT" not in exchanges:
            continue
        pairs += 1
        for col in _INVESTOR_FIELDS:
            k = str(exchanges["KRX"].get(col, "") or "").strip()
            n = str(exchanges["NXT"].get(col, "") or "").strip()
            if k == n:
                identical[col] += 1
            else:
                differing[col] += 1
    return {
        "pairs": pairs,
        "identical_per_column": {col: identical.get(col, 0) for col in _INVESTOR_FIELDS},
        "differing_per_column": {col: differing.get(col, 0) for col in _INVESTOR_FIELDS},
    }


def _analyze_d_vs_e_equality(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """D 카테고리 (ind/orgn/frgn/prm) ↔ E 카테고리 (xxx_netprps, for_qty) row-by-row 동일성.

    의도: dry-run 첫 회차에서 sample 값이 동일하게 보이는 패턴이 진짜 row-by-row 같은지
    검증. 같다면 stock_daily_flow 컬럼 모델에 중복이 있을 가능성 — 컬럼 정리 trigger.

    검사 쌍 (의미 분류):
    - ind ↔ ind_netprps          (개인 vs 개인 순매수)
    - orgn ↔ orgn_netprps        (기관 vs 기관 순매수)
    - frgn ↔ for_netprps         (외국계 vs 외인 순매수 — 분류 다름, 같은지 의심 케이스)
    - for_qty ↔ for_netprps      (외인 거래량 vs 외인 순매수 — 의미 다름, sample 동일 의심)
    """
    pairs = (
        ("ind", "ind_netprps"),
        ("orgn", "orgn_netprps"),
        ("frgn", "for_netprps"),
        ("for_qty", "for_netprps"),
    )
    results: dict[str, dict[str, Any]] = {}
    for d_col, e_col in pairs:
        equal = 0
        diff = 0
        total = 0
        diff_samples: list[dict[str, str]] = []
        for cap in captures:
            for row in cap["rows_raw"]:
                d = str(row.get(d_col, "") or "").strip()
                e = str(row.get(e_col, "") or "").strip()
                if not d and not e:
                    continue
                total += 1
                if d == e:
                    equal += 1
                else:
                    diff += 1
                    if len(diff_samples) < 5:
                        diff_samples.append({d_col: d, e_col: e})
        equality_rate = (equal / total * 100.0) if total else 0.0
        results[f"{d_col}_vs_{e_col}"] = {
            "equal": equal,
            "different": diff,
            "total": total,
            "equality_rate_pct": round(equality_rate, 2),
            "diff_samples": diff_samples,
        }
    return results


def _analyze_for_qty_invariant(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """`for_qty` >= |for_netprps| 합리성 (외인 거래량 >= 외인 net) — 가설 검증.

    위반 시 → 단위 mismatch 또는 부호 처리 오류 의심.
    """
    violations: list[dict[str, Any]] = []
    checked = 0
    for cap in captures:
        if cap["error"]:
            continue
        for raw, norm in zip(cap["rows_raw"], cap["rows_normalized"], strict=False):
            checked += 1
            for_qty = norm.get("foreign_volume")
            for_net = norm.get("foreign_net_purchase")
            if for_qty is None or for_net is None:
                continue
            if abs(for_qty) < abs(for_net):
                violations.append({
                    "stock_code": cap["stock_code"],
                    "exchange": cap["exchange"],
                    "trading_date": norm.get("trading_date"),
                    "for_qty": for_qty,
                    "for_netprps": for_net,
                    "raw_for_qty": raw.get("for_qty"),
                    "raw_for_netprps": raw.get("for_netprps"),
                })
    return {
        "rows_checked": checked,
        "violations": violations,
        "violation_count": len(violations),
    }


# ============================================================================
# Auth + 호출 setup
# ============================================================================


async def _build_clients(base_url_prod: str) -> tuple[KiwoomClient, KiwoomAuthClient]:
    """env appkey/secretkey 로 토큰 발급 후 데이터 클라이언트 빌드."""
    appkey = os.environ.get("KIWOOM_APPKEY", "").strip()
    secretkey = os.environ.get("KIWOOM_SECRETKEY", "").strip()
    if not appkey or not secretkey:
        raise SystemExit("환경변수 KIWOOM_APPKEY / KIWOOM_SECRETKEY 미설정 — dry-run 중단")

    auth = KiwoomAuthClient(base_url=base_url_prod)
    issued = await auth.issue_token(KiwoomCredentials(appkey=appkey, secretkey=secretkey))
    token = issued.token

    async def _token_provider() -> str:
        return token

    kclient = KiwoomClient(
        base_url=base_url_prod,
        token_provider=_token_provider,
        timeout_seconds=15.0,
        min_request_interval_seconds=0.25,
        concurrent_requests=2,  # dry-run 은 보수적
    )
    return kclient, auth


async def _close_all(kclient: KiwoomClient, auth: KiwoomAuthClient) -> None:
    """best-effort close — kclient + auth 둘 다 httpx.AsyncClient 보유."""
    with contextlib.suppress(Exception):
        await kclient.close()
    with contextlib.suppress(Exception):
        await auth.close()


# ============================================================================
# 메인
# ============================================================================


def _run_analysis(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """5개 분석 함수 일괄 실행 (dry-run + analyze-only 둘 다 사용)."""
    return {
        "fill_rate": _analyze_fill_rate(captures),
        "sign_patterns": _analyze_signs(captures),
        "nxt_mirror": _analyze_nxt_mirror(captures),
        "partial_mirror_breakdown": _analyze_partial_mirror_breakdown(captures),
        "d_vs_e_equality": _analyze_d_vs_e_equality(captures),
        "for_qty_invariant": _analyze_for_qty_invariant(captures),
    }


def _print_summary(analysis: dict[str, Any]) -> None:
    """분석 요약 stdout 출력."""
    print("\n=== 분석 요약 ===")
    print(f"fill_rate (rows={analysis['fill_rate']['total_rows']}):")
    for col, rate in analysis["fill_rate"]["fill_rate"].items():
        print(f"  {col:>16}: {rate}")
    print(f"\nsign_patterns (rows scanned={analysis['sign_patterns']['total_rows_scanned']}):")
    print(f"  double_neg (--): {analysis['sign_patterns']['double_neg_count']}")
    print(f"  double_pos (++): {analysis['sign_patterns']['double_pos_count']}")
    print(f"  mixed sign:      {analysis['sign_patterns']['mixed_sign_count']}")
    if analysis["sign_patterns"]["samples_by_column"]:
        print("  samples (max 5/column):")
        for col, sample in analysis["sign_patterns"]["samples_by_column"].items():
            print(f"    {col}: {sample}")
    print(f"\nnxt_mirror: pairs_compared={analysis['nxt_mirror']['pairs_compared']} "
          f"verdict={analysis['nxt_mirror']['verdict_summary']}")
    pmb = analysis["partial_mirror_breakdown"]
    print(f"\npartial_mirror_breakdown (pairs={pmb['pairs']}):")
    print("  컬럼별 KRX==NXT identical / 상이 (동일률):")
    for col in pmb["identical_per_column"]:
        identical = pmb["identical_per_column"][col]
        differing = pmb["differing_per_column"][col]
        total = identical + differing
        rate = f"{100 * identical / total:.1f}%" if total else "n/a"
        print(f"    {col:>14}: identical={identical:4} different={differing:4} ({rate} mirror)")
    print("\nd_vs_e_equality (D 카테고리 ↔ E 카테고리 row-by-row 동일성):")
    for pair_name, res in analysis["d_vs_e_equality"].items():
        print(f"  {pair_name}: equal={res['equal']} diff={res['different']} "
              f"total={res['total']} ({res['equality_rate_pct']}% 동일)")
        if res["diff_samples"]:
            print(f"    diff samples (max 5): {res['diff_samples']}")
    print(f"\nfor_qty_invariant: violations={analysis['for_qty_invariant']['violation_count']} "
          f"/ {analysis['for_qty_invariant']['rows_checked']} rows")
    if analysis["for_qty_invariant"]["violations"]:
        print(f"  first 3 violations: {analysis['for_qty_invariant']['violations'][:3]}")


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


async def _run(args: argparse.Namespace) -> int:
    stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]
    if not stock_codes:
        raise SystemExit("--stocks 가 비어있음")
    query_date = _parse_date(args.query_date)
    exchanges = _parse_exchanges(args.exchanges)
    indc_mode = (
        DailyMarketDisplayMode.AMOUNT
        if args.indc_mode.upper() == "AMOUNT"
        else DailyMarketDisplayMode.QUANTITY
    )
    base_url = args.base_url

    print(f"[dry-run] base_url={base_url} stocks={stock_codes} date={query_date} "
          f"exchanges={[e.value for e in exchanges]} indc_mode={indc_mode.value}",
          file=sys.stderr)

    kclient, auth = await _build_clients(base_url)
    captures: list[dict[str, Any]] = []
    try:
        for code in stock_codes:
            for exch in exchanges:
                cap = await _capture_one(
                    kclient, code,
                    query_date=query_date, exchange=exch, indc_mode=indc_mode,
                    max_rows=args.max_rows, max_pages=args.max_pages,
                )
                status_parts = [f"rows={cap['row_count']}", f"pages={cap['pages_consumed']}",
                                f"stop={cap['stopped_reason']}"]
                if cap["error"]:
                    status_parts.append(f"error={cap['error']}")
                print(f"  [{code} {exch.value}] {' '.join(status_parts)}", file=sys.stderr)
                captures.append(cap)
    finally:
        await _close_all(kclient, auth)

    analysis = _run_analysis(captures)

    output: dict[str, Any] = {
        "metadata": {
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "base_url": base_url,
            "stock_codes": stock_codes,
            "query_date": query_date.isoformat(),
            "exchanges": [e.value for e in exchanges],
            "indc_mode": indc_mode.value,
        },
        "captures": captures,
        "analysis": analysis,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[dry-run] capture saved → {out_path}", file=sys.stderr)

    _print_summary(analysis)

    return 0


def _run_analyze_only(input_path: Path) -> int:
    """이미 캡처된 JSON 을 읽어 분석만 다시 실행 (API 재호출 없음)."""
    if not input_path.exists():
        raise SystemExit(f"--analyze-only 입력 파일 없음: {input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    captures: list[dict[str, Any]] = payload.get("captures", [])
    if not captures:
        raise SystemExit(f"입력 파일에 captures 가 비어있음: {input_path}")
    print(f"[analyze-only] {input_path} (captures={len(captures)})", file=sys.stderr)
    analysis = _run_analysis(captures)
    _print_summary(analysis)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ka10086 dry-run capture (가설 B + NXT mirror)")
    p.add_argument("--stocks", help="comma-separated 6자리 종목코드 (예: 005930,000660)")
    p.add_argument("--query-date", help="YYYY-MM-DD (가까운 평일 권장)")
    p.add_argument("--exchanges", default="KRX,NXT", help="KRX | NXT | KRX,NXT")
    p.add_argument("--indc-mode", default="QUANTITY", choices=("QUANTITY", "AMOUNT"))
    p.add_argument("--base-url", default="https://api.kiwoom.com",
                   help="기본 운영 도메인. mockapi.kiwoom.com 은 NXT 미지원")
    p.add_argument("--output", default="captures/ka10086-dryrun.json",
                   help="JSON dump 경로 (디렉토리 자동 생성)")
    p.add_argument("--max-rows", type=int, default=200,
                   help="(stock, exchange) 별 최대 row 누적 수. 가설 B / NXT mirror 분석엔 200 충분")
    p.add_argument("--max-pages", type=int, default=200,
                   help="(stock, exchange) 별 최대 page 호출 수 (cont-yn=Y 무한 루프 방어)")
    p.add_argument("--analyze-only", type=Path, metavar="JSON",
                   help="이미 캡처된 JSON 재분석 (API 재호출 없음). 지정 시 다른 인자 무시")
    args = p.parse_args()
    if args.analyze_only:
        return _run_analyze_only(args.analyze_only)
    if not args.stocks or not args.query_date:
        raise SystemExit("--stocks 와 --query-date 는 dry-run 모드에서 필수")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
