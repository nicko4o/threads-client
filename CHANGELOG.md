# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-04

### Added
- PEP 561 typing support with `threads_client/py.typed` marker file enabling downstream type checkers (e.g. `mypy`, `pyright`).
- Strongly typed pagination models `ThreadsPaging` and `ThreadsPagingCursors` supporting `cursors.before`, `cursors.after`, `next`, and `previous` pagination URLs with forward-compatible dynamic attribute support.
- Core `ThreadsClient` async client supporting context manager lifecycle (`async with ThreadsClient(...)`).
- Resource-oriented architecture with `PostsResource` (`client.posts`) and `TokensResource` (`client.tokens`).
- Full support for publishing text posts, single image posts, video posts, and multi-asset carousel posts.
- Bounded-concurrency carousel container creation with `asyncio.Semaphore` and parallel status polling.
- Resilience engine with automatic linear backoff for Meta error subcode `4279009` (Media not ready) and exponential backoff for transient errors (`500`, `429`, codes `1`, `2`, `4`, `17`, `341`).
- Post lifecycle polling (`poll_container_status`) and publication retry mechanisms.
- Post deletion (`client.posts.delete`) and cursor-based post listing (`client.posts.list`).
- Post signature search helper (`find_by_signature`) for idempotent publishing workflows.
- OAuth token exchange (`TokensResource.exchange`) and 60-day token refresh (`TokensResource.refresh`).
- Built-in `threads-client` CLI with `token refresh` and `token exchange` commands supporting in-place `.env` updating.
- Strongly typed Pydantic v2 models (`CarouselMediaItem`, `PostCreateResult`, `ThreadsPost`, `TokenInfo`).
- Structured exception hierarchy (`ThreadsError`, `ThreadsAPIError`, `ThreadsAuthenticationError`, `ThreadsRateLimitError`, `ThreadsMediaProcessingError`, `ThreadsTimeoutError`, `ThreadsValidationError`).
- Automatic access token redaction in HTTP error logs.
- Developer workflow tooling: `Makefile` targets (`install`, `lint`, `format`, `mypy`, `vulture`, `test`, `build`, `clean`).
- GitHub Actions workflows for multi-python CI matrix testing (`.github/workflows/ci.yml`) and PyPA Trusted Publishing via OIDC (`.github/workflows/publish.yml`).
- Repository governance templates: `pull_request_template.md`, issue templates (`bug_report.yml`, `feature_request.yml`), `CONTRIBUTING.md`, and `SECURITY.md`.
- Dead code static analysis using `vulture` with 80% confidence threshold integrated into `make lint` and CI.
- MIT License file added to repository root.

### Changed
- Container status polling (`poll_container_status`) now queries Meta API immediately on first check (check-first), eliminating unnecessary 5-second initial latency for fast-completing containers.
- Simplified API error response parsing in `ThreadsAPIError.from_http_error` by extracting `_resolve_error_class` dispatch helper and narrowing exception trapping to `ValueError`.
- Refactored `ThreadsPostPage.paging` from untyped dictionary to validated `ThreadsPaging` model, and replaced `_exc_tb: Any` in `ThreadsClient.__aexit__` with `TracebackType | None`.
- Flattened package layout by removing `src/` hierarchy and placing `threads_client/` directly at repository root.
- Consolidated models, resources, and CLI modules into flat module structure (`models.py`, `client.py`, `cli.py`).

### Fixed
- Missing `py.typed` preventing downstream projects from resolving type annotations.
- Missing repository, issue tracker, and documentation URLs on PyPI project landing page.
