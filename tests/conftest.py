from __future__ import annotations

import pytest


@pytest.fixture
def user_id() -> str:
    return "1234567890"


@pytest.fixture
def access_token() -> str:
    return "TH_TEST_ACCESS_TOKEN_SECRET"


@pytest.fixture
def base_url() -> str:
    return "https://graph.threads.net/v1.0"
