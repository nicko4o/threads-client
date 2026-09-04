.PHONY: help install lint format mypy test build clean

help:
	@echo "threads-client developer commands:"
	@echo "  make install     Install all dependencies via uv"
	@echo "  make lint        Run ruff linter and format check"
	@echo "  make format      Auto-format code with ruff"
	@echo "  make mypy        Run strict static type analysis"
	@echo "  make test        Run full pytest test suite"
	@echo "  make build       Build source distribution and wheel via uv"
	@echo "  make clean       Remove build artifacts and caches"

install:
	uv sync --locked --all-extras

lint:
	uv run ruff check threads_client tests
	uv run ruff format --check threads_client tests
	uv run mypy threads_client tests

format:
	uv run ruff check --fix threads_client tests
	uv run ruff format threads_client tests

mypy:
	uv run mypy threads_client tests

test:
	uv run pytest tests/ -v

build:
	uv build

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/
