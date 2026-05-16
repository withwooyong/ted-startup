"""ranking record (5 Row + 4 enum + to_payload) — Phase F-4 _records.py 신규.

설계: endpoint-18-ka10027.md § 3.4 + endpoint-19~22 + phase-f-4-rankings.md § 5.4.

본 테스트는 import 실패가 red 의도:
- `app.adapter.out.kiwoom._records.{FluRtUpperRow, TodayVolumeUpperRow, ...}` 미존재
- `RankingMarketType / RankingExchangeType / RankingType / FluRtSortType / ...` enum 미존재
→ Step 1 신규 구현 후 green.

검증 (16 시나리오):
- enum value 매핑 7 (RankingMarketType / RankingExchangeType / RankingType /
                    FluRtSortType / TodayVolumeSortType / VolumeSdninSortType /
                    VolumeSdninTimeType)
- Row.to_payload 5 endpoint (부호 / nested / now_rank / sdnin / empty)
- frozen 검증 1
- extra='ignore' 검증 1
- 빈 string 처리 (None 영속화) 1
- ka10030 nested payload (D-9) 1
"""

from __future__ import annotations

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    FluRtSortType,
    FluRtUpperRow,
    PredVolumeUpperRow,
    RankingExchangeType,
    RankingMarketType,
    RankingType,
    TodayVolumeSortType,
    TodayVolumeUpperRow,
    TradeAmountUpperRow,
    VolumeSdninRow,
    VolumeSdninSortType,
    VolumeSdninTimeType,
)

# ---------------------------------------------------------------------------
# Enum value 매핑 — 7건
# ---------------------------------------------------------------------------


def test_ranking_market_type_values() -> None:
    """RankingMarketType — 000/001/101 (Phase F 5 endpoint 공통)."""
    assert RankingMarketType.ALL.value == "000"
    assert RankingMarketType.KOSPI.value == "001"
    assert RankingMarketType.KOSDAQ.value == "101"


def test_ranking_exchange_type_values() -> None:
    """RankingExchangeType — 1/2/3 (KRX/NXT/UNIFIED)."""
    assert RankingExchangeType.KRX.value == "1"
    assert RankingExchangeType.NXT.value == "2"
    assert RankingExchangeType.UNIFIED.value == "3"


def test_ranking_type_enum_values() -> None:
    """RankingType — 5 ranking endpoint 통합 식별자.

    값은 ranking_snapshot.ranking_type 컬럼 그대로 (VARCHAR(16)).
    """
    assert RankingType.FLU_RT.value == "FLU_RT"
    assert RankingType.TODAY_VOLUME.value == "TODAY_VOLUME"
    assert RankingType.PRED_VOLUME.value == "PRED_VOLUME"
    assert RankingType.TRDE_PRICA.value == "TRDE_PRICA"
    assert RankingType.VOLUME_SDNIN.value == "VOLUME_SDNIN"


def test_flu_rt_sort_type_values() -> None:
    """FluRtSortType — ka10027 sort_tp 5종."""
    assert FluRtSortType.UP_RATE.value == "1"
    assert FluRtSortType.UP_AMOUNT.value == "2"
    assert FluRtSortType.DOWN_RATE.value == "3"
    assert FluRtSortType.DOWN_AMOUNT.value == "4"
    assert FluRtSortType.UNCHANGED.value == "5"


def test_today_volume_sort_type_values() -> None:
    """TodayVolumeSortType — ka10030 sort_tp 3종 (거래량 / 회전율 / 거래대금)."""
    assert TodayVolumeSortType.TRADE_VOLUME.value == "1"
    assert TodayVolumeSortType.TURNOVER_RATE.value == "2"
    assert TodayVolumeSortType.TRADE_AMOUNT.value == "3"


def test_volume_sdnin_sort_type_values() -> None:
    """VolumeSdninSortType — ka10023 sort_tp 4종 (급증량 / 급증률 / 감량 / 감률)."""
    assert VolumeSdninSortType.SUDDEN_VOLUME.value == "1"
    assert VolumeSdninSortType.SUDDEN_RATE.value == "2"
    assert VolumeSdninSortType.DROP_VOLUME.value == "3"
    assert VolumeSdninSortType.DROP_RATE.value == "4"


