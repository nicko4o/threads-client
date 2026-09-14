from __future__ import annotations

from typing import Final

DEFAULT_THREADS_API_HOST: Final[str] = "https://graph.threads.net/v1.0"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_CONNECT_TIMEOUT_SECONDS: Final[float] = 10.0
DEFAULT_CAROUSEL_CONCURRENCY_LIMIT: Final[int] = 3
DEFAULT_POLL_MAX_ATTEMPTS: Final[int] = 30
DEFAULT_POLL_DELAY_SECONDS: Final[int] = 5
DEFAULT_PUBLISH_MAX_RETRIES: Final[int] = 5
DEFAULT_REQUEST_MAX_RETRIES: Final[int] = 3
DEFAULT_PAGE_SIZE: Final[int] = 25
LOG_RESPONSE_BODY_LIMIT: Final[int] = 500

ERROR_SUBCODE_MEDIA_NOT_READY: Final[int] = 4279009
ERROR_SUBCODE_CAROUSEL_CHILD_NOT_READY: Final[int] = 4279004
MEDIA_NOT_READY_BACKOFF_FACTOR_SECONDS: Final[int] = 3
MAX_TOPIC_TAG_LENGTH: Final[int] = 50
MAX_ERROR_MESSAGE_LENGTH: Final[int] = 500

VALID_CONTAINER_STATUS_STATES: Final[frozenset[str]] = frozenset(
    {"EXPIRED", "ERROR", "FINISHED", "IN_PROGRESS", "PUBLISHED"}
)

RATE_LIMIT_CODES: Final[tuple[int, ...]] = (4, 17, 32, 341, 613)
TRANSIENT_ERROR_CODES: Final[tuple[int, ...]] = (1, 2, 4, 17, 32, 341, 613)
TRANSIENT_MEDIA_SUBCODES: Final[tuple[int, ...]] = (
    ERROR_SUBCODE_MEDIA_NOT_READY,
    ERROR_SUBCODE_CAROUSEL_CHILD_NOT_READY,
)

SENSITIVE_PARAM_KEYS: Final[frozenset[str]] = frozenset(
    {"access_token", "client_secret", "refresh_token", "short_token", "token"}
)
ENV_FILE_PERMISSIONS: Final[int] = 0o600
