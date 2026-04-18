#!/usr/bin/env python3
"""
KRX 공개 API 응답 캡처 스크립트 (Phase 3 Python 어댑터 회귀 기준)

Java KrxClient.java와 동일한 요청 포맷으로 3개 엔드포인트를 호출하여
실제 응답 JSON을 같은 디렉토리에 저장한다.

공개 엔드포인트(인증 불필요), 요청 간 2초 간격 준수.
"""
from __future__ import annotations

import json
import sys
import time
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiStat/",
    "Origin": "https://data.krx.co.kr",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
REQUEST_INTERVAL = 2.0  # IP 차단 방지

ENDPOINTS = [
    (
        "short_selling",
        {
            "bld": "dbms/MDC/STAT/srt/MDCSTAT1251",
            "searchType": "1",
            "mktId": "ALL",
        },
    ),
    (
        "lending_balance",
        {
            "bld": "dbms/MDC/STAT/srt/MDCSTAT1251",
            "searchType": "2",
            "mktId": "ALL",
        },
    ),
    (
        "stock_price",
        {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
            "mktId": "ALL",
        },
    ),
]


def _build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    # 세션 쿠키 선획득: KRX 포털 메인에 GET으로 노크
    # KRX 포털은 진입 페이지 방문으로 JSESSIONID 발급. 현재 활성 URL 복수 시도.
    warmup_urls = [
        "https://data.krx.co.kr/",
        "https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd",
        "https://data.krx.co.kr/contents/SRT/02/02010000/SRT02010000.jsp",
    ]
    for u in warmup_urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": HEADERS["User-Agent"]})
            with opener.open(req, timeout=15) as r:
                r.read()
        except Exception as e:
            print(f"[WARN] warmup {u} → {type(e).__name__}")
    cookie_names = [c.name for c in jar]
    print(f"[INFO] 획득 쿠키: {cookie_names}")
    return opener


def capture(target_date: date, out_dir: Path) -> int:
    date_str = target_date.strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    opener = _build_opener()

    for idx, (name, params) in enumerate(ENDPOINTS):
        if idx > 0:
            time.sleep(REQUEST_INTERVAL)

        # Java KrxClient와 동일하게 URL-encode 없이 raw 연결(KRX가 bld 값의 '/'를 raw로 기대)
        pairs = list(params.items()) + [("trdDd", date_str)]
        body = "&".join(f"{k}={v}" for k, v in pairs).encode("utf-8")
        req = urllib.request.Request(BASE_URL, data=body, headers=HEADERS, method="POST")
        try:
            with opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as e:
            try:
                body_txt = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                body_txt = ""
            print(f"[FAIL] {name}: HTTP {e.code} body={body_txt!r}")
            failures += 1
            continue
        except Exception as e:
            print(f"[FAIL] {name}: {type(e).__name__}: {e}")
            failures += 1
            continue

        out_path = out_dir / f"{name}_{date_str}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        items = data.get("OutBlock_1", []) if isinstance(data, dict) else []
        print(f"[OK]   {name:<18} {len(items):>5} rows → {out_path.relative_to(out_dir.parent.parent.parent.parent)}")

    return failures


def main() -> int:
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 4, 17)
    out_dir = Path(__file__).resolve().parent
    print(f"KRX 픽스처 캡처 — 대상일={target.isoformat()} 저장위치={out_dir}")
    print("=" * 70)
    failures = capture(target, out_dir)
    print("=" * 70)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
