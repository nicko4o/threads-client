# threads-client

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Production-grade, async-first Python SDK for the Meta Threads Graph API. Built for automated bots, content publishing pipelines, and social media management.

## Features

- **Async-First Architecture**: Built on `httpx.AsyncClient` with non-blocking I/O.
- **Resilience Engine**:
  - Automatic retry for Meta error subcode `4279009` (Media not ready) with linear backoff.
  - Exponential backoff retry for transient Meta errors (`HTTP 500`, `429`, and error codes `1`, `2`, `4`, `17`, `341`).
  - Container status polling with configurable timeout and delay.
- **Carousel Publishing**: Bounded-concurrency item container creation (`asyncio.Semaphore`), automated multi-container status polling, and one-step publishing.
- **OAuth Token Management**: Exchange short-lived tokens for 60-day long-lived tokens and refresh existing tokens.
- **CLI Utility**: Built-in `threads-client` command for automated `.env` token renewal.
- **Safe Logging**: Automatic masking of access tokens in error logs to prevent secret leakage.
- **Strict Typing**: 100% type-annotated with Pydantic v2 models and strict mypy compliance.

## Installation

```bash
pip install threads-client
```

Or using `uv`:

```bash
uv add threads-client
```

## Quickstart

### 1. Publishing Posts

```python
import asyncio
from threads_client import ThreadsClient
from threads_client.models import CarouselMediaItem

async def main() -> None:
    async with ThreadsClient(user_id="YOUR_USER_ID", access_token="YOUR_ACCESS_TOKEN") as client:
        # 1. Text Post
        result = await client.posts.create(
            text="Hello Threads from Python!",
            topic_tag="Tech",
        )
        print(f"Published post ID: {result.post_id}")

        # 2. Single Image Post
        image_result = await client.posts.create(
            text="Check out this chart!",
            image_url="https://example.com/chart.png",
            topic_tag="Baseball",
        )
        print(f"Published image post ID: {image_result.post_id}")

        # 3. Multi-Media Carousel Post
        carousel_result = await client.posts.create_carousel(
            text="Game Highlights",
            items=[
                CarouselMediaItem(media_type="IMAGE", url="https://example.com/card1.png"),
                CarouselMediaItem(media_type="VIDEO", url="https://example.com/walkoff.mp4"),
            ],
            topic_tag="MLB",
        )
        print(f"Published carousel ID: {carousel_result.post_id}")

asyncio.run(main())
```

### 2. Convenience / Backward-Compatible Aliases

For minimal friction when migrating existing scripts:

```python
async with ThreadsClient(user_id="...", access_token="...") as client:
    post_id = await client.post("Simple text post", topic_tag="News")
    carousel_id = await client.post_carousel("Carousel post", items=[...])
```

### 3. Listing and Deleting Posts

```python
async with ThreadsClient(user_id="YOUR_USER_ID", access_token="YOUR_ACCESS_TOKEN") as client:
    # 1. Automatic cursor pagination across all posts
    async for post in client.posts.iter_posts(limit=25):
        print(f"[{post.id}] {post.text} ({post.timestamp})")

    # 2. Fetch a single page
    page = await client.posts.list(limit=10)
    for post in page.data:
        print(f"[{post.id}] {post.text}")

    # 3. Delete a post
    success = await client.posts.delete(post_id="POST_ID_TO_DELETE")
    print(f"Deleted: {success}")
```

### 4. CLI Token Management

Keep long-lived 60-day tokens fresh automatically:

```bash
# Refresh long-lived token and update .env automatically
threads-client token refresh --env-file .env

# Exchange short-lived token for long-lived token
threads-client token exchange --short-token <SHORT_TOKEN> --app-secret <APP_SECRET> --env-file .env
```

## Error Handling

All SDK exceptions inherit from `ThreadsError`:

```python
from threads_client import ThreadsClient
from threads_client.exceptions import (
    ThreadsAPIError,
    ThreadsAuthenticationError,
    ThreadsMediaProcessingError,
    ThreadsRateLimitError,
    ThreadsTimeoutError,
    ThreadsValidationError,
)

try:
    async with ThreadsClient(...) as client:
        await client.posts.create(...)
except ThreadsAuthenticationError as err:
    print(f"Auth failed: {err}")
except ThreadsRateLimitError as err:
    print(f"Rate limited: {err}")
except ThreadsMediaProcessingError as err:
    print(f"Media container processing failed: {err}")
except ThreadsTimeoutError as err:
    print(f"Polling timed out: {err}")
except ThreadsAPIError as err:
    print(f"API returned status {err.status_code}, code {err.code}: {err.message}")
```

## Development & Testing

```bash
# Run test suite
make test

# Run lint, format, type, and dead code checks
make lint

# Or run individual tools via uv
uv run pytest tests/ -v
uv run ruff check threads_client tests
uv run mypy threads_client tests
uv run vulture threads_client tests
```

## License

MIT License
