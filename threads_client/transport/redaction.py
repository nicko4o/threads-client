from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from threads_client.config import SENSITIVE_PARAM_KEYS

_REDACTED = "[REDACTED]"


def mask_url(url: str) -> str:
    """Mask sensitive query parameters in a URL."""
    if not url:
        return url

    parts = urlsplit(url)
    if not parts.query:
        return url

    query_params = parse_qsl(parts.query, keep_blank_values=True)
    masked_params = [(k, _REDACTED if k.lower() in SENSITIVE_PARAM_KEYS else v) for k, v in query_params]
    masked_query = urlencode(masked_params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, masked_query, parts.fragment))


def mask_text(text: str, extra_secrets: Sequence[str] = ()) -> str:
    """Mask sensitive keys in raw JSON/text and any explicit secret tokens."""
    if not text:
        return text

    masked = text
    for secret in extra_secrets:
        if secret and len(secret) >= 4:
            masked = masked.replace(secret, _REDACTED)

    # Regex mask for sensitive key-value pairs in JSON text (e.g. "access_token": "...")
    for key in SENSITIVE_PARAM_KEYS:
        pattern = rf'("{key}"\s*:\s*)"([^"]+)"'
        masked = re.sub(pattern, rf'\1"{_REDACTED}"', masked, flags=re.IGNORECASE)

    return masked