def test_volume_sdnin_time_type_values() -> None:
    """VolumeSdninTimeType — ka10023 tm_tp (1=분 / 2=전일)."""
    assert VolumeSdninTimeType.MINUTES.value == "1"
    assert VolumeSdninTimeType.PREVIOUS_DAY.value == "2"


# ---------------------------------------------------------------------------
# FluRtUpperRow.to_payload — 5건
# ---------------------------------------------------------------------------


def test_flu_rt_upper_row_to_payload_normal() -> None:
    """정상 row → 부호 흡수 + JSONB payload dict."""
    row = FluRtUpperRow(
        stk_cls="0",
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        sel_req="207",
        buy_req="3820638",
        now_trde_qty="446203",
        cntr_str="346.54",
        cnt="4",
    )
    payload = row.to_payload()

    # BIGINT 변환 (부호 흡수)
    assert payload["cur_prc"] == 74800
    assert payload["pred_pre"] == 17200
    assert payload["sel_req"] == 207
    assert payload["buy_req"] == 3820638
    assert payload["now_trde_qty"] == 446203
    # INTEGER 변환
    assert payload["cnt"] == 4
    # 시그널 string 그대로
    assert payload["pred_pre_sig"] == "1"
    # stk_nm string 그대로 (한글 보존)
    assert payload["stk_nm"] == "삼성전자"
    # stk_cls 운영 검증 대상 — string 그대로
    assert payload["stk_cls"] == "0"


def test_flu_rt_upper_row_to_payload_empty_strings_become_none() -> None:
    """빈 string 필드 → payload 에서 None (NULL 영속화 정책)."""
    row = FluRtUpperRow(stk_cd="005930")  # 나머지 모두 default=""
    payload = row.to_payload()

    # 빈 string → None
    assert payload["cur_prc"] is None
    assert payload["pred_pre"] is None
    assert payload["cnt"] is None


def test_flu_rt_upper_row_to_payload_negative_sign() -> None:
    """음수 부호 (`-12000`) → BIGINT 음수 보존."""
    row = FluRtUpperRow(
        stk_cd="005930",
        cur_prc="-12000",
        pred_pre="-2380",
        flu_rt="-5.50",
    )
    payload = row.to_payload()
    assert payload["cur_prc"] == -12000
    assert payload["pred_pre"] == -2380


def test_flu_rt_upper_row_cntr_str_jsonb_safe() -> None:
    """cntr_str (체결강도, NUMERIC) — JSONB 안전 표현 (string 또는 float)."""
    row = FluRtUpperRow(stk_cd="005930", cntr_str="346.54")
    payload = row.to_payload()

    # JSONB 에 들어갈 값 — 정밀도 보존이라면 str, 산술이라면 float
    # 핵심: None 이 아니고, "346.54" 값을 표현
    cntr_str_val = payload["cntr_str"]
    assert cntr_str_val is not None
    # string 또는 float 둘 다 허용
    assert str(cntr_str_val).rstrip("0").rstrip(".") in ("346.54", "346.5"), (
        f"cntr_str JSONB 표현 잘못: {cntr_str_val!r}"
    )


def test_flu_rt_upper_row_frozen() -> None:
    """Pydantic frozen=True — 변경 시도 시 ValidationError 또는 TypeError."""
    row = FluRtUpperRow(stk_cd="005930")
    with pytest.raises(Exception):  # noqa: B017
        row.stk_cd = "999999"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TodayVolumeUpperRow — nested payload (D-9) 1건
# ---------------------------------------------------------------------------


