"""OpenAI Chat Completions 기반 LLMProvider 구현.

설계:
- httpx.AsyncClient 로 `/v1/chat/completions` 직접 호출 (openai SDK 미의존 — DartClient /
  KisClient / TelegramClient 와 동일 패턴, MockTransport 주입 테스트 용이).
- strict JSON 출력: `response_format = {"type": "json_schema", ...}` 사용.
- 역할 분리 프롬프트: 숫자는 Tier1 만, 정성은 Tier2 만 인용하도록 지시.
- MVP 범위:
    * `collect_qualitative`: web_search 미활성 환경에서는 빈 리스트 반환.
      (Responses API + web_search_preview 는 추후 openai_model_collector + tools 로 확장)
    * `analyze`: 실제 호출. Tier1 dataclass 를 간결한 JSON 페이로드로 직렬화해 user 메시지로 주입.
    * `repackage`: 기본 passthrough. nano 로 카드 UI 재변환은 추후.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from decimal import Decimal
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.port.out.llm_provider import (
    DEFAULT_DISCLAIMER,
    REPORT_JSON_SCHEMA,
    GeneratedReport,
    LLMProvider,
    ReportContent,
    ReportSource,
    Tier1Payload,
    Tier2QualitativeItem,
)
from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_PROVIDER = "openai"


class OpenAIProviderError(Exception):
    pass


class OpenAIProviderNotConfigured(OpenAIProviderError):
    pass


def _jsonable(value: Any) -> Any:
    """Decimal/date 포함 페이로드를 JSON 직렬화 가능한 원시 타입으로 변환."""
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


SYSTEM_PROMPT = """당신은 한국 주식 시장 애널리스트입니다. 다음 규칙을 반드시 준수합니다.

[역할 분리 규칙]
- 재무 수치·공시 사실은 제공된 Tier1 payload(DART/KRX) 에서만 인용합니다.
- 정성 이슈·시장 반응은 제공된 Tier2 payload(web_search 결과) 에서만 인용합니다.
- 일반 지식이나 추론으로 숫자를 생성하지 않습니다.
- Tier1 에 없는 재무 수치가 필요하다면 '자료 부재' 로 명시합니다.

[출력 포맷]
- 반드시 JSON 스키마를 준수합니다.
- strengths/risks 는 3~5개, 각 1~2문장으로 간결하게.
- outlook 은 3~6문장 한국어 단락.
- opinion 은 BUY/HOLD/SELL/NEUTRAL 중 택1.
- sources 배열에 본문 근거 URL 을 tier(1/2) 와 함께 최소 3건 이상 나열합니다.
- disclaimer 는 '투자 참고용·투자 책임은 본인에게 있습니다' 를 포함합니다.
"""


class OpenAIProvider:
    """Plan B 기본 구현. provider_name 은 'openai' 고정."""

    provider_name: str = _PROVIDER

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self._settings = s
        self._api_key = s.openai_api_key
        self._model_flagship = s.openai_model_flagship
        self._model_collector = s.openai_model_collector
        self._model_nano = s.openai_model_nano
        self._web_search_enabled = s.ai_report_web_search_enabled
        timeout = httpx.Timeout(
            connect=5.0, read=s.openai_request_timeout_seconds,
            write=s.openai_request_timeout_seconds, pool=5.0,
        )
        self._client = httpx.AsyncClient(
            base_url=s.openai_base_url, timeout=timeout, transport=transport
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenAIProvider":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # LLMProvider protocol
    # ------------------------------------------------------------------

    async def collect_qualitative(
        self,
        *,
        stock_code: str,
        stock_name: str,
        bgn_de: str,
        end_de: str,
    ) -> list[Tier2QualitativeItem]:
        """MVP: web_search 비활성 시 빈 리스트. 활성화 경로는 Responses API + tools 로 추가 예정."""
        if not self._web_search_enabled:
            logger.debug("Tier2 web_search 비활성 — 빈 리스트 반환 (stock=%s)", stock_code)
            return []
        # 추후: /v1/responses + {"type":"web_search_preview", "filters":{"allowed_domains":[...]}}
        logger.warning("Tier2 web_search 활성이나 Responses API 연동 미구현 — 현재 버전은 빈 반환")
        return []

    async def analyze(
        self,
        *,
        tier1: Tier1Payload,
        tier2: list[Tier2QualitativeItem],
    ) -> GeneratedReport:
        if not self.configured:
            raise OpenAIProviderNotConfigured("OPENAI_API_KEY 누락")

        tier1_json = _jsonable(asdict(tier1))
        tier2_json = _jsonable([asdict(item) for item in tier2])
        user_content = (
            f"분석 대상: {tier1.stock_code} {tier1.stock_name}\n\n"
            f"[Tier1 payload — 숫자·공시 원문]\n{json.dumps(tier1_json, ensure_ascii=False)}\n\n"
            f"[Tier2 payload — 정성 이슈(정성만 인용)]\n{json.dumps(tier2_json, ensure_ascii=False)}\n\n"
            "위 두 payload 만 근거로 한국어 분석 리포트를 JSON 스키마에 맞춰 생성하세요."
        )

        payload = {
            "model": self._model_flagship,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": REPORT_JSON_SCHEMA,
            },
            "temperature": 0.2,
        }

        start = time.monotonic()
        body = await self._post_json("/chat/completions", payload)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        content_text = self._extract_content(body)
        try:
            parsed: dict[str, Any] = json.loads(content_text)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError(f"strict JSON 파싱 실패: {exc}") from exc

        usage = body.get("usage") or {}
        return GeneratedReport(
            content=ReportContent(
                summary=str(parsed.get("summary", "")),
                strengths=list(parsed.get("strengths", [])),
                risks=list(parsed.get("risks", [])),
                outlook=str(parsed.get("outlook", "")),
                opinion=str(parsed.get("opinion", "HOLD")),
                disclaimer=str(parsed.get("disclaimer", DEFAULT_DISCLAIMER)),
            ),
            sources=[
                ReportSource(
                    tier=int(s.get("tier", 1)),
                    type=str(s.get("type", "dart")),
                    url=str(s.get("url", "")),
                    label=str(s.get("label", "")),
                    published_at=s.get("published_at"),
                )
                for s in parsed.get("sources", [])
            ],
            provider=_PROVIDER,
            model_id=self._model_flagship,
            token_in=usage.get("prompt_tokens"),
            token_out=usage.get("completion_tokens"),
            elapsed_ms=elapsed_ms,
        )

    async def repackage(self, report: GeneratedReport) -> GeneratedReport:
        """MVP passthrough. 추후 nano 로 카드 UI 변환 추가."""
        return report

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        reraise=True,
    )
    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(path, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise OpenAIProviderError(
                f"OpenAI HTTP {resp.status_code} path={path} body={resp.text[:400]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise OpenAIProviderError(f"OpenAI 응답 JSON 파싱 실패: {resp.text[:400]}") from exc

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            raise OpenAIProviderError(f"choices 부재: {body}")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OpenAIProviderError(f"content 비어있음: {body}")
        return content


