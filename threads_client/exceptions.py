from __future__ import annotations

import httpx

from threads_client.config import ERROR_SUBCODE_MEDIA_NOT_READY, TRANSIENT_ERROR_CODES


class ThreadsError(Exception):
    """Base exception for all threads-client errors."""


class ThreadsValidationError(ThreadsError):
    """Raised when client-side parameter validation fails."""


class ThreadsTimeoutError(ThreadsError):
    """Raised when a container processing or polling operation times out."""


class ThreadsAPIError(ThreadsError):
    """Base exception for Meta Graph API error responses."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
        error_type: str | None = None,
        is_transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.subcode = subcode
        self.error_type = error_type
        self.is_transient = is_transient

    @property
    def is_media_not_ready(self) -> bool:
        return self.subcode == ERROR_SUBCODE_MEDIA_NOT_READY

    @classmethod
    def from_http_error(cls, error: httpx.HTTPStatusError) -> ThreadsAPIError:
        resp = error.response
        if resp is None:
            return cls(message=str(error))

        status_code = resp.status_code
        err_dict = _extract_error_dict(resp)
        message = str(err_dict.get("message") or resp.text or f"HTTP error {status_code}")
        raw_code = err_dict.get("code")
        code = int(raw_code) if isinstance(raw_code, (int, str)) and str(raw_code).isdigit() else None
        raw_subcode = err_dict.get("error_subcode")
        subcode = int(raw_subcode) if isinstance(raw_subcode, (int, str)) and str(raw_subcode).isdigit() else None
        error_type = str(err_dict["type"]) if "type" in err_dict else None
        is_transient = _is_transient_error(status_code, code, err_dict)

        if subcode == ERROR_SUBCODE_MEDIA_NOT_READY:
            return ThreadsMediaProcessingError(
                message=message,
                status_code=status_code,
                code=code,
                subcode=subcode,
                error_type=error_type,
                is_transient=False,
            )
        if status_code == 401 or code == 190:
            return ThreadsAuthenticationError(
                message=message,
                status_code=status_code,
                code=code,
                subcode=subcode,
                error_type=error_type,
                is_transient=is_transient,
            )
        if status_code == 429 or code in (4, 17, 341):
            return ThreadsRateLimitError(
                message=message,
                status_code=status_code,
                code=code,
                subcode=subcode,
                error_type=error_type,
                is_transient=True,
            )

        return cls(
            message=message,
            status_code=status_code,
            code=code,
            subcode=subcode,
            error_type=error_type,
            is_transient=is_transient,
        )


class ThreadsAuthenticationError(ThreadsAPIError):
    """Raised when authentication fails or token is expired."""


class ThreadsRateLimitError(ThreadsAPIError):
    """Raised when rate limits are exceeded."""


class ThreadsMediaProcessingError(ThreadsAPIError):
    """Raised when container processing fails or media format is unsupported."""


def _extract_error_dict(resp: httpx.Response) -> dict[str, object]:
    try:
        data = resp.json()
        if isinstance(data, dict) and "error" in data and isinstance(data["error"], dict):
            return data["error"]
        if isinstance(data, dict):
            return data
    except (ValueError, KeyError, AttributeError):
        pass
    return {}


def _is_transient_error(status_code: int, code: int | None, err_dict: dict[str, object]) -> bool:
    if status_code >= 500 or status_code == 429:
        return True
    if err_dict.get("is_transient") is True:
        return True
    return code is not None and code in TRANSIENT_ERROR_CODES
