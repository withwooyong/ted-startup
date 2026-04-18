#!/usr/bin/env python3
"""
API Key Validation Script (값 비노출)

.env.prod에서 API 키를 읽어 3종 API에 테스트 호출만 수행한다.
키 값은 절대 print/log하지 않으며, HTTP 상태 코드와 PASS/FAIL만 출력한다.

Usage:
    python3 scripts/validate_env.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def check_required(env: dict[str, str], keys: list[str]) -> list[str]:
    return [k for k in keys if not env.get(k)]


def check_dart(api_key: str) -> tuple[bool, str]:
    qs = urllib.parse.urlencode({"crtfc_key": api_key, "corp_code": "00126380"})
    url = f"https://opendart.fss.or.kr/api/company.json?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        status = body.get("status")
        if status == "000":
            return True, "status=000 (OK)"
        return False, f"status={status} message={body.get('message', '')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _key_structure(key: str) -> str:
    """키 값 자체는 노출하지 않고 구조적 특성만 반환."""
    import re

    length = len(key)
    if key.startswith("sk-proj-"):
        prefix = "sk-proj-"
    elif key.startswith("sk-svcacct-"):
        prefix = "sk-svcacct-"
    elif key.startswith("sk-admin-"):
        prefix = "sk-admin-"
    elif key.startswith("sk-"):
        prefix = "sk-"
    else:
        prefix = "(sk- 접두사 없음)"
    has_ws = bool(re.search(r"\s", key))
    has_ctrl = bool(re.search(r"[\r\n\t]", key))
    has_quote = any(c in key for c in ['"', "'"])
    flags: list[str] = []
    if has_ws:
        flags.append("공백포함")
    if has_ctrl:
        flags.append("제어문자포함")
    if has_quote:
        flags.append("따옴표포함")
    flag_str = f" 이상징후={','.join(flags)}" if flags else ""
    return f"길이={length} 접두사={prefix}{flag_str}"


def check_openai(api_key: str) -> tuple[bool, str]:
    structure = _key_structure(api_key)
    req = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200, f"HTTP {resp.status} | {structure}"
    except urllib.error.HTTPError as e:
        msg = ""
        try:
            body = json.loads(e.read().decode("utf-8"))
            err = body.get("error", {})
            msg = f" | error.code={err.get('code')} error.type={err.get('type')} error.message={err.get('message')}"
        except Exception:
            pass
        return False, f"HTTP {e.code}{msg} | {structure}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e} | {structure}"


def check_kis_mock(app_key: str, app_secret: str) -> tuple[bool, str]:
    payload = json.dumps(
        {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://openapivts.koreainvestment.com:29443/oauth2/tokenP",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("access_token"):
            return True, f"HTTP {resp.status} (access_token 발급)"
        return False, f"HTTP {resp.status} (access_token 없음)"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    env = load_env(Path(".env.prod"))

    required = [
        "DART_API_KEY",
        "OPENAI_API_KEY",
        "KIS_APP_KEY_MOCK",
        "KIS_APP_SECRET_MOCK",
        "KIS_ACCOUNT_NO_MOCK",
    ]
    missing = check_required(env, required)

    print("=" * 58)
    if missing:
        for k in missing:
            print(f"[FAIL] {k:<22} .env.prod에 누락")
        print("=" * 58)
        return 1

    acct_digits = len(env["KIS_ACCOUNT_NO_MOCK"].replace("-", ""))
    acct_ok = acct_digits >= 8

    results: list[tuple[str, bool, str]] = [
        ("DART", *check_dart(env["DART_API_KEY"])),
        ("OpenAI", *check_openai(env["OPENAI_API_KEY"])),
        (
            "KIS 모의 OAuth",
            *check_kis_mock(env["KIS_APP_KEY_MOCK"], env["KIS_APP_SECRET_MOCK"]),
        ),
        (
            "KIS 계좌번호 형식",
            acct_ok,
            f"숫자 {acct_digits}자리" + (" (OK)" if acct_ok else " (비정상)"),
        ),
    ]

    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name:<22} {detail}")
    print("=" * 58)

    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
