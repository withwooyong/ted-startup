"""scripts/sync_stock_master.py CLI — argparse + format_summary.

DB / 키움 호출 통합은 별도 e2e — 본 테스트는 CLI 진입점만.
"""

from __future__ import annotations

import pytest

from app.application.service.stock_master_service import (
    MarketStockOutcome,
    StockMasterSyncResult,
)

# ---------- argparse ----------


def test_parse_args_alias_required() -> None:
    """--alias 필수."""
    from scripts.sync_stock_master import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parse_args_default_log_level() -> None:
    """--log-level 디폴트 INFO."""
    from scripts.sync_stock_master import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "prod"])
    assert args.log_level == "INFO"


# ---------- format_summary ----------


def test_format_summary_all_succeeded() -> None:
    """5 시장 모두 성공 — all_succeeded=True 표시."""
    from scripts.sync_stock_master import format_summary

    result = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=900, upserted=900, deactivated=0, nxt_enabled_count=400),
            MarketStockOutcome(market_code="10", fetched=1500, upserted=1500, deactivated=0, nxt_enabled_count=600),
        ],
        total_fetched=2400,
        total_upserted=2400,
        total_deactivated=0,
        total_nxt_enabled=1000,
    )
    out = format_summary(result=result, elapsed_seconds=12.34)
    assert "all_succeeded:     True" in out
    assert "elapsed:           12.3s" in out
    assert "total_upserted:    2400" in out
    assert "OK" in out


def test_format_summary_partial_failure() -> None:
    """한 시장 실패 — error 표시 + all_succeeded=False."""
    from scripts.sync_stock_master import format_summary

    result = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=900, upserted=900, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(
                market_code="10",
                fetched=0,
                upserted=0,
                deactivated=0,
                nxt_enabled_count=0,
                error="KiwoomUpstreamError: 503",
            ),
        ],
        total_fetched=900,
        total_upserted=900,
        total_deactivated=0,
        total_nxt_enabled=0,
    )
    out = format_summary(result=result, elapsed_seconds=5.0)
    assert "all_succeeded:     False" in out
    assert "ERROR=KiwoomUpstreamError: 503" in out
