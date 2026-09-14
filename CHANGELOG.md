# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Automatic backoff retry protection for Carousel container creation against Meta eventual consistency error `4279004` (`Carousel child not ready`).
- Automatic retry and taxonomy mapping for Meta API rate limit codes `32` (`Page request limit reached`) and `613` (`Calls to api exceeded limit`) via `ThreadsRateLimitError`.
- Transient error tolerance in `PostsResource.poll_container_status` to gracefully absorb temporary network hiccups and 502/504 gateway spikes without prematurely failing the publishing pipeline.
- RFC 3986 root-path resolution in `BaseResource._resolve_url` supporting root-level endpoints such as OAuth token exchange and renewal.
- Infinite loop prevention in `iter_posts` detecting stagnant or repetitive pagination cursors.
- Dedicated unit test coverage for `Transport` (HTTP verbs, network error retry, media delay linear backoff, query params forwarding on POST) and gateway error fallback.

### Fixed
- Fixed unversioned OAuth token endpoints (`/access_token` and `/refresh_access_token`) previously misdirected to `/v1.0/` versioned paths.
- Removed dead code exception catch in `_extract_error_dict` and added defensive message truncation for oversized HTML gateway responses.
- Fixed weak typing in `Transport` dispatch methods and eliminated scope creep where non-POST requests could carry invalid body payloads.

### Changed
- Unified retry orchestration within `Transport`, eliminating duplicated manual retry loops in `PostsResource.publish_container` and restoring default retry capabilities in `PostsResource.get_container_status`.

## [0.2.0] - 2026-09-04

### Added
- Atomic container status probe `PostsResource.get_container_status(container_id)` returning `ContainerStatus` for non-blocking inspection without polling delays.
- Domain constant `VALID_CONTAINER_STATUS_STATES` validating Meta container status values (`EXPIRED`, `ERROR`, `FINISHED`, `IN_PROGRESS`, `PUBLISHED`).

### Changed
- Refactored `PostsResource.poll_container_status` to orchestrate status polling on top of `get_container_status`.

## [0.1.0] - 2026-09-04

### Added
- Modular architecture with dedicated `transport/` (`Transport`, `mask_url`, `mask_text`, `retry`) and `resources/` (`BaseResource`, `PostsResource`, `TokensResource`) subpackages.
- Async generator `iter_posts()` on `PostsResource` providing automated cursor-based pagination traversal across all user posts.
- Comprehensive credential redaction in HTTP error logs across URL query strings, request payloads, and response bodies for all sensitive keys.
- Atomic file replacement (`tempfile` + `os.replace`) with strict `0o600` file permissions in `threads-client` CLI.
- Fail-fast authentication validation raising `ThreadsAuthenticationError` when post operations are attempted without an access token.
- Strict mutual exclusivity validation in `PostsResource.create` preventing simultaneous `image_url` and `video_url` payloads.
- Immediate terminal failure handling for container status `EXPIRED` in `poll_container_status`.
- Credential Single Source of Truth (SSOT) via `ClientContext` allowing dynamic updates to `client.access_token` and `client.user_id` to propagate seamlessly to underlying resources.
- Named constant `DEFAULT_PAGE_SIZE` (25) in `config.py` eliminating magic numbers in pagination endpoints.
- PEP 561 typing support with `threads_client/py.typed` marker file enabling downstream type checkers (e.g. `mypy`, `pyright`).
- Strongly typed pagination models `ThreadsPaging` and `ThreadsPagingCursors` supporting `cursors.before`, `cursors.after`, `next`, and `previous` pagination URLs.
- Strongly typed `ContainerStatusState` Literal enforcement on `ContainerStatus.status`.
- Developer workflow tooling: `Makefile` targets (`install`, `lint`, `format`, `mypy`, `vulture`, `test`, `build`, `clean`).
- GitHub Actions workflows for multi-python CI matrix testing (`.github/workflows/ci.yml`) and PyPA Trusted Publishing via OIDC (`.github/workflows/publish.yml`).

### Changed
- Refactored `ThreadsClient` into a clean, lightweight Facade (< 100 LOC) delegating transport and resource logic to modular components.
- Decoupled `ThreadsClient` authentication initialization: `access_token` is now optional (defaulting `user_id="me"`), allowing unauthenticated OAuth token exchanges.
- Replaced custom string-matching helper `find_by_signature` with generic async iterator `iter_posts()`.
- Enhanced CLI error handling to catch `ThreadsAPIError` gracefully and exit with code 1 instead of emitting raw Python tracebacks.

### Fixed
- Fixed 150-second hang on expired media containers by detecting `EXPIRED` terminal status immediately.
- Fixed potential credential leakage of `client_secret` and `short_token` in HTTP error logs.
- Fixed non-atomic file writing and overly permissive file mode when saving tokens in `.env`.
