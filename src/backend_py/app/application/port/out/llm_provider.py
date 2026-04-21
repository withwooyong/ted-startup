"""LLMProvider Protocol — AI 리포트 생성용 추상화.

설계 원칙 (§11.2 3-Tier 신뢰 출처):
- Tier1 payload: 공식 API(DART/KRX/ECOS) 원천 숫자·공시 — 리포트 본문의 모든 숫자·사실
- Tier2 payload: web_search 도메인 화이트리스트(옵션) — 정성 이슈·뉴스 컨텍스트
- 분석 모델은 "숫자는 Tier1 만, 정성은 Tier2 만" 인용하도록 프롬프트 강제

현재 구현체: OpenAIProvider (Plan B). 추후 PerplexityProvider / ClaudeProvider 를
동일 Protocol 뒤에 꽂아 AI_PROVIDER 환경변수로 Plan A 전환 가능하게 설계.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlparse

# ---------- Tier 1 (공식 출처 원문) ----------


@dataclass(slots=True)
class Tier1CompanyInfo:
    corp_code: str
    corp_name: str
    ceo_nm: str | None = None
    corp_cls: str | None = None  # Y/K/N/E
    induty_code: str | None = None
    est_dt: str | None = None
    hm_url: str | None = None


@dataclass(slots=True)
class Tier1DisclosureItem:
    report_nm: str
    rcept_dt: str  # YYYYMMDD
    rcept_no: str
    viewer_url: str


@dataclass(slots=True)
class Tier1FinancialItem:
    account_nm: str
    sj_nm: str
    thstrm_nm: str
    thstrm_amount: Decimal
    frmtrm_amount: Decimal | None = None
    currency: str | None = None


@dataclass(slots=True)
class Tier1PricePoint:
    trading_date: date
    close_price: int
    change_rate: Decimal | None = None


@dataclass(slots=True)
class Tier1SignalItem:
    signal_date: date
    signal_type: str
    score: int
    grade: str


@dataclass(slots=True)
class Tier1Payload:
    """공식 출처 전량 — 리포트 본문 숫자·사실의 유일한 원천."""

    stock_code: str
    stock_name: str
    company: Tier1CompanyInfo | None
    disclosures: list[Tier1DisclosureItem] = field(default_factory=list)
    financials: list[Tier1FinancialItem] = field(default_factory=list)
    prices: list[Tier1PricePoint] = field(default_factory=list)
    signals: list[Tier1SignalItem] = field(default_factory=list)


# ---------- Tier 2 (web_search — 정성 컨텍스트) ----------


@dataclass(slots=True)
class Tier2QualitativeItem:
    title: str
    summary: str
    url: str
    published_at: str | None = None  # ISO 8601 or YYYY-MM-DD
    source_domain: str | None = None


# ---------- Output ----------


@dataclass(slots=True)
class ReportSource:
    tier: int  # 1 또는 2
    type: str  # 'dart' | 'krx' | 'ecos' | 'news' | 'official'
    url: str
    label: str
    published_at: str | None = None


@dataclass(slots=True)
class ReportContent:
    summary: str
    strengths: list[str]
    risks: list[str]
    outlook: str
    opinion: str  # BUY / HOLD / SELL / NEUTRAL
    disclaimer: str


@dataclass(slots=True)
class GeneratedReport:
    content: ReportContent
    sources: list[ReportSource]
    provider: str
    model_id: str
    token_in: int | None = None
    token_out: int | None = None
    elapsed_ms: int | None = None


# ---------- Protocol ----------


class LLMProvider(Protocol):
    """AI 리포트 생성 포트. 구현체 간 런타임 전환(Plan A ↔ B) 을 허용."""

    provider_name: str

    async def collect_qualitative(
        self,
        *,
        stock_code: str,
        stock_name: str,
        bgn_de: str,  # YYYYMMDD
        end_de: str,
    ) -> list[Tier2QualitativeItem]:
        """Tier2 정성 정보 수집. web_search 미지원 구현체는 빈 리스트 반환."""
        ...

    async def analyze(
        self,
        *,
        tier1: Tier1Payload,
        tier2: list[Tier2QualitativeItem],
    ) -> GeneratedReport:
        """Tier1+Tier2 → 구조화 리포트. 숫자는 Tier1 만, 정성은 Tier2 만 인용."""
        ...

    async def repackage(self, report: GeneratedReport) -> GeneratedReport:
        """프론트 카드 UI 형태로 재구성. 기본 구현은 passthrough."""
        ...


# ---------- JSON Schema helpers (OpenAI strict output 용) ----------


REPORT_JSON_SCHEMA: dict[str, Any] = {
    "name": "analysis_report",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "strengths", "risks", "outlook", "opinion", "disclaimer", "sources"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 500},
            "strengths": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
            },
            "risks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
            },
            "outlook": {"type": "string", "minLength": 1, "maxLength": 1200},
            "opinion": {
                "type": "string",
                "enum": ["BUY", "HOLD", "SELL", "NEUTRAL"],
            },
            "disclaimer": {"type": "string", "minLength": 1, "maxLength": 400},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    # OpenAI strict mode 는 `required` 에 모든 properties 키를 포함해야 한다.
                    # published_at 은 nullable 이지만 required 엔 들어가야 함 (type: [string, null]).
                    "required": ["tier", "type", "url", "label", "published_at"],
                    "properties": {
                        "tier": {"type": "integer", "enum": [1, 2]},
                        "type": {
                            "type": "string",
                            "enum": ["dart", "krx", "ecos", "news", "official"],
                        },
                        "url": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1, "maxLength": 200},
                        "published_at": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
}


DEFAULT_DISCLAIMER = "본 리포트는 공시·시세 기반 자동 생성물로 투자 참고용이며, 투자 책임은 본인에게 있습니다."


def is_safe_public_url(url: str) -> bool:
    """http/https 스킴 + 유효한 hostname 만 통과. javascript:/ftp://file:/사설 IP
    대역은 별도 필터링 단계에서 추가 가능하지만 여기서는 스킴 경계만 강제한다.

    왜: LLM 응답 및 외부 API 가 돌려준 URL 을 그대로 DB/응답에 흘리면 프론트
    렌더링 시 open-redirect·javascript: XSS·phishing 위험. 저장 전 이 함수로
    1차 필터링.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
