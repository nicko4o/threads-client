# Contributing to threads-client

Thank you for contributing to `threads-client`! We welcome bug reports, feature suggestions, and pull requests.

## Development Setup

This project uses [`uv`](https://github.com/astral-sh/uv) as the single tool for dependency management, virtual environments, and packaging.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nicko4o/threads-client.git
   cd threads-client
   ```

2. **Install dependencies**:
   ```bash
   make install
   # or: uv sync --locked
   ```

## Development Commands

All common tasks are automated via `make`:

```bash
# Run tests
make test

# Run linter and formatter check
make lint

# Auto-format and fix lint issues
make format

# Run static type checking (strict mode)
make mypy

# Build distribution packages
make build
```

## Engineering Rules & Standards

- **Python Version**: Python 3.11+.
- **Type Annotations**: 100% type-annotated code is required. All modules must pass `mypy --strict`.
- **No Token Leakage**: Never log user access tokens or secrets. Any HTTP request/response logging must redact credentials.
- **Mock-Only Testing in CI**: Tests must use `respx` to mock Meta Graph API HTTP responses. Do not hit live Meta endpoints in unit or integration tests.
- **Function Size & Complexity**:
  - Keep functions small (<= 50 LOC).
  - Flatten nested conditionals (<= 3 levels) using guard clauses or early returns.
  - Avoid `Any` or weak typing; define explicit Pydantic v2 models or types.

## Git & Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: ...` for new features or public API additions.
- `fix: ...` for bug fixes or error handling improvements.
- `refactor: ...` for code restructuring without behavioral change.
- `test: ...` for test additions or updates.
- `docs: ...` for documentation changes.
- `ci: ...` for CI/CD workflow changes.

## Pull Request Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Implement your changes following the rules above.
3. Verify that `make lint`, `make mypy`, and `make test` pass locally.
4. Update `CHANGELOG.md` under the `## [Unreleased]` section.
5. Open a Pull Request on GitHub and fill out the PR template.
