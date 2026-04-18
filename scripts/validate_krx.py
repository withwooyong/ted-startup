#!/usr/bin/env python3
"""
KRX 계정 유효성 검증 (값 비노출)

.env.prod 에서 KRX_ID / KRX_PW 를 읽어 pykrx 로그인 세션을 구성한 뒤
최근 거래일의 OHLCV 1건을 요청해 응답 여부만 판정한다.

사용:
    uv run --with pykrx python3 scripts/validate_krx.py
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"[FATAL] {path} 파일을 찾을 수 없음")
        sys.exit(1)
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def recent_weekday(days_back: int = 1) -> str:
    """최근 평일(거래일 근사) YYYYMMDD."""
    d = date.today() - timedelta(days=days_back)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def main() -> int:
    env = load_env(Path(".env.prod"))
    krx_id = env.get("KRX_ID")
    krx_pw = env.get("KRX_PW")

    print("=" * 58)
    if not krx_id or not krx_pw:
        missing = [k for k in ("KRX_ID", "KRX_PW") if not env.get(k)]
        for k in missing:
            print(f"[FAIL] {k:<22} .env.prod 에 누락")
        print("=" * 58)
        return 1

    os.environ["KRX_ID"] = krx_id
    os.environ["KRX_PW"] = krx_pw

    # 구조 진단(값 비노출)
    print(f"[INFO] KRX_ID 길이={len(krx_id)}자, KRX_PW 길이={len(krx_pw)}자")

    # pykrx 는 로그인 과정에서 ID 및 기타 정보를 stdout/stderr 로 출력한다.
    # 값 비노출 원칙을 지키기 위해 import·로그인 전후 출력은 버퍼로 가두고
    # 로그인 성공 여부만 단일 라인으로 요약 노출.
    pykrx_noise = io.StringIO()
    try:
        with contextlib.redirect_stdout(pykrx_noise), contextlib.redirect_stderr(pykrx_noise):
            from pykrx import stock  # type: ignore[import-not-found]
            # 강제 로그인 트리거 — 첫 인증 필요 호출로 세션 확립
            stock.get_shorting_volume_by_ticker(recent_weekday(1))
    except Exception as e:
        print(f"[FAIL] KRX 로그인/pykrx 초기화: {type(e).__name__}: {str(e)[:120]}")
        return 1
    login_ok = "KRX 로그인 완료" in pykrx_noise.getvalue()
    print(f"[INFO] KRX 로그인: {'성공' if login_ok else '확인 불가(라이브러리 로그 변경 가능성)'}")

    target = recent_weekday(1)
    results: list[tuple[str, bool, str]] = []

    def _silently(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return fn(*args, **kwargs)

    # 1) 시가총액 (베이스라인 — 보통 인증 없이도 됨)
    try:
        df = _silently(stock.get_market_cap_by_ticker, target)
        results.append(("OHLCV/시가총액", len(df) > 0, f"{target} {len(df)}종목"))
    except Exception as e:
        results.append(("OHLCV/시가총액", False, f"{type(e).__name__}: {str(e)[:80]}"))

    # 2) 공매도 거래 (인증 필수)
    try:
        df = _silently(stock.get_shorting_volume_by_ticker, target)
        results.append(("공매도 거래(인증 필수)", len(df) > 0, f"{target} {len(df)}종목"))
    except Exception as e:
        results.append(("공매도 거래(인증 필수)", False, f"{type(e).__name__}: {str(e)[:80]}"))

    # 3) 대차잔고 — pykrx 의 ticker 기준 함수는 스키마 불일치가 있어 date 기준으로 대체 시도
    for fn_name in ("get_shorting_balance_by_ticker", "get_shorting_balance_by_date"):
        fn = getattr(stock, fn_name, None)
        if fn is None:
            continue
        try:
            # by_date 류는 종목코드 인자 필요(삼성전자 005930 샘플)
            df = _silently(fn, target) if "ticker" in fn_name else _silently(fn, target, target, "005930")
            if len(df) > 0:
                results.append((f"대차잔고({fn_name})", True, f"{target} {len(df)}rows"))
                break
            else:
                results.append((f"대차잔고({fn_name})", False, "0 rows"))
        except Exception as e:
            results.append((f"대차잔고({fn_name})", False, f"{type(e).__name__}: {str(e)[:80]}"))

    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name:<26} {detail}")
    print("=" * 58)

    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
