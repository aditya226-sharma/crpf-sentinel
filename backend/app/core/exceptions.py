"""Consistent error envelope used across the API."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("cyberrakshak.errors")


class ApiError(Exception):
    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.http_status = http_status


class NotFoundError(ApiError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found"):
        super().__init__(code, message, status.HTTP_404_NOT_FOUND)


class ForbiddenError(ApiError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "Access denied"):
        super().__init__(code, message, status.HTTP_403_FORBIDDEN)


class UnauthorizedError(ApiError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "Authentication required"):
        super().__init__(code, message, status.HTTP_401_UNAUTHORIZED)


class ConflictError(ApiError):
    def __init__(self, code: str = "CONFLICT", message: str = "Resource already exists"):
        super().__init__(code, message, status.HTTP_409_CONFLICT)


def error_response(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=error_response(exc.code, exc.message))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("INTERNAL_ERROR", "Internal server error"),
        )
