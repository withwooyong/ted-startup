"""글로벌 예외 핸들러 — Java GlobalExceptionHandler 동등."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def _body(status_code: int, message: str) -> dict[str, Any]:
    return {
        "status": status_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ARG001
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", ()))
            message = f"{loc}: {first.get('msg', '유효하지 않은 값입니다')}"
        else:
            message = "요청 본문 검증 실패"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(_body(400, message)),
        )

    @app.exception_handler(ValidationError)
    async def _pyd_validation(request: Request, exc: ValidationError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(_body(400, str(exc))),
        )