def test_today_volume_upper_row_to_payload_nested_d9() -> None:
    """D-9 nested payload — 23 필드를 {opmr, af_mkrt, bf_mkrt} 3 그룹 분리.

    derived feature 쿼리 단순화 — `payload->'opmr'->>'trde_qty'`.
    """
    row = TodayVolumeUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        trde_qty="446203",
        pred_rt="+15.23",
        trde_tern_rt="1.25",
        # 장중 (opmr_*)
        opmr_trde_qty="100000",
        opmr_pred_rt="+10.00",
        opmr_trde_rt="0.5",
        opmr_trde_amt="5000000",
        # 장후 (af_mkrt_*)
        af_mkrt_trde_qty="0",
        af_mkrt_pred_rt="0.00",
        af_mkrt_trde_rt="0",
        af_mkrt_trde_amt="0",
        # 장전 (bf_mkrt_*)
        bf_mkrt_trde_qty="346203",
        bf_mkrt_pred_rt="+8.5",
        bf_mkrt_trde_rt="0.75",
        bf_mkrt_trde_amt="25900000",
    )
    payload = row.to_payload()

    # 3 그룹 nested 분리
    assert "opmr" in payload
    assert "af_mkrt" in payload
    assert "bf_mkrt" in payload
    assert isinstance(payload["opmr"], dict)

    # 장중 그룹 내부
    assert payload["opmr"]["trde_qty"] == 100000
    assert payload["opmr"]["trde_amt"] == 5000000

    # 장후 그룹 — 0 값 (정상)
    assert payload["af_mkrt"]["trde_qty"] == 0

    # 장전 그룹
    assert payload["bf_mkrt"]["trde_qty"] == 346203
    assert payload["bf_mkrt"]["trde_amt"] == 25900000

    # 본 endpoint 정렬 기준은 root level
    assert payload["trde_qty"] == 446203
    # 한글 종목명 보존
    assert payload["stk_nm"] == "삼성전자"


# ---------------------------------------------------------------------------
# PredVolumeUpperRow — 6 필드 단순 1건
# ---------------------------------------------------------------------------


def test_pred_volume_upper_row_to_payload_simple() -> None:
    """ka10031 응답 6 필드 단순 — to_payload 매핑 정확."""
    row = PredVolumeUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        trde_qty="446203",
    )
    payload = row.to_payload()

    assert payload["stk_nm"] == "삼성전자"
    assert payload["cur_prc"] == 74800
    assert payload["pred_pre"] == 17200
    assert payload["trde_qty"] == 446203
    assert payload["pred_pre_sig"] == "1"


# ---------------------------------------------------------------------------
# TradeAmountUpperRow (ka10032) — now_rank/pred_rank 1건
# ---------------------------------------------------------------------------


def test_trade_amount_upper_row_now_rank_pred_rank() -> None:
    """ka10032 now_rank / pred_rank → payload 에 INTEGER."""
    row = TradeAmountUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        trde_prica="33380000",
        now_rank="1",
        pred_rank="5",
    )
    payload = row.to_payload()

    # now_rank / pred_rank INTEGER 변환
    assert payload["now_rank"] == 1
    assert payload["pred_rank"] == 5
    # primary_metric 은 외부 NormalizedRanking 에서 (string→Decimal). payload 도 BIGINT.
    assert payload["trde_prica"] == 33380000


# ---------------------------------------------------------------------------
# VolumeSdninRow (ka10023) — sdnin_rt 부호 1건
# ---------------------------------------------------------------------------


def test_volume_sdnin_row_sdnin_rt_with_sign() -> None:
    """ka10023 sdnin_rt `+38.04` — payload 의 string 또는 float 정규화."""
    row = VolumeSdninRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        sdnin_qty="1500000",
        sdnin_rt="+38.04",
    )
    payload = row.to_payload()

    # sdnin_qty BIGINT
    assert payload["sdnin_qty"] == 1500000
    # sdnin_rt 부호 흡수 + JSONB 안전 (string 또는 float)
    sdnin_rt_val = payload["sdnin_rt"]
    assert sdnin_rt_val is not None
    # +38.04 의 부호 흡수 (38.04 정상값)
    assert str(sdnin_rt_val).lstrip("+").rstrip("0").rstrip(".") in ("38.04", "38.0"), (
        f"sdnin_rt JSONB 표현 잘못: {sdnin_rt_val!r}"
    )


# ---------------------------------------------------------------------------
# extra='ignore' — 1건
# ---------------------------------------------------------------------------


def test_flu_rt_upper_row_extra_ignore() -> None:
    """Pydantic extra='ignore' — vendor 신규 필드 무시 (B-γ-1 A-H1 패턴)."""
    # 알려지지 않은 필드 포함해도 ValidationError 없이 생성
    row = FluRtUpperRow.model_validate(
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "vendor_future_field": "later_addition",
            "another_unknown": 12345,
        }
    )
    assert row.stk_cd == "005930"
    assert row.stk_nm == "삼성전자"
    # 알려지지 않은 필드는 attribute 로 접근 불가
    assert not hasattr(row, "vendor_future_field")
