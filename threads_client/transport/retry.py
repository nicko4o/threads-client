from __future__ import annotations

from threads_client.config import MEDIA_NOT_READY_BACKOFF_FACTOR_SECONDS


def calc_exponential_backoff(attempt: int) -> float:
    """Calculate exponential backoff delay in seconds."""
    return float(2**attempt)


def calc_media_not_ready_backoff(attempt: int) -> float:
    """Calculate linear backoff delay for media processing in seconds."""
    return float(MEDIA_NOT_READY_BACKOFF_FACTOR_SECONDS * (attempt + 1))
